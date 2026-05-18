#!/usr/bin/env python3
"""
PM-OS Performance Review Generator (v5.0)

Generates structured performance reviews (peer, manager, report, self)
by gathering evidence from Brain, GDocs, Slack, and Jira, then producing
a raw context file and a structured review draft calibrated to tone.

Usage:
    from pm_os_career.tools.review_generator import ReviewGenerator
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# v5 shared utils
try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from config_loader import get_config

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from path_resolver import get_paths

# Brain is optional
try:
    from pm_os_brain.tools.brain_core.brain_loader import BrainLoader

    HAS_BRAIN = True
except ImportError:
    HAS_BRAIN = False


# --- Data Classes ---


@dataclass
class PersonInfo:
    """Resolved person information."""

    name: str
    slug: str
    email: str = ""
    role: str = ""
    squad: str = ""
    slack_id: str = ""
    category: str = "reports"  # reports, manager, stakeholders, self


@dataclass
class ReviewParams:
    """Parsed review command parameters."""

    review_type: str  # "peer", "manager", "report", "self"
    timeframe_months: int  # 6 or 12
    tone: int  # 1-5
    person_name: str = ""
    person_email: str = ""


@dataclass
class DataSourceResult:
    """Result from a single data source gathering step."""

    source_name: str  # "brain", "gdocs", "slack", "jira"
    available: bool = True
    entries: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def count(self) -> int:
        return len(self.entries)


@dataclass
class RawGatherResult:
    """Complete raw data from all sources."""

    params: ReviewParams
    person: Optional[PersonInfo] = None
    sources: List[DataSourceResult] = field(default_factory=list)
    gathered_at: str = ""
    raw_file_path: Optional[str] = None

    @property
    def total_entries(self) -> int:
        return sum(s.count for s in self.sources)

    def get_source(self, name: str) -> Optional[DataSourceResult]:
        for s in self.sources:
            if s.source_name == name:
                return s
        return None


# --- Constants ---

REVIEW_TYPE_LABELS = {
    "peer": "Peer Review",
    "manager": "Upward Review (Manager)",
    "report": "Direct Report Review",
    "self": "Self-Review",
}

TONE_GUIDANCE = {
    1: {
        "label": "Critical: Immediate Action Needed",
        "evidence_emphasis": "Lead with gaps, risks, and missed expectations. Present achievements briefly but focus on areas requiring immediate improvement.",
        "language": "fell short of expectations, immediate action needed, below expectations, significant gaps, did not meet, requires urgent attention",
    },
    2: {
        "label": "Below Expectations",
        "evidence_emphasis": "Lead with areas needing improvement. Acknowledge positives but focus on gaps and inconsistencies.",
        "language": "needs improvement, inconsistent performance, did not meet expectations, areas of concern, room for significant growth",
    },
    3: {
        "label": "Meets Expectations",
        "evidence_emphasis": "Balanced assessment. Present strengths and areas for growth equally. Fair and measured.",
        "language": "solid contribution, met expectations, consistent delivery, room to grow, developing well, reliable performance",
    },
    4: {
        "label": "Exceeds Expectations",
        "evidence_emphasis": "Lead with achievements and strengths. Mention development areas as growth opportunities, not deficiencies.",
        "language": "strong performance, exceeded expectations, notable impact, consistently delivered, impressive results, high performer",
    },
    5: {
        "label": "Outstanding / Rockstar",
        "evidence_emphasis": "Emphasize achievements, outsized impact, and exemplary behaviors. Frame development areas as stretch goals for continued excellence.",
        "language": "exceptional performance, outstanding contribution, role model, transformative impact, consistently exceeded, top performer",
    },
}

REVIEW_QUESTIONS = {
    "report": [
        {
            "id": "what",
            "title": "[WHAT] Performance Impact",
            "prompt": (
                "Describe the impact of your employee's performance this period "
                "relative to expectations for their level. Ensure language and examples "
                "are consistent with the calibrated WHAT rating. Outline the degree to which "
                "they met the scale, complexity, and scope appropriate for their level "
                "(reference feedback, self-reflection, goals, and any notes). "
                "Provide examples of achievements and anything you would have liked "
                "to see the person achieve that they were not able to."
            ),
        },
        {
            "id": "how",
            "title": "[HOW] Behavioral Impact",
            "prompt": (
                "Describe the impact of your employee's behaviors this period "
                "relative to expectations for their level. Ensure language and examples "
                "are consistent with the calibrated HOW rating. Outline the degree to which "
                "their skills, competencies, AI usage, or behaviors met the needs of their "
                "role and level (reference feedback, self-reflection, goals, and any notes). "
                "Provide examples and consider the impact. Refer to the organization's DNA (values)."
            ),
        },
        {
            "id": "development",
            "title": "[WHAT & HOW] Development Focus",
            "prompt": (
                "What would you like your employee to focus on for further development? "
                "List 1 to 2 areas for development. Highlight ways these skills will "
                "capitalize on this person's strengths and personal career interests "
                "and ensure these are challenging but within reach for the employee."
            ),
        },
        {
            "id": "leadership",
            "title": "[PEOPLE MANAGERS ONLY] Leadership & Development",
            "prompt": (
                "To what extent has your employee demonstrated the behaviors needed to "
                "successfully lead and develop their team during this period? "
                "Consider any impact they had outside their day-to-day role, "
                "situations that impacted the organization or team, or any other "
                "information that might provide context to the review."
            ),
        },
    ],
    "self": [
        {
            "id": "what",
            "title": "[WHAT] Goals & Achievements",
            "prompt": (
                "What goals did you meet or exceed and what are the achievements "
                "you are most proud of? Think of 1-2 examples of how you impacted "
                "the success of your team/department/organization. Be clear on what "
                "was delivered in terms of outcomes. Provide examples to demonstrate "
                "when your initiatives/projects/work met the expected/agreed upon "
                "scale, complexity, scope, or outcome."
            ),
        },
        {
            "id": "how",
            "title": "[HOW] Skills & Behaviors",
            "prompt": (
                "What skills, competencies, or behaviors helped you do your job "
                "effectively? Share 1-2 skills, competencies, or behaviors "
                "(e.g., project management, stakeholder alignment, or new technology/AI tools) "
                "and describe how these benefited the accomplishment of goals and performance "
                "for you, your team and/or the organization. Reference the DNA values "
                "and consider the skills you have learned and how you have grown."
            ),
        },
        {
            "id": "development",
            "title": "[WHAT & HOW] Development Focus",
            "prompt": (
                "What would you have liked to achieve this period but weren't able to? "
                "Consider roadblocks or challenges you experienced. Consider the impact "
                "of your behaviors, the expectations for your level tied to the DNA values, "
                "and 1-2 focus areas for development."
            ),
        },
        {
            "id": "support",
            "title": "[DEVELOPMENT] Support",
            "prompt": (
                "How can your manager or the organization support you in your development "
                "and achievement of goals during the next review period? Use this time to "
                "think about the actions your manager can take to help you achieve your "
                "goals and improve in your role. Consider what your broader leadership "
                "can do to support your career journey."
            ),
        },
        {
            "id": "highlights",
            "title": "[OPTIONAL] Other Highlights",
            "prompt": (
                "Is there anything outside your regular work expectations that you'd like "
                "to highlight from this period? Consider other experiences and/or achievements "
                "(e.g., participating in or leading an ERG, enhancing staff development, "
                "serving as a mentor, supporting a colleague on a project outside of your scope)."
            ),
        },
    ],
    "peer": [
        {
            "id": "interaction",
            "title": "Interaction Description",
            "prompt": (
                "Briefly describe your interaction with this individual "
                "(e.g., project, event, initiative, meeting, email/slack, day-to-day work)."
            ),
        },
        {
            "id": "strengths",
            "title": "Strengths",
            "prompt": (
                "What are this employee's strengths? Provide examples and describe "
                "the impact they had (WHAT) and DNA values they exemplified (HOW)."
            ),
        },
        {
            "id": "opportunities",
            "title": "Areas of Opportunity",
            "prompt": (
                "What are their areas of opportunity? If possible, provide examples "
                "and describe the impact to WHAT or HOW. Be as specific as possible "
                "and outline actions the individual can take."
            ),
        },
    ],
    "manager": [
        {
            "id": "impact",
            "title": "Impact & DNA",
            "prompt": (
                "Provide examples and describe the impact they had (WHAT) "
                "and DNA values they exemplified (HOW)."
            ),
        },
        {
            "id": "improvement",
            "title": "Areas for Improvement",
            "prompt": (
                "Be as specific as possible and outline actions they can take. "
                "If possible, provide examples and describe the impact to WHAT or HOW."
            ),
        },
        {
            "id": "actions",
            "title": "Specific Actions",
            "prompt": (
                "Think of 1-2 specific actions or behaviors your manager "
                "can change to support you better."
            ),
        },
    ],
}

# Jira JQL templates for evidence gathering
JIRA_JQL_TEMPLATES = {
    "assigned": 'assignee = "{email}" AND updated >= "-{months}m" ORDER BY updated DESC',
    "reported": 'reporter = "{email}" AND updated >= "-{months}m" ORDER BY updated DESC',
}

RAW_FILE_TEMPLATE = """# Review Evidence: {review_type_label}

