# Feature Lifecycle Commands

The Feature Lifecycle Commands provide a complete workflow for managing features from inception to launch within PM-OS. These commands work together as part of the **Context Creation Engine**, tracking progress across multiple parallel tracks (Context, Design, Business Case, Engineering) with quality gates and decision checkpoints.

## Command Summary

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/start-feature` | Initialize a new feature | Beginning of any feature work |
| `/check-feature` | Review feature status | Anytime to see progress |
| `/resume-feature` | Continue paused work | Returning after days away |
| `/validate-feature` | Pre-launch validation | Before decision gate |
| `/attach-artifact` | Link external documents | When designs/specs are ready |
| `/decision-gate` | Formal go/no-go decision | Before moving to implementation |
| `/generate-outputs` | Create deliverables | After decision gate approval |

---

## `/start-feature`

**Initialize a new feature for the Context Creation Engine workflow.**

### Usage

```bash
/start-feature "OTP Checkout Recovery"
/start-feature "Improve Login Flow" --product meal-kit
/start-feature "Push Notifications" --product tpt --priority P1
```

### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `<title>` | Feature title | Yes |
| `--product <id>` | Product ID or name | No (will prompt if ambiguous) |
| `--from-insight <id>` | Link to an existing insight | No |
| `--priority <level>` | P0, P1, P2 | No (default: P2) |

### What It Creates

```
user/products/growth-division/meal-kit/mk-feature-recovery/
├── feature-state.yaml          # State tracking
├── mk-feature-recovery-context.md # Context document
├── context-docs/               # Version history
├── business-case/              # BC documents
├── engineering/                # Technical specs
└── reports/                    # Generated reports
```

### Behavior

1. Identifies the target product (explicit flag > Master Sheet > recent context > Slack channel)
2. Checks for existing features with alias detection (prevents duplicates)
3. Creates folder structure
4. Creates a Brain entity for the feature
5. Initializes feature state tracking

---

## `/check-feature`

**Display status, progress, pending items, and blockers for a feature.**

### Usage

```bash
/check-feature
/check-feature mk-feature-recovery
/check-feature mk-feature-recovery --verbose
```

### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `<slug>` | Feature slug | No (uses current directory) |
| `--verbose` | Show detailed track information | No |

### Sample Output

```
============================================================
 FEATURE STATUS: OTP Checkout Recovery
============================================================

 Slug: mk-feature-recovery
 Product: meal-kit
 Phase: parallel_tracks
 Status: in_progress

 Progress: [========            ] 40%

============================================================
 TRACKS
============================================================

 Context:       [COMPLETE] ✓
 Design:        [WAITING]
 Business Case: [REVIEW]
 Engineering:   [TODO]

============================================================
 PENDING ITEMS (3)
============================================================
 - [Context] Context document v2 needs orthogonal challenge
 - [Business Case] Awaiting approval from: Dave Manager
 - [Engineering] Engineering estimate needed
