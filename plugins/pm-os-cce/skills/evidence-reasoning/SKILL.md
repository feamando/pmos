---
description: When reasoning about decisions, claims, or analyses, always use evidence-based FPF reasoning with explicit confidence levels CL1-CL4
---

# Evidence-Based Reasoning (FPF)

## When to Apply
- Any decision or recommendation is being made
- User asks "should we..." or "what's the best..." questions
- Claims need to be validated or challenged
- Feature workflow requires evidence-backed outputs (PRDs, gate reviews)

## What to Do

### 1. Always State Confidence Levels
Every claim, finding, or recommendation must carry a confidence level:

| Level | Name | Criteria | Example |
|-------|------|----------|---------|
| **CL4** | Verified | Multiple independent sources, no counter-evidence | "Revenue impact confirmed by A/B test and finance review" |
| **CL3** | High | Strong evidence from authoritative source, minimal counter | "User pain point validated by 15 interview quotes" |
| **CL2** | Medium | Some evidence, possible gaps | "Competitor pricing estimated from public data" |
| **CL1** | Low | Limited evidence, significant uncertainty | "Market size based on single analyst report" |

### 2. Evidence Chain
For each recommendation:
- List supporting evidence with sources and CL levels
- List counter-evidence (never omit it)
- Identify gaps -- what evidence would increase confidence
- Note evidence freshness -- stale data (>30 days) gets CL downgrade

### 3. Orthogonal Challenge
Before finalizing any recommendation:
- Challenge from at least one orthogonal perspective
- Ask "what would make this wrong?"
- Check for cognitive biases:
  - **Confirmation bias** -- only seeking supporting evidence
  - **Availability bias** -- over-weighting recent/memorable data
  - **Anchoring** -- fixating on first data point
  - **Sunk cost** -- continuing because of past investment
  - **Survivorship bias** -- only looking at successes

### 4. Decision Readiness
A decision is ready when:
- At least 3 pieces of evidence at CL2+
- No unaddressed CL3+ counter-evidence
- Orthogonal challenge completed
- Gaps identified and accepted or filled

### 5. Confidence Decay
Evidence confidence decays over time:
- Market data: -1 CL after 30 days
- User research: -1 CL after 90 days
- Technical feasibility: -1 CL after 60 days
- Competitive intelligence: -1 CL after 14 days

## Tools Used
- `tools/reasoning/fpf_engine.py` -- Full FPF reasoning pipeline
- `tools/reasoning/orthogonal_challenge.py` -- Bias and challenge detection
- `tools/reasoning/framework_matcher.py` -- Framework-guided reasoning

## Examples

<example>
User: "We should launch feature X next quarter"
Assistant: [does NOT just agree; instead evaluates: supporting evidence (CL3: user research shows demand), counter-evidence (CL2: engineering estimates show 2-quarter timeline), gaps (no competitive analysis), orthogonal challenge (what if demand shifts?), final assessment: CL2 confidence, needs more evidence before committing]
</example>

<example>
User: "What's our biggest risk?"
Assistant: [gathers evidence from Brain entities, ranks risks by evidence strength, flags where confidence is low (CL1-CL2), recommends specific evidence to collect to increase confidence, provides decision with explicit CL levels per risk]
</example>
