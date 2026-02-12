# Validate Feature

Run validation checks against quality gates for each phase of a feature in the Context Creation Engine.

## Overview

This command validates a feature against the quality gates defined in PRD Section F.2, providing:
1. Phase-by-phase validation status (PASS/INCOMPLETE/NOT_STARTED)
2. Gate-level pass/fail details
3. Blocker identification (what's preventing advancement)
4. Actionable next steps for failed gates

## Arguments

- `<slug>` - Feature slug (optional, uses current directory if not specified)
- `--phase <phase>` - Validate specific phase only (context, design, business_case, engineering, decision_gate)
- `--verbose` - Show detailed gate criteria and evidence

**Examples:**
```
/validate-feature
/validate-feature mk-feature-recovery
/validate-feature mk-feature-recovery --phase design
/validate-feature --verbose
```

## Instructions

### Step 1: Find and Load the Feature

Locate the feature folder and load state including specialized tracks.

```python
import sys
sys.path.insert(0, "$PM_OS_COMMON/tools")
from pathlib import Path
from context_engine import FeatureEngine
from context_engine.feature_state import FeatureState, TrackStatus
from context_engine.tracks.business_case import BusinessCaseTrack, BCStatus
from context_engine.tracks.engineering import EngineeringTrack, EngineeringStatus

engine = FeatureEngine()

# If slug provided, use it; otherwise try to detect from cwd
if slug:
    feature_path = engine._find_feature(slug)
    if not feature_path:
        print(f"Error: Feature '{slug}' not found")
        exit(1)
else:
    # Try current directory
    cwd = Path.cwd()
    state_file = cwd / "feature-state.yaml"
    if state_file.exists():
        feature_path = cwd
        state = FeatureState.load(cwd)
        slug = state.slug
    else:
        print("Error: Not in a feature directory. Provide a feature slug.")
        exit(1)

# Load state and specialized tracks
state = FeatureState.load(feature_path)
bc_track = BusinessCaseTrack(feature_path)
eng_track = EngineeringTrack(feature_path)
```

### Step 2: Define Quality Gates

Define quality gate criteria per PRD Section F.2.

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum

class GateStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_STARTED = "not_started"
    INCOMPLETE = "incomplete"

@dataclass
class GateResult:
    """Result of a single gate check."""
    name: str
    status: GateStatus
    message: str
    is_blocking: bool = False
    action: Optional[str] = None  # Suggested action to resolve
    evidence: Optional[str] = None  # What passed/failed

@dataclass
class PhaseValidation:
    """Validation results for a phase."""
    phase: str
    status: GateStatus
    gates: List[GateResult] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(1 for g in self.gates if g.status == GateStatus.PASS)

    @property
    def total_count(self) -> int:
        return len(self.gates)
```

### Step 3: Validate Context Phase

Check context document gates per PRD F.2 quality_gates.context_doc_v1/v2/v3.

```python
def validate_context_phase(state: FeatureState, feature_path: Path) -> PhaseValidation:
    """Validate context document phase gates."""
    track = state.tracks.get("context")
    gates = []
    blockers = []
    warnings = []

    # If not started, return early
    if track.status == TrackStatus.NOT_STARTED:
        return PhaseValidation(
            phase="context",
            status=GateStatus.NOT_STARTED,
            gates=[],
            blockers=["Context track not started"],
        )

    # Check for context document existence
    context_docs_folder = feature_path / "context-docs"
    has_any_version = False
    current_version = track.current_version or 0

    for v in range(1, 4):  # v1, v2, v3
        version_file = context_docs_folder / f"v{v}-draft.md"
        if version_file.exists():
            has_any_version = True

    # Gate: Document exists
    if has_any_version or (feature_path / f"{state.slug}-context.md").exists():
        gates.append(GateResult(
            name="context_document_exists",
            status=GateStatus.PASS,
            message="Context document exists",
            evidence=f"Version {current_version} available"
        ))
    else:
        gates.append(GateResult(
            name="context_document_exists",
            status=GateStatus.FAIL,
            message="Context document not found",
            is_blocking=True,
            action="Run /create-context-doc to generate context document"
        ))
        blockers.append("Context document required")

    # Check for minimum sections in context file
    context_file = feature_path / state.context_file
    if context_file.exists():
        content = context_file.read_text()

        # Gate: Problem statement present
        has_problem = "## Description" in content or "## Problem" in content
        gates.append(GateResult(
            name="problem_statement_present",
            status=GateStatus.PASS if has_problem else GateStatus.FAIL,
            message="Problem statement present" if has_problem else "Problem statement missing",
            is_blocking=True,
            action=None if has_problem else "Add problem statement to context document"
        ))
        if not has_problem:
            blockers.append("Problem statement required")

        # Gate: Stakeholders defined
        has_stakeholders = "## Stakeholders" in content
        gates.append(GateResult(
            name="stakeholders_defined",
            status=GateStatus.PASS if has_stakeholders else GateStatus.INCOMPLETE,
            message="Stakeholders section present" if has_stakeholders else "Stakeholders section missing",
            action=None if has_stakeholders else "Add stakeholders to context document"
        ))

    # Check for challenge file (orthogonal challenge run)
    challenge_files = list(context_docs_folder.glob("v*-challenge.md")) if context_docs_folder.exists() else []
    has_challenge = len(challenge_files) > 0

    if current_version >= 2:
        # v2+ requires orthogonal challenge
        gates.append(GateResult(
            name="orthogonal_challenge_run",
            status=GateStatus.PASS if has_challenge else GateStatus.FAIL,
            message="Orthogonal challenge completed" if has_challenge else "Orthogonal challenge not run",
            is_blocking=current_version >= 2,
            action=None if has_challenge else "Run orthogonal challenge on context document"
        ))
        if not has_challenge and current_version >= 2:
            blockers.append("Orthogonal challenge required for v2+")

    # Determine overall phase status
    if track.status == TrackStatus.COMPLETE:
        phase_status = GateStatus.PASS
    elif any(g.status == GateStatus.FAIL and g.is_blocking for g in gates):
        phase_status = GateStatus.FAIL
    elif track.status in (TrackStatus.IN_PROGRESS, TrackStatus.PENDING_INPUT):
        phase_status = GateStatus.INCOMPLETE
    else:
        phase_status = GateStatus.INCOMPLETE

    return PhaseValidation(
        phase="context",
        status=phase_status,
        gates=gates,
        blockers=blockers,
        warnings=warnings
    )

context_validation = validate_context_phase(state, feature_path)
```

### Step 4: Validate Design Phase

Check design track gates per PRD F.2 quality_gates.design_track.

```python
def validate_design_phase(state: FeatureState, feature_path: Path) -> PhaseValidation:
    """Validate design track phase gates."""
    track = state.tracks.get("design")
    gates = []
    blockers = []
    warnings = []

    # If not started, return early
    if track.status == TrackStatus.NOT_STARTED:
        return PhaseValidation(
            phase="design",
            status=GateStatus.NOT_STARTED,
            gates=[],
            blockers=[],
        )

    # Gate: Design spec approved
    design_spec_file = feature_path / "context-docs" / "design-spec.md"
    has_design_spec = design_spec_file.exists()
    gates.append(GateResult(
        name="design_spec_present",
        status=GateStatus.PASS if has_design_spec else GateStatus.INCOMPLETE,
        message="Design spec document exists" if has_design_spec else "Design spec not created",
        is_blocking=True,
        action=None if has_design_spec else "Create design specification document"
    ))
    if not has_design_spec:
        blockers.append("Design spec required")

    # Gate: Wireframes provided
    wireframes_url = state.artifacts.get("wireframes_url")
    gates.append(GateResult(
        name="wireframes_provided",
        status=GateStatus.PASS if wireframes_url else GateStatus.INCOMPLETE,
        message=f"Wireframes attached: {wireframes_url[:50]}..." if wireframes_url else "Wireframes not attached",
        is_blocking=False,
        action=None if wireframes_url else "Run /attach-artifact wireframes <url>",
        evidence=wireframes_url
    ))
    if not wireframes_url:
        warnings.append("Wireframes recommended before decision gate")

    # Gate: Figma provided (required for decision gate)
    figma_url = state.artifacts.get("figma")
    gates.append(GateResult(
        name="figma_provided",
        status=GateStatus.PASS if figma_url else GateStatus.INCOMPLETE,
        message=f"Figma attached: {figma_url[:50]}..." if figma_url else "Figma design not attached",
        is_blocking=True,
        action=None if figma_url else "Run /attach-artifact figma <url>",
        evidence=figma_url
    ))
    if not figma_url:
        blockers.append("Figma design URL required")

    # Determine overall phase status
    if track.status == TrackStatus.COMPLETE:
        phase_status = GateStatus.PASS
    elif any(g.status == GateStatus.FAIL and g.is_blocking for g in gates):
        phase_status = GateStatus.FAIL
    elif all(g.status == GateStatus.PASS for g in gates):
        phase_status = GateStatus.PASS
    else:
        phase_status = GateStatus.INCOMPLETE

    return PhaseValidation(
        phase="design",
        status=phase_status,
        gates=gates,
        blockers=blockers,
        warnings=warnings
    )

design_validation = validate_design_phase(state, feature_path)
```

### Step 5: Validate Business Case Phase

Check business case track gates per PRD F.2 quality_gates.business_case.

```python
def validate_business_case_phase(
    state: FeatureState,
    feature_path: Path,
    bc_track: BusinessCaseTrack
) -> PhaseValidation:
    """Validate business case phase gates."""
    track = state.tracks.get("business_case")
    gates = []
    blockers = []
    warnings = []

    # If not started, return early
    if bc_track.status == BCStatus.NOT_STARTED:
        return PhaseValidation(
            phase="business_case",
            status=GateStatus.NOT_STARTED,
            gates=[],
            blockers=[],
        )

    # Gate: Baseline metrics provided
    has_baseline = bool(bc_track.assumptions.baseline_metrics)
    gates.append(GateResult(
        name="baseline_metrics_provided",
        status=GateStatus.PASS if has_baseline else GateStatus.INCOMPLETE,
        message="Baseline metrics defined" if has_baseline else "Baseline metrics not provided",
        is_blocking=True,
        action=None if has_baseline else "Provide baseline metrics for business case",
        evidence=str(bc_track.assumptions.baseline_metrics) if has_baseline else None
    ))
    if not has_baseline:
        blockers.append("Baseline metrics required")

    # Gate: Impact assumptions documented
    has_assumptions = bool(bc_track.assumptions.impact_assumptions)
    gates.append(GateResult(
        name="assumptions_documented",
        status=GateStatus.PASS if has_assumptions else GateStatus.INCOMPLETE,
        message="Impact assumptions documented" if has_assumptions else "Impact assumptions not documented",
        is_blocking=True,
        action=None if has_assumptions else "Document impact assumptions",
        evidence=str(bc_track.assumptions.impact_assumptions) if has_assumptions else None
    ))
    if not has_assumptions:
        blockers.append("Impact assumptions required")

    # Gate: ROI analysis (warning if not positive in conservative case)
    has_roi = bc_track.assumptions.roi_analysis is not None
    if has_roi:
        gates.append(GateResult(
            name="roi_positive_conservative",
            status=GateStatus.PASS,
            message="ROI analysis complete",
            evidence=str(bc_track.assumptions.roi_analysis)
        ))
    else:
        gates.append(GateResult(
            name="roi_positive_conservative",
            status=GateStatus.INCOMPLETE,
            message="ROI analysis not performed",
            is_blocking=False,
            action="Consider running ROI sensitivity analysis"
        ))
        warnings.append("ROI analysis recommended")

    # Gate: Stakeholder approval (blocking)
    is_approved = bc_track.is_approved
    approval_count = len(bc_track.approvals)
    pending_count = len(bc_track.pending_approvers)

    if is_approved:
        approvers = ", ".join(a.approver for a in bc_track.approvals if a.approved)
        gates.append(GateResult(
            name="stakeholder_approval",
            status=GateStatus.PASS,
            message=f"Approved by: {approvers}",
            evidence=f"{approval_count} approval(s)"
        ))
    elif bc_track.is_rejected:
        gates.append(GateResult(
            name="stakeholder_approval",
            status=GateStatus.FAIL,
            message="Business case was rejected",
            is_blocking=True,
            action="Address rejection feedback and resubmit"
        ))
        blockers.append("Business case rejected - revision needed")
    elif bc_track.status == BCStatus.PENDING_APPROVAL:
        gates.append(GateResult(
            name="stakeholder_approval",
            status=GateStatus.INCOMPLETE,
            message=f"Awaiting approval from: {', '.join(bc_track.pending_approvers)}",
            is_blocking=True,
            action=f"Follow up with: {', '.join(bc_track.pending_approvers)}"
        ))
        blockers.append("Stakeholder approval pending")
    else:
        gates.append(GateResult(
            name="stakeholder_approval",
            status=GateStatus.INCOMPLETE,
            message="Not submitted for approval",
            is_blocking=True,
            action="Submit business case for approval"
        ))
        blockers.append("Business case approval required")

    # Gate: BC document generated
    bc_folder = feature_path / "business-case"
    bc_files = list(bc_folder.glob("bc-v*.md")) if bc_folder.exists() else []
    has_bc_doc = len(bc_files) > 0
    gates.append(GateResult(
        name="bc_document_generated",
        status=GateStatus.PASS if has_bc_doc else GateStatus.INCOMPLETE,
        message=f"BC document exists (v{bc_track.current_version})" if has_bc_doc else "BC document not generated",
        is_blocking=True,
        action=None if has_bc_doc else "Generate business case document"
    ))
    if not has_bc_doc:
        blockers.append("BC document required")

    # Determine overall phase status
    if bc_track.status == BCStatus.APPROVED:
        phase_status = GateStatus.PASS
    elif bc_track.status == BCStatus.REJECTED:
        phase_status = GateStatus.FAIL
    elif any(g.status == GateStatus.FAIL and g.is_blocking for g in gates):
        phase_status = GateStatus.FAIL
    else:
        phase_status = GateStatus.INCOMPLETE

    return PhaseValidation(
        phase="business_case",
        status=phase_status,
        gates=gates,
        blockers=blockers,
        warnings=warnings
    )

bc_validation = validate_business_case_phase(state, feature_path, bc_track)
```

### Step 6: Validate Engineering Phase

Check engineering track gates per PRD F.2 quality_gates.engineering_spec.

```python
def validate_engineering_phase(
    state: FeatureState,
    feature_path: Path,
    eng_track: EngineeringTrack
) -> PhaseValidation:
    """Validate engineering phase gates."""
    track = state.tracks.get("engineering")
    gates = []
    blockers = []
    warnings = []

    # If not started, return early
    if eng_track.status == EngineeringStatus.NOT_STARTED:
        return PhaseValidation(
            phase="engineering",
            status=GateStatus.NOT_STARTED,
            gates=[],
            blockers=[],
        )

    # Gate: Engineering spec/components identified
    eng_folder = feature_path / "engineering"
    spec_file = eng_folder / "spec.md"
    has_spec = spec_file.exists() if eng_folder.exists() else False
    gates.append(GateResult(
        name="components_identified",
        status=GateStatus.PASS if has_spec else GateStatus.INCOMPLETE,
        message="Engineering spec created" if has_spec else "Engineering spec not created",
        is_blocking=False,
        action=None if has_spec else "Create engineering specification"
    ))

    # Gate: ADRs decided (blocking if any proposed ADRs exist)
    adr_count = len(eng_track.adrs)
    active_adrs = len(eng_track.active_adrs)
    proposed_adrs = [a for a in eng_track.adrs if a.status.value == "proposed"]

    if adr_count > 0:
        if proposed_adrs:
            gates.append(GateResult(
                name="adrs_decided",
                status=GateStatus.INCOMPLETE,
                message=f"{len(proposed_adrs)} ADR(s) pending decision",
                is_blocking=True,
                action="Accept or reject pending ADRs",
                evidence=f"Proposed: {', '.join(a.title[:30] for a in proposed_adrs)}"
            ))
            blockers.append(f"{len(proposed_adrs)} ADR(s) need decision")
        else:
            gates.append(GateResult(
                name="adrs_decided",
                status=GateStatus.PASS,
                message=f"{active_adrs} ADR(s) accepted",
                evidence=f"ADRs: {', '.join(a.title[:30] for a in eng_track.active_adrs)}"
            ))
    else:
        gates.append(GateResult(
            name="adrs_decided",
            status=GateStatus.INCOMPLETE,
            message="No ADRs created",
            is_blocking=False,
            action="Consider creating ADRs for key architectural decisions"
        ))
        warnings.append("ADRs recommended for technical decisions")

    # Gate: Engineering estimate provided
    has_estimate = eng_track.has_estimate
    gates.append(GateResult(
        name="estimate_provided",
        status=GateStatus.PASS if has_estimate else GateStatus.INCOMPLETE,
        message=f"Estimate: {eng_track.estimate.overall}" if has_estimate else "Engineering estimate not provided",
        is_blocking=True,
        action=None if has_estimate else "Provide engineering effort estimate",
        evidence=f"Breakdown: {eng_track.estimate.breakdown}" if has_estimate and eng_track.estimate.breakdown else None
    ))
    if not has_estimate:
        blockers.append("Engineering estimate required")

    # Gate: Dependencies listed (warning if blocking dependencies exist)
    dep_count = len(eng_track.dependencies)
    blocking_deps = eng_track.blocking_dependencies
    if blocking_deps:
        gates.append(GateResult(
            name="dependencies_listed",
            status=GateStatus.INCOMPLETE,
            message=f"{len(blocking_deps)} blocking dependency(ies)",
            is_blocking=True,
            action="Resolve blocking dependencies",
            evidence=f"Blocking: {', '.join(d.name for d in blocking_deps)}"
        ))
        blockers.append(f"{len(blocking_deps)} blocking dependencies")
    elif dep_count > 0:
        gates.append(GateResult(
            name="dependencies_listed",
            status=GateStatus.PASS,
            message=f"{dep_count} dependencies tracked, none blocking"
        ))
    else:
        gates.append(GateResult(
            name="dependencies_listed",
            status=GateStatus.PASS,
            message="No dependencies identified"
        ))

    # Gate: High-impact risks mitigated
    pending_risks = eng_track.pending_risks
    high_impact_unmitigated = [r for r in pending_risks if r.impact == "high" and not r.mitigation]
    if high_impact_unmitigated:
        gates.append(GateResult(
            name="risks_mitigated",
            status=GateStatus.INCOMPLETE,
            message=f"{len(high_impact_unmitigated)} high-impact risk(s) unmitigated",
            is_blocking=True,
            action="Add mitigation plans for high-impact risks",
            evidence=f"Risks: {', '.join(r.risk[:30] for r in high_impact_unmitigated)}"
        ))
        blockers.append("High-impact risks need mitigation plans")
    elif pending_risks:
        gates.append(GateResult(
            name="risks_mitigated",
            status=GateStatus.PASS,
            message=f"{len(pending_risks)} pending risk(s), all have mitigations"
        ))
    else:
        gates.append(GateResult(
            name="risks_mitigated",
            status=GateStatus.PASS,
            message="No pending risks"
        ))

    # Determine overall phase status
    if eng_track.status == EngineeringStatus.COMPLETE:
        phase_status = GateStatus.PASS
    elif any(g.status == GateStatus.FAIL and g.is_blocking for g in gates):
        phase_status = GateStatus.FAIL
    elif eng_track.status == EngineeringStatus.BLOCKED:
        phase_status = GateStatus.FAIL
    else:
        # Check if all non-blocking gates pass
        blocking_gates = [g for g in gates if g.is_blocking]
        if all(g.status == GateStatus.PASS for g in blocking_gates):
            phase_status = GateStatus.PASS
        else:
            phase_status = GateStatus.INCOMPLETE

    return PhaseValidation(
        phase="engineering",
        status=phase_status,
        gates=gates,
        blockers=blockers,
        warnings=warnings
    )

eng_validation = validate_engineering_phase(state, feature_path, eng_track)
```

### Step 7: Validate Decision Gate Readiness

Check if all tracks are ready for decision gate per PRD F.2 quality_gates.decision_gate.

```python
def validate_decision_gate(
    state: FeatureState,
    context_val: PhaseValidation,
    design_val: PhaseValidation,
    bc_val: PhaseValidation,
    eng_val: PhaseValidation
) -> PhaseValidation:
    """Validate decision gate readiness."""
    gates = []
    blockers = []
    warnings = []

    # Gate: Context document complete
    ctx_complete = context_val.status == GateStatus.PASS
    gates.append(GateResult(
        name="context_doc_complete",
        status=GateStatus.PASS if ctx_complete else GateStatus.FAIL,
        message="Context document complete" if ctx_complete else "Context document incomplete",
        is_blocking=True,
        action=None if ctx_complete else "Complete context document requirements"
    ))
    if not ctx_complete:
        blockers.append("Context document must be complete")

    # Gate: Business case approved
    bc_approved = bc_val.status == GateStatus.PASS
    gates.append(GateResult(
        name="business_case_approved",
        status=GateStatus.PASS if bc_approved else GateStatus.FAIL,
        message="Business case approved" if bc_approved else "Business case not approved",
        is_blocking=True,
        action=None if bc_approved else "Obtain business case approval"
    ))
    if not bc_approved:
        blockers.append("Business case approval required")

    # Gate: Design track complete or parallel (can proceed if in progress)
    design_ok = design_val.status in (GateStatus.PASS, GateStatus.NOT_STARTED)
    # Design can be parallel, but Figma is required
    figma_provided = any(g.name == "figma_provided" and g.status == GateStatus.PASS for g in design_val.gates)
    design_gate_status = GateStatus.PASS if design_ok or figma_provided else GateStatus.INCOMPLETE

    gates.append(GateResult(
        name="design_track_complete_or_parallel",
        status=design_gate_status,
        message="Design track acceptable" if design_gate_status == GateStatus.PASS else "Design artifacts missing",
        is_blocking=True,
        action=None if design_gate_status == GateStatus.PASS else "Attach required design artifacts"
    ))
    if design_gate_status != GateStatus.PASS:
        blockers.append("Design artifacts required")

    # Gate: Engineering spec complete
    eng_complete = eng_val.status == GateStatus.PASS
    gates.append(GateResult(
        name="engineering_spec_complete",
        status=GateStatus.PASS if eng_complete else GateStatus.INCOMPLETE,
        message="Engineering spec complete" if eng_complete else "Engineering spec incomplete",
        is_blocking=True,
        action=None if eng_complete else "Complete engineering specification requirements"
    ))
    if not eng_complete:
        blockers.append("Engineering specification required")

    # Gate: No blocking risks
    has_blocking_risks = any("high-impact risk" in b.lower() for b in eng_val.blockers)
    gates.append(GateResult(
        name="no_blocking_risks",
        status=GateStatus.FAIL if has_blocking_risks else GateStatus.PASS,
        message="No blocking risks" if not has_blocking_risks else "High-impact risks need mitigation",
        is_blocking=True,
        action=None if not has_blocking_risks else "Mitigate high-impact risks"
    ))
    if has_blocking_risks:
        blockers.append("High-impact risks must be mitigated")

    # Determine overall gate readiness
    if all(g.status == GateStatus.PASS for g in gates):
        phase_status = GateStatus.PASS
    else:
        phase_status = GateStatus.FAIL

    return PhaseValidation(
        phase="decision_gate",
        status=phase_status,
        gates=gates,
        blockers=blockers,
        warnings=warnings
    )

decision_gate_validation = validate_decision_gate(
    state, context_validation, design_validation, bc_validation, eng_validation
)
```

### Step 8: Display Validation Results

Format and display comprehensive validation report.

```python
def status_indicator(status: GateStatus) -> str:
    """Get display indicator for status."""
    indicators = {
        GateStatus.PASS: "[PASS]",
        GateStatus.FAIL: "[FAIL]",
        GateStatus.INCOMPLETE: "[INCOMPLETE]",
        GateStatus.NOT_STARTED: "[NOT STARTED]",
    }
    return indicators.get(status, "[?]")

def phase_emoji(status: GateStatus) -> str:
    """Get status marker for phase header."""
    if status == GateStatus.PASS:
        return "[DONE]"
    elif status == GateStatus.FAIL:
        return "[BLOCKED]"
    elif status == GateStatus.INCOMPLETE:
        return "[IN PROGRESS]"
    else:
        return "[TODO]"

# Collect all validations
validations = [context_validation, design_validation, bc_validation, eng_validation]

# If specific phase requested, filter
if phase_filter:
    phase_map = {
        "context": context_validation,
        "design": design_validation,
        "business_case": bc_validation,
        "engineering": eng_validation,
        "decision_gate": decision_gate_validation,
    }
    if phase_filter in phase_map:
        validations = [phase_map[phase_filter]]
        if phase_filter == "decision_gate":
            # For decision gate, show the decision gate validation
            pass
    else:
        print(f"Unknown phase: {phase_filter}")
        print("Valid phases: context, design, business_case, engineering, decision_gate")
        exit(1)

# Calculate totals
total_blockers = sum(len(v.blockers) for v in validations)
total_warnings = sum(len(v.warnings) for v in validations)

# Display header
print(f"""
{'=' * 65}
 VALIDATION RESULTS: {state.title}
{'=' * 65}

 Feature: {state.slug}
 Product: {state.product_id}
 Current Phase: {state.current_phase.value}

{'=' * 65}
""")

# Display each phase validation
for validation in validations:
    print(f"""
 {validation.phase.replace('_', ' ').title():40} {phase_emoji(validation.status)}
{'-' * 65}""")

    if validation.status == GateStatus.NOT_STARTED:
        print("   Track not started - run appropriate start command")
        continue

    for gate in validation.gates:
        status_str = status_indicator(gate.status)
        print(f"   {status_str:14} {gate.message}")

        if verbose and gate.evidence:
            print(f"                   Evidence: {gate.evidence}")

        if gate.status != GateStatus.PASS and gate.action:
            print(f"                   -> {gate.action}")

    if validation.blockers:
        print()
        print(f"   Blockers ({len(validation.blockers)}):")
        for blocker in validation.blockers:
            print(f"     [!] {blocker}")

    if validation.warnings:
        print()
        print(f"   Warnings ({len(validation.warnings)}):")
        for warning in validation.warnings:
            print(f"     [*] {warning}")

# Decision gate summary (if not filtering to specific phase)
if not phase_filter or phase_filter == "decision_gate":
    print(f"""
{'=' * 65}
 DECISION GATE READINESS
{'=' * 65}
""")
    for gate in decision_gate_validation.gates:
        status_str = status_indicator(gate.status)
        print(f"   {status_str:14} {gate.message}")

    ready = decision_gate_validation.status == GateStatus.PASS
    print(f"""
{'=' * 65}
 SUMMARY
{'=' * 65}

 Total Blockers: {total_blockers}
 Total Warnings: {total_warnings}

 Ready for Decision Gate: {"YES" if ready else f"NO ({total_blockers} blocker(s))"}
""")

    if not ready and decision_gate_validation.blockers:
        print(" To proceed to decision gate, resolve:")
        for i, blocker in enumerate(decision_gate_validation.blockers, 1):
            print(f"   {i}. {blocker}")

print()
```

## Error Handling

| Error | Resolution |
|-------|------------|
| Feature not found | Provide correct slug or navigate to feature directory |
| No feature-state.yaml | Initialize feature with /start-feature first |
| Track data missing | Some tracks may not be initialized yet |
| Invalid phase filter | Use valid phase name: context, design, business_case, engineering, decision_gate |

## Integration Points

- **FeatureEngine**: `common/tools/context_engine/feature_engine.py`
- **FeatureState**: `common/tools/context_engine/feature_state.py`
- **BusinessCaseTrack**: `common/tools/context_engine/tracks/business_case.py`
- **EngineeringTrack**: `common/tools/context_engine/tracks/engineering.py`

## Quality Gate Reference (PRD F.2)

### Context Document Gates
- `problem_statement_present`: Problem statement exists
- `success_metrics_defined`: Success metrics are defined
- `scope_defined`: Scope is defined
- `orthogonal_challenge_run`: Challenge has been run (v2+)
- `challenge_score >= threshold`: 60 (v2), 75 (v3)

### Business Case Gates
- `baseline_metrics_provided`: Current state metrics exist
- `assumptions_documented`: Impact assumptions documented
- `roi_positive_conservative`: ROI positive (warning if not)
- `stakeholder_approval`: Required approvals obtained (blocking)

### Design Track Gates
- `design_spec_approved`: Design spec exists
- `wireframes_provided`: Wireframes attached
- `figma_provided`: Figma design attached

### Engineering Spec Gates
- `components_identified`: Components/spec documented
- `adrs_decided`: No proposed ADRs (all accepted/rejected)
- `dependencies_listed`: Dependencies tracked
- `estimate_provided`: Engineering estimate recorded

### Decision Gate Gates
- `context_doc_complete`: Context track complete
- `business_case_approved`: BC track approved
- `design_track_complete_or_parallel`: Design acceptable
- `engineering_spec_complete`: Engineering track complete
- `no_blocking_risks`: No high-impact unmitigated risks

## Next Steps After Validation

Based on the validation results, consider:
- **PASS**: Proceed to /decision-gate command
- **BLOCKERS**: Address blocking issues listed in output
- **WARNINGS**: Consider addressing before proceeding (optional)
- **NOT_STARTED tracks**: Start the track with appropriate command

## Execute

Find the feature, load all track data, run validation checks against quality gates for each phase, then display comprehensive validation report with blockers and next steps.
