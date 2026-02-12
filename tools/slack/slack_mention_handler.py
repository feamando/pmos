#!/usr/bin/env python3
"""
Slack Mention Handler

Captures, classifies, and tracks @pmos-slack-bot mentions from Slack.
Routes mentions to:
- Daily context (tasks for Nikita/team)
- PM-OS backlog (feature requests, bugs)
- Review queue (general mentions)

Usage:
    python slack_mention_handler.py                    # Poll for new mentions
    python slack_mention_handler.py --check-complete   # Check for completion reactions
    python slack_mention_handler.py --status           # Show pending tasks
    python slack_mention_handler.py --export           # Export to markdown
"""

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# Add parent directory for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config_loader
from slack_mention_classifier import ClassificationResult, MentionType, classify_mention

# LLM processor for enhanced task formalization
try:
    from slack_mention_llm_processor import (
        FormalizedTask,
        format_task_markdown,
        process_mention_with_llm,
    )

    LLM_PROCESSOR_AVAILABLE = True
except ImportError:
    LLM_PROCESSOR_AVAILABLE = False

from dotenv import load_dotenv

load_dotenv(override=True)

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False
    print("Warning: slack_sdk not installed. Run: pip install slack_sdk")

# Configuration - Bot User ID can be set via env var or auto-discovered
BOT_USER_ID = os.getenv("SLACK_BOT_USER_ID")  # Set via environment or auto-discovered


def get_bot_user_id(client: WebClient) -> str:
    """
    Get bot user ID from env var or auto-discover via auth.test.
    Caches the result in environment for subsequent calls.
    """
    global BOT_USER_ID
    if BOT_USER_ID:
        return BOT_USER_ID

    try:
        response = client.auth_test()
        BOT_USER_ID = response["user_id"]
        print(f"Auto-discovered bot user ID: {BOT_USER_ID}", file=sys.stderr)
        return BOT_USER_ID
    except SlackApiError as e:
        print(f"Error discovering bot ID: {e.response['error']}", file=sys.stderr)
        print("Please set SLACK_BOT_USER_ID in your .env file", file=sys.stderr)
        return None


def get_bot_mention_pattern(client: WebClient = None) -> str:
    """Get the mention pattern for the bot."""
    bot_id = BOT_USER_ID or (get_bot_user_id(client) if client else None)
    if not bot_id:
        raise ValueError(
            "Bot user ID not configured. Set SLACK_BOT_USER_ID in .env or ensure bot token is valid."
        )
    return f"<@{bot_id}>"


# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_BRAIN = config_loader.get_root_path() / "user" / "brain"
MENTIONS_DIR = str(USER_BRAIN / "Inbox" / "Slack" / "Mentions")
STATE_FILE = os.path.join(MENTIONS_DIR, "mentions_state.json")
PMOS_BACKLOG_FILE = str(USER_BRAIN / "Products" / "PM-OS" / "mention_backlog.md")

# Completion reaction names
COMPLETION_REACTIONS = [
    "white_check_mark",
    "heavy_check_mark",
    "done",
    "completed",
    "check",
]

# Completion reply patterns (for DONE thread replies)
COMPLETION_REPLY_PATTERNS = [
    r"(?i)^done\.?$",
    r"(?i)^completed\.?$",
    r"(?i)^finished\.?$",
    r"(?i)^resolved\.?$",
    r"(?i)^fixed\.?$",
    r"(?i)^:white_check_mark:\s*done",
    r"(?i)^done\s*:white_check_mark:",
    r"(?i)^\[done\]",
    r"(?i)^task\s+completed",
    r"(?i)^✓\s*done",
    r"(?i)^done\s*✓",
]


def get_mention_bot_name() -> str:
    """Get configurable bot name from config, with fallback."""
    try:
        return config_loader.get_slack_mention_bot_name()
    except Exception:
        return "pmos-slack-bot"  # Fallback for backwards compatibility


# Stale thresholds
STALE_DAYS = 14
ARCHIVE_DAYS = 30


@dataclass
class MentionTask:
    """A captured mention task."""

    id: str
    source_ts: str
    source_channel: str
    source_channel_name: str
    requester_id: str
    requester_name: str
    classification: str
    extracted_task: str
    assignee: Optional[str]
    priority: str
    confidence: float
    thread_link: str
    raw_text: str
    created_at: str
    status: str = "pending"
    completed_at: Optional[str] = None
    is_stale: bool = False


def get_slack_client() -> Optional[WebClient]:
    """Get authenticated Slack client."""
    if not SLACK_AVAILABLE:
        return None
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        print("Error: SLACK_BOT_TOKEN not set in environment")
        return None
    return WebClient(token=token)


def load_state() -> Dict[str, Any]:
    """Load mention state from file."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {
        "version": "1.0",
        "bot_user_id": BOT_USER_ID,
        "last_poll": None,
        "processed_mentions": {},
        "pending_tasks": [],
        "completed_tasks": [],
        "pm_os_backlog": {"features": [], "bugs": []},
        "statistics": {"total_processed": 0, "by_type": {}, "completion_rate": 0.0},
    }


def save_state(state: Dict[str, Any]) -> None:
    """Save mention state to file."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def generate_mention_id(channel_id: str, ts: str) -> str:
    """Generate unique ID for a mention."""
    return f"mention_{channel_id}_{ts.replace('.', '_')}"


