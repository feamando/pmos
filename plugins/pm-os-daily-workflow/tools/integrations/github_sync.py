#!/usr/bin/env python3
"""
GitHub-to-Brain Sync Tool (v5.0)

Fetches GitHub activity (PRs, commits) for configured squads and writes to Brain
for context enrichment. All repo names and squad mappings come from config.

Usage:
    python3 github_sync.py                        # Default: fetch and write to Inbox
    python3 github_sync.py --squad "My Squad"     # Single squad
    python3 github_sync.py --analyze-files        # Include file change analysis
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
from datetime import datetime, timedelta, timezone
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

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# Constants (structural only — no hardcoded org/repo names)
MAX_PRS_PER_SQUAD = 20
MAX_COMMITS_PER_SQUAD = 30
PARALLEL_WORKERS = 4
DEFAULT_LOOKBACK_DAYS = 7


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


def _get_gh_path() -> Optional[str]:
    """Returns the path to gh CLI, cross-platform."""
    gh_in_path = shutil.which("gh")
    if gh_in_path:
        return gh_in_path
    windows_path = r"C:\Program Files\GitHub CLI\gh.exe"
    if os.path.exists(windows_path):
        return windows_path
    return None


GH_PATH = _get_gh_path()


def _get_configured_repos() -> List[str]:
    """Get list of configured GitHub repos from config."""
    config = get_config() if get_config else None
    if config:
        repos = config.get_list("integrations.github.repos")
        if repos:
            return repos
    return []


def run_gh_api(endpoint: str, jq_filter: Optional[str] = None) -> Optional[Any]:
    """Execute a gh api command and return parsed JSON."""
    if not GH_PATH:
        logger.error("GitHub CLI (gh) not found. Install from https://cli.github.com/")
        return None

    cmd = [GH_PATH, "api", endpoint]
    if jq_filter:
        cmd.extend(["--jq", jq_filter])

    try:
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", timeout=30)
        if result.returncode != 0:
            if "404" not in result.stderr and "Not Found" not in result.stderr:
                logger.warning("gh api error for %s: %s", endpoint, result.stderr[:100])
            return None

        if jq_filter:
            lines = result.stdout.strip().split("\n")
            if len(lines) == 1:
                try:
                    return json.loads(lines[0]) if lines[0] else None
                except json.JSONDecodeError:
                    return result.stdout.strip()
            else:
                return [json.loads(line) for line in lines if line.strip()]
        else:
            return json.loads(result.stdout) if result.stdout.strip() else None

    except subprocess.TimeoutExpired:
        logger.warning("gh api timeout for %s", endpoint)
        return None
    except Exception as e:
        logger.warning("gh api exception for %s: %s", endpoint, e)
        return None


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


def load_squad_registry(filter_tribe: Optional[str] = None) -> List[Dict]:
    """Load squads from registry, optionally filtering by tribe."""
    if not HAS_YAML:
        logger.error("PyYAML not installed — cannot load squad registry")
        return []

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


def fetch_open_prs(repo: str, pr_prefix: str) -> List[Dict]:
    """Fetch open PRs for a repo filtered by prefix."""
    prs = run_gh_api(f"repos/{repo}/pulls?state=open&per_page=100")
    if not prs:
        return []

    filtered = []
    for pr in prs:
        title = pr.get("title", "")
        if pr_prefix and pr_prefix in title:
            created_at = pr.get("created_at", "")
            age_str = "unknown"
            if created_at:
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                age = datetime.now(timezone.utc) - created
                age_str = f"{age.days}d" if age.days > 0 else f"{age.seconds // 3600}h"

            filtered.append({
                "number": pr.get("number"),
                "title": title[:80],
                "author": pr.get("user", {}).get("login", "unknown"),
                "url": pr.get("html_url"),
                "state": pr.get("state"),
                "created_at": created_at,
                "age": age_str,
                "draft": pr.get("draft", False),
                "reviews": [],
            })

    return filtered[:MAX_PRS_PER_SQUAD]


def fetch_recent_commits(
    repo: str, pr_prefix: str, days: int = DEFAULT_LOOKBACK_DAYS
) -> List[Dict]:
    """Fetch recent commits for a repo, filtered by prefix in message."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    commits = run_gh_api(f"repos/{repo}/commits?since={since}&per_page=100")
    if not commits:
        return []

    filtered = []
    for commit in commits:
        message = commit.get("commit", {}).get("message", "")
        first_line = message.split("\n")[0]

        if pr_prefix and (
            pr_prefix in first_line or pr_prefix.lower() in first_line.lower()
        ):
            commit_date = commit.get("commit", {}).get("author", {}).get("date", "")
            age_str = "unknown"
            if commit_date:
                created = datetime.fromisoformat(commit_date.replace("Z", "+00:00"))
                age = datetime.now(timezone.utc) - created
                if age.days > 0:
                    age_str = f"{age.days}d ago"
                elif age.seconds >= 3600:
                    age_str = f"{age.seconds // 3600}h ago"
                else:
                    age_str = f"{age.seconds // 60}m ago"

            filtered.append({
                "sha": commit.get("sha", "")[:7],
                "message": first_line[:80],
                "author": commit.get("commit", {}).get("author", {}).get("name", "unknown"),
                "date": commit_date,
                "age": age_str,
                "url": commit.get("html_url"),
            })

    return filtered[:MAX_COMMITS_PER_SQUAD]


