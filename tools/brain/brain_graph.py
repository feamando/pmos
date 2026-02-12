#!/usr/bin/env python3
"""
Brain Graph - GRAPH Traversal Component

Expands seed entities via 1-hop relationship traversal.
Part of BRAIN+GRAPH retrieval system based on TKS research.

Key features:
- Load $relationships from entity frontmatter
- Resolve targets via canonical_resolver
- Tunable decay factor (default 0.5)
- Support relationship-specific strength field
- Track visited to prevent cycles
- Collect warnings for unresolved targets
"""

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader
from brain_search import SearchResult

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

# Default decay factor for graph neighbors
DEFAULT_DECAY = 0.5


class BrainGraph:
    """
    GRAPH traversal component.

    Expands seed entities by following $relationships to find neighbors.
    Implements TKS research findings: 1-hop traversal with decay.
    """

    def __init__(self, brain_path: Optional[Path] = None, resolver=None):
        """
        Initialize graph component.

        Args:
            brain_path: Path to brain directory
            resolver: Optional CanonicalResolver instance (lazy-loaded if None)
        """
        self.brain_path = Path(brain_path) if brain_path else BRAIN_DIR
        self._resolver = resolver
        self.warnings: List[str] = []

        # Cache for loaded entities
        self._entity_cache: Dict[str, Dict] = {}

    @property
    def resolver(self):
        """Lazy-load canonical resolver."""
        if self._resolver is None:
            from canonical_resolver import CanonicalResolver

            self._resolver = CanonicalResolver(self.brain_path)
            self._resolver.build_index()
        return self._resolver

    def expand(
        self, seeds: List[SearchResult], decay: float = DEFAULT_DECAY, depth: int = 1
    ) -> List[SearchResult]:
        """
        Expand seed entities via relationship traversal.

        Args:
            seeds: List of seed SearchResults from BRAIN search
            decay: Score decay factor for neighbors (default 0.5)
            depth: Traversal depth (1 = neighbors only, 2 = neighbors of neighbors)

        Returns:
            List of neighbor SearchResults
        """
        self.warnings = []  # Reset warnings

        if not seeds:
            return []

        # Track visited entities (seeds + discovered)
        visited: Set[str] = {s.entity_id for s in seeds}
        neighbors: Dict[str, SearchResult] = {}

        # Current frontier = seeds
        current_frontier = [(s.entity_id, s.score, None) for s in seeds]

        for d in range(depth):
            next_frontier = []
            current_decay = decay ** (d + 1)  # Decay compounds with depth

            for entity_id, parent_score, parent_id in current_frontier:
                # Load entity and get relationships
                entity_data = self._load_entity(entity_id)
                if entity_data is None:
                    continue

                relationships = entity_data.get("$relationships", [])
                if not relationships:
                    continue

                for rel in relationships:
                    target = rel.get("target")
                    if not target:
                        continue

                    # Resolve target to canonical ID
                    canonical_target = self.resolver.resolve(target)
                    if canonical_target is None:
                        self.warnings.append(f"Unresolved: '{target}' in {entity_id}")
                        continue

                    # Skip if already visited
                    if canonical_target in visited:
                        continue

                    # Calculate score with decay
                    # Use relationship-specific strength if defined
                    rel_strength = rel.get("strength", current_decay)
                    if isinstance(rel_strength, str):
                        try:
                            rel_strength = float(rel_strength)
                        except ValueError:
                            rel_strength = current_decay

                    score = parent_score * rel_strength

                    # Track via which entity we found this neighbor
                    via_entity = parent_id if parent_id else entity_id

                    # Create or update result (max score wins)
                    if (
                        canonical_target not in neighbors
                        or score > neighbors[canonical_target].score
                    ):
                        neighbors[canonical_target] = SearchResult(
                            entity_id=canonical_target,
                            score=score,
                            source="graph",
                            match_reasons=[
                                f"via {via_entity} ({rel.get('type', 'related_to')})"
                            ],
                            via=via_entity,
                            relationship_type=rel.get("type"),
                        )
                    else:
                        # Already found with higher score, but track additional path
                        neighbors[canonical_target].match_reasons.append(
                            f"also via {via_entity} ({rel.get('type', 'related_to')})"
                        )

                    # Add to visited
                    visited.add(canonical_target)

                    # Add to next frontier for deeper traversal
                    if d < depth - 1:
                        next_frontier.append((canonical_target, score, via_entity))

            current_frontier = next_frontier

        return list(neighbors.values())

    def get_relationships(self, entity_id: str) -> List[Dict]:
        """
        Get relationships for a specific entity.

        Args:
            entity_id: Entity ID to get relationships for

        Returns:
            List of relationship dicts
        """
        entity_data = self._load_entity(entity_id)
        if entity_data is None:
            return []

        return entity_data.get("$relationships", [])

    def _load_entity(self, entity_id: str) -> Optional[Dict]:
        """
        Load entity data from file.

        Args:
            entity_id: Entity ID (canonical or resolvable)

        Returns:
            Dict with entity frontmatter, or None if not found
        """
        # Check cache
        if entity_id in self._entity_cache:
            return self._entity_cache[entity_id]

        # Resolve to canonical ID if needed
        canonical_id = entity_id
        if not entity_id.startswith("entity/") and not entity_id.startswith("project/"):
            resolved = self.resolver.resolve(entity_id)
            if resolved:
                canonical_id = resolved

        # Get file path from resolver
        file_path = (
            self.resolver.get_entity_path(canonical_id)
            if hasattr(self.resolver, "get_entity_path")
            else None
        )

        if file_path is None:
            # Try to find file by scanning common patterns
            file_path = self._find_entity_file(canonical_id)

        if file_path is None or not file_path.exists():
            return None

        # Load and parse file
        try:
            data = self._parse_entity_file(file_path)
            self._entity_cache[entity_id] = data
            return data
        except Exception as e:
            self.warnings.append(f"Error loading {entity_id}: {e}")
            return None

    def _find_entity_file(self, entity_id: str) -> Optional[Path]:
        """Find entity file by ID pattern matching."""
        # entity/person/john-doe -> Entities/People/John_Doe.md
        # project/growth-platform -> Projects/Growth_Platform.md

        parts = entity_id.split("/")
        if len(parts) < 2:
            return None

        entity_type = parts[0]  # entity, project, etc.
        subtype = parts[1] if len(parts) > 2 else None
        name = parts[-1]

        # Convert name: john-doe -> John_Doe
        filename = "_".join(word.capitalize() for word in name.split("-")) + ".md"

        # Try different paths
        search_paths = []

        if entity_type == "entity" and subtype:
            # Entities/People/John_Doe.md
            subdir = (
                subtype.capitalize() + "s"
                if not subtype.endswith("s")
                else subtype.capitalize()
            )
            search_paths.append(self.brain_path / "Entities" / subdir / filename)
            search_paths.append(self.brain_path / "Entities" / filename)

        elif entity_type == "project":
            search_paths.append(self.brain_path / "Projects" / filename)

        elif entity_type == "experiment":
            search_paths.append(self.brain_path / "Experiments" / filename)

        # Try each path
        for path in search_paths:
            if path.exists():
                return path

        # Fallback: search all directories
        for pattern in [
            f"**/{filename}",
            f"**/{name}.md",
            f"**/{name.replace('-', '_')}.md",
        ]:
            matches = list(self.brain_path.glob(pattern))
            if matches:
                return matches[0]

        return None

    def _parse_entity_file(self, file_path: Path) -> Dict:
        """Parse entity file and extract frontmatter."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for YAML frontmatter
        if not content.startswith("---"):
            return {}

        # Find end of frontmatter
        end_match = re.search(r"\n---\s*\n", content[3:])
        if not end_match:
            return {}

        frontmatter_str = content[4 : end_match.start() + 3]

        if HAS_YAML:
            try:
                return yaml.safe_load(frontmatter_str) or {}
            except yaml.YAMLError:
                return {}
        else:
            return {}


def main():
    """Test graph expansion."""
    import argparse

    parser = argparse.ArgumentParser(description="GRAPH Traversal")
    parser.add_argument("entity_id", help="Entity ID to expand")
    parser.add_argument("--depth", type=int, default=1, help="Traversal depth")
    parser.add_argument("--decay", type=float, default=0.5, help="Score decay")

    args = parser.parse_args()

    from brain_search import SearchResult

    graph = BrainGraph()

    # Create seed result
    seed = SearchResult(entity_id=args.entity_id, score=1.0, source="test")

    neighbors = graph.expand([seed], decay=args.decay, depth=args.depth)

    print(f"Entity: {args.entity_id}")
    print(f"Neighbors ({len(neighbors)}):")
    print("-" * 50)

    for n in sorted(neighbors, key=lambda x: -x.score):
        print(f"{n.score:.2f} | {n.entity_id}")
        print(f"      via: {n.via} ({n.relationship_type})")

    if graph.warnings:
        print(f"\nWarnings ({len(graph.warnings)}):")
        for w in graph.warnings[:5]:
            print(f"  - {w}")


if __name__ == "__main__":
    main()