def get_thread_link(channel_id: str, ts: str, team_domain: str = "acme-corp") -> str:
    """Generate Slack thread link."""
    ts_formatted = ts.replace(".", "")
    return f"https://{team_domain}.slack.com/archives/{channel_id}/p{ts_formatted}"


def resolve_user_name(client: WebClient, user_id: str) -> str:
    """Resolve user ID to display name."""
    try:
        response = client.users_info(user=user_id)
        user = response["user"]
        return user.get("real_name") or user.get("name") or user_id
    except SlackApiError:
        return user_id


def resolve_channel_name(client: WebClient, channel_id: str) -> str:
    """Resolve channel ID to name."""
    try:
        response = client.conversations_info(channel=channel_id)
        return response["channel"].get("name", channel_id)
    except SlackApiError:
        return channel_id


def should_skip_message(msg: Dict[str, Any], user_id: str, bot_id: str) -> bool:
    """
    Check if a message should be skipped (noise filtering).

    Args:
        msg: Slack message dict
        user_id: User ID who sent the message
        bot_id: The bot's user ID

    Returns:
        True if message should be skipped
    """
    # Skip bot's own messages
    if user_id == bot_id:
        return True

    # Skip messages with subtypes (joins, leaves, etc.)
    subtype = msg.get("subtype", "")
    if subtype in [
        "channel_join",
        "channel_leave",
        "channel_topic",
        "channel_purpose",
        "bot_message",
        "me_message",
        "file_share",
        "pinned_item",
        "unpinned_item",
    ]:
        return True

    text = msg.get("text", "")

    # Skip if text is just the mention with no real content
    bot_pattern = f"<@{bot_id}>"
    cleaned = text.replace(bot_pattern, "").strip()
    cleaned = cleaned.replace(f"@{get_mention_bot_name()}", "").strip()
    if len(cleaned) < 5:
        return True

    # Skip join/leave messages that slipped through
    if "has joined the channel" in text or "has left the channel" in text:
        return True

    return False


def fetch_thread_context(
    client: WebClient, channel_id: str, thread_ts: str, limit: int = 5
) -> Dict[str, Any]:
    """
    Fetch context from a thread (parent message and recent replies).

    Args:
        client: Slack WebClient
        channel_id: Channel ID
        thread_ts: Thread timestamp (parent message ts)
        limit: Max replies to fetch

    Returns:
        Dict with 'parent_text', 'parent_user', 'replies', 'reply_count'
    """
    context = {
        "parent_text": "",
        "parent_user": "",
        "parent_user_name": "",
        "replies": [],
        "reply_count": 0,
    }

    try:
        # Fetch thread replies (includes parent message)
        response = client.conversations_replies(
            channel=channel_id, ts=thread_ts, limit=limit + 1  # +1 for parent
        )

        messages = response.get("messages", [])
        if not messages:
            return context

        # First message is the parent
        parent = messages[0]
        context["parent_text"] = parent.get("text", "")
        context["parent_user"] = parent.get("user", "")
        context["parent_user_name"] = resolve_user_name(client, parent.get("user", ""))
        context["reply_count"] = parent.get("reply_count", len(messages) - 1)

        # Collect replies (excluding parent)
        for msg in messages[1 : limit + 1]:
            reply_user = resolve_user_name(client, msg.get("user", ""))
            context["replies"].append(
                {
                    "user": reply_user,
                    "text": msg.get("text", "")[:500],  # Truncate long replies
                }
            )

    except SlackApiError as e:
        print(
            f"  Error fetching thread context: {e.response.get('error', str(e))}",
            file=sys.stderr,
        )

    return context


def format_thread_context_for_llm(context: Dict[str, Any]) -> str:
    """Format thread context for inclusion in LLM prompt."""
    if not context.get("parent_text"):
        return ""

    parts = []
    parts.append(
        f"**Thread Parent ({context['parent_user_name']}):** {context['parent_text'][:500]}"
    )

    if context.get("replies"):
        parts.append("\n**Thread Replies:**")
        for reply in context["replies"][:3]:  # Limit to 3 replies
            parts.append(f"- {reply['user']}: {reply['text'][:200]}")

    return "\n".join(parts)


