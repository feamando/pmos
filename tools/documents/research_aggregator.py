#!/usr/bin/env python3
"""
Research Aggregator - Unified research across multiple sources.

Gathers context from web, GDrive, Brain, Jira, GitHub, Slack, and Confluence
for use in document generation and orthogonal challenge system.

Usage:
    python3 research_aggregator.py --topic "OTP architecture" --sources web,brain,jira
    python3 research_aggregator.py --topic "Push notifications" --all
    python3 research_aggregator.py --topic "Customer onboarding" --output context.json
"""

import argparse
import glob as glob_module
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add common directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    import config_loader
except ImportError:
    config_loader = None

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = Path(__file__).parent
REPO_ROOT = BASE_DIR.parent.parent
BRAIN_DIR = REPO_ROOT / "user" / "brain"
TOOLS_DIR = BASE_DIR

# Available research sources
SOURCES = ["web", "gdrive", "brain", "jira", "github", "slack", "confluence"]

# Source priority for deduplication
SOURCE_PRIORITY = {
    "web": 1,
    "gdrive": 2,
    "confluence": 3,
    "brain": 4,
    "jira": 5,
    "github": 6,
    "slack": 7,
}


# ============================================================================
# BRAIN RESEARCH
# ============================================================================


def search_brain(topic: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Search Brain knowledge base for relevant content.

    Args:
        topic: Search topic/query
        limit: Maximum results

    Returns:
        List of matching documents with content excerpts
    """
    results = []
    search_terms = topic.lower().split()

    # Search directories
    search_dirs = [
        BRAIN_DIR / "Projects",
        BRAIN_DIR / "Entities",
        BRAIN_DIR / "Reasoning" / "Decisions",
        BRAIN_DIR / "Reasoning" / "Hypotheses",
        BRAIN_DIR / "Reasoning" / "Evidence",
        BRAIN_DIR / "Inbox",
    ]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        for md_file in search_dir.rglob("*.md"):
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Simple relevance scoring
                content_lower = content.lower()
                filename_lower = md_file.stem.lower().replace("_", " ")

                score = 0
                for term in search_terms:
                    if term in filename_lower:
                        score += 3
                    score += content_lower.count(term)

                if score > 0:
                    # Extract excerpt around first match
                    excerpt = ""
                    for term in search_terms:
                        idx = content_lower.find(term)
                        if idx >= 0:
                            start = max(0, idx - 100)
                            end = min(len(content), idx + 200)
                            excerpt = content[start:end].strip()
                            break

                    results.append(
                        {
                            "source": "brain",
                            "type": search_dir.name.lower(),
                            "path": str(md_file.relative_to(REPO_ROOT)),
                            "title": md_file.stem.replace("_", " "),
                            "excerpt": excerpt[:500] if excerpt else content[:500],
                            "relevance_score": score,
                            "last_modified": datetime.fromtimestamp(
                                md_file.stat().st_mtime
                            ).isoformat(),
                        }
                    )

            except Exception as e:
                continue

    # Sort by relevance and limit
    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    return results[:limit]


# ============================================================================
# JIRA RESEARCH
# ============================================================================


def search_jira(topic: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search Jira for relevant issues and epics.

    Args:
        topic: Search topic/query
        limit: Maximum results

    Returns:
        List of relevant Jira issues
    """
    results = []

    # Check for jira_client.py
    jira_client = TOOLS_DIR / "jira_client.py"
    if not jira_client.exists():
        return results

    try:
        # Use jira_client to search
        cmd = [
            sys.executable,
            str(jira_client),
            "--search",
            topic,
            "--limit",
            str(limit),
            "--json",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0 and result.stdout:
            jira_results = json.loads(result.stdout)
            for issue in jira_results:
                results.append(
                    {
                        "source": "jira",
                        "type": issue.get("type", "issue"),
                        "key": issue.get("key"),
                        "title": issue.get("summary", ""),
                        "status": issue.get("status", ""),
                        "excerpt": (
                            issue.get("description", "")[:500]
                            if issue.get("description")
                            else ""
                        ),
                        "url": issue.get("url", ""),
                        "assignee": issue.get("assignee", ""),
                    }
                )

    except Exception as e:
        print(f"Jira search error: {e}", file=sys.stderr)

    return results


# ============================================================================
# GITHUB RESEARCH
# ============================================================================


def search_github(topic: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search GitHub for relevant PRs, issues, and code.

    Args:
        topic: Search topic/query
        limit: Maximum results

    Returns:
        List of relevant GitHub items
    """
    results = []

    # Check for github_client.py
    github_client = TOOLS_DIR / "github_client.py"
    if not github_client.exists():
        return results

    try:
        cmd = [
            sys.executable,
            str(github_client),
            "--search",
            topic,
            "--limit",
            str(limit),
            "--json",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0 and result.stdout:
            gh_results = json.loads(result.stdout)
            for item in gh_results:
                results.append(
                    {
                        "source": "github",
                        "type": item.get("type", "unknown"),
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "state": item.get("state", ""),
                        "excerpt": (
                            item.get("body", "")[:500] if item.get("body") else ""
                        ),
                        "repo": item.get("repo", ""),
                    }
                )

    except Exception as e:
        print(f"GitHub search error: {e}", file=sys.stderr)

    return results


# ============================================================================
# SLACK RESEARCH
# ============================================================================


def search_slack(topic: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search Slack messages for relevant discussions.

    Args:
        topic: Search topic/query
        limit: Maximum results

    Returns:
        List of relevant Slack messages
    """
    results = []

    # Check Brain/Inbox/Slack for cached messages
    slack_inbox = BRAIN_DIR / "Inbox" / "Slack"
    if slack_inbox.exists():
        search_terms = topic.lower().split()

        for md_file in slack_inbox.rglob("*.md"):
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()

                content_lower = content.lower()
                score = sum(content_lower.count(term) for term in search_terms)

                if score > 0:
                    results.append(
                        {
                            "source": "slack",
                            "type": "message",
                            "path": str(md_file.relative_to(REPO_ROOT)),
                            "title": md_file.stem,
                            "excerpt": content[:500],
                            "relevance_score": score,
                        }
                    )

            except Exception:
                continue

    results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return results[:limit]


# ============================================================================
# GDRIVE RESEARCH
# ============================================================================


def search_gdrive(topic: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search Google Drive for relevant documents.

    Args:
        topic: Search topic/query
        limit: Maximum results

    Returns:
        List of relevant GDrive documents
    """
    results = []

    # Check Brain/Inbox/GDocs for cached documents
    gdocs_inbox = BRAIN_DIR / "Inbox" / "GDocs"
    if gdocs_inbox.exists():
        search_terms = topic.lower().split()

        for md_file in gdocs_inbox.rglob("*.md"):
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()

                content_lower = content.lower()
                filename_lower = md_file.stem.lower()

                score = 0
                for term in search_terms:
                    if term in filename_lower:
                        score += 3
                    score += content_lower.count(term)

                if score > 0:
                    results.append(
                        {
                            "source": "gdrive",
                            "type": "document",
                            "path": str(md_file.relative_to(REPO_ROOT)),
                            "title": md_file.stem,
                            "excerpt": content[:500],
                            "relevance_score": score,
                        }
                    )

            except Exception:
                continue

    results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return results[:limit]


# ============================================================================
# CONFLUENCE RESEARCH
# ============================================================================


def search_confluence(topic: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search Confluence for relevant pages.

    Args:
        topic: Search topic/query
        limit: Maximum results

    Returns:
        List of relevant Confluence pages
    """
    results = []

    # First check Brain/Inbox/Confluence for cached pages
    confluence_inbox = BRAIN_DIR / "Inbox" / "Confluence"
    if confluence_inbox.exists():
        search_terms = topic.lower().split()

        for md_file in confluence_inbox.rglob("*.md"):
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()

                content_lower = content.lower()
                score = sum(content_lower.count(term) for term in search_terms)

                if score > 0:
                    results.append(
                        {
                            "source": "confluence",
                            "type": "page",
                            "path": str(md_file.relative_to(REPO_ROOT)),
                            "title": md_file.stem,
                            "excerpt": content[:500],
                            "relevance_score": score,
                            "cached": True,
                        }
                    )

            except Exception:
                continue

    # Try live Confluence search if client available
    confluence_client = TOOLS_DIR / "confluence_brain_sync.py"
    if confluence_client.exists() and len(results) < limit:
        try:
            cmd = [
                sys.executable,
                str(confluence_client),
                "--search",
                topic,
                "--limit",
                str(limit - len(results)),
                "--json",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and result.stdout:
                conf_results = json.loads(result.stdout)
                for page in conf_results:
                    results.append(
                        {
                            "source": "confluence",
                            "type": "page",
                            "id": page.get("id"),
                            "title": page.get("title", ""),
                            "space": page.get("space_key", ""),
                            "url": page.get("url", ""),
                            "excerpt": "",
                            "cached": False,
                        }
                    )

        except Exception as e:
            print(f"Confluence search error: {e}", file=sys.stderr)

    results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return results[:limit]


# ============================================================================
# WEB RESEARCH
# ============================================================================


def search_web(topic: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Perform web search for topic.

    Note: This is a placeholder. Actual web search requires
    integration with Gemini Deep Research or similar.

    Args:
        topic: Search topic/query
        limit: Maximum results

    Returns:
        List of web search results (requires model invocation)
    """
    # Web search typically requires model invocation
    # Return placeholder indicating web search should be done
    return [
        {
            "source": "web",
            "type": "search_request",
            "query": topic,
            "note": "Web search requires model invocation (Gemini Deep Research recommended)",
            "limit": limit,
        }
    ]


# ============================================================================
# AGGREGATED RESEARCH
# ============================================================================


def gather_context(
    topic: str, sources: Optional[List[str]] = None, limit_per_source: int = 10
) -> Dict[str, Any]:
    """
    Gather research context from multiple sources.

    Args:
        topic: Research topic/query
        sources: List of sources to search (default: all)
        limit_per_source: Maximum results per source

    Returns:
        Dict with 'topic', 'timestamp', 'results' (by source), 'summary'
    """
    if sources is None:
        sources = SOURCES

    # Validate sources
    sources = [s.lower() for s in sources if s.lower() in SOURCES]

    context = {
        "topic": topic,
        "timestamp": datetime.now().isoformat(),
        "sources_searched": sources,
        "results": {},
        "total_results": 0,
    }

    # Search each source
    source_functions = {
        "brain": search_brain,
        "jira": search_jira,
        "github": search_github,
        "slack": search_slack,
        "gdrive": search_gdrive,
        "confluence": search_confluence,
        "web": search_web,
    }

    for source in sources:
        if source in source_functions:
            try:
                results = source_functions[source](topic, limit_per_source)
                context["results"][source] = results
                context["total_results"] += len(results)
            except Exception as e:
                context["results"][source] = [{"error": str(e), "source": source}]

    # Generate summary
    context["summary"] = _generate_summary(context)

    return context


def _generate_summary(context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate summary of research results."""
    summary = {
        "topic": context["topic"],
        "sources_with_results": [],
        "top_items": [],
        "total_results": context["total_results"],
    }

    all_items = []
    for source, results in context.get("results", {}).items():
        if results and not any(r.get("error") for r in results):
            summary["sources_with_results"].append(source)
            for item in results:
                if not item.get("error"):
                    item["_source"] = source
                    all_items.append(item)

    # Sort all items by relevance score
    all_items.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    # Top 5 items across all sources
    summary["top_items"] = [
        {
            "source": item.get("_source"),
            "title": item.get("title", item.get("key", "Unknown")),
            "type": item.get("type", "unknown"),
            "score": item.get("relevance_score", 0),
        }
        for item in all_items[:5]
    ]

    return summary


def format_for_prompt(context: Dict[str, Any], max_length: int = 10000) -> str:
    """
    Format research context for inclusion in a prompt.

    Args:
        context: Research context from gather_context
        max_length: Maximum output length

    Returns:
        Formatted string suitable for prompt injection
    """
    parts = [
        f"# Research Context: {context['topic']}",
        f"*Gathered: {context['timestamp']}*",
        f"*Sources: {', '.join(context['sources_searched'])}*",
        "",
    ]

    current_length = sum(len(p) for p in parts)

    for source, results in context.get("results", {}).items():
        if not results or any(r.get("error") for r in results):
            continue

        section = [f"## {source.title()} Results", ""]

        for item in results[:5]:  # Top 5 per source
            if item.get("error"):
                continue

            title = item.get("title", item.get("key", "Unknown"))
            item_type = item.get("type", "")
            excerpt = item.get("excerpt", "")[:300]

            entry = f"### {title}"
            if item_type:
                entry += f" ({item_type})"
            entry += f"\n{excerpt}\n"

            if current_length + len(entry) > max_length:
                break

            section.append(entry)
            current_length += len(entry)

        if len(section) > 2:  # Has content beyond header
            parts.extend(section)

        if current_length > max_length:
            break

    return "\n".join(parts)


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Research Aggregator - Unified research across multiple sources"
    )
    parser.add_argument("--topic", type=str, required=True, help="Research topic/query")
    parser.add_argument(
        "--sources",
        type=str,
        help=f"Comma-separated sources to search (available: {', '.join(SOURCES)})",
    )
    parser.add_argument(
        "--all", action="store_true", help="Search all available sources"
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="Maximum results per source (default: 10)"
    )
    parser.add_argument("--output", type=str, help="Output file path (JSON)")
    parser.add_argument(
        "--format",
        choices=["json", "prompt", "summary"],
        default="json",
        help="Output format (default: json)",
    )

    args = parser.parse_args()

    # Determine sources
    if args.all:
        sources = SOURCES
    elif args.sources:
        sources = [s.strip() for s in args.sources.split(",")]
    else:
        # Default to internal sources only
        sources = ["brain", "jira", "github", "slack", "gdrive"]

    # Gather context
    context = gather_context(args.topic, sources, args.limit)

    # Format output
    if args.format == "prompt":
        output = format_for_prompt(context)
    elif args.format == "summary":
        output = json.dumps(context["summary"], indent=2)
    else:
        output = json.dumps(context, indent=2)

    # Output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Research context saved to: {args.output}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
