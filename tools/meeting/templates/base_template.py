"""
Base Template Classes for Meeting Prep

Defines the abstract base class and configuration dataclasses
for meeting-type-specific templates.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class DynamicSectionConfig:
    """
    Context-aware section length configuration.

    Instead of hardcoding "max 3 items", use contextual rules
    based on relevance thresholds.
    """

    min_items: int = 1
    max_items: int = 10
    relevance_threshold: float = 0.5

    def get_item_count(self, items: List[Dict], score_key: str = "relevance") -> int:
        """
        Determine how many items to include based on context.

        Args:
            items: List of items with relevance scores
            score_key: Key to use for relevance score in each item

        Returns:
            Number of items to include
        """
        relevant = [
            i for i in items if i.get(score_key, 1.0) >= self.relevance_threshold
        ]
        return max(self.min_items, min(len(relevant), self.max_items))


@dataclass
class TemplateConfig:
    """
    Configuration for a meeting prep template.

    Defines output constraints and section rules.
    """

    max_words: int
    sections: List[str]
    skip_empty_sections: bool = True
    include_tldr: bool = True
    priority_order: Optional[List[str]] = None

    # Dynamic section configuration
    section_rules: Dict[str, DynamicSectionConfig] = field(
        default_factory=lambda: {
            "tldr": DynamicSectionConfig(min_items=3, max_items=7),
            "action_items": DynamicSectionConfig(min_items=0, max_items=20),
            "topics": DynamicSectionConfig(
                min_items=2, max_items=10, relevance_threshold=0.5
            ),
            "questions": DynamicSectionConfig(
                min_items=0, max_items=5, relevance_threshold=0.7
            ),
            "participants": DynamicSectionConfig(min_items=1, max_items=5),
        }
    )


class MeetingTemplate(ABC):
    """
    Abstract base class for meeting prep templates.

    Each meeting type (1:1, standup, interview, etc.) implements
    its own template with specific prompt instructions and output format.
    """

    config: TemplateConfig

    @abstractmethod
    def get_prompt_instructions(self, classified: Dict, context: Dict) -> str:
        """
        Generate type-specific prompt instructions for the LLM.

        Args:
            classified: Classified meeting info (type, participants, summary, etc.)
            context: Gathered context (Brain, GDrive, action items, etc.)

        Returns:
            Prompt instructions string for LLM synthesis
        """
        pass

    @abstractmethod
    def get_sections(self) -> List[str]:
        """
        Return ordered list of sections for this template type.

        Returns:
            List of section names in output order
        """
        pass

    def get_tldr_prompt(self, context: Dict = None) -> str:
        """
        Dynamic TL;DR prompt based on meeting complexity.

        Args:
            context: Optional context to determine complexity

        Returns:
            TL;DR prompt instructions
        """
        # Determine complexity based on context
        bullet_count = self._calculate_tldr_bullets(context)

        return f"""
## TL;DR (Required - Place at TOP)
Provide {bullet_count} bullet points summarizing:
- Why this meeting matters right now
- The ONE key decision or outcome needed
- Most important prep item for the user
- Any critical blockers or time-sensitive items

Be concise but comprehensive. Each bullet should be actionable.
"""

    def _calculate_tldr_bullets(self, context: Dict = None) -> str:
        """
        Calculate appropriate number of TL;DR bullets based on context.

        Returns bullet count as string (e.g., "3-4" or "5-7")
        """
        if not context:
            return "3-5"

        # Calculate complexity score
        complexity = 0

        # More action items = more bullets
        action_count = len(context.get("action_items", []))
        if action_count > 5:
            complexity += 2
        elif action_count > 2:
            complexity += 1

        # Series intelligence = more context
        if context.get("series_intelligence"):
            si = context["series_intelligence"]
            if len(si.get("open_commitments", [])) > 3:
                complexity += 1
            if len(si.get("recurring_topics", [])) > 0:
                complexity += 1

        # More participants = more coordination
        participant_count = len(context.get("participant_context", []))
        if participant_count > 3:
            complexity += 1

        # Jira issues indicate active work
        if len(context.get("jira_issues", [])) > 3:
            complexity += 1

        # Map complexity to bullet count
        if complexity <= 1:
            return "3-4"
        elif complexity <= 3:
            return "4-5"
        else:
            return "5-7"

    def should_skip_section(self, section_name: str, content: str) -> bool:
        """
        Determine if a section should be skipped (no placeholder).

        Args:
            section_name: Name of the section
            content: Generated content for the section

        Returns:
            True if section should be omitted from output
        """
        if not self.config.skip_empty_sections:
            return False

        empty_indicators = [
            "no data found",
            "none found",
            "no recent",
            "not available",
            "no outstanding",
            "no previous",
            "n/a",
        ]
        content_lower = content.lower()
        return any(ind in content_lower for ind in empty_indicators)

    def get_word_limit_instruction(self) -> str:
        """Get instruction for word limit."""
        return f"Keep total output under {self.config.max_words} words."

    def format_action_items_instruction(self, count: int) -> str:
        """
        Get instruction for action items section.

        Args:
            count: Number of action items found

        Returns:
            Instruction string for action items
        """
        if count == 0:
            return "No outstanding action items found - omit this section."

        return f"""
## Action Items
List ALL {count} outstanding action items for participants.
Include completion status indicators:
- [x] for completed (with evidence)
- [~] for possibly complete (with signal)
- [ ] for outstanding

Do NOT limit to 3 items. Include all relevant items.
"""

    def format_topics_instruction(self, count: int) -> str:
        """
        Get instruction for topics section.

        Args:
            count: Number of potential topics found

        Returns:
            Instruction string for topics
        """
        return f"""
## Topics to Discuss
Include topics based on relevance to this meeting.
Current context has {count} potential topics - include those most relevant.
Minimum 2 topics, no maximum if all are relevant.
"""

    def format_questions_instruction(self) -> str:
        """Get instruction for questions section."""
        return """
## Questions
Include strategic questions ONLY where decisions are needed.
If no decisions pending, omit this section entirely.
Do not pad with generic questions like "How are you doing?"
"""

    # =========================================================================
    # Standardized Section Headers
    # =========================================================================

    STANDARD_HEADERS = {
        "tldr": "## TL;DR",
        "action_items": "## Action Items",
        "topics": "## Topics to Discuss",
        "questions": "## Questions to Ask",
        "participants": "## Key Participants",
        "context": "## Context",
        "agenda": "## Suggested Agenda",
        "decisions": "## Decisions Needed",
        "prep": "## Your Prep",
        "history": "## Previous Meeting Summary",
        "commitments": "## Open Commitments",
        "series_intelligence": "## Series Intelligence",
    }

    @classmethod
    def get_standard_header(cls, section: str) -> str:
        """
        Get standardized header for a section.

        Args:
            section: Section identifier

        Returns:
            Standard markdown header
        """
        return cls.STANDARD_HEADERS.get(
            section, f"## {section.replace('_', ' ').title()}"
        )

    def get_output_format_instruction(self) -> str:
        """
        Get standardized output format instruction.

        Returns:
            Output format instruction with exact headers to use
        """
        sections = self.get_sections()
        headers = [self.get_standard_header(s) for s in sections]

        return f"""
## OUTPUT FORMAT
Use these exact headers in this order:
{chr(10).join(f'- {h}' for h in headers)}

Do NOT add extra sections or change header names.
Skip sections with no relevant content (don't use "N/A" placeholders).
"""
