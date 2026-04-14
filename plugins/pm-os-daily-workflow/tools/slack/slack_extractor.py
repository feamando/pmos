#!/usr/bin/env python3
"""
Slack Message Extractor (v5.0)

Extracts messages from Slack channels with thread support
and Brain-compatible formatting.

Ported from v4.x slack_extractor.py — uses connector_bridge for auth,
config_loader for all settings, path_resolver for paths.

Usage:
    python slack_extractor.py --channel general --days 7
    python slack_extractor.py --channel_id C12345 --brain-format
    python slack_extractor.py --list-channels
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta
from typing import List, Optional

logger = logging.getLogger(__name__)

# v5 shared utils — graceful import
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
    from .slack_mrkdwn_parser import MrkdwnParser, format_message_for_brain
    from .slack_user_cache import load_channel_cache, load_user_cache
    CACHE_AVAILABLE = True
except ImportError:
    try:
        from slack_mrkdwn_parser import MrkdwnParser, format_message_for_brain
        from slack_user_cache import load_channel_cache, load_user_cache
        CACHE_AVAILABLE = True
    except ImportError:
        CACHE_AVAILABLE = False


def _get_slack_client():
    """Get authenticated Slack client via connector_bridge."""
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError  # noqa: F401

    auth = get_auth("slack")
    if auth.source == "env":
        return WebClient(token=auth.token)
    elif auth.source == "connector":
        logger.info("Slack connector available — using connector auth")
        return WebClient(token=auth.token) if auth.token else None
    else:
        logger.error("Slack auth not available: %s", auth.help_message)
        raise ValueError(auth.help_message)


def _get_parser() -> Optional[MrkdwnParser]:
    """Get mrkdwn parser with caches if available."""
    if not CACHE_AVAILABLE:
        return None
    try:
        user_cache = load_user_cache()
        channel_cache = load_channel_cache()
        return MrkdwnParser(user_cache, channel_cache)
    except FileNotFoundError:
        logger.warning("Cache files not found. Run slack_user_cache.py first.")
        return MrkdwnParser()


def fetch_thread_replies(client, channel_id: str, thread_ts: str) -> List[dict]:
    """
    Fetch all replies in a thread.

    Args:
        client: Slack WebClient
        channel_id: Channel containing the thread
        thread_ts: Thread parent timestamp

    Returns:
        List of reply messages (excluding parent)
    """
    from slack_sdk.errors import SlackApiError

    replies = []
    cursor = None

    while True:
        try:
            response = client.conversations_replies(
                channel=channel_id, ts=thread_ts, cursor=cursor, limit=200
            )
            messages = response.get("messages", [])
            if cursor is None and len(messages) > 1:
                replies.extend(messages[1:])
            elif cursor:
                replies.extend(messages)

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        except SlackApiError as e:
            if e.response["error"] == "ratelimited":
                retry_after = int(e.response.headers.get("Retry-After", 2))
                logger.warning("Rate limited, waiting %ss...", retry_after)
                time.sleep(retry_after)
                continue
            elif e.response["error"] == "thread_not_found":
                break
            else:
                logger.error("Error fetching thread: %s", e)
                break

    return replies


def find_channel_id(client, channel_name: str) -> Optional[str]:
    """Find a channel ID by name, paginating through all channels."""
    from slack_sdk.errors import SlackApiError

    try:
        if channel_name.startswith("#"):
            channel_name = channel_name[1:]

        cursor = None
        while True:
            try:
                response = client.conversations_list(
                    cursor=cursor, types="public_channel,private_channel", limit=200
                )
            except SlackApiError as e:
                if e.response["error"] == "ratelimited":
                    retry_after = int(e.response.headers.get("Retry-After", 1))
                    logger.warning("Rate limited. Sleeping for %s seconds...", retry_after)
                    time.sleep(retry_after)
                    continue
                else:
                    raise

            for channel in response["channels"]:
                if channel["name"] == channel_name:
                    return channel["id"]

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        return None
    except SlackApiError as e:
        logger.error("Error finding channel: %s", e)
        return None


def find_user_id(client, user_name: str) -> Optional[str]:
    """Find a user ID by name, checking real name, display name, and username."""
    from slack_sdk.errors import SlackApiError

    try:
        cursor = None
        while True:
            response = client.users_list(cursor=cursor)
            for user in response["members"]:
                real_name = user.get("real_name", "").lower()
                display_name = user.get("profile", {}).get("display_name", "").lower()
                name = user.get("name", "").lower()
                search_name = user_name.lower()

                if (
                    search_name in real_name
                    or search_name in display_name
                    or search_name == name
                ):
                    return user["id"]

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        return None
    except SlackApiError as e:
        logger.error("Error finding user: %s", e)
        return None


def extract_messages(
    channel_name: Optional[str] = None,
    channel_id: Optional[str] = None,
    user_name: Optional[str] = None,
    days: int = 7,
    include_threads: bool = True,
    format_for_brain: bool = False,
    output_file: Optional[str] = None,
) -> None:
    """
    Extract messages from a Slack channel.

    Args:
        channel_name: Channel name to search for
        channel_id: Direct channel ID (skips lookup)
        user_name: Filter by user name
        days: Days to look back
        include_threads: Fetch thread replies
        format_for_brain: Use Brain-compatible markdown format
        output_file: Write to file instead of stdout
    """
    from slack_sdk.errors import SlackApiError

    client = _get_slack_client()
    parser = _get_parser()

    if not channel_id:
        if not channel_name:
            logger.error("Must provide either --channel or --channel_id")
            return
        logger.info("Looking for channel: %s", channel_name)
        channel_id = find_channel_id(client, channel_name)
        if not channel_id:
            logger.error("Could not find channel: %s", channel_name)
            return
    else:
        logger.info("Using provided Channel ID: %s", channel_id)

    user_id = None
    if user_name:
        logger.info("Looking for user: %s", user_name)
        user_id = find_user_id(client, user_name)
        if not user_id:
            logger.error("Could not find user: %s", user_name)
            return
        logger.info("Found User ID: %s", user_id)

    resolved_channel_name = channel_name
    if parser and channel_id in parser.channel_cache:
        resolved_channel_name = parser.channel_cache[channel_id].get(
            "name", channel_name
        )

    logger.info(
        "Extracting messages from #%s (%s)...", resolved_channel_name, channel_id
    )

    output_lines = []
    output_lines.append("# Slack: #%s" % resolved_channel_name)
    output_lines.append("Extracted: %s" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    output_lines.append("Period: Last %d days" % days)
    output_lines.append("")

    try:
        oldest = (datetime.now() - timedelta(days=days)).timestamp()
        cursor = None
        all_messages = []

        while True:
            try:
                result = client.conversations_history(
                    channel=channel_id, oldest=str(oldest), cursor=cursor, limit=200
                )
                all_messages.extend(result.get("messages", []))
                cursor = result.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
            except SlackApiError as e:
                if e.response["error"] == "ratelimited":
                    retry_after = int(e.response.headers.get("Retry-After", 2))
                    logger.warning("Rate limited, waiting %ss...", retry_after)
                    time.sleep(retry_after)
                    continue
                else:
                    raise

        logger.info("Found %d messages in the last %d days.", len(all_messages), days)
        all_messages.sort(key=lambda m: float(m.get("ts", 0)))

        count = 0
        thread_count = 0

        for msg in all_messages:
            if user_id and msg.get("user") != user_id:
                continue

            msg_ts = msg.get("ts", "")
            msg_user = msg.get("user", "Unknown")
            msg_text = msg.get("text", "")
            reactions = msg.get("reactions", [])

            if format_for_brain and parser:
                formatted = format_message_for_brain(
                    text=msg_text,
                    user_id=msg_user,
                    timestamp=msg_ts,
                    parser=parser,
                    channel_name=resolved_channel_name,
                    reactions=reactions,
                )
                output_lines.append(formatted)
            else:
                ts_str = datetime.fromtimestamp(float(msg_ts)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                sender = parser.resolve_user(msg_user) if parser else msg_user
                parsed_text = parser.parse(msg_text) if parser else msg_text

                output_lines.append("\n### %s (%s)" % (sender, ts_str))
                output_lines.append(parsed_text)

                if reactions:
                    reaction_str = " ".join(
                        [":%s:(%d)" % (r["name"], r.get("count", 1)) for r in reactions]
                    )
                    output_lines.append("*Reactions: %s*" % reaction_str)

            count += 1

            if include_threads and msg.get("reply_count", 0) > 0:
                replies = fetch_thread_replies(client, channel_id, msg_ts)
                for reply in replies:
                    if user_id and reply.get("user") != user_id:
                        continue

                    reply_ts = reply.get("ts", "")
                    reply_user = reply.get("user", "Unknown")
                    reply_text = reply.get("text", "")
                    reply_reactions = reply.get("reactions", [])

                    if format_for_brain and parser:
                        formatted = format_message_for_brain(
                            text=reply_text,
                            user_id=reply_user,
                            timestamp=reply_ts,
                            parser=parser,
                            channel_name=resolved_channel_name,
                            thread_ts=msg_ts,
                            reactions=reply_reactions,
                        )
                        output_lines.append(formatted)
                    else:
                        ts_str = datetime.fromtimestamp(float(reply_ts)).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        sender = parser.resolve_user(reply_user) if parser else reply_user
                        parsed_text = parser.parse(reply_text) if parser else reply_text
                        output_lines.append("\n> **%s** (%s) [reply]" % (sender, ts_str))
                        output_lines.append("> %s" % parsed_text)

                    thread_count += 1

        output_lines.append("")
        output_lines.append("---")
        output_lines.append("*Total: %d messages, %d thread replies*" % (count, thread_count))

        output_text = "\n".join(output_lines)

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(output_text)
            logger.info("Written to: %s", output_file)
        else:
            print(output_text)

        logger.info("Total: %d messages, %d thread replies", count, thread_count)

    except SlackApiError as e:
        logger.error("Error extracting messages: %s", e)


def list_bot_channels() -> None:
    """List all channels where the bot is a member."""
    from slack_sdk.errors import SlackApiError

    client = _get_slack_client()
    logger.info("Fetching channels where the bot is a member...")
    try:
        cursor = None
        count = 0
        while True:
            response = client.users_conversations(
                cursor=cursor, types="public_channel,private_channel", limit=100
            )
            for channel in response["channels"]:
                print("- %s (ID: %s)" % (channel["name"], channel["id"]))
                count += 1
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        print("Total channels found: %d" % count)
    except SlackApiError as e:
        logger.error("Error listing channels: %s", e)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract Slack messages with thread support and Brain formatting"
    )
    parser.add_argument("--channel", help="Channel name (e.g. general)")
    parser.add_argument("--channel_id", help="Direct Channel ID (e.g. C12345)")
    parser.add_argument("--user", help="Filter by user name")
    parser.add_argument(
        "--days", type=int, default=30, help="Days to look back (default: 30)"
    )
    parser.add_argument(
        "--list-channels", action="store_true", help="List all channels the bot is in"
    )
    parser.add_argument(
        "--threads", action="store_true", default=True,
        help="Include thread replies (default: True)",
    )
    parser.add_argument("--no-threads", action="store_true", help="Exclude thread replies")
    parser.add_argument(
        "--brain-format", action="store_true",
        help="Output in Brain-compatible markdown format",
    )
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.list_channels:
        list_bot_channels()
        return

    if not args.channel and not args.channel_id:
        parser.error("One of --channel or --channel_id is required")

    extract_messages(
        channel_name=args.channel,
        channel_id=args.channel_id,
        user_name=args.user,
        days=args.days,
        include_threads=not args.no_threads,
        format_for_brain=args.brain_format,
        output_file=args.output,
    )


if __name__ == "__main__":
    main()
