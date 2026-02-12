#!/usr/bin/env python3
"""
Slack User & Channel Cache Builder

Builds lookup caches for user IDs → names and channel IDs → names.
Run once before bulk extraction to enable efficient resolution.

Usage:
    python3 slack_user_cache.py [--output-dir PATH]
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Add parent directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

load_dotenv(override=True)

DEFAULT_OUTPUT_DIR = str(
    config_loader.get_root_path() / "user" / "brain" / "Inbox" / "Slack"
)


def get_client():
    """Get authenticated Slack client."""
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        raise ValueError("SLACK_BOT_TOKEN not found in .env")
    return WebClient(token=token)


def fetch_all_users(client, output_dir: str = None, save_every: int = 50) -> dict:
    """
    Fetch all users from Slack workspace with incremental saves.

    Args:
        client: Slack WebClient
        output_dir: Directory to save incremental progress
        save_every: Save progress every N pages

    Returns:
        dict: {user_id: {name, username, email, is_bot, deleted}}
    """
    import time

    users = {}
    cursor = None
    page = 0

    # Load existing progress if available
    if output_dir:
        progress_file = Path(output_dir) / "user_cache_progress.json"
        if progress_file.exists():
            with open(progress_file, "r", encoding="utf-8") as f:
                progress = json.load(f)
                users = progress.get("users", {})
                cursor = progress.get("cursor")
                page = progress.get("page", 0)
                print(
                    f"Resuming from page {page} with {len(users)} users cached",
                    file=sys.stderr,
                )

    print("Fetching users...", file=sys.stderr)

    while True:
        try:
            response = client.users_list(cursor=cursor, limit=200)
            page += 1

            for user in response.get("members", []):
                user_id = user["id"]
                profile = user.get("profile", {})

                users[user_id] = {
                    "name": user.get("real_name") or user.get("name", "Unknown"),
                    "username": user.get("name", ""),
                    "email": profile.get("email", ""),
                    "display_name": profile.get("display_name", ""),
                    "is_bot": user.get("is_bot", False),
                    "deleted": user.get("deleted", False),
                    "title": profile.get("title", ""),
                }

            print(
                f"  Page {page}: {len(response.get('members', []))} users",
                file=sys.stderr,
            )

            cursor = response.get("response_metadata", {}).get("next_cursor")

            # Incremental save
            if output_dir and page % save_every == 0:
                _save_progress(output_dir, "user", users, cursor, page)

            if not cursor:
                break

        except SlackApiError as e:
            if e.response["error"] == "ratelimited":
                retry_after = int(e.response.headers.get("Retry-After", 30))
                print(f"  Rate limited, waiting {retry_after}s...", file=sys.stderr)
                # Save progress before waiting
                if output_dir:
                    _save_progress(output_dir, "user", users, cursor, page)
                time.sleep(retry_after)
                continue
            else:
                # Save progress on error
                if output_dir:
                    _save_progress(output_dir, "user", users, cursor, page)
                raise
        except Exception as e:
            # Save progress on any error
            if output_dir:
                _save_progress(output_dir, "user", users, cursor, page)
            raise

    # Final save and cleanup
    if output_dir:
        progress_file = Path(output_dir) / "user_cache_progress.json"
        if progress_file.exists():
            progress_file.unlink()  # Remove progress file on completion

    print(f"Total users fetched: {len(users)}", file=sys.stderr)
    return users


def _save_progress(
    output_dir: str, cache_type: str, data: dict, cursor: str, page: int
):
    """Save incremental progress to disk."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    progress_file = output_path / f"{cache_type}_cache_progress.json"
    with open(progress_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "type": cache_type,
                "cursor": cursor,
                "page": page,
                "count": len(data),
                "saved_at": datetime.utcnow().isoformat() + "Z",
                "users" if cache_type == "user" else "channels": data,
            },
            f,
            ensure_ascii=False,
        )
    print(
        f"  [Saved progress: {len(data)} {cache_type}s at page {page}]", file=sys.stderr
    )


