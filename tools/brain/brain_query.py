#!/usr/bin/env python3
"""
Brain Query - Unified BRAIN+GRAPH Query Interface

Main entry point for querying the PM-OS Brain knowledge base.
Combines keyword search (BRAIN) with graph traversal (GRAPH).

Based on TKS research findings:
- BRAIN (keyword): Quality Score 0.612
- GRAPH (1-hop neighbors): Quality Score 0.465
- Combined approach outperforms either alone

Usage:
    python brain_query.py "query string"
    python brain_query.py "OTP launch" --no-graph
    python brain_query.py "Growth Platform" --format json --limit 5
"""

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader
from brain_graph import BrainGraph
from brain_search import BrainSearch, SearchResult

# --- Configuration ---
ROOT_PATH = config_loader.get_root_path()
USER_PATH = ROOT_PATH / "user"
BRAIN_DIR = USER_PATH / "brain"


@dataclass
class QueryResult:
    """Result of a BRAIN+GRAPH query."""

    query: str
    results: List[SearchResult]
    seed_count: int
    graph_expanded: bool
    warnings: List[str]
    latency_ms: float

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "query": self.query,
            "results": [
                {
                    "entity_id": r.entity_id,
                    "score": round(r.score, 3),
                    "source": r.source,
                    "match_reasons": r.match_reasons,
                    "via": r.via,
                    "relationship_type": r.relationship_type,
                }
                for r in self.results
            ],
            "seed_count": self.seed_count,
            "graph_expanded": self.graph_expanded,
            "warnings": self.warnings,
            "latency_ms": round(self.latency_ms, 2),
        }


class BrainQuery:
    """
    Unified BRAIN+GRAPH query interface.

    Orchestrates keyword search and graph expansion to find relevant entities.
    """

    def __init__(self, brain_path: Optional[Path] = None):
        """
        Initialize the query system.

        Args:
            brain_path: Path to brain directory (defaults to user/brain)
        """
        self.brain_path = Path(brain_path) if brain_path else BRAIN_DIR

        # Initialize components (lazy loading for speed)
        self._search: Optional[BrainSearch] = None
        self._graph: Optional[BrainGraph] = None

    @property
    def search(self) -> BrainSearch:
        """Lazy-load search component."""
        if self._search is None:
            self._search = BrainSearch(self.brain_path)
        return self._search

    @property
    def graph(self) -> BrainGraph:
        """Lazy-load graph component."""
        if self._graph is None:
            self._graph = BrainGraph(self.brain_path)
        return self._graph

    def query(
        self,
        query: str,
        limit: int = 10,
        use_graph: bool = True,
        graph_decay: float = 0.5,
        graph_depth: int = 1,
    ) -> QueryResult:
        """
        Execute a BRAIN+GRAPH query.

        Args:
            query: Natural language search query
            limit: Maximum results to return
            use_graph: Whether to expand via graph (default True)
            graph_decay: Decay factor for graph neighbors (default 0.5)
            graph_depth: Graph traversal depth (default 1)

        Returns:
            QueryResult with ranked entities
        """
        start = time.time()
        warnings = []

        # Phase 1: BRAIN search (keyword matching)
        # Get more seeds than limit to have good candidates for graph expansion
        seed_limit = limit * 2 if use_graph else limit
        seeds = self.search.search(query, limit=seed_limit)

        # Phase 2: GRAPH expansion (optional)
        all_results = list(seeds)

        if use_graph and seeds:
            neighbors = self.graph.expand(
                seeds[:limit],  # Only expand top seeds
                decay=graph_decay,
                depth=graph_depth,
            )
            warnings.extend(self.graph.warnings)

            # Merge seeds and neighbors
            all_results = self._merge_and_rank(seeds, neighbors)

        # Sort by score
        all_results.sort(key=lambda r: -r.score)

        latency_ms = (time.time() - start) * 1000

        return QueryResult(
            query=query,
            results=all_results[:limit],
            seed_count=len(seeds),
            graph_expanded=use_graph and len(seeds) > 0,
            warnings=warnings,
            latency_ms=latency_ms,
        )

    def _merge_and_rank(
        self, seeds: List[SearchResult], neighbors: List[SearchResult]
    ) -> List[SearchResult]:
        """
        Merge seeds and neighbors, max score wins on collision.

        Args:
            seeds: Results from BRAIN search
            neighbors: Results from GRAPH expansion

        Returns:
            Merged and deduplicated results
        """
        merged: Dict[str, SearchResult] = {}

        # Add seeds first (typically higher scores)
        for r in seeds:
            merged[r.entity_id] = r

        # Merge neighbors
        for n in neighbors:
            if n.entity_id not in merged:
                merged[n.entity_id] = n
            else:
                existing = merged[n.entity_id]
                # Keep max score
                if n.score > existing.score:
                    existing.score = n.score
                    existing.source = "brain+graph"
                # Combine match reasons (but don't duplicate)
                for reason in n.match_reasons:
                    if reason not in existing.match_reasons:
                        existing.match_reasons.append(reason)

        return list(merged.values())

    def get_entity_context(
        self, entity_id: str, include_neighbors: bool = True
    ) -> Dict[str, Any]:
        """
        Get full context for a specific entity.

        Args:
            entity_id: Entity to get context for
            include_neighbors: Whether to include neighbor entities

        Returns:
            Dict with entity content and optionally neighbors
        """
        context = {"entity_id": entity_id, "relationships": [], "neighbors": []}

        # Get relationships
        relationships = self.graph.get_relationships(entity_id)
        context["relationships"] = relationships

        if include_neighbors:
            # Create dummy seed and expand
            seed = SearchResult(entity_id=entity_id, score=1.0, source="direct")
            neighbors = self.graph.expand([seed], decay=0.5, depth=1)
            context["neighbors"] = [
                {"entity_id": n.entity_id, "via_type": n.relationship_type}
                for n in neighbors
            ]

        return context


