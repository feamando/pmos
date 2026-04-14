#!/usr/bin/env python3
"""
Mark Decisions and Experiments as standalone entities (v5.0).

These entity types are legitimately independent records that don't need
relationships to be considered healthy. This script marks orphan entities
of these types with $orphan_reason: standalone so they don't count against
the brain health score.

Usage:
    python3 mark_standalone_entities.py                # Dry run (preview)
    python3 mark_standalone_entities.py --apply        # Apply changes
    python3 mark_standalone_entities.py --type decision --apply
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Tuple, List

import yaml

logger = logging.getLogger(__name__)

# Entity types that should be marked as standalone
STANDALONE_ENTITY_TYPES = [
    "decision",      # Individual decisions are standalone records
    "experiment",    # Individual experiments are standalone records
]


def parse_content(content: str) -> Tuple[Dict[str, Any], str]:
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


def format_content(frontmatter: Dict[str, Any], body: str) -> str:
    """Format frontmatter and body back to markdown."""
    yaml_str = yaml.dump(
        frontmatter,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    return f"---\n{yaml_str}---{body}"


def mark_standalone_entities(
    brain_path: Path,
    entity_types: List[str],
    dry_run: bool = True,
) -> Dict[str, int]:
    """
    Mark orphan entities of specified types as standalone.

    Args:
        brain_path: Path to brain directory
        entity_types: List of entity types to mark as standalone
        dry_run: If True, preview changes without applying

    Returns:
        Dict with counts: {total: int, marked: int, skipped: int, errors: int}
    """
    stats = {
        "total_checked": 0,
        "marked_standalone": 0,
        "already_marked": 0,
        "has_relationships": 0,
        "errors": 0,
    }

    entity_files = list(brain_path.rglob("*.md"))
    entity_files = [
        f for f in entity_files
        if f.name.lower() not in ("readme.md", "index.md", "_index.md", "brain.md", "glossary.md")
        and ".snapshots" not in str(f)
        and ".schema" not in str(f)
        and "Inbox" not in str(f)
        and "Archive" not in str(f)
    ]

    for entity_path in entity_files:
        try:
            content = entity_path.read_text(encoding="utf-8")
            frontmatter, body = parse_content(content)

            if not frontmatter:
                continue

            entity_type = frontmatter.get("$type", "unknown")

            # Only process specified entity types
            if entity_type not in entity_types:
                continue

            stats["total_checked"] += 1

            relationships = frontmatter.get("$relationships", []) or []
            orphan_reason = frontmatter.get("$orphan_reason")

            # Skip if entity has relationships
            if relationships:
                stats["has_relationships"] += 1
                continue

            # Skip if already marked as standalone
            if orphan_reason == "standalone":
                stats["already_marked"] += 1
                continue

            # Mark as standalone
            frontmatter["$orphan_reason"] = "standalone"
            stats["marked_standalone"] += 1

            if not dry_run:
                # Try to use EventHelper if available
                try:
                    try:
                        from temporal.event_helpers import EventHelper
                    except ImportError:
                        from temporal.event_helpers import EventHelper

                    event = EventHelper.create_field_update(
                        actor="system/mark_standalone_entities",
                        field="$orphan_reason",
                        new_value="standalone",
                        old_value=orphan_reason,
                        message=f"Marked {entity_type} as standalone (legitimately independent)",
                    )
                    EventHelper.append_to_frontmatter(frontmatter, event)
                except ImportError:
                    # EventHelper not available, just update the field
                    pass

                new_content = format_content(frontmatter, body)
                entity_path.write_text(new_content, encoding="utf-8")

        except Exception as e:
            stats["errors"] += 1
            logger.warning("Error processing %s: %s", entity_path, e)
            continue

    return stats


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Mark Decisions and Experiments as standalone entities"
    )
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--type",
        type=str,
        choices=STANDALONE_ENTITY_TYPES + ["all"],
        default="all",
        help="Entity type to process (default: all)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry run)",
    )

    args = parser.parse_args()

    # Resolve brain path
    if not args.brain_path:
        try:
            from pm_os_base.tools.core.path_resolver import get_paths
            paths = get_paths()
            args.brain_path = paths.user / "brain"
        except ImportError:
            try:
                from core.path_resolver import get_paths
                paths = get_paths()
                args.brain_path = paths.user / "brain"
            except ImportError:
                args.brain_path = Path.cwd() / "user" / "brain"

    # Determine which types to process
    if args.type == "all":
        types_to_process = STANDALONE_ENTITY_TYPES
    else:
        types_to_process = [args.type]

    # Run the marking process
    print("=" * 60)
    print("Mark Standalone Entities")
    print("=" * 60)
    print(f"Brain path: {args.brain_path}")
    print(f"Entity types: {', '.join(types_to_process)}")
    print(f"Mode: {'APPLY CHANGES' if args.apply else 'DRY RUN (preview only)'}")
    print()

    stats = mark_standalone_entities(
        brain_path=args.brain_path,
        entity_types=types_to_process,
        dry_run=not args.apply,
    )

    # Print results
    print("Results:")
    print(f"  Total checked: {stats['total_checked']}")
    print(f"  {'Would mark' if not args.apply else 'Marked'} as standalone: {stats['marked_standalone']}")
    print(f"  Already marked: {stats['already_marked']}")
    print(f"  Has relationships (skipped): {stats['has_relationships']}")
    if stats["errors"] > 0:
        print(f"  Errors: {stats['errors']}")
    print()

    if not args.apply and stats["marked_standalone"] > 0:
        print("This was a dry run. Use --apply to apply changes.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
