"""
PM-OS CCE Blocker Detection (v5.0)

Identifies and reports blockers that prevent feature progress across
5 categories: missing artifacts, pending approvals, incomplete prerequisites,
blocking dependencies, and unmitigated risks.

Usage:
    from pm_os_cce.tools.feature.blocker_detection import BlockerDetector, Blocker, BlockerReport
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class BlockerType(Enum):
    """Types of blockers that can prevent feature progress."""

    MISSING_ARTIFACT = "missing_artifact"
    PENDING_APPROVAL = "pending_approval"
    INCOMPLETE_PREREQ = "incomplete_prereq"
    BLOCKING_DEPENDENCY = "blocking_dependency"
    UNMITIGATED_RISK = "unmitigated_risk"


class BlockerSeverity(Enum):
    """Severity levels for blockers."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BlockerTrack(Enum):
    """Tracks that blockers can be associated with."""

    CONTEXT = "context"
    DESIGN = "design"
    BUSINESS_CASE = "business_case"
    ENGINEERING = "engineering"
    GENERAL = "general"


@dataclass
class Blocker:
    """Represents a blocker preventing feature progress."""

    type: BlockerType
    description: str
    severity: BlockerSeverity
    track: BlockerTrack = BlockerTrack.GENERAL
    resolution_hint: Optional[str] = None
    details: Optional[str] = None
    detected_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
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
        return self.severity == BlockerSeverity.CRITICAL

    @property
    def is_blocking(self) -> bool:
        return self.severity in (
            BlockerSeverity.CRITICAL,
            BlockerSeverity.HIGH,
            BlockerSeverity.MEDIUM,
        )


