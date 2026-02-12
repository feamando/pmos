#!/usr/bin/env python3
"""
PM-OS Migration Tool

Migrates a PM-OS v2.4 installation to v3.0 structure.

Migration Steps:
1. Run preflight checks
2. Create snapshot
3. Create new directory structure
4. Copy CONTENT to user/
5. Generate config.yaml
6. Create marker files
7. Validate migration

Usage:
    from migration.migrate import run_migration

    result = run_migration(source_path, target_path)
    if result.success:
        print("Migration complete!")

Author: PM-OS Team
Version: 3.0.0
"""

import logging
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent directory to path for imports when running as script
SCRIPT_DIR = Path(__file__).parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MigrationResult:
    """Result of a migration operation."""

    success: bool
    source_path: Path
    target_path: Path
    snapshot_path: Optional[Path] = None
    files_migrated: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# Content migration mapping: v2.4 path -> v3.0 path
MIGRATION_MAP = {
    # Brain content
    "AI_Guidance/Brain": "brain",
    "Brain": "brain",  # Alternative location
    # Context
    "AI_Guidance/Core_Context": "context",
    # Sessions
    "AI_Guidance/Sessions": "sessions",
    # Planning
    "Planning": "planning",
    # Team data
    "Team": "team",
    # User-specific rules
    "AI_Guidance/Rules/NGO.md": "USER.md",
    # Products (user data)
    "Products": "products",
    # Reporting
    "Reporting": "reporting",
}

# Files to skip during migration
SKIP_FILES = {
    ".DS_Store",
    "Thumbs.db",
    ".gitkeep",
}

# Directories to skip
SKIP_DIRS = {
    "__pycache__",
    ".git",
    "node_modules",
    ".venv",
    "venv",
}


