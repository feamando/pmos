#!/usr/bin/env python3
"""
Slack Brain Writer - Phase 4

Takes analyzed Slack data and enriches the Brain:
- Updates/creates entity files
- Logs decisions
- Adds context to projects
- Maintains entity aliases

Usage:
    python3 slack_brain_writer.py [--analysis-dir PATH] [--dry-run]
    python3 slack_brain_writer.py --status
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# Add parent directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# ============================================================================
# CONFIGURATION
# ============================================================================

BRAIN_DIR = config_loader.get_root_path() / "user" / "brain"
ENTITIES_DIR = BRAIN_DIR / "Entities"
PROJECTS_DIR = BRAIN_DIR / "Projects"
DECISIONS_DIR = BRAIN_DIR / "Reasoning" / "Decisions"
INBOX_DIR = BRAIN_DIR / "Inbox" / "Slack"
ANALYZED_DIR = INBOX_DIR / "Analyzed"
STATE_FILE = INBOX_DIR / "brain_writer_state.json"
ALIASES_FILE = BRAIN_DIR / "entity_aliases.json"

# Entity type to directory mapping
ENTITY_DIRS = {
    "person": ENTITIES_DIR / "People",
    "project": PROJECTS_DIR,
    "squad": ENTITIES_DIR / "Squads",
    "system": ENTITIES_DIR / "Systems",
    "brand": ENTITIES_DIR / "Brands",
}

# Known entity aliases (loaded from file + defaults)
DEFAULT_ALIASES = {
    # People
    "jane": "Jane_Smith",
    "ng": "Jane_Smith",
    "@jane.smith": "Jane_Smith",
    "hamed": "Bob_Designer",
    "daniel": "Daniel_Unknown",
    # Squads/Projects
    "Meal Kit": "Meal_Kit",
    "goc": "Meal_Kit",
    "goodchop": "Meal_Kit",
    "gc": "Meal_Kit",
    "tpt": "Brand_B",
    "Brand B": "Brand_B",
    "factor": "Factor",
    "Growth Platform": "Growth_Platform",
    "vms": "Growth_Platform",
    "cross-selling": "Cross_Selling",
    "market integration": "Market_Integration",
    # Systems
    "shopify": "Shopify",
    "statsig": "Statsig",
    "tableau": "Tableau",
}

# ============================================================================
# STATE MANAGEMENT
# ============================================================================


def load_state() -> dict:
    """Load brain writer state."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "started_at": None,
        "last_updated": None,
        "analyses_processed": [],
        "entities_updated": [],
        "entities_created": [],
        "decisions_logged": 0,
        "context_added": 0,
    }


def save_state(state: dict):
    """Save brain writer state."""
    state["last_updated"] = datetime.now().isoformat()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def load_aliases() -> dict:
    """Load entity aliases from file + defaults."""
    aliases = DEFAULT_ALIASES.copy()
    if ALIASES_FILE.exists():
        with open(ALIASES_FILE, "r", encoding="utf-8") as f:
            file_aliases = json.load(f)
            aliases.update(file_aliases)
    return aliases


def save_aliases(aliases: dict):
    """Save entity aliases to file."""
    ALIASES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ALIASES_FILE, "w", encoding="utf-8") as f:
        json.dump(aliases, f, indent=2, sort_keys=True)


def print_status(state: dict):
    """Print brain writer status."""
    print("=" * 60)
    print("BRAIN WRITER STATUS")
    print("=" * 60)
    print(f"Started: {state.get('started_at', 'Not started')}")
    print(f"Last Updated: {state.get('last_updated', 'N/A')}")
    print(f"Analyses Processed: {len(state.get('analyses_processed', []))}")
    print(f"Entities Updated: {len(state.get('entities_updated', []))}")
    print(f"Entities Created: {len(state.get('entities_created', []))}")
    print(f"Decisions Logged: {state.get('decisions_logged', 0)}")
    print(f"Context Added: {state.get('context_added', 0)}")
    print("=" * 60)


# ============================================================================
# ENTITY RESOLUTION
# ============================================================================


def normalize_entity_name(name: str) -> str:
    """Normalize entity name for file naming."""
    # Remove special chars, convert spaces to underscores
    normalized = re.sub(r"[^\w\s-]", "", name)
    normalized = re.sub(r"\s+", "_", normalized.strip())
    return normalized.title()


def resolve_entity(name: str, entity_type: str, aliases: dict) -> Tuple[str, Path]:
    """
    Resolve entity name to canonical name and file path.

    Returns:
        Tuple of (canonical_name, file_path)
    """
    name_lower = name.lower().strip()

    # Check aliases
    if name_lower in aliases:
        canonical = aliases[name_lower]
    else:
        canonical = normalize_entity_name(name)

    # Determine directory
    entity_dir = ENTITY_DIRS.get(entity_type, ENTITIES_DIR)
    entity_dir.mkdir(parents=True, exist_ok=True)

    file_path = entity_dir / f"{canonical}.md"

    return canonical, file_path


