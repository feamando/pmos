"""
PM-OS Brain Entity Schemas (v2)

Pydantic models for Brain 1.2 time-series capable entities.
"""

from .entity import EntityBase, EntityType, EntityStatus, OrphanReason
from .relationship import Relationship, RelationshipType
from .event import ChangeEvent, EventType, FieldChange
from .person import PersonEntity
from .project import ProjectEntity
from .team import TeamEntity, SquadEntity
from .registry import RegistryEntry, RegistryV2

__all__ = [
    # Base
    "EntityBase",
    "EntityType",
    "EntityStatus",
    "OrphanReason",
    # Relationships
    "Relationship",
    "RelationshipType",
    # Events
    "ChangeEvent",
    "EventType",
    "FieldChange",
    # Entity Types
    "PersonEntity",
    "ProjectEntity",
    "TeamEntity",
    "SquadEntity",
    # Registry
    "RegistryEntry",
    "RegistryV2",
]

__version__ = "2.0.0"
