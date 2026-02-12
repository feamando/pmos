#!/usr/bin/env python3
"""
Confluence Documentation Sync - Upload PM-OS documentation to Confluence.

Uploads markdown documentation files to Confluence PMOS space,
maintaining hierarchy and tracking sync status.

Usage:
    python3 confluence_doc_sync.py --file documentation/README.md --space PMOS
    python3 confluence_doc_sync.py --all --space PMOS
    python3 confluence_doc_sync.py --status
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    import path_resolver

    COMMON_DIR = path_resolver.get_common()
except ImportError:
    path_resolver = None
    COMMON_DIR = Path(__file__).parent.parent.parent

# Import config_loader to properly load .env file
try:
    import config_loader

    _conf = config_loader.get_confluence_config()
    CONFLUENCE_URL = _conf.get("url") or "https://your-company.atlassian.net/wiki"
    CONFLUENCE_EMAIL = _conf.get("username") or ""
    CONFLUENCE_API_TOKEN = _conf.get("api_token") or ""
except ImportError:
    # Fallback to direct env vars if config_loader not available
    CONFLUENCE_URL = os.getenv(
        "CONFLUENCE_URL", "https://your-company.atlassian.net/wiki"
    )
    CONFLUENCE_EMAIL = os.getenv("CONFLUENCE_EMAIL", os.getenv("JIRA_USERNAME", ""))
    CONFLUENCE_API_TOKEN = os.getenv(
        "CONFLUENCE_API_TOKEN", os.getenv("JIRA_API_TOKEN", "")
    )

DOC_DIR = COMMON_DIR / "documentation"
STATUS_FILE = DOC_DIR / "_meta" / "documentation-status.json"
SYNC_LOG = DOC_DIR / "_meta" / "confluence-sync-log.md"


# ============================================================================
# CONFLUENCE CLIENT
# ============================================================================


def get_confluence_client():
    """Get Confluence API client."""
    try:
        from atlassian import Confluence
    except ImportError:
        print("Error: atlassian-python-api not installed", file=sys.stderr)
        print("Run: pip install atlassian-python-api", file=sys.stderr)
        return None

    if not CONFLUENCE_URL or not CONFLUENCE_EMAIL or not CONFLUENCE_API_TOKEN:
        print("Error: Confluence credentials not configured", file=sys.stderr)
        print(
            "Required: CONFLUENCE_URL, CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN",
            file=sys.stderr,
        )
        return None

    return Confluence(
        url=CONFLUENCE_URL,
        username=CONFLUENCE_EMAIL,
        password=CONFLUENCE_API_TOKEN,
        cloud=True,
    )


# ============================================================================
# MARKDOWN TO CONFLUENCE CONVERSION
# ============================================================================


def markdown_to_confluence(markdown: str) -> str:
    """
    Convert markdown to Confluence storage format (XHTML).

    Args:
        markdown: Markdown content

    Returns:
        Confluence storage format HTML
    """
    html = markdown

    # Remove YAML frontmatter if present
    if html.startswith("---"):
        end = html.find("---", 3)
        if end > 0:
            html = html[end + 3 :].strip()

    # Convert headers
    html = re.sub(r"^######\s+(.+)$", r"<h6>\1</h6>", html, flags=re.MULTILINE)
    html = re.sub(r"^#####\s+(.+)$", r"<h5>\1</h5>", html, flags=re.MULTILINE)
    html = re.sub(r"^####\s+(.+)$", r"<h4>\1</h4>", html, flags=re.MULTILINE)
    html = re.sub(r"^###\s+(.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^##\s+(.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^#\s+(.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

    # Convert code blocks (fenced)
    def code_block_replacer(match):
        lang = match.group(1) or ""
        code = match.group(2)
        code = code.replace("<", "&lt;").replace(">", "&gt;")
        if lang:
            return f'<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">{lang}</ac:parameter><ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body></ac:structured-macro>'
        return f'<ac:structured-macro ac:name="code"><ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body></ac:structured-macro>'

    html = re.sub(r"```(\w*)\n(.*?)```", code_block_replacer, html, flags=re.DOTALL)

    # Convert inline code
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)

    # Convert bold and italic
    html = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", html)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

    # Convert links
    html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', html)

    # Convert tables
    def table_replacer(match):
        lines = match.group(0).strip().split("\n")
        if len(lines) < 2:
            return match.group(0)

        result = "<table><tbody>"

        # Header row
        header = lines[0]
        cells = [c.strip() for c in header.split("|")[1:-1]]
        result += "<tr>"
        for cell in cells:
            result += f"<th>{cell}</th>"
        result += "</tr>"

        # Skip separator row (lines[1])

        # Data rows
        for line in lines[2:]:
            if "|" in line:
                cells = [c.strip() for c in line.split("|")[1:-1]]
                result += "<tr>"
                for cell in cells:
                    result += f"<td>{cell}</td>"
                result += "</tr>"

        result += "</tbody></table>"
        return result

    # Match tables (simplified)
    html = re.sub(r"(\|.+\|\n)+", table_replacer, html)

    # Convert unordered lists
    def ul_replacer(match):
        items = match.group(0).strip().split("\n")
        result = "<ul>"
        for item in items:
            item_text = re.sub(r"^[\-\*]\s+", "", item.strip())
            if item_text:
                result += f"<li>{item_text}</li>"
        result += "</ul>"
        return result

    html = re.sub(r"(^[\-\*]\s+.+$\n?)+", ul_replacer, html, flags=re.MULTILINE)

    # Convert ordered lists
    def ol_replacer(match):
        items = match.group(0).strip().split("\n")
        result = "<ol>"
        for item in items:
            item_text = re.sub(r"^\d+\.\s+", "", item.strip())
            if item_text:
                result += f"<li>{item_text}</li>"
        result += "</ol>"
        return result

    html = re.sub(r"(^\d+\.\s+.+$\n?)+", ol_replacer, html, flags=re.MULTILINE)

    # Convert blockquotes
    def blockquote_replacer(match):
        lines = match.group(0).strip().split("\n")
        content = " ".join(re.sub(r"^>\s*", "", line) for line in lines)
        return f"<blockquote>{content}</blockquote>"

    html = re.sub(r"(^>\s*.+$\n?)+", blockquote_replacer, html, flags=re.MULTILINE)

    # Convert horizontal rules
    html = re.sub(r"^---+$", "<hr />", html, flags=re.MULTILINE)

    # Wrap remaining paragraphs
    paragraphs = html.split("\n\n")
    wrapped = []
    for p in paragraphs:
        p = p.strip()
        if p and not p.startswith("<"):
            p = f"<p>{p}</p>"
        wrapped.append(p)
    html = "\n".join(wrapped)

    # Clean up
    html = re.sub(r"\n{3,}", "\n\n", html)

    return html


# ============================================================================
# CONFLUENCE OPERATIONS
# ============================================================================


def get_or_create_page(
    confluence, space: str, title: str, parent_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Get existing page or create new one.

    Args:
        confluence: Confluence client
        space: Space key
        title: Page title
        parent_id: Optional parent page ID

    Returns:
        Page info dict or None
    """
    try:
        # Check if page exists
        existing = confluence.get_page_by_title(space, title)
        if existing:
            return existing

        # Create new page
        body = "<p>Page content will be updated.</p>"
        page = confluence.create_page(
            space=space, title=title, body=body, parent_id=parent_id
        )
        return page

    except Exception as e:
        print(f"Error getting/creating page '{title}': {e}", file=sys.stderr)
        return None


