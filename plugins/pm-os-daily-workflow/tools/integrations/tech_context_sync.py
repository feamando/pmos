#!/usr/bin/env python3
"""
Technical Context Sync Tool (v5.0)

Analyzes GitHub repositories and syncs technical standards to populate
the Technical Brain for better PRD/ADR/RFC generation. All repo names
and spec paths come from config — zero hardcoded values.

Usage:
    python3 tech_context_sync.py --analyze owner/repo
    python3 tech_context_sync.py --sync-spec-machine
    python3 tech_context_sync.py --list-repos
    python3 tech_context_sync.py --all
"""

import argparse
import base64
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
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


def _get_configured_repos() -> List[Dict[str, str]]:
    """Get priority repos for analysis from config."""
    config = get_config() if get_config else None
    if config:
        repos = config.get("integrations.github.analysis_repos")
        if repos and isinstance(repos, list):
            return repos
        # Fallback: build from simple repos list
        repo_names = config.get_list("integrations.github.repos")
        if repo_names:
            return [{"name": r, "type": "unknown", "description": ""} for r in repo_names]
    return []


def _get_spec_repo() -> str:
    """Get spec-machine repo from config."""
    config = get_config() if get_config else None
    if config:
        return config.get("integrations.github.spec_repo", "")
    return ""


def _get_spec_branch() -> str:
    """Get spec-machine branch from config."""
    config = get_config() if get_config else None
    if config:
        return config.get("integrations.github.spec_branch", "main")
    return "main"


def _get_spec_standards_path() -> str:
    """Get spec-machine standards path from config."""
    config = get_config() if get_config else None
    if config:
        return config.get("integrations.github.spec_standards_path", "")
    return ""


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
            return result.stdout.strip()
        else:
            return json.loads(result.stdout) if result.stdout.strip() else None

    except subprocess.TimeoutExpired:
        logger.warning("gh api timeout for %s", endpoint)
        return None
    except Exception as e:
        logger.warning("gh api exception for %s: %s", endpoint, e)
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
            logger.warning("Failed to decode %s: %s", path, e)
    return None


def detect_tech_stack(repo: str) -> Dict[str, Any]:
    """Analyze repository and detect tech stack."""
    logger.info("  Detecting tech stack for %s...", repo)

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

            stack["language"] = "TypeScript" if "typescript" in deps else "JavaScript"

            if "zustand" in deps:
                stack["state_management"] = "Zustand"
            elif "@reduxjs/toolkit" in deps or "redux" in deps:
                stack["state_management"] = "Redux"
            elif "mobx" in deps:
                stack["state_management"] = "MobX"

            if "tailwindcss" in deps:
                stack["styling"] = "Tailwind CSS"
            elif "styled-components" in deps:
                stack["styling"] = "Styled Components"
            elif "@emotion/react" in deps:
                stack["styling"] = "Emotion"
            else:
                stack["styling"] = "CSS Modules"

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

            key_deps = [
                "@apollo/client", "graphql", "zod", "react-hook-form",
                "date-fns", "statsig-react", "sentry",
            ]
            stack["dependencies"] = [d for d in key_deps if d in deps]

        except json.JSONDecodeError:
            pass

    # Check for Go projects
    go_mod = fetch_file_content(repo, "go.mod")
    if go_mod:
        stack["language"] = "Go"
        stack["framework"] = "Standard Library" if "gin" not in go_mod.lower() else "Gin"

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
    logger.info("  Fetching structure for %s...", repo)

    endpoint = f"repos/{repo}/git/trees/main?recursive=1"
    data = run_gh_api(endpoint)

    if not data or "tree" not in data:
        endpoint = f"repos/{repo}/git/trees/master?recursive=1"
        data = run_gh_api(endpoint)

    if not data or "tree" not in data:
        return []

    dirs = set()
    for item in data["tree"]:
        if item["type"] == "tree":
            top_level = item["path"].split("/")[0]
            dirs.add(top_level)

    return sorted(list(dirs))


def analyze_repo(repo: str) -> Dict[str, Any]:
    """Full analysis of a repository."""
    logger.info("Analyzing %s...", repo)

    repo_data = run_gh_api(f"repos/{repo}")
    if not repo_data:
        logger.error("Could not fetch repo data for %s", repo)
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

    readme = fetch_file_content(repo, "README.md")
    if readme:
        result["readme_summary"] = readme[:500].strip()

    return result


def write_repo_brain_file(analysis: Dict[str, Any]) -> Path:
    """Write analysis results to Technical Brain."""
    repo_name = analysis.get("name", "unknown")
    safe_name = repo_name.replace("/", "_")

    brain_dir = _resolve_brain_dir()
    repositories_dir = brain_dir / "Technical" / "repositories"
    repositories_dir.mkdir(parents=True, exist_ok=True)
    filepath = repositories_dir / f"{safe_name}.md"

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
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info("  Written: %s", filepath)
    return filepath


