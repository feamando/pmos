#!/usr/bin/env python3
"""
Brain Updater - Changelog Append Tool

Scans context files and appends changelog entries to relevant Brain files.
Closes the feedback loop between episodic (daily context) and semantic (Brain) memory.

Usage:
    python brain_updater.py                           # Scan latest context, update Brain files
    python brain_updater.py --context FILE            # Scan specific context file
    python brain_updater.py --dry-run                 # Show what would be updated without writing
    python brain_updater.py --message "Custom note"   # Add custom changelog message
"""

import argparse
import os
import re
import sys
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add tools directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    print("Error: PyYAML required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# --- Configuration ---
# Use config_loader for proper path resolution
ROOT_PATH = config_loader.get_root_path()
USER_PATH = ROOT_PATH / "user"
BRAIN_DIR = str(USER_PATH / "brain")
REGISTRY_FILE = os.path.join(BRAIN_DIR, "registry.yaml")
CONTEXT_DIR = str(USER_PATH / "context")


def load_registry() -> Dict:
    """Load the entity registry from YAML."""
    if not os.path.exists(REGISTRY_FILE):
        return {}
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_alias_index(registry: Dict) -> Dict[str, Tuple[str, str, str]]:
    """Build reverse index: alias -> (category, entity_id, file_path)"""
    index = {}
    for category in ["projects", "entities", "architecture", "decisions"]:
        if category not in registry or registry[category] is None:
            continue
        for entity_id, entity_data in registry[category].items():
            if not isinstance(entity_data, dict):
                continue
            file_path = entity_data.get("file", "")
            aliases = entity_data.get("aliases", [])
            for alias in [entity_id] + (aliases if aliases else []):
                if alias:
                    index[alias.lower()] = (category, entity_id, file_path)
    return index


def get_latest_context_file() -> Optional[str]:
    """Find the most recent context file."""
    pattern = os.path.join(CONTEXT_DIR, "*-context.md")
    files = sorted(glob(pattern))
    return files[-1] if files else None


def scan_for_entities(text: str, alias_index: Dict) -> Dict[str, Dict]:
    """Scan text for entity mentions, return matches with counts."""
    from collections import defaultdict

    matches = defaultdict(lambda: {"count": 0, "category": "", "file": ""})
    text_lower = text.lower()

    for alias, (category, entity_id, file_path) in alias_index.items():
        escaped_alias = re.escape(alias)
        pattern = r"\b" + escaped_alias + r"\b"
        found = re.findall(pattern, text_lower)
        if found:
            matches[entity_id]["count"] += len(found)
            matches[entity_id]["category"] = category
            matches[entity_id]["file"] = file_path

    return dict(matches)


def extract_key_updates(context_content: str, entity_id: str) -> List[str]:
    """
    Extract key updates related to an entity from context content.
    Returns a list of bullet points.
    """
    updates = []
    lines = context_content.split("\n")

    # Simple extraction: find lines mentioning the entity in key sections
    entity_lower = entity_id.lower().replace("_", " ")
    in_relevant_section = False
    relevant_sections = [
        "key decisions",
        "blockers",
        "action items",
        "updates",
        "status",
    ]

    for line in lines:
        line_lower = line.lower()

        # Check if we're in a relevant section
        if any(section in line_lower for section in relevant_sections):
            in_relevant_section = True
        elif line.startswith("## ") or line.startswith("# "):
            in_relevant_section = False

        # If line mentions entity and we're in relevant section, capture it
        if in_relevant_section and entity_lower in line_lower:
            # Clean up the line
            cleaned = line.strip().lstrip("*-").strip()
            if cleaned and len(cleaned) > 10:  # Skip very short lines
                updates.append(cleaned[:150])  # Truncate long lines

    return updates[:3]  # Max 3 updates per entity


def update_section(
    file_path: str, section_header: str, new_content: str, dry_run: bool = False
) -> bool:
    """
    Replace the content of a specific markdown section with new content.
    If the section doesn't exist, it is appended to the end (before Changelog if present).

    Args:
        file_path: Relative path to Brain file.
        section_header: Header title (e.g. "Current State" for "## Current State").
        new_content: The new text content for the section.
        dry_run: If True, only print changes.
    """
    full_path = os.path.join(BRAIN_DIR, file_path)

    if not os.path.exists(full_path):
        return False

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    header_pattern = f"(## {re.escape(section_header)}\\n)"
    # Pattern to find content until next header or end of file
    # Non-greedy match until the next "## " or end of string
    section_pattern = f"{header_pattern}(.*?)(?=\\n## |\\Z)"

    formatted_content = new_content.strip() + "\n"

    if re.search(header_pattern, content):
        # Section exists, replace it
        new_file_content = re.sub(
            section_pattern, f"\\1{formatted_content}", content, flags=re.DOTALL
        )
    else:
        # Section doesn't exist, insert it
        # Try to insert before Changelog, otherwise at end
        new_section_block = f"\n## {section_header}\n{formatted_content}"

        if "## Changelog" in content:
            new_file_content = content.replace(
                "## Changelog", f"{new_section_block}\n## Changelog"
            )
        else:
            new_file_content = content.rstrip() + "\n" + new_section_block

    if dry_run:
        print(f"  [DRY-RUN] Would update section '{section_header}' in {file_path}")
        return True

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(new_file_content)

    return True


def _is_v2_entity(content: str) -> bool:
    """Check if entity content is v2 format."""
    return "$schema" in content and "$events" in content


def _append_v2_event(
    full_path: str,
    content: str,
    date: str,
    message: str,
    actor: str = "system/brain_updater",
    dry_run: bool = False,
) -> bool:
    """
    Append an event to a v2 entity's $events log.

    Returns True if successful, False otherwise.
    """
    # Parse YAML frontmatter
    if not content.startswith("---"):
        return False

    parts = content.split("---", 2)
    if len(parts) < 3:
        return False

    try:
        frontmatter = yaml.safe_load(parts[1])
        if not frontmatter:
            return False
    except yaml.YAMLError:
        return False

    body = parts[2]

    # Use EventHelper for standardized event creation
    sys.path.insert(0, str(Path(__file__).parent))
    from event_helpers import EventHelper

    correlation_id = f"context-{date}"

    # Check for duplicate (same message on same day)
    existing_events = frontmatter.get("$events", [])
    for ev in existing_events:
        if (
            ev.get("correlation_id") == correlation_id
            and ev.get("message") == message
        ):
            return False  # Already logged

    # Create event via EventHelper
    new_event = EventHelper.create_event(
        event_type="field_update",
        actor=actor,
        changes=[
            {
                "field": "context_mention",
                "operation": "append",
                "value": message,
            }
        ],
        message=message,
        correlation_id=correlation_id,
    )

    # Append event (handles $version + $updated + compaction)
    EventHelper.append_to_frontmatter(frontmatter, new_event)

    if dry_run:
        print(f"  [DRY-RUN] Would append v2 event to {full_path}:")
        print(f"    {message}")
        return True

    # Write back
    new_content = (
        "---\n"
        + yaml.dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
        + "---"
        + body
    )

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return True


def append_changelog_entry(
    file_path: str, date: str, message: str, dry_run: bool = False
) -> bool:
    """
    Append a changelog entry to a Brain file.

    Supports both v1 (## Changelog section) and v2 ($events) formats.
    For v2 entities, appends to $events log instead of changelog section.

    Returns True if successful, False otherwise.
    """
    full_path = os.path.join(BRAIN_DIR, file_path)

    if not os.path.exists(full_path):
        return False

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check if v2 entity - use events instead of changelog
    if _is_v2_entity(content):
        return _append_v2_event(full_path, content, date, message, dry_run=dry_run)

    # V1 format: no $events support, use changelog section
    import logging

    logging.getLogger(__name__).warning(
        "v1 entity without $events: %s — skipping event logging, using changelog section",
        file_path,
    )

    # Check if changelog section exists
    if "## Changelog" not in content:
        # Add changelog section at the end
        content = content.rstrip() + "\n\n## Changelog\n"

    # Find the changelog section and insert entry
    changelog_pattern = r"(## Changelog\n)"
    entry = f"- **{date}:** {message}\n"

    # Check if this exact entry already exists (prevent duplicates)
    if entry.strip() in content:
        return False

    # Insert after the Changelog header
    new_content = re.sub(changelog_pattern, r"\1" + entry, content, count=1)

    if dry_run:
        print(f"  [DRY-RUN] Would append to {file_path}:")
        print(f"    {entry.strip()}")
        return True

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Append changelog entries to Brain files based on context"
    )
    parser.add_argument(
        "--context", type=str, help="Path to specific context file to scan"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without writing",
    )
    parser.add_argument(
        "--message",
        type=str,
        help="Custom changelog message (applied to all matched entities)",
    )
    parser.add_argument(
        "--min-mentions",
        type=int,
        default=2,
        help="Minimum mentions required to trigger update (default: 2)",
    )
    parser.add_argument(
        "--section", type=str, help='Section header to update (e.g. "Current State")'
    )
    parser.add_argument("--content", type=str, help="New content for the section")
    parser.add_argument(
        "--file",
        type=str,
        help="Specific Brain file path to update (required for --section)",
    )

    args = parser.parse_args()

    # Mode: Single Section Update
    if args.section and args.content and args.file:
        success = update_section(args.file, args.section, args.content, args.dry_run)
        if success:
            print(f"Updated section '{args.section}' in {args.file}")
        else:
            print(f"Failed to update {args.file}")
        return

    # Load registry
    registry = load_registry()
    if not registry:
        print("Error: Could not load registry", file=sys.stderr)
        sys.exit(1)

    # Build alias index
    alias_index = build_alias_index(registry)

    # Get context file
    context_file = args.context or get_latest_context_file()
    if not context_file:
        print("Error: No context file found", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning: {os.path.basename(context_file)}", file=sys.stderr)

    with open(context_file, "r", encoding="utf-8") as f:
        context_content = f.read()

    # Extract date from context filename or use today
    filename = os.path.basename(context_file)
    date_match = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
    context_date = (
        date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d")
    )

    # Scan for entities
    matches = scan_for_entities(context_content, alias_index)

    # Filter by minimum mentions
    significant_matches = {
        k: v for k, v in matches.items() if v["count"] >= args.min_mentions
    }

    if not significant_matches:
        print("No significant entity mentions found.", file=sys.stderr)
        return

    print(
        f"\nFound {len(significant_matches)} entities with {args.min_mentions}+ mentions:"
    )
    print("=" * 60)

    updated_count = 0
    skipped_count = 0

    for entity_id, data in sorted(
        significant_matches.items(), key=lambda x: x[1]["count"], reverse=True
    ):
        file_path = data["file"]
        full_path = os.path.join(BRAIN_DIR, file_path)

        print(f"\n{entity_id} ({data['count']} mentions)")
        print(f"  File: Brain/{file_path}")

        if not os.path.exists(full_path):
            print(f"  [SKIP] File does not exist")
            skipped_count += 1
            continue

        # Determine message
        if args.message:
            message = args.message
        else:
            # Auto-generate message from context
            updates = extract_key_updates(context_content, entity_id)
            if updates:
                message = f"Context update: {updates[0]}"
            else:
                message = f"Mentioned in daily context ({data['count']}x)"

        # Append changelog entry
        success = append_changelog_entry(file_path, context_date, message, args.dry_run)

        if success:
            print(f"  [{'DRY-RUN' if args.dry_run else 'UPDATED'}] {message[:60]}...")
            updated_count += 1
        else:
            print(f"  [SKIP] Entry already exists or file missing")
            skipped_count += 1

    print("\n" + "=" * 60)
    print(f"Summary: {updated_count} updated, {skipped_count} skipped")
    if args.dry_run:
        print("(Dry run - no files were modified)")


if __name__ == "__main__":
    main()
