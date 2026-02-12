#!/usr/bin/env python3
"""
Quint-Brain Synchronization Tool

Keeps .quint/ (Quint Code knowledge) and Brain/Reasoning/ in sync.
Enables bidirectional flow between FPF reasoning and PM-OS Brain.

Usage:
    python3 quint_brain_sync.py --to-brain      # Export Quint → Brain
    python3 quint_brain_sync.py --to-quint      # Import Brain → Quint
    python3 quint_brain_sync.py --bidirectional # Both directions
    python3 quint_brain_sync.py --dry-run       # Preview changes
"""

import argparse
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yaml

# Add tools directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# Resolve paths using config_loader
ROOT_DIR = config_loader.get_root_path()
USER_DIR = ROOT_DIR / "user"
QUINT_DIR = ROOT_DIR / ".quint"
BRAIN_DIR = USER_DIR / "brain"
REASONING_DIR = BRAIN_DIR / "Reasoning"
CONTEXT_DIR = USER_DIR / "context"


def parse_frontmatter(file_path: Path) -> dict:
    """Parse YAML frontmatter from a markdown file."""
    content = file_path.read_text(encoding="utf-8")
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                return yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                pass
    return {}


def add_frontmatter(content: str, metadata: dict) -> str:
    """Add or update YAML frontmatter in markdown content."""
    yaml_str = yaml.dump(metadata, default_flow_style=False, allow_unicode=True)
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return f"---\n{yaml_str}---{parts[2]}"
    return f"---\n{yaml_str}---\n\n{content}"


def is_expiring_soon(valid_until: Optional[str], days: int = 14) -> bool:
    """Check if evidence is expiring within specified days."""
    if not valid_until:
        return False
    try:
        expiry = datetime.strptime(valid_until, "%Y-%m-%d")
        return expiry <= datetime.now() + timedelta(days=days)
    except ValueError:
        return False


def sync_quint_to_brain(dry_run: bool = False, verbose: bool = False) -> dict:
    """Export Quint knowledge to Brain/Reasoning format."""

    results = {
        "decisions_synced": 0,
        "hypotheses_synced": 0,
        "evidence_synced": 0,
        "errors": [],
    }

    if not QUINT_DIR.exists():
        results["errors"].append(".quint/ directory not found")
        return results

    # Sync DRRs (Design Rationale Records)
    drr_source = QUINT_DIR / "decisions"
    drr_target = REASONING_DIR / "Decisions"

    if drr_source.exists():
        for drr_file in drr_source.glob("*.md"):
            target_file = drr_target / drr_file.name
            if verbose:
                print(f"  [DRR] {drr_file.name} → {target_file}")
            if not dry_run:
                # Add Brain-specific metadata
                content = drr_file.read_text(encoding="utf-8")
                metadata = parse_frontmatter(drr_file)
                metadata["synced_from"] = ".quint/decisions/"
                metadata["synced_at"] = datetime.now().isoformat()

                # Add Brain links if referenced entities exist
                content_with_links = add_brain_links(content)
                enhanced_content = add_frontmatter(content_with_links, metadata)

                target_file.write_text(enhanced_content, encoding="utf-8")
            results["decisions_synced"] += 1

    # Sync L2 (verified) knowledge
    l2_source = QUINT_DIR / "knowledge" / "L2"
    hyp_target = REASONING_DIR / "Hypotheses"

    if l2_source.exists():
        for claim_file in l2_source.glob("*.md"):
            target_file = hyp_target / f"L2-{claim_file.name}"
            if verbose:
                print(f"  [L2] {claim_file.name} → {target_file}")
            if not dry_run:
                shutil.copy2(claim_file, target_file)
            results["hypotheses_synced"] += 1

    # Sync evidence
    evidence_source = QUINT_DIR / "evidence"
    evidence_target = REASONING_DIR / "Evidence"

    if evidence_source.exists():
        for evidence_file in evidence_source.glob("*"):
            if evidence_file.is_file():
                target_file = evidence_target / evidence_file.name
                if verbose:
                    print(f"  [Evidence] {evidence_file.name} → {target_file}")
                if not dry_run:
                    shutil.copy2(evidence_file, target_file)
                results["evidence_synced"] += 1

    return results


def sync_brain_to_quint(dry_run: bool = False, verbose: bool = False) -> dict:
    """Import Brain context to Quint bounded context."""

    results = {"context_updated": False, "entities_imported": 0, "errors": []}

    if not QUINT_DIR.exists():
        results["errors"].append(".quint/ directory not found")
        return results

    context_file = QUINT_DIR / "context.md"

    # Gather Brain context
    context_sections = []

    # Add project summaries
    context_sections.append("## Active Projects\n")
    projects_dir = BRAIN_DIR / "Projects"
    if projects_dir.exists():
        for project_file in projects_dir.glob("*.md"):
            metadata = parse_frontmatter(project_file)
            name = metadata.get("title", project_file.stem)
            status = metadata.get("status", "unknown")
            context_sections.append(f"- **{name}** ({status})")
            results["entities_imported"] += 1

    # Add daily context summary
    context_sections.append("\n## Recent Context\n")
    if CONTEXT_DIR.exists():
        context_files = sorted(CONTEXT_DIR.glob("*-context.md"), reverse=True)
        if context_files:
            latest = context_files[0]
            context_sections.append(f"Latest: {latest.name}")

    # Add reasoning state
    context_sections.append("\n## Reasoning State\n")
    context_sections.append(
        f"- DRRs: {len(list((REASONING_DIR / 'Decisions').glob('*.md')))}"
    )
    context_sections.append(
        f"- Active cycles: {len(list((QUINT_DIR / 'sessions').glob('*')))}"
    )

    # Write context
    if not dry_run:
        context_content = f"""# Bounded Context - PM-OS Documents Repository

**Generated:** {datetime.now().isoformat()}
**Repository:** Documents (PM-OS)

{chr(10).join(context_sections)}

## Tech Stack

- Python 3.x (tools and automation)
- Markdown (documentation)
- YAML (configuration)
- SQLite (Quint database)

## Constraints

- Git-backed, CLI-first workflow
- AI-augmented (Claude Code, Gemini CLI, Mistral)
- NGO writing style (direct, bullets, metrics)
"""
        context_file.write_text(context_content, encoding="utf-8")
        results["context_updated"] = True

    if verbose:
        print(
            f"  Updated .quint/context.md with {results['entities_imported']} entities"
        )

    return results


