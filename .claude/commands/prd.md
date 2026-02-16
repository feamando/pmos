# PRD Generator

Generate or update a PRD using Deep Research, with optional FPF structured reasoning or orthogonal challenge.

## Arguments
$ARGUMENTS

## Instructions

The user wants to generate or update a PRD. Parse their request:

### Mode Selection

Check for flags:
- **Standard mode:** `/prd <topic>` - Fast Deep Research generation
- **FPF mode:** `/prd --fpf <topic>` - Structured reasoning with hypothesis evaluation
- **Orthogonal mode:** `/prd --orthogonal <topic>` - 3-round Claude vs Gemini challenge

---

### Standard Mode: Deep Research PRD

For quick PRD generation without FPF:

1. Run the PRD generator:
   ```bash
   python3 "$PM_OS_COMMON/tools/deep_research/prd_generator.py" --topic "$ARGUMENTS"
   ```

2. Wait for generation (2-5 minutes)

3. Report output file and offer review

---

### FPF Mode: Structured Reasoning PRD

For complex PRDs requiring auditable decision-making:

#### Phase 1: Problem Framing

1. Initialize FPF cycle:
   ```
   /q0-init
   ```

2. Generate problem hypotheses:
   ```
   /q1-hypothesize "What is the core problem '$ARGUMENTS' is solving? What user needs does it address?"
   ```

3. Verify problem scope:
   ```
   /q2-verify
   ```

#### Phase 2: Solution Analysis

4. Generate solution hypotheses:
   ```
   /q1-hypothesize "What are the viable solutions for '$ARGUMENTS'? Consider technical approaches, UX patterns, and competitive alternatives."
   ```

5. Verify technical feasibility:
   ```
   /q2-verify
   ```

6. Validate with evidence:
   ```
   /q3-validate
   ```
   - Research competitors and prior art
   - Check existing implementations in codebase
   - Review Brain for related decisions

#### Phase 3: Decision

7. Audit for bias:
   ```
   /q4-audit
   ```

8. Create Design Rationale Record:
   ```
   /q5-decide
   ```

#### Phase 4: Generate PRD with DRR

9. Run PRD generator with FPF context:
   ```bash
   python3 "$PM_OS_COMMON/tools/deep_research/prd_generator.py" --topic "$ARGUMENTS"
   ```

10. Enhance the generated PRD with FPF sections:
    - **Decision Rationale:** Summarize the DRR
    - **Alternatives Considered:** List evaluated hypotheses
    - **Evidence:** Link to validation sources
    - **Assurance Level:** Note L2 claims and confidence

11. Sync reasoning to Brain:
    ```
    /quint-sync --to-brain
    ```

---

### Orthogonal Mode: 3-Round Challenge

For high-stakes PRDs requiring rigorous validation across multiple perspectives:

1. Run the orthogonal challenge system:
   ```bash
   python3 "$PM_OS_COMMON/tools/quint/orthogonal_challenge.py" --type prd --topic "$ARGUMENTS"
   ```

2. This will execute:
   - **Round 1 (Claude):** Create initial PRD with research + FPF reasoning
   - **Round 2 (Gemini):** Challenge assumptions, identify gaps, propose alternatives
   - **Round 3 (Claude):** Resolve challenges, produce final PRD

3. Wait for completion (5-15 minutes)

4. Report outputs:
   - Final PRD: `Brain/Reasoning/Orthogonal/<id>/v3_final.md`
   - Challenge FAQ: Shows all challenges and resolutions
   - DRR: Stored in `Brain/Reasoning/Decisions/`

5. The final PRD includes:
   - **Decision Rationale:** DRR reference with assurance levels
   - **Challenge FAQ:** All challenges raised and how they were resolved
   - **Confidence levels:** Per-section confidence assessments
   - **Conditions for revisiting:** When to reconsider this PRD

---

### For PRD Updates

Parse file path and instructions:
```bash
python3 "$PM_OS_COMMON/tools/deep_research/prd_generator.py" --update <filepath> --instructions "<instructions>"
```

### First-Time Setup
```bash
python3 "$PM_OS_COMMON/tools/deep_research/prd_generator.py" --setup
```

## Examples

**Standard:**
- `/prd Add push notifications to BB mobile app`
- `/prd OTP checkout flow for Meal Kit`

**FPF Mode:**
- `/prd --fpf Architecture for multi-tenant subscription system`
- `/prd --fpf Payment gateway migration strategy`

**Orthogonal Mode (rigorous):**
- `/prd --orthogonal New subscription model for Growth Platform`
- `/prd --orthogonal Cross-selling platform architecture`

**Updates:**
- `/prd Products/Meal_Kit/OTP_PRD.md --update Add competitive analysis section`

## Notes

- Standard mode: 2-5 minutes (Deep Research)
- FPF mode: 15-30 minutes (full reasoning cycle)
- Orthogonal mode: 10-20 minutes (3-round challenge)
- Use FPF for architectural decisions with long-term consequences
- Use Orthogonal for high-stakes PRDs requiring multi-perspective validation
- DRRs are stored in `Brain/Reasoning/Decisions/`
