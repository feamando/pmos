"""
PM-OS Dev CommandSync (v5.0)

Syncs plugin commands across CLI environments (Claude Code, Gemini, etc.).
Tracks synced files via manifest for cleanup support.

Usage:
    from pm_os_dev.tools.dev_util.command_sync import sync_commands

CLI:
    python3 command_sync.py              # Sync commands
    python3 command_sync.py --status     # Show sync status
    python3 command_sync.py --clean      # Remove synced commands
"""

import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        from core.path_resolver import get_paths
    except ImportError:
        get_paths = None

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from core.config_loader import get_config
    except ImportError:
        get_config = None


def _get_pmos_root() -> Path:
    if get_paths is not None:
        try:
            return get_paths().root
        except Exception:
            pass
    return Path.home() / "pm-os"


def _get_source_dirs(pmos_root: Path) -> List[Path]:
    """Get all plugin command directories (v5 plugins + marketplace plugins)."""
    source_dirs = []

    # v5 plugins (pm-os-*)
    plugins_dir = pmos_root / "v5" / "plugins"
    if plugins_dir.exists():
        for plugin_dir in sorted(plugins_dir.glob("pm-os-*/commands")):
            source_dirs.append(plugin_dir)

    # Marketplace plugins (specx-ux, etc.)
    marketplace_dir = pmos_root / "claude-plugins-marketplace" / "plugins"
    if marketplace_dir.exists():
        for plugin_dir in sorted(marketplace_dir.glob("*/commands")):
            source_dirs.append(plugin_dir)

    return source_dirs


def _get_target_dir(pmos_root: Path) -> Path:
    """Get the common commands target directory."""
    return pmos_root / "common" / ".claude" / "commands"


def _get_manifest_path(target_dir: Path) -> Path:
    return target_dir / ".sync-manifest.json"


def _get_file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _load_manifest(manifest_path: Path) -> Dict:
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"synced_files": {}, "last_sync": None}


def _save_manifest(manifest: Dict, manifest_path: Path) -> None:
    manifest["last_sync"] = datetime.now().isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=2))


def sync_commands(
    pmos_root: Optional[Path] = None,
    dry_run: bool = False,
    verbose: bool = True,
) -> Tuple[int, int, int]:
    """
    Sync plugin commands to common/.claude/commands/.

    Returns: (copied, updated, skipped) counts
    """
    pmos_root = pmos_root or _get_pmos_root()
    source_dirs = _get_source_dirs(pmos_root)
    target_dir = _get_target_dir(pmos_root)
    manifest_path = _get_manifest_path(target_dir)

    target_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(manifest_path)
    synced = manifest.get("synced_files", {})

    copied = 0
    updated = 0
    skipped = 0

    for source_dir in source_dirs:
        plugin_name = source_dir.parent.name

        for dev_file in sorted(source_dir.glob("*.md")):
            target = target_dir / dev_file.name
            dev_hash = _get_file_hash(dev_file)

            if target.exists():
                if dev_file.name in synced:
                    target_hash = _get_file_hash(target)
                    if dev_hash != target_hash:
                        if verbose:
                            print(f"  UPDATE: {dev_file.name} ({plugin_name})")
                        if not dry_run:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(dev_file, target)
                            synced[dev_file.name] = {
                                "hash": dev_hash,
                                "synced_at": datetime.now().isoformat(),
                                "source": str(dev_file),
                                "plugin": plugin_name,
                            }
                        updated += 1
                    else:
                        skipped += 1
                else:
                    if verbose:
                        print(f"  SKIP (exists): {dev_file.name}")
                    skipped += 1
            else:
                if verbose:
                    print(f"  COPY: {dev_file.name} ({plugin_name})")
                if not dry_run:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dev_file, target)
                    synced[dev_file.name] = {
                        "hash": dev_hash,
                        "synced_at": datetime.now().isoformat(),
                        "source": str(dev_file),
                        "plugin": plugin_name,
                    }
                copied += 1

    if not dry_run:
        manifest["synced_files"] = synced
        _save_manifest(manifest, manifest_path)

    return copied, updated, skipped


def clean_synced_commands(
    pmos_root: Optional[Path] = None,
    dry_run: bool = False,
    verbose: bool = True,
) -> int:
    """Remove commands that were synced from plugins."""
    pmos_root = pmos_root or _get_pmos_root()
    target_dir = _get_target_dir(pmos_root)
    manifest_path = _get_manifest_path(target_dir)
    manifest = _load_manifest(manifest_path)
    synced = manifest.get("synced_files", {})

    removed = 0
    for filename in list(synced.keys()):
        target = target_dir / filename
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
        _save_manifest(manifest, manifest_path)

    return removed


def show_status(pmos_root: Optional[Path] = None) -> None:
    """Show sync status."""
    pmos_root = pmos_root or _get_pmos_root()
    source_dirs = _get_source_dirs(pmos_root)
    target_dir = _get_target_dir(pmos_root)
    manifest_path = _get_manifest_path(target_dir)
    manifest = _load_manifest(manifest_path)
    synced = manifest.get("synced_files", {})

    print("=" * 60)
    print("COMMAND SYNC STATUS")
    print("=" * 60)
    print(f"Target: {target_dir}")
    print(f"Last sync: {manifest.get('last_sync', 'Never')}")
    print()

    total_source = 0
    for source_dir in source_dirs:
        plugin_name = source_dir.parent.name
        cmd_files = list(source_dir.glob("*.md"))
        total_source += len(cmd_files)
        print(f"  {plugin_name}: {len(cmd_files)} commands")
        for f in cmd_files:
            status = "synced" if f.name in synced else "NOT synced"
            print(f"    - {f.name} [{status}]")

    print(f"\nTotal source commands: {total_source}")
    print(f"Synced to target: {len(synced)}")


def main():
    parser = argparse.ArgumentParser(description="Sync plugin commands across CLIs")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", "-q", action="store_true")

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

    if verbose:
        print("Syncing plugin commands...")
        if args.dry_run:
            print("(DRY RUN)\n")

    copied, updated, skipped = sync_commands(dry_run=args.dry_run, verbose=verbose)

    if verbose:
        print(f"\nSync complete: {copied} copied, {updated} updated, {skipped} skipped")
    else:
        if copied or updated:
            print(f"Commands synced: {copied} new, {updated} updated")


if __name__ == "__main__":
    main()