def fetch_pr_files(repo: str, pr_number: int) -> List[Dict]:
    """Fetch files changed in a PR for analysis."""
    files = run_gh_api(f"repos/{repo}/pulls/{pr_number}/files")
    if not files:
        return []

    return [
        {
            "filename": f.get("filename"),
            "status": f.get("status"),
            "additions": f.get("additions", 0),
            "deletions": f.get("deletions", 0),
        }
        for f in files
    ]


def analyze_file_changes(files: List[Dict]) -> Dict[str, int]:
    """Categorize file changes by type."""
    categories = {
        "frontend": 0, "backend": 0, "tests": 0,
        "config": 0, "docs": 0, "other": 0,
    }

    for f in files:
        filename = f.get("filename", "").lower()
        if any(x in filename for x in ["test", "spec", "e2e", "__test__"]):
            categories["tests"] += 1
        elif any(x in filename for x in [".tsx", ".jsx", ".css", ".scss", "component", "page"]):
            categories["frontend"] += 1
        elif any(x in filename for x in [".go", ".py", ".kt", ".java", "service", "handler"]):
            categories["backend"] += 1
        elif any(x in filename for x in [".json", ".yaml", ".yml", ".config", ".env"]):
            categories["config"] += 1
        elif any(x in filename for x in [".md", "readme", "doc"]):
            categories["docs"] += 1
        else:
            categories["other"] += 1

    return {k: v for k, v in categories.items() if v > 0}


def fetch_squad_github(squad: Dict) -> Dict[str, Any]:
    """Fetch GitHub data for a single squad."""
    squad_name = squad.get("name")
    github_repos = squad.get("github_repos", [])
    jira_project = squad.get("jira_project", "")

    result = {
        "squad_name": squad_name,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "open_prs": [],
        "recent_commits": [],
        "file_changes": {},
        "error": None,
    }

    if not github_repos:
        # Use configured default repos with jira project key as prefix
        default_repos = _get_configured_repos()
        if default_repos:
            github_repos = [
                {"repo": repo, "pr_prefix": f"{jira_project}-"}
                for repo in default_repos
            ]

    if not github_repos:
        logger.debug("No repos configured for squad %s", squad_name)
        return result

    try:
        for repo_config in github_repos:
            repo = repo_config.get("repo", "")
            if not repo:
                continue
            pr_prefix = repo_config.get("pr_prefix", f"{jira_project}-")

            prs = fetch_open_prs(repo, pr_prefix)
            for pr in prs:
                pr["repo"] = repo
            result["open_prs"].extend(prs)

            commits = fetch_recent_commits(repo, pr_prefix)
            for commit in commits:
                commit["repo"] = repo
            result["recent_commits"].extend(commits)

    except Exception as e:
        result["error"] = str(e)
        logger.error("Error fetching %s: %s", squad_name, e)

    return result


