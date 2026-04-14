#!/usr/bin/env python3
"""
PM-OS Brain Schema Migrator (v5.0)

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
import logging
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

try:
    from schemas.brain import (
        ChangeEvent,
        EntityBase,
        EntityStatus,
        EntityType,
        EventType,
        FieldChange,
        Relationship,
    )
except ImportError:
    try:
        from pm_os_base.tools.core.entity_validator import (
            EntityType,
            Relationship,
        )
        # Minimal stubs for the rest
        EntityBase = None  # type: ignore[assignment,misc]
        EntityStatus = None  # type: ignore[assignment,misc]
        ChangeEvent = None  # type: ignore[assignment,misc]
        EventType = None  # type: ignore[assignment,misc]
        FieldChange = None  # type: ignore[assignment,misc]
    except ImportError:
        import enum

        class EntityType(enum.Enum):
            PERSON = "person"
            TEAM = "team"
            SQUAD = "squad"
            PROJECT = "project"
            DOMAIN = "domain"
            EXPERIMENT = "experiment"
            SYSTEM = "system"
            BRAND = "brand"

        class Relationship:
            def __init__(self, type: str, target: str):
                self.type = type
                self.target = target
            def model_dump(self):
                return {"type": self.type, "target": self.target}

        EntityBase = None  # type: ignore[assignment,misc]
        EntityStatus = None  # type: ignore[assignment,misc]
        ChangeEvent = None  # type: ignore[assignment,misc]
        EventType = None  # type: ignore[assignment,misc]
        FieldChange = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


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

        logger.info("Found %d entity files to migrate", len(all_files))

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
        now = datetime.now(timezone.utc)

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
        try:
            from temporal.event_helpers import EventHelper
        except ImportError:
            from temporal.event_helpers import EventHelper

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

    # Reverse map: entity type string -> target subdirectory name under Entities/
    TYPE_TO_DIRECTORY = {
        "person": "People",
        "team": "Teams",
        "squad": "Squads",
        "project": "Projects",
        "domain": "Domains",
        "experiment": "Experiments",
        "system": "Systems",
        "brand": "Brands",
        "component": "Components",
        "feature": "Features",
        "company": "Companies",
        "framework": "Frameworks",
        "research": "Research",
        "decision": "Decisions",
    }

    def refile_entity(
        self,
        entity_path: Path,
        target_dir: Path,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """
        Move an entity file to target directory and update its $id.

        Args:
            entity_path: Current path to entity file
            target_dir: Target directory to move into
            dry_run: If True, report without applying

        Returns:
            Dict with old_path, new_path, old_id, new_id, dry_run
        """
        try:
            from temporal.event_helpers import EventHelper
        except ImportError:
            from temporal.event_helpers import EventHelper

        content = entity_path.read_text(encoding="utf-8")
        frontmatter, body = self._parse_frontmatter(content)

        old_id = frontmatter.get("$id", "")
        entity_type = frontmatter.get("$type", "unknown")

        # Compute new $id from target path
        slug = entity_path.stem.lower().replace(" ", "-").replace("_", "-")
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        new_id = f"entity/{entity_type}/{slug}"

        new_path = target_dir / entity_path.name

        result = {
            "old_path": str(entity_path),
            "new_path": str(new_path),
            "old_id": old_id,
            "new_id": new_id,
            "entity_type": entity_type,
            "dry_run": dry_run,
        }

        if dry_run:
            return result

        # Update frontmatter
        if old_id != new_id:
            frontmatter["$id"] = new_id

        # Add refile event
        event = EventHelper.create_event(
            event_type="field_update",
            actor="system/schema_migrator",
            changes=[
                {
                    "field": "file_path",
                    "operation": "set",
                    "value": str(new_path),
                    "old_value": str(entity_path),
                },
            ],
            message=f"Refiled from {entity_path.parent.name}/ to {target_dir.name}/",
        )
        EventHelper.append_to_frontmatter(frontmatter, event)

        # Write to new location
        target_dir.mkdir(parents=True, exist_ok=True)
        fm_str = yaml.dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
        new_content = f"---\n{fm_str}---\n\n{body}"
        new_path.write_text(new_content, encoding="utf-8")

        # Remove old file (only if new file exists)
        if new_path.exists():
            entity_path.unlink()

        return result

    def refile_misplaced(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Scan root Entities/ for entities that belong in typed subdirectories.

        Entities in root Entities/ are matched by their $type to the
        TYPE_TO_DIRECTORY mapping and moved to the appropriate subdirectory.

        Args:
            dry_run: If True, report without applying

        Returns:
            Dict with: total_scanned, to_refile, refiled, errors, by_type, details
        """
        entities_dir = self.brain_path / "Entities"
        if not entities_dir.exists():
            return {"total_scanned": 0, "to_refile": 0}

        # Only scan files directly in Entities/, not in subdirectories
        root_files = [
            f for f in entities_dir.iterdir()
            if f.is_file() and f.suffix == ".md"
            and f.name.lower() not in ("readme.md", "index.md", "_index.md")
        ]

        results = {
            "total_scanned": len(root_files),
            "to_refile": 0,
            "refiled": 0,
            "errors": 0,
            "skipped": 0,
            "by_type": {},
            "details": [],
            "dry_run": dry_run,
        }

        for filepath in sorted(root_files):
            try:
                content = filepath.read_text(encoding="utf-8")
                frontmatter, _ = self._parse_frontmatter(content)
                entity_type = frontmatter.get("$type")

                if not entity_type:
                    results["skipped"] += 1
                    continue

                target_subdir = self.TYPE_TO_DIRECTORY.get(entity_type)
                if not target_subdir:
                    results["skipped"] += 1
                    continue

                target_dir = entities_dir / target_subdir
                results["to_refile"] += 1
                results["by_type"][entity_type] = results["by_type"].get(entity_type, 0) + 1

                refile_result = self.refile_entity(filepath, target_dir, dry_run=dry_run)
                results["details"].append(refile_result)

                if not dry_run:
                    results["refiled"] += 1

            except Exception as e:
                results["errors"] += 1
                results["details"].append({
                    "old_path": str(filepath),
                    "error": str(e),
                })

        return results


