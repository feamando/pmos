"""
Context Engine Tracks

Parallel workflow tracks that run during feature development:
- ContextDocTrack: Context document generation and iteration
- DesignTrack: Design spec, wireframes, Figma
- BusinessCaseTrack: Business case development and approval
- EngineeringTrack: Engineering spec and ADRs

Each track can be worked on in parallel once the context document
reaches v2 stage.

Usage:
    from tools.context_engine.tracks import (
        ContextDocTrack,
        DesignTrack,
        BusinessCaseTrack,
        EngineeringTrack,
    )

    # Initialize tracks for a feature
    context_track = ContextDocTrack(feature_path)
    design_track = DesignTrack(feature_path)
"""

# Track managers will be imported here as they are implemented
# from .context_doc import ContextDocTrack
# from .design import DesignTrack
from .business_case import (
    BCStatus,
    BCTrackResult,
    BusinessCaseTrack,
    StakeholderApproval,
)
from .engineering import (
    ADR,
    ADRStatus,
    Dependency,
    EngineeringEstimate,
    EngineeringStatus,
    EngineeringTrack,
    EngineeringTrackResult,
    EstimateSize,
    TechnicalDecision,
    TechnicalRisk,
)

__all__ = [
    "ContextDocTrack",
    "DesignTrack",
    "BusinessCaseTrack",
    "BCStatus",
    "BCTrackResult",
    "StakeholderApproval",
    "EngineeringTrack",
    "EngineeringStatus",
    "EngineeringTrackResult",
    "ADR",
    "ADRStatus",
    "TechnicalDecision",
    "TechnicalRisk",
    "Dependency",
    "EngineeringEstimate",
    "EstimateSize",
]
