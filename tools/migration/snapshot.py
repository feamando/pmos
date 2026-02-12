#!/usr/bin/env python3
"""
PM-OS Migration Snapshot

Creates and manages snapshots of v2.4 installations for migration safety.

Features:
- Full directory backup with metadata
- Integrity verification via checksums
- Snapshot listing and restoration
- Compression support

Usage:
    from migration.snapshot import create_snapshot, load_snapshot

    # Create snapshot
    snapshot = create_snapshot(source_path, snapshot_dir)
    print(f"Created: {snapshot.path}")

    # List snapshots
    snapshots = list_snapshots(snapshot_dir)

Author: PM-OS Team
Version: 3.0.0
"""

import hashlib
import json
import logging
import os
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SnapshotMetadata:
    """Metadata for a snapshot."""

    snapshot_id: str
    created_at: str
    source_path: str
    pm_os_version: str
    file_count: int
    total_size_bytes: int
    checksums: Dict[str, str] = field(default_factory=dict)
    git_commit: Optional[str] = None
    git_branch: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SnapshotMetadata":
        return cls(**data)


@dataclass
class Snapshot:
    """A PM-OS installation snapshot."""

    path: Path
    metadata: SnapshotMetadata

    @property
    def is_valid(self) -> bool:
        """Check if snapshot is valid and complete."""
        if not self.path.exists():
            return False
        if not (self.path / "metadata.json").exists():
            return False
        if not (self.path / "content").exists():
            return False
        return True


class SnapshotManager:
    """
    Creates and manages PM-OS installation snapshots.

    Snapshots provide a safety net for migration, allowing
    full restoration of the original state.
    """

    METADATA_FILE = "metadata.json"
    CONTENT_DIR = "content"
    CHECKSUMS_FILE = "checksums.sha256"

    # Directories to exclude from snapshot
    EXCLUDE_DIRS = {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".pytest_cache",
    }

    # File patterns to exclude
    EXCLUDE_PATTERNS = {
        "*.pyc",
        "*.pyo",
        ".DS_Store",
        "Thumbs.db",
    }

    def __init__(self, snapshot_dir: Optional[Path] = None):
        """
        Initialize the snapshot manager.

        Args:
            snapshot_dir: Directory to store snapshots. Defaults to ../snapshots
        """
        self.snapshot_dir = (
            Path(snapshot_dir) if snapshot_dir else Path.cwd().parent / "snapshots"
        )

    def create_snapshot(
        self,
        source_path: Path,
        snapshot_id: Optional[str] = None,
        include_git: bool = False,
    ) -> Snapshot:
        """
        Create a snapshot of a PM-OS installation.

        Args:
            source_path: Path to v2.4 installation
            snapshot_id: Custom snapshot ID. Defaults to timestamp.
            include_git: Include .git directory

        Returns:
            Snapshot object with path and metadata
        """
        source_path = Path(source_path).resolve()

        # Generate snapshot ID
        if not snapshot_id:
            snapshot_id = datetime.now().strftime("%Y%m%d-%H%M%S")

        snapshot_path = self.snapshot_dir / f"snapshot-{snapshot_id}"

        # Ensure snapshot directory exists
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        if snapshot_path.exists():
            raise ValueError(f"Snapshot already exists: {snapshot_path}")

        logger.info(f"Creating snapshot: {snapshot_id}")

        # Create snapshot structure
        snapshot_path.mkdir(parents=True)
        content_path = snapshot_path / self.CONTENT_DIR
        content_path.mkdir()

        # Copy files
        file_count = 0
        total_size = 0
        checksums = {}

        exclude_dirs = self.EXCLUDE_DIRS.copy()
        if not include_git:
            exclude_dirs.add(".git")

        for item in source_path.rglob("*"):
            # Skip excluded directories
            if any(excl in item.parts for excl in exclude_dirs):
                continue

            # Skip excluded patterns
            if any(item.match(pattern) for pattern in self.EXCLUDE_PATTERNS):
                continue

            rel_path = item.relative_to(source_path)
            dest_path = content_path / rel_path

            if item.is_dir():
                dest_path.mkdir(parents=True, exist_ok=True)
            else:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest_path)

                # Calculate checksum
                checksum = self._calculate_checksum(item)
                checksums[str(rel_path)] = checksum

                file_count += 1
                total_size += item.stat().st_size

        logger.info(f"Copied {file_count} files ({total_size / 1024 / 1024:.1f}MB)")

        # Get git info
        git_commit = None
        git_branch = None
        try:
            import subprocess

            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=source_path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                git_commit = result.stdout.strip()

            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=source_path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                git_branch = result.stdout.strip()
        except Exception:
            pass

        # Create metadata
        metadata = SnapshotMetadata(
            snapshot_id=snapshot_id,
            created_at=datetime.now().isoformat(),
            source_path=str(source_path),
            pm_os_version="2.4",  # We're snapshotting v2.4
            file_count=file_count,
            total_size_bytes=total_size,
            checksums=checksums,
            git_commit=git_commit,
            git_branch=git_branch,
        )

        # Save metadata
        metadata_path = snapshot_path / self.METADATA_FILE
        with open(metadata_path, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)

        # Save checksums file
        checksums_path = snapshot_path / self.CHECKSUMS_FILE
        with open(checksums_path, "w") as f:
            for path, checksum in sorted(checksums.items()):
                f.write(f"{checksum}  {path}\n")

        logger.info(f"Snapshot created: {snapshot_path}")

        return Snapshot(path=snapshot_path, metadata=metadata)

    def load_snapshot(self, snapshot_path: Path) -> Snapshot:
        """
        Load an existing snapshot.

        Args:
            snapshot_path: Path to snapshot directory

        Returns:
            Snapshot object
        """
        snapshot_path = Path(snapshot_path)

        metadata_path = snapshot_path / self.METADATA_FILE
        if not metadata_path.exists():
            raise ValueError(f"Not a valid snapshot: {snapshot_path}")

        with open(metadata_path) as f:
            metadata_dict = json.load(f)

        metadata = SnapshotMetadata.from_dict(metadata_dict)

        return Snapshot(path=snapshot_path, metadata=metadata)

    def list_snapshots(self) -> List[Snapshot]:
        """
        List all available snapshots.

        Returns:
            List of Snapshot objects
        """
        if not self.snapshot_dir.exists():
            return []

        snapshots = []
        for item in self.snapshot_dir.iterdir():
            if item.is_dir() and item.name.startswith("snapshot-"):
                try:
                    snapshot = self.load_snapshot(item)
                    snapshots.append(snapshot)
                except Exception as e:
                    logger.warning(f"Invalid snapshot {item}: {e}")

        # Sort by creation date (newest first)
        snapshots.sort(key=lambda s: s.metadata.created_at, reverse=True)

        return snapshots

    def verify_snapshot(self, snapshot: Snapshot) -> Dict[str, Any]:
        """
        Verify snapshot integrity.

        Args:
            snapshot: Snapshot to verify

        Returns:
            Verification result with any mismatches
        """
        result = {
            "valid": True,
            "missing_files": [],
            "checksum_mismatches": [],
        }

        content_path = snapshot.path / self.CONTENT_DIR

        for rel_path, expected_checksum in snapshot.metadata.checksums.items():
            file_path = content_path / rel_path

            if not file_path.exists():
                result["valid"] = False
                result["missing_files"].append(rel_path)
                continue

            actual_checksum = self._calculate_checksum(file_path)
            if actual_checksum != expected_checksum:
                result["valid"] = False
                result["checksum_mismatches"].append(
                    {
                        "file": rel_path,
                        "expected": expected_checksum,
                        "actual": actual_checksum,
                    }
                )

        return result

    def delete_snapshot(self, snapshot: Snapshot) -> None:
        """
        Delete a snapshot.

        Args:
            snapshot: Snapshot to delete
        """
        if snapshot.path.exists():
            shutil.rmtree(snapshot.path)
            logger.info(f"Deleted snapshot: {snapshot.path}")

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