def update_page(confluence, page_id: str, title: str, body: str) -> bool:
    """
    Update page content.

    Args:
        confluence: Confluence client
        page_id: Page ID
        title: Page title
        body: Confluence storage format HTML

    Returns:
        True if successful
    """
    try:
        confluence.update_page(page_id=page_id, title=title, body=body)
        return True
    except Exception as e:
        print(f"Error updating page '{title}': {e}", file=sys.stderr)
        return False


def upload_documentation(
    file_path: Path, space: str, parent_id: Optional[str] = None, dry_run: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Upload a markdown file to Confluence.

    Args:
        file_path: Path to markdown file
        space: Confluence space key
        parent_id: Parent page ID
        dry_run: If True, don't actually upload

    Returns:
        Result dict with page info
    """
    if not file_path.exists():
        print(f"File not found: {file_path}", file=sys.stderr)
        return None

    # Read markdown content
    with open(file_path, "r", encoding="utf-8") as f:
        markdown = f.read()

    # Extract title from first H1 or filename
    title_match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
    else:
        title = file_path.stem.replace("-", " ").replace("_", " ").title()

    # Prefix with PM-OS for clarity
    if not title.startswith("PM-OS"):
        title = f"PM-OS: {title}"

    # Convert to Confluence format
    confluence_html = markdown_to_confluence(markdown)

    if dry_run:
        print(f"Would upload: {file_path.name} -> '{title}'")
        return {"title": title, "file": str(file_path), "dry_run": True}

    # Get Confluence client
    confluence = get_confluence_client()
    if not confluence:
        return None

    # Create or get page
    page = get_or_create_page(confluence, space, title, parent_id)
    if not page:
        return None

    page_id = page.get("id")

    # Update content
    if update_page(confluence, page_id, title, confluence_html):
        url = f"{CONFLUENCE_URL}/wiki/spaces/{space}/pages/{page_id}"
        return {
            "id": page_id,
            "title": title,
            "url": url,
            "file": str(file_path),
            "synced_at": datetime.now().isoformat(),
        }

    return None


# ============================================================================
# DOCUMENTATION STRUCTURE
# ============================================================================

# Mapping of doc files to Confluence page hierarchy
DOC_STRUCTURE = [
    # (file_path, title_override, parent_key)
    ("README.md", "PM-OS Documentation", None),
    ("01-overview.md", "Overview", "README.md"),
    ("02-architecture.md", "Architecture", "README.md"),
    ("03-installation.md", "Installation Guide", "README.md"),
    ("04-workflows.md", "Workflows", "README.md"),
    ("05-brain.md", "Brain Architecture", "README.md"),
    ("commands/README.md", "Commands Reference", "README.md"),
    ("commands/core-commands.md", "Core Commands", "commands/README.md"),
    ("commands/document-commands.md", "Document Commands", "commands/README.md"),
    ("commands/integration-commands.md", "Integration Commands", "commands/README.md"),
    ("commands/fpf-commands.md", "FPF Commands", "commands/README.md"),
    ("commands/agent-commands.md", "Agent Commands", "commands/README.md"),
    ("tools/README.md", "Tools Reference", "README.md"),
    ("tools/brain-tools.md", "Brain Tools", "tools/README.md"),
    ("tools/integration-tools.md", "Integration Tools", "tools/README.md"),
    ("tools/session-tools.md", "Session Tools", "tools/README.md"),
    ("tools/utility-tools.md", "Utility Tools", "tools/README.md"),
    ("tools/preflight.md", "Preflight Checks", "tools/README.md"),
    ("schemas/entity-schemas.md", "Entity Schemas", "README.md"),
    ("troubleshooting/common-issues.md", "Common Issues", "README.md"),
    ("troubleshooting/faq.md", "FAQ", "README.md"),
    ("slackbot/creating-your-bot.md", "Creating Your Slackbot", "README.md"),
]


def sync_all_documentation(space: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Sync all documentation to Confluence.

    Args:
        space: Confluence space key
        dry_run: If True, don't actually upload

    Returns:
        Sync results dict
    """
    results = {
        "space": space,
        "synced_at": datetime.now().isoformat(),
        "pages": [],
        "errors": [],
        "dry_run": dry_run,
    }

    # Track page IDs for parent references
    page_ids = {}

    for file_rel, title, parent_key in DOC_STRUCTURE:
        file_path = DOC_DIR / file_rel

        if not file_path.exists():
            results["errors"].append(f"File not found: {file_rel}")
            continue

        # Get parent ID
        parent_id = page_ids.get(parent_key) if parent_key else None

        print(f"Syncing: {file_rel} -> '{title}'...")

        result = upload_documentation(file_path, space, parent_id, dry_run)

        if result:
            results["pages"].append(result)
            page_ids[file_rel] = result.get("id")
            print(f"  Done: {result.get('url', 'dry-run')}")
        else:
            results["errors"].append(f"Failed to sync: {file_rel}")

    return results


def update_status_file(sync_results: Dict[str, Any]):
    """Update the documentation status file with sync results."""
    if not STATUS_FILE.exists():
        return

    with open(STATUS_FILE, "r") as f:
        status = json.load(f)

    status["confluence_sync"] = {
        "enabled": True,
        "space": sync_results.get("space"),
        "last_sync": sync_results.get("synced_at"),
        "pages_synced": len(sync_results.get("pages", [])),
        "pages": {
            p.get("file", "").replace(str(DOC_DIR) + "/", ""): {
                "id": p.get("id"),
                "title": p.get("title"),
                "url": p.get("url"),
                "synced_at": p.get("synced_at"),
            }
            for p in sync_results.get("pages", [])
            if not p.get("dry_run")
        },
    }

    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, indent=2)


