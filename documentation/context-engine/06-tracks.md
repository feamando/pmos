# Parallel Tracks

The Context Engine manages four parallel tracks that progress independently. Work on one track doesn't block progress on others, allowing different team members to contribute simultaneously.

## Track Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PARALLEL TRACKS                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   CONTEXT          DESIGN          BUSINESS CASE     ENGINEERING        │
│   ┌──────┐        ┌──────┐        ┌──────┐         ┌──────┐            │
│   │ v1   │        │ Spec │        │Start │         │Start │            │
│   │  ↓   │        │  ↓   │        │  ↓   │         │  ↓   │            │
│   │ v2   │        │ Wire │        │Draft │         │ ADRs │            │
│   │  ↓   │        │  ↓   │        │  ↓   │         │  ↓   │            │
│   │ v3   │        │Figma │        │Submit│         │ Est. │            │
│   │  ↓   │        │  ↓   │        │  ↓   │         │  ↓   │            │
│   │Done  │        │Done  │        │Approve         │Done  │            │
│   └──────┘        └──────┘        └──────┘         └──────┘            │
│                                                                          │
│   Owner: PM       Owner: Design   Owner: PM        Owner: Eng Lead     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Context Track

**Purpose:** Define the problem, stakeholders, success metrics, and scope.

**Owner:** Product Manager

### Lifecycle

```
NOT_STARTED → IN_PROGRESS → CHALLENGE → ITERATION → COMPLETE
                    ↓            ↓           ↓
                   v1           v2          v3
```

### Versions

| Version | Contents | Challenge |
|---------|----------|-----------|
| **v1** | Initial problem statement, basic scope | None required |
| **v2** | Stakeholders, success metrics, refined scope | Score >= 60% |
| **v3** | Full context after challenge iteration | Score >= 85% |

### Key Files

```
feature-folder/
├── feature-slug-context.md      # Current context document
└── context-docs/
    ├── v1-2026-02-01.md        # Version history
    ├── v2-2026-02-02.md
    └── v3-2026-02-03.md
```

### Status Values

| Status | Meaning |
|--------|---------|
| `not_started` | No context document created |
| `in_progress` | Document being written |
| `pending_input` | Waiting for stakeholder input |
| `pending_challenge` | Awaiting orthogonal challenge |
| `complete` | v3 approved (score >= 85%) |

### Working with Context Track

```bash
# Create initial context (v1)
/start-feature "Feature Name" --product meal-kit

# Check context status
/check-feature --verbose

# Run orthogonal challenge
/orthogonal-challenge goc-feature-slug

# Iterate based on feedback, then re-challenge
```

---

## Design Track

**Purpose:** Visual designs, wireframes, and UX specifications.

**Owner:** Product Designer

### Lifecycle

```
NOT_STARTED → SPEC_CREATION → WIREFRAMES → FIGMA → COMPLETE
```

### Artifacts

| Artifact | Required | Description |
|----------|----------|-------------|
| Design Spec | Yes | Written specification document |
| Wireframes | No (advisory) | Low-fidelity mockups |
| Figma | Yes (for decision gate) | High-fidelity designs |

### Key Files

```
feature-folder/
├── design/
│   └── design-spec.md          # Design specification
└── feature-state.yaml          # Tracks artifact URLs
```

### Attaching Artifacts

```bash
# Attach wireframes
/attach-artifact wireframes https://figma.com/file/abc123/Wireframes

# Attach final Figma designs
/attach-artifact figma https://figma.com/file/xyz789/Final-Design

# Check design track status
/check-feature --verbose
```

### Status Values

| Status | Meaning |
|--------|---------|
| `not_started` | No design work begun |
| `in_progress` | Design spec being written |
| `wireframes_ready` | Wireframes complete |
| `figma_attached` | Figma designs attached |
| `complete` | All design artifacts ready |

---

## Business Case Track

**Purpose:** ROI analysis, metrics, and stakeholder approval.

**Owner:** Product Manager (with Finance/Leadership input)

### Lifecycle

```
NOT_STARTED → IN_PROGRESS → PENDING_APPROVAL → APPROVED
                                    ↓
                                REJECTED
```

### Components

| Component | Description |
|-----------|-------------|
| **Baseline Metrics** | Current state measurements |
| **Impact Assumptions** | Expected changes and their basis |
| **ROI Analysis** | Return on investment calculation |
| **Stakeholder Approvals** | Sign-offs from required approvers |

### Key Files

```
feature-folder/
└── business-case/
    ├── baseline-metrics.yaml   # Current metrics
    ├── impact-assumptions.md   # Assumptions document
    ├── roi-analysis.md         # ROI calculation
    └── approvals.yaml          # Approval records
```

