# Decision Gate

Final review command for the Context Creation Engine that validates feature readiness and records go/no-go decisions.

## Overview

This command performs the decision gate review for a feature including:
1. Running all validation hooks to ensure feature is ready
2. Checking all quality gates pass across tracks
3. Detecting any blockers that would prevent approval
4. Presenting a clear GO/NO-GO recommendation with evidence
5. Recording the decision in feature-state.yaml
6. If approved, transitioning feature to output generation phase

## Arguments

- `<slug>` - Feature slug (optional, uses current directory if not specified)
- `--approve` - Directly approve the feature (skip interactive decision)
- `--reject` - Directly reject the feature with reason
- `--reason "<text>"` - Reason for approve/reject decision
- `--verbose` - Show detailed validation results

**Examples:**
```
/decision-gate
/decision-gate mk-feature-recovery
/decision-gate mk-feature-recovery --approve --reason "All tracks complete, BC approved"
/decision-gate mk-feature-recovery --reject --reason "Missing engineering estimate"
/decision-gate --verbose
```

## Instructions

### Step 1: Find and Load the Feature

Locate the feature folder and load state including all specialized tracks.

```python
import sys
sys.path.insert(0, "$PM_OS_COMMON/tools")
from pathlib import Path
from datetime import datetime
from context_engine import FeatureEngine
from context_engine.feature_state import FeatureState, TrackStatus, FeaturePhase
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

### Step 2: Run Validation Hooks

Use ValidationHookRunner to run all continuous validation hooks.

```python
from context_engine.validation_hooks import (
    ValidationHookRunner,
    ValidationReport,
    ValidationStatus,
    HookSeverity,
    format_validation_results,
)

# Run all validation hooks
runner = ValidationHookRunner(feature_path)
validation_report = runner.generate_report(force=True)  # Force run all hooks

# Categorize validation results
critical_failures = [r for r in validation_report.results
                     if r.is_critical]
high_failures = [r for r in validation_report.results
                 if r.failed and r.severity == HookSeverity.HIGH]
medium_failures = [r for r in validation_report.results
                   if r.failed and r.severity == HookSeverity.MEDIUM]
warnings = [r for r in validation_report.results
            if r.status == ValidationStatus.WARN]
```

### Step 3: Validate Quality Gates

Check all quality gates for each track and the decision gate itself.

```python
from context_engine.quality_gates import (
    QualityGates,
    GateStatus,
    GateLevel,
    validate_decision_gate_readiness,
    validate_context_score,
    validate_business_case_approval,
    validate_design_artifacts,
    validate_engineering_readiness,
    PhaseGateResult,
)

gates_config = QualityGates()

# Validate context track
context_track = state.tracks.get("context")
context_passed = context_track.status == TrackStatus.COMPLETE

# Validate business case track
bc_approved = bc_track.is_approved
bc_rejected = bc_track.is_rejected
approvals = [{"approver": a.approver, "approved": a.approved}
             for a in bc_track.approvals]
bc_gate_result = validate_business_case_approval(
    approvals=approvals,
    gates=gates_config
)

# Validate design artifacts
design_artifacts = {
    "figma": state.artifacts.get("figma"),
    "wireframes": state.artifacts.get("wireframes_url"),
}
design_gate_results = validate_design_artifacts(design_artifacts, gates_config)
design_acceptable = all(g.passed or not g.is_blocking for g in design_gate_results)

# Validate engineering readiness
has_estimate = eng_track.has_estimate
estimate_value = eng_track.estimate.overall if eng_track.estimate else None
proposed_adrs = [a for a in eng_track.adrs if a.status.value == "proposed"]
blocking_deps = eng_track.blocking_dependencies
high_risk_unmitigated = [r for r in eng_track.pending_risks
                         if r.impact == "high" and not r.mitigation]

