#!/usr/bin/env python3
"""
PM-OS Migration Preflight Checks

Validates that a v2.4 installation is ready for migration to v3.0.

Checks:
1. Version compatibility
2. Git status (clean working tree)
3. Python version
4. Disk space
5. File permissions
6. Required directories exist

Usage:
    from migration.preflight import run_preflight

    result = run_preflight()
    if result.can_migrate:
        print("Ready to migrate!")
    else:
        for check in result.failed_checks:
            print(f"Failed: {check.name} - {check.message}")

Author: PM-OS Team
Version: 3.0.0
"""

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CheckStatus(Enum):
    """Status of a preflight check."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class PreflightCheck:
    """Result of a single preflight check."""

    name: str
    status: CheckStatus
    message: str
    details: Optional[str] = None
    fix_hint: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.status in (CheckStatus.PASS, CheckStatus.WARN, CheckStatus.SKIP)


@dataclass
class PreflightResult:
    """Aggregate result of all preflight checks."""

    checks: List[PreflightCheck] = field(default_factory=list)
    source_path: Optional[Path] = None

    @property
    def can_migrate(self) -> bool:
        """True if all critical checks passed."""
        return all(c.status != CheckStatus.FAIL for c in self.checks)

    @property
    def passed_checks(self) -> List[PreflightCheck]:
        return [c for c in self.checks if c.status == CheckStatus.PASS]

    @property
    def failed_checks(self) -> List[PreflightCheck]:
        return [c for c in self.checks if c.status == CheckStatus.FAIL]

    @property
    def warning_checks(self) -> List[PreflightCheck]:
        return [c for c in self.checks if c.status == CheckStatus.WARN]


class PreflightChecker:
    """
    Runs preflight checks for PM-OS migration.

    Validates that the source installation is in a valid state
    for migration to v3.0.
    """

    # Minimum Python version
    MIN_PYTHON = (3, 9)

    # Minimum disk space (MB)
    MIN_DISK_SPACE_MB = 500

    # Required v2.4 directories
    V24_REQUIRED_DIRS = [
        "AI_Guidance",
        "AI_Guidance/Brain",
        "AI_Guidance/Tools",
        ".claude",
    ]

    # Required v2.4 files
    V24_REQUIRED_FILES = [
        "AGENT.md",
        "AI_Guidance/Rules/AI_AGENTS_GUIDE.md",
    ]

    def __init__(self, source_path: Optional[Path] = None):
        """
        Initialize the preflight checker.

        Args:
            source_path: Path to v2.4 installation. Defaults to cwd.
        """
        self.source_path = Path(source_path) if source_path else Path.cwd()

    def run_all_checks(self) -> PreflightResult:
        """
        Run all preflight checks.

        Returns:
            PreflightResult with all check results.
        """
        result = PreflightResult(source_path=self.source_path)

        checks = [
            self._check_v24_structure,
            self._check_python_version,
            self._check_git_status,
            self._check_disk_space,
            self._check_file_permissions,
            self._check_dependencies,
        ]

        for check_fn in checks:
            try:
                check_result = check_fn()
                result.checks.append(check_result)
            except Exception as e:
                result.checks.append(
                    PreflightCheck(
                        name=check_fn.__name__.replace("_check_", ""),
                        status=CheckStatus.FAIL,
                        message=f"Check failed with error: {e}",
                    )
                )

        return result

    def _check_v24_structure(self) -> PreflightCheck:
        """Check for valid v2.4 directory structure."""
        missing_dirs = []
        missing_files = []

        for dir_path in self.V24_REQUIRED_DIRS:
            if not (self.source_path / dir_path).is_dir():
                missing_dirs.append(dir_path)

        for file_path in self.V24_REQUIRED_FILES:
            if not (self.source_path / file_path).is_file():
                missing_files.append(file_path)

        if missing_dirs or missing_files:
            details = []
            if missing_dirs:
                details.append(f"Missing directories: {', '.join(missing_dirs)}")
            if missing_files:
                details.append(f"Missing files: {', '.join(missing_files)}")

            return PreflightCheck(
                name="v24_structure",
                status=CheckStatus.FAIL,
                message="Not a valid PM-OS v2.4 installation",
                details="\n".join(details),
                fix_hint="Ensure you're running from the root of a v2.4 PM-OS installation",
            )

        # Count entities for info
        brain_path = self.source_path / "AI_Guidance" / "Brain"
        entity_count = len(list(brain_path.glob("**/*.md")))

        return PreflightCheck(
            name="v24_structure",
            status=CheckStatus.PASS,
            message=f"Valid v2.4 structure ({entity_count} Brain files)",
        )

    def _check_python_version(self) -> PreflightCheck:
        """Check Python version meets minimum requirements."""
        current = sys.version_info[:2]

        if current < self.MIN_PYTHON:
            return PreflightCheck(
                name="python_version",
                status=CheckStatus.FAIL,
                message=f"Python {current[0]}.{current[1]} is below minimum {self.MIN_PYTHON[0]}.{self.MIN_PYTHON[1]}",
                fix_hint=f"Upgrade Python to {self.MIN_PYTHON[0]}.{self.MIN_PYTHON[1]} or higher",
            )

        return PreflightCheck(
            name="python_version",
            status=CheckStatus.PASS,
            message=f"Python {current[0]}.{current[1]}",
        )

    def _check_git_status(self) -> PreflightCheck:
        """Check git status for uncommitted changes."""
        try:
            # Check if it's a git repo
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.source_path,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                return PreflightCheck(
                    name="git_status",
                    status=CheckStatus.WARN,
                    message="Not a git repository",
                    details="Migration will proceed but no git backup available",
                )

            # Check for uncommitted changes
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.source_path,
                capture_output=True,
                text=True,
            )

            if result.stdout.strip():
                changed_files = len(result.stdout.strip().split("\n"))
                return PreflightCheck(
                    name="git_status",
                    status=CheckStatus.WARN,
                    message=f"{changed_files} uncommitted changes",
                    details="Consider committing changes before migration",
                    fix_hint="Run: git add -A && git commit -m 'Pre-migration snapshot'",
                )

            return PreflightCheck(
                name="git_status",
                status=CheckStatus.PASS,
                message="Clean working tree",
            )

        except FileNotFoundError:
            return PreflightCheck(
                name="git_status",
                status=CheckStatus.WARN,
                message="Git not found",
                details="Git is recommended for migration backup",
            )

    def _check_disk_space(self) -> PreflightCheck:
        """Check available disk space."""
        try:
            stat = shutil.disk_usage(self.source_path)
            free_mb = stat.free // (1024 * 1024)

            if free_mb < self.MIN_DISK_SPACE_MB:
                return PreflightCheck(
                    name="disk_space",
                    status=CheckStatus.FAIL,
                    message=f"Only {free_mb}MB free (need {self.MIN_DISK_SPACE_MB}MB)",
                    fix_hint="Free up disk space before migration",
                )

            return PreflightCheck(
                name="disk_space",
                status=CheckStatus.PASS,
                message=f"{free_mb}MB available",
            )

        except Exception as e:
            return PreflightCheck(
                name="disk_space",
                status=CheckStatus.WARN,
                message=f"Could not check disk space: {e}",
            )

    def _check_file_permissions(self) -> PreflightCheck:
        """Check file system permissions."""
        test_dirs = [
            self.source_path,
            self.source_path / "AI_Guidance",
            self.source_path.parent,  # Need to create sibling directories
        ]

        unwritable = []
        for dir_path in test_dirs:
            if dir_path.exists() and not os.access(dir_path, os.W_OK):
                unwritable.append(str(dir_path))

        if unwritable:
            return PreflightCheck(
                name="file_permissions",
                status=CheckStatus.FAIL,
                message="Cannot write to required directories",
                details=f"Unwritable: {', '.join(unwritable)}",
                fix_hint="Check directory permissions",
            )

        return PreflightCheck(
            name="file_permissions",
            status=CheckStatus.PASS,
            message="Write permissions OK",
        )

    def _check_dependencies(self) -> PreflightCheck:
        """Check for required Python packages."""
        missing = []

        packages = [
            ("yaml", "pyyaml"),
            ("dotenv", "python-dotenv"),
        ]

        for import_name, pip_name in packages:
            try:
                __import__(import_name)
            except ImportError:
                missing.append(pip_name)

        if missing:
            return PreflightCheck(
                name="dependencies",
                status=CheckStatus.WARN,
                message=f"Missing packages: {', '.join(missing)}",
                fix_hint=f"Run: pip install {' '.join(missing)}",
            )

        return PreflightCheck(
            name="dependencies",
            status=CheckStatus.PASS,
            message="All dependencies available",
        )


def run_preflight(source_path: Optional[Path] = None) -> PreflightResult:
    """
    Run preflight checks for migration.

    Args:
        source_path: Path to v2.4 installation

    Returns:
        PreflightResult with all check results
    """
    checker = PreflightChecker(source_path)
    return checker.run_all_checks()


def print_preflight_report(result: PreflightResult) -> None:
    """Print a formatted preflight report."""
    print("\n" + "=" * 50)
    print("PM-OS Migration Preflight Report")
    print("=" * 50)
    print(f"\nSource: {result.source_path}\n")

    status_symbols = {
        CheckStatus.PASS: "✓",
        CheckStatus.WARN: "⚠",
        CheckStatus.FAIL: "✗",
        CheckStatus.SKIP: "○",
    }

    for check in result.checks:
        symbol = status_symbols.get(check.status, "?")
        print(f"  {symbol} {check.name}: {check.message}")
        if check.details:
            print(f"      {check.details}")
        if check.fix_hint and check.status in (CheckStatus.FAIL, CheckStatus.WARN):
            print(f"      Fix: {check.fix_hint}")

    print("\n" + "-" * 50)
    if result.can_migrate:
        print("✓ Ready to migrate")
        if result.warning_checks:
            print(f"  ({len(result.warning_checks)} warnings)")
    else:
        print(f"✗ Cannot migrate ({len(result.failed_checks)} failures)")
    print("=" * 50 + "\n")


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PM-OS Migration Preflight Checks")
    parser.add_argument("path", nargs="?", help="Path to v2.4 installation")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    path = Path(args.path) if args.path else None
    result = run_preflight(path)

    if args.json:
        import json

        output = {
            "can_migrate": result.can_migrate,
            "source_path": str(result.source_path),
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "details": c.details,
                    "fix_hint": c.fix_hint,
                }
                for c in result.checks
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        print_preflight_report(result)

    sys.exit(0 if result.can_migrate else 1)
