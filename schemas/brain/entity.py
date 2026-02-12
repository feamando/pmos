"""
PM-OS Brain Entity Base Schema

The foundation for all Brain 1.2 entities with temporal tracking,
metadata, and event sourcing support.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from .event import ChangeEvent
from .relationship import Relationship


class EntityType(str, Enum):
    """Supported entity types in PM-OS Brain."""

    PERSON = "person"
    TEAM = "team"
    SQUAD = "squad"
    PROJECT = "project"
    DOMAIN = "domain"
    EXPERIMENT = "experiment"
    SYSTEM = "system"
    BRAND = "brand"


class EntityStatus(str, Enum):
    """Entity lifecycle status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
    PENDING = "pending"


class OrphanReason(str, Enum):
    """Reason why an entity has no relationships (bd-7e77)."""

    PENDING_ENRICHMENT = "pending_enrichment"  # Not yet processed by enrichers
    NO_EXTERNAL_DATA = "no_external_data"  # Enrichers found no data in sources
    STANDALONE = "standalone"  # Legitimately independent entity
    ENRICHMENT_FAILED = "enrichment_failed"  # Enrichment attempted but failed


class EntityBase(BaseModel):
    """
    Base schema for all PM-OS Brain entities (v2).

    This schema adds:
    - Unique identification ($schema, $id, $type)
    - Version tracking ($version)
    - Temporal validity ($valid_from, $valid_to)
    - Quality metadata ($confidence, $source, $last_verified)
    - Typed relationships ($relationships)
    - Event sourcing ($events)
    - Classification ($tags, $aliases)
    """

    # Core Metadata (required)
    schema_: str = Field(
        alias="$schema",
        description="Schema URI for this entity type",
        examples=["brain://entity/person/v1", "brain://entity/project/v1"],
    )

    id: str = Field(
        alias="$id",
        description="Unique entity identifier",
        examples=["entity/person/jane-smith", "entity/project/meal-kit"],
    )

    type: EntityType = Field(
        alias="$type",
        description="Entity type",
    )

    version: int = Field(
        default=1,
        alias="$version",
        ge=1,
        description="Entity version number (increments on each update)",
    )

    created: datetime = Field(
        alias="$created",
        description="When the entity was first created",
    )

    updated: datetime = Field(
        alias="$updated",
        description="When the entity was last modified",
    )

    # Temporal Validity
    valid_from: Optional[date] = Field(
        default=None,
        alias="$valid_from",
        description="When this entity became valid (e.g., person's start date)",
    )

    valid_to: Optional[date] = Field(
        default=None,
        alias="$valid_to",
        description="When this entity ceased to be valid (null = current)",
    )

    # Quality Metadata
    confidence: float = Field(
        default=1.0,
        alias="$confidence",
        ge=0.0,
        le=1.0,
        description="Confidence score (0-1). Formula: completeness(40%) + source_reliability(40%) + freshness(20%)",
    )

    source: str = Field(
        default="unknown",
        alias="$source",
        description="Primary data source",
        examples=["hr_system", "manual", "jira", "github", "slack", "auto_generated"],
    )

    last_verified: Optional[date] = Field(
        default=None,
        alias="$last_verified",
        description="When this entity was last verified accurate",
    )

    # Status
    status: EntityStatus = Field(
        default=EntityStatus.ACTIVE,
        alias="$status",
        description="Entity lifecycle status",
    )

    # Orphan tracking (bd-7e77)
    orphan_reason: Optional[OrphanReason] = Field(
        default=None,
        alias="$orphan_reason",
        description="Why entity has no relationships (null if has relationships)",
    )

    # Relationships
    relationships: List[Relationship] = Field(
        default_factory=list,
        alias="$relationships",
        description="Typed relationships to other entities",
    )

    # Classification
    tags: List[str] = Field(
        default_factory=list,
        alias="$tags",
        description="Tags for categorization and filtering",
    )

    aliases: List[str] = Field(
        default_factory=list,
        alias="$aliases",
        description="Alternative names for lookup",
    )

    # Event Log (embedded)
    events: List[ChangeEvent] = Field(
        default_factory=list,
        alias="$events",
        description="Append-only change log for this entity",
    )

    # Human-readable content
    name: str = Field(
        ...,
        description="Display name of the entity",
    )

    description: Optional[str] = Field(
        default=None,
        description="Brief description",
    )

    # Links to external systems
    links: Optional[Dict[str, str]] = Field(
        default=None,
        description="Links to external systems (jira, confluence, github, slack)",
    )

    # Extensible metadata
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata specific to this entity",
    )

    class Config:
        populate_by_name = True  # Allow both alias and field name
        json_schema_extra = {
            "examples": [
                {
                    "$schema": "brain://entity/person/v1",
                    "$id": "entity/person/jane-smith",
                    "$type": "person",
                    "$version": 12,
                    "$created": "2025-07-01T00:00:00Z",
                    "$updated": "2026-01-21T13:20:00Z",
                    "$valid_from": "2024-01-01",
                    "$confidence": 0.95,
                    "$source": "hr_system",
                    "$status": "active",
                    "$relationships": [
                        {
                            "type": "reports_to",
                            "target": "entity/person/holger-hammel",
                            "since": "2024-06-01",
                        }
                    ],
                    "$tags": ["leadership", "product"],
                    "$aliases": ["nikita", "jane.smith"],
                    "name": "Jane Smith",
                    "description": "Director of Product, Growth Division & Ecosystems",
                }
            ]
        }

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is within valid range."""
        return max(0.0, min(1.0, v))

    def add_event(self, event: ChangeEvent) -> None:
        """Append an event to the change log and increment version."""
        self.events.append(event)
        self.version += 1
        self.updated = datetime.utcnow()

    def add_relationship(
        self,
        rel_type: str,
        target: str,
        actor: str,
        since: Optional[date] = None,
        role: Optional[str] = None,
    ) -> None:
        """Add a relationship and log the event."""
        rel = Relationship(type=rel_type, target=target, since=since, role=role)
        self.relationships.append(rel)

        event = ChangeEvent.create_relationship_add(
            actor=actor,
            relationship=rel.model_dump(),
        )
        self.add_event(event)

    def get_active_relationships(
        self, as_of: Optional[date] = None
    ) -> List[Relationship]:
        """Get relationships active as of a given date."""
        return [r for r in self.relationships if r.is_active(as_of)]

    def get_relationships_by_type(self, rel_type: str) -> List[Relationship]:
        """Get all relationships of a specific type."""
        return [r for r in self.relationships if r.type == rel_type]

    def calculate_confidence(
        self,
        completeness_score: float,
        source_reliability: float,
        freshness_score: float,
    ) -> float:
        """
        Calculate confidence score using the standard formula.

        Args:
            completeness_score: 0-1 based on fields populated
            source_reliability: 0-1 based on source (hr=0.95, manual=0.7, auto=0.5)
            freshness_score: 0-1 based on last_verified recency (decay 0.01/week)

        Returns:
            Weighted confidence score
        """
        return (
            completeness_score * 0.4
            + source_reliability * 0.4
            + freshness_score * 0.2
        )

    @classmethod
    def generate_id(cls, entity_type: EntityType, name: str) -> str:
        """Generate a standard entity ID from type and name."""
        slug = name.lower().replace(" ", "-").replace("_", "-")
        # Remove special characters
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        return f"entity/{entity_type.value}/{slug}"

    @classmethod
    def generate_schema_uri(cls, entity_type: EntityType, version: int = 1) -> str:
        """Generate schema URI for an entity type."""
        return f"brain://entity/{entity_type.value}/v{version}"
