#!/usr/bin/env python3
"""
PM-OS Brain Embedding-Based Edge Inferrer (v5.0)

Infers 'similar_to' relationships from embedding similarity
to increase graph density.

Usage:
    from pm_os_brain.tools.relationships.embedding_edge_inferrer import EmbeddingEdgeInferrer
"""

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

# Atomic writes (graceful fallback if unavailable)
try:
    from pm_os_brain.tools.relationships.safe_write import atomic_write
except ImportError:
    try:
        from brain_core.safe_write import atomic_write
    except ImportError:
        def atomic_write(p, c, **kw):
            Path(p).write_text(c, encoding=kw.get("encoding", "utf-8"))

# Event sourcing (graceful fallback if unavailable)
try:
    from pm_os_brain.tools.brain_core.event_helpers import EventHelper
    _EVENT_SOURCING = True
except ImportError:
    try:
        from temporal.event_helpers import EventHelper
        _EVENT_SOURCING = True
    except ImportError:
        _EVENT_SOURCING = False

# Optional: sentence-transformers for embeddings
try:
    import numpy as np
    from sentence_transformers import SentenceTransformer

    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False

# Optional: ChromaDB for ANN (Approximate Nearest Neighbor)
try:
    import chromadb
    _ANN_AVAILABLE = True
except ImportError:
    _ANN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class InferredEdge:
    """A potential relationship inferred from embedding similarity."""

    source_id: str
    target_id: str
    similarity: float
    source_type: str
    target_type: str


@dataclass
class EdgeInferenceReport:
    """Report of inferred edges."""

    entities_processed: int
    edges_inferred: int
    edges_applied: int
    avg_similarity: float
    edges_by_type_pair: Dict[str, int] = field(default_factory=dict)
    edges: List[InferredEdge] = field(default_factory=list)
    used_ann: bool = False