### Recording Approvals

Approvals can be recorded with evidence:

```python
from tools.context_engine.tracks import BusinessCaseTrack

track = BusinessCaseTrack(feature_path)
track.record_approval(
    approver="Jack Approver",
    approved=True,
    approval_type="slack",
    reference="https://slack.com/archives/C123/p456",
    notes="Approved in #product-reviews channel"
)
```

### Approval Types

| Type | When to Use |
|------|-------------|
| `verbal` | Spoken approval (meeting, call) |
| `written` | Formal document signature |
| `email` | Email confirmation |
| `slack` | Slack message approval |

### Status Values

| Status | Meaning |
|--------|---------|
| `not_started` | No BC work begun |
| `in_progress` | Metrics/assumptions being defined |
| `pending_approval` | Submitted for stakeholder review |
| `approved` | All required approvals obtained |
| `rejected` | BC rejected, needs revision |

---

## Engineering Track

**Purpose:** Technical architecture, estimates, and risk assessment.

**Owner:** Engineering Lead

### Lifecycle

```
NOT_STARTED → IN_PROGRESS → ESTIMATION_PENDING → COMPLETE
                    ↓
                 BLOCKED
```

### Components

| Component | Description |
|-----------|-------------|
| **Components** | Technical components affected |
| **ADRs** | Architecture Decision Records |
| **Estimates** | T-shirt size effort estimates |
| **Dependencies** | External dependencies |
| **Risks** | Technical risks and mitigations |

### Key Files

```
feature-folder/
└── engineering/
    ├── components.yaml         # Component breakdown
    ├── adrs/
    │   ├── 001-session-storage.md
    │   └── 002-api-versioning.md
    ├── estimate.yaml           # Effort estimate
    ├── dependencies.yaml       # Dependency tracking
    └── risks.yaml              # Risk register
```

### Architecture Decision Records (ADRs)

ADRs capture architectural decisions with context:

```markdown
# ADR-001: Use Redis for Session Storage

## Status
Accepted

## Context
We need to share user sessions across multiple application instances
for horizontal scaling.

## Decision
Use Redis as a centralized session store.

## Consequences
- **Positive:** Enables horizontal scaling, sessions survive restarts
- **Negative:** Adds infrastructure dependency, requires Redis ops knowledge
```

**ADR Statuses:**
- `proposed` - Under discussion (blocks decision gate)
- `accepted` - Will implement
- `rejected` - Won't implement
- `deprecated` - No longer applies
- `superseded` - Replaced by another ADR

### Estimates

```yaml
# estimate.yaml
overall: M
breakdown:
  frontend: S
  backend: M
  infrastructure: S
  testing: S
notes: "Backend is main effort due to session migration"
estimated_by: "Alex Chen"
estimated_at: "2026-02-03"
```

**T-Shirt Sizes:**
| Size | Description |
|------|-------------|
| S | < 1 sprint |
| M | 1-2 sprints |
| L | 2-4 sprints |
| XL | 4+ sprints |

### Dependencies

```yaml
# dependencies.yaml
dependencies:
  - id: "cart-service-migration"
    type: internal
    team: "Shopping Foundation"
    status: in_progress
    blocking: false
    notes: "Need Cart Service v2 API"

  - id: "redis-cluster"
    type: infrastructure
    team: "Platform"
    status: complete
    blocking: false
```

### Risks

```yaml
# risks.yaml
risks:
  - id: "session-migration"
    description: "Migrating existing sessions may cause user logouts"
    impact: high
    probability: medium
    mitigation: "Implement gradual rollout with session bridging"
    owner: "Alex Chen"
    status: mitigated
```

### Status Values

| Status | Meaning |
|--------|---------|
| `not_started` | No engineering work begun |
| `in_progress` | Components/ADRs being defined |
| `estimation_pending` | Technical work done, needs estimate |
| `complete` | All engineering artifacts ready |
| `blocked` | Blocked by dependency |

---

## Track Dependencies

While tracks are parallel, some natural dependencies exist:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TRACK DEPENDENCIES                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Context v1 ──────────────────────────────────────────────────────┐    │
│       │                                                             │    │
│       ├──────> Design can start (needs problem understanding)      │    │
│       │                                                             │    │
│       ├──────> Engineering can start (needs scope understanding)   │    │
│       │                                                             │    │
│       └──────> Business Case can start (needs success metrics)     │    │
│                                                                          │
│   Design Figma ───────> Engineering estimate (needs UI complexity) │    │
│                                                                          │
│   Engineering Estimate ──> Business Case ROI (needs effort cost)   │    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Best Practice:** Start Context first (even just v1), then all tracks can proceed in parallel.

---

*Next: [Workflow Guide](07-workflow.md)*
