"""
External Meeting Template

For meetings with external participants - includes company/person context.
Target: ~500 words
"""

from typing import Dict, List

from .base_template import DynamicSectionConfig, MeetingTemplate, TemplateConfig


class ExternalTemplate(MeetingTemplate):
    """Template for external meetings - company/person research focus."""

    config = TemplateConfig(
        max_words=500,
        sections=[
            "tldr",
            "company_context",
            "participant_context",
            "talking_points",
            "questions",
        ],
        skip_empty_sections=True,
        include_tldr=True,
        section_rules={
            "tldr": DynamicSectionConfig(min_items=3, max_items=5),
            "talking_points": DynamicSectionConfig(min_items=2, max_items=5),
            "questions": DynamicSectionConfig(min_items=2, max_items=4),
        },
    )

    def get_sections(self) -> List[str]:
        return [
            "tldr",
            "company_context",
            "participant_context",
            "talking_points",
            "questions",
        ]

    def get_prompt_instructions(self, classified: Dict, context: Dict) -> str:
        participants = classified.get("participants", [])
        summary = classified.get("summary", "External Meeting")

        # Extract external participants
        external_participants = [p for p in participants if p.get("is_external", False)]
        external_names = [p.get("name", "Unknown") for p in external_participants]

        # Extract company domains
        companies = set()
        for p in external_participants:
            email = p.get("email", "")
            if "@" in email:
                domain = email.split("@")[-1]
                company = (
                    domain.replace(".com", "")
                    .replace(".io", "")
                    .replace(".org", "")
                    .title()
                )
                if company not in ["Gmail", "Yahoo", "Hotmail", "Outlook"]:
                    companies.add(company)

        company_list = ", ".join(companies) if companies else "External Organization"

        return f"""Generate external meeting prep with company context (max {self.config.max_words} words).

**Meeting:** {summary}
**External Participants:** {', '.join(external_names) if external_names else 'External attendees'}
**Company/Organization:** {company_list}

{self.get_tldr_prompt()}

## Company Context: {company_list}
- Brief on each external company (what they do, their market)
- Your company's relationship with them (partner, vendor, prospect, etc.)
- Recent news or developments if known
- Any relevant history of interactions

## External Participants
For each external attendee, provide:
- Name and role (if known)
- Their relevance to this meeting
- Any prior interactions or context
- What they likely care about

## Talking Points
- Key messages you should convey
- Value propositions or updates to share
- Sensitive topics to handle carefully or avoid

## Questions to Ask
- 2-4 strategic questions to advance the relationship/objective
- Information you need from them

## CONSTRAINTS
- Research external participants thoroughly
- Include company context even if speculative
- Note any confidentiality concerns
- Max {self.config.max_words} words

## OUTPUT FORMAT
Use these exact headers:
- ## TL;DR
- ## Company Context
- ## External Participants
- ## Talking Points
- ## Questions to Ask
"""
