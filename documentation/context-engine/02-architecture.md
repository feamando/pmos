# Context Engine Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CONTEXT CREATION ENGINE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐               │
│  │   Commands   │───▶│FeatureEngine │───▶│FeatureState  │               │
│  │  (Triggers)  │    │(Orchestrator)│    │  (Storage)   │               │
│  └──────────────┘    └──────────────┘    └──────────────┘               │
│         │                   │                   │                        │
│         │                   │                   │                        │
│         ▼                   ▼                   ▼                        │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      PARALLEL TRACKS                             │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐    │    │
│  │  │ Context │  │ Design  │  │Business │  │  Engineering    │    │    │
│  │  │  Track  │  │  Track  │  │  Case   │  │     Track       │    │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────────────┘    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                │                                         │
│                                ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      QUALITY GATES                               │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │  Context Score │ BC Approval │ Design Artifacts │ Eng Estimate  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                │                                         │
│                                ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                   INTEGRATIONS                                   │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │  Brain │ Master Sheet │ Jira │ Confluence │ Spec Machine        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. FeatureEngine (`feature_engine.py`)

The central orchestrator that coordinates all operations:

```python
from tools.context_engine import FeatureEngine

engine = FeatureEngine()

# Start a new feature
feature = engine.start_feature(
    title="OTP Checkout Recovery",
    product_id="meal-kit"
)

# Check status
status = engine.check_feature("mk-feature-recovery")

# Resume paused feature
engine.resume_feature("mk-feature-recovery")
```

**Responsibilities:**
- Feature initialization
- State management coordination
- Track orchestration
- Quality gate validation
- Integration dispatch

### 2. FeatureState (`feature_state.py`)

Manages the `feature-state.yaml` file:

```yaml
slug: mk-feature-recovery
title: "OTP Checkout Recovery"
product_id: meal-kit
organization: growth-division
context_file: mk-feature-recovery-context.md
brain_entity: "[[Entities/MK_Feature_Recovery]]"
created: 2026-02-02T10:30:00Z

engine:
  current_phase: parallel_tracks
  phase_history:
    - phase: initialization
      entered: 2026-02-02T10:30:00Z
      completed: 2026-02-02T10:30:05Z
  tracks:
    context:
      status: complete
      current_version: 3
      challenge_score: 87
    design:
      status: in_progress
      figma_attached: false
    business_case:
      status: pending_approval
      approvals: [{approver: "Irene", approved: true}]
    engineering:
      status: not_started

artifacts:
  figma: null
  jira: "MK-1234"
  confluence: null

decisions: []
aliases: []
```

**Key Enums:**

| Enum | Values |
|------|--------|
| `FeaturePhase` | initialization, signal_analysis, context_doc, parallel_tracks, decision_gate, output_generation, complete, archived, deferred |
| `TrackStatus` | not_started, in_progress, pending_input, pending_approval, complete, blocked |

### 3. Quality Gates (`quality_gates.py`)

Defines validation rules and thresholds:

```python
from tools.context_engine.quality_gates import QualityGates, validate_decision_gate

# Default thresholds
gates = QualityGates()

# Custom thresholds per product
gates = QualityGates(
    context_draft_threshold=55,
    context_review_threshold=70,
    context_approved_threshold=80,
    required_bc_approvers=["ceo", "vp_product"],
    figma_required=True,
)

# Validate
result = validate_decision_gate(state, feature_path, gates)
```

**Gate Levels:**
- `BLOCKING` - Must pass to proceed
- `REQUIRED` - Must pass for completion
- `ADVISORY` - Recommended but not required

### 4. Parallel Tracks

#### Context Track
- Generates and iterates context documents
- Integrates with Orthogonal Challenge for scoring
- Tracks document versions (v1 → v2 → v3)

#### Design Track
- Manages design artifact attachments
- Validates Figma/wireframe presence
- Links to design spec documents

#### Business Case Track (`tracks/business_case.py`)

```python
from tools.context_engine.tracks import BusinessCaseTrack

track = BusinessCaseTrack(feature_path)
track.start(initiated_by="jane")
track.update_assumptions(baseline_metrics={...}, impact_assumptions={...})
track.submit_for_approval(approver="Jack Approver")
track.record_approval(approver="Jack Approver", approved=True, approval_type="verbal")
```

**BC Lifecycle:**
```
NOT_STARTED → IN_PROGRESS → PENDING_APPROVAL → APPROVED
                                    ↓
                                REJECTED
```

#### Engineering Track (`tracks/engineering.py`)

```python
from tools.context_engine.tracks import EngineeringTrack

track = EngineeringTrack(feature_path)
track.start(initiated_by="jane")
track.create_adr(
    title="Use Redis for Session Storage",
    context="Need to share sessions across multiple app instances",
    decision="Use Redis as centralized session store",
    consequences="Adds infrastructure dependency but enables horizontal scaling"
)
track.record_estimate(estimate="M", breakdown={"frontend": "S", "backend": "M"})
```

**Engineering Lifecycle:**
```
NOT_STARTED → IN_PROGRESS → ESTIMATION_PENDING → COMPLETE
                    ↓
                 BLOCKED
```

## File Structure

```
common/tools/context_engine/
├── __init__.py
├── feature_engine.py          # Main orchestrator
├── feature_state.py           # State management
├── quality_gates.py           # Gate validation
├── alias_manager.py           # Duplicate detection
├── artifact_manager.py        # External artifact linking
├── brain_entity_creator.py    # Brain integration
├── product_identifier.py      # Product detection
├── context_doc_generator.py   # Context document creation
├── orthogonal_integration.py  # Challenge scoring
├── bidirectional_sync.py      # Master Sheet sync
├── blocker_detection.py       # Blocker identification
├── validation_hooks.py        # Custom validation
├── spec_export.py             # Spec Machine export
├── jira_integration.py        # Jira ticket creation
├── output_finalizer.py        # Deliverable generation
├── master_sheet_reader.py     # Sheet data access
├── master_sheet_completion.py # Sheet updates
├── input_gate.py              # Input collection
├── gate_prompt_interface.py   # User prompts
├── context_iteration_pipeline.py
├── tracks/
│   ├── __init__.py
│   ├── business_case.py
│   └── engineering.py
├── validators/
│   └── __init__.py
└── tests/
    └── ...
```

## Integration Points

### Brain Integration
- Creates entity on feature initialization
- Updates entity with track progress
- Links artifacts and decisions

### Master Sheet Integration
- Reads priority and deadlines
- Updates completion status
- Syncs with product hierarchy

### Jira Integration
- Creates epics after decision gate
- Links features to tickets
- Syncs status bidirectionally

### Spec Machine Integration
- Exports approved features
- Generates engineering specs
- Handles implementation handoff

---

*Next: [Installation](03-installation.md)*
