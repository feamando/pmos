# PRD Generator

Generate or update a PRD using Deep Research, with optional FPF structured reasoning.

## Arguments
$ARGUMENTS

## Instructions

The user wants to generate or update a PRD. Parse their request:

### Mode Selection

Check if the user wants FPF reasoning:
- **Standard mode:** `/prd <topic>` - Fast Deep Research generation
- **FPF mode:** `/prd --fpf <topic>` or `/prd <topic> --fpf` - Structured reasoning with hypothesis evaluation

---

### Standard Mode: Deep Research PRD

For quick PRD generation without FPF:

1. Run the PRD generator:
   ```bash
   python3 AI_Guidance/Tools/deep_research/prd_generator.py --topic "$ARGUMENTS"
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
   python3 AI_Guidance/Tools/deep_research/prd_generator.py --topic "$ARGUMENTS"
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

### For PRD Updates

Parse file path and instructions:
```bash
python3 AI_Guidance/Tools/deep_research/prd_generator.py --update <filepath> --instructions "<instructions>"
```

### First-Time Setup
```bash
python3 AI_Guidance/Tools/deep_research/prd_generator.py --setup
```

## Examples

**Standard:**
- `/prd Add push notifications to TPT mobile app`
- `/prd OTP checkout flow for Good Chop`

**FPF Mode:**
- `/prd --fpf Architecture for multi-tenant subscription system`
- `/prd --fpf Payment gateway migration strategy`

**Updates:**
- `/prd Products/Good_Chop/OTP_PRD.md --update Add competitive analysis section`

## Notes

- Standard mode: 2-5 minutes (Deep Research)
- FPF mode: 15-30 minutes (full reasoning cycle)
- Use FPF for architectural decisions with long-term consequences
- DRRs are stored in `Brain/Reasoning/Decisions/`
