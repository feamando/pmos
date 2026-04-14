#!/usr/bin/env python3
"""
Context Sources (v5.0)

Abstract base class for context data sources plus concrete implementations.
Each source uses connector_bridge for auth and config_loader for all settings.

Sources: Jira, Slack, GitHub, Google Docs, Gmail

Usage:
    from daily_context.context_sources import get_enabled_sources

    sources = get_enabled_sources(config)
    for source in sources:
        data = source.fetch(config, since)
        formatted = source.format(data)
"""

import logging
import threading
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from config_loader import get_config
    except ImportError:
        get_config = None

try:
    from pm_os_base.tools.core.connector_bridge import get_auth, is_service_available
except ImportError:
    try:
        from connector_bridge import get_auth, is_service_available
    except ImportError:
        get_auth = None
        is_service_available = None

logger = logging.getLogger(__name__)

# --- Constants for content truncation ---
DEFAULT_MAX_DOC_CHARS = 6000
DEFAULT_MAX_EMAIL_CHARS = 2500
DEFAULT_MAX_SLACK_CHARS = 1000
DEFAULT_MAX_JIRA_CHARS = 3000
DEFAULT_MAX_GITHUB_CHARS = 3000


def _smart_truncate(content: str, max_chars: int) -> str:
    """Truncate content keeping start (60%) and end (40%) for context.

    Args:
        content: Raw text content.
        max_chars: Maximum character limit.

    Returns:
        Truncated content with marker, or original if under limit.
    """
    if len(content) <= max_chars:
        return content
    keep_start = int(max_chars * 0.6)
    keep_end = int(max_chars * 0.4)
    omitted = len(content) - max_chars
    marker = f"\n\n... [TRUNCATED: {omitted} chars omitted] ...\n\n"
    return content[:keep_start] + marker + content[-keep_end:]


# =============================================================================
# Abstract Base Class
# =============================================================================


