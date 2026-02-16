"""
Jira Integration Module - Context Engine to Jira Epic Creation

Creates Jira epics from context engine features, links all artifacts,
and creates child stories from ADRs/engineering estimates.

This module provides:
- Epic creation from feature data (title, description from context)
- Artifact linking (Figma, Confluence, ADRs)
- Child story creation from ADRs
- Dry-run mode for previewing changes
- feature-state.yaml update with created epic key

Usage:
    from tools.context_engine.jira_integration import JiraEpicCreator

    creator = JiraEpicCreator()

    # Create epic with all artifacts linked
    result = creator.create_epic_from_feature(
        feature_path=Path("/path/to/feature"),
        dry_run=False
    )

    # Preview what would be created
    preview = creator.create_epic_from_feature(
        feature_path=Path("/path/to/feature"),
        dry_run=True
    )

Author: PM-OS Team
Version: 1.0.0
PRD: Context Creation Engine Integration
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .feature_state import FeatureState
from .tracks.engineering import ADRStatus, EngineeringTrack


class JiraIntegrationError(Exception):
    """Base exception for Jira integration errors."""

    pass


class JiraConfigError(JiraIntegrationError):
    """Raised when Jira configuration is missing or invalid."""

    pass


class JiraApiError(JiraIntegrationError):
    """Raised when Jira API calls fail."""

    pass


class StorySize(Enum):
    """Maps T-shirt sizes to story points."""

    XS = 1
    S = 2
    M = 3
    L = 5
    XL = 8


@dataclass
class LinkedArtifact:
    """Represents an artifact to be linked to the epic."""

    artifact_type: str  # figma, confluence, adr, wireframe
    title: str
    url: str
    description: Optional[str] = None


@dataclass
class StoryData:
    """Data for creating a child story from ADR."""

    title: str
    description: str
    estimate_size: str
    adr_number: Optional[int] = None
    labels: List[str] = field(default_factory=list)


@dataclass
class EpicCreationResult:
    """Result of epic creation operation."""

    success: bool
    epic_key: Optional[str] = None
    epic_url: Optional[str] = None
    stories_created: List[Dict[str, Any]] = field(default_factory=list)
    artifacts_linked: List[Dict[str, Any]] = field(default_factory=list)
    message: str = ""
    errors: List[str] = field(default_factory=list)
    dry_run: bool = False

    # Dry run preview data
    epic_preview: Optional[Dict[str, Any]] = None
    stories_preview: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for reporting."""
        result = {
            "success": self.success,
            "epic_key": self.epic_key,
            "epic_url": self.epic_url,
            "stories_created": self.stories_created,
            "artifacts_linked": self.artifacts_linked,
            "message": self.message,
            "errors": self.errors,
            "dry_run": self.dry_run,
        }
        if self.dry_run:
            result["epic_preview"] = self.epic_preview
            result["stories_preview"] = self.stories_preview
        return result


