#!/usr/bin/env python3
"""
Slack Message Processor (v5.0)

Processes raw extracted Slack messages:
1. Filters noise (bots, joins, reactions-only)
2. Groups threads with parents
3. Tags message types (decision, blocker, question, etc.)
4. Creates batches for LLM analysis

Ported from v4.x slack_processor.py — uses path_resolver for all paths,
config_loader for settings, no hardcoded values.

Usage:
    python slack_processor.py [--batch-size N]
    python slack_processor.py --status
"""

import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# v5 shared utils
try:
    from pm_os_base.tools.core.config_loader import get_config
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        _base = __import__("pathlib").Path(__file__).resolve().parent.parent.parent.parent
        sys.path.insert(0, str(_base / "pm-os-base" / "tools" / "core"))
        from config_loader import get_config
        from path_resolver import get_paths
    except ImportError:
        logger.error("Cannot import pm_os_base core modules")
        raise

# Sibling imports
try:
    from .slack_mrkdwn_parser import MrkdwnParser
    from .slack_user_cache import load_channel_cache, load_user_cache
    PARSER_AVAILABLE = True
except ImportError:
    try:
        from slack_mrkdwn_parser import MrkdwnParser
        from slack_user_cache import load_channel_cache, load_user_cache
        PARSER_AVAILABLE = True
    except ImportError:
        PARSER_AVAILABLE = False

# ============================================================================
# PATHS — all from path_resolver
# ============================================================================

def _get_base_dir() -> Path:
    return get_paths().brain / "Inbox" / "Slack"

def _get_raw_dir() -> Path:
    return _get_base_dir() / "Raw"

def _get_processed_dir() -> Path:
    return _get_base_dir() / "Processed"

def _get_state_file() -> Path:
    return _get_base_dir() / "processing_state.json"


# Batch configuration
DEFAULT_BATCH_SIZE = 75

# Noise filters — skip these message patterns
NOISE_PATTERNS = [
    r"^<@\w+> has joined the channel",
    r"^<@\w+> has left the channel",
    r"^<@\w+> set the channel topic",
    r"^<@\w+> set the channel purpose",
    r"^<@\w+> set the channel description",
    r"^<@\w+> renamed the channel",
    r"^<@\w+> archived the channel",
    r"^This message was deleted",
    r"^<@\w+> pinned a message",
    r"^<@\w+> unpinned a message",
]

# Bot user IDs to skip (common integrations)
BOT_PATTERNS = [
    "USLACKBOT",
]

# High-value keywords for tagging
HIGH_VALUE_KEYWORDS = {
    "decision": [
        "decided", "decision", "agreed", "approved", "confirmed",
        "finalized", "go ahead", "green light",
    ],
    "blocker": [
        "blocker", "blocked", "blocking", "stuck", "waiting on",
        "dependency", "can't proceed",
    ],
    "question": [
        "?", "anyone know", "does anyone", "how do we",
        "what's the", "when will", "who is",
    ],
    "action": [
        "action item", "todo", "to do", "will do",
        "I'll", "let me", "can you", "please",
    ],
    "deadline": [
        "deadline", "due date", "by EOD", "by EOW",
        "by friday", "urgent", "asap",
    ],
    "update": [
        "update:", "fyi:", "heads up", "just wanted to",
        "quick update", "status:",
    ],
    "announcement": [
        "announcing", "announcement", "excited to share",
        "please welcome", "congrats",
    ],
}


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

def load_state() -> dict:
    """Load processing state from file."""
    state_file = _get_state_file()
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "started_at": None,
        "last_updated": None,
        "files_processed": [],
        "total_messages_in": 0,
        "total_messages_out": 0,
        "total_filtered": 0,
        "batches_created": 0,
    }


def save_state(state: dict) -> None:
    """Save processing state to file."""
    state["last_updated"] = datetime.now().isoformat()
    state_file = _get_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def print_status(state: dict) -> None:
    """Print current processing status."""
    print("=" * 60)
    print("SLACK PROCESSING STATUS")
    print("=" * 60)
    print("Started: %s" % state.get("started_at", "Not started"))
    print("Last Updated: %s" % state.get("last_updated", "N/A"))
    print("Files Processed: %d" % len(state.get("files_processed", [])))
    print("Messages In: %s" % "{:,}".format(state.get("total_messages_in", 0)))
    print("Messages Out: %s" % "{:,}".format(state.get("total_messages_out", 0)))
    print("Filtered: %s" % "{:,}".format(state.get("total_filtered", 0)))
    print("Batches Created: %d" % state.get("batches_created", 0))
    print("=" * 60)


# ============================================================================
# FILTERING LOGIC
# ============================================================================

def is_noise_message(msg: dict) -> bool:
    """Check if message is noise that should be filtered."""
    text = msg.get("text", "")

    for pattern in NOISE_PATTERNS:
        if re.match(pattern, text, re.IGNORECASE):
            return True

    if msg.get("bot_id") or msg.get("subtype") == "bot_message":
        if len(text) < 50:
            return True

    if len(text) < 20 and msg.get("reply_count", 0) == 0:
        if not msg.get("reactions"):
            return True

    if re.match(r"^:[\w+-]+:$", text.strip()):
        return True

    if re.match(r"^<@\w+>\s*$", text.strip()):
        return True

    return False