eng_gate_results = validate_engineering_readiness(
    has_estimate=has_estimate,
    estimate_value=estimate_value,
    adr_count=len(eng_track.adrs),
    proposed_adr_count=len(proposed_adrs),
    blocking_dep_count=len(blocking_deps),
    high_risk_unmitigated_count=len(high_risk_unmitigated),
    gates=gates_config
)
engineering_complete = all(g.passed or not g.is_blocking for g in eng_gate_results)

# Check for blocking risks
has_blocking_risks = len(high_risk_unmitigated) > 0

# Overall decision gate readiness
decision_gate_result = validate_decision_gate_readiness(
    context_passed=context_passed,
    business_case_approved=bc_approved,
    design_acceptable=design_acceptable,
    engineering_complete=engineering_complete,
    has_blocking_risks=has_blocking_risks,
    gates=gates_config
)
```

### Step 4: Detect Blockers

Use BlockerDetector to identify any remaining blockers.

```python
from context_engine.blocker_detection import (
    BlockerDetector,
    BlockerReport,
    BlockerSeverity,
    BlockerType,
    format_blocker_list,
)

detector = BlockerDetector(feature_path, gates=gates_config)
blocker_report = detector.generate_report()

# Categorize blockers
critical_blockers = blocker_report.get_by_severity(BlockerSeverity.CRITICAL)
high_blockers = blocker_report.get_by_severity(BlockerSeverity.HIGH)
medium_blockers = blocker_report.get_by_severity(BlockerSeverity.MEDIUM)
advisory_blockers = blocker_report.get_by_severity(BlockerSeverity.LOW)
```

### Step 5: Determine GO/NO-GO Recommendation

Generate recommendation based on validation results, quality gates, and blockers.

```python
def determine_recommendation(
    validation_report: ValidationReport,
    decision_gate_result: PhaseGateResult,
    blocker_report: BlockerReport
) -> tuple[str, str, list]:
    """
    Determine GO/NO-GO recommendation with reasoning.

    Returns:
        Tuple of (recommendation, summary, evidence_list)
    """
    evidence = []

    # Check for critical issues first
    if validation_report.has_critical_failures:
        return (
            "NO-GO",
            "Critical validation failures detected",
            [f"[CRITICAL] {r.message}" for r in validation_report.results if r.is_critical]
        )

    if blocker_report.has_critical:
        return (
            "NO-GO",
            "Critical blockers present",
            [f"[CRITICAL] {b.description}" for b in blocker_report.blockers if b.severity == BlockerSeverity.CRITICAL]
        )

    # Check decision gate status
    if decision_gate_result.status != GateStatus.PASS:
        failed_gates = [g for g in decision_gate_result.gates if not g.passed]
        return (
            "NO-GO",
            f"{len(failed_gates)} decision gate requirement(s) not met",
            [f"[{g.status.value.upper()}] {g.message}" for g in failed_gates]
        )

    # Check for high severity blockers
    if blocker_report.high_count > 0:
        return (
            "NO-GO",
            f"{blocker_report.high_count} high-severity blocker(s) present",
            [f"[HIGH] {b.description}" for b in blocker_report.get_by_severity(BlockerSeverity.HIGH)]
        )

    # Check for medium blockers (warning but can proceed)
    if blocker_report.medium_count > 0:
        evidence.append(f"[!] {blocker_report.medium_count} medium-severity issue(s) - recommend addressing")

    # All gates passed
    evidence.append("[PASS] Context document complete")
    evidence.append("[PASS] Business case approved")
    evidence.append("[PASS] Design artifacts attached")
    evidence.append("[PASS] Engineering spec complete")
    evidence.append("[PASS] No blocking risks")

    return (
        "GO",
        "All decision gate requirements met",
        evidence
    )

recommendation, summary, evidence = determine_recommendation(
    validation_report,
    decision_gate_result,
    blocker_report
)

is_ready = recommendation == "GO"
```

### Step 6: Handle Direct Decision Flags

If --approve or --reject flags provided, process the direct decision.

```python
# Check for direct decision flags
direct_decision = None
decision_reason = reason if reason else None

