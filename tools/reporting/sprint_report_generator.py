#!/usr/bin/env python3
"""
Sprint Report Generator v1.2 - Priority-Focused Version

Generates bi-weekly sprint reports with clustered, prioritized work items.

v1.2 Improvements (based on leadership feedback):
- Clusters tickets into Sprint Focus, Secondary, and Tertiary priorities
- Generates coherent sentences instead of ticket dumps
- Connects work to business value and KPIs
- Shows clear prioritization and focus

Key Features:
- Active JQL fetching with full ticket content and epic links
- Intelligent clustering by epic/theme
- LLM synthesis into outcome-focused sentences
- Support for both Sprint and Kanban boards
- Date range support for historical sprint reports

Usage:
    python3 sprint_report_generator.py
    python3 sprint_report_generator.py --squad "Meal Kit"
    python3 sprint_report_generator.py --output "my_report.csv"
    python3 sprint_report_generator.py --sprint-start 2026-01-05 --sprint-end 2026-01-19
"""

import argparse
import csv
import glob
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add common directory to path for config_loader
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config_loader

# Constants
ROOT_DIR = config_loader.get_root_path()
COMMON_DIR = config_loader.get_common_path()
USER_DIR = ROOT_DIR / "user"
SQUAD_REGISTRY_PATH = ROOT_DIR / "squad_registry.yaml"
JIRA_SCRIPT = COMMON_DIR / "tools" / "integrations" / "jira_mcp" / "server.py"
BRAIN_GITHUB_DIR = USER_DIR / "brain" / "GitHub"
BRAIN_EXPERIMENTS_DIR = USER_DIR / "brain" / "Experiments"


# WCR: Resolve report output directory based on workspace config
def get_report_output_dir() -> Path:
    """Get the sprint report output directory, using WCR paths if available."""
    org_config = config_loader.get_organization_config()
    if org_config:
        org_id = org_config.get("id", "organization")
        wcr_path = USER_DIR / "products" / org_id / "reporting" / "sprint-reports"
        if wcr_path.parent.exists() or (USER_DIR / "products" / org_id).exists():
            wcr_path.mkdir(parents=True, exist_ok=True)
            return wcr_path
    # Fallback to legacy path
    legacy_path = USER_DIR / "planning" / "Reporting" / "Sprint_Reports"
    legacy_path.mkdir(parents=True, exist_ok=True)
    return legacy_path


REPORT_OUTPUT_DIR = get_report_output_dir()

CSV_HEADERS = [
    "Mega-Alliance",
    "Tribe",
    "Squad",
    "KPI Movement",
    "Delivered",
    "Delivered External",  # v1.3: Concise numbered format for external sharing
    "Key Learnings",
    "Learnings External",  # v1.3: "Identified/Learned X, resulting in Y" format
    "Planned",
    "Planned External",  # v1.3: Concise numbered format for external sharing
    "GitHub Activity",
    "Active Experiments",
    "Demo",
    "Delivered Tickets",
    "Planned Tickets",
]

# ============================================================================
# v1.2: Enhanced Data Structures for Clustering
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

    name: str  # e.g., "Sprint Focus", "Secondary", "Tertiary"
    theme: str  # e.g., "OTP Launch", "Performance Optimization"
    tickets: List[TicketDetail] = field(default_factory=list)
    total_points: float = 0.0
    synthesized_summary: str = ""


def get_jira_client():
    """Get direct Jira client for detailed queries."""
    try:
        from atlassian import Jira

        jira_config = config_loader.get_jira_config()
        if not jira_config.get("url"):
            return None
        return Jira(
            url=jira_config["url"],
            username=jira_config["username"],
            password=jira_config["api_token"],
            cloud=True,
        )
    except Exception as e:
        print(f"  Warning: Could not create Jira client: {e}")
        return None