def fetch_all_squads_parallel(squads: List[Dict]) -> Dict[str, Dict]:
    """Fetch GitHub data for all squads in parallel."""
    results = {}
    logger.info("Fetching GitHub data for %d squads in parallel...", len(squads))

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        futures = {
            executor.submit(fetch_squad_github, squad): squad for squad in squads
        }

        for future in as_completed(futures):
            squad = futures[future]
            try:
                data = future.result()
                results[squad["name"]] = data
                logger.info(
                    "  %s: %d PRs, %d commits",
                    squad["name"],
                    len(data["open_prs"]),
                    len(data["recent_commits"]),
                )
            except Exception as e:
                logger.error("  %s: %s", squad["name"], e)
                results[squad["name"]] = {"error": str(e), "squad_name": squad["name"]}

    return results


def write_inbox_file(data: Dict[str, Dict], output_path: Optional[Path] = None) -> Path:
    """Write raw GitHub data to Brain/Inbox as markdown."""
    brain_dir = _resolve_brain_dir()
    inbox_dir = brain_dir / "Inbox"

    if output_path is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        output_path = inbox_dir / f"GITHUB_{date_str}.md"

    inbox_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# GitHub Sync: {timestamp}",
        "",
        "Auto-generated by `github_sync.py`. Contains GitHub activity for configured squads.",
        "",
    ]

    for squad_name, squad_data in data.items():
        lines.append(f"## {squad_name}")
        lines.append("")

        if squad_data.get("error"):
            lines.append(f"**Error:** {squad_data['error']}")
            lines.append("")
            continue

        # Open PRs
        prs = squad_data.get("open_prs", [])
        lines.append(f"### Open PRs ({len(prs)})")
        if prs:
            lines.append("")
            lines.append("| PR | Title | Author | Age | State |")
            lines.append("|----|-------|--------|-----|-------|")
            for pr in prs:
                draft_marker = " (draft)" if pr.get("draft") else ""
                lines.append(
                    f"| [#{pr['number']}]({pr['url']}) | {pr['title'][:50]}{draft_marker} "
                    f"| @{pr['author']} | {pr['age']} | {pr['state']} |"
                )
        else:
            lines.append("*No open PRs.*")
        lines.append("")

        # Recent Commits
        commits = squad_data.get("recent_commits", [])
        lines.append(f"### Recent Commits ({len(commits)})")
        if commits:
            for commit in commits[:10]:
                lines.append(
                    f"- `{commit['sha']}` {commit['message'][:60]} "
                    f"(@{commit['author']}, {commit['age']})"
                )
        else:
            lines.append("*No recent commits.*")
        lines.append("")

        # File Changes Summary
        if squad_data.get("file_changes"):
            lines.append("### File Change Summary")
            for category, count in squad_data["file_changes"].items():
                lines.append(f"- **{category.title()}:** {count} files")
            lines.append("")

        lines.append("---")
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info("Wrote inbox file: %s", output_path)
    return output_path


def write_pr_activity_file(data: Dict[str, Dict]) -> Path:
    """Write dedicated PR activity file to Brain/GitHub/."""
    brain_dir = _resolve_brain_dir()
    github_dir = brain_dir / "GitHub"
    github_dir.mkdir(parents=True, exist_ok=True)
    output_path = github_dir / "PR_Activity.md"

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# PR Activity - Configured Squads",
        "",
        f"*Auto-updated: {timestamp}*",
        "",
    ]

    total_prs = 0
    for squad_name, squad_data in data.items():
        prs = squad_data.get("open_prs", [])
        total_prs += len(prs)
        lines.append(f"## {squad_name} ({len(prs)} open)")
        lines.append("")

        if prs:
            for pr in prs:
                draft_marker = " [DRAFT]" if pr.get("draft") else ""
                lines.append(f"- [#{pr['number']}]({pr['url']}) {pr['title'][:60]}{draft_marker}")
                lines.append(f"  - Author: @{pr['author']} | Age: {pr['age']}")
        else:
            lines.append("*No open PRs*")
        lines.append("")

    lines.insert(3, f"**Total Open PRs:** {total_prs}")
    lines.insert(4, "")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info("Wrote PR activity file: %s", output_path)
    return output_path


def _get_squad_entity_map() -> Dict[str, str]:
    """Get squad-name-to-entity-filename mapping from config."""
    config = get_config() if get_config else None
    if config is not None:
        mapping = config.get("team.squad_entity_map")
        if mapping and isinstance(mapping, dict):
            return mapping

    squads = config.get("team.squads", []) if config else []
    entity_map = {}
    for squad in squads:
        name = squad if isinstance(squad, str) else squad.get("name", "")
        if name:
            safe_name = name.replace(" ", "_")
            entity_map[name] = f"Squad_{safe_name}.md"
    return entity_map