def sync_spec_machine_standards() -> Dict[str, List[str]]:
    """Sync standards from the spec-machine repository."""
    spec_repo = _get_spec_repo()
    spec_branch = _get_spec_branch()
    standards_path = _get_spec_standards_path()

    if not spec_repo:
        logger.error("integrations.github.spec_repo not configured")
        return {}

    if not standards_path:
        logger.error("integrations.github.spec_standards_path not configured")
        return {}

    logger.info("Syncing standards from %s (%s branch)...", spec_repo, spec_branch)

    endpoint = f"repos/{spec_repo}/git/trees/{spec_branch}?recursive=1"
    data = run_gh_api(endpoint)

    if not data or "tree" not in data:
        logger.error("Could not fetch spec-machine tree")
        return {}

    standards_files = []
    for item in data["tree"]:
        if item["type"] == "blob" and standards_path in item["path"]:
            if item["path"].endswith(".md"):
                standards_files.append(item["path"])

    logger.info("  Found %d standard files", len(standards_files))

    # Group by category
    categories = {}
    for filepath in standards_files:
        parts = filepath.replace(standards_path + "/", "").split("/")
        if len(parts) >= 2:
            category = parts[0]
            if category not in categories:
                categories[category] = []
            categories[category].append(filepath)

    # Fetch and summarize each category
    synced = {}
    for category, files in categories.items():
        logger.info("  Processing category: %s", category)
        synced[category] = []

        summaries = []
        for filepath in files[:5]:
            content = fetch_file_content(spec_repo, filepath, ref=spec_branch)
            if content:
                filename = Path(filepath).stem
                summary = content[:300].replace("\n", " ").strip()
                summaries.append(f"### {filename}\n\n{summary}...")
                synced[category].append(filename)

        if summaries:
            _write_pattern_file(category, summaries, spec_repo, standards_path)

    return synced


def _write_pattern_file(
    category: str, summaries: List[str], spec_repo: str, standards_path: str
) -> Path:
    """Write pattern summary file."""
    brain_dir = _resolve_brain_dir()
    patterns_dir = brain_dir / "Technical" / "patterns"
    patterns_dir.mkdir(parents=True, exist_ok=True)
    filepath = patterns_dir / f"{category}.md"

    content = f"""# {category.replace('-', ' ').title()} Patterns

*Source: {spec_repo}/{standards_path}/{category}/*

{chr(10).join(summaries)}

---

*Synced from spec-machine. Run `/sync-tech-context` to update.*
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info("    Written: %s", filepath)
    return filepath


def run_sync(
    analyze_repo_name: Optional[str] = None,
    sync_spec: bool = False,
    analyze_all: bool = False,
) -> Dict[str, Any]:
    """Run tech context sync programmatically."""
    if not GH_PATH:
        return {"status": "error", "message": "GitHub CLI (gh) not found"}

    results = {"status": "success", "repos_analyzed": [], "spec_categories": {}}

    if analyze_repo_name:
        analysis = analyze_repo(analyze_repo_name)
        if analysis:
            write_repo_brain_file(analysis)
            results["repos_analyzed"].append(analyze_repo_name)

    if analyze_all:
        repos = _get_configured_repos()
        for repo in repos:
            repo_name = repo.get("name", "") if isinstance(repo, dict) else repo
            if repo_name:
                analysis = analyze_repo(repo_name)
                if analysis:
                    write_repo_brain_file(analysis)
                    results["repos_analyzed"].append(repo_name)

    if sync_spec:
        synced = sync_spec_machine_standards()
        results["spec_categories"] = {
            cat: len(files) for cat, files in synced.items()
        }

    return results


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Technical Context Sync Tool")
    parser.add_argument("--analyze", metavar="REPO", help="Analyze a GitHub repository")
    parser.add_argument(
        "--sync-spec-machine", action="store_true",
        help="Sync standards from spec-machine",
    )
    parser.add_argument("--list-repos", action="store_true", help="List configured repos for analysis")
    parser.add_argument("--all", action="store_true", help="Analyze all configured repos")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if not GH_PATH:
        logger.error("GitHub CLI (gh) not found. Install from https://cli.github.com/")
        sys.exit(1)

    if args.list_repos:
        repos = _get_configured_repos()
        if repos:
            print("Configured Repositories for Analysis:")
            print("-" * 60)
            for repo in repos:
                if isinstance(repo, dict):
                    print(
                        f"  {repo.get('name', '?'):<35} "
                        f"({repo.get('type', '?')}) - {repo.get('description', '')}"
                    )
                else:
                    print(f"  {repo}")
        else:
            print("No repos configured. Set integrations.github.repos in config.yaml")
        return

    result = run_sync(
        analyze_repo_name=args.analyze,
        sync_spec=args.sync_spec_machine,
        analyze_all=args.all,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result.get("repos_analyzed"):
            print(f"Analyzed {len(result['repos_analyzed'])} repos: {', '.join(result['repos_analyzed'])}")
        if result.get("spec_categories"):
            print(f"Synced {len(result['spec_categories'])} spec categories")
            for cat, count in result["spec_categories"].items():
                print(f"  {cat}: {count} files")
        if not result.get("repos_analyzed") and not result.get("spec_categories"):
            parser.print_help()


if __name__ == "__main__":
    main()
