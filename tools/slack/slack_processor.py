#!/usr/bin/env python3
"""
Slack Message Processor - Phase 2

Processes raw extracted Slack messages:
1. Filters noise (bots, joins, reactions-only)
2. Groups threads with parents
3. Tags message types (decision, blocker, question, etc.)
4. Creates batches for LLM analysis

Usage:
    python3 slack_processor.py [--input-dir PATH] [--batch-size N]
    python3 slack_processor.py --status
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# Try to import parser for text resolution
try:
    from slack_mrkdwn_parser import MrkdwnParser
    from slack_user_cache import load_channel_cache, load_user_cache

    PARSER_AVAILABLE = True
except ImportError:
    PARSER_AVAILABLE = False

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = config_loader.get_root_path() / "user" / "brain" / "Inbox" / "Slack"
RAW_DIR = BASE_DIR / "Raw"
PROCESSED_DIR = BASE_DIR / "Processed"
STATE_FILE = BASE_DIR / "processing_state.json"

# Batch configuration
DEFAULT_BATCH_SIZE = 75  # Messages per batch for analysis

# Noise filters - skip these message patterns
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
    "USLACKBOT",  # Slackbot
]

# High-value keywords for tagging
HIGH_VALUE_KEYWORDS = {
    "decision": [
        "decided",
        "decision",
        "agreed",
        "approved",
        "confirmed",
        "finalized",
        "go ahead",
        "green light",
    ],
    "blocker": [
        "blocker",
        "blocked",
        "blocking",
        "stuck",
        "waiting on",
        "dependency",
        "can't proceed",
    ],
    "question": [
        "?",
        "anyone know",
        "does anyone",
        "how do we",
        "what's the",
        "when will",
        "who is",
    ],
    "action": [
        "action item",
        "todo",
        "to do",
        "will do",
        "I'll",
        "let me",
        "can you",
        "please",
    ],
    "deadline": [
        "deadline",
        "due date",
        "by EOD",
        "by EOW",
        "by friday",
        "urgent",
        "asap",
    ],
    "update": [
        "update:",
        "fyi:",
        "heads up",
        "just wanted to",
        "quick update",
        "status:",
    ],
    "announcement": [
        "announcing",
        "announcement",
        "excited to share",
        "please welcome",
        "congrats",
    ],
}

# ============================================================================
# STATE MANAGEMENT
# ============================================================================


def load_state() -> dict:
    """Load processing state from file."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
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


def save_state(state: dict):
    """Save processing state to file."""
    state["last_updated"] = datetime.now().isoformat()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def print_status(state: dict):
    """Print current processing status."""
    print("=" * 60)
    print("SLACK PROCESSING STATUS")
    print("=" * 60)
    print(f"Started: {state.get('started_at', 'Not started')}")
    print(f"Last Updated: {state.get('last_updated', 'N/A')}")
    print(f"Files Processed: {len(state.get('files_processed', []))}")
    print(f"Messages In: {state.get('total_messages_in', 0):,}")
    print(f"Messages Out: {state.get('total_messages_out', 0):,}")
    print(f"Filtered: {state.get('total_filtered', 0):,}")
    print(f"Batches Created: {state.get('batches_created', 0)}")
    print("=" * 60)


# ============================================================================
# FILTERING LOGIC
# ============================================================================


def is_noise_message(msg: dict) -> bool:
    """Check if message is noise that should be filtered."""
    text = msg.get("text", "")

    # Check noise patterns
    for pattern in NOISE_PATTERNS:
        if re.match(pattern, text, re.IGNORECASE):
            return True

    # Skip bot messages (unless they have substantive content)
    if msg.get("bot_id") or msg.get("subtype") == "bot_message":
        # Allow bot messages with significant content
        if len(text) < 50:
            return True

    # Skip very short messages with no thread replies
    if len(text) < 20 and msg.get("reply_count", 0) == 0:
        # Unless it's a reaction to something (keep context)
        if not msg.get("reactions"):
            return True

    # Skip pure emoji messages
    if re.match(r"^:[\w+-]+:$", text.strip()):
        return True

    # Skip messages that are just user mentions with no content
    if re.match(r"^<@\w+>\s*$", text.strip()):
        return True

    return False


def tag_message(msg: dict) -> list:
    """Tag message with relevant categories based on content."""
    text = msg.get("text", "").lower()
    tags = []

    for tag, keywords in HIGH_VALUE_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                tags.append(tag)
                break

    # Additional heuristics
    if msg.get("reply_count", 0) > 5:
        tags.append("discussion")

    if msg.get("reactions"):
        reaction_count = sum(r.get("count", 0) for r in msg["reactions"])
        if reaction_count > 3:
            tags.append("notable")

    # Thread parent with many replies is likely important
    if msg.get("reply_count", 0) > 10:
        tags.append("high_engagement")

    return list(set(tags))  # Dedupe


