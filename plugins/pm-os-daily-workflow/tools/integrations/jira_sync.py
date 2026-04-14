#!/usr/bin/env python3
"""
Jira-to-Brain Sync Tool (v5.0)

Fetches recent Jira updates for configured squads and writes to Brain
for context enrichment. All squad names, tribe filters, and repo defaults
are loaded from config — zero hardcoded values.

Usage:
    python3 jira_sync.py                        # Default: fetch and write to Inbox
    python3 jira_sync.py --summarize            # Include AI summary
    python3 jira_sync.py --squad "My Squad"     # Single squad
    python3 jira_sync.py --github               # Include GitHub links
"""

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# v5 imports: shared utils from pm_os_base
try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
        from tools.core.config_loader import get_config
    except ImportError:
        get_config = None

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        from tools.core.path_resolver import get_paths
    except ImportError:
        get_paths = None

try:
    from pm_os_base.tools.core.connector_bridge import get_auth
except ImportError:
    try:
        from tools.core.connector_bridge import get_auth
    except ImportError:
        get_auth = None

# Optional YAML for squad registry
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# Constants (non-hardcoded — structural only)
MAX_ITEMS_PER_CATEGORY = 15
PARALLEL_WORKERS = 4


def _resolve_brain_dir() -> Path:
    """Resolve brain directory from config/paths."""
    if get_paths is not None:
        try:
            return get_paths().brain
        except Exception:
            pass
    if get_config is not None:
        try:
            config = get_config()
            if config.user_path:
                return config.user_path / "brain"
        except Exception:
            pass
    return Path.cwd() / "user" / "brain"


def _resolve_squad_registry_path() -> Path:
    """Resolve squad registry path from config/paths."""
    if get_paths is not None:
        try:
            return get_paths().root / "squad_registry.yaml"
        except Exception:
            pass
    if get_config is not None:
        try:
            config = get_config()
            registry = config.get("team.squad_registry_path")
            if registry:
                return Path(registry)
            if config.user_path:
                return config.user_path.parent / "squad_registry.yaml"
        except Exception:
            pass
    return Path.cwd() / "squad_registry.yaml"


def _get_jira_client():
    """Initialize Jira client using connector_bridge for auth."""
    try:
        from atlassian import Jira
    except ImportError:
        logger.error("atlassian-python-api not installed. Run: pip install atlassian-python-api")
        return None

    if get_auth is not None:
        auth = get_auth("jira")
        if auth.source == "connector":
            logger.info("Jira auth via Claude connector (data fetched in session)")
            return None  # Connector mode — no direct API client needed
        elif auth.source == "env":
            pass  # Fall through to env-based setup
        else:
            logger.error("Jira auth not available: %s", auth.help_message)
            return None

    # Load credentials from config/env
    config = get_config() if get_config else None
    if config is None:
        logger.error("Config loader not available")
        return None

    url = config.get("integrations.jira.url") or config.get_secret("JIRA_URL")
    username = config.get("integrations.jira.username") or config.get_secret("JIRA_USERNAME")
    token = config.get_secret("JIRA_API_TOKEN")

    if not url or not username or not token:
        logger.error("Jira configuration missing (JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN)")
        return None

    return Jira(url=url, username=username, password=token, cloud=True)


def load_squad_registry(filter_tribe: Optional[str] = None) -> List[Dict]:
    """Load squads from registry, optionally filtering by tribe.

    The tribe filter comes from config if not explicitly provided.
    """
    if not HAS_YAML:
        logger.error("PyYAML not installed — cannot load squad registry")
        return []

    # If no explicit filter, use config default
    if filter_tribe is None and get_config is not None:
        try:
            filter_tribe = get_config().get("team.tribe")
        except Exception:
            pass

    registry_path = _resolve_squad_registry_path()
    if not registry_path.exists():
        logger.error("Squad registry not found at %s", registry_path)
        return []

    with open(registry_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    squads = data.get("squads", [])
    if filter_tribe:
        squads = [s for s in squads if s.get("tribe") == filter_tribe]

    return squads


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
        "updated": fields.get("updated", "")[:10],
        "labels": fields.get("labels", []),
        "github_links": [],
    }


