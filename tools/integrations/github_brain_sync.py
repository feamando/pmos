#!/usr/bin/env python3
"""
GitHub-to-Brain Sync Tool

Fetches GitHub activity (PRs, commits) for Growth Division squads and writes to Brain
for context enrichment. Links Jira tickets to their GitHub PRs/commits.

Usage:
    python3 github_brain_sync.py                    # Default: fetch and write to Inbox
    python3 github_brain_sync.py --summarize        # Include Gemini summary
    python3 github_brain_sync.py --squad "Meal Kit"  # Single squad
    python3 github_brain_sync.py --analyze-files    # Include file change analysis
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add common directory to path for config_loader
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config_loader

# Constants
ROOT_DIR = config_loader.get_root_path()
SQUAD_REGISTRY_PATH = ROOT_DIR / "squad_registry.yaml"
BRAIN_INBOX_DIR = ROOT_DIR / "user" / "brain" / "Inbox"
BRAIN_ENTITIES_DIR = ROOT_DIR / "user" / "brain" / "Entities"
BRAIN_GITHUB_DIR = ROOT_DIR / "user" / "brain" / "GitHub"
BRAIN_PROJECTS_DIR = ROOT_DIR / "user" / "brain" / "Projects"
MAX_PRS_PER_SQUAD = 20
MAX_COMMITS_PER_SQUAD = 30
PARALLEL_WORKERS = 4
DEFAULT_LOOKBACK_DAYS = 7


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
        print("Error: GitHub CLI (gh) not found. Install from https://cli.github.com/")
        return None

    cmd = [GH_PATH, "api", endpoint]
    if jq_filter:
        cmd.extend(["--jq", jq_filter])

    try:
        # Explicitly set UTF-8 encoding to avoid Windows cp1252 issues
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", timeout=30)
        if result.returncode != 0:
            if "404" not in result.stderr and "Not Found" not in result.stderr:
                print(f"  Warning: gh api error for {endpoint}: {result.stderr[:100]}")
            return None

        if jq_filter:
            # jq output might be multiple JSON objects, parse line by line
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
        print(f"  Warning: gh api timeout for {endpoint}")
        return None
    except Exception as e:
        print(f"  Warning: gh api exception for {endpoint}: {e}")
        return None


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


def fetch_open_prs(repo: str, pr_prefix: str) -> List[Dict]:
    """Fetch open PRs for a repo filtered by prefix."""
    # Get all open PRs
    prs = run_gh_api(f"repos/{repo}/pulls?state=open&per_page=100")
    if not prs:
        return []

    # Filter by prefix in title
    filtered = []
    for pr in prs:
        title = pr.get("title", "")
        if pr_prefix and pr_prefix in title:
            # Calculate age
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
                    "reviews": [],  # Will be populated if needed
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

    # Filter by prefix in commit message
    filtered = []
    for commit in commits:
        message = commit.get("commit", {}).get("message", "")
        first_line = message.split("\n")[0]

        # Include if prefix matches OR if it's a merge commit for a matching PR
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
            "status": f.get("status"),  # added, removed, modified
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


def find_prs_for_jira_ticket(ticket_key: str, repos: List[str] = None) -> List[Dict]:
    """Search for PRs referencing a Jira ticket key."""
    if repos is None:
        repos = ["acme-corp/web"]  # Default to web repo

    all_prs = []
    for repo in repos:
        # Use GitHub search API
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
        # Fallback: use jira project key as PR prefix on default repo
        github_repos = [{"repo": "acme-corp/web", "pr_prefix": f"{jira_project}-"}]

    try:
        for repo_config in github_repos:
            repo = repo_config.get("repo", "acme-corp/web")
            pr_prefix = repo_config.get("pr_prefix", f"{jira_project}-")

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
        print(f"  Error fetching {squad_name}: {e}")

    return result


def fetch_all_squads_parallel(squads: List[Dict]) -> Dict[str, Dict]:
    """Fetch GitHub data for all squads in parallel."""
    results = {}

    print(f"Fetching GitHub data for {len(squads)} squads in parallel...")

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        futures = {
            executor.submit(fetch_squad_github, squad): squad for squad in squads
        }

        for future in as_completed(futures):
            squad = futures[future]
            try:
                data = future.result()
                results[squad["name"]] = data
                pr_count = len(data["open_prs"])
                commit_count = len(data["recent_commits"])
                print(f"  ✓ {squad['name']}: {pr_count} PRs, {commit_count} commits")
            except Exception as e:
                print(f"  ✗ {squad['name']}: {e}")
                results[squad["name"]] = {"error": str(e), "squad_name": squad["name"]}

    return results


def write_inbox_file(data: Dict[str, Dict], output_path: Optional[Path] = None) -> Path:
    """Write raw GitHub data to Brain/Inbox as markdown."""
    if output_path is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        output_path = BRAIN_INBOX_DIR / f"GITHUB_{date_str}.md"

    BRAIN_INBOX_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# GitHub Sync: {timestamp}",
        "",
        "Auto-generated by `github_brain_sync.py`. Contains GitHub activity for Growth Division squads.",
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
                    f"| [#{pr['number']}]({pr['url']}) | {pr['title'][:50]}{draft_marker} | @{pr['author']} | {pr['age']} | {pr['state']} |"
                )
        else:
            lines.append("*No open PRs.*")
        lines.append("")

        # Recent Commits
        commits = squad_data.get("recent_commits", [])
        lines.append(f"### Recent Commits ({len(commits)})")
        if commits:
            for commit in commits[:10]:  # Limit to 10 in output
                lines.append(
                    f"- `{commit['sha']}` {commit['message'][:60]} (@{commit['author']}, {commit['age']})"
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

    print(f"\nWrote inbox file: {output_path}")
    return output_path


def write_pr_activity_file(data: Dict[str, Dict]) -> Path:
    """Write dedicated PR activity file to Brain/GitHub/."""
    BRAIN_GITHUB_DIR.mkdir(parents=True, exist_ok=True)
    output_path = BRAIN_GITHUB_DIR / "PR_Activity.md"

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# PR Activity - Growth Division Squads",
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

    print(f"Wrote PR activity file: {output_path}")
    return output_path


def write_recent_commits_file(data: Dict[str, Dict]) -> Path:
    """Write dedicated recent commits file to Brain/GitHub/."""
    BRAIN_GITHUB_DIR.mkdir(parents=True, exist_ok=True)
    output_path = BRAIN_GITHUB_DIR / "Recent_Commits.md"

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Recent Commits - Growth Division Squads",
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
            for commit in commits[:15]:  # Limit display
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

    print(f"Wrote recent commits file: {output_path}")
    return output_path


def update_squad_entity(squad_name: str, squad_data: Dict) -> bool:
    """Update the GitHub Status section in Brain/Entities/Squad_*.md."""
    filename_map = {
        "Meal Kit": "Squad_Meal_Kit.md",
        "Wellness Brand": "Squad_The_Wellness_Brand.md",
        "Growth Platform": "Squad_Growth_Platform.md",
        "Product Innovation": "Squad_Market_Innovation.md",
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

        # Generate the new GitHub Status section
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        pr_count = len(squad_data.get("open_prs", []))
        commit_count = len(squad_data.get("recent_commits", []))

        new_section = f"""## GitHub Status
