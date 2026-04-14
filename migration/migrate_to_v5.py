"""
PM-OS v4.x -> v5.0 Migration Script

Usage:
  python3 migrate_to_v5.py                  # Interactive (default)
  python3 migrate_to_v5.py --dry-run        # Show what would happen
  python3 migrate_to_v5.py --auto-confirm   # Skip confirmation (CI/testing)
  python3 migrate_to_v5.py --rollback       # Revert to v4.x-backup tag
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class MigrationItem:
    """A single item to migrate, archive, or delete."""
    path: str
    action: str  # "keep", "archive", "delete"
    reason: str
    size_bytes: int = 0


@dataclass
class MigrationReport:
    """Full analysis of what will be migrated."""
    keep_paths: list = field(default_factory=list)
    archive_paths: list = field(default_factory=list)
    delete_paths: list = field(default_factory=list)
    symlinks: list = field(default_factory=list)
    config_changes: list = field(default_factory=list)
    plugins_to_install: list = field(default_factory=list)

    @property
    def total_cleanup_bytes(self) -> int:
        return sum(item.size_bytes for item in self.delete_paths)


@dataclass
class ValidationResult:
    """Results of post-migration validation."""
    checks: list = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(passed for _, passed, _ in self.checks)


def get_pm_os_root() -> Path:
    """Find the PM-OS root directory."""
    # Check environment variable first
    env_root = os.environ.get("PM_OS_ROOT")
    if env_root:
        return Path(env_root)

    # Walk up from script location looking for .pm-os-root marker
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / ".pm-os-root").exists():
            return current
        current = current.parent

    # Fallback to ~/pm-os
    fallback = Path.home() / "pm-os"
    if fallback.exists():
        return fallback

    print("ERROR: Cannot find PM-OS root directory.")
    print("Set PM_OS_ROOT environment variable or run from within pm-os/")
    sys.exit(1)


def get_dir_size(path: Path) -> int:
    """Get total size of a directory in bytes."""
    total = 0
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    return total


def analyze(pm_os_root: Path) -> MigrationReport:
    """Step 1: Scan user/ and categorize KEEP/ARCHIVE/DELETE."""
    report = MigrationReport()
    user_path = pm_os_root / "user"

    if not user_path.exists():
        print("WARNING: user/ directory not found. Fresh install assumed.")
        return report

    # KEEP — valuable content to migrate as-is
    keep_dirs = [
        ("user/brain", "Brain entity files"),
        ("user/products", "Product/feature hierarchies"),
        ("user/team", "Team structure, 1:1 notes"),
        ("user/sessions/Active", "Active sessions"),
        ("user/config.yaml", "User configuration"),
        ("user/.env", "API tokens"),
        ("user/USER.md", "User persona"),
    ]
    for rel_path, reason in keep_dirs:
        full_path = pm_os_root / rel_path
        if full_path.exists():
            report.keep_paths.append(MigrationItem(
                path=rel_path, action="keep", reason=reason,
                size_bytes=get_dir_size(full_path),
            ))

    # KEEP recent context (last 90 days)
    context_dir = user_path / "personal" / "context"
    if context_dir.exists():
        cutoff = datetime.now().timestamp() - (90 * 86400)
        for f in context_dir.glob("*.md"):
            if f.stat().st_mtime >= cutoff:
                report.keep_paths.append(MigrationItem(
                    path=str(f.relative_to(pm_os_root)),
                    action="keep", reason="Recent context (< 90 days)",
                    size_bytes=f.stat().st_size,
                ))
            else:
                report.archive_paths.append(MigrationItem(
                    path=str(f.relative_to(pm_os_root)),
                    action="archive", reason="Context older than 90 days",
                    size_bytes=f.stat().st_size,
                ))

    # ARCHIVE — old but potentially useful
    archive_dirs = [
        ("user/sessions/Archive", "Already-archived sessions"),
        ("user/planning", "Historical planning docs"),
    ]
    for rel_path, reason in archive_dirs:
        full_path = pm_os_root / rel_path
        if full_path.exists():
            report.archive_paths.append(MigrationItem(
                path=rel_path, action="archive", reason=reason,
                size_bytes=get_dir_size(full_path),
            ))

    # DELETE — confirmed dead artifacts
    delete_patterns = [
        ("user/archive/PM-OS_Distribution_v*", "Old distribution snapshots"),
        ("user/archive/PM-OS_Distribution", "Old distribution snapshot"),
        ("user/archive/old-backups", "Ancient backups"),
        ("user/.migration_backup", "Stale migration logs"),
        ("user/brain_backups", "Pre-v2 brain backups"),
    ]
    for pattern, reason in delete_patterns:
        if "*" in pattern:
            matches = list(pm_os_root.glob(pattern))
        else:
            matches = [pm_os_root / pattern] if (pm_os_root / pattern).exists() else []
        for match in matches:
            report.delete_paths.append(MigrationItem(
                path=str(match.relative_to(pm_os_root)),
                action="delete", reason=reason,
                size_bytes=get_dir_size(match),
            ))

    # Find symlinks
    for item in user_path.rglob("*"):
        if item.is_symlink():
            report.symlinks.append(str(item.relative_to(pm_os_root)))

    # Detect plugins to install from existing commands
    commands_dir = pm_os_root / "common" / ".claude" / "commands"
    if commands_dir.exists():
        command_files = [f.stem for f in commands_dir.glob("*.md")]
        plugin_map = {
            "brain": "pm-os-brain",
            "session": "pm-os-daily-workflow",
            "sync": "pm-os-daily-workflow",
            "feature": "pm-os-cce",
            "doc": "pm-os-cce",
            "reason": "pm-os-cce",
            "report": "pm-os-reporting",
            "team": "pm-os-career",
            "ralph": "pm-os-dev",
            "release": "pm-os-dev",
        }
        detected = set()
        for cmd in command_files:
            if cmd in plugin_map:
                detected.add(plugin_map[cmd])
        report.plugins_to_install = ["pm-os-base"] + sorted(detected)

    return report


def confirm(report: MigrationReport, interactive: bool = True) -> bool:
    """Step 2: Show report, ask for confirmation."""
    print("\n" + "=" * 60)
    print("PM-OS v5.0 Migration Analysis")
    print("=" * 60)

    print(f"\n  KEEP:    {len(report.keep_paths)} items")
    for item in report.keep_paths[:10]:
        print(f"    {item.path} — {item.reason}")
    if len(report.keep_paths) > 10:
        print(f"    ... and {len(report.keep_paths) - 10} more")

    print(f"\n  ARCHIVE: {len(report.archive_paths)} items")
    for item in report.archive_paths[:5]:
        print(f"    {item.path} — {item.reason}")
    if len(report.archive_paths) > 5:
        print(f"    ... and {len(report.archive_paths) - 5} more")

    cleanup_mb = report.total_cleanup_bytes / (1024 * 1024)
    print(f"\n  DELETE:  {len(report.delete_paths)} items ({cleanup_mb:.1f}MB)")
    for item in report.delete_paths:
        size_kb = item.size_bytes / 1024
        print(f"    {item.path} ({size_kb:.0f}KB) — {item.reason}")

    if report.symlinks:
        print(f"\n  SYMLINKS TO REMOVE: {len(report.symlinks)}")
        for link in report.symlinks:
            print(f"    {link}")

    print(f"\n  PLUGINS TO INSTALL: {', '.join(report.plugins_to_install)}")

    if not interactive:
        return False

    print()
    response = input("Proceed with migration? [y/N] ").strip().lower()
    return response in ("y", "yes")


def backup(pm_os_root: Path) -> Optional[str]:
    """Step 3: Create git tag v4.x-backup."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        tag = f"v4.x-backup-{timestamp}"
        subprocess.run(
            ["git", "tag", tag],
            cwd=str(pm_os_root), check=True, capture_output=True,
        )
        print(f"  Backup tag created: {tag}")
        return tag
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("  WARNING: Git not available. Skipping backup tag.")
        return None


