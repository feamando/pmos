#!/usr/bin/env python3
"""
PM-OS Entity Validator

Validates Brain entity files against their type schemas.
Provides both strict validation and permissive mode for migration.

Usage:
    from entity_validator import validate_entity, validate_all_entities

    # Validate single entity
    result = validate_entity(Path("entities/Deo_Nathaniel.md"))
    if result.valid:
        print("Valid!")
    else:
        print(f"Errors: {result.errors}")

    # Validate all entities
    results = validate_all_entities(Path("brain/entities"))

Version: 5.0.0
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Optional imports
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    logger.warning("PyYAML not installed. Install with: pip install pyyaml")

try:
    import jsonschema

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    logger.debug("jsonschema not installed. Schema validation disabled.")


class EntityType(Enum):
    """Supported entity types."""

    PERSON = "person"
    TEAM = "team"
    SQUAD = "squad"
    PROJECT = "project"
    DOMAIN = "domain"
    EXPERIMENT = "experiment"
    SYSTEM = "system"
    BRAND = "brand"
    FRAMEWORK = "framework"
    COMPONENT = "component"
    UNKNOWN = "unknown"


@dataclass
class ValidationResult:
    """Result of entity validation."""

    valid: bool
    entity_path: Path
    entity_type: Optional[EntityType] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    frontmatter: Optional[Dict[str, Any]] = None

    def __bool__(self) -> bool:
        return self.valid


@dataclass
class BatchValidationResult:
    """Result of batch entity validation."""

    total: int
    valid: int
    invalid: int
    warnings: int
    results: List[ValidationResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 100.0
        return (self.valid / self.total) * 100


class EntityValidator:
    """
    Validates Brain entity files against schemas.

    Entity files are Markdown with YAML frontmatter:
    ```
    ---
    type: person
    name: Deo Nathaniel
    role: PM
    ---

    # Deo Nathaniel
    ...
    ```
    """

    # YAML frontmatter pattern
    FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

    # Required fields for all entities
    BASE_REQUIRED = ["type", "name"]

    # Type-specific required fields (beyond base)
    TYPE_REQUIRED: Dict[EntityType, List[str]] = {
        EntityType.PERSON: [],
        EntityType.TEAM: [],
        EntityType.SQUAD: [],
        EntityType.PROJECT: [],
        EntityType.DOMAIN: [],
        EntityType.EXPERIMENT: [],
        EntityType.SYSTEM: [],
        EntityType.BRAND: [],
        EntityType.FRAMEWORK: [],
        EntityType.COMPONENT: [],
    }

    # Type-specific recommended fields
    TYPE_RECOMMENDED: Dict[EntityType, List[str]] = {
        EntityType.PERSON: ["role", "email"],
        EntityType.TEAM: ["team_type", "parent"],
        EntityType.SQUAD: ["tribe", "tech_lead"],
        EntityType.PROJECT: ["status", "owner"],
        EntityType.DOMAIN: ["domain_type"],
        EntityType.EXPERIMENT: ["status", "hypothesis"],
        EntityType.SYSTEM: ["owner", "tech_stack"],
        EntityType.BRAND: ["market", "status"],
        EntityType.FRAMEWORK: ["author", "category", "use_case"],
        EntityType.COMPONENT: ["platform", "figma_name", "code_name"],
    }

    def __init__(self, schemas_dir: Optional[Path] = None, strict: bool = False):
        """
        Initialize the validator.

        Args:
            schemas_dir: Directory containing schema files. If None, uses built-in validation.
            strict: If True, treat warnings as errors.
        """
        self.schemas_dir = schemas_dir
        self.strict = strict
        self.schemas: Dict[str, Dict] = {}

        if schemas_dir and YAML_AVAILABLE:
            self._load_schemas()

    def _load_schemas(self) -> None:
        """Load schema files from schemas directory."""
        if not self.schemas_dir or not self.schemas_dir.exists():
            return

        for schema_file in self.schemas_dir.glob("*.schema.yaml"):
            try:
                with open(schema_file, "r", encoding="utf-8") as f:
                    schema = yaml.safe_load(f)
                    if schema:
                        type_name = schema_file.stem.replace(".schema", "")
                        self.schemas[type_name] = schema
                        logger.debug("Loaded schema: %s", type_name)
            except Exception as e:
                logger.warning("Failed to load schema %s: %s", schema_file, e)

    def parse_frontmatter(self, content: str) -> Tuple[Optional[Dict], str]:
        """
        Parse YAML frontmatter from markdown content.

        Returns:
            Tuple of (frontmatter dict, remaining content)
        """
        if not YAML_AVAILABLE:
            return None, content

        match = self.FRONTMATTER_PATTERN.match(content)
        if not match:
            return None, content

        try:
            frontmatter = yaml.safe_load(match.group(1))
            remaining = content[match.end():]
            return frontmatter, remaining
        except yaml.YAMLError as e:
            logger.debug("Failed to parse frontmatter: %s", e)
            return None, content

    def infer_type_from_path(self, entity_path: Path) -> EntityType:
        """Infer entity type from file path."""
        path_str = str(entity_path).lower()

        if "/squads/" in path_str:
            return EntityType.SQUAD
        elif "squad_" in path_str or "/teams/" in path_str:
            return EntityType.TEAM
        elif "/projects/" in path_str:
            return EntityType.PROJECT
        elif "/experiments/" in path_str:
            return EntityType.EXPERIMENT
        elif "domain_" in path_str or "/domains/" in path_str:
            return EntityType.DOMAIN
        elif "/systems/" in path_str:
            return EntityType.SYSTEM
        elif "/brands/" in path_str:
            return EntityType.BRAND
        elif "/frameworks/" in path_str:
            return EntityType.FRAMEWORK
        elif "/components/" in path_str:
            return EntityType.COMPONENT
        elif "/entities/" in path_str:
            return EntityType.PERSON

        return EntityType.UNKNOWN

    def validate_entity(self, entity_path: Path) -> ValidationResult:
        """Validate a single entity file."""
        result = ValidationResult(
            valid=True, entity_path=entity_path, errors=[], warnings=[]
        )

        if not entity_path.exists():
            result.valid = False
            result.errors.append(f"File not found: {entity_path}")
            return result

        try:
            content = entity_path.read_text(encoding="utf-8")
        except Exception as e:
            result.valid = False
            result.errors.append(f"Cannot read file: {e}")
            return result

        frontmatter, body = self.parse_frontmatter(content)
        result.frontmatter = frontmatter

        if frontmatter is None:
            result.warnings.append("No YAML frontmatter found")
            result.entity_type = self.infer_type_from_path(entity_path)

            if self.strict:
                result.valid = False
                result.errors.append("Missing frontmatter (strict mode)")
            return result

        # Check required base fields (support both v1 "type" and v2 "$type")
        for fld in self.BASE_REQUIRED:
            v2_field = f"${fld}"
            if fld not in frontmatter and v2_field not in frontmatter:
                result.errors.append(f"Missing required field: {fld} (or {v2_field})")
                result.valid = False

        # Determine type (support both v1 "type" and v2 "$type")
        type_str = frontmatter.get("type", frontmatter.get("$type", "")).lower()
        try:
            result.entity_type = EntityType(type_str)
        except ValueError:
            result.entity_type = EntityType.UNKNOWN
            result.warnings.append(f"Unknown entity type: {type_str}")

        # Check type-specific required fields
        if result.entity_type in self.TYPE_REQUIRED:
            for fld in self.TYPE_REQUIRED[result.entity_type]:
                if fld not in frontmatter:
                    result.errors.append(
                        f"Missing required field for {result.entity_type.value}: {fld}"
                    )
                    result.valid = False

        # Check type-specific recommended fields (warnings only)
        if result.entity_type in self.TYPE_RECOMMENDED:
            for fld in self.TYPE_RECOMMENDED[result.entity_type]:
                if fld not in frontmatter:
                    result.warnings.append(f"Recommended field missing: {fld}")

        # JSON Schema validation (if available and schema exists)
        if JSONSCHEMA_AVAILABLE and type_str in self.schemas:
            schema = self.schemas[type_str]
            try:
                jsonschema.validate(frontmatter, schema)
            except jsonschema.ValidationError as e:
                result.warnings.append(f"Schema validation: {e.message}")
                if self.strict:
                    result.valid = False
                    result.errors.append(f"Schema validation failed: {e.message}")

        # In strict mode, warnings become errors
        if self.strict and result.warnings:
            result.valid = False
            result.errors.extend(result.warnings)

        return result

    def validate_directory(
        self, directory: Path, recursive: bool = True
    ) -> BatchValidationResult:
        """Validate all entity files in a directory."""
        batch_result = BatchValidationResult(
            total=0, valid=0, invalid=0, warnings=0, results=[]
        )

        if not directory.exists():
            logger.warning("Directory not found: %s", directory)
            return batch_result

        pattern = "**/*.md" if recursive else "*.md"
        entity_files = list(directory.glob(pattern))

        for entity_path in entity_files:
            if entity_path.name.lower() in ["readme.md", "index.md"]:
                continue

            result = self.validate_entity(entity_path)
            batch_result.results.append(result)
            batch_result.total += 1

            if result.valid:
                batch_result.valid += 1
                if result.warnings:
                    batch_result.warnings += 1
            else:
                batch_result.invalid += 1

        return batch_result

    def fix_entity(self, entity_path: Path, dry_run: bool = True) -> Tuple[bool, str]:
        """Attempt to fix an entity by adding missing frontmatter."""
        if not YAML_AVAILABLE:
            return False, "PyYAML required for fixing entities"

        content = entity_path.read_text(encoding="utf-8")
        frontmatter, body = self.parse_frontmatter(content)

        if frontmatter is not None:
            if "type" not in frontmatter:
                inferred_type = self.infer_type_from_path(entity_path)
                frontmatter["type"] = inferred_type.value

                if not dry_run:
                    self._write_entity(entity_path, frontmatter, body)
                return True, f"Added type: {inferred_type.value}"
            return True, "Entity already has valid frontmatter"

        inferred_type = self.infer_type_from_path(entity_path)
        name = entity_path.stem.replace("_", " ")

        frontmatter = {"type": inferred_type.value, "name": name}

        if not dry_run:
            self._write_entity(entity_path, frontmatter, content)

        return True, f"Added frontmatter: type={inferred_type.value}, name={name}"

    def _write_entity(self, entity_path: Path, frontmatter: Dict, body: str) -> None:
        """Write entity with frontmatter to file."""
        content = "---\n"
        content += yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
        content += "---\n\n"
        content += body.lstrip()

        entity_path.write_text(content, encoding="utf-8")


# Convenience functions
def validate_entity(entity_path: Path, strict: bool = False) -> ValidationResult:
    """Validate a single entity file."""
    validator = EntityValidator(strict=strict)
    return validator.validate_entity(entity_path)


def validate_all_entities(
    directory: Path, strict: bool = False
) -> BatchValidationResult:
    """Validate all entities in a directory."""
    validator = EntityValidator(strict=strict)
    return validator.validate_directory(directory)


def fix_entity(entity_path: Path, dry_run: bool = True) -> Tuple[bool, str]:
    """Fix entity by adding missing frontmatter."""
    validator = EntityValidator()
    return validator.fix_entity(entity_path, dry_run)


# CLI interface
if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="PM-OS Entity Validator")
    parser.add_argument("path", nargs="?", help="Entity file or directory to validate")
    parser.add_argument(
        "--strict", action="store_true", help="Treat warnings as errors"
    )
    parser.add_argument(
        "--fix", action="store_true", help="Attempt to fix invalid entities"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show fixes without applying"
    )
    parser.add_argument("--quiet", action="store_true", help="Only show errors")
    parser.add_argument("--summary", action="store_true", help="Show summary only")

    args = parser.parse_args()

    if not args.path:
        parser.print_help()
        sys.exit(0)

    path = Path(args.path)
    validator = EntityValidator(strict=args.strict)

    if path.is_file():
        if args.fix:
            success, message = validator.fix_entity(path, dry_run=args.dry_run)
            print(f"{path}: {message}")
            sys.exit(0 if success else 1)

        result = validator.validate_entity(path)
        if result.valid:
            if not args.quiet:
                print(f"PASS {path}")
                if result.warnings:
                    for warning in result.warnings:
                        print(f"  WARN {warning}")
        else:
            print(f"FAIL {path}")
            for error in result.errors:
                print(f"  FAIL {error}")
            sys.exit(1)

    elif path.is_dir():
        batch_result = validator.validate_directory(path)

        if args.summary:
            print(f"\nValidation Summary for {path}")
            print(f"  Total:    {batch_result.total}")
            print(f"  Valid:    {batch_result.valid}")
            print(f"  Invalid:  {batch_result.invalid}")
            print(f"  Warnings: {batch_result.warnings}")
            print(f"  Success:  {batch_result.success_rate:.1f}%")
        else:
            for result in batch_result.results:
                if result.valid:
                    if not args.quiet:
                        status = "PASS" if not result.warnings else "WARN"
                        print(f"{status} {result.entity_path}")
                        for warning in result.warnings:
                            print(f"    WARN {warning}")
                else:
                    print(f"FAIL {result.entity_path}")
                    for error in result.errors:
                        print(f"    FAIL {error}")

            if not args.quiet:
                print(
                    f"\n{batch_result.valid}/{batch_result.total} valid ({batch_result.success_rate:.1f}%)"
                )

        sys.exit(0 if batch_result.invalid == 0 else 1)

    else:
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)
