"""
Large Meeting Template

For meetings with >5 participants - focus on "Why am I here?"
Target: ~200 words
"""

from typing import Dict, List

from .base_template import DynamicSectionConfig, MeetingTemplate, TemplateConfig


class LargeMeetingTemplate(MeetingTemplate):
    """Template for large meetings - focus on user's role and contribution."""

    config = TemplateConfig(
        max_words=200,
        sections=["tldr", "why_here", "key_stakeholders", "your_contribution"],
        skip_empty_sections=True,
        include_tldr=True,
        section_rules={
            "tldr": DynamicSectionConfig(min_items=3, max_items=5),
            "key_stakeholders": DynamicSectionConfig(min_items=2, max_items=5),
        },
    )

    def get_sections(self) -> List[str]:
        return ["tldr", "why_here", "key_stakeholders", "your_contribution"]

    def get_prompt_instructions(self, classified: Dict, context: Dict) -> str:
        participants = classified.get("participants", [])
        participant_count = len(participants)
        summary = classified.get("summary", "Large Meeting")

        # Get key stakeholders (first 5)
        stakeholders = [p.get("name", "Unknown") for p in participants[:5]]

        return f"""Generate focused large meeting prep (max {self.config.max_words} words).

**Meeting:** {summary}
**Participants:** {participant_count} attendees

{self.get_tldr_prompt()}

## Why Am I Here?
- Your specific role/stake in this meeting (1-2 sentences)
- What input is expected from you
- Why you were invited (if unclear, note that)

## Key Stakeholders
List the 2-3 most relevant participants:
{chr(10).join(f'- {s}' for s in stakeholders[:3])}
Note their interests or what they care about in this meeting.
Flag any politics or sensitivities if relevant.

## Your Contribution
- 1-2 specific points you should raise
- Any data/updates you should bring
- Questions you need answered

## CONSTRAINTS
- Large meetings need LESS prep, not more
- Focus on YOUR role, not general context
- No detailed agenda (that's the organizer's job)
- No participant prep notes for everyone
- Max {self.config.max_words} words

## OUTPUT FORMAT
Use these exact headers:
- ## TL;DR
- ## Why Am I Here?
- ## Key Stakeholders
- ## Your Contribution
"""
