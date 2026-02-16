#!/usr/bin/env python3
"""
Jira Bulk Extractor

Extracts 6 months of Jira issues from configured projects for LLM analysis.
Follows the same pattern as github_commit_extractor.py and slack_bulk_extractor.py.

Usage:
    python3 jira_bulk_extractor.py [--days N] [--dry-run]
    python3 jira_bulk_extractor.py --status
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from atlassian import Jira

# Add common directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config_loader

# ============================================================================
# CONFIGURATION
# ============================================================================

ROOT_DIR = config_loader.get_root_path()
SQUAD_REGISTRY_PATH = ROOT_DIR / "squad_registry.yaml"
OUTPUT_DIR = ROOT_DIR / "user" / "brain" / "Inbox" / "Jira"
RAW_DIR = OUTPUT_DIR / "Raw"
PROCESSED_DIR = OUTPUT_DIR / "Processed"

DEFAULT_LOOKBACK_DAYS = 180  # 6 months like other sources
BATCH_SIZE = 25  # Issues per batch (smaller than docs due to richer content)
MAX_ISSUES_PER_PROJECT = 500
PARALLEL_WORKERS = 4

# Topic filters (same as other extractors)
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
    "shopify",
    "reactivation",
    "dashboard",
    "checkout",
]

# Issue types to extract (prioritize meaningful content)
ISSUE_TYPES = ["Epic", "Story", "Bug", "Task", "Spike", "Sub-task"]

# ============================================================================
# JIRA CLIENT
# ============================================================================


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


# ============================================================================
# SQUAD REGISTRY
# ============================================================================


def load_squad_registry(filter_tribe: Optional[str] = "Growth Division") -> List[Dict]:
    """Load squads from registry, optionally filtering by tribe."""
    if not SQUAD_REGISTRY_PATH.exists():
        print(
            f"Error: Squad registry not found at {SQUAD_REGISTRY_PATH}", file=sys.stderr
        )
        return []

    with open(SQUAD_REGISTRY_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    squads = data.get("squads", [])
    if filter_tribe:
        squads = [s for s in squads if s.get("tribe") == filter_tribe]

    return squads


def get_unique_projects(squads: List[Dict]) -> List[Dict]:
    """Extract unique Jira projects from squads."""
    projects = {}
    for squad in squads:
        project_key = squad.get("jira_project")
        if project_key and project_key not in projects:
            projects[project_key] = {
                "key": project_key,
                "squad_name": squad.get("name"),
                "tribe": squad.get("tribe"),
            }

    return list(projects.values())


# ============================================================================
# ISSUE EXTRACTION
# ============================================================================


def parse_issue(issue: Dict) -> Dict:
    """Extract relevant fields from a Jira issue."""
    fields = issue.get("fields", {})
    assignee = fields.get("assignee")
    reporter = fields.get("reporter")
    parent = fields.get("parent")

    # Extract comments (limited)
    comments = []
    comment_data = fields.get("comment", {})
    if isinstance(comment_data, dict):
        for comment in comment_data.get("comments", [])[:5]:  # Max 5 comments
            comments.append(
                {
                    "author": comment.get("author", {}).get("displayName", "Unknown"),
                    "body": comment.get("body", "")[:500],  # Truncate long comments
                    "created": comment.get("created", "")[:10],
                }
            )

    # Extract linked issues
    links = []
    for link in fields.get("issuelinks", []):
        if link.get("outwardIssue"):
            links.append(
                {
                    "type": link.get("type", {}).get("outward", "relates to"),
                    "key": link["outwardIssue"].get("key"),
                    "summary": link["outwardIssue"]
                    .get("fields", {})
                    .get("summary", "")[:100],
                }
            )
        elif link.get("inwardIssue"):
            links.append(
                {
                    "type": link.get("type", {}).get("inward", "relates to"),
                    "key": link["inwardIssue"].get("key"),
                    "summary": link["inwardIssue"]
                    .get("fields", {})
                    .get("summary", "")[:100],
                }
            )

    return {
        "key": issue.get("key"),
        "summary": fields.get("summary", ""),
        "description": (fields.get("description") or "")[
            :2000
        ],  # Truncate long descriptions
        "issue_type": fields.get("issuetype", {}).get("name", "Unknown"),
        "status": fields.get("status", {}).get("name", "Unknown"),
        "priority": (
            fields.get("priority", {}).get("name", "None")
            if fields.get("priority")
            else "None"
        ),
        "assignee": (
            assignee.get("displayName", "Unassigned") if assignee else "Unassigned"
        ),
        "reporter": reporter.get("displayName", "Unknown") if reporter else "Unknown",
        "created": fields.get("created", "")[:10],
        "updated": fields.get("updated", "")[:10],
        "resolved": (fields.get("resolutiondate") or "")[:10],
        "labels": fields.get("labels", []),
        "components": [c.get("name") for c in fields.get("components", [])],
        "parent_key": parent.get("key") if parent else None,
        "parent_summary": (
            parent.get("fields", {}).get("summary", "") if parent else None
        ),
        "story_points": fields.get("customfield_10016"),  # Common story points field
        "sprint": extract_sprint_name(
            fields.get("customfield_10020", [])
        ),  # Common sprint field
        "comments": comments,
        "links": links[:5],  # Limit links
    }


def extract_sprint_name(sprint_data: Any) -> Optional[str]:
    """Extract sprint name from sprint custom field."""
    if not sprint_data:
        return None
    if isinstance(sprint_data, list) and sprint_data:
        # Sprint data is usually a list of sprint objects
        latest_sprint = sprint_data[-1]
        if isinstance(latest_sprint, dict):
            return latest_sprint.get("name")
        elif isinstance(latest_sprint, str):
            # Sometimes it's a string like "com.atlassian.greenhopper.service..."
            if "name=" in latest_sprint:
                start = latest_sprint.find("name=") + 5
                end = latest_sprint.find(",", start)
                return latest_sprint[start:end] if end > start else None
    return None


def fetch_project_issues(
    project_key: str, jira: Jira, since_days: int = DEFAULT_LOOKBACK_DAYS
) -> List[Dict]:
    """
    Fetch issues from a Jira project.

    Args:
        project_key: Jira project key (e.g., "MK", "BB")
        jira: Jira client
        since_days: How far back to look

    Returns:
        List of issue dictionaries
    """
    since_date = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime(
        "%Y-%m-%d"
    )

    # JQL to fetch issues updated in the time range
    jql = f"""
        project = {project_key}
        AND updated >= "{since_date}"
        AND issuetype IN ({", ".join(f'"{t}"' for t in ISSUE_TYPES)})
        ORDER BY updated DESC
    """

    issues = []
    start_at = 0
    max_results = 100

    print(f"  Fetching issues from {project_key}...", file=sys.stderr)

    while len(issues) < MAX_ISSUES_PER_PROJECT:
        try:
            # Use enhanced_jql for Jira Cloud compatibility
            response = jira.jql(jql, start=start_at, limit=max_results, fields="*all")

            batch_issues = response.get("issues", [])
            if not batch_issues:
                break

            for issue in batch_issues:
                parsed = parse_issue(issue)
                issues.append(parsed)

            start_at += len(batch_issues)

            if len(batch_issues) < max_results:
                break

        except Exception as e:
            print(f"    Error fetching {project_key}: {e}", file=sys.stderr)
            break

    print(f"    Found {len(issues)} issues", file=sys.stderr)
    return issues


def fetch_all_projects_parallel(
    projects: List[Dict], since_days: int
) -> Dict[str, List[Dict]]:
    """Fetch issues from all projects in parallel."""
    all_issues = {}
    jira = get_jira_client()

    print(f"Fetching Jira issues for {len(projects)} projects in parallel...")

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        futures = {
            executor.submit(fetch_project_issues, proj["key"], jira, since_days): proj
            for proj in projects
        }

        for future in as_completed(futures):
            proj = futures[future]
            try:
                issues = future.result()
                all_issues[proj["key"]] = {
                    "project_key": proj["key"],
                    "squad_name": proj.get("squad_name"),
                    "issues": issues,
                }
                print(f"  ✓ {proj['key']}: {len(issues)} issues", file=sys.stderr)
            except Exception as e:
                print(f"  ✗ {proj['key']}: {e}", file=sys.stderr)
                all_issues[proj["key"]] = {
                    "project_key": proj["key"],
                    "error": str(e),
                    "issues": [],
                }

    return all_issues


# ============================================================================
# BATCHING
# ============================================================================


def create_batches(all_issues: Dict[str, Dict]) -> List[Dict]:
    """
    Create batches from extracted issues.

    Returns:
        List of batch dictionaries
    """
    # Flatten all issues
    flat_issues = []
    for project_key, project_data in all_issues.items():
        for issue in project_data.get("issues", []):
            issue["project_key"] = project_key
            issue["squad_name"] = project_data.get("squad_name")
            flat_issues.append(issue)

    # Sort by updated date (newest first)
    flat_issues.sort(key=lambda x: x.get("updated", ""), reverse=True)

    # Create batches
    batches = []
    for i in range(0, len(flat_issues), BATCH_SIZE):
        batch_issues = flat_issues[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1

        # Categorize issues in batch
        issue_types = {}
        for issue in batch_issues:
            it = issue.get("issue_type", "Other")
            issue_types[it] = issue_types.get(it, 0) + 1

        batches.append(
            {
                "batch_id": f"jira_{batch_num:04d}",
                "source": "jira",
                "issue_count": len(batch_issues),
                "issue_types": issue_types,
                "issues": batch_issues,
                "date_range": {
                    "oldest": (
                        batch_issues[-1].get("updated", "") if batch_issues else ""
                    ),
                    "newest": (
                        batch_issues[0].get("updated", "") if batch_issues else ""
                    ),
                },
            }
        )

    return batches


# ============================================================================
# SAVE FUNCTIONS
# ============================================================================


def save_raw_data(all_issues: Dict[str, Dict]):
    """Save raw extracted issues."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    for project_key, project_data in all_issues.items():
        filepath = RAW_DIR / f"{project_key}_{timestamp}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "project_key": project_key,
                    "squad_name": project_data.get("squad_name"),
                    "extracted_at": datetime.now(timezone.utc).isoformat() + "Z",
                    "issue_count": len(project_data.get("issues", [])),
                    "issues": project_data.get("issues", []),
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


