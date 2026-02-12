# Quality Gates Reference

Quality gates ensure features meet minimum standards before advancing through the lifecycle. Each track has specific gates that must pass before the feature can proceed to implementation.

## Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         QUALITY GATES SYSTEM                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  CONTEXT TRACK                    DESIGN TRACK                          │
│  ┌────────────────────┐          ┌────────────────────┐                 │
│  │ □ Document exists  │          │ □ Design spec      │                 │
│  │ □ Problem stated   │          │ □ Wireframes       │                 │
│  │ □ Stakeholders     │          │ □ Figma attached   │                 │
│  │ □ Challenge 85%+   │          │                    │                 │
│  └────────────────────┘          └────────────────────┘                 │
│                                                                          │
│  BUSINESS CASE TRACK              ENGINEERING TRACK                     │
│  ┌────────────────────┐          ┌────────────────────┐                 │
│  │ □ Baseline metrics │          │ □ Components ID'd  │                 │
│  │ □ Impact assumed   │          │ □ ADRs decided     │                 │
│  │ □ ROI analysis     │          │ □ Estimate given   │                 │
│  │ □ Approvals        │          │ □ Deps tracked     │                 │
│  └────────────────────┘          │ □ Risks mitigated  │                 │
│                                   └────────────────────┘                 │
│                                                                          │
│  ═══════════════════════════════════════════════════════════════════    │
│                           DECISION GATE                                  │
│  ═══════════════════════════════════════════════════════════════════    │
│  All above gates MUST pass for GO decision                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Gate Levels

| Level | Behavior | Example |
|-------|----------|---------|
| **BLOCKING** | Must pass to proceed | Context score threshold |
| **REQUIRED** | Must pass for completion | Figma attachment |
| **ADVISORY** | Recommended but optional | Wireframes |

## Context Track Gates

### Gate: Document Exists

| Property | Value |
|----------|-------|
| Level | BLOCKING |
| Check | Context document file exists |
| Action | Run `/start-feature` to create |

### Gate: Problem Statement Present

| Property | Value |
|----------|-------|
| Level | BLOCKING |
| Check | "Problem Statement" section has content |
| Action | Complete the Problem Statement section |

### Gate: Stakeholders Defined

| Property | Value |
|----------|-------|
| Level | REQUIRED |
| Check | At least one stakeholder listed |
| Action | Add stakeholders to context document |

### Gate: Orthogonal Challenge Score

| Property | Value |
|----------|-------|
| Level | BLOCKING |
| Threshold (v1) | N/A (not required) |
| Threshold (v2) | >= 60% |
| Threshold (v3) | >= 85% |
| Action | Run orthogonal challenge, iterate on feedback |

```python
# Score thresholds by version
CONTEXT_THRESHOLDS = {
    "v1": None,      # No challenge required
    "v2": 60,        # Draft threshold
    "v3": 85,        # Approval threshold
}
```

## Design Track Gates

### Gate: Design Spec Present

| Property | Value |
|----------|-------|
| Level | REQUIRED |
| Check | Design specification document exists |
| Action | Create design spec in design/ folder |

### Gate: Wireframes Provided

| Property | Value |
|----------|-------|
| Level | ADVISORY |
| Check | Wireframe artifact attached |
| Action | Attach wireframes via `/attach-artifact wireframes <url>` |

### Gate: Figma Attached

| Property | Value |
|----------|-------|
| Level | REQUIRED (for decision gate) |
| Check | Figma URL in artifacts |
| Action | Attach via `/attach-artifact figma <url>` |

## Business Case Track Gates

### Gate: Baseline Metrics Provided

| Property | Value |
|----------|-------|
| Level | REQUIRED |
| Check | `baseline_metrics` populated in BC track |
| Action | Define current state metrics |

### Gate: Impact Assumptions Documented

| Property | Value |
|----------|-------|
| Level | REQUIRED |
| Check | `impact_assumptions` present |
| Action | Document expected impact and assumptions |

### Gate: ROI Analysis

| Property | Value |
|----------|-------|
| Level | REQUIRED |
| Check | ROI calculated, positive in conservative case |
| Action | Complete ROI analysis in business-case/ folder |

### Gate: Stakeholder Approval

| Property | Value |
|----------|-------|
| Level | BLOCKING |
| Check | All required approvers have approved |
| Action | Get approval, record via BC track |

**Approval Types:**
- `verbal` - Spoken approval (meeting, call)
- `written` - Document signature
- `email` - Email approval
- `slack` - Slack message approval