def tag_message(msg: dict) -> List[str]:
    """Tag message with relevant categories based on content."""
    text = msg.get("text", "").lower()
    tags = []

    for tag, keywords in HIGH_VALUE_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                tags.append(tag)
                break

    if msg.get("reply_count", 0) > 5:
        tags.append("discussion")

    if msg.get("reactions"):
        reaction_count = sum(r.get("count", 0) for r in msg["reactions"])
        if reaction_count > 3:
            tags.append("notable")

    if msg.get("reply_count", 0) > 10:
        tags.append("high_engagement")

    return list(set(tags))


def calculate_importance(msg: dict, tags: List[str]) -> int:
    """Calculate importance score (0-100) for prioritizing messages."""
    score = 50

    tag_scores = {
        "decision": 30, "blocker": 25, "deadline": 20,
        "action": 15, "discussion": 15, "high_engagement": 20,
        "notable": 10, "question": 5, "update": 5, "announcement": 10,
    }

    for tag in tags:
        score += tag_scores.get(tag, 0)

    text_len = len(msg.get("text", ""))
    if text_len > 500:
        score += 20
    elif text_len > 200:
        score += 10

    reply_count = msg.get("reply_count", 0)
    score += min(reply_count * 2, 20)

    if msg.get("reactions"):
        reaction_count = sum(r.get("count", 0) for r in msg["reactions"])
        score += min(reaction_count * 2, 15)

    return min(score, 100)


# ============================================================================
# MESSAGE PROCESSING
# ============================================================================

