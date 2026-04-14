#!/usr/bin/env python3
"""
PM-OS Reporting Sprint Report Generator (v5.0)

Generates bi-weekly sprint reports with clustered, prioritized work items.
Fetches from Jira, clusters by epic/theme, synthesizes via LLM, and outputs CSV.

Features:
- Active JQL fetching with full ticket content and epic links
- Intelligent clustering by epic/theme into Sprint Focus / Secondary priority
- LLM synthesis into outcome-focused sentences (Claude via Bedrock, with fallback)
- External format synthesis (concise numbered format for leadership)
- Support for both Sprint and Kanban boards
- Date range support for historical sprint reports
- GitHub PR activity and experiment linking

Usage:
    from pm_os_reporting.tools.sprint_report_generator import SprintReportGenerator
"""

import csv
import glob
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# --- v5 imports: path resolver, config, connector bridge ---
try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from core.config_loader import get_config

try:
    from pm_os_base.tools.core.connector_bridge import get_auth
except ImportError:
    from core.connector_bridge import get_auth

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


# ============================================================================
# Data Structures
# ============================================================================


@dataclass
class TicketDetail:
    """Detailed ticket information for clustering and synthesis."""

    key: str
    summary: str
    status: str
    priority: str
    epic_key: Optional[str] = None
    epic_name: Optional[str] = None
    story_points: Optional[float] = None
    labels: List[str] = field(default_factory=list)
    description: str = ""
    issue_type: str = "Task"


@dataclass
class PriorityCluster:
    """A cluster of tickets representing a priority area."""

    name: str  # e.g., "Sprint Focus", "Secondary"
    theme: str  # e.g., "Launch Campaign", "Performance Optimization"
    tickets: List[TicketDetail] = field(default_factory=list)
    total_points: float = 0.0
    synthesized_summary: str = ""


# ============================================================================
# CSV Schema
# ============================================================================

CSV_HEADERS = [
    "Division",
    "Department",
    "Team",
    "KPI Movement",
    "Delivered",
    "Delivered External",
    "Key Learnings",
    "Learnings External",
    "Planned",
    "Planned External",
    "GitHub Activity",
    "Active Experiments",
    "Demo",
    "Delivered Tickets",
    "Planned Tickets",
]


# ============================================================================
# Jira Integration (connector_bridge auth)
# ============================================================================


