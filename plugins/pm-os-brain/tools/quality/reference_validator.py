#!/usr/bin/env python3
"""
PM-OS Brain Reference Validator (v5)

Validates entity references before writing to ensure canonical format.
Provides pre-write validation hook for relationship integrity.

Features:
- Pre-write validation for relationship targets
- Canonical format enforcement
- Suggestion generation for invalid references
- Auto-normalization mode

Version: 5.0.0
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# v5 config-driven imports
try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        from tools.core.path_resolver import get_paths
    except ImportError:
        get_paths = None

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from tools.core.config_loader import get_config
    except ImportError:
        get_config = None

# Sibling imports -- may not exist yet in v5
try:
    from pm_os_brain.tools.relationships.canonical_resolver import CanonicalResolver
except ImportError:
    try:
        from tools.relationships.canonical_resolver import CanonicalResolver
    except ImportError:
        try:
            from relationships.canonical_resolver import CanonicalResolver
        except ImportError:
            CanonicalResolver = None

logger = logging.getLogger(__name__)


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

    # Default valid entity types (config-overridable)
    DEFAULT_VALID_TYPES = {
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

        # Load config-driven valid types
        self.valid_types = set(self.DEFAULT_VALID_TYPES)
        if get_config is not None:
            try:
                config = get_config()
                brain_cfg = config.get("brain", {})
                if "valid_entity_types" in brain_cfg:
                    self.valid_types = set(brain_cfg["valid_entity_types"])
            except Exception:
                logger.debug("Config not available, using default valid types")

        # Initialize resolver if available
        self.resolver = None
        if CanonicalResolver is not None:
            try:
                self.resolver = CanonicalResolver(brain_path)
            except Exception as e:
                logger.warning("Failed to initialize CanonicalResolver: %s", e)

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
        if self.resolver is not None:
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
        if self.resolver is not None:
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
                canonical = self._resolve(entity_id)
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
        if self.resolver is not None:
            self.resolver.build_index()

        # Check if already canonical
        if self.CANONICAL_PATTERN.match(reference):
            # Verify it resolves
            resolved = self._resolve(reference)
            if resolved:
                return (True, reference, None)
            else:
                return (
                    False,
                    None,
                    f"Canonical reference '{reference}' does not exist",
                )

        # Try to resolve
        canonical = self._resolve(reference)
        if canonical:
            return (True, canonical, None)

        # Try to find similar
        similar = self._find_similar(reference, max_results=1)
        if similar:
            suggestion = similar[0][0]
            return (
                False,
                suggestion,
                f"Could not resolve '{reference}'. Did you mean '{suggestion}'?",
            )

        return (False, None, f"Could not resolve reference '{reference}'")

    def _resolve(self, reference: str) -> Optional[str]:
        """Resolve a reference using the canonical resolver if available."""
        if self.resolver is not None:
            return self.resolver.resolve(reference)
        return None

    def _find_similar(
        self, reference: str, max_results: int = 3
    ) -> List[Tuple[str, float]]:
        """Find similar references using the resolver if available."""
        if self.resolver is not None:
            return self.resolver.find_similar(reference, max_results=max_results)
        return []

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
                if entity_type not in self.valid_types:
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
            canonical = self._resolve(target)
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
            if not self._resolve(target):
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
            canonical = self._resolve(target)
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
            if not self._resolve(target):
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
