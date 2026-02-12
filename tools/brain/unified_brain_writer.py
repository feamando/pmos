#!/usr/bin/env python3
"""
Unified Brain Writer

Takes analyzed data from GDocs, Slack, and GitHub and enriches the Brain:
- Updates/creates entity files
- Logs decisions
- Adds context to projects
- Maintains entity aliases

Usage:
    python3 unified_brain_writer.py --source gdocs [--dry-run]
    python3 unified_brain_writer.py --source slack [--dry-run]
    python3 unified_brain_writer.py --source github [--dry-run]
    python3 unified_brain_writer.py --all [--dry-run]
    python3 unified_brain_writer.py --status
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
INBOX_DIR = BRAIN_DIR / "Inbox"

# Source directories
SOURCE_DIRS = {
    "gdocs": INBOX_DIR / "GDocs" / "Analyzed",
    "slack": INBOX_DIR / "Slack" / "Analyzed",
    "github": INBOX_DIR / "GitHub" / "Analyzed",
}

STATE_FILE = BRAIN_DIR / "brain_writer_state.json"
ALIASES_FILE = BRAIN_DIR / "entity_aliases.json"

# Entity type to directory mapping
ENTITY_DIRS = {
    "person": ENTITIES_DIR / "People",
    "project": PROJECTS_DIR,
    "squad": ENTITIES_DIR / "Squads",
    "system": ENTITIES_DIR / "Systems",
    "brand": ENTITIES_DIR / "Brands",
    "api": ENTITIES_DIR / "Systems",
    "component": ENTITIES_DIR / "Systems",
    "feature": PROJECTS_DIR,
}

# Known entity aliases — configure via config.yaml for your organization
DEFAULT_ALIASES = {
    # Example people aliases (replace with your team)
    # "jane": "Jane_Smith",
    # "jane smith": "Jane_Smith",
    # Squads/Projects
    "cross-selling": "Cross_Selling",
    "cross selling": "Cross_Selling",
    "otp": "OTP_One_Time_Purchase",
    "one time purchase": "OTP_One_Time_Purchase",
    # Systems
    "shopify": "Shopify",
    "statsig": "Statsig",
    "tableau": "Tableau",
    "jira": "Jira",
    "confluence": "Confluence",
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
        "sources_processed": {},
        "entities_updated": [],
        "entities_created": [],
        "decisions_logged": 0,
        "total_context_added": 0,
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


# ============================================================================
# ENTITY RESOLUTION
# ============================================================================


def normalize_entity_name(name: str) -> str:
    """Normalize entity name for file naming."""
    normalized = re.sub(r"[^\w\s-]", "", name)
    normalized = re.sub(r"\s+", "_", normalized.strip())
    return normalized.title()


def resolve_entity(name: str, entity_type: str, aliases: dict) -> Tuple[str, Path]:
    """Resolve entity name to canonical name and file path."""
    name_lower = name.lower().strip()

    if name_lower in aliases:
        canonical = aliases[name_lower]
    else:
        canonical = normalize_entity_name(name)

    entity_dir = ENTITY_DIRS.get(entity_type, ENTITIES_DIR)
    entity_dir.mkdir(parents=True, exist_ok=True)

    file_path = entity_dir / f"{canonical}.md"
    return canonical, file_path


def find_existing_entity(name: str, aliases: dict) -> Optional[Path]:
    """Try to find an existing entity file."""
    name_lower = name.lower().strip()

    if name_lower in aliases:
        canonical = aliases[name_lower]
        for entity_dir in ENTITY_DIRS.values():
            if entity_dir.exists():
                for file in entity_dir.glob("*.md"):
                    if file.stem.lower() == canonical.lower():
                        return file

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
    """Read a Brain file."""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def append_to_section(content: str, section: str, new_content: str) -> str:
    """Append content to a specific section in a markdown file."""
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


def create_entity_file(
    name: str, entity_type: str, context: str, source: str, use_v2: bool = True
) -> str:
    """
    Create a new entity markdown file content.

    Args:
        name: Entity display name
        entity_type: Type of entity (person, project, squad, etc.)
        context: Initial context/description
        source: Source of the data (gdocs, slack, github)
        use_v2: If True, create v2 format with $schema and $events

    Returns:
        Markdown content for the entity file
    """
    if use_v2:
        return _create_v2_entity_file(name, entity_type, context, source)
    else:
        return _create_v1_entity_file(name, entity_type, context, source)


def _create_v2_entity_file(
    name: str, entity_type: str, context: str, source: str
) -> str:
    """Create a v2 format entity file with schema and events."""
    import yaml as _yaml

    sys.path.insert(0, str(Path(__file__).parent))
    from event_helpers import EventHelper

    now = datetime.utcnow()
    slug = name.lower().replace(" ", "-").replace("_", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)

    # Map source to confidence
    source_confidence = {
        "gdocs": 0.75,
        "slack": 0.70,
        "github": 0.80,
        "manual": 0.70,
    }
    confidence = source_confidence.get(source, 0.50)

    schema_uri = f"brain://entity/{entity_type}/v1"

    # Build frontmatter as dict
    frontmatter = {
        "$schema": schema_uri,
        "$id": f"entity/{entity_type}/{slug}",
        "$type": entity_type,
        "$version": 0,
        "$created": f"{now.isoformat()}Z",
        "$updated": f"{now.isoformat()}Z",
        "$confidence": confidence,
        "$source": source,
        "$status": "active",
        "$relationships": [],
        "$tags": [],
        "$aliases": [name.lower()],
        "$events": [],
        "name": name,
        "description": "[Auto-generated - needs manual review]",
    }

    # Create entity_create event via EventHelper
    event = EventHelper.create_event(
        event_type="entity_create",
        actor="system/unified_brain_writer",
        changes=[
            {"field": "$schema", "operation": "set", "value": schema_uri},
        ],
        message=f"Created from {source} analysis",
        source=source,
    )
    EventHelper.append_to_frontmatter(frontmatter, event)

    yaml_str = _yaml.dump(
        frontmatter,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )

    body = f"""
