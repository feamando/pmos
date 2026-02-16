# Workflow Guide

This guide walks through a complete feature lifecycle from inception to launch decision.

## Example Feature: OTP Checkout Recovery

We'll follow a real example: implementing OTP-based checkout recovery for Meal Kit.

---

## Phase 1: Initialization

### Step 1.1: Start the Feature

```bash
/start-feature "OTP Checkout Recovery" --product meal-kit --priority P1
```

**Output:**
```
Feature initialized:
  Slug: mk-feature-recovery
  Path: user/products/growth-division/meal-kit/mk-feature-recovery/
  Brain Entity: [[Entities/MK_Feature_Recovery]]

Created files:
  - feature-state.yaml
  - mk-feature-recovery-context.md
  - context-docs/
  - business-case/
  - engineering/
  - reports/

Next: Write the initial context document (v1)
```

### Step 1.2: Review Created Structure

```bash
ls -la user/products/growth-division/meal-kit/mk-feature-recovery/
```

---

## Phase 2: Context Document (v1)

### Step 2.1: Write Initial Context

Edit `mk-feature-recovery-context.md`:

```markdown
# OTP Checkout Recovery

## Problem Statement
Users who abandon checkout due to payment failures or session timeouts
currently have no easy way to recover their cart. This leads to lost
conversions and frustrated customers.

## Scope
- Send OTP code to user's phone when checkout is abandoned
- Allow recovery via OTP entry
- Restore cart contents and checkout state

## Out of Scope
- Email-based recovery (future phase)
- Guest checkout recovery

## Success Metrics
- Recovery rate: % of abandoned checkouts recovered
- Time to recovery: Average time from abandonment to completion
- Conversion lift: % increase in overall conversion
```

### Step 2.2: Check Progress

```bash
/check-feature mk-feature-recovery
```

**Output:**
```
FEATURE STATUS: OTP Checkout Recovery

Progress: [====                ] 20%

TRACKS:
 Context:       [IN PROGRESS] - v1 created
 Design:        [NOT STARTED]
 Business Case: [NOT STARTED]
 Engineering:   [NOT STARTED]
```

---

## Phase 3: Parallel Track Work

Work now proceeds on all four tracks simultaneously.

### Track A: Context → v2

**Add stakeholders and refine:**

```markdown
## Stakeholders
- **Dave Manager** - Product Lead (approver)
- **Alex Chen** - Engineering Lead
- **Sarah Kim** - UX Design
- **Marketing** - Communication strategy

## User Research
Based on Hotjar recordings (Jan 2026):
- 23% of checkouts abandoned at payment step
- 67% of abandoners don't return within 24h
- Top reason: "payment failed, couldn't fix it easily"
```

**Run orthogonal challenge:**

```bash
/orthogonal-challenge mk-feature-recovery
```

**Result:** Score 72% - iterate on feedback, then re-challenge for v3.

### Track B: Design

**Create design spec:**

Create `engineering/design-spec.md` with UX flow.

**Attach wireframes:**

```bash
/attach-artifact wireframes https://figma.com/file/abc123/OTP-Wireframes
```

**After designer completes high-fidelity designs:**

```bash
/attach-artifact figma https://figma.com/file/xyz789/OTP-Final-Design
```

### Track C: Business Case

**Define baseline metrics:**

Create `business-case/baseline-metrics.yaml`:

```yaml
metrics:
  checkout_abandonment_rate: 23%
  recovery_rate_current: 8%
  average_order_value: $85
  monthly_abandoned_checkouts: 12000
```

**Document assumptions:**

Create `business-case/impact-assumptions.md`:

```markdown
## Impact Assumptions

### Conservative Estimate
- Recovery rate improvement: 5% → 13% (5pp lift)
- Additional monthly recoveries: 600 orders
- Revenue impact: $51,000/month

### Optimistic Estimate
- Recovery rate improvement: 5% → 20% (15pp lift)
- Additional monthly recoveries: 1800 orders
- Revenue impact: $153,000/month
```

**Get approval:**

```bash
# After presenting to Dave in 1:1
# Record the approval
```

In feature-state.yaml, the BC track records:
```yaml
business_case:
  status: approved
  approvals:
    - approver: "Dave Manager"
      approved: true
      date: "2026-02-05T14:30:00Z"
      approval_type: verbal
      notes: "Approved in weekly 1:1"
```

### Track D: Engineering

**Identify components:**

Create `engineering/components.yaml`:

```yaml
components:
  - name: otp-service
    type: backend
    description: "OTP generation and validation microservice"
    team: checkout

  - name: checkout-recovery-api
    type: backend
    description: "API endpoints for cart recovery"
    team: checkout

  - name: otp-entry-ui
    type: frontend
    description: "OTP entry modal component"
    team: frontend

  - name: sms-integration
    type: integration
    description: "Twilio SMS integration for OTP delivery"
    team: platform
```

**Create ADR:**

Create `engineering/adrs/001-otp-delivery-method.md`:

