#!/usr/bin/env python3
"""
PM-OS Brain Entity Validator

Validates Brain entities against v1 and v2 schemas.

Features:
- Validate both v1 and v2 entity formats
- Report validation errors with details
- Dry-run mode for migration preview
- Batch validation of entire brain
"""

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Add common to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class SchemaVersion(str, Enum):
    """Entity schema version."""

    V1 = "v1"
    V2 = "v2"
    UNKNOWN = "unknown"


@dataclass
class ValidationError:
    """A single validation error."""

    field: str
    message: str
    severity: str = "error"  # error, warning, info


@dataclass
class ValidationResult:
    """Result of validating an entity."""

    filepath: Path
    schema_version: SchemaVersion
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


class EntityValidator:
    """Validates Brain entities against schemas."""

    # Required fields for v2 entities
    V2_REQUIRED_FIELDS = [
        "$schema",
        "$id",
        "$type",
        "$version",
        "$created",
        "$updated",
        "name",
    ]

    # Valid entity types
    VALID_TYPES = [
        "person",
        "team",
        "squad",
        "project",
        "domain",
        "experiment",
        "system",
        "brand",
    ]

    def __init__(self, brain_path: Optional[Path] = None):
        """
        Initialize the validator.

        Args:
            brain_path: Path to the brain directory
        """
        self.brain_path = brain_path

    def validate_file(self, filepath: Path) -> ValidationResult:
        """
        Validate a single entity file.

        Args:
            filepath: Path to the entity file

        Returns:
            ValidationResult with errors and warnings
        """
        try:
            content = filepath.read_text(encoding="utf-8")
        except Exception as e:
            return ValidationResult(
                filepath=filepath,
                schema_version=SchemaVersion.UNKNOWN,
                is_valid=False,
                errors=[ValidationError("file", f"Cannot read file: {e}")],
            )

        # Detect schema version
        version = self._detect_schema_version(content)

        # Parse frontmatter
        frontmatter, body = self._parse_frontmatter(content)

        if version == SchemaVersion.V2:
            return self._validate_v2(filepath, frontmatter, body)
        elif version == SchemaVersion.V1:
            return self._validate_v1(filepath, frontmatter, body)
        else:
            return ValidationResult(
                filepath=filepath,
                schema_version=SchemaVersion.UNKNOWN,
                is_valid=False,
                errors=[ValidationError("frontmatter", "No valid frontmatter found")],
            )

    def validate_all(self) -> List[ValidationResult]:
        """
        Validate all entities in the brain.

        Returns:
            List of ValidationResults
        """
        if not self.brain_path:
            raise ValueError("brain_path not set")

        results = []

        # Validate entities
        entities_path = self.brain_path / "Entities"
        if entities_path.exists():
            for filepath in entities_path.rglob("*.md"):
                if filepath.name.lower() not in ("readme.md", "index.md"):
                    results.append(self.validate_file(filepath))

        # Validate projects
        projects_path = self.brain_path / "Projects"
        if projects_path.exists():
            for filepath in projects_path.rglob("*.md"):
                if filepath.name.lower() not in ("readme.md", "index.md"):
                    results.append(self.validate_file(filepath))

        return results

    def _detect_schema_version(self, content: str) -> SchemaVersion:
        """Detect the schema version from content."""
        if "$schema" in content and "$id" in content:
            return SchemaVersion.V2
        elif content.startswith("---"):
            return SchemaVersion.V1
        return SchemaVersion.UNKNOWN

    def _parse_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter from content."""
        if not content.startswith("---"):
            return {}, content

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content

        try:
            frontmatter = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            frontmatter = {}

        body = parts[2].strip()
        return frontmatter, body

    def _validate_v2(
        self, filepath: Path, frontmatter: Dict[str, Any], body: str
    ) -> ValidationResult:
        """Validate a v2 entity."""
        errors = []
        warnings = []

        # Check required fields
        for field_name in self.V2_REQUIRED_FIELDS:
            if field_name not in frontmatter:
                errors.append(
                    ValidationError(
                        field=field_name,
                        message=f"Required field '{field_name}' is missing",
                    )
                )

        # Validate $type
        entity_type = frontmatter.get("$type")
        if entity_type and entity_type not in self.VALID_TYPES:
            errors.append(
                ValidationError(
                    field="$type",
                    message=f"Invalid entity type: {entity_type}",
                )
            )

        # Validate $version
        version = frontmatter.get("$version")
        if version is not None and not isinstance(version, int):
            errors.append(
                ValidationError(
                    field="$version",
                    message=f"$version must be an integer, got {type(version).__name__}",
                )
            )

        # Validate $confidence
        confidence = frontmatter.get("$confidence")
        if confidence is not None:
            if not isinstance(confidence, (int, float)):
                errors.append(
                    ValidationError(
                        field="$confidence",
                        message=f"$confidence must be a number, got {type(confidence).__name__}",
                    )
                )
            elif not 0 <= confidence <= 1:
                errors.append(
                    ValidationError(
                        field="$confidence",
                        message=f"$confidence must be between 0 and 1, got {confidence}",
                    )
                )

        # Validate $relationships
        relationships = frontmatter.get("$relationships", [])
        if not isinstance(relationships, list):
            errors.append(
                ValidationError(
                    field="$relationships",
                    message="$relationships must be a list",
                )
            )
        else:
            for i, rel in enumerate(relationships):
                if not isinstance(rel, dict):
                    errors.append(
                        ValidationError(
                            field=f"$relationships[{i}]",
                            message="Each relationship must be an object",
                        )
                    )
                elif "type" not in rel or "target" not in rel:
                    errors.append(
                        ValidationError(
                            field=f"$relationships[{i}]",
                            message="Relationship must have 'type' and 'target'",
                        )
                    )

        # Validate $events
        events = frontmatter.get("$events", [])
        if not isinstance(events, list):
            errors.append(
                ValidationError(
                    field="$events",
                    message="$events must be a list",
                )
            )

        # Validate timestamps
        for ts_field in ["$created", "$updated"]:
            ts_value = frontmatter.get(ts_field)
            if ts_value:
                if not self._is_valid_timestamp(ts_value):
                    errors.append(
                        ValidationError(
                            field=ts_field,
                            message=f"Invalid timestamp format: {ts_value}",
                        )
                    )

        # Warnings for quality
        if not frontmatter.get("description"):
            warnings.append(
                ValidationError(
                    field="description",
                    message="Entity has no description",
                    severity="warning",
                )
            )

        if not frontmatter.get("$tags"):
            warnings.append(
                ValidationError(
                    field="$tags",
                    message="Entity has no tags",
                    severity="warning",
                )
            )

        if not body.strip():
            warnings.append(
                ValidationError(
                    field="body",
                    message="Entity has no body content",
                    severity="warning",
                )
            )

        return ValidationResult(
            filepath=filepath,
            schema_version=SchemaVersion.V2,
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            entity_type=entity_type,
            entity_id=frontmatter.get("$id"),
        )

    def _validate_v1(
        self, filepath: Path, frontmatter: Dict[str, Any], body: str
    ) -> ValidationResult:
        """Validate a v1 entity (legacy format)."""
        errors = []
        warnings = []

        # V1 should have at least some frontmatter
        if not frontmatter:
            errors.append(
                ValidationError(
                    field="frontmatter",
                    message="Entity has no frontmatter",
                )
            )

        # Check for common v1 fields
        if not frontmatter.get("type") and not frontmatter.get("name"):
            warnings.append(
                ValidationError(
                    field="type",
                    message="Entity missing 'type' or 'name' field",
                    severity="warning",
                )
            )

        # Warning about migration
        warnings.append(
            ValidationError(
                field="$schema",
                message="Entity is v1 format - consider migration to v2",
                severity="info",
            )
        )

        return ValidationResult(
            filepath=filepath,
            schema_version=SchemaVersion.V1,
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            entity_type=frontmatter.get("type"),
            entity_id=None,
        )

    def _is_valid_timestamp(self, value: Any) -> bool:
        """Check if value is a valid timestamp."""
        if isinstance(value, datetime):
            return True
        if isinstance(value, str):
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
                return True
            except ValueError:
                return False
        return False


def validate_entity(filepath: Path) -> ValidationResult:
    """Convenience function to validate a single entity."""
    validator = EntityValidator()
    return validator.validate_file(filepath)


def validate_all_entities(brain_path: Path) -> List[ValidationResult]:
    """Convenience function to validate all entities."""
    validator = EntityValidator(brain_path)
    return validator.validate_all()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate Brain entities against schemas"
    )
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        help="Path to entity file or brain directory",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all entities in brain",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show summary only",
    )
    parser.add_argument(
        "--errors-only",
        action="store_true",
        help="Show only errors, not warnings",
    )

    args = parser.parse_args()

    # Determine path
    if args.path:
        target_path = args.path
    else:
        from path_resolver import get_paths

        paths = get_paths()
        target_path = paths.user / "brain"

    # Validate
    if target_path.is_file():
        results = [validate_entity(target_path)]
    else:
        results = validate_all_entities(target_path)

    # Summarize
    total = len(results)
    valid = sum(1 for r in results if r.is_valid)
    v1_count = sum(1 for r in results if r.schema_version == SchemaVersion.V1)
    v2_count = sum(1 for r in results if r.schema_version == SchemaVersion.V2)
    error_count = sum(r.error_count for r in results)
    warning_count = sum(r.warning_count for r in results)

    if args.summary:
        print(f"Validation Summary:")
        print(f"  Total entities: {total}")
        print(f"  Valid: {valid}")
        print(f"  Invalid: {total - valid}")
        print(f"  V1 format: {v1_count}")
        print(f"  V2 format: {v2_count}")
        print(f"  Total errors: {error_count}")
        print(f"  Total warnings: {warning_count}")
    else:
        # Show details
        for result in results:
            if not result.is_valid or (not args.errors_only and result.warnings):
                print(f"\n{result.filepath}")
                print(f"  Version: {result.schema_version.value}")
                print(f"  Valid: {result.is_valid}")

                for error in result.errors:
                    print(f"  ERROR [{error.field}]: {error.message}")

                if not args.errors_only:
                    for warning in result.warnings:
                        print(f"  WARN [{warning.field}]: {warning.message}")

    return 0 if valid == total else 1


if __name__ == "__main__":
    sys.exit(main())
