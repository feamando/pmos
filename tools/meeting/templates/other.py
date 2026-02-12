"""
Other/Fallback Template

For meetings that don't fit specific categories.
Target: ~400 words
"""

from typing import Dict, List

from .base_template import DynamicSectionConfig, MeetingTemplate, TemplateConfig


class OtherTemplate(MeetingTemplate):
    """Fallback template for meetings that don't match specific types."""

    config = TemplateConfig(
        max_words=400,
        sections=[
            "tldr",
            "meeting_context",
            "key_participants",
            "your_prep",
            "questions",
        ],
        skip_empty_sections=True,
        include_tldr=True,
        section_rules={
            "tldr": DynamicSectionConfig(min_items=3, max_items=5),
            "key_participants": DynamicSectionConfig(min_items=1, max_items=5),
            "questions": DynamicSectionConfig(min_items=1, max_items=4),
        },
    )

    def get_sections(self) -> List[str]:
        return ["tldr", "meeting_context", "key_participants", "your_prep", "questions"]

    def get_prompt_instructions(self, classified: Dict, context: Dict) -> str:
        summary = classified.get("summary", "Meeting")
        participants = classified.get("participants", [])
        participant_count = len(participants)

        # Get participant names for context
        participant_names = [p.get("name", "Unknown") for p in participants[:5]]

        return f"""Generate general meeting prep (max {self.config.max_words} words).

**Meeting:** {summary}
**Participants:** {participant_count} attendees

{self.get_tldr_prompt()}

## Meeting Context
- What is this meeting about (based on title/description)
- Why was this meeting scheduled
- What outcome is expected
- Any relevant background information

## Key Participants
{chr(10).join(f'- {name}' for name in participant_names)}
Note their relevance to the meeting topic and any context on their interests.

## Your Prep
- What you should review before the meeting
- Any data or materials to bring
- Points you might need to contribute
- Background reading if applicable

## Questions to Prepare
- Key questions to ask or expect
- Information you need from attendees
- Decisions that may need input

## CONSTRAINTS
- Keep prep focused on actionable items
- Don't over-prepare for unknown meeting types
- If meeting purpose is unclear, note that
- Max {self.config.max_words} words

## OUTPUT FORMAT
Use these exact headers:
- ## TL;DR
- ## Meeting Context
- ## Key Participants
- ## Your Prep
- ## Questions
"""
