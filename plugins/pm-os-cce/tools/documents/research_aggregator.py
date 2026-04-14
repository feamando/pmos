"""
PM-OS CCE ResearchAggregator (v5.0)

Unified research across multiple sources: Brain, Jira, GitHub, Slack,
GDrive, Confluence, and web. Gathers context for document generation
and orthogonal challenge system.

Usage:
    from pm_os_cce.tools.documents.research_aggregator import ResearchAggregator
"""

import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from core.config_loader import get_config

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

try:
    from pm_os_base.tools.core.connector_bridge import get_connector_client
except ImportError:
    try:
        from core.connector_bridge import get_connector_client
    except ImportError:
        get_connector_client = None

# Brain plugin is OPTIONAL
try:
    from pm_os_brain.tools.brain_core.brain_loader import BrainLoader
    HAS_BRAIN = True
except ImportError:
    HAS_BRAIN = False

logger = logging.getLogger(__name__)

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


def _resolve_brain_dir() -> Path:
    """Resolve the Brain directory via path resolver."""
    try:
        paths = get_paths()
        return paths.user / "brain"
    except Exception:
        return Path.home() / "pm-os" / "user" / "brain"


def _resolve_root_dir() -> Path:
    """Resolve the root directory via path resolver."""
    try:
        paths = get_paths()
        return paths.root
    except Exception:
        return Path.home() / "pm-os"


