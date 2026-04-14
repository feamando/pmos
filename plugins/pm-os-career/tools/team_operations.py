#!/usr/bin/env python3
"""
PM-OS Team Operations (v5.0)

Team capacity planning, hiring pipeline status, and org chart generation.
Reads from config and user/team/ directory structure.

Usage:
    from pm_os_career.tools.team_operations import TeamOperations
"""

import logging
import re
from dataclasses import dataclass, field
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


# --- Data Classes ---

@dataclass
class TeamMember:
    """A team member with metadata."""
    name: str
    role: str = ""
    team: str = ""
    category: str = "report"  # report, manager, stakeholder
    cadence: str = "weekly"


@dataclass
class HiringPipelineEntry:
    """A candidate or role in the hiring pipeline."""
    role: str = ""
    candidates: int = 0
    recent_scorecards: List[str] = field(default_factory=list)
    status: str = "open"


@dataclass
class CapacityOverview:
    """Team capacity summary."""
    total_headcount: int = 0
    by_team: Dict[str, int] = field(default_factory=dict)
    open_positions: int = 0
    members: List[TeamMember] = field(default_factory=list)


@dataclass
class OrgChart:
    """Text-based org chart data."""
    manager_name: str = ""
    manager_role: str = ""
    user_name: str = ""
    user_role: str = ""
    reports: List[TeamMember] = field(default_factory=list)
    stakeholders: List[TeamMember] = field(default_factory=list)
    department: str = ""

    def to_text(self) -> str:
        """Render as a text-based org chart."""
        lines = []

        if self.department:
            lines.append("  %s" % self.department)
            lines.append("  %s" % ("=" * len(self.department)))
            lines.append("")

        # Manager
        if self.manager_name:
            lines.append("  %s (%s)" % (self.manager_name, self.manager_role))
            lines.append("    |")

        # User
        lines.append("  %s (%s)" % (self.user_name, self.user_role))

        # Reports
        if self.reports:
            for i, report in enumerate(self.reports):
                is_last = i == len(self.reports) - 1
                prefix = "  `-- " if is_last else "  |-- "
                team_str = " [%s]" % report.team if report.team else ""
                lines.append("%s%s (%s)%s" % (prefix, report.name, report.role, team_str))

        # Stakeholders
        if self.stakeholders:
            lines.append("")
            lines.append("  Stakeholders (dotted line):")
            for sh in self.stakeholders:
                lines.append("  ... %s (%s)" % (sh.name, sh.role))

        return "\n".join(lines)


class TeamOperations:
    """Team capacity, hiring pipeline, and org chart operations."""

    def __init__(
        self,
        config: Optional[Any] = None,
        paths: Optional[Any] = None,
    ):
        self.config = config or get_config()
        self.paths = paths or get_paths()

    @property
    def user_name(self) -> str:
        return self.config.get("user.name", "")

    @property
    def user_role(self) -> str:
        return self.config.get("user.role", "")

    @property
    def team_dir(self) -> Path:
        return Path(self.paths.user) / "team"

    @property
    def interviews_dir(self) -> Path:
        custom_path = self.config.get("team.scorecard_path")
        if custom_path:
            return Path(self.paths.user) / custom_path
        return self.team_dir / "recruiting" / "interviews"

    def _parse_members(self, member_list: list, category: str) -> List[TeamMember]:
        """Parse a config member list into TeamMember objects."""
        members = []
        for item in member_list:
            if isinstance(item, dict):
                members.append(TeamMember(
                    name=item.get("name", ""),
                    role=item.get("role", ""),
                    team=item.get("team", ""),
                    category=category,
                    cadence=item.get("cadence", "weekly"),
                ))
            elif isinstance(item, str):
                members.append(TeamMember(name=item, category=category))
        return members

    def get_capacity(self) -> CapacityOverview:
        """Generate a team capacity overview."""
        reports = self._parse_members(
            self.config.get("team.reports", []), "report",
        )

        # Count by team
        by_team: Dict[str, int] = {}
        for member in reports:
            team = member.team or "Unassigned"
            by_team[team] = by_team.get(team, 0) + 1

        # Count open positions from recruiting directory
        open_positions = 0
        recruiting_dir = self.team_dir / "recruiting"
        if recruiting_dir.exists():
            for subdir in recruiting_dir.iterdir():
                if subdir.is_dir() and subdir.name != "interviews":
                    open_positions += 1

        return CapacityOverview(
            total_headcount=len(reports),
            by_team=by_team,
            open_positions=open_positions,
            members=reports,
        )

    def get_hiring_pipeline(self) -> List[HiringPipelineEntry]:
        """Get hiring pipeline status from scorecard files."""
        pipeline: Dict[str, HiringPipelineEntry] = {}

        if not self.interviews_dir.exists():
            return []

        for f in sorted(self.interviews_dir.glob("*scorecard*.md"), reverse=True):
            try:
                content = f.read_text(encoding="utf-8")
                role_match = re.search(r"\*\*Role:\*\*\s*(.+)", content)
                role = role_match.group(1).strip() if role_match else "Unknown"

                if role not in pipeline:
                    pipeline[role] = HiringPipelineEntry(role=role)

                pipeline[role].candidates += 1
                pipeline[role].recent_scorecards.append(f.name)
            except Exception:
                continue

        return list(pipeline.values())

    def get_org_chart(self) -> OrgChart:
        """Generate an org chart from config."""
        reports = self._parse_members(
            self.config.get("team.reports", []), "report",
        )
        stakeholders = self._parse_members(
            self.config.get("team.stakeholders", []), "stakeholder",
        )

        manager = self.config.get("team.manager", {})
        mgr_name = ""
        mgr_role = ""
        if isinstance(manager, dict):
            mgr_name = manager.get("name", "")
            mgr_role = manager.get("role", "")
        elif isinstance(manager, str):
            mgr_name = manager

        department = self.config.get("team.department", "")

        return OrgChart(
            manager_name=mgr_name,
            manager_role=mgr_role,
            user_name=self.user_name,
            user_role=self.user_role,
            reports=reports,
            stakeholders=stakeholders,
            department=department,
        )

    def get_team_context_path(self) -> Optional[Path]:
        """Get the team context file if it exists."""
        context_path = self.team_dir / "team-context.md"
        if context_path.exists():
            return context_path
        return None


# --- CLI for testing ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    ops = TeamOperations()
    print("=== Team Operations ===")
    print("User: %s (%s)" % (ops.user_name, ops.user_role))
    print()

    # Capacity
    cap = ops.get_capacity()
    print("Capacity: %d HC" % cap.total_headcount)
    for team, count in cap.by_team.items():
        print("  %s: %d" % (team, count))
    print("Open positions: %d" % cap.open_positions)
    print()

    # Org chart
    chart = ops.get_org_chart()
    print("Org Chart:")
    print(chart.to_text())
    print()

    # Hiring
    pipeline = ops.get_hiring_pipeline()
    print("Hiring Pipeline: %d roles" % len(pipeline))
    for entry in pipeline:
        print("  %s: %d candidates" % (entry.role, entry.candidates))
