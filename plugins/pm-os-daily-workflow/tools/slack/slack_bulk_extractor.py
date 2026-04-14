#!/usr/bin/env python3
"""
Slack Bulk Extractor (v5.0)

Extracts months of Slack messages from priority channels.
Saves raw JSON by channel/week with state tracking for resumability.

Ported from v4.x slack_bulk_extractor.py — channel tiers loaded from config,
auth via connector_bridge, paths via path_resolver.

Usage:
    python slack_bulk_extractor.py [--channels TIER] [--days DAYS] [--dry-run]
    python slack_bulk_extractor.py --resume
    python slack_bulk_extractor.py --status
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# v5 shared utils
try:
    from pm_os_base.tools.core.config_loader import get_config
    from pm_os_base.tools.core.connector_bridge import get_auth
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        _base = __import__("pathlib").Path(__file__).resolve().parent.parent.parent.parent
        sys.path.insert(0, str(_base / "pm-os-base" / "tools" / "core"))
        from config_loader import get_config
        from connector_bridge import get_auth
        from path_resolver import get_paths
    except ImportError:
        logger.error("Cannot import pm_os_base core modules")
        raise


# ============================================================================
# PATHS — all from path_resolver
# ============================================================================

def _get_base_dir() -> Path:
    return get_paths().brain / "Inbox" / "Slack"

def _get_raw_dir() -> Path:
    return _get_base_dir() / "Raw"

def _get_state_file() -> Path:
    return _get_base_dir() / "extraction_state.json"


# Rate limiting — from config with defaults
def _get_rate_limit_delay() -> int:
    return get_config().get("integrations.slack.rate_limit_delay", 3)

def _get_rate_limit_backoff() -> int:
    return get_config().get("integrations.slack.rate_limit_backoff", 30)


def _get_channel_tiers() -> dict:
    """Load channel tiers from config — ZERO hardcoded channel IDs/names."""
    return get_config().get("integrations.slack.channel_tiers", {})


# ============================================================================
# SLACK CLIENT
# ============================================================================

def _get_slack_client():
    """Get authenticated Slack client via connector_bridge."""
    from slack_sdk import WebClient

    auth = get_auth("slack")
    if auth.source == "env":
        return WebClient(token=auth.token)
    elif auth.source == "connector":
        return WebClient(token=auth.token) if auth.token else None
    else:
        logger.error("Slack auth not available: %s", auth.help_message)
        raise ValueError(auth.help_message)


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

def load_state() -> dict:
    """Load extraction state from file."""
    state_file = _get_state_file()
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "started_at": None,
        "last_updated": None,
        "channels_completed": [],
        "channels_in_progress": {},
        "total_messages": 0,
        "total_threads": 0,
    }


def save_state(state: dict) -> None:
    """Save extraction state to file."""
    state["last_updated"] = datetime.utcnow().isoformat() + "Z"
    state_file = _get_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def print_status(state: dict) -> None:
    """Print current extraction status."""
    print("=" * 60)
    print("SLACK BULK EXTRACTION STATUS")
    print("=" * 60)
    print("Started: %s" % state.get("started_at", "Not started"))
    print("Last Updated: %s" % state.get("last_updated", "N/A"))
    print("Total Messages: %s" % "{:,}".format(state.get("total_messages", 0)))
    print("Total Threads: %s" % "{:,}".format(state.get("total_threads", 0)))
    print("Channels Completed: %d" % len(state.get("channels_completed", [])))

    in_progress = state.get("channels_in_progress", {})
    if in_progress:
        print("\nIn Progress (%d):" % len(in_progress))
        for channel_id, info in in_progress.items():
            print("  - %s: Week %s" % (info.get("name", channel_id), info.get("current_week", "?")))

    completed = state.get("channels_completed", [])
    if completed:
        print("\nCompleted (%d):" % len(completed))
        for ch in completed[:10]:
            print("  - %s" % ch)
        if len(completed) > 10:
            print("  ... and %d more" % (len(completed) - 10))

    print("=" * 60)


# ============================================================================
# EXTRACTION LOGIC
# ============================================================================

def get_weeks(start_date: datetime, end_date: datetime) -> List[Tuple]:
    """Generate list of (week_start, week_end, week_label) tuples."""
    weeks = []
    current = start_date - timedelta(days=start_date.weekday())

    while current < end_date:
        week_end = min(current + timedelta(days=7), end_date)
        week_num = current.isocalendar()[1]
        week_label = "%d-W%02d" % (current.year, week_num)
        weeks.append((current, week_end, week_label))
        current = week_end

    return weeks


def fetch_thread_replies(client, channel_id: str, thread_ts: str) -> list:
    """Fetch all replies in a thread (excluding parent)."""
    from slack_sdk.errors import SlackApiError

    replies = []
    cursor = None

    while True:
        try:
            response = client.conversations_replies(
                channel=channel_id, ts=thread_ts, cursor=cursor, limit=200
            )
            batch = response.get("messages", [])
            if cursor is None and len(batch) > 1:
                replies.extend(batch[1:])
            elif cursor:
                replies.extend(batch)

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
            time.sleep(1)

        except SlackApiError as e:
            if e.response["error"] == "ratelimited":
                retry_after = int(e.response.headers.get("Retry-After", 5))
                time.sleep(retry_after)
                continue
            else:
                break

    return replies


def fetch_messages_for_period(
    client, channel_id: str, start_ts: float, end_ts: float,
    include_threads: bool = True,
) -> Tuple[list, int]:
    """
    Fetch all messages in a channel for a time period.

    Returns:
        Tuple of (messages, thread_count)
    """
    from slack_sdk.errors import SlackApiError

    messages = []
    thread_count = 0
    cursor = None
    rate_limit_delay = _get_rate_limit_delay()
    rate_limit_backoff = _get_rate_limit_backoff()

    while True:
        try:
            response = client.conversations_history(
                channel=channel_id,
                oldest=str(start_ts),
                latest=str(end_ts),
                cursor=cursor,
                limit=200,
            )
            batch = response.get("messages", [])
            messages.extend(batch)

            if include_threads:
                for msg in batch:
                    if msg.get("reply_count", 0) > 0:
                        thread_ts = msg.get("ts")
                        replies = fetch_thread_replies(client, channel_id, thread_ts)
                        msg["_thread_replies"] = replies
                        thread_count += len(replies)

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
            time.sleep(rate_limit_delay)

        except SlackApiError as e:
            if e.response["error"] == "ratelimited":
                retry_after = int(
                    e.response.headers.get("Retry-After", rate_limit_backoff)
                )
                logger.warning("Rate limited, waiting %ss...", retry_after)
                time.sleep(retry_after)
                continue
            elif e.response["error"] == "channel_not_found":
                logger.warning("Channel not found: %s", channel_id)
                return [], 0
            elif e.response["error"] == "not_in_channel":
                logger.warning("Bot not in channel: %s", channel_id)
                return [], 0
            else:
                logger.error("Error: %s", e.response["error"])
                raise

    return messages, thread_count


def save_raw_messages(
    channel_id: str, channel_name: str, week_label: str, messages: list,
) -> Path:
    """Save raw messages to JSON file."""
    channel_dir = _get_raw_dir() / channel_id
    channel_dir.mkdir(parents=True, exist_ok=True)

    output_file = channel_dir / ("%s.json" % week_label)

    data = {
        "channel_id": channel_id,
        "channel_name": channel_name,
        "week": week_label,
        "extracted_at": datetime.utcnow().isoformat() + "Z",
        "message_count": len(messages),
        "messages": messages,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return output_file


def extract_channel(
    client, channel_id: str, channel_name: str,
    start_date: datetime, end_date: datetime,
    state: dict, dry_run: bool = False,
) -> Tuple[int, int]:
    """
    Extract all messages from a channel for the given period.

    Returns:
        Tuple of (total_messages, total_threads)
    """
    weeks = get_weeks(start_date, end_date)
    total_messages = 0
    total_threads = 0

    channel_state = state.get("channels_in_progress", {}).get(channel_id, {})
    resume_week = channel_state.get("current_week")

    logger.info("=" * 60)
    logger.info("Channel: #%s (%s)", channel_name, channel_id)
    logger.info("Period: %s to %s", start_date.date(), end_date.date())
    logger.info("Weeks: %d", len(weeks))
    if resume_week:
        logger.info("Resuming from: %s", resume_week)

    state.setdefault("channels_in_progress", {})[channel_id] = {
        "name": channel_name,
        "started_at": datetime.utcnow().isoformat() + "Z",
        "total_weeks": len(weeks),
        "current_week": None,
    }
    save_state(state)

    skip_until_resume = resume_week is not None

    for week_start, week_end, week_label in weeks:
        if skip_until_resume:
            if week_label == resume_week:
                skip_until_resume = False
            else:
                continue

        state["channels_in_progress"][channel_id]["current_week"] = week_label
        save_state(state)

        if dry_run:
            logger.info("  [DRY RUN] Would extract: %s", week_label)
            continue

        logger.info("  Extracting: %s...", week_label)
        start_ts = week_start.timestamp()
        end_ts = week_end.timestamp()

        messages, thread_count = fetch_messages_for_period(
            client, channel_id, start_ts, end_ts
        )

        if messages:
            output_file = save_raw_messages(
                channel_id, channel_name, week_label, messages
            )
            logger.info(
                "    %d messages, %d threads -> %s",
                len(messages), thread_count, output_file.name,
            )
            total_messages += len(messages)
            total_threads += thread_count
        else:
            logger.info("    0 messages")

        time.sleep(_get_rate_limit_delay())

    if channel_id in state.get("channels_in_progress", {}):
        del state["channels_in_progress"][channel_id]

    state.setdefault("channels_completed", []).append(channel_name)
    state["total_messages"] = state.get("total_messages", 0) + total_messages
    state["total_threads"] = state.get("total_threads", 0) + total_threads
    save_state(state)

    logger.info(
        "Channel complete: %d messages, %d threads", total_messages, total_threads
    )
    return total_messages, total_threads


def run_extraction(
    tiers: List[str], days: int = 180,
    dry_run: bool = False, resume: bool = False,
) -> None:
    """Run the full extraction pipeline."""
    client = _get_slack_client()
    state = load_state()

    if not state.get("started_at"):
        state["started_at"] = datetime.utcnow().isoformat() + "Z"
        save_state(state)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    logger.info("=" * 60)
    logger.info("SLACK BULK EXTRACTION")
    logger.info(
        "Period: %s to %s (%d days)", start_date.date(), end_date.date(), days
    )
    logger.info("Tiers: %s", ", ".join(tiers))
    logger.info("Dry Run: %s", dry_run)
    logger.info("Resume: %s", resume)

    # Gather channels from config — ZERO hardcoded values
    channel_tiers = _get_channel_tiers()
    channels = []
    for tier in tiers:
        tier_config = channel_tiers.get(tier, {})
        channels.extend(tier_config.get("channels", []))

    logger.info("Channels: %d", len(channels))

    if resume:
        completed = set(state.get("channels_completed", []))
        channels = [ch for ch in channels if ch.get("name") not in completed]
        logger.info("Remaining: %d (after filtering completed)", len(channels))

    grand_total_messages = 0
    grand_total_threads = 0

    for channel in channels:
        try:
            messages, threads = extract_channel(
                client,
                channel.get("id", ""),
                channel.get("name", ""),
                start_date, end_date,
                state, dry_run,
            )
            grand_total_messages += messages
            grand_total_threads += threads
        except Exception as e:
            logger.error("Error extracting %s: %s", channel.get("name", ""), e)
            continue

    logger.info("=" * 60)
    logger.info("EXTRACTION COMPLETE")
    logger.info(
        "This run: %s messages, %s threads",
        "{:,}".format(grand_total_messages),
        "{:,}".format(grand_total_threads),
    )
    logger.info(
        "Total (all runs): %s messages",
        "{:,}".format(state.get("total_messages", 0)),
    )
    logger.info(
        "Channels completed: %d", len(state.get("channels_completed", []))
    )


def main() -> None:
    """CLI entry point."""
    # Discover available tiers from config for --help
    available_tiers = list(_get_channel_tiers().keys()) or ["tier1", "tier2", "tier3"]

    parser = argparse.ArgumentParser(
        description="Bulk extract Slack messages for Brain enrichment"
    )
    parser.add_argument(
        "--channels", default="tier1",
        help="Channel tier to extract (configured tiers: %s)" % ", ".join(available_tiers),
    )
    parser.add_argument(
        "--days", type=int, default=180,
        help="Days of history to extract (default: 180)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be extracted without making API calls",
    )
    parser.add_argument(
        "--resume", action="store_true", help="Resume from last extraction state"
    )
    parser.add_argument(
        "--status", action="store_true", help="Show extraction status and exit"
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.status:
        state = load_state()
        print_status(state)
        return

    if args.channels == "all":
        tiers = list(_get_channel_tiers().keys())
    else:
        tiers = [args.channels]

    run_extraction(
        tiers=tiers, days=args.days, dry_run=args.dry_run, resume=args.resume
    )


if __name__ == "__main__":
    main()