def _resolve_brain_path(args) -> Path:
    """Resolve brain path from args or default."""
    brain_path = getattr(args, "brain_path", None)
    if not brain_path:
        try:
            from pm_os_base.tools.core.path_resolver import get_paths
        except ImportError:
            from core.path_resolver import get_paths
        paths = get_paths()
        brain_path = paths.user / "brain"
    return brain_path


def _cmd_migrate(args) -> int:
    """Handle migrate command."""
    brain_path = _resolve_brain_path(args)
    dry_run = getattr(args, "dry_run", False)
    workers = getattr(args, "workers", 4)
    sequential = getattr(args, "sequential", False)

    migrator = SchemaMigrator(brain_path, dry_run=dry_run)
    result = migrator.migrate_all(parallel=not sequential, workers=workers)

    print(f"\nMigration complete:")
    print(f"  Migrated: {result['migrated']}")
    print(f"  Errors: {result['errors']}")
    if result["errors"] > 0:
        print(f"\nFirst errors:")
        for path, error in result["error_details"]:
            print(f"  {path}: {error}")

    return 0 if result["errors"] == 0 else 1


def _cmd_refile(args) -> int:
    """Handle refile command."""
    brain_path = _resolve_brain_path(args)
    dry_run = not args.apply

    migrator = SchemaMigrator(brain_path, dry_run=False)
    result = migrator.refile_misplaced(dry_run=dry_run)

    print(f"Refile scan: {result['total_scanned']} root files")
    print(f"  To refile: {result['to_refile']}")
    print(f"  Skipped (no type or unknown mapping): {result.get('skipped', 0)}")

    if result.get("by_type"):
        print(f"\n  By type:")
        for etype, count in sorted(result["by_type"].items(), key=lambda x: -x[1]):
            target = SchemaMigrator.TYPE_TO_DIRECTORY.get(etype, "?")
            print(f"    {etype} -> Entities/{target}/: {count}")

    if result.get("errors"):
        print(f"\n  Errors: {result['errors']}")
        for d in result["details"]:
            if "error" in d:
                print(f"    {d['old_path']}: {d['error']}")

    if dry_run:
        print(f"\nDry run -- no files moved. Use --apply to refile.")
    else:
        print(f"\nRefiled: {result.get('refiled', 0)} entities")
        if result.get("errors"):
            print(f"Errors: {result['errors']}")

    return 0


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate Brain v1 entities to v2 format"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # migrate command (default)
    migrate_parser = subparsers.add_parser("migrate", help="Migrate v1 to v2")
    migrate_parser.add_argument("--brain-path", type=Path, help="Path to brain directory")
    migrate_parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    migrate_parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    migrate_parser.add_argument("--sequential", action="store_true", help="Run sequentially (for debugging)")

    # refile command
    refile_parser = subparsers.add_parser("refile", help="Move misplaced root entities to typed subdirectories")
    refile_parser.add_argument("--brain-path", type=Path, help="Path to brain directory")
    refile_parser.add_argument("--dry-run", action="store_true", help="Preview refile plan without moving files")
    refile_parser.add_argument("--apply", action="store_true", help="Apply refile (move files)")

    args = parser.parse_args()

    if args.command == "refile":
        return _cmd_refile(args)

    # Default: migrate
    return _cmd_migrate(args)


if __name__ == "__main__":
    sys.exit(main())
