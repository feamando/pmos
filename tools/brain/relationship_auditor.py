#!/usr/bin/env python3
"""
PM-OS Brain Relationship Auditor

Audits relationships between Brain entities for consistency and bidirectionality.
"""

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

# Add tools directory for canonical_resolver import
sys.path.insert(0, str(Path(__file__).parent))

from canonical_resolver import CanonicalResolver


@dataclass
class RelationshipIssue:
    """Represents a relationship inconsistency."""

    issue_type: str
    source_entity: str
    target_entity: str
    relationship_type: str
    message: str
    severity: str = "warning"  # warning, error


@dataclass
class AuditResult:
    """Result of relationship audit."""

    total_entities: int
    total_relationships: int
    orphan_targets: List[RelationshipIssue]
    missing_inverses: List[RelationshipIssue]
    duplicate_relationships: List[RelationshipIssue]
    invalid_types: List[RelationshipIssue]

    @property
    def total_issues(self) -> int:
        return (
            len(self.orphan_targets)
            + len(self.missing_inverses)
            + len(self.duplicate_relationships)
            + len(self.invalid_types)
        )

    @property
    def is_healthy(self) -> bool:
        return self.total_issues == 0


class RelationshipAuditor:
    """
    Audits Brain entity relationships for consistency.

    Checks:
    - Orphan targets (relationships to non-existent entities)
    - Missing inverse relationships (bidirectionality)
    - Duplicate relationships
    - Invalid relationship types
    """

    # Relationship type inversions
    INVERSE_TYPES = {
        "reports_to": "manages",
        "manages": "reports_to",
        "member_of": "has_member",
        "has_member": "member_of",
        "owns": "owned_by",
        "owned_by": "owns",
        "depends_on": "depended_by",
        "depended_by": "depends_on",
        "part_of": "contains",
        "contains": "part_of",
        "works_on": "worked_by",
        "worked_by": "works_on",
        "leads": "led_by",
        "led_by": "leads",
        "collaborates_with": "collaborates_with",  # Symmetric
        "related_to": "related_to",  # Symmetric
    }

    # Valid relationship types
    VALID_TYPES = set(INVERSE_TYPES.keys()) | {
        "stakeholder_of",
        "expert_in",
        "maintains",
        "consumes",
        "produces",
        "succeeded_by",
        "preceded_by",
    }

    def __init__(self, brain_path: Path):
        """
        Initialize the auditor.

        Args:
            brain_path: Path to the brain directory
        """
        self.brain_path = brain_path
        self.entity_index: Dict[str, Path] = {}
        self.relationships: Dict[str, List[Dict]] = {}
        self.resolver = CanonicalResolver(brain_path)

    def audit(self) -> AuditResult:
        """
        Perform full relationship audit.

        Returns:
            AuditResult with all issues found
        """
        # Build canonical resolver index
        self.resolver.build_index()

        # Build entity index
        self._build_entity_index()

        # Load all relationships
        self._load_relationships()

        # Check for issues
        orphan_targets = self._find_orphan_targets()
        missing_inverses = self._find_missing_inverses()
        duplicates = self._find_duplicates()
        invalid_types = self._find_invalid_types()

        return AuditResult(
            total_entities=len(self.entity_index),
            total_relationships=sum(len(rels) for rels in self.relationships.values()),
            orphan_targets=orphan_targets,
            missing_inverses=missing_inverses,
            duplicate_relationships=duplicates,
            invalid_types=invalid_types,
        )

    def fix_issues(
        self,
        result: AuditResult,
        fix_inverses: bool = True,
        fix_orphans: bool = False,
        dry_run: bool = True,
    ) -> Dict[str, int]:
        """
        Attempt to fix identified issues.

        Args:
            result: Audit result with issues
            fix_inverses: Add missing inverse relationships
            fix_orphans: Remove orphan relationships
            dry_run: Preview without making changes

        Returns:
            Dictionary of fixes applied
        """
        fixes = {"inverses_added": 0, "orphans_removed": 0}

        if fix_inverses:
            for issue in result.missing_inverses:
                if self._add_inverse_relationship(issue, dry_run):
                    fixes["inverses_added"] += 1

        if fix_orphans:
            for issue in result.orphan_targets:
                if self._remove_orphan_relationship(issue, dry_run):
                    fixes["orphans_removed"] += 1

        return fixes

    def _build_entity_index(self):
        """Build index of all entities."""
        self.entity_index.clear()

        entity_files = list(self.brain_path.rglob("*.md"))
        entity_files = [
            f
            for f in entity_files
            if f.name.lower() not in ("readme.md", "index.md", "_index.md")
            and ".snapshots" not in str(f)
            and ".schema" not in str(f)
        ]

        for entity_path in entity_files:
            # Create multiple index keys
            relative_path = str(entity_path.relative_to(self.brain_path))
            slug = entity_path.stem.lower().replace(" ", "-").replace("_", "-")

            self.entity_index[relative_path] = entity_path
            self.entity_index[slug] = entity_path

            # Also index by $id if present
            try:
                content = entity_path.read_text(encoding="utf-8")
                frontmatter = self._parse_frontmatter(content)
                if "$id" in frontmatter:
                    self.entity_index[frontmatter["$id"]] = entity_path
            except Exception:
                pass

    def _load_relationships(self):
        """Load all relationships from entities."""
        self.relationships.clear()

        for entity_id, entity_path in self.entity_index.items():
            if not entity_path.exists():
                continue

            try:
                content = entity_path.read_text(encoding="utf-8")
                frontmatter = self._parse_frontmatter(content)
                relationships = frontmatter.get("$relationships", [])

                if relationships and entity_id not in self.relationships:
                    self.relationships[entity_id] = relationships
            except Exception:
                pass

    def _find_orphan_targets(self) -> List[RelationshipIssue]:
        """Find relationships pointing to non-existent entities."""
        issues = []

        for source_id, relationships in self.relationships.items():
            for rel in relationships:
                if not isinstance(rel, dict):
                    continue

                target = rel.get("target", "")
                if not target:
                    continue

                # Check if target exists
                if not self._entity_exists(target):
                    issues.append(
                        RelationshipIssue(
                            issue_type="orphan_target",
                            source_entity=source_id,
                            target_entity=target,
                            relationship_type=rel.get("type", "unknown"),
                            message=f"Target entity '{target}' does not exist",
                            severity="error",
                        )
                    )

        return issues

    def _find_missing_inverses(self) -> List[RelationshipIssue]:
        """Find relationships without corresponding inverse."""
        issues = []

        for source_id, relationships in self.relationships.items():
            source_path = self.entity_index.get(source_id)
            if not source_path:
                continue

            for rel in relationships:
                if not isinstance(rel, dict):
                    continue

                target = rel.get("target", "")
                rel_type = rel.get("type", "")

                if not target or not rel_type:
                    continue

                # Skip if no known inverse
                inverse_type = self.INVERSE_TYPES.get(rel_type)
                if not inverse_type:
                    continue

                # Check if target has inverse relationship
                target_rels = self._get_entity_relationships(target)
                has_inverse = any(
                    r.get("type") == inverse_type
                    and self._targets_match(r.get("target", ""), source_id, source_path)
                    for r in target_rels
                )

                if not has_inverse and self._entity_exists(target):
                    issues.append(
                        RelationshipIssue(
                            issue_type="missing_inverse",
                            source_entity=source_id,
                            target_entity=target,
                            relationship_type=rel_type,
                            message=f"Missing inverse '{inverse_type}' from {target} to {source_id}",
                            severity="warning",
                        )
                    )

        return issues

    def _find_duplicates(self) -> List[RelationshipIssue]:
        """Find duplicate relationships."""
        issues = []

        for source_id, relationships in self.relationships.items():
            seen: Set[Tuple[str, str]] = set()

            for rel in relationships:
                if not isinstance(rel, dict):
                    continue

                key = (rel.get("type", ""), rel.get("target", ""))
                if key in seen:
                    issues.append(
                        RelationshipIssue(
                            issue_type="duplicate",
                            source_entity=source_id,
                            target_entity=rel.get("target", ""),
                            relationship_type=rel.get("type", ""),
                            message="Duplicate relationship",
                            severity="warning",
                        )
                    )
                seen.add(key)

        return issues

    def _find_invalid_types(self) -> List[RelationshipIssue]:
        """Find relationships with invalid types."""
        issues = []

        for source_id, relationships in self.relationships.items():
            for rel in relationships:
                if not isinstance(rel, dict):
                    continue

                rel_type = rel.get("type", "")
                if rel_type and rel_type not in self.VALID_TYPES:
                    issues.append(
                        RelationshipIssue(
                            issue_type="invalid_type",
                            source_entity=source_id,
                            target_entity=rel.get("target", ""),
                            relationship_type=rel_type,
                            message=f"Unknown relationship type: {rel_type}",
                            severity="warning",
                        )
                    )

        return issues

    def _entity_exists(self, entity_ref: str) -> bool:
        """Check if an entity exists using CanonicalResolver."""
        # Use resolver for authoritative lookup
        canonical = self.resolver.resolve(entity_ref)
        if canonical:
            return True

        # Fall back to entity index
        if entity_ref in self.entity_index:
            return True

        # Try various normalizations
        normalized = entity_ref.lower().replace(" ", "-").replace("_", "-")
        if normalized in self.entity_index:
            return True

        # Try as path
        potential_path = self.brain_path / entity_ref
        if potential_path.exists():
            return True

        return False

    def _get_entity_relationships(self, entity_ref: str) -> List[Dict]:
        """Get relationships for an entity."""
        # Try direct lookup
        if entity_ref in self.relationships:
            return self.relationships[entity_ref]

        # Try normalized
        normalized = entity_ref.lower().replace(" ", "-").replace("_", "-")
        if normalized in self.relationships:
            return self.relationships[normalized]

        return []

    def _targets_match(
        self, target: str, expected: str, expected_path: Optional[Path]
    ) -> bool:
        """Check if a target reference matches an expected entity."""
        if target == expected:
            return True

        target_norm = target.lower().replace(" ", "-").replace("_", "-")
        expected_norm = expected.lower().replace(" ", "-").replace("_", "-")

        if target_norm == expected_norm:
            return True

        if expected_path:
            relative = str(expected_path.relative_to(self.brain_path))
            if target == relative:
                return True

        return False

    def _add_inverse_relationship(
        self, issue: RelationshipIssue, dry_run: bool
    ) -> bool:
        """Add missing inverse relationship."""
        target_path = self.entity_index.get(issue.target_entity)

        # Try case-insensitive lookup if not found
        if not target_path:
            target_lower = issue.target_entity.lower()
            for key, path in self.entity_index.items():
                if key.lower() == target_lower:
                    target_path = path
                    break

        if not target_path:
            return False

        inverse_type = self.INVERSE_TYPES.get(issue.relationship_type)
        if not inverse_type:
            return False

        if dry_run:
            print(
                f"Would add {inverse_type}: {issue.target_entity} -> {issue.source_entity}"
            )
            return True

        try:
            content = target_path.read_text(encoding="utf-8")
            frontmatter, body = self._parse_content(content)

            if "$relationships" not in frontmatter:
                frontmatter["$relationships"] = []

            frontmatter["$relationships"].append(
                {
                    "type": inverse_type,
                    "target": issue.source_entity,
                }
            )

            new_content = (
                "---\n"
                + yaml.dump(
                    frontmatter,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )
                + "---"
                + body
            )

            target_path.write_text(new_content, encoding="utf-8")
            return True

        except Exception:
            return False

    def _remove_orphan_relationship(
        self, issue: RelationshipIssue, dry_run: bool
    ) -> bool:
        """Remove orphan relationship."""
        source_path = self.entity_index.get(issue.source_entity)
        if not source_path:
            return False

        if dry_run:
            print(
                f"Would remove orphan: {issue.source_entity} -> {issue.target_entity}"
            )
            return True

        try:
            content = source_path.read_text(encoding="utf-8")
            frontmatter, body = self._parse_content(content)

            relationships = frontmatter.get("$relationships", [])
            frontmatter["$relationships"] = [
                r
                for r in relationships
                if not (
                    r.get("target") == issue.target_entity
                    and r.get("type") == issue.relationship_type
                )
            ]

            new_content = (
                "---\n"
                + yaml.dump(
                    frontmatter,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )
                + "---"
                + body
            )

            source_path.write_text(new_content, encoding="utf-8")
            return True

        except Exception:
            return False

    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """Parse YAML frontmatter."""
        if not content.startswith("---"):
            return {}

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}

        try:
            return yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            return {}

    def _parse_content(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Parse frontmatter and body."""
        if not content.startswith("---"):
            return {}, content

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content

        try:
            frontmatter = yaml.safe_load(parts[1]) or {}
            return frontmatter, parts[2]
        except yaml.YAMLError:
            return {}, content


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Audit Brain entity relationships")
    parser.add_argument(
        "action",
        choices=["audit", "fix"],
        help="Action to perform",
    )
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--fix-inverses",
        action="store_true",
        help="Add missing inverse relationships",
    )
    parser.add_argument(
        "--fix-orphans",
        action="store_true",
        help="Remove orphan relationships",
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

    auditor = RelationshipAuditor(args.brain_path)
    result = auditor.audit()

    print("Relationship Audit Results")
    print("=" * 60)
    print(f"Total entities: {result.total_entities}")
    print(f"Total relationships: {result.total_relationships}")
    print(f"Total issues: {result.total_issues}")
    print()

    if result.orphan_targets:
        print(f"Orphan targets: {len(result.orphan_targets)}")
        for issue in result.orphan_targets[:5]:
            print(f"  - {issue.source_entity} -> {issue.target_entity}")

    if result.missing_inverses:
        print(f"Missing inverses: {len(result.missing_inverses)}")
        for issue in result.missing_inverses[:5]:
            print(f"  - {issue.message}")

    if result.duplicate_relationships:
        print(f"Duplicates: {len(result.duplicate_relationships)}")

    if result.invalid_types:
        print(f"Invalid types: {len(result.invalid_types)}")

    if args.action == "fix":
        fixes = auditor.fix_issues(
            result,
            fix_inverses=args.fix_inverses,
            fix_orphans=args.fix_orphans,
            dry_run=args.dry_run,
        )
        print()
        print(f"Fixes applied: {fixes}")

    return 0 if result.is_healthy else 1


if __name__ == "__main__":
    sys.exit(main())
