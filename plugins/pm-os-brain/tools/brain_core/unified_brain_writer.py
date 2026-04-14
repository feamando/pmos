#!/usr/bin/env python3
"""
Unified Brain Writer (v5.0)

Takes analyzed data from GDocs, Slack, GitHub, and Jira and enriches the Brain:
- Updates/creates entity files
- Logs decisions
- Adds context to projects
- Maintains entity aliases

Usage:
    python3 unified_brain_writer.py --source gdocs [--dry-run]
    python3 unified_brain_writer.py --source slack [--dry-run]
    python3 unified_brain_writer.py --source github [--dry-run]
    python3 unified_brain_writer.py --source jira [--dry-run]
    python3 unified_brain_writer.py --all [--dry-run]
    python3 unified_brain_writer.py --status
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
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent

# --- v5 imports: config + path resolution ---
try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    sys.path.insert(0, str(PLUGIN_ROOT.parent / "pm-os-base" / "tools" / "core"))
    from core.config_loader import get_config

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

# Sibling import: quality_scorer
try:
    from pm_os_brain.tools.brain_core.quality_scorer import QualityScorer
except ImportError:
    try:
        from quality.quality_scorer import QualityScorer
    except ImportError:
        QualityScorer = None
        logger.warning("QualityScorer not available; quality gates disabled")

# ============================================================================
# CONFIGURATION (config-driven, zero hardcoded values)
# ============================================================================

_paths = get_paths()
BRAIN_DIR = _paths.brain
ENTITIES_DIR = BRAIN_DIR / "Entities"
PROJECTS_DIR = BRAIN_DIR / "Projects"
DECISIONS_DIR = BRAIN_DIR / "Reasoning" / "Decisions"
INBOX_DIR = BRAIN_DIR / "Inbox"

# Source directories
SOURCE_DIRS = {
    "gdocs": INBOX_DIR / "GDocs" / "Analyzed",
    "slack": INBOX_DIR / "Slack" / "Analyzed",
    "github": INBOX_DIR / "GitHub" / "Analyzed",
    "jira": INBOX_DIR,  # JIRA_*.md files live directly in Inbox root
}

QUARANTINE_DIR = INBOX_DIR / "Quarantine"
STATE_FILE = BRAIN_DIR / "brain_writer_state.json"
ALIASES_FILE = BRAIN_DIR / "entity_aliases.json"

# Quality gate
_scorer = None


def _get_scorer():
    """Lazy-init quality scorer."""
    global _scorer
    if _scorer is None and QualityScorer is not None:
        _scorer = QualityScorer(BRAIN_DIR)
    return _scorer


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


def _load_aliases_from_config() -> dict:
    """
    Build entity aliases from config.yaml instead of hardcoded values.

    Reads products.items and team.reports to auto-generate aliases.
    Falls back to empty dict if config is not available.
    """
    aliases = {}
    try:
        config = get_config()

        # Build aliases from products config
        products = config.get("products", {}) or {}
        for item in products.get("items", []):
            product_id = item.get("id", "")
            product_name = item.get("name", "")
            product_aliases = item.get("aliases", [])

            if not product_id:
                continue

            # Canonical name uses underscores for file paths
            canonical = product_name.replace(" ", "_") if product_name else product_id.replace("-", "_").title()

            # Map name and aliases to canonical
            if product_name:
                aliases[product_name.lower()] = canonical
            if product_id:
                aliases[product_id.lower()] = canonical
            for alias in product_aliases:
                if alias:
                    aliases[alias.lower()] = canonical

        # Build aliases from team reports
        team = config.get("team", {}) or {}
        for report in team.get("reports", []):
            person_name = report.get("name", "")
            if not person_name:
                continue

            canonical = person_name.replace(" ", "_")
            # Add first name as alias
            parts = person_name.split()
            if parts:
                aliases[parts[0].lower()] = canonical
            aliases[person_name.lower()] = canonical

        # Build aliases from stakeholders
        for stakeholder in team.get("stakeholders", []):
            person_name = stakeholder.get("name", "")
            if not person_name:
                continue

            canonical = person_name.replace(" ", "_")
            parts = person_name.split()
            if parts:
                aliases[parts[0].lower()] = canonical
            aliases[person_name.lower()] = canonical

        # Manager alias
        manager = team.get("manager", {})
        if manager and manager.get("name"):
            manager_name = manager["name"]
            canonical = manager_name.replace(" ", "_")
            parts = manager_name.split()
            if parts:
                aliases[parts[0].lower()] = canonical
            aliases[manager_name.lower()] = canonical

    except Exception as e:
        logger.debug("Could not load aliases from config: %s", e)

    return aliases


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
    """Load entity aliases from config + file overrides."""
    # Start with config-driven aliases (replaces hardcoded DEFAULT_ALIASES)
    aliases = _load_aliases_from_config()

    # Layer on any file-based overrides
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

    try:
        from pm_os_brain.tools.brain_core.event_helpers import EventHelper
    except ImportError:
        try:
            from temporal.event_helpers import EventHelper
        except ImportError:
            logger.warning("EventHelper not available, creating v1 entity instead")
            return _create_v1_entity_file(name, entity_type, context, source)

    now = datetime.utcnow()
    slug = name.lower().replace(" ", "-").replace("_", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)

    # Map source to confidence
    source_confidence = {
        "gdocs": 0.75,
        "slack": 0.70,
        "github": 0.80,
        "jira": 0.85,
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
        logger.info("[DRY RUN] Would create decision: %s", filepath.name)
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
            logger.info("[DRY RUN] Would update: %s", existing.name)
            return True

        existing.write_text(new_content, encoding="utf-8")

        if str(existing) not in state.get("entities_updated", []):
            state.setdefault("entities_updated", []).append(str(existing))

        return True
    else:
        content = create_entity_file(canonical, entity_type, context, source)

        # Quality gate: score before writing
        scorer = _get_scorer()
        if scorer is not None:
            score = scorer.score_content(content, entity_id=canonical)
            decision = scorer.gate_decision(score)

            if decision == "reject":
                logger.info("Rejected: %s (score=%.2f)", canonical, score.overall_score)
                return False

            if decision == "quarantine":
                QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
                quarantine_path = QUARANTINE_DIR / f"{canonical}.md"
                if dry_run:
                    logger.info(
                        "[DRY RUN] Would quarantine: %s (score=%.2f)",
                        canonical,
                        score.overall_score,
                    )
                    return True
                quarantine_path.write_text(content, encoding="utf-8")
                logger.info("Quarantined: %s (score=%.2f)", canonical, score.overall_score)
                return True

            # Accept: write with quality score in frontmatter
            content = content.replace(
                '"$status": "active"',
                f'"$quality_score": {score.overall_score},\n"$status": "active"',
                1,
            )

        if dry_run:
            logger.info("[DRY RUN] Would create: %s", file_path.name)
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


def process_jira_markdown(
    filepath: Path, aliases: dict, state: dict, dry_run: bool
) -> dict:
    """Process a Jira inbox markdown file into Brain entities.

    Parses the structured markdown (squad sections, epic tables, in-progress
    lists, blocker lists) and creates/updates squad and project entities.
    """
    stats = {"decisions": 0, "entities": 0}
    content = filepath.read_text(encoding="utf-8")
    date_str = datetime.now().strftime("%Y-%m-%d")

    # Extract date from filename if possible (JIRA_2026-04-01.md)
    date_match = re.search(r"JIRA_(\d{4}-\d{2}-\d{2})", filepath.name)
    if date_match:
        date_str = date_match.group(1)

    current_squad = None
    current_section = None
    blockers: list = []
    in_progress: list = []
    epics: list = []

    def _flush_squad():
        """Write accumulated data for the current squad."""
        nonlocal blockers, in_progress, epics
        if not current_squad:
            return

        # Build context summary for the squad entity
        parts = [f"- [{date_str}] Jira sync:"]
        if epics:
            parts.append(f"  - Active epics: {len(epics)}")
        if in_progress:
            parts.append(f"  - In-progress tickets: {len(in_progress)}")
            for ticket in in_progress[:5]:
                parts.append(f"    - {ticket}")
            if len(in_progress) > 5:
                parts.append(f"    - ... and {len(in_progress) - 5} more")
        if blockers:
            parts.append(f"  - Blockers ({len(blockers)}):")
            for blocker in blockers:
                parts.append(f"    - {blocker}")

        context_entry = "\n".join(parts)

        if update_entity_context(
            current_squad, "squad", context_entry, "jira", aliases, state, dry_run
        ):
            stats["entities"] += 1

        # Log blockers as decisions (they represent risk signals)
        for blocker in blockers:
            decision = {
                "what": f"Blocker: {blocker[:80]}",
                "date": date_str,
                "who": [current_squad],
                "context": f"Jira blocker for {current_squad}",
                "confidence": "high",
            }
            if write_decision(decision, "Jira", current_squad, dry_run):
                stats["decisions"] += 1
            elif dry_run:
                stats["decisions"] += 1

        blockers = []
        in_progress = []
        epics = []

    for line in content.split("\n"):
        stripped = line.strip()

        # Detect squad headers: ## Squad Name (CODE)
        squad_match = re.match(r"^##\s+(.+?)(?:\s*\((\w+)\))?\s*$", stripped)
        if squad_match and not stripped.startswith("### "):
            _flush_squad()
            current_squad = squad_match.group(1).strip()
            current_section = None
            continue

        # Detect sub-sections: ### Active Epics, ### In Progress, ### Blockers
        section_match = re.match(r"^###\s+(.+?)(?:\s*\(\d+\))?\s*$", stripped)
        if section_match:
            current_section = section_match.group(1).strip().lower()
            continue

        if not current_squad:
            continue

        # Parse epic table rows: | KEY-123 | Summary | Status | Assignee |
        if current_section and "epic" in current_section:
            epic_match = re.match(
                r"^\|\s*(\w+-\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|$",
                stripped,
            )
            if epic_match and epic_match.group(1) != "Key":
                epics.append(
                    f"[{epic_match.group(1)}] {epic_match.group(2).strip()} ({epic_match.group(3).strip()})"
                )

        # Parse in-progress items: - [KEY-123] description @assignee
        elif current_section and "progress" in current_section:
            ip_match = re.match(r"^-\s+\[(\w+-\d+)\]\s+(.+)$", stripped)
            if ip_match:
                in_progress.append(f"[{ip_match.group(1)}] {ip_match.group(2).strip()}")

        # Parse blockers: - **[KEY-123]** description (Priority: X)
        elif current_section and "blocker" in current_section:
            blocker_match = re.match(
                r"^-\s+\*\*\[(\w+-\d+)\]\*\*\s+(.+)$", stripped
            )
            if blocker_match:
                blockers.append(
                    f"[{blocker_match.group(1)}] {blocker_match.group(2).strip()}"
                )

    # Flush last squad
    _flush_squad()

    return stats


def process_analysis_file(
    filepath: Path, source: str, aliases: dict, state: dict, dry_run: bool
) -> dict:
    """Process a single analysis file."""
    logger.info("Processing: %s", filepath.name)

    if source == "jira":
        return process_jira_markdown(filepath, aliases, state, dry_run)

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
    print(f"\n{'=' * 60}")
    print(f"BRAIN WRITER - {source.upper()}")
    print(f"{'=' * 60}")

    state = load_state()
    aliases = load_aliases()

    if not state.get("started_at"):
        state["started_at"] = datetime.now().isoformat()

    source_dir = SOURCE_DIRS.get(source)
    if not source_dir or not source_dir.exists():
        logger.info("No analyzed data found for %s", source)
        return

    if source == "jira":
        analysis_files = sorted(source_dir.glob("JIRA_*.md"))
    else:
        analysis_files = sorted(source_dir.glob("*.json"))
    logger.info("Found %d analysis files", len(analysis_files))

    # Resume support
    processed_key = f"{source}_processed"
    if resume and processed_key in state.get("sources_processed", {}):
        processed_set = set(state["sources_processed"][processed_key])
        analysis_files = [f for f in analysis_files if str(f) not in processed_set]
        logger.info("Remaining after resume: %d", len(analysis_files))

    if not analysis_files:
        logger.info("No new files to process")
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

    print(f"\n{'=' * 60}")
    print(f"BRAIN WRITER COMPLETE - {source.upper()}")
    print(f"  Files processed: {len(analysis_files)}")
    print(f"  Decisions logged: {total_stats.get('decisions', 0)}")
    print(f"  Entities updated: {total_stats.get('entities', 0)}")
    print(f"{'=' * 60}")


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
        "--source", choices=["gdocs", "slack", "github", "jira"], help="Source to process"
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
        for source in ["gdocs", "slack", "github", "jira"]:
            run_brain_writer(source, args.dry_run, not args.no_resume)
    elif args.source:
        run_brain_writer(args.source, args.dry_run, not args.no_resume)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
