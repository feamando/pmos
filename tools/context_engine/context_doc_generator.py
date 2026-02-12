"""
Context Document Generator - v1 Draft Generation

Generates a context document v1 draft from feature information and optional
enriched insight/signal data. The document follows a standardized template
for consistency across features.

Output Location:
    {feature-folder}/context-docs/v1-draft.md

Template Sections:
    - Problem Statement (from insight or placeholder)
    - Success Metrics (suggested based on product type)
    - Scope (In/Out placeholders)
    - Stakeholders (from Brain/product config)
    - User Stories (generated if insight provided)
    - Technical Considerations (placeholder)
    - Risks and Mitigations (placeholder)
    - Open Questions (placeholder for orthogonal challenge)

Usage:
    from tools.context_engine import ContextDocGenerator

    generator = ContextDocGenerator()

    # Generate from feature state
    result = generator.generate_v1(
        feature_path=Path("/path/to/feature"),
        insight={"problem": "Users abandon checkout...", "evidence": [...]}
    )

    # Or generate with explicit feature info
    result = generator.generate_v1_from_info(
        feature_title="OTP Checkout Recovery",
        product_id="meal-kit",
        product_name="Meal Kit",
        feature_path=Path("/path/to/feature"),
        insight={"problem": "...", "user_segments": [...]}
    )

Author: PM-OS Team
Version: 1.0.0
"""

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class ContextDocResult:
    """
    Result of context document generation.

    Attributes:
        success: Whether generation succeeded
        file_path: Path to the generated document
        version: Document version (1 for v1-draft)
        message: Human-readable result message
        sections_populated: Which sections have real content vs placeholders
    """

    success: bool
    file_path: Optional[Path] = None
    version: int = 1
    message: str = ""
    sections_populated: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "file_path": str(self.file_path) if self.file_path else None,
            "version": self.version,
            "message": self.message,
            "sections_populated": self.sections_populated,
        }


@dataclass
class InsightData:
    """
    Enriched insight/signal data for context doc generation.

    Attributes:
        problem: Problem statement from the insight
        evidence: Supporting evidence (Slack messages, data points, etc.)
        user_segments: Affected user segments
        impact: Estimated impact description
        sources: Where the insight came from
        related_features: Related existing features
    """

    problem: str = ""
    evidence: List[str] = field(default_factory=list)
    user_segments: List[str] = field(default_factory=list)
    impact: str = ""
    sources: List[str] = field(default_factory=list)
    related_features: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InsightData":
        """Create InsightData from dictionary."""
        return cls(
            problem=data.get("problem", ""),
            evidence=data.get("evidence", []),
            user_segments=data.get("user_segments", []),
            impact=data.get("impact", ""),
            sources=data.get("sources", []),
            related_features=data.get("related_features", []),
        )


# Default success metrics templates by product type
DEFAULT_METRICS_BY_TYPE = {
    "brand": [
        "Conversion rate improvement",
        "User satisfaction score (NPS/CSAT)",
        "Feature adoption rate",
        "Support ticket reduction",
    ],
    "product": [
        "Monthly active users (MAU)",
        "Feature engagement rate",
        "Task completion rate",
        "Time to value",
    ],
    "feature": [
        "Feature adoption rate",
        "Task success rate",
        "Error rate reduction",
        "User satisfaction",
    ],
    "project": [
        "Project completion on time",
        "Stakeholder satisfaction",
        "Deliverable quality score",
        "Budget adherence",
    ],
}