def migrate_config(pm_os_root: Path):
    """Migrate config.yaml: bump version, add plugins and persona sections."""
    import yaml

    config_path = pm_os_root / "user" / "config.yaml"
    if not config_path.exists():
        return

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Bump version
    config["version"] = "5.0.0"

    # Add plugins section if missing
    if "plugins" not in config:
        config["plugins"] = {
            "format": "anthropic",
            "source": "v5/plugins",
        }

    # Add persona section if missing
    if "persona" not in config:
        config["persona"] = {
            "style": "direct",
            "format": "bullets-over-prose",
            "decision_framework": "first-principles",
        }

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print("  Config migrated: version=5.0.0, plugins + persona sections added")


def install_plugins(pm_os_root: Path, plugin_ids: list):
    """Install v5 plugins by copying commands and skills to .claude/."""
    plugins_dir = pm_os_root / "v5" / "plugins"
    commands_dir = pm_os_root / ".claude" / "commands"
    skills_dir = pm_os_root / ".claude" / "skills"
    commands_dir.mkdir(parents=True, exist_ok=True)
    skills_dir.mkdir(parents=True, exist_ok=True)

    for plugin_id in plugin_ids:
        plugin_dir = plugins_dir / plugin_id
        manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
        if not manifest_path.exists():
            print(f"  WARNING: {plugin_id} manifest not found, skipping")
            continue

        manifest = json.loads(manifest_path.read_text())
        for cmd in manifest.get("commands", []):
            src = plugin_dir / cmd
            if src.exists():
                shutil.copy2(str(src), str(commands_dir / src.name))
        for skill in manifest.get("skills", []):
            src = plugin_dir / skill
            if src.exists():
                shutil.copy2(str(src), str(skills_dir / src.name))

        print(f"  Installed: {plugin_id}")


