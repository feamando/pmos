#!/usr/bin/env python3
"""
PM-OS Brain Graph Health Monitor (v5)

TKS-derived tool for tracking graph density, relationship coverage,
and identifying isolated (orphan) entities.

Provides metrics for:
- Relationship coverage (% entities with edges)
- Graph density (avg edges per node)
- Orphan detection (entities with no connections)
- Type-specific metrics
- Inferred edge tracking

Version: 5.0.0
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

# v5 config-driven imports
try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        from tools.core.path_resolver import get_paths
    except ImportError:
        get_paths = None

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from tools.core.config_loader import get_config
    except ImportError:
        get_config = None

logger = logging.getLogger(__name__)


@dataclass
class GraphHealthReport:
    """Comprehensive graph health metrics."""

    # Entity counts
    total_entities: int = 0
    entities_with_relationships: int = 0
    entities_with_incoming: int = 0
    orphan_entities: int = 0  # Excludes entities marked as standalone

    # Relationship counts
    total_relationships: int = 0
    unique_relationship_types: int = 0
    bidirectional_relationships: int = 0

    # Density metrics
    relationship_coverage: float = 0.0  # % entities with relationships
    avg_relationships_per_entity: float = 0.0
    density_score: float = 0.0  # 0-1 health score

    # By-type breakdown
    entities_by_type: Dict[str, int] = field(default_factory=dict)
    relationships_by_type: Dict[str, int] = field(default_factory=dict)
    avg_relationships_by_entity_type: Dict[str, float] = field(default_factory=dict)

    # Lists
    orphans: List[str] = field(default_factory=list)
    most_connected: List[Tuple[str, int]] = field(default_factory=list)
    least_connected: List[Tuple[str, int]] = field(default_factory=list)

    # Inferred edges (if present)
    inferred_edge_count: int = 0
    inferred_edge_sources: Dict[str, int] = field(default_factory=dict)


class GraphHealthMonitor:
    """
    Monitors Brain graph health including density, orphans, and connectivity.

    Provides metrics for:
    - Relationship coverage (% entities with edges)
    - Graph density (avg edges per node)
    - Orphan detection (entities with no connections)
    - Type-specific metrics
    """

    # Default healthy relationship targets by entity type (config-overridable)
    DEFAULT_HEALTHY_RELATIONSHIP_COUNT = {
        "person": 3,  # manager, team, at least one project
        "team": 4,  # owner, members, related teams
        "squad": 5,  # owner, members, tribe, tech systems
        "project": 3,  # owner, team, related projects
        "domain": 2,  # owner, systems
        "experiment": 2,  # owner, project
        "system": 3,  # owner, dependencies
        "brand": 2,  # owner, market
        "default": 2,
    }

    def __init__(self, brain_path: Path, cache=None):
        """Initialize the health monitor.

        Args:
            brain_path: Path to brain directory
            cache: Optional EntityCache instance. If provided, avoids
                   re-scanning the filesystem.
        """
        self.brain_path = brain_path
        self._cache = cache

        # Load config-driven values
        self.healthy_relationship_count = dict(self.DEFAULT_HEALTHY_RELATIONSHIP_COUNT)
        if get_config is not None:
            try:
                config = get_config()
                brain_cfg = config.get("brain", {})
                if "healthy_relationship_count" in brain_cfg:
                    self.healthy_relationship_count.update(
                        brain_cfg["healthy_relationship_count"]
                    )
            except Exception:
                logger.debug("Config not available, using default relationship counts")

    def analyze(self) -> GraphHealthReport:
        """
        Perform full graph health analysis.

        Returns:
            GraphHealthReport with all metrics
        """
        # Data structures
        entities: Dict[str, Dict[str, Any]] = {}  # id -> frontmatter
        outgoing: Dict[str, List[str]] = defaultdict(list)  # id -> [targets]
        incoming: Dict[str, List[str]] = defaultdict(list)  # id -> [sources]
        relationship_types: Dict[str, int] = defaultdict(int)
        entity_types: Dict[str, int] = defaultdict(int)
        relationships_by_entity_type: Dict[str, List[int]] = defaultdict(list)
        inferred_sources: Dict[str, int] = defaultdict(int)

        # Load entities -- from cache if available, otherwise scan files
        if self._cache is not None:
            cached = self._cache.get_all()
        else:
            cached = self._scan_entities()

        for entity_id, frontmatter in cached.items():
            entity_type = frontmatter.get("$type", "unknown")
            relationships = frontmatter.get("$relationships", [])

            entities[entity_id] = frontmatter
            entity_types[entity_type] += 1

            rel_count = 0
            for rel in relationships:
                if not isinstance(rel, dict):
                    continue

                rel_type = rel.get("type", "unknown")
                target = rel.get("target", "")
                source = rel.get("source", "manual")

                relationship_types[rel_type] += 1
                outgoing[entity_id].append(target)
                incoming[target].append(entity_id)
                rel_count += 1

                # Track inferred edges
                if source in ("auto_embedding", "auto_generated", "inferred"):
                    inferred_sources[source] += 1

            relationships_by_entity_type[entity_type].append(rel_count)

        # Compute metrics
        total_entities = len(entities)
        total_relationships = sum(len(rels) for rels in outgoing.values())

        entities_with_outgoing = sum(1 for rels in outgoing.values() if rels)
        entities_with_incoming = len(
            [e for e in entities if e in incoming and incoming[e]]
        )

        # Orphans: no outgoing AND no incoming
        # An entity is an orphan if it has:
        #   1. No outgoing relationships (not in outgoing dict)
        #   2. No incoming relationships (not referenced by others)
        #   3. Not marked as standalone (legitimately independent)
        all_targets = set()
        for targets in outgoing.values():
            all_targets.update(targets)

        orphans = [
            eid
            for eid in entities
            if not outgoing.get(eid)
            and eid not in all_targets
            and entities[eid].get("$orphan_reason") != "standalone"
        ]

        # Connectivity ranking
        connectivity = [
            (eid, len(outgoing.get(eid, [])) + len(incoming.get(eid, [])))
            for eid in entities
        ]
        connectivity.sort(key=lambda x: -x[1])

        # Avg relationships by entity type
        avg_by_type = {}
        for etype, counts in relationships_by_entity_type.items():
            avg_by_type[etype] = round(sum(counts) / len(counts), 2) if counts else 0

        # Density score: combination of coverage and avg relationships
        coverage = entities_with_outgoing / total_entities if total_entities else 0
        avg_rels = total_relationships / total_entities if total_entities else 0
        # Target: 3 relationships per entity = 1.0 density
        density_score = min(1.0, (coverage * 0.4) + (min(avg_rels / 3, 1.0) * 0.6))

        return GraphHealthReport(
            total_entities=total_entities,
            entities_with_relationships=entities_with_outgoing,
            entities_with_incoming=entities_with_incoming,
            orphan_entities=len(orphans),
            total_relationships=total_relationships,
            unique_relationship_types=len(relationship_types),
            bidirectional_relationships=0,  # Would need more analysis
            relationship_coverage=round(coverage, 3),
            avg_relationships_per_entity=round(avg_rels, 2),
            density_score=round(density_score, 3),
            entities_by_type=dict(entity_types),
            relationships_by_type=dict(relationship_types),
            avg_relationships_by_entity_type=avg_by_type,
            orphans=sorted(orphans)[:50],  # Limit to 50
            most_connected=connectivity[:10],
            least_connected=[c for c in connectivity[-10:] if c[1] > 0],
            inferred_edge_count=sum(inferred_sources.values()),
            inferred_edge_sources=dict(inferred_sources),
        )

    def get_orphans(self) -> List[Dict[str, Any]]:
        """
        Get detailed info about orphan entities.

        Returns:
            List of orphan entity details
        """
        report = self.analyze()
        orphan_details = []

        for orphan_id in report.orphans:
            # Find the entity file
            for entity_path in self.brain_path.rglob("*.md"):
                try:
                    content = entity_path.read_text(encoding="utf-8")
                    frontmatter, _ = self._parse_content(content)

                    if frontmatter.get("$id") == orphan_id:
                        orphan_details.append(
                            {
                                "id": orphan_id,
                                "type": frontmatter.get("$type", "unknown"),
                                "name": frontmatter.get("name", ""),
                                "status": frontmatter.get("$status", "unknown"),
                                "path": str(
                                    entity_path.relative_to(self.brain_path)
                                ),
                            }
                        )
                        break
                except Exception:
                    continue

        return orphan_details

    def _scan_entities(self) -> Dict[str, Dict[str, Any]]:
        """Fallback: scan brain directory when no cache is available."""
        result = {}
        entity_files = list(self.brain_path.rglob("*.md"))
        entity_files = [
            f
            for f in entity_files
            if f.name.lower() not in ("readme.md", "index.md", "_index.md")
            and ".snapshots" not in str(f)
            and ".schema" not in str(f)
        ]
        for entity_path in entity_files:
            try:
                content = entity_path.read_text(encoding="utf-8")
                frontmatter, body = self._parse_content(content)
                if not frontmatter:
                    continue
                entity_id = frontmatter.get(
                    "$id", str(entity_path.relative_to(self.brain_path))
                )
                frontmatter["_path"] = entity_path
                frontmatter["_body"] = body
                result[entity_id] = frontmatter
            except Exception:
                continue
        return result

    def _parse_content(self, content: str) -> Tuple[Dict[str, Any], str]:
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
