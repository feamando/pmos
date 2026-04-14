#!/usr/bin/env python3
"""
Slack User & Channel Cache Builder (v5.0)

Builds lookup caches for user IDs -> names and channel IDs -> names.
Run once before bulk extraction to enable efficient resolution.

Ported from v4.x slack_user_cache.py — auth via connector_bridge,
paths via path_resolver.

Usage:
    python slack_user_cache.py [--output-dir PATH]
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# v5 shared utils
try:
    from pm_os_base.tools.core.connector_bridge import get_auth
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        _base = __import__("pathlib").Path(__file__).resolve().parent.parent.parent.parent
        sys.path.insert(0, str(_base / "pm-os-base" / "tools" / "core"))
        from connector_bridge import get_auth
        from path_resolver import get_paths
    except ImportError:
        logger.error("Cannot import pm_os_base core modules")
        raise


def _default_output_dir() -> str:
    """Get default output directory via path_resolver."""
    try:
        return str(get_paths().brain / "Inbox" / "Slack")
    except Exception:
        return ""


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
        raise ValueError(auth.help_message)


def fetch_all_users(
    client, output_dir: Optional[str] = None, save_every: int = 50,
) -> dict:
    """
    Fetch all users from Slack workspace with incremental saves.

    Args:
        client: Slack WebClient
        output_dir: Directory to save incremental progress
        save_every: Save progress every N pages

    Returns:
        dict: {user_id: {name, username, email, is_bot, deleted}}
    """
    from slack_sdk.errors import SlackApiError

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
                logger.info(
                    "Resuming from page %d with %d users cached", page, len(users)
                )

    logger.info("Fetching users...")

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

            logger.info(
                "  Page %d: %d users", page, len(response.get("members", []))
            )

            cursor = response.get("response_metadata", {}).get("next_cursor")

            if output_dir and page % save_every == 0:
                _save_progress(output_dir, "user", users, cursor, page)

            if not cursor:
                break

        except SlackApiError as e:
            if e.response["error"] == "ratelimited":
                retry_after = int(e.response.headers.get("Retry-After", 30))
                logger.warning("Rate limited, waiting %ss...", retry_after)
                if output_dir:
                    _save_progress(output_dir, "user", users, cursor, page)
                time.sleep(retry_after)
                continue
            else:
                if output_dir:
                    _save_progress(output_dir, "user", users, cursor, page)
                raise

    # Cleanup progress file on completion
    if output_dir:
        progress_file = Path(output_dir) / "user_cache_progress.json"
        if progress_file.exists():
            progress_file.unlink()

    logger.info("Total users fetched: %d", len(users))
    return users


def _save_progress(
    output_dir: str, cache_type: str, data: dict, cursor: str, page: int,
) -> None:
    """Save incremental progress to disk."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    progress_file = output_path / ("%s_cache_progress.json" % cache_type)
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
    logger.info("  [Saved progress: %d %ss at page %d]", len(data), cache_type, page)


