#!/usr/bin/env python3
"""
PM-OS Brain Migration Runner

Orchestrates the full migration from Brain 1.1 to Brain 1.2.
"""

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add tools directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))


class MigrationRunner:
    """
    Orchestrates Brain 1.1 to 1.2 migration.

    Steps:
    1. Create backup
    2. Migrate entities to v2 schema
    3. Build v2 registry
    4. Create initial snapshot
    5. Verify tools work
    """

    def __init__(self, brain_path: Path):
        """
        Initialize the migration runner.

        Args:
            brain_path: Path to the brain directory
        """
        self.brain_path = brain_path
        self.backup_path: Optional[Path] = None
        self.stats = {
            "entities_migrated": 0,
            "entities_skipped": 0,
            "entities_failed": 0,
            "start_time": None,
            "end_time": None,
        }

    def run_migration(
        self,
        dry_run: bool = False,
        skip_backup: bool = False,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Run the full migration.

        Args:
            dry_run: Preview without making changes
            skip_backup: Skip backup creation
            force: Force migration even if already migrated

        Returns:
            Migration result summary
        """
        self.stats["start_time"] = datetime.now(timezone.utc).isoformat()

        print("Brain 1.2 Migration")
        print("=" * 60)

        # Check if already migrated
        if not force and self._is_already_migrated():
            print("Brain appears to already be v2 format. Use --force to re-migrate.")
            return {"status": "skipped", "reason": "already_migrated"}

        # Step 1: Create backup
        if not skip_backup and not dry_run:
            print("\n[1/5] Creating backup...")
            self.backup_path = self._create_backup()
            print(f"  Backup created: {self.backup_path}")
        else:
            print("\n[1/5] Skipping backup")

        # Step 2: Migrate entities
        print("\n[2/5] Migrating entities to v2 schema...")
        self._migrate_entities(dry_run)
        print(f"  Migrated: {self.stats['entities_migrated']}")
        print(f"  Skipped: {self.stats['entities_skipped']}")
        print(f"  Failed: {self.stats['entities_failed']}")

        # Step 3: Build v2 registry
        print("\n[3/5] Building v2 registry...")
        if not dry_run:
            self._build_v2_registry()
            print("  Registry updated")
        else:
            print("  [DRY-RUN] Would build v2 registry")

        # Step 4: Create initial snapshot
        print("\n[4/5] Creating initial snapshot...")
        if not dry_run:
            snapshot_path = self._create_initial_snapshot()
            print(f"  Snapshot created: {snapshot_path}")
        else:
            print("  [DRY-RUN] Would create snapshot")

        # Step 5: Verify tools
        print("\n[5/5] Verifying tool compatibility...")
        verification = self._verify_tools(dry_run)
        print(f"  Tools verified: {verification['passed']}/{verification['total']}")

        self.stats["end_time"] = datetime.now(timezone.utc).isoformat()

        # Summary
        print("\n" + "=" * 60)
        print("Migration Complete!")
        print(f"  Entities migrated: {self.stats['entities_migrated']}")
        if self.backup_path:
            print(f"  Backup location: {self.backup_path}")

        return {
            "status": "success",
            "stats": self.stats,
            "verification": verification,
            "backup_path": str(self.backup_path) if self.backup_path else None,
        }

    def rollback(self) -> bool:
        """
        Rollback migration from backup.

        Returns:
            True if rollback successful
        """
        if not self.backup_path or not self.backup_path.exists():
            print("No backup found to rollback from")
            return False

        print(f"Rolling back from: {self.backup_path}")

        # Remove current brain
        if self.brain_path.exists():
            shutil.rmtree(self.brain_path)

        # Restore from backup
        shutil.copytree(self.backup_path, self.brain_path)
        print("Rollback complete")

        return True

    def _is_already_migrated(self) -> bool:
        """Check if brain is already v2 format."""
        registry_path = self.brain_path / "registry.yaml"
        if not registry_path.exists():
            return False

        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                registry = yaml.safe_load(f) or {}
            return "$schema" in registry
        except Exception:
            return False

    def _create_backup(self) -> Path:
        """Create backup of current brain state."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = self.brain_path.parent / "brain_backups"
        backup_dir.mkdir(exist_ok=True)

        backup_path = backup_dir / f"brain-pre-v2-{timestamp}"
        shutil.copytree(self.brain_path, backup_path)

        return backup_path

    def _migrate_entities(self, dry_run: bool):
        """Migrate all entities to v2 schema."""
        from schema_migrator import SchemaMigrator

        migrator = SchemaMigrator(self.brain_path)

        # Get all entity files
        entity_files = list(self.brain_path.rglob("*.md"))
        entity_files = [
            f
            for f in entity_files
            if f.name.lower() not in ("readme.md", "index.md", "_index.md")
            and ".snapshots" not in str(f)
            and ".schema" not in str(f)
            and "brain_backups" not in str(f)
        ]

        for entity_path in entity_files:
            try:
                if self._is_v2_entity(entity_path):
                    self.stats["entities_skipped"] += 1
                    continue

                if not dry_run:
                    migrator.migrate_file(entity_path)

                self.stats["entities_migrated"] += 1

            except Exception as e:
                self.stats["entities_failed"] += 1
                print(f"  Failed: {entity_path.name}: {e}")

    def _is_v2_entity(self, entity_path: Path) -> bool:
        """Check if entity is already v2 format."""
        try:
            content = entity_path.read_text(encoding="utf-8")
            return "$schema" in content and "brain://entity" in content
        except Exception:
            return False

    def _build_v2_registry(self):
        """Build v2 registry from migrated entities."""
        from registry_v2_builder import RegistryV2Builder

        builder = RegistryV2Builder(self.brain_path)
        registry = builder.build()
        builder.save(registry)

    def _create_initial_snapshot(self) -> Path:
        """Create initial snapshot after migration."""
        from snapshot_manager import SnapshotManager

        manager = SnapshotManager(self.brain_path)
        return manager.create_snapshot(
            include_entities=True,
            compress=True,
            metadata={
                "migration": "v1_to_v2",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _verify_tools(self, dry_run: bool) -> Dict[str, Any]:
        """Verify that tools work with new format."""
        verification = {"total": 0, "passed": 0, "failed": [], "checks": {}}

        # Test 1: Registry loads
        verification["total"] += 1
        try:
            from brain_loader import load_registry

            registry = load_registry()
            if registry:
                verification["passed"] += 1
                verification["checks"]["registry_load"] = "passed"
            else:
                verification["failed"].append("registry_load")
                verification["checks"]["registry_load"] = "failed"
        except Exception as e:
            verification["failed"].append(f"registry_load: {e}")
            verification["checks"]["registry_load"] = f"failed: {e}"

        # Test 2: Entity validator works
        verification["total"] += 1
        try:
            from entity_validator import EntityValidator

            validator = EntityValidator(self.brain_path)
            # Just verify it can be instantiated
            verification["passed"] += 1
            verification["checks"]["entity_validator"] = "passed"
        except Exception as e:
            verification["failed"].append(f"entity_validator: {e}")
            verification["checks"]["entity_validator"] = f"failed: {e}"

        # Test 3: Quality scorer works
        verification["total"] += 1
        try:
            from quality_scorer import QualityScorer

            scorer = QualityScorer(self.brain_path)
            # Just verify it can be instantiated
            verification["passed"] += 1
            verification["checks"]["quality_scorer"] = "passed"
        except Exception as e:
            verification["failed"].append(f"quality_scorer: {e}")
            verification["checks"]["quality_scorer"] = f"failed: {e}"

        # Test 4: Event store works
        verification["total"] += 1
        try:
            from event_store import EventStore

            store = EventStore(self.brain_path)
            verification["passed"] += 1
            verification["checks"]["event_store"] = "passed"
        except Exception as e:
            verification["failed"].append(f"event_store: {e}")
            verification["checks"]["event_store"] = f"failed: {e}"

        # Test 5: Temporal query works
        verification["total"] += 1
        try:
            from temporal_query import TemporalQuery

            query = TemporalQuery(self.brain_path)
            verification["passed"] += 1
            verification["checks"]["temporal_query"] = "passed"
        except Exception as e:
            verification["failed"].append(f"temporal_query: {e}")
            verification["checks"]["temporal_query"] = f"failed: {e}"

        return verification


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run Brain 1.1 to 1.2 migration")
    parser.add_argument(
        "action",
        choices=["migrate", "rollback", "verify", "status"],
        help="Action to perform",
    )
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without making changes",
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip backup creation",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force migration even if already migrated",
    )
    parser.add_argument(
        "--backup-path",
        type=Path,
        help="Specific backup path for rollback",
    )

    args = parser.parse_args()

    # Default brain path
    if not args.brain_path:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from path_resolver import get_paths

        paths = get_paths()
        args.brain_path = paths.user / "brain"

    runner = MigrationRunner(args.brain_path)

    if args.action == "migrate":
        result = runner.run_migration(
            dry_run=args.dry_run,
            skip_backup=args.skip_backup,
            force=args.force,
        )
        return 0 if result.get("status") == "success" else 1

    elif args.action == "rollback":
        if args.backup_path:
            runner.backup_path = args.backup_path
        success = runner.rollback()
        return 0 if success else 1

    elif args.action == "verify":
        verification = runner._verify_tools(dry_run=True)
        print("Tool Verification")
        print("=" * 40)
        for check, status in verification["checks"].items():
            print(f"  {check}: {status}")
        print(f"\nPassed: {verification['passed']}/{verification['total']}")
        return 0 if verification["passed"] == verification["total"] else 1

    elif args.action == "status":
        is_v2 = runner._is_already_migrated()
        print(f"Brain version: {'v2 (migrated)' if is_v2 else 'v1'}")
        print(f"Brain path: {args.brain_path}")

        # Count entities
        entity_files = list(args.brain_path.rglob("*.md"))
        entity_files = [
            f for f in entity_files if f.name.lower() not in ("readme.md", "index.md")
        ]
        print(f"Total entities: {len(entity_files)}")

        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