def find_existing_entity(name: str, aliases: dict) -> Optional[Path]:
    """Try to find an existing entity file."""
    name_lower = name.lower().strip()

    # Check aliases
    if name_lower in aliases:
        canonical = aliases[name_lower]
        # Search in all entity dirs
        for entity_dir in ENTITY_DIRS.values():
            if entity_dir.exists():
                for file in entity_dir.glob("*.md"):
                    if file.stem.lower() == canonical.lower():
                        return file

    # Try direct match
    normalized = normalize_entity_name(name)
    for entity_dir in ENTITY_DIRS.values():
        if entity_dir.exists():
            candidate = entity_dir / f"{normalized}.md"
            if candidate.exists():
                return candidate

    return None


# ============================================================================
# BRAIN FILE OPERATIONS
# ============================================================================


def read_brain_file(path: Path) -> str:
    """Read a Brain file, return empty string if doesn't exist."""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def append_to_section(content: str, section: str, new_content: str) -> str:
    """
    Append content to a specific section in a markdown file.

    If section doesn't exist, creates it at the end.
    """
    section_header = f"## {section}"

    if section_header in content:
        # Find section and append before next section or end
        lines = content.split("\n")
        result = []
        in_section = False
        appended = False

        for i, line in enumerate(lines):
            if line.strip() == section_header:
                in_section = True
                result.append(line)
                continue

            if in_section and line.startswith("## ") and not appended:
                # New section starting, append before it
                result.append("")
                result.append(new_content)
                result.append("")
                appended = True
                in_section = False

            result.append(line)

        if in_section and not appended:
            # Section was at end of file
            result.append("")
            result.append(new_content)

        return "\n".join(result)
    else:
        # Section doesn't exist, add at end
        return f"{content.rstrip()}\n\n{section_header}\n\n{new_content}\n"


def create_entity_file(name: str, entity_type: str, context: str) -> str:
    """Create a new entity markdown file content."""
    template = f"""# {name}

**Type:** {entity_type}
**Created:** {datetime.now().strftime('%Y-%m-%d')}
**Source:** Slack extraction

## Overview

[Auto-generated from Slack mentions - needs manual review]

## Slack Context

{context}

## Related Entities

[To be filled]

## Notes

- Created automatically from Slack analysis
- Review and enrich manually

---
*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
    return template


def update_timestamp(content: str) -> str:
    """Update the last updated timestamp in a file."""
    timestamp_pattern = r"\*Last updated:.*\*"
    new_timestamp = f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*"

    if re.search(timestamp_pattern, content):
        return re.sub(timestamp_pattern, new_timestamp, content)
    else:
        return f"{content.rstrip()}\n\n---\n{new_timestamp}\n"


# ============================================================================
# WRITING LOGIC
# ============================================================================


def write_decision(
    decision: dict, channel_name: str, dry_run: bool = False
) -> Optional[Path]:
    """
    Write a decision to the Decisions directory.

    Returns path if written, None otherwise.
    """
    DECISIONS_DIR.mkdir(parents=True, exist_ok=True)

    # Generate filename from date and content
    date_str = decision.get("date", datetime.now().strftime("%Y-%m-%d"))
    what = decision.get("what", "Unknown decision")[:50]
    safe_what = re.sub(r"[^\w\s-]", "", what)[:30].strip().replace(" ", "_")

    filename = f"{date_str}_{safe_what}.md"
    filepath = DECISIONS_DIR / filename

    content = f"""# Decision: {decision.get('what', 'Unknown')}

**Date:** {date_str}
**Source:** Slack #{channel_name}
**Confidence:** {decision.get('confidence', 'medium')}

## Decision

{decision.get('what', '[No description]')}

## Participants

{', '.join(decision.get('who', ['Unknown']))}

## Context

{decision.get('context', '[No context provided]')}

