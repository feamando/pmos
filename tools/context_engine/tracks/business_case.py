"""
Business Case Track

Manages the business case workflow for features including:
- Status tracking (not_started, in_progress, pending_approval, approved, rejected)
- Stakeholder approval management
- Business case artifact storage (ROI analysis, budget estimates, etc.)
- Integration with input gates for approval prompts

Business Case Workflow:
    1. start() - Initialize BC track, gather baseline metrics
    2. draft() - Create initial BC document with assumptions
    3. submit_for_approval() - Send to stakeholders for sign-off
    4. record_approval() - Capture approval decision
    5. complete() / reject() - Terminal states

PRD References:
    - Section A.1: Business Case Assumptions, Business Case Approval (blocking gates)
    - Section C.4: Business case track in feature-state.yaml
    - Section D.2: Business Case Phase inputs (baseline_metrics, impact_assumptions, etc.)

Usage:
    from tools.context_engine.tracks import BusinessCaseTrack

    track = BusinessCaseTrack(feature_path)
    track.start(initiated_by="jane")
    track.update_assumptions(baseline_metrics={...}, impact_assumptions={...})
    result = track.submit_for_approval(approver="Jack Approver")
    track.record_approval(approver="Jack Approver", approved=True, approval_type="verbal")
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class BCStatus(Enum):
    """
    Business case track status values.

    Lifecycle:
        NOT_STARTED -> IN_PROGRESS -> PENDING_APPROVAL -> APPROVED
                                         |
                                         +-> REJECTED
    """

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class StakeholderApproval:
    """
    Records a stakeholder approval decision.

    Attributes:
        approver: Name of approver (from Brain entities if possible)
        approved: Whether they approved or rejected
        date: Date of decision
        approval_type: How approval was given (verbal, written, email, slack)
        reference: Link to evidence (Slack thread, email, etc.)
        notes: Additional context
    """

    approver: str
    approved: bool
    date: datetime
    approval_type: str = "verbal"
    reference: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result = {
            "approver": self.approver,
            "approved": self.approved,
            "date": (
                self.date.isoformat() if isinstance(self.date, datetime) else self.date
            ),
            "approval_type": self.approval_type,
        }
        if self.reference:
            result["reference"] = self.reference
        if self.notes:
            result["notes"] = self.notes
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StakeholderApproval":
        """Create from dictionary."""
        date = data.get("date")
        if isinstance(date, str):
            date = datetime.fromisoformat(date)
        elif not isinstance(date, datetime):
            date = datetime.now()

        return cls(
            approver=data["approver"],
            approved=data.get("approved", True),
            date=date,
            approval_type=data.get("approval_type", "verbal"),
            reference=data.get("reference"),
            notes=data.get("notes"),
        )


@dataclass
class BCAssumptions:
    """
    Business case assumptions and metrics.

    From PRD D.2 - Business Case Phase inputs:
        - baseline_metrics: Current state metrics
        - impact_assumptions: Expected improvement
        - investment_estimate: Rough effort estimate (optional, can defer to engineering)
    """

    baseline_metrics: Dict[str, Any] = field(default_factory=dict)
    impact_assumptions: Dict[str, Any] = field(default_factory=dict)
    investment_estimate: Optional[str] = None
    roi_analysis: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "baseline_metrics": self.baseline_metrics,
            "impact_assumptions": self.impact_assumptions,
        }
        if self.investment_estimate:
            result["investment_estimate"] = self.investment_estimate
        if self.roi_analysis:
            result["roi_analysis"] = self.roi_analysis
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BCAssumptions":
        """Create from dictionary."""
        return cls(
            baseline_metrics=data.get("baseline_metrics", {}),
            impact_assumptions=data.get("impact_assumptions", {}),
            investment_estimate=data.get("investment_estimate"),
            roi_analysis=data.get("roi_analysis"),
        )

    @property
    def is_complete(self) -> bool:
        """Check if required assumptions are provided."""
        return bool(self.baseline_metrics) and bool(self.impact_assumptions)


@dataclass
class BCTrackResult:
    """Result of a business case track operation."""

    success: bool
    status: BCStatus
    message: str
    version: Optional[int] = None
    file_path: Optional[Path] = None
    pending_approvers: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BusinessCaseTrack:
    """
    Manages the business case track for a feature.

    The business case track is one of four parallel tracks that run
    during feature development. It handles:

    1. **Assumptions Management**: Baseline metrics, impact estimates
    2. **BC Document Generation**: ROI analysis, budget estimates
    3. **Stakeholder Approval**: Track who needs to approve and status
    4. **Version Control**: BC document iterations (v1, v2, v2-approved)

    Integrates with:
    - feature-state.yaml: Stores track state in engine.tracks.business_case
    - Input Gate: Uses business_case_assumptions and business_case_approval gates
    - Context file: Updates action log on state changes

    Example:
        track = BusinessCaseTrack(feature_path)

        # Start the track
        result = track.start(initiated_by="jane")

        # Update assumptions
        track.update_assumptions(
            baseline_metrics={"conversion_rate": 0.65, "abandonment_rate": 0.35},
            impact_assumptions={"conversion_improvement": 0.10}
        )

        # Generate BC document
        track.generate_document(version=1)

        # Submit for approval
        result = track.submit_for_approval(
            approver="Jack Approver",
            message="Ready for review"
        )

        # Record approval
        track.record_approval(
            approver="Jack Approver",
            approved=True,
            approval_type="verbal",
            reference="Slack thread #meal-kit-planning"
        )
    """

    def __init__(self, feature_path: Path):
        """
        Initialize business case track.

        Args:
            feature_path: Path to the feature folder
        """
        self.feature_path = Path(feature_path)
        self.bc_folder = self.feature_path / "business-case"

        # Track state
        self._status = BCStatus.NOT_STARTED
        self._current_version: Optional[int] = None
        self._assumptions = BCAssumptions()
        self._approvals: List[StakeholderApproval] = []
        self._required_approvers: List[str] = []
        self._started_at: Optional[datetime] = None
        self._completed_at: Optional[datetime] = None
        self._started_by: Optional[str] = None

        # File references
        self._current_file: Optional[str] = None

        # Load existing state if available
        self._load_from_feature_state()

    @property
    def status(self) -> BCStatus:
        """Current track status."""
        return self._status

    @property
    def current_version(self) -> Optional[int]:
        """Current BC document version."""
        return self._current_version

    @property
    def assumptions(self) -> BCAssumptions:
        """Current assumptions."""
        return self._assumptions

    @property
    def approvals(self) -> List[StakeholderApproval]:
        """List of approval decisions."""
        return self._approvals

    @property
    def is_approved(self) -> bool:
        """Check if BC is approved (at least one approval and no rejections)."""
        if not self._approvals:
            return False
        # Check if any required approver has approved
        for approval in self._approvals:
            if approval.approved:
                return True
        return False

    @property
    def is_rejected(self) -> bool:
        """Check if BC is rejected."""
        return self._status == BCStatus.REJECTED

    @property
    def pending_approvers(self) -> List[str]:
        """Get list of approvers who haven't yet decided."""
        decided = {a.approver for a in self._approvals}
        return [a for a in self._required_approvers if a not in decided]

    # ========== Lifecycle Methods ==========

    def start(self, initiated_by: str) -> BCTrackResult:
        """
        Start the business case track.

        This initializes the BC track, creates the business-case folder
        if needed, and sets status to IN_PROGRESS.

        Args:
            initiated_by: Username of who started the track

        Returns:
            BCTrackResult with operation outcome
        """
        if self._status != BCStatus.NOT_STARTED:
            return BCTrackResult(
                success=False,
                status=self._status,
                message=f"Track already started (status: {self._status.value})",
            )

        # Create BC folder if needed
        self.bc_folder.mkdir(parents=True, exist_ok=True)

        # Update state
        self._status = BCStatus.IN_PROGRESS
        self._started_at = datetime.now()
        self._started_by = initiated_by
        self._current_version = 1

        # Save state
        self._save_to_feature_state()

        return BCTrackResult(
            success=True,
            status=BCStatus.IN_PROGRESS,
            message="Business case track started",
            version=1,
            metadata={
                "started_by": initiated_by,
                "started_at": self._started_at.isoformat(),
            },
        )

    def update_assumptions(
        self,
        baseline_metrics: Optional[Dict[str, Any]] = None,
        impact_assumptions: Optional[Dict[str, Any]] = None,
        investment_estimate: Optional[str] = None,
        roi_analysis: Optional[Dict[str, Any]] = None,
    ) -> BCTrackResult:
        """
        Update business case assumptions.

        Args:
            baseline_metrics: Current state metrics
            impact_assumptions: Expected improvement
            investment_estimate: Rough effort estimate (T-shirt size or points)
            roi_analysis: Calculated ROI analysis

        Returns:
            BCTrackResult with operation outcome
        """
        if self._status == BCStatus.NOT_STARTED:
            return BCTrackResult(
                success=False,
                status=self._status,
                message="Track not started. Call start() first.",
            )

        if self._status in (BCStatus.APPROVED, BCStatus.REJECTED):
            return BCTrackResult(
                success=False,
                status=self._status,
                message=f"Cannot update assumptions: track is {self._status.value}",
            )

        # Update assumptions
        if baseline_metrics:
            self._assumptions.baseline_metrics.update(baseline_metrics)
        if impact_assumptions:
            self._assumptions.impact_assumptions.update(impact_assumptions)
        if investment_estimate:
            self._assumptions.investment_estimate = investment_estimate
        if roi_analysis:
            self._assumptions.roi_analysis = roi_analysis

        # Save state
        self._save_to_feature_state()

        return BCTrackResult(
            success=True,
            status=self._status,
            message="Assumptions updated",
            metadata={"assumptions_complete": self._assumptions.is_complete},
        )

    def add_required_approver(self, approver: str) -> None:
        """
        Add a required approver to the list.

        Args:
            approver: Name of approver to add
        """
        if approver not in self._required_approvers:
            self._required_approvers.append(approver)
            self._save_to_feature_state()

    def set_required_approvers(self, approvers: List[str]) -> None:
        """
        Set the list of required approvers.

        Args:
            approvers: List of approver names
        """
        self._required_approvers = list(approvers)
        self._save_to_feature_state()

    def generate_document(
        self, version: Optional[int] = None, template: Optional[str] = None
    ) -> BCTrackResult:
        """
        Generate a business case document.

        Creates a markdown document in the business-case folder with
        the current assumptions and a structured template.

        Args:
            version: Version number (auto-incremented if not provided)
            template: Optional custom template content

        Returns:
            BCTrackResult with file path
        """
        if self._status == BCStatus.NOT_STARTED:
            return BCTrackResult(
                success=False,
                status=self._status,
                message="Track not started. Call start() first.",
            )

        if not self._assumptions.is_complete:
            return BCTrackResult(
                success=False,
                status=self._status,
                message="Assumptions incomplete. Provide baseline_metrics and impact_assumptions.",
            )

        # Determine version
        if version is None:
            version = self._current_version or 1

        # Generate document content
        if template:
            content = template
        else:
            content = self._generate_bc_template(version)

        # Write file
        filename = f"bc-v{version}.md"
        file_path = self.bc_folder / filename
        file_path.write_text(content)

        # Update state
        self._current_version = version
        self._current_file = filename
        self._save_to_feature_state()

        return BCTrackResult(
            success=True,
            status=self._status,
            message=f"Business case v{version} generated",
            version=version,
            file_path=file_path,
        )

    def submit_for_approval(
        self, approver: str, message: Optional[str] = None
    ) -> BCTrackResult:
        """
        Submit the business case for stakeholder approval.

        This transitions the track to PENDING_APPROVAL status and
        records the submission. Integrates with input gate system.

        Args:
            approver: Name of stakeholder to request approval from
            message: Optional message to approver

        Returns:
            BCTrackResult with submission details
        """
        if self._status not in (BCStatus.IN_PROGRESS, BCStatus.PENDING_APPROVAL):
            return BCTrackResult(
                success=False,
                status=self._status,
                message=f"Cannot submit for approval from status: {self._status.value}",
            )

        if not self._assumptions.is_complete:
            return BCTrackResult(
                success=False,
                status=self._status,
                message="Cannot submit: assumptions incomplete",
            )

        # Add to required approvers if not already there
        if approver not in self._required_approvers:
            self._required_approvers.append(approver)

        # Update status
        self._status = BCStatus.PENDING_APPROVAL
        self._save_to_feature_state()

        return BCTrackResult(
            success=True,
            status=BCStatus.PENDING_APPROVAL,
            message=f"Business case submitted for approval to {approver}",
            version=self._current_version,
            pending_approvers=self.pending_approvers,
            metadata={
                "submitted_to": approver,
                "submitted_at": datetime.now().isoformat(),
                "message": message,
            },
        )

    def record_approval(
        self,
        approver: str,
        approved: bool,
        approval_type: str = "verbal",
        reference: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> BCTrackResult:
        """
        Record a stakeholder approval or rejection decision.

        This records the decision and updates track status:
        - If approved: Marks as APPROVED if all required approvers approved
        - If rejected: Marks as REJECTED immediately

        Args:
            approver: Name of approver
            approved: True for approval, False for rejection
            approval_type: How approval was given (verbal, written, email, slack)
            reference: Link to evidence (Slack thread, email, etc.)
            notes: Additional context

        Returns:
            BCTrackResult with updated status
        """
        if self._status not in (BCStatus.PENDING_APPROVAL, BCStatus.IN_PROGRESS):
            return BCTrackResult(
                success=False,
                status=self._status,
                message=f"Cannot record approval from status: {self._status.value}",
            )

        # Create approval record
        approval = StakeholderApproval(
            approver=approver,
            approved=approved,
            date=datetime.now(),
            approval_type=approval_type,
            reference=reference,
            notes=notes,
        )

        # Add to approvals list
        self._approvals.append(approval)

        # Determine new status
        if not approved:
            # Rejection immediately rejects the BC
            self._status = BCStatus.REJECTED
            self._completed_at = datetime.now()

            # Rename file to indicate rejection
            if self._current_file:
                self._rename_to_status("rejected")

            result_message = f"Business case rejected by {approver}"
        else:
            # Check if all required approvers have approved
            approved_by = {a.approver for a in self._approvals if a.approved}
            required_set = set(self._required_approvers)

            if required_set and required_set.issubset(approved_by):
                # All required approvers have approved
                self._status = BCStatus.APPROVED
                self._completed_at = datetime.now()

                # Rename file to indicate approval
                if self._current_file:
                    self._rename_to_status("approved")

                result_message = "Business case approved"
            else:
                # Still waiting for more approvals
                result_message = f"Approval recorded from {approver}, awaiting: {self.pending_approvers}"

        # Save state
        self._save_to_feature_state()

        return BCTrackResult(
            success=True,
            status=self._status,
            message=result_message,
            version=self._current_version,
            pending_approvers=(
                self.pending_approvers
                if self._status == BCStatus.PENDING_APPROVAL
                else None
            ),
            metadata={
                "approval": approval.to_dict(),
                "all_approvals": [a.to_dict() for a in self._approvals],
            },
        )

    def _rename_to_status(self, status: str) -> None:
        """
        Rename current BC file to indicate final status.

        E.g., bc-v2.md -> bc-v2-approved.md
        """
        if not self._current_file:
            return

        current_path = self.bc_folder / self._current_file
        if not current_path.exists():
            return

        # Generate new filename
        base = self._current_file.rsplit(".", 1)[0]  # Remove .md
        new_filename = f"{base}-{status}.md"
        new_path = self.bc_folder / new_filename

        # Rename
        current_path.rename(new_path)
        self._current_file = new_filename

    # ========== Document Generation ==========

    def _generate_bc_template(self, version: int) -> str:
        """
        Generate business case document template.

        Args:
            version: Document version number

        Returns:
            Markdown content
        """
        now = datetime.now().strftime("%Y-%m-%d")

        # Format baseline metrics
        baseline_lines = []
        for key, value in self._assumptions.baseline_metrics.items():
            baseline_lines.append(f"- **{key}**: {value}")
        baseline_text = (
            "\n".join(baseline_lines)
            if baseline_lines
            else "- *No baseline metrics provided*"
        )

        # Format impact assumptions
        impact_lines = []
        for key, value in self._assumptions.impact_assumptions.items():
            impact_lines.append(f"- **{key}**: {value}")
        impact_text = (
            "\n".join(impact_lines)
            if impact_lines
            else "- *No impact assumptions provided*"
        )

        # Format investment estimate
        investment_text = (
            self._assumptions.investment_estimate
            or "TBD (pending engineering estimate)"
        )

        # Format ROI if available
        roi_section = ""
        if self._assumptions.roi_analysis:
            roi_lines = []
            for key, value in self._assumptions.roi_analysis.items():
                roi_lines.append(f"- **{key}**: {value}")
            roi_text = "\n".join(roi_lines)
            roi_section = f"""
## ROI Analysis

{roi_text}
"""

        # Format required approvers
        approvers_text = (
            ", ".join(self._required_approvers) if self._required_approvers else "TBD"
        )

        return f"""# Business Case v{version}

**Feature**: {self.feature_path.name}
**Version**: {version}
**Status**: {self._status.value}
**Date**: {now}

## Executive Summary

*[Brief summary of the business opportunity and recommendation]*

## Problem Statement

*[What problem are we solving? Reference the context document.]*

## Baseline Metrics

Current state metrics:

{baseline_text}

## Impact Assumptions

Expected improvements:

{impact_text}

## Investment Estimate

{investment_text}
{roi_section}
## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| *Risk 1* | *Impact* | *Mitigation* |

## Approval Required From

{approvers_text}

## Approval History

| Approver | Decision | Date | Type | Reference |
|----------|----------|------|------|-----------|

---
*Generated by Context Creation Engine*
"""

    # ========== State Persistence ==========

    def _load_from_feature_state(self) -> None:
        """Load track state from feature-state.yaml."""
        state_file = self.feature_path / "feature-state.yaml"
        if not state_file.exists():
            return

        try:
            with open(state_file, "r") as f:
                data = yaml.safe_load(f)
        except Exception:
            return

        if not data:
            return

        # Get track data from engine.tracks.business_case
        engine = data.get("engine", {})
        tracks = engine.get("tracks", {})
        bc_data = tracks.get("business_case", {})

        if not bc_data:
            return

        # Restore status
        status_str = bc_data.get("status", "not_started")
        try:
            self._status = BCStatus(status_str)
        except ValueError:
            # Map from TrackStatus to BCStatus
            status_mapping = {
                "not_started": BCStatus.NOT_STARTED,
                "in_progress": BCStatus.IN_PROGRESS,
                "pending_input": BCStatus.IN_PROGRESS,
                "pending_approval": BCStatus.PENDING_APPROVAL,
                "complete": BCStatus.APPROVED,
                "blocked": BCStatus.IN_PROGRESS,
            }
            self._status = status_mapping.get(status_str, BCStatus.NOT_STARTED)

        # Restore version
        self._current_version = bc_data.get("current_version")

        # Restore file reference
        self._current_file = bc_data.get("file")

        # Restore approvals
        approvals_data = bc_data.get("approvals", [])
        self._approvals = [StakeholderApproval.from_dict(a) for a in approvals_data]

        # Restore required approvers
        self._required_approvers = bc_data.get("required_approvers", [])

        # Restore assumptions from artifacts if available
        artifacts = bc_data.get("artifacts", {})
        assumptions_data = artifacts.get("assumptions", {})
        if assumptions_data:
            self._assumptions = BCAssumptions.from_dict(assumptions_data)

    def _save_to_feature_state(self) -> None:
        """Save track state to feature-state.yaml."""
        state_file = self.feature_path / "feature-state.yaml"

        # Load existing state
        data = {}
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    data = yaml.safe_load(f) or {}
            except Exception:
                pass

        # Ensure engine.tracks structure exists
        if "engine" not in data:
            data["engine"] = {}
        if "tracks" not in data["engine"]:
            data["engine"]["tracks"] = {}

        # Update business_case track
        data["engine"]["tracks"]["business_case"] = {
            "status": self._status.value,
            "current_version": self._current_version,
            "file": self._current_file,
            "approvals": [a.to_dict() for a in self._approvals],
            "required_approvers": self._required_approvers,
            "artifacts": {"assumptions": self._assumptions.to_dict()},
        }

        # Write back
        try:
            with open(state_file, "w") as f:
                yaml.dump(
                    data,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )
        except Exception:
            pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert track state to dictionary."""
        return {
            "status": self._status.value,
            "current_version": self._current_version,
            "file": self._current_file,
            "assumptions": self._assumptions.to_dict(),
            "approvals": [a.to_dict() for a in self._approvals],
            "required_approvers": self._required_approvers,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "completed_at": (
                self._completed_at.isoformat() if self._completed_at else None
            ),
            "started_by": self._started_by,
            "is_approved": self.is_approved,
            "is_rejected": self.is_rejected,
            "pending_approvers": self.pending_approvers,
        }

    @classmethod
    def from_feature_path(cls, feature_path: Path) -> "BusinessCaseTrack":
        """
        Create a BusinessCaseTrack instance from a feature path.

        Args:
            feature_path: Path to the feature folder

        Returns:
            BusinessCaseTrack instance with state loaded from feature-state.yaml
        """
        return cls(feature_path)


def get_bc_status_for_feature_state(bc_status: BCStatus) -> str:
    """
    Map BCStatus to TrackStatus string for feature-state.yaml compatibility.

    Args:
        bc_status: BCStatus enum value

    Returns:
        TrackStatus string value
    """
    mapping = {
        BCStatus.NOT_STARTED: "not_started",
        BCStatus.IN_PROGRESS: "in_progress",
        BCStatus.PENDING_APPROVAL: "pending_approval",
        BCStatus.APPROVED: "complete",
        BCStatus.REJECTED: "blocked",
    }
    return mapping.get(bc_status, "not_started")
