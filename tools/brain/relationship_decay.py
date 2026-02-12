#!/usr/bin/env python3
"""
PM-OS Brain Relationship Decay Monitor

TKS-derived tool (bd-2ac6) for tracking relationship staleness and confidence decay.
Identifies relationships that need re-verification.

Usage:
    python3 relationship_decay.py scan              # Scan all relationships
    python3 relationship_decay.py stale             # Show only stale relationships
    python3 relationship_decay.py report            # Full staleness report
    python3 relationship_decay.py --threshold 60    # Custom staleness threshold (days)
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


@dataclass
class StaleRelationship:
    """A relationship flagged as stale."""

    entity_id: str
    entity_type: str
    relationship_type: str
    target: str
    base_confidence: float
    decayed_confidence: float
    last_verified: Optional[date]
    days_stale: int
    source: Optional[str] = None


@dataclass
class RelationshipDecayReport:
    """Summary report of relationship staleness."""

    total_entities: int
    total_relationships: int
    stale_relationships: int
    avg_confidence: float
    avg_decayed_confidence: float
    stale_by_type: Dict[str, int] = field(default_factory=dict)
    stale_list: List[StaleRelationship] = field(default_factory=list)


class RelationshipDecayMonitor:
    """
    Monitors relationship staleness and confidence decay.

    Based on TKS temporal decay formula:
    conf(t) = max(floor, base × (1 - decay_rate × weeks_stale))
    """

    # Default staleness thresholds by relationship type (days)
    STALENESS_THRESHOLDS = {
        "reports_to": 90,  # Org structure - relatively stable
        "manages": 90,
        "member_of": 60,  # Team membership changes more often
        "owns": 60,
        "works_with": 45,  # Collaboration relationships
        "collaborates_with": 45,
        "depends_on": 30,  # Technical dependencies
        "blocks": 14,  # Should be resolved quickly
        "related_to": 90,
        "similar_to": 120,  # Inferred relationships - more stable
        "default": 90,
    }

    def __init__(
        self,
        brain_path: Path,
        decay_rate: float = 0.01,
        confidence_floor: float = 0.3,
    ):
        """
        Initialize the decay monitor.

        Args:
            brain_path: Path to brain directory
            decay_rate: Weekly decay rate (default: 1%)
            confidence_floor: Minimum confidence (default: 0.3)
        """
        self.brain_path = brain_path
        self.decay_rate = decay_rate
        self.confidence_floor = confidence_floor

    def scan_relationships(
        self,
        as_of: Optional[date] = None,
        threshold_days: Optional[int] = None,
    ) -> RelationshipDecayReport:
        """
        Scan all entities for relationship staleness.

        Args:
            as_of: Date to check against (default: today)
            threshold_days: Override default threshold

        Returns:
            RelationshipDecayReport with findings
        """
        check_date = as_of or date.today()

        total_entities = 0
        total_relationships = 0
        stale_relationships = []
        confidence_sum = 0.0
        decayed_sum = 0.0
        stale_by_type: Dict[str, int] = {}

        # Find all entity files
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

                total_entities += 1
                entity_id = frontmatter.get(
                    "$id", str(entity_path.relative_to(self.brain_path))
                )
                entity_type = frontmatter.get("$type", "unknown")
                relationships = frontmatter.get("$relationships", [])

                for rel in relationships:
                    if not isinstance(rel, dict):
                        continue

                    total_relationships += 1

                    rel_type = rel.get("type", "unknown")
                    target = rel.get("target", "unknown")
                    base_confidence = rel.get("confidence", 1.0)
                    last_verified = self._parse_date(rel.get("last_verified"))
                    since = self._parse_date(rel.get("since"))
                    source = rel.get("source")

                    # Compute decayed confidence
                    decayed = self._compute_decay(
                        base_confidence,
                        last_verified or since,
                        check_date,
                    )

                    confidence_sum += base_confidence
                    decayed_sum += decayed

                    # Check if stale
                    threshold = threshold_days or self.STALENESS_THRESHOLDS.get(
                        rel_type, self.STALENESS_THRESHOLDS["default"]
                    )

                    ref_date = last_verified or since
                    days_stale = (check_date - ref_date).days if ref_date else 999

                    if days_stale > threshold:
                        stale_rel = StaleRelationship(
                            entity_id=entity_id,
                            entity_type=entity_type,
                            relationship_type=rel_type,
                            target=target,
                            base_confidence=base_confidence,
                            decayed_confidence=round(decayed, 3),
                            last_verified=last_verified,
                            days_stale=days_stale,
                            source=source,
                        )
                        stale_relationships.append(stale_rel)
                        stale_by_type[rel_type] = stale_by_type.get(rel_type, 0) + 1

            except Exception:
                continue

        return RelationshipDecayReport(
            total_entities=total_entities,
            total_relationships=total_relationships,
            stale_relationships=len(stale_relationships),
            avg_confidence=(
                round(confidence_sum / total_relationships, 3)
                if total_relationships
                else 0
            ),
            avg_decayed_confidence=(
                round(decayed_sum / total_relationships, 3)
                if total_relationships
                else 0
            ),
            stale_by_type=stale_by_type,
            stale_list=sorted(stale_relationships, key=lambda x: -x.days_stale),
        )

    def _compute_decay(
        self,
        base_confidence: float,
        reference_date: Optional[date],
        as_of: date,
    ) -> float:
        """Compute decayed confidence."""
        if not reference_date:
            return max(self.confidence_floor, base_confidence * 0.7)

        days_stale = (as_of - reference_date).days
        if days_stale <= 0:
            return base_confidence

        weeks_stale = days_stale / 7
        decay = self.decay_rate * weeks_stale
        decayed = base_confidence * (1 - decay)

        return max(self.confidence_floor, min(base_confidence, decayed))

    def _parse_date(self, value: Any) -> Optional[date]:
        """Parse date from various formats."""
        if not value:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None
        return None

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
        description="Monitor relationship staleness and confidence decay"
    )
    parser.add_argument(
        "action",
        choices=["scan", "stale", "report"],
        nargs="?",
        default="scan",
        help="Action to perform",
    )
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        help="Override staleness threshold (days)",
    )
    parser.add_argument(
        "--decay-rate",
        type=float,
        default=0.01,
        help="Weekly decay rate (default: 0.01)",
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

    monitor = RelationshipDecayMonitor(
        args.brain_path,
        decay_rate=args.decay_rate,
    )

    report = monitor.scan_relationships(threshold_days=args.threshold)

    if args.output == "json":
        output = {
            "total_entities": report.total_entities,
            "total_relationships": report.total_relationships,
            "stale_relationships": report.stale_relationships,
            "avg_confidence": report.avg_confidence,
            "avg_decayed_confidence": report.avg_decayed_confidence,
            "stale_by_type": report.stale_by_type,
            "stale_list": [
                {
                    "entity_id": s.entity_id,
                    "relationship_type": s.relationship_type,
                    "target": s.target,
                    "days_stale": s.days_stale,
                    "decayed_confidence": s.decayed_confidence,
                }
                for s in report.stale_list[:50]
            ],
        }
        print(json.dumps(output, indent=2))
        return 0

    # Text output
    if args.action == "scan":
        print(f"Relationship Decay Scan")
        print(f"=" * 50)
        print(f"Entities scanned: {report.total_entities}")
        print(f"Total relationships: {report.total_relationships}")
        print(f"Stale relationships: {report.stale_relationships}")
        print(f"Avg confidence: {report.avg_confidence}")
        print(f"Avg decayed confidence: {report.avg_decayed_confidence}")
        print()
        if report.stale_by_type:
            print("Stale by type:")
            for rel_type, count in sorted(
                report.stale_by_type.items(), key=lambda x: -x[1]
            ):
                print(f"  {rel_type}: {count}")

    elif args.action == "stale":
        print(f"Stale Relationships ({report.stale_relationships} total)")
        print(f"=" * 70)
        for stale in report.stale_list[:30]:
            print(
                f"{stale.days_stale:4d}d | {stale.decayed_confidence:.2f} | "
                f"{stale.relationship_type:15} | {stale.entity_id} -> {stale.target}"
            )

    elif args.action == "report":
        print("Relationship Decay Report")
        print("=" * 60)
        print(f"Generated: {date.today().isoformat()}")
        print()
        print(f"Summary:")
        print(f"  Entities: {report.total_entities}")
        print(f"  Relationships: {report.total_relationships}")
        print(
            f"  Stale: {report.stale_relationships} ({report.stale_relationships/max(1,report.total_relationships)*100:.1f}%)"
        )
        print()
        print(f"Confidence:")
        print(f"  Average base: {report.avg_confidence:.3f}")
        print(f"  Average decayed: {report.avg_decayed_confidence:.3f}")
        print(
            f"  Decay delta: {report.avg_confidence - report.avg_decayed_confidence:.3f}"
        )
        print()
        if report.stale_by_type:
            print("Stale by relationship type:")
            for rel_type, count in sorted(
                report.stale_by_type.items(), key=lambda x: -x[1]
            ):
                print(f"  {rel_type}: {count}")
        print()
        print("Top 10 stalest relationships:")
        for i, stale in enumerate(report.stale_list[:10], 1):
            print(
                f"  {i}. {stale.entity_id} --[{stale.relationship_type}]--> {stale.target}"
            )
            print(
                f"     Days stale: {stale.days_stale}, Confidence: {stale.base_confidence:.2f} -> {stale.decayed_confidence:.2f}"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
