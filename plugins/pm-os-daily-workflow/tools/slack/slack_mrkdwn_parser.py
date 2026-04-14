#!/usr/bin/env python3
"""
Slack Mrkdwn Parser (v5.0)

Converts Slack's mrkdwn format to readable markdown/plain text.
Resolves user IDs, channel IDs, and special formatting.

Ported from v4.x slack_mrkdwn_parser.py — cache path via path_resolver,
mostly generic (no hardcoded values).

Usage:
    from slack_mrkdwn_parser import MrkdwnParser

    parser = MrkdwnParser(user_cache, channel_cache)
    readable_text = parser.parse(slack_message_text)
"""

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# v5 shared utils
try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        _base = __import__("pathlib").Path(__file__).resolve().parent.parent.parent.parent
        sys.path.insert(0, str(_base / "pm-os-base" / "tools" / "core"))
        from path_resolver import get_paths
    except ImportError:
        logger.warning("Cannot import path_resolver; using fallback cache dir")
        get_paths = None


def _default_cache_dir() -> str:
    """Get default cache directory via path_resolver."""
    if get_paths is not None:
        try:
            return str(get_paths().brain / "Inbox" / "Slack")
        except Exception:
            pass
    return ""


class MrkdwnParser:
    """
    Parse Slack mrkdwn format into readable text.

    Handles:
    - User mentions: <@U123> -> @Real Name
    - Channel links: <#C123|channel-name> -> #channel-name
    - URLs: <https://url|display> -> display (url)
    - Special mentions: <!channel>, <!here>, <!everyone>
    - Date formatting: <!date^timestamp^format|fallback>
    - Emoji: :emoji_name: -> :emoji_name: (preserved)
    """

    def __init__(self, user_cache: dict = None, channel_cache: dict = None):
        """
        Initialize parser with optional caches.

        Args:
            user_cache: Dict of {user_id: {name, username, display_name, ...}}
            channel_cache: Dict of {channel_id: {name, ...}}
        """
        self.user_cache = user_cache or {}
        self.channel_cache = channel_cache or {}

    @classmethod
    def from_cache_dir(cls, cache_dir: str = None) -> "MrkdwnParser":
        """
        Create parser by loading caches from directory.

        Args:
            cache_dir: Directory containing user_cache.json and channel_cache.json

        Returns:
            MrkdwnParser instance with loaded caches
        """
        if cache_dir is None:
            cache_dir = _default_cache_dir()

        cache_path = Path(cache_dir)
        user_cache = {}
        channel_cache = {}

        user_cache_file = cache_path / "user_cache.json"
        if user_cache_file.exists():
            with open(user_cache_file, "r", encoding="utf-8") as f:
                user_cache = json.load(f)

        channel_cache_file = cache_path / "channel_cache.json"
        if channel_cache_file.exists():
            with open(channel_cache_file, "r", encoding="utf-8") as f:
                channel_cache = json.load(f)

        return cls(user_cache, channel_cache)

    def resolve_user(self, user_id: str) -> str:
        """Resolve user ID to display name."""
        if user_id in self.user_cache:
            data = self.user_cache[user_id]
            return (
                data.get("display_name")
                or data.get("name")
                or data.get("username")
                or user_id
            )
        return user_id

    def resolve_channel(self, channel_id: str, fallback: str = None) -> str:
        """Resolve channel ID to name."""
        if channel_id in self.channel_cache:
            return self.channel_cache[channel_id].get("name", fallback or channel_id)
        return fallback or channel_id

    def _parse_user_mention(self, match: re.Match) -> str:
        """Parse <@U123> or <@U123|display> format."""
        user_id = match.group(1)
        fallback = match.group(3) if match.lastindex >= 3 and match.group(3) else None

        resolved = self.resolve_user(user_id)
        if resolved != user_id:
            return "@%s" % resolved
        elif fallback:
            return "@%s" % fallback
        else:
            return "@%s" % user_id

    def _parse_channel_link(self, match: re.Match) -> str:
        """Parse <#C123|channel-name> format."""
        channel_id = match.group(1)
        fallback = match.group(3) if match.lastindex >= 3 and match.group(3) else None
        resolved = self.resolve_channel(channel_id, fallback)
        return "#%s" % resolved

    def _parse_url(self, match: re.Match) -> str:
        """Parse <url|display> or <url> format."""
        url = match.group(1)
        display = match.group(3) if match.lastindex >= 3 and match.group(3) else None
        if display:
            return "%s (%s)" % (display, url)
        else:
            return url

    def _parse_special_mention(self, match: re.Match) -> str:
        """Parse <!channel>, <!here>, <!everyone>, etc."""
        mention_type = match.group(1)
        special_mentions = {
            "channel": "@channel",
            "here": "@here",
            "everyone": "@everyone",
        }
        return special_mentions.get(mention_type, "@%s" % mention_type)

    def _parse_date(self, match: re.Match) -> str:
        """Parse <!date^timestamp^format|fallback> format."""
        timestamp = match.group(1)
        date_format = match.group(2) if match.lastindex >= 2 else None
        fallback = match.group(4) if match.lastindex >= 4 and match.group(4) else None

        try:
            ts = int(timestamp)
            dt = datetime.fromtimestamp(ts)

            if date_format:
                if "{date_short}" in date_format:
                    return dt.strftime("%b %d, %Y")
                elif "{date_long}" in date_format:
                    return dt.strftime("%B %d, %Y")
                elif "{time}" in date_format:
                    return dt.strftime("%H:%M")
                elif "{date_num}" in date_format:
                    return dt.strftime("%Y-%m-%d")

            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return fallback or timestamp

    def _parse_subteam(self, match: re.Match) -> str:
        """Parse <!subteam^S123|@group-name> format."""
        display = match.group(3) if match.lastindex >= 3 and match.group(3) else None
        if display:
            return display
        return "@group"

    def parse(self, text: str) -> str:
        """
        Parse Slack mrkdwn text to readable format.

        Args:
            text: Raw Slack message text with mrkdwn formatting

        Returns:
            Readable text with resolved mentions and links
        """
        if not text:
            return ""

        result = text

        # User mentions: <@U123> or <@U123|display>
        result = re.sub(
            r"<@([UW][A-Z0-9]+)(\|([^>]+))?>", self._parse_user_mention, result
        )

        # Channel links: <#C123|channel-name> or <#C123>
        result = re.sub(
            r"<#([C][A-Z0-9]+)(\|([^>]+))?>", self._parse_channel_link, result
        )

        # Special mentions: <!channel>, <!here>, <!everyone>
        result = re.sub(
            r"<!(channel|here|everyone)>", self._parse_special_mention, result
        )

        # Subteam mentions: <!subteam^S123|@group>
        result = re.sub(
            r"<!subteam\^([A-Z0-9]+)(\|([^>]+))?>", self._parse_subteam, result
        )

        # Date formatting: <!date^timestamp^format|fallback>
        result = re.sub(
            r"<!date\^(\d+)\^([^|>]+)(\|([^>]+))?>", self._parse_date, result
        )

        # URLs: <url|display> or <url>
        result = re.sub(r"<(https?://[^|>]+)(\|([^>]+))?>", self._parse_url, result)

        # mailto links: <mailto:email|display>
        result = re.sub(
            r"<mailto:([^|>]+)(\|([^>]+))?>",
            lambda m: m.group(3) if m.lastindex >= 3 and m.group(3) else m.group(1),
            result,
        )

        return result

    def parse_with_context(self, text: str) -> dict:
        """
        Parse text and extract metadata about mentions.

        Returns:
            dict with text, mentions, channels, links
        """
        mentions = []
        channels = []
        links = []

        for match in re.finditer(r"<@([UW][A-Z0-9]+)(\|([^>]+))?>", text):
            user_id = match.group(1)
            resolved = self.resolve_user(user_id)
            mentions.append({"type": "user", "id": user_id, "name": resolved})

        for match in re.finditer(r"<#([C][A-Z0-9]+)(\|([^>]+))?>", text):
            channel_id = match.group(1)
            fallback = match.group(3) if match.lastindex >= 3 and match.group(3) else None
            resolved = self.resolve_channel(channel_id, fallback)
            channels.append({"id": channel_id, "name": resolved})

        for match in re.finditer(r"<(https?://[^|>]+)(\|([^>]+))?>", text):
            links.append(match.group(1))

        return {
            "text": self.parse(text),
            "mentions": mentions,
            "channels": channels,
            "links": links,
        }


