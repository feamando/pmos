"""
PM-OS Brain Relationship Schema

Defines typed relationships between entities with temporal tracking.
"""

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RelationshipType(str, Enum):
    """Common relationship types (extensible via freeform strings)."""

    # Organizational
    REPORTS_TO = "reports_to"
    MANAGES = "manages"
    MEMBER_OF = "member_of"
    LEADS = "leads"

    # Ownership
    OWNS = "owns"
    OWNED_BY = "owned_by"
    MAINTAINS = "maintains"

    # Collaboration
    WORKS_WITH = "works_with"
    COLLABORATES_WITH = "collaborates_with"
    STAKEHOLDER_OF = "stakeholder_of"

    # Dependencies
    DEPENDS_ON = "depends_on"
    BLOCKS = "blocks"
    RELATED_TO = "related_to"

    # Hierarchy
    PARENT_OF = "parent_of"
    CHILD_OF = "child_of"
    PART_OF = "part_of"


class Relationship(BaseModel):
    """
    A typed relationship between two entities.

    Relationships are stored on entities and support temporal tracking
    to know when relationships started/ended.

    TKS Enhancement (bd-2ac6): Added confidence and last_verified for
    relationship quality tracking with temporal decay.
    """

    type: str = Field(
        ...,
        description="Relationship type (can be RelationshipType enum or freeform string)",
        examples=["reports_to", "owns", "member_of", "custom_relationship"],
    )

    target: str = Field(
        ...,
        description="Target entity $id (e.g., 'entity/person/john-doe')",
        examples=["entity/person/holger-hammel", "entity/team/growth-division"],
    )

    since: Optional[date] = Field(
        default=None,
        description="When this relationship started",
    )

    until: Optional[date] = Field(
        default=None,
        description="When this relationship ended (null = current)",
    )

    role: Optional[str] = Field(
        default=None,
        description="Optional role context (e.g., 'product_lead', 'tech_lead')",
        examples=["product_lead", "contributor", "stakeholder"],
    )

    # TKS-derived fields for relationship quality (bd-2ac6)
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Relationship confidence score [0,1]. Decays over time if not verified.",
    )

    last_verified: Optional[date] = Field(
        default=None,
        description="When this relationship was last verified accurate",
    )

    source: Optional[str] = Field(
        default=None,
        description="Source of relationship (hr_system, jira, slack, manual, auto_embedding)",
        examples=["hr_system", "jira", "manual", "auto_embedding"],
    )

    metadata: Optional[dict] = Field(
        default=None,
        description="Additional relationship metadata",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "reports_to",
                    "target": "entity/person/holger-hammel",
                    "since": "2024-06-01",
                },
                {
                    "type": "owns",
                    "target": "entity/project/meal-kit",
                    "role": "product_lead",
                    "since": "2024-01-01",
                },
            ]
        }

    def is_active(self, as_of: Optional[date] = None) -> bool:
        """Check if relationship is active as of a given date."""
        check_date = as_of or date.today()

        if self.since and check_date < self.since:
            return False
        if self.until and check_date > self.until:
            return False
        return True

    def get_inverse_type(self) -> Optional[str]:
        """Get the inverse relationship type if known."""
        inverses = {
            RelationshipType.REPORTS_TO.value: RelationshipType.MANAGES.value,
            RelationshipType.MANAGES.value: RelationshipType.REPORTS_TO.value,
            RelationshipType.OWNS.value: RelationshipType.OWNED_BY.value,
            RelationshipType.OWNED_BY.value: RelationshipType.OWNS.value,
            RelationshipType.PARENT_OF.value: RelationshipType.CHILD_OF.value,
            RelationshipType.CHILD_OF.value: RelationshipType.PARENT_OF.value,
            RelationshipType.BLOCKS.value: RelationshipType.DEPENDS_ON.value,
            RelationshipType.DEPENDS_ON.value: RelationshipType.BLOCKS.value,
            RelationshipType.LEADS.value: RelationshipType.MEMBER_OF.value,
        }
        return inverses.get(self.type)

    def compute_decayed_confidence(
        self,
        as_of: Optional[date] = None,
        decay_rate: float = 0.01,
        floor: float = 0.3,
    ) -> float:
        """
        Compute confidence with temporal decay (TKS bd-2ac6).

        Formula: conf(t) = max(floor, base × (1 - decay_rate × weeks_stale))

        Args:
            as_of: Date to compute confidence for (default: today)
            decay_rate: Decay per week (default: 0.01 = 1% per week)
            floor: Minimum confidence floor (default: 0.3)

        Returns:
            Decayed confidence in [floor, base_confidence]
        """
        check_date = as_of or date.today()
        base = self.confidence

        # If no last_verified, use since date or assume stale
        reference_date = self.last_verified or self.since
        if not reference_date:
            # No verification date - apply moderate decay
            return max(floor, base * 0.7)

        days_stale = (check_date - reference_date).days
        if days_stale <= 0:
            return base

        weeks_stale = days_stale / 7
        decay = decay_rate * weeks_stale
        decayed = base * (1 - decay)

        return max(floor, min(base, decayed))

    def is_stale(
        self,
        as_of: Optional[date] = None,
        threshold_days: int = 90,
    ) -> bool:
        """
        Check if relationship is stale (needs re-verification).

        Args:
            as_of: Date to check staleness against
            threshold_days: Days without verification before considered stale

        Returns:
            True if relationship needs re-verification
        """
        check_date = as_of or date.today()
        reference_date = self.last_verified or self.since

        if not reference_date:
            return True  # No date = stale

        days_since = (check_date - reference_date).days
        return days_since > threshold_days
