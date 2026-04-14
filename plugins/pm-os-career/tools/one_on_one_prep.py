#!/usr/bin/env python3
"""
PM-OS 1:1 Meeting Prep (v5.0)

Prepares structured 1:1 meeting agendas for direct reports,
manager, and stakeholders. Pulls context from previous notes,
daily context, career plans, and Brain entities (if available).

Usage:
    from pm_os_career.tools.one_on_one_prep import OneOnOnePreparer
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
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
class PersonContext:
    """Resolved person with relationship context."""
    name: str
    slug: str
    role: str = ""
    team: str = ""
    category: str = "reports"  # reports, manager, stakeholders
    oneonone_dir: Optional[Path] = None
    career_dir: Optional[Path] = None


@dataclass
class PrepSection:
    """A section of the 1:1 prep document."""
    title: str
    items: List[str] = field(default_factory=list)


@dataclass
class OneOnOnePrep:
    """Complete 1:1 prep document."""
    person_name: str
    date: str
    relationship: str
    sections: List[PrepSection] = field(default_factory=list)
    previous_action_items: List[str] = field(default_factory=list)
    brain_context_loaded: bool = False

    def to_markdown(self) -> str:
        """Render the prep as markdown."""
        lines = [
            "## 1:1 Prep — %s | %s" % (self.person_name, self.date),
            "",
        ]
        for section in self.sections:
            lines.append("### %s" % section.title)
            if section.items:
                for item in section.items:
                    lines.append("- %s" % item)
            else:
                lines.append("- *No items*")
            lines.append("")

        return "\n".join(lines)


# --- Time Allocation ---

TIME_ALLOCATION = {
    "reports": {
        "Check-in": 3,
        "Blockers": 5,
        "Projects": 12,
        "Development": 5,
        "Asks": 5,
    },
    "manager": {
        "Check-in": 3,
        "Blockers": 3,
        "Projects": 14,
        "Development": 2,
        "Asks": 8,
    },
    "stakeholders": {
        "Check-in": 3,
        "Blockers": 3,
        "Projects": 16,
        "Development": 0,
        "Asks": 8,
    },
}


class OneOnOnePreparer:
    """Prepares 1:1 meeting agendas with context."""

    def __init__(
        self,
        config: Optional[Any] = None,
        paths: Optional[Any] = None,
    ):
        self.config = config or get_config()
        self.paths = paths or get_paths()
        self._brain_loader = None

    @property
    def user_name(self) -> str:
        """Get the user's name."""
        return self.config.get("user.name", "")

    @property
    def team_dir(self) -> Path:
        """Get the team directory."""
        return Path(self.paths.user) / "team"

    def _get_brain_loader(self) -> Optional[Any]:
        """Get brain loader if available."""
        if not HAS_BRAIN:
            return None
        if self._brain_loader is None:
            try:
                self._brain_loader = BrainLoader(paths=self.paths)
            except Exception:
                logger.debug("Brain loader init failed")
        return self._brain_loader

    def _slugify(self, name: str) -> str:
        """Convert a name to a slug."""
        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")

    def resolve_person(self, name: str) -> Optional[PersonContext]:
        """Resolve a person from config."""
        name_lower = name.lower().strip()

        # Check direct reports
        reports = self.config.get("team.reports", [])
        for report in reports:
            report_name = ""
            report_role = ""
            report_team = ""
            if isinstance(report, dict):
                report_name = report.get("name", "")
                report_role = report.get("role", "")
                report_team = report.get("team", "")
            elif isinstance(report, str):
                report_name = report

            if report_name and name_lower in report_name.lower():
                slug = self._slugify(report_name)
                return PersonContext(
                    name=report_name,
                    slug=slug,
                    role=report_role,
                    team=report_team,
                    category="reports",
                    oneonone_dir=self.team_dir / "reports" / slug / "1on1s",
                    career_dir=self.team_dir / "reports" / slug / "career",
                )

        # Check manager
        manager = self.config.get("team.manager", {})
        if manager:
            mgr_name = manager.get("name", "") if isinstance(manager, dict) else str(manager)
            if mgr_name and name_lower in mgr_name.lower():
                slug = self._slugify(mgr_name)
                return PersonContext(
                    name=mgr_name,
                    slug=slug,
                    role=manager.get("role", "") if isinstance(manager, dict) else "",
                    category="manager",
                    oneonone_dir=self.team_dir / "manager" / slug / "1on1s",
                )

        # Check stakeholders
        stakeholders = self.config.get("team.stakeholders", [])
        for sh in stakeholders:
            sh_name = ""
            sh_role = ""
            if isinstance(sh, dict):
                sh_name = sh.get("name", "")
                sh_role = sh.get("role", "")
            elif isinstance(sh, str):
                sh_name = sh

            if sh_name and name_lower in sh_name.lower():
                slug = self._slugify(sh_name)
                return PersonContext(
                    name=sh_name,
                    slug=slug,
                    role=sh_role,
                    category="stakeholders",
                    oneonone_dir=self.team_dir / "stakeholders" / slug / "1on1s",
                )

        # Fallback
        slug = self._slugify(name)
        return PersonContext(
            name=name,
            slug=slug,
            category="reports",
            oneonone_dir=self.team_dir / "reports" / slug / "1on1s",
        )

    def _load_previous_notes(self, person: PersonContext, limit: int = 3) -> List[Dict[str, str]]:
        """Load recent 1:1 notes for a person."""
        if not person.oneonone_dir or not person.oneonone_dir.exists():
            return []

        notes = []
        files = sorted(person.oneonone_dir.glob("*.md"), reverse=True)
        # Skip archive directory
        files = [f for f in files if f.is_file()]

        for note_file in files[:limit]:
            try:
                content = note_file.read_text(encoding="utf-8")
                notes.append({
                    "file": note_file.name,
                    "content": content[:3000],
                })
            except Exception:
                continue
        return notes

    def _extract_action_items(self, notes: List[Dict[str, str]]) -> List[str]:
        """Extract open action items from previous notes."""
        action_items = []
        for note in notes:
            content = note.get("content", "")
            # Match unchecked checkboxes
            for match in re.finditer(r"^- \[ \] (.+)$", content, re.MULTILINE):
                item = match.group(1).strip()
                if item:
                    action_items.append(item)
        return action_items

    def _load_career_context(self, person: PersonContext) -> List[str]:
        """Load career development items if career dir exists."""
        if not person.career_dir or not person.career_dir.exists():
            return []

        items = []

        # Check for active career plan
        for plan_file in person.career_dir.glob("Career_Plan_*.md"):
            try:
                content = plan_file.read_text(encoding="utf-8")
                # Extract key risks section
                if "Key Risks" in content:
                    risks_section = content.split("Key Risks")[1][:500]
                    items.append("Career plan active: %s" % plan_file.stem)
                elif "Draft" in content:
                    items.append("Career plan in draft: %s" % plan_file.stem)
            except Exception:
                continue

        # Check feedback log for recent entries
        feedback_path = person.career_dir / "feedback_log.md"
        if feedback_path.exists():
            try:
                content = feedback_path.read_text(encoding="utf-8")
                recent = re.findall(
                    r"^\| (\d{4}-\d{2}-\d{2}) \| (\w+) \| (.+?) \|",
                    content,
                    re.MULTILINE,
                )
                if recent:
                    last = recent[-1]
                    items.append("Last feedback: %s (%s) — %s" % (last[0], last[1], last[2].strip()))
            except Exception:
                pass

        return items

    def _load_brain_context(self, person: PersonContext) -> List[str]:
        """Load context from Brain entity if available."""
        brain = self._get_brain_loader()
        if not brain:
            return []

        try:
            entity = brain.search(person.name)
            if entity:
                items = []
                if hasattr(entity, "relationships"):
                    for rel in getattr(entity, "relationships", [])[:5]:
                        items.append("Brain: %s" % str(rel))
                return items
        except Exception:
            logger.debug("Brain context load failed for %s", person.name)
        return []

    def prepare(self, person_name: str) -> OneOnOnePrep:
        """Prepare a 1:1 meeting agenda for a person."""
        person = self.resolve_person(person_name)
        today = datetime.now().strftime("%Y-%m-%d")

        previous_notes = self._load_previous_notes(person)
        action_items = self._extract_action_items(previous_notes)
        career_items = self._load_career_context(person)
        brain_items = self._load_brain_context(person)

        # Build sections
        sections = []

        # Check-in
        checkin_items = []
        if action_items:
            checkin_items.append("Open items from last meeting:")
            for item in action_items[:5]:
                checkin_items.append("  - %s" % item)
        checkin_items.append("What's top of mind?")
        sections.append(PrepSection(title="Check-in", items=checkin_items))

        # Blockers
        blocker_items = ["Known blockers relevant to %s?" % person.name]
        if brain_items:
            blocker_items.extend(brain_items[:3])
        sections.append(PrepSection(title="Blockers", items=blocker_items))

        # Projects
        project_items = []
        if person.team:
            project_items.append("Team: %s" % person.team)
        project_items.append("Quick status on key initiatives")
        sections.append(PrepSection(title="Projects", items=project_items))

        # Development (skip for stakeholders)
        if person.category != "stakeholders":
            dev_items = []
            if career_items:
                dev_items.extend(career_items)
            else:
                dev_items.append("Career development check-in")
            sections.append(PrepSection(title="Development", items=dev_items))

        # Asks
        ask_items = [
            "What do I need from %s?" % person.name.split()[0],
            "What does %s need from me?" % person.name.split()[0],
        ]
        sections.append(PrepSection(title="Asks", items=ask_items))

        return OneOnOnePrep(
            person_name=person.name,
            date=today,
            relationship=person.category,
            sections=sections,
            previous_action_items=action_items,
            brain_context_loaded=bool(brain_items),
        )

    def save_prep(self, prep: OneOnOnePrep, person_name: str) -> str:
        """Save the prep document and return the file path."""
        person = self.resolve_person(person_name)
        if not person.oneonone_dir:
            return ""

        person.oneonone_dir.mkdir(parents=True, exist_ok=True)
        filename = "%s-prep.md" % prep.date
        file_path = person.oneonone_dir / filename
        file_path.write_text(prep.to_markdown(), encoding="utf-8")
        return str(file_path)

    def list_upcoming(self) -> List[Dict[str, str]]:
        """List all team members with 1:1 directories."""
        members = []

        reports = self.config.get("team.reports", [])
        for report in reports:
            name = report.get("name", "") if isinstance(report, dict) else str(report)
            if name:
                slug = self._slugify(name)
                oneonone_dir = self.team_dir / "reports" / slug / "1on1s"
                last_prep = ""
                if oneonone_dir.exists():
                    preps = sorted(oneonone_dir.glob("*-prep.md"), reverse=True)
                    if preps:
                        last_prep = preps[0].stem.replace("-prep", "")
                members.append({
                    "name": name,
                    "category": "report",
                    "last_prep": last_prep,
                })

        manager = self.config.get("team.manager", {})
        if manager:
            mgr_name = manager.get("name", "") if isinstance(manager, dict) else str(manager)
            if mgr_name:
                members.append({"name": mgr_name, "category": "manager", "last_prep": ""})

        return members


# --- CLI for testing ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    preparer = OneOnOnePreparer()
    print("=== 1:1 Prep ===")
    print("User: %s" % preparer.user_name)
    print("Team dir: %s" % preparer.team_dir)
    print("Brain available: %s" % HAS_BRAIN)

    members = preparer.list_upcoming()
    print("\nTeam members with 1:1s:")
    for m in members:
        print("  %s (%s) — last prep: %s" % (m["name"], m["category"], m["last_prep"] or "none"))
