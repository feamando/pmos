"""
PM-OS Brain Registry Schema (v2)

Enhanced registry with versioning, denormalized lookups, and schema validation.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .entity import EntityStatus, EntityType


class RegistryEntry(BaseModel):
    """
    A single entry in the registry with denormalized metadata.

    Provides fast lookup without reading the full entity file.
    """

    ref: str = Field(
        alias="$ref",
        description="Relative path to entity file",
        examples=["Entities/People/Jane_Smith.md"],
    )

    type: EntityType = Field(
        alias="$type",
        description="Entity type",
    )

    status: EntityStatus = Field(
        default=EntityStatus.ACTIVE,
        alias="$status",
        description="Entity status",
    )

    version: int = Field(
        default=1,
        alias="$version",
        description="Entity version number",
    )

    updated: datetime = Field(
        alias="$updated",
        description="Last update timestamp",
    )

    # Denormalized for fast lookup
    aliases: List[str] = Field(
        default_factory=list,
        description="Alternative names for lookup",
    )

    # Type-specific denormalized fields
    role: Optional[str] = Field(
        default=None,
        description="For person: job role",
    )

    team: Optional[str] = Field(
        default=None,
        description="Team reference",
    )

    owner: Optional[str] = Field(
        default=None,
        description="For project: owner reference",
    )

    relationships_count: int = Field(
        default=0,
        description="Number of relationships",
    )

    confidence: float = Field(
        default=1.0,
        description="Entity confidence score",
    )

    class Config:
        populate_by_name = True


class RegistryV2(BaseModel):
    """
    PM-OS Brain Registry v2.

    Enhanced registry format with:
    - Schema versioning
    - Denormalized entity metadata for fast lookup
    - Alias-based resolution
    - Statistics and health metrics
    """

    schema_: str = Field(
        default="brain://registry/v2",
        alias="$schema",
        description="Registry schema URI",
    )

    version: str = Field(
        default="2.0",
        alias="$version",
        description="Registry format version",
    )

    generated: datetime = Field(
        default_factory=datetime.utcnow,
        alias="$generated",
        description="When registry was last generated",
    )

    # Entity index
    entities: Dict[str, RegistryEntry] = Field(
        default_factory=dict,
        description="Entity entries keyed by entity slug",
    )

    # Alias index for fast lookup
    alias_index: Dict[str, str] = Field(
        default_factory=dict,
        description="Maps aliases to entity slugs",
    )

    # Statistics
    stats: Optional[Dict[str, int]] = Field(
        default=None,
        description="Registry statistics",
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "examples": [
                {
                    "$schema": "brain://registry/v2",
                    "$version": "2.0",
                    "$generated": "2026-01-21T13:20:00Z",
                    "entities": {
                        "jane-smith": {
                            "$ref": "Entities/People/Jane_Smith.md",
                            "$type": "person",
                            "$status": "active",
                            "$version": 12,
                            "$updated": "2026-01-21T13:20:00Z",
                            "aliases": ["jane", "jane.smith"],
                            "role": "Director of Product",
                            "team": "growth-division",
                            "relationships_count": 15,
                            "confidence": 0.95,
                        }
                    },
                    "alias_index": {
                        "jane": "jane-smith",
                        "jane.smith": "jane-smith",
                    },
                    "stats": {
                        "total_entities": 2945,
                        "active_entities": 2800,
                        "people": 150,
                        "teams": 25,
                        "projects": 100,
                    },
                }
            ]
        }

    def add_entity(self, slug: str, entry: RegistryEntry) -> None:
        """Add an entity to the registry and update alias index."""
        self.entities[slug] = entry
        for alias in entry.aliases:
            self.alias_index[alias.lower()] = slug

    def resolve_alias(self, alias: str) -> Optional[str]:
        """Resolve an alias to an entity slug."""
        return self.alias_index.get(alias.lower())

    def get_entity(self, slug_or_alias: str) -> Optional[RegistryEntry]:
        """Get entity by slug or alias."""
        # Try direct slug first
        if slug_or_alias in self.entities:
            return self.entities[slug_or_alias]

        # Try alias resolution
        resolved = self.resolve_alias(slug_or_alias)
        if resolved:
            return self.entities.get(resolved)

        return None

    def get_entities_by_type(self, entity_type: EntityType) -> Dict[str, RegistryEntry]:
        """Get all entities of a specific type."""
        return {
            slug: entry
            for slug, entry in self.entities.items()
            if entry.type == entity_type
        }

    def get_active_entities(self) -> Dict[str, RegistryEntry]:
        """Get all active entities."""
        return {
            slug: entry
            for slug, entry in self.entities.items()
            if entry.status == EntityStatus.ACTIVE
        }

    def compute_stats(self) -> Dict[str, int]:
        """Compute and return registry statistics."""
        stats = {
            "total_entities": len(self.entities),
            "active_entities": len(self.get_active_entities()),
        }

        # Count by type
        for entity_type in EntityType:
            type_entries = self.get_entities_by_type(entity_type)
            stats[entity_type.value] = len(type_entries)

        self.stats = stats
        return stats

    def rebuild_alias_index(self) -> None:
        """Rebuild the alias index from entities."""
        self.alias_index = {}
        for slug, entry in self.entities.items():
            for alias in entry.aliases:
                self.alias_index[alias.lower()] = slug
