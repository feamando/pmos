#!/usr/bin/env python3
"""
Brain Search - BRAIN Keyword Search Component

Implements keyword search across aliases and content using:
- O(1) alias lookup via registry alias_index
- O(1) content lookup via inverted index
- Query expansion for common synonyms
- AND semantics for multi-word queries
- Relevance scoring

Part of BRAIN+GRAPH retrieval system based on TKS research.
"""

import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# Import from sibling modules
from brain_index import BrainIndex, PorterStemmer

# Try to import yaml
try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# --- Configuration ---
ROOT_PATH = config_loader.get_root_path()
USER_PATH = ROOT_PATH / "user"
BRAIN_DIR = USER_PATH / "brain"
REGISTRY_FILE = BRAIN_DIR / "registry.yaml"
INDEX_FILE = BRAIN_DIR / "content_index.json"

# Scoring weights
SCORE_ALIAS_EXACT = 1.0
SCORE_ALIAS_PARTIAL = 0.5
SCORE_CONTENT_TITLE = 0.3
SCORE_CONTENT_BODY = 0.1


@dataclass
class SearchResult:
    """Single search result with relevance info."""

    entity_id: str
    score: float
    source: str  # 'alias', 'content', 'graph'
    match_reasons: List[str] = field(default_factory=list)
    file_path: Optional[str] = None
    via: Optional[str] = None  # For graph results: which entity led here
    relationship_type: Optional[str] = None

    def __hash__(self):
        return hash(self.entity_id)

    def __eq__(self, other):
        return isinstance(other, SearchResult) and self.entity_id == other.entity_id


