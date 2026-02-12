#!/usr/bin/env python3
"""
PM-OS Brain Snapshot Manager

Creates and manages point-in-time snapshots of the Brain registry and entities.
"""

import argparse
import gzip
import json
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


class SnapshotManager:
    """
    Manages Brain snapshots for point-in-time queries.

    Features:
    - Daily registry snapshots (~30 KB each)
    - Optional entity snapshots (full or incremental)
    - Snapshot retention policy
    - Fast point-in-time lookups
    """

    def __init__(self, brain_path: Path):
        """
        Initialize the snapshot manager.

        Args:
            brain_path: Path to the brain directory
        """
        self.brain_path = brain_path
        self.snapshots_dir = brain_path / ".snapshots"
        self.registry_path = brain_path / "registry.yaml"

    def create_snapshot(
        self,
        include_entities: bool = False,
        compress: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Create a snapshot of the current Brain state.

        Args:
            include_entities: Include full entity snapshots (larger)
            compress: Compress the snapshot
            metadata: Additional metadata to include

        Returns:
            Path to the created snapshot
        """
        timestamp = datetime.utcnow()
        date_str = timestamp.strftime("%Y-%m-%d")
        time_str = timestamp.strftime("%H%M%S")

        # Create snapshot directory
        snapshot_dir = self.snapshots_dir / date_str
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        # Create snapshot data
        snapshot = {
            "$snapshot_version": "1.0",
            "$created": timestamp.isoformat() + "Z",
            "$type": "full" if include_entities else "registry",
            "metadata": metadata or {},
        }

        # Snapshot registry
        if self.registry_path.exists():
            with open(self.registry_path, "r", encoding="utf-8") as f:
                registry = yaml.safe_load(f) or {}
            snapshot["registry"] = registry

        # Optionally snapshot entities
        if include_entities:
            snapshot["entities"] = self._snapshot_entities()

        # Save snapshot
        snapshot_name = f"snapshot-{time_str}"
        if compress:
            snapshot_path = snapshot_dir / f"{snapshot_name}.json.gz"
            with gzip.open(snapshot_path, "wt", encoding="utf-8") as f:
                json.dump(snapshot, f, default=json_serial)
        else:
            snapshot_path = snapshot_dir / f"{snapshot_name}.json"
            with open(snapshot_path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2, default=json_serial)

        # Create latest symlink
        latest_link = self.snapshots_dir / "latest"
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(snapshot_path.relative_to(self.snapshots_dir))

        return snapshot_path

    def get_snapshot(
        self,
        point_in_time: Optional[datetime] = None,
        date_str: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get snapshot closest to a point in time.

        Args:
            point_in_time: The target datetime
            date_str: Specific date string (YYYY-MM-DD)

        Returns:
            Snapshot data if found
        """
        if date_str:
            target_dir = self.snapshots_dir / date_str
        elif point_in_time:
            date_str = point_in_time.strftime("%Y-%m-%d")
            target_dir = self.snapshots_dir / date_str
        else:
            # Use latest
            latest_link = self.snapshots_dir / "latest"
            if latest_link.exists():
                return self._load_snapshot(latest_link)
            return None

        if not target_dir.exists():
            # Find closest earlier snapshot
            available_dates = sorted(
                [d.name for d in self.snapshots_dir.iterdir() if d.is_dir()],
                reverse=True,
            )
            for d in available_dates:
                if d <= date_str:
                    target_dir = self.snapshots_dir / d
                    break
            else:
                return None

        # Get latest snapshot from target date
        snapshots = sorted(target_dir.glob("snapshot-*"), reverse=True)
        if snapshots:
            return self._load_snapshot(snapshots[0])

        return None

    def get_registry_at(self, point_in_time: datetime) -> Optional[Dict[str, Any]]:
        """
        Get registry state at a point in time.

        Args:
            point_in_time: The target datetime

        Returns:
            Registry data if found
        """
        snapshot = self.get_snapshot(point_in_time=point_in_time)
        if snapshot:
            return snapshot.get("registry")
        return None

    def list_snapshots(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        List available snapshots.

        Args:
            since: Filter snapshots after this time
            until: Filter snapshots before this time

        Returns:
            List of snapshot metadata
        """
        snapshots = []

        if not self.snapshots_dir.exists():
            return snapshots

        for date_dir in sorted(self.snapshots_dir.iterdir()):
            if not date_dir.is_dir() or date_dir.name == "latest":
                continue

            try:
                dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
            except ValueError:
                continue

            if since and dir_date.date() < since.date():
                continue
            if until and dir_date.date() > until.date():
                continue

            for snapshot_file in sorted(date_dir.glob("snapshot-*")):
                try:
                    # Parse time from filename
                    time_part = snapshot_file.stem.split("-")[1]
                    if time_part.endswith(".json"):
                        time_part = time_part[:-5]
                    snapshot_time = datetime.strptime(
                        f"{date_dir.name} {time_part}", "%Y-%m-%d %H%M%S"
                    )

                    snapshots.append(
                        {
                            "path": str(snapshot_file),
                            "date": date_dir.name,
                            "timestamp": snapshot_time.isoformat(),
                            "size_bytes": snapshot_file.stat().st_size,
                            "compressed": snapshot_file.suffix == ".gz",
                        }
                    )
                except (ValueError, IndexError):
                    continue

        return snapshots

    def cleanup_old_snapshots(
        self,
        retention_days: int = 30,
        keep_monthly: bool = True,
        dry_run: bool = False,
    ) -> List[str]:
        """
        Remove old snapshots based on retention policy.

        Args:
            retention_days: Keep daily snapshots for this many days
            keep_monthly: Keep first snapshot of each month indefinitely
            dry_run: Preview without deleting

        Returns:
            List of removed snapshot paths
        """
        removed = []
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        if not self.snapshots_dir.exists():
            return removed

        monthly_snapshots = set()

        for date_dir in sorted(self.snapshots_dir.iterdir()):
            if not date_dir.is_dir() or date_dir.name == "latest":
                continue

            try:
                dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
            except ValueError:
                continue

            # Track monthly snapshots
            month_key = dir_date.strftime("%Y-%m")
            if month_key not in monthly_snapshots:
                monthly_snapshots.add(month_key)
                if keep_monthly:
                    continue  # Keep first snapshot of each month

            # Check if older than retention
            if dir_date < cutoff_date:
                if dry_run:
                    print(f"Would remove: {date_dir}")
                else:
                    shutil.rmtree(date_dir)
                removed.append(str(date_dir))

        return removed

    def _snapshot_entities(self) -> Dict[str, Dict[str, Any]]:
        """Create snapshot of all entities."""
        entities = {}

        entity_files = list(self.brain_path.rglob("*.md"))
        entity_files = [
            f
            for f in entity_files
            if f.name.lower() not in ("readme.md", "index.md", "_index.md")
            and ".snapshots" not in str(f)
        ]

        for entity_path in entity_files:
            try:
                content = entity_path.read_text(encoding="utf-8")
                frontmatter = self._parse_frontmatter(content)
                if frontmatter:
                    entity_id = str(entity_path.relative_to(self.brain_path))
                    entities[entity_id] = frontmatter
            except Exception:
                continue

        return entities

    def _load_snapshot(self, path: Path) -> Optional[Dict[str, Any]]:
        """Load snapshot from file."""
        try:
            # Handle symlink
            if path.is_symlink():
                path = path.resolve()

            if path.suffix == ".gz":
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    return json.load(f)
            else:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            return None

    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """Parse YAML frontmatter from content."""
        if not content.startswith("---"):
            return {}

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}

        try:
            return yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            return {}


def create_daily_snapshot(brain_path: Optional[Path] = None) -> Path:
    """
    Convenience function to create a daily snapshot.

    Args:
        brain_path: Path to brain directory

    Returns:
        Path to created snapshot
    """
    if brain_path is None:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from path_resolver import get_paths

        paths = get_paths()
        brain_path = paths.user / "brain"

    manager = SnapshotManager(brain_path)
    return manager.create_snapshot(include_entities=False, compress=True)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Manage Brain snapshots")
    parser.add_argument(
        "action",
        choices=["create", "list", "cleanup", "get"],
        help="Action to perform",
    )
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--include-entities",
        action="store_true",
        help="Include full entity snapshots",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Target date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="Retention period in days",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without making changes",
    )

    args = parser.parse_args()

    # Default brain path
    if not args.brain_path:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from path_resolver import get_paths

        paths = get_paths()
        args.brain_path = paths.user / "brain"

    manager = SnapshotManager(args.brain_path)

    if args.action == "create":
        path = manager.create_snapshot(
            include_entities=args.include_entities,
            compress=True,
        )
        print(f"Created snapshot: {path}")

    elif args.action == "list":
        snapshots = manager.list_snapshots()
        for s in snapshots:
            size_kb = s["size_bytes"] / 1024
            print(f"{s['timestamp']} - {size_kb:.1f} KB - {s['path']}")

    elif args.action == "cleanup":
        removed = manager.cleanup_old_snapshots(
            retention_days=args.retention_days,
            dry_run=args.dry_run,
        )
        if removed:
            print(
                f"{'Would remove' if args.dry_run else 'Removed'} {len(removed)} snapshots"
            )
        else:
            print("No snapshots to remove")

    elif args.action == "get":
        if args.date:
            snapshot = manager.get_snapshot(date_str=args.date)
        else:
            snapshot = manager.get_snapshot()

        if snapshot:
            print(json.dumps(snapshot, indent=2)[:2000])
        else:
            print("No snapshot found")

    return 0


if __name__ == "__main__":
    sys.exit(main())