class MigrationEngine:
    """
    Engine for migrating PM-OS v2.4 to v3.0.

    Handles the actual file operations and structure transformation.
    """

    def __init__(
        self,
        source_path: Path,
        target_path: Optional[Path] = None,
        common_path: Optional[Path] = None,
    ):
        """
        Initialize the migration engine.

        Args:
            source_path: Path to v2.4 installation
            target_path: Target path for user/ content. Defaults to pm-os/user
            common_path: Path to common/ (LOGIC). Defaults to pm-os/common
        """
        self.source_path = Path(source_path).resolve()

        if target_path:
            self.target_path = Path(target_path).resolve()
        else:
            # Default: create pm-os/ alongside source
            self.target_path = self.source_path.parent / "pm-os" / "user"

        if common_path:
            self.common_path = Path(common_path).resolve()
        else:
            self.common_path = self.target_path.parent / "common"

        self.root_path = self.target_path.parent

    def run_migration(
        self,
        create_snapshot: bool = True,
        dry_run: bool = False,
    ) -> MigrationResult:
        """
        Run the full migration process.

        Args:
            create_snapshot: Create backup snapshot before migration
            dry_run: If True, only simulate migration

        Returns:
            MigrationResult with migration status
        """
        result = MigrationResult(
            success=False,
            source_path=self.source_path,
            target_path=self.target_path,
        )

        try:
            # Step 1: Preflight
            logger.info("Running preflight checks...")
            try:
                from .preflight import run_preflight
            except ImportError:
                from preflight import run_preflight
            preflight = run_preflight(self.source_path)

            if not preflight.can_migrate:
                result.errors.append("Preflight checks failed")
                for check in preflight.failed_checks:
                    result.errors.append(f"  {check.name}: {check.message}")
                return result

            # Step 2: Create snapshot
            if create_snapshot and not dry_run:
                logger.info("Creating snapshot...")
                try:
                    from .snapshot import create_snapshot as make_snapshot
                except ImportError:
                    from snapshot import create_snapshot as make_snapshot
                snapshot = make_snapshot(
                    self.source_path,
                    self.root_path / "snapshots",
                )
                result.snapshot_path = snapshot.path
                logger.info(f"Snapshot created: {snapshot.path}")

            # Step 3: Create directory structure
            logger.info("Creating directory structure...")
            if not dry_run:
                self._create_directory_structure()

            # Step 4: Migrate content
            logger.info("Migrating content...")
            files_migrated, migration_errors = self._migrate_content(dry_run)
            result.files_migrated = files_migrated
            result.errors.extend(migration_errors)

            # Step 5: Generate config.yaml
            logger.info("Generating config.yaml...")
            if not dry_run:
                self._generate_config()

            # Step 6: Create marker files
            logger.info("Creating marker files...")
            if not dry_run:
                self._create_markers()

            # Step 7: Validate
            logger.info("Validating migration...")
            if not dry_run:
                try:
                    from .validate import validate_migration
                except ImportError:
                    from validate import validate_migration
                validation = validate_migration(self.target_path, self.common_path)
                if not validation.success:
                    result.warnings.extend(validation.warnings)
                    if validation.errors:
                        result.errors.extend(validation.errors)

            result.success = len(result.errors) == 0 or dry_run

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            result.errors.append(str(e))

        return result

    def _create_directory_structure(self) -> None:
        """Create the v3.0 directory structure."""
        dirs = [
            self.root_path,
            self.target_path,
            self.target_path / "brain" / "entities",
            self.target_path / "brain" / "projects",
            self.target_path / "brain" / "experiments",
            self.target_path / "brain" / "reasoning",
            self.target_path / "context",
            self.target_path / "sessions",
            self.target_path / "planning" / "meeting-prep",
            self.target_path / ".secrets",
        ]

        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)

    def _migrate_content(self, dry_run: bool = False) -> Tuple[int, List[str]]:
        """
        Migrate content from v2.4 to v3.0 structure.

        Returns:
            Tuple of (files_migrated, errors)
        """
        files_migrated = 0
        errors = []

        for source_rel, target_rel in MIGRATION_MAP.items():
            source_item = self.source_path / source_rel
            target_item = self.target_path / target_rel

            if not source_item.exists():
                continue

            try:
                if source_item.is_file():
                    # Single file migration
                    if not dry_run:
                        target_item.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source_item, target_item)
                    files_migrated += 1
                    logger.debug(f"Copied: {source_rel} -> {target_rel}")

                elif source_item.is_dir():
                    # Directory migration
                    count, dir_errors = self._migrate_directory(
                        source_item, target_item, dry_run
                    )
                    files_migrated += count
                    errors.extend(dir_errors)

            except Exception as e:
                errors.append(f"Failed to migrate {source_rel}: {e}")

        return files_migrated, errors

    def _migrate_directory(
        self,
        source_dir: Path,
        target_dir: Path,
        dry_run: bool = False,
    ) -> Tuple[int, List[str]]:
        """
        Migrate a directory recursively.

        Returns:
            Tuple of (files_migrated, errors)
        """
        files_migrated = 0
        errors = []

        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)

        for item in source_dir.rglob("*"):
            # Skip excluded items
            if item.name in SKIP_FILES:
                continue
            if any(skip in item.parts for skip in SKIP_DIRS):
                continue

            rel_path = item.relative_to(source_dir)
            target_path = target_dir / rel_path

            try:
                if item.is_dir():
                    if not dry_run:
                        target_path.mkdir(parents=True, exist_ok=True)
                else:
                    if not dry_run:
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, target_path)
                    files_migrated += 1

            except Exception as e:
                errors.append(f"Failed to copy {rel_path}: {e}")

        return files_migrated, errors

    def _generate_config(self) -> None:
        """Generate config.yaml from v2.4 settings."""
        try:
            import yaml
        except ImportError:
            logger.warning("PyYAML not available, creating minimal config")
            self._create_minimal_config()
            return

        # Try to extract settings from v2.4
        config = {
            "version": "3.0.0",
            "user": {
                "name": self._extract_user_name(),
                "email": "",
                "position": "Product Manager",
            },
            "integrations": {
                "jira": {"enabled": self._has_jira_config()},
                "github": {"enabled": self._has_github_config()},
                "slack": {"enabled": self._has_slack_config()},
                "google": {"enabled": self._has_google_config()},
            },
            "pm_os": {
                "fpf_enabled": True,
                "confucius_enabled": True,
                "auto_update": False,
            },
        }

        config_path = self.target_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        # Copy .env if exists
        source_env = self.source_path / ".env"
        target_env = self.target_path / ".env"
        if source_env.exists() and not target_env.exists():
            shutil.copy2(source_env, target_env)

    def _create_minimal_config(self) -> None:
        """Create minimal config without YAML."""
        config_content = """# PM-OS User Configuration
version: "3.0.0"

user:
  name: "User"
  email: ""
  position: "Product Manager"

integrations:
  jira:
    enabled: false
  github:
    enabled: false
  slack:
    enabled: false

pm_os:
  fpf_enabled: true
  confucius_enabled: true
"""
        config_path = self.target_path / "config.yaml"
        config_path.write_text(config_content)

    def _create_markers(self) -> None:
        """Create PM-OS marker files."""
        markers = [
            (self.root_path / ".pm-os-root", "PM-OS root directory"),
            (self.target_path / ".pm-os-user", "PM-OS user content directory"),
        ]

        for marker_path, content in markers:
            if not marker_path.exists():
                marker_path.write_text(f"# {content}\n")

    def _extract_user_name(self) -> str:
        """Try to extract user name from v2.4 files."""
        # Try NGO.md
        ngo_path = self.source_path / "AI_Guidance" / "Rules" / "NGO.md"
        if ngo_path.exists():
            content = ngo_path.read_text()
            # Look for name patterns
            for line in content.split("\n")[:20]:
                if "name:" in line.lower() or "# " in line:
                    return line.split(":")[-1].strip().replace("#", "").strip()

        return "User"

    def _has_jira_config(self) -> bool:
        """Check if Jira was configured in v2.4."""
        env_path = self.source_path / ".env"
        if env_path.exists():
            content = env_path.read_text()
            # Check for JIRA token presence (not hardcoded - just validating .env)
            token_key = "JIRA_API_TOKEN"
            assignment_pattern = token_key + "="
            return (
                token_key in content
                and assignment_pattern
                not in content.replace(" ", "").split(assignment_pattern)[0]
            )
        return False

    def _has_github_config(self) -> bool:
        """Check if GitHub was configured."""
        return (self.source_path / ".github").exists()

    def _has_slack_config(self) -> bool:
        """Check if Slack was configured."""
        env_path = self.source_path / ".env"
        if env_path.exists():
            content = env_path.read_text()
            return "SLACK_BOT_TOKEN" in content
        return False

    def _has_google_config(self) -> bool:
        """Check if Google was configured."""
        secrets_path = self.source_path / "AI_Guidance" / "Tools" / "gdrive_mcp"
        return secrets_path.exists()


