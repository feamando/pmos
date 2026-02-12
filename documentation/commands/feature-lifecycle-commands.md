# Feature Lifecycle Commands

The Feature Lifecycle Commands provide a complete workflow for managing features from inception to launch within PM-OS. These commands work together as part of the **Context Creation Engine**, tracking progress across multiple parallel tracks (Context, Design, Business Case, Engineering) with quality gates and decision checkpoints.

## Overview

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/start-feature` | Initialize a new feature | Beginning of any feature work |
| `/check-feature` | Review feature status | Anytime to see progress |
| `/resume-feature` | Continue paused work | Returning after days away |
| `/validate-feature` | Pre-launch validation | Before decision gate |
| `/attach-artifact` | Link external documents | When designs/specs are ready |
| `/decision-gate` | Formal go/no-go decision | Before moving to implementation |
| `/generate-outputs` | Create deliverables | After decision gate approval |

## Command Details

### `/start-feature`

**Initialize a new feature for the Context Creation Engine workflow.**

```bash
/start-feature "OTP Checkout Recovery"
/start-feature "Improve Login Flow" --product meal-kit
/start-feature "Push Notifications" --product tpt --priority P1
```

**Arguments:**
- `<title>` - Feature title (required)
- `--product <id>` - Product ID or name (optional, will prompt if ambiguous)
- `--from-insight <id>` - Link to an existing insight (optional)
- `--priority <level>` - P0, P1, P2 (default: P2)

**What it does:**
1. Identifies the target product using smart detection (explicit flag > Master Sheet > recent context > Slack channel)
2. Checks for existing features with alias detection (prevents duplicates)
3. Creates folder structure: `user/products/{org}/{product}/{feature-slug}/`
4. Creates a Brain entity for the feature
5. Initializes feature state tracking

**Created files:**
```
user/products/growth-division/meal-kit/mk-feature-recovery/
├── feature-state.yaml          # State tracking
├── mk-feature-recovery-context.md # Context document
├── context-docs/               # Version history
├── business-case/              # BC documents
├── engineering/                # Technical specs
└── reports/                    # Generated reports
```

---

### `/check-feature`

**Display status, progress, pending items, and blockers for a feature.**

```bash
/check-feature
/check-feature mk-feature-recovery
/check-feature mk-feature-recovery --verbose
```

**Arguments:**
- `<slug>` - Feature slug (optional, uses current directory)
- `--verbose` - Show detailed track information

**Output includes:**
- Overall progress percentage with visual bar
- Track-by-track status (Context, Design, Business Case, Engineering)
- Pending items that need attention
- Blockers preventing progress
- Attached artifacts
- Last activity timestamp

**Sample output:**
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

 Context:       [WORKING]
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

### `/resume-feature`

**Continue paused work with full context restoration.**

```bash
/resume-feature mk-feature-recovery
/resume-feature
```

**Arguments:**
- `<slug>` - Feature slug (optional, uses current directory)

**What it does:**
1. Loads feature state and full context
2. Shows what was last worked on
3. Displays any new context since last touch (meetings, Slack, documents)
4. Lists pending items in priority order
5. Suggests next action based on track status

---

### `/validate-feature`

**Run validation checks against quality gates for each phase.**

```bash
/validate-feature
/validate-feature mk-feature-recovery
/validate-feature mk-feature-recovery --phase design
/validate-feature --verbose
```

**Arguments:**
- `<slug>` - Feature slug (optional, uses current directory)
- `--phase <phase>` - Validate specific phase only (context, design, business_case, engineering, decision_gate)
- `--verbose` - Show detailed gate criteria and evidence

**Quality Gates Checked:**

| Phase | Gates |
|-------|-------|
| Context | Document exists, Problem statement present, Stakeholders defined, Orthogonal challenge run (v2+) |
| Design | Design spec present, Wireframes provided, Figma attached |
| Business Case | Baseline metrics, Impact assumptions, ROI analysis, Stakeholder approval |
| Engineering | Components identified, ADRs decided, Estimate provided, Dependencies listed, Risks mitigated |
| Decision Gate | All of the above + no blocking risks |

**Output:**
- Phase-by-phase PASS/INCOMPLETE/NOT_STARTED status
- Gate-level pass/fail details with evidence
- Blockers preventing advancement
- Actionable next steps for failed gates

---

### `/attach-artifact`

**Attach external artifacts to a feature.**

```bash
/attach-artifact figma https://figma.com/file/abc123/Design-v1
/attach-artifact jira MK-1234
/attach-artifact wireframes https://figma.com/file/xyz789/Wireframes
/attach-artifact confluence https://your-company.atlassian.net/wiki/spaces/MK/pages/123456
```

**Arguments:**
- `<type>` - Artifact type: `figma`, `wireframes`, `jira`, `confluence`, `gdocs`
- `<url_or_value>` - URL or identifier (e.g., `MK-1234` for Jira)
- `--feature <slug>` - Feature slug (optional, uses current directory)

**Supported artifact types:**

| Type | Description | Example |
|------|-------------|---------|
| `figma` | Figma design files | `figma.com/file/<id>` |
| `wireframes` | Wireframe designs | Same as figma |
| `jira` | Jira tickets/epics | `MK-1234` or full URL |
| `confluence` | Confluence pages | Full wiki URL |
| `gdocs` | Google Docs | `docs.google.com/document/d/<id>` |

**What it does:**
1. Validates the URL format
2. Updates `feature-state.yaml` artifacts section
3. Updates the context document References section

---

### `/decision-gate`

**Final review command that validates feature readiness and records go/no-go decisions.**

```bash
/decision-gate
/decision-gate mk-feature-recovery
/decision-gate mk-feature-recovery --approve --reason "All tracks complete, BC approved"
/decision-gate mk-feature-recovery --reject --reason "Missing engineering estimate"
/decision-gate --verbose
```

**Arguments:**
- `<slug>` - Feature slug (optional, uses current directory)
- `--approve` - Directly approve the feature
- `--reject` - Directly reject the feature
- `--reason "<text>"` - Reason for decision
- `--verbose` - Show detailed validation results

**Decision Gate Requirements (for GO):**
- Context document complete (v3 with challenge score >= 85%)
- Business case approved by required stakeholders
- Design artifacts attached (Figma required)
- Engineering estimate provided
- All ADRs decided (accepted or rejected)
- No blocking dependencies
- High-impact risks have mitigation plans

**What happens on approval:**
1. Records decision in feature-state.yaml
2. Transitions feature to OUTPUT_GENERATION phase
3. Creates audit trail report
4. Suggests next steps (/generate-outputs)

**What happens on rejection:**
1. Records rejection with reason
2. Returns feature to PARALLEL_TRACKS phase
3. Lists items to address

---

### `/generate-outputs`

**Create feature deliverables after decision gate approval.**

```bash
/generate-outputs mk-feature-recovery
/generate-outputs mk-feature-recovery --type prd
/generate-outputs --all
```

**Arguments:**
- `<slug>` - Feature slug (optional, uses current directory)
- `--type <type>` - Output type: `prd`, `spec`, `bc`, `all` (default: all)

**Generated outputs:**
- **PRD** - Product Requirements Document from context and decisions
- **Spec** - Engineering specification for Spec Machine export
- **BC Summary** - Business case summary document
- **Jira Epic** - Ready-to-create Jira epic definition

---

## Feature Lifecycle Flow

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

## Quality Gates Reference

### Context Document (PRD F.2)

| Version | Requirements | Challenge Score |
|---------|--------------|-----------------|
| v1 | Problem statement, basic scope | N/A |
| v2 | Stakeholders, success metrics, orthogonal challenge | >= 60% |
| v3 | Full context, refined after challenge | >= 85% |

### Business Case

- Baseline metrics provided
- Impact assumptions documented
- ROI analysis (positive in conservative case)
- Required stakeholder approvals obtained

### Design Track

- Design spec document exists
- Wireframes provided (recommended)
- Figma design attached (required for decision gate)

### Engineering Spec

- Components/architecture identified
- All ADRs decided (no "proposed" status)
- Engineering estimate provided
- Dependencies tracked (none blocking)
- High-impact risks have mitigation plans

---

## Integration Points

All Feature Lifecycle commands integrate with:

- **Brain** - Entities created and updated automatically
- **Master Sheet** - Priority and deadline tracking
- **Jira** - Ticket creation and linking
- **Confluence** - Document sync
- **Spec Machine** - Export for implementation

## File Locations

- **Commands**: `common/.claude/commands/`
- **Engine**: `common/tools/context_engine/`
- **Tracks**: `common/tools/context_engine/tracks/`
- **Feature folders**: `user/products/{org}/{product}/{feature}/`

---

*Part of PM-OS v3.2.1 - Context Creation Engine*