```python
# Recording an approval
track.record_approval(
    approver="Jack Approver",
    approved=True,
    approval_type="slack",
    reference="https://slack.com/archives/C123/p456"
)
```

## Engineering Track Gates

### Gate: Components Identified

| Property | Value |
|----------|-------|
| Level | REQUIRED |
| Check | Technical components listed |
| Action | Identify frontend/backend/infra components |

### Gate: ADRs Decided

| Property | Value |
|----------|-------|
| Level | BLOCKING |
| Check | All ADRs in `accepted` or `rejected` status (no `proposed`) |
| Action | Review and decide on all architectural decisions |

**ADR Statuses:**
- `proposed` - Under discussion (BLOCKS decision gate)
- `accepted` - Decision made, will implement
- `rejected` - Decision made, won't implement
- `deprecated` - Previously accepted, now obsolete
- `superseded` - Replaced by another ADR

### Gate: Estimate Provided

| Property | Value |
|----------|-------|
| Level | REQUIRED |
| Check | Engineering estimate recorded |
| Action | Provide T-shirt size estimate (S/M/L/XL) |

**Estimate Sizes:**
| Size | Description | Typical Duration |
|------|-------------|------------------|
| S | Small | < 1 sprint |
| M | Medium | 1-2 sprints |
| L | Large | 2-4 sprints |
| XL | Extra Large | 4+ sprints |

### Gate: Dependencies Tracked

| Property | Value |
|----------|-------|
| Level | REQUIRED |
| Check | Dependencies listed (or explicitly "none") |
| Action | Identify and track dependencies |

### Gate: Risks Mitigated

| Property | Value |
|----------|-------|
| Level | REQUIRED (high-impact only) |
| Check | High-impact risks have mitigation plans |
| Action | Add mitigation plan for each high-impact risk |

## Decision Gate

The decision gate aggregates all track gates:

```
DECISION GATE =
    Context (PASS) +
    Design (PASS) +
    Business Case (PASS) +
    Engineering (PASS) +
    No Blocking Dependencies +
    High-Impact Risks Mitigated
```

### Decision Gate Validation

```bash
# Check if ready for decision gate
/validate-feature --phase decision_gate --verbose
```

Output:
```
============================================================
 DECISION GATE VALIDATION
============================================================

 Context Track:       PASS
   ✓ Document exists
   ✓ Problem statement present
   ✓ Stakeholders defined
   ✓ Challenge score: 87% (threshold: 85%)

 Design Track:        PASS
   ✓ Design spec present
   ⚠ Wireframes not attached (advisory)
   ✓ Figma attached

 Business Case Track: PASS
   ✓ Baseline metrics provided
   ✓ Impact assumptions documented
   ✓ ROI analysis complete
   ✓ Approvals: Jack Approver (slack), Dave Manager (verbal)

 Engineering Track:   INCOMPLETE
   ✓ Components identified
   ✓ ADRs decided (2 accepted, 0 proposed)
   ✗ Estimate not provided
   ✓ Dependencies tracked
   ✓ Risks mitigated

============================================================
 RESULT: NOT READY
============================================================

 Blocking Items:
 - [Engineering] Estimate not provided

 Next Steps:
 1. Request engineering estimate for the feature
 2. Re-run /validate-feature
```

## Customizing Thresholds

Override thresholds per product in `user/config.yaml`:

```yaml
quality_gates:
  default:
    context_draft_threshold: 60
    context_review_threshold: 75
    context_approved_threshold: 85
    figma_required: true
    wireframes_required: false

  products:
    meal-kit:
      context_approved_threshold: 80
      required_bc_approvers:
        - "Dave Manager"

    tpt:
      context_approved_threshold: 85
      required_bc_approvers:
        - "Sebastien Phlix"
        - "Oliver Murphy"
```

## Programmatic Access

```python
from tools.context_engine.quality_gates import (
    QualityGates,
    validate_context_gate,
    validate_business_case_gate,
    validate_design_gate,
    validate_engineering_gate,
    validate_decision_gate,
)

# Load gates with custom config
gates = QualityGates(
    context_approved_threshold=80,
    required_bc_approvers=["CEO", "VP Product"],
)

# Validate individual gates
context_result = validate_context_gate(state, feature_path, gates)
bc_result = validate_business_case_gate(state, feature_path, gates)

# Validate decision gate (all combined)
decision_result = validate_decision_gate(state, feature_path, gates)

if decision_result.status == GateStatus.PASS:
    print("Ready for GO decision!")
else:
    for blocker in decision_result.blockers:
        print(f"Blocker: {blocker}")
```

---

*Next: [Parallel Tracks](06-tracks.md)*