# {name}

## Overview

[Auto-generated - needs manual review]

## Context

{context}

## Related Entities

[To be filled]

## Notes

- Created automatically from {source} analysis
- Review and enrich manually
"""

    return f"---\n{yaml_str}---{body}"


def _create_v1_entity_file(
    name: str, entity_type: str, context: str, source: str
) -> str:
    """Create a v1 format entity file (legacy)."""
    return f"""# {name}

**Type:** {entity_type}
**Created:** {datetime.now().strftime('%Y-%m-%d')}
**Source:** {source} extraction

## Overview

[Auto-generated - needs manual review]

## Context

{context}

## Related Entities

[To be filled]

## Notes

- Created automatically from {source} analysis
- Review and enrich manually

---
*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""


def update_timestamp(content: str) -> str:
    """Update the last updated timestamp."""
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
    decision, source: str, source_context: str, dry_run: bool = False
) -> Optional[Path]:
    """Write a decision to the Decisions directory."""
    DECISIONS_DIR.mkdir(parents=True, exist_ok=True)

    # Handle string decisions (simple format)
    if isinstance(decision, str):
        decision = {"what": decision}

    date_str = decision.get("date", datetime.now().strftime("%Y-%m-%d"))
    if len(date_str) > 10:
        date_str = date_str[:10]

    what = decision.get("what", "Unknown decision")[:50]
    safe_what = re.sub(r"[^\w\s-]", "", what)[:30].strip().replace(" ", "_")

    filename = f"{date_str}_{safe_what}.md"
    filepath = DECISIONS_DIR / filename

    # Handle different decision formats from different sources
    who = decision.get("who", decision.get("approved_by", ["Unknown"]))
    if isinstance(who, str):
        who = [who]

    context = decision.get(
        "context", decision.get("rationale", "[No context provided]")
    )
    ticket = decision.get("ticket", "")

    content = f"""# Decision: {decision.get('what', 'Unknown')}

**Date:** {date_str}
**Source:** {source} - {source_context}
**Confidence:** {decision.get('confidence', 'medium')}
{f'**Ticket:** {ticket}' if ticket else ''}

## Decision

{decision.get('what', '[No description]')}

## Participants

{', '.join(who)}

## Context

{context}

---
*Extracted from {source} on {datetime.now().strftime('%Y-%m-%d')}*
"""

    if dry_run:
        print(f"    [DRY RUN] Would create decision: {filepath.name}", file=sys.stderr)
        return None

    # Don't overwrite existing decisions
    if filepath.exists():
        # Add suffix
        base = filepath.stem
        for i in range(2, 10):
            new_path = DECISIONS_DIR / f"{base}_{i}.md"
            if not new_path.exists():
                filepath = new_path
                break

    filepath.write_text(content, encoding="utf-8")
    return filepath


