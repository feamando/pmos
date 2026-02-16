#!/usr/bin/env python3
"""
Brain Loader - Hot Topics Identification

Scans context files for entity mentions and identifies relevant Brain files to load.
Used during boot to give agents deeper semantic context.

Now includes FPF/Quint Code reasoning awareness:
- Scans Brain/Reasoning/ for decisions and hypotheses
- Checks .quint/ for active reasoning cycles
- Reports expiring evidence

Usage:
    python brain_loader.py                          # Scan latest context, output hot topics
    python brain_loader.py --context FILE           # Scan specific context file
    python brain_loader.py --query "OTP launch"     # Search for specific terms
    python brain_loader.py --list-all               # List all registered entities
    python brain_loader.py --reasoning              # Show FPF reasoning state
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from glob import glob
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Add tools directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# Try to import yaml, fall back to basic parsing if not available
try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    print("Warning: PyYAML not installed. Using basic parsing.", file=sys.stderr)

# --- Configuration ---
# Use config_loader for proper path resolution
ROOT_PATH = config_loader.get_root_path()
USER_PATH = ROOT_PATH / "user"
BRAIN_DIR = str(USER_PATH / "brain")
REGISTRY_FILE = os.path.join(BRAIN_DIR, "registry.yaml")
CONTEXT_DIR = str(USER_PATH / "personal" / "context")
QUINT_DIR = str(ROOT_PATH / ".quint")
REASONING_DIR = os.path.join(BRAIN_DIR, "Reasoning")


def _is_v2_registry(registry: Dict) -> bool:
    """Check if registry is v2 format."""
    return "$schema" in registry and registry.get("$schema", "").startswith(
        "brain://registry"
    )


def load_registry() -> Dict:
    """
    Load the entity registry from YAML.

    Supports both v1 and v2 registry formats:
    - v1: {projects: {...}, entities: {...}, ...}
    - v2: {$schema: ..., entities: {...}, alias_index: {...}, ...}
    """
    if not os.path.exists(REGISTRY_FILE):
        print(f"Error: Registry not found at {REGISTRY_FILE}", file=sys.stderr)
        return {}

    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        if HAS_YAML:
            registry = yaml.safe_load(f)

            # If v2, normalize to v1-compatible structure for backward compatibility
            if registry and _is_v2_registry(registry):
                return _normalize_v2_registry(registry)

            return registry
        else:
            # Basic fallback - just return empty if no yaml
            print("Cannot parse registry without PyYAML", file=sys.stderr)
            return {}


def _normalize_v2_registry(v2_registry: Dict) -> Dict:
    """
    Normalize v2 registry to v1-compatible structure.

    v2 has flat entities dict; v1 has category-based structure.
    This allows existing code to work with v2 registries.
    """
    v1_compatible = {
        "projects": {},
        "entities": {},
        "architecture": {},
        "decisions": {},
        "_v2_metadata": {
            "$schema": v2_registry.get("$schema"),
            "$version": v2_registry.get("$version"),
            "$generated": v2_registry.get("$generated"),
            "stats": v2_registry.get("stats", {}),
        },
        "_v2_alias_index": v2_registry.get("alias_index", {}),
    }

    # Map v2 entities back to v1 categories
    for slug, entry in v2_registry.get("entities", {}).items():
        entity_type = entry.get("$type", "unknown")

        # Convert v2 entry to v1 format
        v1_entry = {
            "file": entry.get("$ref", ""),
            "status": entry.get("$status", "active"),
            "aliases": entry.get("aliases", []),
            # Preserve v2 fields for tools that need them
            "_v2": {
                "$type": entity_type,
                "$version": entry.get("$version", 1),
                "$updated": entry.get("$updated"),
                "confidence": entry.get("confidence", 0.5),
                "relationships_count": entry.get("relationships_count", 0),
            },
        }

        # Add type-specific fields
        if entry.get("role"):
            v1_entry["role"] = entry["role"]
        if entry.get("team"):
            v1_entry["team"] = entry["team"]
        if entry.get("owner"):
            v1_entry["owner"] = entry["owner"]

        # Map to appropriate category
        if entity_type == "project":
            v1_compatible["projects"][slug] = v1_entry
        elif entity_type in ("person", "team", "squad", "domain", "system", "brand"):
            v1_compatible["entities"][slug] = v1_entry
        elif entity_type == "experiment":
            # experiments are indexed separately
            pass
        else:
            v1_compatible["entities"][slug] = v1_entry

    return v1_compatible


def build_alias_index(registry: Dict) -> Dict[str, Tuple[str, str, str]]:
    """
    Build a reverse index: alias -> (category, entity_id, file_path)

    Returns dict where keys are lowercase aliases and values are tuples of
    (category, entity_id, relative_file_path)

    For v2 registries, uses the pre-built alias_index for faster lookup.
    """
    index = {}

    # Check if this is a normalized v2 registry with pre-built alias index
    if "_v2_alias_index" in registry and registry["_v2_alias_index"]:
        v2_alias_index = registry["_v2_alias_index"]
        # v2 alias_index maps alias -> slug
        # We need to expand this to include category and file info
        for alias, slug in v2_alias_index.items():
            # Find the entity in the normalized structure
            for category in ["projects", "entities", "architecture", "decisions"]:
                if category in registry and slug in registry[category]:
                    entity_data = registry[category][slug]
                    file_path = entity_data.get("file", "")
                    index[alias.lower()] = (category, slug, file_path)
                    break

    # Standard v1 index building (also catches any v2 entities not in alias_index)
    for category in ["projects", "entities", "architecture", "decisions"]:
        if category not in registry or registry[category] is None:
            continue

        for entity_id, entity_data in registry[category].items():
            if not isinstance(entity_data, dict):
                continue

            file_path = entity_data.get("file", "")
            aliases = entity_data.get("aliases", [])

            # Add entity_id itself as an alias
            all_aliases = [entity_id] + (aliases if aliases else [])

            for alias in all_aliases:
                if alias:
                    # Store lowercase for case-insensitive matching
                    index[alias.lower()] = (category, entity_id, file_path)

    return index


def index_experiments() -> Dict[str, Tuple[str, str, str]]:
    """Scan Brain/Experiments folder and build index."""
    index = {}
    exp_dir = os.path.join(BRAIN_DIR, "Experiments")
    if not os.path.exists(exp_dir):
        return index

    for file_path in glob(os.path.join(exp_dir, "*.md")):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract ID from filename
            filename = os.path.basename(file_path)
            entity_id = filename.replace(".md", "")

            # Extract Title (Name)
            match = re.search(r"^# (.+)$", content, re.MULTILINE)
            name = match.group(1).strip() if match else entity_id

            # Add aliases: Name, ID
            rel_path = f"Experiments/{filename}"
            index[name.lower()] = ("experiments", entity_id, rel_path)
            index[entity_id.lower()] = ("experiments", entity_id, rel_path)

            # Extract raw ID if filename has prefix
            if entity_id.startswith("EXP-"):
                raw_id = entity_id[4:]
                index[raw_id.lower()] = ("experiments", entity_id, rel_path)

        except Exception:
            continue

    return index


def index_reasoning() -> Dict[str, Tuple[str, str, str]]:
    """Scan Brain/Reasoning folder and build index for DRRs and hypotheses."""
    index = {}

    # Index Decisions (DRRs)
    decisions_dir = os.path.join(REASONING_DIR, "Decisions")
    if os.path.exists(decisions_dir):
        for file_path in glob(os.path.join(decisions_dir, "*.md")):
            try:
                filename = os.path.basename(file_path)
                if filename.startswith("."):
                    continue
                entity_id = filename.replace(".md", "")
                rel_path = f"Reasoning/Decisions/{filename}"
                index[entity_id.lower()] = ("reasoning", entity_id, rel_path)

                # Add "drr" prefix alias
                if entity_id.startswith("drr-"):
                    short_id = entity_id[4:]
                    index[short_id.lower()] = ("reasoning", entity_id, rel_path)
            except Exception:
                continue

    # Index Hypotheses
    hypotheses_dir = os.path.join(REASONING_DIR, "Hypotheses")
    if os.path.exists(hypotheses_dir):
        for file_path in glob(os.path.join(hypotheses_dir, "*.md")):
            try:
                filename = os.path.basename(file_path)
                if filename.startswith("."):
                    continue
                entity_id = filename.replace(".md", "")
                rel_path = f"Reasoning/Hypotheses/{filename}"
                index[entity_id.lower()] = ("reasoning", entity_id, rel_path)
            except Exception:
                continue

    return index


def get_reasoning_state() -> Dict:
    """
    Get current FPF/Quint reasoning state.

    Returns dict with:
        - active_cycles: Number of active reasoning sessions
        - total_drrs: Total Design Rationale Records
        - l0_claims, l1_claims, l2_claims: Claims by assurance level
        - expiring_evidence: List of evidence expiring within 14 days
        - recent_decisions: List of recent DRRs (last 7 days)
    """
    state = {
        "active_cycles": 0,
        "total_drrs": 0,
        "l0_claims": 0,
        "l1_claims": 0,
        "l2_claims": 0,
        "expiring_evidence": [],
        "recent_decisions": [],
    }

    if not os.path.exists(QUINT_DIR):
        return state

    # Count active sessions
    sessions_dir = os.path.join(QUINT_DIR, "sessions")
    if os.path.exists(sessions_dir):
        state["active_cycles"] = len(
            [f for f in os.listdir(sessions_dir) if not f.startswith(".")]
        )

    # Count DRRs
    drr_quint = os.path.join(QUINT_DIR, "decisions")
    drr_brain = os.path.join(REASONING_DIR, "Decisions")

    drr_count = 0
    if os.path.exists(drr_quint):
        drr_count += len([f for f in os.listdir(drr_quint) if f.endswith(".md")])
    if os.path.exists(drr_brain):
        drr_count += len(
            [
                f
                for f in os.listdir(drr_brain)
                if f.endswith(".md") and not f.startswith(".")
            ]
        )
    state["total_drrs"] = drr_count

    # Count claims by level
    knowledge_dir = os.path.join(QUINT_DIR, "knowledge")
    if os.path.exists(knowledge_dir):
        for level in ["L0", "L1", "L2"]:
            level_dir = os.path.join(knowledge_dir, level)
            if os.path.exists(level_dir):
                count = len([f for f in os.listdir(level_dir) if f.endswith(".md")])
                state[f"{level.lower()}_claims"] = count

    # Check for expiring evidence (basic check - looks for valid_until in frontmatter)
    evidence_dir = os.path.join(QUINT_DIR, "evidence")
    if os.path.exists(evidence_dir) and HAS_YAML:
        threshold = datetime.now() + timedelta(days=14)
        for evidence_file in glob(os.path.join(evidence_dir, "*.md")):
            try:
                with open(evidence_file, "r", encoding="utf-8") as f:
                    content = f.read()
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        metadata = yaml.safe_load(parts[1]) or {}
                        valid_until = metadata.get("valid_until")
                        if valid_until:
                            if isinstance(valid_until, str):
                                expiry = datetime.strptime(valid_until, "%Y-%m-%d")
                            else:
                                expiry = valid_until
                            if expiry <= threshold:
                                state["expiring_evidence"].append(
                                    {
                                        "file": os.path.basename(evidence_file),
                                        "expires": (
                                            valid_until
                                            if isinstance(valid_until, str)
                                            else valid_until.strftime("%Y-%m-%d")
                                        ),
                                    }
                                )
            except Exception:
                continue

    return state


def format_reasoning_output(state: Dict) -> str:
    """Format reasoning state for output."""
    lines = []
    lines.append("=" * 60)
    lines.append("FPF REASONING STATE")
    lines.append("=" * 60)
    lines.append("")

    lines.append("## CURRENT STATE")
    lines.append("")
    lines.append(f"  Active FPF Cycles: {state['active_cycles']}")
    lines.append(f"  Total DRRs: {state['total_drrs']}")
    lines.append("")

    lines.append("## KNOWLEDGE LEVELS")
    lines.append("")
    lines.append(f"  L0 (Conjectures): {state['l0_claims']}")
    lines.append(f"  L1 (Substantiated): {state['l1_claims']}")
    lines.append(f"  L2 (Corroborated): {state['l2_claims']}")
    lines.append("")

    if state["expiring_evidence"]:
        lines.append("## EXPIRING EVIDENCE (within 14 days)")
        lines.append("")
        for ev in state["expiring_evidence"]:
            lines.append(f"  - {ev['file']} (expires: {ev['expires']})")
        lines.append("")
        lines.append("  Run `/q-decay` to refresh or waive.")
        lines.append("")

    lines.append("=" * 60)

    if state["active_cycles"] > 0:
        lines.append(f"STATUS: {state['active_cycles']} active reasoning cycle(s)")
        lines.append("  Run `/q-status` for details")
    else:
        lines.append("STATUS: No active reasoning cycles")
        lines.append("  Run `/q1-hypothesize <problem>` to start")

    lines.append("=" * 60)

    return "\n".join(lines)


def get_latest_context_file() -> Optional[str]:
    """Find the most recent context file."""
    pattern = os.path.join(CONTEXT_DIR, "*-context.md")
    files = glob(pattern)

    if not files:
        return None

    # Sort lexicographically (works with YYYY-MM-DD format)
    files.sort()
    return files[-1]


def scan_for_entities(
    text: str, alias_index: Dict[str, Tuple], partial_match: bool = False
) -> Dict[str, Dict]:
    """
    Scan text for entity mentions.

    Args:
        text: Content to scan
        alias_index: Dictionary of aliases to entities
        partial_match: If True, matches if alias is IN text (good for short search queries).
                       If False, uses word boundaries (good for scanning long docs).

    Returns dict of matched entities with their details and match count.
    """
    matches = defaultdict(
        lambda: {"count": 0, "category": "", "file": "", "matched_aliases": set()}
    )

    # Normalize text for matching
    text_lower = text.lower()

    for alias, (category, entity_id, file_path) in alias_index.items():
        if partial_match:
            # For search queries: simple substring check
            # e.g. Query "OTP" matches alias "meal-kit-otp"
            if text_lower in alias or alias in text_lower:
                # Found a match
                matches[entity_id]["count"] += 1
                matches[entity_id]["category"] = category
                matches[entity_id]["file"] = file_path
                matches[entity_id]["matched_aliases"].add(alias)
        else:
            # For context scanning: Word boundary matching for precision
            escaped_alias = re.escape(alias)
            pattern = r"\b" + escaped_alias + r"\b"

            found = re.findall(pattern, text_lower)
            if found:
                matches[entity_id]["count"] += len(found)
                matches[entity_id]["category"] = category
                matches[entity_id]["file"] = file_path
                matches[entity_id]["matched_aliases"].add(alias)

    # Convert sets to lists for output
    for entity_id in matches:
        matches[entity_id]["matched_aliases"] = list(
            matches[entity_id]["matched_aliases"]
        )

    return dict(matches)


def format_output(matches: Dict[str, Dict], verbose: bool = False) -> str:
    """Format matches for output."""
    if not matches:
        return "No entity matches found."

    lines = []
    lines.append("=" * 60)
    lines.append("HOT TOPICS - Entities mentioned in context")
    lines.append("=" * 60)
    lines.append("")

    # Sort by count (most mentioned first)
    sorted_matches = sorted(matches.items(), key=lambda x: x[1]["count"], reverse=True)

    # Group by category
    by_category = defaultdict(list)
    for entity_id, data in sorted_matches:
        by_category[data["category"]].append((entity_id, data))

    for category in [
        "projects",
        "entities",
        "architecture",
        "decisions",
        "experiments",
        "reasoning",
    ]:
        if category not in by_category:
            continue

        lines.append(f"## {category.upper()}")
        lines.append("")

        for entity_id, data in by_category[category]:
            file_path = data["file"]
            full_path = os.path.join(BRAIN_DIR, file_path)
            exists = os.path.exists(full_path)
            status = "EXISTS" if exists else "MISSING"

            lines.append(f"- **{entity_id}** ({data['count']} mentions) [{status}]")
            lines.append(f"  File: `Brain/{file_path}`")

            if verbose:
                lines.append(f"  Matched: {', '.join(data['matched_aliases'])}")

            lines.append("")

    lines.append("=" * 60)
    lines.append("Files to load:")

    # Output list of existing files to load
    files_to_load = []
    for entity_id, data in sorted_matches:
        file_path = data["file"]
        full_path = os.path.join(BRAIN_DIR, file_path)
        if os.path.exists(full_path):
            files_to_load.append(f"Brain/{file_path}")

    if files_to_load:
        for f in files_to_load:
            lines.append(f"  - {f}")
    else:
        lines.append("  (No existing Brain files match)")

    lines.append("")

    return "\n".join(lines)


def validate_registry(registry: Dict) -> Tuple[List[str], List[str], int]:
    """
    Validate registry for missing files and issues.

    Returns:
        Tuple of (existing_files, missing_files, total_aliases)
    """
    existing = []
    missing = []
    total_aliases = 0

    for category in ["projects", "entities", "architecture", "decisions"]:
        if category not in registry or registry[category] is None:
            continue

        for entity_id, entity_data in registry[category].items():
            if not isinstance(entity_data, dict):
                continue

            file_path = entity_data.get("file", "")
            aliases = entity_data.get("aliases", [])
            total_aliases += len(aliases) + 1  # +1 for entity_id itself

            if file_path:
                full_path = os.path.join(BRAIN_DIR, file_path)
                if os.path.exists(full_path):
                    existing.append(f"{category}/{entity_id}: {file_path}")
                else:
                    missing.append(f"{category}/{entity_id}: {file_path}")

    return existing, missing, total_aliases


def format_validation_report(
    existing: List[str], missing: List[str], total_aliases: int
) -> str:
    """Format validation results."""
    lines = []
    lines.append("=" * 60)
    lines.append("BRAIN REGISTRY VALIDATION REPORT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Total entities registered: {len(existing) + len(missing)}")
    lines.append(f"Total aliases indexed: {total_aliases}")
    lines.append(f"Files existing: {len(existing)}")
    lines.append(f"Files missing: {len(missing)}")
    lines.append("")

    if missing:
        lines.append("## MISSING FILES (need creation)")
        lines.append("")
        for item in missing:
            lines.append(f"  - {item}")
        lines.append("")

    if existing:
        lines.append("## EXISTING FILES (valid)")
        lines.append("")
        for item in existing:
            lines.append(f"  - {item}")
        lines.append("")

    # Summary
    lines.append("=" * 60)
    if missing:
        lines.append(f"STATUS: {len(missing)} missing file(s) need attention")
    else:
        lines.append("STATUS: All registered files exist")
    lines.append("=" * 60)

    return "\n".join(lines)


def list_all_entities(registry: Dict) -> str:
    """List all registered entities."""
    lines = []
    lines.append("=" * 60)
    lines.append("BRAIN REGISTRY - All Registered Entities")
    lines.append("=" * 60)
    lines.append("")

    for category in [
        "projects",
        "entities",
        "architecture",
        "decisions",
        "experiments",
    ]:
        if category not in registry or registry[category] is None:
            continue

        lines.append(f"## {category.upper()}")
        lines.append("")

        for entity_id, entity_data in registry[category].items():
            if not isinstance(entity_data, dict):
                continue

            file_path = entity_data.get("file", "N/A")
            status = entity_data.get("status", "unknown")
            aliases = entity_data.get("aliases", [])

            full_path = os.path.join(BRAIN_DIR, file_path)
            exists = "EXISTS" if os.path.exists(full_path) else "MISSING"

            lines.append(f"- **{entity_id}** ({status}) [{exists}]")
            lines.append(f"  File: `Brain/{file_path}`")
            if aliases:
                lines.append(
                    f"  Aliases: {', '.join(aliases[:5])}{'...' if len(aliases) > 5 else ''}"
                )
            lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Scan context for entity mentions and identify Brain files to load"
    )
    parser.add_argument(
        "--context", type=str, help="Path to specific context file to scan"
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Search for specific terms instead of scanning context file",
    )
    parser.add_argument(
        "--list-all", action="store_true", help="List all registered entities"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate registry - check for missing Brain files",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show matched aliases"
    )
    parser.add_argument(
        "--files-only",
        action="store_true",
        help="Output only the list of files to load (for scripting)",
    )
    parser.add_argument(
        "--reasoning",
        action="store_true",
        help="Show FPF reasoning state (active cycles, DRRs, evidence)",
    )

    args = parser.parse_args()

    # Load registry
    registry = load_registry()
    if not registry:
        sys.exit(1)

    # Reasoning state mode
    if args.reasoning:
        state = get_reasoning_state()
        print(format_reasoning_output(state))
        return

    # List all entities mode
    if args.list_all:
        print(list_all_entities(registry))
        return

    # Validate registry mode
    if args.validate:
        existing, missing, total_aliases = validate_registry(registry)
        print(format_validation_report(existing, missing, total_aliases))
        # Exit with error code if missing files
        sys.exit(1 if missing else 0)

    # Build alias index
    alias_index = build_alias_index(registry)
    alias_index.update(index_experiments())
    alias_index.update(index_reasoning())

    # Determine text to scan
    if args.query:
        text = args.query
        print(f"Searching for: {args.query}", file=sys.stderr)
    else:
        context_file = args.context or get_latest_context_file()
        if not context_file:
            print("Error: No context file found", file=sys.stderr)
            sys.exit(1)

        print(f"Scanning: {os.path.basename(context_file)}", file=sys.stderr)

        with open(context_file, "r", encoding="utf-8") as f:
            text = f.read()

    # Scan for entities
    # Enable partial matching if using query mode
    matches = scan_for_entities(text, alias_index, partial_match=bool(args.query))

    # Persist hot topics to JSON when scanning context (not query mode)
    if not args.query:
        hot_topics_path = os.path.join(BRAIN_DIR, "hot_topics.json")
        hot_topics_data = {
            "generated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": os.path.basename(context_file) if context_file else "unknown",
            "entity_count": len(matches),
            "entities": {
                eid: {
                    "count": data["count"],
                    "category": data["category"],
                    "file": data["file"],
                }
                for eid, data in sorted(
                    matches.items(), key=lambda x: x[1]["count"], reverse=True
                )
            },
        }
        try:
            with open(hot_topics_path, "w", encoding="utf-8") as f:
                json.dump(hot_topics_data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save hot_topics.json: {e}", file=sys.stderr)

    # Output
    if args.files_only:
        # Just output file paths for scripting
        for entity_id, data in sorted(
            matches.items(), key=lambda x: x[1]["count"], reverse=True
        ):
            file_path = data["file"]
            full_path = os.path.join(BRAIN_DIR, file_path)
            if os.path.exists(full_path):
                print(os.path.join("Brain", file_path))
    else:
        print(format_output(matches, verbose=args.verbose))


if __name__ == "__main__":
    main()