def fetch_squad_jira(squad: Dict, jira) -> Dict[str, Any]:
    """Fetch epics, in-progress items, and blockers for a single squad."""
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
        # Active Epics
        epics_jql = (
            f"project = {project_key} AND issuetype = Epic "
            f"AND status NOT IN (Done, Closed) ORDER BY updated DESC"
        )
        epics_response = jira.jql(epics_jql, limit=MAX_ITEMS_PER_CATEGORY)
        for issue in epics_response.get("issues", []):
            result["epics"].append(parse_issue(issue))

        # In Progress Items
        ip_jql = (
            f'project = {project_key} AND status = "In Progress" '
            f"ORDER BY updated DESC"
        )
        ip_response = jira.jql(ip_jql, limit=MAX_ITEMS_PER_CATEGORY)
        for issue in ip_response.get("issues", []):
            result["in_progress"].append(parse_issue(issue))

        # Blockers
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


def fetch_all_squads_parallel(squads: List[Dict]) -> Dict[str, Dict]:
    """Fetch Jira data for all squads in parallel."""
    jira = _get_jira_client()
    if jira is None:
        logger.error("Could not initialize Jira client")
        return {}

    results = {}
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


def write_inbox_file(data: Dict[str, Dict], output_path: Optional[Path] = None) -> Path:
    """Write raw Jira data to Brain/Inbox as markdown."""
    brain_dir = _resolve_brain_dir()
    inbox_dir = brain_dir / "Inbox"

    if output_path is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        output_path = inbox_dir / f"JIRA_{date_str}.md"

    inbox_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# Jira Sync: {timestamp}",
        "",
        "Auto-generated by `jira_sync.py`. Contains raw Jira data for configured squads.",
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


def _get_squad_entity_map() -> Dict[str, str]:
    """Get squad-name-to-entity-filename mapping from config."""
    config = get_config() if get_config else None
    if config is not None:
        mapping = config.get("team.squad_entity_map")
        if mapping and isinstance(mapping, dict):
            return mapping

    # Build from configured squads list
    squads = config.get("team.squads", []) if config else []
    entity_map = {}
    for squad in squads:
        name = squad if isinstance(squad, str) else squad.get("name", "")
        if name:
            safe_name = name.replace(" ", "_")
            entity_map[name] = f"Squad_{safe_name}.md"
    return entity_map


def update_squad_entity(squad_name: str, squad_data: Dict) -> bool:
    """Update the Jira Status section in Brain/Entities/Squad_*.md."""
    entity_map = _get_squad_entity_map()
    filename = entity_map.get(squad_name)
    if not filename:
        logger.debug("No entity mapping for squad: %s", squad_name)
        return False

    brain_dir = _resolve_brain_dir()
    entity_path = brain_dir / "Entities" / filename
    if not entity_path.exists():
        logger.debug("Entity file not found: %s", entity_path)
        return False

    try:
        with open(entity_path, "r", encoding="utf-8") as f:
            content = f.read()

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

        if squad_data.get("in_progress"):
            new_section += "\n### Current Focus\n"
            for item in squad_data["in_progress"][:3]:
                new_section += f"- [{item['key']}] {item['summary'][:60]}\n"

        if squad_data.get("blockers"):
            new_section += "\n### Blockers\n"
            for item in squad_data["blockers"][:3]:
                new_section += f"- [{item['key']}] {item['summary'][:60]}\n"

        # Replace existing section or append
        jira_status_pattern = r"## Jira Status\n.*?(?=\n## |\Z)"
        if re.search(jira_status_pattern, content, re.DOTALL):
            content = re.sub(
                jira_status_pattern, new_section.rstrip(), content, flags=re.DOTALL
            )
        else:
            changelog_match = re.search(r"\n## Changelog", content)
            if changelog_match:
                insert_pos = changelog_match.start()
                content = content[:insert_pos] + "\n" + new_section + content[insert_pos:]
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


