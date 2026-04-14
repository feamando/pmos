#!/usr/bin/env python3
"""
Slack Mention Handler (v5.0)

Captures, classifies, and tracks bot mentions from Slack.
Routes mentions to:
- Daily context (tasks for user/team)
- PM-OS backlog (feature requests, bugs)
- Review queue (general mentions)

Ported from v4.x slack_mention_handler.py — all hardcoded values removed,
auth via connector_bridge, paths via path_resolver, config via config_loader.

Usage:
    python slack_mention_handler.py                    # Poll for new mentions
    python slack_mention_handler.py --check-complete   # Check for completion reactions
    python slack_mention_handler.py --status           # Show pending tasks
    python slack_mention_handler.py --export           # Export to markdown
"""

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

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

# Sibling imports
try:
    from .slack_mention_classifier import ClassificationResult, MentionType, classify_mention
except ImportError:
    try:
        from slack_mention_classifier import ClassificationResult, MentionType, classify_mention
    except ImportError:
        logger.error("Cannot import slack_mention_classifier")
        raise

# LLM processor for enhanced task formalization
try:
    from .slack_mention_llm_processor import (
        FormalizedTask, format_task_markdown, process_mention_with_llm,
    )
    LLM_PROCESSOR_AVAILABLE = True
except ImportError:
    try:
        from slack_mention_llm_processor import (
            FormalizedTask, format_task_markdown, process_mention_with_llm,
        )
        LLM_PROCESSOR_AVAILABLE = True
    except ImportError:
        LLM_PROCESSOR_AVAILABLE = False


# ============================================================================
# CONFIG-DRIVEN VALUES (no hardcoding)
# ============================================================================

def _get_bot_name() -> str:
    """Get configurable bot name from config."""
    return get_config().get("integrations.slack.bot_name", "")


def _get_team_domain() -> str:
    """Get Slack team domain from config."""
    return get_config().get("integrations.slack.team_domain", "")


def _get_mentions_dir() -> str:
    return str(get_paths().brain / "Inbox" / "Slack" / "Mentions")


def _get_state_file() -> str:
    return os.path.join(_get_mentions_dir(), "mentions_state.json")


def _get_backlog_file() -> str:
    return str(get_paths().brain / "Products" / "PM-OS" / "mention_backlog.md")


# Configuration — Bot User ID can be set via env var or auto-discovered
BOT_USER_ID = os.getenv("SLACK_BOT_USER_ID")

# Completion reaction names
COMPLETION_REACTIONS = [
    "white_check_mark", "heavy_check_mark", "done", "completed", "check",
]

# Completion reply patterns
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
]

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
        return None


def get_bot_user_id(client) -> Optional[str]:
    """Get bot user ID from env var or auto-discover via auth.test."""
    global BOT_USER_ID
    if BOT_USER_ID:
        return BOT_USER_ID

    from slack_sdk.errors import SlackApiError

    try:
        response = client.auth_test()
        BOT_USER_ID = response["user_id"]
        logger.info("Auto-discovered bot user ID: %s", BOT_USER_ID)
        return BOT_USER_ID
    except SlackApiError as e:
        logger.error("Error discovering bot ID: %s", e.response["error"])
        return None


def _get_bot_mention_pattern(client=None) -> str:
    """Get the mention pattern for the bot."""
    bot_id = BOT_USER_ID or (get_bot_user_id(client) if client else None)
    if not bot_id:
        raise ValueError(
            "Bot user ID not configured. Set SLACK_BOT_USER_ID in .env "
            "or ensure bot token is valid."
        )
    return "<@%s>" % bot_id


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

def load_state() -> Dict[str, Any]:
    """Load mention state from file."""
    state_file = _get_state_file()
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
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
    state_file = _get_state_file()
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


def generate_mention_id(channel_id: str, ts: str) -> str:
    """Generate unique ID for a mention."""
    return "mention_%s_%s" % (channel_id, ts.replace(".", "_"))