def update_entity_context(
    entity_name: str,
    entity_type: str,
    context: str,
    source: str,
    aliases: dict,
    state: dict,
    dry_run: bool = False,
) -> bool:
    """Update or create an entity file with new context."""
    canonical, file_path = resolve_entity(entity_name, entity_type, aliases)
    existing = find_existing_entity(entity_name, aliases)

    section_name = f"{source.title()} Context"

    if existing:
        content = read_brain_file(existing)
        new_content = append_to_section(content, section_name, context)
        new_content = update_timestamp(new_content)

        if dry_run:
            print(f"    [DRY RUN] Would update: {existing.name}", file=sys.stderr)
            return True

        existing.write_text(new_content, encoding="utf-8")

        if str(existing) not in state.get("entities_updated", []):
            state.setdefault("entities_updated", []).append(str(existing))

        return True
    else:
        content = create_entity_file(canonical, entity_type, context, source)

        if dry_run:
            print(f"    [DRY RUN] Would create: {file_path.name}", file=sys.stderr)
            return True

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        state.setdefault("entities_created", []).append(str(file_path))
        aliases[entity_name.lower()] = canonical

        return True


# ============================================================================
# SOURCE-SPECIFIC PROCESSING
# ============================================================================


def process_gdocs_analysis(
    analysis: dict, aliases: dict, state: dict, dry_run: bool
) -> dict:
    """Process a GDocs analysis file."""
    stats = {"decisions": 0, "entities": 0}
    results = analysis.get("results", [analysis])  # Handle both batch and single format

    for result in results:
        doc_title = result.get("doc_title", "Unknown Doc")
        source_context = doc_title[:50]

        # Process decisions
        for decision in result.get("decisions", []):
            if write_decision(decision, "GDocs", source_context, dry_run):
                stats["decisions"] += 1
            elif dry_run:
                stats["decisions"] += 1

        # Process entities
        for entity in result.get("entities", []):
            name = entity.get("name", "")
            etype = entity.get("type", "unknown")
            context = entity.get("context", entity.get("role", ""))

            if name and len(name) > 2:
                context_entry = f"- [{datetime.now().strftime('%Y-%m-%d')}] {context} (from: {doc_title[:40]})"
                if update_entity_context(
                    name, etype, context_entry, "gdocs", aliases, state, dry_run
                ):
                    stats["entities"] += 1

    return stats


def process_slack_analysis(
    analysis: dict, aliases: dict, state: dict, dry_run: bool
) -> dict:
    """Process a Slack analysis file."""
    stats = {"decisions": 0, "entities": 0}
    channel_name = analysis.get("channel_name", "unknown")

    # Process decisions
    for decision in analysis.get("decisions", []):
        if write_decision(decision, "Slack", f"#{channel_name}", dry_run):
            stats["decisions"] += 1
        elif dry_run:
            stats["decisions"] += 1

    # Process entities
    for entity in analysis.get("entities", []):
        name = entity.get("name", "")
        etype = entity.get("type", "unknown")
        context = entity.get("context", "")

        if name and len(name) > 2:
            context_entry = (
                f"- [{datetime.now().strftime('%Y-%m-%d')}] {context} (#{channel_name})"
            )
            if update_entity_context(
                name, etype, context_entry, "slack", aliases, state, dry_run
            ):
                stats["entities"] += 1

    return stats


def process_github_analysis(
    analysis: dict, aliases: dict, state: dict, dry_run: bool
) -> dict:
    """Process a GitHub analysis file."""
    stats = {"decisions": 0, "entities": 0, "features": 0}
    batch_id = analysis.get("batch_id", "unknown")

    # Process decisions
    for decision in analysis.get("decisions", []):
        if write_decision(decision, "GitHub", f"commits {batch_id}", dry_run):
            stats["decisions"] += 1
        elif dry_run:
            stats["decisions"] += 1

    # Process entities
    for entity in analysis.get("entities", []):
        name = entity.get("name", "")
        etype = entity.get("type", "system")
        context = entity.get("context", "")

        if name and len(name) > 2:
            context_entry = (
                f"- [{datetime.now().strftime('%Y-%m-%d')}] {context} (GitHub commits)"
            )
            if update_entity_context(
                name, etype, context_entry, "github", aliases, state, dry_run
            ):
                stats["entities"] += 1

    # Process features as project context
    for feature in analysis.get("features", []):
        stats["features"] += 1

    return stats