def add_brain_links(content: str) -> str:
    """Add Brain entity links to content where entities are mentioned."""
    # Load registry
    registry_file = BRAIN_DIR / "registry.yaml"
    if not registry_file.exists():
        return content

    try:
        with open(registry_file, "r", encoding="utf-8") as f:
            registry = yaml.safe_load(f)
    except Exception:
        return content

    # Build alias map
    alias_map = {}
    for section in ["entities", "projects"]:
        if section in registry and registry[section]:
            for key, data in registry[section].items():
                if isinstance(data, dict):
                    file_path = data.get("file", "")
                    if file_path:
                        alias_map[key.lower()] = file_path
                        for alias in data.get("aliases", []):
                            alias_map[alias.lower()] = file_path

    # Simple replacement (could be made smarter)
    for alias, file_path in alias_map.items():
        # Only replace if not already a link
        pattern = rf"\b({re.escape(alias)})\b(?!\]\])"
        replacement = rf"[[{file_path}|\1]]"
        content = re.sub(pattern, replacement, content, flags=re.IGNORECASE, count=1)

    return content


def get_reasoning_summary() -> dict:
    """Get summary of current reasoning state."""
    summary = {
        "active_cycles": 0,
        "total_drrs": 0,
        "l0_claims": 0,
        "l1_claims": 0,
        "l2_claims": 0,
        "expiring_evidence": [],
    }

    if not QUINT_DIR.exists():
        return summary

    # Count active sessions
    sessions_dir = QUINT_DIR / "sessions"
    if sessions_dir.exists():
        summary["active_cycles"] = len(list(sessions_dir.glob("*")))

    # Count DRRs
    drr_dir = QUINT_DIR / "decisions"
    if drr_dir.exists():
        summary["total_drrs"] = len(list(drr_dir.glob("*.md")))

    # Count claims by level
    knowledge_dir = QUINT_DIR / "knowledge"
    if knowledge_dir.exists():
        for level in ["L0", "L1", "L2"]:
            level_dir = knowledge_dir / level
            if level_dir.exists():
                count = len(list(level_dir.glob("*.md")))
                summary[f"{level.lower()}_claims"] = count

    # Check for expiring evidence
    evidence_dir = QUINT_DIR / "evidence"
    if evidence_dir.exists():
        for evidence_file in evidence_dir.glob("*.md"):
            metadata = parse_frontmatter(evidence_file)
            valid_until = metadata.get("valid_until")
            if is_expiring_soon(valid_until):
                summary["expiring_evidence"].append(
                    {"file": evidence_file.name, "expires": valid_until}
                )

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Synchronize Quint Code knowledge with PM-OS Brain"
    )
    parser.add_argument(
        "--to-brain",
        action="store_true",
        help="Export Quint knowledge to Brain/Reasoning/",
    )
    parser.add_argument(
        "--to-quint",
        action="store_true",
        help="Import Brain context to Quint bounded context",
    )
    parser.add_argument(
        "--bidirectional", action="store_true", help="Sync both directions"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without writing files"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed sync log"
    )
    parser.add_argument(
        "--status", action="store_true", help="Show reasoning state summary"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("QUINT-BRAIN SYNC")
    print("=" * 60)

    if args.status:
        summary = get_reasoning_summary()
        print(f"\nReasoning State:")
        print(f"  Active Cycles: {summary['active_cycles']}")
        print(f"  Total DRRs: {summary['total_drrs']}")
        print(f"  L0 Claims: {summary['l0_claims']}")
        print(f"  L1 Claims: {summary['l1_claims']}")
        print(f"  L2 Claims: {summary['l2_claims']}")
        if summary["expiring_evidence"]:
            print(f"\n  Expiring Evidence ({len(summary['expiring_evidence'])}):")
            for ev in summary["expiring_evidence"]:
                print(f"    - {ev['file']} (expires: {ev['expires']})")
        return

    if not any([args.to_brain, args.to_quint, args.bidirectional]):
        print(
            "No sync direction specified. Use --to-brain, --to-quint, or --bidirectional"
        )
        return

    if args.dry_run:
        print("[DRY RUN - No files will be modified]\n")

    if args.to_brain or args.bidirectional:
        print("\n→ Syncing Quint → Brain...")
        results = sync_quint_to_brain(dry_run=args.dry_run, verbose=args.verbose)
        print(f"  Decisions synced: {results['decisions_synced']}")
        print(f"  Hypotheses synced: {results['hypotheses_synced']}")
        print(f"  Evidence synced: {results['evidence_synced']}")
        if results["errors"]:
            for err in results["errors"]:
                print(f"  ERROR: {err}")

    if args.to_quint or args.bidirectional:
        print("\n→ Syncing Brain → Quint...")
        results = sync_brain_to_quint(dry_run=args.dry_run, verbose=args.verbose)
        print(f"  Context updated: {results['context_updated']}")
        print(f"  Entities imported: {results['entities_imported']}")
        if results["errors"]:
            for err in results["errors"]:
                print(f"  ERROR: {err}")

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
