"""
Feature Engine - Main Orchestrator

The FeatureEngine is the central orchestrator for the Context Creation Engine.
It manages the feature lifecycle from initialization through decision gate.

Usage:
    from tools.context_engine import FeatureEngine

    engine = FeatureEngine()

    # Start a new feature
    feature = engine.start_feature(
        title="OTP Checkout Recovery",
        product_id="meal-kit"
    )

    # Check status
    status = engine.check_feature("mk-feature-recovery")

    # Resume a paused feature
    engine.resume_feature("mk-feature-recovery")
"""

import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .alias_manager import AliasManager, MatchResult
from .bidirectional_sync import BidirectionalSync
from .brain_entity_creator import (
    BrainEntityCreator,
    BrainEntityResult,
    generate_entity_name,
)
from .feature_state import (
    AliasInfo,
    FeaturePhase,
    FeatureState,
    TrackStatus,
    generate_brain_entity_name,
    generate_slug,
)
from .product_identifier import (
    IdentificationResult,
    IdentificationSource,
    ProductIdentifier,
    ProductInfo,
)
from .tracks.business_case import BCStatus, BCTrackResult, BusinessCaseTrack
from .tracks.engineering import (
    ADRStatus,
    EngineeringStatus,
    EngineeringTrack,
    EngineeringTrackResult,
)


@dataclass
class InitializationResult:
    """Result of feature initialization."""

    success: bool
    feature_slug: str
    feature_path: Path
    state: Optional[FeatureState] = None
    message: str = ""
    linked_to_existing: bool = False
    existing_feature: Optional[str] = None
    needs_product_selection: bool = False
    product_selection_result: Optional[IdentificationResult] = None


@dataclass
class FeatureStatus:
    """Status report for a feature."""

    slug: str
    title: str
    product_id: str
    current_phase: FeaturePhase
    tracks: Dict[str, Dict[str, Any]]
    pending_items: List[str]
    blockers: List[str]
    artifacts: Dict[str, Optional[str]]
    last_activity: datetime


