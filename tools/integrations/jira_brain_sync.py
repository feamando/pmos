#!/usr/bin/env python3
"""
Jira-to-Brain Sync Tool

Fetches recent Jira updates from Growth Division squads and writes to Brain
for context enrichment. Designed to run without consuming Claude Code context.

Usage:
    python3 jira_brain_sync.py                    # Default: fetch and write to Inbox
    python3 jira_brain_sync.py --summarize        # Include Gemini summary
    python3 jira_brain_sync.py --squad "Meal Kit"  # Single squad
    python3 jira_brain_sync.py --github           # Include GitHub links (Phase 2)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from atlassian import Jira

# Add common directory to path for config_loader
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config_loader

# Constants
ROOT_DIR = config_loader.get_root_path()
SQUAD_REGISTRY_PATH = ROOT_DIR / "squad_registry.yaml"
BRAIN_DIR = ROOT_DIR / "user" / "brain"
BRAIN_INBOX_DIR = BRAIN_DIR / "Inbox"
BRAIN_ENTITIES_DIR = BRAIN_DIR / "Entities"
MAX_ITEMS_PER_CATEGORY = 15
PARALLEL_WORKERS = 4


def get_jira_client() -> Jira:
    """Initialize Jira client from config."""
    conf = config_loader.get_jira_config()
    if not conf["url"] or not conf["username"] or not conf["api_token"]:
        raise ValueError(
            "Jira configuration missing in .env (JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN)"
        )

    return Jira(
        url=conf["url"],
        username=conf["username"],
        password=conf["api_token"],
        cloud=True,
    )


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


def fetch_squad_jira(squad: Dict, jira: Jira) -> Dict[str, Any]:
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
        epics_jql = f"project = {project_key} AND issuetype = Epic AND status NOT IN (Done, Closed) ORDER BY updated DESC"
        epics_response = jira.jql(epics_jql, limit=MAX_ITEMS_PER_CATEGORY)
        for issue in epics_response.get("issues", []):
            result["epics"].append(parse_issue(issue))

        # Fetch In Progress Items
        in_progress_jql = (
            f'project = {project_key} AND status = "In Progress" ORDER BY updated DESC'
        )
        in_progress_response = jira.jql(in_progress_jql, limit=MAX_ITEMS_PER_CATEGORY)
        for issue in in_progress_response.get("issues", []):
            result["in_progress"].append(parse_issue(issue))

        # Fetch Blockers (High priority or flagged)
        blockers_jql = f"project = {project_key} AND (priority = High OR priority = Highest OR labels = blocked) AND status NOT IN (Done, Closed) ORDER BY priority DESC, updated DESC"
        blockers_response = jira.jql(blockers_jql, limit=MAX_ITEMS_PER_CATEGORY)
        for issue in blockers_response.get("issues", []):
            result["blockers"].append(parse_issue(issue))

    except Exception as e:
        result["error"] = str(e)
        print(f"  Error fetching {squad_name}: {e}")

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
        "github_links": [],  # Populated in Phase 2
    }


def fetch_all_squads_parallel(squads: List[Dict]) -> Dict[str, Dict]:
    """Fetch Jira data for all squads in parallel."""
    results = {}
    jira = get_jira_client()

    print(f"Fetching Jira data for {len(squads)} squads in parallel...")

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        futures = {
            executor.submit(fetch_squad_jira, squad, jira): squad for squad in squads
        }

        for future in as_completed(futures):
            squad = futures[future]
            try:
                data = future.result()
                results[squad["name"]] = data
                epic_count = len(data["epics"])
                ip_count = len(data["in_progress"])
                blocker_count = len(data["blockers"])
                print(
                    f"  ✓ {squad['name']}: {epic_count} epics, {ip_count} in-progress, {blocker_count} blockers"
                )
            except Exception as e:
                print(f"  ✗ {squad['name']}: {e}")
                results[squad["name"]] = {"error": str(e), "squad_name": squad["name"]}

    return results


def write_inbox_file(data: Dict[str, Dict], output_path: Optional[Path] = None) -> Path:
    """Write raw Jira data to Brain/Inbox as markdown."""
    if output_path is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        output_path = BRAIN_INBOX_DIR / f"JIRA_{date_str}.md"

    BRAIN_INBOX_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# Jira Sync: {timestamp}",
        "",
        "Auto-generated by `jira_brain_sync.py`. Contains raw Jira data for Growth Division squads.",
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

    print(f"\nWrote inbox file: {output_path}")
    return output_path


def update_squad_entity(squad_name: str, squad_data: Dict) -> bool:
    """
    Update the Jira Status section in Brain/Entities/Squad_*.md

    Returns True if updated, False if file not found or error.
    """
    # Map squad names to entity filenames
    filename_map = {
        "Meal Kit": "Squad_Meal_Kit.md",
        "Brand B": "Squad_Brand_B.md",
        "Growth Platform": "Squad_Growth_Platform.md",
        "Product Innovation": "Squad_Product_Innovation.md",
    }

    filename = filename_map.get(squad_name)
    if not filename:
        return False

    entity_path = BRAIN_ENTITIES_DIR / filename
    if not entity_path.exists():
        print(f"  Entity file not found: {entity_path}")
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
        print(f"  Error updating {filename}: {e}")
        return False


def update_all_squad_entities(data: Dict[str, Dict]) -> int:
    """Update all squad entity files. Returns count of updated files."""
    updated = 0
    print("\nUpdating squad entity files...")

    for squad_name, squad_data in data.items():
        if squad_data.get("error"):
            continue
        if update_squad_entity(squad_name, squad_data):
            print(f"  ✓ Updated {squad_name}")
            updated += 1

    return updated


def summarize_with_gemini(data: Dict[str, Dict]) -> Optional[str]:
    """
    Use Gemini to create an intelligent summary of the Jira data.
    Returns summary string or None if failed.
    """
    try:
        import google.generativeai as genai
    except ImportError:
        print("Warning: google-generativeai not installed. Skipping Gemini summary.")
        return None

    gemini_config = config_loader.get_gemini_config()
    api_key = gemini_config.get("api_key")

    if not api_key:
        print("Warning: GEMINI_API_KEY not set. Skipping Gemini summary.")
        return None

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(gemini_config.get("model", "gemini-2.5-flash"))

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

    prompt = f"""Analyze this Jira status for Growth Division squads and provide a brief executive summary (3-5 bullet points) highlighting:
