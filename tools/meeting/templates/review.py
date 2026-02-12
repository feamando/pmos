"""
Review/Retro/Demo Template

For retrospectives, demos, and review meetings.
Target: ~400 words
"""

from typing import Dict, List

from .base_template import DynamicSectionConfig, MeetingTemplate, TemplateConfig


class ReviewTemplate(MeetingTemplate):
    """Template for reviews, retros, and demos."""

    config = TemplateConfig(
        max_words=400,
        sections=["tldr", "review_scope", "your_prep", "discussion_points"],
        skip_empty_sections=True,
        include_tldr=True,
        section_rules={
            "tldr": DynamicSectionConfig(min_items=3, max_items=5),
            "discussion_points": DynamicSectionConfig(min_items=2, max_items=6),
        },
    )

    def get_sections(self) -> List[str]:
        return ["tldr", "review_scope", "your_prep", "discussion_points"]

    def get_prompt_instructions(self, classified: Dict, context: Dict) -> str:
        summary = classified.get("summary", "Review")
        participants = classified.get("participants", [])
        participant_count = len(participants)

        # Determine review type from summary
        is_retro = any(word in summary.lower() for word in ["retro", "retrospective"])
        is_demo = any(
            word in summary.lower() for word in ["demo", "showcase", "show and tell"]
        )
        is_review = not is_retro and not is_demo

        review_type = "Retrospective" if is_retro else ("Demo" if is_demo else "Review")

        return f"""Generate {review_type.lower()} meeting prep (max {self.config.max_words} words).

**Meeting:** {summary}
**Type:** {review_type}
**Participants:** {participant_count} attendees

{self.get_tldr_prompt()}

## {review_type} Scope
- What time period/project/work is being reviewed
- Key deliverables or milestones covered
- Success criteria or goals being assessed

## Your Prep
{'### For Retrospective' if is_retro else '### For ' + review_type}
{'''
- **What went well:** 2-3 wins to celebrate
- **What didn't go well:** 2-3 challenges/issues
- **What to try:** 1-2 process improvements to suggest
''' if is_retro else '''
- What you're presenting/demoing (if applicable)
- Questions you need answered
- Feedback you're seeking
'''}

## Discussion Points
- Key topics likely to be discussed
- Decisions that may need to be made
- Your perspective on key issues

## CONSTRAINTS
- Focus on actionable insights, not just status
- {'Include both positives and negatives for balance' if is_retro else 'Prepare to both give and receive feedback'}
- Max {self.config.max_words} words

## OUTPUT FORMAT
Use these exact headers:
- ## TL;DR
- ## {review_type} Scope
- ## Your Prep
- ## Discussion Points
"""
