#!/usr/bin/env python3
"""
GitHub Commit Extractor

Extracts commit messages from configured repos for LLM analysis.
Uses gh CLI for authentication and API access.

Usage:
    python3 github_commit_extractor.py [--days N] [--dry-run]
    python3 github_commit_extractor.py --status
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add common directory to path for config_loader
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config_loader

# ============================================================================
# CONFIGURATION
# ============================================================================

ROOT_DIR = config_loader.get_root_path()
USER_DIR = ROOT_DIR / "user"
SQUAD_REGISTRY_PATH = ROOT_DIR / "squad_registry.yaml"
OUTPUT_DIR = USER_DIR / "brain" / "Inbox" / "GitHub"
RAW_DIR = OUTPUT_DIR / "Raw"
PROCESSED_DIR = OUTPUT_DIR / "Processed"

DEFAULT_LOOKBACK_DAYS = 180  # 6 months like other sources
BATCH_SIZE = 20  # Commits per batch
MAX_COMMITS_PER_REPO = 500

# Topic filters (same as GDocs/Slack)
TOPIC_FILTERS = [
    "growth division",
    "Meal Kit",
    "goodchop",
    "goc",
    "Brand B",
    "Brand B",
    "tpt",
    "Growth Platform",
    "vms",
    "product innovation",
    "market integration",
    "cross-selling",
    "cross selling",
    "crossselling",
    "otp",
    "one time purchase",
    "one-time purchase",
    "seasonal boxes",
    "seasonal box",
    "occasion boxes",
    "occasion box",
]

# ============================================================================
# GH CLI HELPERS
# ============================================================================


def get_gh_path() -> Optional[str]:
    """Returns the path to gh CLI."""
    gh_in_path = shutil.which("gh")
    if gh_in_path:
        return gh_in_path
    windows_path = r"C:\Program Files\GitHub CLI\gh.exe"
    if os.path.exists(windows_path):
        return windows_path
    return None


GH_PATH = get_gh_path()


def run_gh_api(endpoint: str, params: Dict = None) -> Optional[Any]:
    """Execute a gh api command and return parsed JSON."""
    if not GH_PATH:
        print("Error: GitHub CLI (gh) not found", file=sys.stderr)
        return None

    cmd = [GH_PATH, "api", endpoint]

    # Add query parameters
    if params:
        for key, value in params.items():
            cmd.extend(["-f", f"{key}={value}"])

    try:
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", timeout=60)
        if result.returncode != 0:
            if "404" not in result.stderr:
                print(
                    f"  Warning: gh api error: {result.stderr[:100]}", file=sys.stderr
                )
            return None

        return json.loads(result.stdout) if result.stdout.strip() else None

    except subprocess.TimeoutExpired:
        print(f"  Warning: gh api timeout for {endpoint}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  Warning: gh api exception: {e}", file=sys.stderr)
        return None


# ============================================================================
# SQUAD REGISTRY
# ============================================================================


def load_squad_registry() -> List[Dict]:
    """Load squads from registry."""
    if not SQUAD_REGISTRY_PATH.exists():
        print(
            f"Error: Squad registry not found at {SQUAD_REGISTRY_PATH}", file=sys.stderr
        )
        return []

    with open(SQUAD_REGISTRY_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data.get("squads", [])


def get_unique_repos(squads: List[Dict]) -> List[Dict]:
    """Extract unique repos with their prefixes from squads."""
    repos = {}
    for squad in squads:
        squad_name = squad.get("name", "Unknown")
        for repo_config in squad.get("github_repos", []):
            repo = repo_config.get("repo")
            if repo and repo not in repos:
                repos[repo] = {"repo": repo, "prefixes": [], "squads": []}
            if repo:
                prefix = repo_config.get("pr_prefix", "")
                if prefix and prefix not in repos[repo]["prefixes"]:
                    repos[repo]["prefixes"].append(prefix)
                if squad_name not in repos[repo]["squads"]:
                    repos[repo]["squads"].append(squad_name)

    return list(repos.values())


# ============================================================================
# COMMIT EXTRACTION
# ============================================================================


def fetch_commits(
    repo: str, since_days: int = DEFAULT_LOOKBACK_DAYS, prefixes: List[str] = None
) -> List[Dict]:
    """
    Fetch commits from a repo.

    Args:
        repo: Full repo name (e.g., "acme-corp/web")
        since_days: How far back to look
        prefixes: Optional list of prefixes to filter by (e.g., ["MK-", "WB-"])

    Returns:
        List of commit dictionaries
    """
    since_date = (datetime.utcnow() - timedelta(days=since_days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    # GitHub API: list commits
    # We'll paginate to get more commits
    commits = []
    page = 1
    per_page = 100

    print(f"  Fetching commits from {repo}...", file=sys.stderr)

    while len(commits) < MAX_COMMITS_PER_REPO:
        endpoint = (
            f"repos/{repo}/commits?since={since_date}&per_page={per_page}&page={page}"
        )
        result = run_gh_api(endpoint)

        if not result or len(result) == 0:
            break

        for commit_data in result:
            commit = {
                "sha": commit_data.get("sha", "")[:8],
                "message": commit_data.get("commit", {}).get("message", ""),
                "author": commit_data.get("commit", {})
                .get("author", {})
                .get("name", "Unknown"),
                "author_email": commit_data.get("commit", {})
                .get("author", {})
                .get("email", ""),
                "date": commit_data.get("commit", {}).get("author", {}).get("date", ""),
                "url": commit_data.get("html_url", ""),
                "repo": repo,
            }

            # Filter by prefix if specified
            if prefixes:
                msg_lower = commit["message"].lower()
                title_line = commit["message"].split("\n")[0].lower()
                matched = False
                for prefix in prefixes:
                    if prefix.lower().rstrip("-") in title_line:
                        matched = True
                        commit["matched_prefix"] = prefix
                        break
                if not matched:
                    continue

            commits.append(commit)

        page += 1
        if len(result) < per_page:
            break

    print(f"    Found {len(commits)} commits", file=sys.stderr)
    return commits


def filter_by_topics(commits: List[Dict]) -> List[Dict]:
    """Filter commits by topic relevance."""
    filtered = []
    for commit in commits:
        msg_lower = commit["message"].lower()

        # Check topic filters
        for topic in TOPIC_FILTERS:
            if topic in msg_lower:
                commit["matched_topic"] = topic
                filtered.append(commit)
                break

    return filtered


def extract_all_commits(
    since_days: int = DEFAULT_LOOKBACK_DAYS,
) -> Dict[str, List[Dict]]:
    """
    Extract commits from all configured repos.

    Returns:
        Dict mapping repo names to their commits
    """
    squads = load_squad_registry()
    repos = get_unique_repos(squads)

    all_commits = {}

    for repo_config in repos:
        repo = repo_config["repo"]
        prefixes = repo_config["prefixes"]

        commits = fetch_commits(repo, since_days, prefixes)

        if commits:
            all_commits[repo] = commits

    return all_commits


# ============================================================================
# BATCHING
# ============================================================================


def create_batches(all_commits: Dict[str, List[Dict]]) -> List[Dict]:
    """
    Create batches from extracted commits.

    Returns:
        List of batch dictionaries
    """
    # Flatten all commits
    flat_commits = []
    for repo, commits in all_commits.items():
        flat_commits.extend(commits)

    # Sort by date (newest first)
    flat_commits.sort(key=lambda x: x.get("date", ""), reverse=True)

    # Create batches
    batches = []
    for i in range(0, len(flat_commits), BATCH_SIZE):
        batch_commits = flat_commits[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1

        batches.append(
            {
                "batch_id": f"github_{batch_num:04d}",
                "source": "github",
                "commit_count": len(batch_commits),
                "commits": batch_commits,
                "date_range": {
                    "oldest": (
                        batch_commits[-1].get("date", "") if batch_commits else ""
                    ),
                    "newest": batch_commits[0].get("date", "") if batch_commits else "",
                },
            }
        )

    return batches


def save_raw_data(all_commits: Dict[str, List[Dict]]):
    """Save raw extracted commits."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    for repo, commits in all_commits.items():
        safe_repo = repo.replace("/", "_")
        filepath = RAW_DIR / f"{safe_repo}_{timestamp}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "repo": repo,
                    "extracted_at": datetime.utcnow().isoformat() + "Z",
                    "commit_count": len(commits),
                    "commits": commits,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        print(f"  Saved: {filepath.name}", file=sys.stderr)