class EmbeddingEdgeInferrer:
    """
    Infers 'similar_to' relationships from embedding similarity.

    Soft edges increase graph density and enable discovery of
    non-obvious relationships.
    """

    DEFAULT_MODEL = "all-MiniLM-L6-v2"  # Fast, 384d embeddings
    DEFAULT_THRESHOLD = 0.75

    def __init__(
        self,
        brain_path: Path,
        model_name: str = DEFAULT_MODEL,
        threshold: float = DEFAULT_THRESHOLD,
        cache=None,
    ):
        """
        Initialize the edge inferrer.

        Args:
            brain_path: Path to brain directory
            model_name: sentence-transformers model name
            threshold: Similarity threshold for edge creation
            cache: Optional EntityCache instance
        """
        self.brain_path = brain_path
        self.model_name = model_name
        self.threshold = threshold
        self._model = None
        self._embeddings_cache: Dict[str, Any] = {}
        self._entity_cache = cache

    def _get_model(self):
        """Lazy-load the embedding model, preferring local cache to avoid network latency."""
        if not EMBEDDINGS_AVAILABLE:
            raise ImportError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
        if self._model is None:
            try:
                self._model = SentenceTransformer(self.model_name, local_files_only=True)
            except Exception:
                # First run or cache miss -- download from HuggingFace
                self._model = SentenceTransformer(self.model_name)
        return self._model

    def scan_for_edges(
        self,
        entity_type: Optional[str] = None,
        limit: int = 100,
    ) -> EdgeInferenceReport:
        """
        Scan entities and find potential similar_to edges.

        Uses ANN (ChromaDB) when available and PMOS_ENRICH_ANN != "0",
        otherwise falls back to brute-force O(n^2) comparison.

        Args:
            entity_type: Filter by entity type
            limit: Max edges to return

        Returns:
            EdgeInferenceReport with potential edges
        """
        use_ann = (
            _ANN_AVAILABLE
            and EMBEDDINGS_AVAILABLE
            and os.environ.get("PMOS_ENRICH_ANN", "1") != "0"
        )

        # Load entities
        entities = self._load_entities(entity_type)

        if len(entities) < 2:
            return EdgeInferenceReport(
                entities_processed=len(entities),
                edges_inferred=0,
                edges_applied=0,
                avg_similarity=0.0,
            )

        # Get embeddings
        entity_ids = list(entities.keys())
        contents = [self._get_entity_content(entities[eid]) for eid in entity_ids]

        if EMBEDDINGS_AVAILABLE:
            model = self._get_model()
            embeddings = model.encode(contents, normalize_embeddings=True)
        else:
            embeddings = None

        # Choose scan strategy
        used_ann = False
        if use_ann and embeddings is not None and len(entity_ids) >= 20:
            inferred_edges, edges_by_type_pair, similarity_sum = (
                self._ann_scan(entities, entity_ids, embeddings, limit)
            )
            used_ann = True
        else:
            inferred_edges, edges_by_type_pair, similarity_sum = (
                self._bruteforce_scan(
                    entities, entity_ids, contents, embeddings, limit
                )
            )

        # Sort by similarity
        inferred_edges.sort(key=lambda e: -e.similarity)

        avg_sim = similarity_sum / len(inferred_edges) if inferred_edges else 0.0

        return EdgeInferenceReport(
            entities_processed=len(entities),
            edges_inferred=len(inferred_edges),
            edges_applied=0,
            avg_similarity=round(avg_sim, 4),
            edges_by_type_pair=edges_by_type_pair,
            edges=inferred_edges,
            used_ann=used_ann,
        )

    def _ann_scan(
        self,
        entities: Dict[str, Dict[str, Any]],
        entity_ids: List[str],
        embeddings: Any,
        limit: int,
    ) -> Tuple[List[InferredEdge], Dict[str, int], float]:
        """ANN scan using ChromaDB ephemeral collection.

        Collects ALL candidate edges from k-NN queries, then returns
        the top-N by similarity to avoid positional bias.
        """
        all_edges: List[InferredEdge] = []
        seen_pairs: set = set()

        # Create ephemeral ChromaDB collection
        client = chromadb.Client()
        collection = client.create_collection(
            name="edge_scan",
            metadata={"hnsw:space": "cosine"},
        )

        # Add all embeddings
        collection.add(
            ids=entity_ids,
            embeddings=[e.tolist() for e in embeddings],
        )

        # Query each entity for nearest neighbors
        k = min(20, len(entity_ids) - 1)
        results = collection.query(
            query_embeddings=[e.tolist() for e in embeddings],
            n_results=k + 1,  # +1 because self-match
        )

        for i, eid_i in enumerate(entity_ids):
            neighbors = results["ids"][i]
            distances = results["distances"][i]

            for j, (eid_j, dist) in enumerate(zip(neighbors, distances)):
                if eid_j == eid_i:
                    continue

                # Cosine distance -> cosine similarity
                sim = 1.0 - dist

                if sim < self.threshold:
                    continue

                # Dedup: only count each pair once
                pair_key = tuple(sorted([eid_i, eid_j]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # Skip if already related
                if eid_i in entities and self._already_related(entities[eid_i], eid_j):
                    continue
                if eid_j in entities and self._already_related(entities[eid_j], eid_i):
                    continue

                type_i = entities.get(eid_i, {}).get("$type", "unknown")
                type_j = entities.get(eid_j, {}).get("$type", "unknown")

                all_edges.append(InferredEdge(
                    source_id=eid_i,
                    target_id=eid_j,
                    similarity=round(sim, 4),
                    source_type=type_i,
                    target_type=type_j,
                ))

        # Cleanup ephemeral collection
        try:
            client.delete_collection("edge_scan")
        except Exception:
            pass

        # Sort by similarity descending, take top-N
        all_edges.sort(key=lambda e: -e.similarity)
        inferred_edges = all_edges[:limit]

        # Build summary stats from the returned edges
        edges_by_type_pair: Dict[str, int] = {}
        similarity_sum = 0.0
        for edge in inferred_edges:
            similarity_sum += edge.similarity
            type_pair = f"{edge.source_type}-{edge.target_type}"
            edges_by_type_pair[type_pair] = (
                edges_by_type_pair.get(type_pair, 0) + 1
            )

        return inferred_edges, edges_by_type_pair, similarity_sum

    def _bruteforce_scan(
        self,
        entities: Dict[str, Dict[str, Any]],
        entity_ids: List[str],
        contents: List[str],
        embeddings: Any,
        limit: int,
    ) -> Tuple[List[InferredEdge], Dict[str, int], float]:
        """Brute-force O(n^2) pairwise similarity scan.

        Collects ALL edges above threshold, then returns the top-N by
        similarity. This avoids positional bias where early entities
        in the list would dominate the result set.
        """
        all_edges: List[InferredEdge] = []

        for i in range(len(entity_ids)):
            for j in range(i + 1, len(entity_ids)):
                eid_i = entity_ids[i]
                eid_j = entity_ids[j]

                # Skip if already related
                if self._already_related(entities[eid_i], eid_j):
                    continue
                if self._already_related(entities[eid_j], eid_i):
                    continue

                # Compute similarity
                if embeddings is not None:
                    sim = float(np.dot(embeddings[i], embeddings[j]))
                else:
                    sim = self._jaccard_similarity(contents[i], contents[j])

                if sim >= self.threshold:
                    type_i = entities[eid_i].get("$type", "unknown")
                    type_j = entities[eid_j].get("$type", "unknown")

                    all_edges.append(InferredEdge(
                        source_id=eid_i,
                        target_id=eid_j,
                        similarity=round(sim, 4),
                        source_type=type_i,
                        target_type=type_j,
                    ))

        # Sort by similarity descending, take top-N
        all_edges.sort(key=lambda e: -e.similarity)
        inferred_edges = all_edges[:limit]

        # Build summary stats from the returned edges
        edges_by_type_pair: Dict[str, int] = {}
        similarity_sum = 0.0
        for edge in inferred_edges:
            similarity_sum += edge.similarity
            type_pair = f"{edge.source_type}-{edge.target_type}"
            edges_by_type_pair[type_pair] = (
                edges_by_type_pair.get(type_pair, 0) + 1
            )

        return inferred_edges, edges_by_type_pair, similarity_sum

    def apply_edges(
        self,
        edges: List[InferredEdge],
        dry_run: bool = False,
    ) -> int:
        """
        Apply inferred edges to entity files.

        Args:
            edges: List of edges to apply
            dry_run: If True, don't actually modify files

        Returns:
            Number of edges applied
        """
        applied = 0
        entities = self._load_entities()

        for edge in edges:
            if edge.source_id not in entities:
                continue

            # Find source entity file
            source_path = self._find_entity_file(edge.source_id)
            if not source_path:
                continue

            try:
                content = source_path.read_text(encoding="utf-8")
                frontmatter, body = self._parse_content(content)

                if not frontmatter:
                    continue

                # Add relationship
                relationships = frontmatter.get("$relationships", [])

                new_rel = {
                    "type": "similar_to",
                    "target": edge.target_id,
                    "confidence": edge.similarity,
                    "source": "auto_embedding",
                    "last_verified": date.today().isoformat(),
                    "metadata": {
                        "model": self.model_name,
                        "threshold": self.threshold,
                    },
                }

                relationships.append(new_rel)
                frontmatter["$relationships"] = relationships

                # Event sourcing: record the relationship addition
                if _EVENT_SOURCING:
                    event = EventHelper.create_relationship_event(
                        actor="enrichment/embedding",
                        target=edge.target_id,
                        rel_type="similar_to",
                        operation="add",
                        source="auto_embedding",
                        message=(
                            f"Inferred similar_to edge "
                            f"(similarity={edge.similarity}, "
                            f"model={self.model_name})"
                        ),
                    )
                    EventHelper.append_to_frontmatter(frontmatter, event)

                if not dry_run:
                    # Write back (atomic for crash safety)
                    new_content = self._format_content(frontmatter, body)
                    atomic_write(source_path, new_content)

                applied += 1

            except Exception as e:
                logger.error("Error applying edge to %s: %s", edge.source_id, e)
                continue

        return applied

    def _load_entities(
        self,
        entity_type: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Load entities -- from cache if available, otherwise scan files."""
        if self._entity_cache is not None:
            if entity_type:
                return dict(self._entity_cache.get_by_type(entity_type))
            return dict(self._entity_cache.get_all())

        # Fallback: scan files directly
        entities = {}
        entity_files = list(self.brain_path.rglob("*.md"))
        entity_files = [
            f
            for f in entity_files
            if f.name.lower() not in ("readme.md", "index.md", "_index.md")
            and ".snapshots" not in str(f)
            and ".schema" not in str(f)
        ]

        for entity_path in entity_files:
            try:
                content = entity_path.read_text(encoding="utf-8")
                frontmatter, body = self._parse_content(content)

                if not frontmatter:
                    continue

                eid = frontmatter.get(
                    "$id", str(entity_path.relative_to(self.brain_path))
                )
                etype = frontmatter.get("$type", "unknown")

                if entity_type and etype != entity_type:
                    continue

                frontmatter["_body"] = body
                frontmatter["_path"] = entity_path
                entities[eid] = frontmatter

            except Exception:
                continue

        return entities

    def _get_entity_content(self, entity: Dict[str, Any]) -> str:
        """Extract content string for embedding."""
        parts = []

        # Name/title
        name = entity.get("name")
        if name:
            parts.append(str(name))

        # Description
        description = entity.get("description")
        if description:
            parts.append(str(description))

        # Body content
        body = entity.get("_body", "")
        if body:
            # Take first 500 chars of body
            parts.append(body[:500].strip())

        # Tags
        tags = entity.get("$tags")
        if tags:
            parts.append(" ".join(str(t) for t in tags))

        return " ".join(parts)

    def _already_related(
        self,
        entity: Dict[str, Any],
        target_id: str,
    ) -> bool:
        """Check if entities are already related."""
        relationships = entity.get("$relationships", [])
        for rel in relationships:
            if isinstance(rel, dict) and rel.get("target") == target_id:
                return True
        return False

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """Simple Jaccard similarity fallback."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _find_entity_file(self, entity_id: str) -> Optional[Path]:
        """Find the file path for an entity ID."""
        for entity_path in self.brain_path.rglob("*.md"):
            try:
                content = entity_path.read_text(encoding="utf-8")
                frontmatter, _ = self._parse_content(content)
                if frontmatter.get("$id") == entity_id:
                    return entity_path
            except Exception:
                continue
        return None

    def _parse_content(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter from content."""
        if not content.startswith("---"):
            return {}, content

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content

        try:
            frontmatter = yaml.safe_load(parts[1]) or {}
            return frontmatter, parts[2]
        except yaml.YAMLError:
            return {}, content

    def _format_content(
        self,
        frontmatter: Dict[str, Any],
        body: str,
    ) -> str:
        """Format frontmatter and body back to markdown."""
        # Remove internal fields
        fm_copy = {k: v for k, v in frontmatter.items() if not k.startswith("_")}
        yaml_str = yaml.dump(
            fm_copy, default_flow_style=False, allow_unicode=True, sort_keys=False
        )
        return f"---\n{yaml_str}---{body}"


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Infer similar_to relationships from embedding similarity"
    )
    parser.add_argument(
        "action",
        choices=["scan", "apply"],
        nargs="?",
        default="scan",
        help="Action to perform",
    )
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        help="Similarity threshold (default: 0.75)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="all-MiniLM-L6-v2",
        help="Embedding model name",
    )
    parser.add_argument(
        "--type",
        type=str,
        help="Filter by entity type",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Max edges to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without applying changes",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )

    args = parser.parse_args()

    if not EMBEDDINGS_AVAILABLE:
        logger.warning(
            "sentence-transformers not installed. Using fallback similarity. "
            "For better results: pip install sentence-transformers"
        )

    # Resolve brain path
    if not args.brain_path:
        try:
            paths = get_paths()
            args.brain_path = paths.user / "brain"
        except Exception:
            args.brain_path = Path.cwd() / "user" / "brain"

    inferrer = EmbeddingEdgeInferrer(
        args.brain_path,
        model_name=args.model,
        threshold=args.threshold,
    )

    if args.action == "scan":
        report = inferrer.scan_for_edges(
            entity_type=args.type,
            limit=args.limit,
        )

        if args.output == "json":
            output = {
                "entities_processed": report.entities_processed,
                "edges_inferred": report.edges_inferred,
                "avg_similarity": report.avg_similarity,
                "threshold": args.threshold,
                "edges_by_type_pair": report.edges_by_type_pair,
                "edges": [
                    {
                        "source_id": e.source_id,
                        "target_id": e.target_id,
                        "similarity": e.similarity,
                    }
                    for e in report.edges[:50]
                ],
            }
            print(json.dumps(output, indent=2))
        else:
            print("Embedding Edge Inference Scan")
            print("=" * 60)
            print(f"Model: {args.model}")
            print(f"Threshold: {args.threshold}")
            print(f"Entities processed: {report.entities_processed}")
            print(f"Edges inferred: {report.edges_inferred}")
            print(f"Avg similarity: {report.avg_similarity:.4f}")
            print()

            if report.edges_by_type_pair:
                print("Edges by type pair:")
                for pair, count in sorted(
                    report.edges_by_type_pair.items(), key=lambda x: -x[1]
                ):
                    print(f"  {pair}: {count}")
                print()

            print(f"Top {min(20, len(report.edges))} inferred edges:")
            print("-" * 60)
            for edge in report.edges[:20]:
                print(f"  {edge.similarity:.3f} | {edge.source_id}")
                print(f"        -> {edge.target_id}")
                print()

    elif args.action == "apply":
        # First scan
        report = inferrer.scan_for_edges(
            entity_type=args.type,
            limit=args.limit,
        )

        if not report.edges:
            print("No edges to apply")
            return 0

        if args.dry_run:
            print(f"DRY RUN: Would apply {len(report.edges)} edges")
            for edge in report.edges[:10]:
                print(
                    f"  {edge.source_id} --[similar_to]--> {edge.target_id} ({edge.similarity:.3f})"
                )
            return 0

        # Apply edges
        applied = inferrer.apply_edges(report.edges, dry_run=False)
        print(f"Applied {applied} soft edges to entity files")
        print("Edges marked with $source: auto_embedding")

    return 0


if __name__ == "__main__":
    sys.exit(main())