1. Key blockers that need attention
2. Major initiatives in progress
3. Any patterns or risks across squads

Data:
{chr(10).join(summary_input)}

Keep the summary concise and actionable."""

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Warning: Gemini summary failed: {e}")
        return None


def fetch_github_links_for_issue(issue_key: str, repos: List[str] = None) -> List[Dict]:
    """
    Use gh CLI to find PRs referencing the issue key via GitHub Search API.
    Returns list of PR dicts with number, title, state, url.
    """
    if repos is None:
        repos = ["acme-corp/web"]

    gh_path = shutil.which("gh")
    if not gh_path:
        return []

    all_prs = []
    for repo in repos:
        try:
            # Use GitHub search API for better results
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
    Enrich issue data with GitHub links (Phase 2).
    Only enriches blockers and top in-progress items to save API calls.
    """
    print("\nEnriching with GitHub links...")

    for squad_name, squad_data in data.items():
        if squad_data.get("error"):
            continue

        # Enrich blockers
        for item in squad_data.get("blockers", []):
            prs = fetch_github_links_for_issue(item["key"])
            if prs:
                # Store both full PR info and simple URL list for compatibility
                item["github_prs"] = prs
                item["github_links"] = [pr["url"] for pr in prs]
                print(f"  Found {len(prs)} PR(s) for {item['key']}")

        # Enrich top 5 in-progress
        for item in squad_data.get("in_progress", [])[:5]:
            prs = fetch_github_links_for_issue(item["key"])
            if prs:
                item["github_prs"] = prs
                item["github_links"] = [pr["url"] for pr in prs]

    return data


def main():
    parser = argparse.ArgumentParser(
        description="Sync Jira data to Brain for Growth Division squads"
    )
    parser.add_argument(
        "--squad", type=str, help='Sync specific squad only (e.g., "Meal Kit")'
    )
    parser.add_argument(
        "--summarize", action="store_true", help="Include Gemini-generated summary"
    )
    parser.add_argument(
        "--github", action="store_true", help="Include GitHub PR/commit links (Phase 2)"
    )
    parser.add_argument(
        "--no-entities", action="store_true", help="Skip updating squad entity files"
    )
    parser.add_argument("--output", type=str, help="Custom output path for inbox file")

    args = parser.parse_args()

    # Load squads
    squads = load_squad_registry(filter_tribe="Growth Division")
    if not squads:
        print("No squads found in registry.")
        return 1

    # Filter to specific squad if requested
    if args.squad:
        squads = [s for s in squads if s["name"].lower() == args.squad.lower()]
        if not squads:
            print(f"Squad '{args.squad}' not found in registry.")
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
        print(f"Updated {updated_count} entity files.")

    # Generate Gemini summary if requested
    if args.summarize:
        print("\nGenerating Gemini summary...")
        summary = summarize_with_gemini(data)
        if summary:
            print("\n--- Executive Summary ---")
            print(summary)
            print("-------------------------\n")

            # Append summary to inbox file
            with open(inbox_path, "a", encoding="utf-8") as f:
                f.write("\n## Executive Summary (Gemini)\n\n")
                f.write(summary)
                f.write("\n")

    print("\nJira sync complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