def run_migration(
    source_path: Path,
    target_path: Optional[Path] = None,
    common_path: Optional[Path] = None,
    create_snapshot: bool = True,
    dry_run: bool = False,
) -> MigrationResult:
    """
    Run PM-OS migration.

    Args:
        source_path: Path to v2.4 installation
        target_path: Target path for user/ content
        common_path: Path to common/ (LOGIC)
        create_snapshot: Create backup snapshot
        dry_run: Simulate migration only

    Returns:
        MigrationResult with status
    """
    engine = MigrationEngine(source_path, target_path, common_path)
    return engine.run_migration(create_snapshot, dry_run)


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PM-OS Migration Tool")
    parser.add_argument("source", help="Source v2.4 installation path")
    parser.add_argument("--target", help="Target user/ path")
    parser.add_argument("--common", help="Path to common/")
    parser.add_argument(
        "--no-snapshot", action="store_true", help="Skip snapshot creation"
    )
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration")

    args = parser.parse_args()

    result = run_migration(
        Path(args.source),
        Path(args.target) if args.target else None,
        Path(args.common) if args.common else None,
        create_snapshot=not args.no_snapshot,
        dry_run=args.dry_run,
    )

    print("\n" + "=" * 50)
    print("Migration " + ("Simulation " if args.dry_run else "") + "Result")
    print("=" * 50)

    if result.success:
        print("✓ Migration successful!")
        print(f"  Files migrated: {result.files_migrated}")
        print(f"  Target: {result.target_path}")
        if result.snapshot_path:
            print(f"  Snapshot: {result.snapshot_path}")
    else:
        print("✗ Migration failed")
        for error in result.errors:
            print(f"  Error: {error}")

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  ⚠ {warning}")

    sys.exit(0 if result.success else 1)
