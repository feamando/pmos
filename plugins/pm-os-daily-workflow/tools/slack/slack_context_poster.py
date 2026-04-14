#!/usr/bin/env python3
"""
Slack Context Poster (v5.0)

Posts context document highlights to Slack channel.
Extracts critical alerts, action items, blockers, and key dates.

Ported from v4.x slack_context_poster.py — timezone from config,
auth via connector_bridge, channel from config.

Usage:
    python slack_context_poster.py <context_file>
    python slack_context_poster.py <context_file> --channel YOUR_CHANNEL_ID
    python slack_context_poster.py <context_file> --type boot|update|logout
    python slack_context_poster.py --test
"""

import argparse
import logging
import os
import re
import sys
from datetime import datetime

logger = logging.getLogger(__name__)

# v5 shared utils
try:
    from pm_os_base.tools.core.config_loader import get_config
    from pm_os_base.tools.core.connector_bridge import get_auth
except ImportError:
    try:
        _base = __import__("pathlib").Path(__file__).resolve().parent.parent.parent.parent
        sys.path.insert(0, str(_base / "pm-os-base" / "tools" / "core"))
        from config_loader import get_config
        from connector_bridge import get_auth
    except ImportError:
        logger.error("Cannot import pm_os_base core modules")
        raise


def _get_timezone() -> str:
    """Get user timezone from config."""
    return get_config().get("user.timezone", "UTC")


def _resolve_default_channel() -> str:
    """Resolve default channel from config chain."""
    config = get_config()
    return (
        config.get("integrations.slack.context_output_channel")
        or config.get("integrations.slack.channel")
        or os.environ.get("SLACK_CHANNEL", "")
    )


def _get_slack_client():
    """Initialize Slack client via connector_bridge."""
    from slack_sdk import WebClient

    auth = get_auth("slack")
    if auth.source == "env":
        return WebClient(token=auth.token)
    elif auth.source == "connector":
        return WebClient(token=auth.token) if auth.token else None
    else:
        raise ValueError(auth.help_message or "Slack auth not available")