def fetch_bot_mentions(
    client: WebClient, state: Dict[str, Any], lookback_hours: int = 24
) -> List[Dict[str, Any]]:
    """
    Fetch messages mentioning the bot from all accessible channels.

    Args:
        client: Slack WebClient
        state: Current state dict
        lookback_hours: How far back to look for mentions

    Returns:
        List of mention messages with metadata
    """
    mentions = []

    # Get bot ID (auto-discover if not set)
    bot_id = get_bot_user_id(client)
    bot_mention_pattern = f"<@{bot_id}>"

    # Update state with discovered bot ID
    state["bot_user_id"] = bot_id

    # Calculate since timestamp
    if state.get("last_poll"):
        since = datetime.fromisoformat(state["last_poll"])
    else:
        since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    since_ts = str(since.timestamp())

    try:
        # Get channels the bot is in
        response = client.users_conversations(types="public_channel,private_channel")
        channels = response["channels"]

        print(
            f"Scanning {len(channels)} channels for mentions since {since.isoformat()}"
        )

        for channel in channels:
            channel_id = channel["id"]
            channel_name = channel.get("name", channel_id)

            try:
                # Fetch messages from channel
                history = client.conversations_history(
                    channel=channel_id, oldest=since_ts, limit=100
                )

                for msg in history.get("messages", []):
                    text = msg.get("text", "")
                    user_id = msg.get("user", "unknown")

                    # Check if bot is mentioned
                    bot_name = get_mention_bot_name()
                    if bot_mention_pattern in text or f"@{bot_name}" in text.lower():
                        # Apply noise filtering
                        if should_skip_message(msg, user_id, bot_id):
                            continue

                        unique_id = generate_mention_id(channel_id, msg["ts"])

                        # Skip if already processed
                        if unique_id in state.get("processed_mentions", {}):
                            continue

                        mention = {
                            "ts": msg["ts"],
                            "user": user_id,
                            "text": text,
                            "channel_id": channel_id,
                            "channel_name": channel_name,
                            "unique_id": unique_id,
                            "thread_ts": msg.get("thread_ts"),
                            "reply_count": msg.get("reply_count", 0),
                            "thread_context": None,
                        }

                        # Resolve user name
                        mention["user_name"] = resolve_user_name(
                            client, mention["user"]
                        )

                        # Fetch thread context if this is a reply
                        thread_ts = msg.get("thread_ts")
                        if thread_ts and thread_ts != msg["ts"]:
                            # This is a reply, not the parent - fetch parent context
                            print(f"    Fetching thread context for reply...")
                            mention["thread_context"] = fetch_thread_context(
                                client, channel_id, thread_ts
                            )

                        mentions.append(mention)

                        print(
                            f"  Found mention in #{channel_name} from {mention['user_name']}"
                        )

            except SlackApiError as e:
                print(f"  Error fetching from #{channel_name}: {e.response['error']}")
                continue

    except SlackApiError as e:
        print(f"Error listing channels: {e.response['error']}")

    return mentions


def process_mention(mention: Dict[str, Any], state: Dict[str, Any]) -> MentionTask:
    """
    Process a single mention and classify it.

    Args:
        mention: Raw mention data from Slack
        state: Current state dict

    Returns:
        MentionTask with classification
    """
    # Classify the mention
    result = classify_mention(mention["text"])

    task = MentionTask(
        id=mention["unique_id"],
        source_ts=mention["ts"],
        source_channel=mention["channel_id"],
        source_channel_name=mention["channel_name"],
        requester_id=mention["user"],
        requester_name=mention["user_name"],
        classification=result.mention_type.value,
        extracted_task=result.extracted_task,
        assignee=result.assignee,
        priority=result.priority,
        confidence=result.confidence,
        thread_link=get_thread_link(mention["channel_id"], mention["ts"]),
        raw_text=mention["text"],
        created_at=datetime.now(timezone.utc).isoformat(),
        status="pending",
    )

    return task


def add_task_to_state(
    task: MentionTask,
    state: Dict[str, Any],
    formalized: Optional[Dict[str, Any]] = None,
) -> None:
    """Add a processed task to the appropriate state location."""
    task_dict = asdict(task)

    # Include formalized data if provided
    if formalized:
        task_dict["formalized"] = formalized

    # Mark as processed
    state["processed_mentions"][task.id] = {
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "classification": task.classification,
        "status": "pending",
    }

    # Route based on classification
    if task.classification == MentionType.PM_OS_FEATURE.value:
        entry = {
            "id": task.id,
            "title": task.extracted_task[:100],
            "description": task.extracted_task,
            "source_mention_id": task.id,
            "requester": task.requester_name,
            "status": "backlog",
            "created_at": task.created_at,
            "thread_link": task.thread_link,
        }
        if formalized:
            entry["formalized"] = formalized
        state["pm_os_backlog"]["features"].append(entry)
    elif task.classification == MentionType.PM_OS_BUG.value:
        entry = {
            "id": task.id,
            "title": task.extracted_task[:100],
            "description": task.extracted_task,
            "source_mention_id": task.id,
            "requester": task.requester_name,
            "status": "open",
            "created_at": task.created_at,
            "thread_link": task.thread_link,
        }
        if formalized:
            entry["formalized"] = formalized
        state["pm_os_backlog"]["bugs"].append(entry)
    else:
        # Add to pending tasks (nikita_task, team_task, general)
        state["pending_tasks"].append(task_dict)

    # Update statistics
    state["statistics"]["total_processed"] += 1
    type_counts = state["statistics"].setdefault("by_type", {})
    type_counts[task.classification] = type_counts.get(task.classification, 0) + 1


def check_completion_reactions(client: WebClient, state: Dict[str, Any]) -> int:
    """
    Check pending tasks for completion reactions.

    Returns:
        Number of tasks marked complete
    """
    completed_count = 0
    pending = state.get("pending_tasks", [])
    completed = state.setdefault("completed_tasks", [])

    for task in pending[:]:  # Copy list to allow modification
        try:
            # Get reactions on the message
            response = client.reactions_get(
                channel=task["source_channel"], timestamp=task["source_ts"]
            )

            message = response.get("message", {})
            reactions = message.get("reactions", [])

            # Check for completion reactions
            for reaction in reactions:
                if reaction["name"] in COMPLETION_REACTIONS:
                    task["status"] = "completed"
                    task["completed_at"] = datetime.now(timezone.utc).isoformat()
                    task["completed_by"] = "reaction"
                    task["completion_reaction"] = reaction["name"]

                    # Move to completed
                    pending.remove(task)
                    completed.append(task)

                    # Update processed state
                    if task["id"] in state["processed_mentions"]:
                        state["processed_mentions"][task["id"]]["status"] = "completed"

                    completed_count += 1
                    print(f"  Marked complete: {task['extracted_task'][:50]}...")
                    break

        except SlackApiError as e:
            print(f"  Error checking reactions for {task['id']}: {e.response['error']}")
            continue

    # Update completion rate
    total = len(pending) + len(completed)
    if total > 0:
        state["statistics"]["completion_rate"] = len(completed) / total

    return completed_count


