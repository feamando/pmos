"""
Planning/Sprint Template

For sprint planning, grooming, and planning sessions.
Target: ~400 words
"""

from typing import Dict, List

from .base_template import DynamicSectionConfig, MeetingTemplate, TemplateConfig


class PlanningTemplate(MeetingTemplate):
    """Template for planning sessions, sprint planning, grooming."""

    config = TemplateConfig(
        max_words=400,
        sections=[
            "tldr",
            "planning_context",
            "items_to_discuss",
            "your_input",
            "decisions_needed",
        ],
        skip_empty_sections=True,
        include_tldr=True,
        section_rules={
            "tldr": DynamicSectionConfig(min_items=3, max_items=5),
            "items_to_discuss": DynamicSectionConfig(min_items=2, max_items=10),
            "decisions_needed": DynamicSectionConfig(min_items=1, max_items=5),
        },
    )

    def get_sections(self) -> List[str]:
        return [
            "tldr",
            "planning_context",
            "items_to_discuss",
            "your_input",
            "decisions_needed",
        ]

    def get_prompt_instructions(self, classified: Dict, context: Dict) -> str:
        summary = classified.get("summary", "Planning")
        participants = classified.get("participants", [])

        # Determine planning type
        is_sprint = any(word in summary.lower() for word in ["sprint", "iteration"])
        is_grooming = any(
            word in summary.lower() for word in ["grooming", "refinement", "backlog"]
        )

        planning_type = (
            "Sprint Planning"
            if is_sprint
            else ("Backlog Grooming" if is_grooming else "Planning")
        )

        # Get Jira context if available
        jira_issues = context.get("jira_issues", [])
        jira_count = len(jira_issues)

        return f"""Generate {planning_type.lower()} prep (max {self.config.max_words} words).

**Meeting:** {summary}
**Type:** {planning_type}
**Participants:** {len(participants)} attendees

{self.get_tldr_prompt()}

## Planning Context
- What sprint/period are we planning for
- Capacity constraints or team availability issues
- Carryover from previous sprint (if applicable)
- Key deadlines or milestones to hit

## Items to Discuss
{f'From Jira ({jira_count} issues found):' if jira_count > 0 else 'Backlog items to review:'}
- List high-priority items that need sizing/discussion
- Flag any items with unclear requirements
- Note dependencies between items

## Your Input Needed
- Items you own or need to speak to
- Estimates or sizing you need to provide
- Concerns about scope or feasibility

## Decisions Needed
- Scope decisions for the sprint/period
- Priority trade-offs to make
- Resource allocation questions

## CONSTRAINTS
- Focus on items that need discussion, not status
- Prepare estimates where you're the subject matter expert
- Max {self.config.max_words} words

## OUTPUT FORMAT
Use these exact headers:
- ## TL;DR
- ## Planning Context
- ## Items to Discuss
- ## Your Input
- ## Decisions Needed
"""
