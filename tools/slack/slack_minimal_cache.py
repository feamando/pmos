#!/usr/bin/env python3
"""
Slack Minimal Cache Builder

Builds a cache for only the user/channel IDs found in extracted data.
Much faster than fetching the entire workspace (56 users vs 53,531).

Usage:
    python3 slack_minimal_cache.py [--audit-file PATH]
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

BRAIN_SLACK_DIR = config_loader.get_root_path() / "user" / "brain" / "Inbox" / "Slack"
OUTPUT_DIR = BRAIN_SLACK_DIR / "Cache"
AUDIT_FILE = BRAIN_SLACK_DIR / "cache_audit.json"


def get_client():
    """Get authenticated Slack client."""
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        raise ValueError("SLACK_BOT_TOKEN not found in .env")
    return WebClient(token=token)


def load_audit() -> dict:
    """Load the cache audit file."""
    if not AUDIT_FILE.exists():
        raise FileNotFoundError(f"Audit file not found: {AUDIT_FILE}")
    with open(AUDIT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_user_info(client, user_id: str) -> dict:
    """Fetch info for a single user."""
    try:
        response = client.users_info(user=user_id)
        user = response.get("user", {})
        profile = user.get("profile", {})

        return {
            "id": user_id,
            "name": user.get("real_name") or user.get("name", "Unknown"),
            "username": user.get("name", ""),
            "display_name": profile.get("display_name", ""),
            "email": profile.get("email", ""),
            "is_bot": user.get("is_bot", False),
            "deleted": user.get("deleted", False),
            "title": profile.get("title", ""),
        }
    except SlackApiError as e:
        if e.response["error"] == "user_not_found":
            return {
                "id": user_id,
                "name": f"Unknown ({user_id})",
                "error": "user_not_found",
            }
        elif e.response["error"] == "ratelimited":
            import time

            retry_after = int(e.response.headers.get("Retry-After", 5))
            print(f"  Rate limited, waiting {retry_after}s...", file=sys.stderr)
            time.sleep(retry_after)
            return fetch_user_info(client, user_id)  # Retry
        else:
            return {
                "id": user_id,
                "name": f"Error ({user_id})",
                "error": str(e.response["error"]),
            }


def fetch_channel_info(client, channel_id: str) -> dict:
    """Fetch info for a single channel."""
    try:
        response = client.conversations_info(channel=channel_id)
        channel = response.get("channel", {})

        return {
            "id": channel_id,
            "name": channel.get("name", ""),
            "is_private": channel.get("is_private", False),
            "is_archived": channel.get("is_archived", False),
            "topic": channel.get("topic", {}).get("value", ""),
            "purpose": channel.get("purpose", {}).get("value", ""),
            "num_members": channel.get("num_members", 0),
        }
    except SlackApiError as e:
        if e.response["error"] in [
            "channel_not_found",
            "method_not_supported_for_channel_type",
        ]:
            return {
                "id": channel_id,
                "name": f"Unknown ({channel_id})",
                "error": e.response["error"],
            }
        elif e.response["error"] == "ratelimited":
            import time

            retry_after = int(e.response.headers.get("Retry-After", 5))
            print(f"  Rate limited, waiting {retry_after}s...", file=sys.stderr)
            time.sleep(retry_after)
            return fetch_channel_info(client, channel_id)  # Retry
        else:
            return {
                "id": channel_id,
                "name": f"Error ({channel_id})",
                "error": str(e.response["error"]),
            }


def build_minimal_cache(audit: dict) -> tuple:
    """
    Build cache for only the users and channels in the audit.

    Returns:
        tuple: (user_cache, channel_cache)
    """
    client = get_client()

    user_ids = audit.get("unique_users", [])
    channel_ids = audit.get("unique_channels", [])

    print(f"Fetching {len(user_ids)} users...", file=sys.stderr)
    user_cache = {}
    for i, user_id in enumerate(user_ids, 1):
        user_info = fetch_user_info(client, user_id)
        user_cache[user_id] = user_info
        print(
            f"  [{i}/{len(user_ids)}] {user_id} → {user_info.get('name', 'Unknown')}",
            file=sys.stderr,
        )

        # Save incrementally every 20 users
        if i % 20 == 0:
            save_cache(user_cache, {}, partial=True)

    print(f"\nFetching {len(channel_ids)} channels...", file=sys.stderr)
    channel_cache = {}
    for i, channel_id in enumerate(channel_ids, 1):
        channel_info = fetch_channel_info(client, channel_id)
        channel_cache[channel_id] = channel_info
        print(
            f"  [{i}/{len(channel_ids)}] {channel_id} → #{channel_info.get('name', 'Unknown')}",
            file=sys.stderr,
        )

    return user_cache, channel_cache


def save_cache(user_cache: dict, channel_cache: dict, partial: bool = False):
    """Save cache files."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # User cache
    user_file = OUTPUT_DIR / "user_cache.json"
    with open(user_file, "w", encoding="utf-8") as f:
        json.dump(user_cache, f, indent=2, ensure_ascii=False)

    if not partial:
        # Channel cache
        channel_file = OUTPUT_DIR / "channel_cache.json"
        with open(channel_file, "w", encoding="utf-8") as f:
            json.dump(channel_cache, f, indent=2, ensure_ascii=False)

        # Build reverse lookups
        username_to_id = {}
        for user_id, data in user_cache.items():
            if data.get("username"):
                username_to_id[data["username"].lower()] = user_id
            if data.get("display_name"):
                username_to_id[data["display_name"].lower()] = user_id
            if data.get("name"):
                first_name = data["name"].split()[0].lower() if data["name"] else ""
                if first_name and first_name not in username_to_id:
                    username_to_id[first_name] = user_id

        channel_name_to_id = {}
        for channel_id, data in channel_cache.items():
            if data.get("name"):
                channel_name_to_id[data["name"].lower()] = channel_id

        # Save lookups
        with open(OUTPUT_DIR / "username_to_id.json", "w", encoding="utf-8") as f:
            json.dump(username_to_id, f, indent=2, ensure_ascii=False)

        with open(OUTPUT_DIR / "channel_name_to_id.json", "w", encoding="utf-8") as f:
            json.dump(channel_name_to_id, f, indent=2, ensure_ascii=False)

        # Metadata
        metadata = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "user_count": len(user_cache),
            "channel_count": len(channel_cache),
            "type": "minimal_cache",
            "source": "cache_audit.json",
        }
        with open(OUTPUT_DIR / "cache_metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print(f"\nSaved to: {OUTPUT_DIR}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Build minimal Slack cache for extracted data"
    )
    parser.add_argument(
        "--audit-file",
        default=str(AUDIT_FILE),
        help=f"Path to audit file (default: {AUDIT_FILE})",
    )
    args = parser.parse_args()

    print("=" * 60, file=sys.stderr)
    print("MINIMAL SLACK CACHE BUILDER", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Load audit
    audit = load_audit()
    print(
        f"Audit: {audit['total_users']} users, {audit['total_channels']} channels needed",
        file=sys.stderr,
    )

    # Build cache
    user_cache, channel_cache = build_minimal_cache(audit)

    # Save
    save_cache(user_cache, channel_cache)

    # Summary
    errors = sum(1 for u in user_cache.values() if u.get("error"))
    print("=" * 60, file=sys.stderr)
    print("CACHE BUILD COMPLETE", file=sys.stderr)
    print(f"  Users: {len(user_cache)} ({errors} errors)", file=sys.stderr)
    print(f"  Channels: {len(channel_cache)}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


if __name__ == "__main__":
    main()
