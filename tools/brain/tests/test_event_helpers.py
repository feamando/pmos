#!/usr/bin/env python3
"""
Unit tests for PM-OS Brain EventHelper.

Run: pytest common/tools/brain/tests/test_event_helpers.py -v
"""

import sys
from copy import deepcopy
from pathlib import Path

import pytest

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from event_helpers import EventHelper
from schemas.brain import EventType


# --- create_event ---


class TestCreateEvent:
    """Tests for EventHelper.create_event()."""

    def test_all_event_types_valid(self):
        """Every EventType value produces a valid event dict."""
        for et in EventType:
            event = EventHelper.create_event(
                event_type=et.value,
                actor="test/unit",
                changes=[{"field": "f", "operation": "set", "value": "v"}],
                message=f"Test {et.value}",
            )
            assert event["type"] == et.value
            assert event["event_id"].startswith("evt-")
            assert "timestamp" in event
            assert event["actor"] == "test/unit"

    def test_invalid_event_type_raises(self):
        """Invalid event type raises ValueError."""
        with pytest.raises(ValueError):
            EventHelper.create_event(
                event_type="not_a_real_type",
                actor="test/unit",
                changes=[],
                message="Should fail",
            )

    def test_changes_serialized_correctly(self):
        """Changes are plain dicts with no None leakage."""
        event = EventHelper.create_event(
            event_type="field_update",
            actor="test/unit",
            changes=[
                {"field": "name", "operation": "set", "value": "New Name"},
            ],
            message="Update name",
        )
        change = event["changes"][0]
        assert change["field"] == "name"
        assert change["operation"] == "set"
        assert change["value"] == "New Name"
        assert "old_value" not in change  # None values stripped

    def test_old_value_preserved_when_present(self):
        """old_value included when explicitly provided."""
        event = EventHelper.create_event(
            event_type="field_update",
            actor="test/unit",
            changes=[
                {"field": "role", "operation": "set", "value": "Director", "old_value": "Manager"},
            ],
            message="Promoted",
        )
        assert event["changes"][0]["old_value"] == "Manager"

    def test_optional_fields_absent_when_none(self):
        """source and correlation_id absent from dict when not provided."""
        event = EventHelper.create_event(
            event_type="field_update",
            actor="test/unit",
            changes=[],
            message="Minimal",
        )
        assert "source" not in event
        assert "correlation_id" not in event

    def test_optional_fields_present_when_provided(self):
        """source and correlation_id present when explicitly provided."""
        event = EventHelper.create_event(
            event_type="field_update",
            actor="test/unit",
            changes=[],
            message="Full",
            source="jira:TEST-1",
            correlation_id="ctx-2026-02-11",
        )
        assert event["source"] == "jira:TEST-1"
        assert event["correlation_id"] == "ctx-2026-02-11"

    def test_unique_event_ids(self):
        """Each call generates a unique event_id."""
        ids = set()
        for _ in range(100):
            event = EventHelper.create_event(
                event_type="field_update",
                actor="test/unit",
                changes=[],
                message="Unique ID test",
            )
            ids.add(event["event_id"])
        assert len(ids) == 100

    def test_empty_changes_allowed(self):
        """Events with no changes are valid."""
        event = EventHelper.create_event(
            event_type="entity_create",
            actor="test/unit",
            message="Created",
        )
        assert event["changes"] == []


# --- append_to_frontmatter ---