def format_message_for_brain(
    text: str,
    user_id: str,
    timestamp: str,
    parser: MrkdwnParser,
    channel_name: str = None,
    thread_ts: str = None,
    reactions: list = None,
) -> str:
    """
    Format a Slack message for Brain ingestion.

    Args:
        text: Raw message text
        user_id: Sender's user ID
        timestamp: Message timestamp (Slack ts format)
        parser: MrkdwnParser instance
        channel_name: Channel name (optional)
        thread_ts: Thread parent timestamp if this is a reply
        reactions: List of reaction dicts

    Returns:
        Formatted string for Brain markdown
    """
    try:
        ts = float(timestamp)
        dt = datetime.fromtimestamp(ts)
        time_str = dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        time_str = timestamp

    sender = parser.resolve_user(user_id)
    parsed_text = parser.parse(text)

    lines = []

    header_parts = ["**%s**" % sender, "(%s)" % time_str]
    if channel_name:
        header_parts.insert(1, "in #%s" % channel_name)
    if thread_ts and thread_ts != timestamp:
        header_parts.append("[reply]")

    lines.append(" ".join(header_parts))
    lines.append("")
    lines.append(parsed_text)

    if reactions:
        reaction_strs = [":%s: (%d)" % (r["name"], r.get("count", 1)) for r in reactions]
        lines.append("")
        lines.append("Reactions: %s" % " ".join(reaction_strs))

    lines.append("")
    lines.append("---")

    return "\n".join(lines)


def parse_slack_text(text: str, cache_dir: str = None) -> str:
    """
    Quick parse of Slack text using cached lookups.

    Args:
        text: Raw Slack message text
        cache_dir: Directory containing cache files

    Returns:
        Readable text
    """
    parser = MrkdwnParser.from_cache_dir(cache_dir)
    return parser.parse(text)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) > 1:
        test_text = " ".join(sys.argv[1:])
    else:
        print("Slack Mrkdwn Parser")
        print("=" * 40)
        print("Enter text to parse (Ctrl+D to finish):")
        test_text = sys.stdin.read()

    print("\nParsed output:")
    print("-" * 40)

    try:
        parser = MrkdwnParser.from_cache_dir()
        result = parser.parse_with_context(test_text)
        print(result["text"])
        print()
        if result["mentions"]:
            print("Mentions: %s" % result["mentions"])
        if result["channels"]:
            print("Channels: %s" % result["channels"])
        if result["links"]:
            print("Links: %s" % result["links"])
    except Exception:
        parser = MrkdwnParser()
        print(parser.parse(test_text))
        logger.warning("User/channel caches not found - IDs not resolved")