---
*Extracted from Slack on {datetime.now().strftime('%Y-%m-%d')}*
"""

    if dry_run:
        print(f"  [DRY RUN] Would create decision: {filepath.name}")
        return None

    filepath.write_text(content, encoding="utf-8")
    return filepath


def update_entity_context(
    entity_name: str,
    entity_type: str,
    context: str,
    aliases: dict,
    state: dict,
    dry_run: bool = False,
) -> bool:
    """
    Update or create an entity file with new context.

    Returns True if successful.
    """
    canonical, file_path = resolve_entity(entity_name, entity_type, aliases)

    # Check if exists
    existing = find_existing_entity(entity_name, aliases)

    if existing:
        # Update existing file
        content = read_brain_file(existing)
        new_content = append_to_section(content, "Slack Context", context)
        new_content = update_timestamp(new_content)

        if dry_run:
            print(f"  [DRY RUN] Would update: {existing.name}")
            return True

        existing.write_text(new_content, encoding="utf-8")

        if str(existing) not in state.get("entities_updated", []):
            state.setdefault("entities_updated", []).append(str(existing))

        return True
    else:
        # Create new file
        content = create_entity_file(canonical, entity_type, context)

        if dry_run:
            print(f"  [DRY RUN] Would create: {file_path.name}")
            return True

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        state.setdefault("entities_created", []).append(str(file_path))

        # Add to aliases for future reference
        aliases[entity_name.lower()] = canonical

        return True


def process_analysis_file(
    filepath: Path, aliases: dict, state: dict, dry_run: bool = False
) -> dict:
    """
    Process a single analysis file and update Brain.

    Returns stats dict.
    """
    print(f"\nProcessing: {filepath.name}", file=sys.stderr)

    with open(filepath, "r", encoding="utf-8") as f:
        analysis = json.load(f)

    channel_name = analysis.get("channel_name", "unknown")
    stats = {
        "decisions": 0,
        "entities": 0,
        "blockers": 0,
        "actions": 0,
    }

    # Process decisions
    for decision in analysis.get("decisions", []):
        result = write_decision(decision, channel_name, dry_run)
        if result or dry_run:
            stats["decisions"] += 1

    # Process entities
    for entity in analysis.get("entities", []):
        name = entity.get("name", "")
        etype = entity.get("type", "unknown")
        context = entity.get("context", "")

        if name:
            # Format context
            context_entry = (
                f"- [{datetime.now().strftime('%Y-%m-%d')}] {context} (#{channel_name})"
            )
            success = update_entity_context(
                name, etype, context_entry, aliases, state, dry_run
            )
            if success:
                stats["entities"] += 1

    # Process blockers (as context on related entities/projects)
    for blocker in analysis.get("blockers", []):
        # Add as context to Brain inbox for manual processing
        stats["blockers"] += 1

    # Process action items (as context)
    for action in analysis.get("action_items", []):
        stats["actions"] += 1

    # Summary
    print(f"  Decisions: {stats['decisions']}", file=sys.stderr)
    print(f"  Entities: {stats['entities']}", file=sys.stderr)
    print(f"  Blockers: {stats['blockers']}", file=sys.stderr)
    print(f"  Actions: {stats['actions']}", file=sys.stderr)

    return stats


# ============================================================================
# MAIN PIPELINE
# ============================================================================


def find_analysis_files() -> list:
    """Find all analysis files."""
    if not ANALYZED_DIR.exists():
        return []
    return sorted(ANALYZED_DIR.glob("analysis_*.json"))


def run_brain_writer(dry_run: bool = False, resume: bool = True):
    """Run the brain writer pipeline."""
    state = load_state()
    aliases = load_aliases()

    if not state.get("started_at"):
        state["started_at"] = datetime.now().isoformat()
        save_state(state)

    # Find analysis files
    files = find_analysis_files()
    print(f"Found {len(files)} analysis files", file=sys.stderr)

    # Filter already processed
    if resume:
        processed_set = set(state.get("analyses_processed", []))
        files = [f for f in files if str(f) not in processed_set]
        print(f"Remaining after resume filter: {len(files)}", file=sys.stderr)

    if not files:
        print("No new analysis files to process", file=sys.stderr)
        return

    # Process files
    total_stats = defaultdict(int)

    for filepath in files:
        stats = process_analysis_file(filepath, aliases, state, dry_run)

        for key, val in stats.items():
            total_stats[key] += val

        if not dry_run:
            state.setdefault("analyses_processed", []).append(str(filepath))
            state["decisions_logged"] = (
                state.get("decisions_logged", 0) + stats["decisions"]
            )
            state["context_added"] = state.get("context_added", 0) + stats["entities"]
            save_state(state)

    # Save updated aliases
    if not dry_run:
        save_aliases(aliases)

    # Summary
    print("\n" + "=" * 60, file=sys.stderr)
    print("BRAIN WRITER COMPLETE", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"Files processed: {len(files)}", file=sys.stderr)
    print(f"Decisions logged: {total_stats['decisions']}", file=sys.stderr)
    print(f"Entities updated: {total_stats['entities']}", file=sys.stderr)
    print(f"Blockers noted: {total_stats['blockers']}", file=sys.stderr)
    print(f"Actions noted: {total_stats['actions']}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(description="Write analyzed Slack data to Brain")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written without making changes",
    )
    parser.add_argument(
        "--no-resume", action="store_true", help="Reprocess all analysis files"
    )
    parser.add_argument(
        "--status", action="store_true", help="Show brain writer status and exit"
    )

    args = parser.parse_args()

    if args.status:
        state = load_state()
        print_status(state)
        return

    run_brain_writer(dry_run=args.dry_run, resume=not args.no_resume)


if __name__ == "__main__":
    main()
