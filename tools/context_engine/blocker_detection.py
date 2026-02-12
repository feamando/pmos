"""
Blocker Detection and Reporting

Identifies and reports blockers that prevent feature progress including:
- Missing required artifacts (Figma, wireframes based on config)
- Pending approvals (BC stakeholders who haven't approved)
- Incomplete prerequisites (context doc below threshold, missing estimates)
- Blocking dependencies (external dependencies not resolved)
- High-impact unmitigated risks

Integrates with quality_gates.py for threshold-based blocking detection.

Usage:
    from tools.context_engine.blocker_detection import (
        BlockerDetector,
        BlockerType,
        BlockerSeverity,
        Blocker,
    )

    # Detect all blockers for a feature
    detector = BlockerDetector(feature_path)
    blockers = detector.detect_all()

    # Get blockers by type
    missing_artifacts = detector.get_blockers_by_type(BlockerType.MISSING_ARTIFACT)

    # Get blockers by severity
    critical = detector.get_blockers_by_severity(BlockerSeverity.CRITICAL)

    # Get blockers for specific track
    bc_blockers = detector.get_blockers_by_track("business_case")

    # Generate blocker report
    report = detector.generate_report()

PRD References:
    - Section A.1: Quality gates and blocking criteria
    - Section F.2: Phase gate requirements
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class BlockerType(Enum):
    """Types of blockers that can prevent feature progress."""

    MISSING_ARTIFACT = "missing_artifact"
    PENDING_APPROVAL = "pending_approval"
    INCOMPLETE_PREREQ = "incomplete_prereq"
    BLOCKING_DEPENDENCY = "blocking_dependency"
    UNMITIGATED_RISK = "unmitigated_risk"


class BlockerSeverity(Enum):
    """Severity levels for blockers."""

    CRITICAL = "critical"  # Blocks all progress
    HIGH = "high"  # Blocks phase transition
    MEDIUM = "medium"  # Blocks track completion
    LOW = "low"  # Advisory, not blocking


class BlockerTrack(Enum):
    """Tracks that blockers can be associated with."""

    CONTEXT = "context"
    DESIGN = "design"
    BUSINESS_CASE = "business_case"
    ENGINEERING = "engineering"
    GENERAL = "general"  # Not tied to specific track


@dataclass
class Blocker:
    """
    Represents a blocker preventing feature progress.

    Attributes:
        type: The type of blocker (missing artifact, pending approval, etc.)
        description: Human-readable description of the blocker
        severity: How critical this blocker is
        track: Which track this blocker affects
        resolution_hint: Suggested action to resolve the blocker
        details: Additional context (e.g., specific artifact name, approver)
        detected_at: When the blocker was detected
        metadata: Additional structured data
    """

    type: BlockerType
    description: str
    severity: BlockerSeverity
    track: BlockerTrack = BlockerTrack.GENERAL
    resolution_hint: Optional[str] = None
    details: Optional[str] = None
    detected_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "type": self.type.value,
            "description": self.description,
            "severity": self.severity.value,
            "track": self.track.value,
            "detected_at": self.detected_at.isoformat(),
        }
        if self.resolution_hint:
            result["resolution_hint"] = self.resolution_hint
        if self.details:
            result["details"] = self.details
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Blocker":
        """Create from dictionary."""
        detected_at = data.get("detected_at")
        if isinstance(detected_at, str):
            detected_at = datetime.fromisoformat(detected_at)
        elif not isinstance(detected_at, datetime):
            detected_at = datetime.now()

        return cls(
            type=BlockerType(data["type"]),
            description=data["description"],
            severity=BlockerSeverity(data["severity"]),
            track=BlockerTrack(data.get("track", "general")),
            resolution_hint=data.get("resolution_hint"),
            details=data.get("details"),
            detected_at=detected_at,
            metadata=data.get("metadata", {}),
        )

    @property
    def is_critical(self) -> bool:
        """Check if this is a critical blocker."""
        return self.severity == BlockerSeverity.CRITICAL

    @property
    def is_blocking(self) -> bool:
        """Check if this blocker actually blocks progress (not just advisory)."""
        return self.severity in (
            BlockerSeverity.CRITICAL,
            BlockerSeverity.HIGH,
            BlockerSeverity.MEDIUM,
        )


@dataclass
class BlockerReport:
    """
    Aggregated blocker report for a feature.

    Attributes:
        feature_slug: The feature this report is for
        blockers: List of all blockers
        generated_at: When the report was generated
        has_critical: Whether any critical blockers exist
        has_blocking: Whether any blocking issues exist
    """

    feature_slug: str
    blockers: List[Blocker] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def has_critical(self) -> bool:
        """Check if any critical blockers exist."""
        return any(b.is_critical for b in self.blockers)

    @property
    def has_blocking(self) -> bool:
        """Check if any blocking issues exist."""
        return any(b.is_blocking for b in self.blockers)

    @property
    def total_count(self) -> int:
        """Total number of blockers."""
        return len(self.blockers)

    @property
    def critical_count(self) -> int:
        """Count of critical blockers."""
        return sum(1 for b in self.blockers if b.severity == BlockerSeverity.CRITICAL)

    @property
    def high_count(self) -> int:
        """Count of high severity blockers."""
        return sum(1 for b in self.blockers if b.severity == BlockerSeverity.HIGH)

    @property
    def medium_count(self) -> int:
        """Count of medium severity blockers."""
        return sum(1 for b in self.blockers if b.severity == BlockerSeverity.MEDIUM)

    @property
    def low_count(self) -> int:
        """Count of low severity (advisory) blockers."""
        return sum(1 for b in self.blockers if b.severity == BlockerSeverity.LOW)

    def get_by_type(self, blocker_type: BlockerType) -> List[Blocker]:
        """Get blockers filtered by type."""
        return [b for b in self.blockers if b.type == blocker_type]

    def get_by_severity(self, severity: BlockerSeverity) -> List[Blocker]:
        """Get blockers filtered by severity."""
        return [b for b in self.blockers if b.severity == severity]

    def get_by_track(self, track: str) -> List[Blocker]:
        """Get blockers filtered by track name."""
        try:
            track_enum = BlockerTrack(track)
        except ValueError:
            return []
        return [b for b in self.blockers if b.track == track_enum]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "feature_slug": self.feature_slug,
            "generated_at": self.generated_at.isoformat(),
            "total_count": self.total_count,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "has_critical": self.has_critical,
            "has_blocking": self.has_blocking,
            "blockers": [b.to_dict() for b in self.blockers],
        }

    def to_summary(self) -> str:
        """Generate a human-readable summary."""
        if not self.blockers:
            return "No blockers detected"

        lines = [f"Blockers for {self.feature_slug}: {self.total_count} total"]
        if self.critical_count > 0:
            lines.append(f"  [CRITICAL] {self.critical_count}")
        if self.high_count > 0:
            lines.append(f"  [HIGH] {self.high_count}")
        if self.medium_count > 0:
            lines.append(f"  [MEDIUM] {self.medium_count}")
        if self.low_count > 0:
            lines.append(f"  [LOW] {self.low_count}")
        return "\n".join(lines)


class BlockerDetector:
    """
    Detects and reports blockers for a feature.

    Scans feature state, track states, and quality gates to identify
    all blockers preventing progress.

    Usage:
        detector = BlockerDetector(feature_path)
        blockers = detector.detect_all()

        # Or with custom gates configuration
        detector = BlockerDetector(feature_path, gates=custom_gates)
        blockers = detector.detect_all()
    """

    def __init__(self, feature_path: Path, gates: Optional["QualityGates"] = None):
        """
        Initialize blocker detector.

        Args:
            feature_path: Path to the feature folder
            gates: Optional custom QualityGates configuration
        """
        self.feature_path = Path(feature_path)

        # Lazy import to avoid circular dependencies
        from .quality_gates import QualityGates, get_default_gates

        self.gates = gates or get_default_gates()

        # Cached state and tracks (loaded on demand)
        self._state = None
        self._bc_track = None
        self._eng_track = None

    def _load_state(self):
        """Load feature state if not already loaded."""
        if self._state is None:
            from .feature_state import FeatureState

            self._state = FeatureState.load(self.feature_path)

    def _load_bc_track(self):
        """Load business case track if not already loaded."""
        if self._bc_track is None:
            from .tracks.business_case import BusinessCaseTrack

            self._bc_track = BusinessCaseTrack(self.feature_path)

    def _load_eng_track(self):
        """Load engineering track if not already loaded."""
        if self._eng_track is None:
            from .tracks.engineering import EngineeringTrack

            self._eng_track = EngineeringTrack(self.feature_path)

    @property
    def state(self):
        """Get feature state (loaded on first access)."""
        self._load_state()
        return self._state

    @property
    def bc_track(self):
        """Get business case track (loaded on first access)."""
        self._load_bc_track()
        return self._bc_track

    @property
    def eng_track(self):
        """Get engineering track (loaded on first access)."""
        self._load_eng_track()
        return self._eng_track

    def detect_all(self) -> List[Blocker]:
        """
        Detect all blockers for the feature.

        Returns:
            List of all detected blockers
        """
        blockers = []

        # Detect each type of blocker
        blockers.extend(self.detect_missing_artifacts())
        blockers.extend(self.detect_pending_approvals())
        blockers.extend(self.detect_incomplete_prerequisites())
        blockers.extend(self.detect_blocking_dependencies())
        blockers.extend(self.detect_unmitigated_risks())

        return blockers

    def detect_missing_artifacts(self) -> List[Blocker]:
        """
        Detect missing required artifacts.

        Checks:
        - Figma URL (required by default)
        - Wireframes URL (optional by default, configurable)
        - Other configured design artifacts

        Returns:
            List of MISSING_ARTIFACT blockers
        """
        if self.state is None:
            return []

        blockers = []
        artifacts = self.state.artifacts or {}

        # Check design artifacts from gates configuration
        for artifact_req in self.gates.design_artifacts:
            artifact_type = artifact_req.artifact_type
            url = artifacts.get(artifact_type)
            has_artifact = url is not None and url.strip() != ""

            if not has_artifact and artifact_req.required:
                blockers.append(
                    Blocker(
                        type=BlockerType.MISSING_ARTIFACT,
                        description=f"Required {artifact_type} not attached",
                        severity=BlockerSeverity.HIGH,
                        track=BlockerTrack.DESIGN,
                        resolution_hint=f"Use /attach-artifact {artifact_type} <url> to attach",
                        details=artifact_req.description
                        or f"{artifact_type.title()} URL",
                        metadata={"artifact_type": artifact_type, "required": True},
                    )
                )
            elif not has_artifact and not artifact_req.required:
                # Advisory only for optional artifacts
                blockers.append(
                    Blocker(
                        type=BlockerType.MISSING_ARTIFACT,
                        description=f"Recommended {artifact_type} not attached",
                        severity=BlockerSeverity.LOW,
                        track=BlockerTrack.DESIGN,
                        resolution_hint=f"Consider attaching {artifact_type} via /attach-artifact",
                        details=artifact_req.description
                        or f"{artifact_type.title()} URL (optional)",
                        metadata={"artifact_type": artifact_type, "required": False},
                    )
                )

        return blockers

    def detect_pending_approvals(self) -> List[Blocker]:
        """
        Detect pending approval blockers.

        Checks:
        - Business case stakeholder approvals
        - Required approvers who haven't approved yet
        - Rejected business cases

        Returns:
            List of PENDING_APPROVAL blockers
        """
        blockers = []

        # Check BC track approvals
        if self.bc_track.status.value == "pending_approval":
            pending = self.bc_track.pending_approvers
            if pending:
                blockers.append(
                    Blocker(
                        type=BlockerType.PENDING_APPROVAL,
                        description=f"Business case awaiting approval from: {', '.join(pending)}",
                        severity=BlockerSeverity.HIGH,
                        track=BlockerTrack.BUSINESS_CASE,
                        resolution_hint="Follow up with stakeholders to obtain approval",
                        details=f"Pending: {', '.join(pending)}",
                        metadata={
                            "pending_approvers": pending,
                            "approvals_received": len(self.bc_track.approvals),
                        },
                    )
                )

        # Check for BC rejection
        if self.bc_track.is_rejected:
            blockers.append(
                Blocker(
                    type=BlockerType.PENDING_APPROVAL,
                    description="Business case was rejected",
                    severity=BlockerSeverity.CRITICAL,
                    track=BlockerTrack.BUSINESS_CASE,
                    resolution_hint="Review rejection feedback and revise business case",
                    details="Must address rejection feedback before proceeding",
                    metadata={"status": "rejected"},
                )
            )

        return blockers

    def detect_incomplete_prerequisites(self) -> List[Blocker]:
        """
        Detect incomplete prerequisite blockers.

        Checks:
        - Context document score below threshold
        - Missing engineering estimate
        - Track status issues
        - Context doc version requirements

        Returns:
            List of INCOMPLETE_PREREQ blockers
        """
        if self.state is None:
            return []

        blockers = []

        # Check context track
        context_track = self.state.tracks.get("context")
        if context_track:
            from .feature_state import TrackStatus

            # Context doc not complete when needed for decision gate
            if self.state.current_phase.value in ("parallel_tracks", "decision_gate"):
                if context_track.status != TrackStatus.COMPLETE:
                    blockers.append(
                        Blocker(
                            type=BlockerType.INCOMPLETE_PREREQ,
                            description="Context document not complete",
                            severity=BlockerSeverity.HIGH,
                            track=BlockerTrack.CONTEXT,
                            resolution_hint="Complete context document iterations to proceed",
                            details=f"Status: {context_track.status.value}",
                            metadata={"current_version": context_track.current_version},
                        )
                    )

            # Check if context doc version is below required threshold
            version = context_track.current_version or 0
            if version > 0:
                required_threshold = self.gates.get_threshold_for_version(version)
                # Note: Actual score checking would require reading the challenge result
                # This is a structural check - actual score validation is in quality_gates

        # Check engineering track - missing estimate
        if not self.eng_track.has_estimate:
            # Only a blocker if engineering track has started
            if self.eng_track.status.value != "not_started":
                blockers.append(
                    Blocker(
                        type=BlockerType.INCOMPLETE_PREREQ,
                        description="Engineering estimate not provided",
                        severity=BlockerSeverity.MEDIUM,
                        track=BlockerTrack.ENGINEERING,
                        resolution_hint="Use /engineering-spec estimate <S|M|L|XL> to provide estimate",
                        details="Estimate required for engineering track completion",
                        metadata={"has_adrs": len(self.eng_track.adrs) > 0},
                    )
                )

        # Check business case assumptions
        if self.bc_track.status.value == "in_progress":
            if not self.bc_track.assumptions.is_complete:
                blockers.append(
                    Blocker(
                        type=BlockerType.INCOMPLETE_PREREQ,
                        description="Business case assumptions incomplete",
                        severity=BlockerSeverity.MEDIUM,
                        track=BlockerTrack.BUSINESS_CASE,
                        resolution_hint="Provide baseline_metrics and impact_assumptions",
                        details="Baseline metrics and impact assumptions required",
                        metadata={
                            "has_baseline": bool(
                                self.bc_track.assumptions.baseline_metrics
                            ),
                            "has_impact": bool(
                                self.bc_track.assumptions.impact_assumptions
                            ),
                        },
                    )
                )

        # Check for blocked tracks
        for track_name, track in self.state.tracks.items():
            if track.status.value == "blocked":
                blockers.append(
                    Blocker(
                        type=BlockerType.INCOMPLETE_PREREQ,
                        description=f"{track_name.replace('_', ' ').title()} track is blocked",
                        severity=BlockerSeverity.HIGH,
                        track=(
                            BlockerTrack(track_name)
                            if track_name in [t.value for t in BlockerTrack]
                            else BlockerTrack.GENERAL
                        ),
                        resolution_hint="Investigate and resolve blocking issue",
                        details=f"Track status: blocked",
                        metadata={"track": track_name},
                    )
                )

        return blockers

    def detect_blocking_dependencies(self) -> List[Blocker]:
        """
        Detect blocking external dependencies.

        Checks:
        - Dependencies in 'blocked' or 'pending' status
        - External dependencies not resolved

        Returns:
            List of BLOCKING_DEPENDENCY blockers
        """
        blockers = []

        # Check engineering track dependencies
        for dep in self.eng_track.blocking_dependencies:
            blockers.append(
                Blocker(
                    type=BlockerType.BLOCKING_DEPENDENCY,
                    description=f"Dependency blocked: {dep.name}",
                    severity=BlockerSeverity.HIGH,
                    track=BlockerTrack.ENGINEERING,
                    resolution_hint=f"Resolve or update status for dependency: {dep.name}",
                    details=dep.description
                    or f"Type: {dep.type}, Status: {dep.status}",
                    metadata={
                        "dependency_name": dep.name,
                        "dependency_type": dep.type,
                        "status": dep.status,
                        "owner": dep.owner,
                        "eta": dep.eta,
                    },
                )
            )

        return blockers

    def detect_unmitigated_risks(self) -> List[Blocker]:
        """
        Detect high-impact unmitigated risks.

        Checks:
        - High-impact risks without mitigation plans
        - High-likelihood/high-impact risks

        Returns:
            List of UNMITIGATED_RISK blockers
        """
        blockers = []

        # Check if high risks must have mitigation
        if not self.gates.engineering_high_risks_require_mitigation:
            return blockers

        for risk in self.eng_track.pending_risks:
            # Check for high impact + high likelihood first (most severe)
            if risk.impact == "high" and risk.likelihood == "high":
                # High-high risks are critical when unmitigated, medium when mitigated
                blockers.append(
                    Blocker(
                        type=BlockerType.UNMITIGATED_RISK,
                        description=f"Critical risk (high impact + high likelihood): {risk.risk[:50]}...",
                        severity=(
                            BlockerSeverity.CRITICAL
                            if not risk.mitigation
                            else BlockerSeverity.MEDIUM
                        ),
                        track=BlockerTrack.ENGINEERING,
                        resolution_hint=(
                            "Add mitigation plan urgently"
                            if not risk.mitigation
                            else "Review and strengthen mitigation plan"
                        ),
                        details=f"Impact: high, Likelihood: high, Mitigation: {'present' if risk.mitigation else 'missing'}",
                        metadata={
                            "risk": risk.risk,
                            "impact": "high",
                            "likelihood": "high",
                            "has_mitigation": bool(risk.mitigation),
                        },
                    )
                )
            elif risk.impact == "high" and not risk.mitigation:
                # High impact without mitigation (but not high-high)
                blockers.append(
                    Blocker(
                        type=BlockerType.UNMITIGATED_RISK,
                        description=f"High-impact risk needs mitigation: {risk.risk[:60]}...",
                        severity=BlockerSeverity.HIGH,
                        track=BlockerTrack.ENGINEERING,
                        resolution_hint="Add mitigation plan for this risk",
                        details=f"Impact: {risk.impact}, Likelihood: {risk.likelihood}",
                        metadata={
                            "risk": risk.risk,
                            "impact": risk.impact,
                            "likelihood": risk.likelihood,
                            "owner": risk.owner,
                            "status": risk.status,
                        },
                    )
                )

        return blockers

    def get_blockers_by_type(self, blocker_type: BlockerType) -> List[Blocker]:
        """
        Get blockers filtered by type.

        Args:
            blocker_type: Type of blocker to filter for

        Returns:
            List of blockers matching the type
        """
        return [b for b in self.detect_all() if b.type == blocker_type]

    def get_blockers_by_severity(self, severity: BlockerSeverity) -> List[Blocker]:
        """
        Get blockers filtered by severity.

        Args:
            severity: Severity level to filter for

        Returns:
            List of blockers matching the severity
        """
        return [b for b in self.detect_all() if b.severity == severity]

    def get_blockers_by_track(self, track: str) -> List[Blocker]:
        """
        Get blockers filtered by track.

        Args:
            track: Track name to filter for (context, design, business_case, engineering, general)

        Returns:
            List of blockers affecting the specified track
        """
        try:
            track_enum = BlockerTrack(track)
        except ValueError:
            return []
        return [b for b in self.detect_all() if b.track == track_enum]

    def generate_report(self) -> BlockerReport:
        """
        Generate a comprehensive blocker report.

        Returns:
            BlockerReport with all blockers and summary statistics
        """
        slug = self.state.slug if self.state else self.feature_path.name
        blockers = self.detect_all()

        return BlockerReport(
            feature_slug=slug,
            blockers=blockers,
            generated_at=datetime.now(),
        )

    def has_blocking_issues(self) -> bool:
        """
        Check if there are any blocking issues.

        Returns:
            True if any blocker with severity CRITICAL, HIGH, or MEDIUM exists
        """
        for blocker in self.detect_all():
            if blocker.is_blocking:
                return True
        return False

    def has_critical_blockers(self) -> bool:
        """
        Check if there are any critical blockers.

        Returns:
            True if any blocker with severity CRITICAL exists
        """
        for blocker in self.detect_all():
            if blocker.is_critical:
                return True
        return False

    def can_proceed_to_phase(self, target_phase: str) -> tuple[bool, List[Blocker]]:
        """
        Check if the feature can proceed to a target phase.

        Args:
            target_phase: The phase to check transition to

        Returns:
            Tuple of (can_proceed, blocking_issues)
        """
        blockers = self.detect_all()

        # Filter to only blocking issues (not advisory)
        blocking = [b for b in blockers if b.is_blocking]

        if target_phase == "decision_gate":
            # Decision gate requires all critical/high issues resolved
            critical_high = [
                b
                for b in blocking
                if b.severity in (BlockerSeverity.CRITICAL, BlockerSeverity.HIGH)
            ]
            return len(critical_high) == 0, critical_high

        elif target_phase == "output_generation":
            # Output generation requires all blockers resolved
            return len(blocking) == 0, blocking

        # Default: allow with no critical blockers
        critical = [b for b in blocking if b.severity == BlockerSeverity.CRITICAL]
        return len(critical) == 0, critical


# ========== Helper Functions ==========


def detect_blockers(
    feature_path: Path, gates: Optional["QualityGates"] = None
) -> List[Blocker]:
    """
    Convenience function to detect all blockers for a feature.

    Args:
        feature_path: Path to the feature folder
        gates: Optional custom QualityGates configuration

    Returns:
        List of all detected blockers
    """
    detector = BlockerDetector(feature_path, gates)
    return detector.detect_all()


def get_blocker_report(
    feature_path: Path, gates: Optional["QualityGates"] = None
) -> BlockerReport:
    """
    Convenience function to generate a blocker report.

    Args:
        feature_path: Path to the feature folder
        gates: Optional custom QualityGates configuration

    Returns:
        BlockerReport with all blockers and statistics
    """
    detector = BlockerDetector(feature_path, gates)
    return detector.generate_report()


def has_blockers(
    feature_path: Path, severity: Optional[BlockerSeverity] = None
) -> bool:
    """
    Convenience function to check if a feature has blockers.

    Args:
        feature_path: Path to the feature folder
        severity: Optional specific severity to check for

    Returns:
        True if blockers exist (at the specified severity or any blocking level)
    """
    detector = BlockerDetector(feature_path)

    if severity:
        return len(detector.get_blockers_by_severity(severity)) > 0

    return detector.has_blocking_issues()


def format_blocker_list(blockers: List[Blocker], include_hints: bool = True) -> str:
    """
    Format a list of blockers for display.

    Args:
        blockers: List of blockers to format
        include_hints: Whether to include resolution hints

    Returns:
        Formatted string for display
    """
    if not blockers:
        return "No blockers detected"

    lines = []
    severity_order = [
        BlockerSeverity.CRITICAL,
        BlockerSeverity.HIGH,
        BlockerSeverity.MEDIUM,
        BlockerSeverity.LOW,
    ]

    for severity in severity_order:
        severity_blockers = [b for b in blockers if b.severity == severity]
        if severity_blockers:
            lines.append(f"\n[{severity.value.upper()}]")
            for b in severity_blockers:
                prefix = (
                    "[!]"
                    if severity in (BlockerSeverity.CRITICAL, BlockerSeverity.HIGH)
                    else "[-]"
                )
                lines.append(f"  {prefix} {b.description}")
                if include_hints and b.resolution_hint:
                    lines.append(f"      Hint: {b.resolution_hint}")

    return "\n".join(lines)