def fetch_all_channels(
    client, include_private=True, output_dir: str = None, save_every: int = 100
) -> dict:
    """
    Fetch all channels the bot has access to with incremental saves.

    Args:
        client: Slack WebClient
        include_private: Include private channels
        output_dir: Directory to save incremental progress
        save_every: Save progress every N pages

    Returns:
        dict: {channel_id: {name, is_private, is_archived, topic, purpose, member_count}}
    """
    import time

    channels = {}
    cursor = None
    page = 0

    # Load existing progress if available
    if output_dir:
        progress_file = Path(output_dir) / "channel_cache_progress.json"
        if progress_file.exists():
            with open(progress_file, "r", encoding="utf-8") as f:
                progress = json.load(f)
                channels = progress.get("channels", {})
                cursor = progress.get("cursor")
                page = progress.get("page", 0)
                print(
                    f"Resuming from page {page} with {len(channels)} channels cached",
                    file=sys.stderr,
                )

    types = "public_channel,private_channel" if include_private else "public_channel"
    print(f"Fetching channels ({types})...", file=sys.stderr)

    while True:
        try:
            response = client.conversations_list(cursor=cursor, limit=200, types=types)
            page += 1

            for channel in response.get("channels", []):
                channel_id = channel["id"]

                channels[channel_id] = {
                    "name": channel.get("name", ""),
                    "is_private": channel.get("is_private", False),
                    "is_archived": channel.get("is_archived", False),
                    "topic": channel.get("topic", {}).get("value", ""),
                    "purpose": channel.get("purpose", {}).get("value", ""),
                    "num_members": channel.get("num_members", 0),
                    "created": channel.get("created", 0),
                }

            print(
                f"  Page {page}: {len(response.get('channels', []))} channels",
                file=sys.stderr,
            )

            cursor = response.get("response_metadata", {}).get("next_cursor")

            # Incremental save
            if output_dir and page % save_every == 0:
                _save_progress(output_dir, "channel", channels, cursor, page)

            if not cursor:
                break

        except SlackApiError as e:
            if e.response["error"] == "ratelimited":
                retry_after = int(e.response.headers.get("Retry-After", 30))
                print(f"  Rate limited, waiting {retry_after}s...", file=sys.stderr)
                # Save progress before waiting
                if output_dir:
                    _save_progress(output_dir, "channel", channels, cursor, page)
                time.sleep(retry_after)
                continue
            else:
                # Save progress on error
                if output_dir:
                    _save_progress(output_dir, "channel", channels, cursor, page)
                raise
        except Exception as e:
            # Save progress on any error
            if output_dir:
                _save_progress(output_dir, "channel", channels, cursor, page)
            raise

    # Cleanup progress file on completion
    if output_dir:
        progress_file = Path(output_dir) / "channel_cache_progress.json"
        if progress_file.exists():
            progress_file.unlink()

    print(f"Total channels fetched: {len(channels)}", file=sys.stderr)
    return channels


def fetch_bot_channels(client) -> dict:
    """
    Fetch only channels where the bot is a member.

    Returns:
        dict: {channel_id: {name, is_private, ...}}
    """
    channels = {}
    cursor = None
    page = 0

    print("Fetching bot's channels...", file=sys.stderr)

    while True:
        try:
            response = client.users_conversations(
                cursor=cursor, limit=200, types="public_channel,private_channel"
            )
            page += 1

            for channel in response.get("channels", []):
                channel_id = channel["id"]

                channels[channel_id] = {
                    "name": channel.get("name", ""),
                    "is_private": channel.get("is_private", False),
                    "is_archived": channel.get("is_archived", False),
                    "num_members": channel.get("num_members", 0),
                }

            print(
                f"  Page {page}: {len(response.get('channels', []))} channels",
                file=sys.stderr,
            )

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        except SlackApiError as e:
            if e.response["error"] == "ratelimited":
                retry_after = int(e.response.headers.get("Retry-After", 5))
                print(f"  Rate limited, waiting {retry_after}s...", file=sys.stderr)
                import time

                time.sleep(retry_after)
                continue
            else:
                raise

    print(f"Bot is member of {len(channels)} channels", file=sys.stderr)
    return channels