def migrate(pm_os_root: Path, report: MigrationReport):
    """Step 4: Config migration, content cleanup, plugin setup."""
    archive_dest = pm_os_root / "user" / "archive" / "v4-migration"

    # a) Move archived content
    for item in report.archive_paths:
        src = pm_os_root / item.path
        if src.exists():
            dest = archive_dest / Path(item.path).name
            dest.parent.mkdir(parents=True, exist_ok=True)
            print(f"  Archiving: {item.path}")
            shutil.move(str(src), str(dest))

    # b) Delete confirmed dead artifacts
    for item in report.delete_paths:
        src = pm_os_root / item.path
        if src.exists():
            print(f"  Deleting: {item.path}")
            if src.is_dir():
                shutil.rmtree(str(src))
            else:
                src.unlink()

    # c) Remove symlinks
    for link_path in report.symlinks:
        link = pm_os_root / link_path
        if link.is_symlink():
            print(f"  Removing symlink: {link_path}")
            os.unlink(str(link))

    # d) Clear v4.x commands from common/.claude/commands/
    old_commands_dir = pm_os_root / "common" / ".claude" / "commands"
    if old_commands_dir.exists():
        for f in old_commands_dir.glob("*.md"):
            f.unlink()
        print(f"  Cleared v4.x commands from {old_commands_dir} (archive/ preserved)")

    # d2) Archive stale v4 commands from root .claude/commands/
    root_commands_dir = pm_os_root / ".claude" / "commands"
    if root_commands_dir.exists():
        archive_v4 = root_commands_dir / "archive" / "v4"
        archive_v4.mkdir(parents=True, exist_ok=True)
        # Collect v5 plugin command filenames
        v5_command_names = set()
        plugins_dir = pm_os_root / "v5" / "plugins"
        if plugins_dir.exists():
            for manifest_path in plugins_dir.glob("pm-os-*/.claude-plugin/plugin.json"):
                manifest = json.loads(manifest_path.read_text())
                for cmd in manifest.get("commands", []):
                    v5_command_names.add(Path(cmd).name)
        # Move non-v5 commands to archive
        archived = 0
        for f in root_commands_dir.glob("*.md"):
            if f.name not in v5_command_names:
                shutil.move(str(f), str(archive_v4 / f.name))
                archived += 1
        if archived:
            print(f"  Archived {archived} stale v4 commands to .claude/commands/archive/v4/")

    # e) Config migration
    config_path = pm_os_root / "user" / "config.yaml"
    if config_path.exists():
        print("  Migrating config.yaml...")
        migrate_config(pm_os_root)

    # f) Plugin installation
    if report.plugins_to_install:
        print("  Installing v5 plugins...")
        install_plugins(pm_os_root, report.plugins_to_install)

    print("  Migration steps complete.")


