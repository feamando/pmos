#!/usr/bin/env python3
"""
Slack Bulk Extractor - Phase 1

Extracts 6 months of Slack messages from priority channels.
Saves raw JSON by channel/week with state tracking for resumability.

Usage:
    python3 slack_bulk_extractor.py [--channels TIER] [--days DAYS] [--dry-run]

Examples:
    python3 slack_bulk_extractor.py --channels tier1 --days 180
    python3 slack_bulk_extractor.py --resume
    python3 slack_bulk_extractor.py --status
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Add parent directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

load_dotenv(override=True)

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = config_loader.get_root_path() / "user" / "brain" / "Inbox" / "Slack"
RAW_DIR = BASE_DIR / "Raw"
STATE_FILE = BASE_DIR / "extraction_state.json"

# Channel Priority Tiers
CHANNEL_TIERS = {
    "tier1": {
        "description": "High Value - Leadership & Squad channels",
        "channels": [
            {"id": "C06CT0185T3", "name": "tribe-growth-division-leads-internal"},
            {"id": "C06CE7FB951", "name": "tribe-growth-division-internal"},
            {"id": "C08KU0F8EF4", "name": "tribe-growth-division-product"},
            {"id": "C03DDD4R537", "name": "squad-nv-meal-kit"},
            {"id": "C04FVDBJZCK", "name": "squad-nv-pet-food"},
            {"id": "C09QXQC2C7Q", "name": "squad-rte-vms-business-metrics"},
            {"id": "C09NKC5J2GL", "name": "squad-market-io"},
        ],
    },
    "tier2": {
        "description": "Medium Value - Product & Cross-functional",
        "channels": [
            {"id": "C02RQHFTJ0V", "name": "meal-kit-product"},
            {"id": "C025A4WK3J4", "name": "goodchop"},
            {"id": "CXXXXXXXXXX", "name": "tpt_team"},
            {"id": "C07TGTQSZDQ", "name": "enterprise-alliance"},
            {"id": "C089R2T84RA", "name": "goc-charge-at-checkout"},
        ],
    },
    "tier3": {
        "description": "Lower Priority - Alerts & General",
        "channels": [],  # To be populated from bot_channels.json
    },
}

# Rate limiting
RATE_LIMIT_DELAY = 3  # seconds between API calls
RATE_LIMIT_BACKOFF = 30  # seconds on rate limit hit

# ============================================================================
# STATE MANAGEMENT
# ============================================================================


def load_state() -> dict:
    """Load extraction state from file."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "started_at": None,
        "last_updated": None,
        "channels_completed": [],
        "channels_in_progress": {},
        "total_messages": 0,
        "total_threads": 0,
    }


def save_state(state: dict):
    """Save extraction state to file."""
    state["last_updated"] = datetime.utcnow().isoformat() + "Z"
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def print_status(state: dict):
    """Print current extraction status."""
    print("=" * 60)
    print("SLACK BULK EXTRACTION STATUS")
    print("=" * 60)
    print(f"Started: {state.get('started_at', 'Not started')}")
    print(f"Last Updated: {state.get('last_updated', 'N/A')}")
    print(f"Total Messages: {state.get('total_messages', 0):,}")
    print(f"Total Threads: {state.get('total_threads', 0):,}")
    print(f"Channels Completed: {len(state.get('channels_completed', []))}")

    in_progress = state.get("channels_in_progress", {})
    if in_progress:
        print(f"\nIn Progress ({len(in_progress)}):")
        for channel_id, info in in_progress.items():
            print(
                f"  - {info.get('name', channel_id)}: Week {info.get('current_week', '?')}"
            )

    completed = state.get("channels_completed", [])
    if completed:
        print(f"\nCompleted ({len(completed)}):")
        for ch in completed[:10]:
            print(f"  - {ch}")
        if len(completed) > 10:
            print(f"  ... and {len(completed) - 10} more")

    print("=" * 60)


# ============================================================================
# EXTRACTION LOGIC
# ============================================================================


def get_client() -> WebClient:
    """Get authenticated Slack client."""
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        raise ValueError("SLACK_BOT_TOKEN not found in .env")
    return WebClient(token=token)


