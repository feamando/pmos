#!/usr/bin/env python3
"""
GitHub-to-Brain Sync Tool (v5.0)

Fetches GitHub activity (PRs, commits) for configured squads and writes to Brain
for context enrichment. Links Jira tickets to their GitHub PRs/commits.

Usage:
    python3 github_brain_sync.py                    # Default: fetch and write to Inbox
    python3 github_brain_sync.py --summarize        # Include Gemini summary
    python3 github_brain_sync.py --squad "My Squad"   # Single squad
    python3 github_brain_sync.py --analyze-files    # Include file change analysis
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

try:
    import yaml
except ImportError:
    yaml = None
    logger.warning("PyYAML not installed. Install with: pip install pyyaml")

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

MAX_PRS_PER_SQUAD = 20
MAX_COMMITS_PER_SQUAD = 30
PARALLEL_WORKERS = 4
DEFAULT_LOOKBACK_DAYS = 7


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
    registry = config.get("integrations.github.squad_registry_path")
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


# ---------------------------------------------------------------------------
# GitHub CLI Helpers
# ---------------------------------------------------------------------------

def get_gh_path() -> Optional[str]:
    """Returns the path to gh CLI, cross-platform."""
    gh_in_path = shutil.which("gh")
    if gh_in_path:
        return gh_in_path
    windows_path = r"C:\Program Files\GitHub CLI\gh.exe"
    if os.path.exists(windows_path):
        return windows_path
    return None


GH_PATH = get_gh_path()


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
# GitHub Data Fetching
# ---------------------------------------------------------------------------

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
                if age.days > 0:
                    age_str = f"{age.days}d"
                else:
                    age_str = f"{age.seconds // 3600}h"

            filtered.append(
                {
                    "number": pr.get("number"),
                    "title": title[:80],
                    "author": pr.get("user", {}).get("login", "unknown"),
                    "url": pr.get("html_url"),
                    "state": pr.get("state"),
                    "created_at": created_at,
                    "age": age_str,
                    "draft": pr.get("draft", False),
                    "reviews": [],
                }
            )

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

            filtered.append(
                {
                    "sha": commit.get("sha", "")[:7],
                    "message": first_line[:80],
                    "author": commit.get("commit", {})
                    .get("author", {})
                    .get("name", "unknown"),
                    "date": commit_date,
                    "age": age_str,
                    "url": commit.get("html_url"),
                }
            )

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
        "frontend": 0,
        "backend": 0,
        "tests": 0,
        "config": 0,
        "docs": 0,
        "other": 0,
    }

    for f in files:
        filename = f.get("filename", "").lower()
        if any(x in filename for x in ["test", "spec", "e2e", "__test__"]):
            categories["tests"] += 1
        elif any(
            x in filename
            for x in [".tsx", ".jsx", ".css", ".scss", "component", "page"]
        ):
            categories["frontend"] += 1
        elif any(
            x in filename for x in [".go", ".py", ".kt", ".java", "service", "handler"]
        ):
            categories["backend"] += 1
        elif any(x in filename for x in [".json", ".yaml", ".yml", ".config", ".env"]):
            categories["config"] += 1
        elif any(x in filename for x in [".md", "readme", "doc"]):
            categories["docs"] += 1
        else:
            categories["other"] += 1

    return {k: v for k, v in categories.items() if v > 0}


def find_prs_for_jira_ticket(
    ticket_key: str, repos: Optional[List[str]] = None
) -> List[Dict]:
    """Search for PRs referencing a Jira ticket key."""
    if repos is None:
        config = get_config()
        repos = config.get_list("integrations.github.repos", [])
    if not repos:
        return []

    all_prs = []
    for repo in repos:
        search_result = run_gh_api(
            f"search/issues?q=repo:{repo}+is:pr+{ticket_key}+in:title&per_page=5"
        )
        if search_result and "items" in search_result:
            for item in search_result["items"]:
                all_prs.append(
                    {
                        "number": item.get("number"),
                        "title": item.get("title", "")[:60],
                        "state": item.get("state"),
                        "url": item.get("html_url"),
                        "repo": repo,
                    }
                )

    return all_prs


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
        # Fallback: use config repos with jira project key as prefix
        config = get_config()
        default_repos = config.get_list("integrations.github.repos", [])
        if default_repos:
            github_repos = [
                {"repo": r, "pr_prefix": f"{jira_project}-"} for r in default_repos
            ]
        else:
            result["error"] = "No github_repos configured for squad and no default repos in config"
            return result

    try:
        for repo_config in github_repos:
            repo = repo_config.get("repo", "")
            pr_prefix = repo_config.get("pr_prefix", f"{jira_project}-")

            if not repo:
                continue

            # Fetch PRs
            prs = fetch_open_prs(repo, pr_prefix)
            for pr in prs:
                pr["repo"] = repo
            result["open_prs"].extend(prs)

            # Fetch commits
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


# ---------------------------------------------------------------------------
# Brain Output: Inbox File
# ---------------------------------------------------------------------------

def write_inbox_file(data: Dict[str, Dict], output_path: Optional[Path] = None) -> Path:
    """Write raw GitHub data to Brain/Inbox as markdown."""
    brain_dir = _resolve_brain_dir()
    brain_inbox_dir = brain_dir / "Inbox"

    if output_path is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        output_path = brain_inbox_dir / f"GITHUB_{date_str}.md"

    brain_inbox_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# GitHub Sync: {timestamp}",
        "",
        "Auto-generated by `github_brain_sync.py`. Contains GitHub activity for configured squads.",
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


# ---------------------------------------------------------------------------
# Brain Output: Dedicated GitHub Files
# ---------------------------------------------------------------------------

def write_pr_activity_file(data: Dict[str, Dict]) -> Path:
    """Write dedicated PR activity file to Brain/GitHub/."""
    brain_dir = _resolve_brain_dir()
    brain_github_dir = brain_dir / "GitHub"
    brain_github_dir.mkdir(parents=True, exist_ok=True)
    output_path = brain_github_dir / "PR_Activity.md"

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
                lines.append(
                    f"- [#{pr['number']}]({pr['url']}) {pr['title'][:60]}{draft_marker}"
                )
                lines.append(f"  - Author: @{pr['author']} | Age: {pr['age']}")
        else:
            lines.append("*No open PRs*")
        lines.append("")

    # Summary at top
    lines.insert(3, f"**Total Open PRs:** {total_prs}")
    lines.insert(4, "")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info("Wrote PR activity file: %s", output_path)
    return output_path


def write_recent_commits_file(data: Dict[str, Dict]) -> Path:
    """Write dedicated recent commits file to Brain/GitHub/."""
    brain_dir = _resolve_brain_dir()
    brain_github_dir = brain_dir / "GitHub"
    brain_github_dir.mkdir(parents=True, exist_ok=True)
    output_path = brain_github_dir / "Recent_Commits.md"

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Recent Commits - Configured Squads",
        "",
        f"*Auto-updated: {timestamp}*",
        f"*Lookback: {DEFAULT_LOOKBACK_DAYS} days*",
        "",
    ]

    total_commits = 0
    for squad_name, squad_data in data.items():
        commits = squad_data.get("recent_commits", [])
        total_commits += len(commits)

        lines.append(f"## {squad_name} ({len(commits)} commits)")
        lines.append("")

        if commits:
            for commit in commits[:15]:
                lines.append(f"- `{commit['sha']}` {commit['message'][:60]}")
                lines.append(f"  - @{commit['author']} | {commit['age']}")
        else:
            lines.append("*No recent commits*")
        lines.append("")

    # Summary at top
    lines.insert(4, f"**Total Commits:** {total_commits}")
    lines.insert(5, "")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info("Wrote recent commits file: %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# Brain Output: Entity Updates
# ---------------------------------------------------------------------------

def update_squad_entity(squad_name: str, squad_data: Dict) -> bool:
    """Update the GitHub Status section in Brain/Entities/Squad_*.md."""
    brain_dir = _resolve_brain_dir()
    entities_dir = brain_dir / "Entities"

    config = get_config()
    entity_map = config.get("integrations.github.squad_entity_map", {}) or {}

    filename = entity_map.get(squad_name)
    if not filename:
        safe_name = squad_name.replace(" ", "_")
        filename = f"Squad_{safe_name}.md"

    entity_path = entities_dir / filename
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
            jira_status_match = re.search(r"\n## Jira Status", content)

            if changelog_match:
                insert_pos = changelog_match.start()
                content = (
                    content[:insert_pos] + "\n" + new_section + content[insert_pos:]
                )
            elif jira_status_match:
                jira_end = re.search(
                    r"## Jira Status\n.*?(?=\n## |\Z)", content, re.DOTALL
                )
                if jira_end:
                    insert_pos = jira_end.end()
                    content = (
                        content[:insert_pos]
                        + "\n\n"
                        + new_section
                        + content[insert_pos:]
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
    logger.info("Updating squad entity files with GitHub status...")

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
    """Use Gemini to create an intelligent summary of the GitHub data."""
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

    summary_input = []
    for squad_name, squad_data in data.items():
        if squad_data.get("error"):
            continue

        squad_summary = f"## {squad_name}\n"
        squad_summary += f"Open PRs: {len(squad_data.get('open_prs', []))}, "
        squad_summary += (
            f"Recent Commits: {len(squad_data.get('recent_commits', []))}\n"
        )

        if squad_data.get("open_prs"):
            squad_summary += "Open PRs:\n"
            for pr in squad_data["open_prs"][:5]:
                squad_summary += (
                    f"- #{pr['number']} {pr['title'][:50]} (Age: {pr['age']})\n"
                )

        summary_input.append(squad_summary)

    prompt = (
        "Analyze this GitHub activity for the configured squads and provide a brief "
        "summary (3-5 bullet points) highlighting:\n"
        "1. PRs that may need attention (old, draft, blocked)\n"
        "2. Active development areas based on commit patterns\n"
        "3. Any velocity or collaboration observations\n\n"
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
# Project Technical Context Updates
# ---------------------------------------------------------------------------

def fetch_repo_file(repo: str, filepath: str) -> Optional[str]:
    """Fetch raw content of a file from the repo (e.g., README.md)."""
    try:
        cmd = [
            GH_PATH,
            "api",
            f"repos/{repo}/contents/{filepath}",
            "-H",
            "Accept: application/vnd.github.raw",
        ]
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", timeout=30)
        if result.returncode == 0:
            return result.stdout
        return None
    except Exception as e:
        logger.warning("Failed to fetch %s from %s: %s", filepath, repo, e)
        return None


def update_project_technical_context(squad_name: str, context: str) -> bool:
    """Update the Technical Context section in Brain/Projects/*.md."""
    brain_dir = _resolve_brain_dir()

    config = get_config()
    project_map = config.get("integrations.github.project_entity_map", {}) or {}

    filename = project_map.get(squad_name)
    if not filename:
        safe_name = squad_name.replace(" ", "_")
        filename = f"Projects/{safe_name}.md"

    project_path = brain_dir / filename
    if not project_path.exists():
        logger.debug("Project file not found: %s", project_path)
        return False

    try:
        with open(project_path, "r", encoding="utf-8") as f:
            content = f.read()

        header = "## Technical Context"
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        new_block = f"{header}\n*Auto-synced from GitHub: {date_str}*\n\n{context}\n"

        pattern = f"{re.escape(header)}.*?(?=\\n## |\\Z)"

        if re.search(pattern, content, re.DOTALL):
            content = re.sub(pattern, new_block.strip(), content, flags=re.DOTALL)
        else:
            if "## Changelog" in content:
                content = content.replace(
                    "## Changelog", f"{new_block.strip()}\n\n## Changelog"
                )
            else:
                content = content.rstrip() + "\n\n" + new_block.strip()

        with open(project_path, "w", encoding="utf-8") as f:
            f.write(content)

        return True
    except Exception as e:
        logger.error("Error updating project %s: %s", filename, e)
        return False


def summarize_readme_with_gemini(readme_content: str, repo_name: str) -> Optional[str]:
    """Summarize a README for technical context."""
    try:
        import google.generativeai as genai
    except ImportError:
        return None

    config = get_config()
    api_key = config.get_secret("GEMINI_API_KEY")
    model_name = config.get("integrations.gemini.model", "gemini-2.5-flash")

    if not api_key:
        return None

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    prompt = (
        f"Summarize the following README.md for the repository '{repo_name}' into a "
        f"concise 'Technical Context' section for a project documentation file.\n"
        f"Focus on: Tech stack, key architecture patterns, deployment, and core capabilities.\n"
        f"Keep it under 200 words. Use bullet points.\n\n"
        f"README Content:\n{readme_content[:10000]}\n"
    )

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception:
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Sync GitHub data to Brain for configured squads"
    )
    parser.add_argument(
        "--squad", type=str, help='Sync specific squad only (e.g., "My Squad")'
    )
    parser.add_argument(
        "--tribe", type=str, default=None,
        help="Filter squads by tribe name"
    )
    parser.add_argument(
        "--summarize", action="store_true", help="Include Gemini-generated summary"
    )
    parser.add_argument(
        "--analyze-files",
        action="store_true",
        help="Include file change analysis for PRs (slower)",
    )
    parser.add_argument(
        "--no-entities", action="store_true", help="Skip updating squad entity files"
    )
    parser.add_argument(
        "--update-projects",
        action="store_true",
        help="Fetch READMEs and update Brain Project files (Technical Context)",
    )
    parser.add_argument("--output", type=str, help="Custom output path for inbox file")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Check gh CLI
    if not GH_PATH:
        logger.error("GitHub CLI (gh) not found. Install from https://cli.github.com/")
        return 1

    # Determine tribe filter from config or CLI
    config = get_config()
    tribe_filter = args.tribe or config.get("integrations.github.default_tribe")

    # Load squads
    squads = load_squad_registry(filter_tribe=tribe_filter)
    if not squads:
        logger.error("No squads found in registry.")
        return 1

    # Filter to specific squad if requested
    if args.squad:
        squads = [s for s in squads if s["name"].lower() == args.squad.lower()]
        if not squads:
            logger.error("Squad '%s' not found in registry.", args.squad)
            return 1

    # Fetch data in parallel
    data = fetch_all_squads_parallel(squads)

    # Project Updates (README Sync)
    if args.update_projects:
        logger.info("Updating Project Technical Contexts...")
        for squad in squads:
            squad_name = squad["name"]

            repos = squad.get("github_repos", [])
            if not repos:
                continue

            primary_repo = repos[0].get("repo")
            for r in repos:
                if "web" in r.get("repo", ""):
                    primary_repo = r.get("repo")
                    break

            if not primary_repo:
                continue

            logger.info("  Fetching README for %s (%s)...", squad_name, primary_repo)
            readme = fetch_repo_file(primary_repo, "README.md")

            if readme:
                summary = summarize_readme_with_gemini(readme, primary_repo)
                if not summary:
                    summary = (
                        f"**Repo:** [{primary_repo}](https://github.com/{primary_repo})\n\n"
                        f"(Gemini summary unavailable. Please check repo manually.)"
                    )

                if update_project_technical_context(squad_name, summary):
                    logger.info("  Updated project file for %s", squad_name)
            else:
                logger.warning("  No README found for %s", primary_repo)

    # Analyze files if requested
    if args.analyze_files:
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

    # Write inbox file
    output_path = Path(args.output) if args.output else None
    inbox_path = write_inbox_file(data, output_path)

    # Write dedicated GitHub files
    write_pr_activity_file(data)
    write_recent_commits_file(data)

    # Update squad entities unless disabled
    if not args.no_entities:
        updated_count = update_all_squad_entities(data)
        logger.info("Updated %d entity files.", updated_count)

    # Generate Gemini summary if requested
    if args.summarize:
        logger.info("Generating Gemini summary...")
        summary = summarize_with_gemini(data)
        if summary:
            logger.info("--- GitHub Activity Summary ---\n%s\n-------------------------------", summary)

            with open(inbox_path, "a", encoding="utf-8") as f:
                f.write("\n## Executive Summary (Gemini)\n\n")
                f.write(summary)
                f.write("\n")

    logger.info("GitHub sync complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
