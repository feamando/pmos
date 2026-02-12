#!/usr/bin/env python3
"""
PM-OS Brain Stale Entity Detector

Identifies outdated or potentially stale Brain entities.
"""

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


@dataclass
class StaleEntity:
    """Represents a potentially stale entity."""

    entity_id: str
    entity_type: str
    entity_path: Path
    last_updated: Optional[datetime]
    days_stale: int
    staleness_reasons: List[str]
    recommended_action: str


class StaleEntityDetector:
    """
    Detects stale or outdated Brain entities.

    Checks:
    - Last update date vs threshold
    - No recent events
    - Missing or outdated status
    - Terminated relationships
    - Known stale patterns
    """

    # Default staleness thresholds (days)
    THRESHOLDS = {
        "person": 90,  # People should be updated quarterly
        "team": 60,  # Teams change frequently
        "squad": 60,  # Squads change frequently
        "project": 30,  # Projects need monthly updates
        "experiment": 14,  # Experiments are short-lived
        "domain": 180,  # Domains are stable
        "system": 90,  # Systems need quarterly review
        "brand": 180,  # Brands are stable
        "default": 90,
    }

    # Status values that indicate staleness
    STALE_STATUSES = {
        "deprecated",
        "archived",
        "inactive",
        "completed",
        "cancelled",
        "on-hold",
        "abandoned",
    }

    def __init__(self, brain_path: Path):
        """
        Initialize the detector.

        Args:
            brain_path: Path to the brain directory
        """
        self.brain_path = brain_path

    def detect_stale(
        self,
        threshold_days: Optional[int] = None,
        entity_type: Optional[str] = None,
    ) -> List[StaleEntity]:
        """
        Detect stale entities.

        Args:
            threshold_days: Override default threshold
            entity_type: Filter by entity type

        Returns:
            List of stale entities
        """
        stale_entities = []

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
                stale = self._check_entity(entity_path, threshold_days)
                if stale:
                    if entity_type and stale.entity_type != entity_type:
                        continue
                    stale_entities.append(stale)
            except Exception:
                continue

        return sorted(stale_entities, key=lambda e: e.days_stale, reverse=True)

    def get_summary(
        self, stale_entities: Optional[List[StaleEntity]] = None
    ) -> Dict[str, Any]:
        """
        Get summary of stale entities.

        Args:
            stale_entities: Pre-detected entities (or will detect)

        Returns:
            Summary statistics
        """
        if stale_entities is None:
            stale_entities = self.detect_stale()

        if not stale_entities:
            return {"total_stale": 0}

        # Count by type
        by_type: Dict[str, int] = {}
        by_reason: Dict[str, int] = {}
        by_action: Dict[str, int] = {}

        for entity in stale_entities:
            by_type[entity.entity_type] = by_type.get(entity.entity_type, 0) + 1
            by_action[entity.recommended_action] = (
                by_action.get(entity.recommended_action, 0) + 1
            )
            for reason in entity.staleness_reasons:
                by_reason[reason] = by_reason.get(reason, 0) + 1

        avg_days = sum(e.days_stale for e in stale_entities) / len(stale_entities)

        return {
            "total_stale": len(stale_entities),
            "average_days_stale": round(avg_days),
            "by_type": by_type,
            "by_reason": sorted(by_reason.items(), key=lambda x: x[1], reverse=True),
            "by_action": by_action,
            "oldest": stale_entities[0].entity_id if stale_entities else None,
            "oldest_days": stale_entities[0].days_stale if stale_entities else 0,
        }

    def _check_entity(
        self, entity_path: Path, threshold_override: Optional[int] = None
    ) -> Optional[StaleEntity]:
        """Check if an entity is stale."""
        content = entity_path.read_text(encoding="utf-8")
        frontmatter, body = self._parse_content(content)

        entity_id = str(entity_path.relative_to(self.brain_path))
        entity_type = frontmatter.get("$type", "unknown")

        # Determine threshold
        if threshold_override:
            threshold = threshold_override
        else:
            threshold = self.THRESHOLDS.get(entity_type, self.THRESHOLDS["default"])

        # Get last update time
        last_updated = self._get_last_updated(frontmatter)
        days_stale = self._calculate_days_stale(last_updated)

        # Check for staleness indicators
        reasons = []
        action = "review"

        # Check age
        if days_stale > threshold:
            reasons.append(f"Not updated in {days_stale} days (threshold: {threshold})")
            action = "update"

        # Check status
        status = frontmatter.get("$status", frontmatter.get("status", ""))
        if status.lower() in self.STALE_STATUSES:
            reasons.append(f"Status is '{status}'")
            action = "archive_or_remove"

        # Check validity period
        valid_to = frontmatter.get("$valid_to")
        if valid_to:
            try:
                valid_to_dt = datetime.fromisoformat(
                    str(valid_to).replace("Z", "+00:00")
                )
                if valid_to_dt < datetime.now(valid_to_dt.tzinfo):
                    reasons.append("Validity period has ended")
                    action = "archive_or_remove"
            except (ValueError, TypeError):
                pass

        # Check for no events
        events = frontmatter.get("$events", [])
        if not events and days_stale > 30:
            reasons.append("No change events recorded")

        # Check for terminated relationships (person left)
        if entity_type == "person":
            if self._check_person_terminated(frontmatter):
                reasons.append("Person may have left (no recent activity)")
                action = "verify_status"

        # Check for completed projects
        if entity_type in ("project", "experiment"):
            project_status = frontmatter.get(
                "project_status", frontmatter.get("status", "")
            )
            if project_status.lower() in ("completed", "done", "finished", "shipped"):
                if days_stale > 30:
                    reasons.append("Project completed but not archived")
                    action = "archive"

        # Check low confidence
        confidence = frontmatter.get("$confidence", 1.0)
        if confidence < 0.3:
            reasons.append(f"Very low confidence ({confidence})")

        if not reasons:
            return None

        return StaleEntity(
            entity_id=entity_id,
            entity_type=entity_type,
            entity_path=entity_path,
            last_updated=last_updated,
            days_stale=days_stale,
            staleness_reasons=reasons,
            recommended_action=action,
        )

    def _get_last_updated(self, frontmatter: Dict[str, Any]) -> Optional[datetime]:
        """Get the last update timestamp."""
        # Try various fields
        for field in ["$updated", "updated", "$modified", "modified"]:
            value = frontmatter.get(field)
            if value:
                try:
                    if isinstance(value, datetime):
                        return value
                    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    continue

        # Fall back to events
        events = frontmatter.get("$events", [])
        if events:
            try:
                last_event = events[-1]
                timestamp = last_event.get("timestamp", "")
                return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except (ValueError, TypeError, IndexError):
                pass

        return None

    def _calculate_days_stale(self, last_updated: Optional[datetime]) -> int:
        """Calculate days since last update."""
        if not last_updated:
            return 365  # Assume very stale if unknown

        now = (
            datetime.now(last_updated.tzinfo) if last_updated.tzinfo else datetime.now()
        )
        return (now - last_updated).days

    def _check_person_terminated(self, frontmatter: Dict[str, Any]) -> bool:
        """Check if a person may have left the organization."""
        # Check for explicit status
        status = frontmatter.get("$status", frontmatter.get("status", ""))
        if status.lower() in ("inactive", "departed", "alumni", "former"):
            return True

        # Check for valid_to in the past
        valid_to = frontmatter.get("$valid_to")
        if valid_to:
            try:
                valid_to_dt = datetime.fromisoformat(
                    str(valid_to).replace("Z", "+00:00")
                )
                if valid_to_dt < datetime.now(valid_to_dt.tzinfo):
                    return True
            except (ValueError, TypeError):
                pass

        return False

    def _parse_content(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Parse frontmatter and body."""
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
    parser = argparse.ArgumentParser(description="Detect stale Brain entities")
    parser.add_argument(
        "action",
        choices=["detect", "summary", "list"],
        help="Action to perform",
    )
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--type",
        type=str,
        help="Filter by entity type",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        help="Override staleness threshold (days)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Limit output (default: 20)",
    )

    args = parser.parse_args()

    # Default brain path
    if not args.brain_path:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from path_resolver import get_paths

        paths = get_paths()
        args.brain_path = paths.user / "brain"

    detector = StaleEntityDetector(args.brain_path)

    if args.action in ("detect", "list"):
        stale = detector.detect_stale(
            threshold_days=args.threshold,
            entity_type=args.type,
        )

        print(f"Found {len(stale)} stale entities")
        print("=" * 60)

        for entity in stale[: args.limit]:
            print(f"\n{entity.entity_id}")
            print(f"  Type: {entity.entity_type}")
            print(f"  Days stale: {entity.days_stale}")
            print(f"  Reasons: {', '.join(entity.staleness_reasons)}")
            print(f"  Action: {entity.recommended_action}")

        if len(stale) > args.limit:
            print(f"\n... and {len(stale) - args.limit} more")

    elif args.action == "summary":
        stale = detector.detect_stale(
            threshold_days=args.threshold,
            entity_type=args.type,
        )
        summary = detector.get_summary(stale)

        print("Stale Entity Summary")
        print("=" * 60)
        print(f"Total stale: {summary['total_stale']}")
        print(f"Average days stale: {summary['average_days_stale']}")
        print()
        print("By type:")
        for t, count in summary["by_type"].items():
            print(f"  {t}: {count}")
        print()
        print("Top reasons:")
        for reason, count in summary["by_reason"][:5]:
            print(f"  - {reason}: {count}")
        print()
        print("Recommended actions:")
        for action, count in summary["by_action"].items():
            print(f"  {action}: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
