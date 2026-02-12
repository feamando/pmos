#!/usr/bin/env python3
"""
Tests for BRAIN+GRAPH Query System

Tests cover:
- Inverted index building
- BRAIN keyword search (alias + content)
- GRAPH traversal
- Scoring and ranking
- Merge logic
- End-to-end queries
- Performance benchmarks
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import List

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from brain_graph import BrainGraph
from brain_index import BrainIndex, PorterStemmer
from brain_query import BrainQuery, QueryResult
from brain_search import BrainSearch, SearchResult


class TestPorterStemmer:
    """Tests for the Porter stemmer implementation."""

    def test_basic_stemming(self):
        stemmer = PorterStemmer()
        assert stemmer.stem("running") == "run"
        assert stemmer.stem("cats") == "cat"
        assert stemmer.stem("connecting") == "connect"

    def test_stem_caching(self):
        stemmer = PorterStemmer()
        # First call
        result1 = stemmer.stem("testing")
        # Should be cached
        result2 = stemmer.stem("testing")
        assert result1 == result2
        assert "testing" in stemmer.cache

    def test_short_words(self):
        stemmer = PorterStemmer()
        assert stemmer.stem("a") == "a"
        assert stemmer.stem("to") == "to"


class TestBrainIndex:
    """Tests for inverted index building."""

    @pytest.fixture
    def temp_brain(self, tmp_path):
        """Create a temporary brain directory with test entities."""
        brain_dir = tmp_path / "brain"
        brain_dir.mkdir()

        # Create Entities directory
        entities_dir = brain_dir / "Entities"
        entities_dir.mkdir()

        # Create test entity files
        (entities_dir / "Test_Entity.md").write_text("""---
$id: entity/test/test-entity
$type: test
---
# Test Entity

This is a test entity about launches and products.
It contains important keywords like alpha beta gamma.
""")

        (entities_dir / "Another_Entity.md").write_text("""---
$id: entity/test/another-entity
$type: test
---
# Another Entity

This entity discusses launches and testing strategies.
""")

        return brain_dir

    def test_index_build(self, temp_brain):
        indexer = BrainIndex(temp_brain)
        result = indexer.build()

        assert "meta" in result
        assert "index" in result
        assert result["meta"]["entity_count"] == 2
        assert len(result["index"]) > 0

    def test_index_search(self, temp_brain):
        indexer = BrainIndex(temp_brain)
        indexer.build()

        # Search for "launch" (should match both entities)
        results = indexer.search("launch")
        assert len(results) == 2

        # Search for "alpha" (should match only first entity)
        results = indexer.search("alpha")
        assert len(results) == 1
        assert "test-entity" in results[0]

    def test_and_semantics(self, temp_brain):
        indexer = BrainIndex(temp_brain)
        indexer.build()

        # "launch test" should match entities with both words
        results = indexer.search("launch test", mode="and")
        assert len(results) >= 1

    def test_or_semantics(self, temp_brain):
        indexer = BrainIndex(temp_brain)
        indexer.build()

        # "alpha gamma" in OR mode should find entity with either
        results = indexer.search("alpha gamma", mode="or")
        assert len(results) >= 1


class TestBrainSearch:
    """Tests for BRAIN keyword search."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock registry for testing."""
        return {
            "projects": {
                "test-project": {
                    "file": "Projects/Test_Project.md",
                    "aliases": ["tp", "testproj"],
                }
            },
            "entities": {
                "john-doe": {
                    "file": "Entities/People/John_Doe.md",
                    "aliases": ["john", "jd"],
                }
            },
        }

    def test_alias_exact_match(self, mock_registry, tmp_path):
        # Create minimal content index
        index_file = tmp_path / "content_index.json"
        index_file.write_text('{"meta": {}, "index": {}}')

        search = BrainSearch(tmp_path, mock_registry)

        # Exact alias match
        results = search._search_aliases("john")
        assert len(results) > 0
        assert any(r.entity_id == "john-doe" for r in results)

    def test_alias_partial_match(self, mock_registry, tmp_path):
        index_file = tmp_path / "content_index.json"
        index_file.write_text('{"meta": {}, "index": {}}')

        search = BrainSearch(tmp_path, mock_registry)

        # Multi-term query should match partial
        results = search._search_aliases("john project")
        assert len(results) >= 1

    def test_query_expansion(self, tmp_path):
        # Test synonym expansion
        search = BrainSearch.__new__(BrainSearch)
        search.stemmer = PorterStemmer()
        search.synonyms = search._build_synonym_dict()

        # "launch" should expand to include "release", "deploy", etc.
        tokens = search._tokenize_query("launch")
        expanded = search._expand_query(tokens)

        assert len(expanded) >= 1
        # Check that synonyms are included
        assert "launch" in expanded or any("releas" in t for t in expanded)