class ContextSource(ABC):
    """Abstract base class for all context data sources.

    Each source implements fetch() to retrieve raw data via connector_bridge
    and format() to render data as human-readable text for synthesis.
    """

    service_name: str = ""
    display_name: str = ""

    @abstractmethod
    def fetch(
        self,
        config: Any,
        since: datetime,
        processed_files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch data from the source.

        Args:
            config: ConfigLoader instance.
            since: Fetch data modified/created after this timestamp.
            processed_files: Previously processed item IDs to skip.

        Returns:
            Dict with 'items' list and optional metadata.
        """

    @abstractmethod
    def format(self, data: Dict[str, Any]) -> str:
        """Format fetched data into human-readable text.

        Args:
            data: Output from fetch().

        Returns:
            Formatted string for synthesis.
        """

    def is_available(self) -> bool:
        """Check if this source has auth available."""
        if is_service_available is None:
            return False
        return is_service_available(self.service_name)

    def _get_auth(self):
        """Get auth for this source via connector_bridge."""
        if get_auth is None:
            logger.warning("connector_bridge not available for %s", self.service_name)
            return None
        return get_auth(self.service_name)


# =============================================================================
# Google Docs Source
# =============================================================================


class GoogleDocsContextSource(ContextSource):
    """Fetch recently modified Google Docs and Sheets."""

    service_name = "google"
    display_name = "Google Docs"

    def fetch(
        self,
        config: Any,
        since: datetime,
        processed_files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch Google Docs modified since timestamp.

        Uses config-driven search terms built from:
        - config.get("context.search_terms", [])
        - config.get("team.reports") names
        - config.get("products.items") names
        """
        processed_files = processed_files or {}
        auth = self._get_auth()
        if auth is None or auth.source == "none":
            logger.info("Google auth not available, skipping Docs fetch")
            return {"items": [], "source": self.service_name}

        items = []
        try:
            # Build search terms from config (ZERO hardcoded values)
            search_terms = list(config.get("context.search_terms", []) or [])

            # Auto-build from team reports
            reports = config.get("team.reports", []) or []
            for report in reports:
                name = report.get("name", "") if isinstance(report, dict) else str(report)
                if name:
                    search_terms.append(name)

            # Auto-build from products
            products = config.get("products.items", []) or []
            for product in products:
                name = product.get("name", "") if isinstance(product, dict) else str(product)
                if name:
                    search_terms.append(name)

            user_email = config.get("user.email", "")
            if user_email:
                search_terms.append(user_email)

            # Deduplicate
            search_terms = list(dict.fromkeys(search_terms))

            since_str = since.strftime("%Y-%m-%dT%H:%M:%S")
            mime_types = [
                "application/vnd.google-apps.document",
                "application/vnd.google-apps.spreadsheet",
            ]
            mime_query = (
                "(" + " or ".join([f"mimeType = '{m}'" for m in mime_types]) + ")"
            )
            base_filters = (
                f"{mime_query} and modifiedTime > '{since_str}' and trashed = false"
            )

            if auth.source == "env":
                items = self._fetch_with_api(
                    auth, search_terms, base_filters, processed_files, since_str
                )
            else:
                # Connector mode: data fetched through Claude MCP tool
                logger.info(
                    "Google Docs available via connector — "
                    "use Claude MCP tool '%s' for interactive fetch",
                    auth.connector_tool_name,
                )

        except Exception as e:
            logger.error("Google Docs fetch failed: %s", e)

        return {"items": items, "source": self.service_name, "search_terms": search_terms}

    def _fetch_with_api(
        self,
        auth: Any,
        search_terms: List[str],
        base_filters: str,
        processed_files: Dict[str, Any],
        since_str: str,
    ) -> List[Dict[str, Any]]:
        """Fetch docs using Google API with .env credentials."""
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError:
            logger.warning("Google API client not installed")
            return []

        # Import credential helper from config
        try:
            from pm_os_base.tools.core.config_loader import get_google_paths
        except ImportError:
            try:
                from config_loader import get_google_paths
            except ImportError:
                logger.warning("Cannot resolve Google credential paths")
                return []

        google_paths = get_google_paths()
        token_file = google_paths.get("token")
        if not token_file or not __import__("os").path.exists(token_file):
            logger.warning("Google token file not found at %s", token_file)
            return []

        try:
            creds = Credentials.from_authorized_user_file(token_file)
        except Exception as e:
            logger.error("Failed to load Google credentials: %s", e)
            return []

        all_docs = {}
        all_docs_lock = threading.Lock()

        # Build queries
        queries = [
            ("owned", f"'me' in owners and {base_filters}"),
            ("shared", f"sharedWithMe and {base_filters}"),
        ]

        # Add fulltext search if we have search terms
        if search_terms:
            terms_query = (
                "("
                + " or ".join(
                    [f"fullText contains '{term}'" for term in search_terms[:15]]
                )
                + ")"
            )
            queries.append(("fulltext", f"{terms_query} and {base_filters}"))

        def _run_query(label_and_query):
            label, query = label_and_query
            found = {}
            try:
                thread_service = build("drive", "v3", credentials=creds)
                page_token = None
                while True:
                    results = (
                        thread_service.files()
                        .list(
                            pageSize=50,
                            fields="nextPageToken, files(id, name, mimeType, webViewLink, modifiedTime, owners)",
                            q=query,
                            orderBy="modifiedTime desc",
                            pageToken=page_token,
                        )
                        .execute()
                    )
                    for item in results.get("files", []):
                        item_id = item["id"]
                        item_mod = item.get("modifiedTime")
                        if item_id in processed_files and processed_files[item_id] == item_mod:
                            continue
                        if item_id not in found:
                            found[item_id] = item
                    page_token = results.get("nextPageToken")
                    if not page_token:
                        break
            except Exception as e:
                logger.warning("Drive query '%s' failed: %s", label, e)
            return found

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(_run_query, q): q[0] for q in queries}
            for future in as_completed(futures):
                label = futures[future]
                try:
                    result = future.result()
                    with all_docs_lock:
                        for doc_id, doc in result.items():
                            if doc_id not in all_docs:
                                all_docs[doc_id] = doc
                except Exception as e:
                    logger.warning("Drive query '%s' result failed: %s", label, e)

        return list(all_docs.values())

    def format(self, data: Dict[str, Any]) -> str:
        """Format Google Docs items for synthesis."""
        items = data.get("items", [])
        if not items:
            return ""

        lines = []
        lines.append("## GOOGLE DOCS")
        lines.append("")
        for doc in items:
            modified = doc.get("modifiedTime", "Unknown")[:10]
            owners = doc.get("owners", [{}])
            owner_name = owners[0].get("displayName", "Unknown") if owners else "Unknown"
            name = doc.get("name", "Untitled")
            link = doc.get("webViewLink", "")
            lines.append(f"- [DOC] [{name}]({link}) | Modified: {modified} | Owner: {owner_name}")
        lines.append("")
        return "\n".join(lines)