if approve_flag:
    if not is_ready:
        print("WARNING: Feature does not meet all decision gate requirements.")
        print("Proceeding with approval will override the following issues:")
        for item in evidence:
            if item.startswith("[") and not item.startswith("[PASS"):
                print(f"  {item}")
        print()
        # In a direct flag scenario, we allow override
    direct_decision = "approved"
    decision_reason = decision_reason or "Manually approved via --approve flag"
elif reject_flag:
    direct_decision = "rejected"
    decision_reason = decision_reason or "Manually rejected via --reject flag"
```

### Step 7: Display Decision Gate Summary

Format and display comprehensive decision gate report.

```python
def status_indicator(status) -> str:
    """Get display indicator for status."""
    indicators = {
        "pass": "[PASS]",
        "fail": "[FAIL]",
        "incomplete": "[INCOMPLETE]",
        "not_started": "[NOT STARTED]",
        "warning": "[WARN]",
    }
    if hasattr(status, 'value'):
        return indicators.get(status.value, "[?]")
    return indicators.get(str(status).lower(), "[?]")

# Display header
print(f"""
{'=' * 70}
 DECISION GATE REVIEW: {state.title}
{'=' * 70}

 Feature: {state.slug}
 Product: {state.product_id}
 Current Phase: {state.current_phase.value}

{'=' * 70}
 VALIDATION HOOKS ({validation_report.passed_count}/{validation_report.total_count} passed)
{'=' * 70}
""")

# Show validation results
if validation_report.has_critical_failures:
    print(" [CRITICAL FAILURES]")
    for r in validation_report.results:
        if r.is_critical:
            print(f"   [!] {r.message}")
            if r.remediation:
                print(f"       Fix: {r.remediation}")
    print()

if verbose:
    for r in validation_report.results:
        if not r.is_critical:
            print(f"   {status_indicator(r.status):14} {r.message}")

# Display quality gates
print(f"""
{'=' * 70}
 QUALITY GATES
{'=' * 70}

 Context Track:
""")
print(f"   {status_indicator('pass' if context_passed else 'fail'):14} Context document {'complete' if context_passed else 'incomplete'}")

print(f"""
 Business Case Track:
""")
print(f"   {status_indicator(bc_gate_result.status):14} {bc_gate_result.message}")

print(f"""
 Design Track:
""")
for gate in design_gate_results:
    print(f"   {status_indicator(gate.status):14} {gate.message}")

print(f"""
 Engineering Track:
""")
for gate in eng_gate_results:
    print(f"   {status_indicator(gate.status):14} {gate.message}")

# Display decision gate summary
print(f"""
{'=' * 70}
 DECISION GATE REQUIREMENTS
{'=' * 70}
""")
for gate in decision_gate_result.gates:
    print(f"   {status_indicator(gate.status):14} {gate.message}")

# Display blockers
print(f"""
{'=' * 70}
 BLOCKERS ({blocker_report.total_count} total)
{'=' * 70}
""")
if blocker_report.total_count > 0:
    if blocker_report.critical_count > 0:
        print(f"   [CRITICAL] {blocker_report.critical_count}")
        for b in critical_blockers:
            print(f"     [!] {b.description}")
    if blocker_report.high_count > 0:
        print(f"   [HIGH] {blocker_report.high_count}")
        for b in high_blockers:
            print(f"     [!] {b.description}")
    if blocker_report.medium_count > 0:
        print(f"   [MEDIUM] {blocker_report.medium_count}")
        for b in medium_blockers:
            print(f"     [-] {b.description}")
    if blocker_report.low_count > 0 and verbose:
        print(f"   [LOW/ADVISORY] {blocker_report.low_count}")
        for b in advisory_blockers:
            print(f"     [*] {b.description}")
else:
    print("   No blockers detected!")

