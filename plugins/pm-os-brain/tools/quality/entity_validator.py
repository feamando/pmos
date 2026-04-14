#!/usr/bin/env python3
"""
PM-OS Brain Entity Validator (v5)

Validates Brain entities against v1 and v2 schemas.
Wraps Base entity_validator and adds Brain-specific checks:
- Schema version detection (v1 vs v2)
- Type mismatch detection via directory and body patterns
- Auto-fix types with event logging

Features:
- Validate both v1 and v2 entity formats
- Report validation errors with details
- Dry-run mode for migration preview
- Batch validation of entire brain
- Type mismatch detection and auto-correction

Version: 5.0.0
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
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

# Re-export Base entity_validator for consumers that just need basic validation
try:
    from pm_os_base.tools.core.entity_validator import (
        EntityValidator as BaseEntityValidator,
        ValidationResult as BaseValidationResult,
        BatchValidationResult,
        EntityType,
        validate_entity as base_validate_entity,
        validate_all_entities as base_validate_all_entities,
    )
except ImportError:
    try:
        from tools.core.entity_validator import (
            EntityValidator as BaseEntityValidator,
            ValidationResult as BaseValidationResult,
            BatchValidationResult,
            EntityType,
            validate_entity as base_validate_entity,
            validate_all_entities as base_validate_all_entities,
        )
    except ImportError:
        BaseEntityValidator = None
        BaseValidationResult = None
        BatchValidationResult = None
        EntityType = None
        base_validate_entity = None
        base_validate_all_entities = None

# Sibling imports — may not exist yet in v5
try:
    from pm_os_brain.tools.brain_core.safe_write import atomic_write
except ImportError:
    try:
        from tools.core.safe_write import atomic_write
    except ImportError:
        atomic_write = None

try:
    from pm_os_brain.tools.brain_core.event_helpers import EventHelper
except ImportError:
    try:
        from tools.core.event_helpers import EventHelper
    except ImportError:
        EventHelper = None

logger = logging.getLogger(__name__)


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


class BrainEntityValidator:
    """
    Validates Brain entities against schemas.

    Extends Base EntityValidator with Brain-specific checks:
    - v1/v2 schema detection and validation
    - Type mismatch detection from directory structure and body content
    - Auto-fix for type mismatches with event logging
    """

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

    # Valid entity types (config-overridable)
    DEFAULT_VALID_TYPES = [
        "person",
        "team",
        "squad",
        "project",
        "domain",
        "experiment",
        "system",
        "brand",
        "decision",
        "feature",
        "component",
        "framework",
        "company",
        "research",
        "unknown",
    ]

    # Default directory-to-type mapping (config-overridable)
    DEFAULT_DIRECTORY_TYPE_MAP = {
        "People": "person",
        "Teams": "team",
        "Squads": "squad",
        "Projects": "project",
        "Domains": "domain",
        "Experiments": "experiment",
        "Systems": "system",
        "Brands": "brand",
        "Features": "feature",
        "Companies": "company",
    }

    # Patterns for inferring type from body content (used for root Entities/ files)
    _BODY_TYPE_PATTERNS = {
        "person": [
            r"(?m)^-\s*\*\*Type\*\*:\s*Person",
            r"(?m)^type:\s*person\s*$",
            r"(?m)^-\s*\*\*Reports\s+to\*\*:",
            r"(?m)^-\s*\*\*Title\*\*:\s*(?:Product Manager|Engineering|PM |VP |Director|Designer|Data |Staff |Principal |Lead |Manager|Head of|Senior |Tech Lead)",
        ],
        "project": [
            r"(?m)^-\s*\*\*Type\*\*:\s*[Pp]roject",
            r"(?m)^type:\s*project\s*$",
        ],
        "system": [
            r"(?m)^-\s*\*\*Type\*\*:\s*[Ss]ystem",
            r"(?m)^type:\s*system\s*$",
        ],
        "squad": [
            r"(?m)^-\s*\*\*Type\*\*:\s*[Ss]quad",
            r"(?m)^type:\s*squad\s*$",
        ],
        "brand": [
            r"(?m)^-\s*\*\*Type\*\*:\s*[Bb]rand",
            r"(?m)^type:\s*brand\s*$",
        ],
        "experiment": [
            r"(?m)^-\s*\*\*Type\*\*:\s*[Ee]xperiment",
            r"(?m)^type:\s*experiment\s*$",
        ],
        "decision": [
            r"(?m)^-\s*\*\*Type\*\*:\s*[Dd]ecision",
            r"(?m)^type:\s*decision\s*$",
        ],
        "team": [
            r"(?m)^-\s*\*\*Type\*\*:\s*[Tt]eam",
            r"(?m)^type:\s*team\s*$",
        ],
    }

    def __init__(self, brain_path: Optional[Path] = None):
        """
        Initialize the validator.

        Args:
            brain_path: Path to the brain directory
        """
        self.brain_path = brain_path

        # Load config-driven values
        self.valid_types = list(self.DEFAULT_VALID_TYPES)
        self.directory_type_map = dict(self.DEFAULT_DIRECTORY_TYPE_MAP)

        if get_config is not None:
            try:
                config = get_config()
                brain_cfg = config.get("brain", {})
                if "valid_entity_types" in brain_cfg:
                    self.valid_types = brain_cfg["valid_entity_types"]
                if "directory_type_map" in brain_cfg:
                    self.directory_type_map = brain_cfg["directory_type_map"]
            except Exception:
                logger.debug("Config not available, using defaults")

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

    def detect_type_mismatches(self) -> List[Tuple[str, str, str, Path]]:
        """
        Detect entities where $type doesn't match the directory or body content.

        Two-pass detection:
        1. Path-based: Compares $type against type inferred from directory
        2. Body-based: For root Entities/ files where path gives no signal,
           checks body content and legacy frontmatter for type hints

        Returns:
            List of (entity_id, declared_type, inferred_type, file_path) tuples
        """
        if not self.brain_path:
            raise ValueError("brain_path not set")

        mismatches = []

        # Scan all entity directories
        for scan_dir in [self.brain_path / "Entities", self.brain_path / "Projects"]:
            if not scan_dir.exists():
                continue
            for filepath in scan_dir.rglob("*.md"):
                if filepath.name.lower() in ("readme.md", "index.md", "_index.md"):
                    continue

                try:
                    content = filepath.read_text(encoding="utf-8")
                except Exception:
                    continue

                frontmatter, body = self._parse_frontmatter(content)
                declared_type = frontmatter.get("$type")
                if not declared_type:
                    # v1 entities or entities without $type -- skip
                    continue

                # Pass 1: Infer type from directory path
                inferred_type = self._infer_type_from_path(filepath)

                # Pass 2: If path gives no signal, try body content
                if not inferred_type:
                    inferred_type = self._infer_type_from_body(body, frontmatter)

                if inferred_type and declared_type != inferred_type:
                    entity_id = frontmatter.get("$id", "unknown")
                    mismatches.append(
                        (entity_id, declared_type, inferred_type, filepath)
                    )

        return mismatches

    def auto_fix_types(
        self,
        mismatches: List[Tuple[str, str, str, Path]],
        dry_run: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Fix type mismatches by updating $type, $schema, and $id fields.

        Args:
            mismatches: List from detect_type_mismatches()
            dry_run: If True, report changes without applying them

        Returns:
            List of dicts describing each fix applied (or that would be applied)
        """
        fixes = []

        for entity_id, declared_type, inferred_type, filepath in mismatches:
            try:
                content = filepath.read_text(encoding="utf-8")
                frontmatter, body = self._parse_frontmatter(content)

                old_schema = frontmatter.get("$schema", "")
                old_id = frontmatter.get("$id", "")

                # Update $type
                frontmatter["$type"] = inferred_type

                # Update $schema URI: brain://entity/{type}/v1
                frontmatter["$schema"] = f"brain://entity/{inferred_type}/v1"

                # Update $id prefix: entity/{type}/{slug}
                if old_id:
                    # Extract slug from old ID
                    parts = old_id.split("/")
                    slug = parts[-1] if len(parts) >= 3 else parts[-1]
                    frontmatter["$id"] = f"entity/{inferred_type}/{slug}"

                # Add event if EventHelper is available
                if EventHelper is not None:
                    event = EventHelper.create_event(
                        event_type="field_update",
                        actor="system/entity_validator",
                        changes=[
                            {
                                "field": "$type",
                                "operation": "set",
                                "value": inferred_type,
                                "old_value": declared_type,
                            },
                            {
                                "field": "$schema",
                                "operation": "set",
                                "value": frontmatter["$schema"],
                                "old_value": old_schema,
                            },
                            {
                                "field": "$id",
                                "operation": "set",
                                "value": frontmatter.get("$id", ""),
                                "old_value": old_id,
                            },
                        ],
                        message=f"Type corrected from {declared_type} to {inferred_type}",
                    )
                    EventHelper.append_to_frontmatter(frontmatter, event)

                fix_record = {
                    "filepath": str(filepath),
                    "old_type": declared_type,
                    "new_type": inferred_type,
                    "old_id": old_id,
                    "new_id": frontmatter.get("$id", ""),
                    "dry_run": dry_run,
                }
                fixes.append(fix_record)

                if not dry_run:
                    # Rewrite entity file
                    fm_str = yaml.dump(
                        frontmatter,
                        default_flow_style=False,
                        allow_unicode=True,
                        sort_keys=False,
                    )
                    new_content = f"---\n{fm_str}---\n\n{body}"

                    if atomic_write is not None:
                        atomic_write(filepath, new_content)
                    else:
                        filepath.write_text(new_content, encoding="utf-8")

            except Exception as e:
                logger.warning("Failed to fix %s: %s", filepath, e)
                fixes.append(
                    {
                        "filepath": str(filepath),
                        "error": str(e),
                        "dry_run": dry_run,
                    }
                )

        return fixes

    def _infer_type_from_path(self, filepath: Path) -> Optional[str]:
        """
        Infer entity type from file path using directory_type_map.

        Returns:
            Inferred type string, or None if no directory match found
        """
        parts = filepath.parts
        for part in parts:
            if part in self.directory_type_map:
                return self.directory_type_map[part]
        return None

    def _infer_type_from_body(
        self, body: str, frontmatter: Dict[str, Any]
    ) -> Optional[str]:
        """
        Infer entity type from body content patterns.

        Used as fallback when _infer_type_from_path returns None (root Entities/ files).
        Checks for explicit type declarations and strong type indicators in the body.

        Returns:
            Inferred type string, or None if no confident match
        """
        # Also check for a nested 'type' key from legacy migration
        if "type" in frontmatter and isinstance(frontmatter["type"], str):
            legacy_type = frontmatter["type"].lower().strip()
            if legacy_type in self.valid_types:
                return legacy_type

        full_text = body
        for candidate_type, patterns in self._BODY_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, full_text):
                    return candidate_type

        return None

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
        if entity_type and entity_type not in self.valid_types:
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


# Convenience functions
def validate_entity(filepath: Path) -> ValidationResult:
    """Convenience function to validate a single entity."""
    validator = BrainEntityValidator()
    return validator.validate_file(filepath)


def validate_all_entities(brain_path: Path) -> List[ValidationResult]:
    """Convenience function to validate all entities."""
    validator = BrainEntityValidator(brain_path)
    return validator.validate_all()
