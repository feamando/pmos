"""
PM-OS Brain Team Entity Schema

Schema for team and squad entities.
"""

from datetime import date
from typing import List, Optional

from pydantic import Field

from .entity import EntityBase, EntityType


class TeamEntity(EntityBase):
    """
    Team entity for PM-OS Brain.

    Represents organizational teams, tribes, or departments.
    """

    # Override type to be team
    type: EntityType = Field(
        default=EntityType.TEAM,
        alias="$type",
    )

    # Team-specific fields
    lead: Optional[str] = Field(
        default=None,
        description="Team lead (entity reference)",
        examples=["entity/person/jane-smith"],
    )

    members: List[str] = Field(
        default_factory=list,
        description="Team members (entity references)",
    )

    parent_team: Optional[str] = Field(
        default=None,
        description="Parent team/tribe (entity reference)",
        examples=["entity/team/cma"],
    )

    sub_teams: List[str] = Field(
        default_factory=list,
        description="Sub-teams or squads (entity references)",
    )

    # Organization context
    tribe: Optional[str] = Field(
        default=None,
        description="Tribe this team belongs to",
        examples=["Growth Division", "EA", "Tech Platform"],
    )

    department: Optional[str] = Field(
        default=None,
        description="Department",
        examples=["Product", "Engineering", "Design"],
    )

    # Scope
    focus_areas: List[str] = Field(
        default_factory=list,
        description="Areas of focus or responsibility",
    )

    projects: List[str] = Field(
        default_factory=list,
        description="Active projects (entity references)",
    )

    domains: List[str] = Field(
        default_factory=list,
        description="Technical domains owned",
    )

    # Communication
    slack_channel: Optional[str] = Field(
        default=None,
        description="Primary Slack channel",
        examples=["#team-growth-division", "#squad-meal-kit"],
    )

    meeting_cadence: Optional[str] = Field(
        default=None,
        description="Regular meeting schedule",
        examples=["Weekly standup Mon 10:00 CET", "Bi-weekly sync Thu 14:00 CET"],
    )

    # History
    formed_date: Optional[date] = Field(
        default=None,
        description="When the team was formed",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "$schema": "brain://entity/team/v1",
                    "$id": "entity/team/growth-division",
                    "$type": "team",
                    "$version": 3,
                    "$created": "2024-06-01T00:00:00Z",
                    "$updated": "2026-01-21T13:20:00Z",
                    "$confidence": 0.9,
                    "$source": "manual",
                    "$status": "active",
                    "$relationships": [
                        {
                            "type": "led_by",
                            "target": "entity/person/jane-smith",
                        },
                        {
                            "type": "part_of",
                            "target": "entity/team/cma",
                        },
                    ],
                    "$tags": ["product", "growth-division"],
                    "name": "Growth Division & Ecosystems",
                    "description": "Team responsible for new business ventures",
                    "lead": "entity/person/jane-smith",
                    "tribe": "Growth Division",
                    "department": "Product",
                    "focus_areas": ["Meal Kit", "BB", "Growth Platform"],
                    "slack_channel": "#team-growth-division",
                }
            ]
        }


class SquadEntity(EntityBase):
    """
    Squad entity for PM-OS Brain.

    Represents cross-functional squads working on specific products/features.
    """

    # Override type to be squad
    type: EntityType = Field(
        default=EntityType.SQUAD,
        alias="$type",
    )

    # Squad-specific fields
    product_manager: Optional[str] = Field(
        default=None,
        description="Product manager (entity reference)",
    )

    tech_lead: Optional[str] = Field(
        default=None,
        description="Technical lead (entity reference)",
    )

    engineering_manager: Optional[str] = Field(
        default=None,
        description="Engineering manager (entity reference)",
    )

    designer: Optional[str] = Field(
        default=None,
        description="Designer (entity reference)",
    )

    members: List[str] = Field(
        default_factory=list,
        description="Squad members (entity references)",
    )

    # Scope
    product: Optional[str] = Field(
        default=None,
        description="Primary product/project (entity reference)",
        examples=["entity/project/meal-kit"],
    )

    parent_team: Optional[str] = Field(
        default=None,
        description="Parent team (entity reference)",
    )

    focus_areas: List[str] = Field(
        default_factory=list,
        description="Current focus areas",
    )

    # Agile
    sprint_cadence: Optional[str] = Field(
        default=None,
        description="Sprint length",
        examples=["2 weeks", "1 week"],
    )

    jira_board: Optional[str] = Field(
        default=None,
        description="Jira board URL or key",
    )

    # Communication
    slack_channel: Optional[str] = Field(
        default=None,
        description="Squad Slack channel",
    )

    standup_time: Optional[str] = Field(
        default=None,
        description="Daily standup time",
        examples=["10:00 CET", "09:30 EST"],
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "$schema": "brain://entity/squad/v1",
                    "$id": "entity/squad/meal-kit",
                    "$type": "squad",
                    "$version": 2,
                    "$created": "2024-01-01T00:00:00Z",
                    "$updated": "2026-01-21T13:20:00Z",
                    "$confidence": 0.85,
                    "$source": "jira",
                    "$status": "active",
                    "name": "Meal Kit Squad",
                    "description": "Squad responsible for Meal Kit product",
                    "product_manager": "entity/person/beatrice-example",
                    "tech_lead": "entity/person/tushar-example",
                    "product": "entity/project/meal-kit",
                    "parent_team": "entity/team/growth-division",
                    "sprint_cadence": "2 weeks",
                    "slack_channel": "#squad-meal-kit",
                }
            ]
        }


# Factory functions
def create_team(
    name: str,
    lead: Optional[str] = None,
    tribe: Optional[str] = None,
    source: str = "manual",
) -> TeamEntity:
    """Factory function to create a new team entity."""
    from datetime import datetime

    entity_id = EntityBase.generate_id(EntityType.TEAM, name)
    schema_uri = EntityBase.generate_schema_uri(EntityType.TEAM)
    now = datetime.utcnow()

    return TeamEntity(
        **{
            "$schema": schema_uri,
            "$id": entity_id,
            "$type": EntityType.TEAM,
            "$version": 1,
            "$created": now,
            "$updated": now,
            "$source": source,
            "$confidence": 0.7 if source == "manual" else 0.5,
            "name": name,
            "lead": lead,
            "tribe": tribe,
        }
    )


def create_squad(
    name: str,
    product_manager: Optional[str] = None,
    tech_lead: Optional[str] = None,
    product: Optional[str] = None,
    source: str = "manual",
) -> SquadEntity:
    """Factory function to create a new squad entity."""
    from datetime import datetime

    entity_id = EntityBase.generate_id(EntityType.SQUAD, name)
    schema_uri = EntityBase.generate_schema_uri(EntityType.SQUAD)
    now = datetime.utcnow()

    return SquadEntity(
        **{
            "$schema": schema_uri,
            "$id": entity_id,
            "$type": EntityType.SQUAD,
            "$version": 1,
            "$created": now,
            "$updated": now,
            "$source": source,
            "$confidence": 0.7 if source == "manual" else 0.5,
            "name": name,
            "product_manager": product_manager,
            "tech_lead": tech_lead,
            "product": product,
        }
    )
