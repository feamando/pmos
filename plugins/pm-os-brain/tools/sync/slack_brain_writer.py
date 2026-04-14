#!/usr/bin/env python3
"""
Slack Brain Writer (v5.0)

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
import logging
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# v5 imports
try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from core.config_loader import get_config

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    get_paths = None

try:
    from pm_os_base.tools.core.connector_bridge import get_auth
except ImportError:
    get_auth = None


# ---------------------------------------------------------------------------
# Configuration (config-driven, zero hardcoded values)
# ---------------------------------------------------------------------------

def _resolve_brain_dir() -> Path:
    """Resolve brain directory via path_resolver or config."""
    if get_paths is not None:
        try:
            return get_paths().brain
        except Exception:
            pass
    config = get_config()
    if config.user_path:
        return config.user_path / "brain"
    return Path.cwd() / "user" / "brain"


def _get_brain_paths() -> dict:
    """Get all brain sub-paths needed by the writer."""
    brain_dir = _resolve_brain_dir()
    return {
        "brain_dir": brain_dir,
        "entities_dir": brain_dir / "Entities",
        "projects_dir": brain_dir / "Projects",
        "decisions_dir": brain_dir / "Reasoning" / "Decisions",
        "inbox_dir": brain_dir / "Inbox" / "Slack",
        "analyzed_dir": brain_dir / "Inbox" / "Slack" / "Analyzed",
        "state_file": brain_dir / "Inbox" / "Slack" / "brain_writer_state.json",
        "aliases_file": brain_dir / "entity_aliases.json",
    }


# Entity type to directory mapping (relative to brain_dir)
ENTITY_TYPE_SUBDIRS = {
    "person": "Entities/People",
    "project": "Projects",
    "squad": "Entities/Squads",
    "system": "Entities/Systems",
    "brand": "Entities/Brands",
}


def _get_entity_dir(entity_type: str) -> Path:
    """Get entity directory for a given type."""
    brain_dir = _resolve_brain_dir()
    subdir = ENTITY_TYPE_SUBDIRS.get(entity_type, "Entities")
    return brain_dir / subdir


def _load_configured_aliases() -> dict:
    """
    Load entity aliases from config + file. No hardcoded aliases.

    Aliases can be configured in:
    - config.yaml: integrations.slack.entity_aliases
    - entity_aliases.json in brain directory
    """
    aliases = {}

    # Load from config.yaml
    config = get_config()
    config_aliases = config.get("integrations.slack.entity_aliases", {}) or {}
    aliases.update(config_aliases)

    # Load from file
    paths = _get_brain_paths()
    aliases_file = paths["aliases_file"]
    if aliases_file.exists():
        try:
            with open(aliases_file, "r", encoding="utf-8") as f:
                file_aliases = json.load(f)
                aliases.update(file_aliases)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("Failed to load aliases file: %s", e)

    return aliases


# ---------------------------------------------------------------------------
# State Management
# ---------------------------------------------------------------------------

def load_state() -> dict:
    """Load brain writer state."""
    paths = _get_brain_paths()
    if paths["state_file"].exists():
        with open(paths["state_file"], "r", encoding="utf-8") as f:
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
    paths = _get_brain_paths()
    state["last_updated"] = datetime.now().isoformat()
    paths["state_file"].parent.mkdir(parents=True, exist_ok=True)
    with open(paths["state_file"], "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def save_aliases(aliases: dict):
    """Save entity aliases to file."""
    paths = _get_brain_paths()
    paths["aliases_file"].parent.mkdir(parents=True, exist_ok=True)
    with open(paths["aliases_file"], "w", encoding="utf-8") as f:
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


# ---------------------------------------------------------------------------
# Entity Resolution
# ---------------------------------------------------------------------------

def normalize_entity_name(name: str) -> str:
    """Normalize entity name for file naming."""
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
    entity_dir = _get_entity_dir(entity_type)
    entity_dir.mkdir(parents=True, exist_ok=True)

    file_path = entity_dir / f"{canonical}.md"

    return canonical, file_path


def find_existing_entity(name: str, aliases: dict) -> Optional[Path]:
    """Try to find an existing entity file."""
    name_lower = name.lower().strip()

    # Check aliases
    if name_lower in aliases:
        canonical = aliases[name_lower]
        for entity_type in ENTITY_TYPE_SUBDIRS:
            entity_dir = _get_entity_dir(entity_type)
            if entity_dir.exists():
                for file in entity_dir.glob("*.md"):
                    if file.stem.lower() == canonical.lower():
                        return file

    # Try direct match
    normalized = normalize_entity_name(name)
    for entity_type in ENTITY_TYPE_SUBDIRS:
        entity_dir = _get_entity_dir(entity_type)
        if entity_dir.exists():
            candidate = entity_dir / f"{normalized}.md"
            if candidate.exists():
                return candidate

    return None


# ---------------------------------------------------------------------------
# Brain File Operations
# ---------------------------------------------------------------------------

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
        lines = content.split("\n")
        result = []
        in_section = False
        appended = False

        for line in lines:
            if line.strip() == section_header:
                in_section = True
                result.append(line)
                continue

            if in_section and line.startswith("## ") and not appended:
                result.append("")
                result.append(new_content)
                result.append("")
                appended = True
                in_section = False

            result.append(line)

        if in_section and not appended:
            result.append("")
            result.append(new_content)

        return "\n".join(result)
    else:
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


# ---------------------------------------------------------------------------
# Writing Logic
# ---------------------------------------------------------------------------

def write_decision(
    decision: dict, channel_name: str, dry_run: bool = False
) -> Optional[Path]:
    """
    Write a decision to the Decisions directory.

    Returns path if written, None otherwise.
    """
    paths = _get_brain_paths()
    decisions_dir = paths["decisions_dir"]
    decisions_dir.mkdir(parents=True, exist_ok=True)

    date_str = decision.get("date", datetime.now().strftime("%Y-%m-%d"))
    what = decision.get("what", "Unknown decision")[:50]
    safe_what = re.sub(r"[^\w\s-]", "", what)[:30].strip().replace(" ", "_")

    filename = f"{date_str}_{safe_what}.md"
    filepath = decisions_dir / filename

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
        logger.info("[DRY RUN] Would create decision: %s", filepath.name)
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

    existing = find_existing_entity(entity_name, aliases)

    if existing:
        content = read_brain_file(existing)
        new_content = append_to_section(content, "Slack Context", context)
        new_content = update_timestamp(new_content)

        if dry_run:
            logger.info("[DRY RUN] Would update: %s", existing.name)
            return True

        existing.write_text(new_content, encoding="utf-8")

        if str(existing) not in state.get("entities_updated", []):
            state.setdefault("entities_updated", []).append(str(existing))

        return True
    else:
        content = create_entity_file(canonical, entity_type, context)

        if dry_run:
            logger.info("[DRY RUN] Would create (needs_review): %s", file_path.name)
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
    logger.info("Processing: %s", filepath.name)

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
        stats["blockers"] += 1

    # Process action items (as context)
    for action in analysis.get("action_items", []):
        stats["actions"] += 1

    logger.info(
        "  Decisions: %d, Entities: %d, Blockers: %d, Actions: %d",
        stats["decisions"],
        stats["entities"],
        stats["blockers"],
        stats["actions"],
    )

    return stats


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def find_analysis_files() -> list:
    """Find all analysis files."""
    paths = _get_brain_paths()
    analyzed_dir = paths["analyzed_dir"]
    if not analyzed_dir.exists():
        return []
    return sorted(analyzed_dir.glob("analysis_*.json"))


def run_brain_writer(dry_run: bool = False, resume: bool = True):
    """Run the brain writer pipeline."""
    state = load_state()
    aliases = _load_configured_aliases()

    if not state.get("started_at"):
        state["started_at"] = datetime.now().isoformat()
        save_state(state)

    # Find analysis files
    files = find_analysis_files()
    logger.info("Found %d analysis files", len(files))

    # Filter already processed
    if resume:
        processed_set = set(state.get("analyses_processed", []))
        files = [f for f in files if str(f) not in processed_set]
        logger.info("Remaining after resume filter: %d", len(files))

    if not files:
        logger.info("No new analysis files to process")
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
    logger.info("=" * 60)
    logger.info("BRAIN WRITER COMPLETE")
    logger.info("=" * 60)
    logger.info("Files processed: %d", len(files))
    logger.info("Decisions logged: %d", total_stats["decisions"])
    logger.info("Entities updated: %d", total_stats["entities"])
    logger.info("Blockers noted: %d", total_stats["blockers"])
    logger.info("Actions noted: %d", total_stats["actions"])
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

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

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.status:
        state = load_state()
        print_status(state)
        return

    run_brain_writer(dry_run=args.dry_run, resume=not args.no_resume)


if __name__ == "__main__":
    main()
