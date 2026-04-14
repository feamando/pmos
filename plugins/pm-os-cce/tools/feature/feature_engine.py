"""
PM-OS CCE Feature Engine (v5.0)

Main orchestrator for the Context Creation Engine. Manages the complete
feature lifecycle from initialization through decision gate. Delegates
to specialized modules: product identification, brain entities, alias
management, bidirectional sync, quality gates, and Cowork project generation.

Usage:
    from pm_os_cce.tools.feature.feature_engine import FeatureEngine
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from core.config_loader import get_config
    except ImportError:
        get_config = None

try:
    from pm_os_cce.tools.feature.alias_manager import AliasManager, MatchResult
except ImportError:
    from feature.alias_manager import AliasManager, MatchResult

try:
    from pm_os_cce.tools.feature.bidirectional_sync import BidirectionalSync
except ImportError:
    from feature.bidirectional_sync import BidirectionalSync

try:
    from pm_os_cce.tools.feature.brain_entity_creator import (
        BrainEntityCreator,
        BrainEntityResult,
        generate_entity_name,
    )
except ImportError:
    from feature.brain_entity_creator import (
        BrainEntityCreator,
        BrainEntityResult,
        generate_entity_name,
    )

try:
    from pm_os_cce.tools.feature.feature_state import (
        AliasInfo,
        FeaturePhase,
        FeatureState,
        TrackStatus,
        generate_brain_entity_name,
        generate_slug,
    )
except ImportError:
    from feature.feature_state import (
        AliasInfo,
        FeaturePhase,
        FeatureState,
        TrackStatus,
        generate_brain_entity_name,
        generate_slug,
    )

try:
    from pm_os_cce.tools.feature.product_identifier import (
        IdentificationResult,
        IdentificationSource,
        ProductIdentifier,
        ProductInfo,
    )
except ImportError:
    from feature.product_identifier import (
        IdentificationResult,
        IdentificationSource,
        ProductIdentifier,
        ProductInfo,
    )

logger = logging.getLogger(__name__)

# Optional imports - tracks and discovery
DiscoveryResearcher = None
DiscoveryResult = None
try:
    from pm_os_cce.tools.feature.discovery_researcher import (
        DiscoveryResearcher,
        DiscoveryResult,
    )
except ImportError:
    try:
        from feature.discovery_researcher import DiscoveryResearcher, DiscoveryResult
    except ImportError:
        pass

BusinessCaseTrack = None
BCStatus = None
try:
    from pm_os_cce.tools.feature.tracks.business_case import (
        BCStatus,
        BCTrackResult,
        BusinessCaseTrack,
    )
except ImportError:
    try:
        from feature.tracks.business_case import (
            BCStatus,
            BCTrackResult,
            BusinessCaseTrack,
        )
    except ImportError:
        pass

EngineeringTrack = None
EngineeringStatus = None
ADRStatus = None
try:
    from pm_os_cce.tools.feature.tracks.engineering import (
        ADRStatus,
        EngineeringStatus,
        EngineeringTrack,
        EngineeringTrackResult,
    )
except ImportError:
    try:
        from feature.tracks.engineering import (
            ADRStatus,
            EngineeringStatus,
            EngineeringTrack,
            EngineeringTrackResult,
        )
    except ImportError:
        pass

# Optional Cowork project generation
CoworkProjectGenerator = None
try:
    from pm_os_cce.tools.feature.cowork_project_generator import CoworkProjectGenerator
except ImportError:
    try:
        from feature.cowork_project_generator import CoworkProjectGenerator
    except ImportError:
        pass


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
    discovery_result: Any = None


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
    """Main orchestrator for the Context Creation Engine.

    Manages the complete feature lifecycle:
    1. Initialization - Create feature folder, state file, brain entity
    2. Signal Analysis - Gather and analyze signals
    3. Context Document - Generate and iterate context doc
    4. Parallel Tracks - Design, Business Case, Engineering
    5. Decision Gate - Final review
    6. Output Generation - PRD, spec export

    All product names, user names, and organization details come from config.
    No hardcoded values.
    """

    def __init__(self, user_path: Optional[Path] = None):
        """Initialize the feature engine.

        Args:
            user_path: Path to user/ directory. If None, auto-detected from config.
        """
        self._config = None
        self._raw_config = {}
        self.user_path = user_path
        self.products_config = {}
        self.organization = {}

        if get_config is not None:
            try:
                self._config = get_config()
                self.user_path = user_path or Path(self._config.user_path)
                self._raw_config = (
                    self._config.config if hasattr(self._config, "config") else {}
                )
                self.products_config = self._raw_config.get("products", {})
                self.organization = self.products_config.get("organization", {})
            except Exception:
                pass

        # Initialize sub-modules
        self.alias_manager = AliasManager()
        self.product_identifier = ProductIdentifier(user_path=self.user_path)
        self._sync = BidirectionalSync(user_path=self.user_path)

    # ========== Config Helpers ==========

    def _get_user_name(self) -> str:
        """Get user name from config."""
        if self._config and hasattr(self._config, "get_user_name"):
            return self._config.get_user_name()
        return self._raw_config.get("user", {}).get("name", "PM")

    def _get_product_info(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get product information from config.

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
        """Get the path for a feature folder.

        Args:
            product_id: Product ID
            slug: Feature slug

        Returns:
            Path to feature folder
        """
        org_id = self.organization.get("id", "default")
        return self.user_path / "products" / org_id / product_id / slug

    # ========== Folder and Template Creation ==========

    def _create_feature_folder(
        self, feature_path: Path, slug: str, title: str, product_id: str
    ) -> None:
        """Create the feature folder structure.

        Creates:
            {feature-slug}/
            {feature-slug}/{feature-slug}-context.md
            {feature-slug}/context-docs/
            {feature-slug}/business-case/
            {feature-slug}/engineering/
            {feature-slug}/engineering/adrs/

        Args:
            feature_path: Path to create
            slug: Feature slug
            title: Feature title
            product_id: Product ID
        """
        feature_path.mkdir(parents=True, exist_ok=True)
        (feature_path / "context-docs").mkdir(exist_ok=True)
        (feature_path / "business-case").mkdir(exist_ok=True)
        (feature_path / "engineering").mkdir(exist_ok=True)
        (feature_path / "engineering" / "adrs").mkdir(exist_ok=True)

        context_file = feature_path / f"{slug}-context.md"
        if not context_file.exists():
            context_content = self._generate_context_template(slug, title, product_id)
            context_file.write_text(context_content)

    def _generate_context_template(self, slug: str, title: str, product_id: str) -> str:
        """Generate initial context file content.

        Args:
            slug: Feature slug
            title: Feature title
            product_id: Product ID

        Returns:
            Context file content
        """
        now = datetime.now().strftime("%Y-%m-%d")
        user_name = self._get_user_name()

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

    # ========== Brain Entity ==========

    def _create_brain_entity(self, title: str, slug: str, product_id: str) -> Path:
        """Create a Brain entity for the feature using v2 schema format.

        Args:
            title: Feature title
            slug: Feature slug
            product_id: Product ID

        Returns:
            Path to created (or existing) entity file
        """
        product_info = self._get_product_info(product_id)
        product_name = (
            product_info.get("name", product_id) if product_info else product_id
        )
        organization_id = self.organization.get("id", "default")

        creator = BrainEntityCreator(self.user_path)
        result = creator.create_feature_entity(
            title=title,
            slug=slug,
            product_id=product_id,
            product_name=product_name,
            organization_id=organization_id,
            description=None,
            source="context_engine",
            confidence=0.8,
        )

        return result.entity_path

    # ========== Discovery ==========

    def _run_discovery(
        self,
        feature_path: Path,
        title: str,
        product_id: str,
        state: FeatureState,
    ) -> Any:
        """Run feature-scoped discovery across Brain and Master Sheet.

        Non-blocking: returns None if discovery fails or is unavailable.

        Args:
            feature_path: Path to feature folder
            title: Feature title
            product_id: Product identifier
            state: FeatureState to update with discovery results

        Returns:
            DiscoveryResult if successful, None otherwise
        """
        if DiscoveryResearcher is None:
            return None

        brain_path = None
        if self.user_path:
            brain_path = self.user_path / "brain"
        if not brain_path or not brain_path.exists():
            return None

        try:
            product_info = self._get_product_info(product_id)
            product_name = product_info.get("name", "") if product_info else ""

            researcher = DiscoveryResearcher(brain_path)
            result = researcher.run_discovery(
                feature_title=title,
                product_id=product_id,
                product_name=product_name,
            )

            state.discovery = {
                "ran_at": datetime.now().isoformat(),
                "researchers": result.sources_searched,
                "findings_count": len(result.findings),
                "completeness_coverage": result.coverage,
                "related_entities": result.related_entities[:20],
            }
            state.save(feature_path)

            logger.info(
                f"Discovery complete for '{title}': "
                f"{len(result.findings)} findings, "
                f"coverage: {sum(result.coverage.values())}/{len(result.coverage)}"
            )
            return result

        except Exception as e:
            logger.warning(f"Discovery failed for '{title}': {e}")
            return None

    # ========== Feature Lifecycle ==========

    def create_feature_folder(
        self, product_id: str, feature_title: str
    ) -> Tuple[bool, Path, str]:
        """Create a feature folder standalone (without full start_feature workflow).

        Args:
            product_id: Product ID
            feature_title: Human-readable feature title

        Returns:
            Tuple of (success, feature_path, message)
        """
        product_info = self._get_product_info(product_id)
        if not product_info:
            available_products = [
                p.get("id") for p in self.products_config.get("items", [])
            ]
            return (
                False,
                Path(),
                f"Product '{product_id}' not found in config. Available: {available_products}",
            )

        slug = generate_slug(feature_title, product_id)
        feature_path = self._get_feature_path(product_id, slug)

        if feature_path.exists() and (feature_path / "feature-state.yaml").exists():
            return (
                False,
                feature_path,
                f"Feature folder already exists at {feature_path} with feature-state.yaml",
            )

        try:
            self._create_feature_folder(feature_path, slug, feature_title, product_id)
        except (PermissionError, OSError) as e:
            return (False, feature_path, str(e))

        user_name = self._get_user_name()
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

        return (True, feature_path, f"Feature folder created at {feature_path}")

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
        """Initialize a feature with automatic product identification.

        Follows PRD Section C.6 priority order:
        1. Explicit product flag
        2. Master Sheet lookup
        3. Current daily context
        4. Signal source (channel inference)
        5. Return list for user selection

        Args:
            title: Feature title
            product: Optional explicit product ID, name, or abbreviation
            channel_name: Optional Slack channel for inference
            from_insight: Optional insight ID
            priority: Priority level
            target_date: Optional target date
            check_duplicates: Whether to check for similar features

        Returns:
            InitializationResult with feature details or product selection options
        """
        identification = self.product_identifier.identify_product(
            explicit_product=product,
            topic_name=title,
            channel_name=channel_name,
            check_master_sheet=True,
            check_daily_context=True,
        )

        if not identification.found:
            return InitializationResult(
                success=False,
                feature_slug="",
                feature_path=Path(),
                message=identification.message,
                needs_product_selection=True,
                product_selection_result=identification,
            )

        return self.start_feature(
            title=title,
            product_id=identification.product_id,
            from_insight=from_insight,
            priority=priority,
            target_date=target_date,
            check_duplicates=check_duplicates,
        )

    def get_products(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get list of available products from config."""
        products = self.product_identifier.get_products_from_config(active_only)
        return [p.to_dict() for p in products]

    def format_product_selection(self, result: InitializationResult) -> str:
        """Format a product selection prompt for display."""
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
        """Initialize a new feature when product is known.

        Args:
            title: Feature title
            product_id: Product ID
            from_insight: Optional insight ID
            priority: Priority level
            target_date: Optional target date
            check_duplicates: Whether to check for similar features

        Returns:
            InitializationResult with feature details
        """
        product_info = self._get_product_info(product_id)
        if not product_info:
            return InitializationResult(
                success=False,
                feature_slug="",
                feature_path=Path(),
                message=f"Product '{product_id}' not found in config",
            )

        slug = generate_slug(title, product_id)

        # Check for duplicates
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
                return InitializationResult(
                    success=False,
                    feature_slug=slug,
                    feature_path=self._get_feature_path(product_id, slug),
                    message=match_result.question or "",
                    linked_to_existing=False,
                    existing_feature=match_result.existing_name,
                )

        feature_path = self._get_feature_path(product_id, slug)

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

        try:
            self._create_feature_folder(feature_path, slug, title, product_id)
        except (PermissionError, OSError) as e:
            return InitializationResult(
                success=False,
                feature_slug=slug,
                feature_path=feature_path,
                message=str(e),
            )

        brain_entity_path = self._create_brain_entity(title, slug, product_id)
        brain_ref = f"[[Entities/{generate_brain_entity_name(title)}]]"

        user_name = self._get_user_name()
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

        state.enter_phase(
            FeaturePhase.INITIALIZATION,
            metadata={
                "from_insight": from_insight,
                "priority": priority,
                "target_date": target_date,
            },
        )
        state.save(feature_path)

        discovery_result = self._run_discovery(feature_path, title, product_id, state)

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
            discovery_result=discovery_result,
        )

    def start_feature_with_deep_research(
        self,
        title: str,
        product_id: str,
        questionnaire_result=None,
        research_opt_in: bool = False,
        priority: str = "medium",
        from_insight: Optional[str] = None,
    ) -> InitializationResult:
        """Initialize a feature with optional questionnaire and deep research.

        Args:
            title: Feature title
            product_id: Product ID
            questionnaire_result: QuestionnaireResult or dict with answers
            research_opt_in: Whether to run deep research pipeline
            priority: Priority level
            from_insight: Optional insight ID

        Returns:
            InitializationResult with feature details
        """
        result = self.start_feature(
            title=title,
            product_id=product_id,
            priority=priority,
            from_insight=from_insight,
        )

        if not result.success or result.state is None:
            return result

        state = result.state
        feature_path = result.feature_path

        if questionnaire_result is not None:
            if hasattr(questionnaire_result, "to_dict"):
                state.questionnaire = questionnaire_result.to_dict()
            elif isinstance(questionnaire_result, dict):
                state.questionnaire = questionnaire_result
            else:
                state.questionnaire = dict(questionnaire_result)

            state.enter_phase(
                FeaturePhase.QUESTIONNAIRE,
                metadata={"questionnaire_stored": True},
            )
            state.save(feature_path)

        if research_opt_in and questionnaire_result is not None:
            try:
                state.enter_phase(
                    FeaturePhase.DEEP_RESEARCH,
                    metadata={"research_opt_in": True},
                )

                try:
                    from pm_os_cce.tools.research.research_plan_generator import (
                        ResearchPlanGenerator,
                    )
                    from pm_os_cce.tools.research.deep_research_swarm import (
                        DeepResearchSwarm,
                    )
                    from pm_os_cce.tools.research.research_insight_bridge import (
                        ResearchInsightBridge,
                    )
                except ImportError:
                    from research.research_plan_generator import ResearchPlanGenerator
                    from research.deep_research_swarm import DeepResearchSwarm
                    from research.research_insight_bridge import ResearchInsightBridge

                generator = ResearchPlanGenerator()
                probes = generator.probe_available_sources()
                scan = generator.first_pass_scan(questionnaire_result, probes)
                plan = generator.generate_plan(
                    feature_title=title,
                    questionnaire=state.questionnaire,
                    source_probes=probes,
                    first_pass_results=scan,
                )

                swarm = DeepResearchSwarm()
                swarm_result = swarm.execute_plan(plan, feature_path=feature_path)

                bridge = ResearchInsightBridge()
                bridge.convert_to_insight(swarm_result)

                state.research_plan = {
                    "feature_title": plan.feature_title,
                    "total_tasks": len(plan.internal_tasks) + len(plan.external_tasks),
                    "quality_score": swarm_result.quality_score,
                    "total_findings": swarm_result.total_findings,
                }

                state.enter_phase(FeaturePhase.SIGNAL_ANALYSIS)
                state.save(feature_path)

            except Exception as e:
                logger.warning(f"Deep research failed (non-blocking): {e}")
                state.save(feature_path)
        elif questionnaire_result is not None:
            state.enter_phase(FeaturePhase.SIGNAL_ANALYSIS)
            state.save(feature_path)

        return InitializationResult(
            success=True,
            feature_slug=result.feature_slug,
            feature_path=feature_path,
            state=state,
            message=result.message,
            discovery_result=result.discovery_result,
        )

    # ========== Feature Query ==========

    def check_feature(self, slug: str) -> Optional[FeatureStatus]:
        """Get the current status of a feature.

        Args:
            slug: Feature slug

        Returns:
            FeatureStatus or None if not found
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        state = FeatureState.load(feature_path)
        if not state:
            return None

        pending_items = self._get_pending_items(state)
        blockers = self._get_blockers(state)

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
        """Find a feature by slug across all products.

        Args:
            slug: Feature slug

        Returns:
            Path to feature folder or None
        """
        if not self.user_path:
            return None

        products_path = self.user_path / "products"
        if not products_path.exists():
            return None

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
        """Get list of pending items for a feature."""
        pending = []

        for track_name, track in state.tracks.items():
            if track.status == TrackStatus.PENDING_INPUT:
                pending.append(f"{track_name}: Awaiting input")
            elif track.status == TrackStatus.PENDING_APPROVAL:
                pending.append(f"{track_name}: Awaiting approval")

        if "design" in state.tracks and state.tracks["design"].status != TrackStatus.NOT_STARTED:
            if not state.artifacts.get("figma"):
                pending.append("Design: Figma URL required")
            if not state.artifacts.get("wireframes_url"):
                pending.append("Design: Wireframes URL required")

        return pending

    def _get_blockers(self, state: FeatureState) -> List[str]:
        """Get list of blockers for a feature."""
        blockers = []

        for track_name, track in state.tracks.items():
            if track.status == TrackStatus.BLOCKED:
                blockers.append(f"{track_name}: Track is blocked")

        if state.current_phase == FeaturePhase.PARALLEL_TRACKS:
            if "context" in state.tracks and state.tracks["context"].status != TrackStatus.COMPLETE:
                blockers.append("Context document must be complete before decision gate")

        if state.current_phase == FeaturePhase.DECISION_GATE:
            if "business_case" in state.tracks and state.tracks["business_case"].status != TrackStatus.COMPLETE:
                blockers.append("Business case approval required")

        return blockers

    def resume_feature(self, slug: str) -> Optional[Dict[str, Any]]:
        """Resume a paused or inactive feature.

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

    def list_features(
        self, product_id: Optional[str] = None, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all features, optionally filtered.

        Args:
            product_id: Filter by product
            status: Filter by status

        Returns:
            List of feature summaries
        """
        features = []
        if not self.user_path:
            return features

        products_path = self.user_path / "products"
        if not products_path.exists():
            return features

        for org_path in products_path.iterdir():
            if not org_path.is_dir():
                continue
            for product_path in org_path.iterdir():
                if not product_path.is_dir():
                    continue
                if product_id and product_path.name != product_id:
                    continue
                for feature_path in product_path.iterdir():
                    if not feature_path.is_dir():
                        continue
                    if not (feature_path / "feature-state.yaml").exists():
                        continue
                    state = FeatureState.load(feature_path)
                    if not state:
                        continue
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

    # ========== Action Log ==========

    def _log_action(
        self,
        feature_path: Path,
        action: str,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        deadline: Optional[str] = None,
    ) -> bool:
        """Add an action to the context file's action log.

        Called automatically on phase transitions, decisions, and track changes.

        Args:
            feature_path: Path to the feature folder
            action: Description of the action
            status: Optional status
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
            logger.warning(f"Failed to add action to log: {e}")
            return False

    # ========== Artifact Management ==========

    def attach_artifact(self, slug: str, artifact_type: str, url: str) -> bool:
        """Attach an external artifact to a feature.

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

        self._update_context_references(feature_path, state)

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
        """Update the context file's References section with artifacts."""
        context_file = feature_path / state.context_file
        if not context_file.exists():
            return

        content = context_file.read_text()

        # Try to use ArtifactManager for consistent formatting
        ArtifactManager = None
        ArtifactType = None
        try:
            from pm_os_cce.tools.feature.artifact_manager import (
                ArtifactManager,
                ArtifactType,
            )
        except ImportError:
            try:
                from feature.artifact_manager import ArtifactManager, ArtifactType
            except ImportError:
                pass

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

        refs = []
        for artifact_key, artifact_url in state.artifacts.items():
            if artifact_url:
                label = artifact_labels.get(artifact_key, artifact_key)
                refs.append(f"- **{label}**: [{label}]({artifact_url})")

        if not refs:
            refs.append("*Links to artifacts will be added as they are attached*")

        refs_text = "\n".join(refs)
        pattern = r"(## References\n).*?(\n## |\Z)"
        replacement = f"\\1{refs_text}\n\n\\2"
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

        if new_content != content:
            context_file.write_text(new_content)

    # ========== Phase and Decision Tracking ==========

    def record_phase_transition(
        self,
        slug: str,
        from_phase: FeaturePhase,
        to_phase: FeaturePhase,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Record a phase transition for a feature.

        Args:
            slug: Feature slug
            from_phase: Phase transitioning from
            to_phase: Phase transitioning to
            metadata: Optional metadata

        Returns:
            Transition details dict, or None if not found
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        state = FeatureState.load(feature_path)
        if not state:
            return None

        entry = state.record_phase_transition(from_phase, to_phase, metadata)
        state.save(feature_path)

        self._log_action(
            feature_path=feature_path,
            action=f"Phase transition: {from_phase.value} -> {to_phase.value}",
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
        """Record a decision for a feature.

        Args:
            slug: Feature slug
            decision: What was decided
            rationale: Why
            decided_by: Who decided
            phase: Optional phase (defaults to current)
            metadata: Optional additional data

        Returns:
            Decision details dict, or None if not found
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        state = FeatureState.load(feature_path)
        if not state:
            return None

        decision_phase = phase or state.current_phase.value

        decision_entry = state.record_decision(
            phase=decision_phase,
            decision=decision,
            rationale=rationale,
            decided_by=decided_by,
            metadata=metadata,
        )
        state.save(feature_path)

        truncated_decision = decision[:50] + "..." if len(decision) > 50 else decision
        self._log_action(
            feature_path=feature_path,
            action=f"Decision: {truncated_decision}",
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
        """Get the phase history for a feature."""
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
        """Get decisions for a feature, optionally filtered by phase."""
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None
        state = FeatureState.load(feature_path)
        if not state:
            return None
        return state.get_decisions(phase)

    # ========== Track Status ==========

    def update_track_status(
        self,
        slug: str,
        track_name: str,
        status: TrackStatus,
        auto_sync: bool = True,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """Update a track's status and log the change.

        Args:
            slug: Feature slug
            track_name: Track name (context, design, business_case, engineering)
            status: New TrackStatus
            auto_sync: If True, sync derived status to context file and Master Sheet
            **kwargs: Additional fields to update on the track

        Returns:
            Update details dict, or None if not found
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        state = FeatureState.load(feature_path)
        if not state:
            return None

        previous_status = (
            state.tracks[track_name].status.value
            if track_name in state.tracks
            else "unknown"
        )

        state.update_track(track_name, status=status, **kwargs)
        state.save(feature_path)

        derived_status = state.get_derived_status()

        self._log_action(
            feature_path=feature_path,
            action=f"Track '{track_name}': {previous_status} -> {status.value}",
            status=derived_status,
        )

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
        """Get a phase summary for a feature."""
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None
        state = FeatureState.load(feature_path)
        if not state:
            return None
        return state.get_phase_summary()

    def get_feature_derived_status(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get the derived status based on track completion states."""
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
        """Sync a feature's derived status to context file and Master Sheet."""
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        result = self._sync.sync_from_state(feature_path)
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

    # ========== Business Case Track ==========

    def start_business_case(
        self,
        slug: str,
        approvers: Optional[List[str]] = None,
        baseline_metrics: Optional[Dict[str, Any]] = None,
        impact_assumptions: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Start the business case track for a feature.

        Args:
            slug: Feature slug
            approvers: Optional list of required approvers
            baseline_metrics: Optional initial baseline metrics
            impact_assumptions: Optional initial impact assumptions

        Returns:
            BC track status dict, or None if not found
        """
        if BusinessCaseTrack is None:
            return {"slug": slug, "success": False, "message": "BusinessCaseTrack not available"}

        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        state = FeatureState.load(feature_path)
        if not state:
            return None

        bc_track = BusinessCaseTrack(feature_path)
        user_name = self._get_user_name()
        result = bc_track.start(initiated_by=user_name)

        if not result.success:
            return {
                "slug": slug,
                "bc_status": bc_track.status.value,
                "success": False,
                "message": result.message,
            }

        if approvers:
            bc_track.set_required_approvers(approvers)
        if baseline_metrics or impact_assumptions:
            bc_track.update_assumptions(
                baseline_metrics=baseline_metrics, impact_assumptions=impact_assumptions
            )

        self.update_track_status(
            slug=slug, track_name="business_case", status=TrackStatus.IN_PROGRESS, auto_sync=True,
        )

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
        """Submit the business case for stakeholder approval.

        Args:
            slug: Feature slug
            approver: Stakeholder name. Defaults to first required approver.
            message: Optional message

        Returns:
            Submission status dict, or None if not found
        """
        if BusinessCaseTrack is None:
            return {"slug": slug, "success": False, "message": "BusinessCaseTrack not available"}

        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        bc_track = BusinessCaseTrack(feature_path)

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

        result = bc_track.submit_for_approval(approver=approver, message=message)
        if not result.success:
            return {
                "slug": slug,
                "bc_status": bc_track.status.value,
                "success": False,
                "message": result.message,
            }

        self.update_track_status(
            slug=slug, track_name="business_case", status=TrackStatus.PENDING_APPROVAL, auto_sync=True,
        )

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
        """Record a stakeholder approval or rejection for the business case.

        Args:
            slug: Feature slug
            approver: Approver name
            approved: True for approval, False for rejection
            approval_type: How approval was given (verbal, written, email, slack)
            reference: Link to evidence
            notes: Additional context

        Returns:
            Updated status dict, or None if not found
        """
        if BusinessCaseTrack is None or BCStatus is None:
            return {"slug": slug, "success": False, "message": "BusinessCaseTrack not available"}

        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        bc_track = BusinessCaseTrack(feature_path)
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
            slug=slug, track_name="business_case", status=track_status, auto_sync=True,
        )

        self._log_action(
            feature_path=feature_path,
            action=action_msg,
            status="In Progress" if track_status != TrackStatus.COMPLETE else "Done",
        )

        decision_text = f"Business case {'approved' if approved else 'rejected'}"
        if notes:
            decision_text += f": {notes[:100]}"

        self.record_decision(
            slug=slug,
            decision=decision_text,
            rationale=notes or f"{'Approved' if approved else 'Rejected'} by {approver}",
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
        """Get the current status of the business case track."""
        if BusinessCaseTrack is None:
            return None

        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

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

    # ========== Engineering Track ==========

    def start_engineering_track(self, slug: str) -> Optional[Dict[str, Any]]:
        """Start the engineering track for a feature.

        Args:
            slug: Feature slug

        Returns:
            Engineering track status dict, or None if not found
        """
        if EngineeringTrack is None:
            return {"slug": slug, "success": False, "message": "EngineeringTrack not available"}

        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        state = FeatureState.load(feature_path)
        if not state:
            return None

        eng_track = EngineeringTrack(feature_path)
        user_name = self._get_user_name()
        result = eng_track.start(initiated_by=user_name)

        if not result.success:
            return {
                "slug": slug,
                "eng_status": eng_track.status.value,
                "success": False,
                "message": result.message,
            }

        self.update_track_status(
            slug=slug, track_name="engineering", status=TrackStatus.IN_PROGRESS, auto_sync=True,
        )

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
        """Create an Architecture Decision Record (ADR).

        Args:
            slug: Feature slug
            title: ADR title
            context: Issue motivating the decision
            decision: Change being proposed/made
            consequences: What becomes easier/harder
            status: Initial status (proposed, accepted)
            supersedes: Optional ADR number this supersedes

        Returns:
            ADR details dict, or None if not found
        """
        if EngineeringTrack is None or EngineeringStatus is None or ADRStatus is None:
            return {"slug": slug, "success": False, "message": "EngineeringTrack not available"}

        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        eng_track = EngineeringTrack(feature_path)
        if eng_track.status == EngineeringStatus.NOT_STARTED:
            return {
                "slug": slug,
                "success": False,
                "message": "Engineering track not started. Call start_engineering_track() first.",
            }

        try:
            adr_status = ADRStatus(status)
        except ValueError:
            adr_status = ADRStatus.PROPOSED

        user_name = self._get_user_name()
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

        self._log_action(
            feature_path=feature_path,
            action=f"ADR-{result.adr_number:03d} created: {title[:30]}...",
            status="In Progress",
        )

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
        """Record an engineering effort estimate (T-shirt size).

        Args:
            slug: Feature slug
            estimate: T-shirt size (S, M, L, XL)
            breakdown: Optional component breakdown
            confidence: Confidence level (low, medium, high)
            assumptions: Optional list of assumptions

        Returns:
            Estimate details dict, or None if not found
        """
        if EngineeringTrack is None or EngineeringStatus is None:
            return {"slug": slug, "success": False, "message": "EngineeringTrack not available"}

        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        eng_track = EngineeringTrack(feature_path)
        if eng_track.status == EngineeringStatus.NOT_STARTED:
            return {
                "slug": slug,
                "success": False,
                "message": "Engineering track not started. Call start_engineering_track() first.",
            }

        user_name = self._get_user_name()
        result = eng_track.record_estimate(
            estimate=estimate,
            breakdown=breakdown,
            confidence=confidence,
            assumptions=assumptions,
            estimated_by=user_name,
        )

        if not result.success:
            return {"slug": slug, "success": False, "message": result.message}

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
        """Get the current status of the engineering track."""
        if EngineeringTrack is None:
            return None

        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

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
        """Record a technical decision for a feature.

        Args:
            slug: Feature slug
            decision: What was decided
            rationale: Why
            category: Category (architecture, implementation, tooling, testing)
            related_adr: Optional related ADR number

        Returns:
            Decision details dict, or None if not found
        """
        if EngineeringTrack is None or EngineeringStatus is None:
            return {"slug": slug, "success": False, "message": "EngineeringTrack not available"}

        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        eng_track = EngineeringTrack(feature_path)
        if eng_track.status == EngineeringStatus.NOT_STARTED:
            return {
                "slug": slug,
                "success": False,
                "message": "Engineering track not started. Call start_engineering_track() first.",
            }

        user_name = self._get_user_name()
        result = eng_track.record_technical_decision(
            decision=decision,
            rationale=rationale,
            decided_by=user_name,
            category=category,
            related_adr=related_adr,
        )

        if not result.success:
            return {"slug": slug, "success": False, "message": result.message}

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
        """Add a technical risk to the engineering track.

        Args:
            slug: Feature slug
            risk: Risk description
            impact: Impact level (high, medium, low)
            likelihood: Likelihood (high, medium, low)
            mitigation: Mitigation strategy

        Returns:
            Risk details dict, or None if not found
        """
        if EngineeringTrack is None or EngineeringStatus is None:
            return {"slug": slug, "success": False, "message": "EngineeringTrack not available"}

        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        eng_track = EngineeringTrack(feature_path)
        if eng_track.status == EngineeringStatus.NOT_STARTED:
            return {
                "slug": slug,
                "success": False,
                "message": "Engineering track not started. Call start_engineering_track() first.",
            }

        user_name = self._get_user_name()
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
        """Add a technical dependency to the engineering track.

        Args:
            slug: Feature slug
            name: Dependency name
            type: Type (internal_team, external_api, infrastructure, library)
            description: What the dependency is
            eta: Expected availability date

        Returns:
            Dependency details dict, or None if not found
        """
        if EngineeringTrack is None or EngineeringStatus is None:
            return {"slug": slug, "success": False, "message": "EngineeringTrack not available"}

        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        eng_track = EngineeringTrack(feature_path)
        if eng_track.status == EngineeringStatus.NOT_STARTED:
            return {
                "slug": slug,
                "success": False,
                "message": "Engineering track not started. Call start_engineering_track() first.",
            }

        user_name = self._get_user_name()
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
        """Mark the engineering track as complete.

        Args:
            slug: Feature slug

        Returns:
            Completion status dict, or None if not found
        """
        if EngineeringTrack is None:
            return {"slug": slug, "success": False, "message": "EngineeringTrack not available"}

        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        eng_track = EngineeringTrack(feature_path)
        result = eng_track.complete()

        if not result.success:
            return {
                "slug": slug,
                "eng_status": eng_track.status.value,
                "success": False,
                "message": result.message,
            }

        self.update_track_status(
            slug=slug, track_name="engineering", status=TrackStatus.COMPLETE, auto_sync=True,
        )

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

    # ========== Cowork Project Generation ==========

    def generate_cowork_project(
        self, slug: str, output_path: Optional[Path] = None
    ) -> Optional[Dict[str, Any]]:
        """Generate a Cowork project file from feature state.

        Delegates to CoworkProjectGenerator for the actual generation.

        Args:
            slug: Feature slug
            output_path: Optional output path

        Returns:
            Generation result dict, or None if not found
        """
        if CoworkProjectGenerator is None:
            return {"slug": slug, "success": False, "message": "CoworkProjectGenerator not available"}

        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        generator = CoworkProjectGenerator()
        result_path = generator.generate_from_feature(feature_path, output_path)

        if result_path:
            return {
                "slug": slug,
                "success": True,
                "output_path": str(result_path),
                "message": f"Cowork project generated at {result_path}",
            }

        return {
            "slug": slug,
            "success": False,
            "message": "Failed to generate Cowork project file",
        }