class FeatureEngine:
    """
    Main orchestrator for the Context Creation Engine.

    Manages the complete feature lifecycle:
    1. Initialization - Create feature folder, state file, brain entity
    2. Signal Analysis - Gather and analyze signals
    3. Context Document - Generate and iterate context doc
    4. Parallel Tracks - Design, Business Case, Engineering
    5. Decision Gate - Final review
    6. Output Generation - PRD, spec export
    """

    def __init__(self, user_path: Optional[Path] = None):
        """
        Initialize the feature engine.

        Args:
            user_path: Path to user/ directory. If None, auto-detected.
        """
        import config_loader

        self.config = config_loader.get_config()
        self.user_path = user_path or Path(self.config.user_path)

        # Get product and organization info from config
        self.products_config = self.config.config.get("products", {})
        self.organization = self.products_config.get("organization", {})

        # Initialize alias manager for duplicate detection
        self.alias_manager = AliasManager()

        # Initialize product identifier
        self.product_identifier = ProductIdentifier(user_path=self.user_path)

        # Initialize bidirectional sync for action log updates
        self._sync = BidirectionalSync(user_path=self.user_path)

    def _get_product_info(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Get product information from config.

        Args:
            product_id: Product ID

        Returns:
            Product info dict or None
        """
        items = self.products_config.get("items", [])
        for product in items:
            if product.get("id") == product_id:
                return product
        return None

    def _get_feature_path(self, product_id: str, slug: str) -> Path:
        """
        Get the path for a feature folder.

        Args:
            product_id: Product ID
            slug: Feature slug

        Returns:
            Path to feature folder
        """
        org_id = self.organization.get("id", "default")
        return self.user_path / "products" / org_id / product_id / slug

    def _create_feature_folder(
        self, feature_path: Path, slug: str, title: str, product_id: str
    ) -> None:
        """
        Create the feature folder structure.

        Creates:
            - {feature-slug}/
            - {feature-slug}/{feature-slug}-context.md
            - {feature-slug}/context-docs/
            - {feature-slug}/business-case/
            - {feature-slug}/engineering/
            - {feature-slug}/engineering/adrs/

        Args:
            feature_path: Path to create
            slug: Feature slug
            title: Feature title
            product_id: Product ID for context file

        Raises:
            PermissionError: If unable to create directories
            OSError: If filesystem operation fails
        """
        try:
            # Create main folder and subfolders
            feature_path.mkdir(parents=True, exist_ok=True)
            (feature_path / "context-docs").mkdir(exist_ok=True)
            (feature_path / "business-case").mkdir(exist_ok=True)
            (feature_path / "engineering").mkdir(exist_ok=True)
            (feature_path / "engineering" / "adrs").mkdir(exist_ok=True)

            # Create initial context file from template
            context_file = feature_path / f"{slug}-context.md"
            if not context_file.exists():
                context_content = self._generate_context_template(
                    slug, title, product_id
                )
                context_file.write_text(context_content)
        except PermissionError as e:
            raise PermissionError(
                f"Permission denied creating feature folder at {feature_path}: {e}"
            )
        except OSError as e:
            raise OSError(f"Failed to create feature folder at {feature_path}: {e}")

    def _generate_context_template(self, slug: str, title: str, product_id: str) -> str:
        """
        Generate initial context file content.

        Args:
            slug: Feature slug
            title: Feature title
            product_id: Product ID (e.g., "meal-kit")

        Returns:
            Context file content
        """
        import config_loader

        now = datetime.now().strftime("%Y-%m-%d")

        # Get user name from config
        user_name = config_loader.get_user_name()

        # Get product code for display (uppercase shorthand)
        product_info = self._get_product_info(product_id)
        product_code = (
            product_info.get("jira_project", product_id.upper())
            if product_info
            else product_id.upper()
        )

        return f"""# {title} Context

**Product:** {product_code}
**Status:** To Do
**Owner:** {user_name}
**Priority:** P2
**Deadline:** TBD
**Last Updated:** {now}

## Description
*Feature context created by Context Creation Engine*

## Stakeholders
- **{user_name}** (Owner)

## Action Log
| Date | Action | Status | Priority | Deadline |
|------|--------|--------|----------|----------|

## References
- *No links yet*

## Brain Entities
- [[Entities/{generate_brain_entity_name(title)}]]

## Changelog
- **{now}**: Context file created by Context Creation Engine
"""

    def _create_brain_entity(self, title: str, slug: str, product_id: str) -> Path:
        """
        Create a Brain entity for the feature using v2 schema format.

        Creates entity at user/brain/Entities/{Feature_Name}.md with proper
        YAML frontmatter including $schema, $id, $type, $version, $created,
        $updated, $confidence, $source, $status, $relationships, $tags,
        $aliases, $events, and markdown body with Overview, Product, Context,
        Relationships, and References sections.

        Args:
            title: Feature title (e.g., "OTP Checkout Recovery")
            slug: Feature slug (e.g., "mk-feature-recovery")
            product_id: Product ID (e.g., "meal-kit")

        Returns:
            Path to created (or existing) entity file

        Example:
            path = engine._create_brain_entity(
                title="OTP Checkout Recovery",
                slug="mk-feature-recovery",
                product_id="meal-kit"
            )
            # Creates: user/brain/Entities/Otp_Checkout_Recovery.md
        """
        # Get product information for better entity content
        product_info = self._get_product_info(product_id)
        product_name = (
            product_info.get("name", product_id) if product_info else product_id
        )
        organization_id = self.organization.get("id", "default")

        # Use BrainEntityCreator for consistent v2 schema format
        creator = BrainEntityCreator(self.user_path)
        result = creator.create_feature_entity(
            title=title,
            slug=slug,
            product_id=product_id,
            product_name=product_name,
            organization_id=organization_id,
            description=None,  # Will use default placeholder
            source="context_engine",
            confidence=0.8,
        )

        return result.entity_path

    def create_feature_folder(
        self, product_id: str, feature_title: str
    ) -> Tuple[bool, Path, str]:
        """
        Create a feature folder at user/products/{org}/{product_id}/{feature-slug}/.

        This is a public method for creating feature folders standalone, without
        going through the full start_feature workflow.

        Args:
            product_id: Product ID (e.g., "meal-kit", "wellness-brand")
            feature_title: Human-readable feature title (e.g., "OTP Checkout Recovery")

        Returns:
            Tuple of (success: bool, feature_path: Path, message: str)

        Raises:
            ValueError: If product_id is not found in config

        Example:
            engine = FeatureEngine()
            success, path, msg = engine.create_feature_folder("meal-kit", "OTP Checkout Recovery")
            if success:
                print(f"Created folder at: {path}")
            else:
                print(f"Error: {msg}")
        """
        # Validate product exists in config
        product_info = self._get_product_info(product_id)
        if not product_info:
            available_products = [
                p.get("id") for p in self.products_config.get("items", [])
            ]
            return (
                False,
                Path(),
                f"Product '{product_id}' not found in config. Available products: {available_products}",
            )

        # Generate slug from title
        slug = generate_slug(feature_title, product_id)

        # Get feature path
        feature_path = self._get_feature_path(product_id, slug)

        # Check if folder already exists
        if feature_path.exists():
            state_file = feature_path / "feature-state.yaml"
            if state_file.exists():
                return (
                    False,
                    feature_path,
                    f"Feature folder already exists at {feature_path} with feature-state.yaml",
                )
            # Folder exists but no state file - could be partial creation
            # We'll allow overwriting in this case but warn

        # Create the folder structure
        try:
            self._create_feature_folder(feature_path, slug, feature_title, product_id)
        except PermissionError as e:
            return (False, feature_path, f"Permission denied: {e}")
        except OSError as e:
            return (False, feature_path, f"Filesystem error: {e}")

        # Create feature-state.yaml
        import config_loader

        user_name = config_loader.get_user_name()

        state = FeatureState(
            slug=slug,
            title=feature_title,
            product_id=product_id,
            organization=self.organization.get("id", "default"),
            context_file=f"{slug}-context.md",
            brain_entity=f"[[Entities/{generate_brain_entity_name(feature_title)}]]",
            created_by=user_name,
            aliases=AliasInfo(primary_name=feature_title),
        )

        try:
            state.save(feature_path)
        except (PermissionError, OSError) as e:
            return (False, feature_path, f"Failed to save feature-state.yaml: {e}")

        return (
            True,
            feature_path,
            f"Feature folder created successfully at {feature_path}",
        )

    def start_feature_with_identification(
        self,
        title: str,
        product: Optional[str] = None,
        channel_name: Optional[str] = None,
        from_insight: Optional[str] = None,
        priority: str = "medium",
        target_date: Optional[str] = None,
        check_duplicates: bool = True,
    ) -> InitializationResult:
        """
        Initialize a new feature with automatic product identification.

        This method follows the PRD Section C.6 priority order:
        1. Explicit product flag
        2. Master Sheet lookup (if topic exists)
        3. Current daily context
        4. Signal source (channel inference)
        5. Return list for user selection

        Args:
            title: Feature title
            product: Optional explicit product ID, name, or abbreviation
            channel_name: Optional Slack channel for inference
            from_insight: Optional insight ID to start from
            priority: Priority level (P0, P1, P2, medium, low)
            target_date: Optional target completion date
            check_duplicates: Whether to check for existing similar features

        Returns:
            InitializationResult with feature details or product selection options
        """
        # Use ProductIdentifier to determine the product
        identification = self.product_identifier.identify_product(
            explicit_product=product,
            topic_name=title,
            channel_name=channel_name,
            check_master_sheet=True,
            check_daily_context=True,
        )

        if not identification.found:
            # Product not determined - return result for user selection
            return InitializationResult(
                success=False,
                feature_slug="",
                feature_path=Path(),
                message=identification.message,
                needs_product_selection=True,
                product_selection_result=identification,
            )

        # Product found - proceed with feature creation
        return self.start_feature(
            title=title,
            product_id=identification.product_id,
            from_insight=from_insight,
            priority=priority,
            target_date=target_date,
            check_duplicates=check_duplicates,
        )

    def get_products(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get list of available products.

        Convenience method that delegates to ProductIdentifier.

        Args:
            active_only: If True, only return active products

        Returns:
            List of product dictionaries
        """
        products = self.product_identifier.get_products_from_config(active_only)
        return [p.to_dict() for p in products]

    def format_product_selection(self, result: InitializationResult) -> str:
        """
        Format a product selection prompt for display.

        Args:
            result: InitializationResult that needs product selection

        Returns:
            Formatted string for user display
        """
        if not result.needs_product_selection or not result.product_selection_result:
            return ""
        return self.product_identifier.format_product_selection(
            result.product_selection_result
        )

    def start_feature(
        self,
        title: str,
        product_id: str,
        from_insight: Optional[str] = None,
        priority: str = "medium",
        target_date: Optional[str] = None,
        check_duplicates: bool = True,
    ) -> InitializationResult:
        """
        Initialize a new feature.

        This is the entry point for /start-feature command when product is known.
        For automatic product identification, use start_feature_with_identification().

        Args:
            title: Feature title
            product_id: Product ID (e.g., "meal-kit")
            from_insight: Optional insight ID to start from
            priority: Priority level (P0, P1, P2, medium, low)
            target_date: Optional target completion date
            check_duplicates: Whether to check for existing similar features

        Returns:
            InitializationResult with feature details
        """
        # Validate product exists
        product_info = self._get_product_info(product_id)
        if not product_info:
            return InitializationResult(
                success=False,
                feature_slug="",
                feature_path=Path(),
                message=f"Product '{product_id}' not found in config",
            )

        # Generate slug
        slug = generate_slug(title, product_id)

        # Check for duplicates/similar features
        if check_duplicates:
            match_result = self.alias_manager.find_existing_feature(title, product_id)
            if match_result.type == "auto_consolidate":
                return InitializationResult(
                    success=True,
                    feature_slug=match_result.existing_slug or slug,
                    feature_path=self._get_feature_path(
                        product_id, match_result.existing_slug or slug
                    ),
                    message=match_result.message,
                    linked_to_existing=True,
                    existing_feature=match_result.existing_name,
                )
            elif match_result.type == "ask_user":
                # Return a result that indicates user input is needed
                return InitializationResult(
                    success=False,
                    feature_slug=slug,
                    feature_path=self._get_feature_path(product_id, slug),
                    message=match_result.question or "",
                    linked_to_existing=False,
                    existing_feature=match_result.existing_name,
                )

        # Get feature path
        feature_path = self._get_feature_path(product_id, slug)

        # Check if feature already exists
        if feature_path.exists():
            existing_state = FeatureState.load(feature_path)
            if existing_state:
                return InitializationResult(
                    success=False,
                    feature_slug=slug,
                    feature_path=feature_path,
                    state=existing_state,
                    message=f"Feature '{slug}' already exists at {feature_path}",
                )

        # Create folder structure
        try:
            self._create_feature_folder(feature_path, slug, title, product_id)
        except (PermissionError, OSError) as e:
            return InitializationResult(
                success=False,
                feature_slug=slug,
                feature_path=feature_path,
                message=str(e),
            )

        # Create brain entity
        brain_entity_path = self._create_brain_entity(title, slug, product_id)
        brain_ref = f"[[Entities/{generate_brain_entity_name(title)}]]"

        # Create initial state
        import config_loader

        user_name = config_loader.get_user_name()

        state = FeatureState(
            slug=slug,
            title=title,
            product_id=product_id,
            organization=self.organization.get("id", "default"),
            context_file=f"{slug}-context.md",
            brain_entity=brain_ref,
            created_by=user_name,
            aliases=AliasInfo(primary_name=title),
        )

        # Record initialization phase
        state.enter_phase(
            FeaturePhase.INITIALIZATION,
            metadata={
                "from_insight": from_insight,
                "priority": priority,
                "target_date": target_date,
            },
        )

        # Save state
        state.save(feature_path)

        # Auto-update action log in context file with initialization entry
        self._log_action(
            feature_path=feature_path,
            action=f"Feature initialized: {title}",
            status="To Do",
            priority=priority if priority in ("P0", "P1", "P2") else "P2",
        )

        return InitializationResult(
            success=True,
            feature_slug=slug,
            feature_path=feature_path,
            state=state,
            message=f"Feature '{title}' initialized successfully",
        )

    def check_feature(self, slug: str) -> Optional[FeatureStatus]:
        """
        Get the current status of a feature.

        Args:
            slug: Feature slug

        Returns:
            FeatureStatus or None if not found
        """
        # Find the feature across all products
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        state = FeatureState.load(feature_path)
        if not state:
            return None

        # Analyze pending items
        pending_items = self._get_pending_items(state)

        # Analyze blockers
        blockers = self._get_blockers(state)

        # Get last activity from phase history
        last_activity = state.created
        if state.phase_history:
            last_entry = state.phase_history[-1]
            last_activity = last_entry.completed or last_entry.entered

        return FeatureStatus(
            slug=state.slug,
            title=state.title,
            product_id=state.product_id,
            current_phase=state.current_phase,
            tracks={name: track.to_dict() for name, track in state.tracks.items()},
            pending_items=pending_items,
            blockers=blockers,
            artifacts=state.artifacts,
            last_activity=last_activity,
        )

    def _find_feature(self, slug: str) -> Optional[Path]:
        """
        Find a feature by slug across all products.

        Args:
            slug: Feature slug

        Returns:
            Path to feature folder or None
        """
        products_path = self.user_path / "products"
        if not products_path.exists():
            return None

        # Search through organization/product/feature structure
        for org_path in products_path.iterdir():
            if not org_path.is_dir():
                continue
            for product_path in org_path.iterdir():
                if not product_path.is_dir():
                    continue
                feature_path = product_path / slug
                if (
                    feature_path.exists()
                    and (feature_path / "feature-state.yaml").exists()
                ):
                    return feature_path

        return None

    def _get_pending_items(self, state: FeatureState) -> List[str]:
        """
        Get list of pending items for a feature.

        Args:
            state: Feature state

        Returns:
            List of pending item descriptions
        """
        pending = []

        # Check each track
        for track_name, track in state.tracks.items():
            if track.status == TrackStatus.PENDING_INPUT:
                pending.append(f"{track_name}: Awaiting input")
            elif track.status == TrackStatus.PENDING_APPROVAL:
                pending.append(f"{track_name}: Awaiting approval")

        # Check for missing artifacts in design track
        if state.tracks["design"].status != TrackStatus.NOT_STARTED:
            if not state.artifacts.get("figma"):
                pending.append("Design: Figma URL required")
            if not state.artifacts.get("wireframes_url"):
                pending.append("Design: Wireframes URL required")

        return pending

    def _get_blockers(self, state: FeatureState) -> List[str]:
        """
        Get list of blockers for a feature.

        Args:
            state: Feature state

        Returns:
            List of blocker descriptions
        """
        blockers = []

        # Check for blocked tracks
        for track_name, track in state.tracks.items():
            if track.status == TrackStatus.BLOCKED:
                blockers.append(f"{track_name}: Track is blocked")

        # Check for missing critical items based on phase
        if state.current_phase == FeaturePhase.PARALLEL_TRACKS:
            if state.tracks["context"].status != TrackStatus.COMPLETE:
                blockers.append(
                    "Context document must be complete before decision gate"
                )

        if state.current_phase == FeaturePhase.DECISION_GATE:
            if state.tracks["business_case"].status != TrackStatus.COMPLETE:
                blockers.append("Business case approval required")

        return blockers

    def resume_feature(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Resume a paused or inactive feature.

        Args:
            slug: Feature slug

        Returns:
            Resume information or None if not found
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        state = FeatureState.load(feature_path)
        if not state:
            return None

        # Get current status
        status = self.check_feature(slug)

        return {
            "slug": slug,
            "title": state.title,
            "last_phase": state.current_phase.value,
            "pending_items": status.pending_items if status else [],
            "blockers": status.blockers if status else [],
            "last_activity": (
                state.phase_history[-1].entered
                if state.phase_history
                else state.created
            ),
            "message": f"Feature '{state.title}' ready to resume",
        }

    def attach_artifact(self, slug: str, artifact_type: str, url: str) -> bool:
        """
        Attach an external artifact to a feature.

        Args:
            slug: Feature slug
            artifact_type: Type (figma, jira_epic, wireframes_url, confluence_page)
            url: URL to the artifact

        Returns:
            True if successful
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return False

        state = FeatureState.load(feature_path)
        if not state:
            return False

        state.add_artifact(artifact_type, url)
        state.save(feature_path)

        # Update context file with new reference
        self._update_context_references(feature_path, state)

        # Auto-update action log in context file
        artifact_labels = {
            "figma": "Figma design",
            "jira_epic": "Jira epic",
            "confluence_page": "Confluence page",
            "wireframes_url": "Wireframes",
        }
        label = artifact_labels.get(artifact_type, artifact_type)
        self._log_action(
            feature_path=feature_path,
            action=f"Attached artifact: {label}",
            status=state.get_derived_status(),
        )

        return True

    def _update_context_references(
        self, feature_path: Path, state: FeatureState
    ) -> None:
        """
        Update the context file's References section with artifacts.

        Formats links with bold labels and markdown links:
        - **Figma Design**: [Design Name](https://figma.com/file/abc123)
        - **Jira Epic**: [MK-1234](https://atlassian.net/browse/MK-1234)

        Args:
            feature_path: Path to feature folder
            state: Current feature state
        """
        context_file = feature_path / state.context_file
        if not context_file.exists():
            return

        content = context_file.read_text()

        # Use ArtifactManager for consistent formatting
        from .artifact_manager import ArtifactManager, ArtifactType

        manager = ArtifactManager()

        # Mapping from state artifact keys to ArtifactType
        artifact_type_map = {
            "figma": ArtifactType.FIGMA,
            "wireframes_url": ArtifactType.WIREFRAMES,
            "jira_epic": ArtifactType.JIRA_EPIC,
            "confluence_page": ArtifactType.CONFLUENCE_PAGE,
            "gdocs": ArtifactType.GDOCS,
            "meeting_notes": ArtifactType.MEETING_NOTES,
            "stakeholder_approval": ArtifactType.STAKEHOLDER_APPROVAL,
            "engineering_estimate": ArtifactType.ENGINEERING_ESTIMATE,
            "other": ArtifactType.OTHER,
        }

        # Labels for display
        artifact_labels = {
            "figma": "Figma Design",
            "wireframes_url": "Wireframes",
            "jira_epic": "Jira Epic",
            "confluence_page": "Confluence",
            "gdocs": "Google Doc",
            "meeting_notes": "Meeting Notes",
            "stakeholder_approval": "Stakeholder Approval",
            "engineering_estimate": "Engineering Estimate",
            "other": "Reference",
        }

        # Build references section with proper markdown formatting
        refs = []
        for artifact_key, artifact_url in state.artifacts.items():
            if artifact_url:
                label = artifact_labels.get(artifact_key, artifact_key)
                artifact_type = artifact_type_map.get(artifact_key)
                if artifact_type:
                    link_title = manager._generate_link_title(
                        artifact_type, artifact_url
                    )
                else:
                    link_title = "Link"
                refs.append(f"- **{label}**: [{link_title}]({artifact_url})")

        if not refs:
            refs.append("*Links to artifacts will be added as they are attached*")

        # Replace references section
        refs_text = "\n".join(refs)
        import re

        pattern = r"(## References\n).*?(\n## |\Z)"
        replacement = f"\\1{refs_text}\n\n\\2"
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

        if new_content != content:
            context_file.write_text(new_content)

    def list_features(
        self, product_id: Optional[str] = None, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all features, optionally filtered.

        Args:
            product_id: Filter by product
            status: Filter by status (in_progress, complete, etc.)

        Returns:
            List of feature summaries
        """
        features = []
        products_path = self.user_path / "products"

        if not products_path.exists():
            return features

        for org_path in products_path.iterdir():
            if not org_path.is_dir():
                continue
            for product_path in org_path.iterdir():
                if not product_path.is_dir():
                    continue

                # Filter by product if specified
                if product_id and product_path.name != product_id:
                    continue

                for feature_path in product_path.iterdir():
                    if not feature_path.is_dir():
                        continue

                    state_file = feature_path / "feature-state.yaml"
                    if not state_file.exists():
                        continue

                    state = FeatureState.load(feature_path)
                    if not state:
                        continue

                    # Filter by status if specified
                    if status:
                        derived_status = state.get_derived_status().lower()
                        if status.lower() not in derived_status:
                            continue

                    features.append(
                        {
                            "slug": state.slug,
                            "title": state.title,
                            "product_id": state.product_id,
                            "phase": state.current_phase.value,
                            "status": state.get_derived_status(),
                            "path": str(feature_path),
                        }
                    )

        return features

    # ========== Action Log Integration ==========

    def _log_action(
        self,
        feature_path: Path,
        action: str,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        deadline: Optional[str] = None,
    ) -> bool:
        """
        Add an action to the context file's action log.

        This is called automatically when significant state changes occur:
        - Phase transitions
        - Decisions recorded
        - Track status changes

        Args:
            feature_path: Path to the feature folder
            action: Description of the action
            status: Optional status (derived from state if not provided)
            priority: Optional priority
            deadline: Optional deadline

        Returns:
            True if action was logged successfully
        """
        try:
            result = self._sync.add_action_to_log(
                feature_path=feature_path,
                action=action,
                status=status,
                priority=priority,
                deadline=deadline,
            )
            return result.success
        except Exception as e:
            # Log error but don't fail the main operation
            import logging

            logging.getLogger(__name__).warning(f"Failed to add action to log: {e}")
            return False

    # ========== Phase History and Decision Tracking ==========

    def record_phase_transition(
        self,
        slug: str,
        from_phase: FeaturePhase,
        to_phase: FeaturePhase,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Record a phase transition for a feature.

        This method loads the feature state, records the transition, saves the state,
        and returns the transition details.

        Args:
            slug: Feature slug
            from_phase: The phase transitioning from
            to_phase: The phase transitioning to
            metadata: Optional metadata for the transition

        Returns:
            Dictionary with transition details, or None if feature not found

        Example:
            engine.record_phase_transition(
                slug="mk-feature-recovery",
                from_phase=FeaturePhase.SIGNAL_ANALYSIS,
                to_phase=FeaturePhase.CONTEXT_DOC,
                metadata={"insights_reviewed": 5, "insight_selected": "insight-otp-abandonment"}
            )
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        state = FeatureState.load(feature_path)
        if not state:
            return None

        # Record the transition
        entry = state.record_phase_transition(from_phase, to_phase, metadata)

        # Save updated state
        state.save(feature_path)

        # Auto-update action log in context file
        action_description = f"Phase transition: {from_phase.value} -> {to_phase.value}"
        self._log_action(
            feature_path=feature_path,
            action=action_description,
            status=state.get_derived_status(),
        )

        return {
            "slug": slug,
            "from_phase": from_phase.value,
            "to_phase": to_phase.value,
            "entered": entry.entered.isoformat(),
            "metadata": metadata or {},
            "message": f"Transitioned from {from_phase.value} to {to_phase.value}",
        }

    def record_decision(
        self,
        slug: str,
        decision: str,
        rationale: str,
        decided_by: str,
        phase: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Record a decision for a feature.

        If phase is not provided, uses the feature's current phase.

        Args:
            slug: Feature slug
            decision: What was decided
            rationale: Why this decision was made
            decided_by: Who made the decision
            phase: Optional phase (defaults to current phase)
            metadata: Optional additional data

        Returns:
            Dictionary with decision details, or None if feature not found

        Example:
            engine.record_decision(
                slug="mk-feature-recovery",
                decision='Proceed with "remember device" approach',
                rationale="Best balance of UX and security",
                decided_by="jane.smith"
            )
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        state = FeatureState.load(feature_path)
        if not state:
            return None

        # Use current phase if not specified
        decision_phase = phase or state.current_phase.value

        # Record the decision
        decision_entry = state.record_decision(
            phase=decision_phase,
            decision=decision,
            rationale=rationale,
            decided_by=decided_by,
            metadata=metadata,
        )

        # Save updated state
        state.save(feature_path)

        # Auto-update action log in context file
        # Truncate decision text if too long for action log
        truncated_decision = decision[:50] + "..." if len(decision) > 50 else decision
        action_description = f"Decision: {truncated_decision}"
        self._log_action(
            feature_path=feature_path,
            action=action_description,
            status=state.get_derived_status(),
        )

        return {
            "slug": slug,
            "date": decision_entry.date.isoformat(),
            "phase": decision_phase,
            "decision": decision,
            "rationale": rationale,
            "decided_by": decided_by,
            "message": f"Decision recorded for phase {decision_phase}",
        }

    def get_phase_history(self, slug: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get the phase history for a feature.

        Args:
            slug: Feature slug

        Returns:
            List of phase history entries, or None if feature not found

        Example return:
            [
                {
                    "phase": "initialization",
                    "entered": "2026-02-02T10:30:00Z",
                    "completed": "2026-02-02T10:30:15Z"
                },
                {
                    "phase": "signal_analysis",
                    "entered": "2026-02-02T10:30:15Z",
                    "completed": "2026-02-02T11:45:00Z",
                    "insights_reviewed": 5,
                    "insight_selected": "insight-otp-abandonment"
                }
            ]
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        state = FeatureState.load(feature_path)
        if not state:
            return None

        return state.get_phase_history()

    def get_decisions(
        self, slug: str, phase: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get decisions for a feature, optionally filtered by phase.

        Args:
            slug: Feature slug
            phase: Optional phase to filter by

        Returns:
            List of decision entries, or None if feature not found

        Example return:
            [
                {
                    "date": "2026-02-02T12:00:00Z",
                    "phase": "context_doc",
                    "decision": "Proceed with 'remember device' approach",
                    "rationale": "Best balance of UX and security",
                    "decided_by": "jane.smith"
                }
            ]
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        state = FeatureState.load(feature_path)
        if not state:
            return None

        return state.get_decisions(phase)

    def update_track_status(
        self,
        slug: str,
        track_name: str,
        status: TrackStatus,
        auto_sync: bool = True,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Update a track's status and log the change.

        This method updates the track status in the feature state,
        automatically logs the change to the context file's action log,
        and syncs the derived status to context file and Master Sheet.

        When any track status changes, the feature's overall Status is
        automatically recalculated per PRD C.5 rules:
            - All tracks complete -> "Done"
            - Any track in progress/pending -> "In Progress"
            - All tracks not started -> "To Do"

        Args:
            slug: Feature slug
            track_name: Name of track (context, design, business_case, engineering)
            status: New status for the track
            auto_sync: If True (default), automatically sync derived status
                       to context file and Master Sheet
            **kwargs: Additional fields to update on the track

        Returns:
            Dictionary with update details, or None if feature not found

        Example:
            engine.update_track_status(
                slug="mk-feature-recovery",
                track_name="design",
                status=TrackStatus.IN_PROGRESS,
                current_step="wireframes"
            )
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        state = FeatureState.load(feature_path)
        if not state:
            return None

        # Get previous status for logging
        previous_status = (
            state.tracks[track_name].status.value
            if track_name in state.tracks
            else "unknown"
        )

        # Update the track
        state.update_track(track_name, status=status, **kwargs)

        # Save updated state
        state.save(feature_path)

        # Get the new derived status (after track update)
        derived_status = state.get_derived_status()

        # Auto-update action log in context file
        action_description = (
            f"Track '{track_name}': {previous_status} -> {status.value}"
        )
        self._log_action(
            feature_path=feature_path, action=action_description, status=derived_status
        )

        # Sync derived status to context file and Master Sheet
        sync_result = None
        if auto_sync:
            sync_result = self._sync.sync_from_state(feature_path)

        return {
            "slug": slug,
            "track_name": track_name,
            "previous_status": previous_status,
            "new_status": status.value,
            "derived_status": derived_status,
            "context_file_updated": (
                sync_result.context_file_updated if sync_result else False
            ),
            "master_sheet_updated": (
                sync_result.master_sheet_updated if sync_result else False
            ),
            "message": f"Track '{track_name}' status updated to {status.value}",
        }

    def get_phase_summary(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Get a phase summary for a feature.

        Args:
            slug: Feature slug

        Returns:
            Summary dictionary, or None if feature not found

        Example return:
            {
                "current_phase": "design_track",
                "phases_completed": 3,
                "total_phases": 4,
                "hours_in_current_phase": 2.5,
                "last_transition": "2026-02-02T14:30:00Z"
            }
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        state = FeatureState.load(feature_path)
        if not state:
            return None

        return state.get_phase_summary()

    def get_feature_derived_status(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Get the derived status for a feature based on track completion states.

        Implements PRD C.5 rules:
            - All tracks complete -> "Done"
            - Any track in progress/pending -> "In Progress"
            - All tracks not started -> "To Do"

        When a track status changes, call this method to get the current
        overall feature status, which can be used for syncing to context
        file and Master Sheet.

        Args:
            slug: Feature slug

        Returns:
            Dictionary with status details, or None if feature not found

        Example return:
            {
                "slug": "mk-feature-recovery",
                "derived_status": "In Progress",
                "track_statuses": {
                    "context": "complete",
                    "design": "in_progress",
                    "business_case": "not_started",
                    "engineering": "not_started"
                },
                "all_complete": False,
                "any_in_progress": True
            }
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        state = FeatureState.load(feature_path)
        if not state:
            return None

        return {
            "slug": slug,
            "derived_status": state.get_derived_status(),
            "track_statuses": {
                name: track.status.value for name, track in state.tracks.items()
            },
            "all_complete": state.all_tracks_complete,
            "any_in_progress": state.any_track_in_progress,
        }

    def sync_feature_status(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Sync a feature's derived status to context file and Master Sheet.

        This method:
        1. Derives the current status from track completion states
        2. Updates the context file's Status field
        3. Updates the Master Sheet if configured

        Use this after any track status change to ensure the feature's
        overall status is consistently reflected across all data sources.

        Args:
            slug: Feature slug

        Returns:
            Dictionary with sync results, or None if feature not found

        Example return:
            {
                "slug": "mk-feature-recovery",
                "derived_status": "In Progress",
                "context_file_updated": True,
                "master_sheet_updated": False,
                "fields_updated": ["status", "last_updated", "references"]
            }
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        # Use bidirectional sync to update context file and Master Sheet
        result = self._sync.sync_from_state(feature_path)

        # Load state to get derived status for response
        state = FeatureState.load(feature_path)
        derived_status = state.get_derived_status() if state else "Unknown"

        return {
            "slug": slug,
            "derived_status": derived_status,
            "context_file_updated": result.context_file_updated,
            "master_sheet_updated": result.master_sheet_updated,
            "fields_updated": result.fields_updated,
            "success": result.success,
            "errors": result.errors,
        }

    # ========== Business Case Track Methods ==========

    def start_business_case(
        self,
        slug: str,
        approvers: Optional[List[str]] = None,
        baseline_metrics: Optional[Dict[str, Any]] = None,
        impact_assumptions: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Start the business case track for a feature.

        This initializes the BC track, optionally setting required approvers
        and initial assumptions. The track will be set to IN_PROGRESS status.

        Args:
            slug: Feature slug
            approvers: Optional list of stakeholders who must approve
            baseline_metrics: Optional initial baseline metrics
            impact_assumptions: Optional initial impact assumptions

        Returns:
            Dictionary with BC track status, or None if feature not found

        Example:
            engine.start_business_case(
                slug="mk-feature-recovery",
                approvers=["Jack Approver"],
                baseline_metrics={"conversion_rate": 0.65, "abandonment_rate": 0.35},
                impact_assumptions={"conversion_improvement": 0.10}
            )

        Example return:
            {
                "slug": "mk-feature-recovery",
                "bc_status": "in_progress",
                "version": 1,
                "message": "Business case track started",
                "assumptions_complete": True
            }
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        # Load feature state to get current user
        state = FeatureState.load(feature_path)
        if not state:
            return None

        # Initialize BC track
        bc_track = BusinessCaseTrack(feature_path)

        # Start the track
        import config_loader

        user_name = config_loader.get_user_name()
        result = bc_track.start(initiated_by=user_name)

        if not result.success:
            return {
                "slug": slug,
                "bc_status": bc_track.status.value,
                "success": False,
                "message": result.message,
            }

        # Set required approvers if provided
        if approvers:
            bc_track.set_required_approvers(approvers)

        # Update assumptions if provided
        if baseline_metrics or impact_assumptions:
            bc_track.update_assumptions(
                baseline_metrics=baseline_metrics, impact_assumptions=impact_assumptions
            )

        # Update feature state track status
        self.update_track_status(
            slug=slug,
            track_name="business_case",
            status=TrackStatus.IN_PROGRESS,
            auto_sync=True,
        )

        # Log action
        self._log_action(
            feature_path=feature_path,
            action="Business case track started",
            status=state.get_derived_status(),
        )

        return {
            "slug": slug,
            "bc_status": bc_track.status.value,
            "version": bc_track.current_version,
            "success": True,
            "message": result.message,
            "assumptions_complete": bc_track.assumptions.is_complete,
            "required_approvers": bc_track._required_approvers,
        }

    def submit_for_bc_approval(
        self,
        slug: str,
        approver: Optional[str] = None,
        message: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Submit the business case for stakeholder approval.

        This transitions the BC track to PENDING_APPROVAL status.
        The approver will need to provide their decision via record_bc_approval().

        Args:
            slug: Feature slug
            approver: Name of stakeholder to request approval from.
                     If not provided, uses first required approver.
            message: Optional message to include with approval request

        Returns:
            Dictionary with submission status, or None if feature not found

        Example:
            engine.submit_for_bc_approval(
                slug="mk-feature-recovery",
                approver="Jack Approver",
                message="Ready for review - conservative ROI estimate shows 15% improvement"
            )

        Example return:
            {
                "slug": "mk-feature-recovery",
                "bc_status": "pending_approval",
                "submitted_to": "Jack Approver",
                "pending_approvers": ["Jack Approver"],
                "message": "Business case submitted for approval"
            }
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        # Load BC track
        bc_track = BusinessCaseTrack(feature_path)

        # Determine approver
        if not approver:
            if bc_track._required_approvers:
                approver = bc_track._required_approvers[0]
            else:
                return {
                    "slug": slug,
                    "bc_status": bc_track.status.value,
                    "success": False,
                    "message": "No approver specified and no required approvers set",
                }

        # Generate document if not already done
        if (
            bc_track.current_version is None
            or not (bc_track.bc_folder / f"bc-v{bc_track.current_version}.md").exists()
        ):
            doc_result = bc_track.generate_document()
            if not doc_result.success:
                return {
                    "slug": slug,
                    "bc_status": bc_track.status.value,
                    "success": False,
                    "message": f"Failed to generate BC document: {doc_result.message}",
                }

        # Submit for approval
        result = bc_track.submit_for_approval(approver=approver, message=message)

        if not result.success:
            return {
                "slug": slug,
                "bc_status": bc_track.status.value,
                "success": False,
                "message": result.message,
            }

        # Update feature state track status
        self.update_track_status(
            slug=slug,
            track_name="business_case",
            status=TrackStatus.PENDING_APPROVAL,
            auto_sync=True,
        )

        # Log action
        self._log_action(
            feature_path=feature_path,
            action=f"BC submitted for approval to {approver}",
            status="In Progress",
        )

        return {
            "slug": slug,
            "bc_status": bc_track.status.value,
            "success": True,
            "submitted_to": approver,
            "pending_approvers": bc_track.pending_approvers,
            "version": bc_track.current_version,
            "message": result.message,
        }

    def record_bc_approval(
        self,
        slug: str,
        approver: str,
        approved: bool,
        approval_type: str = "verbal",
        reference: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Record a stakeholder approval or rejection decision for the business case.

        This records the decision and updates the BC track status:
        - If approved by all required approvers: BC track marked COMPLETE
        - If rejected: BC track marked BLOCKED

        Args:
            slug: Feature slug
            approver: Name of approver
            approved: True for approval, False for rejection
            approval_type: How approval was given (verbal, written, email, slack)
            reference: Link to evidence (Slack thread, email, meeting notes, etc.)
            notes: Additional context or conditions

        Returns:
            Dictionary with updated status, or None if feature not found

        Example (approval):
            engine.record_bc_approval(
                slug="mk-feature-recovery",
                approver="Jack Approver",
                approved=True,
                approval_type="verbal",
                reference="Slack thread #meal-kit-planning 2026-02-02",
                notes="Approved with condition to revisit after 30 days"
            )

        Example (rejection):
            engine.record_bc_approval(
                slug="mk-feature-recovery",
                approver="Jack Approver",
                approved=False,
                notes="Need more data on customer segment breakdown"
            )

        Example return:
            {
                "slug": "mk-feature-recovery",
                "bc_status": "approved",
                "approved_by": "Jack Approver",
                "approval_type": "verbal",
                "all_approvals": [...],
                "message": "Business case approved"
            }
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        # Load BC track
        bc_track = BusinessCaseTrack(feature_path)

        # Record the approval
        result = bc_track.record_approval(
            approver=approver,
            approved=approved,
            approval_type=approval_type,
            reference=reference,
            notes=notes,
        )

        if not result.success:
            return {
                "slug": slug,
                "bc_status": bc_track.status.value,
                "success": False,
                "message": result.message,
            }

        # Update feature state track status based on BC result
        if bc_track.status == BCStatus.APPROVED:
            track_status = TrackStatus.COMPLETE
            action_msg = f"BC approved by {approver}"
        elif bc_track.status == BCStatus.REJECTED:
            track_status = TrackStatus.BLOCKED
            action_msg = f"BC rejected by {approver}"
        else:
            track_status = TrackStatus.PENDING_APPROVAL
            action_msg = f"BC approval recorded from {approver}"

        self.update_track_status(
            slug=slug, track_name="business_case", status=track_status, auto_sync=True
        )

        # Log action
        self._log_action(
            feature_path=feature_path,
            action=action_msg,
            status="In Progress" if track_status != TrackStatus.COMPLETE else "Done",
        )

        # Record decision in feature state
        decision_text = f"Business case {'approved' if approved else 'rejected'}"
        if notes:
            decision_text += f": {notes[:100]}"

        self.record_decision(
            slug=slug,
            decision=decision_text,
            rationale=notes
            or f"{'Approved' if approved else 'Rejected'} by {approver}",
            decided_by=approver,
            phase="business_case",
            metadata={
                "approval_type": approval_type,
                "reference": reference,
                "approved": approved,
            },
        )

        return {
            "slug": slug,
            "bc_status": bc_track.status.value,
            "success": True,
            "approved": approved,
            "approved_by": approver,
            "approval_type": approval_type,
            "reference": reference,
            "pending_approvers": bc_track.pending_approvers,
            "all_approvals": [a.to_dict() for a in bc_track.approvals],
            "message": result.message,
        }

    def get_bc_status(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Get the current status of the business case track.

        Args:
            slug: Feature slug

        Returns:
            Dictionary with BC track details, or None if feature not found

        Example return:
            {
                "slug": "mk-feature-recovery",
                "bc_status": "pending_approval",
                "version": 2,
                "assumptions_complete": True,
                "required_approvers": ["Jack Approver"],
                "pending_approvers": ["Jack Approver"],
                "approvals": [],
                "is_approved": False,
                "is_rejected": False
            }
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        # Load BC track
        bc_track = BusinessCaseTrack(feature_path)

        return {
            "slug": slug,
            "bc_status": bc_track.status.value,
            "version": bc_track.current_version,
            "assumptions_complete": bc_track.assumptions.is_complete,
            "baseline_metrics": bc_track.assumptions.baseline_metrics,
            "impact_assumptions": bc_track.assumptions.impact_assumptions,
            "required_approvers": bc_track._required_approvers,
            "pending_approvers": bc_track.pending_approvers,
            "approvals": [a.to_dict() for a in bc_track.approvals],
            "is_approved": bc_track.is_approved,
            "is_rejected": bc_track.is_rejected,
        }

    # ========== Engineering Track Methods ==========

    def start_engineering_track(
        self,
        slug: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Start the engineering track for a feature.

        This initializes the engineering track and sets it to IN_PROGRESS status.
        Creates the engineering folder structure if it doesn't exist.

        Args:
            slug: Feature slug

        Returns:
            Dictionary with engineering track status, or None if feature not found

        Example:
            engine.start_engineering_track(slug="mk-feature-recovery")

        Example return:
            {
                "slug": "mk-feature-recovery",
                "eng_status": "in_progress",
                "message": "Engineering track started",
                "success": True
            }
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        # Load feature state to get current user
        state = FeatureState.load(feature_path)
        if not state:
            return None

        # Initialize engineering track
        eng_track = EngineeringTrack(feature_path)

        # Start the track
        import config_loader

        user_name = config_loader.get_user_name()
        result = eng_track.start(initiated_by=user_name)

        if not result.success:
            return {
                "slug": slug,
                "eng_status": eng_track.status.value,
                "success": False,
                "message": result.message,
            }

        # Update feature state track status
        self.update_track_status(
            slug=slug,
            track_name="engineering",
            status=TrackStatus.IN_PROGRESS,
            auto_sync=True,
        )

        # Log action
        self._log_action(
            feature_path=feature_path,
            action="Engineering track started",
            status=state.get_derived_status(),
        )

        return {
            "slug": slug,
            "eng_status": eng_track.status.value,
            "success": True,
            "message": result.message,
            "started_by": user_name,
        }

    def create_adr(
        self,
        slug: str,
        title: str,
        context: str,
        decision: str,
        consequences: str,
        status: str = "proposed",
        supersedes: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create an Architecture Decision Record (ADR) for a feature.

        ADRs document important architectural decisions along with their
        context and consequences. They are stored in {feature}/engineering/adrs/.

        Args:
            slug: Feature slug
            title: Short descriptive title for the ADR
            context: What is the issue motivating this decision?
            decision: What is the change being proposed/made?
            consequences: What becomes easier/harder as a result?
            status: Initial status (proposed, accepted). Default: proposed
            supersedes: Optional ADR number that this new ADR supersedes

        Returns:
            Dictionary with ADR details, or None if feature not found

        Example:
            engine.create_adr(
                slug="mk-feature-recovery",
                title="Use Redis for Session Storage",
                context="Need to share sessions across multiple app instances",
                decision="Use Redis as centralized session store",
                consequences="Adds infrastructure dependency but enables horizontal scaling"
            )

        Example return:
            {
                "slug": "mk-feature-recovery",
                "adr_number": 1,
                "title": "Use Redis for Session Storage",
                "file_path": "/path/to/feature/engineering/adrs/adr-001-use-redis-for-session-storage.md",
                "message": "ADR-001 created: Use Redis for Session Storage",
                "success": True
            }
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        # Load engineering track
        eng_track = EngineeringTrack(feature_path)

        # Ensure track is started
        if eng_track.status == EngineeringStatus.NOT_STARTED:
            return {
                "slug": slug,
                "success": False,
                "message": "Engineering track not started. Call start_engineering_track() first.",
            }

        # Parse status
        try:
            adr_status = ADRStatus(status)
        except ValueError:
            adr_status = ADRStatus.PROPOSED

        # Get current user
        import config_loader

        user_name = config_loader.get_user_name()

        # Create ADR
        result = eng_track.create_adr(
            title=title,
            context=context,
            decision=decision,
            consequences=consequences,
            status=adr_status,
            created_by=user_name,
            supersedes=supersedes,
        )

        if not result.success:
            return {"slug": slug, "success": False, "message": result.message}

        # Log action
        self._log_action(
            feature_path=feature_path,
            action=f"ADR-{result.adr_number:03d} created: {title[:30]}...",
            status="In Progress",
        )

        # Record as a decision in feature state
        self.record_decision(
            slug=slug,
            decision=f"ADR-{result.adr_number:03d}: {title}",
            rationale=context,
            decided_by=user_name,
            phase="engineering",
            metadata={
                "adr_number": result.adr_number,
                "adr_status": status,
                "consequences": consequences,
            },
        )

        return {
            "slug": slug,
            "adr_number": result.adr_number,
            "title": title,
            "status": status,
            "file_path": str(result.file_path) if result.file_path else None,
            "success": True,
            "message": result.message,
        }

    def record_engineering_estimate(
        self,
        slug: str,
        estimate: str,
        breakdown: Optional[Dict[str, str]] = None,
        confidence: str = "medium",
        assumptions: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Record an engineering effort estimate for a feature.

        Estimates use T-shirt sizes (S, M, L, XL) with optional component breakdown.

        Args:
            slug: Feature slug
            estimate: Overall T-shirt size (S, M, L, XL)
            breakdown: Optional component breakdown
                       (e.g., {"frontend": "S", "backend": "M", "testing": "S"})
            confidence: Confidence level (low, medium, high). Default: medium
            assumptions: Optional list of assumptions the estimate is based on

        Returns:
            Dictionary with estimate details, or None if feature not found

        Example:
            engine.record_engineering_estimate(
                slug="mk-feature-recovery",
                estimate="M",
                breakdown={"frontend": "S", "backend": "M", "testing": "S"},
                confidence="medium",
                assumptions=["Design finalized", "API spec available"]
            )

        Example return:
            {
                "slug": "mk-feature-recovery",
                "estimate": "M",
                "breakdown": {"frontend": "S", "backend": "M", "testing": "S"},
                "confidence": "medium",
                "message": "Estimate recorded: M",
                "success": True
            }
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        # Load engineering track
        eng_track = EngineeringTrack(feature_path)

        # Ensure track is started
        if eng_track.status == EngineeringStatus.NOT_STARTED:
            return {
                "slug": slug,
                "success": False,
                "message": "Engineering track not started. Call start_engineering_track() first.",
            }

        # Get current user
        import config_loader

        user_name = config_loader.get_user_name()

        # Record estimate
        result = eng_track.record_estimate(
            estimate=estimate,
            breakdown=breakdown,
            confidence=confidence,
            assumptions=assumptions,
            estimated_by=user_name,
        )

        if not result.success:
            return {"slug": slug, "success": False, "message": result.message}

        # Log action
        self._log_action(
            feature_path=feature_path,
            action=f"Engineering estimate recorded: {estimate.upper()}",
            status="In Progress",
        )

        return {
            "slug": slug,
            "estimate": estimate.upper(),
            "breakdown": breakdown,
            "confidence": confidence,
            "assumptions": assumptions,
            "estimated_by": user_name,
            "success": True,
            "message": result.message,
        }

    def get_engineering_status(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Get the current status of the engineering track.

        Args:
            slug: Feature slug

        Returns:
            Dictionary with engineering track details, or None if feature not found

        Example return:
            {
                "slug": "mk-feature-recovery",
                "eng_status": "in_progress",
                "adrs": [...],
                "adrs_count": 2,
                "decisions_count": 3,
                "estimate": {"overall": "M", "breakdown": {...}},
                "has_estimate": True,
                "risks": [...],
                "dependencies": [...]
            }
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        # Load engineering track
        eng_track = EngineeringTrack(feature_path)

        return {
            "slug": slug,
            "eng_status": eng_track.status.value,
            "started_at": (
                eng_track._started_at.isoformat() if eng_track._started_at else None
            ),
            "started_by": eng_track._started_by,
            "adrs": [a.to_dict() for a in eng_track.adrs],
            "adrs_count": len(eng_track.adrs),
            "active_adrs_count": len(eng_track.active_adrs),
            "decisions": [d.to_dict() for d in eng_track.decisions],
            "decisions_count": len(eng_track.decisions),
            "estimate": eng_track.estimate.to_dict() if eng_track.estimate else None,
            "has_estimate": eng_track.has_estimate,
            "risks": [r.to_dict() for r in eng_track.risks],
            "pending_risks_count": len(eng_track.pending_risks),
            "dependencies": [d.to_dict() for d in eng_track.dependencies],
            "blocking_dependencies_count": len(eng_track.blocking_dependencies),
        }

    def record_technical_decision(
        self,
        slug: str,
        decision: str,
        rationale: str,
        category: str = "general",
        related_adr: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Record a technical decision for a feature.

        Technical decisions capture choices made during engineering that
        may not warrant a full ADR but should still be documented.

        Args:
            slug: Feature slug
            decision: What was decided
            rationale: Why this decision was made
            category: Category (architecture, implementation, tooling, testing)
            related_adr: Optional ADR number this decision relates to

        Returns:
            Dictionary with decision details, or None if feature not found

        Example:
            engine.record_technical_decision(
                slug="mk-feature-recovery",
                decision="Use TypeScript for frontend components",
                rationale="Team expertise and type safety benefits",
                category="tooling"
            )
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        # Load engineering track
        eng_track = EngineeringTrack(feature_path)

        # Ensure track is started
        if eng_track.status == EngineeringStatus.NOT_STARTED:
            return {
                "slug": slug,
                "success": False,
                "message": "Engineering track not started. Call start_engineering_track() first.",
            }

        # Get current user
        import config_loader

        user_name = config_loader.get_user_name()

        # Record decision
        result = eng_track.record_technical_decision(
            decision=decision,
            rationale=rationale,
            decided_by=user_name,
            category=category,
            related_adr=related_adr,
        )

        if not result.success:
            return {"slug": slug, "success": False, "message": result.message}

        # Log action
        truncated = decision[:40] + "..." if len(decision) > 40 else decision
        self._log_action(
            feature_path=feature_path,
            action=f"Technical decision: {truncated}",
            status="In Progress",
        )

        return {
            "slug": slug,
            "decision": decision,
            "rationale": rationale,
            "category": category,
            "decided_by": user_name,
            "related_adr": related_adr,
            "success": True,
            "message": result.message,
        }

    def add_engineering_risk(
        self,
        slug: str,
        risk: str,
        impact: str = "medium",
        likelihood: str = "medium",
        mitigation: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Add a technical risk to the engineering track.

        Args:
            slug: Feature slug
            risk: Description of the risk
            impact: Impact level (high, medium, low)
            likelihood: Likelihood of occurrence (high, medium, low)
            mitigation: How to mitigate the risk

        Returns:
            Dictionary with risk details, or None if feature not found

        Example:
            engine.add_engineering_risk(
                slug="mk-feature-recovery",
                risk="Redis cluster may experience downtime during migration",
                impact="high",
                likelihood="low",
                mitigation="Implement fallback to database sessions"
            )
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        # Load engineering track
        eng_track = EngineeringTrack(feature_path)

        # Ensure track is started
        if eng_track.status == EngineeringStatus.NOT_STARTED:
            return {
                "slug": slug,
                "success": False,
                "message": "Engineering track not started. Call start_engineering_track() first.",
            }

        # Get current user
        import config_loader

        user_name = config_loader.get_user_name()

        # Add risk
        result = eng_track.add_risk(
            risk=risk,
            impact=impact,
            likelihood=likelihood,
            mitigation=mitigation,
            owner=user_name,
        )

        if not result.success:
            return {"slug": slug, "success": False, "message": result.message}

        return {
            "slug": slug,
            "risk": risk,
            "impact": impact,
            "likelihood": likelihood,
            "mitigation": mitigation,
            "success": True,
            "message": result.message,
        }

    def add_engineering_dependency(
        self,
        slug: str,
        name: str,
        type: str = "internal",
        description: str = "",
        eta: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Add a technical dependency to the engineering track.

        Args:
            slug: Feature slug
            name: Name of the dependency
            type: Type (internal_team, external_api, infrastructure, library)
            description: What the dependency is
            eta: Expected availability date

        Returns:
            Dictionary with dependency details, or None if feature not found

        Example:
            engine.add_engineering_dependency(
                slug="mk-feature-recovery",
                name="Payment Gateway API v2",
                type="external_api",
                description="New API version with improved session handling",
                eta="2026-03-01"
            )
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        # Load engineering track
        eng_track = EngineeringTrack(feature_path)

        # Ensure track is started
        if eng_track.status == EngineeringStatus.NOT_STARTED:
            return {
                "slug": slug,
                "success": False,
                "message": "Engineering track not started. Call start_engineering_track() first.",
            }

        # Get current user
        import config_loader

        user_name = config_loader.get_user_name()

        # Add dependency
        result = eng_track.add_dependency(
            name=name, type=type, description=description, eta=eta, owner=user_name
        )

        if not result.success:
            return {"slug": slug, "success": False, "message": result.message}

        return {
            "slug": slug,
            "name": name,
            "type": type,
            "description": description,
            "eta": eta,
            "success": True,
            "message": result.message,
        }

    def complete_engineering_track(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Mark the engineering track as complete.

        Requires at least one ADR or technical decision and an estimate.

        Args:
            slug: Feature slug

        Returns:
            Dictionary with completion status, or None if feature not found

        Example:
            engine.complete_engineering_track(slug="mk-feature-recovery")
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        # Load engineering track
        eng_track = EngineeringTrack(feature_path)

        # Complete the track
        result = eng_track.complete()

        if not result.success:
            return {
                "slug": slug,
                "eng_status": eng_track.status.value,
                "success": False,
                "message": result.message,
            }

        # Update feature state track status
        self.update_track_status(
            slug=slug,
            track_name="engineering",
            status=TrackStatus.COMPLETE,
            auto_sync=True,
        )

        # Log action
        self._log_action(
            feature_path=feature_path,
            action="Engineering track completed",
            status="In Progress",
        )

        return {
            "slug": slug,
            "eng_status": eng_track.status.value,
            "success": True,
            "message": result.message,
            "adrs_count": len(eng_track.adrs),
            "decisions_count": len(eng_track.decisions),
            "estimate": eng_track.estimate.overall if eng_track.estimate else None,
        }