def process_analysis_file(
    filepath: Path, source: str, aliases: dict, state: dict, dry_run: bool
) -> dict:
    """Process a single analysis file."""
    print(f"  Processing: {filepath.name}", file=sys.stderr)

    with open(filepath, "r", encoding="utf-8") as f:
        analysis = json.load(f)

    if source == "gdocs":
        return process_gdocs_analysis(analysis, aliases, state, dry_run)
    elif source == "slack":
        return process_slack_analysis(analysis, aliases, state, dry_run)
    else:
        return process_github_analysis(analysis, aliases, state, dry_run)


# ============================================================================
# MAIN PIPELINE
# ============================================================================


def run_brain_writer(source: str, dry_run: bool = False, resume: bool = True):
    """Run the brain writer for a source."""
    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"BRAIN WRITER - {source.upper()}", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)

    state = load_state()
    aliases = load_aliases()

    if not state.get("started_at"):
        state["started_at"] = datetime.now().isoformat()

    source_dir = SOURCE_DIRS.get(source)
    if not source_dir or not source_dir.exists():
        print(f"No analyzed data found for {source}", file=sys.stderr)
        return

    analysis_files = sorted(source_dir.glob("*.json"))
    print(f"Found {len(analysis_files)} analysis files", file=sys.stderr)

    # Resume support
    processed_key = f"{source}_processed"
    if resume and processed_key in state.get("sources_processed", {}):
        processed_set = set(state["sources_processed"][processed_key])
        analysis_files = [f for f in analysis_files if str(f) not in processed_set]
        print(f"Remaining after resume: {len(analysis_files)}", file=sys.stderr)

    if not analysis_files:
        print("No new files to process", file=sys.stderr)
        return

    total_stats = {"decisions": 0, "entities": 0}

    for filepath in analysis_files:
        stats = process_analysis_file(filepath, source, aliases, state, dry_run)

        for key, value in stats.items():
            total_stats[key] = total_stats.get(key, 0) + value

        if not dry_run:
            state.setdefault("sources_processed", {}).setdefault(
                processed_key, []
            ).append(str(filepath))
            state["decisions_logged"] = state.get("decisions_logged", 0) + stats.get(
                "decisions", 0
            )
            state["total_context_added"] = state.get(
                "total_context_added", 0
            ) + stats.get("entities", 0)
            save_state(state)

    if not dry_run:
        save_aliases(aliases)

    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"BRAIN WRITER COMPLETE - {source.upper()}", file=sys.stderr)
    print(f"  Files processed: {len(analysis_files)}", file=sys.stderr)
    print(f"  Decisions logged: {total_stats.get('decisions', 0)}", file=sys.stderr)
    print(f"  Entities updated: {total_stats.get('entities', 0)}", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)


def show_status():
    """Show brain writer status."""
    state = load_state()

    print("=" * 60)
    print("BRAIN WRITER STATUS")
    print("=" * 60)
    print(f"Started: {state.get('started_at', 'Not started')}")
    print(f"Last Updated: {state.get('last_updated', 'N/A')}")
    print()

    for source, processed in state.get("sources_processed", {}).items():
        print(f"{source}: {len(processed)} files processed")

    print()
    print(f"Total Entities Updated: {len(state.get('entities_updated', []))}")
    print(f"Total Entities Created: {len(state.get('entities_created', []))}")
    print(f"Total Decisions Logged: {state.get('decisions_logged', 0)}")
    print(f"Total Context Added: {state.get('total_context_added', 0)}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Unified Brain Writer")
    parser.add_argument(
        "--source", choices=["gdocs", "slack", "github"], help="Source to process"
    )
    parser.add_argument("--all", action="store_true", help="Process all sources")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written without making changes",
    )
    parser.add_argument("--no-resume", action="store_true", help="Reprocess all files")
    parser.add_argument("--status", action="store_true", help="Show status and exit")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.all:
        for source in ["gdocs", "slack", "github"]:
            run_brain_writer(source, args.dry_run, not args.no_resume)
    elif args.source:
        run_brain_writer(args.source, args.dry_run, not args.no_resume)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
