---
description: Full end-to-end initiative pipeline — from idea to Engineering Discovery Kickoff with solution paths and specs
---

# Spec Pipeline

Master pipeline orchestrating /spec-brief + /export-to-spec + Spec Machine to produce a complete Engineering Discovery Kickoff package.

## When to Apply

- User wants a full spec package for an initiative
- User has an approved brief and wants to generate the full discovery kickoff
- User says "build the spec" or "run the pipeline"

## Protocol

### Phase 1: Brief (skip if approved brief provided)

Run spec-brief logic: context gathering, canonical metrics, brief with problem + scenarios + solution space + questions + reviewers + concept visual.

Save to: `specs/YYYY-MM-DD-<initiative>/planning/brief.md`

### Phase 2: Solution Path Development

For each solution path (3 minimum):

1. **Solution path document** (`solution-paths/path-X.md`):
   - Approach (2-3 paragraphs)
   - UX Impact (what changes, which scenarios benefit)
   - Business Value (how it moves the metric)
   - Open Questions for Engineering (questions, not assertions)
   - Open Questions for Design

### Phase 3: Export to Spec

1. Export the brief and solution paths to the spec format via /export-to-spec
2. Create `planning/requirements.md` in Q&A format

### Phase 4: Spec Machine Deep Dive

1. Run spec-machine against the exported requirements
2. Save to `reference/spec.md` + `reference/tasks.md`
3. Flag any task >3 days

### Phase 5: README Assembly

Create **Engineering Discovery Kickoff** (`README.md`) with:
- Problem (metric-anchored)
- User Scenarios (matrix from brief)
- Solution Paths (summary + key question each)
- Open Questions (consolidated, categorized: Technical/Data/UX/Business)
- Complexity Estimates table (engineering to fill — NEVER fill yourself)
- Measurement Plan (primary/secondary/guardrail metrics)
- Review Status table

### Phase 6: Verification

All checks must pass:
- No `_pending_` in PM-owned fields
- Canonical metric cited with source and date
- Open questions framed as questions
- No effort/timeline estimates from PM side
- Tasks >3 days flagged

### Phase 7: Deliver

Report output structure. **Do NOT auto-push to git.** Ask user first.

## Output Structure

```
specs/YYYY-MM-DD-<initiative>/
├── README.md                    ← PRIMARY artifact
├── planning/                    ← Brief + concept visual + requirements
├── solution-paths/              ← UX + business value + questions
└── reference/                   ← spec.md + tasks.md
```

## Optional: /wireframe for Early Exploration

Use /wireframe as a standalone tool for early concept exploration — before or outside the pipeline. It generates interactive HTML wireframes to visualize ideas quickly. It is NOT a required step in this pipeline; use it when you want to explore a concept visually before committing to a full spec.

## Rules

- **Single-phase.** No approval gates. Produce everything, user reviews complete output.
- **README is primary.** spec.md is reference material.
- **No solutionizing in the brief.** Solution paths come in Phase 2.
- **No effort estimates.** Complexity table is for engineering.
- **Questions, not assertions.**
- **Date every source.** Flag >30 days.