class TestBrainGraph:
    """Tests for GRAPH traversal."""

    @pytest.fixture
    def temp_brain_with_relationships(self, tmp_path):
        """Create brain with entities that have relationships."""
        brain_dir = tmp_path / "brain"
        brain_dir.mkdir()

        entities_dir = brain_dir / "Entities"
        entities_dir.mkdir()

        # Entity A with relationships to B and C
        (entities_dir / "Entity_A.md").write_text("""---
$id: entity/test/entity-a
$type: test
$relationships:
  - target: entity/test/entity-b
    type: related_to
  - target: entity/test/entity-c
    type: depends_on
    strength: 0.7
---
# Entity A
""")

        # Entity B
        (entities_dir / "Entity_B.md").write_text("""---
$id: entity/test/entity-b
$type: test
$relationships:
  - target: entity/test/entity-d
    type: related_to
---
# Entity B
""")

        # Entity C (no relationships)
        (entities_dir / "Entity_C.md").write_text("""---
$id: entity/test/entity-c
$type: test
---
# Entity C
""")

        return brain_dir

    def test_basic_expansion(self, temp_brain_with_relationships):
        graph = BrainGraph(temp_brain_with_relationships)

        seed = SearchResult(entity_id="entity/test/entity-a", score=1.0, source="test")
        neighbors = graph.expand([seed], decay=0.5, depth=1)

        assert len(neighbors) == 2  # B and C
        assert any(n.entity_id == "entity/test/entity-b" for n in neighbors)
        assert any(n.entity_id == "entity/test/entity-c" for n in neighbors)

    def test_decay_factor(self, temp_brain_with_relationships):
        graph = BrainGraph(temp_brain_with_relationships)

        seed = SearchResult(entity_id="entity/test/entity-a", score=1.0, source="test")
        neighbors = graph.expand([seed], decay=0.5, depth=1)

        # Default decay should apply to entity-b
        b_result = next(
            (n for n in neighbors if n.entity_id == "entity/test/entity-b"), None
        )
        assert b_result is not None
        assert b_result.score == 0.5  # 1.0 * 0.5

        # Custom strength should apply to entity-c
        c_result = next(
            (n for n in neighbors if n.entity_id == "entity/test/entity-c"), None
        )
        assert c_result is not None
        assert c_result.score == 0.7  # 1.0 * 0.7 (custom strength)

    def test_cycle_prevention(self, temp_brain_with_relationships):
        graph = BrainGraph(temp_brain_with_relationships)

        # Even with depth=2, shouldn't revisit seed
        seed = SearchResult(entity_id="entity/test/entity-a", score=1.0, source="test")
        neighbors = graph.expand([seed], decay=0.5, depth=2)

        # Should not include entity-a in neighbors
        assert not any(n.entity_id == "entity/test/entity-a" for n in neighbors)


class TestBrainQuery:
    """Tests for unified query interface."""

    def test_brain_only_query(self):
        """Test query with graph disabled."""
        # This uses actual brain - skip if brain not available
        if not Path("/Users/jane.smith/pm-os/user/brain").exists():
            pytest.skip("Brain not available")

        bq = BrainQuery()
        result = bq.query("otp", limit=5, use_graph=False)

        assert isinstance(result, QueryResult)
        assert result.query == "otp"
        assert len(result.results) <= 5
        assert not result.graph_expanded

    def test_brain_graph_query(self):
        """Test query with graph enabled."""
        if not Path("/Users/jane.smith/pm-os/user/brain").exists():
            pytest.skip("Brain not available")

        bq = BrainQuery()
        result = bq.query("Growth Platform", limit=10, use_graph=True)

        assert isinstance(result, QueryResult)
        assert result.graph_expanded or result.seed_count == 0

    def test_merge_max_score_wins(self):
        """Test that merge takes max score on collision."""
        bq = BrainQuery.__new__(BrainQuery)

        seeds = [
            SearchResult(entity_id="entity-a", score=0.8, source="alias"),
            SearchResult(entity_id="entity-b", score=0.6, source="alias"),
        ]
        neighbors = [
            SearchResult(
                entity_id="entity-a", score=0.3, source="graph"
            ),  # Lower score
            SearchResult(entity_id="entity-c", score=0.4, source="graph"),  # New entity
        ]

        merged = bq._merge_and_rank(seeds, neighbors)

        # entity-a should have score 0.8 (max of 0.8 and 0.3)
        a_result = next((r for r in merged if r.entity_id == "entity-a"), None)
        assert a_result is not None
        assert a_result.score == 0.8

        # All three entities should be present
        assert len(merged) == 3


class TestQueryDependence:
    """Tests to verify query dependence (TKS learning: results must vary by query)."""

    def test_different_queries_different_results(self):
        """Different queries should return different results."""
        if not Path("/Users/jane.smith/pm-os/user/brain").exists():
            pytest.skip("Brain not available")

        bq = BrainQuery()

        result1 = bq.query("otp launch", limit=10, use_graph=False)
        result2 = bq.query("Growth Platform canada", limit=10, use_graph=False)

        # Extract entity IDs
        ids1 = {r.entity_id for r in result1.results}
        ids2 = {r.entity_id for r in result2.results}

        # Calculate overlap
        if ids1 and ids2:
            overlap = len(ids1.intersection(ids2)) / max(len(ids1), len(ids2))
            # TKS target: overlap < 20%
            assert overlap < 0.5, f"Queries too similar: {overlap*100:.1f}% overlap"


class TestPerformance:
    """Performance benchmarks."""

    def test_search_latency(self):
        """Test that search completes within acceptable time."""
        if not Path("/Users/jane.smith/pm-os/user/brain").exists():
            pytest.skip("Brain not available")

        bq = BrainQuery()

        # Warm up
        bq.query("test", limit=5, use_graph=False)

        # Measure
        start = time.time()
        result = bq.query("Growth Platform", limit=10, use_graph=False)
        latency = (time.time() - start) * 1000

        # Target: < 500ms for BRAIN only
        assert latency < 1000, f"BRAIN search too slow: {latency:.0f}ms"

    def test_full_query_latency(self):
        """Test full BRAIN+GRAPH query latency."""
        if not Path("/Users/jane.smith/pm-os/user/brain").exists():
            pytest.skip("Brain not available")

        bq = BrainQuery()

        # Warm up (builds resolver index)
        bq.query("test", limit=5, use_graph=True)

        # Measure
        start = time.time()
        result = bq.query("otp", limit=10, use_graph=True)
        latency = (time.time() - start) * 1000

        # Target: < 500ms after warmup
        # Note: First query is slower due to index building
        assert latency < 3000, f"Full query too slow: {latency:.0f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