def parse_context_file(file_path: str) -> dict:
    """
    Parse a context markdown file and extract key sections.

    Returns dict with:
        - title: Document title
        - critical_alerts: List of critical items
        - action_items: List of action items (new + carried)
        - blockers: List of active blockers
        - key_dates: List of upcoming dates
        - session_summary: Session end summary (if present)
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    result = {
        "title": "",
        "critical_alerts": [],
        "action_items": [],
        "blockers": [],
        "key_dates": [],
        "session_summary": None,
    }

    # Extract title (first H1)
    title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
    if title_match:
        result["title"] = title_match.group(1).strip()

    # Extract Critical Alerts section
    critical_match = re.search(
        r"## Critical Alerts\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL | re.IGNORECASE
    )
    if critical_match:
        alerts = re.findall(
            r"^- \*\*(.+?)\*\*:?\s*(.*)$", critical_match.group(1), re.MULTILINE
        )
        result["critical_alerts"] = [
            {"title": a[0], "detail": a[1].strip()} for a in alerts
        ]

    # Extract Action Items section
    action_match = re.search(
        r"## Action Items\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL | re.IGNORECASE
    )
    if action_match:
        items = re.findall(
            r"^- \[ \] \*\*(.+?)\*\*:?\s*(.*)$", action_match.group(1), re.MULTILINE
        )
        result["action_items"] = [{"owner": i[0], "task": i[1].strip()} for i in items]

    # Extract Blockers & Risks section (Active table)
    blocker_match = re.search(
        r"### Active\s*\n\s*\|[^\n]*\n\s*\|[-\s|]+\n(.*?)(?=\n### |\n## |\Z)",
        content, re.DOTALL | re.IGNORECASE,
    )
    if blocker_match:
        rows = re.findall(
            r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|",
            blocker_match.group(1), re.MULTILINE,
        )
        result["blockers"] = [
            {"blocker": r[0], "owner": r[1], "impact": r[2]} for r in rows
        ]

    # Extract Key Dates & Milestones table
    dates_match = re.search(
        r"## Key Dates & Milestones\s*\n\s*\|[^\n]*\n\s*\|[-\s|]+\n(.*?)(?=\n## |\Z)",
        content, re.DOTALL | re.IGNORECASE,
    )
    if dates_match:
        rows = re.findall(
            r"^\|\s*\*?\*?(.+?)\*?\*?\s*\|\s*(.+?)\s*\|",
            dates_match.group(1), re.MULTILINE,
        )
        result["key_dates"] = [
            {"date": r[0].strip("*"), "milestone": r[1]} for r in rows
        ]

    # Extract Session End summary
    session_match = re.search(
        r"## Session End.*?\n(.*?)(?=\n## |\Z)", content, re.DOTALL | re.IGNORECASE
    )
    if session_match:
        result["session_summary"] = session_match.group(1).strip()

    return result


def format_slack_message(parsed: dict, msg_type: str = "update") -> list:
    """
    Format parsed context into Slack blocks.

    Args:
        parsed: Parsed context dict
        msg_type: "boot", "update", or "logout"

    Returns:
        List of Slack block objects
    """
    blocks = []

    emoji_map = {
        "boot": ":rocket:",
        "update": ":arrows_counterclockwise:",
        "logout": ":checkered_flag:",
    }
    title_map = {
        "boot": "Context Loaded",
        "update": "Context Updated",
        "logout": "Session Complete",
    }

    emoji = emoji_map.get(msg_type, ":page_facing_up:")
    title = title_map.get(msg_type, "Context Update")

    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": "%s %s" % (emoji, title), "emoji": True},
    })

    if parsed["title"]:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*%s*" % parsed["title"]},
        })

    blocks.append({"type": "divider"})

    if parsed["critical_alerts"]:
        alert_text = "*:rotating_light: Critical Alerts*\n"
        for alert in parsed["critical_alerts"][:5]:
            alert_text += "* *%s*" % alert["title"]
            if alert["detail"]:
                alert_text += " - %s" % alert["detail"][:100]
            alert_text += "\n"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": alert_text.strip()},
        })

    if parsed["action_items"]:
        action_text = "*:white_check_mark: Open Action Items*\n"
        for item in parsed["action_items"][:7]:
            task_preview = (
                item["task"][:80] + "..." if len(item["task"]) > 80 else item["task"]
            )
            action_text += "* *%s*: %s\n" % (item["owner"], task_preview)
        if len(parsed["action_items"]) > 7:
            action_text += "_...and %d more_\n" % (len(parsed["action_items"]) - 7)
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": action_text.strip()},
        })

    if parsed["blockers"]:
        blocker_text = "*:no_entry: Active Blockers*\n"
        for b in parsed["blockers"][:5]:
            blocker_text += "* %s (%s)\n" % (b["blocker"], b["owner"])
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": blocker_text.strip()},
        })

    if parsed["key_dates"]:
        dates_text = "*:calendar: Upcoming*\n"
        for d in parsed["key_dates"][:5]:
            dates_text += "* *%s* - %s\n" % (d["date"], d["milestone"])
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": dates_text.strip()},
        })

    if msg_type == "logout" and parsed["session_summary"]:
        blocks.append({"type": "divider"})
        summary_preview = parsed["session_summary"][:500]
        if len(parsed["session_summary"]) > 500:
            summary_preview += "..."
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Session Summary:*\n%s" % summary_preview,
            },
        })

    # Footer with timestamp — timezone from config
    tz_label = _get_timezone()
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": "Posted %s %s" % (datetime.now().strftime("%Y-%m-%d %H:%M"), tz_label),
        }],
    })

    return blocks


def post_to_slack(client, channel: str, blocks: list, fallback_text: str) -> dict:
    """Post message to Slack channel."""
    from slack_sdk.errors import SlackApiError

    try:
        result = client.chat_postMessage(
            channel=channel,
            blocks=blocks,
            text=fallback_text,
        )
        return {"success": True, "ts": result["ts"], "channel": result["channel"]}
    except SlackApiError as e:
        return {"success": False, "error": e.response["error"]}


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Post context highlights to Slack")
    parser.add_argument("context_file", nargs="?", help="Path to context markdown file")
    parser.add_argument(
        "--channel", default=None,
        help="Slack channel ID (default: from config)",
    )
    parser.add_argument(
        "--type", choices=["boot", "update", "logout"], default="update",
        help="Message type (affects header/formatting)",
    )
    parser.add_argument("--test", action="store_true", help="Test Slack connection only")
    parser.add_argument(
        "--dry-run", action="store_true", help="Parse and format but do not post"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if not args.channel:
        args.channel = _resolve_default_channel()
    if not args.channel:
        parser.error(
            "No channel specified. Set --channel, integrations.slack.context_output_channel "
            "in config.yaml, or SLACK_CHANNEL env var."
        )

    if args.test:
        try:
            client = _get_slack_client()
            auth = client.auth_test()
            logger.info("OK: Connected as %s to %s", auth["user"], auth["team"])
            info = client.conversations_info(channel=args.channel)
            logger.info(
                "OK: Channel access confirmed: #%s",
                info["channel"].get("name", args.channel),
            )
            return 0
        except Exception as e:
            logger.error("FAILED: %s", e)
            return 1

    if not args.context_file:
        parser.error("context_file is required (or use --test)")

    if not os.path.exists(args.context_file):
        logger.error("File not found: %s", args.context_file)
        return 1

    logger.info("Parsing: %s", args.context_file)
    parsed = parse_context_file(args.context_file)

    blocks = format_slack_message(parsed, args.type)
    fallback = "Context %s: %s" % (args.type, parsed["title"])

    if args.dry_run:
        print("\n--- DRY RUN ---")
        print("Would post to channel: %s" % args.channel)
        print("Title: %s" % parsed["title"])
        print("Critical alerts: %d" % len(parsed["critical_alerts"]))
        print("Action items: %d" % len(parsed["action_items"]))
        print("Blockers: %d" % len(parsed["blockers"]))
        print("Key dates: %d" % len(parsed["key_dates"]))
        return 0

    logger.info("Posting to Slack channel: %s", args.channel)
    client = _get_slack_client()
    result = post_to_slack(client, args.channel, blocks, fallback)

    if result["success"]:
        logger.info("SUCCESS: Posted to %s (ts: %s)", result["channel"], result["ts"])
        return 0
    else:
        logger.error("FAILED: %s", result["error"])
        return 1


if __name__ == "__main__":
    sys.exit(main())