def check_completion_replies(client: WebClient, state: Dict[str, Any]) -> int:
    """
    Check pending tasks for "DONE" thread replies.

    Fetches thread replies for each pending task and looks for
    messages matching completion patterns.

    Returns:
        Number of tasks marked complete via reply detection
    """
    completed_count = 0
    pending = state.get("pending_tasks", [])
    completed = state.setdefault("completed_tasks", [])

    for task in pending[:]:  # Copy list for safe modification
        try:
            # Use conversations.replies to get thread messages
            response = client.conversations_replies(
                channel=task["source_channel"],
                ts=task["source_ts"],
                limit=20,  # Recent replies only
            )

            messages = response.get("messages", [])
            # Skip first message (parent), check replies
            for reply in messages[1:]:
                reply_text = reply.get("text", "").strip()

                # Check against completion patterns
                for pattern in COMPLETION_REPLY_PATTERNS:
                    if re.search(pattern, reply_text):
                        task["status"] = "completed"
                        task["completed_at"] = datetime.now(timezone.utc).isoformat()
                        task["completed_by"] = "reply"
                        task["completion_reply_user"] = reply.get("user", "unknown")
                        task["completion_reply_text"] = reply_text[:100]

                        pending.remove(task)
                        completed.append(task)

                        if task["id"] in state["processed_mentions"]:
                            state["processed_mentions"][task["id"]][
                                "status"
                            ] = "completed"

                        completed_count += 1
                        print(
                            f"  Marked complete (reply): {task['extracted_task'][:50]}..."
                        )
                        break

                if task["status"] == "completed":
                    break

        except SlackApiError as e:
            print(
                f"  Error checking replies for {task['id']}: {e.response.get('error', str(e))}"
            )
            continue

    # Update completion rate
    total = len(pending) + len(completed)
    if total > 0:
        state["statistics"]["completion_rate"] = len(completed) / total

    return completed_count


def check_all_completions(client: WebClient, state: Dict[str, Any]) -> Dict[str, int]:
    """
    Check for task completions via both reactions AND replies.

    Returns:
        Dict with 'reactions', 'replies', and 'total' counts
    """
    reaction_count = check_completion_reactions(client, state)
    reply_count = check_completion_replies(client, state)

    return {
        "reactions": reaction_count,
        "replies": reply_count,
        "total": reaction_count + reply_count,
    }


def get_pending_tasks_for_context() -> Dict[str, Any]:
    """
    Get pending mention tasks formatted for daily context inclusion.

    Called by daily_context_updater or context synthesis tools.

    Returns:
        Dict with 'nikita_tasks', 'team_tasks', 'general', 'pmos_backlog'
    """
    state = load_state()
    pending = state.get("pending_tasks", [])
    backlog = state.get("pm_os_backlog", {})

    result = {
        "nikita_tasks": [],
        "team_tasks": [],
        "general": [],
        "pmos_bugs": backlog.get("bugs", []),
        "pmos_features": backlog.get("features", []),
        "last_poll": state.get("last_poll"),
        "total_pending": len(pending),
    }

    for task in pending:
        task_summary = {
            "id": task["id"],
            "task": task["extracted_task"],
            "requester": task["requester_name"],
            "channel": task["source_channel_name"],
            "thread_link": task["thread_link"],
            "priority": task.get("priority", "medium"),
            "created_at": task["created_at"],
            "is_stale": task.get("is_stale", False),
            "assignee": task.get("assignee"),
        }

        if task["classification"] == "nikita_task":
            result["nikita_tasks"].append(task_summary)
        elif task["classification"] == "team_task":
            result["team_tasks"].append(task_summary)
        else:
            result["general"].append(task_summary)

    return result