def fetch_detailed_tickets(
    project: str, jql_suffix: str, limit: int = 30
) -> List[TicketDetail]:
    """Fetch tickets with full details including epic links."""
    jira = get_jira_client()
    if not jira:
        return []

    try:
        jql = f'project = "{project}" {jql_suffix}'
        # Request fields we need for clustering
        issues = jira.jql(
            jql,
            limit=limit,
            fields="summary,status,priority,labels,description,issuetype,customfield_10014,parent,customfield_10016",
            # customfield_10014 = Epic Link (classic), parent = Epic (next-gen), customfield_10016 = Story Points
        )

        tickets = []
        epic_cache = {}  # Cache epic names to avoid repeated API calls

        for issue in issues.get("issues", []):
            fields = issue["fields"]

            # Extract epic info (handles both classic and next-gen projects)
            epic_key = None
            epic_name = None

            # Classic projects: Epic Link field
            epic_link = fields.get("customfield_10014")
            if epic_link:
                epic_key = epic_link
                # Fetch epic name (with cache)
                if epic_key not in epic_cache:
                    try:
                        epic_issue = jira.issue(epic_link, fields="summary")
                        epic_cache[epic_key] = epic_issue["fields"]["summary"]
                    except:
                        epic_cache[epic_key] = epic_link
                epic_name = epic_cache[epic_key]

            # Next-gen projects: Parent field
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
        print(f"  Error fetching detailed tickets: {e}")
        return []


def cluster_tickets(
    tickets: List[TicketDetail], max_clusters: int = 2
) -> List[PriorityCluster]:
    """
    Cluster tickets into priority groups based on epic and effort.

    Strategy:
    1. Group by epic (tickets under same epic = same theme)
    2. Rank groups by total story points / ticket count
    3. Top group = Sprint Focus, next = Secondary, etc.
    """
    if not tickets:
        return []

    # Group by epic
    epic_groups: Dict[str, List[TicketDetail]] = {}
    no_epic_tickets = []

    for ticket in tickets:
        if ticket.epic_key:
            key = ticket.epic_key
            if key not in epic_groups:
                epic_groups[key] = []
            epic_groups[key].append(ticket)
        else:
            no_epic_tickets.append(ticket)

    # Calculate group scores (story points + ticket count as tiebreaker)
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
                "score": total_points
                + (len(group_tickets) * 0.5),  # Points + count bonus
            }
        )

    # Sort by score descending
    group_scores.sort(key=lambda x: x["score"], reverse=True)

    # Build clusters
    clusters = []
    priority_names = ["Sprint Focus", "Secondary Priority"]

    for i, group in enumerate(group_scores[:max_clusters]):
        cluster = PriorityCluster(
            name=priority_names[i] if i < len(priority_names) else f"Priority {i+1}",
            theme=group["epic_name"],
            tickets=group["tickets"],
            total_points=group["total_points"],
        )
        clusters.append(cluster)

    # Handle tickets without epics - group into "Other Work" if significant
    if no_epic_tickets and len(clusters) < max_clusters:
        # Sub-cluster no-epic tickets by type
        bug_tickets = [t for t in no_epic_tickets if t.issue_type.lower() == "bug"]
        other_tickets = [t for t in no_epic_tickets if t.issue_type.lower() != "bug"]

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
                    total_points=sum(t.story_points or 0.5 for t in bug_tickets),
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
                    total_points=sum(t.story_points or 0.5 for t in other_tickets),
                )
            )
    elif no_epic_tickets:
        # Few tickets without epic - add to last cluster or create one
        if clusters:
            clusters[-1].tickets.extend(no_epic_tickets)
        else:
            clusters.append(
                PriorityCluster(
                    name="Sprint Work",
                    theme="Various Tasks",
                    tickets=no_epic_tickets,
                    total_points=sum(t.story_points or 0.5 for t in no_epic_tickets),
                )
            )

    return clusters