class ResearchAggregator:
    """
    Unified research across multiple sources.

    Searches Brain, Jira, GitHub, Slack, GDrive, Confluence, and web
    to gather research context for document generation.
    """

    def __init__(
        self,
        brain_dir: Optional[Path] = None,
        root_dir: Optional[Path] = None,
    ):
        """
        Initialize the research aggregator.

        Args:
            brain_dir: Path to Brain directory. If None, resolved via config.
            root_dir: Path to PM-OS root. If None, resolved via config.
        """
        self._brain_dir = brain_dir or _resolve_brain_dir()
        self._root_dir = root_dir or _resolve_root_dir()

    def search_brain(self, topic: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search Brain knowledge base for relevant content."""
        results = []
        search_terms = topic.lower().split()

        search_dirs = [
            self._brain_dir / "Projects",
            self._brain_dir / "Entities",
            self._brain_dir / "Reasoning" / "Decisions",
            self._brain_dir / "Reasoning" / "Hypotheses",
            self._brain_dir / "Reasoning" / "Evidence",
            self._brain_dir / "Inbox",
        ]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            for md_file in search_dir.rglob("*.md"):
                try:
                    content = md_file.read_text(encoding="utf-8")
                    content_lower = content.lower()
                    filename_lower = md_file.stem.lower().replace("_", " ")

                    score = 0
                    for term in search_terms:
                        if term in filename_lower:
                            score += 3
                        score += content_lower.count(term)

                    if score > 0:
                        excerpt = ""
                        for term in search_terms:
                            idx = content_lower.find(term)
                            if idx >= 0:
                                start = max(0, idx - 100)
                                end = min(len(content), idx + 200)
                                excerpt = content[start:end].strip()
                                break

                        try:
                            rel_path = str(md_file.relative_to(self._root_dir))
                        except ValueError:
                            rel_path = str(md_file)

                        results.append(
                            {
                                "source": "brain",
                                "type": search_dir.name.lower(),
                                "path": rel_path,
                                "title": md_file.stem.replace("_", " "),
                                "excerpt": excerpt[:500] if excerpt else content[:500],
                                "relevance_score": score,
                                "last_modified": datetime.fromtimestamp(
                                    md_file.stat().st_mtime
                                ).isoformat(),
                            }
                        )
                except Exception:
                    continue

        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:limit]

    def search_jira(self, topic: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search Jira for relevant issues and epics."""
        results = []
        if get_connector_client is not None:
            try:
                client = get_connector_client("jira")
                if client and hasattr(client, "search"):
                    jira_results = client.search(topic, limit=limit)
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
                                    if issue.get("description") else ""
                                ),
                                "url": issue.get("url", ""),
                                "assignee": issue.get("assignee", ""),
                            }
                        )
                    return results
            except Exception as e:
                logger.debug("Jira connector search failed: %s", e)
        return results

    def search_github(self, topic: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search GitHub for relevant PRs, issues, and code."""
        results = []
        if get_connector_client is not None:
            try:
                client = get_connector_client("github")
                if client and hasattr(client, "search"):
                    gh_results = client.search(topic, limit=limit)
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
                    return results
            except Exception as e:
                logger.debug("GitHub connector search failed: %s", e)
        return results

    def search_slack(self, topic: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search Slack messages for relevant discussions."""
        results = []

        # Check Brain/Inbox/Slack for cached messages
        slack_inbox = self._brain_dir / "Inbox" / "Slack"
        if slack_inbox.exists():
            search_terms = topic.lower().split()
            for md_file in slack_inbox.rglob("*.md"):
                try:
                    content = md_file.read_text(encoding="utf-8")
                    content_lower = content.lower()
                    score = sum(content_lower.count(term) for term in search_terms)
                    if score > 0:
                        try:
                            rel_path = str(md_file.relative_to(self._root_dir))
                        except ValueError:
                            rel_path = str(md_file)
                        results.append(
                            {
                                "source": "slack",
                                "type": "message",
                                "path": rel_path,
                                "title": md_file.stem,
                                "excerpt": content[:500],
                                "relevance_score": score,
                            }
                        )
                except Exception:
                    continue

        results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        return results[:limit]

    def search_gdrive(self, topic: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search Google Drive for relevant documents."""
        results = []

        gdocs_inbox = self._brain_dir / "Inbox" / "GDocs"
        if gdocs_inbox.exists():
            search_terms = topic.lower().split()
            for md_file in gdocs_inbox.rglob("*.md"):
                try:
                    content = md_file.read_text(encoding="utf-8")
                    content_lower = content.lower()
                    filename_lower = md_file.stem.lower()

                    score = 0
                    for term in search_terms:
                        if term in filename_lower:
                            score += 3
                        score += content_lower.count(term)

                    if score > 0:
                        try:
                            rel_path = str(md_file.relative_to(self._root_dir))
                        except ValueError:
                            rel_path = str(md_file)
                        results.append(
                            {
                                "source": "gdrive",
                                "type": "document",
                                "path": rel_path,
                                "title": md_file.stem,
                                "excerpt": content[:500],
                                "relevance_score": score,
                            }
                        )
                except Exception:
                    continue

        results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        return results[:limit]

    def search_confluence(self, topic: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search Confluence for relevant pages."""
        results = []

        # Check Brain/Inbox/Confluence for cached pages
        confluence_inbox = self._brain_dir / "Inbox" / "Confluence"
        if confluence_inbox.exists():
            search_terms = topic.lower().split()
            for md_file in confluence_inbox.rglob("*.md"):
                try:
                    content = md_file.read_text(encoding="utf-8")
                    content_lower = content.lower()
                    score = sum(content_lower.count(term) for term in search_terms)
                    if score > 0:
                        try:
                            rel_path = str(md_file.relative_to(self._root_dir))
                        except ValueError:
                            rel_path = str(md_file)
                        results.append(
                            {
                                "source": "confluence",
                                "type": "page",
                                "path": rel_path,
                                "title": md_file.stem,
                                "excerpt": content[:500],
                                "relevance_score": score,
                                "cached": True,
                            }
                        )
                except Exception:
                    continue

        # Try live Confluence search via connector_bridge
        if get_connector_client is not None and len(results) < limit:
            try:
                client = get_connector_client("confluence")
                if client and hasattr(client, "search"):
                    conf_results = client.search(topic, limit=limit - len(results))
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
                logger.debug("Confluence connector search failed: %s", e)

        results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        return results[:limit]

    def search_web(self, topic: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Perform web search for topic (placeholder for model invocation)."""
        return [
            {
                "source": "web",
                "type": "search_request",
                "query": topic,
                "note": "Web search requires model invocation",
                "limit": limit,
            }
        ]

    def gather_context(
        self,
        topic: str,
        sources: Optional[List[str]] = None,
        limit_per_source: int = 10,
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

        sources = [s.lower() for s in sources if s.lower() in SOURCES]

        context = {
            "topic": topic,
            "timestamp": datetime.now().isoformat(),
            "sources_searched": sources,
            "results": {},
            "total_results": 0,
        }

        source_functions = {
            "brain": self.search_brain,
            "jira": self.search_jira,
            "github": self.search_github,
            "slack": self.search_slack,
            "gdrive": self.search_gdrive,
            "confluence": self.search_confluence,
            "web": self.search_web,
        }

        for source in sources:
            if source in source_functions:
                try:
                    results = source_functions[source](topic, limit_per_source)
                    context["results"][source] = results
                    context["total_results"] += len(results)
                except Exception as e:
                    context["results"][source] = [{"error": str(e), "source": source}]

        context["summary"] = self._generate_summary(context)
        return context

    def _generate_summary(self, context: Dict[str, Any]) -> Dict[str, Any]:
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

        all_items.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

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

    def format_for_prompt(
        self, context: Dict[str, Any], max_length: int = 10000
    ) -> str:
        """Format research context for inclusion in a prompt."""
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

            for item in results[:5]:
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

            if len(section) > 2:
                parts.extend(section)

            if current_length > max_length:
                break

        return "\n".join(parts)


# Module-level convenience functions

_default_aggregator = None


def _get_default_aggregator() -> ResearchAggregator:
    global _default_aggregator
    if _default_aggregator is None:
        _default_aggregator = ResearchAggregator()
    return _default_aggregator


def gather_context(
    topic: str,
    sources: Optional[List[str]] = None,
    limit_per_source: int = 10,
) -> Dict[str, Any]:
    """Gather research context from multiple sources."""
    return _get_default_aggregator().gather_context(topic, sources, limit_per_source)


def format_for_prompt(context: Dict[str, Any], max_length: int = 10000) -> str:
    """Format research context for inclusion in a prompt."""
    return _get_default_aggregator().format_for_prompt(context, max_length)


def search_brain(topic: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Search Brain knowledge base for relevant content."""
    return _get_default_aggregator().search_brain(topic, limit)
