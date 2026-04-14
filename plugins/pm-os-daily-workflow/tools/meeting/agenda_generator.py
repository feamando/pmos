#!/usr/bin/env python3
"""
Agenda Generator (v5.0)

Generates meeting agendas from meeting context and participant context.
Handles template selection by meeting type and pre-read content assembly.

Extracted from v4.x meeting_prep.py to isolate agenda/prompt construction.

Usage:
    from meeting.agenda_generator import AgendaGenerator

    generator = AgendaGenerator(config)
    prompt = generator.build_synthesis_prompt(classified, context)
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from config_loader import get_config
    except ImportError:
        get_config = None


# ---------------------------------------------------------------------------
# Agenda Generator
# ---------------------------------------------------------------------------


class AgendaGenerator:
    """Build synthesis prompts and pre-read content from meeting + participant context."""

    def __init__(self, config: Any):
        """
        Args:
            config: PM-OS ConfigLoader instance.
        """
        self.config = config

    # -- Public API ----------------------------------------------------------

    def build_synthesis_prompt(
        self, classified: Dict, context: Dict
    ) -> str:
        """
        Build the full synthesis prompt with context data for the LLM.

        Args:
            classified: Output of MeetingManager.classify_meeting().
            context: Output of MeetingManager.gather_context().

        Returns:
            Complete prompt string ready for synthesis.
        """
        template_prompt = self._get_template_prompt(classified, context)

        action_items_str = self._format_action_items(context)
        projects_str = self._format_projects(context)
        series_history_str, series_intelligence_str = self._format_series(context)
        jira_str = self._format_jira(context)
        frameworks_str = self._format_frameworks(context)

        depth_note = ""
        prep_depth = classified.get("prep_depth", "standard")
        if prep_depth in ("quick", "minimal"):
            depth_note = (
                "\n**MODE: QUICK** - Generate minimal, concise output. "
                "Focus only on critical items.\n"
            )

        return f"""{template_prompt}
{depth_note}
---

## Context Data

### Participants
{json.dumps(context.get('participant_context', []), indent=2)}

### Related Projects
{projects_str}

### Frameworks (For Interviews)
{frameworks_str}

### Recent Context (Key Decisions)
{context.get('context_summary', 'No recent context.')}

### Past Meeting Notes
{self._truncate(context.get('past_notes', ''), 2000, 'No past notes found.')}

### Previous Series History
{series_history_str if not series_intelligence_str else '(See Series Intelligence below)'}

### Series Intelligence (Synthesized History)
{series_intelligence_str if series_intelligence_str else 'No series intelligence available.'}

### Outstanding Action Items
{action_items_str}

### Recent Jira Activity
{jira_str}

