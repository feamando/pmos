"""
PM-OS Context Creation Engine

Automates feature context development from signals through to PRD/spec output.
Integrates with PM-OS folder structure (products/{org}/{product}/{feature}/),
Master Sheet, and Brain.

Architecture Overview:
    - FeatureEngine: Main orchestrator for feature lifecycle
    - FeatureState: State management for features (feature-state.yaml)
    - InputGate: User input gate state machine
    - Tracks: Parallel workflow tracks (context, design, business_case, engineering)
    - Validators: Quality gates and validation framework
    - ArtifactManager: External artifact handling (Figma, Jira, etc.)

Usage:
    from tools.context_engine import FeatureEngine, FeatureState

    # Initialize a new feature
    engine = FeatureEngine()
    feature = engine.start_feature(
        title="OTP Checkout Recovery",
        product_id="meal-kit",
        from_insight="insight-otp-abandonment"
    )

    # Check feature status
    status = engine.check_feature("mk-feature-recovery")

    # Attach artifacts
    engine.attach_artifact("mk-feature-recovery", "figma", "https://figma.com/...")

Commands:
    /start-feature      - Initialize new feature with alias detection
    /analyze-signals    - Review and select insights
    /explore-insight    - Enrich selected insight
    /create-context-doc - Generate and iterate context document
    /business-case      - Manage business case track
    /design-track       - Manage design track
    /engineering-spec   - Manage engineering track
    /attach-artifact    - Add external artifact
    /validate-feature   - Check quality gates
    /check-feature      - View feature status
    /resume-feature     - Resume paused feature
    /decision-gate      - Final review and decision
    /generate-outputs   - Create PRD + spec input

See Also:
    - PRD: user/brain/Products/PM-OS/PRD_Context_Creation_Engine_v2.md
    - Master Sheet: tools.master_sheet.MasterSheetSync
    - Brain: tools.brain
    - Workspace: tools.workspace.WorkspaceManager

Author: PM-OS Team
Version: 1.0.0
"""

__version__ = "1.0.0"

from .alias_manager import (
    AliasManager,
    MatchResult,
    combined_similarity,
    jaccard_similarity,
    tokenize,
)
from .artifact_manager import (
    Artifact,
    ArtifactManager,
    ArtifactType,
    ArtifactValidation,
    guess_artifact_type,
)
from .bidirectional_sync import (
    BidirectionalSync,
    SyncDirection,
    SyncField,
    SyncResult,
    sync_context_to_master_sheet,
    sync_feature_state_to_context,
    sync_master_sheet_to_context,
)
from .blocker_detection import (
    Blocker,
    BlockerDetector,
    BlockerReport,
    BlockerSeverity,
    BlockerTrack,
    BlockerType,
    detect_blockers,
    format_blocker_list,
    get_blocker_report,
    has_blockers,
)
from .brain_entity_creator import (
    BrainEntityCreator,
    BrainEntityResult,
    generate_entity_name,
    generate_entity_slug,
)
from .context_doc_generator import ContextDocGenerator, ContextDocResult, InsightData
from .context_iteration_pipeline import (
    THRESHOLD_V1_TO_V2,
    THRESHOLD_V2_TO_V3,
    THRESHOLD_V3_COMPLETE,
    ContextIterationPipeline,
    PipelineResult,
    PipelineState,
    PipelineStatus,
    VersionInfo,
    VersionStatus,
)
from .feature_engine import FeatureEngine, FeatureStatus, InitializationResult

# Core classes
from .feature_state import (
    AliasInfo,
    Decision,
    FeaturePhase,
    FeatureState,
    PhaseEntry,
    TrackState,
    TrackStatus,
    generate_brain_entity_name,
    generate_slug,
)
from .gate_prompt_interface import (
    ACTION_DETAILS,
    OPTIONAL_INPUTS,
    ActionDetails,
    GatePromptInterface,
    OptionalInput,
    ParsedResponse,
    ResponseType,
    format_gate_prompt,
    parse_gate_response,
)
from .input_gate import (
    STATE_TRANSITIONS,
    GateAction,
    GateInput,
    GateManager,
    GatePhase,
    GateResult,
    GateState,
    InputGate,
    StateChangeEntry,
)
from .jira_integration import (
    EpicCreationResult,
    JiraApiError,
    JiraConfigError,
    JiraEpicCreator,
    JiraIntegrationError,
    LinkedArtifact,
    StoryData,
    create_jira_epic,
)
from .master_sheet_completion import (
    CompletionResult,
    MasterSheetCompleter,
    add_feature_links,
    mark_feature_complete,
    update_feature_status,
)
from .master_sheet_reader import (
    ConfigurationError,
    CredentialsError,
    MasterSheetReader,
    MasterSheetReaderError,
    NetworkError,
    TopicEntry,
    get_master_sheet_topics,
)
from .orthogonal_integration import (
    SCORE_THRESHOLDS,
    ChallengeIssue,
    ChallengeResult,
    OrthogonalIntegration,
    ReadinessLevel,
    determine_readiness,
)
from .output_finalizer import (
    FinalizationResult,
    OutputFinalizer,
    add_prd_to_context,
    finalize_feature_outputs,
    update_all_artifact_links,
    verify_bidirectional_links,
)
from .product_identifier import (
    IdentificationResult,
    IdentificationSource,
    ProductIdentifier,
    ProductInfo,
)
from .spec_export import FeatureContent, SpecExporter, SpecExportResult