class JiraEpicCreator:
    """
    Creates Jira epics from context engine features.

    This class handles the complete workflow of:
    1. Creating an epic from feature data
    2. Linking all associated artifacts
    3. Creating child stories from ADRs
    4. Updating feature-state.yaml with the epic key
    """

    def __init__(self, user_path: Optional[Path] = None):
        """
        Initialize the Jira epic creator.

        Args:
            user_path: Path to user/ directory. If None, auto-detected.
        """
        import config_loader

        self._config = config_loader.get_config()
        self._user_path = user_path or Path(self._config.user_path)
        self._jira_config = config_loader.get_jira_config()
        self._jira_client = None

    def _get_jira_client(self):
        """
        Get or create Jira client.

        Returns:
            Jira client instance

        Raises:
            JiraConfigError: If Jira configuration is missing
        """
        if self._jira_client is not None:
            return self._jira_client

        try:
            from atlassian import Jira
        except ImportError:
            raise JiraConfigError(
                "atlassian-python-api not installed. "
                "Install with: pip install atlassian-python-api"
            )

        url = self._jira_config.get("url")
        username = self._jira_config.get("username")
        api_token = self._jira_config.get("api_token")

        if not all([url, username, api_token]):
            missing = []
            if not url:
                missing.append("JIRA_URL")
            if not username:
                missing.append("JIRA_USERNAME")
            if not api_token:
                missing.append("JIRA_API_TOKEN")
            raise JiraConfigError(
                f"Jira configuration missing: {', '.join(missing)}. "
                "Set these in .env file."
            )

        self._jira_client = Jira(
            url=url, username=username, password=api_token, cloud=True
        )

        return self._jira_client

    def _get_project_key(self, state: FeatureState) -> str:
        """
        Get Jira project key from feature state or product config.

        Args:
            state: Feature state

        Returns:
            Jira project key (e.g., 'MK')

        Raises:
            JiraConfigError: If project key cannot be determined
        """
        import config_loader

        # Try to get from product config
        product = config_loader.get_product_by_id(state.product_id)
        if product and product.get("jira_project"):
            return product["jira_project"]

        # Fallback: derive from product_id
        # Common patterns: meal-kit -> MK, brand-b -> BB
        product_id = state.product_id.upper()
        if "-" in product_id:
            parts = product_id.split("-")
            # Take first letter of each part
            project_key = "".join(p[0] for p in parts if p)
            if len(project_key) >= 2:
                return project_key

        raise JiraConfigError(
            f"Cannot determine Jira project key for product: {state.product_id}. "
            "Configure jira_project in config.yaml products section."
        )

    def _extract_description(self, feature_path: Path, state: FeatureState) -> str:
        """
        Extract description from context document for epic.

        Args:
            feature_path: Path to feature folder
            state: Feature state

        Returns:
            Description text for Jira epic
        """
        description_parts = []

        # Try to read context document
        context_doc = feature_path / state.context_file
        if not context_doc.exists():
            # Try context-docs folder for latest version
            context_docs_dir = feature_path / "context-docs"
            if context_docs_dir.exists():
                versions = sorted(context_docs_dir.glob("v*-final.md"), reverse=True)
                if versions:
                    context_doc = versions[0]
                else:
                    versions = sorted(context_docs_dir.glob("v*.md"), reverse=True)
                    if versions:
                        context_doc = versions[0]

        if context_doc.exists():
            import re

            doc_text = context_doc.read_text()

            # Extract problem statement / description
            desc_match = re.search(
                r"## (?:Description|Problem Statement)\n+(.*?)(?=\n## |\Z)",
                doc_text,
                re.DOTALL,
            )
            if desc_match:
                problem_text = desc_match.group(1).strip()
                description_parts.append("*Problem Statement:*")
                description_parts.append(problem_text[:1500])  # Limit length

            # Extract scope summary
            scope_match = re.search(
                r"## Scope\n+(.*?)(?=\n## |\Z)", doc_text, re.DOTALL
            )
            if scope_match:
                scope_text = scope_match.group(1).strip()[:800]
                description_parts.append("")
                description_parts.append("*Scope:*")
                description_parts.append(scope_text)

        # Add business case summary if available
        bc_dir = feature_path / "business-case"
        if bc_dir.exists():
            bc_files = sorted(bc_dir.glob("bc-v*-approved.md"), reverse=True)
            if not bc_files:
                bc_files = sorted(bc_dir.glob("bc-v*.md"), reverse=True)

            if bc_files:
                import re

                bc_text = bc_files[0].read_text()
                exec_match = re.search(
                    r"## Executive Summary\n+(.*?)(?=\n## |\Z)", bc_text, re.DOTALL
                )
                if exec_match:
                    exec_summary = exec_match.group(1).strip()[:500]
                    description_parts.append("")
                    description_parts.append("*Business Case Summary:*")
                    description_parts.append(exec_summary)

        if not description_parts:
            description_parts.append(f"Feature: {state.title}")
            description_parts.append(f"Product: {state.product_id}")
            description_parts.append("")
            description_parts.append(
                "_See context-engine feature folder for full details._"
            )

        # Add footer with source info
        description_parts.append("")
        description_parts.append("---")
        description_parts.append(
            f"_Created by Context Engine from feature: {state.slug}_"
        )

        return "\n".join(description_parts)

    def _collect_artifacts(
        self, feature_path: Path, state: FeatureState
    ) -> List[LinkedArtifact]:
        """
        Collect all artifacts to link to the epic.

        Args:
            feature_path: Path to feature folder
            state: Feature state

        Returns:
            List of artifacts to link
        """
        artifacts = []

        # Figma link
        if state.artifacts.get("figma"):
            artifacts.append(
                LinkedArtifact(
                    artifact_type="figma",
                    title=f"Figma: {state.title}",
                    url=state.artifacts["figma"],
                    description="Design files for this feature",
                )
            )

        # Confluence page
        if state.artifacts.get("confluence_page"):
            artifacts.append(
                LinkedArtifact(
                    artifact_type="confluence",
                    title=f"Confluence: {state.title}",
                    url=state.artifacts["confluence_page"],
                    description="Confluence documentation",
                )
            )

        # Wireframes
        if state.artifacts.get("wireframes_url"):
            artifacts.append(
                LinkedArtifact(
                    artifact_type="wireframe",
                    title=f"Wireframes: {state.title}",
                    url=state.artifacts["wireframes_url"],
                    description="Wireframe designs",
                )
            )

        # ADR files - create links to them if they have URLs
        eng_track = EngineeringTrack(feature_path)
        for adr in eng_track.adrs:
            if adr.status in (ADRStatus.PROPOSED, ADRStatus.ACCEPTED):
                # ADRs don't have URLs, but we'll reference them in the story
                # Still useful to track which ADRs exist
                adr_path = (
                    feature_path / "engineering" / "adrs" / f"adr-{adr.number:03d}-*.md"
                )
                adr_files = list(
                    feature_path.glob(f"engineering/adrs/adr-{adr.number:03d}-*.md")
                )
                if adr_files:
                    artifacts.append(
                        LinkedArtifact(
                            artifact_type="adr",
                            title=f"ADR-{adr.number:03d}: {adr.title}",
                            url=str(adr_files[0]),  # Local path
                            description=adr.context[:200],
                        )
                    )

        return artifacts

    def _generate_stories_from_adrs(
        self, feature_path: Path, state: FeatureState
    ) -> List[StoryData]:
        """
        Generate story data from ADRs.

        Each accepted ADR becomes a potential story that implements
        the architectural decision.

        Args:
            feature_path: Path to feature folder
            state: Feature state

        Returns:
            List of StoryData for creating stories
        """
        stories = []
        eng_track = EngineeringTrack(feature_path)

        # Get overall estimate for sizing stories
        overall_estimate = "M"  # Default
        if eng_track.estimate:
            overall_estimate = eng_track.estimate.overall

        for adr in eng_track.adrs:
            if adr.status not in (ADRStatus.PROPOSED, ADRStatus.ACCEPTED):
                continue

            # Create story from ADR
            story = StoryData(
                title=f"[{state.slug}] Implement ADR-{adr.number:03d}: {adr.title}",
                description=self._format_adr_story_description(adr),
                estimate_size=overall_estimate,  # Use overall estimate
                adr_number=adr.number,
                labels=["context-engine", "adr-implementation"],
            )
            stories.append(story)

        # If no ADRs, create a single implementation story
        if not stories and eng_track.estimate:
            stories.append(
                StoryData(
                    title=f"[{state.slug}] Implementation",
                    description=self._format_implementation_story_description(
                        state, eng_track
                    ),
                    estimate_size=eng_track.estimate.overall,
                    labels=["context-engine"],
                )
            )

        return stories

    def _format_adr_story_description(self, adr) -> str:
        """Format ADR content as story description."""
        lines = [
            f"*ADR-{adr.number:03d}: {adr.title}*",
            "",
            "h3. Context",
            adr.context[:1000],
            "",
            "h3. Decision",
            adr.decision[:1000],
            "",
            "h3. Consequences",
            adr.consequences[:500],
            "",
            "---",
            f"_Status: {adr.status.value}_",
            f"_Created by: {adr.created_by}_",
        ]
        return "\n".join(lines)

    def _format_implementation_story_description(
        self, state: FeatureState, eng_track: EngineeringTrack
    ) -> str:
        """Format generic implementation story description."""
        lines = [
            f"*Feature: {state.title}*",
            "",
            "Implement the feature as specified in the context document.",
            "",
        ]

        if eng_track.estimate:
            lines.append("h3. Estimate")
            lines.append(f"Overall: {eng_track.estimate.overall}")
            if eng_track.estimate.breakdown:
                for component, size in eng_track.estimate.breakdown.items():
                    lines.append(f"- {component}: {size}")
            if eng_track.estimate.assumptions:
                lines.append("")
                lines.append("h3. Assumptions")
                for assumption in eng_track.estimate.assumptions:
                    lines.append(f"- {assumption}")

        if eng_track.risks:
            lines.append("")
            lines.append("h3. Risks")
            for risk in eng_track.risks[:5]:
                lines.append(
                    f"- {risk.risk} "
                    f"(Impact: {risk.impact}, Likelihood: {risk.likelihood})"
                )

        return "\n".join(lines)

    def _estimate_to_story_points(self, estimate: str) -> Optional[int]:
        """Convert T-shirt size to story points."""
        mapping = {
            "XS": 1,
            "S": 2,
            "M": 3,
            "L": 5,
            "XL": 8,
        }
        return mapping.get(estimate.upper())

    def create_epic(
        self,
        project_key: str,
        title: str,
        description: str,
        labels: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a Jira epic.

        Args:
            project_key: Jira project key
            title: Epic title
            description: Epic description
            labels: Optional labels
            dry_run: If True, return preview without creating

        Returns:
            Dictionary with epic key, url, or preview data
        """
        if dry_run:
            return {
                "dry_run": True,
                "project_key": project_key,
                "title": title,
                "description": (
                    description[:500] + "..." if len(description) > 500 else description
                ),
                "labels": labels or ["context-engine"],
            }

        jira = self._get_jira_client()

        # Create epic
        epic_data = {
            "project": {"key": project_key},
            "summary": title,
            "description": description,
            "issuetype": {"name": "Epic"},
            "labels": labels or ["context-engine"],
        }

        try:
            result = jira.create_issue(fields=epic_data)
            epic_key = result.get("key")

            return {
                "key": epic_key,
                "url": f"{self._jira_config['url']}/browse/{epic_key}",
                "id": result.get("id"),
            }
        except Exception as e:
            raise JiraApiError(f"Failed to create epic: {e}")

    def link_artifact(
        self, epic_key: str, artifact: LinkedArtifact, dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Link an artifact to an epic via remote link.

        Args:
            epic_key: Jira epic key
            artifact: Artifact to link
            dry_run: If True, return preview without linking

        Returns:
            Dictionary with link result or preview
        """
        if dry_run:
            return {
                "dry_run": True,
                "epic_key": epic_key,
                "artifact_type": artifact.artifact_type,
                "title": artifact.title,
                "url": artifact.url,
            }

        # Skip local file paths - only link URLs
        if not artifact.url.startswith(("http://", "https://")):
            return {
                "skipped": True,
                "reason": "Local path, not linkable",
                "artifact_type": artifact.artifact_type,
                "title": artifact.title,
            }

        jira = self._get_jira_client()

        try:
            # Use remote links API
            link_data = {
                "globalId": f"{artifact.artifact_type}:{artifact.url}",
                "application": {
                    "type": "com.atlassian.jira",
                    "name": artifact.artifact_type.capitalize(),
                },
                "relationship": "links to",
                "object": {
                    "url": artifact.url,
                    "title": artifact.title,
                    "summary": artifact.description or "",
                    "icon": self._get_artifact_icon(artifact.artifact_type),
                },
            }

            result = jira.create_or_update_issue_remote_links(
                issue_key=epic_key,
                link_url=artifact.url,
                title=artifact.title,
                global_id=link_data["globalId"],
                relationship=link_data["relationship"],
            )

            return {
                "success": True,
                "artifact_type": artifact.artifact_type,
                "title": artifact.title,
                "url": artifact.url,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "artifact_type": artifact.artifact_type,
                "title": artifact.title,
            }

    def _get_artifact_icon(self, artifact_type: str) -> Dict[str, str]:
        """Get icon URL for artifact type."""
        icons = {
            "figma": {
                "url16x16": "https://static.figma.com/app/icon/1/favicon.png",
                "title": "Figma",
            },
            "confluence": {
                "url16x16": "https://wac-cdn.atlassian.com/assets/img/favicons/confluence/favicon.png",
                "title": "Confluence",
            },
            "wireframe": {
                "url16x16": "https://www.google.com/s2/favicons?domain=miro.com",
                "title": "Wireframe",
            },
            "adr": {
                "url16x16": "https://www.google.com/s2/favicons?domain=github.com",
                "title": "ADR",
            },
        }
        return icons.get(artifact_type, {"url16x16": "", "title": artifact_type})

    def create_story(
        self, project_key: str, epic_key: str, story: StoryData, dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Create a story linked to an epic.

        Args:
            project_key: Jira project key
            epic_key: Parent epic key
            story: Story data
            dry_run: If True, return preview without creating

        Returns:
            Dictionary with story key, url, or preview
        """
        if dry_run:
            return {
                "dry_run": True,
                "project_key": project_key,
                "epic_key": epic_key,
                "title": story.title,
                "estimate": story.estimate_size,
                "labels": story.labels,
            }

        jira = self._get_jira_client()

        # Story data
        story_data = {
            "project": {"key": project_key},
            "summary": story.title,
            "description": story.description,
            "issuetype": {"name": "Story"},
            "labels": story.labels,
        }

        # Add story points if we can map the estimate
        story_points = self._estimate_to_story_points(story.estimate_size)
        if story_points:
            # Story points field - this varies by Jira instance
            # Common field names: customfield_10016, customfield_10026
            # We'll try to add it but won't fail if the field doesn't exist
            story_data["customfield_10016"] = story_points

        try:
            result = jira.create_issue(fields=story_data)
            story_key = result.get("key")

            # Link story to epic
            try:
                jira.set_issue_field(story_key, {"parent": {"key": epic_key}})
            except Exception:
                # If parent field doesn't work, try epic link
                try:
                    jira.create_issue_link(
                        type="Epic-Story Link",
                        inwardIssue=epic_key,
                        outwardIssue=story_key,
                    )
                except Exception:
                    # Epic linking may not be available
                    pass

            return {
                "key": story_key,
                "url": f"{self._jira_config['url']}/browse/{story_key}",
                "title": story.title,
            }
        except Exception as e:
            raise JiraApiError(f"Failed to create story: {e}")

    def create_epic_from_feature(
        self,
        feature_path: Path,
        dry_run: bool = False,
        create_stories: bool = True,
        link_artifacts: bool = True,
    ) -> EpicCreationResult:
        """
        Create a Jira epic from a context engine feature.

        This is the main method that orchestrates:
        1. Loading feature state
        2. Creating the epic
        3. Linking all artifacts
        4. Creating child stories from ADRs
        5. Updating feature-state.yaml

        Args:
            feature_path: Path to feature folder
            dry_run: If True, preview without creating
            create_stories: If True, create stories from ADRs
            link_artifacts: If True, link artifacts to epic

        Returns:
            EpicCreationResult with outcome
        """
        result = EpicCreationResult(success=False, dry_run=dry_run)

        # Load feature state
        state = FeatureState.load(feature_path)
        if not state:
            result.message = f"Feature state not found at {feature_path}"
            result.errors.append("feature-state.yaml not found")
            return result

        # Check if epic already exists
        if state.artifacts.get("jira_epic") and not dry_run:
            result.message = (
                f"Feature already has Jira epic: {state.artifacts['jira_epic']}. "
                "Remove from feature-state.yaml to create new epic."
            )
            result.epic_key = state.artifacts["jira_epic"]
            result.success = True
            return result

        try:
            # Get project key
            project_key = self._get_project_key(state)

            # Extract description
            description = self._extract_description(feature_path, state)

            # Create epic
            epic_result = self.create_epic(
                project_key=project_key,
                title=state.title,
                description=description,
                labels=["context-engine", state.product_id],
                dry_run=dry_run,
            )

            if dry_run:
                result.epic_preview = epic_result
            else:
                result.epic_key = epic_result.get("key")
                result.epic_url = epic_result.get("url")

            # Collect and link artifacts
            if link_artifacts:
                artifacts = self._collect_artifacts(feature_path, state)
                for artifact in artifacts:
                    link_result = self.link_artifact(
                        epic_key=result.epic_key or "PREVIEW",
                        artifact=artifact,
                        dry_run=dry_run,
                    )
                    result.artifacts_linked.append(link_result)

            # Create stories from ADRs
            if create_stories:
                stories = self._generate_stories_from_adrs(feature_path, state)
                for story in stories:
                    if dry_run:
                        story_preview = self.create_story(
                            project_key=project_key,
                            epic_key="PREVIEW",
                            story=story,
                            dry_run=True,
                        )
                        result.stories_preview.append(story_preview)
                    else:
                        try:
                            story_result = self.create_story(
                                project_key=project_key,
                                epic_key=result.epic_key,
                                story=story,
                                dry_run=False,
                            )
                            result.stories_created.append(story_result)
                        except JiraApiError as e:
                            result.errors.append(f"Failed to create story: {e}")

            # Update feature state with epic key
            if not dry_run and result.epic_key:
                state.add_artifact("jira_epic", result.epic_key)
                state.save(feature_path)

            result.success = True
            if dry_run:
                result.message = (
                    f"[DRY RUN] Would create epic in project {project_key} "
                    f"with {len(stories)} stories"
                )
            else:
                result.message = (
                    f"Created epic {result.epic_key} with "
                    f"{len(result.stories_created)} stories"
                )

        except JiraConfigError as e:
            result.message = str(e)
            result.errors.append(str(e))
        except JiraApiError as e:
            result.message = f"Jira API error: {e}"
            result.errors.append(str(e))
        except Exception as e:
            result.message = f"Unexpected error: {e}"
            result.errors.append(str(e))

        return result

    def get_epic_preview(self, feature_path: Path) -> Dict[str, Any]:
        """
        Get a preview of what would be created for a feature.

        Args:
            feature_path: Path to feature folder

        Returns:
            Dictionary with preview data
        """
        result = self.create_epic_from_feature(feature_path=feature_path, dry_run=True)
        return result.to_dict()


def create_jira_epic(
    feature_path: Path,
    dry_run: bool = False,
    create_stories: bool = True,
    link_artifacts: bool = True,
) -> EpicCreationResult:
    """
    Convenience function to create Jira epic from feature.

    Args:
        feature_path: Path to feature folder
        dry_run: If True, preview only
        create_stories: If True, create child stories
        link_artifacts: If True, link artifacts

    Returns:
        EpicCreationResult
    """
    creator = JiraEpicCreator()
    return creator.create_epic_from_feature(
        feature_path=feature_path,
        dry_run=dry_run,
        create_stories=create_stories,
        link_artifacts=link_artifacts,
    )