def build_reverse_lookups(users: dict, channels: dict) -> tuple:
    """
    Build reverse lookup maps (name → ID).

    Returns:
        tuple: (username_to_id, channel_name_to_id)
    """
    username_to_id = {}
    for user_id, data in users.items():
        # Index by username
        if data["username"]:
            username_to_id[data["username"].lower()] = user_id
        # Index by display name
        if data["display_name"]:
            username_to_id[data["display_name"].lower()] = user_id
        # Index by real name (first name)
        if data["name"]:
            first_name = data["name"].split()[0].lower()
            if first_name not in username_to_id:  # Don't overwrite
                username_to_id[first_name] = user_id

    channel_name_to_id = {}
    for channel_id, data in channels.items():
        if data["name"]:
            channel_name_to_id[data["name"].lower()] = channel_id

    return username_to_id, channel_name_to_id


def save_cache(output_dir: str, users: dict, channels: dict, bot_channels: dict):
    """Save all caches to JSON files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    username_to_id, channel_name_to_id = build_reverse_lookups(users, channels)

    # Build metadata
    metadata = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "user_count": len(users),
        "channel_count": len(channels),
        "bot_channel_count": len(bot_channels),
    }

    files = {
        "user_cache.json": users,
        "channel_cache.json": channels,
        "bot_channels.json": bot_channels,
        "username_to_id.json": username_to_id,
        "channel_name_to_id.json": channel_name_to_id,
        "cache_metadata.json": metadata,
    }

    for filename, data in files.items():
        filepath = output_path / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Saved: {filepath}", file=sys.stderr)

    return metadata


def load_user_cache(output_dir: str = DEFAULT_OUTPUT_DIR) -> dict:
    """Load user cache from file."""
    filepath = Path(output_dir) / "user_cache.json"
    if not filepath.exists():
        raise FileNotFoundError(
            f"User cache not found at {filepath}. Run slack_user_cache.py first."
        )
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_channel_cache(output_dir: str = DEFAULT_OUTPUT_DIR) -> dict:
    """Load channel cache from file."""
    filepath = Path(output_dir) / "channel_cache.json"
    if not filepath.exists():
        raise FileNotFoundError(
            f"Channel cache not found at {filepath}. Run slack_user_cache.py first."
        )
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_user(user_id: str, cache: dict) -> str:
    """Resolve user ID to display name."""
    if user_id in cache:
        data = cache[user_id]
        return (
            data.get("display_name")
            or data.get("name")
            or data.get("username")
            or user_id
        )
    return user_id


def resolve_channel(channel_id: str, cache: dict) -> str:
    """Resolve channel ID to name."""
    if channel_id in cache:
        return cache[channel_id].get("name", channel_id)
    return channel_id


def main():
    parser = argparse.ArgumentParser(description="Build Slack user and channel caches")
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for cache files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--skip-all-channels",
        action="store_true",
        help="Skip fetching all workspace channels (only fetch bot's channels)",
    )
    args = parser.parse_args()

    print("=" * 60, file=sys.stderr)
    print("SLACK CACHE BUILDER", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    client = get_client()
    output_dir = args.output_dir

    # Fetch users (with incremental saves)
    users = fetch_all_users(client, output_dir=output_dir)

    # Fetch channels (with incremental saves)
    if args.skip_all_channels:
        channels = {}
    else:
        channels = fetch_all_channels(client, output_dir=output_dir)

    # Fetch bot's channels
    bot_channels = fetch_bot_channels(client)

    # Merge bot_channels into channels if we skipped all channels
    if args.skip_all_channels:
        channels = bot_channels

    # Save caches
    metadata = save_cache(args.output_dir, users, channels, bot_channels)

    print("=" * 60, file=sys.stderr)
    print("CACHE BUILD COMPLETE", file=sys.stderr)
    print(f"  Users: {metadata['user_count']}", file=sys.stderr)
    print(f"  Channels: {metadata['channel_count']}", file=sys.stderr)
    print(f"  Bot Channels: {metadata['bot_channel_count']}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


if __name__ == "__main__":
    main()
