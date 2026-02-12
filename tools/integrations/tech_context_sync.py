#!/usr/bin/env python3
"""
Technical Context Sync Tool

Analyzes GitHub repositories and syncs technical standards from spec-machine
to populate the Technical Brain for better PRD/ADR/RFC generation.

Usage:
    python3 tech_context_sync.py --analyze acme-corp/web
    python3 tech_context_sync.py --sync-spec-machine
    python3 tech_context_sync.py --list-repos
"""

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add common directory to path for config_loader
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    import config_loader

    ROOT_DIR = config_loader.get_root_path()
except ImportError:
    ROOT_DIR = Path(__file__).parent.parent.parent

# Constants
TECHNICAL_BRAIN_DIR = ROOT_DIR / "user" / "brain" / "Technical"
REPOSITORIES_DIR = TECHNICAL_BRAIN_DIR / "repositories"
PATTERNS_DIR = TECHNICAL_BRAIN_DIR / "patterns"
COMPONENTS_DIR = TECHNICAL_BRAIN_DIR / "components"

SPEC_MACHINE_REPO = "acme-corp/spec-machine"
SPEC_MACHINE_BRANCH = "main"  # Standards are on main branch, not master
SPEC_MACHINE_STANDARDS_PATH = "profiles/engagement-dau/standards"

# Priority repos to analyze
PRIORITY_REPOS = [
    {
        "name": "acme-corp/web",
        "type": "frontend",
        "description": "Consumer web frontend",
    },
    {
        "name": "acme-corp/whitelabel-mobile",
        "type": "mobile",
        "description": "React Native mobile apps",
    },
    {
        "name": "acme-corp/engagement-dau",
        "type": "backend",
        "description": "Engagement services",
    },
    {
        "name": "acme-corp/consumer-bff",
        "type": "bff",
        "description": "Consumer BFF layer",
    },
]


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
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", timeout=30)
        if result.returncode != 0:
            if "404" not in result.stderr and "Not Found" not in result.stderr:
                print(f"  Warning: gh api error for {endpoint}: {result.stderr[:100]}")
            return None

        if jq_filter:
            return result.stdout.strip()
        else:
            return json.loads(result.stdout) if result.stdout.strip() else None

    except subprocess.TimeoutExpired:
        print(f"  Warning: gh api timeout for {endpoint}")
        return None
    except Exception as e:
        print(f"  Warning: gh api exception for {endpoint}: {e}")
        return None


def fetch_file_content(
    repo: str, path: str, ref: Optional[str] = None
) -> Optional[str]:
    """Fetch file content from a GitHub repo."""
    endpoint = f"repos/{repo}/contents/{path}"
    if ref:
        endpoint += f"?ref={ref}"
    data = run_gh_api(endpoint)
    if data and "content" in data:
        try:
            return base64.b64decode(data["content"]).decode("utf-8")
        except Exception as e:
            print(f"  Warning: Failed to decode {path}: {e}")
    return None


def detect_tech_stack(repo: str) -> Dict[str, Any]:
    """Analyze repository and detect tech stack."""
    print(f"  Detecting tech stack for {repo}...")

    stack = {
        "framework": None,
        "language": None,
        "state_management": None,
        "styling": None,
        "testing": [],
        "dependencies": [],
    }

    # Check package.json for JS/TS projects
    pkg_content = fetch_file_content(repo, "package.json")
    if pkg_content:
        try:
            pkg = json.loads(pkg_content)
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

            # Framework detection
            if "next" in deps:
                stack["framework"] = "Next.js"
            elif "react-native" in deps:
                stack["framework"] = "React Native"
            elif "react" in deps:
                stack["framework"] = "React"
            elif "express" in deps:
                stack["framework"] = "Express"
            elif "@nestjs/core" in deps:
                stack["framework"] = "NestJS"

            # Language
            if "typescript" in deps:
                stack["language"] = "TypeScript"
            else:
                stack["language"] = "JavaScript"

            # State management
            if "zustand" in deps:
                stack["state_management"] = "Zustand"
            elif "@reduxjs/toolkit" in deps or "redux" in deps:
                stack["state_management"] = "Redux"
            elif "mobx" in deps:
                stack["state_management"] = "MobX"

            # Styling
            if "tailwindcss" in deps:
                stack["styling"] = "Tailwind CSS"
            elif "styled-components" in deps:
                stack["styling"] = "Styled Components"
            elif "@emotion/react" in deps:
                stack["styling"] = "Emotion"
            else:
                stack["styling"] = "CSS Modules"

            # Testing
            if "jest" in deps:
                stack["testing"].append("Jest")
            if "@testing-library/react" in deps:
                stack["testing"].append("React Testing Library")
            if "playwright" in deps or "@playwright/test" in deps:
                stack["testing"].append("Playwright")
            if "cypress" in deps:
                stack["testing"].append("Cypress")
            if "detox" in deps:
                stack["testing"].append("Detox")

            # Key dependencies
            key_deps = [
                "@apollo/client",
                "graphql",
                "zod",
                "react-hook-form",
                "date-fns",
                "statsig-react",
                "sentry",
            ]
            stack["dependencies"] = [d for d in key_deps if d in deps]

        except json.JSONDecodeError:
            pass

    # Check for Go projects
    go_mod = fetch_file_content(repo, "go.mod")
    if go_mod:
        stack["language"] = "Go"
        stack["framework"] = (
            "Standard Library" if "gin" not in go_mod.lower() else "Gin"
        )

    # Check for Python projects
    pyproject = fetch_file_content(repo, "pyproject.toml")
    if pyproject:
        stack["language"] = "Python"
        if "fastapi" in pyproject.lower():
            stack["framework"] = "FastAPI"
        elif "django" in pyproject.lower():
            stack["framework"] = "Django"
        elif "flask" in pyproject.lower():
            stack["framework"] = "Flask"

    return stack