def get_thread_link(channel_id: str, ts: str) -> str:
    """Generate Slack thread link using config team domain."""
    team_domain = _get_team_domain()
    ts_formatted = ts.replace(".", "")
    return "https://%s.slack.com/archives/%s/p%s" % (team_domain, channel_id, ts_formatted)


# ============================================================================
# USER/CHANNEL RESOLUTION
# ============================================================================

def resolve_user_name(client, user_id: str) -> str:
    """Resolve user ID to display name."""
    from slack_sdk.errors import SlackApiError

    try:
        response = client.users_info(user=user_id)
        user = response["user"]
        return user.get("real_name") or user.get("name") or user_id
    except SlackApiError:
        return user_id


def resolve_channel_name(client, channel_id: str) -> str:
    """Resolve channel ID to name."""
    from slack_sdk.errors import SlackApiError

    try:
        response = client.conversations_info(channel=channel_id)
        return response["channel"].get("name", channel_id)
    except SlackApiError:
        return channel_id


# ============================================================================
# MESSAGE FILTERING
# ============================================================================

def should_skip_message(msg: Dict[str, Any], user_id: str, bot_id: str) -> bool:
    """Check if a message should be skipped (noise filtering)."""
    if user_id == bot_id:
        return True

    subtype = msg.get("subtype", "")
    if subtype in [
        "channel_join", "channel_leave", "channel_topic", "channel_purpose",
        "bot_message", "me_message", "file_share", "pinned_item", "unpinned_item",
    ]:
        return True

    text = msg.get("text", "")
    bot_pattern = "<@%s>" % bot_id
    cleaned = text.replace(bot_pattern, "").strip()
    bot_name = _get_bot_name()
    if bot_name:
        cleaned = cleaned.replace("@%s" % bot_name, "").strip()
    if len(cleaned) < 5:
        return True

    if "has joined the channel" in text or "has left the channel" in text:
        return True

    return False


# ============================================================================
# THREAD CONTEXT
# ============================================================================

def fetch_thread_context(
    client, channel_id: str, thread_ts: str, limit: int = 5,
) -> Dict[str, Any]:
    """Fetch context from a thread (parent message and recent replies)."""
    from slack_sdk.errors import SlackApiError

    context = {
        "parent_text": "", "parent_user": "", "parent_user_name": "",
        "replies": [], "reply_count": 0,
    }

    try:
        response = client.conversations_replies(
            channel=channel_id, ts=thread_ts, limit=limit + 1
        )
        messages = response.get("messages", [])
        if not messages:
            return context

        parent = messages[0]
        context["parent_text"] = parent.get("text", "")
        context["parent_user"] = parent.get("user", "")
        context["parent_user_name"] = resolve_user_name(client, parent.get("user", ""))
        context["reply_count"] = parent.get("reply_count", len(messages) - 1)

        for msg in messages[1: limit + 1]:
            reply_user = resolve_user_name(client, msg.get("user", ""))
            context["replies"].append({
                "user": reply_user,
                "text": msg.get("text", "")[:500],
            })

    except SlackApiError as e:
        logger.warning("Error fetching thread context: %s", e.response.get("error", str(e)))

    return context


def format_thread_context_for_llm(context: Dict[str, Any]) -> str:
    """Format thread context for inclusion in LLM prompt."""
    if not context.get("parent_text"):
        return ""

    parts = []
    parts.append(
        "**Thread Parent (%s):** %s" % (context["parent_user_name"], context["parent_text"][:500])
    )

    if context.get("replies"):
        parts.append("\n**Thread Replies:**")
        for reply in context["replies"][:3]:
            parts.append("- %s: %s" % (reply["user"], reply["text"][:200]))

    return "\n".join(parts)


# ============================================================================
# MENTION POLLING
# ============================================================================

