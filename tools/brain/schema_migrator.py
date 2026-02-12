#!/usr/bin/env python3
"""
PM-OS Brain Schema Migrator

Migrates Brain v1 entities to v2 format with temporal tracking and metadata.

Features:
- Parse existing frontmatter (if any)
- Infer entity type from directory/filename
- Generate unique $id from path
- Extract relationships from wiki-links
- Create initial $events log
- Set $version=1, $confidence based on data quality
- Preserve human-readable body unchanged
"""

import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Add common to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from schemas.brain import (
    ChangeEvent,
    EntityBase,
    EntityStatus,
    EntityType,
    EventType,
    FieldChange,
    Relationship,
)


class SchemaMigrator:
    """Migrates Brain v1 entities to v2 format."""

    # Map directory names to entity types
    DIRECTORY_TYPE_MAP = {
        "People": EntityType.PERSON,
        "Teams": EntityType.TEAM,
        "Squads": EntityType.SQUAD,
        "Projects": EntityType.PROJECT,
        "Domains": EntityType.DOMAIN,
        "Experiments": EntityType.EXPERIMENT,
        "Systems": EntityType.SYSTEM,
        "Brands": EntityType.BRAND,
    }

    # Source reliability scores
    SOURCE_RELIABILITY = {
        "hr_system": 0.95,
        "jira": 0.85,
        "github": 0.85,
        "confluence": 0.80,
        "slack": 0.75,
        "manual": 0.70,
        "auto_generated": 0.50,
        "unknown": 0.50,
    }

    def __init__(self, brain_path: Path, dry_run: bool = False):
        """
        Initialize the migrator.

        Args:
            brain_path: Path to the brain directory
            dry_run: If True, don't write files
        """
        self.brain_path = brain_path
        self.dry_run = dry_run
        self.migrated_count = 0
        self.error_count = 0
        self.errors: List[Tuple[Path, str]] = []

    def migrate_all(self, parallel: bool = True, workers: int = 4) -> Dict[str, Any]:
        """
        Migrate all entities in the brain.

        Args:
            parallel: Use parallel processing
            workers: Number of worker threads

        Returns:
            Migration summary
        """
        entities_path = self.brain_path / "Entities"
        projects_path = self.brain_path / "Projects"

        all_files = []

        # Collect entity files
        if entities_path.exists():
            all_files.extend(entities_path.rglob("*.md"))
        if projects_path.exists():
            all_files.extend(projects_path.rglob("*.md"))

        # Filter out README and index files
        all_files = [
            f
            for f in all_files
            if f.name.lower() not in ("readme.md", "index.md", "_index.md")
        ]

        print(f"Found {len(all_files)} entity files to migrate")

        if parallel and len(all_files) > 10:
            return self._migrate_parallel(all_files, workers)
        else:
            return self._migrate_sequential(all_files)

    def _migrate_parallel(self, files: List[Path], workers: int) -> Dict[str, Any]:
        """Migrate files in parallel."""
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(self.migrate_file, f): f for f in files}

            for future in as_completed(futures):
                filepath = futures[future]
                try:
                    future.result()
                except Exception as e:
                    self.errors.append((filepath, str(e)))
                    self.error_count += 1

        return self._get_summary()

    def _migrate_sequential(self, files: List[Path]) -> Dict[str, Any]:
        """Migrate files sequentially."""
        for filepath in files:
            try:
                self.migrate_file(filepath)
            except Exception as e:
                self.errors.append((filepath, str(e)))
                self.error_count += 1

        return self._get_summary()

    def migrate_file(self, filepath: Path) -> bool:
        """
        Migrate a single entity file to v2 format.

        Args:
            filepath: Path to the entity file

        Returns:
            True if migrated successfully
        """
        content = filepath.read_text(encoding="utf-8")

        # Check if already v2 format
        if self._is_v2_entity(content):
            return False

        # Parse existing content
        frontmatter, body = self._parse_frontmatter(content)

        # Infer entity type
        entity_type = self._infer_entity_type(filepath)

        # Generate entity ID
        entity_id = self._generate_entity_id(filepath, entity_type)

        # Extract name from filename or frontmatter
        name = frontmatter.get("name") or self._name_from_filename(filepath)

        # Extract relationships from wiki-links
        relationships = self._extract_relationships(body, frontmatter)

        # Calculate confidence
        confidence = self._calculate_confidence(frontmatter, body)

        # Determine source
        source = frontmatter.get("source", "unknown")

        # Build v2 frontmatter
        v2_frontmatter = self._build_v2_frontmatter(
            entity_id=entity_id,
            entity_type=entity_type,
            name=name,
            source=source,
            confidence=confidence,
            relationships=relationships,
            existing_frontmatter=frontmatter,
        )

        # Combine v2 frontmatter with body
        v2_content = self._format_v2_content(v2_frontmatter, body)

        # Write if not dry run
        if not self.dry_run:
            filepath.write_text(v2_content, encoding="utf-8")

        self.migrated_count += 1
        return True

    def _is_v2_entity(self, content: str) -> bool:
        """Check if content is already in v2 format."""
        return "$schema" in content and "$id" in content

    def _parse_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter from content."""
        if not content.startswith("---"):
            return {}, content

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content

        try:
            frontmatter = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            frontmatter = {}

        body = parts[2].strip()
        return frontmatter, body

    def _infer_entity_type(self, filepath: Path) -> EntityType:
        """Infer entity type from file path."""
        parts = filepath.parts

        # Check directory names
        for part in parts:
            if part in self.DIRECTORY_TYPE_MAP:
                return self.DIRECTORY_TYPE_MAP[part]

        # Default to project for Projects directory
        if "Projects" in parts:
            return EntityType.PROJECT

        return EntityType.PROJECT  # Default

    def _generate_entity_id(self, filepath: Path, entity_type: EntityType) -> str:
        """Generate unique entity ID from filepath."""
        # Use filename without extension as slug
        slug = filepath.stem.lower().replace(" ", "-").replace("_", "-")
        # Remove special characters
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        return f"entity/{entity_type.value}/{slug}"

    def _name_from_filename(self, filepath: Path) -> str:
        """Extract display name from filename."""
        name = filepath.stem.replace("_", " ").replace("-", " ")
        return name.title()

    def _extract_relationships(
        self, body: str, frontmatter: Dict[str, Any]
    ) -> List[Relationship]:
        """Extract relationships from wiki-links and frontmatter."""
        relationships = []

        # Extract wiki-links from body
        wiki_link_pattern = r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]"
        matches = re.findall(wiki_link_pattern, body)

        for match in matches:
            # Convert wiki-link to entity reference
            target = match.lower().replace(" ", "-").replace("_", "-")
            if "/" not in target:
                target = f"entity/unknown/{target}"

            relationships.append(Relationship(type="related_to", target=target))

        # Extract from frontmatter fields
        if "manager" in frontmatter:
            target = self._normalize_reference(frontmatter["manager"])
            relationships.append(Relationship(type="reports_to", target=target))

        if "team" in frontmatter:
            target = self._normalize_reference(frontmatter["team"])
            relationships.append(Relationship(type="member_of", target=target))

        if "owner" in frontmatter:
            target = self._normalize_reference(frontmatter["owner"])
            relationships.append(Relationship(type="owned_by", target=target))

        return relationships

    def _normalize_reference(self, ref: str) -> str:
        """Normalize a reference to entity ID format."""
        if ref.startswith("entity/"):
            return ref
        slug = ref.lower().replace(" ", "-").replace("_", "-")
        slug = re.sub(r"[^a-z0-9-/]", "", slug)
        return f"entity/unknown/{slug}"

    def _calculate_confidence(self, frontmatter: Dict[str, Any], body: str) -> float:
        """
        Calculate confidence score.

        Formula: completeness(40%) + source_reliability(40%) + freshness(20%)
        """
        # Completeness: based on fields populated
        required_fields = ["name", "description"]
        optional_fields = ["tags", "status", "created", "updated"]
        filled = sum(1 for f in required_fields + optional_fields if f in frontmatter)
        completeness = filled / len(required_fields + optional_fields)

        # Source reliability
        source = frontmatter.get("source", "unknown")
        reliability = self.SOURCE_RELIABILITY.get(source, 0.5)

        # Freshness: assume fresh for migration
        freshness = 0.8

        return completeness * 0.4 + reliability * 0.4 + freshness * 0.2

    def _build_v2_frontmatter(
        self,
        entity_id: str,
        entity_type: EntityType,
        name: str,
        source: str,
        confidence: float,
        relationships: List[Relationship],
        existing_frontmatter: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build v2 frontmatter from parsed data."""
        now = datetime.utcnow()

        # Core v2 fields
        v2 = {
            "$schema": f"brain://entity/{entity_type.value}/v1",
            "$id": entity_id,
            "$type": entity_type.value,
            "$version": 1,
            "$created": existing_frontmatter.get("created", now.isoformat() + "Z"),
            "$updated": now.isoformat() + "Z",
            "$confidence": round(confidence, 2),
            "$source": source,
            "$status": existing_frontmatter.get("status", "active"),
            "$relationships": [r.model_dump() for r in relationships],
            "$tags": existing_frontmatter.get("tags", []),
            "$aliases": existing_frontmatter.get("aliases", []),
            "$events": [],
            "name": name,
        }

        # Copy over other existing fields
        skip_fields = {
            "name",
            "tags",
            "aliases",
            "status",
            "created",
            "updated",
            "source",
            "manager",
            "team",
            "owner",
        }
        for key, value in existing_frontmatter.items():
            if key not in skip_fields and not key.startswith("$"):
                v2[key] = value

        # Add migration event via EventHelper
        sys.path.insert(0, str(Path(__file__).parent))
        from event_helpers import EventHelper

        event = EventHelper.create_event(
            event_type="entity_create",
            actor="system/schema_migrator",
            changes=[
                {
                    "field": "$schema",
                    "operation": "set",
                    "value": f"brain://entity/{entity_type.value}/v1",
                }
            ],
            message="Migrated from v1 to v2 schema",
        )
        EventHelper.append_to_frontmatter(
            v2, event, increment_version=False, update_timestamp=False
        )

        return v2

    def _format_v2_content(self, frontmatter: Dict[str, Any], body: str) -> str:
        """Format v2 content with frontmatter and body."""
        # Custom YAML dump for better formatting
        fm_str = yaml.dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
        return f"---\n{fm_str}---\n\n{body}"

    def _get_summary(self) -> Dict[str, Any]:
        """Get migration summary."""
        return {
            "migrated": self.migrated_count,
            "errors": self.error_count,
            "error_details": self.errors[:10],  # First 10 errors
            "dry_run": self.dry_run,
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate Brain v1 entities to v2 format"
    )
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Run sequentially (for debugging)",
    )

    args = parser.parse_args()

    # Default brain path
    if not args.brain_path:
        from path_resolver import get_paths

        paths = get_paths()
        args.brain_path = paths.user / "brain"

    migrator = SchemaMigrator(args.brain_path, dry_run=args.dry_run)
    result = migrator.migrate_all(
        parallel=not args.sequential,
        workers=args.workers,
    )

    print(f"\nMigration complete:")
    print(f"  Migrated: {result['migrated']}")
    print(f"  Errors: {result['errors']}")
    if result["errors"] > 0:
        print(f"\nFirst errors:")
        for path, error in result["error_details"]:
            print(f"  {path}: {error}")

    return 0 if result["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
