#!/usr/bin/env python3
"""
PM-OS Brain Temporal Query System

Enables point-in-time reconstruction and temporal queries on Brain entities.
"""

import copy
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Add to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from event_store import Event, EventStore


@dataclass
class EntitySnapshot:
    """Represents entity state at a point in time."""

    entity_id: str
    timestamp: datetime
    frontmatter: Dict[str, Any]
    body: str
    version: int


class TemporalQuery:
    """
    Enables temporal queries on Brain entities.

    Supports:
    - Point-in-time reconstruction
    - Change history analysis
    - Temporal comparisons
    - State diff generation
    """

    def __init__(self, brain_path: Path):
        """
        Initialize the temporal query system.

        Args:
            brain_path: Path to the brain directory
        """
        self.brain_path = brain_path
        self.event_store = EventStore(brain_path)
        self.snapshot_cache: Dict[str, Dict[str, EntitySnapshot]] = {}

    def get_entity_at(
        self,
        entity_path: Path,
        point_in_time: datetime,
    ) -> Optional[EntitySnapshot]:
        """
        Reconstruct entity state at a specific point in time.

        Works by:
        1. Getting all events up to point_in_time
        2. Applying events in order to reconstruct state

        Args:
            entity_path: Path to entity file
            point_in_time: The point in time to reconstruct

        Returns:
            EntitySnapshot if reconstruction possible, None otherwise
        """
        if not entity_path.exists():
            return None

        # Get current state as base
        content = entity_path.read_text(encoding="utf-8")
        frontmatter, body = self._parse_content(content)

        entity_id = str(entity_path.relative_to(self.brain_path))

        # Get all events for this entity
        all_events = self.event_store.get_entity_events(entity_path)

        if not all_events:
            # No events, return current state if created before point_in_time
            created = frontmatter.get("$created", "")
            if created:
                created_dt = self._parse_datetime(created)
                if created_dt and created_dt <= point_in_time:
                    return EntitySnapshot(
                        entity_id=entity_id,
                        timestamp=point_in_time,
                        frontmatter=frontmatter,
                        body=body,
                        version=frontmatter.get("$version", 1),
                    )
            return None

        # Filter events up to point_in_time
        relevant_events = [e for e in all_events if e.timestamp <= point_in_time]

        if not relevant_events:
            return None

        # Reconstruct state by replaying events
        reconstructed = self._reconstruct_from_events(
            frontmatter, body, relevant_events
        )

        return EntitySnapshot(
            entity_id=entity_id,
            timestamp=point_in_time,
            frontmatter=reconstructed["frontmatter"],
            body=reconstructed["body"],
            version=len(relevant_events),
        )

    def compare_states(
        self,
        entity_path: Path,
        time_a: datetime,
        time_b: datetime,
    ) -> Dict[str, Any]:
        """
        Compare entity state between two points in time.

        Args:
            entity_path: Path to entity file
            time_a: First point in time
            time_b: Second point in time

        Returns:
            Dictionary with differences
        """
        state_a = self.get_entity_at(entity_path, time_a)
        state_b = self.get_entity_at(entity_path, time_b)

        diff = {
            "entity_id": str(entity_path.relative_to(self.brain_path)),
            "time_a": time_a.isoformat(),
            "time_b": time_b.isoformat(),
            "exists_at_a": state_a is not None,
            "exists_at_b": state_b is not None,
            "field_changes": [],
        }

        if state_a and state_b:
            diff["field_changes"] = self._diff_frontmatter(
                state_a.frontmatter, state_b.frontmatter
            )
            diff["version_a"] = state_a.version
            diff["version_b"] = state_b.version

        return diff

    def get_field_history(
        self,
        entity_path: Path,
        field_name: str,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get the history of changes to a specific field.

        Args:
            entity_path: Path to entity file
            field_name: Name of the field to track
            since: Only show changes after this time

        Returns:
            List of changes to the field
        """
        events = self.event_store.get_entity_events(entity_path, since=since)
        history = []

        for event in events:
            for change in event.changes:
                if change.get("field") == field_name:
                    history.append(
                        {
                            "timestamp": event.timestamp.isoformat(),
                            "operation": change.get("operation", "unknown"),
                            "old_value": change.get("old_value"),
                            "new_value": change.get("value"),
                            "actor": event.actor,
                            "event_id": event.event_id,
                        }
                    )

        return history

    def query_entities_at(
        self,
        point_in_time: datetime,
        entity_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[EntitySnapshot]:
        """
        Query all entities at a specific point in time.

        Args:
            point_in_time: The point in time to query
            entity_type: Filter by entity type
            status: Filter by status

        Returns:
            List of entity snapshots matching criteria
        """
        snapshots = []

        # Find all entity files
        entity_files = list(self.brain_path.rglob("*.md"))
        entity_files = [
            f
            for f in entity_files
            if f.name.lower() not in ("readme.md", "index.md", "_index.md")
        ]

        for entity_path in entity_files:
            snapshot = self.get_entity_at(entity_path, point_in_time)
            if not snapshot:
                continue

            # Apply filters
            if entity_type:
                if snapshot.frontmatter.get("$type") != entity_type:
                    continue
            if status:
                if snapshot.frontmatter.get("$status") != status:
                    continue

            snapshots.append(snapshot)

        return snapshots

    def get_changes_in_period(
        self,
        start: datetime,
        end: datetime,
        entity_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get summary of changes in a time period.

        Args:
            start: Start of period
            end: End of period
            entity_type: Filter by entity type

        Returns:
            Summary of changes
        """
        events = self.event_store.query_events(since=start, until=end, limit=10000)

        summary = {
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "total_events": len(events),
            "entities_changed": len(set(e.entity_id for e in events)),
            "by_type": {},
            "by_actor": {},
            "by_entity": {},
        }

        for event in events:
            # Count by event type
            event_type = event.event_type
            summary["by_type"][event_type] = summary["by_type"].get(event_type, 0) + 1

            # Count by actor
            actor = event.actor
            summary["by_actor"][actor] = summary["by_actor"].get(actor, 0) + 1

            # Count by entity
            entity_id = event.entity_id
            summary["by_entity"][entity_id] = summary["by_entity"].get(entity_id, 0) + 1

        return summary

    def _reconstruct_from_events(
        self,
        base_frontmatter: Dict[str, Any],
        base_body: str,
        events: List[Event],
    ) -> Dict[str, Any]:
        """
        Reconstruct state by replaying events.

        Note: This is a simplified reconstruction that tracks field updates.
        Full reconstruction would require storing complete snapshots.
        """
        frontmatter = copy.deepcopy(base_frontmatter)

        # For now, we can't fully reconstruct past states without snapshots
        # We can only confirm which fields changed
        changed_fields = set()

        for event in events:
            for change in event.changes:
                field = change.get("field", "")
                if field:
                    changed_fields.add(field)

        return {
            "frontmatter": frontmatter,
            "body": base_body,
            "changed_fields": list(changed_fields),
        }

    def _diff_frontmatter(
        self,
        fm_a: Dict[str, Any],
        fm_b: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Generate diff between two frontmatter dicts."""
        changes = []
        all_keys = set(fm_a.keys()) | set(fm_b.keys())

        for key in all_keys:
            if key.startswith("$events"):
                continue  # Skip events in diff

            val_a = fm_a.get(key)
            val_b = fm_b.get(key)

            if val_a != val_b:
                changes.append(
                    {
                        "field": key,
                        "old_value": val_a,
                        "new_value": val_b,
                    }
                )

        return changes

    def _parse_content(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Parse frontmatter and body from content."""
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

    def _parse_datetime(self, date_str: str) -> Optional[datetime]:
        """Parse datetime from string."""
        if not date_str:
            return None

        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None


def create_temporal_query(brain_path: Optional[Path] = None) -> TemporalQuery:
    """
    Factory function to create a TemporalQuery.

    Args:
        brain_path: Path to brain directory (uses default if not specified)

    Returns:
        Configured TemporalQuery instance
    """
    if brain_path is None:
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))
        from path_resolver import get_paths

        paths = get_paths()
        brain_path = paths.user / "brain"

    return TemporalQuery(brain_path)