def fetch_all_channels(
    client, include_private: bool = True,
    output_dir: Optional[str] = None, save_every: int = 100,
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
    from slack_sdk.errors import SlackApiError

    channels = {}
    cursor = None
    page = 0

    if output_dir:
        progress_file = Path(output_dir) / "channel_cache_progress.json"
        if progress_file.exists():
            with open(progress_file, "r", encoding="utf-8") as f:
                progress = json.load(f)
                channels = progress.get("channels", {})
                cursor = progress.get("cursor")
                page = progress.get("page", 0)
                logger.info(
                    "Resuming from page %d with %d channels cached", page, len(channels)
                )

    types = "public_channel,private_channel" if include_private else "public_channel"
    logger.info("Fetching channels (%s)...", types)

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

            logger.info(
                "  Page %d: %d channels", page, len(response.get("channels", []))
            )

            cursor = response.get("response_metadata", {}).get("next_cursor")

            if output_dir and page % save_every == 0:
                _save_progress(output_dir, "channel", channels, cursor, page)

            if not cursor:
                break

        except SlackApiError as e:
            if e.response["error"] == "ratelimited":
                retry_after = int(e.response.headers.get("Retry-After", 30))
                logger.warning("Rate limited, waiting %ss...", retry_after)
                if output_dir:
                    _save_progress(output_dir, "channel", channels, cursor, page)
                time.sleep(retry_after)
                continue
            else:
                if output_dir:
                    _save_progress(output_dir, "channel", channels, cursor, page)
                raise

    if output_dir:
        progress_file = Path(output_dir) / "channel_cache_progress.json"
        if progress_file.exists():
            progress_file.unlink()

    logger.info("Total channels fetched: %d", len(channels))
    return channels


def fetch_bot_channels(client) -> dict:
    """
    Fetch only channels where the bot is a member.

    Returns:
        dict: {channel_id: {name, is_private, ...}}
    """
    from slack_sdk.errors import SlackApiError

    channels = {}
    cursor = None
    page = 0

    logger.info("Fetching bot's channels...")

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

            logger.info(
                "  Page %d: %d channels", page, len(response.get("channels", []))
            )

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        except SlackApiError as e:
            if e.response["error"] == "ratelimited":
                retry_after = int(e.response.headers.get("Retry-After", 5))
                logger.warning("Rate limited, waiting %ss...", retry_after)
                time.sleep(retry_after)
                continue
            else:
                raise

    logger.info("Bot is member of %d channels", len(channels))
    return channels


def build_reverse_lookups(users: dict, channels: dict) -> tuple:
    """
    Build reverse lookup maps (name -> ID).

    Returns:
        Tuple of (username_to_id, channel_name_to_id)
    """
    username_to_id = {}
    for user_id, data in users.items():
        if data["username"]:
            username_to_id[data["username"].lower()] = user_id
        if data["display_name"]:
            username_to_id[data["display_name"].lower()] = user_id
        if data["name"]:
            first_name = data["name"].split()[0].lower()
            if first_name not in username_to_id:
                username_to_id[first_name] = user_id

    channel_name_to_id = {}
    for channel_id, data in channels.items():
        if data["name"]:
            channel_name_to_id[data["name"].lower()] = channel_id

    return username_to_id, channel_name_to_id


def save_cache(
    output_dir: str, users: dict, channels: dict, bot_channels: dict,
) -> dict:
    """Save all caches to JSON files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    username_to_id, channel_name_to_id = build_reverse_lookups(users, channels)

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
        logger.info("Saved: %s", filepath)

    return metadata


def load_user_cache(output_dir: str = None) -> dict:
    """Load user cache from file."""
    if output_dir is None:
        output_dir = _default_output_dir()
    filepath = Path(output_dir) / "user_cache.json"
    if not filepath.exists():
        raise FileNotFoundError(
            "User cache not found at %s. Run slack_user_cache.py first." % filepath
        )
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_channel_cache(output_dir: str = None) -> dict:
    """Load channel cache from file."""
    if output_dir is None:
        output_dir = _default_output_dir()
    filepath = Path(output_dir) / "channel_cache.json"
    if not filepath.exists():
        raise FileNotFoundError(
            "Channel cache not found at %s. Run slack_user_cache.py first." % filepath
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


def main() -> None:
    """CLI entry point."""
    default_dir = _default_output_dir()

    parser = argparse.ArgumentParser(description="Build Slack user and channel caches")
    parser.add_argument(
        "--output-dir", default=default_dir,
        help="Output directory for cache files (default: %s)" % default_dir,
    )
    parser.add_argument(
        "--skip-all-channels", action="store_true",
        help="Skip fetching all workspace channels (only fetch bot's channels)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    logger.info("=" * 60)
    logger.info("SLACK CACHE BUILDER")
    logger.info("=" * 60)

    client = _get_slack_client()
    output_dir = args.output_dir

    users = fetch_all_users(client, output_dir=output_dir)

    if args.skip_all_channels:
        channels = {}
    else:
        channels = fetch_all_channels(client, output_dir=output_dir)

    bot_channels = fetch_bot_channels(client)

    if args.skip_all_channels:
        channels = bot_channels

    metadata = save_cache(output_dir, users, channels, bot_channels)

    logger.info("=" * 60)
    logger.info("CACHE BUILD COMPLETE")
    logger.info("  Users: %d", metadata["user_count"])
    logger.info("  Channels: %d", metadata["channel_count"])
    logger.info("  Bot Channels: %d", metadata["bot_channel_count"])
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