def fetch_bot_mentions(
    client, state: Dict[str, Any], lookback_hours: int = 24,
) -> List[Dict[str, Any]]:
    """Fetch messages mentioning the bot from all accessible channels."""
    from slack_sdk.errors import SlackApiError

    mentions = []
    bot_id = get_bot_user_id(client)
    bot_mention_pattern = "<@%s>" % bot_id

    state["bot_user_id"] = bot_id

    if state.get("last_poll"):
        since = datetime.fromisoformat(state["last_poll"])
    else:
        since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    since_ts = str(since.timestamp())

    try:
        response = client.users_conversations(types="public_channel,private_channel")
        channels = response["channels"]

        logger.info(
            "Scanning %d channels for mentions since %s", len(channels), since.isoformat()
        )

        for channel in channels:
            channel_id = channel["id"]
            channel_name = channel.get("name", channel_id)

            try:
                history = client.conversations_history(
                    channel=channel_id, oldest=since_ts, limit=100
                )

                for msg in history.get("messages", []):
                    text = msg.get("text", "")
                    msg_user_id = msg.get("user", "unknown")

                    bot_name = _get_bot_name()
                    if bot_mention_pattern in text or (
                        bot_name and ("@%s" % bot_name) in text.lower()
                    ):
                        if should_skip_message(msg, msg_user_id, bot_id):
                            continue

                        unique_id = generate_mention_id(channel_id, msg["ts"])
                        if unique_id in state.get("processed_mentions", {}):
                            continue

                        mention = {
                            "ts": msg["ts"],
                            "user": msg_user_id,
                            "text": text,
                            "channel_id": channel_id,
                            "channel_name": channel_name,
                            "unique_id": unique_id,
                            "thread_ts": msg.get("thread_ts"),
                            "reply_count": msg.get("reply_count", 0),
                            "thread_context": None,
                        }

                        mention["user_name"] = resolve_user_name(client, mention["user"])

                        thread_ts = msg.get("thread_ts")
                        if thread_ts and thread_ts != msg["ts"]:
                            logger.debug("Fetching thread context for reply...")
                            mention["thread_context"] = fetch_thread_context(
                                client, channel_id, thread_ts
                            )

                        mentions.append(mention)
                        logger.info(
                            "  Found mention in #%s from %s",
                            channel_name, mention["user_name"],
                        )

            except SlackApiError as e:
                logger.warning(
                    "Error fetching from #%s: %s", channel_name, e.response["error"]
                )
                continue

    except SlackApiError as e:
        logger.error("Error listing channels: %s", e.response["error"])

    return mentions


# ============================================================================
# MENTION PROCESSING
# ============================================================================

def process_mention(mention: Dict[str, Any], state: Dict[str, Any]) -> MentionTask:
    """Process a single mention and classify it."""
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
    task: MentionTask, state: Dict[str, Any],
    formalized: Optional[Dict[str, Any]] = None,
) -> None:
    """Add a processed task to the appropriate state location."""
    task_dict = asdict(task)

    if formalized:
        task_dict["formalized"] = formalized

    state["processed_mentions"][task.id] = {
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "classification": task.classification,
        "status": "pending",
    }

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
        state["pending_tasks"].append(task_dict)

    state["statistics"]["total_processed"] += 1
    type_counts = state["statistics"].setdefault("by_type", {})
    type_counts[task.classification] = type_counts.get(task.classification, 0) + 1


# ============================================================================
# COMPLETION DETECTION
# ============================================================================