def get_weeks(start_date: datetime, end_date: datetime) -> list:
    """Generate list of (week_start, week_end, week_label) tuples."""
    weeks = []
    current = start_date

    # Align to Monday
    current = current - timedelta(days=current.weekday())

    while current < end_date:
        week_end = min(current + timedelta(days=7), end_date)
        week_num = current.isocalendar()[1]
        week_label = f"{current.year}-W{week_num:02d}"
        weeks.append((current, week_end, week_label))
        current = week_end

    return weeks


def fetch_messages_for_period(
    client: WebClient,
    channel_id: str,
    start_ts: float,
    end_ts: float,
    include_threads: bool = True,
) -> tuple:
    """
    Fetch all messages in a channel for a time period.

    Returns:
        tuple: (messages, thread_count)
    """
    messages = []
    thread_count = 0
    cursor = None

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

            # Fetch thread replies for messages with replies
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

            time.sleep(RATE_LIMIT_DELAY)

        except SlackApiError as e:
            if e.response["error"] == "ratelimited":
                retry_after = int(
                    e.response.headers.get("Retry-After", RATE_LIMIT_BACKOFF)
                )
                print(f"  Rate limited, waiting {retry_after}s...", file=sys.stderr)
                time.sleep(retry_after)
                continue
            elif e.response["error"] == "channel_not_found":
                print(f"  Channel not found: {channel_id}", file=sys.stderr)
                return [], 0
            elif e.response["error"] == "not_in_channel":
                print(f"  Bot not in channel: {channel_id}", file=sys.stderr)
                return [], 0
            else:
                print(f"  Error: {e.response['error']}", file=sys.stderr)
                raise

    return messages, thread_count


def fetch_thread_replies(client: WebClient, channel_id: str, thread_ts: str) -> list:
    """Fetch all replies in a thread (excluding parent)."""
    replies = []
    cursor = None

    while True:
        try:
            response = client.conversations_replies(
                channel=channel_id, ts=thread_ts, cursor=cursor, limit=200
            )

            batch = response.get("messages", [])
            # Skip parent message (first in list)
            if cursor is None and len(batch) > 1:
                replies.extend(batch[1:])
            elif cursor:
                replies.extend(batch)

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

            time.sleep(1)  # Lighter rate limit for thread calls

        except SlackApiError as e:
            if e.response["error"] == "ratelimited":
                retry_after = int(e.response.headers.get("Retry-After", 5))
                time.sleep(retry_after)
                continue
            else:
                break

    return replies


