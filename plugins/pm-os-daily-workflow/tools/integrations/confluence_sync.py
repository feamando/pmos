#!/usr/bin/env python3
"""
Confluence Brain Sync (v5.0)

Fetches Confluence pages via CQL search and syncs them to Brain/Inbox/Confluence/
for document research and context enrichment. All credentials and spaces
are loaded from config/connector_bridge — zero hardcoded values.

Usage:
    python3 confluence_sync.py --search "architecture"
    python3 confluence_sync.py --page 12345678
    python3 confluence_sync.py --space PROJ --recent 10
    python3 confluence_sync.py --list-synced
"""

import argparse
import html
import json
import logging
import re
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


def _get_confluence_client():
    """Get Confluence API client using connector_bridge for auth."""
    try:
        from atlassian import Confluence
    except ImportError:
        logger.error(
            "atlassian-python-api not installed. Run: pip install atlassian-python-api"
        )
        return None

    # Check auth via connector bridge
    if get_auth is not None:
        auth = get_auth("confluence")
        if auth.source == "connector":
            logger.info("Confluence auth via Claude connector")
            return None  # Connector mode
        elif auth.source == "none":
            logger.error("Confluence auth not available: %s", auth.help_message)
            return None

    # Load credentials from config/env
    config = get_config() if get_config else None
    if config is None:
        logger.error("Config loader not available")
        return None

    url = config.get("integrations.confluence.url") or config.get_secret("CONFLUENCE_URL")
    email = config.get("integrations.confluence.email") or config.get_secret("CONFLUENCE_EMAIL")
    token = config.get_secret("JIRA_API_TOKEN") or config.get_secret("CONFLUENCE_API_TOKEN")

    if not url or not email or not token:
        logger.error(
            "Confluence credentials not configured. "
            "Set CONFLUENCE_URL, CONFLUENCE_EMAIL, JIRA_API_TOKEN"
        )
        return None

    return Confluence(url=url, username=email, password=token, cloud=True)


def _get_configured_spaces() -> List[str]:
    """Get configured Confluence spaces from config."""
    config = get_config() if get_config else None
    if config:
        spaces = config.get_list("integrations.confluence.spaces")
        if spaces:
            return spaces
    return []


def _get_confluence_url() -> str:
    """Get Confluence base URL from config."""
    config = get_config() if get_config else None
    if config:
        url = config.get("integrations.confluence.url") or config.get_secret("CONFLUENCE_URL")
        if url:
            return url
    return ""


# ============================================================================
# SEARCH & FETCH
# ============================================================================


def search_confluence(
    query: str, space_key: Optional[str] = None, limit: int = 20
) -> List[Dict[str, Any]]:
    """Search Confluence for pages matching query via CQL."""
    confluence = _get_confluence_client()
    if not confluence:
        return []

    base_url = _get_confluence_url()

    try:
        cql = f'text ~ "{query}"'
        if space_key:
            cql += f' AND space = "{space_key}"'
        cql += " ORDER BY lastmodified DESC"

        results = confluence.cql(cql, limit=limit)

        pages = []
        for result in results.get("results", []):
            content = result.get("content", result)
            pages.append({
                "id": content.get("id"),
                "title": content.get("title"),
                "space_key": content.get("space", {}).get("key"),
                "space_name": content.get("space", {}).get("name"),
                "type": content.get("type", "page"),
                "url": f"{base_url}/wiki{content.get('_links', {}).get('webui', '')}",
                "last_modified": result.get("lastModified"),
            })

        return pages

    except Exception as e:
        logger.error("Confluence search error: %s", e)
        return []


def fetch_page_content(page_id: str) -> Optional[Dict[str, Any]]:
    """Fetch full content of a Confluence page."""
    confluence = _get_confluence_client()
    if not confluence:
        return None

    base_url = _get_confluence_url()

    try:
        page = confluence.get_page_by_id(
            page_id, expand="body.storage,version,space,ancestors"
        )

        body_html = page.get("body", {}).get("storage", {}).get("value", "")
        body_text = html_to_text(body_html)

        return {
            "id": page.get("id"),
            "title": page.get("title"),
            "space_key": page.get("space", {}).get("key"),
            "space_name": page.get("space", {}).get("name"),
            "version": page.get("version", {}).get("number"),
            "last_modified": page.get("version", {}).get("when"),
            "url": f"{base_url}/wiki{page.get('_links', {}).get('webui', '')}",
            "content_html": body_html,
            "content_text": body_text,
            "ancestors": [
                {"id": a.get("id"), "title": a.get("title")}
                for a in page.get("ancestors", [])
            ],
        }

    except Exception as e:
        logger.error("Confluence fetch error: %s", e)
        return None