**Person:** {person_name} ({person_email})
**Review Type:** {review_type_label}
**Timeframe:** Last {timeframe_months} months (since {since_date})
**Tone/Direction:** {tone}/5 ({tone_label})
**Gathered:** {gathered_at}
**Reviewer:** {reviewer_name}

---

## Data Sources Summary

| Source | Status | Entries |
|--------|--------|---------|
{source_summary_rows}

---

{source_sections}

---

*Generated by PM-OS Career Plugin v5.0 - Review Generator*
"""


class ReviewGenerator:
    """Generates performance reviews with multi-source evidence gathering."""

    def __init__(
        self,
        config: Optional[Any] = None,
        paths: Optional[Any] = None,
    ):
        self.config = config or get_config()
        self.paths = paths or get_paths()
        self._brain_loader = None

    # --- Properties ---

    @property
    def user_name(self) -> str:
        """Get the current user's name from config."""
        return self.config.get("user.name", "")

    @property
    def user_email(self) -> str:
        """Get the current user's email from config."""
        return self.config.get("user.email", "")

    @property
    def team_dir(self) -> Path:
        """Get the team directory path."""
        return Path(self.paths.user) / "team"

    @property
    def plugin_dir(self) -> Path:
        """Get the plugin directory for reference files."""
        # Walk up from tools/ to plugin root
        return Path(__file__).parent.parent

    # --- Utility ---

    def _slugify(self, name: str) -> str:
        """Convert a name to a slug (lowercase, hyphenated)."""
        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9\\s-]", "", slug)
        slug = re.sub(r"[\\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")

    def _get_brain_loader(self) -> Optional[Any]:
        """Get brain loader if available."""
        if not HAS_BRAIN:
            return None
        if self._brain_loader is None:
            try:
                self._brain_loader = BrainLoader(paths=self.paths)
            except Exception:
                logger.debug("Brain loader init failed, continuing without Brain")
        return self._brain_loader

    # --- Parameter Parsing ---

    def parse_params(self, args: str) -> ReviewParams:
        """Parse review command arguments.

        Expected format:
            --peer --6m --4 "Alex Partner, alex.partner@example.com"
            --self --6m --3

        Returns:
            ReviewParams with validated fields.

        Raises:
            ValueError if arguments are invalid.
        """
        # Extract review type
        review_type = None
        for rt in ("peer", "manager", "report", "self"):
            if f"--{rt}" in args:
                if review_type is not None:
                    raise ValueError(
                        f"Multiple review types specified: --{review_type} and --{rt}. "
                        "Choose exactly one."
                    )
                review_type = rt

        if review_type is None:
            raise ValueError(
                "No review type specified. Use --peer, --manager, --report, or --self."
            )

        # Extract timeframe
        timeframe_months = None
        for tf in ("6m", "12m"):
            if f"--{tf}" in args:
                timeframe_months = int(tf.replace("m", ""))

        if timeframe_months is None:
            default_tf = self.config.get("review.default_timeframe", "6m")
            timeframe_months = int(default_tf.replace("m", ""))

        # Extract tone (1-5)
        tone = None
        for t in range(1, 6):
            if f"--{t}" in args:
                tone = t

        if tone is None:
            tone = self.config.get("review.default_tone", 3)

        # Extract person (quoted string "Name, email")
        person_name = ""
        person_email = ""
        quoted_match = re.search(r'"([^"]+)"', args)
        if quoted_match:
            person_str = quoted_match.group(1)
            parts = [p.strip() for p in person_str.split(",")]
            person_name = parts[0]
            if len(parts) > 1:
                person_email = parts[1]

        # Validate: non-self requires person
        if review_type != "self" and not person_name:
            raise ValueError(
                f"--{review_type} requires a person. "
                'Usage: --{review_type} --6m --3 "Name, email"'
            )

        return ReviewParams(
            review_type=review_type,
            timeframe_months=timeframe_months,
            tone=tone,
            person_name=person_name,
            person_email=person_email,
        )

    # --- Person Resolution ---

    def resolve_person(self, params: ReviewParams) -> PersonInfo:
        """Resolve the review subject from config or Brain.

        For --self, returns the user's own info.
        For others, looks up in config team hierarchy then Brain.
        """
        if params.review_type == "self":
            return PersonInfo(
                name=self.user_name,
                slug=self._slugify(self.user_name),
                email=self.user_email,
                role=self.config.get("user.role", ""),
                category="self",
            )

        name_lower = params.person_name.lower().strip()

        # Check direct reports
        reports = self.config.get("team.reports", [])
        for report in reports:
            report_name = ""
            if isinstance(report, dict):
                report_name = report.get("name", "")
            elif isinstance(report, str):
                report_name = report

            if report_name and name_lower in report_name.lower():
                return PersonInfo(
                    name=report_name,
                    slug=self._slugify(report_name),
                    email=report.get("email", params.person_email)
                    if isinstance(report, dict)
                    else params.person_email,
                    role=report.get("role", "") if isinstance(report, dict) else "",
                    squad=report.get("squad", "") if isinstance(report, dict) else "",
                    slack_id=report.get("slack_id", "")
                    if isinstance(report, dict)
                    else "",
                    category="reports",
                )

        # Check manager
        manager = self.config.get("team.manager", {})
        if isinstance(manager, dict):
            mgr_name = manager.get("name", "")
            if mgr_name and name_lower in mgr_name.lower():
                return PersonInfo(
                    name=mgr_name,
                    slug=self._slugify(mgr_name),
                    email=manager.get("email", params.person_email),
                    role=manager.get("role", ""),
                    slack_id=manager.get("slack_id", ""),
                    category="manager",
                )

        # Check stakeholders
        stakeholders = self.config.get("team.stakeholders", [])
        for sh in stakeholders:
            sh_name = ""
            if isinstance(sh, dict):
                sh_name = sh.get("name", "")
            elif isinstance(sh, str):
                sh_name = sh

            if sh_name and name_lower in sh_name.lower():
                return PersonInfo(
                    name=sh_name,
                    slug=self._slugify(sh_name),
                    email=sh.get("email", params.person_email)
                    if isinstance(sh, dict)
                    else params.person_email,
                    role=sh.get("role", "") if isinstance(sh, dict) else "",
                    slack_id=sh.get("slack_id", "")
                    if isinstance(sh, dict)
                    else "",
                    category="stakeholders",
                )

        # Brain fallback
        brain = self._get_brain_loader()
        if brain:
            try:
                result = brain.search(params.person_name)
                if result:
                    logger.info("Found %s in Brain", params.person_name)
            except Exception:
                pass

        # Final fallback: use provided name/email as-is
        return PersonInfo(
            name=params.person_name,
            slug=self._slugify(params.person_name),
            email=params.person_email,
            category="reports",  # default assumption
        )

    # --- Framework Loading ---

    def load_frameworks(self) -> Dict[str, str]:
        """Load values and career framework reference files.

        Checks config for custom paths first, falls back to plugin reference/ defaults.

        Returns:
            Dict with 'values' and 'career' keys containing markdown text.
        """
        frameworks = {}

        # Values framework
        values_path = self.config.get("review.values_framework_path", "")
        if values_path:
            values_path = Path(values_path)
        else:
            values_path = self.plugin_dir / "reference" / "values_framework.md"

        if values_path.exists():
            frameworks["values"] = values_path.read_text(encoding="utf-8")
        else:
            logger.warning("Values framework not found at %s", values_path)
            frameworks["values"] = ""

        # Career framework
        career_path = self.config.get("review.career_framework_path", "")
        if career_path:
            career_path = Path(career_path)
        else:
            career_path = self.plugin_dir / "reference" / "career_framework.md"

        if career_path.exists():
            frameworks["career"] = career_path.read_text(encoding="utf-8")
        else:
            logger.warning("Career framework not found at %s", career_path)
            frameworks["career"] = ""

        return frameworks

    # --- Review Questions ---

    def get_review_questions(self, review_type: str) -> List[Dict[str, str]]:
        """Get the review questions for a given type."""
        return REVIEW_QUESTIONS.get(review_type, [])

    # --- Tone Guidance ---

    def get_tone_guidance(self, tone: int) -> Dict[str, str]:
        """Get tone label and guidance for the given tone level."""
        return TONE_GUIDANCE.get(tone, TONE_GUIDANCE[3])

    # --- Output Paths ---

    def get_review_dir(self, person: PersonInfo) -> Path:
        """Get the review output directory for a person.

        All reviews are saved to user/team/reviews/ with filenames
        that include the review type and person slug for disambiguation.
        """
        return self.team_dir / "reviews"

    def _build_filename(self, params: ReviewParams, person: PersonInfo, suffix: str = "") -> str:
        """Build a review filename.

        Format: review_{YYYYMMDD-HHMM}_{type}_{timeframe}_{slug}{suffix}.md
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        parts = [
            "review",
            timestamp,
            params.review_type,
            f"{params.timeframe_months}m",
            person.slug,
        ]
        return "_".join(parts) + f"{suffix}.md"

    def get_raw_path(self, params: ReviewParams, person: PersonInfo) -> Path:
        """Get the path for the raw evidence file."""
        review_dir = self.get_review_dir(person)
        return review_dir / self._build_filename(params, person, "_RAW")

    def get_output_path(self, params: ReviewParams, person: PersonInfo) -> Path:
        """Get the path for the final review file."""
        review_dir = self.get_review_dir(person)
        return review_dir / self._build_filename(params, person)

    # --- Timeframe ---

    def get_timeframe_start(self, params: ReviewParams) -> datetime:
        """Calculate the start date for evidence gathering."""
        return datetime.now() - timedelta(days=params.timeframe_months * 30)

    # --- JQL Queries ---

    def get_jira_queries(self, person: PersonInfo, params: ReviewParams) -> Dict[str, str]:
        """Build Jira JQL queries for the person.

        Returns dict of query_name -> JQL string.
        """
        email = person.email
        months = params.timeframe_months
        if not email:
            return {}

        return {
            "assigned": f'assignee = "{email}" AND updated >= "-{months}m" ORDER BY updated DESC',
            "reported": f'reporter = "{email}" AND updated >= "-{months}m" ORDER BY updated DESC',
        }

    # --- GDocs Search Queries ---

    def get_gdocs_search_queries(self, person: PersonInfo) -> List[str]:
        """Build GDocs search queries for the person.

        Returns list of search terms to try.
        """
        queries = []
        if person.name:
            queries.append(person.name)
            # Also try "1:1" format
            reviewer_first = self.user_name.split()[0] if self.user_name else ""
            person_first = person.name.split()[0] if person.name else ""
            if reviewer_first and person_first:
                queries.append(f"{person_first}:{reviewer_first} 1:1")
                queries.append(f"{reviewer_first}:{person_first} 1:1")
        return queries

    # --- Raw File Generation ---

    def save_raw(self, result: RawGatherResult) -> str:
        """Save raw gathered data to a RAW.md file.

        Returns the file path as string.
        """
        person = result.person or PersonInfo(
            name=result.params.person_name,
            slug=self._slugify(result.params.person_name),
            email=result.params.person_email,
        )

        review_dir = self.get_review_dir(person)
        review_dir.mkdir(parents=True, exist_ok=True)

        raw_path = self.get_raw_path(result.params, person)
        tone_info = self.get_tone_guidance(result.params.tone)
        since_date = self.get_timeframe_start(result.params).strftime("%Y-%m-%d")

        # Build source summary rows
        source_rows = []
        for src in result.sources:
            status = "Available" if src.available else f"Unavailable ({src.error or 'N/A'})"
            source_rows.append(f"| {src.source_name.title()} | {status} | {src.count} |")
        source_summary = "\n".join(source_rows) if source_rows else "| None | - | 0 |"

        # Build source detail sections
        source_sections = []
        for src in result.sources:
            if not src.available or src.count == 0:
                continue
            section = f"## {src.source_name.title()} Evidence\n\n"
            for i, entry in enumerate(src.entries, 1):
                title = entry.get("title", f"Entry {i}")
                content = entry.get("content", "")
                source_ref = entry.get("source", "")
                date = entry.get("date", "")
                section += f"### {title}\n"
                if date:
                    section += f"**Date:** {date}\n"
                if source_ref:
                    section += f"**Source:** {source_ref}\n"
                section += f"\n{content}\n\n---\n\n"
            source_sections.append(section)

        content = RAW_FILE_TEMPLATE.format(
            review_type_label=REVIEW_TYPE_LABELS.get(
                result.params.review_type, result.params.review_type
            ),
            person_name=person.name,
            person_email=person.email,
            timeframe_months=result.params.timeframe_months,
            since_date=since_date,
            tone=result.params.tone,
            tone_label=tone_info["label"],
            gathered_at=result.gathered_at or datetime.now().strftime("%Y-%m-%d %H:%M"),
            reviewer_name=self.user_name,
            source_summary_rows=source_summary,
            source_sections="\n".join(source_sections) if source_sections else "*No evidence gathered from any source.*",
        )

        raw_path.write_text(content, encoding="utf-8")
        result.raw_file_path = str(raw_path)
        return str(raw_path)

    # --- Review Prompt Builder ---

    def build_review_prompt(self, raw_result: RawGatherResult) -> str:
        """Build the structured prompt for Claude to generate the review.

        Assembles: raw evidence + frameworks + questions + tone guidance.
        Returns a prompt string that Claude can use to write the review.
        """
        frameworks = self.load_frameworks()
        questions = self.get_review_questions(raw_result.params.review_type)
        tone_info = self.get_tone_guidance(raw_result.params.tone)
        person = raw_result.person

        prompt_parts = []

        # Header
        prompt_parts.append(
            f"Generate a {REVIEW_TYPE_LABELS.get(raw_result.params.review_type, 'Review')} "
            f"for **{person.name if person else raw_result.params.person_name}**."
        )

        # Tone instructions
        prompt_parts.append(f"\n## Tone: {raw_result.params.tone}/5 ({tone_info['label']})\n")
        prompt_parts.append(f"**Evidence emphasis:** {tone_info['evidence_emphasis']}")
        prompt_parts.append(f"**Language calibration:** Use vocabulary like: {tone_info['language']}")

        # Frameworks
        if frameworks.get("values"):
            prompt_parts.append("\n## Values Framework (for HOW assessment)\n")
            prompt_parts.append(frameworks["values"])

        if frameworks.get("career"):
            prompt_parts.append("\n## Career Framework (for level expectations)\n")
            prompt_parts.append(frameworks["career"])

        # Questions
        prompt_parts.append("\n## Review Sections to Complete\n")
        prompt_parts.append(
            "Answer each section below using specific evidence from the raw data. "
            "Cite dates, ticket numbers, project names, and direct observations where possible."
        )
        for q in questions:
            prompt_parts.append(f"\n### {q['title']}\n")
            prompt_parts.append(f"**Guidance:** {q['prompt']}\n")

        # Raw evidence reference
        if raw_result.raw_file_path:
            prompt_parts.append(f"\n## Raw Evidence File\n")
            prompt_parts.append(f"Read the raw evidence file at: `{raw_result.raw_file_path}`")
            prompt_parts.append(
                "Use the evidence in this file to ground every statement in the review "
                "with specific examples, dates, and references."
            )

        return "\n".join(prompt_parts)

    # --- Local Evidence (1:1 Notes, Career Logs) ---

    def gather_local_evidence(self, person: PersonInfo, since: datetime) -> DataSourceResult:
        """Gather evidence from local files (1:1 notes, career logs, meeting preps).

        This runs locally without MCP calls.
        """
        entries = []
        since_str = since.strftime("%Y-%m-%d")

        # 1:1 notes
        oneonone_dir = self.team_dir / person.category / person.slug / "1on1s"
        if oneonone_dir.exists():
            for note_file in sorted(oneonone_dir.glob("*.md"), reverse=True):
                # Extract date from filename (YYYY-MM-DD prefix)
                date_match = re.match(r"(\d{4}-\d{2}-\d{2})", note_file.name)
                if date_match:
                    file_date = date_match.group(1)
                    if file_date < since_str:
                        continue
                try:
                    content = note_file.read_text(encoding="utf-8")
                    entries.append({
                        "title": f"1:1 Note: {note_file.stem}",
                        "date": date_match.group(1) if date_match else "",
                        "content": content[:3000],
                        "source": f"local:{note_file}",
                    })
                except Exception as e:
                    logger.debug("Failed to read %s: %s", note_file, e)

        # Career plan and logs
        career_dir = self.team_dir / person.category / person.slug / "career"
        if career_dir.exists():
            for career_file in career_dir.glob("*.md"):
                try:
                    content = career_file.read_text(encoding="utf-8")
                    entries.append({
                        "title": f"Career: {career_file.stem}",
                        "date": "",
                        "content": content[:3000],
                        "source": f"local:{career_file}",
                    })
                except Exception as e:
                    logger.debug("Failed to read %s: %s", career_file, e)

        return DataSourceResult(
            source_name="local",
            available=True,
            entries=entries,
        )


# --- CLI Smoke Test ---

if __name__ == "__main__":
    gen = ReviewGenerator()
    print(f"User: {gen.user_name}")
    print(f"Email: {gen.user_email}")
    print(f"Team dir: {gen.team_dir}")
    print(f"Plugin dir: {gen.plugin_dir}")
    print(f"Brain available: {HAS_BRAIN}")

    # Load frameworks
    frameworks = gen.load_frameworks()
    print(f"Values framework: {len(frameworks.get('values', ''))} chars")
    print(f"Career framework: {len(frameworks.get('career', ''))} chars")

    # Test param parsing
    test_args = '--peer --6m --4 "Alex Partner, alex.partner@example.com"'
    try:
        params = gen.parse_params(test_args)
        print(f"\nParsed: type={params.review_type}, months={params.timeframe_months}, "
              f"tone={params.tone}, person={params.person_name}, email={params.person_email}")
    except ValueError as e:
        print(f"Parse error: {e}")

    # Test self
    test_self = "--self --6m --3"
    try:
        params = gen.parse_params(test_self)
        print(f"Self: type={params.review_type}, months={params.timeframe_months}, tone={params.tone}")
    except ValueError as e:
        print(f"Parse error: {e}")

    # Test review questions
    for rt in ("peer", "manager", "report", "self"):
        qs = gen.get_review_questions(rt)
        print(f"\n{rt} questions: {len(qs)}")
        for q in qs:
            print(f"  - {q['title']}")

    # Test tone guidance
    for t in range(1, 6):
        g = gen.get_tone_guidance(t)
        print(f"Tone {t}: {g['label']}")