def save_raw_messages(
    channel_id: str, channel_name: str, week_label: str, messages: list
):
    """Save raw messages to JSON file."""
    channel_dir = RAW_DIR / channel_id
    channel_dir.mkdir(parents=True, exist_ok=True)

    output_file = channel_dir / f"{week_label}.json"

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
    client: WebClient,
    channel_id: str,
    channel_name: str,
    start_date: datetime,
    end_date: datetime,
    state: dict,
    dry_run: bool = False,
) -> tuple:
    """
    Extract all messages from a channel for the given period.

    Returns:
        tuple: (total_messages, total_threads)
    """
    weeks = get_weeks(start_date, end_date)
    total_messages = 0
    total_threads = 0

    # Check for resume point
    channel_state = state.get("channels_in_progress", {}).get(channel_id, {})
    resume_week = channel_state.get("current_week")

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Channel: #{channel_name} ({channel_id})", file=sys.stderr)
    print(f"Period: {start_date.date()} to {end_date.date()}", file=sys.stderr)
    print(f"Weeks: {len(weeks)}", file=sys.stderr)
    if resume_week:
        print(f"Resuming from: {resume_week}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    # Update state
    state.setdefault("channels_in_progress", {})[channel_id] = {
        "name": channel_name,
        "started_at": datetime.utcnow().isoformat() + "Z",
        "total_weeks": len(weeks),
        "current_week": None,
    }
    save_state(state)

    skip_until_resume = resume_week is not None

    for week_start, week_end, week_label in weeks:
        # Skip weeks until we reach resume point
        if skip_until_resume:
            if week_label == resume_week:
                skip_until_resume = False
            else:
                continue

        # Update state
        state["channels_in_progress"][channel_id]["current_week"] = week_label
        save_state(state)

        if dry_run:
            print(f"  [DRY RUN] Would extract: {week_label}", file=sys.stderr)
            continue

        print(f"  Extracting: {week_label}...", file=sys.stderr, end=" ")

        start_ts = week_start.timestamp()
        end_ts = week_end.timestamp()

        messages, thread_count = fetch_messages_for_period(
            client, channel_id, start_ts, end_ts
        )

        if messages:
            output_file = save_raw_messages(
                channel_id, channel_name, week_label, messages
            )
            print(
                f"{len(messages)} messages, {thread_count} threads → {output_file.name}",
                file=sys.stderr,
            )
            total_messages += len(messages)
            total_threads += thread_count
        else:
            print("0 messages", file=sys.stderr)

        # Rate limit between weeks
        time.sleep(RATE_LIMIT_DELAY)

    # Mark channel as completed
    if channel_id in state.get("channels_in_progress", {}):
        del state["channels_in_progress"][channel_id]

    state.setdefault("channels_completed", []).append(channel_name)
    state["total_messages"] = state.get("total_messages", 0) + total_messages
    state["total_threads"] = state.get("total_threads", 0) + total_threads
    save_state(state)

    print(
        f"\nChannel complete: {total_messages} messages, {total_threads} threads",
        file=sys.stderr,
    )

    return total_messages, total_threads


def run_extraction(
    tiers: list, days: int = 180, dry_run: bool = False, resume: bool = False
):
    """Run the full extraction pipeline."""
    client = get_client()
    state = load_state()

    # Initialize state if fresh start
    if not state.get("started_at"):
        state["started_at"] = datetime.utcnow().isoformat() + "Z"
        save_state(state)

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    print("=" * 60, file=sys.stderr)
    print("SLACK BULK EXTRACTION", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(
        f"Period: {start_date.date()} to {end_date.date()} ({days} days)",
        file=sys.stderr,
    )
    print(f"Tiers: {', '.join(tiers)}", file=sys.stderr)
    print(f"Dry Run: {dry_run}", file=sys.stderr)
    print(f"Resume: {resume}", file=sys.stderr)

    # Gather channels
    channels = []
    for tier in tiers:
        if tier in CHANNEL_TIERS:
            channels.extend(CHANNEL_TIERS[tier]["channels"])

    print(f"Channels: {len(channels)}", file=sys.stderr)

    # Skip completed channels unless not resuming
    if resume:
        completed = set(state.get("channels_completed", []))
        channels = [ch for ch in channels if ch["name"] not in completed]
        print(
            f"Remaining: {len(channels)} (after filtering completed)", file=sys.stderr
        )

    # Extract each channel
    grand_total_messages = 0
    grand_total_threads = 0

    for channel in channels:
        try:
            messages, threads = extract_channel(
                client,
                channel["id"],
                channel["name"],
                start_date,
                end_date,
                state,
                dry_run,
            )
            grand_total_messages += messages
            grand_total_threads += threads
        except Exception as e:
            print(f"\nError extracting {channel['name']}: {e}", file=sys.stderr)
            continue

    # Final summary
    print("\n" + "=" * 60, file=sys.stderr)
    print("EXTRACTION COMPLETE", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(
        f"This run: {grand_total_messages:,} messages, {grand_total_threads:,} threads",
        file=sys.stderr,
    )
    print(
        f"Total (all runs): {state.get('total_messages', 0):,} messages",
        file=sys.stderr,
    )
    print(
        f"Channels completed: {len(state.get('channels_completed', []))}",
        file=sys.stderr,
    )
    print("=" * 60, file=sys.stderr)


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Bulk extract Slack messages for Brain enrichment"
    )
    parser.add_argument(
        "--channels",
        choices=["tier1", "tier2", "tier3", "all"],
        default="tier1",
        help="Channel tier to extract (default: tier1)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=180,
        help="Days of history to extract (default: 180)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be extracted without making API calls",
    )
    parser.add_argument(
        "--resume", action="store_true", help="Resume from last extraction state"
    )
    parser.add_argument(
        "--status", action="store_true", help="Show extraction status and exit"
    )

    args = parser.parse_args()

    if args.status:
        state = load_state()
        print_status(state)
        return

    # Determine tiers
    if args.channels == "all":
        tiers = ["tier1", "tier2", "tier3"]
    else:
        tiers = [args.channels]

    run_extraction(
        tiers=tiers, days=args.days, dry_run=args.dry_run, resume=args.resume
    )


if __name__ == "__main__":
    main()