def synthesize_cluster_summary(
    cluster: PriorityCluster, mode: str = "delivered", squad_name: str = ""
) -> str:
    """
    Synthesize a cluster of tickets into coherent sentences.

    Args:
        cluster: The priority cluster to synthesize
        mode: 'delivered' or 'planned'
        squad_name: Squad name for context

    Returns:
        1-3 sentences describing the work
    """
    if not cluster.tickets:
        return ""

    try:
        import google.generativeai as genai

        gemini_config = config_loader.get_gemini_config()
        api_key = gemini_config.get("api_key")

        if not api_key:
            return _simple_synthesis(cluster, mode)

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(gemini_config.get("model", "gemini-1.5-flash"))

        # Build ticket context
        ticket_lines = []
        for t in cluster.tickets:
            ticket_lines.append(
                f"- [{t.key}] {t.summary} (Type: {t.issue_type}, Status: {t.status})"
            )
            if t.description:
                ticket_lines.append(f"  Description: {t.description[:200]}...")

        sentence_count = (
            "1-3 sentences" if cluster.name == "Sprint Focus" else "1-2 sentences"
        )

        prompt = f"""You are writing a sprint report for leadership at {squad_name}.

**Theme:** {cluster.theme}
**Priority Level:** {cluster.name}
**Mode:** {'Work Completed' if mode == 'delivered' else 'Planned for Next Sprint'}

**Tickets:**
{chr(10).join(ticket_lines)}

**Task:** Write {sentence_count} that:
1. Describe WHAT was {'built and shipped to production' if mode == 'delivered' else 'will be built'}
2. Explain the BUSINESS VALUE or outcome (connect to user/business impact)
3. {'Emphasize what shipped to production' if mode == 'delivered' else 'Set clear expectations for delivery'}

**Rules:**
- NO bullet points - write flowing, professional sentences
- DO NOT include ticket keys or numbers - they will be added separately
- Focus on OUTCOMES and VALUE, not technical implementation details
- Be concise - leadership reads quickly
- Avoid jargon - use business language

**Output (just the sentences, nothing else):**"""

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        print(f"    Synthesis error: {e}")
        return _simple_synthesis(cluster, mode)


def _simple_synthesis(cluster: PriorityCluster, mode: str) -> str:
    """Fallback synthesis without LLM."""
    if not cluster.tickets:
        return ""

    if mode == "delivered":
        return f"Completed work on {cluster.theme}: {len(cluster.tickets)} items shipped to production."
    else:
        return f"Planned: Continue {cluster.theme} with {len(cluster.tickets)} items targeted for completion."


def format_clustered_work(
    clusters: List[PriorityCluster], mode: str = "delivered", squad_name: str = ""
) -> str:
    """
    Format clustered work into the final report format.

    Output format:
    **Sprint Focus:** [sentences]
    **Secondary Priority:** [sentences]
    **Tertiary Priority:** [sentences] (optional)
    """
    if not clusters:
        return "No items found."

    output_lines = []

    for cluster in clusters:
        # Synthesize if not already done
        if not cluster.synthesized_summary:
            print(f"    Synthesizing {cluster.name}: {cluster.theme}...")
            cluster.synthesized_summary = synthesize_cluster_summary(
                cluster, mode, squad_name
            )

        # Format with priority header
        output_lines.append(f"**{cluster.name}:** {cluster.synthesized_summary}")

    return "\n\n".join(output_lines)


# ============================================================================
# v1.3: External Format Synthesis Functions
# ============================================================================


