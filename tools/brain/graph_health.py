#!/usr/bin/env python3
"""
PM-OS Brain Graph Health Monitor

TKS-derived tool (bd-408c) for tracking graph density, relationship coverage,
and identifying isolated (orphan) entities.

Usage:
    python3 graph_health.py                    # Full health report
    python3 graph_health.py orphans            # List orphan entities
    python3 graph_health.py density            # Density metrics only
    python3 graph_health.py --output json      # JSON output
"""

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml


@dataclass
class GraphHealthReport:
    """Comprehensive graph health metrics."""

    # Entity counts
    total_entities: int = 0
    entities_with_relationships: int = 0
    entities_with_incoming: int = 0
    orphan_entities: int = 0

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

    # Healthy relationship targets by entity type
    HEALTHY_RELATIONSHIP_COUNT = {
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

    def __init__(self, brain_path: Path):
        """Initialize the health monitor."""
        self.brain_path = brain_path

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

        # Scan all entities
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
                frontmatter, _ = self._parse_content(content)

                if not frontmatter:
                    continue

                entity_id = frontmatter.get(
                    "$id", str(entity_path.relative_to(self.brain_path))
                )
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

            except Exception:
                continue

        # Compute metrics
        total_entities = len(entities)
        total_relationships = sum(len(rels) for rels in outgoing.values())

        entities_with_outgoing = sum(1 for rels in outgoing.values() if rels)
        entities_with_incoming = len(
            [e for e in entities if e in incoming and incoming[e]]
        )

        # Orphans: no outgoing AND no incoming
        all_targets = set()
        for targets in outgoing.values():
            all_targets.update(targets)

        orphans = [
            eid for eid in entities if not outgoing.get(eid) and eid not in all_targets
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
                                "path": str(entity_path.relative_to(self.brain_path)),
                            }
                        )
                        break
                except Exception:
                    continue

        return orphan_details

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


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Monitor Brain graph health and density"
    )
    parser.add_argument(
        "action",
        choices=["report", "orphans", "density", "connected"],
        nargs="?",
        default="report",
        help="Action to perform",
    )
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )

    args = parser.parse_args()

    # Resolve brain path
    if not args.brain_path:
        script_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(script_dir))
        try:
            from path_resolver import get_paths

            paths = get_paths()
            args.brain_path = paths.user / "brain"
        except ImportError:
            args.brain_path = Path.cwd() / "user" / "brain"

    monitor = GraphHealthMonitor(args.brain_path)
    report = monitor.analyze()

    if args.output == "json":
        output = {
            "total_entities": report.total_entities,
            "entities_with_relationships": report.entities_with_relationships,
            "orphan_entities": report.orphan_entities,
            "total_relationships": report.total_relationships,
            "relationship_coverage": report.relationship_coverage,
            "avg_relationships_per_entity": report.avg_relationships_per_entity,
            "density_score": report.density_score,
            "entities_by_type": report.entities_by_type,
            "relationships_by_type": report.relationships_by_type,
            "orphans": report.orphans[:20],
            "most_connected": report.most_connected,
            "inferred_edge_count": report.inferred_edge_count,
        }
        print(json.dumps(output, indent=2))
        return 0

    # Text output
    if args.action == "report":
        print("Brain Graph Health Report")
        print("=" * 60)
        print(f"Generated: {date.today().isoformat()}")
        print()

        print("Entity Summary:")
        print(f"  Total entities: {report.total_entities}")
        print(f"  With relationships: {report.entities_with_relationships}")
        print(f"  Orphans (isolated): {report.orphan_entities}")
        print()

        print("Relationship Summary:")
        print(f"  Total relationships: {report.total_relationships}")
        print(f"  Unique types: {report.unique_relationship_types}")
        print(f"  Inferred edges: {report.inferred_edge_count}")
        print()

        print("Density Metrics:")
        print(
            f"  Coverage: {report.relationship_coverage*100:.1f}% of entities have relationships"
        )
        print(f"  Avg per entity: {report.avg_relationships_per_entity:.2f}")
        print(f"  Density score: {report.density_score:.3f} (1.0 = healthy)")
        print()

        if report.entities_by_type:
            print("Entities by type:")
            for etype, count in sorted(
                report.entities_by_type.items(), key=lambda x: -x[1]
            ):
                avg = report.avg_relationships_by_entity_type.get(etype, 0)
                print(f"  {etype}: {count} (avg {avg:.1f} rels)")
        print()

        if report.relationships_by_type:
            print("Relationships by type:")
            for rtype, count in sorted(
                report.relationships_by_type.items(), key=lambda x: -x[1]
            )[:10]:
                print(f"  {rtype}: {count}")

    elif args.action == "orphans":
        orphan_details = monitor.get_orphans()
        print(f"Orphan Entities ({len(orphan_details)} total)")
        print("=" * 60)
        print("Entities with no relationships (not connected to graph):")
        print()
        for orphan in orphan_details[:30]:
            print(f"  [{orphan['type']:10}] {orphan['id']}")
            if orphan["name"]:
                print(f"              Name: {orphan['name']}")
        if len(orphan_details) > 30:
            print(f"  ... and {len(orphan_details) - 30} more")

    elif args.action == "density":
        print("Graph Density Metrics")
        print("=" * 40)
        print(f"Coverage: {report.relationship_coverage*100:.1f}%")
        print(f"Avg relationships: {report.avg_relationships_per_entity:.2f}")
        print(f"Density score: {report.density_score:.3f}")
        print()
        print("Target: 3+ relationships per entity for healthy density")
        if report.density_score < 0.5:
            print("Status: LOW - Consider running soft edge inference")
        elif report.density_score < 0.8:
            print("Status: MODERATE - Graph could be denser")
        else:
            print("Status: HEALTHY - Good relationship coverage")

    elif args.action == "connected":
        print("Most Connected Entities")
        print("=" * 50)
        for entity_id, count in report.most_connected:
            print(f"  {count:3d} connections | {entity_id}")
        print()
        print("Least Connected (with some relationships):")
        for entity_id, count in report.least_connected:
            print(f"  {count:3d} connections | {entity_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
