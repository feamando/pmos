"""
PM-OS CCE FigmaClient (v5.0)

Figma REST API client for design file analysis. Fetches file summaries,
component instances, and screen/frame lists. Cross-references found
components with ZestLoader to identify design system coverage.

Auth: Uses connector_bridge (get_connector_client) for token management.
Cache: 1-hour in-memory response cache to avoid repeated API calls.

Usage:
    from pm_os_cce.tools.design.figma_client import FigmaClient
"""

import json
import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from pm_os_base.tools.core.connector_bridge import get_connector_client
except ImportError:
    try:
        from core.connector_bridge import get_connector_client
    except ImportError:
        get_connector_client = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Cache TTL: 1 hour
_CACHE_TTL = 3600

# Figma API base
_FIGMA_API = "https://api.figma.com/v1"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class FigmaFileSummary:
    """Summary of a Figma design file."""

    file_key: str
    name: str = ""
    last_modified: str = ""
    version: str = ""
    pages: List[str] = field(default_factory=list)
    total_frames: int = 0
    total_components: int = 0
    thumbnail_url: str = ""


@dataclass
class FigmaComponentInstance:
    """A component instance found in a Figma file."""

    name: str
    node_id: str = ""
    component_id: str = ""
    page: str = ""
    containing_frame: str = ""
    zest_match: Optional[str] = None  # Matched Zest component name


