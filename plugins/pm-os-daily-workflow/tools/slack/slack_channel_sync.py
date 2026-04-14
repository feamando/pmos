#!/usr/bin/env python3
"""
Slack Channel Sync (v5.0)

Syncs the list of channels the bot has access to with the local config file.
Used by context capture commands to ensure we're pulling from all available channels.

Ported from v4.x slack_channel_sync.py — default config path via path_resolver,
auth via connector_bridge.

Usage:
    python slack_channel_sync.py                    # Sync and report changes
    python slack_channel_sync.py --check            # Check only, no write
    python slack_channel_sync.py --config PATH      # Custom config path
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Dict, List, Tuple

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

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    logger.warning("PyYAML not installed. Install with: pip install pyyaml")


def _default_config_path() -> str:
    """Get default channel config path via path_resolver."""
    try:
        return str(get_paths().user / "slack-channels.yaml")
    except Exception:
        return ""


def _get_slack_client():
    """Get authenticated Slack client via connector_bridge."""
    auth = get_auth("slack")
    if auth.source == "env" and auth.token:
        try:
            from slack_sdk import WebClient
            return WebClient(token=auth.token)
        except ImportError:
            return None
    elif auth.source == "connector":
        try:
            from slack_sdk import WebClient
            return WebClient(token=auth.token) if auth.token else None
        except ImportError:
            return None
    else:
        logger.warning("Slack auth not available: %s", auth.help_message)
        return None


def fetch_bot_channels_sdk(client) -> List[Dict]:
    """Fetch all channels the bot is in using slack_sdk."""
    channels = []
    cursor = None
    while True:
        kwargs = {"types": "public_channel,private_channel", "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        try:
            response = client.users_conversations(**kwargs)
            channels.extend(response.get("channels", []))
            cursor = response.get("response_metadata", {}).get("next_cursor", "")
            if not cursor:
                break
            time.sleep(1)
        except Exception as e:
            if "ratelimited" in str(e).lower():
                time.sleep(30)
                continue
            logger.error("Error fetching channels: %s", e)
            break
    return channels


def fetch_bot_channels_requests(token: str) -> List[Dict]:
    """Fetch all channels using requests (fallback)."""
    import requests

    headers = {"Authorization": "Bearer %s" % token}
    channels = []
    cursor = None
    while True:
        params = {"types": "public_channel,private_channel", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        r = requests.get(
            "https://slack.com/api/users.conversations",
            params=params,
            headers=headers,
        )
        d = r.json()
        if not d.get("ok"):
            if d.get("error") == "ratelimited":
                time.sleep(int(r.headers.get("Retry-After", 30)))
                continue
            logger.error("Error: %s", d.get("error"))
            break
        channels.extend(d.get("channels", []))
        cursor = d.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
        time.sleep(1)
    return channels


def load_config(path: str) -> Dict:
    """Load the channel config YAML."""
    if not YAML_AVAILABLE:
        logger.error("PyYAML required for channel sync")
        return {"channels": {}}
    if not os.path.exists(path):
        return {"channels": {}}
    with open(path) as f:
        return yaml.safe_load(f) or {"channels": {}}


def sync_channels(
    config_path: str = None, check_only: bool = False,
) -> Tuple[int, int, int]:
    """
    Sync bot channels with config file.

    Returns:
        Tuple of (total_live, added, removed)
    """
    if config_path is None:
        config_path = _default_config_path()
    if not config_path:
        logger.error("No config path available")
        return (0, 0, 0)

    # Get live channels from Slack
    client = _get_slack_client()
    if client:
        live_channels = fetch_bot_channels_sdk(client)
    else:
        # Try requests fallback with token from connector_bridge
        auth = get_auth("slack")
        if auth.source == "env" and auth.token:
            live_channels = fetch_bot_channels_requests(auth.token)
        else:
            logger.error("No Slack token available")
            return (0, 0, 0)

    if not live_channels:
        logger.warning("No channels fetched from Slack")
        return (0, 0, 0)

    # Build live channel map
    live_map = {}
    for ch in live_channels:
        live_map[ch["name"]] = {
            "id": ch["id"],
            "type": "private" if ch.get("is_private") else "public",
        }

    # Load current config
    config = load_config(config_path)
    config_channels = config.get("channels", {})

    # Find additions and removals
    live_names = set(live_map.keys())
    config_names = set(config_channels.keys())
    added = live_names - config_names
    removed = config_names - live_names

    if check_only:
        return (len(live_channels), len(added), len(removed))

    if not added and not removed:
        return (len(live_channels), 0, 0)

    # Update config
    for name in added:
        config_channels[name] = live_map[name]
    for name in removed:
        del config_channels[name]

    config["channels"] = dict(sorted(config_channels.items()))

    # Write updated config
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    header = (
        "# Slack Channel Registry\n"
        "# Updated: %s\n"
        "# Total: %d channels\n"
        "# Changes: +%d added, -%d removed\n\n"
    ) % (time.strftime("%Y-%m-%d %H:%M"), len(config_channels), len(added), len(removed))

    with open(config_path, "w") as f:
        f.write(header)
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    return (len(live_channels), len(added), len(removed))


def get_all_channel_ids(config_path: str = None) -> List[Dict[str, str]]:
    """
    Get all channel IDs from config. Used by context capture commands.

    Returns:
        List of {"id": ..., "name": ..., "type": ...}
    """
    if config_path is None:
        config_path = _default_config_path()
    config = load_config(config_path)
    result = []
    for name, info in config.get("channels", {}).items():
        if isinstance(info, dict):
            result.append({
                "id": info.get("id", ""),
                "name": name,
                "type": info.get("type", "public"),
            })
    return result


def main() -> None:
    """CLI entry point."""
    default_path = _default_config_path()

    parser = argparse.ArgumentParser(description="Sync Slack channel config")
    parser.add_argument("--check", action="store_true", help="Check only, no write")
    parser.add_argument(
        "--config", default=default_path,
        help="Config file path (default: %s)" % default_path,
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    total, added, removed = sync_channels(args.config, check_only=args.check)

    if args.check:
        print("Live channels: %d" % total)
        print("Would add: %d" % added)
        print("Would remove: %d" % removed)
        if added == 0 and removed == 0:
            print("Config is up to date")
    else:
        print("Channels synced: %d total, +%d added, -%d removed" % (total, added, removed))


if __name__ == "__main__":
    main()
