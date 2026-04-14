#!/usr/bin/env python3
"""
PM-OS Brain MCP Server (v5.0)

Exposes Brain knowledge graph via MCP protocol with support for both
stdin/stdout (CLI) and Streamable HTTP (Cowork) transports.

Provides tools for searching, retrieving, and querying Brain entities
so any MCP-compatible client (Cursor, Windsurf, Claude Code, Cowork)
can access the knowledge graph.

Usage:
    python3 brain_mcp_server.py              # Start MCP server (stdio)
    MCP_TRANSPORT=http python3 brain_mcp_server.py   # Streamable HTTP
    python3 brain_mcp_server.py --cli search_entities "checkout"   # CLI mode
"""

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import yaml
except ImportError:
    yaml = None
    logger.warning("PyYAML not installed. Install with: pip install pyyaml")

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None

# v5 imports
try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from core.config_loader import get_config
    except ImportError:
        get_config = None

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        from core.path_resolver import get_paths
    except ImportError:
        get_paths = None

try:
    from pm_os_base.tools.core.connector_bridge import get_auth
except ImportError:
    get_auth = None


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Max token size for Cowork responses (25,000 token limit)
MAX_RESPONSE_CHARS = 75000  # ~25k tokens at ~3 chars/token
MAX_BODY_CHARS = 3000  # Per-entity body truncation


# Initialize FastMCP (stub if mcp package not installed — CLI mode still works)
if FastMCP:
    mcp = FastMCP("brain-mcp")
else:
    class _StubMCP:
        """No-op MCP stub for when mcp package isn't installed (CLI mode)."""
        def tool(self, **kwargs):
            def decorator(fn):
                return fn
            return decorator
        def run(self, **kwargs):
            print("Error: mcp package not installed. Install with: pip install mcp")
    mcp = _StubMCP()

# Brain path resolution (cached)
_BRAIN_PATH: Optional[Path] = None


def _get_brain_path() -> Path:
    """Resolve Brain directory path from path_resolver, env, or config."""
    global _BRAIN_PATH
    if _BRAIN_PATH is not None:
        return _BRAIN_PATH

    # 1. path_resolver (v5 preferred)
    if get_paths is not None:
        try:
            _BRAIN_PATH = get_paths().brain
            return _BRAIN_PATH
        except Exception:
            pass

    # 2. Explicit env var
    env_path = os.environ.get("PM_OS_BRAIN_PATH")
    if env_path:
        _BRAIN_PATH = Path(env_path)
        return _BRAIN_PATH

    # 3. Derive from PM_OS_USER
    user_path = os.environ.get("PM_OS_USER")
    if user_path:
        _BRAIN_PATH = Path(user_path) / "brain"
        return _BRAIN_PATH

    # 4. Config loader
    if get_config is not None:
        try:
            config = get_config()
            if config.user_path:
                _BRAIN_PATH = config.user_path / "brain"
                return _BRAIN_PATH
        except Exception:
            pass

    # 5. Fallback (no hardcoded user-specific paths)
    _BRAIN_PATH = Path.cwd() / "user" / "brain"
    return _BRAIN_PATH


def _parse_frontmatter(content: str) -> tuple:
    """Parse YAML frontmatter from markdown content. Returns (frontmatter_dict, body_text)."""
    if yaml is None or not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    try:
        fm = yaml.safe_load(parts[1]) or {}
        return fm, parts[2].strip()
    except Exception:
        return {}, content


def _load_entity_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Load and parse a Brain entity file."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, IOError):
        return None

    fm, body = _parse_frontmatter(content)
    if not fm:
        return None

    fm["_body"] = body
    fm["_path"] = str(file_path)
    fm["_name"] = file_path.stem.replace("_", " ")
    return fm