def validate(pm_os_root: Path) -> ValidationResult:
    """Step 5: Check brain entities, config, plugins."""
    result = ValidationResult()
    user_path = pm_os_root / "user"

    # Brain entities readable
    brain_dir = user_path / "brain"
    if brain_dir.exists():
        entity_count = len(list(brain_dir.glob("*.md")))
        result.checks.append(
            ("Brain entities", entity_count > 0, f"{entity_count} entities")
        )
    else:
        result.checks.append(("Brain entities", False, "brain/ directory not found"))

    # Config exists
    config_path = user_path / "config.yaml"
    if config_path.exists():
        result.checks.append(("Config exists", True, "OK"))
    else:
        result.checks.append(("Config exists", False, "config.yaml not found"))

    # Config version is 5.0.0
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)
            version = config.get("version", "unknown")
            result.checks.append(
                ("Config version", version == "5.0.0", f"v{version}")
            )
            has_plugins = "plugins" in config
            result.checks.append(
                ("Config plugins section", has_plugins,
                 "present" if has_plugins else "missing")
            )
        except Exception as e:
            result.checks.append(("Config parseable", False, str(e)))

    # No dead symlinks
    dead_links = []
    if user_path.exists():
        for item in user_path.rglob("*"):
            if item.is_symlink() and not item.resolve().exists():
                dead_links.append(str(item))
    result.checks.append(
        ("No dead symlinks", len(dead_links) == 0, f"{len(dead_links)} found")
    )

    # v5 directory exists
    v5_dir = pm_os_root / "v5"
    result.checks.append(
        ("v5/ workspace", v5_dir.exists(), "exists" if v5_dir.exists() else "missing")
    )

    # v5/plugins/ has 7 pm-os-* subdirs
    plugins_dir = pm_os_root / "v5" / "plugins"
    if plugins_dir.exists():
        plugin_dirs = [d for d in plugins_dir.iterdir()
                       if d.is_dir() and d.name.startswith("pm-os-")]
        result.checks.append(
            ("v5 plugin directories", len(plugin_dirs) >= 7,
             f"{len(plugin_dirs)} found")
        )
    else:
        result.checks.append(("v5 plugin directories", False, "v5/plugins/ missing"))

    # Plugins installed (commands registered)
    commands_dir = pm_os_root / ".claude" / "commands"
    if commands_dir.exists():
        base_cmd = commands_dir / "base.md"
        result.checks.append(
            ("Base plugin installed", base_cmd.exists(),
             "base.md registered" if base_cmd.exists() else "base.md missing")
        )
    else:
        result.checks.append(
            ("Base plugin installed", False, ".claude/commands/ not found")
        )

    return result


def print_report(result: ValidationResult, backup_tag: Optional[str]):
    """Step 6: Print summary."""
    print("\n" + "=" * 50)
    print("PM-OS v5.0 Migration Complete")
    print("=" * 50)

    for name, passed, detail in result.checks:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}: {detail}")

    if backup_tag:
        print(f"\n  Backup:   git tag {backup_tag}")
        print(f"  Rollback: python3 migrate_to_v5.py --rollback")
        print(f"            or: git checkout {backup_tag}")

    print("\n  Next: Run /base status to verify everything works.")
    print("=" * 50)


def rollback(pm_os_root: Path):
    """Restore from git tag."""
    try:
        result = subprocess.run(
            ["git", "tag", "-l", "v4.x-backup-*"],
            cwd=str(pm_os_root), capture_output=True, text=True, check=True,
        )
        tags = sorted(result.stdout.strip().split("\n"))
        tags = [t for t in tags if t]  # Remove empty strings
    except (subprocess.CalledProcessError, FileNotFoundError):
        tags = []

    if not tags:
        print("No backup tags found.")
        return

    latest = tags[-1]
    print(f"Restoring from {latest}...")
    try:
        subprocess.run(
            ["git", "checkout", latest, "--", "user/", "common/"],
            cwd=str(pm_os_root), check=True,
        )
        print(f"Restored. You're back on v4.x.")
    except subprocess.CalledProcessError as e:
        print(f"Rollback failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="PM-OS v4.x -> v5.0 Migration")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen")
    parser.add_argument("--auto-confirm", action="store_true", help="Skip confirmation")
    parser.add_argument("--rollback", action="store_true", help="Revert to v4.x-backup")
    args = parser.parse_args()

    pm_os_root = get_pm_os_root()
    print(f"PM-OS root: {pm_os_root}")

    if args.rollback:
        rollback(pm_os_root)
        return

    # Step 1: Analyze
    print("\nStep 1: Analyzing...")
    report = analyze(pm_os_root)

    # Step 2: Confirm
    if args.dry_run:
        confirm(report, interactive=False)
        print("\n[DRY RUN] No changes made.")
        return

    if not args.auto_confirm:
        if not confirm(report):
            print("Migration cancelled.")
            return
    else:
        print(f"\n  Auto-confirmed: {len(report.keep_paths)} keep, "
              f"{len(report.archive_paths)} archive, "
              f"{len(report.delete_paths)} delete")

    # Step 3: Backup
    print("\nStep 3: Backing up...")
    backup_tag = backup(pm_os_root)

    # Step 4: Migrate
    print("\nStep 4: Migrating...")
    migrate(pm_os_root, report)

    # Step 5: Validate
    print("\nStep 5: Validating...")
    result = validate(pm_os_root)

    # Step 6: Report
    print_report(result, backup_tag)


if __name__ == "__main__":
    main()