def save_state(all_issues: Dict[str, Dict], batches: List[Dict]):
    """Save extraction state."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total_issues = sum(len(p.get("issues", [])) for p in all_issues.values())

    state = {
        "extracted_at": datetime.now(timezone.utc).isoformat() + "Z",
        "projects": list(all_issues.keys()),
        "total_issues": total_issues,
        "total_batches": len(batches),
        "issues_per_project": {
            k: len(v.get("issues", [])) for k, v in all_issues.items()
        },
    }

    with open(OUTPUT_DIR / "extraction_state.json", "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# ============================================================================
# STATUS
# ============================================================================


def show_status():
    """Show current extraction status."""
    print("=" * 60, file=sys.stderr)
    print("JIRA BULK EXTRACTION STATUS", file=sys.stderr)
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
        print(f"Total issues: {state.get('total_issues', 0)}", file=sys.stderr)
        print(f"Total batches: {state.get('total_batches', 0)}", file=sys.stderr)

        print("\nIssues per project:", file=sys.stderr)
        for proj, count in state.get("issues_per_project", {}).items():
            print(f"  {proj}: {count}", file=sys.stderr)

    # Check analyzed files
    analyzed_dir = OUTPUT_DIR / "Analyzed"
    analyzed_files = list(analyzed_dir.glob("*.json")) if analyzed_dir.exists() else []
    print(f"\nAnalyzed batches: {len(analyzed_files)}", file=sys.stderr)

    print("=" * 60, file=sys.stderr)


# ============================================================================
# MAIN
# ============================================================================


def main():
    parser = argparse.ArgumentParser(description="Extract Jira issues for analysis")
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
        "--project", type=str, help="Extract specific project only (e.g., MK, BB)"
    )
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    print("=" * 60, file=sys.stderr)
    print("JIRA BULK EXTRACTOR", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Load squads and get projects
    squads = load_squad_registry(filter_tribe="Growth Division")
    if not squads:
        print("No squads found in registry.", file=sys.stderr)
        sys.exit(1)

    projects = get_unique_projects(squads)
    print(f"Found {len(projects)} Jira projects", file=sys.stderr)

    # Filter to specific project if requested
    if args.project:
        projects = [p for p in projects if p["key"].upper() == args.project.upper()]
        if not projects:
            print(f"Project '{args.project}' not found in registry.", file=sys.stderr)
            sys.exit(1)

    # Extract issues
    print(f"\nExtracting issues from last {args.days} days...", file=sys.stderr)
    all_issues = fetch_all_projects_parallel(projects, args.days)

    total_issues = sum(len(p.get("issues", [])) for p in all_issues.values())
    print(f"\nTotal issues extracted: {total_issues}", file=sys.stderr)

    if args.dry_run:
        print("\n[DRY RUN] Would create batches:", file=sys.stderr)
        batches = create_batches(all_issues)
        print(f"  Batches: {len(batches)}", file=sys.stderr)
        for batch in batches[:5]:
            print(
                f"    - {batch['batch_id']}: {batch['issue_count']} issues ({batch['issue_types']})",
                file=sys.stderr,
            )
        if len(batches) > 5:
            print(f"    ... and {len(batches) - 5} more", file=sys.stderr)
        return

    # Save raw data
    print("\nSaving raw data...", file=sys.stderr)
    save_raw_data(all_issues)

    # Create and save batches
    print("\nCreating batches...", file=sys.stderr)
    batches = create_batches(all_issues)
    save_batches(batches)

    # Save state
    save_state(all_issues, batches)

    print("=" * 60, file=sys.stderr)
    print("EXTRACTION COMPLETE", file=sys.stderr)
    print(f"  Projects: {len(all_issues)}", file=sys.stderr)
    print(f"  Issues: {total_issues}", file=sys.stderr)
    print(f"  Batches: {len(batches)}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(
        "\nNext step: python3 batch_llm_analyzer.py --source jira --all",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
