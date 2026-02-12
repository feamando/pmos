#!/usr/bin/env python3
"""
Confluence Brain Sync - Fetch and sync Confluence pages to Brain.

Searches Confluence for relevant pages and syncs them to Brain/Inbox/Confluence/
for use in document research and orthogonal challenges.

Usage:
    python3 confluence_brain_sync.py --search "OTP architecture"
    python3 confluence_brain_sync.py --page 12345678
    python3 confluence_brain_sync.py --space PROJ --recent 10
    python3 confluence_brain_sync.py --sync-all
"""

import argparse
import html
import json
import os
import re
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
CONFLUENCE_INBOX = BRAIN_DIR / "Inbox" / "Confluence"

# Confluence API configuration
CONFLUENCE_URL = os.getenv("CONFLUENCE_URL", "")
CONFLUENCE_EMAIL = os.getenv("CONFLUENCE_EMAIL", "")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN", "")
CONFLUENCE_SPACES = os.getenv("CONFLUENCE_SPACES", "").split(",")


# ============================================================================
# CONFLUENCE API CLIENT
# ============================================================================


def get_confluence_client():
    """Get Confluence API client."""
    try:
        from atlassian import Confluence
    except ImportError:
        print(
            "atlassian-python-api not installed. Run: pip install atlassian-python-api",
            file=sys.stderr,
        )
        return None

    if not CONFLUENCE_URL or not CONFLUENCE_EMAIL or not CONFLUENCE_API_TOKEN:
        print(
            "Confluence credentials not configured. Set CONFLUENCE_URL, CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN",
            file=sys.stderr,
        )
        return None

    return Confluence(
        url=CONFLUENCE_URL,
        username=CONFLUENCE_EMAIL,
        password=CONFLUENCE_API_TOKEN,
        cloud=True,
    )