# Convenience functions
def create_snapshot(
    source_path: Path,
    snapshot_dir: Optional[Path] = None,
    snapshot_id: Optional[str] = None,
) -> Snapshot:
    """Create a snapshot of a PM-OS installation."""
    manager = SnapshotManager(snapshot_dir)
    return manager.create_snapshot(source_path, snapshot_id)


def load_snapshot(snapshot_path: Path) -> Snapshot:
    """Load an existing snapshot."""
    manager = SnapshotManager()
    return manager.load_snapshot(snapshot_path)


def list_snapshots(snapshot_dir: Optional[Path] = None) -> List[Snapshot]:
    """List all available snapshots."""
    manager = SnapshotManager(snapshot_dir)
    return manager.list_snapshots()


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PM-OS Snapshot Manager")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Create command
    create_parser = subparsers.add_parser("create", help="Create snapshot")
    create_parser.add_argument("source", help="Source path")
    create_parser.add_argument("--id", help="Snapshot ID")
    create_parser.add_argument("--output", help="Output directory")
    create_parser.add_argument(
        "--include-git", action="store_true", help="Include .git"
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List snapshots")
    list_parser.add_argument("--dir", help="Snapshot directory")

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify snapshot")
    verify_parser.add_argument("path", help="Snapshot path")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete snapshot")
    delete_parser.add_argument("path", help="Snapshot path")

    args = parser.parse_args()

    if args.command == "create":
        snapshot_dir = Path(args.output) if args.output else None
        snapshot = create_snapshot(
            Path(args.source),
            snapshot_dir,
            args.id,
        )
        print(f"Created: {snapshot.path}")
        print(f"Files: {snapshot.metadata.file_count}")
        print(f"Size: {snapshot.metadata.total_size_bytes / 1024 / 1024:.1f}MB")

    elif args.command == "list":
        snapshot_dir = Path(args.dir) if args.dir else None
        manager = SnapshotManager(snapshot_dir)
        snapshots = manager.list_snapshots()

        if not snapshots:
            print("No snapshots found")
        else:
            print(f"Found {len(snapshots)} snapshot(s):\n")
            for s in snapshots:
                print(f"  {s.metadata.snapshot_id}")
                print(f"    Created: {s.metadata.created_at}")
                print(f"    Files: {s.metadata.file_count}")
                print(f"    Path: {s.path}")
                print()

    elif args.command == "verify":
        snapshot = load_snapshot(Path(args.path))
        manager = SnapshotManager()
        result = manager.verify_snapshot(snapshot)

        if result["valid"]:
            print("✓ Snapshot is valid")
        else:
            print("✗ Snapshot has issues:")
            if result["missing_files"]:
                print(f"  Missing files: {len(result['missing_files'])}")
            if result["checksum_mismatches"]:
                print(f"  Checksum mismatches: {len(result['checksum_mismatches'])}")
            sys.exit(1)

    elif args.command == "delete":
        snapshot = load_snapshot(Path(args.path))
        manager = SnapshotManager()
        manager.delete_snapshot(snapshot)
        print(f"Deleted: {args.path}")

    else:
        parser.print_help()