def calculate_importance(msg: dict, tags: list) -> int:
    """Calculate importance score (0-100) for prioritizing messages."""
    score = 50  # Base score

    # Tag bonuses
    tag_scores = {
        "decision": 30,
        "blocker": 25,
        "deadline": 20,
        "action": 15,
        "discussion": 15,
        "high_engagement": 20,
        "notable": 10,
        "question": 5,
        "update": 5,
        "announcement": 10,
    }

    for tag in tags:
        score += tag_scores.get(tag, 0)

    # Length bonus (substantive content)
    text_len = len(msg.get("text", ""))
    if text_len > 200:
        score += 10
    elif text_len > 500:
        score += 20

    # Thread bonus
    reply_count = msg.get("reply_count", 0)
    score += min(reply_count * 2, 20)

    # Reaction bonus
    if msg.get("reactions"):
        reaction_count = sum(r.get("count", 0) for r in msg["reactions"])
        score += min(reaction_count * 2, 15)

    return min(score, 100)


# ============================================================================
# MESSAGE PROCESSING
# ============================================================================


def process_raw_file(filepath: Path, parser: Optional[object] = None) -> list:
    """
    Process a single raw extraction file.

    Returns:
        list: Processed messages with tags and scores
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
        # Skip noise
        if is_noise_message(msg):
            filtered_count += 1
            continue

        # Parse text if parser available
        raw_text = msg.get("text", "")
        parsed_text = parser.parse(raw_text) if parser else raw_text

        # Tag message
        tags = tag_message(msg)
        importance = calculate_importance(msg, tags)

        # Build processed message
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

        # Include thread replies if present
        if "_thread_replies" in msg:
            thread_replies = []
            for reply in msg["_thread_replies"]:
                if not is_noise_message(reply):
                    reply_text = reply.get("text", "")
                    parsed_reply = parser.parse(reply_text) if parser else reply_text
                    thread_replies.append(
                        {
                            "ts": reply.get("ts"),
                            "user": reply.get("user"),
                            "user_name": (
                                parser.resolve_user(reply.get("user", ""))
                                if parser
                                else reply.get("user")
                            ),
                            "text": parsed_reply,
                        }
                    )
            processed_msg["thread_replies"] = thread_replies

        processed.append(processed_msg)

    return processed, filtered_count


def create_batches(messages: list, batch_size: int = DEFAULT_BATCH_SIZE) -> list:
    """
    Create batches of messages for LLM analysis.

    Groups by:
    1. Channel (keep context together)
    2. Week (temporal grouping)
    3. Thread (keep conversations together)

    Returns:
        list: List of batch dicts with metadata
    """
    batches = []

    # Group by channel first
    by_channel = defaultdict(list)
    for msg in messages:
        by_channel[msg["channel_id"]].append(msg)

    for channel_id, channel_msgs in by_channel.items():
        # Sort by timestamp
        channel_msgs.sort(key=lambda m: float(m.get("ts", 0)))

        # Group threads together
        threads = defaultdict(list)
        standalone = []

        for msg in channel_msgs:
            thread_ts = msg.get("thread_ts")
            if thread_ts and thread_ts != msg.get("ts"):
                # This is a reply - should be in thread_replies, skip
                continue
            elif msg.get("reply_count", 0) > 0:
                # Thread parent with replies
                threads[msg["ts"]].append(msg)
            else:
                standalone.append(msg)

        # Combine threads and standalone into batches
        current_batch = []
        current_size = 0

        # Add threads first (keep together)
        for thread_ts, thread_msgs in threads.items():
            thread_size = len(thread_msgs)
            # Include reply count in size estimate
            for m in thread_msgs:
                thread_size += len(m.get("thread_replies", []))

            if current_size + thread_size > batch_size and current_batch:
                # Save current batch
                batches.append(create_batch_record(current_batch, channel_id))
                current_batch = []
                current_size = 0

            current_batch.extend(thread_msgs)
            current_size += thread_size

        # Add standalone messages
        for msg in standalone:
            if current_size >= batch_size and current_batch:
                batches.append(create_batch_record(current_batch, channel_id))
                current_batch = []
                current_size = 0

            current_batch.append(msg)
            current_size += 1

        # Don't forget the last batch
        if current_batch:
            batches.append(create_batch_record(current_batch, channel_id))

    return batches


def create_batch_record(messages: list, channel_id: str) -> dict:
    """Create a batch record with metadata."""
    if not messages:
        return None

    # Calculate batch statistics
    tags = []
    importance_sum = 0
    for msg in messages:
        tags.extend(msg.get("tags", []))
        importance_sum += msg.get("importance", 50)

    tag_counts = {}
    for tag in tags:
        tag_counts[tag] = tag_counts.get(tag, 0) + 1

    return {
        "batch_id": f"{channel_id}_{messages[0].get('ts', 'unknown')}",
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


def save_batch(batch: dict, batch_num: int):
    """Save a batch to the processed directory."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"batch_{batch_num:04d}.json"
    filepath = PROCESSED_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)

    return filepath


