import argparse
import os
import sys
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Load environment variables
load_dotenv(override=True)

# Import local modules for parsing/caching
try:
    from slack_mrkdwn_parser import MrkdwnParser, format_message_for_brain
    from slack_user_cache import load_channel_cache, load_user_cache

    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False


def get_client():
    """Get authenticated Slack client."""
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        raise ValueError("SLACK_BOT_TOKEN not found in .env")
    return WebClient(token=token)


def get_parser():
    """Get mrkdwn parser with caches if available."""
    if CACHE_AVAILABLE:
        try:
            user_cache = load_user_cache()
            channel_cache = load_channel_cache()
            return MrkdwnParser(user_cache, channel_cache)
        except FileNotFoundError:
            print(
                "Warning: Cache files not found. Run slack_user_cache.py first.",
                file=sys.stderr,
            )
            return MrkdwnParser()
    return None


def fetch_thread_replies(client, channel_id: str, thread_ts: str) -> list:
    """
    Fetch all replies in a thread.

    Args:
        client: Slack WebClient
        channel_id: Channel containing the thread
        thread_ts: Thread parent timestamp

    Returns:
        List of reply messages (excluding parent)
    """
    replies = []
    cursor = None

    while True:
        try:
            response = client.conversations_replies(
                channel=channel_id, ts=thread_ts, cursor=cursor, limit=200
            )

            messages = response.get("messages", [])
            # First message is parent, rest are replies
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
                print(f"Rate limited, waiting {retry_after}s...", file=sys.stderr)
                time.sleep(retry_after)
                continue
            elif e.response["error"] == "thread_not_found":
                break
            else:
                print(f"Error fetching thread: {e}", file=sys.stderr)
                break

    return replies


def find_channel_id(client, channel_name):
    try:
        # Remove # if present
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
                    print(f"Rate limited. Sleeping for {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue
                else:
                    raise e

            for channel in response["channels"]:
                if channel["name"] == channel_name:
                    return channel["id"]

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        return None
    except SlackApiError as e:
        print(f"Error finding channel: {e}")
        return None


def find_user_id(client, user_name):
    try:
        cursor = None
        while True:
            response = client.users_list(cursor=cursor)
            for user in response["members"]:
                # Check real name, display name, and name
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
        print(f"Error finding user: {e}")
        return None


def extract_messages(
    channel_name=None,
    channel_id=None,
    user_name=None,
    days=7,
    include_threads=True,
    format_for_brain=False,
    output_file=None,
):
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
    client = get_client()
    parser = get_parser()

    if not channel_id:
        if not channel_name:
            print(
                "Error: Must provide either --channel or --channel_id", file=sys.stderr
            )
            return
        print(f"Looking for channel: {channel_name}", file=sys.stderr)
        channel_id = find_channel_id(client, channel_name)
        if not channel_id:
            print(f"Could not find channel: {channel_name}", file=sys.stderr)
            return
    else:
        print(f"Using provided Channel ID: {channel_id}", file=sys.stderr)

    user_id = None
    if user_name:
        print(f"Looking for user: {user_name}", file=sys.stderr)
        user_id = find_user_id(client, user_name)
        if not user_id:
            print(f"Could not find user: {user_name}", file=sys.stderr)
            return
        print(f"Found User ID: {user_id}", file=sys.stderr)

    resolved_channel_name = channel_name
    if parser and channel_id in parser.channel_cache:
        resolved_channel_name = parser.channel_cache[channel_id].get(
            "name", channel_name
        )

    print(
        f"Extracting messages from #{resolved_channel_name} ({channel_id})...",
        file=sys.stderr,
    )

    output_lines = []
    output_lines.append(f"# Slack: #{resolved_channel_name}")
    output_lines.append(f"Extracted: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    output_lines.append(f"Period: Last {days} days")
    output_lines.append("")

    try:
        # Calculate oldest timestamp
        oldest = (datetime.now() - timedelta(days=days)).timestamp()
        cursor = None
        all_messages = []

        # Paginate through all messages
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
                    print(f"Rate limited, waiting {retry_after}s...", file=sys.stderr)
                    time.sleep(retry_after)
                    continue
                else:
                    raise

        print(
            f"Found {len(all_messages)} messages in the last {days} days.",
            file=sys.stderr,
        )

        # Sort by timestamp (oldest first)
        all_messages.sort(key=lambda m: float(m.get("ts", 0)))

        count = 0
        thread_count = 0

        for msg in all_messages:
            # Filter by user if specified
            if user_id and msg.get("user") != user_id:
                continue

            msg_ts = msg.get("ts", "")
            msg_user = msg.get("user", "Unknown")
            msg_text = msg.get("text", "")
            reactions = msg.get("reactions", [])

            # Format the message
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

                output_lines.append(f"\n### {sender} ({ts_str})")
                output_lines.append(parsed_text)

                if reactions:
                    reaction_str = " ".join(
                        [f":{r['name']}:({r.get('count', 1)})" for r in reactions]
                    )
                    output_lines.append(f"*Reactions: {reaction_str}*")

            count += 1

            # Fetch thread replies if message has replies
            if include_threads and msg.get("reply_count", 0) > 0:
                thread_ts = msg_ts
                replies = fetch_thread_replies(client, channel_id, thread_ts)

                for reply in replies:
                    # Skip if filtering by user and doesn't match
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
                            thread_ts=thread_ts,
                            reactions=reply_reactions,
                        )
                        output_lines.append(formatted)
                    else:
                        ts_str = datetime.fromtimestamp(float(reply_ts)).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        sender = (
                            parser.resolve_user(reply_user) if parser else reply_user
                        )
                        parsed_text = parser.parse(reply_text) if parser else reply_text

                        output_lines.append(f"\n> **{sender}** ({ts_str}) [reply]")
                        output_lines.append(f"> {parsed_text}")

                    thread_count += 1

        output_lines.append("")
        output_lines.append("---")
        output_lines.append(f"*Total: {count} messages, {thread_count} thread replies*")

        # Output
        output_text = "\n".join(output_lines)

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(output_text)
            print(f"Written to: {output_file}", file=sys.stderr)
        else:
            print(output_text)

        print(
            f"\nTotal: {count} messages, {thread_count} thread replies", file=sys.stderr
        )

    except SlackApiError as e:
        print(f"Error extracting messages: {e}", file=sys.stderr)


def list_bot_channels():
    client = get_client()
    print("Fetching channels where the bot is a member...")
    try:
        cursor = None
        count = 0
        while True:
            response = client.users_conversations(
                cursor=cursor, types="public_channel,private_channel", limit=100
            )

            for channel in response["channels"]:
                print(f"- {channel['name']} (ID: {channel['id']})")
                count += 1

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        print(f"Total channels found: {count}")
    except SlackApiError as e:
        print(f"Error listing channels: {e}")


if __name__ == "__main__":
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
        "--threads",
        action="store_true",
        default=True,
        help="Include thread replies (default: True)",
    )
    parser.add_argument(
        "--no-threads", action="store_true", help="Exclude thread replies"
    )
    parser.add_argument(
        "--brain-format",
        action="store_true",
        help="Output in Brain-compatible markdown format",
    )
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")

    args = parser.parse_args()

    if args.list_channels:
        list_bot_channels()
        exit(0)

    if not args.channel and not args.channel_id:
        parser.error("One of --channel or --channel_id is required")

    include_threads = not args.no_threads

    extract_messages(
        channel_name=args.channel,
        channel_id=args.channel_id,
        user_name=args.user,
        days=args.days,
        include_threads=include_threads,
        format_for_brain=args.brain_format,
        output_file=args.output,
    )