class TestAppendToFrontmatter:
    """Tests for EventHelper.append_to_frontmatter()."""

    def _make_frontmatter(self, version=1, num_events=0):
        fm = {"$version": version, "$updated": "2026-01-01T00:00:00", "$events": []}
        for i in range(num_events):
            fm["$events"].append(
                EventHelper.create_event(
                    event_type="field_update",
                    actor=f"test/seed{i}",
                    changes=[],
                    message=f"Seed {i}",
                )
            )
        return fm

    def test_increments_version(self):
        """$version incremented by 1 per append."""
        fm = self._make_frontmatter(version=5)
        event = EventHelper.create_event(
            event_type="field_update", actor="test", changes=[], message="x"
        )
        EventHelper.append_to_frontmatter(fm, event)
        assert fm["$version"] == 6

    def test_updates_timestamp(self):
        """$updated changed to recent timestamp."""
        fm = self._make_frontmatter()
        event = EventHelper.create_event(
            event_type="field_update", actor="test", changes=[], message="x"
        )
        EventHelper.append_to_frontmatter(fm, event)
        assert fm["$updated"] != "2026-01-01T00:00:00"
        assert "2026-02" in fm["$updated"]  # Should be today

    def test_appends_event(self):
        """Event added to $events list."""
        fm = self._make_frontmatter(num_events=2)
        event = EventHelper.create_event(
            event_type="field_update", actor="test/new", changes=[], message="new"
        )
        EventHelper.append_to_frontmatter(fm, event)
        assert len(fm["$events"]) == 3
        assert fm["$events"][-1]["actor"] == "test/new"

    def test_creates_events_list_if_missing(self):
        """$events created if not present in frontmatter."""
        fm = {"$version": 1}
        event = EventHelper.create_event(
            event_type="entity_create", actor="test", changes=[], message="create"
        )
        EventHelper.append_to_frontmatter(fm, event)
        assert "$events" in fm
        assert len(fm["$events"]) == 1

    def test_skip_version_increment(self):
        """increment_version=False skips $version bump."""
        fm = self._make_frontmatter(version=3)
        event = EventHelper.create_event(
            event_type="field_update", actor="test", changes=[], message="x"
        )
        EventHelper.append_to_frontmatter(fm, event, increment_version=False)
        assert fm["$version"] == 3

    def test_multiple_appends(self):
        """3 sequential appends produce correct version and count."""
        fm = self._make_frontmatter(version=1)
        for i in range(3):
            event = EventHelper.create_event(
                event_type="field_update", actor=f"test/{i}", changes=[], message=f"e{i}"
            )
            EventHelper.append_to_frontmatter(fm, event)
        assert fm["$version"] == 4
        assert len(fm["$events"]) == 3

    def test_triggers_compaction_at_threshold(self):
        """Compaction runs when events exceed MAX_EVENTS."""
        fm = self._make_frontmatter(num_events=10)  # At limit
        event = EventHelper.create_event(
            event_type="field_update", actor="test/overflow", changes=[], message="overflow"
        )
        EventHelper.append_to_frontmatter(fm, event)
        # 11 events -> compacted to 10
        assert len(fm["$events"]) == 10


# --- Factory methods ---


class TestFactoryMethods:
    """Tests for factory convenience methods."""

    def test_create_field_update(self):
        event = EventHelper.create_field_update(
            actor="test", field="name", new_value="Alice", old_value="Bob"
        )
        assert event["type"] == "field_update"
        assert event["changes"][0]["field"] == "name"
        assert event["changes"][0]["value"] == "Alice"
        assert event["changes"][0]["old_value"] == "Bob"

    def test_create_field_update_no_old_value(self):
        event = EventHelper.create_field_update(actor="test", field="name", new_value="Alice")
        assert "old_value" not in event["changes"][0]

    def test_create_relationship_event_add(self):
        event = EventHelper.create_relationship_event(
            actor="test", target="entity/person/x", rel_type="reports_to", operation="add"
        )
        assert event["type"] == "relationship_add"
        assert event["changes"][0]["operation"] == "append"
        assert event["changes"][0]["value"]["target"] == "entity/person/x"

    def test_create_relationship_event_remove(self):
        event = EventHelper.create_relationship_event(
            actor="test", target="entity/person/x", rel_type="member_of", operation="remove"
        )
        assert event["type"] == "relationship_remove"
        assert event["changes"][0]["operation"] == "remove"

    def test_create_status_change(self):
        event = EventHelper.create_status_change(
            actor="test", old_status="active", new_status="archived"
        )
        assert event["type"] == "status_change"
        assert event["changes"][0]["value"] == "archived"
        assert event["changes"][0]["old_value"] == "active"


