"""
One-on-One Meeting Template

Optimized for 1:1 meetings with action items first.
Target: ~300 words
"""

from typing import Dict, List

from .base_template import DynamicSectionConfig, MeetingTemplate, TemplateConfig


class OneOnOneTemplate(MeetingTemplate):
    """Template for 1:1 meetings - concise, action-focused."""

    config = TemplateConfig(
        max_words=300,
        sections=["tldr", "action_items", "topics", "context"],
        skip_empty_sections=True,
        include_tldr=True,
        priority_order=["action_items", "topics"],
        section_rules={
            "tldr": DynamicSectionConfig(min_items=3, max_items=5),
            "action_items": DynamicSectionConfig(min_items=0, max_items=20),
            "topics": DynamicSectionConfig(
                min_items=2, max_items=7, relevance_threshold=0.5
            ),
            "questions": DynamicSectionConfig(
                min_items=0, max_items=3, relevance_threshold=0.8
            ),
        },
    )

    def get_sections(self) -> List[str]:
        return ["tldr", "action_items", "topics", "context"]

    def get_prompt_instructions(self, classified: Dict, context: Dict) -> str:
        participant = classified.get("participants", [{}])[0]
        participant_name = participant.get("name", "the participant")

        action_items = context.get("action_items", [])
        action_count = len(action_items)

        topics = context.get("topics", [])
        topic_count = len(topics)

        # Build series intelligence section if available
        series_intel = ""
        if context.get("series_intelligence"):
            si = context["series_intelligence"]
            if si.get("open_commitments"):
                series_intel += (
                    f"\n- {len(si['open_commitments'])} open commitments to follow up"
                )
            if si.get("recurring_topics"):
                series_intel += f"\n- {len(si['recurring_topics'])} recurring topics (potential stuck issues)"

        return f"""Generate a CONCISE 1:1 meeting prep (max {self.config.max_words} words).

**Participant:** {participant_name}

{self.get_tldr_prompt()}

{self.format_action_items_instruction(action_count)}

{self.format_topics_instruction(topic_count)}

## Quick Context
- {participant_name}'s current focus (1-2 sentences max)
- Any recent wins/challenges to acknowledge
{series_intel}

## CONSTRAINTS
- Lead with ACTION ITEMS (most important for 1:1s)
- No generic sections - if no data, omit the section
- Keep total under {self.config.max_words} words
- Be specific, not generic
- No time-boxed agenda (this is a 1:1, not a formal meeting)
- Skip "Key Questions" unless there's a real decision to make

## OUTPUT FORMAT
Use these exact headers:
- ## TL;DR
- ## Outstanding Actions
- ## Topics to Discuss
- ## Quick Context (only if meaningful)
"""
