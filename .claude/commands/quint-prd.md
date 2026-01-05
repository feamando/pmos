# FPF-Enhanced PRD Generation

Generate a PRD using structured FPF reasoning for solution analysis.

## Arguments
$ARGUMENTS

## Instructions

### Phase 1: Problem Framing

1. **Initialize FPF cycle:**
   ```
   /q0-init
   ```

2. **Generate problem hypotheses:**
   ```
   /q1-hypothesize "What is the core problem $ARGUMENTS is solving?"
   ```

3. **Verify problem scope:**
   ```
   /q2-verify
   ```

### Phase 2: Solution Analysis

4. **Generate solution hypotheses:**
   ```
   /q1-hypothesize "What are the viable solutions for $ARGUMENTS?"
   ```

5. **Verify technical feasibility:**
   ```
   /q2-verify
   ```

6. **Validate with evidence:**
   ```
   /q3-validate
   ```
   - Research competitors
   - Check existing implementations
   - Review technical constraints

### Phase 3: Decision

7. **Audit for bias:**
   ```
   /q4-audit
   ```

8. **Create DRR:**
   ```
   /q5-decide
   ```

### Phase 4: Generate PRD

9. **Run standard PRD generation with FPF context:**
   ```
   /prd $ARGUMENTS
   ```

   The PRD will include:
   - **Decision Rationale** section from DRR
   - **Alternatives Considered** from hypotheses
   - **Evidence** from validation phase
   - **Assurance Level** for key claims

10. **Sync to Brain:**
    ```
    /quint-sync --to-brain
    ```

## Output

- PRD document with embedded FPF reasoning
- DRR in `Brain/Reasoning/Decisions/`
- Evidence archive in `Brain/Reasoning/Evidence/`