def get_recent_pages(space_key: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Get recently modified pages in a space."""
    return search_confluence("", space_key=space_key, limit=limit)


def get_child_pages(parent_id: str) -> List[Dict[str, Any]]:
    """Get child pages of a parent page."""
    confluence = _get_confluence_client()
    if not confluence:
        return []

    try:
        children = confluence.get_page_child_by_type(parent_id, type="page", limit=50)
        pages = []
        for child in children.get("results", []):
            pages.append({
                "id": child.get("id"),
                "title": child.get("title"),
                "type": child.get("type", "page"),
            })
        return pages

    except Exception as e:
        logger.error("Confluence child pages error: %s", e)
        return []


# ============================================================================
# HTML TO TEXT CONVERSION
# ============================================================================


def html_to_text(html_content: str) -> str:
    """Convert Confluence HTML to plain text with markdown-like formatting."""
    if not html_content:
        return ""

    text = html_content

    # Remove style and script tags
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Convert headers
    for i in range(6, 0, -1):
        text = re.sub(
            rf"<h{i}[^>]*>(.*?)</h{i}>",
            r"\n" + "#" * i + r" \1\n",
            text, flags=re.IGNORECASE,
        )

    # Convert lists
    text = re.sub(r"<li[^>]*>", "\n- ", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[ou]l[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</[ou]l>", "\n", text, flags=re.IGNORECASE)

    # Convert paragraphs and breaks
    text = re.sub(r"<p[^>]*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<br[^>]*/?>", "\n", text, flags=re.IGNORECASE)

    # Convert bold and italic
    text = re.sub(r"<strong[^>]*>(.*?)</strong>", r"**\1**", text, flags=re.IGNORECASE)
    text = re.sub(r"<b[^>]*>(.*?)</b>", r"**\1**", text, flags=re.IGNORECASE)
    text = re.sub(r"<em[^>]*>(.*?)</em>", r"*\1*", text, flags=re.IGNORECASE)
    text = re.sub(r"<i[^>]*>(.*?)</i>", r"*\1*", text, flags=re.IGNORECASE)

    # Convert code blocks
    text = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", text, flags=re.IGNORECASE)
    text = re.sub(
        r"<pre[^>]*>(.*?)</pre>", r"\n```\n\1\n```\n",
        text, flags=re.DOTALL | re.IGNORECASE,
    )

    # Convert tables (simplified)
    text = re.sub(r"<table[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</table>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<tr[^>]*>", "\n| ", text, flags=re.IGNORECASE)
    text = re.sub(r"</tr>", " |", text, flags=re.IGNORECASE)
    text = re.sub(r"<t[dh][^>]*>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"</t[dh]>", " |", text, flags=re.IGNORECASE)

    # Remove remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode HTML entities
    text = html.unescape(text)

    # Clean up whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    text = text.strip()

    return text


# ============================================================================
# BRAIN SYNC
# ============================================================================


def sync_page_to_brain(page: Dict[str, Any]) -> Path:
    """Sync a Confluence page to Brain/Inbox/Confluence."""
    brain_dir = _resolve_brain_dir()
    confluence_inbox = brain_dir / "Inbox" / "Confluence"
    confluence_inbox.mkdir(parents=True, exist_ok=True)

    # Create safe filename
    title_safe = re.sub(r"[^\w\s-]", "", page.get("title", "Untitled"))
    title_safe = re.sub(r"\s+", "_", title_safe)[:50]
    filename = f"{page.get('id')}_{title_safe}.md"
    filepath = confluence_inbox / filename

    content = f"""---
confluence_id: {page.get('id')}
title: "{page.get('title', 'Untitled')}"
space: {page.get('space_key')}
url: {page.get('url')}
last_modified: {page.get('last_modified')}
synced_at: {datetime.now().isoformat()}
---

# {page.get('title', 'Untitled')}

**Space:** {page.get('space_name', page.get('space_key'))}
**URL:** [{page.get('url')}]({page.get('url')})
**Last Modified:** {page.get('last_modified')}

---

{page.get('content_text', '')}
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath


def sync_search_results(
    query: str, space_key: Optional[str] = None, limit: int = 10
) -> List[Path]:
    """Search and sync matching pages to Brain."""
    results = search_confluence(query, space_key, limit)

    synced = []
    for result in results:
        page = fetch_page_content(result["id"])
        if page:
            path = sync_page_to_brain(page)
            synced.append(path)
            logger.info("Synced: %s -> %s", page.get("title"), path.name)

    return synced


def get_synced_pages() -> List[Dict[str, Any]]:
    """Get list of pages already synced to Brain."""
    brain_dir = _resolve_brain_dir()
    confluence_inbox = brain_dir / "Inbox" / "Confluence"

    if not confluence_inbox.exists():
        return []

    pages = []
    for filepath in confluence_inbox.glob("*.md"):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse frontmatter
        frontmatter = {}
        if content.startswith("---"):
            end = content.find("---", 3)
            if end > 0:
                fm_content = content[3:end]
                for line in fm_content.strip().split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        frontmatter[key.strip()] = value.strip().strip('"')

        pages.append({"file": filepath.name, "path": str(filepath), **frontmatter})

    return pages


def run_sync(
    query: Optional[str] = None,
    page_id: Optional[str] = None,
    space_key: Optional[str] = None,
    recent: Optional[int] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Run Confluence sync programmatically.

    Args:
        query: Search query
        page_id: Specific page ID to sync
        space_key: Confluence space key
        recent: Number of recent pages to sync
        limit: Maximum pages to sync

    Returns:
        Dict with sync results
    """
    if page_id:
        page = fetch_page_content(page_id)
        if page:
            path = sync_page_to_brain(page)
            return {"status": "success", "pages_synced": 1, "files": [str(path)]}
        return {"status": "error", "message": f"Page {page_id} not found"}

    if query:
        synced = sync_search_results(query, space_key, limit)
        return {
            "status": "success",
            "pages_synced": len(synced),
            "files": [str(p) for p in synced],
        }

    if recent and space_key:
        results = get_recent_pages(space_key, recent)
        synced = []
        for r in results:
            page = fetch_page_content(r["id"])
            if page:
                path = sync_page_to_brain(page)
                synced.append(str(path))
        return {"status": "success", "pages_synced": len(synced), "files": synced}

    return {"status": "error", "message": "No query, page_id, or space+recent provided"}


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Confluence Brain Sync - Fetch and sync Confluence pages"
    )
    parser.add_argument("--search", type=str, help="Search Confluence for pages matching query")
    parser.add_argument("--page", type=str, help="Fetch and sync a specific page by ID")
    parser.add_argument("--space", type=str, help="Confluence space key to search/sync")
    parser.add_argument("--recent", type=int, metavar="N", help="Get N most recent pages in space")
    parser.add_argument("--limit", type=int, default=10, help="Maximum pages to return (default: 10)")
    parser.add_argument("--sync", action="store_true", help="Sync search results to Brain")
    parser.add_argument("--list-synced", action="store_true", help="List pages already synced to Brain")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.list_synced:
        pages = get_synced_pages()
        if args.json:
            print(json.dumps(pages, indent=2))
        else:
            print(f"Synced Confluence pages ({len(pages)}):")
            for p in pages:
                print(f"  [{p.get('confluence_id')}] {p.get('title', 'Unknown')}")
        return 0

    if args.page:
        page = fetch_page_content(args.page)
        if page:
            if args.sync:
                path = sync_page_to_brain(page)
                print(f"Synced to: {path}")
            elif args.json:
                print(json.dumps(page, indent=2))
            else:
                print(f"Title: {page.get('title')}")
                print(f"Space: {page.get('space_name')}")
                print(f"URL: {page.get('url')}")
                print("-" * 60)
                print(page.get("content_text", "")[:2000])
        else:
            logger.error("Page not found or error fetching")
            return 1
        return 0

    if args.search:
        if args.sync:
            synced = sync_search_results(args.search, args.space, args.limit)
            print(f"Synced {len(synced)} pages to Brain")
        else:
            results = search_confluence(args.search, args.space, args.limit)
            if args.json:
                print(json.dumps(results, indent=2))
            else:
                print(f"Search results for '{args.search}':")
                for r in results:
                    print(f"  [{r.get('id')}] {r.get('title')} ({r.get('space_key')})")
        return 0

    if args.recent and args.space:
        results = get_recent_pages(args.space, args.recent)
        if args.sync:
            for r in results:
                page = fetch_page_content(r["id"])
                if page:
                    sync_page_to_brain(page)
                    print(f"Synced: {page.get('title')}")
        elif args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"Recent pages in {args.space}:")
            for r in results:
                print(f"  [{r.get('id')}] {r.get('title')}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