# =============================================================================
# Gmail Source
# =============================================================================


class GmailContextSource(ContextSource):
    """Fetch recent Gmail messages, filtering promotional emails."""

    service_name = "google"
    display_name = "Gmail"

    # Default promotional filter keywords (can be overridden via config)
    _DEFAULT_PROMO_SUBJECT = [
        "sale", "discount", "offer", "promo", "voucher", "% off",
        "cyber monday", "black friday", "save now", "free shipping",
        "coupon", "deal", "limited time", "special", "exclusive", "giveaway",
    ]
    _DEFAULT_PROMO_SENDER = [
        "noreply", "marketing", "promotions", "deals", "updates", "newsletter",
    ]

    def fetch(
        self,
        config: Any,
        since: datetime,
        processed_files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch Gmail messages since timestamp, filtering promotions."""
        processed_files = processed_files or {}
        auth = self._get_auth()
        if auth is None or auth.source == "none":
            logger.info("Google auth not available, skipping Gmail fetch")
            return {"items": [], "source": "gmail"}

        items = []
        try:
            if auth.source == "env":
                items = self._fetch_with_api(config, since, processed_files)
            else:
                logger.info(
                    "Gmail available via connector — use Claude MCP tool for interactive fetch"
                )
        except Exception as e:
            logger.error("Gmail fetch failed: %s", e)

        return {"items": items, "source": "gmail"}

    def _is_promotional(self, message: Dict[str, Any], config: Any) -> bool:
        """Check if email is promotional based on configurable patterns."""
        headers = message.get("payload", {}).get("headers", [])
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "").lower()
        sender = next((h["value"] for h in headers if h["name"] == "From"), "").lower()

        promo_subjects = config.get("context.promo_subject_keywords", self._DEFAULT_PROMO_SUBJECT)
        promo_senders = config.get("context.promo_sender_keywords", self._DEFAULT_PROMO_SENDER)

        for keyword in promo_subjects:
            if keyword in subject:
                return True
        for keyword in promo_senders:
            if keyword in sender:
                return True
        return False

    def _fetch_with_api(
        self, config: Any, since: datetime, processed_files: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Fetch emails using Google API."""
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError:
            logger.warning("Google API client not installed")
            return []

        try:
            from pm_os_base.tools.core.config_loader import get_google_paths
        except ImportError:
            try:
                from config_loader import get_google_paths
            except ImportError:
                return []

        google_paths = get_google_paths()
        token_file = google_paths.get("token")
        if not token_file or not __import__("os").path.exists(token_file):
            logger.warning("Google token not found")
            return []

        try:
            creds = Credentials.from_authorized_user_file(token_file)
        except Exception as e:
            logger.error("Failed to load Google credentials: %s", e)
            return []

        messages = []
        try:
            service = build("gmail", "v1", credentials=creds)
            since_ts = int(since.timestamp())
            query = f"after:{since_ts}"

            results = (
                service.users()
                .messages()
                .list(userId="me", q=query, maxResults=50)
                .execute()
            )
            message_list = results.get("messages", [])

            to_fetch = [
                msg["id"]
                for msg in message_list
                if msg["id"] not in processed_files
                or processed_files[msg["id"]] != msg.get("internalDate")
            ]

            def _fetch_one(msg_id):
                try:
                    thread_svc = build("gmail", "v1", credentials=creds)
                    full_msg = (
                        thread_svc.users()
                        .messages()
                        .get(userId="me", id=msg_id, format="full")
                        .execute()
                    )
                    if not self._is_promotional(full_msg, config):
                        return full_msg
                except Exception as e:
                    logger.warning("Could not fetch email %s: %s", msg_id, e)
                return None

            if to_fetch:
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = {executor.submit(_fetch_one, mid): mid for mid in to_fetch}
                    for future in as_completed(futures):
                        result = future.result()
                        if result is not None:
                            messages.append(result)

        except Exception as e:
            logger.warning("Gmail query failed: %s", e)

        return messages

    def format(self, data: Dict[str, Any]) -> str:
        """Format Gmail items for synthesis."""
        items = data.get("items", [])
        if not items:
            return ""

        lines = []
        lines.append("## GMAIL")
        lines.append("")
        for email in items:
            headers = email.get("payload", {}).get("headers", [])
            subject = next(
                (h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)"
            )
            sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
            date_ts = int(email.get("internalDate", 0)) / 1000
            date_str = datetime.fromtimestamp(date_ts).strftime("%Y-%m-%d")
            lines.append(f"- [EMAIL] {subject} | From: {sender} | Date: {date_str}")
        lines.append("")
        return "\n".join(lines)


# =============================================================================
# Slack Source
# =============================================================================


class SlackContextSource(ContextSource):
    """Fetch Slack messages from configured channels."""

    service_name = "slack"
    display_name = "Slack"

    def fetch(
        self,
        config: Any,
        since: datetime,
        processed_files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch Slack messages from channels since timestamp."""
        processed_files = processed_files or {}
        auth = self._get_auth()
        if auth is None or auth.source == "none":
            logger.info("Slack auth not available, skipping")
            return {"items": [], "source": self.service_name}

        items = []
        try:
            if auth.source == "env":
                items = self._fetch_with_api(auth, config, since, processed_files)
            else:
                logger.info(
                    "Slack available via connector — use Claude MCP tool for interactive fetch"
                )
        except Exception as e:
            logger.error("Slack fetch failed: %s", e)

        return {"items": items, "source": self.service_name}

    def _fetch_with_api(
        self,
        auth: Any,
        config: Any,
        since: datetime,
        processed_files: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Fetch Slack messages using bot token."""
        try:
            from slack_sdk import WebClient
            from slack_sdk.errors import SlackApiError
        except ImportError:
            logger.warning("slack_sdk not installed")
            return []

        client = WebClient(token=auth.token)
        messages = []
        user_cache: Dict[str, str] = {}
        user_cache_lock = threading.Lock()
        oldest = str(since.timestamp())

        # Get channels from config or API
        configured_channels = config.get("integrations.slack.channels", []) or []
        channels = []

        if configured_channels:
            channels = [
                {"id": ch.get("id", ""), "name": ch.get("name", "")}
                for ch in configured_channels
                if ch.get("id")
            ]
            logger.info("Slack: Using %s channels from config", len(channels))
        else:
            try:
                response = client.users_conversations(
                    types="public_channel,private_channel"
                )
                channels = response["channels"]
                logger.info("Slack: Using %s channels from API", len(channels))
            except Exception as e:
                logger.warning("Could not list Slack channels: %s", e)
                return []

        def _fetch_channel(channel):
            channel_id = channel["id"]
            channel_name = channel["name"]
            channel_msgs = []
            try:
                result = client.conversations_history(
                    channel=channel_id, oldest=oldest, limit=50
                )
                for msg in result["messages"]:
                    if msg.get("subtype"):
                        continue
                    msg_id = f"slack_{channel_id}_{msg['ts']}"
                    if msg_id in processed_files:
                        continue
                    msg["channel_name"] = channel_name
                    msg["channel_id"] = channel_id
                    msg["unique_id"] = msg_id

                    user_id = msg.get("user")
                    if user_id:
                        with user_cache_lock:
                            cached = user_cache.get(user_id)
                        if cached is None:
                            try:
                                user_info = client.users_info(user=user_id)
                                real_name = user_info["user"]["real_name"]
                            except Exception:
                                real_name = user_id
                            with user_cache_lock:
                                user_cache[user_id] = real_name
                            cached = real_name
                        msg["user_name"] = cached
                    channel_msgs.append(msg)
            except Exception as e:
                logger.warning("Could not fetch history for %s: %s", channel_name, e)
            return channel_msgs

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(_fetch_channel, ch): ch["name"] for ch in channels}
            for future in as_completed(futures):
                channel_msgs = future.result()
                messages.extend(channel_msgs)

        return messages

    def format(self, data: Dict[str, Any]) -> str:
        """Format Slack messages for synthesis."""
        items = data.get("items", [])
        if not items:
            return ""

        lines = []
        lines.append("## SLACK MESSAGES")
        lines.append("")
        for msg in items:
            ts = float(msg.get("ts", 0))
            date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
            user = msg.get("user_name", msg.get("user", "Unknown"))
            channel = msg.get("channel_name", "Unknown")
            text = _smart_truncate(
                msg.get("text", "").replace("\n", " "), DEFAULT_MAX_SLACK_CHARS
            )
            lines.append(f"- [SLACK] {channel} | {user} ({date_str}): {text[:80]}...")
        lines.append("")
        return "\n".join(lines)


# =============================================================================
# Jira Source
# =============================================================================


class JiraContextSource(ContextSource):
    """Fetch Jira issues from configured projects/boards."""

    service_name = "jira"
    display_name = "Jira"

    def fetch(
        self,
        config: Any,
        since: datetime,
        processed_files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch recently updated Jira issues."""
        processed_files = processed_files or {}
        auth = self._get_auth()
        if auth is None or auth.source == "none":
            logger.info("Jira auth not available, skipping")
            return {"items": [], "source": self.service_name}

        items = []
        try:
            if auth.source == "env":
                items = self._fetch_with_api(auth, config, since, processed_files)
            else:
                logger.info(
                    "Jira available via connector — use Claude MCP tool for interactive fetch"
                )
        except Exception as e:
            logger.error("Jira fetch failed: %s", e)

        return {"items": items, "source": self.service_name}

    def _fetch_with_api(
        self,
        auth: Any,
        config: Any,
        since: datetime,
        processed_files: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Fetch Jira issues using REST API."""
        try:
            import requests
        except ImportError:
            logger.warning("requests library not installed")
            return []

        jira_config = config.get("integrations.jira", {}) or {}
        base_url = jira_config.get("url", "")
        user_email = config.get("user.email", "")
        projects = jira_config.get("projects", [])

        if not base_url:
            logger.warning("Jira URL not configured (integrations.jira.url)")
            return []

        since_str = since.strftime("%Y-%m-%d")
        project_clause = ""
        if projects:
            project_list = ", ".join(projects)
            project_clause = f"project in ({project_list}) AND "

        jql = f"{project_clause}updated >= '{since_str}' ORDER BY updated DESC"

        try:
            response = requests.get(
                f"{base_url}/rest/api/3/search",
                params={"jql": jql, "maxResults": 50, "fields": "summary,status,assignee,priority,updated"},
                auth=(user_email, auth.token),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            items = []
            for issue in data.get("issues", []):
                issue_key = issue.get("key", "")
                if issue_key in processed_files:
                    continue
                fields = issue.get("fields", {})
                assignee = fields.get("assignee", {})
                items.append({
                    "key": issue_key,
                    "summary": fields.get("summary", ""),
                    "status": (fields.get("status") or {}).get("name", "Unknown"),
                    "assignee": (assignee or {}).get("displayName", "Unassigned"),
                    "priority": (fields.get("priority") or {}).get("name", "None"),
                    "updated": fields.get("updated", ""),
                })
            return items

        except Exception as e:
            logger.warning("Jira API request failed: %s", e)
            return []

    def format(self, data: Dict[str, Any]) -> str:
        """Format Jira issues for synthesis."""
        items = data.get("items", [])
        if not items:
            return ""

        lines = []
        lines.append("## JIRA ISSUES")
        lines.append("")
        for issue in items:
            lines.append(
                f"- [{issue['key']}] {issue['summary']} "
                f"| Status: {issue['status']} "
                f"| Assignee: {issue['assignee']} "
                f"| Priority: {issue['priority']}"
            )
        lines.append("")
        return "\n".join(lines)


# =============================================================================
# GitHub Source
# =============================================================================


class GitHubContextSource(ContextSource):
    """Fetch GitHub notifications and recent PRs/issues."""

    service_name = "github"
    display_name = "GitHub"

    def fetch(
        self,
        config: Any,
        since: datetime,
        processed_files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch GitHub notifications since timestamp."""
        processed_files = processed_files or {}
        auth = self._get_auth()
        if auth is None or auth.source == "none":
            logger.info("GitHub auth not available, skipping")
            return {"items": [], "source": self.service_name}

        items = []
        try:
            if auth.source == "env":
                items = self._fetch_with_api(auth, config, since, processed_files)
            else:
                logger.info(
                    "GitHub available via connector — use Claude MCP tool for interactive fetch"
                )
        except Exception as e:
            logger.error("GitHub fetch failed: %s", e)

        return {"items": items, "source": self.service_name}

    def _fetch_with_api(
        self,
        auth: Any,
        config: Any,
        since: datetime,
        processed_files: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Fetch GitHub notifications using REST API."""
        try:
            import requests
        except ImportError:
            logger.warning("requests library not installed")
            return []

        headers = {
            "Authorization": f"token {auth.token}",
            "Accept": "application/vnd.github+json",
        }
        since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        items = []
        try:
            response = requests.get(
                "https://api.github.com/notifications",
                params={"since": since_str, "all": "false"},
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()

            for notification in response.json():
                notif_id = notification.get("id", "")
                if notif_id in processed_files:
                    continue
                subject = notification.get("subject", {})
                items.append({
                    "id": notif_id,
                    "title": subject.get("title", ""),
                    "type": subject.get("type", "Unknown"),
                    "repo": notification.get("repository", {}).get("full_name", ""),
                    "reason": notification.get("reason", ""),
                    "updated_at": notification.get("updated_at", ""),
                })

        except Exception as e:
            logger.warning("GitHub API request failed: %s", e)

        return items

    def format(self, data: Dict[str, Any]) -> str:
        """Format GitHub notifications for synthesis."""
        items = data.get("items", [])
        if not items:
            return ""

        lines = []
        lines.append("## GITHUB NOTIFICATIONS")
        lines.append("")
        for notif in items:
            lines.append(
                f"- [{notif['type']}] {notif['title']} "
                f"| Repo: {notif['repo']} "
                f"| Reason: {notif['reason']}"
            )
        lines.append("")
        return "\n".join(lines)


# =============================================================================
# Source Registry
# =============================================================================

# All available context sources
ALL_SOURCES = [
    JiraContextSource(),
    SlackContextSource(),
    GitHubContextSource(),
    GoogleDocsContextSource(),
    GmailContextSource(),
]


def get_enabled_sources(config: Any) -> List[ContextSource]:
    """Get list of context sources that are enabled and have auth.

    Checks both config enable flags and auth availability.

    Args:
        config: ConfigLoader instance.

    Returns:
        List of ContextSource instances ready to fetch.
    """
    enabled = []
    for source in ALL_SOURCES:
        # Check config enable flag
        config_key = f"context.sources.{source.service_name}.enabled"
        is_enabled = config.get(config_key, True)  # Default: enabled

        if not is_enabled:
            logger.debug("Source %s disabled in config", source.display_name)
            continue

        if source.is_available():
            enabled.append(source)
            logger.debug("Source %s enabled and available", source.display_name)
        else:
            logger.debug("Source %s enabled but no auth available", source.display_name)

    return enabled


def fetch_all_sources(
    config: Any,
    since: datetime,
    processed_files: Optional[Dict[str, Any]] = None,
    max_workers: int = 3,
) -> Dict[str, Dict[str, Any]]:
    """Fetch from all enabled sources in parallel.

    Args:
        config: ConfigLoader instance.
        since: Fetch data after this timestamp.
        processed_files: Previously processed item IDs.
        max_workers: Max parallel fetches.

    Returns:
        Dict mapping source name to fetch result.
    """
    processed_files = processed_files or {}
    sources = get_enabled_sources(config)
    results = {}

    if not sources:
        logger.warning("No context sources available")
        return results

    logger.info("Fetching from %s source(s) in parallel", len(sources))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(source.fetch, config, since, processed_files): source
            for source in sources
        }
        for future in as_completed(futures):
            source = futures[future]
            try:
                data = future.result()
                results[source.service_name] = data
                item_count = len(data.get("items", []))
                logger.info(
                    "Source %s: fetched %s items", source.display_name, item_count
                )
            except Exception as e:
                logger.error("Source %s fetch failed: %s", source.display_name, e)
                results[source.service_name] = {"items": [], "source": source.service_name, "error": str(e)}

    return results


# =============================================================================
# CLI Interface
# =============================================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="PM-OS Context Sources")
    parser.add_argument(
        "--list", action="store_true", help="List all available sources"
    )
    parser.add_argument(
        "--check", metavar="SOURCE", help="Check auth for a specific source"
    )
    parser.add_argument(
        "--fetch", action="store_true", help="Fetch from all enabled sources"
    )
    parser.add_argument(
        "--days", type=int, default=7, help="Days to look back (default: 7)"
    )

    args = parser.parse_args()

    if get_config is None:
        print("Error: config_loader not available", file=__import__("sys").stderr)
        __import__("sys").exit(1)

    config = get_config()

    if args.list:
        print("Context Sources:")
        for source in ALL_SOURCES:
            available = source.is_available()
            status = "available" if available else "not configured"
            print(f"  [{source.service_name}] {source.display_name}: {status}")

    elif args.check:
        for source in ALL_SOURCES:
            if source.service_name == args.check:
                auth = source._get_auth()
                if auth:
                    print(f"{source.display_name}: source={auth.source}")
                else:
                    print(f"{source.display_name}: not available")
                break
        else:
            print(f"Unknown source: {args.check}")

    elif args.fetch:
        from datetime import timedelta, timezone

        since = datetime.now(timezone.utc) - timedelta(days=args.days)
        results = fetch_all_sources(config, since)
        for name, data in results.items():
            source_obj = next((s for s in ALL_SOURCES if s.service_name == name), None)
            if source_obj:
                formatted = source_obj.format(data)
                if formatted:
                    print(formatted)
                else:
                    print(f"## {source_obj.display_name}: no items")
            print()

    else:
        parser.print_help()
