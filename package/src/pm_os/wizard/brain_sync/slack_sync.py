"""
PM-OS Slack Brain Sync

Syncs channels, users, and recent messages from Slack.
"""

from pathlib import Path
from typing import Optional, Callable, Dict, List, Any
from datetime import datetime, timedelta

from pm_os.wizard.brain_sync.base import BaseSyncer, SyncResult, SyncProgress
from pm_os.wizard.exceptions import CredentialError, SyncError, NetworkError


class SlackSyncer(BaseSyncer):
    """Sync brain entities from Slack."""

    def __init__(
        self,
        brain_path: Path,
        token: str,
        channels: Optional[List[str]] = None
    ):
        """Initialize Slack syncer.

        Args:
            brain_path: Path to brain directory
            token: Slack bot token (xoxb-...)
            channels: Optional list of channel names to sync (None = all public)
        """
        super().__init__(brain_path)
        self.token = token
        self.channels = channels
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def _api_call(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Make a Slack API call."""
        try:
            import requests
        except ImportError:
            raise SyncError(
                "requests library not installed",
                service="Slack",
                remediation="pip install requests"
            )

        url = f"https://slack.com/api/{method}"

        response = requests.get(
            url,
            headers=self._headers,
            params=params or {},
            timeout=30
        )

        if response.status_code != 200:
            raise NetworkError(
                f"Slack API error: {response.status_code}",
                endpoint=url
            )

        data = response.json()
        if not data.get("ok"):
            error = data.get("error", "Unknown error")
            if error in ("invalid_auth", "token_revoked"):
                raise CredentialError(
                    f"Slack authentication failed: {error}",
                    credential_type="Slack"
                )
            raise SyncError(f"Slack API error: {error}", service="Slack")

        return data

    def test_connection(self) -> tuple:
        """Test connection to Slack."""
        try:
            data = self._api_call("auth.test")
            bot_name = data.get("user", "bot")
            team = data.get("team", "workspace")
            return True, f"Connected as @{bot_name} in {team}"
        except CredentialError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    def sync(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        incremental: bool = True
    ) -> SyncResult:
        """Sync Slack data to brain.

        Args:
            progress_callback: Progress callback (current, total, phase)
            incremental: Only sync recent messages

        Returns:
            SyncResult with details
        """
        result = SyncResult(success=True, message="")
        progress = SyncProgress(callback=progress_callback)

        try:
            # Phase 1: Get channels
            progress.phase = "Fetching channels"
            channels = self._fetch_channels()

            if self.channels:
                channels = [c for c in channels if c['name'] in self.channels]

            progress.total = len(channels) * 2 + 1  # channels + users + messages per channel

            # Phase 2: Sync users first (for relationship mapping)
            progress.update(0, "Syncing users")
            user_map = self._sync_users(result)
            progress.increment()

            # Phase 3: Sync channels
            for channel in channels:
                progress.update(progress.current, f"Syncing channel: #{channel['name']}")
                self._sync_channel(channel, user_map, result)
                progress.increment()

            # Phase 4: Sync recent messages (if incremental)
            for channel in channels[:10]:  # Limit to 10 most active channels
                progress.update(progress.current, f"Syncing messages: #{channel['name']}")
                self._sync_messages(channel, user_map, result, days_back=7 if incremental else 30)
                progress.increment()

            # Build summary message
            total_entities = result.entities_created + result.entities_updated
            result.message = f"Synced {total_entities} entities from {len(channels)} channels"

        except CredentialError:
            raise
        except SyncError:
            raise
        except Exception as e:
            result.success = False
            result.message = f"Sync failed: {str(e)}"
            result.errors.append(str(e))

        return result

    def _fetch_channels(self) -> List[Dict]:
        """Fetch accessible channels."""
        data = self._api_call(
            "conversations.list",
            params={"limit": 100, "types": "public_channel,private_channel"}
        )
        return data.get("channels", [])

    def _sync_users(self, result: SyncResult) -> Dict[str, Dict]:
        """Sync users and return a mapping of user_id -> user info."""
        user_map = {}

        try:
            data = self._api_call("users.list", params={"limit": 200})
            members = data.get("members", [])

            for member in members:
                if member.get("deleted") or member.get("is_bot"):
                    continue

                user_id = member.get("id")
                profile = member.get("profile", {})
                name = profile.get("real_name") or profile.get("display_name") or member.get("name", "Unknown")

                user_map[user_id] = {
                    "name": name,
                    "email": profile.get("email", ""),
                    "title": profile.get("title", "")
                }

                # Write person entity
                body = f"""# {name}

## Profile

- **Title**: {profile.get('title', 'Not set')}
- **Email**: {profile.get('email', 'Not set')}
- **Status**: {profile.get('status_text', '')}

## Slack

- **Username**: @{member.get('name', 'unknown')}
- **Timezone**: {member.get('tz', 'Unknown')}
"""

                self.write_entity(
                    entity_type="person",
                    name=name,
                    source="slack",
                    body=body,
                    sync_id=user_id,
                    email=profile.get("email", ""),
                    role=profile.get("title", ""),
                    slack_id=user_id
                )

                result.entities_created += 1

        except Exception as e:
            result.errors.append(f"Error syncing users: {str(e)}")

        return user_map

    def _sync_channel(self, channel: Dict, user_map: Dict, result: SyncResult):
        """Sync a single channel entity."""
        name = channel.get("name", "unknown")
        channel_id = channel.get("id")

        # Get member count
        member_count = channel.get("num_members", 0)

        body = f"""# #{name}

## Details

- **Type**: {'Private' if channel.get('is_private') else 'Public'} Channel
- **Members**: {member_count}
- **Created**: {datetime.fromtimestamp(channel.get('created', 0)).strftime('%Y-%m-%d')}

## Topic

{channel.get('topic', {}).get('value', 'No topic set')}

## Purpose

{channel.get('purpose', {}).get('value', 'No purpose set')}
"""

        self.write_entity(
            entity_type="channel",
            name=f"#{name}",
            source="slack",
            body=body,
            sync_id=channel_id,
            channel_id=channel_id,
            is_private=channel.get("is_private", False),
            topic=channel.get("topic", {}).get("value", ""),
            purpose=channel.get("purpose", {}).get("value", ""),
            member_count=member_count
        )

        result.entities_created += 1

    def _sync_messages(
        self,
        channel: Dict,
        user_map: Dict,
        result: SyncResult,
        days_back: int = 7
    ):
        """Sync recent messages from a channel (saved as daily digests)."""
        channel_id = channel.get("id")
        channel_name = channel.get("name")

        # Calculate timestamp for oldest message to fetch
        oldest_ts = (datetime.now() - timedelta(days=days_back)).timestamp()

        try:
            data = self._api_call(
                "conversations.history",
                params={
                    "channel": channel_id,
                    "oldest": str(oldest_ts),
                    "limit": 100
                }
            )

            messages = data.get("messages", [])
            if not messages:
                return

            # Group messages by date
            daily_messages = {}
            for msg in messages:
                ts = float(msg.get("ts", 0))
                date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                if date not in daily_messages:
                    daily_messages[date] = []
                daily_messages[date].append(msg)

            # Create a digest for each day
            for date, day_msgs in daily_messages.items():
                self._create_message_digest(
                    channel_name,
                    channel_id,
                    date,
                    day_msgs,
                    user_map,
                    result
                )

        except Exception as e:
            result.errors.append(f"Error syncing messages for #{channel_name}: {str(e)}")

    def _create_message_digest(
        self,
        channel_name: str,
        channel_id: str,
        date: str,
        messages: List[Dict],
        user_map: Dict,
        result: SyncResult
    ):
        """Create a daily message digest entity."""
        # Build message list
        message_lines = []
        for msg in sorted(messages, key=lambda m: float(m.get("ts", 0))):
            ts = float(msg.get("ts", 0))
            time_str = datetime.fromtimestamp(ts).strftime("%H:%M")
            user_id = msg.get("user", "")
            user_info = user_map.get(user_id, {})
            user_name = user_info.get("name", "Unknown")
            text = msg.get("text", "")[:200]  # Truncate long messages

            message_lines.append(f"**{time_str}** - *{user_name}*: {text}")

        body = f"""# #{channel_name} - {date}

## Messages

{chr(10).join(message_lines)}

---
*{len(messages)} messages*
"""

        # Save as a document type
        self.write_entity(
            entity_type="document",
            name=f"Slack #{channel_name} {date}",
            source="slack",
            body=body,
            sync_id=f"{channel_id}_{date}",
            channel=channel_name,
            date=date,
            message_count=len(messages),
            relationships={"channel": [f"#{channel_name}"]}
        )

        result.entities_created += 1