```

---

## `/resume-feature`

**Continue paused work with full context restoration.**

### Usage

```bash
/resume-feature mk-feature-recovery
/resume-feature
```

### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `<slug>` | Feature slug | No (uses current directory) |

### What It Does

1. Loads feature state and full context
2. Shows what was last worked on
3. Displays any new context since last touch (meetings, Slack, documents)
4. Lists pending items in priority order
5. Suggests next action based on track status

---

## `/validate-feature`

**Run validation checks against quality gates for each phase.**

### Usage

```bash
/validate-feature
/validate-feature mk-feature-recovery
/validate-feature mk-feature-recovery --phase design
/validate-feature --verbose
```

### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `<slug>` | Feature slug | No (uses current directory) |
| `--phase <phase>` | Validate specific phase only | No |
| `--verbose` | Show detailed gate criteria | No |

### Phases

- `context` - Context document validation
- `design` - Design artifacts validation
- `business_case` - Business case validation
- `engineering` - Engineering spec validation
- `decision_gate` - All gates combined

### Output

- Phase-by-phase PASS/INCOMPLETE/NOT_STARTED status
- Gate-level pass/fail details with evidence
- Blockers preventing advancement
- Actionable next steps for failed gates

---

## `/attach-artifact`

**Attach external artifacts to a feature.**

### Usage

```bash
/attach-artifact figma https://figma.com/file/abc123/Design-v1
/attach-artifact jira MK-1234
/attach-artifact wireframes https://figma.com/file/xyz789/Wireframes
/attach-artifact confluence https://your-company.atlassian.net/wiki/spaces/MK/pages/123456
```

### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `<type>` | Artifact type | Yes |
| `<url_or_value>` | URL or identifier | Yes |
| `--feature <slug>` | Feature slug | No (uses current directory) |

### Supported Types

| Type | Description | Example |
|------|-------------|---------|
| `figma` | Figma design files | `figma.com/file/<id>` |
| `wireframes` | Wireframe designs | Same as figma |
| `jira` | Jira tickets/epics | `MK-1234` or full URL |
| `confluence` | Confluence pages | Full wiki URL |
| `gdocs` | Google Docs | `docs.google.com/document/d/<id>` |

---

## `/decision-gate`

**Final review command that validates feature readiness and records go/no-go decisions.**

### Usage

```bash
/decision-gate
/decision-gate mk-feature-recovery
/decision-gate mk-feature-recovery --approve --reason "All tracks complete, BC approved"
/decision-gate mk-feature-recovery --reject --reason "Missing engineering estimate"
/decision-gate --verbose
```

### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `<slug>` | Feature slug | No (uses current directory) |
| `--approve` | Directly approve the feature | No |
| `--reject` | Directly reject the feature | No |
| `--reason "<text>"` | Reason for decision | Required with --approve/--reject |
| `--verbose` | Show detailed validation results | No |

### Requirements for GO

- Context document complete (v3 with challenge score >= 85%)
- Business case approved by required stakeholders
- Design artifacts attached (Figma required)
- Engineering estimate provided
- All ADRs decided (accepted or rejected)
- No blocking dependencies
- High-impact risks have mitigation plans

### On Approval

1. Records decision in feature-state.yaml
2. Transitions feature to OUTPUT_GENERATION phase
3. Creates audit trail report
4. Suggests next steps (`/generate-outputs`)

### On Rejection

1. Records rejection with reason
2. Returns feature to PARALLEL_TRACKS phase
3. Lists items to address

---

## `/generate-outputs`

**Create feature deliverables after decision gate approval.**

### Usage

```bash
/generate-outputs mk-feature-recovery
/generate-outputs mk-feature-recovery --type prd
/generate-outputs --all
```

### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `<slug>` | Feature slug | No (uses current directory) |
| `--type <type>` | Output type | No (default: all) |

### Output Types

| Type | Description |
|------|-------------|
| `prd` | Product Requirements Document |
| `spec` | Engineering specification for Spec Machine |
| `bc` | Business case summary document |
| `all` | All of the above |

### Generated Files

```
reports/
├── mk-feature-recovery-prd.md
├── mk-feature-recovery-spec.md
├── mk-feature-recovery-bc-summary.md
└── mk-feature-recovery-jira-epic.json
```

---

## Complete Workflow

```
┌──────────────────────────────────────────────────────────────────┐
│                    FEATURE LIFECYCLE FLOW                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. /start-feature "Feature Name"                                │
│     └─> Creates folder, Brain entity, initializes state          │
│                                                                   │
│  2. PARALLEL TRACKS (work happens in any order)                  │
│     ├─> Context: Write context document (v1 → v2 → v3)          │
│     ├─> Design: Attach Figma, wireframes                         │
│     ├─> Business Case: Define metrics, get approval              │
│     └─> Engineering: Estimate, ADRs, risks                       │
│                                                                   │
│  3. /check-feature (anytime)                                     │
│     └─> See progress across all tracks                           │
│                                                                   │
│  4. /attach-artifact figma <url> (as artifacts ready)            │
│     └─> Links designs, specs, tickets                            │
│                                                                   │
│  5. /validate-feature (before decision gate)                     │
│     └─> Check all quality gates pass                             │
│                                                                   │
│  6. /decision-gate --approve                                     │
│     └─> Formal GO/NO-GO decision                                 │
│                                                                   │
│  7. /generate-outputs                                            │
│     └─> Create PRD, specs, BC summary                            │
│                                                                   │
│  8. /export-to-spec                                              │
│     └─> Send to Spec Machine for implementation                  │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

*Next: [Quality Gates](05-quality-gates.md)*