def format_text_output(result: QueryResult) -> str:
    """Format query result as human-readable text."""
    lines = []
    lines.append(f"Query: {result.query}")
    lines.append(f"Results: {len(result.results)} (from {result.seed_count} seeds)")
    lines.append(f"Graph: {'expanded' if result.graph_expanded else 'disabled'}")
    lines.append(f"Latency: {result.latency_ms:.1f}ms")
    lines.append("-" * 60)

    for r in result.results:
        source_icon = {
            "alias": "A",
            "content": "C",
            "graph": "G",
            "brain+graph": "B+G",
        }.get(r.source, "?")
        lines.append(f"[{source_icon}] {r.score:.2f} | {r.entity_id}")

        if r.match_reasons:
            reason_str = ", ".join(r.match_reasons[:2])
            if len(r.match_reasons) > 2:
                reason_str += f" (+{len(r.match_reasons)-2} more)"
            lines.append(f"         {reason_str}")

    if result.warnings:
        lines.append("")
        lines.append(f"Warnings ({len(result.warnings)}):")
        for w in result.warnings[:3]:
            lines.append(f"  - {w}")
        if len(result.warnings) > 3:
            lines.append(f"  ... and {len(result.warnings)-3} more")

    return "\n".join(lines)


def format_markdown_output(result: QueryResult) -> str:
    """Format query result as markdown."""
    lines = []
    lines.append(f"## Query: {result.query}")
    lines.append("")
    lines.append(
        f"**Results:** {len(result.results)} | **Seeds:** {result.seed_count} | **Latency:** {result.latency_ms:.1f}ms"
    )
    lines.append("")
    lines.append("| Score | Entity | Source | Match |")
    lines.append("|-------|--------|--------|-------|")

    for r in result.results:
        reason = r.match_reasons[0] if r.match_reasons else "-"
        lines.append(f"| {r.score:.2f} | {r.entity_id} | {r.source} | {reason} |")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="BRAIN+GRAPH Query Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python brain_query.py "OTP launch"
  python brain_query.py "Growth Platform" --no-graph
  python brain_query.py "squad cart" --format json
  python brain_query.py "jane" --limit 5 --decay 0.3
        """,
    )

    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument(
        "--limit", "-l", type=int, default=10, help="Max results (default: 10)"
    )
    parser.add_argument(
        "--no-graph", action="store_true", help="Disable graph expansion (BRAIN only)"
    )
    parser.add_argument(
        "--decay",
        "-d",
        type=float,
        default=0.5,
        help="Graph decay factor (default: 0.5)",
    )
    parser.add_argument(
        "--depth", type=int, default=1, help="Graph traversal depth (default: 1)"
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format",
    )
    parser.add_argument("--brain-path", type=str, help="Path to brain directory")

    args = parser.parse_args()

    if not args.query:
        parser.print_help()
        return

    # Initialize query system
    brain_path = Path(args.brain_path) if args.brain_path else None
    bq = BrainQuery(brain_path)

    # Execute query
    result = bq.query(
        args.query,
        limit=args.limit,
        use_graph=not args.no_graph,
        graph_decay=args.decay,
        graph_depth=args.depth,
    )

    # Format output
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2))
    elif args.format == "markdown":
        print(format_markdown_output(result))
    else:
        print(format_text_output(result))


if __name__ == "__main__":
    main()