class SprintReportGenerator:
    """Generates sprint reports from Jira data with clustering and synthesis."""

    def __init__(self):
        self.paths = get_paths()
        self.config = get_config()
        self._jira_client = None

    # --- Path helpers ---

    def _get_report_output_dir(self) -> Path:
        """Get the sprint report output directory from config."""
        org_id = self.config.get("organization.id", "organization")
        user_dir = self.paths.user

        # WCR path
        wcr_path = user_dir / "products" / org_id / "reporting" / "sprint-reports"
        if wcr_path.parent.exists() or (user_dir / "products" / org_id).exists():
            wcr_path.mkdir(parents=True, exist_ok=True)
            return wcr_path

        # Fallback
        legacy_path = user_dir / "planning" / "Reporting" / "Sprint_Reports"
        legacy_path.mkdir(parents=True, exist_ok=True)
        return legacy_path

    def _get_team_registry_path(self) -> Path:
        """Get team registry path."""
        return self.paths.root / "team_registry.yaml"

    def _get_brain_github_dir(self) -> Path:
        """Get Brain GitHub directory."""
        return self.paths.user / "brain" / "GitHub"

    def _get_brain_experiments_dir(self) -> Path:
        """Get Brain experiments directory."""
        return self.paths.user / "brain" / "Experiments"

    # --- Jira client ---

    def _get_jira_client(self):
        """Get Jira client using connector bridge three-tier auth."""
        if self._jira_client is not None:
            return self._jira_client

        auth = get_auth("jira")
        if auth.source == "none":
            logger.warning("No Jira auth available: %s", auth.help_message)
            return None

        if auth.source == "env" and auth.token:
            try:
                from atlassian import Jira

                jira_url = self.config.get("integrations.jira.url", "")
                jira_user = self.config.get("integrations.jira.username", "")
                if not jira_url or not jira_user:
                    logger.warning("Jira URL or username not configured")
                    return None

                self._jira_client = Jira(
                    url=jira_url,
                    username=jira_user,
                    password=auth.token,
                    cloud=True,
                )
                return self._jira_client
            except Exception as e:
                logger.warning("Could not create Jira client: %s", e)
                return None

        # Connector mode — Jira data fetched via MCP in Claude session
        return None

    # --- Squad registry ---

    def load_team_registry(
        self, filter_department: Optional[str] = None
    ) -> List[Dict]:
        """Load teams from registry, optionally filtering by department.

        Args:
            filter_department: Department name to filter by. If None, uses config default.
        """
        registry_path = self._get_team_registry_path()
        if not registry_path.exists():
            logger.error("Team registry not found at %s", registry_path)
            return []

        if not YAML_AVAILABLE:
            logger.error("PyYAML required for team registry")
            return []

        with open(registry_path, "r") as f:
            data = yaml.safe_load(f)

        teams = data.get("teams", data.get("squads", []))

        if filter_department is None:
            filter_department = self.config.get("reporting.default_department", None)

        if filter_department:
            teams = [t for t in teams if t.get("department", t.get("tribe")) == filter_department]

        return teams

    # --- Detailed ticket fetching ---

    def fetch_detailed_tickets(
        self, project: str, jql_suffix: str, limit: int = 30
    ) -> List[TicketDetail]:
        """Fetch tickets with full details including epic links."""
        jira = self._get_jira_client()
        if not jira:
            return []

        try:
            jql = f'project = "{project}" {jql_suffix}'
            issues = jira.jql(
                jql,
                limit=limit,
                fields="summary,status,priority,labels,description,issuetype,"
                "customfield_10014,parent,customfield_10016",
            )

            tickets = []
            epic_cache = {}

            for issue in issues.get("issues", []):
                fields = issue["fields"]

                # Extract epic info (classic + next-gen projects)
                epic_key = None
                epic_name = None

                epic_link = fields.get("customfield_10014")
                if epic_link:
                    epic_key = epic_link
                    if epic_key not in epic_cache:
                        try:
                            epic_issue = jira.issue(epic_link, fields="summary")
                            epic_cache[epic_key] = epic_issue["fields"]["summary"]
                        except Exception:
                            epic_cache[epic_key] = epic_link
                    epic_name = epic_cache[epic_key]

                parent = fields.get("parent")
                if parent and not epic_key:
                    epic_key = parent.get("key")
                    epic_name = parent.get("fields", {}).get("summary", epic_key)

                ticket = TicketDetail(
                    key=issue["key"],
                    summary=fields.get("summary", ""),
                    status=fields.get("status", {}).get("name", "Unknown"),
                    priority=(
                        fields.get("priority", {}).get("name", "Medium")
                        if fields.get("priority")
                        else "Medium"
                    ),
                    epic_key=epic_key,
                    epic_name=epic_name,
                    story_points=fields.get("customfield_10016") or 0,
                    labels=fields.get("labels", []),
                    description=(fields.get("description") or "")[:500],
                    issue_type=fields.get("issuetype", {}).get("name", "Task"),
                )
                tickets.append(ticket)

            return tickets

        except Exception as e:
            logger.error("Error fetching detailed tickets: %s", e)
            return []

    # --- Clustering ---

    @staticmethod
    def cluster_tickets(
        tickets: List[TicketDetail], max_clusters: int = 2
    ) -> List[PriorityCluster]:
        """Cluster tickets into priority groups based on epic and effort."""
        if not tickets:
            return []

        # Group by epic
        epic_groups: Dict[str, List[TicketDetail]] = {}
        no_epic_tickets = []

        for ticket in tickets:
            if ticket.epic_key:
                epic_groups.setdefault(ticket.epic_key, []).append(ticket)
            else:
                no_epic_tickets.append(ticket)

        # Score groups
        group_scores = []
        for epic_key, group_tickets in epic_groups.items():
            total_points = sum(t.story_points or 1 for t in group_tickets)
            epic_name = group_tickets[0].epic_name or "Unnamed Epic"
            group_scores.append(
                {
                    "epic_key": epic_key,
                    "epic_name": epic_name,
                    "tickets": group_tickets,
                    "total_points": total_points,
                    "count": len(group_tickets),
                    "score": total_points + (len(group_tickets) * 0.5),
                }
            )

        group_scores.sort(key=lambda x: x["score"], reverse=True)

        # Build clusters
        clusters = []
        priority_names = ["Sprint Focus", "Secondary Priority"]

        for i, group in enumerate(group_scores[:max_clusters]):
            cluster = PriorityCluster(
                name=(
                    priority_names[i]
                    if i < len(priority_names)
                    else f"Priority {i + 1}"
                ),
                theme=group["epic_name"],
                tickets=group["tickets"],
                total_points=group["total_points"],
            )
            clusters.append(cluster)

        # Handle no-epic tickets
        if no_epic_tickets and len(clusters) < max_clusters:
            bug_tickets = [
                t for t in no_epic_tickets if t.issue_type.lower() == "bug"
            ]
            other_tickets = [
                t for t in no_epic_tickets if t.issue_type.lower() != "bug"
            ]

            if bug_tickets and len(bug_tickets) >= 2:
                cluster_name = (
                    priority_names[min(len(clusters), 2)]
                    if len(clusters) < 3
                    else "Bug Fixes"
                )
                clusters.append(
                    PriorityCluster(
                        name=cluster_name,
                        theme="Bug Fixes & Maintenance",
                        tickets=bug_tickets,
                        total_points=sum(
                            t.story_points or 0.5 for t in bug_tickets
                        ),
                    )
                )

            if other_tickets and len(clusters) < max_clusters:
                cluster_name = (
                    priority_names[min(len(clusters), 2)]
                    if len(clusters) < 3
                    else "Other Work"
                )
                clusters.append(
                    PriorityCluster(
                        name=cluster_name,
                        theme="Other Work",
                        tickets=other_tickets,
                        total_points=sum(
                            t.story_points or 0.5 for t in other_tickets
                        ),
                    )
                )
        elif no_epic_tickets:
            if clusters:
                clusters[-1].tickets.extend(no_epic_tickets)
            else:
                clusters.append(
                    PriorityCluster(
                        name="Sprint Work",
                        theme="Various Tasks",
                        tickets=no_epic_tickets,
                        total_points=sum(
                            t.story_points or 0.5 for t in no_epic_tickets
                        ),
                    )
                )

        return clusters

    # --- Synthesis ---
    # LLM synthesis happens in the Claude session context when the user runs
    # /report. These methods provide structured summaries for programmatic use.

    @staticmethod
    def synthesize_cluster_summary(
        cluster: PriorityCluster,
        mode: str = "delivered",
        squad_name: str = "",
    ) -> str:
        """Synthesize a cluster into a structured summary.

        When run inside a Claude session via /report, Claude provides
        richer narrative synthesis directly. This method produces a clean
        structured summary for programmatic/background use.
        """
        if not cluster.tickets:
            return ""

        ticket_summaries = [t.summary for t in cluster.tickets]
        action = "shipped to production" if mode == "delivered" else "targeted for next sprint"

        if len(cluster.tickets) == 1:
            return f"{cluster.tickets[0].summary} — {action}."

        return (
            f"{cluster.theme}: {len(cluster.tickets)} items {action}, "
            f"including {ticket_summaries[0]}"
            + (f" and {ticket_summaries[1]}" if len(ticket_summaries) > 1 else "")
            + (f" (+{len(ticket_summaries) - 2} more)" if len(ticket_summaries) > 2 else "")
            + "."
        )

    @staticmethod
    def format_clustered_work(
        clusters: List[PriorityCluster],
        mode: str = "delivered",
        squad_name: str = "",
    ) -> str:
        """Format clustered work into priority-labelled report sections."""
        if not clusters:
            return "No items found."

        output_lines = []
        for cluster in clusters:
            if not cluster.synthesized_summary:
                cluster.synthesized_summary = (
                    SprintReportGenerator.synthesize_cluster_summary(
                        cluster, mode, squad_name
                    )
                )
            output_lines.append(
                f"**{cluster.name}:** {cluster.synthesized_summary}"
            )

        return "\n\n".join(output_lines)

    # --- External format ---

    @staticmethod
    def synthesize_external_format(
        clusters: List[PriorityCluster],
        mode: str = "delivered",
        squad_name: str = "",
    ) -> str:
        """Generate concise external numbered format for leadership scanning."""
        if not clusters:
            return ""

        lines = []
        for i, cluster in enumerate(clusters, 1):
            if not cluster.tickets:
                continue
            action = "shipped" if mode == "delivered" else "planned"
            sub_items = [f"   - {t.summary}" for t in cluster.tickets[:4]]
            lines.append(
                f"{i}. {cluster.theme}: "
                f"{len(cluster.tickets)} items {action}"
            )
            lines.extend(sub_items)

        return "\n".join(lines)

    # --- External learnings ---

    @staticmethod
    def format_external_learnings(learnings_text: str) -> str:
        """Convert verbose internal learnings to concise external bullets.

        Extracts Learning + Action pairs and combines into single-line format.
        """
        if not learnings_text or learnings_text.strip() == "":
            return ""

        learning_pattern = r"\*\*Learning:\*\*\s*(.+?)(?=\*\*|$)"
        action_pattern = r"\*\*Action:\*\*\s*(.+?)(?=\*\*|$)"

        learnings = re.findall(learning_pattern, learnings_text, re.DOTALL)
        actions = re.findall(action_pattern, learnings_text, re.DOTALL)

        lines = []
        for i, (learning, action) in enumerate(zip(learnings, actions)):
            if i >= 5:
                break
            learning = learning.strip().rstrip(".")
            action = action.strip().rstrip(".")
            lines.append(
                f"- Identified {learning.lower()}, "
                f"resulting in {action.lower()}"
            )

        return "\n".join(lines) if lines else ""

    # --- GitHub / Experiments ---

    def parse_github_pr_activity(self) -> Dict[str, List[str]]:
        """Parse PR_Activity.md to extract PR info per squad."""
        file_path = self._get_brain_github_dir() / "PR_Activity.md"
        if not file_path.exists():
            return {}

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        squads_prs: Dict[str, List[str]] = {}
        current_squad = None
        current_prs: List[str] = []

        for line in content.split("\n"):
            squad_match = re.match(r"^## (.+?) \(\d+ open\)", line)
            if squad_match:
                if current_squad:
                    squads_prs[current_squad] = current_prs
                current_squad = squad_match.group(1)
                current_prs = []
                continue

            if current_squad and line.startswith("- [#"):
                current_prs.append(line[2:].strip())

        if current_squad:
            squads_prs[current_squad] = current_prs

        return squads_prs

    def get_active_experiments(
        self, squad_name: str, ticket_keys: List[str]
    ) -> str:
        """Fetch active experiments linked to squad or tickets."""
        experiments_dir = self._get_brain_experiments_dir()
        if not experiments_dir.exists():
            return "No experiments found (Directory missing)."

        active_experiments = []

        for file_path in glob.glob(str(experiments_dir / "*.md")):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                if "status: active" not in content.lower():
                    continue

                is_linked = False
                if (
                    f"[[Squad_{squad_name}]]" in content
                    or f"[[{squad_name}]]" in content
                ):
                    is_linked = True

                if not is_linked and ticket_keys:
                    for key in ticket_keys:
                        if key in content:
                            is_linked = True
                            break

                if is_linked:
                    match = re.search(r"^# (.+)$", content, re.MULTILINE)
                    name = match.group(1) if match else Path(file_path).stem
                    id_match = re.search(r"id: (.+)", content)
                    exp_id = (
                        id_match.group(1).strip() if id_match else "unknown"
                    )
                    active_experiments.append(f"- **{name}** (`{exp_id}`)")

            except Exception:
                continue

        if not active_experiments:
            return "No active experiments linked."

        return "\n".join(active_experiments)

    # --- Squad data fetching ---

    def get_squad_data(
        self,
        squad: Dict,
        sprint_start: Optional[str] = None,
        sprint_end: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch delivered and planned items with detailed clustering."""
        project = squad.get("jira_project")
        if not project:
            return {
                "delivered_clusters": [],
                "planned_clusters": [],
                "raw_delivered": [],
                "raw_planned": [],
                "delivered_tickets": [],
                "planned_tickets": [],
            }

        squad_name = squad["name"]
        logger.info("Fetching Jira data for %s (%s)...", squad_name, project)

        # Delivered: resolved in date range or last 14 days
        if sprint_start and sprint_end:
            delivered_jql = (
                f'AND statusCategory = Done AND resolved >= "{sprint_start}" '
                f'AND resolved <= "{sprint_end}" ORDER BY resolved DESC'
            )
        elif sprint_start:
            delivered_jql = (
                f'AND statusCategory = Done AND resolved >= "{sprint_start}" '
                f"ORDER BY resolved DESC"
            )
        else:
            delivered_jql = (
                "AND statusCategory = Done AND resolved >= -14d "
                "ORDER BY resolved DESC"
            )

        delivered_tickets = self.fetch_detailed_tickets(
            project, delivered_jql, limit=30
        )

        # Planned: active sprint or top backlog
        planned_jql = "AND sprint in openSprints() ORDER BY rank ASC"
        planned_tickets = self.fetch_detailed_tickets(
            project, planned_jql, limit=30
        )

        if not planned_tickets:
            planned_jql = "AND statusCategory != Done ORDER BY rank ASC"
            planned_tickets = self.fetch_detailed_tickets(
                project, planned_jql, limit=15
            )

        # Cluster
        delivered_clusters = self.cluster_tickets(delivered_tickets, max_clusters=2)
        planned_clusters = self.cluster_tickets(planned_tickets, max_clusters=2)

        # Raw format for learnings
        raw_delivered = [
            f"[{t.key}] {t.summary} (Status: {t.status}, Type: {t.issue_type})"
            for t in delivered_tickets
        ]
        raw_planned = [
            f"[{t.key}] {t.summary} (Status: {t.status}, Type: {t.issue_type})"
            for t in planned_tickets
        ]

        return {
            "delivered_clusters": delivered_clusters,
            "planned_clusters": planned_clusters,
            "raw_delivered": raw_delivered,
            "raw_planned": raw_planned,
            "delivered_tickets": delivered_tickets,
            "planned_tickets": planned_tickets,
        }

    # --- Report generation ---

    def generate_report(
        self,
        squads: List[Dict],
        output_path: Path,
        sprint_start: Optional[str] = None,
        sprint_end: Optional[str] = None,
    ) -> Path:
        """Main generation loop — produces CSV report."""
        github_data = self.parse_github_pr_activity()
        output_dir = self._get_report_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        # Read org-level labels from config
        division = self.config.get(
            "reporting.division", "Division"
        )

        if sprint_start:
            if sprint_end:
                logger.info(
                    "Generating report for sprint: %s to %s",
                    sprint_start,
                    sprint_end,
                )
            else:
                logger.info(
                    "Generating report for sprint starting: %s", sprint_start
                )

        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(CSV_HEADERS)

            for squad in squads:
                squad_name = squad["name"]
                logger.info("Processing: %s", squad_name)

                data = self.get_squad_data(
                    squad, sprint_start=sprint_start, sprint_end=sprint_end
                )

                delivered_tickets = data.get("delivered_tickets", [])
                planned_tickets = data.get("planned_tickets", [])
                all_ticket_keys = [t.key for t in delivered_tickets] + [
                    t.key for t in planned_tickets
                ]

                delivered_keys_str = (
                    ", ".join([t.key for t in delivered_tickets])
                    if delivered_tickets
                    else "N/A"
                )
                planned_keys_str = (
                    ", ".join([t.key for t in planned_tickets])
                    if planned_tickets
                    else "N/A"
                )

                # Delivered
                delivered_summary = self.format_clustered_work(
                    data["delivered_clusters"],
                    mode="delivered",
                    squad_name=squad_name,
                )
                delivered_external = self.synthesize_external_format(
                    data["delivered_clusters"],
                    mode="delivered",
                    squad_name=squad_name,
                )

                # Learnings placeholder
                learnings_summary = "TBD - Run /report sprint-learnings"
                learnings_external = ""

                # Planned
                planned_summary = self.format_clustered_work(
                    data["planned_clusters"],
                    mode="planned",
                    squad_name=squad_name,
                )
                planned_external = self.synthesize_external_format(
                    data["planned_clusters"],
                    mode="planned",
                    squad_name=squad_name,
                )

                # GitHub
                squad_prs = github_data.get(squad_name, [])
                github_summary = "No GitHub activity."
                if squad_prs:
                    github_summary = (
                        f"{len(squad_prs)} open PRs:\n"
                        + "\n".join(squad_prs[:5])
                    )

                # Experiments
                experiments_summary = self.get_active_experiments(
                    squad_name, all_ticket_keys
                )

                # Write row
                writer.writerow(
                    [
                        division,
                        squad.get("department", squad.get("tribe", "")),
                        squad_name,
                        "N/A (Manual Entry)",
                        delivered_summary,
                        delivered_external,
                        learnings_summary,
                        learnings_external,
                        planned_summary,
                        planned_external,
                        github_summary,
                        experiments_summary,
                        "To be confirmed",
                        delivered_keys_str,
                        planned_keys_str,
                    ]
                )

                logger.info("Done: %s", squad_name)

        logger.info("Report generated: %s", output_path)
        return output_path

    # --- CLI entry point ---

    def run(
        self,
        team_filter: Optional[str] = None,
        output: Optional[str] = None,
        sprint_start: Optional[str] = None,
        sprint_end: Optional[str] = None,
        department: Optional[str] = None,
    ) -> Path:
        """Run the report generator.

        Args:
            team_filter: Optional team name to filter by.
            output: Optional output file path.
            sprint_start: Sprint start date (YYYY-MM-DD).
            sprint_end: Sprint end date (YYYY-MM-DD).
            department: Optional department name override.
        """
        squads = self.load_team_registry(filter_department=department)
        if not squads:
            raise ValueError("No teams found in registry")

        if team_filter:
            squads = [
                s
                for s in squads
                if s["name"].lower() == team_filter.lower()
            ]
            if not squads:
                raise ValueError(f"Team '{team_filter}' not found")

        # Determine output filename
        output_dir = self._get_report_output_dir()
        if sprint_start:
            date_str = sprint_start.replace("-", "")[:8]
            if sprint_end:
                end_str = sprint_end.replace("-", "")[:8]
                output_filename = f"Sprint_Report_{date_str}_to_{end_str}.csv"
            else:
                output_filename = f"Sprint_Report_{date_str}.csv"
        else:
            date_str = datetime.now().strftime("%m-%d-%Y")
            output_filename = f"Sprint_Report_{date_str}.csv"

        output_path = Path(output) if output else output_dir / output_filename

        return self.generate_report(
            squads,
            output_path,
            sprint_start=sprint_start,
            sprint_end=sprint_end,
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Sprint Report Generator v5.0"
    )
    parser.add_argument("--team", type=str, help="Generate for specific team")
    parser.add_argument("--output", type=str, help="Custom output path")
    parser.add_argument("--department", type=str, help="Filter by department")
    parser.add_argument(
        "--sprint-start", type=str, help="Sprint start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--sprint-end", type=str, help="Sprint end date (YYYY-MM-DD)"
    )
    args = parser.parse_args()

    generator = SprintReportGenerator()
    result = generator.run(
        team_filter=args.team,
        output=args.output,
        sprint_start=args.sprint_start,
        sprint_end=args.sprint_end,
        department=args.department,
    )
    print(f"Report generated: {result}")
