# RFC Generator

Generate a Request for Comments document with optional orthogonal challenge.

## Arguments
$ARGUMENTS

## Instructions

The user wants to generate an RFC (Request for Comments) for a technical proposal. Parse their request:

### Mode Selection

Check for flags:
- **Standard mode:** `/rfc <proposal topic>` - Generate with FPF reasoning
- **Orthogonal mode:** `/rfc --orthogonal <topic>` - 3-round Claude vs Gemini challenge

---

### Standard Mode: RFC with FPF Reasoning

For technical proposals requiring team discussion:

#### Phase 1: Research

1. Initialize FPF cycle:
   ```
   /q0-init
   ```

2. Gather context:
   - Search Brain for related projects and decisions
   - Check codebase for existing implementations
   - Review Jira for related tickets
   - Search Confluence for prior discussions

3. Generate approach hypotheses:
   ```
   /q1-hypothesize "What are the design options for '$ARGUMENTS'? Consider technical feasibility, team capacity, and timeline."
   ```

#### Phase 2: Design

4. Verify design feasibility:
   ```
   /q2-verify
   ```

5. Validate with evidence:
   ```
   /q3-validate
   ```
   - Check for prior art in industry
   - Review similar RFCs from other teams
   - Identify affected stakeholders

6. Audit for completeness:
   ```
   /q4-audit
   ```

#### Phase 3: Generate RFC

7. Create RFC document:
   ```bash
   python3 "$PM_OS_COMMON/tools/documents/template_manager.py" --type rfc --render --fpf
   ```

8. Populate the RFC with:
   - **Summary:** One-paragraph overview
   - **Motivation:** Why is this needed?
   - **Proposal:** Detailed technical design
   - **Drawbacks:** Known limitations
   - **Alternatives:** Other options considered
   - **Testing Strategy:** How to validate
   - **Rollout Plan:** Implementation phases

9. Create Design Rationale Record:
   ```
   /q5-decide
   ```

---

### Orthogonal Mode: 3-Round Challenge

For significant technical changes requiring rigorous validation:

1. Run the orthogonal challenge system:
   ```bash
   python3 "$PM_OS_COMMON/tools/quint/orthogonal_challenge.py" --type rfc --topic "$ARGUMENTS"
   ```

2. This will execute:
   - **Round 1 (Claude):** Create initial RFC with research + FPF reasoning
   - **Round 2 (Gemini):** Challenge design, identify edge cases, propose alternatives
   - **Round 3 (Claude):** Resolve challenges, produce final RFC

3. Wait for completion (5-15 minutes)

4. Report outputs:
   - Final RFC: `Brain/Reasoning/Orthogonal/<id>/v3_final.md`
   - Challenge FAQ: Shows all challenges and resolutions
   - DRR: Stored in `Brain/Reasoning/Decisions/`

---

### RFC Template Sections

The generated RFC will include:

1. **Metadata:** RFC ID, Author, Status, Stakeholders
2. **Summary:** Brief overview
3. **Motivation:** Problem being solved
4. **Detailed Design:** Technical specification
5. **Drawbacks:** Why we might NOT want this
6. **Alternatives:** Other approaches considered
7. **Unresolved Questions:** Open items for discussion
8. **Testing Strategy:** Validation approach
9. **Rollout Plan:** Phased implementation
10. **Decision Rationale (FPF Mode):** DRR reference
11. **Challenge FAQ (Orthogonal Mode):** Q&A from challenge process

## Examples

**Standard:**
- `/rfc Implement GraphQL federation for microservices`
- `/rfc Add real-time notifications via WebSocket`
- `/rfc Introduce feature flags system`

**Orthogonal (rigorous):**
- `/rfc --orthogonal Database sharding strategy for scale`
- `/rfc --orthogonal Event-driven architecture migration`
- `/rfc --orthogonal Zero-downtime deployment pipeline`

## Notes

- Standard mode: 5-10 minutes (FPF reasoning)
- Orthogonal mode: 10-20 minutes (3-round challenge)
- Use orthogonal for changes affecting multiple teams
- RFCs should invite feedback before implementation
- Share with stakeholders for async discussion