*Auto-updated: {date_str}*

- **Open PRs:** {pr_count}
- **Commits ({DEFAULT_LOOKBACK_DAYS}d):** {commit_count}
"""

        # Add active PRs
        if squad_data.get("open_prs"):
            new_section += "\n### Active PRs\n"
            for pr in squad_data["open_prs"][:5]:
                draft_marker = " [DRAFT]" if pr.get("draft") else ""
                new_section += f"- [#{pr['number']}]({pr['url']}) {pr['title'][:50]}{draft_marker} ({pr['age']} old)\n"

        # Replace existing GitHub Status section or append
        github_status_pattern = r"## GitHub Status\n.*?(?=\n## |\Z)"
        if re.search(github_status_pattern, content, re.DOTALL):
            content = re.sub(
                github_status_pattern, new_section.rstrip(), content, flags=re.DOTALL
            )
        else:
            # Append before changelog if exists, otherwise at end
            changelog_match = re.search(r"\n## Changelog", content)
            jira_status_match = re.search(r"\n## Jira Status", content)

            if changelog_match:
                insert_pos = changelog_match.start()
                content = (
                    content[:insert_pos] + "\n" + new_section + content[insert_pos:]
                )
            elif jira_status_match:
                # Insert after Jira Status section
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
        print(f"  Error updating {filename}: {e}")
        return False


def update_all_squad_entities(data: Dict[str, Dict]) -> int:
    """Update all squad entity files. Returns count of updated files."""
    updated = 0
    print("\nUpdating squad entity files with GitHub status...")

    for squad_name, squad_data in data.items():
        if squad_data.get("error"):
            continue
        if update_squad_entity(squad_name, squad_data):
            print(f"  ✓ Updated {squad_name}")
            updated += 1

    return updated


def summarize_with_gemini(data: Dict[str, Dict]) -> Optional[str]:
    """Use Gemini to create an intelligent summary of the GitHub data."""
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

    prompt = f"""Analyze this GitHub activity for Growth Division squads and provide a brief summary (3-5 bullet points) highlighting:
1. PRs that may need attention (old, draft, blocked)
2. Active development areas based on commit patterns
3. Any velocity or collaboration observations

Data:
{chr(10).join(summary_input)}