# Track managers - placeholders for future implementation
# from .tracks import (
#     ContextDocTrack,
#     DesignTrack,
#     BusinessCaseTrack,
#     EngineeringTrack,
# )

# Validators - placeholders for future implementation
# from .validators import (
#     QualityGate,
#     FeatureValidator,
#     ValidationResult,
#     GateCriteria,
# )

# Exports
__all__ = [
    # Core
    "FeatureEngine",
    "FeatureState",
    "FeaturePhase",
    "TrackStatus",
    # Input Gates
    "InputGate",
    "GateAction",
    "GateState",
    "GatePhase",
    "GateInput",
    "GateResult",
    "GateManager",
    "StateChangeEntry",
    "STATE_TRANSITIONS",
    # Artifacts
    "ArtifactManager",
    "ArtifactType",
    "ArtifactValidation",
    # Aliases
    "AliasManager",
    "MatchResult",
    # Master Sheet
    "MasterSheetReader",
    "MasterSheetReaderError",
    "TopicEntry",
    "get_master_sheet_topics",
    # Brain Entity Creator
    "BrainEntityCreator",
    "BrainEntityResult",
    "generate_entity_name",
    "generate_entity_slug",
    # Product Identifier
    "ProductIdentifier",
    "ProductInfo",
    "IdentificationResult",
    "IdentificationSource",
    # Context Doc Generator
    "ContextDocGenerator",
    "ContextDocResult",
    "InsightData",
    # Orthogonal Integration
    "OrthogonalIntegration",
    "ChallengeResult",
    "ChallengeIssue",
    "ReadinessLevel",
    "determine_readiness",
    "SCORE_THRESHOLDS",
    # Context Iteration Pipeline
    "ContextIterationPipeline",
    "PipelineStatus",
    "PipelineState",
    "PipelineResult",
    "VersionInfo",
    "VersionStatus",
    "THRESHOLD_V1_TO_V2",
    "THRESHOLD_V2_TO_V3",
    "THRESHOLD_V3_COMPLETE",
    # Gate Prompt Interface
    "GatePromptInterface",
    "ParsedResponse",
    "ResponseType",
    "ActionDetails",
    "OptionalInput",
    "ACTION_DETAILS",
    "OPTIONAL_INPUTS",
    "format_gate_prompt",
    "parse_gate_response",
    # Bidirectional Sync
    "BidirectionalSync",
    "SyncDirection",
    "SyncResult",
    "SyncField",
    "sync_feature_state_to_context",
    "sync_context_to_master_sheet",
    "sync_master_sheet_to_context",
    # Blocker Detection
    "BlockerDetector",
    "BlockerType",
    "BlockerSeverity",
    "BlockerTrack",
    "Blocker",
    "BlockerReport",
    "detect_blockers",
    "get_blocker_report",
    "has_blockers",
    "format_blocker_list",
    # Spec Export
    "SpecExporter",
    "SpecExportResult",
    "FeatureContent",
    # Jira Integration
    "JiraEpicCreator",
    "JiraIntegrationError",
    "JiraConfigError",
    "JiraApiError",
    "EpicCreationResult",
    "LinkedArtifact",
    "StoryData",
    "create_jira_epic",
    # Output Finalizer
    "OutputFinalizer",
    "FinalizationResult",
    "finalize_feature_outputs",
    "add_prd_to_context",
    "update_all_artifact_links",
    "verify_bidirectional_links",
    # Master Sheet Completion
    "MasterSheetCompleter",
    "CompletionResult",
    "mark_feature_complete",
    "update_feature_status",
    "add_feature_links",
    # Tracks
    "ContextDocTrack",
    "DesignTrack",
    "BusinessCaseTrack",
    "EngineeringTrack",
    # Validators
    "QualityGate",
    "FeatureValidator",
    "ValidationResult",
    "GateCriteria",
]

# Version info
VERSION_INFO = {
    "version": __version__,
    "status": "development",
    "prd_version": "2.1",
}