def process_raw_file(
    filepath: Path, parser: Optional[object] = None
) -> Tuple[list, int]:
    """
    Process a single raw extraction file.

    Returns:
        Tuple of (processed messages list, filtered count)
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    channel_name = data.get("channel_name", "unknown")
    channel_id = data.get("channel_id", "")
    week = data.get("week", "")
    messages = data.get("messages", [])

    processed = []
    filtered_count = 0

    for msg in messages:
        if is_noise_message(msg):
            filtered_count += 1
            continue

        raw_text = msg.get("text", "")
        parsed_text = parser.parse(raw_text) if parser else raw_text

        tags = tag_message(msg)
        importance = calculate_importance(msg, tags)

        processed_msg = {
            "ts": msg.get("ts"),
            "user": msg.get("user"),
            "user_name": (
                parser.resolve_user(msg.get("user", "")) if parser else msg.get("user")
            ),
            "text": parsed_text,
            "raw_text": raw_text,
            "channel_id": channel_id,
            "channel_name": channel_name,
            "week": week,
            "tags": tags,
            "importance": importance,
            "reply_count": msg.get("reply_count", 0),
            "reactions": msg.get("reactions", []),
            "thread_ts": msg.get("thread_ts"),
        }

        if "_thread_replies" in msg:
            thread_replies = []
            for reply in msg["_thread_replies"]:
                if not is_noise_message(reply):
                    reply_text = reply.get("text", "")
                    parsed_reply = parser.parse(reply_text) if parser else reply_text
                    thread_replies.append({
                        "ts": reply.get("ts"),
                        "user": reply.get("user"),
                        "user_name": (
                            parser.resolve_user(reply.get("user", ""))
                            if parser else reply.get("user")
                        ),
                        "text": parsed_reply,
                    })
            processed_msg["thread_replies"] = thread_replies

        processed.append(processed_msg)

    return processed, filtered_count


def create_batches(messages: list, batch_size: int = DEFAULT_BATCH_SIZE) -> list:
    """
    Create batches of messages for LLM analysis.

    Groups by channel, week, and thread for coherent context.
    """
    batches = []

    by_channel = defaultdict(list)
    for msg in messages:
        by_channel[msg["channel_id"]].append(msg)

    for channel_id, channel_msgs in by_channel.items():
        channel_msgs.sort(key=lambda m: float(m.get("ts", 0)))

        threads = defaultdict(list)
        standalone = []

        for msg in channel_msgs:
            thread_ts = msg.get("thread_ts")
            if thread_ts and thread_ts != msg.get("ts"):
                continue
            elif msg.get("reply_count", 0) > 0:
                threads[msg["ts"]].append(msg)
            else:
                standalone.append(msg)

        current_batch = []
        current_size = 0

        for thread_ts, thread_msgs in threads.items():
            thread_size = len(thread_msgs)
            for m in thread_msgs:
                thread_size += len(m.get("thread_replies", []))

            if current_size + thread_size > batch_size and current_batch:
                batches.append(_create_batch_record(current_batch, channel_id))
                current_batch = []
                current_size = 0

            current_batch.extend(thread_msgs)
            current_size += thread_size

        for msg in standalone:
            if current_size >= batch_size and current_batch:
                batches.append(_create_batch_record(current_batch, channel_id))
                current_batch = []
                current_size = 0
            current_batch.append(msg)
            current_size += 1

        if current_batch:
            batches.append(_create_batch_record(current_batch, channel_id))

    return batches


def _create_batch_record(messages: list, channel_id: str) -> Optional[dict]:
    """Create a batch record with metadata."""
    if not messages:
        return None

    tags = []
    importance_sum = 0
    for msg in messages:
        tags.extend(msg.get("tags", []))
        importance_sum += msg.get("importance", 50)

    tag_counts = {}
    for tag in tags:
        tag_counts[tag] = tag_counts.get(tag, 0) + 1

    return {
        "batch_id": "%s_%s" % (channel_id, messages[0].get("ts", "unknown")),
        "channel_id": channel_id,
        "channel_name": messages[0].get("channel_name", ""),
        "message_count": len(messages),
        "thread_count": sum(1 for m in messages if m.get("reply_count", 0) > 0),
        "avg_importance": importance_sum / len(messages) if messages else 0,
        "tag_summary": tag_counts,
        "time_range": {
            "start": messages[0].get("ts"),
            "end": messages[-1].get("ts"),
        },
        "messages": messages,
    }


def save_batch(batch: dict, batch_num: int) -> Path:
    """Save a batch to the processed directory."""
    processed_dir = _get_processed_dir()
    processed_dir.mkdir(parents=True, exist_ok=True)

    filename = "batch_%04d.json" % batch_num
    filepath = processed_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)

    return filepath


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def find_raw_files() -> list:
    """Find all raw extraction files."""
    raw_dir = _get_raw_dir()
    if not raw_dir.exists():
        return []

    files = []
    for channel_dir in raw_dir.iterdir():
        if channel_dir.is_dir():
            for json_file in channel_dir.glob("*.json"):
                files.append(json_file)

    return sorted(files)


def run_processing(batch_size: int = DEFAULT_BATCH_SIZE, resume: bool = True) -> None:
    """Run the full processing pipeline."""
    state = load_state()

    if not state.get("started_at"):
        state["started_at"] = datetime.now().isoformat()
        save_state(state)

    parser = None
    if PARSER_AVAILABLE:
        try:
            user_cache = load_user_cache()
            channel_cache = load_channel_cache()
            parser = MrkdwnParser(user_cache, channel_cache)
            logger.info("Parser loaded with caches")
        except FileNotFoundError:
            logger.warning("Cache files not found, parsing without resolution")
            parser = MrkdwnParser()

    raw_files = find_raw_files()
    logger.info("Found %d raw files", len(raw_files))

    if resume:
        processed_set = set(state.get("files_processed", []))
        raw_files = [f for f in raw_files if str(f) not in processed_set]
        logger.info("Remaining after resume filter: %d", len(raw_files))

    if not raw_files:
        logger.info("No new files to process")
        return

    all_messages = []
    total_filtered = 0

    for filepath in raw_files:
        logger.info("Processing: %s...", filepath.name)
        messages, filtered = process_raw_file(filepath, parser)
        all_messages.extend(messages)
        total_filtered += filtered
        logger.info("  %d kept, %d filtered", len(messages), filtered)

        state["files_processed"].append(str(filepath))
        state["total_messages_in"] = (
            state.get("total_messages_in", 0) + len(messages) + filtered
        )
        state["total_filtered"] = state.get("total_filtered", 0) + filtered
        save_state(state)

    logger.info("Total messages to batch: %d", len(all_messages))

    batches = create_batches(all_messages, batch_size)
    logger.info("Created %d batches", len(batches))

    batch_start = state.get("batches_created", 0)
    for i, batch in enumerate(batches):
        if batch:
            batch_num = batch_start + i + 1
            filepath = save_batch(batch, batch_num)
            logger.info("  Saved: %s (%d messages)", filepath.name, batch["message_count"])

    state["total_messages_out"] = state.get("total_messages_out", 0) + len(all_messages)
    state["batches_created"] = batch_start + len(batches)
    save_state(state)

    logger.info("=" * 60)
    logger.info("PROCESSING COMPLETE")
    logger.info("Files processed: %d", len(raw_files))
    logger.info("Messages in: %s", "{:,}".format(state["total_messages_in"]))
    logger.info("Messages out: %s", "{:,}".format(state["total_messages_out"]))
    logger.info("Filtered: %s", "{:,}".format(state["total_filtered"]))
    logger.info("Batches: %d", state["batches_created"])


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Process raw Slack extractions for analysis"
    )
    parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
        help="Messages per batch (default: %d)" % DEFAULT_BATCH_SIZE,
    )
    parser.add_argument(
        "--no-resume", action="store_true",
        help="Reprocess all files (don't skip already processed)",
    )
    parser.add_argument(
        "--status", action="store_true", help="Show processing status and exit"
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.status:
        state = load_state()
        print_status(state)
        return

    run_processing(batch_size=args.batch_size, resume=not args.no_resume)


if __name__ == "__main__":
    main()