def format_mentions_for_daily_context() -> str:
    """
    Format pending mention tasks as markdown for daily context files.

    Returns:
        Markdown string suitable for inclusion in context files.
    """
    data = get_pending_tasks_for_context()
    lines = []

    bot_name = get_mention_bot_name()
    lines.append(f"## Pending Slack Mention Tasks (@{bot_name})")
    lines.append("")
    lines.append(
        f"_Last poll: {data['last_poll'] or 'Never'} | Total pending: {data['total_pending']}_"
    )
    lines.append("")

    if data["nikita_tasks"]:
        lines.append("### Tasks for Nikita")
        for task in data["nikita_tasks"]:
            stale = " [STALE]" if task["is_stale"] else ""
            priority_icon = {"high": "!", "critical": "!!"}.get(task["priority"], "")
            lines.append(f"- [ ] {priority_icon}{task['task']}{stale}")
            lines.append(f"  - From: @{task['requester']} in #{task['channel']}")
            lines.append(f"  - [Thread]({task['thread_link']})")
        lines.append("")

    if data["team_tasks"]:
        lines.append("### Team Task Tracking")
        for task in data["team_tasks"]:
            stale = " [STALE]" if task["is_stale"] else ""
            lines.append(
                f"- [ ] **{task['assignee'] or 'Unassigned'}**: {task['task']}{stale}"
            )
            lines.append(f"  - From: @{task['requester']}")
            lines.append(f"  - [Thread]({task['thread_link']})")
        lines.append("")

    if data["pmos_bugs"]:
        open_bugs = [b for b in data["pmos_bugs"] if b.get("status") == "open"]
        if open_bugs:
            lines.append(f"### PM-OS Bugs ({len(open_bugs)} open)")
            for bug in open_bugs[:5]:  # Limit for context
                lines.append(f"- :bug: {bug['title']}")
            lines.append("")

    if data["pmos_features"]:
        backlog = [f for f in data["pmos_features"] if f.get("status") == "backlog"]
        if backlog:
            lines.append(f"### PM-OS Feature Requests ({len(backlog)} in backlog)")
            for feature in backlog[:5]:  # Limit for context
                lines.append(f"- :sparkles: {feature['title']}")
            lines.append("")

    if (
        not data["nikita_tasks"]
        and not data["team_tasks"]
        and not data["pmos_bugs"]
        and not data["pmos_features"]
    ):
        lines.append("_No pending mention tasks._")
        lines.append("")

    return "\n".join(lines)


def detect_stale_tasks(state: Dict[str, Any]) -> int:
    """Mark old tasks as stale."""
    now = datetime.now(timezone.utc)
    stale_count = 0

    for task in state.get("pending_tasks", []):
        created = datetime.fromisoformat(task["created_at"].replace("Z", "+00:00"))
        age_days = (now - created).days

        if age_days >= ARCHIVE_DAYS:
            task["status"] = "archived"
            task["archived_at"] = now.isoformat()
            stale_count += 1
        elif age_days >= STALE_DAYS and not task.get("is_stale"):
            task["is_stale"] = True
            task["stale_since"] = now.isoformat()
            stale_count += 1

    return stale_count


def export_daily_markdown(
    state: Dict[str, Any], output_path: Optional[str] = None
) -> str:
    """
    Export mentions to daily markdown file.

    Args:
        state: Current state
        output_path: Optional output path (defaults to MENTIONS_YYYY-MM-DD.md)

    Returns:
        Path to generated file
    """
    today = datetime.now().strftime("%Y-%m-%d")
    if not output_path:
        output_path = os.path.join(MENTIONS_DIR, f"MENTIONS_{today}.md")

    lines = [
        f"# Mention Capture: {today}",
        f"",
        f"Generated: {datetime.now().isoformat()}",
        f"",
    ]

    # Pending tasks by type
    pending = state.get("pending_tasks", [])

    nikita_tasks = [t for t in pending if t["classification"] == "nikita_task"]
    team_tasks = [t for t in pending if t["classification"] == "team_task"]
    general = [t for t in pending if t["classification"] == "general"]

    if nikita_tasks:
        lines.append("## Tasks for Nikita")
        lines.append("")
        for task in nikita_tasks:
            checkbox = "[ ]" if task["status"] == "pending" else "[x]"
            stale_marker = " (STALE)" if task.get("is_stale") else ""
            lines.append(f"- {checkbox} {task['extracted_task']}{stale_marker}")
            lines.append(
                f"  - From: @{task['requester_name']} in #{task['source_channel_name']}"
            )
            lines.append(f"  - [Thread]({task['thread_link']})")
        lines.append("")

    if team_tasks:
        lines.append("## Team Delegation Tracking")
        lines.append("")
        for task in team_tasks:
            checkbox = "[ ]" if task["status"] == "pending" else "[x]"
            stale_marker = " (STALE)" if task.get("is_stale") else ""
            lines.append(
                f"- {checkbox} **{task['assignee']}**: {task['extracted_task']}{stale_marker}"
            )
            lines.append(f"  - From: @{task['requester_name']}")
            lines.append(f"  - [Thread]({task['thread_link']})")
        lines.append("")

    # PM-OS Backlog
    backlog = state.get("pm_os_backlog", {})
    bugs = backlog.get("bugs", [])
    features = backlog.get("features", [])

    if bugs or features:
        lines.append("## PM-OS Backlog")
        lines.append("")

        if bugs:
            lines.append("### Bugs")
            for bug in bugs:
                status_emoji = (
                    ":bug:" if bug["status"] == "open" else ":white_check_mark:"
                )
                lines.append(f"- {status_emoji} **{bug['title']}**")
                lines.append(f"  - Reported by: {bug['requester']}")
                lines.append(f"  - [Thread]({bug['thread_link']})")
            lines.append("")

        if features:
            lines.append("### Feature Requests")
            for feature in features:
                lines.append(f"- **{feature['title']}**")
                lines.append(f"  - Requested by: {feature['requester']}")
                lines.append(f"  - [Thread]({feature['thread_link']})")
            lines.append("")

    if general:
        lines.append("## General Mentions (Review Queue)")
        lines.append("")
        for task in general:
            lines.append(f"- {task['extracted_task'][:100]}")
            lines.append(
                f"  - From: @{task['requester_name']} in #{task['source_channel_name']}"
            )
        lines.append("")

    # Statistics
    stats = state.get("statistics", {})
    lines.append("## Statistics")
    lines.append("")
    lines.append(f"- Total processed: {stats.get('total_processed', 0)}")
    lines.append(f"- Completion rate: {stats.get('completion_rate', 0):.1%}")
    lines.append(f"- Pending tasks: {len(pending)}")
    lines.append(f"- By type: {stats.get('by_type', {})}")
    lines.append("")

    content = "\n".join(lines)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(content)

    return output_path


