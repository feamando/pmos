#!/usr/bin/env python3
"""
Jira-to-Brain Sync Tool (v5.0)

Fetches recent Jira updates from configured squads and writes to Brain
for context enrichment. Designed to run without consuming Claude Code context.

Usage:
    python3 jira_brain_sync.py                    # Default: fetch and write to Inbox
    python3 jira_brain_sync.py --summarize        # Include Gemini summary
    python3 jira_brain_sync.py --squad "My Squad"   # Single squad
    python3 jira_brain_sync.py --github           # Include GitHub links
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import yaml
except ImportError:
    yaml = None
    logger.warning("PyYAML not installed. Install with: pip install pyyaml")

try:
    from atlassian import Jira
except ImportError:
    Jira = None
    logger.warning("atlassian-python-api not installed. Install with: pip install atlassian-python-api")

# v5 imports
try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from core.config_loader import get_config

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    get_paths = None

try:
    from pm_os_base.tools.core.connector_bridge import get_auth
except ImportError:
    get_auth = None


# ---------------------------------------------------------------------------
# Configuration (config-driven, zero hardcoded values)
# ---------------------------------------------------------------------------

def _resolve_brain_dir() -> Path:
    """Resolve brain directory via path_resolver or config."""
    if get_paths is not None:
        try:
            return get_paths().brain
        except Exception:
            pass
    config = get_config()
    if config.user_path:
        return config.user_path / "brain"
    return Path.cwd() / "user" / "brain"


def _resolve_squad_registry_path() -> Path:
    """Resolve squad registry path via path_resolver or config."""
    config = get_config()
    registry = config.get("integrations.jira.squad_registry_path")
    if registry:
        return Path(registry)
    if get_paths is not None:
        try:
            return get_paths().root / "squad_registry.yaml"
        except Exception:
            pass
    if config.user_path:
        return config.user_path.parent / "squad_registry.yaml"
    return Path.cwd() / "squad_registry.yaml"


MAX_ITEMS_PER_CATEGORY = 15
PARALLEL_WORKERS = 4


# ---------------------------------------------------------------------------
# Jira Client
# ---------------------------------------------------------------------------

def get_jira_client() -> "Jira":
    """Initialize Jira client from connector_bridge or config."""
    if Jira is None:
        raise ImportError("atlassian-python-api not installed")

    config = get_config()
    jira_config = config.get("integrations.jira", {}) or {}

    url = jira_config.get("url") or os.getenv("JIRA_URL", "")
    username = jira_config.get("username") or os.getenv("JIRA_USERNAME", "")
    api_token = os.getenv("JIRA_API_TOKEN", "")

    if get_auth is not None:
        auth = get_auth("jira")
        if auth.source == "env" and auth.token:
            api_token = api_token or auth.token

    if not url or not username or not api_token:
        raise ValueError(
            "Jira configuration missing. Set JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN "
            "in .env or configure integrations.jira in config.yaml"
        )

    return Jira(
        url=url,
        username=username,
        password=api_token,
        cloud=True,
    )


# ---------------------------------------------------------------------------
# Squad Registry
# ---------------------------------------------------------------------------

def load_squad_registry(filter_tribe: Optional[str] = None) -> List[Dict]:
    """Load squads from registry, optionally filtering by tribe."""
    if yaml is None:
        logger.error("PyYAML required to load squad registry")
        return []

    registry_path = _resolve_squad_registry_path()
    if not registry_path.exists():
        logger.error("Squad registry not found at %s", registry_path)
        return []

    with open(registry_path, "r") as f:
        data = yaml.safe_load(f)

    squads = data.get("squads", [])
    if filter_tribe:
        squads = [s for s in squads if s.get("tribe") == filter_tribe]

    return squads


# ---------------------------------------------------------------------------
# Jira Data Fetching
# ---------------------------------------------------------------------------

def fetch_squad_jira(squad: Dict, jira: "Jira") -> Dict[str, Any]:
    """
    Fetch epics, in-progress items, and blockers for a single squad.

    Returns dict with:
        - squad_name: str
        - project_key: str
        - fetched_at: str (ISO timestamp)
        - epics: list of dicts
        - in_progress: list of dicts
        - blockers: list of dicts
        - error: str (if failed)
    """
    project_key = squad.get("jira_project")
    squad_name = squad.get("name")

    result = {
        "squad_name": squad_name,
        "project_key": project_key,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "epics": [],
        "in_progress": [],
        "blockers": [],
        "error": None,
    }

    try:
        # Fetch Active Epics
        epics_jql = (
            f"project = {project_key} AND issuetype = Epic "
            f"AND status NOT IN (Done, Closed) ORDER BY updated DESC"
        )
        epics_response = jira.jql(epics_jql, limit=MAX_ITEMS_PER_CATEGORY)
        for issue in epics_response.get("issues", []):
            result["epics"].append(parse_issue(issue))

        # Fetch In Progress Items
        in_progress_jql = (
            f'project = {project_key} AND status = "In Progress" '
            f"ORDER BY updated DESC"
        )
        in_progress_response = jira.jql(in_progress_jql, limit=MAX_ITEMS_PER_CATEGORY)
        for issue in in_progress_response.get("issues", []):
            result["in_progress"].append(parse_issue(issue))

        # Fetch Blockers (High priority or flagged)
        blockers_jql = (
            f"project = {project_key} AND "
            f"(priority = High OR priority = Highest OR labels = blocked) "
            f"AND status NOT IN (Done, Closed) "
            f"ORDER BY priority DESC, updated DESC"
        )
        blockers_response = jira.jql(blockers_jql, limit=MAX_ITEMS_PER_CATEGORY)
        for issue in blockers_response.get("issues", []):
            result["blockers"].append(parse_issue(issue))

    except Exception as e:
        result["error"] = str(e)
        logger.error("Error fetching %s: %s", squad_name, e)

    return result


def parse_issue(issue: Dict) -> Dict:
    """Extract relevant fields from a Jira issue."""
    fields = issue.get("fields", {})
    assignee = fields.get("assignee")

    return {
        "key": issue.get("key"),
        "summary": fields.get("summary", ""),
        "status": fields.get("status", {}).get("name", "Unknown"),
        "priority": (
            fields.get("priority", {}).get("name", "None")
            if fields.get("priority")
            else "None"
        ),
        "assignee": (
            assignee.get("displayName", "Unassigned") if assignee else "Unassigned"
        ),
        "updated": fields.get("updated", "")[:10],  # YYYY-MM-DD
        "labels": fields.get("labels", []),
        "github_links": [],
    }


def fetch_all_squads_parallel(squads: List[Dict]) -> Dict[str, Dict]:
    """Fetch Jira data for all squads in parallel."""
    results = {}
    jira = get_jira_client()

    logger.info("Fetching Jira data for %d squads in parallel...", len(squads))

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        futures = {
            executor.submit(fetch_squad_jira, squad, jira): squad for squad in squads
        }

        for future in as_completed(futures):
            squad = futures[future]
            try:
                data = future.result()
                results[squad["name"]] = data
                logger.info(
                    "  %s: %d epics, %d in-progress, %d blockers",
                    squad["name"],
                    len(data["epics"]),
                    len(data["in_progress"]),
                    len(data["blockers"]),
                )
            except Exception as e:
                logger.error("  %s: %s", squad["name"], e)
                results[squad["name"]] = {"error": str(e), "squad_name": squad["name"]}

    return results


# ---------------------------------------------------------------------------
# Brain Output: Inbox File
# ---------------------------------------------------------------------------

def write_inbox_file(data: Dict[str, Dict], output_path: Optional[Path] = None) -> Path:
    """Write raw Jira data to Brain/Inbox as markdown."""
    brain_dir = _resolve_brain_dir()
    brain_inbox_dir = brain_dir / "Inbox"

    if output_path is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        output_path = brain_inbox_dir / f"JIRA_{date_str}.md"

    brain_inbox_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# Jira Sync: {timestamp}",
        "",
        "Auto-generated by `jira_brain_sync.py`. Contains raw Jira data for configured squads.",
        "",
    ]

    for squad_name, squad_data in data.items():
        project_key = squad_data.get("project_key", "???")
        lines.append(f"## {squad_name} ({project_key})")
        lines.append("")

        if squad_data.get("error"):
            lines.append(f"**Error:** {squad_data['error']}")
            lines.append("")
            continue

        # Active Epics
        epics = squad_data.get("epics", [])
        lines.append(f"### Active Epics ({len(epics)})")
        if epics:
            lines.append("")
            lines.append("| Key | Summary | Status | Assignee |")
            lines.append("|-----|---------|--------|----------|")
            for epic in epics:
                lines.append(
                    f"| {epic['key']} | {epic['summary'][:60]} | {epic['status']} | {epic['assignee']} |"
                )
        else:
            lines.append("*No active epics.*")
        lines.append("")

        # In Progress
        in_progress = squad_data.get("in_progress", [])
        lines.append(f"### In Progress ({len(in_progress)})")
        if in_progress:
            for item in in_progress:
                assignee_str = (
                    f"@{item['assignee']}" if item["assignee"] != "Unassigned" else ""
                )
                lines.append(f"- [{item['key']}] {item['summary'][:80]} {assignee_str}")
        else:
            lines.append("*No items in progress.*")
        lines.append("")

        # Blockers
        blockers = squad_data.get("blockers", [])
        lines.append(f"### Blockers ({len(blockers)})")
        if blockers:
            for item in blockers:
                priority_str = (
                    f"(Priority: {item['priority']})"
                    if item["priority"] != "None"
                    else ""
                )
                lines.append(
                    f"- **[{item['key']}]** {item['summary'][:80]} {priority_str}"
                )
                if item.get("github_links"):
                    for link in item["github_links"]:
                        lines.append(f"  - GitHub: {link}")
        else:
            lines.append("*No blockers.*")
        lines.append("")
        lines.append("---")
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info("Wrote inbox file: %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# Brain Output: Entity Updates
# ---------------------------------------------------------------------------

def update_squad_entity(squad_name: str, squad_data: Dict) -> bool:
    """
    Update the Jira Status section in Brain/Entities/Squad_*.md

    Squad-to-filename mapping is loaded from config. No hardcoded squad names.

    Returns True if updated, False if file not found or error.
    """
    brain_dir = _resolve_brain_dir()
    entities_dir = brain_dir / "Entities"

    config = get_config()
    # Config-driven mapping: integrations.jira.squad_entity_map
    # Example: {"My Squad": "Squad_My_Squad.md", ...}
    entity_map = config.get("integrations.jira.squad_entity_map", {}) or {}

    filename = entity_map.get(squad_name)
    if not filename:
        # Fallback: auto-generate filename from squad name
        safe_name = squad_name.replace(" ", "_")
        filename = f"Squad_{safe_name}.md"

    entity_path = entities_dir / filename
    if not entity_path.exists():
        logger.debug("Entity file not found: %s", entity_path)
        return False

    try:
        with open(entity_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Generate the new Jira Status section
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        epic_count = len(squad_data.get("epics", []))
        ip_count = len(squad_data.get("in_progress", []))
        blocker_count = len(squad_data.get("blockers", []))

        new_section = f"""## Jira Status
