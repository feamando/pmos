"""
PM-OS Confluence Brain Sync

Syncs spaces and pages from Confluence.
"""

from pathlib import Path
from typing import Optional, Callable, Dict, List, Any
from datetime import datetime
import re

from pm_os.wizard.brain_sync.base import BaseSyncer, SyncResult, SyncProgress
from pm_os.wizard.exceptions import CredentialError, SyncError, NetworkError


class ConfluenceSyncer(BaseSyncer):
    """Sync brain entities from Confluence."""

    def __init__(
        self,
        brain_path: Path,
        url: str,
        email: str,
        token: str,
        spaces: Optional[List[str]] = None
    ):
        """Initialize Confluence syncer.

        Args:
            brain_path: Path to brain directory
            url: Confluence instance URL
            email: User email for auth
            token: API token
            spaces: Optional list of space keys to sync (None = all)
        """
        super().__init__(brain_path)
        self.url = url.rstrip("/")
        self.email = email
        self.token = token
        self.spaces = spaces
        self._session = None

    def _get_session(self):
        """Get or create requests session."""
        if self._session is None:
            try:
                import requests
                from requests.auth import HTTPBasicAuth
            except ImportError:
                raise SyncError(
                    "requests library not installed",
                    service="Confluence",
                    remediation="pip install requests"
                )

            self._session = requests.Session()
            self._session.auth = HTTPBasicAuth(self.email, self.token)
            self._session.headers.update({"Accept": "application/json"})

        return self._session

    def _api_call(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a Confluence API call."""
        session = self._get_session()

        # Try wiki API first (Cloud), fall back to standard API
        url = f"{self.url}/wiki/rest/api{endpoint}"

        response = session.get(url, params=params or {}, timeout=30)

        # If 404, try without /wiki prefix (Server)
        if response.status_code == 404:
            url = f"{self.url}/rest/api{endpoint}"
            response = session.get(url, params=params or {}, timeout=30)

        if response.status_code == 401:
            raise CredentialError(
                "Confluence authentication failed",
                credential_type="Confluence"
            )
        elif response.status_code == 403:
            raise CredentialError(
                "Confluence access denied",
                credential_type="Confluence"
            )
        elif response.status_code != 200:
            raise NetworkError(
                f"Confluence API error: {response.status_code}",
                endpoint=url
            )

        return response.json()

    def test_connection(self) -> tuple:
        """Test connection to Confluence."""
        try:
            data = self._api_call("/user/current")
            display_name = data.get("displayName", "user")
            return True, f"Connected as {display_name}"
        except CredentialError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    def sync(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        incremental: bool = True
    ) -> SyncResult:
        """Sync Confluence data to brain.

        Args:
            progress_callback: Progress callback (current, total, phase)
            incremental: Only sync changes since last sync

        Returns:
            SyncResult with details
        """
        result = SyncResult(success=True, message="")
        progress = SyncProgress(callback=progress_callback)

        try:
            # Phase 1: Get spaces
            progress.phase = "Fetching spaces"
            spaces = self._fetch_spaces()

            if self.spaces:
                spaces = [s for s in spaces if s['key'] in self.spaces]

            progress.total = len(spaces) * 2  # spaces + pages

            # Phase 2: Sync spaces
            for space in spaces:
                progress.update(progress.current, f"Syncing space: {space['key']}")
                self._sync_space(space, result)
                progress.increment()

            # Phase 3: Sync pages for each space
            for space in spaces:
                progress.update(progress.current, f"Syncing pages: {space['key']}")
                last_sync = self.get_last_sync_time(f"confluence_pages_{space['key']}") if incremental else None
                self._sync_pages(space, last_sync, result)
                self.set_last_sync_time(f"confluence_pages_{space['key']}")
                progress.increment()

            # Build summary message
            total_entities = result.entities_created + result.entities_updated
            result.message = f"Synced {total_entities} entities from {len(spaces)} spaces"

        except CredentialError:
            raise
        except SyncError:
            raise
        except Exception as e:
            result.success = False
            result.message = f"Sync failed: {str(e)}"
            result.errors.append(str(e))

        return result

    def _fetch_spaces(self) -> List[Dict]:
        """Fetch accessible spaces."""
        try:
            data = self._api_call("/space", params={"limit": 50})
            return data.get("results", [])
        except Exception as e:
            raise SyncError(f"Failed to fetch spaces: {str(e)}", service="Confluence")

    def _sync_space(self, space: Dict, result: SyncResult):
        """Sync a single space entity."""
        key = space.get("key")
        name = space.get("name", key)

        body = f"""# {name}

## Overview

- **Key**: {key}
- **Type**: {space.get('type', 'global')}

## Description

{space.get('description', {}).get('plain', {}).get('value', 'No description')}

## Links

- [View in Confluence]({self.url}/wiki/spaces/{key})
"""

        self.write_entity(
            entity_type="project",  # Treat spaces as projects
            name=f"Confluence: {name}",
            source="confluence",
            body=body,
            sync_id=str(space.get("id")),
            confluence_key=key,
            space_type=space.get("type"),
            url=f"{self.url}/wiki/spaces/{key}"
        )

        result.entities_created += 1

    def _sync_pages(
        self,
        space: Dict,
        last_sync: Optional[str],
        result: SyncResult,
        max_pages: int = 50
    ):
        """Sync pages for a space."""
        space_key = space.get("key")

        # CQL query for pages
        cql = f"space = {space_key} AND type = page"
        if last_sync:
            cql += f" AND lastmodified > '{last_sync[:10]}'"
        cql += " ORDER BY lastmodified DESC"

        try:
            data = self._api_call(
                "/content/search",
                params={"cql": cql, "limit": max_pages, "expand": "ancestors,body.view"}
            )

            pages = data.get("results", [])

            for page in pages:
                self._sync_page(page, space_key, result)

        except Exception as e:
            result.errors.append(f"Error syncing pages for {space_key}: {str(e)}")

    def _sync_page(self, page: Dict, space_key: str, result: SyncResult):
        """Sync a single page entity."""
        page_id = page.get("id")
        title = page.get("title", "Untitled")

        # Get parent page
        ancestors = page.get("ancestors", [])
        parent_title = ancestors[-1].get("title") if ancestors else None

        # Build relationships
        relationships = {"space": [space_key]}
        if parent_title:
            relationships["parent"] = [parent_title]

        # Get a preview of the content
        body_content = page.get("body", {}).get("view", {}).get("value", "")
        preview = self._html_to_text(body_content)[:500]

        body = f"""# {title}

## Overview

- **Space**: {space_key}
- **Parent**: {parent_title or 'None (top-level)'}
- **Last Modified**: {page.get('history', {}).get('lastUpdated', {}).get('when', 'Unknown')[:10]}

## Preview

{preview}

## Links

- [View in Confluence]({self.url}/wiki/spaces/{space_key}/pages/{page_id})
"""

        self.write_entity(
            entity_type="document",
            name=title,
            source="confluence",
            body=body,
            sync_id=page_id,
            page_id=page_id,
            space=space_key,
            parent=parent_title,
            url=f"{self.url}/wiki/spaces/{space_key}/pages/{page_id}",
            relationships=relationships
        )

        result.entities_created += 1

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text."""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)
        # Decode entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
