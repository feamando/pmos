#!/usr/bin/env python3
"""
Slack Connection Test

Tests Slack API connection by fetching the last message sent by a specific user.

Usage:
    python slack_test.py                    # Uses SLACK_USER_ID from .env
    python slack_test.py --user U12345678   # Override user ID
"""

import argparse
import os
import sys

# Add common directory to path for config_loader
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config_loader

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ImportError:
    print("Error: slack_sdk not installed. Run: pip install slack_sdk")
    sys.exit(1)


def get_slack_config():
    """Get Slack configuration from environment."""
    return {
        "bot_token": os.getenv("SLACK_BOT_TOKEN"),
        "user_id": os.getenv("SLACK_USER_ID"),
    }


def test_connection(client: WebClient) -> bool:
    """Test basic API connection."""
    try:
        response = client.auth_test()
        print(f"Connected as: {response['user']} ({response['team']})")
        return True
    except SlackApiError as e:
        print(f"Connection failed: {e.response['error']}")
        return False


def get_user_info(client: WebClient, user_id: str) -> dict:
    """Get user info by ID."""
    try:
        response = client.users_info(user=user_id)
        return response["user"]
    except SlackApiError as e:
        print(f"Failed to get user info: {e.response['error']}")
        return None


def find_last_message_by_user(
    client: WebClient, user_id: str, limit: int = 100
) -> dict:
    """
    Find the last message sent by a specific user.
    Searches through recent conversations the bot has access to.
    """
    try:
        # Get list of conversations the bot can access
        conversations = client.conversations_list(
            types="public_channel,private_channel,im,mpim", limit=50
        )

        last_message = None
        last_ts = 0

        for channel in conversations["channels"]:
            try:
                # Get recent messages from this channel
                history = client.conversations_history(
                    channel=channel["id"], limit=limit
                )

                for msg in history["messages"]:
                    # Check if message is from our target user
                    if msg.get("user") == user_id:
                        msg_ts = float(msg.get("ts", 0))
                        if msg_ts > last_ts:
                            last_ts = msg_ts
                            last_message = {
                                "text": msg.get("text", ""),
                                "channel": channel.get("name", channel["id"]),
                                "channel_id": channel["id"],
                                "timestamp": msg.get("ts"),
                                "type": msg.get("type"),
                            }
            except SlackApiError as e:
                # Skip channels we don't have access to
                if e.response["error"] not in ["channel_not_found", "not_in_channel"]:
                    print(
                        f"  Warning: Could not read {channel.get('name', channel['id'])}: {e.response['error']}"
                    )
                continue

        return last_message

    except SlackApiError as e:
        print(f"Failed to search messages: {e.response['error']}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Test Slack API connection")
    parser.add_argument("--user", type=str, help="Slack User ID to search for")
    args = parser.parse_args()

    # Load config
    config = get_slack_config()

    if not config["bot_token"]:
        print("Error: SLACK_BOT_TOKEN not set in .env")
        print("\nTo set up:")
        print("1. Go to https://api.slack.com/apps")
        print("2. Create New App → From scratch")
        print("3. OAuth & Permissions → Add scopes:")
        print("   - channels:history, groups:history, im:history, users:read")
        print("4. Install to Workspace → Copy Bot Token")
        print("5. Add to .env: SLACK_BOT_" + "TOKEN=xoxb-...")
        sys.exit(1)

    user_id = args.user or config["user_id"]
    if not user_id:
        print("Error: No user ID specified.")
        print("Either set SLACK_USER_ID in .env or use --user flag")
        print("\nTo find your Slack User ID:")
        print("1. Open Slack → Click your profile")
        print("2. Click '...' More → Copy member ID")
        sys.exit(1)

    # Initialize client
    client = WebClient(token=config["bot_token"])

    print("=" * 50)
    print("SLACK CONNECTION TEST")
    print("=" * 50)

    # Test 1: Basic connection
    print("\n[1] Testing connection...")
    if not test_connection(client):
        sys.exit(1)
    print("   OK")

    # Test 2: Get user info
    print(f"\n[2] Looking up user: {user_id}...")
    user_info = get_user_info(client, user_id)
    if user_info:
        print(
            f"   Found: {user_info.get('real_name', 'Unknown')} (@{user_info.get('name', 'unknown')})"
        )
    else:
        print("   Warning: Could not fetch user info (may still work)")

    # Test 3: Find last message
    print(f"\n[3] Searching for last message by user...")
    last_msg = find_last_message_by_user(client, user_id)

    if last_msg:
        print(f"\n   FOUND in #{last_msg['channel']}:")
        print(f"   Timestamp: {last_msg['timestamp']}")
        print(
            f"   Message: {last_msg['text'][:200]}{'...' if len(last_msg['text']) > 200 else ''}"
        )
    else:
        print("   No messages found (bot may not have access to user's channels)")

    print("\n" + "=" * 50)
    print("TEST COMPLETE")
    print("=" * 50)


if __name__ == "__main__":
    main()
