#!/usr/bin/env python3
"""
PM-OS Brain Body Relationship Extractor

Extracts relationships from entity body content by analyzing mentions
of other entities using the alias registry.

Part of bd-3771: Brain Orphan Cleanup & Enrichment System
Story: bd-392b

Usage:
    python3 body_relationship_extractor.py scan              # Preview relationships
    python3 body_relationship_extractor.py apply             # Apply relationships
    python3 body_relationship_extractor.py --type person     # Filter by entity type
    python3 body_relationship_extractor.py --orphans-only    # Only process orphans
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml


@dataclass
class ExtractedRelationship:
    """A relationship extracted from body text."""

    source_id: str
    source_type: str
    target_id: str
    target_type: str
    relationship_type: str
    context: str  # The text snippet where mention was found
    confidence: float


@dataclass
class ExtractionReport:
    """Report of body text extraction."""

    entities_scanned: int
    entities_with_extractions: int
    relationships_extracted: int
    relationships_applied: int
    by_relationship_type: Dict[str, int] = field(default_factory=dict)
    by_source_type: Dict[str, int] = field(default_factory=dict)
    relationships: List[ExtractedRelationship] = field(default_factory=list)


# Relationship type inference based on entity types
RELATIONSHIP_INFERENCE = {
    # (source_type, target_type) -> (forward_rel, inverse_rel)
    ("person", "person"): ("collaborates_with", "collaborates_with"),
    ("person", "team"): ("member_of", "has_member"),
    ("person", "squad"): ("member_of", "has_member"),
    ("person", "project"): ("works_on", "has_contributor"),
    ("person", "system"): ("works_on", "has_contributor"),
    ("person", "brand"): ("works_on", "has_contributor"),
    ("project", "person"): ("has_contributor", "works_on"),
    ("project", "team"): ("owned_by", "owns"),
    ("project", "system"): ("uses", "used_by"),
    ("project", "brand"): ("belongs_to", "has_project"),
    ("system", "person"): ("maintained_by", "maintains"),
    ("system", "team"): ("owned_by", "owns"),
    ("system", "system"): ("related_to", "related_to"),
    ("experiment", "person"): ("owned_by", "owns"),
    ("experiment", "project"): ("part_of", "has_experiment"),
    ("experiment", "brand"): ("belongs_to", "has_experiment"),
    ("team", "person"): ("has_member", "member_of"),
    ("squad", "person"): ("has_member", "member_of"),
    ("brand", "person"): ("managed_by", "manages"),
    ("brand", "team"): ("owned_by", "owns"),
}

# Default relationship type when no specific inference exists
DEFAULT_RELATIONSHIP = ("mentioned_in", "mentions")


class BodyRelationshipExtractor:
    """
    Extracts relationships from entity body content.

    Scans markdown body text for mentions of other entities using
    the alias registry, then creates appropriate relationships.
    """

    # Minimum alias length to avoid false positives
    MIN_ALIAS_LENGTH = 3

    # Context extraction (chars before/after match)
    CONTEXT_CHARS = 100

    # Base confidence for body-extracted relationships
    BASE_CONFIDENCE = 0.6

    def __init__(self, brain_path: Path):
        """Initialize the extractor."""
        self.brain_path = brain_path
        self._alias_index: Optional[Dict[str, str]] = None
        self._entity_types: Optional[Dict[str, str]] = None
        self._entity_relationships: Optional[Dict[str, Set[str]]] = None

    def scan(
        self,
        entity_type: Optional[str] = None,
        orphans_only: bool = False,
        limit: int = 1000,
    ) -> ExtractionReport:
        """
        Scan entities for body text relationships.

        Args:
            entity_type: Filter by source entity type
            orphans_only: Only scan entities without relationships
            limit: Maximum relationships to extract

        Returns:
            ExtractionReport with all discovered relationships
        """
        # Build indices
        self._build_alias_index()
        self._build_entity_type_index()
        self._build_relationship_index()

        extracted: List[ExtractedRelationship] = []
        entities_scanned = 0
        entities_with_extractions = 0
        by_rel_type: Dict[str, int] = {}
        by_source_type: Dict[str, int] = {}

        # Scan all entities
        for entity_path in self._get_entity_files():
            try:
                content = entity_path.read_text(encoding="utf-8")
                frontmatter, body = self._parse_content(content)

                if not frontmatter or not body.strip():
                    continue

                entity_id = frontmatter.get("$id", "")
                etype = frontmatter.get("$type", "unknown")

                # Apply filters
                if entity_type and etype != entity_type:
                    continue

                if orphans_only:
                    existing_rels = frontmatter.get("$relationships", [])
                    if existing_rels:
                        continue

                entities_scanned += 1

                # Extract mentions from body
                mentions = self._extract_mentions(body, entity_id)

                if mentions:
                    entities_with_extractions += 1

                    for target_id, context in mentions:
                        target_type = self._entity_types.get(target_id, "unknown")

                        # Determine relationship type
                        rel_types = RELATIONSHIP_INFERENCE.get(
                            (etype, target_type), DEFAULT_RELATIONSHIP
                        )
                        forward_rel = rel_types[0]

                        # Calculate confidence based on context quality
                        confidence = self._calculate_confidence(context, target_id)

                        rel = ExtractedRelationship(
                            source_id=entity_id,
                            source_type=etype,
                            target_id=target_id,
                            target_type=target_type,
                            relationship_type=forward_rel,
                            context=context[:200],
                            confidence=round(confidence, 3),
                        )
                        extracted.append(rel)

                        by_rel_type[forward_rel] = by_rel_type.get(forward_rel, 0) + 1
                        by_source_type[etype] = by_source_type.get(etype, 0) + 1

                        if len(extracted) >= limit:
                            break

                if len(extracted) >= limit:
                    break

            except Exception as e:
                continue

        return ExtractionReport(
            entities_scanned=entities_scanned,
            entities_with_extractions=entities_with_extractions,
            relationships_extracted=len(extracted),
            relationships_applied=0,
            by_relationship_type=by_rel_type,
            by_source_type=by_source_type,
            relationships=extracted,
        )

    def apply(
        self,
        relationships: List[ExtractedRelationship],
        dry_run: bool = False,
    ) -> int:
        """
        Apply extracted relationships to entities.

        Creates bidirectional relationships for each extraction.

        Args:
            relationships: List of relationships to apply
            dry_run: If True, don't write changes

        Returns:
            Number of relationships applied
        """
        applied = 0

        for rel in relationships:
            # Get inverse relationship type
            rel_types = RELATIONSHIP_INFERENCE.get(
                (rel.source_type, rel.target_type), DEFAULT_RELATIONSHIP
            )
            inverse_rel = rel_types[1]

            # Apply forward relationship (source -> target)
            forward_ok = self._add_relationship(
                rel.source_id,
                rel.target_id,
                rel.relationship_type,
                rel.confidence,
                dry_run,
            )

            # Apply inverse relationship (target -> source)
            inverse_ok = self._add_relationship(
                rel.target_id,
                rel.source_id,
                inverse_rel,
                rel.confidence,
                dry_run,
            )

            if forward_ok or inverse_ok:
                applied += 1

        return applied

    def _build_alias_index(self) -> None:
        """Build index of aliases to entity IDs."""
        if self._alias_index is not None:
            return

        self._alias_index = {}

        # Load from registry if exists
        registry_path = self.brain_path / "registry.yaml"
        if registry_path.exists():
            try:
                registry = yaml.safe_load(registry_path.read_text())

                # Check for pre-built index
                if "alias_index" in registry:
                    self._alias_index = {
                        k.lower(): v for k, v in registry["alias_index"].items()
                    }
                    return

                # Build from entities
                entities = registry.get("entities", registry)
                for slug, entry in entities.items():
                    if isinstance(entry, dict):
                        aliases = entry.get("aliases", entry.get("$aliases", []))
                        for alias in aliases:
                            if alias and len(alias) >= self.MIN_ALIAS_LENGTH:
                                self._alias_index[alias.lower()] = slug
            except Exception:
                pass

        # Also scan entity files for names
        for entity_path in self._get_entity_files():
            try:
                content = entity_path.read_text(encoding="utf-8")
                frontmatter, _ = self._parse_content(content)

                if not frontmatter:
                    continue

                entity_id = frontmatter.get("$id", "")
                name = frontmatter.get("name", "")
                aliases = frontmatter.get("$aliases", [])

                if name and len(name) >= self.MIN_ALIAS_LENGTH:
                    self._alias_index[name.lower()] = entity_id

                for alias in aliases:
                    if alias and len(alias) >= self.MIN_ALIAS_LENGTH:
                        self._alias_index[alias.lower()] = entity_id

            except Exception:
                continue

    def _build_entity_type_index(self) -> None:
        """Build index of entity IDs to types."""
        if self._entity_types is not None:
            return

        self._entity_types = {}

        for entity_path in self._get_entity_files():
            try:
                content = entity_path.read_text(encoding="utf-8")
                frontmatter, _ = self._parse_content(content)

                if frontmatter:
                    entity_id = frontmatter.get("$id", "")
                    etype = frontmatter.get("$type", "unknown")
                    self._entity_types[entity_id] = etype
            except Exception:
                continue

    def _build_relationship_index(self) -> None:
        """Build index of existing relationships to avoid duplicates."""
        if self._entity_relationships is not None:
            return

        self._entity_relationships = {}

        for entity_path in self._get_entity_files():
            try:
                content = entity_path.read_text(encoding="utf-8")
                frontmatter, _ = self._parse_content(content)

                if not frontmatter:
                    continue

                entity_id = frontmatter.get("$id", "")
                relationships = frontmatter.get("$relationships", [])

                targets = set()
                for rel in relationships:
                    if isinstance(rel, dict):
                        target = rel.get("target", "")
                        if target:
                            targets.add(target)

                self._entity_relationships[entity_id] = targets

            except Exception:
                continue

    def _extract_mentions(
        self,
        body: str,
        source_id: str,
    ) -> List[Tuple[str, str]]:
        """
        Extract entity mentions from body text.

        Args:
            body: Body text to scan
            source_id: ID of source entity (to exclude self-references)

        Returns:
            List of (target_id, context) tuples
        """
        mentions = []
        seen_targets = set()

        # Get existing relationships to avoid duplicates
        existing = self._entity_relationships.get(source_id, set())

        body_lower = body.lower()

        for alias, target_id in self._alias_index.items():
            # Skip self-references
            if target_id == source_id:
                continue

            # Skip if already related
            if target_id in existing:
                continue

            # Skip if already found this target
            if target_id in seen_targets:
                continue

            # Search for alias with word boundaries
            pattern = r"\b" + re.escape(alias) + r"\b"
            match = re.search(pattern, body_lower)

            if match:
                # Extract context around the match
                start = max(0, match.start() - self.CONTEXT_CHARS)
                end = min(len(body), match.end() + self.CONTEXT_CHARS)
                context = body[start:end].strip()

                mentions.append((target_id, context))
                seen_targets.add(target_id)

        return mentions

    def _calculate_confidence(self, context: str, target_id: str) -> float:
        """
        Calculate confidence based on context quality.

        Higher confidence for:
        - Longer context
        - Multiple mentions
        - Near relationship words (works with, manages, etc.)
        """
        confidence = self.BASE_CONFIDENCE

        # Bonus for relationship keywords
        relationship_keywords = [
            "works with",
            "manages",
            "reports to",
            "member of",
            "leads",
            "owns",
            "maintains",
            "collaborates",
            "team",
            "squad",
            "project",
            "department",
        ]

        context_lower = context.lower()
        for keyword in relationship_keywords:
            if keyword in context_lower:
                confidence += 0.05
                break

        # Bonus for proper noun context (capitalized mentions)
        if re.search(r"[A-Z][a-z]+", context):
            confidence += 0.05

        # Cap at 0.85 (body extraction is never fully reliable)
        return min(0.85, confidence)

    def _add_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        confidence: float,
        dry_run: bool,
    ) -> bool:
        """Add a relationship to an entity."""
        entity_path = self._find_entity_file(source_id)
        if not entity_path:
            return False

        try:
            content = entity_path.read_text(encoding="utf-8")
            frontmatter, body = self._parse_content(content)

            if not frontmatter:
                return False

            # Check if relationship already exists
            relationships = frontmatter.get("$relationships", [])
            for rel in relationships:
                if isinstance(rel, dict) and rel.get("target") == target_id:
                    return False  # Already exists

            # Add new relationship
            new_rel = {
                "type": rel_type,
                "target": target_id,
                "confidence": confidence,
                "source": "body_extraction",
                "last_verified": date.today().isoformat(),
            }
            relationships.append(new_rel)
            frontmatter["$relationships"] = relationships

            if not dry_run:
                # Log event via EventHelper (handles $version + $updated)
                from event_helpers import EventHelper

                event = EventHelper.create_relationship_event(
                    actor="system/body_relationship_extractor",
                    target=target_id,
                    rel_type=rel_type,
                    operation="add",
                    source="body_extraction",
                )
                EventHelper.append_to_frontmatter(frontmatter, event)

                new_content = self._format_content(frontmatter, body)
                entity_path.write_text(new_content, encoding="utf-8")

            return True

        except Exception as e:
            print(f"Error adding relationship to {source_id}: {e}", file=sys.stderr)
            return False

    def _find_entity_file(self, entity_id: str) -> Optional[Path]:
        """Find the file path for an entity ID."""
        for entity_path in self._get_entity_files():
            try:
                content = entity_path.read_text(encoding="utf-8")
                frontmatter, _ = self._parse_content(content)
                if frontmatter.get("$id") == entity_id:
                    return entity_path
            except Exception:
                continue
        return None

    def _get_entity_files(self) -> List[Path]:
        """Get all entity files in brain."""
        files = list(self.brain_path.rglob("*.md"))
        return [
            f
            for f in files
            if f.name.lower() not in ("readme.md", "index.md", "_index.md")
            and ".snapshots" not in str(f)
            and ".schema" not in str(f)
        ]

    def _parse_content(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter from content."""
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

    def _format_content(self, frontmatter: Dict[str, Any], body: str) -> str:
        """Format frontmatter and body back to markdown."""
        yaml_str = yaml.dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
        return f"---\n{yaml_str}---{body}"


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract relationships from entity body content"
    )
    parser.add_argument(
        "action",
        choices=["scan", "apply"],
        nargs="?",
        default="scan",
        help="Action to perform",
    )
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--type",
        type=str,
        help="Filter by entity type",
    )
    parser.add_argument(
        "--orphans-only",
        action="store_true",
        help="Only process orphan entities",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Maximum relationships to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without applying changes",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )

    args = parser.parse_args()

    # Resolve brain path
    if not args.brain_path:
        script_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(script_dir))
        try:
            from path_resolver import get_paths

            paths = get_paths()
            args.brain_path = paths.user / "brain"
        except ImportError:
            args.brain_path = Path.cwd() / "user" / "brain"

    extractor = BodyRelationshipExtractor(args.brain_path)

    if args.action == "scan":
        report = extractor.scan(
            entity_type=args.type,
            orphans_only=args.orphans_only,
            limit=args.limit,
        )

        if args.output == "json":
            output = {
                "entities_scanned": report.entities_scanned,
                "entities_with_extractions": report.entities_with_extractions,
                "relationships_extracted": report.relationships_extracted,
                "by_relationship_type": report.by_relationship_type,
                "by_source_type": report.by_source_type,
                "relationships": [
                    {
                        "source_id": r.source_id,
                        "target_id": r.target_id,
                        "type": r.relationship_type,
                        "confidence": r.confidence,
                    }
                    for r in report.relationships[:100]
                ],
            }
            print(json.dumps(output, indent=2))
        else:
            print("Body Relationship Extraction Scan")
            print("=" * 60)
            print(f"Entities scanned: {report.entities_scanned}")
            print(f"With extractions: {report.entities_with_extractions}")
            print(f"Relationships found: {report.relationships_extracted}")
            print()

            if report.by_relationship_type:
                print("By relationship type:")
                for rel_type, count in sorted(
                    report.by_relationship_type.items(), key=lambda x: -x[1]
                ):
                    print(f"  {rel_type}: {count}")
                print()

            if report.by_source_type:
                print("By source entity type:")
                for etype, count in sorted(
                    report.by_source_type.items(), key=lambda x: -x[1]
                ):
                    print(f"  {etype}: {count}")
                print()

            print(f"Top {min(20, len(report.relationships))} extractions:")
            print("-" * 60)
            for rel in report.relationships[:20]:
                print(f"  {rel.confidence:.2f} | {rel.source_id}")
                print(f"       --[{rel.relationship_type}]--> {rel.target_id}")
                print(f"       Context: {rel.context[:80]}...")
                print()

    elif args.action == "apply":
        # First scan
        report = extractor.scan(
            entity_type=args.type,
            orphans_only=args.orphans_only,
            limit=args.limit,
        )

        if not report.relationships:
            print("No relationships to apply")
            return 0

        if args.dry_run:
            print(f"DRY RUN: Would apply {len(report.relationships)} relationships")
            for rel in report.relationships[:10]:
                print(
                    f"  {rel.source_id} --[{rel.relationship_type}]--> {rel.target_id}"
                )
            return 0

        # Apply relationships
        applied = extractor.apply(report.relationships, dry_run=False)
        print(f"Applied {applied} bidirectional relationships")
        print("Relationships marked with source: body_extraction")

    return 0


if __name__ == "__main__":
    sys.exit(main())