def update_squad_entity(squad_name: str, squad_data: Dict) -> bool:
    """Update the GitHub Status section in Brain/Entities/Squad_*.md."""
    entity_map = _get_squad_entity_map()
    filename = entity_map.get(squad_name)
    if not filename:
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
        pr_count = len(squad_data.get("open_prs", []))
        commit_count = len(squad_data.get("recent_commits", []))

        new_section = f"""## GitHub Status
*Auto-updated: {date_str}*

- **Open PRs:** {pr_count}
- **Commits ({DEFAULT_LOOKBACK_DAYS}d):** {commit_count}
"""

        if squad_data.get("open_prs"):
            new_section += "\n### Active PRs\n"
            for pr in squad_data["open_prs"][:5]:
                draft_marker = " [DRAFT]" if pr.get("draft") else ""
                new_section += (
                    f"- [#{pr['number']}]({pr['url']}) "
                    f"{pr['title'][:50]}{draft_marker} ({pr['age']} old)\n"
                )

        github_status_pattern = r"## GitHub Status\n.*?(?=\n## |\Z)"
        if re.search(github_status_pattern, content, re.DOTALL):
            content = re.sub(
                github_status_pattern, new_section.rstrip(), content, flags=re.DOTALL
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
    logger.info("Updating squad entity files with GitHub status...")

    for squad_name, squad_data in data.items():
        if squad_data.get("error"):
            continue
        if update_squad_entity(squad_name, squad_data):
            logger.info("  Updated %s", squad_name)
            updated += 1

    return updated


def run_sync(
    squad_filter: Optional[str] = None,
    analyze_files: bool = False,
    update_entities: bool = True,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Run GitHub sync programmatically.

    Args:
        squad_filter: Optional squad name to filter
        analyze_files: Whether to include file change analysis
        update_entities: Whether to update Brain entity files
        output_path: Custom output path for inbox file

    Returns:
        Dict with sync results
    """
    if not GH_PATH:
        return {"status": "error", "message": "GitHub CLI (gh) not found"}

    squads = load_squad_registry()
    if not squads:
        return {"status": "error", "message": "No squads found in registry"}

    if squad_filter:
        squads = [s for s in squads if s["name"].lower() == squad_filter.lower()]
        if not squads:
            return {"status": "error", "message": f"Squad '{squad_filter}' not found"}

    data = fetch_all_squads_parallel(squads)

    # Analyze files if requested
    if analyze_files:
        logger.info("Analyzing file changes...")
        for squad_name, squad_data in data.items():
            all_files = []
            for pr in squad_data.get("open_prs", [])[:5]:
                repo = pr.get("repo", "")
                if repo:
                    files = fetch_pr_files(repo, pr["number"])
                    all_files.extend(files)
            if all_files:
                squad_data["file_changes"] = analyze_file_changes(all_files)

    inbox_path = write_inbox_file(data, output_path)
    pr_path = write_pr_activity_file(data)

    entity_count = 0
    if update_entities:
        entity_count = update_all_squad_entities(data)

    return {
        "status": "success",
        "squads_synced": len(data),
        "entities_updated": entity_count,
        "inbox_file": str(inbox_path),
        "pr_activity_file": str(pr_path),
    }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Sync GitHub data to Brain for configured squads"
    )
    parser.add_argument("--squad", type=str, help="Sync specific squad only")
    parser.add_argument(
        "--analyze-files", action="store_true",
        help="Include file change analysis for PRs (slower)",
    )
    parser.add_argument(
        "--no-entities", action="store_true", help="Skip updating squad entity files"
    )
    parser.add_argument("--output", type=str, help="Custom output path for inbox file")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    output_path = Path(args.output) if args.output else None
    result = run_sync(
        squad_filter=args.squad,
        analyze_files=args.analyze_files,
        update_entities=not args.no_entities,
        output_path=output_path,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result.get("status") == "success":
            print(f"GitHub sync complete. {result['squads_synced']} squads synced.")
            print(f"Entities updated: {result['entities_updated']}")
            print(f"Inbox file: {result['inbox_file']}")
        else:
            print(f"Error: {result.get('message', 'Unknown error')}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