def synthesize_external_format(
    clusters: List[PriorityCluster], mode: str = "delivered", squad_name: str = ""
) -> str:
    """
    Generate concise external format for work done/planned.

    Output format:
    1. [[Sprint Focus]]: [[Milestone]], focusing on [[metric]] and includes:
       - Sub-feature 1
       - Sub-feature 2

    2. [[Secondary]]: [[Milestone]], focusing on [[metric]] and includes:
       - Sub-feature 1

    Args:
        clusters: List of priority clusters (sorted by priority)
        mode: 'delivered' or 'planned'
        squad_name: Squad name for context

    Returns:
        Numbered external format string
    """
    if not clusters:
        return ""

    try:
        import google.generativeai as genai

        gemini_config = config_loader.get_gemini_config()
        api_key = gemini_config.get("api_key")

        if not api_key:
            return _simple_external_synthesis(clusters, mode)

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(gemini_config.get("model", "gemini-1.5-flash"))

        # Build context from all clusters
        cluster_context = []
        for i, cluster in enumerate(clusters, 1):
            ticket_lines = []
            for t in cluster.tickets:
                ticket_lines.append(f"  - [{t.key}] {t.summary}")
            cluster_context.append(f"""Priority {i} - {cluster.name}:
Theme: {cluster.theme}
Tickets:
{chr(10).join(ticket_lines)}""")

        prompt = f"""You are writing an external-facing sprint report for leadership at {squad_name}.

**Mode:** {'Work Completed This Sprint' if mode == 'delivered' else 'Planned for Next Sprint'}

**Clusters:**
{chr(10).join(cluster_context)}

**Task:** Generate a CONCISE numbered summary using this EXACT format:

1. [[Theme Name]]: [[One-line milestone description]], focusing on [[business metric/outcome]] and includes:
   - [[Sub-feature/experience 1]]
   - [[Sub-feature/experience 2]]

2. [[Theme Name]]: [[One-line milestone description]], focusing on [[business metric/outcome]] and includes:
   - [[Sub-feature 1]]

**Rules:**
- Number each priority (1., 2., etc.)
- One main sentence per priority describing the milestone
- Include "focusing on [[metric/outcome]]"
- 2-4 bullet sub-features per priority (derived from tickets)
- NO ticket numbers
- NO verbose explanations
- Be CONCISE - this is for quick scanning
- Only include priorities that have meaningful work

**Output (just the numbered format, nothing else):**"""

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        print(f"    External synthesis error: {e}")
        return _simple_external_synthesis(clusters, mode)


def _simple_external_synthesis(clusters: List[PriorityCluster], mode: str) -> str:
    """Fallback external synthesis without LLM."""
    if not clusters:
        return ""

    lines = []
    for i, cluster in enumerate(clusters, 1):
        if cluster.tickets:
            action = "shipped" if mode == "delivered" else "planned"
            lines.append(f"{i}. {cluster.theme}: {len(cluster.tickets)} items {action}")

    return "\n".join(lines)


def format_external_learnings(learnings_text: str) -> str:
    """
    Convert verbose internal learnings to external bullet format.

    Input format (internal):
    **Learning:** OTP security needed proactive hardening
    **Evidence:** MK-3442 investigation revealed...
    **Action:** Add auth guard review to new module checklist.

    Output format (external):
    - Identified need for proactive security hardening, resulting in auth guard review added to module checklist

    Args:
        learnings_text: The verbose internal learnings text

    Returns:
        Concise external learnings (3-5 bullets max)
    """
    if not learnings_text or learnings_text.strip() == "":
        return ""

    try:
        import google.generativeai as genai

        gemini_config = config_loader.get_gemini_config()
        api_key = gemini_config.get("api_key")

        if not api_key:
            return _simple_external_learnings(learnings_text)

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(gemini_config.get("model", "gemini-1.5-flash"))

        prompt = f"""Convert these internal sprint learnings to external format.

**Internal Learnings:**
{learnings_text}

**Task:** Create 3-5 concise bullet points using this EXACT format:
- Identified [[issue/opportunity]], resulting in [[action taken by team]]
- Learned [[insight]], resulting in [[process/behavior change]]

**Rules:**
- REMOVE all ticket numbers and evidence details
- COMBINE Learning + Action into single line
- Start with "Identified" or "Learned"
- End with "resulting in [[specific action]]"
- Maximum 5 bullets
- Be CONCISE - external audience doesn't need details

**Output (just the bullets, nothing else):**"""

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        print(f"    External learnings error: {e}")
        return _simple_external_learnings(learnings_text)


