#!/usr/bin/env python3
"""
PM-OS Migration Revert

Reverts a v3.0 migration back to v2.4 using a snapshot.

Steps:
1. Verify snapshot integrity
2. Clear v3.0 user/ content
3. Restore from snapshot
4. Verify restoration
5. Clean up v3.0 structure (optional)

Author: PM-OS Team
Version: 3.0.0
"""

import logging
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RevertResult:
    """Result of a revert operation."""

    success: bool
    snapshot_path: Path
    target_path: Path
    files_restored: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class RevertEngine:
    """
    Engine for reverting PM-OS migrations.

    Restores the original v2.4 state from a snapshot.
    """

    def __init__(
        self,
        snapshot_path: Path,
        target_path: Optional[Path] = None,
    ):
        """
        Initialize the revert engine.

        Args:
            snapshot_path: Path to snapshot directory
            target_path: Where to restore. Defaults to original source.
        """
        self.snapshot_path = Path(snapshot_path).resolve()
        self.target_path = Path(target_path).resolve() if target_path else None

        # Load snapshot metadata
        from .snapshot import load_snapshot

        self.snapshot = load_snapshot(self.snapshot_path)

        if not self.target_path:
            self.target_path = Path(self.snapshot.metadata.source_path)

    def run_revert(
        self,
        force: bool = False,
        dry_run: bool = False,
        clean_v30: bool = False,
    ) -> RevertResult:
        """
        Run the revert process.

        Args:
            force: Skip confirmation prompts
            dry_run: Simulate revert only
            clean_v30: Also remove v3.0 structure

        Returns:
            RevertResult with status
        """
        result = RevertResult(
            success=False,
            snapshot_path=self.snapshot_path,
            target_path=self.target_path,
        )

        try:
            # Step 1: Verify snapshot
            logger.info("Verifying snapshot integrity...")
            from .snapshot import SnapshotManager

            manager = SnapshotManager()
            verification = manager.verify_snapshot(self.snapshot)

            if not verification["valid"]:
                result.errors.append("Snapshot integrity check failed")
                if verification["missing_files"]:
                    result.errors.append(
                        f"Missing {len(verification['missing_files'])} files"
                    )
                if verification["checksum_mismatches"]:
                    result.errors.append(
                        f"{len(verification['checksum_mismatches'])} checksum mismatches"
                    )
                return result

            logger.info("Snapshot verified")

            # Step 2: Check target
            if self.target_path.exists() and not force and not dry_run:
                logger.warning(f"Target exists: {self.target_path}")
                result.warnings.append("Target directory exists - will be overwritten")

            # Step 3: Restore files
            logger.info("Restoring files...")
            files_restored, restore_errors = self._restore_files(dry_run)
            result.files_restored = files_restored
            result.errors.extend(restore_errors)

            # Step 4: Verify restoration
            if not dry_run:
                logger.info("Verifying restoration...")
                verified, verify_errors = self._verify_restoration()
                if not verified:
                    result.errors.extend(verify_errors)

            # Step 5: Clean v3.0 structure if requested
            if clean_v30 and not dry_run:
                logger.info("Cleaning v3.0 structure...")
                self._clean_v30_structure()

            result.success = len(result.errors) == 0

        except Exception as e:
            logger.error(f"Revert failed: {e}")
            result.errors.append(str(e))

        return result

    def _restore_files(self, dry_run: bool = False) -> tuple:
        """
        Restore files from snapshot.

        Returns:
            Tuple of (files_restored, errors)
        """
        files_restored = 0
        errors = []

        content_path = self.snapshot_path / "content"

        if not dry_run:
            # Clear target if it exists
            if self.target_path.exists():
                # Don't remove, just overwrite files
                pass
            else:
                self.target_path.mkdir(parents=True)

        for item in content_path.rglob("*"):
            if item.is_dir():
                continue

            rel_path = item.relative_to(content_path)
            target_file = self.target_path / rel_path

            try:
                if not dry_run:
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target_file)
                files_restored += 1

            except Exception as e:
                errors.append(f"Failed to restore {rel_path}: {e}")

        return files_restored, errors

    def _verify_restoration(self) -> tuple:
        """
        Verify restoration matches snapshot.

        Returns:
            Tuple of (success, errors)
        """
        errors = []
        import hashlib

        for rel_path, expected_checksum in self.snapshot.metadata.checksums.items():
            target_file = self.target_path / rel_path

            if not target_file.exists():
                errors.append(f"Missing after restore: {rel_path}")
                continue

            # Verify checksum
            sha256 = hashlib.sha256()
            with open(target_file, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)

            if sha256.hexdigest() != expected_checksum:
                errors.append(f"Checksum mismatch: {rel_path}")

        return len(errors) == 0, errors

    def _clean_v30_structure(self) -> None:
        """Remove v3.0 directory structure."""
        v30_dirs = [
            self.target_path.parent / "pm-os",
            self.target_path.parent / "common",
            self.target_path.parent / "user",
        ]

        for dir_path in v30_dirs:
            if dir_path.exists() and dir_path != self.target_path:
                try:
                    shutil.rmtree(dir_path)
                    logger.info(f"Removed: {dir_path}")
                except Exception as e:
                    logger.warning(f"Could not remove {dir_path}: {e}")

        # Remove marker files
        markers = [
            self.target_path.parent / ".pm-os-root",
            self.target_path / ".pm-os-user",
        ]

        for marker in markers:
            if marker.exists():
                marker.unlink()


def revert_migration(
    snapshot_path: Path,
    target_path: Optional[Path] = None,
    force: bool = False,
    dry_run: bool = False,
    clean_v30: bool = False,
) -> RevertResult:
    """
    Revert a PM-OS migration.

    Args:
        snapshot_path: Path to snapshot directory
        target_path: Where to restore
        force: Skip confirmations
        dry_run: Simulate only
        clean_v30: Remove v3.0 structure

    Returns:
        RevertResult with status
    """
    engine = RevertEngine(snapshot_path, target_path)
    return engine.run_revert(force, dry_run, clean_v30)


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PM-OS Migration Revert")
    parser.add_argument("snapshot", help="Path to snapshot directory")
    parser.add_argument("--target", help="Target path for restoration")
    parser.add_argument("--force", action="store_true", help="Skip confirmations")
    parser.add_argument("--dry-run", action="store_true", help="Simulate revert")
    parser.add_argument(
        "--clean-v30", action="store_true", help="Remove v3.0 structure"
    )

    args = parser.parse_args()

    # Confirmation unless force or dry-run
    if not args.force and not args.dry_run:
        print(f"\nThis will restore from: {args.snapshot}")
        if args.target:
            print(f"To: {args.target}")
        else:
            # Load snapshot to show original path
            from .snapshot import load_snapshot

            snapshot = load_snapshot(Path(args.snapshot))
            print(f"To: {snapshot.metadata.source_path}")

        response = input("\nProceed? [y/N] ")
        if response.lower() != "y":
            print("Revert cancelled")
            sys.exit(0)

    result = revert_migration(
        Path(args.snapshot),
        Path(args.target) if args.target else None,
        force=args.force,
        dry_run=args.dry_run,
        clean_v30=args.clean_v30,
    )

    print("\n" + "=" * 50)
    print("Revert " + ("Simulation " if args.dry_run else "") + "Result")
    print("=" * 50)

    if result.success:
        print("✓ Revert successful!")
        print(f"  Files restored: {result.files_restored}")
        print(f"  Target: {result.target_path}")
    else:
        print("✗ Revert failed")
        for error in result.errors:
            print(f"  Error: {error}")

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  ⚠ {warning}")

    sys.exit(0 if result.success else 1)