def export_pmos_backlog(state: Dict[str, Any]) -> str:
    """Export PM-OS backlog to markdown file with formalized details."""
    backlog = state.get("pm_os_backlog", {})
    bugs = backlog.get("bugs", [])
    features = backlog.get("features", [])

    bot_name = get_mention_bot_name()
    lines = [
        "# PM-OS Backlog (Auto-synced from Slack Mentions)",
        "",
        f"Last updated: {datetime.now().isoformat()}",
        "",
        f"Items below are captured from @{bot_name} mentions in Slack.",
        "",
    ]

    if bugs:
        lines.append("## Bugs (Priority)")
        lines.append("")
        open_bugs = [b for b in bugs if b["status"] == "open"]
        closed_bugs = [b for b in bugs if b["status"] != "open"]

        for bug in open_bugs:
            formalized = bug.get("formalized", {})
            title = (
                formalized.get("title", bug["title"]) if formalized else bug["title"]
            )
            urgency = formalized.get("urgency", "medium") if formalized else "medium"
            urgency_icon = {
                "critical": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "🟢",
            }.get(urgency, "⚪")

            lines.append(f"### {urgency_icon} {title}")
            lines.append("")
            lines.append(f"- **Status:** Open")
            lines.append(
                f"- **Reported:** {bug['created_at'][:10]} by {bug['requester']}"
            )
            lines.append(f"- **Urgency:** {urgency}")

            if formalized:
                if formalized.get("description"):
                    lines.append("")
                    lines.append(f"**Description:** {formalized['description']}")

                if formalized.get("acceptance_criteria"):
                    lines.append("")
                    lines.append("**Fix Criteria:**")
                    for criterion in formalized["acceptance_criteria"]:
                        lines.append(f"- [ ] {criterion}")

            lines.append("")
            lines.append(f"[View in Slack]({bug['thread_link']})")
            lines.append("")

        for bug in closed_bugs:
            lines.append(f"- [x] ~~{bug['title']}~~ (Fixed)")
        if closed_bugs:
            lines.append("")

    if features:
        lines.append("## Feature Requests")
        lines.append("")
        backlog_features = [f for f in features if f["status"] == "backlog"]
        done_features = [f for f in features if f["status"] != "backlog"]

        for feature in backlog_features:
            formalized = feature.get("formalized", {})
            title = (
                formalized.get("title", feature["title"])
                if formalized
                else feature["title"]
            )
            urgency = formalized.get("urgency", "medium") if formalized else "medium"
            urgency_icon = {
                "critical": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "🟢",
            }.get(urgency, "⚪")

            lines.append(f"### {urgency_icon} {title}")
            lines.append("")
            lines.append(f"- **Status:** Backlog")
            lines.append(
                f"- **Requested:** {feature['created_at'][:10]} by {feature['requester']}"
            )
            lines.append(f"- **Priority:** {urgency}")

            if formalized:
                if formalized.get("description"):
                    lines.append("")
                    lines.append(f"**Description:** {formalized['description']}")

                if formalized.get("context_summary"):
                    lines.append("")
                    lines.append(f"**Why:** {formalized['context_summary']}")

                if formalized.get("acceptance_criteria"):
                    lines.append("")
                    lines.append("**Acceptance Criteria:**")
                    for criterion in formalized["acceptance_criteria"]:
                        lines.append(f"- [ ] {criterion}")

                if formalized.get("dependencies"):
                    lines.append("")
                    lines.append("**Dependencies:**")
                    for dep in formalized["dependencies"]:
                        lines.append(f"- {dep}")

            lines.append("")
            lines.append(f"[View in Slack]({feature['thread_link']})")
            lines.append("")

        for feature in done_features:
            lines.append(f"- [x] ~~{feature['title']}~~ (Implemented)")
        if done_features:
            lines.append("")

    if not bugs and not features:
        lines.append("*No items in backlog yet.*")
        lines.append("")

    content = "\n".join(lines)

    os.makedirs(os.path.dirname(PMOS_BACKLOG_FILE), exist_ok=True)
    with open(PMOS_BACKLOG_FILE, "w") as f:
        f.write(content)

    return PMOS_BACKLOG_FILE


def send_acknowledgment(
    client: WebClient, channel: str, ts: str, task: MentionTask
) -> bool:
    """Send acknowledgment reply to captured mention."""
    try:
        type_emoji = {
            "nikita_task": ":clipboard:",
            "team_task": ":busts_in_silhouette:",
            "pmos_feature": ":sparkles:",
            "pmos_bug": ":bug:",
            "general": ":eyes:",
        }

        emoji = type_emoji.get(task.classification, ":memo:")
        assignee_text = f" for *{task.assignee}*" if task.assignee else ""

        message = (
            f"{emoji} Captured{assignee_text}!\n"
            f"_{task.extracted_task[:100]}_\n\n"
            f"React with :white_check_mark: when done."
        )

        client.chat_postMessage(channel=channel, thread_ts=ts, text=message)
        return True

    except SlackApiError as e:
        print(f"Failed to send ack: {e.response['error']}")
        return False


