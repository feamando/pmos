---
description: When working on product features, follow the 5-phase feature lifecycle from Discovery through Data, with phase gates and evidence requirements
---

# Feature Workflow

## When to Apply
- User starts work on a new feature or initiative
- User is in the middle of feature development
- User asks about feature phases, gates, or progress
- Any `/feature` command is executed

## Feature Lifecycle Phases

### Phase 1: Discovery
**Goal:** Understand the problem space and validate opportunity.

| Activity | Output | Tool |
|----------|--------|------|
| Problem framing | Problem statement | `/reason init` |
| User research | Research findings | `/doc meeting-notes`, research skill |
| Market analysis | Competitive landscape | research skill |
| Opportunity sizing | TAM/SAM/SOM estimate | `/reason add` evidence |
| Stakeholder mapping | Stakeholder map | Brain entity lookup |

**Gate Criteria:**
- Problem statement with CL3+ evidence
- At least 5 user research data points
- Opportunity size estimated
- Key stakeholders identified

### Phase 2: Definition
**Goal:** Define what to build and why.

| Activity | Output | Tool |
|----------|--------|------|
| Requirements | PRD | `/doc prd` |
| Success metrics | Metric definitions | `/reason add` |
| Technical feasibility | Feasibility assessment | research skill |
| Prioritization | RICE/framework score | `/reason` + framework skill |
| Decision | Go/No-go decision | `/reason decide` |

**Gate Criteria:**
- PRD approved
- Success metrics defined with baselines
- Technical feasibility at CL3+
- Go decision at CL3+

### Phase 3: Design
**Goal:** Design the solution and validate with users.

| Activity | Output | Tool |
|----------|--------|------|
| Wireframes | Design artifacts | `/feature prototype` |
| Technical design | Architecture document | `/doc rfc` or `/doc adr` |
| Edge case analysis | Edge case document | `/reason` reasoning |
| User validation | Usability findings | research skill |
| Spec export | Confluence/Jira spec | `/doc export-to-spec` |

**Gate Criteria:**
- Prototype reviewed with users
- Technical design approved
- Edge cases documented
- Spec exported to team wiki

### Phase 4: Delivery
**Goal:** Build, test, and ship.

| Activity | Output | Tool |
|----------|--------|------|
| Story creation | Jira stories | `/roadmap create-story` |
| Task breakdown | Jira tasks | `/roadmap create-task` |
| Progress tracking | Status updates | `/feature status` |
| Risk monitoring | Risk updates | `/reason` |
| Launch prep | Rollout plan | `/doc documentation` |

**Gate Criteria:**
- All stories completed
- Tests passing
- Rollout plan approved
- Monitoring configured

### Phase 5: Data
**Goal:** Measure impact and capture learnings.

| Activity | Output | Tool |
|----------|--------|------|
| Metric collection | Dashboard/report | analysis tools |
| Hypothesis validation | Results analysis | `/reason verify` |
| Learning capture | Retrospective | `/doc meeting-notes` |
| Brain update | Updated entities | Brain MCP tools |
| Decision record | ADR | `/doc adr` |

**Gate Criteria:**
- Metrics collected for at least 2 weeks
- Hypothesis validated or invalidated with evidence
- Learnings captured in Brain
- ADR recorded for key decisions

## Phase Transitions

Moving between phases requires a gate review (`/feature gate`):
1. Validate all gate criteria for current phase
2. Identify any gaps and their severity
3. Gate verdict: PASS (advance), CONDITIONAL (advance with noted gaps), FAIL (stay and address gaps)
4. If PASS or CONDITIONAL: advance phase and set up next phase workspace

## Context Continuity

Feature context persists across sessions:
- `/feature resume` restores full context
- Brain entities linked to feature stay current
- FPF reasoning state preserved
- All artifacts accessible via `/feature outputs`

## Tools Used
- `tools/feature/feature_engine.py` -- Feature lifecycle management
- `tools/feature/feature_state.py` -- State persistence
- `tools/feature/context_doc_generator.py` -- Context management
- `tools/prototype/prototype_engine.py` -- Prototype generation
- `tools/reasoning/fpf_engine.py` -- Evidence-based reasoning
- `tools/integration/jira_integration.py` -- Jira synchronization

## Examples

<example>
User: "/feature start 'Smart Recommendations'"
Assistant: [creates feature workspace, enters Discovery phase, loads Brain context for recommendation-related entities, suggests first research questions, sets up FPF session]
</example>

<example>
User: "/feature gate"
Assistant: [checks current phase (Definition), validates gate criteria: PRD exists (pass), metrics defined (pass), technical feasibility (CL2 - warning: needs more evidence), go decision (not yet made - fail), verdict: FAIL - need feasibility evidence and go decision before advancing to Design]
</example>
