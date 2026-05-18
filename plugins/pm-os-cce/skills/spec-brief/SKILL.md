---
description: Generate a problem-framing brief for a new initiative — search context, anchor on metrics, open the solution space
---

# Spec Brief

Problem framing for new or abstract initiative ideas. Searches PM-OS for context, anchors on canonical metrics, produces a brief with divergent solution space and concept visual.

## When to Apply

- User has an idea (one-liner, rough notes, roadmap item, abstract concept)
- User asks to "frame the problem" or "write a brief"
- Starting discovery for a new initiative

## Protocol

### Step 1: Context Gathering

Search PM-OS sources for everything relevant:
1. **Brain** (`user/brain/`) — entities, relationships, prior context
2. **Daily context** (`user/personal/context/`) — recent discussions
3. **Product docs** (`user/products/`) — existing related work
4. **Sessions** — past working sessions on this topic
5. **Google Docs** — search Drive if local sources are thin

### Step 2: Find Canonical Metrics Source

Discover the right metrics source for THIS initiative (don't hardcode):
- Once found: read it, extract metric(s), note date, quote exact number with attribution
- If no baseline exists: flag "No baseline exists. Measurement plan is the first deliverable."

### Step 3: Write the Brief

Structure:

1. **Problem** — Metric-anchored: `**[Metric]** is **[value]** (source: [doc], [date]).`
2. **User Scenarios** — Minimum 2x2 matrix (warm/cold x profile/no-profile or initiative-specific)
3. **Solution Space** — 3-5 DIVERGENT approaches. No ranking. No recommendations. No effort estimates.
4. **Open Questions** — Framed as QUESTIONS not assertions. Categories: Technical, Data, UX, Business.
5. **Review Needed From** — Table with reviewer, what they review, status.

### Step 4: Generate Concept Visual

One rough concept visual (optional — invoke /wireframe separately if needed):
- Shows core idea, not polished design
- Covers all user scenario quadrants
- Conversation starter, not a spec

### Step 5: Output Summary

Report: paths saved, canonical metric cited, open question count, next step (`/spec-pipeline` for full kickoff).

## Rules

- **No solutionizing.** Open the solution space, don't narrow it.
- **No effort/timeline estimates.** That's engineering's job.
- **Canonical metrics only.** Never cite an individual's spreadsheet.
- **Questions, not assertions** for feasibility.
- **Date every source.** Flag >30 days as potentially stale.
- **Intellectual honesty** — if you lack data, say so.