def update_sync_log(sync_results: Dict[str, Any]):
    """Append sync results to the sync log."""
    entry = f"""
### {sync_results.get('synced_at', 'Unknown')}

**Space:** {sync_results.get('space')}
**Pages synced:** {len(sync_results.get('pages', []))}
**Errors:** {len(sync_results.get('errors', []))}

| File | Title | Status |
|------|-------|--------|
"""

    for page in sync_results.get("pages", []):
        status = "Dry run" if page.get("dry_run") else f"[View]({page.get('url', '#')})"
        entry += f"| {page.get('file', '').split('/')[-1]} | {page.get('title')} | {status} |\n"

    for error in sync_results.get("errors", []):
        entry += f"| - | - | Error: {error} |\n"

    entry += "\n---\n"

    # Append to log
    with open(SYNC_LOG, "a") as f:
        f.write(entry)


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Confluence Documentation Sync - Upload PM-OS docs to Confluence"
    )
    parser.add_argument("--file", type=str, help="Upload a single documentation file")
    parser.add_argument(
        "--all", action="store_true", help="Sync all documentation files"
    )
    parser.add_argument(
        "--space", type=str, default="PMOS", help="Confluence space key (default: PMOS)"
    )
    parser.add_argument(
        "--parent", type=str, help="Parent page ID for single file upload"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be uploaded without uploading",
    )
    parser.add_argument(
        "--status", action="store_true", help="Show current sync status"
    )

    args = parser.parse_args()

    if args.status:
        if STATUS_FILE.exists():
            with open(STATUS_FILE, "r") as f:
                status = json.load(f)
            sync = status.get("confluence_sync", {})
            print(f"Confluence Sync Status")
            print(f"  Space: {sync.get('space', 'Not configured')}")
            print(f"  Last sync: {sync.get('last_sync', 'Never')}")
            print(f"  Pages synced: {sync.get('pages_synced', 0)}")
        else:
            print("Status file not found")
        return 0

    if args.all:
        print(f"Syncing all documentation to Confluence space '{args.space}'...")
        if args.dry_run:
            print("(Dry run - no changes will be made)")

        results = sync_all_documentation(args.space, args.dry_run)

        print(f"\nSync complete:")
        print(f"  Pages synced: {len(results.get('pages', []))}")
        print(f"  Errors: {len(results.get('errors', []))}")

        if results.get("errors"):
            print("\nErrors:")
            for error in results["errors"]:
                print(f"  - {error}")

        if not args.dry_run:
            update_status_file(results)
            update_sync_log(results)
            print(f"\nView at: {CONFLUENCE_URL}/wiki/spaces/{args.space}")

        return 0

    if args.file:
        file_path = Path(args.file)
        if not file_path.is_absolute():
            file_path = DOC_DIR / file_path

        print(f"Uploading {file_path.name} to Confluence space '{args.space}'...")
        if args.dry_run:
            print("(Dry run - no changes will be made)")

        result = upload_documentation(file_path, args.space, args.parent, args.dry_run)

        if result:
            print(f"Success: {result.get('title')}")
            if result.get("url"):
                print(f"URL: {result.get('url')}")
        else:
            print("Failed to upload")
            return 1

        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