# ============================================================================
# MAIN PIPELINE
# ============================================================================


def find_raw_files() -> list:
    """Find all raw extraction files."""
    if not RAW_DIR.exists():
        return []

    files = []
    for channel_dir in RAW_DIR.iterdir():
        if channel_dir.is_dir():
            for json_file in channel_dir.glob("*.json"):
                files.append(json_file)

    return sorted(files)


def run_processing(batch_size: int = DEFAULT_BATCH_SIZE, resume: bool = True):
    """Run the full processing pipeline."""
    state = load_state()

    # Initialize state if fresh start
    if not state.get("started_at"):
        state["started_at"] = datetime.now().isoformat()
        save_state(state)

    # Setup parser if available
    parser = None
    if PARSER_AVAILABLE:
        try:
            user_cache = load_user_cache()
            channel_cache = load_channel_cache()
            parser = MrkdwnParser(user_cache, channel_cache)
            print("Parser loaded with caches", file=sys.stderr)
        except FileNotFoundError:
            print(
                "Warning: Cache files not found, parsing without resolution",
                file=sys.stderr,
            )
            parser = MrkdwnParser()

    # Find raw files
    raw_files = find_raw_files()
    print(f"Found {len(raw_files)} raw files", file=sys.stderr)

    # Filter already processed
    if resume:
        processed_set = set(state.get("files_processed", []))
        raw_files = [f for f in raw_files if str(f) not in processed_set]
        print(f"Remaining after resume filter: {len(raw_files)}", file=sys.stderr)

    if not raw_files:
        print("No new files to process", file=sys.stderr)
        return

    # Process files
    all_messages = []
    total_filtered = 0

    for filepath in raw_files:
        print(f"Processing: {filepath.name}...", file=sys.stderr, end=" ")

        messages, filtered = process_raw_file(filepath, parser)
        all_messages.extend(messages)
        total_filtered += filtered

        print(f"{len(messages)} kept, {filtered} filtered", file=sys.stderr)

        # Update state
        state["files_processed"].append(str(filepath))
        state["total_messages_in"] = (
            state.get("total_messages_in", 0) + len(messages) + filtered
        )
        state["total_filtered"] = state.get("total_filtered", 0) + filtered
        save_state(state)

    print(f"\nTotal messages to batch: {len(all_messages)}", file=sys.stderr)

    # Create batches
    batches = create_batches(all_messages, batch_size)
    print(f"Created {len(batches)} batches", file=sys.stderr)

    # Save batches
    batch_start = state.get("batches_created", 0)
    for i, batch in enumerate(batches):
        if batch:
            batch_num = batch_start + i + 1
            filepath = save_batch(batch, batch_num)
            print(
                f"  Saved: {filepath.name} ({batch['message_count']} messages)",
                file=sys.stderr,
            )

    # Update state
    state["total_messages_out"] = state.get("total_messages_out", 0) + len(all_messages)
    state["batches_created"] = batch_start + len(batches)
    save_state(state)

    # Summary
    print("\n" + "=" * 60, file=sys.stderr)
    print("PROCESSING COMPLETE", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"Files processed: {len(raw_files)}", file=sys.stderr)
    print(f"Messages in: {state['total_messages_in']:,}", file=sys.stderr)
    print(f"Messages out: {state['total_messages_out']:,}", file=sys.stderr)
    print(f"Filtered: {state['total_filtered']:,}", file=sys.stderr)
    print(f"Batches: {state['batches_created']}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Process raw Slack extractions for analysis"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Messages per batch (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Reprocess all files (don't skip already processed)",
    )
    parser.add_argument(
        "--status", action="store_true", help="Show processing status and exit"
    )

    args = parser.parse_args()

    if args.status:
        state = load_state()
        print_status(state)
        return

    run_processing(batch_size=args.batch_size, resume=not args.no_resume)


if __name__ == "__main__":
    main()