def _simple_external_learnings(learnings_text: str) -> str:
    """Fallback external learnings without LLM."""
    import re

    # Extract Learning and Action pairs
    learning_pattern = r"\*\*Learning:\*\*\s*(.+?)(?=\*\*|$)"
    action_pattern = r"\*\*Action:\*\*\s*(.+?)(?=\*\*|$)"

    learnings = re.findall(learning_pattern, learnings_text, re.DOTALL)
    actions = re.findall(action_pattern, learnings_text, re.DOTALL)

    lines = []
    for i, (learning, action) in enumerate(zip(learnings, actions)):
        if i >= 5:  # Max 5 bullets
            break
        learning = learning.strip().rstrip(".")
        action = action.strip().rstrip(".")
        lines.append(f"- Identified {learning.lower()}, resulting in {action.lower()}")

    return "\n".join(lines) if lines else ""


# ============================================================================
# Original Functions (Updated for v1.2)
# ============================================================================


def load_squad_registry(filter_tribe: Optional[str] = "Growth Division") -> List[Dict]:
    """Load squads from registry, optionally filtering by tribe."""
    if not SQUAD_REGISTRY_PATH.exists():
        print(f"Error: Squad registry not found at {SQUAD_REGISTRY_PATH}")
        return []

    with open(SQUAD_REGISTRY_PATH, "r") as f:
        data = yaml.safe_load(f)

    squads = data.get("squads", [])
    if filter_tribe:
        squads = [s for s in squads if s.get("tribe") == filter_tribe]

    return squads


def fetch_jira_issues(jql: str, limit: int = 50) -> List[str]:
    """Execute JQL using the Jira MCP server script (legacy, for learnings)."""
    if not JIRA_SCRIPT.exists():
        print(f"Error: Jira script not found at {JIRA_SCRIPT}")
        return []

    cmd = [sys.executable, str(JIRA_SCRIPT), "--cli", "search_issues", jql]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        issues = [line for line in output.split("\n") if line.strip()]
        return issues[:limit]

    except subprocess.CalledProcessError as e:
        print(f"Jira fetch failed: {e}")
        return []


def get_squad_data_v12(
    squad: Dict, sprint_start: Optional[str] = None, sprint_end: Optional[str] = None
) -> Dict[str, Any]:
    """
    v1.2: Fetch Delivered and Planned items with detailed clustering.

    Args:
        squad: Squad configuration dict
        sprint_start: Optional start date for historical reports (YYYY-MM-DD format)
        sprint_end: Optional end date for historical reports (YYYY-MM-DD format)

    Returns:
        {
            'delivered_clusters': List[PriorityCluster],
            'planned_clusters': List[PriorityCluster],
            'raw_delivered': List[str],  # For learnings generation
            'raw_planned': List[str]
        }
    """
    project = squad.get("jira_project")
    if not project:
        return {
            "delivered_clusters": [],
            "planned_clusters": [],
            "raw_delivered": [],
            "raw_planned": [],
        }

    squad_name = squad["name"]
    print(f"  Fetching Jira data for {squad_name} ({project})...")

    # 1. Delivered: Resolved in date range or last 14 days
    print(f"    Fetching delivered items...")
    if sprint_start and sprint_end:
        # Historical report: use specific date range
        delivered_jql = f'AND statusCategory = Done AND resolved >= "{sprint_start}" AND resolved <= "{sprint_end}" ORDER BY resolved DESC'
    elif sprint_start:
        # Just start date: from start to now (or calculate 14 days after)
        delivered_jql = f'AND statusCategory = Done AND resolved >= "{sprint_start}" ORDER BY resolved DESC'
    else:
        # Default: last 14 days
        delivered_jql = (
            "AND statusCategory = Done AND resolved >= -14d ORDER BY resolved DESC"
        )
    delivered_tickets = fetch_detailed_tickets(project, delivered_jql, limit=30)

    # 2. Planned: Active Sprint OR Top Backlog
    print(f"    Fetching planned items...")
    planned_jql = "AND sprint in openSprints() ORDER BY rank ASC"
    planned_tickets = fetch_detailed_tickets(project, planned_jql, limit=30)

    # Fallback to Backlog if no active sprint items
    if not planned_tickets:
        print("    No active sprint found, falling back to backlog...")
        planned_jql = "AND statusCategory != Done ORDER BY rank ASC"
        planned_tickets = fetch_detailed_tickets(project, planned_jql, limit=15)

    # 3. Cluster tickets (Sprint Focus + Secondary only, no Tertiary)
    print(f"    Clustering {len(delivered_tickets)} delivered tickets...")
    delivered_clusters = cluster_tickets(delivered_tickets, max_clusters=2)

    print(f"    Clustering {len(planned_tickets)} planned tickets...")
    planned_clusters = cluster_tickets(planned_tickets, max_clusters=2)

    # 4. Also fetch raw format for learnings (uses existing ticket data)
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


