# ADR Generator

Generate an Architecture Decision Record with optional orthogonal challenge.

## Arguments
$ARGUMENTS

## Instructions

The user wants to generate an ADR (Architecture Decision Record). Parse their request:

### Mode Selection

Check for flags:
- **Standard mode:** `/adr <decision topic>` - Generate with FPF reasoning
- **Orthogonal mode:** `/adr --orthogonal <topic>` - 3-round Claude vs Gemini challenge

---

### Standard Mode: ADR with FPF Reasoning

For architecture decisions requiring documented rationale:

#### Phase 1: Context Gathering

1. Initialize FPF cycle:
   ```
   /q0-init
   ```

2. Research existing architecture:
   - Search Brain for related decisions
   - Check codebase for current implementation
   - Review Confluence for architectural docs

3. Generate decision hypotheses:
   ```
   /q1-hypothesize "What are the viable approaches for '$ARGUMENTS'? Consider trade-offs, constraints, and alignment with existing architecture."
   ```

#### Phase 2: Evaluation

4. Verify technical feasibility:
   ```
   /q2-verify
   ```

5. Validate with evidence:
   ```
   /q3-validate
   ```
   - Research similar decisions at other companies
   - Check for known pitfalls
   - Consult existing team expertise

6. Audit for bias:
   ```
   /q4-audit
   ```

#### Phase 3: Decision

7. Create ADR:
   ```bash
   python3 "$PM_OS_COMMON/tools/documents/template_manager.py" --type adr --render --fpf
   ```

8. Populate the ADR with:
   - **Context:** Why this decision is needed now
   - **Decision:** The chosen approach
   - **Consequences:** Both positive and negative
   - **Alternatives Considered:** Other options and why rejected
   - **DRR Reference:** Link to reasoning in Brain

9. Create Design Rationale Record:
   ```
   /q5-decide
   ```

10. Save to appropriate location (suggest Brain/Reasoning/Decisions/)

---

### Orthogonal Mode: 3-Round Challenge

For high-stakes architectural decisions requiring rigorous validation:

1. Run the orthogonal challenge system:
   ```bash
   python3 "$PM_OS_COMMON/tools/quint/orthogonal_challenge.py" --type adr --topic "$ARGUMENTS"
   ```

2. This will execute:
   - **Round 1 (Claude):** Create initial ADR with research + FPF reasoning
   - **Round 2 (Gemini):** Challenge assumptions, identify gaps, propose alternatives
   - **Round 3 (Claude):** Resolve challenges, produce final ADR

3. Wait for completion (5-15 minutes)

4. Report outputs:
   - Final ADR: `Brain/Reasoning/Orthogonal/<id>/v3_final.md`
   - Challenge FAQ: Shows all challenges and resolutions
   - DRR: Stored in `Brain/Reasoning/Decisions/`

---

### ADR Template Sections

The generated ADR will include:

1. **Title:** Short summary of decision
2. **Status:** Draft / Proposed / Accepted / Deprecated / Superseded
3. **Context:** Why is this decision needed?
4. **Decision:** What is the change being proposed?
5. **Consequences:** What becomes easier/harder?
6. **Options Considered:** What alternatives were evaluated?
7. **Validation:** Evidence supporting the decision
8. **Decision Rationale (FPF Mode):** DRR reference and assurance level
9. **Challenge FAQ (Orthogonal Mode):** Q&A from challenge process

## Examples

**Standard:**
- `/adr Migrate from monolith to microservices for checkout`
- `/adr Use PostgreSQL vs MongoDB for subscription data`
- `/adr Adopt Next.js for frontend framework`

**Orthogonal (rigorous):**
- `/adr --orthogonal Multi-region deployment strategy`
- `/adr --orthogonal Authentication architecture redesign`
- `/adr --orthogonal Data lake vs warehouse for analytics`

## Notes

- Standard mode: 5-10 minutes (FPF reasoning)
- Orthogonal mode: 10-20 minutes (3-round challenge)
- Use orthogonal for irreversible or expensive decisions
- ADRs are immutable once accepted - create new ADR to supersede
- Store in `Brain/Reasoning/Decisions/` or project-specific location