def send_formalized_task_reply(
    client: WebClient,
    channel: str,
    ts: str,
    task: MentionTask,
    formalized: Dict[str, Any],
) -> bool:
    """
    Send a detailed reply with the formalized task for confirmation.

    Args:
        client: Slack WebClient
        channel: Channel ID
        ts: Thread timestamp
        task: The MentionTask
        formalized: The formalized task dict (from FormalizedTask.asdict())

    Returns:
        True if sent successfully
    """
    try:
        # Build urgency indicator
        urgency = formalized.get("urgency", "medium")
        urgency_emoji = {
            "critical": ":red_circle:",
            "high": ":large_orange_circle:",
            "medium": ":large_yellow_circle:",
            "low": ":large_green_circle:",
        }.get(urgency, ":white_circle:")

        # Build type emoji
        task_type = formalized.get("task_type", task.classification)
        type_emoji = {
            "nikita_task": ":clipboard:",
            "team_task": ":busts_in_silhouette:",
            "pmos_feature": ":sparkles:",
            "pmos_bug": ":bug:",
            "general": ":eyes:",
        }.get(task_type, ":memo:")

        # Build blocks for rich formatting
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{formalized.get('title', task.extracted_task)[:150]}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Type:* {type_emoji} {task_type}"},
                    {"type": "mrkdwn", "text": f"*Urgency:* {urgency_emoji} {urgency}"},
                ],
            },
        ]

        # Add assignee/delegator if present
        meta_fields = []
        if formalized.get("assignee"):
            meta_fields.append(
                {"type": "mrkdwn", "text": f"*Assignee:* {formalized['assignee']}"}
            )
        if formalized.get("delegator"):
            meta_fields.append(
                {"type": "mrkdwn", "text": f"*From:* {formalized['delegator']}"}
            )
        if formalized.get("deadline"):
            meta_fields.append(
                {"type": "mrkdwn", "text": f"*Deadline:* {formalized['deadline']}"}
            )

        if meta_fields:
            blocks.append(
                {
                    "type": "section",
                    "fields": meta_fields[:4],  # Slack limits to 10 fields
                }
            )

        # Add context summary
        if formalized.get("context_summary"):
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Context:* {formalized['context_summary'][:500]}",
                    },
                }
            )

        # Add acceptance criteria
        if formalized.get("acceptance_criteria"):
            criteria_text = "*Acceptance Criteria:*\n"
            for criterion in formalized["acceptance_criteria"][:4]:
                criteria_text += f"• {criterion[:100]}\n"
            blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": criteria_text}}
            )

        # Add completion instructions
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": ":white_check_mark: React to mark complete | :x: React to dismiss | Confidence: {:.0%}".format(
                            formalized.get("confidence", 0.8)
                        ),
                    }
                ],
            }
        )

        # Send the message
        client.chat_postMessage(
            channel=channel,
            thread_ts=ts,
            text=f"Task captured: {formalized.get('title', task.extracted_task)}",  # Fallback text
            blocks=blocks,
        )
        return True

    except SlackApiError as e:
        print(f"Failed to send formalized reply: {e.response.get('error', str(e))}")
        return False


def print_status(state: Dict[str, Any]) -> None:
    """Print current mention status."""
    pending = state.get("pending_tasks", [])
    completed = state.get("completed_tasks", [])
    backlog = state.get("pm_os_backlog", {})
    stats = state.get("statistics", {})

    print("\n=== Mention Capture Status ===\n")
    print(f"Total processed: {stats.get('total_processed', 0)}")
    print(f"Pending tasks: {len(pending)}")
    print(f"Completed tasks: {len(completed)}")
    print(f"Completion rate: {stats.get('completion_rate', 0):.1%}")
    print(f"PM-OS bugs: {len(backlog.get('bugs', []))}")
    print(f"PM-OS features: {len(backlog.get('features', []))}")
    print(f"Last poll: {state.get('last_poll', 'Never')}")

    if pending:
        print("\n--- Pending Tasks ---")
        for task in pending[:10]:
            stale = " [STALE]" if task.get("is_stale") else ""
            print(
                f"  [{task['classification']}] {task['extracted_task'][:60]}...{stale}"
            )

        if len(pending) > 10:
            print(f"  ... and {len(pending) - 10} more")