class BrainSearch:
    """
    BRAIN keyword search component.

    Combines alias matching (fast, exact) with content search (via inverted index).
    Implements query expansion and relevance scoring.
    """

    def __init__(
        self, brain_path: Optional[Path] = None, registry: Optional[Dict] = None
    ):
        self.brain_path = Path(brain_path) if brain_path else BRAIN_DIR
        self.stemmer = PorterStemmer()

        # Load registry and build alias index
        self.registry = registry if registry else self._load_registry()
        self.alias_index = self._build_alias_index()

        # Load content index
        self.content_index = self._load_content_index()

        # Query expansion dictionary (synonyms)
        self.synonyms = self._build_synonym_dict()

    def search(self, query: str, limit: int = 20) -> List[SearchResult]:
        """
        Search for entities matching query.

        Args:
            query: Natural language search query
            limit: Maximum results to return

        Returns:
            List of SearchResult sorted by relevance score
        """
        if not query or not query.strip():
            return []

        query = query.strip()

        # 1. Alias matches (O(1) per alias)
        alias_results = self._search_aliases(query)

        # 2. Content matches via inverted index
        content_results = self._search_content(query)

        # 3. Merge and rank (dedup, max score wins)
        merged = self._merge_results(alias_results, content_results)

        # 4. Sort by score and return top results
        merged.sort(key=lambda r: -r.score)

        return merged[:limit]

    def _search_aliases(self, query: str) -> List[SearchResult]:
        """Search aliases for exact and partial matches."""
        results = {}
        query_lower = query.lower()
        query_terms = query_lower.split()

        # Exact match on full query
        if query_lower in self.alias_index:
            cat, entity_id, file_path = self.alias_index[query_lower]
            results[entity_id] = SearchResult(
                entity_id=entity_id,
                score=SCORE_ALIAS_EXACT,
                source="alias",
                match_reasons=[f'alias exact: "{query_lower}"'],
                file_path=file_path,
            )

        # Partial matches (each query term)
        for term in query_terms:
            if len(term) < 2:
                continue

            # Exact match on term
            if term in self.alias_index:
                cat, entity_id, file_path = self.alias_index[term]
                if entity_id not in results:
                    results[entity_id] = SearchResult(
                        entity_id=entity_id,
                        score=SCORE_ALIAS_PARTIAL,
                        source="alias",
                        match_reasons=[f'alias term: "{term}"'],
                        file_path=file_path,
                    )
                else:
                    results[entity_id].match_reasons.append(f'alias term: "{term}"')
                    # Boost score for multiple term matches
                    results[entity_id].score = min(1.0, results[entity_id].score + 0.1)

            # Prefix matching on aliases (for partial word matches)
            for alias, (cat, entity_id, file_path) in self.alias_index.items():
                if alias.startswith(term) and len(alias) <= len(term) + 3:
                    if entity_id not in results:
                        results[entity_id] = SearchResult(
                            entity_id=entity_id,
                            score=SCORE_ALIAS_PARTIAL
                            * 0.8,  # Slightly lower for prefix
                            source="alias",
                            match_reasons=[f'alias prefix: "{term}" -> "{alias}"'],
                            file_path=file_path,
                        )

        return list(results.values())

    def _search_content(self, query: str) -> List[SearchResult]:
        """Search content via inverted index with AND semantics."""
        if not self.content_index:
            return []

        # Tokenize and stem query
        tokens = self._tokenize_query(query)
        if not tokens:
            return []

        # Expand query with synonyms
        expanded_tokens = self._expand_query(tokens)

        # Get posting lists for each token
        posting_lists = []
        matched_tokens = []

        for token in expanded_tokens:
            if token in self.content_index:
                posting_lists.append(set(self.content_index[token]))
                matched_tokens.append(token)

        if not posting_lists:
            return []

        # AND semantics: intersection of all posting lists
        result_set = posting_lists[0]
        for pl in posting_lists[1:]:
            result_set = result_set.intersection(pl)

        # Score based on token coverage
        results = []
        for entity_id in result_set:
            # Calculate score based on how many tokens matched
            coverage = len(matched_tokens) / len(tokens) if tokens else 0
            score = SCORE_CONTENT_BODY * coverage

            # Boost if entity name contains query terms
            entity_name = entity_id.split("/")[-1].replace("-", " ")
            if any(term in entity_name for term in query.lower().split()):
                score = max(score, SCORE_CONTENT_TITLE)

            results.append(
                SearchResult(
                    entity_id=entity_id,
                    score=score,
                    source="content",
                    match_reasons=[f'content: {", ".join(matched_tokens)}'],
                )
            )

        return results

    def _merge_results(
        self, alias_results: List[SearchResult], content_results: List[SearchResult]
    ) -> List[SearchResult]:
        """Merge results from alias and content search, max score wins on collision."""
        merged: Dict[str, SearchResult] = {}

        # Add alias results first (typically higher scores)
        for r in alias_results:
            merged[r.entity_id] = r

        # Merge content results
        for r in content_results:
            if r.entity_id not in merged:
                merged[r.entity_id] = r
            else:
                # Entity already found via alias - merge info
                existing = merged[r.entity_id]
                # Keep max score
                if r.score > existing.score:
                    existing.score = r.score
                # Combine match reasons
                existing.match_reasons.extend(r.match_reasons)

        return list(merged.values())

    def _tokenize_query(self, query: str) -> List[str]:
        """Tokenize and stem query terms."""
        # Extract words
        words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9]*\b", query.lower())

        # Stopwords to skip
        stopwords = {
            "a",
            "an",
            "the",
            "and",
            "or",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "was",
            "are",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "this",
            "that",
            "it",
            "they",
            "we",
            "you",
            "he",
            "she",
            "i",
            "my",
            "me",
            "what",
            "how",
            "when",
        }

        tokens = []
        for word in words:
            if word in stopwords or len(word) < 2:
                continue
            stemmed = self.stemmer.stem(word)
            if len(stemmed) >= 2:
                tokens.append(stemmed)

        return tokens

    def _expand_query(self, tokens: List[str]) -> Set[str]:
        """Expand query tokens with synonyms."""
        expanded = set(tokens)

        for token in tokens:
            if token in self.synonyms:
                expanded.update(self.synonyms[token])

        return expanded

    def _build_synonym_dict(self) -> Dict[str, List[str]]:
        """Build synonym dictionary for query expansion."""
        # Stem synonyms too for consistency
        raw_synonyms = {
            # Project aliases
            "otp": ["one-time-purchase", "one-time", "onetime"],
            "tpt": ["brand-b", "brand-b", "pettabl"],
            "ff": ["growth-platform", "factorform"],
            # Common terms
            "launch": ["releas", "deploy", "ship", "rollout"],
            "bug": ["issu", "defect", "error", "problem"],
            "feature": ["function", "capabil"],
            "user": ["custom", "client"],
            "team": ["squad", "group"],
            "test": ["verifi", "valid", "check"],
            "config": ["set", "configur"],
            "auth": ["authent", "login", "signin"],
            "api": ["endpoint", "servic"],
            "db": ["databas", "store"],
            "ui": ["interfac", "frontend", "ux"],
        }

        # Stem all synonyms
        synonyms = {}
        for key, values in raw_synonyms.items():
            stemmed_key = self.stemmer.stem(key)
            stemmed_values = [self.stemmer.stem(v) for v in values]
            synonyms[stemmed_key] = stemmed_values

            # Bidirectional: each synonym also maps to others
            for v in stemmed_values:
                if v not in synonyms:
                    synonyms[v] = []
                if stemmed_key not in synonyms[v]:
                    synonyms[v].append(stemmed_key)

        return synonyms

    def _load_registry(self) -> Dict:
        """Load registry from YAML file."""
        if not REGISTRY_FILE.exists():
            return {}

        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                if HAS_YAML:
                    registry = yaml.safe_load(f)
                    # Normalize v2 if needed
                    if registry and "$schema" in registry:
                        return self._normalize_v2_registry(registry)
                    return registry or {}
                else:
                    return {}
        except Exception as e:
            print(f"Error loading registry: {e}", file=sys.stderr)
            return {}

    def _normalize_v2_registry(self, v2_registry: Dict) -> Dict:
        """Normalize v2 registry to v1-compatible structure."""
        v1 = {
            "projects": {},
            "entities": {},
            "architecture": {},
            "decisions": {},
            "_v2_alias_index": v2_registry.get("alias_index", {}),
        }

        entities = v2_registry.get("entities", {})
        for slug, data in entities.items():
            if not isinstance(data, dict):
                continue

            entity_type = data.get("$type", "entity")
            ref = data.get("$ref", "")

            # Determine category from type
            type_to_category = {
                "project": "projects",
                "person": "entities",
                "team": "entities",
                "squad": "entities",
                "system": "entities",
                "brand": "entities",
                "architecture": "architecture",
                "decision": "decisions",
            }
            category = type_to_category.get(entity_type, "entities")

            v1[category][slug] = {"file": ref, "aliases": data.get("aliases", [])}

        return v1

    def _build_alias_index(self) -> Dict[str, Tuple[str, str, str]]:
        """Build alias index from registry."""
        index = {}

        # Use v2 alias index if available
        if "_v2_alias_index" in self.registry and self.registry["_v2_alias_index"]:
            v2_index = self.registry["_v2_alias_index"]
            for alias, slug in v2_index.items():
                # Find entity info
                for category in ["projects", "entities", "architecture", "decisions"]:
                    if category in self.registry and slug in self.registry[category]:
                        data = self.registry[category][slug]
                        file_path = data.get("file", "")
                        index[alias.lower()] = (category, slug, file_path)
                        break

        # Standard index building
        for category in ["projects", "entities", "architecture", "decisions"]:
            if category not in self.registry or not self.registry[category]:
                continue

            for entity_id, data in self.registry[category].items():
                if not isinstance(data, dict):
                    continue

                file_path = data.get("file", "")
                aliases = data.get("aliases", [])

                # Add entity_id and all aliases
                for alias in [entity_id] + (aliases if aliases else []):
                    if alias:
                        index[alias.lower()] = (category, entity_id, file_path)

        return index

    def _load_content_index(self) -> Dict[str, List[str]]:
        """Load content index from JSON file."""
        if not INDEX_FILE.exists():
            return {}

        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("index", {})
        except Exception as e:
            print(f"Error loading content index: {e}", file=sys.stderr)
            return {}


def main():
    """Test search functionality."""
    import argparse

    parser = argparse.ArgumentParser(description="BRAIN Keyword Search")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--limit", type=int, default=10, help="Max results")

    args = parser.parse_args()

    if not args.query:
        print("Usage: python brain_search.py <query>")
        return

    search = BrainSearch()
    results = search.search(args.query, limit=args.limit)

    print(f"Query: {args.query}")
    print(f"Results ({len(results)}):")
    print("-" * 50)

    for r in results:
        print(f"{r.score:.2f} | {r.entity_id}")
        print(f"      {r.source}: {', '.join(r.match_reasons[:3])}")


if __name__ == "__main__":
    main()
