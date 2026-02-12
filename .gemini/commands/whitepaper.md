# Strategic Proposal (Whitepaper Style)

Create persuasive strategic documents for organizational or product proposals, with optional FPF structured reasoning for rigorous option evaluation.

## Arguments
$ARGUMENTS

## Mode Selection

- **Standard mode:** `/whitepaper <topic>` - Direct document generation
- **FPF mode:** `/whitepaper --fpf <topic>` - Structured reasoning with hypothesis evaluation
- **Orthogonal mode:** `/whitepaper --orthogonal <topic>` - 3-round Claude vs Gemini challenge

---

## Standard Mode

Generate a strategic proposal directly following the structure below.

---

## FPF Mode: Strategic Reasoning

For strategic proposals requiring systematic option evaluation:

### Phase 1: Problem Analysis

1. Initialize FPF cycle:
   ```
   /q0-init
   ```

2. Generate strategic hypotheses:
   ```
   /q1-hypothesize "What strategic options exist for '$ARGUMENTS'? Consider different approaches, resource allocations, and market positioning."
   ```

3. Verify strategic feasibility:
   ```
   /q2-verify
   ```
   - Check alignment with organizational constraints
   - Validate resource requirements
   - Assess market timing

### Phase 2: Evidence Gathering

4. Validate with evidence:
   ```
   /q3-validate
   ```
   - Research competitor strategies
   - Gather internal metrics and feedback
   - Review industry benchmarks
   - Check Brain for related decisions

### Phase 3: Decision & Documentation

5. Audit for bias:
   ```
   /q4-audit
   ```

6. Create DRR:
   ```
   /q5-decide
   ```

7. Generate whitepaper with FPF enhancements:
   - Include **Decision Rationale** section from DRR
   - Add **Strategic Alternatives** with evaluation scores
   - Show **Evidence Chain** with assurance levels
   - Note **Conditions for Revisiting** (evidence expiry)

8. Sync to Brain:
   ```
   /quint-sync --to-brain
   ```

---

## Orthogonal Mode: 3-Round Challenge

For strategic proposals requiring rigorous multi-perspective validation:

1. Run the orthogonal challenge system:
   ```bash
   python3 "$PM_OS_COMMON/tools/quint/orthogonal_challenge.py" --type prd --topic "$ARGUMENTS"
   ```
   Note: Uses PRD template which includes strategic proposal sections.

2. This will execute:
   - **Round 1 (Claude):** Create initial proposal with research + FPF reasoning
   - **Round 2 (Gemini):** Challenge assumptions, stress-test strategy, propose alternatives
   - **Round 3 (Claude):** Resolve challenges, produce final whitepaper

3. Wait for completion (5-15 minutes)

4. Report outputs:
   - Final Whitepaper: `Brain/Reasoning/Orthogonal/<id>/v3_final.md`
   - Challenge FAQ: Shows all challenges and resolutions
   - DRR: Stored in `Brain/Reasoning/Decisions/`

---

## Structure

### 1. Purpose / Executive Summary
- What this document proposes
- Why it matters now
- **[FPF Mode]:** Summary of DRR decision

### 2. Current State / Problem
- Existing situation analysis
- Pain points and gaps
- Evidence (metrics, feedback, competitive pressure)

### 3. Strategic Options Evaluated (FPF Mode)
- **Option A:** [Description] - L2 Verified | R_eff: X.XX
- **Option B:** [Description] - L1 Substantiated | R_eff: X.XX
- **Option C:** [Description] - Invalid | Reason: [...]

### 4. Strategic Solution (Selected)
- Proposed approach
- Key mechanisms and how they work
- Organizational/process design implications
- **[FPF Mode]:** Why this option won (WLNK analysis)

### 5. Recommendations / Roadmap
- Phased implementation plan
- Key milestones
- Success metrics

### 6. Decision Rationale (FPF Mode)
- DRR reference: `Brain/Reasoning/Decisions/drr-YYYY-MM-DD-topic.md`
- Evidence expiry dates
- Conditions for revisiting decision

## Writing Style
- **Persuasive & Visionary** - focus on mechanisms, ecosystems, paradigm shifts
- **Evidence-Based** - cite frameworks (DIBB, ICE) or external models (Amazon, Spotify)
- **Structured** - use headers and bullets for skimmability
- **Outcome-Focused** - tie everything to business impact

## Template
```markdown
# [Proposal Title]

*[One-line purpose statement]*

## Executive Summary
[2-3 bullets on what/why/impact]

## Current State
### Situation
- [Current approach]
- [Pain points]

### Evidence
- [Metrics/data]
- [Stakeholder feedback]

## Strategic Options Evaluated
| Option | Assurance | R_eff | Status |
|--------|-----------|-------|--------|
| [Option A] | L2 | 0.85 | **Selected** |
| [Option B] | L1 | 0.72 | Viable alternative |
| [Option C] | Invalid | - | Rejected: [reason] |

## Strategic Solution
### Approach
[Description of proposed solution]

### Key Mechanisms
- **[Mechanism 1]:** [How it works]
- **[Mechanism 2]:** [How it works]

### Organizational Impact
[Process/team changes required]

## Recommendations
### Phase 1: [Name]
- [Actions]
- **Success Metric:** [KPI]

### Phase 2: [Name]
- [Actions]
- **Success Metric:** [KPI]

## Decision Rationale
- **DRR:** [[Brain/Reasoning/Decisions/drr-YYYY-MM-DD-topic.md]]
- **Evidence expires:** YYYY-MM-DD
- **Revisit if:** [conditions]

---
*Author: [Name] | Date: [YYYY-MM-DD] | Status: Draft*
```

## Examples

**Standard:**
- `/whitepaper Platform consolidation strategy for Growth Division`
- `/whitepaper Creator economy integration proposal`

**FPF Mode:**
- `/whitepaper --fpf Build vs. Buy decision for payment processing`
- `/whitepaper --fpf Market expansion strategy for DACH region`

**Orthogonal Mode (rigorous):**
- `/whitepaper --orthogonal AI-first product development strategy`
- `/whitepaper --orthogonal Multi-brand platform architecture vision`

## Notes

- Standard mode: 5-10 minutes
- FPF mode: 15-30 minutes (full reasoning cycle)
- Orthogonal mode: 10-20 minutes (3-round challenge)
- Use Orthogonal for strategic proposals with significant organizational impact

What strategic initiative should we document?
