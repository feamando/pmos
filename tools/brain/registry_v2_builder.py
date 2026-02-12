#!/usr/bin/env python3
"""
PM-OS Brain Registry V2 Builder

Builds the enhanced v2 registry from Brain entities.

Features:
- Generate v2 registry with $schema, $version, denormalized entity info
- Build alias index for fast lookup
- Compute statistics
- Support incremental updates
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add common to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class RegistryV2Builder:
    """Builds v2 registry from Brain entities."""

    def __init__(self, brain_path: Path):
        """
        Initialize the builder.

        Args:
            brain_path: Path to the brain directory
        """
        self.brain_path = brain_path
        self.registry_path = brain_path / "registry.yaml"

    def build(self, incremental: bool = False) -> Dict[str, Any]:
        """
        Build the v2 registry.

        Args:
            incremental: If True, update existing registry

        Returns:
            The built registry
        """
        if incremental and self.registry_path.exists():
            registry = self._load_existing_registry()
        else:
            registry = self._create_empty_registry()

        # Scan entities
        entities_scanned = 0

        # Process Entities directory
        entities_path = self.brain_path / "Entities"
        if entities_path.exists():
            for filepath in entities_path.rglob("*.md"):
                if filepath.name.lower() not in ("readme.md", "index.md", "_index.md"):
                    entry = self._process_entity(filepath)
                    if entry:
                        slug = self._filepath_to_slug(filepath)
                        registry["entities"][slug] = entry
                        entities_scanned += 1

        # Process Projects directory
        projects_path = self.brain_path / "Projects"
        if projects_path.exists():
            for filepath in projects_path.rglob("*.md"):
                if filepath.name.lower() not in ("readme.md", "index.md", "_index.md"):
                    entry = self._process_entity(filepath)
                    if entry:
                        slug = self._filepath_to_slug(filepath)
                        registry["entities"][slug] = entry
                        entities_scanned += 1

        # Rebuild alias index
        registry["alias_index"] = self._build_alias_index(registry["entities"])

        # Compute stats
        registry["stats"] = self._compute_stats(registry["entities"])

        # Update timestamp
        registry["$generated"] = datetime.utcnow().isoformat() + "Z"

        print(f"Scanned {entities_scanned} entities")

        return registry

    def save(self, registry: Dict[str, Any]) -> None:
        """Save registry to file."""
        with open(self.registry_path, "w", encoding="utf-8") as f:
            yaml.dump(
                registry,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
        print(f"Saved registry to {self.registry_path}")

    def _create_empty_registry(self) -> Dict[str, Any]:
        """Create empty v2 registry structure."""
        return {
            "$schema": "brain://registry/v2",
            "$version": "2.0",
            "$generated": datetime.utcnow().isoformat() + "Z",
            "entities": {},
            "alias_index": {},
            "stats": {},
        }

    def _load_existing_registry(self) -> Dict[str, Any]:
        """Load existing registry."""
        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                registry = yaml.safe_load(f) or {}

            # Ensure v2 structure
            if "$schema" not in registry:
                # Migrate v1 registry
                return self._migrate_v1_registry(registry)

            return registry
        except Exception:
            return self._create_empty_registry()

    def _migrate_v1_registry(self, v1_registry: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate v1 registry to v2 format."""
        v2_registry = self._create_empty_registry()

        # Convert v1 entries to v2
        for slug, v1_entry in v1_registry.items():
            if isinstance(v1_entry, dict):
                v2_entry = {
                    "$ref": v1_entry.get("path", ""),
                    "$type": v1_entry.get("type", "unknown"),
                    "$status": v1_entry.get("status", "active"),
                    "$version": 1,
                    "$updated": datetime.utcnow().isoformat() + "Z",
                    "aliases": v1_entry.get("aliases", []),
                    "confidence": 0.5,
                }
                v2_registry["entities"][slug] = v2_entry

        return v2_registry

    def _process_entity(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """Process a single entity file and extract registry entry."""
        try:
            content = filepath.read_text(encoding="utf-8")
        except Exception:
            return None

        # Parse frontmatter
        frontmatter = self._parse_frontmatter(content)
        if not frontmatter:
            # Create minimal entry for entities without frontmatter
            return self._create_minimal_entry(filepath)

        # Check if v2 format
        if "$schema" in frontmatter:
            return self._extract_v2_entry(filepath, frontmatter)
        else:
            return self._extract_v1_entry(filepath, frontmatter)

    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """Parse YAML frontmatter from content."""
        if not content.startswith("---"):
            return {}

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}

        try:
            return yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            return {}

    def _extract_v2_entry(
        self, filepath: Path, frontmatter: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract registry entry from v2 entity."""
        relative_path = filepath.relative_to(self.brain_path)

        return {
            "$ref": str(relative_path),
            "$type": frontmatter.get("$type", "unknown"),
            "$status": frontmatter.get("$status", "active"),
            "$version": frontmatter.get("$version", 1),
            "$updated": frontmatter.get(
                "$updated", datetime.utcnow().isoformat() + "Z"
            ),
            "aliases": frontmatter.get("$aliases", []),
            "role": frontmatter.get("role"),
            "team": frontmatter.get("team"),
            "owner": frontmatter.get("owner"),
            "relationships_count": len(frontmatter.get("$relationships", [])),
            "confidence": frontmatter.get("$confidence", 0.5),
        }

    def _extract_v1_entry(
        self, filepath: Path, frontmatter: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract registry entry from v1 entity."""
        relative_path = filepath.relative_to(self.brain_path)

        # Infer type from directory
        entity_type = self._infer_type_from_path(filepath)

        return {
            "$ref": str(relative_path),
            "$type": frontmatter.get("type", entity_type),
            "$status": frontmatter.get("status", "active"),
            "$version": 1,
            "$updated": frontmatter.get("updated", datetime.utcnow().isoformat() + "Z"),
            "aliases": frontmatter.get("aliases", []),
            "role": frontmatter.get("role"),
            "team": frontmatter.get("team"),
            "owner": frontmatter.get("owner"),
            "relationships_count": 0,
            "confidence": 0.5,  # Lower confidence for v1
        }

    def _create_minimal_entry(self, filepath: Path) -> Dict[str, Any]:
        """Create minimal entry for entity without frontmatter."""
        relative_path = filepath.relative_to(self.brain_path)
        entity_type = self._infer_type_from_path(filepath)

        return {
            "$ref": str(relative_path),
            "$type": entity_type,
            "$status": "active",
            "$version": 1,
            "$updated": datetime.utcnow().isoformat() + "Z",
            "aliases": [],
            "confidence": 0.3,  # Low confidence
        }

    def _infer_type_from_path(self, filepath: Path) -> str:
        """Infer entity type from file path."""
        parts = filepath.parts

        type_map = {
            "People": "person",
            "Teams": "team",
            "Squads": "squad",
            "Projects": "project",
            "Domains": "domain",
            "Experiments": "experiment",
            "Systems": "system",
            "Brands": "brand",
        }

        for part in parts:
            if part in type_map:
                return type_map[part]

        if "Projects" in parts:
            return "project"

        return "unknown"

    def _filepath_to_slug(self, filepath: Path) -> str:
        """Convert filepath to slug."""
        slug = filepath.stem.lower().replace(" ", "-").replace("_", "-")
        import re

        slug = re.sub(r"[^a-z0-9-]", "", slug)
        return slug

    def _build_alias_index(self, entities: Dict[str, Any]) -> Dict[str, str]:
        """Build alias index from entities."""
        index = {}

        for slug, entry in entities.items():
            aliases = entry.get("aliases", [])
            for alias in aliases:
                if alias:
                    index[alias.lower()] = slug

        return index

    def _compute_stats(self, entities: Dict[str, Any]) -> Dict[str, int]:
        """Compute registry statistics."""
        stats = {
            "total_entities": len(entities),
            "active_entities": 0,
            "v2_entities": 0,
            "person": 0,
            "team": 0,
            "squad": 0,
            "project": 0,
            "domain": 0,
            "experiment": 0,
            "system": 0,
            "brand": 0,
            "unknown": 0,
        }

        for entry in entities.values():
            # Count active
            if entry.get("$status") == "active":
                stats["active_entities"] += 1

            # Count v2
            if entry.get("$version", 1) > 1 or entry.get("confidence", 0) > 0.5:
                stats["v2_entities"] += 1

            # Count by type
            entity_type = entry.get("$type", "unknown")
            if entity_type in stats:
                stats[entity_type] += 1
            else:
                stats["unknown"] += 1

        return stats


def build_registry_v2(brain_path: Path, incremental: bool = False) -> Dict[str, Any]:
    """Convenience function to build v2 registry."""
    builder = RegistryV2Builder(brain_path)
    return builder.build(incremental=incremental)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Build Brain v2 registry")
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Update existing registry instead of rebuilding",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without saving",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Custom output path",
    )

    args = parser.parse_args()

    # Default brain path
    if not args.brain_path:
        from path_resolver import get_paths

        paths = get_paths()
        args.brain_path = paths.user / "brain"

    # Build registry
    builder = RegistryV2Builder(args.brain_path)
    registry = builder.build(incremental=args.incremental)

    # Print stats
    stats = registry.get("stats", {})
    print(f"\nRegistry Statistics:")
    print(f"  Total entities: {stats.get('total_entities', 0)}")
    print(f"  Active: {stats.get('active_entities', 0)}")
    print(f"  V2 format: {stats.get('v2_entities', 0)}")
    print(f"\nBy type:")
    for type_name in ["person", "team", "squad", "project", "domain", "experiment"]:
        count = stats.get(type_name, 0)
        if count > 0:
            print(f"  {type_name}: {count}")

    # Save
    if not args.dry_run:
        if args.output:
            builder.registry_path = args.output
        builder.save(registry)

    return 0


if __name__ == "__main__":
    sys.exit(main())
