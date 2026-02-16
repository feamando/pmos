# BC Generator

Generate a Business Case document with optional orthogonal challenge.

## Arguments
$ARGUMENTS

## Instructions

The user wants to generate a Business Case (BC) for investment justification. Parse their request:

### Mode Selection

Check for flags:
- **Standard mode:** `/bc <initiative topic>` - Generate with research
- **Orthogonal mode:** `/bc --orthogonal <topic>` - 3-round Claude vs Gemini challenge

---

### Standard Mode: Business Case with Research

For investment proposals requiring financial justification:

#### Phase 1: Problem Analysis

1. Initialize FPF cycle:
   ```
   /q0-init
   ```

2. Gather context:
   - Search Brain for related projects
   - Review market data if available
   - Check Jira for scope and estimates
   - Search for competitor analysis

3. Generate hypotheses:
   ```
   /q1-hypothesize "What is the business value of '$ARGUMENTS'? What are the investment options and expected returns?"
   ```

#### Phase 2: Financial Analysis

4. Validate assumptions:
   ```
   /q3-validate
   ```
   - Research market size and opportunity
   - Check internal data for baselines
   - Review similar past investments

5. Audit for bias:
   ```
   /q4-audit
   ```
   - Check for overly optimistic projections
   - Verify cost assumptions are complete
   - Ensure risks are adequately addressed

#### Phase 3: Generate Business Case

6. Create BC document:
   ```bash
   python3 "$PM_OS_COMMON/tools/documents/template_manager.py" --type bc --render --fpf
   ```

7. Populate the Business Case with:
   - **Executive Summary:** 1-page overview for leadership
   - **Problem Statement:** What problem this solves
   - **Proposed Solution:** What we're investing in
   - **Investment Required:** Costs breakdown
   - **Expected Returns:** Revenue/savings projections
   - **Risk Assessment:** What could go wrong
   - **Recommendation:** Go/No-Go with rationale

8. Create Design Rationale Record:
   ```
   /q5-decide
   ```

---

### Orthogonal Mode: 3-Round Challenge

For significant investments requiring rigorous financial validation:

1. Run the orthogonal challenge system:
   ```bash
   python3 "$PM_OS_COMMON/tools/quint/orthogonal_challenge.py" --type bc --topic "$ARGUMENTS"
   ```

2. This will execute:
   - **Round 1 (Claude):** Create initial BC with research + FPF reasoning
   - **Round 2 (Gemini):** Challenge assumptions, stress-test financials
   - **Round 3 (Claude):** Resolve challenges, produce final BC

3. Wait for completion (5-15 minutes)

4. Report outputs:
   - Final BC: `Brain/Reasoning/Orthogonal/<id>/v3_final.md`
   - Challenge FAQ: Shows all challenges and resolutions
   - DRR: Stored in `Brain/Reasoning/Decisions/`

---

### Business Case Template Sections

The generated BC will include:

1. **Executive Summary:** Key points for decision makers
2. **Problem Statement:** Business problem being addressed
3. **Proposed Solution:** What we're recommending
4. **Market Analysis:** Opportunity size and context
5. **Investment Required:**
   - Development costs
   - Operational costs
   - Timeline
6. **Expected Returns:**
   - Revenue projections
   - Cost savings
   - Strategic value
7. **Risk Assessment:** Risks and mitigations
8. **Alternatives Considered:** Build vs buy vs partner
9. **Recommendation:** Go/No-Go with conditions
10. **Decision Rationale (FPF Mode):** DRR reference
11. **Challenge FAQ (Orthogonal Mode):** Q&A from challenge process

## Examples

**Standard:**
- `/bc Expand to Canadian market with Meal Kit`
- `/bc Launch mobile app for BB customers`
- `/bc Migrate to new payment processor`

**Orthogonal (rigorous):**
- `/bc --orthogonal Acquisition of competitor company`
- `/bc --orthogonal Build vs buy decision for AI platform`
- `/bc --orthogonal International expansion strategy`

## Notes

- Standard mode: 5-10 minutes
- Orthogonal mode: 10-20 minutes (3-round challenge)
- Use orthogonal for investments > $1M or strategic initiatives
- Business cases should include sensitivity analysis
- Update projections as actuals become available
