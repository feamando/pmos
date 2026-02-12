#!/usr/bin/env python3
"""
PM-OS Migration Validation

Validates a completed migration to ensure all content was properly transferred.

Checks:
1. Directory structure
2. Critical files exist
3. Config is valid
4. Brain entities accessible
5. Path resolution works

Author: PM-OS Team
Version: 3.0.0
"""

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of migration validation."""

    success: bool
    user_path: Path
    common_path: Optional[Path]
    checks_passed: int = 0
    checks_total: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class MigrationValidator:
    """
    Validates a PM-OS v3.0 migration.

    Ensures all components are properly set up and functional.
    """

    # Required directories in user/
    REQUIRED_USER_DIRS = [
        "brain",
        "context",
        "sessions",
    ]

    # Required files in user/
    REQUIRED_USER_FILES = [
        "config.yaml",
    ]

    # Recommended directories
    RECOMMENDED_DIRS = [
        "brain/entities",
        "brain/projects",
        "planning",
    ]

    def __init__(self, user_path: Path, common_path: Optional[Path] = None):
        """
        Initialize the validator.

        Args:
            user_path: Path to user/ directory
            common_path: Path to common/ directory (optional)
        """
        self.user_path = Path(user_path).resolve()
        self.common_path = Path(common_path).resolve() if common_path else None

    def validate(self) -> ValidationResult:
        """
        Run all validation checks.

        Returns:
            ValidationResult with status and any issues
        """
        result = ValidationResult(
            success=True,
            user_path=self.user_path,
            common_path=self.common_path,
        )

        checks = [
            self._check_user_structure,
            self._check_user_files,
            self._check_config_valid,
            self._check_brain_accessible,
            self._check_recommended_dirs,
            self._check_path_resolution,
        ]

        for check_fn in checks:
            result.checks_total += 1
            try:
                passed, message = check_fn()
                if passed:
                    result.checks_passed += 1
                    logger.debug(f"✓ {check_fn.__name__}: {message}")
                else:
                    if "warning" in message.lower():
                        result.warnings.append(message)
                    else:
                        result.errors.append(message)
                        result.success = False
            except Exception as e:
                result.errors.append(f"{check_fn.__name__} failed: {e}")
                result.success = False

        return result

    def _check_user_structure(self) -> tuple:
        """Check required user/ directories exist."""
        missing = []
        for dir_name in self.REQUIRED_USER_DIRS:
            if not (self.user_path / dir_name).is_dir():
                missing.append(dir_name)

        if missing:
            return False, f"Missing directories: {', '.join(missing)}"
        return True, "User directory structure OK"

    def _check_user_files(self) -> tuple:
        """Check required user/ files exist."""
        missing = []
        for file_name in self.REQUIRED_USER_FILES:
            if not (self.user_path / file_name).is_file():
                missing.append(file_name)

        if missing:
            return False, f"Missing files: {', '.join(missing)}"
        return True, "Required files present"

    def _check_config_valid(self) -> tuple:
        """Check config.yaml is valid."""
        config_path = self.user_path / "config.yaml"
        if not config_path.exists():
            return False, "config.yaml not found"

        try:
            import yaml

            with open(config_path) as f:
                config = yaml.safe_load(f)

            if not config:
                return False, "config.yaml is empty"

            if "version" not in config:
                return False, "config.yaml missing version field"

            if not config.get("version", "").startswith("3."):
                return False, f"Invalid config version: {config.get('version')}"

            return True, f"Config valid (v{config.get('version')})"

        except yaml.YAMLError as e:
            return False, f"Invalid YAML: {e}"
        except ImportError:
            # Can't validate without YAML
            return True, "Config exists (YAML validation skipped)"

    def _check_brain_accessible(self) -> tuple:
        """Check Brain directory is accessible and has content."""
        brain_path = self.user_path / "brain"
        if not brain_path.is_dir():
            return False, "Brain directory not found"

        # Count entities
        entity_count = len(list(brain_path.glob("**/*.md")))
        if entity_count == 0:
            return True, "Warning: Brain is empty (no entities migrated)"

        return True, f"Brain accessible ({entity_count} files)"

    def _check_recommended_dirs(self) -> tuple:
        """Check recommended directories exist."""
        missing = []
        for dir_name in self.RECOMMENDED_DIRS:
            if not (self.user_path / dir_name).exists():
                missing.append(dir_name)

        if missing:
            return (
                True,
                f"Warning: Recommended directories missing: {', '.join(missing)}",
            )
        return True, "Recommended directories present"

    def _check_path_resolution(self) -> tuple:
        """Check path resolver can find the installation."""
        try:
            # Add tools to path
            if self.common_path:
                sys.path.insert(0, str(self.common_path / "tools"))

            from path_resolver import get_paths, reset_paths

            # Reset to force re-resolution
            reset_paths()

            # Try to resolve from user directory
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(self.user_path)
                paths = get_paths()

                if paths.user != self.user_path:
                    return False, f"Path resolver found wrong user path: {paths.user}"

                return True, f"Path resolution OK (strategy: {paths.strategy})"

            finally:
                os.chdir(original_cwd)
                reset_paths()

        except ImportError:
            return (
                True,
                "Warning: Could not test path resolution (tools not accessible)",
            )
        except Exception as e:
            return False, f"Path resolution failed: {e}"


def validate_migration(
    user_path: Path,
    common_path: Optional[Path] = None,
) -> ValidationResult:
    """
    Validate a PM-OS migration.

    Args:
        user_path: Path to user/ directory
        common_path: Path to common/ directory

    Returns:
        ValidationResult with status
    """
    validator = MigrationValidator(user_path, common_path)
    return validator.validate()


def print_validation_report(result: ValidationResult) -> None:
    """Print formatted validation report."""
    print("\n" + "=" * 50)
    print("PM-OS Migration Validation Report")
    print("=" * 50)
    print(f"\nUser path: {result.user_path}")
    if result.common_path:
        print(f"Common path: {result.common_path}")

    print(f"\nChecks: {result.checks_passed}/{result.checks_total} passed")

    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"  ✗ {error}")

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  ⚠ {warning}")

    print("\n" + "-" * 50)
    if result.success:
        print("✓ Migration validation passed")
    else:
        print("✗ Migration validation failed")
    print("=" * 50 + "\n")


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PM-OS Migration Validator")
    parser.add_argument("user_path", help="Path to user/ directory")
    parser.add_argument("--common", help="Path to common/ directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    result = validate_migration(
        Path(args.user_path),
        Path(args.common) if args.common else None,
    )

    if args.json:
        import json

        output = {
            "success": result.success,
            "user_path": str(result.user_path),
            "common_path": str(result.common_path) if result.common_path else None,
            "checks_passed": result.checks_passed,
            "checks_total": result.checks_total,
            "errors": result.errors,
            "warnings": result.warnings,
        }
        print(json.dumps(output, indent=2))
    else:
        print_validation_report(result)

    sys.exit(0 if result.success else 1)