def check_completion_reactions(client, state: Dict[str, Any]) -> int:
    """Check pending tasks for completion reactions."""
    from slack_sdk.errors import SlackApiError

    completed_count = 0
    pending = state.get("pending_tasks", [])
    completed = state.setdefault("completed_tasks", [])

    for task in pending[:]:
        try:
            response = client.reactions_get(
                channel=task["source_channel"], timestamp=task["source_ts"]
            )
            message = response.get("message", {})
            reactions = message.get("reactions", [])

            for reaction in reactions:
                if reaction["name"] in COMPLETION_REACTIONS:
                    task["status"] = "completed"
                    task["completed_at"] = datetime.now(timezone.utc).isoformat()
                    task["completed_by"] = "reaction"
                    task["completion_reaction"] = reaction["name"]

                    pending.remove(task)
                    completed.append(task)

                    if task["id"] in state["processed_mentions"]:
                        state["processed_mentions"][task["id"]]["status"] = "completed"

                    completed_count += 1
                    logger.info("Marked complete: %s...", task["extracted_task"][:50])
                    break

        except SlackApiError as e:
            logger.warning(
                "Error checking reactions for %s: %s", task["id"], e.response["error"]
            )
            continue

    total = len(pending) + len(completed)
    if total > 0:
        state["statistics"]["completion_rate"] = len(completed) / total

    return completed_count


def check_completion_replies(client, state: Dict[str, Any]) -> int:
    """Check pending tasks for 'DONE' thread replies."""
    from slack_sdk.errors import SlackApiError

    completed_count = 0
    pending = state.get("pending_tasks", [])
    completed = state.setdefault("completed_tasks", [])

    for task in pending[:]:
        try:
            response = client.conversations_replies(
                channel=task["source_channel"],
                ts=task["source_ts"],
                limit=20,
            )
            messages = response.get("messages", [])
            for reply in messages[1:]:
                reply_text = reply.get("text", "").strip()
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
                            state["processed_mentions"][task["id"]]["status"] = "completed"

                        completed_count += 1
                        logger.info(
                            "Marked complete (reply): %s...", task["extracted_task"][:50]
                        )
                        break

                if task["status"] == "completed":
                    break

        except SlackApiError as e:
            logger.warning(
                "Error checking replies for %s: %s",
                task["id"], e.response.get("error", str(e)),
            )
            continue

    total = len(pending) + len(completed)
    if total > 0:
        state["statistics"]["completion_rate"] = len(completed) / total

    return completed_count


def check_all_completions(client, state: Dict[str, Any]) -> Dict[str, int]:
    """Check for task completions via both reactions AND replies."""
    reaction_count = check_completion_reactions(client, state)
    reply_count = check_completion_replies(client, state)
    return {
        "reactions": reaction_count,
        "replies": reply_count,
        "total": reaction_count + reply_count,
    }


# ============================================================================
# CONTEXT INTEGRATION
# ============================================================================