def fetch_github_links_for_issue(
    issue_key: str, repos: Optional[List[str]] = None
) -> List[Dict]:
    """Use gh CLI to find PRs referencing the issue key."""
    if repos is None:
        config = get_config() if get_config else None
        if config:
            repos = config.get_list("integrations.github.repos")
        if not repos:
            default_repo = (
                config.get("integrations.github.default_repo", "")
                if config
                else ""
            )
            repos = [default_repo] if default_repo else []

    if not repos:
        logger.debug("No GitHub repos configured for issue linking")
        return []

    gh_path = shutil.which("gh")
    if not gh_path:
        return []

    all_prs = []
    for repo in repos:
        try:
            result = subprocess.run(
                [
                    gh_path, "api",
                    f"search/issues?q=repo:{repo}+is:pr+{issue_key}+in:title&per_page=5",
                ],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                for item in data.get("items", []):
                    all_prs.append({
                        "number": item.get("number"),
                        "title": item.get("title", "")[:60],
                        "state": item.get("state"),
                        "url": item.get("html_url"),
                        "repo": repo,
                    })
        except Exception:
            pass

    return all_prs


def enrich_with_github_links(data: Dict[str, Dict]) -> Dict[str, Dict]:
    """Enrich issue data with GitHub links."""
    logger.info("Enriching with GitHub links...")

    for squad_name, squad_data in data.items():
        if squad_data.get("error"):
            continue

        for item in squad_data.get("blockers", []):
            prs = fetch_github_links_for_issue(item["key"])
            if prs:
                item["github_prs"] = prs
                item["github_links"] = [pr["url"] for pr in prs]
                logger.info("  Found %d PR(s) for %s", len(prs), item["key"])

        for item in squad_data.get("in_progress", [])[:5]:
            prs = fetch_github_links_for_issue(item["key"])
            if prs:
                item["github_prs"] = prs
                item["github_links"] = [pr["url"] for pr in prs]

    return data


def run_sync(
    squad_filter: Optional[str] = None,
    include_github: bool = False,
    update_entities: bool = True,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Run Jira sync programmatically.

    Args:
        squad_filter: Optional squad name to filter
        include_github: Whether to enrich with GitHub links
        update_entities: Whether to update Brain entity files
        output_path: Custom output path for inbox file

    Returns:
        Dict with sync results
    """
    squads = load_squad_registry()
    if not squads:
        return {"status": "error", "message": "No squads found in registry"}

    if squad_filter:
        squads = [s for s in squads if s["name"].lower() == squad_filter.lower()]
        if not squads:
            return {"status": "error", "message": f"Squad '{squad_filter}' not found"}

    data = fetch_all_squads_parallel(squads)

    if include_github:
        data = enrich_with_github_links(data)

    inbox_path = write_inbox_file(data, output_path)

    entity_count = 0
    if update_entities:
        entity_count = update_all_squad_entities(data)

    return {
        "status": "success",
        "squads_synced": len(data),
        "entities_updated": entity_count,
        "inbox_file": str(inbox_path),
    }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Sync Jira data to Brain for configured squads"
    )
    parser.add_argument("--squad", type=str, help="Sync specific squad only")
    parser.add_argument(
        "--github", action="store_true", help="Include GitHub PR links"
    )
    parser.add_argument(
        "--no-entities", action="store_true", help="Skip updating squad entity files"
    )
    parser.add_argument("--output", type=str, help="Custom output path for inbox file")
    parser.add_argument(
        "--json", action="store_true", help="Output result as JSON"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    output_path = Path(args.output) if args.output else None
    result = run_sync(
        squad_filter=args.squad,
        include_github=args.github,
        update_entities=not args.no_entities,
        output_path=output_path,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result.get("status") == "success":
            print(f"Jira sync complete. {result['squads_synced']} squads synced.")
            print(f"Entities updated: {result['entities_updated']}")
            print(f"Inbox file: {result['inbox_file']}")
        else:
            print(f"Error: {result.get('message', 'Unknown error')}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
