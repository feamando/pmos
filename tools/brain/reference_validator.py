#!/usr/bin/env python3
"""
PM-OS Brain Reference Validator

Validates entity references before writing to ensure canonical format.
Provides pre-write validation hook for relationship integrity.
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent))

from canonical_resolver import CanonicalResolver


@dataclass
class ValidationError:
    """Represents a reference validation error."""

    field: str
    value: str
    error_type: str  # invalid_format, unresolvable, non_canonical
    message: str
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of validating an entity."""

    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]
    normalized_data: Optional[Dict[str, Any]] = None


class ReferenceValidator:
    """
    Validates and normalizes entity references.

    Features:
    - Pre-write validation for relationship targets
    - Canonical format enforcement
    - Suggestion generation for invalid references
    - Auto-normalization mode
    """

    # Canonical $id format pattern
    CANONICAL_PATTERN = re.compile(r"^entity/[a-z]+/[a-z0-9-]+$")

    # Valid entity types
    VALID_TYPES = {
        "person",
        "project",
        "team",
        "squad",
        "domain",
        "system",
        "brand",
        "experiment",
        "entity",
        "reasoning",
    }

    def __init__(self, brain_path: Path):
        """
        Initialize the validator.

        Args:
            brain_path: Path to the brain directory
        """
        self.brain_path = brain_path
        self.resolver = CanonicalResolver(brain_path)

    def validate_entity(
        self,
        frontmatter: Dict[str, Any],
        strict: bool = False,
    ) -> ValidationResult:
        """
        Validate an entity's frontmatter.

        Args:
            frontmatter: Entity frontmatter to validate
            strict: If True, non-canonical refs are errors; otherwise warnings

        Returns:
            ValidationResult with errors and warnings
        """
        self.resolver.build_index()

        errors = []
        warnings = []

        # Validate $id
        entity_id = frontmatter.get("$id", "")
        if entity_id:
            id_errors = self._validate_canonical_id(entity_id)
            errors.extend(id_errors)

        # Validate relationships
        relationships = frontmatter.get("$relationships", [])
        for i, rel in enumerate(relationships):
            if isinstance(rel, dict):
                rel_errors, rel_warnings = self._validate_relationship(rel, i, strict)
                errors.extend(rel_errors)
                warnings.extend(rel_warnings)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def validate_and_normalize(
        self,
        frontmatter: Dict[str, Any],
    ) -> ValidationResult:
        """
        Validate and auto-normalize an entity's frontmatter.

        Args:
            frontmatter: Entity frontmatter to validate

        Returns:
            ValidationResult with normalized data
        """
        self.resolver.build_index()

        errors = []
        warnings = []
        normalized = dict(frontmatter)

        # Normalize $id
        entity_id = frontmatter.get("$id", "")
        if entity_id:
            id_errors = self._validate_canonical_id(entity_id)
            if id_errors:
                # Try to normalize
                canonical = self.resolver.resolve(entity_id)
                if canonical:
                    normalized["$id"] = canonical
                    warnings.append(
                        ValidationError(
                            field="$id",
                            value=entity_id,
                            error_type="non_canonical",
                            message=f"Normalized $id from '{entity_id}' to '{canonical}'",
                            suggestion=canonical,
                        )
                    )
                else:
                    errors.extend(id_errors)

        # Normalize relationships
        relationships = frontmatter.get("$relationships", [])
        normalized_rels = []

        for i, rel in enumerate(relationships):
            if isinstance(rel, dict):
                normalized_rel, rel_errors, rel_warnings = self._normalize_relationship(
                    rel, i
                )
                normalized_rels.append(normalized_rel)
                errors.extend(rel_errors)
                warnings.extend(rel_warnings)
            else:
                normalized_rels.append(rel)

        if normalized_rels:
            normalized["$relationships"] = normalized_rels

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_data=normalized if warnings or errors else None,
        )

    def validate_reference(
        self, reference: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate a single reference.

        Args:
            reference: Reference to validate

        Returns:
            Tuple of (is_valid, canonical_form, error_message)
        """
        self.resolver.build_index()

        # Check if already canonical
        if self.CANONICAL_PATTERN.match(reference):
            # Verify it resolves
            if self.resolver.resolve(reference):
                return (True, reference, None)
            else:
                return (
                    False,
                    None,
                    f"Canonical reference '{reference}' does not exist",
                )

        # Try to resolve
        canonical = self.resolver.resolve(reference)
        if canonical:
            return (True, canonical, None)

        # Try to find similar
        similar = self.resolver.find_similar(reference, max_results=1)
        if similar:
            suggestion = similar[0][0]
            return (
                False,
                suggestion,
                f"Could not resolve '{reference}'. Did you mean '{suggestion}'?",
            )

        return (False, None, f"Could not resolve reference '{reference}'")

    def _validate_canonical_id(self, entity_id: str) -> List[ValidationError]:
        """Validate $id format."""
        errors = []

        if not self.CANONICAL_PATTERN.match(entity_id):
            errors.append(
                ValidationError(
                    field="$id",
                    value=entity_id,
                    error_type="invalid_format",
                    message=f"$id '{entity_id}' does not match canonical format 'entity/{{type}}/{{slug}}'",
                )
            )
        else:
            # Check entity type
            parts = entity_id.split("/")
            if len(parts) >= 2:
                entity_type = parts[1]
                if entity_type not in self.VALID_TYPES:
                    errors.append(
                        ValidationError(
                            field="$id",
                            value=entity_id,
                            error_type="invalid_type",
                            message=f"Unknown entity type '{entity_type}' in $id",
                        )
                    )

        return errors

    def _validate_relationship(
        self,
        rel: Dict[str, Any],
        index: int,
        strict: bool,
    ) -> Tuple[List[ValidationError], List[ValidationError]]:
        """Validate a single relationship."""
        errors = []
        warnings = []

        target = rel.get("target", "")
        rel_type = rel.get("type", "")

        if not target:
            errors.append(
                ValidationError(
                    field=f"$relationships[{index}].target",
                    value="",
                    error_type="missing",
                    message="Relationship target is empty",
                )
            )
            return errors, warnings

        if not rel_type:
            warnings.append(
                ValidationError(
                    field=f"$relationships[{index}].type",
                    value="",
                    error_type="missing",
                    message="Relationship type is empty",
                )
            )

        # Check if target is canonical
        if not self.CANONICAL_PATTERN.match(target):
            canonical = self.resolver.resolve(target)
            if canonical:
                issue = ValidationError(
                    field=f"$relationships[{index}].target",
                    value=target,
                    error_type="non_canonical",
                    message=f"Target '{target}' should use canonical format '{canonical}'",
                    suggestion=canonical,
                )
                if strict:
                    errors.append(issue)
                else:
                    warnings.append(issue)
            else:
                errors.append(
                    ValidationError(
                        field=f"$relationships[{index}].target",
                        value=target,
                        error_type="unresolvable",
                        message=f"Cannot resolve target '{target}'",
                    )
                )
        else:
            # Canonical format but verify it exists
            if not self.resolver.resolve(target):
                errors.append(
                    ValidationError(
                        field=f"$relationships[{index}].target",
                        value=target,
                        error_type="orphan",
                        message=f"Target '{target}' does not exist",
                    )
                )

        return errors, warnings

    def _normalize_relationship(
        self,
        rel: Dict[str, Any],
        index: int,
    ) -> Tuple[Dict[str, Any], List[ValidationError], List[ValidationError]]:
        """Normalize a relationship target."""
        errors = []
        warnings = []
        normalized = dict(rel)

        target = rel.get("target", "")

        if not target:
            errors.append(
                ValidationError(
                    field=f"$relationships[{index}].target",
                    value="",
                    error_type="missing",
                    message="Relationship target is empty",
                )
            )
            return normalized, errors, warnings

        # Try to normalize
        if not self.CANONICAL_PATTERN.match(target):
            canonical = self.resolver.resolve(target)
            if canonical:
                normalized["target"] = canonical
                warnings.append(
                    ValidationError(
                        field=f"$relationships[{index}].target",
                        value=target,
                        error_type="non_canonical",
                        message=f"Normalized target from '{target}' to '{canonical}'",
                        suggestion=canonical,
                    )
                )
            else:
                errors.append(
                    ValidationError(
                        field=f"$relationships[{index}].target",
                        value=target,
                        error_type="unresolvable",
                        message=f"Cannot resolve target '{target}'",
                    )
                )
        else:
            # Verify canonical target exists
            if not self.resolver.resolve(target):
                errors.append(
                    ValidationError(
                        field=f"$relationships[{index}].target",
                        value=target,
                        error_type="orphan",
                        message=f"Target '{target}' does not exist",
                    )
                )

        return normalized, errors, warnings

    def generate_report(self, result: ValidationResult) -> str:
        """Generate a human-readable validation report."""
        lines = ["# Reference Validation Report", ""]

        if result.is_valid:
            lines.append("**Status:** VALID")
        else:
            lines.append("**Status:** INVALID")

        lines.append("")

        if result.errors:
            lines.append(f"## Errors ({len(result.errors)})")
            lines.append("")
            for error in result.errors:
                lines.append(f"- **{error.field}**: {error.message}")
                if error.suggestion:
                    lines.append(f"  - Suggestion: `{error.suggestion}`")
            lines.append("")

        if result.warnings:
            lines.append(f"## Warnings ({len(result.warnings)})")
            lines.append("")
            for warning in result.warnings:
                lines.append(f"- **{warning.field}**: {warning.message}")
                if warning.suggestion:
                    lines.append(f"  - Suggestion: `{warning.suggestion}`")
            lines.append("")

        return "\n".join(lines)


def validate_file(
    file_path: Path, validator: ReferenceValidator, strict: bool = False
) -> ValidationResult:
    """Validate a single entity file."""
    if not file_path.exists():
        return ValidationResult(
            is_valid=False,
            errors=[
                ValidationError(
                    field="file",
                    value=str(file_path),
                    error_type="not_found",
                    message=f"File does not exist: {file_path}",
                )
            ],
            warnings=[],
        )

    content = file_path.read_text(encoding="utf-8")

    if not content.startswith("---"):
        return ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[
                ValidationError(
                    field="file",
                    value=str(file_path),
                    error_type="no_frontmatter",
                    message="File has no YAML frontmatter",
                )
            ],
        )

    parts = content.split("---", 2)
    if len(parts) < 3:
        return ValidationResult(is_valid=True, errors=[], warnings=[])

    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as e:
        return ValidationResult(
            is_valid=False,
            errors=[
                ValidationError(
                    field="frontmatter",
                    value="",
                    error_type="parse_error",
                    message=f"YAML parse error: {e}",
                )
            ],
            warnings=[],
        )

    return validator.validate_entity(frontmatter, strict)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate Brain entity references")
    parser.add_argument(
        "action",
        choices=["validate", "normalize", "check"],
        help="Action to perform",
    )
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Specific file to validate",
    )
    parser.add_argument(
        "--reference",
        "-r",
        help="Single reference to check",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat non-canonical references as errors",
    )

    args = parser.parse_args()

    # Default brain path
    if not args.brain_path:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from path_resolver import get_paths

        paths = get_paths()
        args.brain_path = paths.user / "brain"

    validator = ReferenceValidator(args.brain_path)

    if args.action == "check" and args.reference:
        is_valid, canonical, error = validator.validate_reference(args.reference)
        if is_valid:
            print(f"VALID: '{args.reference}' -> '{canonical}'")
        else:
            print(f"INVALID: {error}")
        return 0 if is_valid else 1

    elif args.action == "validate":
        if args.file:
            result = validate_file(args.file, validator, args.strict)
            print(validator.generate_report(result))
            return 0 if result.is_valid else 1
        else:
            # Validate all entities
            entity_files = list(args.brain_path.rglob("*.md"))
            entity_files = [
                f
                for f in entity_files
                if f.name.lower() not in ("readme.md", "index.md", "_index.md")
                and ".snapshots" not in str(f)
                and ".schema" not in str(f)
            ]

            total_errors = 0
            total_warnings = 0
            invalid_files = []

            for entity_path in entity_files:
                result = validate_file(entity_path, validator, args.strict)
                if not result.is_valid:
                    invalid_files.append(str(entity_path))
                total_errors += len(result.errors)
                total_warnings += len(result.warnings)

            print(f"Validated {len(entity_files)} files")
            print(f"Total errors: {total_errors}")
            print(f"Total warnings: {total_warnings}")
            print(f"Invalid files: {len(invalid_files)}")

            if invalid_files:
                print("\nInvalid files:")
                for f in invalid_files[:20]:
                    print(f"  - {f}")
                if len(invalid_files) > 20:
                    print(f"  ... and {len(invalid_files) - 20} more")

            return 0 if total_errors == 0 else 1

    elif args.action == "normalize":
        if not args.file:
            print("Error: --file required for normalize action")
            return 1

        result = validate_file(args.file, validator, strict=False)

        if result.normalized_data:
            print("Normalized frontmatter:")
            print(yaml.dump(result.normalized_data, default_flow_style=False))
        else:
            print("No normalization needed")

        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