def save_batches(batches: List[Dict]):
    """Save processed batches."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    for batch in batches:
        filepath = PROCESSED_DIR / f"batch_{batch['batch_id']}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(batch, f, indent=2, ensure_ascii=False)

        print(f"  Saved: {filepath.name}", file=sys.stderr)


def save_state(all_commits: Dict[str, List[Dict]], batches: List[Dict]):
    """Save extraction state."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    state = {
        "extracted_at": datetime.utcnow().isoformat() + "Z",
        "repos": list(all_commits.keys()),
        "total_commits": sum(len(c) for c in all_commits.values()),
        "total_batches": len(batches),
        "commits_per_repo": {
            repo: len(commits) for repo, commits in all_commits.items()
        },
    }

    with open(OUTPUT_DIR / "extraction_state.json", "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# ============================================================================
# MAIN
# ============================================================================


def show_status():
    """Show current extraction status."""
    print("=" * 60, file=sys.stderr)
    print("GITHUB COMMIT EXTRACTION STATUS", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Check raw files
    raw_files = list(RAW_DIR.glob("*.json")) if RAW_DIR.exists() else []
    print(f"Raw files: {len(raw_files)}", file=sys.stderr)

    # Check batches
    batch_files = (
        list(PROCESSED_DIR.glob("batch_*.json")) if PROCESSED_DIR.exists() else []
    )
    print(f"Batch files: {len(batch_files)}", file=sys.stderr)

    # Check state
    state_file = OUTPUT_DIR / "extraction_state.json"
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        print(
            f"Last extraction: {state.get('extracted_at', 'Unknown')}", file=sys.stderr
        )
        print(f"Total commits: {state.get('total_commits', 0)}", file=sys.stderr)
        print(f"Total batches: {state.get('total_batches', 0)}", file=sys.stderr)

    print("=" * 60, file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Extract GitHub commits for analysis")
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help=f"Days to look back (default: {DEFAULT_LOOKBACK_DAYS})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be extracted without saving",
    )
    parser.add_argument(
        "--status", action="store_true", help="Show extraction status and exit"
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="Don't filter by topic (extract all commits matching prefixes)",
    )
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if not GH_PATH:
        print(
            "Error: GitHub CLI (gh) not found. Install from https://cli.github.com/",
            file=sys.stderr,
        )
        sys.exit(1)

    print("=" * 60, file=sys.stderr)
    print("GITHUB COMMIT EXTRACTOR", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Extract commits
    print(f"\nExtracting commits from last {args.days} days...", file=sys.stderr)
    all_commits = extract_all_commits(args.days)

    total_commits = sum(len(c) for c in all_commits.values())
    print(f"\nTotal commits extracted: {total_commits}", file=sys.stderr)

    if args.dry_run:
        print("\n[DRY RUN] Would create batches:", file=sys.stderr)
        batches = create_batches(all_commits)
        print(f"  Batches: {len(batches)}", file=sys.stderr)
        for batch in batches[:5]:
            print(
                f"    - {batch['batch_id']}: {batch['commit_count']} commits",
                file=sys.stderr,
            )
        if len(batches) > 5:
            print(f"    ... and {len(batches) - 5} more", file=sys.stderr)
        return

    # Save raw data
    print("\nSaving raw data...", file=sys.stderr)
    save_raw_data(all_commits)

    # Create and save batches
    print("\nCreating batches...", file=sys.stderr)
    batches = create_batches(all_commits)
    save_batches(batches)

    # Save state
    save_state(all_commits, batches)

    print("=" * 60, file=sys.stderr)
    print("EXTRACTION COMPLETE", file=sys.stderr)
    print(f"  Repos: {len(all_commits)}", file=sys.stderr)
    print(f"  Commits: {total_commits}", file=sys.stderr)
    print(f"  Batches: {len(batches)}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


if __name__ == "__main__":
    main()
