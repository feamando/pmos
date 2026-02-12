"""
PM-OS Brain Person Entity Schema

Schema for person entities (team members, stakeholders, etc.).
"""

from datetime import date
from typing import List, Optional

from pydantic import Field

from .entity import EntityBase, EntityType


class PersonEntity(EntityBase):
    """
    Person entity for PM-OS Brain.

    Extends EntityBase with person-specific fields like role,
    team affiliation, expertise, and communication preferences.
    """

    # Override type to be person
    type: EntityType = Field(
        default=EntityType.PERSON,
        alias="$type",
    )

    # Person-specific fields
    role: Optional[str] = Field(
        default=None,
        description="Job title or role",
        examples=["Director of Product", "Senior Engineer", "Product Manager"],
    )

    email: Optional[str] = Field(
        default=None,
        description="Email address",
    )

    team: Optional[str] = Field(
        default=None,
        description="Primary team affiliation (entity reference)",
        examples=["entity/team/growth-division", "entity/squad/meal-kit"],
    )

    tribe: Optional[str] = Field(
        default=None,
        description="Tribe or organization unit",
        examples=["Growth Division", "EA", "Tech Platform"],
    )

    manager: Optional[str] = Field(
        default=None,
        description="Direct manager (entity reference)",
        examples=["entity/person/holger-hammel"],
    )

    direct_reports: List[str] = Field(
        default_factory=list,
        description="List of direct reports (entity references)",
    )

    location: Optional[str] = Field(
        default=None,
        description="Office location or timezone",
        examples=["Berlin", "Amsterdam", "Remote - CET"],
    )

    start_date: Optional[date] = Field(
        default=None,
        description="When they joined the organization",
    )

    expertise: List[str] = Field(
        default_factory=list,
        description="Areas of expertise",
        examples=[["product management", "mobile apps", "growth"]],
    )

    projects: List[str] = Field(
        default_factory=list,
        description="Current projects (entity references)",
    )

    # Communication preferences
    slack_handle: Optional[str] = Field(
        default=None,
        description="Slack handle (without @)",
    )

    preferred_contact: Optional[str] = Field(
        default=None,
        description="Preferred contact method",
        examples=["slack", "email", "meeting"],
    )

    timezone: Optional[str] = Field(
        default=None,
        description="Primary timezone",
        examples=["Europe/Berlin", "America/New_York"],
    )

    # Notes
    working_style: Optional[str] = Field(
        default=None,
        description="Notes on communication/working style preferences",
    )

    current_focus: Optional[str] = Field(
        default=None,
        description="Current focus areas or priorities",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "$schema": "brain://entity/person/v1",
                    "$id": "entity/person/jane-smith",
                    "$type": "person",
                    "$version": 1,
                    "$created": "2025-07-01T00:00:00Z",
                    "$updated": "2026-01-21T13:20:00Z",
                    "$confidence": 0.95,
                    "$source": "hr_system",
                    "$status": "active",
                    "$relationships": [
                        {
                            "type": "reports_to",
                            "target": "entity/person/holger-hammel",
                            "since": "2024-06-01",
                        },
                        {
                            "type": "leads",
                            "target": "entity/team/growth-division",
                            "since": "2024-06-01",
                        },
                    ],
                    "$tags": ["leadership", "product", "growth-division"],
                    "$aliases": ["jane", "jane.smith", "Jane Smith"],
                    "name": "Jane Smith",
                    "description": "Director of Product, Growth Division & Ecosystems",
                    "role": "Director of Product",
                    "email": "user@example.com",
                    "team": "entity/team/growth-division",
                    "tribe": "Growth Division",
                    "manager": "entity/person/holger-hammel",
                    "location": "Berlin",
                    "expertise": ["product management", "mobile apps", "new ventures"],
                    "slack_handle": "jane.smith",
                    "timezone": "Europe/Berlin",
                    "current_focus": "Leading Meal Kit, WB, Growth Platform, Product Innovation",
                }
            ]
        }

    @classmethod
    def create(
        cls,
        name: str,
        role: Optional[str] = None,
        email: Optional[str] = None,
        team: Optional[str] = None,
        source: str = "manual",
    ) -> "PersonEntity":
        """Factory method to create a new person entity."""
        from datetime import datetime

        entity_id = cls.generate_id(EntityType.PERSON, name)
        schema_uri = cls.generate_schema_uri(EntityType.PERSON)
        now = datetime.utcnow()

        return cls(
            **{
                "$schema": schema_uri,
                "$id": entity_id,
                "$type": EntityType.PERSON,
                "$version": 1,
                "$created": now,
                "$updated": now,
                "$source": source,
                "$confidence": 0.7 if source == "manual" else 0.5,
                "name": name,
                "role": role,
                "email": email,
                "team": team,
            }
        )