class ContextDocGenerator:
    """
    Generates context document v1 drafts from feature information and insights.

    The generator creates standardized context documents that serve as the
    foundation for feature development. Documents include problem statements,
    success metrics, scope, stakeholders, and user stories.
    """

    def __init__(self, user_path: Optional[Path] = None):
        """
        Initialize the context document generator.

        Args:
            user_path: Path to user/ directory. If None, auto-detected.
        """
        import config_loader

        self._config = config_loader.get_config()
        self._user_path = user_path or Path(self._config.user_path)
        self._raw_config = self._config.config

    def _get_user_info(self) -> Dict[str, str]:
        """Get user information from config."""
        user_config = self._raw_config.get("user", {})
        return {
            "name": user_config.get("name", "PM"),
            "email": user_config.get("email", ""),
            "position": user_config.get("position", "Product Manager"),
        }

    def _get_product_info(self, product_id: str) -> Dict[str, Any]:
        """
        Get product information from config.

        Args:
            product_id: Product ID (e.g., "meal-kit")

        Returns:
            Product configuration dict or empty dict if not found
        """
        products_config = self._raw_config.get("products", {})
        items = products_config.get("items", [])

        for product in items:
            if product.get("id") == product_id:
                return product
        return {}

    def _get_stakeholders(self, product_id: str) -> List[Dict[str, str]]:
        """
        Get stakeholders for a product from config.

        Args:
            product_id: Product ID

        Returns:
            List of stakeholder dicts with name, role, responsibility
        """
        stakeholders = []
        user_info = self._get_user_info()
        product_info = self._get_product_info(product_id)

        # Add owner (current user)
        stakeholders.append(
            {
                "role": "Owner",
                "name": user_info["name"],
                "responsibility": "Overall accountability",
            }
        )

        # Add squad lead if available from team config
        team_config = self._raw_config.get("team", {})
        squad_name = product_info.get("squad", "")

        # Find reports that match the squad
        reports = team_config.get("reports", [])
        for report in reports:
            if report.get("squad") == squad_name:
                stakeholders.append(
                    {
                        "role": "Product Lead",
                        "name": report.get("name", ""),
                        "responsibility": f"Product decisions for {squad_name}",
                    }
                )
                break

        # Add engineering partner if configured
        eng_stakeholders = team_config.get("stakeholders", [])
        for stakeholder in eng_stakeholders:
            if stakeholder.get("relationship") == "leadership_partner":
                if "Engineering" in stakeholder.get("role", ""):
                    stakeholders.append(
                        {
                            "role": "Engineering Lead",
                            "name": stakeholder.get("name", ""),
                            "responsibility": "Technical feasibility and implementation",
                        }
                    )
                    break

        return stakeholders

    def _get_suggested_metrics(
        self, product_type: str = "brand", insight: Optional[InsightData] = None
    ) -> List[str]:
        """
        Get suggested success metrics based on product type and insight.

        Args:
            product_type: Type of product (brand, product, feature, project)
            insight: Optional insight data for context-specific metrics

        Returns:
            List of suggested metric strings
        """
        base_metrics = DEFAULT_METRICS_BY_TYPE.get(
            product_type, DEFAULT_METRICS_BY_TYPE["brand"]
        )

        # If insight has impact data, add specific metric suggestions
        if insight and insight.impact:
            # Add impact-based metric at the top
            return [f"Impact metric: {insight.impact}"] + base_metrics[:3]

        return base_metrics

    def _generate_user_stories(
        self, insight: Optional[InsightData] = None, feature_title: str = ""
    ) -> str:
        """
        Generate user stories section from insight data.

        Args:
            insight: Optional insight data with user segments
            feature_title: Feature title for context

        Returns:
            Markdown formatted user stories section
        """
        if not insight or not insight.user_segments:
            return """*User stories will be generated during context refinement.*

Example format:
- As a [user type], I want to [action] so that [benefit]
"""

        stories = []
        for segment in insight.user_segments[:5]:  # Limit to 5 segments
            # Generate a basic user story template for each segment
            stories.append(
                f"- As a **{segment}**, I want to [action TBD] "
                f"so that [benefit TBD]"
            )

        return (
            "\n".join(stories)
            + "\n\n*Refine these user stories during context iteration.*"
        )

    def _generate_problem_statement(
        self, insight: Optional[InsightData] = None, feature_title: str = ""
    ) -> str:
        """
        Generate problem statement from insight or placeholder.

        Args:
            insight: Optional insight data with problem description
            feature_title: Feature title for context

        Returns:
            Problem statement text
        """
        if insight and insight.problem:
            statement = insight.problem

            # Add evidence if available
            if insight.evidence:
                statement += "\n\n**Supporting Evidence:**\n"
                for evidence in insight.evidence[:5]:  # Limit evidence items
                    statement += f"- {evidence}\n"

            # Add sources if available
            if insight.sources:
                statement += "\n**Sources:** " + ", ".join(insight.sources)

            return statement

        return f"""*Define the problem that "{feature_title}" will solve.*

Consider:
- Who is affected by this problem?
- What is the current state vs. desired state?
- What evidence supports this problem exists?
- What is the cost of not solving it?
"""

    def generate_v1(
        self, feature_path: Path, insight: Optional[Dict[str, Any]] = None
    ) -> ContextDocResult:
        """
        Generate a v1 context document for an existing feature.

        Reads feature-state.yaml to get feature info and generates
        the context document at {feature-path}/context-docs/v1-draft.md.

        Args:
            feature_path: Path to the feature folder
            insight: Optional dict with insight/signal data

        Returns:
            ContextDocResult with generation outcome
        """
        from .feature_state import FeatureState, TrackStatus

        # Load feature state
        state = FeatureState.load(feature_path)
        if not state:
            return ContextDocResult(
                success=False,
                message=f"Feature state not found at {feature_path}/feature-state.yaml",
            )

        # Get product info
        product_info = self._get_product_info(state.product_id)
        product_name = product_info.get("name", state.product_id)
        product_type = product_info.get("type", "brand")

        # Parse insight data if provided
        insight_data = InsightData.from_dict(insight) if insight else None

        # Generate the document
        result = self.generate_v1_from_info(
            feature_title=state.title,
            product_id=state.product_id,
            product_name=product_name,
            product_type=product_type,
            feature_path=feature_path,
            insight=insight_data,
        )

        if result.success:
            # Update feature state with context track status
            state.update_track(
                "context",
                status=TrackStatus.IN_PROGRESS,
                current_version=1,
                current_step="v1_draft",
                file="context-docs/v1-draft.md",
            )
            state.save(feature_path)

        return result

    def generate_v1_from_info(
        self,
        feature_title: str,
        product_id: str,
        product_name: str,
        feature_path: Path,
        product_type: str = "brand",
        insight: Optional[InsightData] = None,
    ) -> ContextDocResult:
        """
        Generate a v1 context document from explicit feature information.

        Args:
            feature_title: Feature title
            product_id: Product ID
            product_name: Product display name
            feature_path: Path to feature folder
            product_type: Product type (brand, product, feature, project)
            insight: Optional InsightData with enriched signal

        Returns:
            ContextDocResult with generation outcome
        """
        # Ensure context-docs directory exists
        context_docs_dir = feature_path / "context-docs"
        context_docs_dir.mkdir(parents=True, exist_ok=True)

        # Get current date
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")

        # Get stakeholders
        stakeholders = self._get_stakeholders(product_id)

        # Get suggested metrics
        metrics = self._get_suggested_metrics(product_type, insight)

        # Generate sections
        problem_statement = self._generate_problem_statement(insight, feature_title)
        user_stories = self._generate_user_stories(insight, feature_title)

        # Track which sections have real content
        sections_populated = {
            "problem_statement": insight is not None and bool(insight.problem),
            "success_metrics": False,  # Always placeholder in v1
            "scope": False,  # Always placeholder in v1
            "stakeholders": len(stakeholders) > 1,  # More than just owner
            "user_stories": insight is not None and bool(insight.user_segments),
            "technical_considerations": False,
            "risks": False,
            "open_questions": False,
        }

        # Build stakeholders table
        stakeholders_table = (
            "| Role | Name | Responsibility |\n|------|------|----------------|\n"
        )
        for s in stakeholders:
            stakeholders_table += (
                f"| {s['role']} | {s['name']} | {s['responsibility']} |\n"
            )

        # Build metrics checklist
        metrics_checklist = ""
        for metric in metrics:
            metrics_checklist += f"- [ ] {metric}\n"

        # Generate slug from feature path
        feature_slug = feature_path.name

        # Generate the document content
        content = f"""# Context Document: {feature_title}

**Slug:** `{feature_slug}`
**Version:** 1 (Draft)
**Status:** Pending Review
**Created:** {date_str}
**Product:** {product_name}

## Problem Statement

{problem_statement}

## Success Metrics

{metrics_checklist}
*Metrics to be refined during context iteration.*

## Scope

### In Scope

- TBD

### Out of Scope

- TBD

## Stakeholders

{stakeholders_table}

## User Stories

{user_stories}

## Technical Considerations

- TBD
- *Technical considerations will be identified during engineering review.*

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| *Identify during context refinement* | - | - | - |

## Open Questions

1. *Questions from orthogonal challenge will go here*

---
*Generated by Context Creation Engine | Ready for orthogonal challenge*
"""

        # Write the document
        output_path = context_docs_dir / "v1-draft.md"
        try:
            output_path.write_text(content)
        except (IOError, OSError) as e:
            return ContextDocResult(
                success=False, message=f"Failed to write context document: {e}"
            )

        return ContextDocResult(
            success=True,
            file_path=output_path,
            version=1,
            message=f"Context document v1 generated at {output_path}",
            sections_populated=sections_populated,
        )

    def get_document_path(self, feature_path: Path, version: int = 1) -> Path:
        """
        Get the path to a context document version.

        Args:
            feature_path: Path to feature folder
            version: Document version number

        Returns:
            Path to the document
        """
        version_map = {
            1: "v1-draft.md",
            2: "v2-revised.md",
            3: "v3-final.md",
        }
        filename = version_map.get(version, f"v{version}-draft.md")
        return feature_path / "context-docs" / filename

    def document_exists(self, feature_path: Path, version: int = 1) -> bool:
        """
        Check if a context document version exists.

        Args:
            feature_path: Path to feature folder
            version: Document version number

        Returns:
            True if document exists
        """
        return self.get_document_path(feature_path, version).exists()