# --- compact_events ---


class TestCompactEvents:
    """Tests for event compaction."""

    def test_no_compaction_under_threshold(self):
        """Events under threshold are not touched."""
        fm = {"$events": [{"event_id": f"e{i}", "type": "x", "actor": "a", "timestamp": "t", "changes": []} for i in range(8)]}
        result = EventHelper.compact_events(fm)
        assert len(result["$events"]) == 8

    def test_compaction_at_threshold(self):
        """Events at exactly threshold are not compacted."""
        fm = {"$events": [{"event_id": f"e{i}", "type": "x", "actor": "a", "timestamp": "t", "changes": []} for i in range(10)]}
        result = EventHelper.compact_events(fm)
        assert len(result["$events"]) == 10

    def test_compaction_over_threshold(self):
        """Events over threshold compacted to max_events."""
        events = []
        for i in range(15):
            events.append({
                "event_id": f"e{i}",
                "type": "field_update",
                "actor": f"actor{i}",
                "timestamp": f"2026-01-{i+1:02d}T00:00:00",
                "changes": [{"field": f"f{i}", "operation": "set"}],
            })
        fm = {"$events": events}
        result = EventHelper.compact_events(fm)
        assert len(result["$events"]) == 10
        # First preserved
        assert result["$events"][0]["event_id"] == "e0"
        # Summary second
        assert result["$events"][1]["type"] == "compacted_summary"
        # Last 8 preserved
        assert result["$events"][-1]["event_id"] == "e14"
        assert result["$events"][2]["event_id"] == "e7"

    def test_compaction_preserves_first_event(self):
        """First event (creation) always preserved."""
        events = [
            {"event_id": "creation", "type": "entity_create", "actor": "system", "timestamp": "2026-01-01T00:00:00", "changes": []},
        ]
        for i in range(14):
            events.append({
                "event_id": f"e{i}",
                "type": "field_update",
                "actor": "test",
                "timestamp": f"2026-02-{i+1:02d}T00:00:00",
                "changes": [{"field": "f", "operation": "set"}],
            })
        fm = {"$events": events}
        result = EventHelper.compact_events(fm)
        assert result["$events"][0]["event_id"] == "creation"


# --- Round-trip test ---


class TestRoundTrip:
    """End-to-end test simulating real usage."""

    def test_create_add_relationship_update_field(self):
        """Simulate: create entity -> add relationship -> update field."""
        fm = {"$version": 0, "$events": []}

        # 1. Entity creation
        e1 = EventHelper.create_event(
            event_type="entity_create",
            actor="system/writer",
            changes=[{"field": "$schema", "operation": "set", "value": "brain://entity/person/v1"}],
            message="Created entity",
        )
        EventHelper.append_to_frontmatter(fm, e1)

        # 2. Add relationship
        e2 = EventHelper.create_relationship_event(
            actor="system/relationship_builder",
            target="entity/team/nve",
            rel_type="member_of",
            operation="add",
        )
        EventHelper.append_to_frontmatter(fm, e2)

        # 3. Update field
        e3 = EventHelper.create_field_update(
            actor="system/brain_updater",
            field="role",
            new_value="Director",
            correlation_id="context-2026-02-11",
        )
        EventHelper.append_to_frontmatter(fm, e3)

        assert fm["$version"] == 3
        assert len(fm["$events"]) == 3
        assert fm["$events"][0]["type"] == "entity_create"
        assert fm["$events"][1]["type"] == "relationship_add"
        assert fm["$events"][2]["type"] == "field_update"
        assert fm["$events"][2]["correlation_id"] == "context-2026-02-11"
