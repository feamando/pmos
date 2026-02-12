"""
PM-OS Brain Event Schema

Event sourcing for entity change tracking.
"""

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of changes that can be logged."""

    # Field changes
    FIELD_UPDATE = "field_update"
    FIELD_ADD = "field_add"
    FIELD_REMOVE = "field_remove"

    # Relationship changes
    RELATIONSHIP_ADD = "relationship_add"
    RELATIONSHIP_REMOVE = "relationship_remove"
    RELATIONSHIP_UPDATE = "relationship_update"

    # Status changes
    STATUS_CHANGE = "status_change"

    # Entity lifecycle
    ENTITY_CREATE = "entity_create"
    ENTITY_ARCHIVE = "entity_archive"
    ENTITY_RESTORE = "entity_restore"

    # Metadata updates
    CONFIDENCE_UPDATE = "confidence_update"
    VERIFICATION = "verification"


class FieldChange(BaseModel):
    """A single field change within an event."""

    field: str = Field(
        ...,
        description="Field path that changed (e.g., 'role', '$relationships')",
    )

    operation: str = Field(
        ...,
        description="Operation performed: set, append, remove, update",
        examples=["set", "append", "remove", "update"],
    )

    value: Optional[Any] = Field(
        default=None,
        description="New value (for set/append) or removed value (for remove)",
    )

    old_value: Optional[Any] = Field(
        default=None,
        description="Previous value (for audit trail)",
    )


class ChangeEvent(BaseModel):
    """
    An immutable record of a change to an entity.

    Events are append-only and enable:
    - Full audit trail
    - Point-in-time reconstruction
    - Change attribution
    """

    event_id: str = Field(
        default_factory=lambda: f"evt-{uuid4().hex[:12]}",
        description="Unique event identifier",
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the change occurred (UTC)",
    )

    type: EventType = Field(
        ...,
        description="Type of change",
    )

    actor: str = Field(
        ...,
        description="Who/what made the change (e.g., 'user/nikita', 'system/daily_context')",
        examples=["user/nikita", "system/daily_context", "sync/jira", "sync/github"],
    )

    changes: List[FieldChange] = Field(
        default_factory=list,
        description="List of field changes in this event",
    )

    correlation_id: Optional[str] = Field(
        default=None,
        description="ID to correlate related events (e.g., 'context-2026-01-21')",
    )

    source: Optional[str] = Field(
        default=None,
        description="Source system or document that triggered this change",
        examples=["jira:PROJ-123", "gdoc:1abc2def", "slack:C123ABC"],
    )

    message: Optional[str] = Field(
        default=None,
        description="Human-readable description of the change",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "event_id": "evt-2026-01-21-001",
                    "timestamp": "2026-01-21T13:20:00Z",
                    "type": "field_update",
                    "actor": "system/daily_context",
                    "changes": [
                        {
                            "field": "current_focus",
                            "operation": "set",
                            "value": "Leading 4 squads across Meal Kit, WB, Growth Platform",
                        }
                    ],
                    "correlation_id": "context-2026-01-21",
                }
            ]
        }

    @classmethod
    def create_field_update(
        cls,
        actor: str,
        field: str,
        new_value: Any,
        old_value: Any = None,
        source: Optional[str] = None,
        message: Optional[str] = None,
    ) -> "ChangeEvent":
        """Factory method for simple field updates."""
        return cls(
            type=EventType.FIELD_UPDATE,
            actor=actor,
            changes=[
                FieldChange(
                    field=field,
                    operation="set",
                    value=new_value,
                    old_value=old_value,
                )
            ],
            source=source,
            message=message,
        )

    @classmethod
    def create_relationship_add(
        cls,
        actor: str,
        relationship: dict,
        source: Optional[str] = None,
    ) -> "ChangeEvent":
        """Factory method for adding a relationship."""
        return cls(
            type=EventType.RELATIONSHIP_ADD,
            actor=actor,
            changes=[
                FieldChange(
                    field="$relationships",
                    operation="append",
                    value=relationship,
                )
            ],
            source=source,
            message=f"Added relationship: {relationship.get('type')} -> {relationship.get('target')}",
        )