def get_repo_structure(repo: str) -> List[str]:
    """Get key directories in a repository."""
    print(f"  Fetching structure for {repo}...")

    endpoint = f"repos/{repo}/git/trees/main?recursive=1"
    data = run_gh_api(endpoint)

    if not data or "tree" not in data:
        # Try master branch
        endpoint = f"repos/{repo}/git/trees/master?recursive=1"
        data = run_gh_api(endpoint)

    if not data or "tree" not in data:
        return []

    # Extract top-level directories
    dirs = set()
    for item in data["tree"]:
        if item["type"] == "tree":
            path = item["path"]
            # Get first-level directory
            top_level = path.split("/")[0]
            dirs.add(top_level)

    return sorted(list(dirs))


def analyze_repo(repo: str) -> Dict[str, Any]:
    """Full analysis of a repository."""
    print(f"\nAnalyzing {repo}...")

    # Get repo metadata
    repo_data = run_gh_api(f"repos/{repo}")
    if not repo_data:
        print(f"  Error: Could not fetch repo data for {repo}")
        return {}

    result = {
        "name": repo,
        "description": repo_data.get("description", ""),
        "default_branch": repo_data.get("default_branch", "main"),
        "language": repo_data.get("language", "Unknown"),
        "updated_at": repo_data.get("updated_at", ""),
        "tech_stack": detect_tech_stack(repo),
        "key_directories": get_repo_structure(repo),
        "analyzed_at": datetime.now().isoformat(),
    }

    # Get README
    readme = fetch_file_content(repo, "README.md")
    if readme:
        # Extract first 500 chars as summary
        result["readme_summary"] = readme[:500].strip()

    return result


def write_repo_brain_file(analysis: Dict[str, Any]) -> Path:
    """Write analysis results to Technical Brain."""
    repo_name = analysis.get("name", "unknown")
    safe_name = repo_name.replace("/", "_")

    REPOSITORIES_DIR.mkdir(parents=True, exist_ok=True)
    filepath = REPOSITORIES_DIR / f"{safe_name}.md"

    stack = analysis.get("tech_stack", {})

    content = f"""# {repo_name}

## Overview

- **Description:** {analysis.get('description', 'N/A')}
- **Primary Language:** {analysis.get('language', 'Unknown')}
- **Last Updated:** {analysis.get('updated_at', 'Unknown')[:10]}
- **Analyzed:** {analysis.get('analyzed_at', '')[:10]}

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | {stack.get('framework', 'N/A')} |
| Language | {stack.get('language', 'N/A')} |
| State Management | {stack.get('state_management', 'N/A')} |
| Styling | {stack.get('styling', 'N/A')} |
| Testing | {', '.join(stack.get('testing', [])) or 'N/A'} |

### Key Dependencies

{chr(10).join(f'- {dep}' for dep in stack.get('dependencies', [])) or '- None detected'}

## Key Directories

```
{chr(10).join(analysis.get('key_directories', [])[:15])}
```

## README Summary

{analysis.get('readme_summary', 'No README found.')[:400]}...

---

*Auto-generated by tech_context_sync.py*
*Run `/analyze-codebase {repo_name}` to refresh*
"""

    with open(filepath, "w") as f:
        f.write(content)

    print(f"  Written: {filepath}")
    return filepath


