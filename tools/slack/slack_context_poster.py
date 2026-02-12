#!/usr/bin/env python3
"""
Slack Context Poster

Posts context document highlights to Slack channel.
Extracts critical alerts, action items, blockers, and key dates.

Usage:
    python slack_context_poster.py <context_file>
    python slack_context_poster.py <context_file> --channel CXXXXXXXXXX
    python slack_context_poster.py <context_file> --type boot|update|logout
    python slack_context_poster.py --test  # Test connection only
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Add common directory to path for config_loader
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config_loader

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ImportError:
    print("Error: slack_sdk not installed. Run: pip install slack_sdk")
    sys.exit(1)

# Default channel for context updates
DEFAULT_CHANNEL = "CXXXXXXXXXX"  # #pmos-slack-channel


def get_slack_client() -> WebClient:
    """Initialize Slack client from config."""
    slack_config = config_loader.get_slack_config()
    token = slack_config.get("bot_token")
    if not token:
        raise ValueError("SLACK_BOT_TOKEN not set in environment or config")
    return WebClient(token=token)


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

    # Extract Action Items section (both New and Carried Forward)
    action_match = re.search(
        r"## Action Items\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL | re.IGNORECASE
    )
    if action_match:
        # Find unchecked items [ ]
        items = re.findall(
            r"^- \[ \] \*\*(.+?)\*\*:?\s*(.*)$", action_match.group(1), re.MULTILINE
        )
        result["action_items"] = [{"owner": i[0], "task": i[1].strip()} for i in items]

    # Extract Blockers & Risks section (Active table)
    # Note: Use [^\n]* instead of .* to prevent matching across lines with DOTALL
    blocker_match = re.search(
        r"### Active\s*\n\s*\|[^\n]*\n\s*\|[-\s|]+\n(.*?)(?=\n### |\n## |\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if blocker_match:
        # Table format: | Blocker | Owner | Impact | Status |
        rows = re.findall(
            r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|",
            blocker_match.group(1),
            re.MULTILINE,
        )
        result["blockers"] = [
            {"blocker": r[0], "owner": r[1], "impact": r[2]} for r in rows
        ]

    # Extract Key Dates & Milestones table
    # Note: Use [^\n]* instead of .* to prevent matching across lines with DOTALL
    dates_match = re.search(
        r"## Key Dates & Milestones\s*\n\s*\|[^\n]*\n\s*\|[-\s|]+\n(.*?)(?=\n## |\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if dates_match:
        rows = re.findall(
            r"^\|\s*\*?\*?(.+?)\*?\*?\s*\|\s*(.+?)\s*\|",
            dates_match.group(1),
            re.MULTILINE,
        )
        result["key_dates"] = [
            {"date": r[0].strip("*"), "milestone": r[1]} for r in rows
        ]

    # Extract Session End summary (for logout)
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

    # Header based on type
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

    blocks.append(
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{emoji} {title}", "emoji": True},
        }
    )

    # Context title
    if parsed["title"]:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{parsed['title']}*"},
            }
        )

    blocks.append({"type": "divider"})

    # Critical Alerts (always show if present)
    if parsed["critical_alerts"]:
        alert_text = "*:rotating_light: Critical Alerts*\n"
        for alert in parsed["critical_alerts"][:5]:  # Limit to 5
            alert_text += f"• *{alert['title']}*"
            if alert["detail"]:
                alert_text += f" - {alert['detail'][:100]}"
            alert_text += "\n"
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": alert_text.strip()}}
        )

    # Action Items
    if parsed["action_items"]:
        action_text = "*:white_check_mark: Open Action Items*\n"
        for item in parsed["action_items"][:7]:  # Limit to 7
            task_preview = (
                item["task"][:80] + "..." if len(item["task"]) > 80 else item["task"]
            )
            action_text += f"• *{item['owner']}*: {task_preview}\n"
        if len(parsed["action_items"]) > 7:
            action_text += f"_...and {len(parsed['action_items']) - 7} more_\n"
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": action_text.strip()}}
        )

    # Blockers
    if parsed["blockers"]:
        blocker_text = "*:no_entry: Active Blockers*\n"
        for b in parsed["blockers"][:5]:
            blocker_text += f"• {b['blocker']} ({b['owner']})\n"
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": blocker_text.strip()},
            }
        )

    # Key Dates (next 5)
    if parsed["key_dates"]:
        dates_text = "*:calendar: Upcoming*\n"
        for d in parsed["key_dates"][:5]:
            dates_text += f"• *{d['date']}* - {d['milestone']}\n"
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": dates_text.strip()}}
        )

    # Session summary for logout
    if msg_type == "logout" and parsed["session_summary"]:
        blocks.append({"type": "divider"})
        summary_preview = parsed["session_summary"][:500]
        if len(parsed["session_summary"]) > 500:
            summary_preview += "..."
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Session Summary:*\n{summary_preview}",
                },
            }
        )

    # Footer with timestamp
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Posted {datetime.now().strftime('%Y-%m-%d %H:%M')} CET",
                }
            ],
        }
    )

    return blocks


def post_to_slack(
    client: WebClient, channel: str, blocks: list, fallback_text: str
) -> dict:
    """Post message to Slack channel."""
    try:
        result = client.chat_postMessage(
            channel=channel,
            blocks=blocks,
            text=fallback_text,  # Fallback for notifications
        )
        return {"success": True, "ts": result["ts"], "channel": result["channel"]}
    except SlackApiError as e:
        return {"success": False, "error": e.response["error"]}


def main():
    parser = argparse.ArgumentParser(description="Post context highlights to Slack")
    parser.add_argument("context_file", nargs="?", help="Path to context markdown file")
    parser.add_argument(
        "--channel",
        default=DEFAULT_CHANNEL,
        help=f"Slack channel ID (default: {DEFAULT_CHANNEL})",
    )
    parser.add_argument(
        "--type",
        choices=["boot", "update", "logout"],
        default="update",
        help="Message type (affects header/formatting)",
    )
    parser.add_argument(
        "--test", action="store_true", help="Test Slack connection only"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Parse and format but do not post"
    )
    args = parser.parse_args()

    # Test mode
    if args.test:
        try:
            client = get_slack_client()
            auth = client.auth_test()
            print(f"OK: Connected as {auth['user']} to {auth['team']}")
            info = client.conversations_info(channel=args.channel)
            print(
                f"OK: Channel access confirmed: #{info['channel'].get('name', args.channel)}"
            )
            return 0
        except Exception as e:
            print(f"FAILED: {e}")
            return 1

    # Require context file for non-test mode
    if not args.context_file:
        parser.error("context_file is required (or use --test)")

    if not os.path.exists(args.context_file):
        print(f"Error: File not found: {args.context_file}")
        return 1

    # Parse context file
    print(f"Parsing: {args.context_file}")
    parsed = parse_context_file(args.context_file)

    # Format for Slack
    blocks = format_slack_message(parsed, args.type)
    fallback = f"Context {args.type}: {parsed['title']}"

    if args.dry_run:
        print("\n--- DRY RUN ---")
        print(f"Would post to channel: {args.channel}")
        print(f"Title: {parsed['title']}")
        print(f"Critical alerts: {len(parsed['critical_alerts'])}")
        print(f"Action items: {len(parsed['action_items'])}")
        print(f"Blockers: {len(parsed['blockers'])}")
        print(f"Key dates: {len(parsed['key_dates'])}")
        return 0

    # Post to Slack
    print(f"Posting to Slack channel: {args.channel}")
    client = get_slack_client()
    result = post_to_slack(client, args.channel, blocks, fallback)

    if result["success"]:
        print(f"SUCCESS: Posted to {result['channel']} (ts: {result['ts']})")
        return 0
    else:
        print(f"FAILED: {result['error']}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