*Auto-updated: {date_str}*

- **Active Epics:** {epic_count}
- **In Progress:** {ip_count}
- **Blockers:** {blocker_count}
"""

        # Add current focus (top 3 in-progress)
        if squad_data.get("in_progress"):
            new_section += "\n### Current Focus\n"
            for item in squad_data["in_progress"][:3]:
                new_section += f"- [{item['key']}] {item['summary'][:60]}\n"

        # Add blockers detail
        if squad_data.get("blockers"):
            new_section += "\n### Blockers\n"
            for item in squad_data["blockers"][:3]:
                new_section += f"- [{item['key']}] {item['summary'][:60]}\n"

        # Replace existing Jira Status section or append
        jira_status_pattern = r"## Jira Status\n.*?(?=\n## |\Z)"
        if re.search(jira_status_pattern, content, re.DOTALL):
            content = re.sub(
                jira_status_pattern, new_section.rstrip(), content, flags=re.DOTALL
            )
        else:
            # Append before changelog if exists, otherwise at end
            changelog_match = re.search(r"\n## Changelog", content)
            if changelog_match:
                insert_pos = changelog_match.start()
                content = (
                    content[:insert_pos] + "\n" + new_section + content[insert_pos:]
                )
            else:
                content = content.rstrip() + "\n\n" + new_section

        with open(entity_path, "w", encoding="utf-8") as f:
            f.write(content)

        return True

    except Exception as e:
        logger.error("Error updating %s: %s", filename, e)
        return False


def update_all_squad_entities(data: Dict[str, Dict]) -> int:
    """Update all squad entity files. Returns count of updated files."""
    updated = 0
    logger.info("Updating squad entity files...")

    for squad_name, squad_data in data.items():
        if squad_data.get("error"):
            continue
        if update_squad_entity(squad_name, squad_data):
            logger.info("  Updated %s", squad_name)
            updated += 1

    return updated


# ---------------------------------------------------------------------------
# Gemini Summary (optional)
# ---------------------------------------------------------------------------

def summarize_with_gemini(data: Dict[str, Dict]) -> Optional[str]:
    """
    Use Gemini to create an intelligent summary of the Jira data.
    Returns summary string or None if failed.
    """
    try:
        import google.generativeai as genai
    except ImportError:
        logger.warning("google-generativeai not installed. Skipping Gemini summary.")
        return None

    config = get_config()
    api_key = config.get_secret("GEMINI_API_KEY")
    model_name = config.get("integrations.gemini.model", "gemini-2.5-flash")

    if not api_key:
        logger.warning("GEMINI_API_KEY not set. Skipping Gemini summary.")
        return None

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    # Prepare compact data representation
    summary_input = []
    for squad_name, squad_data in data.items():
        if squad_data.get("error"):
            continue

        squad_summary = f"## {squad_name}\n"
        squad_summary += f"Epics: {len(squad_data.get('epics', []))}, "
        squad_summary += f"In Progress: {len(squad_data.get('in_progress', []))}, "
        squad_summary += f"Blockers: {len(squad_data.get('blockers', []))}\n"

        if squad_data.get("blockers"):
            squad_summary += "Blockers:\n"
            for b in squad_data["blockers"][:5]:
                squad_summary += (
                    f"- [{b['key']}] {b['summary']} (Priority: {b['priority']})\n"
                )

        if squad_data.get("in_progress"):
            squad_summary += "Top In Progress:\n"
            for item in squad_data["in_progress"][:5]:
                squad_summary += f"- [{item['key']}] {item['summary']}\n"

        summary_input.append(squad_summary)

    prompt = (
        "Analyze this Jira status for the configured squads and provide a brief "
        "executive summary (3-5 bullet points) highlighting:\n"
        "1. Key blockers that need attention\n"
        "2. Major initiatives in progress\n"
        "3. Any patterns or risks across squads\n\n"
        f"Data:\n{chr(10).join(summary_input)}\n\n"
        "Keep the summary concise and actionable."
    )

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.warning("Gemini summary failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# GitHub Link Enrichment
# ---------------------------------------------------------------------------

def fetch_github_links_for_issue(
    issue_key: str, repos: Optional[List[str]] = None
) -> List[Dict]:
    """
    Use gh CLI to find PRs referencing the issue key via GitHub Search API.
    Returns list of PR dicts with number, title, state, url.
    """
    config = get_config()
    if repos is None:
        repos = config.get_list("integrations.github.repos", [])
    if not repos:
        return []

    gh_path = shutil.which("gh")
    if not gh_path:
        return []

    all_prs = []
    for repo in repos:
        try:
            result = subprocess.run(
                [
                    gh_path,
                    "api",
                    f"search/issues?q=repo:{repo}+is:pr+{issue_key}+in:title&per_page=5",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )

            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                for item in data.get("items", []):
                    all_prs.append(
                        {
                            "number": item.get("number"),
                            "title": item.get("title", "")[:60],
                            "state": item.get("state"),
                            "url": item.get("html_url"),
                            "repo": repo,
                        }
                    )
        except Exception:
            pass

    return all_prs


def enrich_with_github_links(data: Dict[str, Dict]) -> Dict[str, Dict]:
    """
    Enrich issue data with GitHub links.
    Only enriches blockers and top in-progress items to save API calls.
    """
    logger.info("Enriching with GitHub links...")

    for squad_name, squad_data in data.items():
        if squad_data.get("error"):
            continue

        # Enrich blockers
        for item in squad_data.get("blockers", []):
            prs = fetch_github_links_for_issue(item["key"])
            if prs:
                item["github_prs"] = prs
                item["github_links"] = [pr["url"] for pr in prs]
                logger.info("  Found %d PR(s) for %s", len(prs), item["key"])

        # Enrich top 5 in-progress
        for item in squad_data.get("in_progress", [])[:5]:
            prs = fetch_github_links_for_issue(item["key"])
            if prs:
                item["github_prs"] = prs
                item["github_links"] = [pr["url"] for pr in prs]

    return data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Sync Jira data to Brain for configured squads"
    )
    parser.add_argument(
        "--squad", type=str, help='Sync specific squad only (e.g., "My Squad")'
    )
    parser.add_argument(
        "--tribe", type=str, default=None,
        help="Filter squads by tribe name (from config or squad_registry)"
    )
    parser.add_argument(
        "--summarize", action="store_true", help="Include Gemini-generated summary"
    )
    parser.add_argument(
        "--github", action="store_true", help="Include GitHub PR/commit links"
    )
    parser.add_argument(
        "--no-entities", action="store_true", help="Skip updating squad entity files"
    )
    parser.add_argument("--output", type=str, help="Custom output path for inbox file")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Determine tribe filter from config or CLI
    config = get_config()
    tribe_filter = args.tribe or config.get("integrations.jira.default_tribe")

    # Load squads
    squads = load_squad_registry(filter_tribe=tribe_filter)
    if not squads:
        # Fallback: try loading projects directly from config
        projects = config.get_list("integrations.jira.projects", [])
        if projects:
            squads = [{"name": p, "jira_project": p} for p in projects]
        else:
            logger.error("No squads found in registry and no jira.projects configured.")
            return 1

    # Filter to specific squad if requested
    if args.squad:
        squads = [s for s in squads if s["name"].lower() == args.squad.lower()]
        if not squads:
            logger.error("Squad '%s' not found in registry.", args.squad)
            return 1

    # Fetch data in parallel
    data = fetch_all_squads_parallel(squads)

    # Enrich with GitHub links if requested
    if args.github:
        data = enrich_with_github_links(data)

    # Write inbox file
    output_path = Path(args.output) if args.output else None
    inbox_path = write_inbox_file(data, output_path)

    # Update squad entities unless disabled
    if not args.no_entities:
        updated_count = update_all_squad_entities(data)
        logger.info("Updated %d entity files.", updated_count)

    # Generate Gemini summary if requested
    if args.summarize:
        logger.info("Generating Gemini summary...")
        summary = summarize_with_gemini(data)
        if summary:
            logger.info("--- Executive Summary ---\n%s\n-------------------------", summary)

            # Append summary to inbox file
            with open(inbox_path, "a", encoding="utf-8") as f:
                f.write("\n## Executive Summary (Gemini)\n\n")
                f.write(summary)
                f.write("\n")

    logger.info("Jira sync complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