# Display recommendation
print(f"""
{'=' * 70}
 RECOMMENDATION
{'=' * 70}

   Decision: {recommendation}
   Summary: {summary}

 Evidence:
""")
for item in evidence:
    print(f"   {item}")

print()
```

### Step 8: Record Decision

Record the decision in feature-state.yaml and transition phase if approved.

```python
def record_decision_gate(
    state: FeatureState,
    feature_path: Path,
    decision: str,
    reason: str,
    evidence: list,
    recommendation: str,
    decided_by: str = "user"
) -> FeatureState:
    """
    Record the decision gate outcome in feature state.

    Args:
        state: Current feature state
        feature_path: Path to feature folder
        decision: "approved" or "rejected" or "deferred"
        reason: Reason for the decision
        evidence: List of evidence items
        recommendation: System recommendation (GO/NO-GO)
        decided_by: Who made the decision

    Returns:
        Updated FeatureState
    """
    now = datetime.now()

    # Record the decision
    state.record_decision(
        phase="decision_gate",
        decision=f"Decision Gate: {decision.upper()}",
        rationale=reason,
        decided_by=decided_by,
        metadata={
            "recommendation": recommendation,
            "evidence_count": len(evidence),
            "timestamp": now.isoformat(),
        }
    )

    # Transition phase based on decision
    if decision == "approved":
        # Mark decision gate as complete and transition to output generation
        state.record_phase_transition(
            from_phase=FeaturePhase.DECISION_GATE,
            to_phase=FeaturePhase.OUTPUT_GENERATION,
            metadata={
                "approved_at": now.isoformat(),
                "approved_by": decided_by,
                "recommendation": recommendation,
            }
        )
    elif decision == "rejected":
        # Stay in decision gate but mark as rejected
        state.record_phase_transition(
            from_phase=state.current_phase,
            to_phase=FeaturePhase.PARALLEL_TRACKS,  # Go back to parallel tracks to fix issues
            metadata={
                "rejected_at": now.isoformat(),
                "rejected_by": decided_by,
                "reason": reason,
            }
        )
    # If deferred, stay in current phase

    # Save the updated state
    state.save(feature_path)

    return state

# Process decision if direct flag provided or prompt user
if direct_decision:
    final_decision = direct_decision
    final_reason = decision_reason
elif is_ready:
    # Show prompt for user decision
    print(f"""
{'=' * 70}
 ACTION REQUIRED
{'=' * 70}

 The feature meets all decision gate requirements.

 To proceed:
   /decision-gate {slug} --approve --reason "Your approval reason"

 To reject despite passing:
   /decision-gate {slug} --reject --reason "Your rejection reason"

""")
    final_decision = None
    final_reason = None
else:
    # Show what needs to be fixed
    print(f"""
{'=' * 70}
 ACTION REQUIRED
{'=' * 70}

 The feature does NOT meet decision gate requirements.

 To fix issues:
""")
    if decision_gate_result.blockers:
        for i, blocker in enumerate(decision_gate_result.blockers, 1):
            print(f"   {i}. {blocker}")

    print(f"""
 After fixing, re-run:
   /decision-gate {slug}

 To reject:
   /decision-gate {slug} --reject --reason "Your reason"

 To override and approve anyway (not recommended):
   /decision-gate {slug} --approve --reason "Override reason"

""")
    final_decision = None
    final_reason = None