def _truncate_response(text: str, max_chars: int = MAX_RESPONSE_CHARS) -> str:
    """Truncate response to fit within Cowork token limits."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    truncated += f"\n\n... (response truncated at {max_chars} chars to fit token limit)"
    return truncated


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
def search_entities(query: str, entity_type: str = "", limit: int = 10) -> str:
    """
    Search Brain entities by keyword and/or semantic similarity.

    Args:
        query: Search query (natural language)
        entity_type: Optional filter by entity type (e.g., "project", "person", "system")
        limit: Maximum results to return (default: 10)

    Returns:
        Formatted list of matching entities with ID, name, type, status, confidence, snippet.
    """
    try:
        brain_path = _get_brain_path()

        # Add brain tools to path for search modules
        brain_tools = brain_path.parent.parent / "common" / "tools" / "brain"
        if brain_tools.exists():
            sys.path.insert(0, str(brain_tools))

        results = []

        # Try semantic search first (if available)
        try:
            from index.vector_index import BrainVectorIndex, VECTOR_AVAILABLE
            if VECTOR_AVAILABLE:
                idx = BrainVectorIndex(brain_path)
                vector_results = idx.query(
                    query,
                    top_k=limit,
                    entity_type=entity_type or None,
                )
                for vr in vector_results:
                    results.append(
                        f"[{vr['score']:.3f}] {vr['metadata'].get('name', vr['entity_id'])}\n"
                        f"  ID: {vr['entity_id']}\n"
                        f"  Type: {vr['metadata'].get('entity_type', '?')} | "
                        f"Status: {vr['metadata'].get('entity_status', '?')} | "
                        f"Confidence: {vr['metadata'].get('confidence', 0.0)}\n"
                        f"  Path: {vr.get('entity_path', '')}\n"
                        f"  Snippet: {vr.get('snippet', '')[:120]}..."
                    )
        except ImportError:
            pass

        # Fall back to keyword search if no vector results
        if not results:
            try:
                from index.brain_search import BrainSearch
                bs = BrainSearch(brain_path=brain_path)
                keyword_results = bs.search(query, limit=limit)
                for kr in keyword_results:
                    results.append(
                        f"[{kr.score:.3f}] {kr.entity_id}\n"
                        f"  Source: {kr.source}\n"
                        f"  Reasons: {', '.join(kr.match_reasons[:3])}\n"
                        f"  Path: {kr.file_path or 'N/A'}"
                    )
            except ImportError:
                # Direct file scan fallback
                results.append("Keyword search unavailable -- install brain tools")

        if not results:
            return f"No entities found for query: {query}"

        response = (
            f"Search results for '{query}' ({len(results)} matches):\n\n"
            + "\n\n".join(results)
        )
        return _truncate_response(response)

    except Exception as e:
        return f"Error searching entities: {str(e)}"


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
def get_entity(entity_id: str) -> str:
    """
    Get full details of a specific Brain entity.

    Args:
        entity_id: The entity's $id (e.g., "entity/project/good-chop")

    Returns:
        Full entity data: frontmatter fields + body content.
    """
    try:
        brain_path = _get_brain_path()

        # Search for entity file by $id
        for md_file in brain_path.rglob("*.md"):
            if md_file.name in ("BRAIN.md", "README.md"):
                continue
            if any(
                d in md_file.parts
                for d in ("Inbox", "Archive", "__pycache__", ".vector_index")
            ):
                continue

            data = _load_entity_file(md_file)
            if not data:
                continue

            file_id = data.get("$id", "")
            if file_id == entity_id:
                output_parts = [f"Entity: {entity_id}", f"File: {md_file}", "=" * 60]

                # Frontmatter fields (excluding internal)
                output_parts.append("## Frontmatter")
                for key, value in data.items():
                    if key.startswith("_"):
                        continue
                    if isinstance(value, (list, dict)):
                        output_parts.append(
                            f"{key}: {json.dumps(value, indent=2, default=str)}"
                        )
                    else:
                        output_parts.append(f"{key}: {value}")

                # Body
                body = data.get("_body", "")
                if body:
                    output_parts.append("")
                    output_parts.append("## Body")
                    output_parts.append(body[:MAX_BODY_CHARS])
                    if len(body) > MAX_BODY_CHARS:
                        output_parts.append(
                            f"\n... ({len(body)} chars total, truncated)"
                        )

                response = "\n".join(output_parts)
                return _truncate_response(response)

        return f"Entity not found: {entity_id}"

    except Exception as e:
        return f"Error fetching entity {entity_id}: {str(e)}"


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
def query_knowledge(question: str) -> str:
    """
    Query the Brain knowledge graph with a natural language question.

    Uses vector search (if available) combined with keyword search to find
    relevant entities, then synthesizes a response with source references.

    Args:
        question: Natural language question about the knowledge base

    Returns:
        Answer with relevant entity references and source paths.
    """
    try:
        brain_path = _get_brain_path()
        brain_tools = brain_path.parent.parent / "common" / "tools" / "brain"
        if brain_tools.exists():
            sys.path.insert(0, str(brain_tools))

        all_findings = []

        # Vector search
        try:
            from index.vector_index import BrainVectorIndex, VECTOR_AVAILABLE
            if VECTOR_AVAILABLE:
                idx = BrainVectorIndex(brain_path)
                vector_results = idx.query(question, top_k=5)
                for vr in vector_results:
                    all_findings.append({
                        "source": "semantic",
                        "score": vr["score"],
                        "entity_id": vr["entity_id"],
                        "name": vr["metadata"].get("name", vr["entity_id"]),
                        "type": vr["metadata"].get("entity_type", "unknown"),
                        "snippet": vr.get("snippet", "")[:200],
                        "path": vr.get("entity_path", ""),
                    })
        except ImportError:
            pass

        # Keyword search
        try:
            from index.brain_search import BrainSearch
            bs = BrainSearch(brain_path=brain_path)
            keyword_results = bs.search(question, limit=5)
            for kr in keyword_results:
                # Avoid duplicates
                if not any(f["entity_id"] == kr.entity_id for f in all_findings):
                    all_findings.append({
                        "source": "keyword",
                        "score": kr.score,
                        "entity_id": kr.entity_id,
                        "name": kr.entity_id,
                        "type": "unknown",
                        "snippet": ", ".join(kr.match_reasons[:2]),
                        "path": kr.file_path or "",
                    })
        except ImportError:
            pass

        if not all_findings:
            return f"No relevant knowledge found for: {question}"

        # Sort by score
        all_findings.sort(key=lambda f: -f["score"])

        # Build response
        output_parts = [
            f"Knowledge query: {question}",
            f"Found {len(all_findings)} relevant entities:",
            "",
        ]

        for i, finding in enumerate(all_findings, 1):
            output_parts.append(
                f"{i}. [{finding['source']}] {finding['name']} "
                f"(score: {finding['score']:.3f}, type: {finding['type']})"
            )
            if finding.get("snippet"):
                output_parts.append(f"   {finding['snippet'][:150]}")
            if finding.get("path"):
                output_parts.append(f"   Path: {finding['path']}")
            output_parts.append("")

        output_parts.append(
            "Use get_entity(<entity_id>) to read the full content of any entity."
        )

        response = "\n".join(output_parts)
        return _truncate_response(response)

    except Exception as e:
        return f"Error querying knowledge: {str(e)}"


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
def get_relationships(entity_id: str) -> str:
    """
    Get all relationships for a Brain entity.

    Args:
        entity_id: The entity's $id (e.g., "entity/project/good-chop")

    Returns:
        List of relationships with target names, types, and confidence.
    """
    try:
        brain_path = _get_brain_path()

        for md_file in brain_path.rglob("*.md"):
            if md_file.name in ("BRAIN.md", "README.md"):
                continue
            if any(
                d in md_file.parts
                for d in ("Inbox", "Archive", "__pycache__", ".vector_index")
            ):
                continue

            data = _load_entity_file(md_file)
            if not data:
                continue

            if data.get("$id") != entity_id:
                continue

            relationships = data.get("$relationships", [])
            if not relationships:
                return f"Entity {entity_id} has no relationships."

            output_parts = [
                f"Relationships for: {entity_id}",
                f"Total: {len(relationships)}",
                "-" * 50,
            ]

            for rel in relationships:
                if not isinstance(rel, dict):
                    continue
                rel_type = rel.get("type", "unknown")
                target = rel.get("target", "unknown")
                confidence = rel.get("confidence", 0.0)
                source = rel.get("source", "unknown")
                verified = rel.get("last_verified", "N/A")

                output_parts.append(
                    f"  --[{rel_type}]--> {target}\n"
                    f"    Confidence: {confidence} | Source: {source} | Verified: {verified}"
                )

            response = "\n".join(output_parts)
            return _truncate_response(response)

        return f"Entity not found: {entity_id}"

    except Exception as e:
        return f"Error fetching relationships for {entity_id}: {str(e)}"


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
def list_entities(entity_type: str = "", status: str = "", limit: int = 20) -> str:
    """
    List Brain entities with optional filters.

    Args:
        entity_type: Filter by type (e.g., "project", "person", "system")
        status: Filter by status (e.g., "active", "archived")
        limit: Maximum results (default: 20)

    Returns:
        Paginated list of entities sorted by last update time.
    """
    try:
        brain_path = _get_brain_path()
        entities = []

        exclude_dirs = {
            "Inbox", "Archive", "__pycache__", ".snapshots", ".schema", ".vector_index"
        }
        exclude_files = {"BRAIN.md", "README.md", "index.md", "_index.md"}

        for md_file in brain_path.rglob("*.md"):
            if md_file.name in exclude_files:
                continue
            if any(d in md_file.parts for d in exclude_dirs):
                continue

            data = _load_entity_file(md_file)
            if not data:
                continue

            etype = data.get("$type", "unknown")
            estatus = data.get("$status", "unknown")

            # Apply filters
            if entity_type and etype != entity_type:
                continue
            if status and estatus != status:
                continue

            entities.append({
                "id": data.get("$id", str(md_file.relative_to(brain_path))),
                "name": data.get("name", data.get("_name", md_file.stem)),
                "type": etype,
                "status": estatus,
                "confidence": data.get("$confidence", 0.0),
                "updated": str(data.get("$updated", "N/A")),
                "path": str(md_file),
            })

        # Sort by update time (newest first)
        entities.sort(key=lambda e: e.get("updated", ""), reverse=True)

        # Apply limit
        entities = entities[:limit]

        if not entities:
            filters = []
            if entity_type:
                filters.append(f"type={entity_type}")
            if status:
                filters.append(f"status={status}")
            filter_str = f" (filters: {', '.join(filters)})" if filters else ""
            return f"No entities found{filter_str}"

        output_parts = [
            f"Brain entities ({len(entities)} shown):",
            "",
        ]

        for e in entities:
            output_parts.append(
                f"  {e['id']}\n"
                f"    Name: {e['name']} | Type: {e['type']} | "
                f"Status: {e['status']} | Confidence: {e['confidence']}\n"
                f"    Updated: {e['updated']}"
            )

        response = "\n".join(output_parts)
        return _truncate_response(response)

    except Exception as e:
        return f"Error listing entities: {str(e)}"


# ---------------------------------------------------------------------------
# CLI & Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli_commands = {
        "search_entities", "get_entity", "query_knowledge",
        "get_relationships", "list_entities",
    }

    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        sys.argv.pop(1)
        parser = argparse.ArgumentParser(description="Brain MCP Server CLI")
        subparsers = parser.add_subparsers(dest="command", required=True)

        p_search = subparsers.add_parser("search_entities")
        p_search.add_argument("query", help="Search query")
        p_search.add_argument("--type", default="", help="Entity type filter")
        p_search.add_argument("--limit", type=int, default=10)

        p_get = subparsers.add_parser("get_entity")
        p_get.add_argument("entity_id", help="Entity $id")

        p_query = subparsers.add_parser("query_knowledge")
        p_query.add_argument("question", help="Natural language question")

        p_rels = subparsers.add_parser("get_relationships")
        p_rels.add_argument("entity_id", help="Entity $id")

        p_list = subparsers.add_parser("list_entities")
        p_list.add_argument("--type", default="", help="Entity type filter")
        p_list.add_argument("--status", default="", help="Status filter")
        p_list.add_argument("--limit", type=int, default=20)

        args = parser.parse_args()

        if args.command == "search_entities":
            print(search_entities(args.query, entity_type=args.type, limit=args.limit))
        elif args.command == "get_entity":
            print(get_entity(args.entity_id))
        elif args.command == "query_knowledge":
            print(query_knowledge(args.question))
        elif args.command == "get_relationships":
            print(get_relationships(args.entity_id))
        elif args.command == "list_entities":
            print(
                list_entities(
                    entity_type=args.type, status=args.status, limit=args.limit
                )
            )
    else:
        # Transport selection: stdio (default) or streamable-http (Cowork)
        transport = os.environ.get("MCP_TRANSPORT", "stdio")
        if transport in ("http", "streamable-http"):
            mcp.run(
                transport="streamable-http",
                host="127.0.0.1",
                port=int(os.environ.get("MCP_PORT", "8741")),
            )
        else:
            mcp.run()  # Default: stdin/stdout for CLI
