#!/usr/bin/env python3
"""
Synapse Builder - Bi-Directional Link Enforcer

Scans Brain files for 'relationships' in frontmatter and ensures reciprocity.
If A -> 'owner' -> B, then B -> 'owns' -> A.

Supports both entity relationships and FPF reasoning relationships:
- Entity: owner/owns, member_of/has_member, blocked_by/blocks, etc.
- FPF: supports/supported_by, decides/decided_by, evidence_for/has_evidence, etc.

Usage:
    python synapse_builder.py           # Run on all files (incl. Reasoning/)
    python synapse_builder.py --dry-run # Preview changes

Examples of FPF relationships:
- Evidence supports Hypothesis: Evidence/test-results.md -> 'supports' -> Hypotheses/api-design.md
- DRR decides Hypothesis: Decisions/drr-2025-01-15-api.md -> 'decides' -> Hypotheses/api-design.md
"""

import os
import re
import sys
from glob import glob
from pathlib import Path
from typing import Dict, List, Set, Tuple

import yaml

# Add tools directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# --- Configuration ---
# Use config_loader for proper path resolution
ROOT_PATH = config_loader.get_root_path()
USER_PATH = ROOT_PATH / "user"
BRAIN_DIR = str(USER_PATH / "brain")

# Relationship Mapping (Forward -> Inverse)
RELATIONSHIP_MAP = {
    # Entity relationships
    "owner": "owns",
    "owns": "owner",
    "member_of": "has_member",
    "has_member": "member_of",
    "blocked_by": "blocks",
    "blocks": "blocked_by",
    "depends_on": "dependency_for",
    "dependency_for": "depends_on",
    "relates_to": "relates_to",
    "part_of": "has_part",
    "has_part": "part_of",
    # FPF Reasoning relationships
    "supports": "supported_by",  # Evidence supports hypothesis
    "supported_by": "supports",
    "invalidates": "invalidated_by",  # Evidence invalidates hypothesis
    "invalidated_by": "invalidates",
    "decides": "decided_by",  # DRR decides/resolves hypothesis
    "decided_by": "decides",
    "evidence_for": "has_evidence",  # Hypothesis has evidence
    "has_evidence": "evidence_for",
    "derived_from": "derives",  # Hypothesis derived from parent
    "derives": "derived_from",
    "supersedes": "superseded_by",  # DRR supersedes old decision
    "superseded_by": "supersedes",
    "informs": "informed_by",  # Evidence informs project/entity
    "informed_by": "informs",
}


def parse_frontmatter(content: str) -> Tuple[Dict, str]:
    """Extract YAML frontmatter and body."""
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
    if match:
        try:
            return yaml.safe_load(match.group(1)) or {}, match.group(2)
        except yaml.YAMLError:
            return {}, content
    return {}, content


def get_brain_files() -> List[str]:
    """Get all .md files in Brain subdirectories."""
    files = []
    for root, _, filenames in os.walk(BRAIN_DIR):
        for filename in filenames:
            if filename.endswith(".md") and filename != "README.md":
                files.append(os.path.join(root, filename))
    return files


def normalize_link(link: str) -> str:
    """Clean wiki link to just the relative path."""
    # Remove [[ and ]] and path prefixes if present
    clean = link.replace("[[", "").replace("]]", "")
    # We want relative path from Brain/ root, e.g. "Entities/Nikita.md"
    # Handle both old (AI_Guidance/Brain/) and new (user/brain/) structures
    for prefix in ["AI_Guidance/Brain/", "user/brain/"]:
        if clean.startswith(prefix):
            clean = clean.replace(prefix, "")
            break
    return clean


def format_link(path: str) -> str:
    """Format path as wiki link."""
    # Ensure it doesn't already have brackets
    clean = normalize_link(path)
    return f"[[{clean}]]"


def read_file_safe(path: str) -> str:
    """Read file with encoding fallback."""
    encodings = ["utf-8", "utf-16", "latin-1"]
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"Error reading {path}: {e}")
            return ""
    print(f"Failed to decode {path}")
    return ""


def main(dry_run: bool = False):
    print(f"Scanning Brain in {BRAIN_DIR}...")

    files = get_brain_files()
    # Normalize to forward slashes for consistency across platforms
    file_map = {os.path.relpath(f, BRAIN_DIR).replace("\\", "/"): f for f in files}

    # 1. Build Graph of existing relationships
    # graph[source_file] = { 'owner': set(['target_file']), ... }
    graph: Dict[str, Dict[str, Set[str]]] = {}

    for rel_path, full_path in file_map.items():
        content = read_file_safe(full_path)
        if not content:
            continue

        fm, _ = parse_frontmatter(content)
        if not fm or "relationships" not in fm:
            continue

        if rel_path not in graph:
            graph[rel_path] = {}

        for rel_type, targets in fm["relationships"].items():
            if rel_type not in RELATIONSHIP_MAP:
                continue  # Skip unknown types

            if rel_type not in graph[rel_path]:
                graph[rel_path][rel_type] = set()

            for target in targets:
                target_clean = normalize_link(target)
                # Check if target exists in our file map (simple validation)
                # Note: target might be missing extension in link, handle that?
                # For now assume links are correct or exact paths

                # Try adding .md if missing
                if target_clean not in file_map and (target_clean + ".md") in file_map:
                    target_clean += ".md"

                if target_clean in file_map:
                    graph[rel_path][rel_type].add(target_clean)
                else:
                    # Debug: Why is it missing?
                    # print(f"Warning: Link '{target_clean}' in '{rel_path}' not found in file map.")
                    pass

    # 2. Calculate Inverses Needed
    updates_needed: Dict[str, Dict[str, Set[str]]] = {}

    for source, relations in graph.items():
        for rel_type, targets in relations.items():
            inverse_type = RELATIONSHIP_MAP[rel_type]

            for target in targets:
                # We need to ensure 'target' has 'inverse_type' pointing to 'source'
                if target not in updates_needed:
                    updates_needed[target] = {}
                if inverse_type not in updates_needed[target]:
                    updates_needed[target][inverse_type] = set()

                updates_needed[target][inverse_type].add(source)

    # 3. Apply Updates
    modified_count = 0

    for target_file, needed_rels in updates_needed.items():
        if target_file not in file_map:
            continue

        full_path = file_map[target_file]

        content = read_file_safe(full_path)
        if not content:
            continue

        fm, body = parse_frontmatter(content)
        if "relationships" not in fm:
            fm["relationships"] = {}

        changed = False

        for rel_type, sources in needed_rels.items():
            if rel_type not in fm["relationships"]:
                fm["relationships"][rel_type] = []

            current_values = set(
                normalize_link(x) for x in fm["relationships"][rel_type]
            )

            for source in sources:
                if source not in current_values:
                    # Add new link
                    # Fix path for display if needed, but simple relative path is standard
                    fm["relationships"][rel_type].append(format_link(source))
                    changed = True
                    print(f"  [+] {target_file}: Adding '{rel_type}' -> {source}")

        if changed:
            modified_count += 1
            if not dry_run:
                # Reconstruct file
                new_fm = yaml.dump(fm, sort_keys=False, allow_unicode=True).strip()
                new_content = f"---\n{new_fm}\n---\n{body}"
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

    print(f"\nDone. Modified {modified_count} files.")


if __name__ == "__main__":
    is_dry_run = "--dry-run" in sys.argv
    main(is_dry_run)
