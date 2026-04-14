#!/usr/bin/env python3
"""
PM-OS Brain Vector Index — ChromaDB-based semantic search for Brain entities.

Provides embedding-powered fuzzy search across Brain entities using
sentence-transformers for encoding and ChromaDB for vector storage.

Usage:
    python3 vector_index.py build              # Build/rebuild full index
    python3 vector_index.py query "search text" # Query the index
    python3 vector_index.py stats              # Show index statistics
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# Standalone support
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent

# v5 imports: config-driven paths
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

# Optional dependencies — graceful degradation if not installed
try:
    import chromadb
    from chromadb.config import Settings

    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

try:
    from sentence_transformers import SentenceTransformer

    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


VECTOR_AVAILABLE = HAS_CHROMADB and HAS_SENTENCE_TRANSFORMERS


def _resolve_brain_dir() -> Path:
    """Resolve brain directory from config/paths, no hardcoded values."""
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
    candidate = PLUGIN_ROOT.parent.parent.parent / "user" / "brain"
    if candidate.exists():
        return candidate
    return Path.cwd() / "user" / "brain"


class BrainVectorIndex:
    """
    ChromaDB-backed vector index for semantic search across Brain entities.

    Embeds entity content (name + body text) using sentence-transformers
    and stores in a persistent ChromaDB collection for fast similarity search.
    """

    DEFAULT_MODEL = "all-MiniLM-L6-v2"
    COLLECTION_NAME = "brain_entities"
    INDEX_DIR_NAME = ".vector_index"
    SCHEMA_VERSION = "5.0"

    # Directories to exclude from indexing
    EXCLUDE_DIRS = {"Inbox", "Archive", "__pycache__", ".snapshots", ".schema"}
    EXCLUDE_FILES = {"BRAIN.md", "README.md", "index.md", "_index.md"}

    def __init__(
        self,
        brain_path: Path,
        model_name: str = DEFAULT_MODEL,
    ):
        """
        Initialize the vector index.

        Args:
            brain_path: Path to user/brain/ directory
            model_name: sentence-transformers model name (default: all-MiniLM-L6-v2)
        """
        if not VECTOR_AVAILABLE:
            missing = []
            if not HAS_CHROMADB:
                missing.append("chromadb")
            if not HAS_SENTENCE_TRANSFORMERS:
                missing.append("sentence-transformers")
            raise ImportError(
                f"Missing dependencies: {', '.join(missing)}. "
                f"Install with: pip install {' '.join(missing)}"
            )

        self.brain_path = Path(brain_path)
        self.model_name = model_name
        self._model = None
        self._client = None
        self._collection = None

        # Index location
        self.index_path = self.brain_path / self.INDEX_DIR_NAME

    @property
    def model(self) -> "SentenceTransformer":
        """Lazy-load the embedding model, preferring local cache to avoid network latency."""
        if self._model is None:
            try:
                self._model = SentenceTransformer(
                    self.model_name, local_files_only=True
                )
            except Exception:
                # First run or cache miss — download from HuggingFace
                self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def client(self) -> "chromadb.ClientAPI":
        """Lazy-load the ChromaDB client with persistent storage."""
        if self._client is None:
            self.index_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(self.index_path),
                settings=Settings(anonymized_telemetry=False),
            )
        return self._client

    @property
    def collection(self) -> "chromadb.Collection":
        """Get or create the brain entities collection, auto-migrating old indexes."""
        if self._collection is None:
            coll = self.client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={
                    "hnsw:space": "cosine",
                    "schema_version": self.SCHEMA_VERSION,
                },
            )
            # Auto-migrate: if existing collection lacks current schema marker, rebuild
            if (
                coll.count() > 0
                and coll.metadata.get("schema_version") != self.SCHEMA_VERSION
            ):
                logger.warning(
                    "Vector index schema outdated (upgrading to v%s), rebuilding...",
                    self.SCHEMA_VERSION,
                )
                try:
                    self.client.delete_collection(self.COLLECTION_NAME)
                except Exception:
                    pass
                coll = self.client.get_or_create_collection(
                    name=self.COLLECTION_NAME,
                    metadata={
                        "hnsw:space": "cosine",
                        "schema_version": self.SCHEMA_VERSION,
                    },
                )
            self._collection = coll
        return self._collection

    def build_index(self) -> Dict[str, Any]:
        """
        Build the full vector index from all Brain entities.

        Scans all markdown files in the brain directory, extracts
        frontmatter metadata and body text, generates embeddings,
        and stores in ChromaDB.

        Returns:
            Dict with build statistics: entities_indexed, errors, duration
        """
        entities = self._scan_entities()

        if not entities:
            return {"entities_indexed": 0, "errors": 0, "message": "No entities found"}

        # Clear existing collection and recreate
        try:
            self.client.delete_collection(self.COLLECTION_NAME)
        except Exception:
            pass
        self._collection = None  # Force recreation

        # Prepare data for batch insert
        ids = []
        documents = []
        metadatas = []

        for entity_id, entity_data in entities.items():
            doc_text = self._build_document_text(entity_data)
            if not doc_text.strip():
                continue

            ids.append(entity_id)
            documents.append(doc_text)
            metadatas.append(self._sanitize_metadata(entity_id, entity_data))

        # Batch embed and insert
        errors = 0
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i : i + batch_size]
            batch_docs = documents[i : i + batch_size]
            batch_meta = metadatas[i : i + batch_size]

            try:
                embeddings = self.model.encode(
                    batch_docs, normalize_embeddings=True
                ).tolist()

                self.collection.add(
                    ids=batch_ids,
                    documents=batch_docs,
                    embeddings=embeddings,
                    metadatas=batch_meta,
                )
            except Exception as e:
                errors += 1
                logger.error("Error indexing batch %d: %s", i // batch_size, e)

        return {
            "entities_indexed": self.collection.count(),
            "total_scanned": len(entities),
            "errors": errors,
        }

    def query(
        self,
        text: str,
        top_k: int = 10,
        entity_type: Optional[str] = None,
        min_confidence: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query the vector index for semantically similar entities.

        Args:
            text: Natural language query text
            top_k: Number of results to return
            entity_type: Filter by entity $type (e.g., "project", "person")
            min_confidence: Filter by minimum $confidence score

        Returns:
            List of result dicts with keys:
                entity_id, entity_path, score, snippet, metadata
        """
        if self.collection.count() == 0:
            # Auto-rebuild if index is empty
            logger.info("Vector index empty, rebuilding...")
            self.build_index()
            if self.collection.count() == 0:
                return []

        # Build where filter
        where_filter = None
        if entity_type:
            where_filter = {"entity_type": entity_type}

        # Encode query
        query_embedding = self.model.encode(
            [text], normalize_embeddings=True
        ).tolist()

        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=min(top_k, self.collection.count()),
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        # Convert to output format
        output = []
        if results and results["ids"] and results["ids"][0]:
            for i, entity_id in enumerate(results["ids"][0]):
                distance = (
                    results["distances"][0][i] if results["distances"] else 0.0
                )
                # ChromaDB cosine distance: 0 = identical, 2 = opposite
                # Convert to similarity score: 1 - (distance / 2)
                score = 1.0 - (distance / 2.0)

                metadata = (
                    results["metadatas"][0][i] if results["metadatas"] else {}
                )
                document = (
                    results["documents"][0][i] if results["documents"] else ""
                )

                # Apply post-query confidence filter
                if min_confidence is not None:
                    if metadata.get("confidence", 0.0) < min_confidence:
                        continue

                output.append(
                    {
                        "entity_id": entity_id,
                        "entity_path": metadata.get("file_path", ""),
                        "score": round(score, 4),
                        "snippet": document[:200] if document else "",
                        "metadata": metadata,
                    }
                )

        return output

    def add_entity(self, entity_path: Path) -> bool:
        """
        Add or update a single entity in the index.

        Args:
            entity_path: Path to the entity markdown file

        Returns:
            True if successfully added/updated
        """
        try:
            entity_data = self._parse_entity_file(entity_path)
            if not entity_data:
                return False

            entity_id = entity_data.get(
                "$id", str(entity_path.relative_to(self.brain_path))
            )
            doc_text = self._build_document_text(entity_data)

            if not doc_text.strip():
                return False

            embedding = self.model.encode(
                [doc_text], normalize_embeddings=True
            ).tolist()

            metadata = self._sanitize_metadata(entity_id, entity_data)
            metadata["file_path"] = str(entity_path)

            self.collection.upsert(
                ids=[entity_id],
                documents=[doc_text],
                embeddings=embedding,
                metadatas=[metadata],
            )
            return True

        except Exception as e:
            logger.error("Error adding entity %s: %s", entity_path, e)
            return False

    def remove_entity(self, entity_id: str) -> bool:
        """
        Remove an entity from the index.

        Args:
            entity_id: The entity's $id to remove

        Returns:
            True if successfully removed
        """
        try:
            self.collection.delete(ids=[entity_id])
            return True
        except Exception as e:
            logger.error("Error removing entity %s: %s", entity_id, e)
            return False

    def rebuild(self) -> Dict[str, Any]:
        """
        Full rebuild of the vector index. Alias for build_index().

        Returns:
            Build statistics dict
        """
        return self.build_index()

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _sanitize_metadata(
        self, entity_id: str, entity_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Sanitize metadata for ChromaDB (only str, int, float, bool allowed; no $ in keys)."""
        raw_conf = entity_data.get("$confidence")
        try:
            confidence = float(raw_conf) if raw_conf is not None else 0.0
        except (ValueError, TypeError):
            confidence = 0.0

        raw_name = entity_data.get("name", entity_data.get("$id", entity_id))
        name = str(raw_name) if raw_name is not None else entity_id

        return {
            "entity_type": str(entity_data.get("$type", "unknown") or "unknown"),
            "entity_status": str(
                entity_data.get("$status", "unknown") or "unknown"
            ),
            "confidence": confidence,
            "file_path": str(entity_data.get("_path", "")),
            "name": name,
        }

    def _scan_entities(self) -> Dict[str, Dict[str, Any]]:
        """Scan all Brain entity files and parse their metadata."""
        entities = {}

        for md_file in self.brain_path.rglob("*.md"):
            # Skip excluded directories
            if any(excluded in md_file.parts for excluded in self.EXCLUDE_DIRS):
                continue
            # Skip excluded files
            if md_file.name in self.EXCLUDE_FILES:
                continue

            try:
                entity_data = self._parse_entity_file(md_file)
                if not entity_data:
                    continue

                entity_id = entity_data.get(
                    "$id", str(md_file.relative_to(self.brain_path))
                )
                entity_data["_path"] = md_file
                entities[entity_id] = entity_data

            except Exception:
                continue

        return entities

    def _parse_entity_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse a markdown file's YAML frontmatter and body."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, IOError):
            return None

        if not content.startswith("---"):
            return None

        parts = content.split("---", 2)
        if len(parts) < 3:
            return None

        try:
            frontmatter = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            return None

        frontmatter["_body"] = parts[2].strip()
        frontmatter["_name"] = file_path.stem.replace("_", " ")
        return frontmatter

    def _build_document_text(self, entity_data: Dict[str, Any]) -> str:
        """Build the document text for embedding from entity data."""
        parts = []

        # Entity name (high weight via repetition)
        name = entity_data.get("name", entity_data.get("_name", ""))
        if name:
            parts.append(name)

        # Description
        desc = entity_data.get("description", "")
        if desc:
            parts.append(str(desc))

        # Body content (first 500 chars for efficiency)
        body = entity_data.get("_body", "")
        if body:
            parts.append(body[:500].strip())

        # Tags
        tags = entity_data.get("$tags", [])
        if tags and isinstance(tags, list):
            parts.append(" ".join(str(t) for t in tags))

        return " ".join(parts)


def main():
    """CLI entry point."""
    # Configure logging for CLI
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s: %(message)s"
    )

    parser = argparse.ArgumentParser(
        description="PM-OS Brain Vector Index (ChromaDB)"
    )
    parser.add_argument(
        "action",
        choices=["build", "query", "stats", "rebuild"],
        help="Action to perform",
    )
    parser.add_argument(
        "query_text",
        nargs="?",
        help="Query text (for query action)",
    )
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=BrainVectorIndex.DEFAULT_MODEL,
        help=f"Embedding model (default: {BrainVectorIndex.DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of results (default: 10)",
    )
    parser.add_argument(
        "--type",
        type=str,
        help="Filter by entity type",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )

    args = parser.parse_args()

    if not VECTOR_AVAILABLE:
        missing = []
        if not HAS_CHROMADB:
            missing.append("chromadb")
        if not HAS_SENTENCE_TRANSFORMERS:
            missing.append("sentence-transformers")
        print(
            f"Error: Missing dependencies: {', '.join(missing)}\n"
            f"Install with: pip install {' '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    # Resolve brain path via v5 path resolver
    brain_path = args.brain_path
    if not brain_path:
        brain_path = _resolve_brain_dir()

    index = BrainVectorIndex(brain_path, model_name=args.model)

    if args.action in ("build", "rebuild"):
        print(f"Building vector index from {brain_path}...")
        stats = index.build_index()

        if args.output == "json":
            print(json.dumps(stats, indent=2))
        else:
            print(f"Entities indexed: {stats['entities_indexed']}")
            print(f"Total scanned: {stats.get('total_scanned', 0)}")
            print(f"Errors: {stats['errors']}")
            print(f"Index location: {index.index_path}")

    elif args.action == "query":
        if not args.query_text:
            print("Error: query action requires query text", file=sys.stderr)
            return 1

        results = index.query(
            args.query_text,
            top_k=args.top_k,
            entity_type=args.type,
        )

        if args.output == "json":
            print(json.dumps(results, indent=2))
        else:
            print(f"Query: {args.query_text}")
            print(f"Results ({len(results)}):")
            print("-" * 60)
            for r in results:
                print(f"  {r['score']:.3f} | {r['entity_id']}")
                print(
                    f"         {r['metadata'].get('entity_type', '?')} | {r['entity_path']}"
                )
                if r.get("snippet"):
                    print(f"         {r['snippet'][:80]}...")
                print()

    elif args.action == "stats":
        count = index.collection.count()
        if args.output == "json":
            print(
                json.dumps(
                    {"entity_count": count, "index_path": str(index.index_path)}
                )
            )
        else:
            print(f"Index location: {index.index_path}")
            print(f"Entities in index: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
