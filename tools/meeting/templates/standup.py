"""
Standup/Daily Sync Template

Minimal template for standups and daily syncs.
Target: ~150 words
"""

from typing import Dict, List

from .base_template import DynamicSectionConfig, MeetingTemplate, TemplateConfig


class StandupTemplate(MeetingTemplate):
    """Template for standups - minimal, status-focused."""

    config = TemplateConfig(
        max_words=150,
        sections=["team_status", "blockers", "your_update"],
        skip_empty_sections=True,
        include_tldr=False,  # Standup IS the TL;DR
        section_rules={
            "blockers": DynamicSectionConfig(min_items=0, max_items=5),
            "team_status": DynamicSectionConfig(min_items=1, max_items=10),
        },
    )

    def get_sections(self) -> List[str]:
        return ["team_status", "blockers", "your_update"]

    def get_prompt_instructions(self, classified: Dict, context: Dict) -> str:
        participants = classified.get("participants", [])
        participant_names = [p.get("name", "Unknown") for p in participants[:5]]

        blockers = context.get("blockers", [])
        blocker_count = len(blockers)

        return f"""Generate MINIMAL standup prep (max {self.config.max_words} words).

**Participants:** {', '.join(participant_names)}

## Team Status Snapshot
Quick bullets on each participant's current focus:
- Only include what's relevant for TODAY's sync
- Highlight any blocked items

## Blockers ({blocker_count} found)
{f'List the {blocker_count} known blockers affecting the team' if blocker_count > 0 else 'No blockers found - omit this section'}

## Your Update Prep
What you'll share:
- Done: [what you completed since last standup]
- Doing: [what you're working on today]
- Blocked: [any blockers - or "None"]

## CONSTRAINTS
- This should take 30 seconds to read
- No context sections - standup is for status only
- No TL;DR section (the whole doc is a TL;DR)
- No agenda suggestions
- No "Key Questions"
- Max {self.config.max_words} words total

## OUTPUT FORMAT
Use these exact headers:
- ## Team Status
- ## Blockers (only if any exist)
- ## Your Update
"""
