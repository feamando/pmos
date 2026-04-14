"""
PM-OS CCE Feature Tools (v5.0)

Feature lifecycle management for the Context Creation Engine.
Provides the main engine, state management, quality gates, input gates,
validation, blocker detection, sync, product identification, alias management,
brain entity creation, context iteration, and Cowork project generation.

Usage:
    from pm_os_cce.tools.feature.feature_engine import FeatureEngine
    from pm_os_cce.tools.feature.feature_state import FeatureState, FeaturePhase
"""

try:
    from pm_os_cce.tools.feature.feature_state import (
        AliasInfo,
        Decision,
        FeaturePhase,
        FeatureState,
        GateState,
        PhaseEntry,
        TrackState,
        TrackStatus,
        generate_brain_entity_name,
        generate_slug,
    )
except ImportError:
    from feature.feature_state import (
        AliasInfo,
        Decision,
        FeaturePhase,
        FeatureState,
        GateState,
        PhaseEntry,
        TrackState,
        TrackStatus,
        generate_brain_entity_name,
        generate_slug,
    )

try:
    from pm_os_cce.tools.feature.feature_engine import (
        FeatureEngine,
        FeatureStatus,
        InitializationResult,
    )
except ImportError:
    from feature.feature_engine import (
        FeatureEngine,
        FeatureStatus,
        InitializationResult,
    )

try:
    from pm_os_cce.tools.feature.quality_gates import QualityGates
except ImportError:
    from feature.quality_gates import QualityGates

try:
    from pm_os_cce.tools.feature.input_gate import (
        GateAction,
        GateResult,
        GateState as InputGateState,
        InputGate,
    )
except ImportError:
    from feature.input_gate import (
        GateAction,
        GateResult,
        GateState as InputGateState,
        InputGate,
    )

try:
    from pm_os_cce.tools.feature.alias_manager import AliasManager, MatchResult
except ImportError:
    from feature.alias_manager import AliasManager, MatchResult

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

try:
    from pm_os_cce.tools.feature.bidirectional_sync import BidirectionalSync
except ImportError:
    from feature.bidirectional_sync import BidirectionalSync

try:
    from pm_os_cce.tools.feature.brain_entity_creator import (
        BrainEntityCreator,
        BrainEntityResult,
    )
except ImportError:
    from feature.brain_entity_creator import BrainEntityCreator, BrainEntityResult

try:
    from pm_os_cce.tools.feature.blocker_detection import BlockerDetector
except ImportError:
    from feature.blocker_detection import BlockerDetector

try:
    from pm_os_cce.tools.feature.validation_hooks import ValidationHookRunner
except ImportError:
    from feature.validation_hooks import ValidationHookRunner

try:
    from pm_os_cce.tools.feature.gate_prompt_interface import GatePromptInterface
except ImportError:
    from feature.gate_prompt_interface import GatePromptInterface

try:
    from pm_os_cce.tools.feature.context_iteration_pipeline import (
        ContextIterationPipeline,
    )
except ImportError:
    from feature.context_iteration_pipeline import ContextIterationPipeline

try:
    from pm_os_cce.tools.feature.cowork_project_generator import (
        CoworkProjectGenerator,
    )
except ImportError:
    from feature.cowork_project_generator import CoworkProjectGenerator

__all__ = [
    # Feature state
    "AliasInfo",
    "Decision",
    "FeaturePhase",
    "FeatureState",
    "GateState",
    "PhaseEntry",
    "TrackState",
    "TrackStatus",
    "generate_brain_entity_name",
    "generate_slug",
    # Feature engine
    "FeatureEngine",
    "FeatureStatus",
    "InitializationResult",
    # Quality gates
    "QualityGates",
    # Input gate
    "GateAction",
    "GateResult",
    "InputGateState",
    "InputGate",
    # Alias manager
    "AliasManager",
    "MatchResult",
    # Product identifier
    "IdentificationResult",
    "IdentificationSource",
    "ProductIdentifier",
    "ProductInfo",
    # Bidirectional sync
    "BidirectionalSync",
    # Brain entity creator
    "BrainEntityCreator",
    "BrainEntityResult",
    # Blocker detection
    "BlockerDetector",
    # Validation hooks
    "ValidationHookRunner",
    # Gate prompt interface
    "GatePromptInterface",
    # Context iteration pipeline
    "ContextIterationPipeline",
    # Cowork project generator
    "CoworkProjectGenerator",
]
