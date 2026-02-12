"""
PM-OS Brain Project Entity Schema

Schema for project entities (initiatives, features, products).
"""

from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import Field

from .entity import EntityBase, EntityType


class ProjectStatus(str, Enum):
    """Project-specific status values."""

    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    LAUNCHED = "launched"


class ProjectEntity(EntityBase):
    """
    Project entity for PM-OS Brain.

    Represents initiatives, features, products, or any tracked work.
    """

    # Override type to be project
    type: EntityType = Field(
        default=EntityType.PROJECT,
        alias="$type",
    )

    # Project-specific fields
    project_status: Optional[ProjectStatus] = Field(
        default=ProjectStatus.PLANNING,
        description="Project lifecycle status",
    )

    owner: Optional[str] = Field(
        default=None,
        description="Project owner (entity reference)",
        examples=["entity/person/jane-smith"],
    )

    team: Optional[str] = Field(
        default=None,
        description="Owning team (entity reference)",
        examples=["entity/team/growth-division", "entity/squad/meal-kit"],
    )

    stakeholders: List[str] = Field(
        default_factory=list,
        description="Project stakeholders (entity references)",
    )

    # Timeline
    start_date: Optional[date] = Field(
        default=None,
        description="Project start date",
    )

    target_date: Optional[date] = Field(
        default=None,
        description="Target completion date",
    )

    launched_date: Optional[date] = Field(
        default=None,
        description="Actual launch date",
    )

    # Business context
    business_unit: Optional[str] = Field(
        default=None,
        description="Business unit or brand",
        examples=["Meal Kit", "Wellness Brand", "Growth Platform", "Acme Corp"],
    )

    market: Optional[str] = Field(
        default=None,
        description="Target market",
        examples=["US", "DE", "UK", "Global"],
    )

    # Technical context
    tech_stack: List[str] = Field(
        default_factory=list,
        description="Technologies used",
        examples=[["React Native", "Go", "Shopify"]],
    )

    repositories: List[str] = Field(
        default_factory=list,
        description="Related GitHub repositories",
    )

    # Metrics and goals
    okrs: List[str] = Field(
        default_factory=list,
        description="Related OKRs or goals",
    )

    kpis: List[str] = Field(
        default_factory=list,
        description="Key performance indicators",
    )

    # Documentation
    prd_link: Optional[str] = Field(
        default=None,
        description="Link to PRD document",
    )

    confluence_space: Optional[str] = Field(
        default=None,
        description="Confluence space or page",
    )

    # Experiment tracking
    experiments: List[str] = Field(
        default_factory=list,
        description="Related experiments (entity references)",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "$schema": "brain://entity/project/v1",
                    "$id": "entity/project/meal-kit",
                    "$type": "project",
                    "$version": 5,
                    "$created": "2024-01-01T00:00:00Z",
                    "$updated": "2026-01-21T13:20:00Z",
                    "$confidence": 0.9,
                    "$source": "manual",
                    "$status": "active",
                    "$relationships": [
                        {
                            "type": "owned_by",
                            "target": "entity/person/jane-smith",
                            "role": "product_lead",
                        },
                        {
                            "type": "part_of",
                            "target": "entity/team/growth-division",
                        },
                    ],
                    "$tags": ["growth-division", "d2c", "meat"],
                    "name": "Meal Kit",
                    "description": "Premium meat delivery service for US market",
                    "project_status": "launched",
                    "owner": "entity/person/jane-smith",
                    "team": "entity/squad/meal-kit",
                    "business_unit": "Meal Kit",
                    "market": "US",
                    "launched_date": "2023-01-15",
                }
            ]
        }

    @classmethod
    def create(
        cls,
        name: str,
        owner: Optional[str] = None,
        team: Optional[str] = None,
        business_unit: Optional[str] = None,
        source: str = "manual",
    ) -> "ProjectEntity":
        """Factory method to create a new project entity."""
        from datetime import datetime

        entity_id = cls.generate_id(EntityType.PROJECT, name)
        schema_uri = cls.generate_schema_uri(EntityType.PROJECT)
        now = datetime.utcnow()

        return cls(
            **{
                "$schema": schema_uri,
                "$id": entity_id,
                "$type": EntityType.PROJECT,
                "$version": 1,
                "$created": now,
                "$updated": now,
                "$source": source,
                "$confidence": 0.7 if source == "manual" else 0.5,
                "name": name,
                "owner": owner,
                "team": team,
                "business_unit": business_unit,
            }
        )