def get_pending_tasks_for_context() -> Dict[str, Any]:
    """Get pending mention tasks formatted for daily context inclusion."""
    state = load_state()
    pending = state.get("pending_tasks", [])
    backlog = state.get("pm_os_backlog", {})

    result = {
        "owner_tasks": [],
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

        if task["classification"] == "owner_task":
            result["owner_tasks"].append(task_summary)
        elif task["classification"] == "team_task":
            result["team_tasks"].append(task_summary)
        else:
            result["general"].append(task_summary)

    return result


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


# ============================================================================
# EXPORT
# ============================================================================

def export_daily_markdown(
    state: Dict[str, Any], output_path: Optional[str] = None,
) -> str:
    """Export mentions to daily markdown file."""
    today = datetime.now().strftime("%Y-%m-%d")
    if not output_path:
        output_path = os.path.join(_get_mentions_dir(), "MENTIONS_%s.md" % today)

    lines = [
        "# Mention Capture: %s" % today,
        "",
        "Generated: %s" % datetime.now().isoformat(),
        "",
    ]

    pending = state.get("pending_tasks", [])
    user_name = get_config().get("user.name", "User")

    owner_tasks = [t for t in pending if t["classification"] == "owner_task"]
    team_tasks = [t for t in pending if t["classification"] == "team_task"]
    general = [t for t in pending if t["classification"] == "general"]

    if owner_tasks:
        lines.append("## Tasks for %s" % user_name)
        lines.append("")
        for task in owner_tasks:
            checkbox = "[ ]" if task["status"] == "pending" else "[x]"
            stale_marker = " (STALE)" if task.get("is_stale") else ""
            lines.append("- %s %s%s" % (checkbox, task["extracted_task"], stale_marker))
            lines.append(
                "  - From: @%s in #%s" % (task["requester_name"], task["source_channel_name"])
            )
            lines.append("  - [Thread](%s)" % task["thread_link"])
        lines.append("")

    if team_tasks:
        lines.append("## Team Delegation Tracking")
        lines.append("")
        for task in team_tasks:
            checkbox = "[ ]" if task["status"] == "pending" else "[x]"
            stale_marker = " (STALE)" if task.get("is_stale") else ""
            lines.append(
                "- %s **%s**: %s%s" % (
                    checkbox, task.get("assignee", "Unassigned"),
                    task["extracted_task"], stale_marker,
                )
            )
            lines.append("  - From: @%s" % task["requester_name"])
            lines.append("  - [Thread](%s)" % task["thread_link"])
        lines.append("")

    if general:
        lines.append("## General Mentions (Review Queue)")
        lines.append("")
        for task in general:
            lines.append("- %s" % task["extracted_task"][:100])
            lines.append(
                "  - From: @%s in #%s" % (task["requester_name"], task["source_channel_name"])
            )
        lines.append("")

    stats = state.get("statistics", {})
    lines.append("## Statistics")
    lines.append("")
    lines.append("- Total processed: %d" % stats.get("total_processed", 0))
    lines.append("- Completion rate: %.1f%%" % (stats.get("completion_rate", 0) * 100))
    lines.append("- Pending tasks: %d" % len(pending))
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
    backlog_file = _get_backlog_file()

    bot_name = _get_bot_name()
    lines = [
        "# PM-OS Backlog (Auto-synced from Slack Mentions)",
        "",
        "Last updated: %s" % datetime.now().isoformat(),
        "",
    ]
    if bot_name:
        lines.append("Items below are captured from @%s mentions in Slack." % bot_name)
        lines.append("")

    if bugs:
        lines.append("## Bugs (Priority)")
        lines.append("")
        open_bugs = [b for b in bugs if b["status"] == "open"]
        for bug in open_bugs:
            formalized = bug.get("formalized", {})
            title = formalized.get("title", bug["title"]) if formalized else bug["title"]
            lines.append("### %s" % title)
            lines.append("")
            lines.append("- **Status:** Open")
            lines.append(
                "- **Reported:** %s by %s" % (bug["created_at"][:10], bug["requester"])
            )
            if formalized and formalized.get("description"):
                lines.append("")
                lines.append("**Description:** %s" % formalized["description"])
            lines.append("")
            lines.append("[View in Slack](%s)" % bug["thread_link"])
            lines.append("")

    if features:
        lines.append("## Feature Requests")
        lines.append("")
        backlog_features = [f for f in features if f["status"] == "backlog"]
        for feature in backlog_features:
            formalized = feature.get("formalized", {})
            title = formalized.get("title", feature["title"]) if formalized else feature["title"]
            lines.append("### %s" % title)
            lines.append("")
            lines.append("- **Status:** Backlog")
            lines.append(
                "- **Requested:** %s by %s" % (feature["created_at"][:10], feature["requester"])
            )
            if formalized and formalized.get("description"):
                lines.append("")
                lines.append("**Description:** %s" % formalized["description"])
            lines.append("")
            lines.append("[View in Slack](%s)" % feature["thread_link"])
            lines.append("")

    if not bugs and not features:
        lines.append("*No items in backlog yet.*")
        lines.append("")

    content = "\n".join(lines)
    os.makedirs(os.path.dirname(backlog_file), exist_ok=True)
    with open(backlog_file, "w") as f:
        f.write(content)

    return backlog_file


# ============================================================================
# STATUS
# ============================================================================

def print_mention_status(state: Dict[str, Any]) -> None:
    """Print current mention status."""
    pending = state.get("pending_tasks", [])
    completed = state.get("completed_tasks", [])
    backlog = state.get("pm_os_backlog", {})
    stats = state.get("statistics", {})

    print("\n=== Mention Capture Status ===\n")
    print("Total processed: %d" % stats.get("total_processed", 0))
    print("Pending tasks: %d" % len(pending))
    print("Completed tasks: %d" % len(completed))
    print("Completion rate: %.1f%%" % (stats.get("completion_rate", 0) * 100))
    print("PM-OS bugs: %d" % len(backlog.get("bugs", [])))
    print("PM-OS features: %d" % len(backlog.get("features", [])))
    print("Last poll: %s" % state.get("last_poll", "Never"))

    if pending:
        print("\n--- Pending Tasks ---")
        for task in pending[:10]:
            stale = " [STALE]" if task.get("is_stale") else ""
            print(
                "  [%s] %s...%s" % (task["classification"], task["extracted_task"][:60], stale)
            )
        if len(pending) > 10:
            print("  ... and %d more" % (len(pending) - 10))


# ============================================================================
# CLI
# ============================================================================

def main() -> None:
    """CLI entry point."""
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
        "--llm", action="store_true",
        help="Use LLM to formalize tasks (requires AWS Bedrock)",
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    state = load_state()

    if args.status:
        print_mention_status(state)
        return

    client = _get_slack_client()
    if not client:
        logger.error("Could not initialize Slack client")
        sys.exit(1)

    if args.check_complete:
        logger.info("Checking for task completions (reactions + replies)...")
        results = check_all_completions(client, state)
        logger.info("Marked %d task(s) as complete", results["total"])
        logger.info("  Via reactions: %d", results["reactions"])
        logger.info("  Via replies: %d", results["replies"])
        if not args.dry_run:
            save_state(state)
        return

    # Main polling flow
    bot_name = _get_bot_name()
    logger.info("Polling for @%s mentions (last %dh)...", bot_name, args.lookback)

    mentions = fetch_bot_mentions(client, state, args.lookback)
    logger.info("Found %d new mention(s)", len(mentions))

    new_tasks = []
    for mention in mentions:
        task = process_mention(mention, state)
        formalized_dict = None

        if args.llm and LLM_PROCESSOR_AVAILABLE:
            logger.info("  Enhancing with LLM: %s...", task.extracted_task[:40])
            llm_context = {
                "channel": mention["channel_name"],
                "requester": mention["user_name"],
                "thread_link": task.thread_link,
            }
            thread_context = mention.get("thread_context")
            if thread_context and thread_context.get("parent_text"):
                llm_context["thread_context"] = format_thread_context_for_llm(thread_context)

            formalized = process_mention_with_llm(mention["text"], context=llm_context)
            if formalized:
                task.classification = formalized.task_type
                task.extracted_task = formalized.title
                task.priority = formalized.urgency
                if formalized.assignee:
                    task.assignee = formalized.assignee
                formalized_dict = asdict(formalized)

        add_task_to_state(task, state, formalized=formalized_dict)
        new_tasks.append(task)

    stale = detect_stale_tasks(state)
    if stale:
        logger.info("Marked %d task(s) as stale", stale)

    state["last_poll"] = datetime.now(timezone.utc).isoformat()

    if not args.dry_run:
        save_state(state)
        logger.info("State saved to %s", _get_state_file())

    if args.export or new_tasks:
        md_path = export_daily_markdown(state)
        logger.info("Exported to %s", md_path)
        pmos_path = export_pmos_backlog(state)
        logger.info("PM-OS backlog exported to %s", pmos_path)

    logger.info("Processed %d new mention(s)", len(new_tasks))
    for task in new_tasks:
        logger.info("  [%s] %s...", task.classification, task.extracted_task[:50])


if __name__ == "__main__":
    main()
