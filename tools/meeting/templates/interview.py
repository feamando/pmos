"""
Interview Template

For job interviews - keeps existing depth, good structure.
Target: ~1000 words (interviews need detail)
"""

from typing import Dict, List

from .base_template import DynamicSectionConfig, MeetingTemplate, TemplateConfig


class InterviewTemplate(MeetingTemplate):
    """Template for interviews - detailed assessment criteria and questions."""

    config = TemplateConfig(
        max_words=1000,
        sections=[
            "tldr",
            "role_context",
            "assessment_criteria",
            "suggested_questions",
            "candidate_profile",
        ],
        skip_empty_sections=False,  # All sections important for interviews
        include_tldr=True,
        section_rules={
            "tldr": DynamicSectionConfig(min_items=3, max_items=5),
            "suggested_questions": DynamicSectionConfig(min_items=5, max_items=10),
            "assessment_criteria": DynamicSectionConfig(min_items=3, max_items=8),
        },
    )

    def get_sections(self) -> List[str]:
        return [
            "tldr",
            "role_context",
            "assessment_criteria",
            "suggested_questions",
            "candidate_profile",
        ]

    def get_prompt_instructions(self, classified: Dict, context: Dict) -> str:
        summary = classified.get("summary", "Interview")
        participants = classified.get("participants", [])

        # Extract candidate info
        candidate_name = "Candidate"
        for p in participants:
            if p.get("is_external", False):
                candidate_name = p.get("name", "Candidate")
                break

        # Get role from summary
        role = summary.replace("Virtual Interview", "").replace("Interview", "").strip()
        role = role.strip(" -:")

        # Get frameworks from context
        frameworks = context.get("frameworks", "")
        past_interviews = context.get("past_notes", "")

        return f"""Generate detailed interview prep (max {self.config.max_words} words).

**Interview:** {summary}
**Candidate:** {candidate_name}
**Role:** {role if role else 'Not specified'}

{self.get_tldr_prompt()}

## Role Context
- Brief on the role and team context
- What this role is responsible for
- Why we're hiring for this position
- Key success factors for the first 6 months

## Assessment Criteria
Based on the Career Framework and company values provided, list:
- **Primary Skills:** 3-4 key skills/competencies to assess
- **Traits:** 2-3 traits critical for success
- **Level Signals:** What distinguishes good vs. great for this level

{f'Use this framework context: {frameworks[:500]}' if frameworks else 'Use general product/engineering career ladder criteria.'}

## Suggested Questions
Provide 5-7 targeted interview questions:
- Mix of behavioral ("Tell me about a time...") and situational
- At least 2 role-specific technical questions
- One question about failure/learning
- One question about collaboration/influence

{f'Reference past interview questions if helpful: {past_interviews[:300]}' if past_interviews else ''}

## Candidate Profile
- Name: {candidate_name}
- Current context (if available from resume/LinkedIn)
- Key areas to probe based on their background
- Potential red flags to explore

## CONSTRAINTS
- Focus on signal-gathering questions, not gotchas
- Include both breadth and depth questions
- Note areas where the candidate's background aligns/gaps with role
- Max {self.config.max_words} words

## OUTPUT FORMAT
Use these exact headers:
- ## TL;DR
- ## Role Context
- ## Assessment Criteria
- ## Suggested Questions
- ## Candidate Profile
"""
