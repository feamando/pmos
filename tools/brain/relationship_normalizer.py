#!/usr/bin/env python3
"""
PM-OS Brain Relationship Normalizer

Normalizes all relationship targets to canonical $id format and deduplicates.
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from canonical_resolver import CanonicalResolver


@dataclass
class NormalizationResult:
    """Result of normalizing a single entity."""

    entity_path: Path
    canonical_id: str
    original_count: int
    normalized_count: int
    duplicates_removed: int
    orphans_found: List[str] = field(default_factory=list)
    changes_made: List[Dict[str, Any]] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


@dataclass
class BatchNormalizationResult:
    """Result of batch normalization."""

    total_entities: int
    entities_processed: int
    entities_modified: int
    relationships_normalized: int
    duplicates_removed: int
    orphans_found: int
    orphan_targets: List[Tuple[str, str]] = field(
        default_factory=list
    )  # (source, target)
    errors: List[str] = field(default_factory=list)


class RelationshipNormalizer:
    """
    Normalizes relationship targets to canonical $id format.

    Features:
    - Convert all target formats to entity/{type}/{slug}
    - Remove exact duplicates (same type + same normalized target)
    - Flag orphan references (targets that don't exist)
    - Generate detailed normalization report
    """

    def __init__(self, brain_path: Path):
        """
        Initialize the normalizer.

        Args:
            brain_path: Path to the brain directory
        """
        self.brain_path = brain_path
        self.resolver = CanonicalResolver(brain_path)

    def normalize_entity(
        self,
        entity_path: Path,
        dry_run: bool = True,
    ) -> NormalizationResult:
        """
        Normalize relationships in a single entity.

        Args:
            entity_path: Path to entity file
            dry_run: If True, don't write changes

        Returns:
            NormalizationResult with details
        """
        try:
            content = entity_path.read_text(encoding="utf-8")
            frontmatter, body = self._parse_content(content)
        except Exception as e:
            return NormalizationResult(
                entity_path=entity_path,
                canonical_id="",
                original_count=0,
                normalized_count=0,
                duplicates_removed=0,
                success=False,
                error=str(e),
            )

        canonical_id = frontmatter.get("$id", "")
        relationships = frontmatter.get("$relationships", [])

        if not relationships:
            return NormalizationResult(
                entity_path=entity_path,
                canonical_id=canonical_id,
                original_count=0,
                normalized_count=0,
                duplicates_removed=0,
            )

        original_count = len(relationships)
        orphans = []
        changes = []

        # Normalize each relationship
        normalized_relationships = []
        for rel in relationships:
            if not isinstance(rel, dict):
                continue

            target = rel.get("target", "")
            rel_type = rel.get("type", "")

            if not target:
                continue

            # Resolve to canonical
            canonical_target = self.resolver.resolve(target)

            if canonical_target:
                if canonical_target != target:
                    changes.append(
                        {
                            "type": "normalize",
                            "relationship_type": rel_type,
                            "old_target": target,
                            "new_target": canonical_target,
                        }
                    )

                new_rel = dict(rel)
                new_rel["target"] = canonical_target
                normalized_relationships.append(new_rel)
            else:
                # Orphan - keep but flag
                orphans.append(target)
                normalized_relationships.append(rel)

        # Deduplicate
        deduplicated = self._deduplicate(normalized_relationships)
        duplicates_removed = len(normalized_relationships) - len(deduplicated)

        if duplicates_removed > 0:
            changes.append(
                {
                    "type": "deduplicate",
                    "removed": duplicates_removed,
                }
            )

        result = NormalizationResult(
            entity_path=entity_path,
            canonical_id=canonical_id,
            original_count=original_count,
            normalized_count=len(deduplicated),
            duplicates_removed=duplicates_removed,
            orphans_found=orphans,
            changes_made=changes,
        )

        # Write if changes and not dry_run
        if changes and not dry_run:
            frontmatter["$relationships"] = deduplicated
            frontmatter["$updated"] = datetime.now(timezone.utc).isoformat()

            # Add normalization event
            if "$events" not in frontmatter:
                frontmatter["$events"] = []

            frontmatter["$events"].append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": "normalization",
                    "actor": "system/relationship_normalizer",
                    "changes": [
                        {
                            "field": "$relationships",
                            "operation": "normalize",
                            "count": len(changes),
                        }
                    ],
                }
            )

            new_content = self._rebuild_content(frontmatter, body)
            entity_path.write_text(new_content, encoding="utf-8")

        return result

    def normalize_all(
        self,
        dry_run: bool = True,
        progress_callback=None,
    ) -> BatchNormalizationResult:
        """
        Normalize all entities in brain.

        Args:
            dry_run: If True, don't write changes
            progress_callback: Optional callback(processed, total)

        Returns:
            BatchNormalizationResult with summary
        """
        # Build resolver index first
        self.resolver.build_index()

        entity_files = list(self.brain_path.rglob("*.md"))
        entity_files = [
            f
            for f in entity_files
            if f.name.lower() not in ("readme.md", "index.md", "_index.md")
            and ".snapshots" not in str(f)
            and ".schema" not in str(f)
            and ".events" not in str(f)
        ]

        result = BatchNormalizationResult(
            total_entities=len(entity_files),
            entities_processed=0,
            entities_modified=0,
            relationships_normalized=0,
            duplicates_removed=0,
            orphans_found=0,
        )

        for i, entity_path in enumerate(entity_files):
            entity_result = self.normalize_entity(entity_path, dry_run)

            result.entities_processed += 1

            if entity_result.success:
                if entity_result.changes_made:
                    result.entities_modified += 1
                    result.relationships_normalized += len(
                        [
                            c
                            for c in entity_result.changes_made
                            if c.get("type") == "normalize"
                        ]
                    )
                    result.duplicates_removed += entity_result.duplicates_removed

                if entity_result.orphans_found:
                    result.orphans_found += len(entity_result.orphans_found)
                    for orphan in entity_result.orphans_found:
                        result.orphan_targets.append(
                            (
                                entity_result.canonical_id or str(entity_path),
                                orphan,
                            )
                        )
            else:
                result.errors.append(f"{entity_path}: {entity_result.error}")

            if progress_callback:
                progress_callback(result.entities_processed, result.total_entities)

        return result

    def _deduplicate(self, relationships: List[Dict]) -> List[Dict]:
        """
        Remove duplicate relationships.

        Duplicates are defined as same (type, target) pair.
        """
        seen: Set[Tuple[str, str]] = set()
        deduplicated = []

        for rel in relationships:
            key = (rel.get("type", ""), rel.get("target", ""))
            if key not in seen:
                seen.add(key)
                deduplicated.append(rel)

        return deduplicated

    def get_normalization_report(
        self,
        result: BatchNormalizationResult,
    ) -> str:
        """Generate a human-readable normalization report."""
        lines = [
            "# Relationship Normalization Report",
            "",
            f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total entities | {result.total_entities} |",
            f"| Entities processed | {result.entities_processed} |",
            f"| Entities modified | {result.entities_modified} |",
            f"| Relationships normalized | {result.relationships_normalized} |",
            f"| Duplicates removed | {result.duplicates_removed} |",
            f"| Orphans found | {result.orphans_found} |",
            f"| Errors | {len(result.errors)} |",
            "",
        ]

        if result.orphan_targets:
            lines.extend(
                [
                    "## Orphan Targets",
                    "",
                    "| Source Entity | Target Reference |",
                    "|--------------|------------------|",
                ]
            )
            for source, target in result.orphan_targets[:50]:  # Limit output
                lines.append(f"| {source} | {target} |")

            if len(result.orphan_targets) > 50:
                lines.append(f"| ... | ({len(result.orphan_targets) - 50} more) |")
            lines.append("")

        if result.errors:
            lines.extend(
                [
                    "## Errors",
                    "",
                ]
            )
            for error in result.errors[:20]:
                lines.append(f"- {error}")
            if len(result.errors) > 20:
                lines.append(f"- ... ({len(result.errors) - 20} more)")
            lines.append("")

        return "\n".join(lines)

    def _parse_content(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Parse frontmatter and body."""
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

    def _rebuild_content(self, frontmatter: Dict[str, Any], body: str) -> str:
        """Rebuild file content from frontmatter and body."""
        yaml_content = yaml.dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
        return f"---\n{yaml_content}---{body}"


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Normalize Brain entity relationships")
    parser.add_argument(
        "action",
        choices=["normalize", "report"],
        help="Action to perform",
    )
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview without making changes (default)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (not dry run)",
    )
    parser.add_argument(
        "--entity",
        type=Path,
        help="Normalize single entity",
    )

    args = parser.parse_args()

    # Default brain path
    if not args.brain_path:
        from path_resolver import get_paths

        paths = get_paths()
        args.brain_path = paths.user / "brain"

    normalizer = RelationshipNormalizer(args.brain_path)
    dry_run = not args.apply

    if args.action == "normalize":
        if args.entity:
            # Single entity
            result = normalizer.normalize_entity(args.entity, dry_run)
            print(f"Entity: {result.entity_path}")
            print(f"Original relationships: {result.original_count}")
            print(f"After normalization: {result.normalized_count}")
            print(f"Duplicates removed: {result.duplicates_removed}")
            print(f"Orphans found: {len(result.orphans_found)}")
            if result.orphans_found:
                for orphan in result.orphans_found:
                    print(f"  - {orphan}")
            print(f"Changes: {len(result.changes_made)}")
            if dry_run:
                print("\n(Dry run - no changes written)")
        else:
            # Batch normalization
            def progress(processed, total):
                if processed % 100 == 0:
                    print(f"Progress: {processed}/{total}")

            result = normalizer.normalize_all(dry_run, progress)
            print("\n" + normalizer.get_normalization_report(result))
            if dry_run:
                print("(Dry run - no changes written. Use --apply to write changes)")

    elif args.action == "report":
        # Just generate report without changes
        result = normalizer.normalize_all(dry_run=True)
        print(normalizer.get_normalization_report(result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
