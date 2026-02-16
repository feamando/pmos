# 4CQ Project Definition

Rapid alignment framework before full specs. Use for quick project scoping with optional orthogonal challenge.

## Arguments
$ARGUMENTS

## Instructions

The user wants to create a 4CQ (Four Critical Questions) document. Parse their request:

### Mode Selection

Check for flags:
- **Standard mode:** `/4cq <project topic>` - Quick alignment document
- **Orthogonal mode:** `/4cq --orthogonal <topic>` - 3-round Claude vs Gemini challenge

---

## The 4 Critical Questions

1. **Who is the customer?** (Persona)
   - Define the target user segment
   - Include relevant context (new vs existing, behavior patterns)

2. **What is the problem?** (Pain point)
   - Specific pain point or unmet need
   - Evidence/data supporting this problem exists

3. **What is the solution?** (Hypothesis/Prototype)
   - High-level solution approach
   - Key features or changes proposed

4. **What is the primary benefit?** (Value prop)
   - Single most important outcome
   - How success will be measured

---

## Standard Mode

For quick project alignment:

1. Gather context from Brain and available sources
2. Generate 4CQ document with answers to all four questions
3. Include evidence where available
4. Output in standard format

---

## Orthogonal Mode: 3-Round Challenge

For projects requiring rigorous scoping validation:

1. Run the orthogonal challenge system:
   ```bash
   python3 "$PM_OS_COMMON/tools/quint/orthogonal_challenge.py" --type 4cq --topic "$ARGUMENTS"
   ```

2. This will execute:
   - **Round 1 (Claude):** Create initial 4CQ with research + FPF reasoning
   - **Round 2 (Gemini):** Challenge customer definition, problem evidence, solution fit
   - **Round 3 (Claude):** Resolve challenges, produce final 4CQ

3. Wait for completion (5-10 minutes)

4. Report outputs:
   - Final 4CQ: `Brain/Reasoning/Orthogonal/<id>/v3_final.md`
   - Challenge FAQ: Shows all challenges and resolutions
   - DRR: Stored in `Brain/Reasoning/Decisions/`

---

## Output Format

```markdown
# 4CQ: [Project Name]

## 1. Customer
**Who is the customer?**

### Primary Persona
- **Name:** [Persona name]
- **Segment:** [New/Existing/Churned]
- **Size:** [Market size]

### Jobs to be Done
1. [Job 1]
2. [Job 2]

## 2. Problem
**What is the problem?**

### Problem Statement
> [One sentence problem statement]

### Evidence
| Source | Finding | Confidence |
|--------|---------|------------|
| [Source] | [Insight] | High/Med/Low |

### Why Now?
[Urgency driver]

## 3. Solution
**What is the solution?**

### Hypothesis
> If we [solution], then [outcome], because [rationale].

### Key Features (MVP)
| Feature | Description | Priority |
|---------|-------------|----------|
| [Feature] | [What] | Must/Should/Could |

### What This Is NOT
- [Out of scope 1]
- [Out of scope 2]

## 4. Primary Benefit
**What is the primary benefit?**

### Value Proposition
> [Single most important outcome]

### Success Metric
| Metric | Baseline | Target | Timeframe |
|--------|----------|--------|-----------|
| [KPI] | [Current] | [Goal] | [When] |

---

## Challenge FAQ (Orthogonal Mode)
*Populated when using --orthogonal flag*

### Q: [Challenge]
**A:** [Resolution]

---
*Status: Draft | Owner: [Name] | Date: [YYYY-MM-DD]*
```

## Examples

**Standard:**
- `/4cq Push notifications for BB app`
- `/4cq One-time purchase for Factor meals`
- `/4cq Loyalty program for Acme Corp`

**Orthogonal (rigorous):**
- `/4cq --orthogonal New market expansion strategy`
- `/4cq --orthogonal Platform consolidation proposal`

## Notes

- Standard mode: 2-5 minutes
- Orthogonal mode: 5-10 minutes (3-round challenge)
- Use orthogonal for complex projects with unclear scope
- 4CQ is meant for quick alignment - expand to PRD after approval

What project should we define?