@dataclass
class BlockerReport:
    """Aggregated blocker report for a feature."""

    feature_slug: str
    blockers: List[Blocker] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def has_critical(self) -> bool:
        return any(b.is_critical for b in self.blockers)

    @property
    def has_blocking(self) -> bool:
        return any(b.is_blocking for b in self.blockers)

    @property
    def total_count(self) -> int:
        return len(self.blockers)

    @property
    def critical_count(self) -> int:
        return sum(1 for b in self.blockers if b.severity == BlockerSeverity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for b in self.blockers if b.severity == BlockerSeverity.HIGH)

    @property
    def medium_count(self) -> int:
        return sum(1 for b in self.blockers if b.severity == BlockerSeverity.MEDIUM)

    @property
    def low_count(self) -> int:
        return sum(1 for b in self.blockers if b.severity == BlockerSeverity.LOW)

    def get_by_type(self, blocker_type: BlockerType) -> List[Blocker]:
        return [b for b in self.blockers if b.type == blocker_type]

    def get_by_severity(self, severity: BlockerSeverity) -> List[Blocker]:
        return [b for b in self.blockers if b.severity == severity]

    def get_by_track(self, track: str) -> List[Blocker]:
        try:
            track_enum = BlockerTrack(track)
        except ValueError:
            return []
        return [b for b in self.blockers if b.track == track_enum]

    def to_dict(self) -> Dict[str, Any]:
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
    """Detects and reports blockers for a feature.

    Scans feature state, track states, and quality gates to identify
    all blockers preventing progress.
    """

    def __init__(self, feature_path: Path, gates: Optional[Any] = None):
        self.feature_path = Path(feature_path)

        # Lazy import to avoid circular dependencies
        try:
            from pm_os_cce.tools.feature.quality_gates import QualityGates, get_default_gates
        except ImportError:
            from feature.quality_gates import QualityGates, get_default_gates

        self.gates = gates or get_default_gates()

        self._state = None
        self._bc_track = None
        self._eng_track = None

    def _load_state(self):
        if self._state is None:
            try:
                from pm_os_cce.tools.feature.feature_state import FeatureState
            except ImportError:
                from feature.feature_state import FeatureState

            self._state = FeatureState.load(self.feature_path)

    def _load_bc_track(self):
        if self._bc_track is None:
            try:
                from pm_os_cce.tools.tracks.business_case import BusinessCaseTrack
            except ImportError:
                try:
                    from tracks.business_case import BusinessCaseTrack
                except ImportError:
                    logger.debug("BusinessCaseTrack not available")
                    return

            self._bc_track = BusinessCaseTrack(self.feature_path)

    def _load_eng_track(self):
        if self._eng_track is None:
            try:
                from pm_os_cce.tools.tracks.engineering import EngineeringTrack
            except ImportError:
                try:
                    from tracks.engineering import EngineeringTrack
                except ImportError:
                    logger.debug("EngineeringTrack not available")
                    return

            self._eng_track = EngineeringTrack(self.feature_path)

    @property
    def state(self):
        self._load_state()
        return self._state

    @property
    def bc_track(self):
        self._load_bc_track()
        return self._bc_track

    @property
    def eng_track(self):
        self._load_eng_track()
        return self._eng_track

    def detect_all(self) -> List[Blocker]:
        blockers = []
        blockers.extend(self.detect_missing_artifacts())
        blockers.extend(self.detect_pending_approvals())
        blockers.extend(self.detect_incomplete_prerequisites())
        blockers.extend(self.detect_blocking_dependencies())
        blockers.extend(self.detect_unmitigated_risks())
        return blockers

    def detect_missing_artifacts(self) -> List[Blocker]:
        if self.state is None:
            return []

        blockers = []
        artifacts = self.state.artifacts or {}

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
                        resolution_hint=f"Use /brain attach {artifact_type} <url> to attach",
                        details=artifact_req.description
                        or f"{artifact_type.title()} URL",
                        metadata={"artifact_type": artifact_type, "required": True},
                    )
                )
            elif not has_artifact and not artifact_req.required:
                blockers.append(
                    Blocker(
                        type=BlockerType.MISSING_ARTIFACT,
                        description=f"Recommended {artifact_type} not attached",
                        severity=BlockerSeverity.LOW,
                        track=BlockerTrack.DESIGN,
                        resolution_hint=f"Consider attaching {artifact_type} via /brain attach",
                        details=artifact_req.description
                        or f"{artifact_type.title()} URL (optional)",
                        metadata={"artifact_type": artifact_type, "required": False},
                    )
                )

        return blockers

    def detect_pending_approvals(self) -> List[Blocker]:
        blockers = []

        if self.bc_track is None:
            return blockers

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
        if self.state is None:
            return []

        blockers = []

        context_track = self.state.tracks.get("context")
        if context_track:
            try:
                from pm_os_cce.tools.feature.feature_state import TrackStatus
            except ImportError:
                from feature.feature_state import TrackStatus

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

        if self.eng_track is not None and not self.eng_track.has_estimate:
            if self.eng_track.status.value != "not_started":
                blockers.append(
                    Blocker(
                        type=BlockerType.INCOMPLETE_PREREQ,
                        description="Engineering estimate not provided",
                        severity=BlockerSeverity.MEDIUM,
                        track=BlockerTrack.ENGINEERING,
                        resolution_hint="Use /feature engineering-spec estimate <S|M|L|XL> to provide estimate",
                        details="Estimate required for engineering track completion",
                        metadata={"has_adrs": len(self.eng_track.adrs) > 0},
                    )
                )

        if self.bc_track is not None and self.bc_track.status.value == "in_progress":
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
                        details="Track status: blocked",
                        metadata={"track": track_name},
                    )
                )

        return blockers

    def detect_blocking_dependencies(self) -> List[Blocker]:
        blockers = []

        if self.eng_track is None:
            return blockers

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
        blockers = []

        if not self.gates.engineering_high_risks_require_mitigation:
            return blockers

        if self.eng_track is None:
            return blockers

        for risk in self.eng_track.pending_risks:
            if risk.impact == "high" and risk.likelihood == "high":
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
        return [b for b in self.detect_all() if b.type == blocker_type]

    def get_blockers_by_severity(self, severity: BlockerSeverity) -> List[Blocker]:
        return [b for b in self.detect_all() if b.severity == severity]

    def get_blockers_by_track(self, track: str) -> List[Blocker]:
        try:
            track_enum = BlockerTrack(track)
        except ValueError:
            return []
        return [b for b in self.detect_all() if b.track == track_enum]

    def generate_report(self) -> BlockerReport:
        slug = self.state.slug if self.state else self.feature_path.name
        blockers = self.detect_all()

        return BlockerReport(
            feature_slug=slug,
            blockers=blockers,
            generated_at=datetime.now(),
        )

    def has_blocking_issues(self) -> bool:
        for blocker in self.detect_all():
            if blocker.is_blocking:
                return True
        return False

    def has_critical_blockers(self) -> bool:
        for blocker in self.detect_all():
            if blocker.is_critical:
                return True
        return False

    def can_proceed_to_phase(self, target_phase: str) -> tuple:
        blockers = self.detect_all()
        blocking = [b for b in blockers if b.is_blocking]

        if target_phase == "decision_gate":
            critical_high = [
                b
                for b in blocking
                if b.severity in (BlockerSeverity.CRITICAL, BlockerSeverity.HIGH)
            ]
            return len(critical_high) == 0, critical_high

        elif target_phase == "output_generation":
            return len(blocking) == 0, blocking

        critical = [b for b in blocking if b.severity == BlockerSeverity.CRITICAL]
        return len(critical) == 0, critical


# ========== Helper Functions ==========


def detect_blockers(
    feature_path: Path, gates: Optional[Any] = None
) -> List[Blocker]:
    """Convenience function to detect all blockers for a feature."""
    detector = BlockerDetector(feature_path, gates)
    return detector.detect_all()


def get_blocker_report(
    feature_path: Path, gates: Optional[Any] = None
) -> BlockerReport:
    """Convenience function to generate a blocker report."""
    detector = BlockerDetector(feature_path, gates)
    return detector.generate_report()


def has_blockers(
    feature_path: Path, severity: Optional[BlockerSeverity] = None
) -> bool:
    """Convenience function to check if a feature has blockers."""
    detector = BlockerDetector(feature_path)

    if severity:
        return len(detector.get_blockers_by_severity(severity)) > 0

    return detector.has_blocking_issues()


def format_blocker_list(blockers: List[Blocker], include_hints: bool = True) -> str:
    """Format a list of blockers for display."""
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
