# PRFAQ Generator

Generate an Amazon-style Press Release / FAQ document with optional orthogonal challenge.

## Arguments
$ARGUMENTS

## Instructions

The user wants to generate a PRFAQ (Press Release / FAQ) document. Parse their request:

### Mode Selection

Check for flags:
- **Standard mode:** `/prfaq <product/feature>` - Generate with research
- **Orthogonal mode:** `/prfaq --orthogonal <topic>` - 3-round Claude vs Gemini challenge

---

### Standard Mode: PRFAQ with Research

For product/feature proposals using Amazon's Working Backwards method:

#### Phase 1: Customer Research

1. Initialize FPF cycle:
   ```
   /q0-init
   ```

2. Gather customer context:
   - Search Brain for customer insights
   - Review Jira for user feedback
   - Check Slack for customer discussions
   - Search for competitive analysis

3. Generate customer hypotheses:
   ```
   /q1-hypothesize "Who is the customer for '$ARGUMENTS'? What problem are we solving? What benefit do they get?"
   ```

#### Phase 2: Validation

4. Validate customer need:
   ```
   /q3-validate
   ```
   - Research similar products in market
   - Check customer interview data
   - Review usage analytics if available

5. Audit for customer-centricity:
   ```
   /q4-audit
   ```
   - Is this solving a real customer problem?
   - Are we making assumptions about customer behavior?
   - What evidence supports the value proposition?

#### Phase 3: Generate PRFAQ

6. Create PRFAQ document:
   ```bash
   python3 "$PM_OS_COMMON/tools/documents/template_manager.py" --type prfaq --render --fpf
   ```

7. Populate the PRFAQ with:

   **Press Release:**
   - **Headline:** Compelling product announcement
   - **Summary:** What it is and why it matters
   - **Customer Quote:** Voice of the customer
   - **How It Works:** Key features/benefits
   - **Call to Action:** How to get started

   **FAQ Sections:**
   - **Customer FAQ:** What customers would ask
   - **Internal FAQ:** What leadership would ask
   - **Technical FAQ:** What engineers would ask

8. Create Design Rationale Record:
   ```
   /q5-decide
   ```

---

### Orthogonal Mode: 3-Round Challenge

For significant product launches requiring rigorous validation:

1. Run the orthogonal challenge system:
   ```bash
   python3 "$PM_OS_COMMON/tools/quint/orthogonal_challenge.py" --type prfaq --topic "$ARGUMENTS"
   ```

2. This will execute:
   - **Round 1 (Claude):** Create initial PRFAQ with research + FPF reasoning
   - **Round 2 (Gemini):** Challenge assumptions, customer value, feasibility
   - **Round 3 (Claude):** Resolve challenges, produce final PRFAQ

3. Wait for completion (5-15 minutes)

4. Report outputs:
   - Final PRFAQ: `Brain/Reasoning/Orthogonal/<id>/v3_final.md`
   - Challenge FAQ: Shows all challenges and resolutions
   - DRR: Stored in `Brain/Reasoning/Decisions/`

---

### PRFAQ Structure

The generated PRFAQ will include:

**Press Release:**
1. **Headline + Subhead:** Attention-grabbing announcement
2. **First Paragraph:** Summary of what, for whom, why
3. **Problem/Solution:** The customer pain and our answer
4. **Executive Quote:** Vision and commitment
5. **Customer Quote:** Voice of customer validation
6. **Call to Action:** What to do next

**Customer FAQ:**
- What is it?
- Who is it for?
- How does it work?
- How is it different?
- How much does it cost?

**Internal FAQ:**
- Why are we building this?
- What are the success metrics?
- What are the risks?
- What's the timeline?
- What resources are needed?

**Technical FAQ:**
- What's the architecture?
- What systems are affected?
- How will we ensure reliability?

## Examples

**Standard:**
- `/prfaq Push notifications for BB app`
- `/prfaq One-time purchase for Factor meals`
- `/prfaq Loyalty rewards program`

**Orthogonal (rigorous):**
- `/prfaq --orthogonal New brand launch in wellness space`
- `/prfaq --orthogonal AI-powered meal recommendations`
- `/prfaq --orthogonal Marketplace for recipe creators`

## Notes

- Standard mode: 5-10 minutes
- Orthogonal mode: 10-20 minutes (3-round challenge)
- PRFAQs work backwards from customer experience
- Write as if the product is launching today
- Keep the press release to one page
- Use orthogonal for major product launches
