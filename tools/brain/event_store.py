#!/usr/bin/env python3
"""
PM-OS Brain Event Store

Manages event persistence and querying for Brain entities.
Supports both embedded events (in entity files) and separate event logs.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import yaml


@dataclass
class Event:
    """Represents a single change event."""

    event_id: str
    timestamp: datetime
    event_type: str
    actor: str
    entity_id: str
    message: str
    changes: List[Dict[str, Any]] = field(default_factory=list)
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat() + "Z",
            "type": self.event_type,
            "actor": self.actor,
            "entity_id": self.entity_id,
            "message": self.message,
            "changes": self.changes,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], entity_id: str = "") -> "Event":
        """Create Event from dictionary."""
        from datetime import timezone

        timestamp = data.get("timestamp", "")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        elif isinstance(timestamp, datetime):
            pass  # keep as-is
        else:
            timestamp = datetime.now(timezone.utc)

        # Normalize to timezone-aware (UTC) for consistent comparisons
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        return cls(
            event_id=data.get("event_id", ""),
            timestamp=timestamp,
            event_type=data.get("type", "unknown"),
            actor=data.get("actor", "unknown"),
            entity_id=data.get("entity_id", entity_id),
            message=data.get("message", ""),
            changes=data.get("changes", []),
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {}),
        )


class EventStore:
    """
    Manages event storage and retrieval for Brain entities.

    Supports:
    - Reading events from entity files (embedded $events)
    - Writing events to entity files
    - Querying events by time range, entity, or type
    - Aggregating events across entities
    """

    def __init__(self, brain_path: Path):
        """
        Initialize the event store.

        Args:
            brain_path: Path to the brain directory
        """
        self.brain_path = brain_path
        self.events_cache: Dict[str, List[Event]] = {}

    def get_entity_events(
        self,
        entity_path: Path,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
    ) -> List[Event]:
        """
        Get events for a specific entity.

        Args:
            entity_path: Path to entity file
            since: Filter events after this time
            until: Filter events before this time
            event_types: Filter by event types

        Returns:
            List of events matching criteria
        """
        events = self._load_entity_events(entity_path)

        # Apply filters
        if since:
            events = [e for e in events if e.timestamp >= since]
        if until:
            events = [e for e in events if e.timestamp <= until]
        if event_types:
            events = [e for e in events if e.event_type in event_types]

        return sorted(events, key=lambda e: e.timestamp)

    def append_event(
        self,
        entity_path: Path,
        event_type: str,
        message: str,
        actor: str = "system",
        changes: Optional[List[Dict]] = None,
        correlation_id: Optional[str] = None,
    ) -> Event:
        """
        Append a new event to an entity.

        Args:
            entity_path: Path to entity file
            event_type: Type of event
            message: Event message
            actor: Who/what triggered the event
            changes: List of field changes
            correlation_id: Optional correlation ID

        Returns:
            The created event
        """
        # Generate event ID
        event_id = f"evt-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        # Determine entity ID from path
        try:
            entity_id = str(entity_path.relative_to(self.brain_path))
        except ValueError:
            entity_id = entity_path.stem

        event = Event(
            event_id=event_id,
            timestamp=datetime.utcnow(),
            event_type=event_type,
            actor=actor,
            entity_id=entity_id,
            message=message,
            changes=changes or [],
            correlation_id=correlation_id,
        )

        self._write_event_to_entity(entity_path, event)
        return event

    def query_events(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
        actors: Optional[List[str]] = None,
        entity_pattern: Optional[str] = None,
        limit: int = 100,
    ) -> List[Event]:
        """
        Query events across all entities.

        Args:
            since: Filter events after this time
            until: Filter events before this time
            event_types: Filter by event types
            actors: Filter by actors
            entity_pattern: Glob pattern for entity paths
            limit: Maximum events to return

        Returns:
            List of matching events
        """
        all_events = []

        # Find entity files
        if entity_pattern:
            entity_files = list(self.brain_path.glob(entity_pattern))
        else:
            entity_files = list(self.brain_path.rglob("*.md"))
            entity_files = [
                f
                for f in entity_files
                if f.name.lower() not in ("readme.md", "index.md", "_index.md")
            ]

        for entity_path in entity_files:
            events = self.get_entity_events(entity_path, since, until, event_types)

            if actors:
                events = [e for e in events if e.actor in actors]

            all_events.extend(events)

        # Sort by timestamp descending and limit
        all_events.sort(key=lambda e: e.timestamp, reverse=True)
        return all_events[:limit]

    def get_events_by_correlation(self, correlation_id: str) -> List[Event]:
        """
        Get all events with a specific correlation ID.

        Args:
            correlation_id: The correlation ID to search for

        Returns:
            List of events with matching correlation ID
        """
        events = self.query_events(limit=10000)
        return [e for e in events if e.correlation_id == correlation_id]

    def get_entity_timeline(
        self,
        entity_path: Path,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get timeline of changes for an entity.

        Args:
            entity_path: Path to entity file
            start: Start of timeline
            end: End of timeline

        Returns:
            List of timeline entries with state snapshots
        """
        events = self.get_entity_events(entity_path, since=start, until=end)
        timeline = []

        for event in events:
            entry = {
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type,
                "actor": event.actor,
                "message": event.message,
                "changes": event.changes,
            }
            timeline.append(entry)

        return timeline

    def count_events(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        group_by: str = "type",
    ) -> Dict[str, int]:
        """
        Count events grouped by a field.

        Args:
            since: Filter events after this time
            until: Filter events before this time
            group_by: Field to group by (type, actor, entity_id)

        Returns:
            Dictionary of counts by group
        """
        events = self.query_events(since=since, until=until, limit=10000)
        counts: Dict[str, int] = {}

        for event in events:
            if group_by == "type":
                key = event.event_type
            elif group_by == "actor":
                key = event.actor
            elif group_by == "entity_id":
                key = event.entity_id
            else:
                key = "unknown"

            counts[key] = counts.get(key, 0) + 1

        return counts

    def _load_entity_events(self, entity_path: Path) -> List[Event]:
        """Load events from an entity file."""
        cache_key = str(entity_path)

        if cache_key in self.events_cache:
            return self.events_cache[cache_key]

        events = []

        if not entity_path.exists():
            return events

        try:
            content = entity_path.read_text(encoding="utf-8")
            frontmatter = self._parse_frontmatter(content)

            entity_id = str(entity_path.relative_to(self.brain_path))
            raw_events = frontmatter.get("$events", [])

            for raw_event in raw_events:
                events.append(Event.from_dict(raw_event, entity_id))

        except Exception:
            pass

        self.events_cache[cache_key] = events
        return events

    def _write_event_to_entity(self, entity_path: Path, event: Event) -> bool:
        """Write an event to an entity file."""
        if not entity_path.exists():
            return False

        try:
            content = entity_path.read_text(encoding="utf-8")
            frontmatter, body = self._parse_content(content)

            if "$events" not in frontmatter:
                frontmatter["$events"] = []

            frontmatter["$events"].append(event.to_dict())

            # Update version and timestamp
            frontmatter["$version"] = frontmatter.get("$version", 0) + 1
            frontmatter["$updated"] = datetime.utcnow().isoformat() + "Z"

            # Write back
            new_content = (
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

            entity_path.write_text(new_content, encoding="utf-8")

            # Invalidate cache
            cache_key = str(entity_path)
            if cache_key in self.events_cache:
                del self.events_cache[cache_key]

            return True

        except Exception:
            return False

    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """Parse YAML frontmatter from content."""
        if not content.startswith("---"):
            return {}

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}

        try:
            return yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            return {}

    def _parse_content(self, content: str) -> tuple[Dict[str, Any], str]:
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

    def clear_cache(self):
        """Clear the events cache."""
        self.events_cache.clear()


def create_event_store(brain_path: Optional[Path] = None) -> EventStore:
    """
    Factory function to create an EventStore.

    Args:
        brain_path: Path to brain directory (uses default if not specified)

    Returns:
        Configured EventStore instance
    """
    if brain_path is None:
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))
        from path_resolver import get_paths

        paths = get_paths()
        brain_path = paths.user / "brain"

    return EventStore(brain_path)