@dataclass
class FigmaScreen:
    """A top-level frame (screen) in a Figma file."""

    name: str
    node_id: str = ""
    page: str = ""
    width: float = 0
    height: float = 0
    child_count: int = 0


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class FigmaClient:
    """
    REST client for the Figma API.

    Authenticates via connector_bridge (get_connector_client) which manages
    token retrieval from config, env vars, or credential stores.
    Caches responses in memory for 1 hour.

    Usage::

        client = FigmaClient()
        if client.is_authenticated():
            summary = client.get_file_summary("file_key_here")
    """

    def __init__(self, token: Optional[str] = None) -> None:
        """
        Initialize the Figma client.

        Args:
            token: Figma personal access token. If None, uses
                get_connector_client("figma") to obtain credentials.
        """
        self._token = token or self._load_token()
        self._cache: Dict[str, Tuple[float, Any]] = {}

    @staticmethod
    def _load_token() -> str:
        """Load Figma token via connector_bridge."""
        if get_connector_client is not None:
            try:
                client = get_connector_client("figma")
                if client and hasattr(client, "token"):
                    return client.token or ""
                if client and hasattr(client, "get_token"):
                    return client.get_token() or ""
            except Exception:
                pass

        # Fallback: check environment variable
        import os
        return os.environ.get("FIGMA_ACCESS_TOKEN", "")

    def is_authenticated(self) -> bool:
        """Check if a Figma token is available."""
        return bool(self._token)

    def test_auth(self) -> bool:
        """Test if the token is valid by hitting the /me endpoint."""
        if not self._token:
            return False
        try:
            data = self._api_get("/me")
            return bool(data and data.get("id"))
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_file_summary(self, file_key: str) -> FigmaFileSummary:
        """
        Get a summary of a Figma file.

        Args:
            file_key: The Figma file key (from URL: figma.com/file/<key>/...).

        Returns:
            FigmaFileSummary with pages, component/frame counts.
        """
        cache_key = f"file_summary:{file_key}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        data = self._api_get(f"/files/{file_key}?depth=2")
        if not data:
            return FigmaFileSummary(file_key=file_key)

        summary = FigmaFileSummary(
            file_key=file_key,
            name=data.get("name", ""),
            last_modified=data.get("lastModified", ""),
            version=data.get("version", ""),
            thumbnail_url=data.get("thumbnailUrl", ""),
        )

        # Extract pages and count frames
        document = data.get("document", {})
        for page_node in document.get("children", []):
            if page_node.get("type") == "CANVAS":
                summary.pages.append(page_node.get("name", ""))
                for child in page_node.get("children", []):
                    if child.get("type") == "FRAME":
                        summary.total_frames += 1
                    if child.get("type") == "COMPONENT":
                        summary.total_components += 1

        # Also count components from the components map
        components_map = data.get("components", {})
        if components_map:
            summary.total_components = max(
                summary.total_components, len(components_map)
            )

        self._set_cached(cache_key, summary)
        return summary

    def get_component_instances(
        self,
        file_key: str,
        zest_loader=None,
    ) -> List[FigmaComponentInstance]:
        """
        Get component instances used in a Figma file.

        Cross-references with ZestLoader when provided to identify
        which Figma components map to Zest design system components.

        Args:
            file_key: Figma file key.
            zest_loader: Optional ZestLoader for cross-referencing.

        Returns:
            List of FigmaComponentInstance with optional zest_match.
        """
        cache_key = f"components:{file_key}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            if zest_loader:
                for inst in cached:
                    inst.zest_match = self._match_to_zest(inst.name, zest_loader)
            return cached

        data = self._api_get(f"/files/{file_key}?depth=2")
        if not data:
            return []

        instances: List[FigmaComponentInstance] = []
        seen_names: Set[str] = set()
        components_map = data.get("components", {})

        document = data.get("document", {})
        for page_node in document.get("children", []):
            if page_node.get("type") != "CANVAS":
                continue
            page_name = page_node.get("name", "")
            self._find_instances_recursive(
                page_node, page_name, "", components_map,
                instances, seen_names,
            )

        if zest_loader:
            for inst in instances:
                inst.zest_match = self._match_to_zest(inst.name, zest_loader)

        self._set_cached(cache_key, instances)
        return instances

    def get_screen_list(
        self,
        file_key: str,
        page_name: Optional[str] = None,
    ) -> List[FigmaScreen]:
        """
        Get top-level frames (screens) from a Figma file.

        Args:
            file_key: Figma file key.
            page_name: Optional page name to filter by.

        Returns:
            List of FigmaScreen objects.
        """
        cache_key = f"screens:{file_key}:{page_name or 'all'}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        data = self._api_get(f"/files/{file_key}?depth=2")
        if not data:
            return []

        screens: List[FigmaScreen] = []
        document = data.get("document", {})

        for page_node in document.get("children", []):
            if page_node.get("type") != "CANVAS":
                continue
            pname = page_node.get("name", "")
            if page_name and pname.lower() != page_name.lower():
                continue

            for child in page_node.get("children", []):
                if child.get("type") == "FRAME":
                    abs_box = child.get("absoluteBoundingBox", {})
                    screens.append(FigmaScreen(
                        name=child.get("name", ""),
                        node_id=child.get("id", ""),
                        page=pname,
                        width=abs_box.get("width", 0),
                        height=abs_box.get("height", 0),
                        child_count=len(child.get("children", [])),
                    ))

        self._set_cached(cache_key, screens)
        return screens

    # ------------------------------------------------------------------
    # Helpers: Figma file key extraction
    # ------------------------------------------------------------------

    @staticmethod
    def extract_file_key(figma_url: str) -> Optional[str]:
        """
        Extract the file key from a Figma URL.

        Supports formats:
        - https://www.figma.com/file/<key>/...
        - https://www.figma.com/design/<key>/...
        - https://figma.com/file/<key>/...

        Returns:
            File key string, or None if URL doesn't match.
        """
        match = re.search(
            r"figma\.com/(?:file|design|proto)/([a-zA-Z0-9]+)",
            figma_url,
        )
        return match.group(1) if match else None

    # ------------------------------------------------------------------
    # Internal: API calls
    # ------------------------------------------------------------------

    def _api_get(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """
        Make a GET request to the Figma API using curl.

        Args:
            endpoint: API endpoint path (e.g., "/files/<key>").

        Returns:
            Parsed JSON response, or None on failure.
        """
        if not self._token:
            logger.warning("No Figma access token — skipping API call")
            return None

        url = f"{_FIGMA_API}{endpoint}"
        try:
            result = subprocess.run(
                [
                    "curl", "-s", "-f",
                    "-H", f"X-Figma-Token: {self._token}",
                    url,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.warning(
                    "Figma API %s failed (rc=%d): %s",
                    endpoint, result.returncode, result.stderr[:200],
                )
                return None

            return json.loads(result.stdout)
        except subprocess.TimeoutExpired:
            logger.warning("Figma API timeout for %s", endpoint)
            return None
        except json.JSONDecodeError as e:
            logger.warning("Figma API invalid JSON for %s: %s", endpoint, e)
            return None
        except Exception as e:
            logger.warning("Figma API error for %s: %s", endpoint, e)
            return None

    # ------------------------------------------------------------------
    # Internal: tree walking
    # ------------------------------------------------------------------

    def _find_instances_recursive(
        self,
        node: Dict[str, Any],
        page_name: str,
        parent_frame: str,
        components_map: Dict[str, Any],
        out: List[FigmaComponentInstance],
        seen: Set[str],
    ) -> None:
        """Recursively walk the Figma node tree to find component instances."""
        node_type = node.get("type", "")
        node_name = node.get("name", "")

        current_frame = parent_frame
        if node_type == "FRAME" and not parent_frame:
            current_frame = node_name

        if node_type == "INSTANCE":
            comp_id = node.get("componentId", "")
            comp_info = components_map.get(comp_id, {})
            comp_name = comp_info.get("name", node_name)

            if comp_name not in seen:
                seen.add(comp_name)
                out.append(FigmaComponentInstance(
                    name=comp_name,
                    node_id=node.get("id", ""),
                    component_id=comp_id,
                    page=page_name,
                    containing_frame=current_frame,
                ))

        for child in node.get("children", []):
            self._find_instances_recursive(
                child, page_name, current_frame,
                components_map, out, seen,
            )

    @staticmethod
    def _match_to_zest(figma_name: str, zest_loader) -> Optional[str]:
        """
        Try to match a Figma component name to a Zest component.

        Uses ZestLoader.find_component_by_figma_name() for exact matching,
        then falls back to case-insensitive name comparison.
        """
        try:
            match = zest_loader.find_component_by_figma_name(figma_name)
            if match:
                return match.name
        except Exception:
            pass

        try:
            all_comps = zest_loader.load_components()
            figma_lower = figma_name.lower().replace(" ", "").replace("-", "")
            for comp_name, comp in all_comps.items():
                if comp_name.lower().replace(" ", "").replace("-", "") == figma_lower:
                    return comp_name
        except Exception:
            pass

        return None

    # ------------------------------------------------------------------
    # Internal: caching
    # ------------------------------------------------------------------

    def _get_cached(self, key: str) -> Any:
        """Get a cached value if it exists and hasn't expired."""
        if key in self._cache:
            ts, value = self._cache[key]
            if time.time() - ts < _CACHE_TTL:
                return value
            del self._cache[key]
        return None

    def _set_cached(self, key: str, value: Any) -> None:
        """Store a value in the cache with current timestamp."""
        self._cache[key] = (time.time(), value)