def parse_github_pr_activity(file_path: Path) -> Dict[str, List[str]]:
    """Parse PR_Activity.md to extract PR info per squad."""
    if not file_path.exists():
        return {}

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    squads_prs = {}
    current_squad = None
    current_prs = []

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


def get_active_experiments(squad_name: str, ticket_keys: List[str]) -> str:
    """Fetch active experiments linked to squad or tickets."""
    if not BRAIN_EXPERIMENTS_DIR.exists():
        return "No experiments found (Directory missing)."

    active_experiments = []
    squad_slug = squad_name.lower().replace(" ", "_")

    for file_path in glob.glob(str(BRAIN_EXPERIMENTS_DIR / "*.md")):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if "status: active" not in content.lower():
                continue

            is_linked = False
            if f"[[Squad_{squad_name}]]" in content or f"[[{squad_name}]]" in content:
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
                exp_id = id_match.group(1).strip() if id_match else "unknown"
                active_experiments.append(f"- **{name}** (`{exp_id}`)")

        except Exception:
            continue

    if not active_experiments:
        return "No active experiments linked."

    return "\n".join(active_experiments)


def extract_keys_from_items(items: List[str]) -> List[str]:
    """Extract Jira keys [KEY] from item strings."""
    keys = []
    for item in items:
        match = re.search(r"\[([A-Z]+-\d+)\]", item)
        if match:
            keys.append(match.group(1))
    return keys


