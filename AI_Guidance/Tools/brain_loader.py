#!/usr/bin/env python3
"""
Brain Loader - Hot Topics Identification

Scans context files for entity mentions and identifies relevant Brain files to load.
Used during boot to give agents deeper semantic context.

Usage:
    python brain_loader.py                          # Scan latest context, output hot topics
    python brain_loader.py --context FILE           # Scan specific context file
    python brain_loader.py --query "OTP launch"     # Search for specific terms
    python brain_loader.py --list-all               # List all registered entities
"""

import os
import sys
import argparse
import re
from glob import glob
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict

# Try to import yaml, fall back to basic parsing if not available
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    print("Warning: PyYAML not installed. Using basic parsing.", file=sys.stderr)

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BRAIN_DIR = os.path.join(os.path.dirname(BASE_DIR), "Brain")
REGISTRY_FILE = os.path.join(BRAIN_DIR, "registry.yaml")
CONTEXT_DIR = os.path.join(os.path.dirname(BASE_DIR), "Core_Context")


def load_registry() -> Dict:
    """Load the entity registry from YAML."""
    if not os.path.exists(REGISTRY_FILE):
        print(f"Error: Registry not found at {REGISTRY_FILE}", file=sys.stderr)
        return {}

    with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
        if HAS_YAML:
            return yaml.safe_load(f)
        else:
            # Basic fallback - just return empty if no yaml
            print("Cannot parse registry without PyYAML", file=sys.stderr)
            return {}


def build_alias_index(registry: Dict) -> Dict[str, Tuple[str, str, str]]:
    """
    Build a reverse index: alias -> (category, entity_id, file_path)

    Returns dict where keys are lowercase aliases and values are tuples of
    (category, entity_id, relative_file_path)
    """
    index = {}

    for category in ['projects', 'entities', 'architecture', 'decisions']:
        if category not in registry or registry[category] is None:
            continue

        for entity_id, entity_data in registry[category].items():
            if not isinstance(entity_data, dict):
                continue

            file_path = entity_data.get('file', '')
            aliases = entity_data.get('aliases', [])

            # Add entity_id itself as an alias
            all_aliases = [entity_id] + (aliases if aliases else [])

            for alias in all_aliases:
                if alias:
                    # Store lowercase for case-insensitive matching
                    index[alias.lower()] = (category, entity_id, file_path)

    return index


def get_latest_context_file() -> Optional[str]:
    """Find the most recent context file."""
    pattern = os.path.join(CONTEXT_DIR, "*-context.md")
    files = glob(pattern)

    if not files:
        return None

    # Sort lexicographically (works with YYYY-MM-DD format)
    files.sort()
    return files[-1]


def scan_for_entities(text: str, alias_index: Dict[str, Tuple]) -> Dict[str, Dict]:
    """
    Scan text for entity mentions.

    Returns dict of matched entities with their details and match count.
    """
    matches = defaultdict(lambda: {'count': 0, 'category': '', 'file': '', 'matched_aliases': set()})

    # Normalize text for matching
    text_lower = text.lower()

    for alias, (category, entity_id, file_path) in alias_index.items():
        # Use word boundary matching for better precision
        # Escape special regex characters in alias
        escaped_alias = re.escape(alias)
        pattern = r'\b' + escaped_alias + r'\b'

        found = re.findall(pattern, text_lower)
        if found:
            matches[entity_id]['count'] += len(found)
            matches[entity_id]['category'] = category
            matches[entity_id]['file'] = file_path
            matches[entity_id]['matched_aliases'].add(alias)

    # Convert sets to lists for output
    for entity_id in matches:
        matches[entity_id]['matched_aliases'] = list(matches[entity_id]['matched_aliases'])

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
    sorted_matches = sorted(matches.items(), key=lambda x: x[1]['count'], reverse=True)

    # Group by category
    by_category = defaultdict(list)
    for entity_id, data in sorted_matches:
        by_category[data['category']].append((entity_id, data))

    for category in ['projects', 'entities', 'architecture', 'decisions']:
        if category not in by_category:
            continue

        lines.append(f"## {category.upper()}")
        lines.append("")

        for entity_id, data in by_category[category]:
            file_path = data['file']
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
        file_path = data['file']
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

    for category in ['projects', 'entities', 'architecture', 'decisions']:
        if category not in registry or registry[category] is None:
            continue

        for entity_id, entity_data in registry[category].items():
            if not isinstance(entity_data, dict):
                continue

            file_path = entity_data.get('file', '')
            aliases = entity_data.get('aliases', [])
            total_aliases += len(aliases) + 1  # +1 for entity_id itself

            if file_path:
                full_path = os.path.join(BRAIN_DIR, file_path)
                if os.path.exists(full_path):
                    existing.append(f"{category}/{entity_id}: {file_path}")
                else:
                    missing.append(f"{category}/{entity_id}: {file_path}")

    return existing, missing, total_aliases


def format_validation_report(existing: List[str], missing: List[str], total_aliases: int) -> str:
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

    for category in ['projects', 'entities', 'architecture', 'decisions']:
        if category not in registry or registry[category] is None:
            continue

        lines.append(f"## {category.upper()}")
        lines.append("")

        for entity_id, entity_data in registry[category].items():
            if not isinstance(entity_data, dict):
                continue

            file_path = entity_data.get('file', 'N/A')
            status = entity_data.get('status', 'unknown')
            aliases = entity_data.get('aliases', [])

            full_path = os.path.join(BRAIN_DIR, file_path)
            exists = "EXISTS" if os.path.exists(full_path) else "MISSING"

            lines.append(f"- **{entity_id}** ({status}) [{exists}]")
            lines.append(f"  File: `Brain/{file_path}`")
            if aliases:
                lines.append(f"  Aliases: {', '.join(aliases[:5])}{'...' if len(aliases) > 5 else ''}")
            lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Scan context for entity mentions and identify Brain files to load"
    )
    parser.add_argument(
        '--context',
        type=str,
        help='Path to specific context file to scan'
    )
    parser.add_argument(
        '--query',
        type=str,
        help='Search for specific terms instead of scanning context file'
    )
    parser.add_argument(
        '--list-all',
        action='store_true',
        help='List all registered entities'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate registry - check for missing Brain files'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show matched aliases'
    )
    parser.add_argument(
        '--files-only',
        action='store_true',
        help='Output only the list of files to load (for scripting)'
    )

    args = parser.parse_args()

    # Load registry
    registry = load_registry()
    if not registry:
        sys.exit(1)

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

        with open(context_file, 'r', encoding='utf-8') as f:
            text = f.read()

    # Scan for entities
    matches = scan_for_entities(text, alias_index)

    # Output
    if args.files_only:
        # Just output file paths for scripting
        for entity_id, data in sorted(matches.items(), key=lambda x: x[1]['count'], reverse=True):
            file_path = data['file']
            full_path = os.path.join(BRAIN_DIR, file_path)
            if os.path.exists(full_path):
                print(os.path.join("Brain", file_path))
    else:
        print(format_output(matches, verbose=args.verbose))


if __name__ == "__main__":
    main()