Keep the summary concise and actionable."""

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Warning: Gemini summary failed: {e}")
        return None


def fetch_repo_file(repo: str, filepath: str) -> Optional[str]:
    """Fetch raw content of a file from the repo (e.g., README.md)."""
    # Use gh api to get file content (base64 encoded by default, or raw)
    # media type raw gives the raw content
    try:
        cmd = [
            GH_PATH,
            "api",
            f"repos/{repo}/contents/{filepath}",
            "-H",
            "Accept: application/vnd.github.raw",
        ]
        # Explicit UTF-8 encoding
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", timeout=30)
        if result.returncode == 0:
            return result.stdout
        return None
    except Exception as e:
        print(f"  Warning: Failed to fetch {filepath} from {repo}: {e}")
        return None


def update_project_technical_context(squad_name: str, context: str) -> bool:
    """Update the Technical Context section in Brain/Projects/*.md."""
    # Map Squad -> Project File
    # Note: Product Innovation doesn't map 1:1 to a single project file yet
    filename_map = {
        "Meal Kit": "Projects/Meal_Kit.md",
        "Wellness Brand": "Projects/The_Wellness_Brand.md",
        "Growth Platform": "Projects/Growth_Platform.md",
    }

    filename = filename_map.get(squad_name)
    if not filename:
        return False

    project_path = ROOT_DIR / "user" / "brain" / filename
    if not project_path.exists():
        print(f"  Project file not found: {project_path}")
        return False

    try:
        with open(project_path, "r", encoding="utf-8") as f:
            content = f.read()

        # We want to replace or add "## Technical Context"
        header = "## Technical Context"
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        new_block = f"{header}\n*Auto-synced from GitHub: {date_str}*\n\n{context}\n"

        # Regex to find existing section
        pattern = f"{re.escape(header)}.*?(?=\\n## |\\Z)"

        if re.search(pattern, content, re.DOTALL):
            content = re.sub(pattern, new_block.strip(), content, flags=re.DOTALL)
        else:
            # Append before Changelog or at end
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
        print(f"  Error updating project {filename}: {e}")
        return False


def summarize_readme_with_gemini(readme_content: str, repo_name: str) -> Optional[str]:
    """Summarize a README for technical context."""
    try:
        import google.generativeai as genai
    except ImportError:
        return None

    gemini_config = config_loader.get_gemini_config()
    api_key = gemini_config.get("api_key")
    if not api_key:
        return None

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(gemini_config.get("model", "gemini-2.5-flash"))

    prompt = f"""Summarize the following README.md for the repository '{repo_name}' into a concise 'Technical Context' section for a project documentation file.
    Focus on: Tech stack, key architecture patterns, deployment, and core capabilities. 
    Keep it under 200 words. Use bullet points.
    
    README Content:
    {readme_content[:10000]} 
    """

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Sync GitHub data to Brain for Growth Division squads"
    )
    parser.add_argument(
        "--squad", type=str, help='Sync specific squad only (e.g., "Meal Kit")'
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

    # Check gh CLI
    if not GH_PATH:
        print("Error: GitHub CLI (gh) not found. Install from https://cli.github.com/")
        return 1

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

    # Project Updates (README Sync)
    if args.update_projects:
        print("\nUpdating Project Technical Contexts...")
        for squad in squads:
            squad_name = squad["name"]

            # Find primary repo
            repos = squad.get("github_repos", [])
            if not repos:
                continue

            # Prefer 'web' repo or first one
            primary_repo = repos[0].get("repo")
            for r in repos:
                if "web" in r.get("repo", ""):
                    primary_repo = r.get("repo")
                    break

            if not primary_repo:
                continue

            print(f"  Fetching README for {squad_name} ({primary_repo})...")
            readme = fetch_repo_file(primary_repo, "README.md")

            if readme:
                # Summarize
                summary = summarize_readme_with_gemini(readme, primary_repo)
                if not summary:
                    # Fallback if no Gemini or error
                    summary = f"**Repo:** [{primary_repo}](https://github.com/{primary_repo})\n\n(Gemini summary unavailable. Please check repo manually.)"

                if update_project_technical_context(squad_name, summary):
                    print(f"  ✓ Updated project file for {squad_name}")
            else:
                print(f"  ✗ No README found for {primary_repo}")

    # Analyze files if requested
    if args.analyze_files:
        print("\nAnalyzing file changes...")
        for squad_name, squad_data in data.items():
            all_files = []
            for pr in squad_data.get("open_prs", [])[:5]:  # Limit to top 5 PRs
                repo = pr.get("repo", "acme-corp/web")
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
        print(f"Updated {updated_count} entity files.")

    # Generate Gemini summary if requested
    if args.summarize:
        print("\nGenerating Gemini summary...")
        summary = summarize_with_gemini(data)
        if summary:
            print("\n--- GitHub Activity Summary ---")
            print(summary)
            print("-------------------------------\n")

            # Append summary to inbox file
            with open(inbox_path, "a", encoding="utf-8") as f:
                f.write("\n## Executive Summary (Gemini)\n\n")
                f.write(summary)
                f.write("\n")

    print("\nGitHub sync complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
