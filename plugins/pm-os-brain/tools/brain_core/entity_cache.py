#!/usr/bin/env python3
"""
Shared Entity Cache -- single scan, multiple consumers.

Loads and parses all Brain entity .md files once. Provides typed
access (get_all, get_by_type, get_by_id) and content hashing
for incremental enrichment.

Usage:
    from pm_os_brain.tools.brain_core.entity_cache import EntityCache

    cache = EntityCache(brain_path)
    cache.load()
    persons = cache.get_by_type("person")
    entity = cache.get_by_id("entity/person/person-01")
"""

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import yaml
except ImportError:
    logger.error("PyYAML required. Install with: pip install pyyaml")
    raise

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


class EntityCache:
    """In-memory cache for all Brain entities.

    Not a singleton -- each enrichment run creates its own instance.
    Provides O(1) access by ID and O(1) access by type after the
    initial O(n) scan.
    """

    def __init__(self, brain_path: Path):
        self.brain_path = brain_path
        self._entities: Dict[str, Dict[str, Any]] = {}  # id -> frontmatter+meta
        self._by_type: Dict[str, List[str]] = {}  # type -> [ids]
        self._loaded = False
        self._entity_count = 0
        self._scan_ms = 0.0

    def load(self) -> "EntityCache":
        """Scan brain directory and load all entities into memory.

        Returns self for chaining: cache = EntityCache(path).load()
        """
        import time

        t0 = time.perf_counter()

        self._entities.clear()
        self._by_type.clear()

        entity_files = list(self.brain_path.rglob("*.md"))
        entity_files = [
            f
            for f in entity_files
            if f.name.lower() not in ("readme.md", "index.md", "_index.md")
            and ".snapshots" not in str(f)
            and ".schema" not in str(f)
        ]

        by_type: Dict[str, List[str]] = {}

        for entity_path in entity_files:
            try:
                content = entity_path.read_text(encoding="utf-8")
                frontmatter, body = self._parse_content(content)

                if not frontmatter:
                    continue

                entity_id = frontmatter.get(
                    "$id", str(entity_path.relative_to(self.brain_path))
                )
                entity_type = frontmatter.get("$type", "unknown")

                # Attach metadata for consumers
                frontmatter["_body"] = body
                frontmatter["_path"] = entity_path
                frontmatter["_content_hash"] = self._content_hash(content)

                self._entities[entity_id] = frontmatter

                if entity_type not in by_type:
                    by_type[entity_type] = []
                by_type[entity_type].append(entity_id)

            except Exception:
                continue

        self._by_type = by_type
        self._entity_count = len(self._entities)
        self._loaded = True
        self._scan_ms = (time.perf_counter() - t0) * 1000

        logger.debug(
            "EntityCache loaded %d entities in %.1fms",
            self._entity_count,
            self._scan_ms,
        )

        return self

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Return all entities as {id: frontmatter}."""
        self._ensure_loaded()
        return self._entities

    def get_by_type(self, entity_type: str) -> Dict[str, Dict[str, Any]]:
        """Return entities of a specific type as {id: frontmatter}."""
        self._ensure_loaded()
        ids = self._by_type.get(entity_type, [])
        return {eid: self._entities[eid] for eid in ids}

    def get_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Return a single entity by ID, or None."""
        self._ensure_loaded()
        return self._entities.get(entity_id)

    def get_types(self) -> List[str]:
        """Return list of all entity types present."""
        self._ensure_loaded()
        return list(self._by_type.keys())

    def invalidate(self, entity_id: str) -> None:
        """Reload a single entity from disk (after modification)."""
        self._ensure_loaded()
        entity = self._entities.get(entity_id)
        if entity is None:
            return

        entity_path = entity.get("_path")
        if entity_path is None or not entity_path.exists():
            return

        try:
            content = entity_path.read_text(encoding="utf-8")
            frontmatter, body = self._parse_content(content)
            if frontmatter:
                frontmatter["_body"] = body
                frontmatter["_path"] = entity_path
                frontmatter["_content_hash"] = self._content_hash(content)
                self._entities[entity_id] = frontmatter
        except Exception:
            pass

    def reload(self) -> "EntityCache":
        """Full reload from disk."""
        return self.load()

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        self._ensure_loaded()
        return {
            "entity_count": self._entity_count,
            "type_count": len(self._by_type),
            "types": {t: len(ids) for t, ids in self._by_type.items()},
            "scan_ms": round(self._scan_ms, 2),
        }

    @property
    def entity_count(self) -> int:
        """Number of loaded entities."""
        self._ensure_loaded()
        return self._entity_count

    @property
    def scan_ms(self) -> float:
        """Time taken for the last scan in milliseconds."""
        return self._scan_ms

    def _ensure_loaded(self) -> None:
        """Auto-load on first access if not yet loaded."""
        if not self._loaded:
            self.load()

    @staticmethod
    def _content_hash(content: str) -> str:
        """SHA-256 hash of file content for change detection."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _parse_content(content: str) -> Tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter from content."""
        if not content.startswith("---"):
            return {}, content

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content

        try:
            frontmatter = yaml.safe_load(parts[1]) or {}
            return frontmatter, parts[2]
        except yaml.YAMLError:
            return {}, content
