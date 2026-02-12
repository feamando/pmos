"""
PM-OS Migration Tools

Tools for migrating from PM-OS v2.4 to v3.0.

Usage:
    from migration import run_preflight, create_snapshot, run_migration

    # Check if migration is possible
    result = run_preflight()
    if result.can_migrate:
        snapshot = create_snapshot()
        run_migration()
"""

from .migrate import MigrationResult, run_migration
from .preflight import PreflightCheck, PreflightResult, run_preflight
from .revert import RevertResult, revert_migration
from .snapshot import (
    Snapshot,
    SnapshotMetadata,
    create_snapshot,
    list_snapshots,
    load_snapshot,
)
from .validate import ValidationResult, validate_migration

__all__ = [
    # Preflight
    "PreflightResult",
    "PreflightCheck",
    "run_preflight",
    # Snapshot
    "Snapshot",
    "SnapshotMetadata",
    "create_snapshot",
    "load_snapshot",
    "list_snapshots",
    # Migration
    "MigrationResult",
    "run_migration",
    # Validation
    "ValidationResult",
    "validate_migration",
    # Revert
    "RevertResult",
    "revert_migration",
]
