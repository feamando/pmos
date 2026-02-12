#!/usr/bin/env python3
"""
Base Enricher Class

Abstract base class for all Brain entity enrichers.
"""

import re
import sys
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add parent directory for canonical_resolver import
sys.path.insert(0, str(Path(__file__).parent.parent))

from canonical_resolver import CanonicalResolver


class BaseEnricher(ABC):
    """
    Abstract base class for entity enrichers.

    Enrichers process raw data from various sources and update
    Brain entity files with extracted information.
    """

    def __init__(self, brain_path: Path):
        """
        Initialize the enricher.

        Args:
            brain_path: Path to the brain directory
        """
        self.brain_path = brain_path
        self.registry_path = brain_path / "registry.yaml"
        self._registry_cache: Optional[Dict] = None
        self._alias_index: Optional[Dict[str, str]] = None
        self._resolver: Optional[CanonicalResolver] = None

    def get_resolver(self) -> CanonicalResolver:
        """Get or create the canonical resolver."""
        if self._resolver is None:
            self._resolver = CanonicalResolver(self.brain_path)
            self._resolver.build_index()
        return self._resolver

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the data source (e.g., 'gdocs', 'slack')."""
        pass

    @abstractmethod
    def enrich(self, item: Dict[str, Any], dry_run: bool = False) -> int:
        """
        Enrich an entity from a source item.

        Args:
            item: Raw data item from the source
            dry_run: If True, don't write changes

        Returns:
            Number of fields updated
        """
        pass

    def get_registry(self) -> Dict[str, Any]:
        """Load and cache the registry."""
        if self._registry_cache is None:
            if self.registry_path.exists():
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    self._registry_cache = yaml.safe_load(f) or {}
            else:
                self._registry_cache = {}
        return self._registry_cache

    def get_alias_index(self) -> Dict[str, str]:
        """Build alias index from registry."""
        if self._alias_index is not None:
            return self._alias_index

        registry = self.get_registry()
        self._alias_index = {}

        # Check for v2 pre-built index
        if "alias_index" in registry:
            self._alias_index = registry["alias_index"]
            return self._alias_index

        # Build from v1 or v2 entities
        entities = registry.get("entities", registry)
        for slug, entry in entities.items():
            if isinstance(entry, dict):
                aliases = entry.get("aliases", entry.get("$aliases", []))
                for alias in aliases:
                    if alias:
                        self._alias_index[alias.lower()] = slug

        return self._alias_index

    def find_entity_by_mention(self, text: str) -> Optional[str]:
        """
        Find entity canonical ID from text mention.

        Uses CanonicalResolver for lookup.

        Args:
            text: Text that may contain entity mention

        Returns:
            Entity canonical $id if found, None otherwise
        """
        resolver = self.get_resolver()
        text_lower = text.lower()

        # Try to resolve the entire text first
        canonical = resolver.resolve(text)
        if canonical:
            return canonical

        # Fall back to alias index for partial matches
        alias_index = self.get_alias_index()
        for alias, slug in alias_index.items():
            if alias in text_lower:
                # Resolve slug to canonical
                canonical = resolver.resolve(slug)
                return canonical if canonical else slug

        return None

    def get_entity_path(self, slug_or_id: str) -> Optional[Path]:
        """
        Get file path for an entity by slug or canonical ID.

        Uses CanonicalResolver for lookup.

        Args:
            slug_or_id: Entity slug or canonical $id

        Returns:
            Path to entity file if found
        """
        resolver = self.get_resolver()

        # Try to resolve to canonical ID
        canonical = resolver.resolve(slug_or_id)
        if canonical:
            return resolver.get_entity_path(canonical)

        # Fall back to registry lookup
        registry = self.get_registry()
        entities = registry.get("entities", registry)
        entry = entities.get(slug_or_id)

        if entry:
            ref = entry.get("$ref", entry.get("file", ""))
            if ref:
                return self.brain_path / ref

        return None

    def normalize_relationship_target(self, target: str) -> str:
        """
        Normalize a relationship target to canonical $id format.

        Args:
            target: Original target reference

        Returns:
            Canonical $id or original target if not resolvable
        """
        resolver = self.get_resolver()
        canonical = resolver.resolve(target)
        return canonical if canonical else target

    def read_entity(self, entity_path: Path) -> tuple[Dict[str, Any], str]:
        """
        Read entity file and parse frontmatter.

        Args:
            entity_path: Path to entity file

        Returns:
            Tuple of (frontmatter dict, body text)
        """
        if not entity_path.exists():
            return {}, ""

        content = entity_path.read_text(encoding="utf-8")
        return self._parse_entity_content(content)

    def _parse_entity_content(self, content: str) -> tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter and body from content."""
        if not content.startswith("---"):
            return {}, content

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content

        try:
            frontmatter = yaml.safe_load(parts[1]) or {}
            body = parts[2]
            return frontmatter, body
        except yaml.YAMLError:
            return {}, content

    def write_entity(
        self,
        entity_path: Path,
        frontmatter: Dict[str, Any],
        body: str,
        dry_run: bool = False,
    ) -> bool:
        """
        Write entity file with updated frontmatter.

        Args:
            entity_path: Path to entity file
            frontmatter: Updated frontmatter dict
            body: Body text
            dry_run: If True, don't write

        Returns:
            True if written successfully
        """
        if dry_run:
            return True

        # Update metadata
        frontmatter["$updated"] = datetime.now(timezone.utc).isoformat()
        frontmatter["$version"] = frontmatter.get("$version", 0) + 1

        content = (
            "---\n"
            + yaml.dump(
                frontmatter,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
            + "---"
            + body
        )

        entity_path.write_text(content, encoding="utf-8")
        return True

    def append_event(
        self,
        frontmatter: Dict[str, Any],
        event_type: str,
        message: str,
        changes: Optional[List[Dict]] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Append an event to entity's $events log.

        Delegates to EventHelper for standardized event creation.
        Note: Does NOT increment $version/$updated here — write_entity() handles that.

        Args:
            frontmatter: Entity frontmatter dict
            event_type: Type of event (legacy types mapped to EventType values)
            message: Event message
            changes: List of field changes
            correlation_id: Optional correlation ID

        Returns:
            Updated frontmatter
        """
        from event_helpers import EventHelper

        # Map legacy enricher event types to valid EventType values
        type_mapping = {
            "enrichment": "field_update",
            "enriched": "field_update",
            "update": "field_update",
            "link": "relationship_add",
        }
        mapped_type = type_mapping.get(event_type, event_type)

        # Normalize changes: map "update" operation to "set"
        normalized_changes = []
        for change in (changes or []):
            nc = dict(change)
            if nc.get("operation") == "update":
                nc["operation"] = "set"
            normalized_changes.append(nc)

        event = EventHelper.create_event(
            event_type=mapped_type,
            actor=f"system/{self.source_name}_enricher",
            changes=normalized_changes,
            message=message,
            source=self.source_name,
            correlation_id=correlation_id,
        )

        # Append without version/timestamp increment (write_entity handles those)
        EventHelper.append_to_frontmatter(
            frontmatter, event, increment_version=False, update_timestamp=False
        )
        return frontmatter

    def extract_mentions(self, text: str) -> List[str]:
        """
        Extract entity mentions from text.

        Args:
            text: Text to scan

        Returns:
            List of entity slugs mentioned
        """
        mentions = []
        alias_index = self.get_alias_index()

        for alias, slug in alias_index.items():
            if len(alias) > 2:  # Skip very short aliases
                pattern = r"\b" + re.escape(alias) + r"\b"
                if re.search(pattern, text, re.IGNORECASE):
                    if slug not in mentions:
                        mentions.append(slug)

        return mentions

    def calculate_confidence(
        self,
        completeness: float,
        source_reliability: float = 0.7,
        freshness_days: int = 0,
    ) -> float:
        """
        Calculate confidence score for enriched data.

        Formula: completeness(40%) + source_reliability(40%) + freshness(20%)
        Freshness decays at 0.01 per week.

        Args:
            completeness: 0-1 score of data completeness
            source_reliability: 0-1 score of source reliability
            freshness_days: Days since data was generated

        Returns:
            Confidence score 0-1
        """
        freshness_decay = min(freshness_days / 7 * 0.01, 0.2)
        freshness_score = max(0, 1.0 - freshness_decay)

        return completeness * 0.4 + source_reliability * 0.4 + freshness_score * 0.2