def search_confluence(
    query: str, space_key: Optional[str] = None, limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Search Confluence for pages matching query.

    Args:
        query: Search query (CQL supported)
        space_key: Limit to specific space
        limit: Maximum results

    Returns:
        List of page metadata dicts
    """
    confluence = get_confluence_client()
    if not confluence:
        return []

    try:
        # Build CQL query
        cql = f'text ~ "{query}"'
        if space_key:
            cql += f' AND space = "{space_key}"'
        cql += " ORDER BY lastmodified DESC"

        results = confluence.cql(cql, limit=limit)

        pages = []
        for result in results.get("results", []):
            content = result.get("content", result)
            pages.append(
                {
                    "id": content.get("id"),
                    "title": content.get("title"),
                    "space_key": content.get("space", {}).get("key"),
                    "space_name": content.get("space", {}).get("name"),
                    "type": content.get("type", "page"),
                    "url": f"{CONFLUENCE_URL}/wiki{content.get('_links', {}).get('webui', '')}",
                    "last_modified": result.get("lastModified"),
                }
            )

        return pages

    except Exception as e:
        print(f"Confluence search error: {e}", file=sys.stderr)
        return []


def fetch_page_content(page_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch full content of a Confluence page.

    Args:
        page_id: Confluence page ID

    Returns:
        Dict with page content and metadata
    """
    confluence = get_confluence_client()
    if not confluence:
        return None

    try:
        page = confluence.get_page_by_id(
            page_id, expand="body.storage,version,space,ancestors"
        )

        # Convert HTML to markdown-like text
        body_html = page.get("body", {}).get("storage", {}).get("value", "")
        body_text = html_to_text(body_html)

        return {
            "id": page.get("id"),
            "title": page.get("title"),
            "space_key": page.get("space", {}).get("key"),
            "space_name": page.get("space", {}).get("name"),
            "version": page.get("version", {}).get("number"),
            "last_modified": page.get("version", {}).get("when"),
            "url": f"{CONFLUENCE_URL}/wiki{page.get('_links', {}).get('webui', '')}",
            "content_html": body_html,
            "content_text": body_text,
            "ancestors": [
                {"id": a.get("id"), "title": a.get("title")}
                for a in page.get("ancestors", [])
            ],
        }

    except Exception as e:
        print(f"Confluence fetch error: {e}", file=sys.stderr)
        return None


def get_recent_pages(space_key: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get recently modified pages in a space.

    Args:
        space_key: Confluence space key
        limit: Maximum results

    Returns:
        List of page metadata dicts
    """
    return search_confluence("", space_key=space_key, limit=limit)


def get_child_pages(parent_id: str) -> List[Dict[str, Any]]:
    """
    Get child pages of a parent page.

    Args:
        parent_id: Parent page ID

    Returns:
        List of child page metadata dicts
    """
    confluence = get_confluence_client()
    if not confluence:
        return []

    try:
        children = confluence.get_page_child_by_type(parent_id, type="page", limit=50)

        pages = []
        for child in children.get("results", []):
            pages.append(
                {
                    "id": child.get("id"),
                    "title": child.get("title"),
                    "type": child.get("type", "page"),
                }
            )

        return pages

    except Exception as e:
        print(f"Confluence child pages error: {e}", file=sys.stderr)
        return []


# ============================================================================
# HTML TO TEXT CONVERSION
# ============================================================================


def html_to_text(html_content: str) -> str:
    """
    Convert Confluence HTML to plain text with markdown-like formatting.

    Args:
        html_content: HTML string from Confluence

    Returns:
        Plain text with basic formatting
    """
    if not html_content:
        return ""

    text = html_content

    # Remove style and script tags
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(
        r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE
    )

    # Convert headers
    for i in range(6, 0, -1):
        text = re.sub(
            rf"<h{i}[^>]*>(.*?)</h{i}>",
            r"\n" + "#" * i + r" \1\n",
            text,
            flags=re.IGNORECASE,
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
        r"<pre[^>]*>(.*?)</pre>",
        r"\n```\n\1\n```\n",
        text,
        flags=re.DOTALL | re.IGNORECASE,
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
    """
    Sync a Confluence page to Brain/Inbox/Confluence.

    Args:
        page: Page dict from fetch_page_content

    Returns:
        Path to created markdown file
    """
    CONFLUENCE_INBOX.mkdir(parents=True, exist_ok=True)

    # Create safe filename
    title_safe = re.sub(r"[^\w\s-]", "", page.get("title", "Untitled"))
    title_safe = re.sub(r"\s+", "_", title_safe)[:50]
    filename = f"{page.get('id')}_{title_safe}.md"
    filepath = CONFLUENCE_INBOX / filename

    # Build markdown content
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
    """
    Search and sync matching pages to Brain.

    Args:
        query: Search query
        space_key: Limit to specific space
        limit: Maximum pages to sync

    Returns:
        List of paths to synced files
    """
    results = search_confluence(query, space_key, limit)

    synced = []
    for result in results:
        page = fetch_page_content(result["id"])
        if page:
            path = sync_page_to_brain(page)
            synced.append(path)
            print(f"Synced: {page.get('title')} -> {path.name}", file=sys.stderr)

    return synced


def get_synced_pages() -> List[Dict[str, Any]]:
    """
    Get list of pages already synced to Brain.

    Returns:
        List of page metadata from synced files
    """
    if not CONFLUENCE_INBOX.exists():
        return []

    pages = []
    for filepath in CONFLUENCE_INBOX.glob("*.md"):
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


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Confluence Brain Sync - Fetch and sync Confluence pages"
    )
    parser.add_argument(
        "--search", type=str, help="Search Confluence for pages matching query"
    )
    parser.add_argument("--page", type=str, help="Fetch and sync a specific page by ID")
    parser.add_argument("--space", type=str, help="Confluence space key to search/sync")
    parser.add_argument(
        "--recent",
        type=int,
        metavar="N",
        help="Get N most recently modified pages in space",
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="Maximum pages to return (default: 10)"
    )
    parser.add_argument(
        "--sync", action="store_true", help="Sync search results to Brain"
    )
    parser.add_argument(
        "--list-synced", action="store_true", help="List pages already synced to Brain"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

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
            print("Page not found or error fetching", file=sys.stderr)
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
                    path = sync_page_to_brain(page)
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