def generate_report(
    squads: List[Dict],
    output_path: Path,
    sprint_start: Optional[str] = None,
    sprint_end: Optional[str] = None,
):
    """Main generation loop - v1.2 with clustering.

    Args:
        squads: List of squad configurations
        output_path: Path to write the CSV report
        sprint_start: Optional start date for historical reports (YYYY-MM-DD)
        sprint_end: Optional end date for historical reports (YYYY-MM-DD)
    """

    # Load GitHub data
    pr_activity_file = BRAIN_GITHUB_DIR / "PR_Activity.md"
    github_data = parse_github_pr_activity(pr_activity_file)

    REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Log date range if specified
    if sprint_start:
        if sprint_end:
            print(f"Generating report for sprint: {sprint_start} to {sprint_end}")
        else:
            print(f"Generating report for sprint starting: {sprint_start}")

    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(CSV_HEADERS)

        for squad in squads:
            squad_name = squad["name"]
            print(f"Processing: {squad_name}")

            # 1. Fetch Data with v1.2 clustering
            data = get_squad_data_v12(
                squad, sprint_start=sprint_start, sprint_end=sprint_end
            )

            # Extract ticket keys for matching and separate columns
            delivered_tickets = data.get("delivered_tickets", [])
            planned_tickets = data.get("planned_tickets", [])
            all_ticket_keys = [t.key for t in delivered_tickets] + [
                t.key for t in planned_tickets
            ]

            # Format ticket keys for separate columns
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

            # 2. Format Delivered with clustering and synthesis
            print(f"  Generating Delivered summary...")
            delivered_summary = format_clustered_work(
                data["delivered_clusters"], mode="delivered", squad_name=squad_name
            )

            # 2b. v1.3: Generate external format for Delivered
            print(f"  Generating Delivered External summary...")
            delivered_external = synthesize_external_format(
                data["delivered_clusters"], mode="delivered", squad_name=squad_name
            )

            # 3. Key Learnings - placeholder for Claude analysis (run /sprint-learnings after)
            # We provide the raw ticket data for learnings generation
            learnings_summary = "TBD - Run /sprint-learnings"
            learnings_external = ""  # v1.3: Populated by /sprint-learnings

            # 4. Format Planned with clustering and synthesis
            print(f"  Generating Planned summary...")
            planned_summary = format_clustered_work(
                data["planned_clusters"], mode="planned", squad_name=squad_name
            )

            # 4b. v1.3: Generate external format for Planned
            print(f"  Generating Planned External summary...")
            planned_external = synthesize_external_format(
                data["planned_clusters"], mode="planned", squad_name=squad_name
            )

            # 5. GitHub Data
            squad_prs = github_data.get(squad_name, [])
            github_summary = "No GitHub activity."
            if squad_prs:
                github_summary = f"{len(squad_prs)} open PRs:\n" + "\n".join(
                    squad_prs[:5]
                )

            # 6. Active Experiments
            experiments_summary = get_active_experiments(squad_name, all_ticket_keys)

            # 7. Write Row (v1.3: includes external columns)
            writer.writerow(
                [
                    "Enterprise Alliance",
                    squad.get("tribe", "Growth Division"),
                    squad_name,
                    "N/A (Manual Entry)",
                    delivered_summary,
                    delivered_external,  # v1.3: External format
                    learnings_summary,
                    learnings_external,  # v1.3: External format
                    planned_summary,
                    planned_external,  # v1.3: External format
                    github_summary,
                    experiments_summary,
                    "To be confirmed",
                    delivered_keys_str,
                    planned_keys_str,
                ]
            )

            print(f"  Done: {squad_name}")

    print(f"\nReport generated: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate Sprint Report v1.2")
    parser.add_argument("--squad", type=str, help="Generate for specific squad only")
    parser.add_argument("--output", type=str, help="Custom output path")
    parser.add_argument(
        "--sprint-start",
        type=str,
        help="Sprint start date (YYYY-MM-DD) for historical reports",
    )
    parser.add_argument(
        "--sprint-end",
        type=str,
        help="Sprint end date (YYYY-MM-DD) for historical reports",
    )
    args = parser.parse_args()

    squads = load_squad_registry()
    if not squads:
        return 1

    if args.squad:
        squads = [s for s in squads if s["name"].lower() == args.squad.lower()]
        if not squads:
            print(f"Squad '{args.squad}' not found.")
            return 1

    # Determine output filename based on date range
    if args.sprint_start:
        # Use sprint start date for filename
        date_str = args.sprint_start.replace("-", "")[:8]  # YYYYMMDD
        if args.sprint_end:
            end_str = args.sprint_end.replace("-", "")[:8]
            output_filename = f"Sprint_Report_{date_str}_to_{end_str}.csv"
        else:
            output_filename = f"Sprint_Report_{date_str}.csv"
    else:
        date_str = datetime.now().strftime("%m-%d-%Y")
        output_filename = f"Sprint_Report_{date_str}.csv"

    output_path = (
        Path(args.output) if args.output else REPORT_OUTPUT_DIR / output_filename
    )

    generate_report(
        squads, output_path, sprint_start=args.sprint_start, sprint_end=args.sprint_end
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