def sync_spec_machine_standards() -> Dict[str, List[str]]:
    """Sync standards from spec-machine repository."""
    print(
        f"\nSyncing standards from {SPEC_MACHINE_REPO} ({SPEC_MACHINE_BRANCH} branch)..."
    )

    # Get list of standard files from the main branch (where profiles live)
    endpoint = f"repos/{SPEC_MACHINE_REPO}/git/trees/{SPEC_MACHINE_BRANCH}?recursive=1"
    data = run_gh_api(endpoint)

    if not data or "tree" not in data:
        print("  Error: Could not fetch spec-machine tree")
        return {}

    standards_files = []
    for item in data["tree"]:
        if item["type"] == "blob" and SPEC_MACHINE_STANDARDS_PATH in item["path"]:
            if item["path"].endswith(".md"):
                standards_files.append(item["path"])

    print(f"  Found {len(standards_files)} standard files")

    # Group by category
    categories = {}
    for filepath in standards_files:
        # Extract category from path
        parts = filepath.replace(SPEC_MACHINE_STANDARDS_PATH + "/", "").split("/")
        if len(parts) >= 2:
            category = parts[0]
            if category not in categories:
                categories[category] = []
            categories[category].append(filepath)

    # Fetch and summarize each category
    synced = {}
    for category, files in categories.items():
        print(f"  Processing category: {category}")
        synced[category] = []

        summaries = []
        for filepath in files[:5]:  # Limit to 5 files per category
            content = fetch_file_content(
                SPEC_MACHINE_REPO, filepath, ref=SPEC_MACHINE_BRANCH
            )
            if content:
                filename = Path(filepath).stem
                # Extract first 300 chars as summary
                summary = content[:300].replace("\n", " ").strip()
                summaries.append(f"### {filename}\n\n{summary}...")
                synced[category].append(filename)

        # Write category summary to patterns
        if summaries:
            write_pattern_file(category, summaries)

    return synced


def write_pattern_file(category: str, summaries: List[str]) -> Path:
    """Write pattern summary file."""
    PATTERNS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = PATTERNS_DIR / f"{category}.md"

    content = f"""# {category.replace('-', ' ').title()} Patterns

*Source: acme-corp/spec-machine/profiles/engagement-dau/standards/{category}/*

{chr(10).join(summaries)}

---

*Synced from spec-machine. Run `/sync-tech-context` to update.*
"""

    with open(filepath, "w") as f:
        f.write(content)

    print(f"    Written: {filepath}")
    return filepath


def list_repos():
    """List priority repos for analysis."""
    print("\nPriority Repositories for Analysis:")
    print("-" * 60)
    for repo in PRIORITY_REPOS:
        print(f"  {repo['name']:<35} ({repo['type']}) - {repo['description']}")
    print("\nUse: python3 tech_context_sync.py --analyze <repo>")


def main():
    parser = argparse.ArgumentParser(description="Technical Context Sync Tool")
    parser.add_argument("--analyze", metavar="REPO", help="Analyze a GitHub repository")
    parser.add_argument(
        "--sync-spec-machine",
        action="store_true",
        help="Sync standards from spec-machine",
    )
    parser.add_argument(
        "--list-repos", action="store_true", help="List priority repos for analysis"
    )
    parser.add_argument("--all", action="store_true", help="Analyze all priority repos")

    args = parser.parse_args()

    if not GH_PATH:
        print("Error: GitHub CLI (gh) not found.")
        print("Install from: https://cli.github.com/")
        sys.exit(1)

    if args.list_repos:
        list_repos()
        return

    if args.analyze:
        analysis = analyze_repo(args.analyze)
        if analysis:
            write_repo_brain_file(analysis)
            print(f"\nDone. Technical Brain updated for {args.analyze}")
        return

    if args.all:
        for repo in PRIORITY_REPOS:
            analysis = analyze_repo(repo["name"])
            if analysis:
                write_repo_brain_file(analysis)
        print(f"\nDone. Analyzed {len(PRIORITY_REPOS)} repositories.")
        return

    if args.sync_spec_machine:
        synced = sync_spec_machine_standards()
        if synced:
            print(f"\nSynced {len(synced)} categories:")
            for cat, files in synced.items():
                print(f"  {cat}: {len(files)} files")
        return

    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()