```markdown
# ADR-001: Use SMS for OTP Delivery

## Status
Accepted

## Context
We need to deliver OTP codes to users. Options include SMS, email,
push notifications, or authenticator apps.

## Decision
Use SMS via Twilio for OTP delivery.

## Consequences
- **Positive:** Universal reach (no app required), fast delivery
- **Negative:** Per-message cost (~$0.01), some regions have SMS issues
```

**Provide estimate:**

Create `engineering/estimate.yaml`:

```yaml
overall: M
breakdown:
  backend: M
  frontend: S
  integration: S
  testing: M
estimated_by: "Alex Chen"
estimated_at: "2026-02-05"
notes: "Main complexity is SMS integration and rate limiting"
```

---

## Phase 4: Validation

### Step 4.1: Check All Tracks

```bash
/check-feature mk-feature-recovery --verbose
```

**Output:**
```
FEATURE STATUS: OTP Checkout Recovery

Progress: [================    ] 80%

TRACKS:
 Context:       [COMPLETE] ✓ v3, score 87%
 Design:        [COMPLETE] ✓ Figma attached
 Business Case: [COMPLETE] ✓ Approved by Dave Manager
 Engineering:   [COMPLETE] ✓ Estimate: M

ARTIFACTS:
 - Figma: https://figma.com/file/xyz789
 - Wireframes: https://figma.com/file/abc123
 - Jira: (not yet created)
```

### Step 4.2: Run Validation

```bash
/validate-feature mk-feature-recovery --verbose
```

**Output:**
```
VALIDATION RESULTS

Context Track:       PASS
 ✓ Document exists
 ✓ Problem statement present
 ✓ Stakeholders defined
 ✓ Challenge score: 87% (threshold: 85%)

Design Track:        PASS
 ✓ Design spec present
 ✓ Wireframes attached
 ✓ Figma attached

Business Case Track: PASS
 ✓ Baseline metrics provided
 ✓ Impact assumptions documented
 ✓ ROI analysis complete
 ✓ Approvals: Dave Manager (verbal)

Engineering Track:   PASS
 ✓ Components identified (4)
 ✓ ADRs decided (1 accepted, 0 proposed)
 ✓ Estimate provided: M
 ✓ Dependencies tracked (0 blocking)
 ✓ No high-impact risks without mitigation

DECISION GATE:       READY ✓
```

---

## Phase 5: Decision Gate

### Step 5.1: Request Approval

```bash
/decision-gate mk-feature-recovery --approve --reason "All tracks complete, BC approved by Dave, ready for implementation"
```

**Output:**
```
DECISION GATE: APPROVED ✓

Feature: OTP Checkout Recovery (mk-feature-recovery)
Decision: GO
Reason: All tracks complete, BC approved by Dave, ready for implementation
Decided: 2026-02-06T10:30:00Z

Audit trail saved to: reports/decision-gate-2026-02-06.md

Next steps:
1. Run /generate-outputs to create deliverables
2. Run /export-to-spec to send to Spec Machine
```

---

## Phase 6: Output Generation

### Step 6.1: Generate Deliverables

```bash
/generate-outputs mk-feature-recovery
```

**Output:**
```
Generated outputs:

 ✓ PRD: reports/mk-feature-recovery-prd.md
 ✓ Engineering Spec: reports/mk-feature-recovery-spec.md
 ✓ BC Summary: reports/mk-feature-recovery-bc-summary.md
 ✓ Jira Epic: reports/mk-feature-recovery-jira-epic.json

Ready for implementation handoff.
```

### Step 6.2: Export to Spec Machine

```bash
/export-to-spec mk-feature-recovery
```

---

## Phase 7: Handoff Complete

The feature is now ready for implementation:

```
✓ Context document finalized (v3, 87% score)
✓ Designs complete and attached
✓ Business case approved
✓ Engineering estimate provided
✓ Decision gate passed
✓ PRD and specs generated
✓ Exported to Spec Machine
```

---

## Quick Reference: Commands by Phase

| Phase | Command | Purpose |
|-------|---------|---------|
| Initialize | `/start-feature` | Create feature structure |
| Work | `/check-feature` | Monitor progress |
| Work | `/attach-artifact` | Link external docs |
| Work | `/resume-feature` | Return after pause |
| Validate | `/validate-feature` | Check quality gates |
| Decide | `/decision-gate` | GO/NO-GO decision |
| Output | `/generate-outputs` | Create deliverables |
| Handoff | `/export-to-spec` | Send to implementation |

---

## Tips for Success

### 1. Start Context Early
Even a rough v1 context document unlocks parallel work on other tracks.

### 2. Attach Artifacts as They're Ready
Don't wait until everything is done—attach Figma, Jira, etc. as they become available.

### 3. Check Progress Regularly
Run `/check-feature` to see what's blocking and what's next.

### 4. Use Resume After Breaks
When returning to a feature after days away, `/resume-feature` restores context and shows what changed.

### 5. Validate Before Decision Gate
Always run `/validate-feature` before requesting decision gate approval.

### 6. Record Approvals with Evidence
When stakeholders approve, record it with reference links (Slack, email) for audit trail.

---

*End of Workflow Guide*