def main():
    parser = argparse.ArgumentParser(description="Slack Mention Handler")
    parser.add_argument(
        "--check-complete", action="store_true", help="Check for completion reactions"
    )
    parser.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--export", action="store_true", help="Export to markdown")
    parser.add_argument(
        "--lookback", type=int, default=24, help="Hours to look back (default: 24)"
    )
    parser.add_argument(
        "--no-ack", action="store_true", help="Don't send acknowledgment replies"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Don't save state or send messages"
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Use LLM to formalize tasks (requires AWS Bedrock)",
    )
    parser.add_argument(
        "--reprocess",
        type=str,
        metavar="MENTION_ID",
        help="Reprocess a specific mention with LLM",
    )

    args = parser.parse_args()

    # Load state
    state = load_state()

    if args.status:
        print_status(state)
        return

    # Get Slack client
    client = get_slack_client()
    if not client:
        print("Error: Could not initialize Slack client")
        sys.exit(1)

    if args.check_complete:
        print("Checking for task completions (reactions + replies)...")
        results = check_all_completions(client, state)
        print(f"Marked {results['total']} task(s) as complete")
        print(f"  - Via reactions: {results['reactions']}")
        print(f"  - Via replies: {results['replies']}")

        if not args.dry_run:
            save_state(state)
        return

    # Reprocess single mention with LLM
    if args.reprocess:
        if not LLM_PROCESSOR_AVAILABLE:
            print("Error: LLM processor not available")
            sys.exit(1)

        # Find the mention in pending tasks OR PM-OS backlog
        target_task = None
        task_location = None

        # Check pending tasks
        for task in state.get("pending_tasks", []):
            if task["id"] == args.reprocess:
                target_task = task
                task_location = "pending"
                break

        # Check PM-OS backlog features
        if not target_task:
            for task in state.get("pm_os_backlog", {}).get("features", []):
                if task["id"] == args.reprocess:
                    target_task = task
                    task_location = "feature"
                    break

        # Check PM-OS backlog bugs
        if not target_task:
            for task in state.get("pm_os_backlog", {}).get("bugs", []):
                if task["id"] == args.reprocess:
                    target_task = task
                    task_location = "bug"
                    break

        if not target_task:
            print(
                f"Error: Mention {args.reprocess} not found in pending tasks or PM-OS backlog"
            )
            sys.exit(1)

        title = target_task.get("extracted_task", target_task.get("title", "Unknown"))
        raw_text = target_task.get("raw_text", target_task.get("description", ""))

        print(f"Reprocessing ({task_location}): {title[:50]}...")
        formalized = process_mention_with_llm(
            raw_text,
            context={
                "channel": target_task.get("source_channel_name", "unknown"),
                "requester": target_task.get(
                    "requester_name", target_task.get("requester", "Unknown")
                ),
                "thread_link": target_task.get("thread_link", ""),
            },
        )

        if formalized:
            # Update task with formalized data
            target_task["formalized"] = asdict(formalized)
            if task_location == "pending":
                target_task["classification"] = formalized.task_type
                target_task["extracted_task"] = formalized.title
                target_task["priority"] = formalized.urgency
                if formalized.assignee:
                    target_task["assignee"] = formalized.assignee
            else:
                # For backlog items, update title
                target_task["title"] = formalized.title

            print("\n" + format_task_markdown(formalized))

            if not args.dry_run:
                save_state(state)
                # Also re-export backlog if it was a PM-OS item
                if task_location in ("feature", "bug"):
                    export_pmos_backlog(state)
                    print(f"\nBacklog updated.")
                print(f"\nState updated.")
        else:
            print("LLM processing failed")
        return

    # Main polling flow
    bot_name = get_mention_bot_name()
    print(f"Polling for @{bot_name} mentions (last {args.lookback}h)...")

    mentions = fetch_bot_mentions(client, state, args.lookback)
    print(f"Found {len(mentions)} new mention(s)")

    new_tasks = []
    for mention in mentions:
        task = process_mention(mention, state)
        formalized_dict = None

        # LLM enhancement if requested
        if args.llm and LLM_PROCESSOR_AVAILABLE:
            print(f"  Enhancing with LLM: {task.extracted_task[:40]}...")

            # Build context for LLM
            llm_context = {
                "channel": mention["channel_name"],
                "requester": mention["user_name"],
                "thread_link": task.thread_link,
            }

            # Add thread context if available
            thread_context = mention.get("thread_context")
            if thread_context and thread_context.get("parent_text"):
                llm_context["thread_context"] = format_thread_context_for_llm(
                    thread_context
                )
                print(
                    f"    Including thread context (parent by {thread_context.get('parent_user_name', 'unknown')})"
                )

            formalized = process_mention_with_llm(mention["text"], context=llm_context)
            if formalized:
                # Enhance task with LLM results
                task.classification = formalized.task_type
                task.extracted_task = formalized.title
                task.priority = formalized.urgency
                if formalized.assignee:
                    task.assignee = formalized.assignee

                # Store full formalized data for state
                formalized_dict = asdict(formalized)

        add_task_to_state(task, state, formalized=formalized_dict)
        new_tasks.append(task)

        # Send acknowledgment (use rich format if we have formalized data)
        if not args.no_ack and not args.dry_run:
            if formalized_dict:
                send_formalized_task_reply(
                    client, mention["channel_id"], mention["ts"], task, formalized_dict
                )
            else:
                send_acknowledgment(client, mention["channel_id"], mention["ts"], task)

    # Check for stale tasks
    stale = detect_stale_tasks(state)
    if stale:
        print(f"Marked {stale} task(s) as stale")

    # Update last poll timestamp
    state["last_poll"] = datetime.now(timezone.utc).isoformat()

    # Save state
    if not args.dry_run:
        save_state(state)
        print(f"State saved to {STATE_FILE}")

    # Export if requested
    if args.export or new_tasks:
        md_path = export_daily_markdown(state)
        print(f"Exported to {md_path}")

        pmos_path = export_pmos_backlog(state)
        print(f"PM-OS backlog exported to {pmos_path}")

    # Print summary
    print(f"\nProcessed {len(new_tasks)} new mention(s)")
    for task in new_tasks:
        print(f"  [{task.classification}] {task.extracted_task[:50]}...")


if __name__ == "__main__":
    main()
