#!/usr/bin/env python3
"""
Command Sync - Syncs developer commands to common/.claude/commands/

Copies slash commands from developer/.claude/commands/ to common/.claude/commands/
so they're visible to Claude Code. Tracks synced files to enable cleanup.

Usage:
    python3 command_sync.py              # Sync commands
    python3 command_sync.py --status     # Show sync status
    python3 command_sync.py --clean      # Remove synced commands from common

Author: PM-OS Team
Version: 1.0.0
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Path resolution
SCRIPT_DIR = Path(__file__).parent
COMMON_ROOT = SCRIPT_DIR.parent.parent
PM_OS_ROOT = COMMON_ROOT.parent

# Source and target directories
DEVELOPER_COMMANDS = PM_OS_ROOT / "developer" / ".claude" / "commands"
COMMON_COMMANDS = COMMON_ROOT / ".claude" / "commands"
SYNC_MANIFEST = COMMON_COMMANDS / ".sync-manifest.json"


def get_file_hash(path: Path) -> str:
    """Get MD5 hash of file contents."""
    return hashlib.md5(path.read_bytes()).hexdigest()


def load_manifest() -> Dict:
    """Load sync manifest tracking which files came from developer."""
    if SYNC_MANIFEST.exists():
        return json.loads(SYNC_MANIFEST.read_text())
    return {"synced_files": {}, "last_sync": None}


def save_manifest(manifest: Dict) -> None:
    """Save sync manifest."""
    manifest["last_sync"] = datetime.now().isoformat()
    SYNC_MANIFEST.write_text(json.dumps(manifest, indent=2))


def get_developer_commands() -> List[Path]:
    """Get list of command files in developer folder."""
    if not DEVELOPER_COMMANDS.exists():
        return []
    return sorted(DEVELOPER_COMMANDS.glob("*.md"))


def get_common_commands() -> List[Path]:
    """Get list of command files in common folder."""
    if not COMMON_COMMANDS.exists():
        return []
    return sorted(COMMON_COMMANDS.glob("*.md"))


def sync_commands(dry_run: bool = False, verbose: bool = True) -> Tuple[int, int, int]:
    """
    Sync developer commands to common.

    Returns: (copied, updated, skipped) counts
    """
    manifest = load_manifest()
    synced = manifest.get("synced_files", {})

    dev_commands = get_developer_commands()

    if not dev_commands:
        if verbose:
            print("No developer commands found to sync.")
        return 0, 0, 0

    copied = 0
    updated = 0
    skipped = 0

    for dev_file in dev_commands:
        target = COMMON_COMMANDS / dev_file.name
        dev_hash = get_file_hash(dev_file)

        # Check if file exists in common
        if target.exists():
            target_hash = get_file_hash(target)

            # Check if this is a synced file we manage
            if dev_file.name in synced:
                if dev_hash != target_hash:
                    # Developer file changed, update it
                    if verbose:
                        print(f"  UPDATE: {dev_file.name}")
                    if not dry_run:
                        shutil.copy2(dev_file, target)
                        synced[dev_file.name] = {
                            "hash": dev_hash,
                            "synced_at": datetime.now().isoformat(),
                            "source": str(dev_file),
                        }
                    updated += 1
                else:
                    skipped += 1
            else:
                # File exists but wasn't synced by us - skip to avoid overwriting
                if verbose:
                    print(f"  SKIP (exists): {dev_file.name}")
                skipped += 1
        else:
            # New file, copy it
            if verbose:
                print(f"  COPY: {dev_file.name}")
            if not dry_run:
                shutil.copy2(dev_file, target)
                synced[dev_file.name] = {
                    "hash": dev_hash,
                    "synced_at": datetime.now().isoformat(),
                    "source": str(dev_file),
                }
            copied += 1

    if not dry_run:
        manifest["synced_files"] = synced
        save_manifest(manifest)

    return copied, updated, skipped


def clean_synced_commands(dry_run: bool = False, verbose: bool = True) -> int:
    """Remove commands that were synced from developer."""
    manifest = load_manifest()
    synced = manifest.get("synced_files", {})

    removed = 0
    for filename in list(synced.keys()):
        target = COMMON_COMMANDS / filename
        if target.exists():
            if verbose:
                print(f"  REMOVE: {filename}")
            if not dry_run:
                target.unlink()
            removed += 1

        if not dry_run:
            del synced[filename]

    if not dry_run:
        manifest["synced_files"] = synced
        save_manifest(manifest)

    return removed


def show_status() -> None:
    """Show sync status."""
    manifest = load_manifest()
    synced = manifest.get("synced_files", {})
    last_sync = manifest.get("last_sync", "Never")

    dev_commands = get_developer_commands()
    common_commands = get_common_commands()

    print("=" * 60)
    print("COMMAND SYNC STATUS")
    print("=" * 60)
    print(f"Developer commands: {DEVELOPER_COMMANDS}")
    print(f"Common commands:    {COMMON_COMMANDS}")
    print(f"Last sync:          {last_sync}")
    print()

    print(f"Developer commands: {len(dev_commands)}")
    for f in dev_commands:
        status = "synced" if f.name in synced else "NOT synced"
        print(f"  - {f.name} [{status}]")

    print(f"\nSynced to common: {len(synced)}")
    for name, info in synced.items():
        target = COMMON_COMMANDS / name
        exists = "OK" if target.exists() else "MISSING"
        print(f"  - {name} [{exists}]")

    # Check for pending syncs
    pending = [f.name for f in dev_commands if f.name not in synced]
    if pending:
        print(f"\nPending sync: {len(pending)}")
        for name in pending:
            print(f"  - {name}")


def main():
    parser = argparse.ArgumentParser(
        description="Sync developer commands to common/.claude/commands/"
    )
    parser.add_argument("--status", action="store_true", help="Show sync status")
    parser.add_argument("--clean", action="store_true", help="Remove synced commands")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")

    args = parser.parse_args()
    verbose = not args.quiet

    if args.status:
        show_status()
        return

    if args.clean:
        if verbose:
            print("Cleaning synced commands...")
        removed = clean_synced_commands(dry_run=args.dry_run, verbose=verbose)
        if verbose:
            print(f"\nRemoved: {removed}")
        return

    # Default: sync
    if verbose:
        print("Syncing developer commands to common...")
        if args.dry_run:
            print("(DRY RUN - no changes will be made)\n")

    copied, updated, skipped = sync_commands(dry_run=args.dry_run, verbose=verbose)

    if verbose:
        print(f"\nSync complete: {copied} copied, {updated} updated, {skipped} skipped")
    else:
        # Quiet mode - just show if anything changed
        if copied or updated:
            print(f"Commands synced: {copied} new, {updated} updated")


if __name__ == "__main__":
    main()