---
Generate the meeting prep using the exact output format specified above.
"""

    def get_instructions_block(self, meeting_type: str) -> str:
        """
        Return meeting-type-specific output instructions.

        Args:
            meeting_type: Classification string (1on1, interview, standup, etc.)

        Returns:
            Instruction block string.
        """
        if meeting_type == "interview":
            return (
                "1. **Context / Role** - Brief on the role and team context.\n"
                "2. **Assessment Criteria** - Key skills/traits to assess based on "
                "the Career Framework and company DNA provided.\n"
                "3. **Suggested Questions** - 5-7 targeted questions. Use the "
                "'Past Interviews' to find proven questions for this role. "
                "Ensure questions target the assessment criteria.\n"
                "4. **Candidate Profile** - Brief bio if available from participants list.\n"
            )

        return (
            "1. **Context / Why** - Meeting purpose, incorporating project "
            "context and past discussions\n"
            "2. **Participant Notes** - Role-specific preparation points for "
            "each participant, include their pending action items\n"
            "3. **Last Meeting Recap** - Key decisions/outcomes from past notes "
            "(if available)\n"
            "4. **Agenda Suggestions** - Time-boxed agenda items (total ~30-50 min), "
            "specific to current context\n"
            "5. **Key Questions** - Specific questions informed by projects, "
            "action items, and recent context\n"
        )

    # -- Formatting helpers --------------------------------------------------

    def _format_action_items(self, context: Dict) -> str:
        """Format action items including completion inference markers."""
        items = context.get("action_items", [])
        if not items:
            return "None found for participants."

        lines: List[str] = []
        for item in items:
            completion_status = item.get("completion_status")
            if completion_status:
                marker = getattr(completion_status, "marker", None)
                if marker is None:
                    status = getattr(completion_status, "status", "outstanding")
                    if status == "completed":
                        marker = "[x]"
                    elif status == "possibly_complete":
                        marker = "[~]"
                    else:
                        marker = "[ ]"
                evidence_list = getattr(completion_status, "evidence", [])
                evidence = (
                    f" *({evidence_list[0][:50]}...)*"
                    if evidence_list
                    else ""
                )
            else:
                marker = "[x]" if item.get("completed") else "[ ]"
                evidence = ""
            lines.append(
                f"- {marker} **{item.get('owner', 'Unknown')}**: "
                f"{item.get('task', '')}{evidence}"
            )
        return "\n".join(lines)

    def _format_projects(self, context: Dict) -> str:
        """Format related projects for prompt."""
        projects = context.get("topic_context", [])
        if not projects:
            return "No related projects found."
        parts: List[str] = []
        for proj in projects:
            parts.append(
                f"### {proj['name']} ({proj['status']})\n{proj['summary']}\n"
            )
        return "\n".join(parts)

    def _format_series(self, context: Dict):
        """Format series history and intelligence. Returns (history_str, intelligence_str)."""
        series_intelligence_str = ""
        series_history_str = ""

        si = context.get("series_intelligence")
        if si and si.get("summary"):
            series_intelligence_str = si["summary"]
        elif context.get("series_history"):
            for entry in context["series_history"][:3]:
                series_history_str += (
                    f"### {entry['date']}\n{entry['summary'][:400]}\n\n"
                )

        if not series_history_str and not series_intelligence_str:
            series_history_str = "No previous series entries found."

        return series_history_str, series_intelligence_str

    def _format_jira(self, context: Dict) -> str:
        """Format Jira issues for prompt."""
        issues = context.get("jira_issues", [])
        if not issues:
            return "No recent Jira issues found."
        lines: List[str] = []
        for issue in issues:
            lines.append(
                f"- [{issue['key']}]({issue.get('url', '')}) - "
                f"{issue['summary']} ({issue['status']}, "
                f"{issue.get('priority', 'N/A')}) - Assignee: {issue['assignee']}"
            )
        return "\n".join(lines)

    def _format_frameworks(self, context: Dict) -> str:
        """Format interview frameworks."""
        parts: List[str] = []
        if context.get("career_framework"):
            parts.append(
                f"## Product Career Framework\n{context['career_framework']}\n"
            )
        if context.get("company_dna"):
            parts.append(
                f"## Company DNA\n{context['company_dna']}\n"
            )
        return "\n".join(parts) if parts else ""

    def _get_template_prompt(self, classified: Dict, context: Dict) -> str:
        """
        Get the template-based prompt instructions.

        Tries to load from the templates module; falls back to inline defaults.
        """
        try:
            from meeting.templates import get_template
            template = get_template(classified["meeting_type"])
            return template.get_prompt_instructions(classified, context)
        except ImportError:
            try:
                from templates import get_template
                template = get_template(classified["meeting_type"])
                return template.get_prompt_instructions(classified, context)
            except ImportError:
                logger.debug("Templates module not available; using inline default")

        meeting_type = classified["meeting_type"]
        summary = classified.get("summary", "Untitled")
        instructions = self.get_instructions_block(meeting_type)
        return (
            f"Generate a meeting pre-read for: {summary}\n"
            f"Meeting Type: {meeting_type}\n\n"
            f"Generate a comprehensive pre-read with these sections:\n"
            f"{instructions}\n"
            "Important:\n"
            "- Use participant roles correctly (from the participant context)\n"
            "- Reference specific projects and their status where relevant\n"
            "- Include outstanding action items as follow-up points\n"
            "- Be specific rather than generic\n\n"
            "Output clean Markdown.\n"
        )

    @staticmethod
    def _truncate(text: str, max_len: int, fallback: str = "") -> str:
        if not text:
            return fallback
        return text[:max_len]

    # -- Output cleaning -----------------------------------------------------

    @staticmethod
    def clean_output(content: str) -> str:
        """Remove empty sections from generated output."""
        empty_patterns = [
            r"## [^\n]+\n+(?:No [^\n]+found\.?\n*)+(?=##|\Z)",
            r"## [^\n]+\n+(?:None [^\n]+\.?\n*)+(?=##|\Z)",
            r"## [^\n]+\n+(?:-\s*N/A\s*\n*)+(?=##|\Z)",
            r"## [^\n]+\n\s*\n+(?=##|\Z)",
        ]
        cleaned = content
        for pattern in empty_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()


# ---------------------------------------------------------------------------
# CLI for testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test agenda generator")
    parser.add_argument(
        "--meeting-type", type=str, default="1on1",
        help="Meeting type (1on1, interview, standup, etc.)",
    )
    args = parser.parse_args()

    print(AgendaGenerator(None).get_instructions_block(args.meeting_type))
