"""
Quality Gates Configuration

Defines quality gate thresholds and validation rules for the Context Creation Engine.
Based on PRD Section F.2 requirements.

Quality Gate Thresholds:
    - Context Document: 60% (draft/v2), 75% (review/v2+), 85% (approved/v3)
    - Business Case: Requires stakeholder approval (configurable stakeholders)
    - Design: Figma required, wireframes optional but recommended
    - Engineering: ADRs decided, estimates provided

Usage:
    from tools.context_engine.quality_gates import (
        QualityGates,
        validate_context_gate,
        validate_business_case_gate,
        validate_design_gate,
        validate_engineering_gate,
        validate_decision_gate,
    )

    # Use default thresholds
    gates = QualityGates()

    # Or customize per product
    gates = QualityGates(
        context_draft_threshold=55,
        context_review_threshold=70,
        context_approved_threshold=80,
        required_bc_approvers=["ceo", "vp_product"],
        figma_required=True,
        wireframes_required=False,
    )

    # Validate a specific gate
    result = validate_context_gate(state, feature_path, gates)
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ========== Enums ==========


class GateStatus(Enum):
    """Status values for quality gate checks."""

    PASS = "pass"
    FAIL = "fail"
    NOT_STARTED = "not_started"
    INCOMPLETE = "incomplete"
    WARNING = "warning"  # Passes but with concerns


class GateLevel(Enum):
    """Quality gate severity levels."""

    BLOCKING = "blocking"  # Must pass to proceed
    REQUIRED = "required"  # Must pass for completion
    ADVISORY = "advisory"  # Recommended but not required


class ThresholdLevel(Enum):
    """Context document threshold levels."""

    DRAFT = "draft"  # v1 - initial creation
    REVIEW = "review"  # v2 - after first challenge
    APPROVED = "approved"  # v3 - ready for approval


# ========== Data Classes ==========


@dataclass
class GateResult:
    """
    Result of a single quality gate check.

    Attributes:
        gate_name: Identifier for the gate (e.g., "context_score_threshold")
        status: Pass/fail/incomplete status
        message: Human-readable status message
        level: Blocking/required/advisory level
        score: Numeric score if applicable
        threshold: Threshold value if applicable
        action: Suggested action to resolve failure
        evidence: Supporting evidence for the result
        metadata: Additional context
    """

    gate_name: str
    status: GateStatus
    message: str
    level: GateLevel = GateLevel.REQUIRED
    score: Optional[float] = None
    threshold: Optional[float] = None
    action: Optional[str] = None
    evidence: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_blocking(self) -> bool:
        """Check if this gate is blocking."""
        return self.level == GateLevel.BLOCKING

    @property
    def passed(self) -> bool:
        """Check if gate passed."""
        return self.status in (GateStatus.PASS, GateStatus.WARNING)

    @property
    def needs_attention(self) -> bool:
        """Check if gate needs attention (failed or warning)."""
        return self.status in (
            GateStatus.FAIL,
            GateStatus.INCOMPLETE,
            GateStatus.WARNING,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "gate_name": self.gate_name,
            "status": self.status.value,
            "message": self.message,
            "level": self.level.value,
            "is_blocking": self.is_blocking,
        }
        if self.score is not None:
            result["score"] = self.score
        if self.threshold is not None:
            result["threshold"] = self.threshold
        if self.action:
            result["action"] = self.action
        if self.evidence:
            result["evidence"] = self.evidence
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class PhaseGateResult:
    """
    Aggregated gate results for a phase.

    Attributes:
        phase: Phase name (context, design, business_case, engineering, decision_gate)
        status: Overall phase status
        gates: List of individual gate results
        blockers: List of blocking issues
        warnings: List of warnings
        passed_count: Number of gates passed
        total_count: Total number of gates
    """

    phase: str
    status: GateStatus
    gates: List[GateResult] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def passed_count(self) -> int:
        """Count of passed gates."""
        return sum(1 for g in self.gates if g.passed)

    @property
    def total_count(self) -> int:
        """Total gate count."""
        return len(self.gates)

    @property
    def has_blockers(self) -> bool:
        """Check if any blockers exist."""
        return len(self.blockers) > 0

    @property
    def blocking_gates_passed(self) -> bool:
        """Check if all blocking gates passed."""
        blocking = [g for g in self.gates if g.is_blocking]
        return all(g.passed for g in blocking)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "phase": self.phase,
            "status": self.status.value,
            "gates": [g.to_dict() for g in self.gates],
            "blockers": self.blockers,
            "warnings": self.warnings,
            "passed_count": self.passed_count,
            "total_count": self.total_count,
            "has_blockers": self.has_blockers,
        }


@dataclass
class StakeholderRequirement:
    """
    Defines a stakeholder approval requirement.

    Attributes:
        role: Stakeholder role (e.g., "product_lead", "engineering_lead")
        name: Optional specific person name
        required: Whether approval is required
        can_delegate: Whether approval can be delegated
    """

    role: str
    name: Optional[str] = None
    required: bool = True
    can_delegate: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "role": self.role,
            "required": self.required,
            "can_delegate": self.can_delegate,
        }
        if self.name:
            result["name"] = self.name
        return result


@dataclass
class DesignArtifactRequirement:
    """
    Defines a design artifact requirement.

    Attributes:
        artifact_type: Type of artifact (figma, wireframes, prototype, etc.)
        required: Whether artifact is required
        url_pattern: Optional URL validation pattern
        description: Human-readable description
    """

    artifact_type: str
    required: bool = True
    url_pattern: Optional[str] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "artifact_type": self.artifact_type,
            "required": self.required,
            "url_pattern": self.url_pattern,
            "description": self.description,
        }


@dataclass
class EngineeringRequirement:
    """
    Defines an engineering track requirement.

    Attributes:
        requirement_type: Type (adr, estimate, dependency, risk)
        required: Whether it's required
        min_count: Minimum count required
        description: Human-readable description
    """

    requirement_type: str
    required: bool = True
    min_count: int = 0
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "requirement_type": self.requirement_type,
            "required": self.required,
            "min_count": self.min_count,
            "description": self.description,
        }


# ========== Main Configuration Class ==========


@dataclass
class QualityGates:
    """
    Quality gate configuration for the Context Creation Engine.

    Default values are based on PRD Section F.2 requirements:
        - Context doc: 60% draft, 75% review, 85% approved
        - Business case: stakeholder approval required
        - Design: Figma required, wireframes recommended
        - Engineering: ADRs decided, estimate required

    All thresholds can be overridden per product or organization.

    Usage:
        # Default configuration
        gates = QualityGates()

        # Custom thresholds
        gates = QualityGates(
            context_draft_threshold=55,
            context_review_threshold=70,
            context_approved_threshold=80,
        )

        # Access thresholds
        min_score = gates.get_context_threshold(ThresholdLevel.REVIEW)
    """

    # Context document thresholds (orthogonal challenge scores)
    context_draft_threshold: float = 60.0  # v1 minimum score
    context_review_threshold: float = 75.0  # v2 minimum score
    context_approved_threshold: float = 85.0  # v3 minimum score

    # Context document requirements
    context_requires_problem_statement: bool = True
    context_requires_success_metrics: bool = True
    context_requires_scope: bool = True
    context_requires_stakeholders: bool = False  # Advisory for v1
    context_max_challenge_iterations: int = 3  # Max iterations before escalation

    # Business case requirements
    bc_requires_baseline_metrics: bool = True
    bc_requires_impact_assumptions: bool = True
    bc_requires_roi_analysis: bool = False  # Advisory
    bc_roi_must_be_positive: bool = False  # Warning if negative
    bc_stakeholder_requirements: List[StakeholderRequirement] = field(
        default_factory=lambda: [
            StakeholderRequirement(
                role="product_lead",
                required=True,
                can_delegate=True,
            ),
        ]
    )

    # Design track requirements
    design_artifacts: List[DesignArtifactRequirement] = field(
        default_factory=lambda: [
            DesignArtifactRequirement(
                artifact_type="figma",
                required=True,
                url_pattern=r"^https?://.*figma\.com.*",
                description="Figma design file URL",
            ),
            DesignArtifactRequirement(
                artifact_type="wireframes",
                required=False,
                description="Wireframes URL (recommended but optional)",
            ),
        ]
    )
    design_requires_spec: bool = True
    design_spec_requires_approval: bool = True

    # Engineering track requirements
    engineering_requirements: List[EngineeringRequirement] = field(
        default_factory=lambda: [
            EngineeringRequirement(
                requirement_type="adr",
                required=False,  # ADRs are recommended, not required
                min_count=0,
                description="Architecture Decision Records",
            ),
            EngineeringRequirement(
                requirement_type="estimate",
                required=True,
                description="Engineering effort estimate (S/M/L/XL)",
            ),
            EngineeringRequirement(
                requirement_type="dependency",
                required=False,
                description="Dependencies must be identified (not blocking)",
            ),
        ]
    )
    engineering_adrs_must_be_decided: bool = True  # Proposed ADRs block
    engineering_high_risks_require_mitigation: bool = True
    engineering_blocking_deps_fail: bool = True

    # Decision gate requirements
    decision_gate_requires_all_tracks: bool = True
    decision_gate_parallel_design_allowed: bool = True  # Design can be in progress

    # Product/organization overrides
    product_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def get_context_threshold(self, level: ThresholdLevel) -> float:
        """
        Get the context document score threshold for a given level.

        Args:
            level: ThresholdLevel (DRAFT, REVIEW, APPROVED)

        Returns:
            Score threshold (0-100)
        """
        thresholds = {
            ThresholdLevel.DRAFT: self.context_draft_threshold,
            ThresholdLevel.REVIEW: self.context_review_threshold,
            ThresholdLevel.APPROVED: self.context_approved_threshold,
        }
        return thresholds.get(level, self.context_draft_threshold)

    def get_threshold_for_version(self, version: int) -> float:
        """
        Get the required score threshold for a context document version.

        Args:
            version: Document version (1, 2, or 3)

        Returns:
            Required score threshold
        """
        if version <= 1:
            return self.context_draft_threshold
        elif version == 2:
            return self.context_review_threshold
        else:
            return self.context_approved_threshold

    def get_design_artifact(
        self, artifact_type: str
    ) -> Optional[DesignArtifactRequirement]:
        """
        Get design artifact requirement by type.

        Args:
            artifact_type: Artifact type (figma, wireframes, etc.)

        Returns:
            DesignArtifactRequirement or None if not found
        """
        for artifact in self.design_artifacts:
            if artifact.artifact_type == artifact_type:
                return artifact
        return None

    def is_figma_required(self) -> bool:
        """Check if Figma design is required."""
        figma = self.get_design_artifact("figma")
        return figma is not None and figma.required

    def is_wireframes_required(self) -> bool:
        """Check if wireframes are required."""
        wireframes = self.get_design_artifact("wireframes")
        return wireframes is not None and wireframes.required

    def get_required_approvers(self) -> List[str]:
        """
        Get list of required approver roles.

        Returns:
            List of role names that must approve
        """
        return [req.role for req in self.bc_stakeholder_requirements if req.required]

    def apply_product_overrides(self, product_id: str) -> "QualityGates":
        """
        Apply product-specific overrides to create a new QualityGates instance.

        Args:
            product_id: Product identifier

        Returns:
            New QualityGates with overrides applied
        """
        if product_id not in self.product_overrides:
            return self

        overrides = self.product_overrides[product_id]

        # Create a copy with overrides
        return QualityGates(
            context_draft_threshold=overrides.get(
                "context_draft_threshold", self.context_draft_threshold
            ),
            context_review_threshold=overrides.get(
                "context_review_threshold", self.context_review_threshold
            ),
            context_approved_threshold=overrides.get(
                "context_approved_threshold", self.context_approved_threshold
            ),
            # ... additional fields can be overridden
            product_overrides=self.product_overrides,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "context": {
                "thresholds": {
                    "draft": self.context_draft_threshold,
                    "review": self.context_review_threshold,
                    "approved": self.context_approved_threshold,
                },
                "requirements": {
                    "problem_statement": self.context_requires_problem_statement,
                    "success_metrics": self.context_requires_success_metrics,
                    "scope": self.context_requires_scope,
                    "stakeholders": self.context_requires_stakeholders,
                },
                "max_iterations": self.context_max_challenge_iterations,
            },
            "business_case": {
                "requirements": {
                    "baseline_metrics": self.bc_requires_baseline_metrics,
                    "impact_assumptions": self.bc_requires_impact_assumptions,
                    "roi_analysis": self.bc_requires_roi_analysis,
                    "roi_must_be_positive": self.bc_roi_must_be_positive,
                },
                "stakeholder_requirements": [
                    req.to_dict() for req in self.bc_stakeholder_requirements
                ],
            },
            "design": {
                "artifacts": [a.to_dict() for a in self.design_artifacts],
                "requires_spec": self.design_requires_spec,
                "spec_requires_approval": self.design_spec_requires_approval,
            },
            "engineering": {
                "requirements": [r.to_dict() for r in self.engineering_requirements],
                "adrs_must_be_decided": self.engineering_adrs_must_be_decided,
                "high_risks_require_mitigation": self.engineering_high_risks_require_mitigation,
                "blocking_deps_fail": self.engineering_blocking_deps_fail,
            },
            "decision_gate": {
                "requires_all_tracks": self.decision_gate_requires_all_tracks,
                "parallel_design_allowed": self.decision_gate_parallel_design_allowed,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualityGates":
        """Create QualityGates from dictionary."""
        context = data.get("context", {})
        thresholds = context.get("thresholds", {})
        ctx_requirements = context.get("requirements", {})

        bc = data.get("business_case", {})
        bc_requirements = bc.get("requirements", {})

        design = data.get("design", {})
        engineering = data.get("engineering", {})
        decision_gate = data.get("decision_gate", {})

        return cls(
            # Context thresholds
            context_draft_threshold=thresholds.get("draft", 60.0),
            context_review_threshold=thresholds.get("review", 75.0),
            context_approved_threshold=thresholds.get("approved", 85.0),
            # Context requirements
            context_requires_problem_statement=ctx_requirements.get(
                "problem_statement", True
            ),
            context_requires_success_metrics=ctx_requirements.get(
                "success_metrics", True
            ),
            context_requires_scope=ctx_requirements.get("scope", True),
            context_requires_stakeholders=ctx_requirements.get("stakeholders", False),
            context_max_challenge_iterations=context.get("max_iterations", 3),
            # Business case requirements
            bc_requires_baseline_metrics=bc_requirements.get("baseline_metrics", True),
            bc_requires_impact_assumptions=bc_requirements.get(
                "impact_assumptions", True
            ),
            bc_requires_roi_analysis=bc_requirements.get("roi_analysis", False),
            bc_roi_must_be_positive=bc_requirements.get("roi_must_be_positive", False),
            # Design
            design_requires_spec=design.get("requires_spec", True),
            design_spec_requires_approval=design.get("spec_requires_approval", True),
            # Engineering
            engineering_adrs_must_be_decided=engineering.get(
                "adrs_must_be_decided", True
            ),
            engineering_high_risks_require_mitigation=engineering.get(
                "high_risks_require_mitigation", True
            ),
            engineering_blocking_deps_fail=engineering.get("blocking_deps_fail", True),
            # Decision gate
            decision_gate_requires_all_tracks=decision_gate.get(
                "requires_all_tracks", True
            ),
            decision_gate_parallel_design_allowed=decision_gate.get(
                "parallel_design_allowed", True
            ),
        )


# ========== Validation Functions ==========


def validate_context_score(
    score: float, version: int, gates: Optional[QualityGates] = None
) -> GateResult:
    """
    Validate a context document's orthogonal challenge score.

    Args:
        score: Challenge score (0-100)
        version: Document version (1, 2, or 3)
        gates: Quality gates configuration (uses defaults if None)

    Returns:
        GateResult with pass/fail status
    """
    gates = gates or QualityGates()
    threshold = gates.get_threshold_for_version(version)

    if score >= threshold:
        return GateResult(
            gate_name=f"context_score_v{version}",
            status=GateStatus.PASS,
            message=f"Challenge score {score:.0f} meets v{version} threshold ({threshold:.0f})",
            level=GateLevel.BLOCKING,
            score=score,
            threshold=threshold,
        )
    else:
        gap = threshold - score
        return GateResult(
            gate_name=f"context_score_v{version}",
            status=GateStatus.FAIL,
            message=f"Challenge score {score:.0f} below v{version} threshold ({threshold:.0f})",
            level=GateLevel.BLOCKING,
            score=score,
            threshold=threshold,
            action=f"Address challenge findings to improve score by {gap:.0f}+ points",
        )


def validate_context_requirements(
    has_problem_statement: bool,
    has_success_metrics: bool,
    has_scope: bool,
    has_stakeholders: bool = False,
    gates: Optional[QualityGates] = None,
) -> List[GateResult]:
    """
    Validate context document content requirements.

    Args:
        has_problem_statement: Whether problem statement is present
        has_success_metrics: Whether success metrics are defined
        has_scope: Whether scope is defined
        has_stakeholders: Whether stakeholders are defined
        gates: Quality gates configuration

    Returns:
        List of GateResults for each requirement
    """
    gates = gates or QualityGates()
    results = []

    # Problem statement
    if gates.context_requires_problem_statement:
        results.append(
            GateResult(
                gate_name="problem_statement_present",
                status=GateStatus.PASS if has_problem_statement else GateStatus.FAIL,
                message=(
                    "Problem statement present"
                    if has_problem_statement
                    else "Problem statement missing"
                ),
                level=GateLevel.BLOCKING,
                action=(
                    None
                    if has_problem_statement
                    else "Add problem statement to context document"
                ),
            )
        )

    # Success metrics
    if gates.context_requires_success_metrics:
        results.append(
            GateResult(
                gate_name="success_metrics_defined",
                status=GateStatus.PASS if has_success_metrics else GateStatus.FAIL,
                message=(
                    "Success metrics defined"
                    if has_success_metrics
                    else "Success metrics not defined"
                ),
                level=GateLevel.BLOCKING,
                action=(
                    None
                    if has_success_metrics
                    else "Define success metrics in context document"
                ),
            )
        )

    # Scope
    if gates.context_requires_scope:
        results.append(
            GateResult(
                gate_name="scope_defined",
                status=GateStatus.PASS if has_scope else GateStatus.FAIL,
                message="Scope defined" if has_scope else "Scope not defined",
                level=GateLevel.BLOCKING,
                action=None if has_scope else "Define in-scope and out-of-scope items",
            )
        )

    # Stakeholders (advisory by default)
    if gates.context_requires_stakeholders:
        results.append(
            GateResult(
                gate_name="stakeholders_defined",
                status=GateStatus.PASS if has_stakeholders else GateStatus.INCOMPLETE,
                message=(
                    "Stakeholders defined"
                    if has_stakeholders
                    else "Stakeholders section missing"
                ),
                level=GateLevel.ADVISORY,
                action=(
                    None
                    if has_stakeholders
                    else "Add stakeholders section (recommended)"
                ),
            )
        )

    return results


def validate_business_case_approval(
    approvals: List[Dict[str, Any]],
    required_approvers: Optional[List[str]] = None,
    gates: Optional[QualityGates] = None,
) -> GateResult:
    """
    Validate business case stakeholder approval status.

    Args:
        approvals: List of approval records [{"approver": name, "approved": bool, ...}]
        required_approvers: Optional explicit list of required approver names
        gates: Quality gates configuration

    Returns:
        GateResult with approval status
    """
    gates = gates or QualityGates()

    # Get required approver roles
    if required_approvers:
        required = set(required_approvers)
    else:
        required = set(gates.get_required_approvers())

    # Check who has approved
    approved_by = {a["approver"] for a in approvals if a.get("approved", False)}
    rejected_by = {a["approver"] for a in approvals if not a.get("approved", True)}

    # If any rejection, fail immediately
    if rejected_by:
        rejectors = ", ".join(rejected_by)
        return GateResult(
            gate_name="stakeholder_approval",
            status=GateStatus.FAIL,
            message=f"Business case rejected by: {rejectors}",
            level=GateLevel.BLOCKING,
            action="Address rejection feedback and resubmit for approval",
            evidence=f"Rejected by: {rejectors}",
        )

    # If required approvers specified, check them
    if required:
        pending = required - approved_by
        if pending:
            pending_str = ", ".join(pending)
            return GateResult(
                gate_name="stakeholder_approval",
                status=GateStatus.INCOMPLETE,
                message=f"Awaiting approval from: {pending_str}",
                level=GateLevel.BLOCKING,
                action=f"Obtain approval from: {pending_str}",
                metadata={"pending_approvers": list(pending)},
            )

    # All required approvers have approved
    if approved_by:
        approvers_str = ", ".join(approved_by)
        return GateResult(
            gate_name="stakeholder_approval",
            status=GateStatus.PASS,
            message=f"Business case approved by: {approvers_str}",
            level=GateLevel.BLOCKING,
            evidence=f"Approved by: {approvers_str}",
        )

    # No approvals yet
    return GateResult(
        gate_name="stakeholder_approval",
        status=GateStatus.INCOMPLETE,
        message="Business case not yet submitted for approval",
        level=GateLevel.BLOCKING,
        action="Submit business case for stakeholder approval",
    )


def validate_design_artifacts(
    artifacts: Dict[str, Optional[str]], gates: Optional[QualityGates] = None
) -> List[GateResult]:
    """
    Validate design artifact requirements.

    Args:
        artifacts: Dictionary of artifact URLs {"figma": url, "wireframes": url, ...}
        gates: Quality gates configuration

    Returns:
        List of GateResults for each artifact requirement
    """
    import re

    gates = gates or QualityGates()
    results = []

    for artifact_req in gates.design_artifacts:
        artifact_type = artifact_req.artifact_type
        url = artifacts.get(artifact_type)
        has_artifact = url is not None and url.strip() != ""

        # Determine status
        if has_artifact:
            # Validate URL pattern if specified
            if artifact_req.url_pattern:
                if re.match(artifact_req.url_pattern, url):
                    status = GateStatus.PASS
                    message = f"{artifact_type.title()} attached: {url[:50]}..."
                else:
                    status = GateStatus.WARNING
                    message = f"{artifact_type.title()} URL format may be invalid"
            else:
                status = GateStatus.PASS
                message = f"{artifact_type.title()} attached"
        else:
            if artifact_req.required:
                status = GateStatus.FAIL
                message = f"{artifact_type.title()} not attached (required)"
            else:
                status = GateStatus.INCOMPLETE
                message = f"{artifact_type.title()} not attached (recommended)"

        results.append(
            GateResult(
                gate_name=f"{artifact_type}_provided",
                status=status,
                message=message,
                level=(
                    GateLevel.BLOCKING if artifact_req.required else GateLevel.ADVISORY
                ),
                action=(
                    None
                    if has_artifact
                    else f"Attach {artifact_type} URL via /attach-artifact {artifact_type}"
                ),
                evidence=url if has_artifact else None,
            )
        )

    return results


def validate_engineering_readiness(
    has_estimate: bool,
    estimate_value: Optional[str] = None,
    adr_count: int = 0,
    proposed_adr_count: int = 0,
    blocking_dep_count: int = 0,
    high_risk_unmitigated_count: int = 0,
    gates: Optional[QualityGates] = None,
) -> List[GateResult]:
    """
    Validate engineering track readiness.

    Args:
        has_estimate: Whether an estimate has been provided
        estimate_value: The estimate value (S/M/L/XL)
        adr_count: Total number of ADRs
        proposed_adr_count: Number of ADRs still in proposed status
        blocking_dep_count: Number of blocking dependencies
        high_risk_unmitigated_count: Number of high-impact unmitigated risks
        gates: Quality gates configuration

    Returns:
        List of GateResults for engineering requirements
    """
    gates = gates or QualityGates()
    results = []

    # Estimate requirement
    for req in gates.engineering_requirements:
        if req.requirement_type == "estimate":
            results.append(
                GateResult(
                    gate_name="estimate_provided",
                    status=GateStatus.PASS if has_estimate else GateStatus.FAIL,
                    message=(
                        f"Estimate: {estimate_value}"
                        if has_estimate
                        else "Engineering estimate not provided"
                    ),
                    level=GateLevel.BLOCKING if req.required else GateLevel.ADVISORY,
                    action=(
                        None
                        if has_estimate
                        else "Provide engineering effort estimate (S/M/L/XL)"
                    ),
                    evidence=estimate_value,
                )
            )

    # ADR decision requirement
    if gates.engineering_adrs_must_be_decided:
        if adr_count > 0 and proposed_adr_count > 0:
            results.append(
                GateResult(
                    gate_name="adrs_decided",
                    status=GateStatus.FAIL,
                    message=f"{proposed_adr_count} ADR(s) pending decision",
                    level=GateLevel.BLOCKING,
                    action="Accept or reject pending ADRs via /adr-decide",
                )
            )
        elif adr_count > 0:
            results.append(
                GateResult(
                    gate_name="adrs_decided",
                    status=GateStatus.PASS,
                    message=f"{adr_count} ADR(s) decided",
                )
            )
        else:
            results.append(
                GateResult(
                    gate_name="adrs_decided",
                    status=GateStatus.PASS,
                    message="No ADRs required",
                    level=GateLevel.ADVISORY,
                )
            )

    # Blocking dependencies
    if gates.engineering_blocking_deps_fail and blocking_dep_count > 0:
        results.append(
            GateResult(
                gate_name="no_blocking_dependencies",
                status=GateStatus.FAIL,
                message=f"{blocking_dep_count} blocking dependency(ies)",
                level=GateLevel.BLOCKING,
                action="Resolve blocking dependencies or update their status",
            )
        )
    else:
        results.append(
            GateResult(
                gate_name="no_blocking_dependencies",
                status=GateStatus.PASS,
                message="No blocking dependencies",
            )
        )

    # High-impact risks
    if (
        gates.engineering_high_risks_require_mitigation
        and high_risk_unmitigated_count > 0
    ):
        results.append(
            GateResult(
                gate_name="high_risks_mitigated",
                status=GateStatus.FAIL,
                message=f"{high_risk_unmitigated_count} high-impact risk(s) need mitigation",
                level=GateLevel.BLOCKING,
                action="Add mitigation plans for high-impact risks",
            )
        )
    else:
        results.append(
            GateResult(
                gate_name="high_risks_mitigated",
                status=GateStatus.PASS,
                message="All high-impact risks have mitigations",
            )
        )

    return results


def validate_decision_gate_readiness(
    context_passed: bool,
    business_case_approved: bool,
    design_acceptable: bool,
    engineering_complete: bool,
    has_blocking_risks: bool = False,
    gates: Optional[QualityGates] = None,
) -> PhaseGateResult:
    """
    Validate readiness for decision gate.

    Args:
        context_passed: Whether context track has passed all gates
        business_case_approved: Whether BC is approved
        design_acceptable: Whether design is complete or acceptable for parallel
        engineering_complete: Whether engineering track is complete
        has_blocking_risks: Whether there are unmitigated high-impact risks
        gates: Quality gates configuration

    Returns:
        PhaseGateResult with decision gate readiness status
    """
    gates_config = gates or QualityGates()
    gate_results = []
    blockers = []

    # Context complete
    gate_results.append(
        GateResult(
            gate_name="context_doc_complete",
            status=GateStatus.PASS if context_passed else GateStatus.FAIL,
            message=(
                "Context document complete"
                if context_passed
                else "Context document incomplete"
            ),
            level=GateLevel.BLOCKING,
            action=None if context_passed else "Complete context document requirements",
        )
    )
    if not context_passed:
        blockers.append("Context document must be complete")

    # Business case approved
    gate_results.append(
        GateResult(
            gate_name="business_case_approved",
            status=GateStatus.PASS if business_case_approved else GateStatus.FAIL,
            message=(
                "Business case approved"
                if business_case_approved
                else "Business case not approved"
            ),
            level=GateLevel.BLOCKING,
            action=None if business_case_approved else "Obtain business case approval",
        )
    )
    if not business_case_approved:
        blockers.append("Business case approval required")

    # Design track
    if gates_config.decision_gate_parallel_design_allowed:
        # Design can be in progress, just needs minimum artifacts
        gate_results.append(
            GateResult(
                gate_name="design_track_acceptable",
                status=GateStatus.PASS if design_acceptable else GateStatus.INCOMPLETE,
                message=(
                    "Design track acceptable"
                    if design_acceptable
                    else "Required design artifacts missing"
                ),
                level=GateLevel.BLOCKING,
                action=(
                    None if design_acceptable else "Attach required design artifacts"
                ),
            )
        )
    else:
        gate_results.append(
            GateResult(
                gate_name="design_track_complete",
                status=GateStatus.PASS if design_acceptable else GateStatus.FAIL,
                message=(
                    "Design track complete"
                    if design_acceptable
                    else "Design track incomplete"
                ),
                level=GateLevel.BLOCKING,
                action=None if design_acceptable else "Complete design track",
            )
        )
    if not design_acceptable:
        blockers.append("Design artifacts required")

    # Engineering complete
    gate_results.append(
        GateResult(
            gate_name="engineering_spec_complete",
            status=GateStatus.PASS if engineering_complete else GateStatus.INCOMPLETE,
            message=(
                "Engineering spec complete"
                if engineering_complete
                else "Engineering spec incomplete"
            ),
            level=GateLevel.BLOCKING,
            action=(
                None if engineering_complete else "Complete engineering specification"
            ),
        )
    )
    if not engineering_complete:
        blockers.append("Engineering specification required")

    # No blocking risks
    gate_results.append(
        GateResult(
            gate_name="no_blocking_risks",
            status=GateStatus.FAIL if has_blocking_risks else GateStatus.PASS,
            message=(
                "No blocking risks"
                if not has_blocking_risks
                else "High-impact risks need mitigation"
            ),
            level=GateLevel.BLOCKING,
            action=None if not has_blocking_risks else "Mitigate high-impact risks",
        )
    )
    if has_blocking_risks:
        blockers.append("High-impact risks must be mitigated")

    # Determine overall status
    all_passed = all(g.status == GateStatus.PASS for g in gate_results)
    overall_status = GateStatus.PASS if all_passed else GateStatus.FAIL

    return PhaseGateResult(
        phase="decision_gate",
        status=overall_status,
        gates=gate_results,
        blockers=blockers,
    )


# ========== Default Instance ==========

# Default quality gates configuration
DEFAULT_QUALITY_GATES = QualityGates()


def get_default_gates() -> QualityGates:
    """Get the default quality gates configuration."""
    return DEFAULT_QUALITY_GATES


def create_gates_for_product(
    product_id: str, overrides: Optional[Dict[str, Any]] = None
) -> QualityGates:
    """
    Create a QualityGates instance for a specific product with optional overrides.

    Args:
        product_id: Product identifier
        overrides: Optional dictionary of threshold overrides

    Returns:
        QualityGates configured for the product
    """
    gates = QualityGates()

    if overrides:
        gates.product_overrides[product_id] = overrides
        return gates.apply_product_overrides(product_id)

    return gates