# Record decision if one was made
if final_decision:
    state = record_decision_gate(
        state=state,
        feature_path=feature_path,
        decision=final_decision,
        reason=final_reason,
        evidence=evidence,
        recommendation=recommendation,
        decided_by="user"
    )

    if final_decision == "approved":
        print(f"""
{'=' * 70}
 DECISION RECORDED: APPROVED
{'=' * 70}

 Feature has been approved and transitioned to OUTPUT_GENERATION phase.

 Next steps:
   1. Generate PRD: /generate-outputs {slug}
   2. Export to spec: /export-to-spec {slug}
   3. Create Jira epic (optional): /create-jira-epic {slug}

""")
    elif final_decision == "rejected":
        print(f"""
{'=' * 70}
 DECISION RECORDED: REJECTED
{'=' * 70}

 Feature has been rejected and moved back to PARALLEL_TRACKS phase.

 Reason: {final_reason}

 Next steps:
   1. Address rejection feedback
   2. Update relevant tracks
   3. Re-run: /decision-gate {slug}

""")
```

### Step 9: Generate Decision Gate Report File

Create a decision gate report file in the feature folder for audit trail.

```python
# Generate decision gate report file
if final_decision:
    report_content = f"""# Decision Gate Report: {state.title}

**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Feature**: {state.slug}
**Product**: {state.product_id}

## Decision

**Result**: {final_decision.upper()}
**Reason**: {final_reason}
**System Recommendation**: {recommendation}

## Validation Summary

- Total Hooks Run: {validation_report.total_count}
- Passed: {validation_report.passed_count}
- Critical Failures: {validation_report.critical_count}

## Quality Gate Status

### Context Track
- Status: {'PASS' if context_passed else 'INCOMPLETE'}

### Business Case Track
- Status: {bc_gate_result.status.value.upper()}
- Approved: {bc_approved}

### Design Track
{chr(10).join([f'- {g.gate_name}: {g.status.value.upper()}' for g in design_gate_results])}

### Engineering Track
{chr(10).join([f'- {g.gate_name}: {g.status.value.upper()}' for g in eng_gate_results])}

## Blockers at Decision Time

- Critical: {blocker_report.critical_count}
- High: {blocker_report.high_count}
- Medium: {blocker_report.medium_count}
- Advisory: {blocker_report.low_count}

## Evidence

{chr(10).join([f'- {e}' for e in evidence])}

---
*Generated by Context Creation Engine Decision Gate*
"""

    reports_dir = feature_path / "reports"
    reports_dir.mkdir(exist_ok=True)

    report_filename = f"decision-gate-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    report_path = reports_dir / report_filename
    report_path.write_text(report_content)

    print(f" Report saved: {report_path}")

print()
```

## Error Handling

| Error | Resolution |
|-------|------------|
| Feature not found | Provide correct slug or navigate to feature directory |
| No feature-state.yaml | Initialize feature with /start-feature first |
| Track data missing | Some tracks may not be initialized yet |
| Cannot approve | Address blockers and quality gate failures first |
| Missing required reason | Provide --reason with approve/reject flags |

## Integration Points

- **ValidationHookRunner**: `common/tools/context_engine/validation_hooks.py`
- **QualityGates**: `common/tools/context_engine/quality_gates.py`
- **BlockerDetector**: `common/tools/context_engine/blocker_detection.py`
- **FeatureState**: `common/tools/context_engine/feature_state.py`
- **BusinessCaseTrack**: `common/tools/context_engine/tracks/business_case.py`
- **EngineeringTrack**: `common/tools/context_engine/tracks/engineering.py`

## Decision Gate Criteria (PRD F.2)

### Required for GO
- Context document v3 complete (challenge score >= 85%)
- Business case approved by required stakeholders
- Design artifacts attached (Figma required, wireframes recommended)
- Engineering estimate provided
- All ADRs decided (accepted or rejected)
- No blocking dependencies
- High-impact risks have mitigation plans
- No critical validation failures

### Results in NO-GO
- Any critical validation failure
- Any critical blocker
- Business case rejected
- Missing required design artifacts
- Unresolved blocking dependencies
- High-impact risks without mitigation

## Next Steps After Decision Gate

Based on the decision:
- **APPROVED**: Proceed to /generate-outputs to create PRD
- **REJECTED**: Address feedback, update tracks, re-run /decision-gate
- **DEFERRED**: Feature remains in current phase for later review

## Execute

Find the feature, run all validation hooks, check quality gates, detect blockers, generate GO/NO-GO recommendation, record decision if approved/rejected, and transition phase accordingly.
