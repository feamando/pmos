#!/usr/bin/env python3
"""
PM-OS Brain Relationship Builder (v5.0)

Enforces bidirectional relationship creation - when A->B is created,
automatically creates B->A with the inverse relationship type.

Usage:
    from pm_os_brain.tools.relationships.relationship_builder import RelationshipBuilder

    builder = RelationshipBuilder(brain_path)
    result = builder.create_bidirectional(
        source_id="entity/person/john",
        target_id="entity/team/growth",
        relationship_type="member_of",
        confidence=0.9,
        source="jira"
    )
"""

import json
import logging
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from core.config_loader import get_config
    except ImportError:
        get_config = None

logger = logging.getLogger(__name__)

# Comprehensive inverse relationship mapping
INVERSE_RELATIONSHIPS = {
    # Organizational
    "reports_to": "manages",
    "manages": "reports_to",
    "member_of": "has_member",
    "has_member": "member_of",
    "leads": "led_by",
    "led_by": "leads",
    # Ownership
    "owns": "owned_by",
    "owned_by": "owns",
    "maintains": "maintained_by",
    "maintained_by": "maintains",
    "managed_by": "manages",
    # Collaboration
    "works_with": "works_with",  # Symmetric
    "collaborates_with": "collaborates_with",  # Symmetric
    "stakeholder_of": "has_stakeholder",
    "has_stakeholder": "stakeholder_of",
    "works_on": "has_contributor",
    "has_contributor": "works_on",
    # Dependencies
    "depends_on": "depended_on_by",
    "depended_on_by": "depends_on",
    "blocks": "blocked_by",
    "blocked_by": "blocks",
    "uses": "used_by",
    "used_by": "uses",
    # Hierarchy
    "parent_of": "child_of",
    "child_of": "parent_of",
    "part_of": "has_part",
    "has_part": "part_of",
    "belongs_to": "contains",
    "contains": "belongs_to",
    # Content relationships
    "mentioned_in": "mentions",
    "mentions": "mentioned_in",
    "related_to": "related_to",  # Symmetric
    "similar_to": "similar_to",  # Symmetric
    "documented_in": "documents",
    "documents": "documented_in",
    # Experiments
    "has_experiment": "part_of",
}


@dataclass
class RelationshipResult:
    """Result of a relationship creation operation."""

    source_id: str
    target_id: str
    forward_type: str
    inverse_type: str
    forward_created: bool
    inverse_created: bool
    forward_existed: bool
    inverse_existed: bool


@dataclass
class MergeResult:
    """Result of a merge operation."""

    primary_id: str
    duplicate_id: str
    relationships_transferred: int
    aliases_merged: int
    references_updated: int
    body_appended: bool
    confidence_updated: bool
    duplicate_deleted: bool
    dry_run: bool
    error: Optional[str] = None


class RelationshipBuilder:
    """
    Creates bidirectional relationships between Brain entities.

    Ensures that when a relationship A->B is created, the inverse
    relationship B->A is also created automatically.
    """

    def __init__(self, brain_path: Path):
        """Initialize the relationship builder."""
        self.brain_path = brain_path
        self._entity_cache: Dict[str, Path] = {}

    def create_bidirectional(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        confidence: float = 1.0,
        source: Optional[str] = None,
        since: Optional[date] = None,
        role: Optional[str] = None,
        dry_run: bool = False,
    ) -> RelationshipResult:
        """
        Create a bidirectional relationship between two entities.

        Args:
            source_id: Source entity $id
            target_id: Target entity $id
            relationship_type: Forward relationship type (e.g., "member_of")
            confidence: Confidence score [0,1]
            source: Source of relationship data
            since: When relationship started
            role: Optional role context
            dry_run: If True, don't write changes

        Returns:
            RelationshipResult with creation status
        """
        # Get inverse relationship type
        inverse_type = self.get_inverse_type(relationship_type)

        # Create forward relationship (source -> target)
        forward_created, forward_existed = self._add_relationship(
            entity_id=source_id,
            target_id=target_id,
            rel_type=relationship_type,
            confidence=confidence,
            source=source,
            since=since,
            role=role,
            dry_run=dry_run,
        )

        # Create inverse relationship (target -> source)
        inverse_created, inverse_existed = self._add_relationship(
            entity_id=target_id,
            target_id=source_id,
            rel_type=inverse_type,
            confidence=confidence,
            source=source,
            since=since,
            role=role,
            dry_run=dry_run,
        )

        return RelationshipResult(
            source_id=source_id,
            target_id=target_id,
            forward_type=relationship_type,
            inverse_type=inverse_type,
            forward_created=forward_created,
            inverse_created=inverse_created,
            forward_existed=forward_existed,
            inverse_existed=inverse_existed,
        )

    def get_inverse_type(self, relationship_type: str) -> str:
        """
        Get the inverse relationship type.

        Args:
            relationship_type: Forward relationship type

        Returns:
            Inverse relationship type
        """
        # Check known inverses
        if relationship_type in INVERSE_RELATIONSHIPS:
            return INVERSE_RELATIONSHIPS[relationship_type]

        # Generate inverse for unknown types
        if relationship_type.startswith("has_"):
            return relationship_type[4:] + "_of"
        if relationship_type.endswith("_of"):
            return "has_" + relationship_type[:-3]
        if relationship_type.endswith("_by"):
            return relationship_type[:-3] + "s"
        if relationship_type.endswith("s") and not relationship_type.endswith("_by"):
            return relationship_type[:-1] + "_by"

        # Default: prefix with "inverse_"
        return f"inverse_{relationship_type}"

    def ensure_inverse_exists(
        self,
        source_id: str,
        relationship: Dict[str, Any],
        dry_run: bool = False,
    ) -> bool:
        """
        Ensure the inverse of an existing relationship exists.

        Useful for retroactively fixing one-way relationships.

        Args:
            source_id: ID of entity that has the relationship
            relationship: The existing relationship dict
            dry_run: If True, don't write changes

        Returns:
            True if inverse was created or already existed
        """
        target_id = relationship.get("target", "")
        if not target_id:
            return False

        rel_type = relationship.get("type", "related_to")
        inverse_type = self.get_inverse_type(rel_type)

        created, existed = self._add_relationship(
            entity_id=target_id,
            target_id=source_id,
            rel_type=inverse_type,
            confidence=relationship.get("confidence", 1.0),
            source=relationship.get("source"),
            since=self._parse_date(relationship.get("since")),
            role=relationship.get("role"),
            dry_run=dry_run,
        )

        return created or existed

    def fix_all_inverses(
        self,
        dry_run: bool = False,
        limit: int = 1000,
    ) -> Dict[str, int]:
        """
        Scan all entities and create missing inverse relationships.

        Args:
            dry_run: If True, don't write changes
            limit: Maximum inverses to create

        Returns:
            Stats dict with counts
        """
        stats = {
            "entities_scanned": 0,
            "relationships_checked": 0,
            "inverses_created": 0,
            "inverses_existed": 0,
        }

        for entity_path in self._get_entity_files():
            try:
                content = entity_path.read_text(encoding="utf-8")
                frontmatter, body = self._parse_content(content)

                if not frontmatter:
                    continue

                stats["entities_scanned"] += 1
                entity_id = frontmatter.get("$id", "")
                relationships = frontmatter.get("$relationships", [])

                for rel in relationships:
                    if not isinstance(rel, dict):
                        continue

                    stats["relationships_checked"] += 1

                    if self.ensure_inverse_exists(entity_id, rel, dry_run):
                        # Check if it was created or existed
                        target_id = rel.get("target", "")
                        inverse_exists = self._relationship_exists(target_id, entity_id)
                        if inverse_exists:
                            stats["inverses_existed"] += 1
                        else:
                            stats["inverses_created"] += 1

                    if stats["inverses_created"] >= limit:
                        break

                if stats["inverses_created"] >= limit:
                    break

            except Exception:
                continue

        return stats

    def merge_entities(
        self,
        primary_id: str,
        duplicate_id: str,
        dry_run: bool = True,
    ) -> MergeResult:
        """
        Merge a duplicate entity into a primary entity.

        Transfers relationships, aliases, body content, and updates all
        references across the Brain from duplicate_id to primary_id.
        Then deletes the duplicate file.

        Args:
            primary_id: The entity to keep (absorbs the duplicate)
            duplicate_id: The entity to merge away (will be deleted)
            dry_run: If True, report without applying

        Returns:
            MergeResult with stats
        """
        try:
            from pm_os_brain.tools.relationships.safe_write import atomic_write
        except ImportError:
            try:
                from brain_core.safe_write import atomic_write
            except ImportError:
                def atomic_write(p, c, **kw):
                    Path(p).write_text(c, encoding=kw.get("encoding", "utf-8"))

        try:
            from pm_os_brain.tools.brain_core.event_helpers import EventHelper
        except ImportError:
            try:
                from temporal.event_helpers import EventHelper
            except ImportError:
                EventHelper = None

        primary_path = self._find_entity_file(primary_id)
        dup_path = self._find_entity_file(duplicate_id)

        if not primary_path:
            return MergeResult(
                primary_id=primary_id, duplicate_id=duplicate_id,
                relationships_transferred=0, aliases_merged=0,
                references_updated=0, body_appended=False,
                confidence_updated=False, duplicate_deleted=False,
                dry_run=dry_run, error=f"Primary entity not found: {primary_id}",
            )
        if not dup_path:
            return MergeResult(
                primary_id=primary_id, duplicate_id=duplicate_id,
                relationships_transferred=0, aliases_merged=0,
                references_updated=0, body_appended=False,
                confidence_updated=False, duplicate_deleted=False,
                dry_run=dry_run, error=f"Duplicate entity not found: {duplicate_id}",
            )

        # Load both entities
        p_fm, p_body = self._parse_content(primary_path.read_text(encoding="utf-8"))
        d_fm, d_body = self._parse_content(dup_path.read_text(encoding="utf-8"))

        # --- Merge relationships ---
        p_rels = p_fm.get("$relationships", [])
        d_rels = d_fm.get("$relationships", [])
        existing_targets = {
            (r.get("type"), r.get("target"))
            for r in p_rels if isinstance(r, dict)
        }
        rels_transferred = 0
        for rel in d_rels:
            if not isinstance(rel, dict):
                continue
            # Skip self-referencing relationships
            if rel.get("target") == primary_id:
                continue
            key = (rel.get("type"), rel.get("target"))
            if key not in existing_targets:
                p_rels.append(rel)
                existing_targets.add(key)
                rels_transferred += 1
        p_fm["$relationships"] = p_rels

        # --- Merge aliases ---
        p_aliases = p_fm.get("$aliases", []) or []
        d_aliases = d_fm.get("$aliases", []) or []
        d_name = d_fm.get("name", "")
        aliases_before = len(p_aliases)
        alias_set = set(p_aliases)
        for a in d_aliases:
            if a and a not in alias_set:
                p_aliases.append(a)
                alias_set.add(a)
        if d_name and d_name not in alias_set:
            p_aliases.append(d_name)
        p_fm["$aliases"] = p_aliases
        aliases_merged = len(p_aliases) - aliases_before

        # --- Merge body ---
        body_appended = False
        d_body_stripped = d_body.strip()
        if d_body_stripped and "[Auto-generated" not in d_body_stripped:
            if d_body_stripped not in p_body:
                p_body = p_body.rstrip() + f"\n\n## Merged Content\n\n{d_body_stripped}\n"
                body_appended = True

        # --- Confidence: take max ---
        p_conf = p_fm.get("$confidence", 0)
        d_conf = d_fm.get("$confidence", 0)
        confidence_updated = False
        if d_conf > p_conf:
            p_fm["$confidence"] = d_conf
            confidence_updated = True

        # --- Update references across all entities ---
        refs_updated = 0
        if not dry_run:
            refs_updated = self._repoint_references(duplicate_id, primary_id)

        # --- Log merge event ---
        if not dry_run:
            if EventHelper is not None:
                event = EventHelper.create_event(
                    event_type="field_update",
                    actor="system/relationship_builder",
                    changes=[
                        {"field": "merge_source", "operation": "set", "value": duplicate_id},
                        {"field": "relationships_transferred", "operation": "set", "value": rels_transferred},
                        {"field": "aliases_merged", "operation": "set", "value": aliases_merged},
                    ],
                    message=f"Merged duplicate {duplicate_id} into {primary_id}",
                )
                EventHelper.append_to_frontmatter(p_fm, event)

            # Write updated primary
            new_content = self._format_content(p_fm, p_body)
            atomic_write(primary_path, new_content)

            # Delete duplicate
            dup_path.unlink()

        return MergeResult(
            primary_id=primary_id,
            duplicate_id=duplicate_id,
            relationships_transferred=rels_transferred,
            aliases_merged=aliases_merged,
            references_updated=refs_updated,
            body_appended=body_appended,
            confidence_updated=confidence_updated,
            duplicate_deleted=not dry_run,
            dry_run=dry_run,
        )

    def batch_merge(
        self,
        merge_pairs: List[Tuple[str, str]],
        dry_run: bool = True,
    ) -> List[MergeResult]:
        """
        Merge multiple duplicate pairs sequentially.

        Args:
            merge_pairs: List of (primary_id, duplicate_id) tuples
            dry_run: If True, report without applying

        Returns:
            List of MergeResult for each pair
        """
        results = []
        for primary_id, duplicate_id in merge_pairs:
            result = self.merge_entities(primary_id, duplicate_id, dry_run=dry_run)
            results.append(result)
        return results

    def detect_duplicates(self, threshold: float = 0.90) -> List[Dict[str, Any]]:
        """
        Detect likely duplicate entity pairs using similar_to relationships
        and name similarity.

        Args:
            threshold: Minimum similarity confidence to consider as duplicate

        Returns:
            List of dicts with: primary, duplicate, confidence, reason
        """
        candidates = []
        seen_pairs = set()

        # Pass 1: Use existing similar_to relationships
        for entity_path in self._get_entity_files():
            try:
                content = entity_path.read_text(encoding="utf-8")
                fm, _ = self._parse_content(content)
                if not fm:
                    continue

                entity_id = fm.get("$id", "")
                if not entity_id:
                    continue

                rels = fm.get("$relationships", [])
                for rel in rels:
                    if not isinstance(rel, dict):
                        continue
                    if rel.get("type") != "similar_to":
                        continue
                    conf = rel.get("confidence", 0)
                    if conf < threshold:
                        continue

                    target = rel.get("target", "")
                    pair_key = tuple(sorted([entity_id, target]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    candidates.append({
                        "entity_a": entity_id,
                        "entity_b": target,
                        "confidence": conf,
                        "reason": f"similar_to relationship (confidence: {conf})",
                    })

            except Exception:
                continue

        # Pass 2: Check for name-based duplicates (same slug, different type prefix)
        id_to_path = {}
        for entity_path in self._get_entity_files():
            try:
                content = entity_path.read_text(encoding="utf-8")
                fm, _ = self._parse_content(content)
                eid = fm.get("$id", "")
                if eid:
                    id_to_path[eid] = entity_path
            except Exception:
                continue

        # Group by slug (last part of entity ID)
        from collections import defaultdict
        slug_groups = defaultdict(list)
        for eid in id_to_path:
            parts = eid.split("/")
            if len(parts) >= 3:
                slug = parts[-1]
                slug_groups[slug].append(eid)

        for slug, eids in slug_groups.items():
            if len(eids) < 2:
                continue
            for i in range(len(eids)):
                for j in range(i + 1, len(eids)):
                    pair_key = tuple(sorted([eids[i], eids[j]]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    candidates.append({
                        "entity_a": eids[i],
                        "entity_b": eids[j],
                        "confidence": 0.95,
                        "reason": f"Same slug '{slug}' with different type prefix",
                    })

        # Sort by confidence descending
        candidates.sort(key=lambda x: -x["confidence"])
        return candidates

    def _repoint_references(self, old_id: str, new_id: str) -> int:
        """
        Scan all entities and update relationship targets from old_id to new_id.

        Returns:
            Number of references updated
        """
        try:
            from pm_os_brain.tools.relationships.safe_write import atomic_write
        except ImportError:
            try:
                from brain_core.safe_write import atomic_write
            except ImportError:
                def atomic_write(p, c, **kw):
                    Path(p).write_text(c, encoding=kw.get("encoding", "utf-8"))

        count = 0
        for entity_path in self._get_entity_files():
            try:
                content = entity_path.read_text(encoding="utf-8")
                fm, body = self._parse_content(content)
                if not fm:
                    continue

                modified = False
                rels = fm.get("$relationships", [])
                for rel in rels:
                    if isinstance(rel, dict) and rel.get("target") == old_id:
                        rel["target"] = new_id
                        modified = True
                        count += 1

                if modified:
                    new_content = self._format_content(fm, body)
                    atomic_write(entity_path, new_content)

            except Exception:
                continue

        return count

    def _add_relationship(
        self,
        entity_id: str,
        target_id: str,
        rel_type: str,
        confidence: float,
        source: Optional[str],
        since: Optional[date],
        role: Optional[str],
        dry_run: bool,
    ) -> Tuple[bool, bool]:
        """
        Add a relationship to an entity.

        Returns:
            Tuple of (was_created, already_existed)
        """
        entity_path = self._find_entity_file(entity_id)
        if not entity_path:
            return False, False

        try:
            content = entity_path.read_text(encoding="utf-8")
            frontmatter, body = self._parse_content(content)

            if not frontmatter:
                return False, False

            relationships = frontmatter.get("$relationships", [])

            # Check if relationship already exists
            for rel in relationships:
                if isinstance(rel, dict) and rel.get("target") == target_id:
                    return False, True  # Already exists

            # Build new relationship
            new_rel = {
                "type": rel_type,
                "target": target_id,
                "confidence": confidence,
                "last_verified": date.today().isoformat(),
            }

            if source:
                new_rel["source"] = source
            if since:
                new_rel["since"] = since.isoformat()
            if role:
                new_rel["role"] = role

            relationships.append(new_rel)
            frontmatter["$relationships"] = relationships

            if not dry_run:
                # Log event via EventHelper (handles $version + $updated)
                try:
                    from pm_os_brain.tools.brain_core.event_helpers import EventHelper
                except ImportError:
                    try:
                        from temporal.event_helpers import EventHelper
                    except ImportError:
                        EventHelper = None

                if EventHelper is not None:
                    event = EventHelper.create_relationship_event(
                        actor="system/relationship_builder",
                        target=target_id,
                        rel_type=rel_type,
                        operation="add",
                        source=source,
                    )
                    EventHelper.append_to_frontmatter(frontmatter, event)

                new_content = self._format_content(frontmatter, body)
                entity_path.write_text(new_content, encoding="utf-8")

            return True, False

        except Exception as e:
            logger.error("Error adding relationship to %s: %s", entity_id, e)
            return False, False

    def _relationship_exists(self, entity_id: str, target_id: str) -> bool:
        """Check if a relationship to target exists on entity."""
        entity_path = self._find_entity_file(entity_id)
        if not entity_path:
            return False

        try:
            content = entity_path.read_text(encoding="utf-8")
            frontmatter, _ = self._parse_content(content)

            relationships = frontmatter.get("$relationships", [])
            for rel in relationships:
                if isinstance(rel, dict) and rel.get("target") == target_id:
                    return True
            return False
        except Exception:
            return False

    def _find_entity_file(self, entity_id: str) -> Optional[Path]:
        """Find the file path for an entity ID."""
        # Check cache first
        if entity_id in self._entity_cache:
            return self._entity_cache[entity_id]

        for entity_path in self._get_entity_files():
            try:
                content = entity_path.read_text(encoding="utf-8")
                frontmatter, _ = self._parse_content(content)
                eid = frontmatter.get("$id", "")

                # Cache this mapping
                if eid:
                    self._entity_cache[eid] = entity_path

                if eid == entity_id:
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

    def _parse_date(self, value: Any) -> Optional[date]:
        """Parse date from various formats."""
        if not value:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None
        return None


def _resolve_brain_path(args) -> Path:
    """Resolve brain path from args or config."""
    brain_path = getattr(args, "brain_path", None)
    if not brain_path:
        try:
            paths = get_paths()
            brain_path = paths.user / "brain"
        except Exception:
            brain_path = Path.cwd() / "user" / "brain"
    return brain_path


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Build bidirectional relationships in Brain"
    )
    parser.add_argument(
        "action",
        choices=["fix-inverses", "create", "check", "merge", "detect-duplicates", "batch-merge"],
        help="Action to perform",
    )
    parser.add_argument("--brain-path", type=Path, help="Path to brain directory")
    parser.add_argument("--source", type=str, help="Source entity ID (for create)")
    parser.add_argument("--target", type=str, help="Target entity ID (for create)")
    parser.add_argument("--primary", type=str, help="Primary entity ID (for merge)")
    parser.add_argument("--duplicate", type=str, help="Duplicate entity ID (for merge)")
    parser.add_argument("--manifest", type=str, help="Path to merge manifest JSON (for batch-merge)")
    parser.add_argument("--threshold", type=float, default=0.90, help="Similarity threshold (for detect-duplicates)")
    parser.add_argument("--type", type=str, help="Relationship type (for create)")
    parser.add_argument("--limit", type=int, default=500, help="Maximum operations")
    parser.add_argument("--dry-run", action="store_true", help="Preview without applying changes")
    parser.add_argument("--output", choices=["text", "json"], default="text", help="Output format")

    args = parser.parse_args()
    args.brain_path = _resolve_brain_path(args)
    builder = RelationshipBuilder(args.brain_path)

    if args.action == "fix-inverses":
        logger.info("Fixing missing inverse relationships...")
        stats = builder.fix_all_inverses(dry_run=args.dry_run, limit=args.limit)
        if args.output == "json":
            print(json.dumps(stats, indent=2))
        else:
            print(f"Entities scanned: {stats['entities_scanned']}")
            print(f"Relationships checked: {stats['relationships_checked']}")
            print(f"Inverses created: {stats['inverses_created']}")
            print(f"Inverses existed: {stats['inverses_existed']}")

    elif args.action == "create":
        if not args.source or not args.target or not args.type:
            print("Error: --source, --target, and --type required for create")
            return 1
        result = builder.create_bidirectional(
            source_id=args.source, target_id=args.target,
            relationship_type=args.type, dry_run=args.dry_run,
        )
        if args.output == "json":
            print(json.dumps({
                "source_id": result.source_id, "target_id": result.target_id,
                "forward_type": result.forward_type, "inverse_type": result.inverse_type,
                "forward_created": result.forward_created, "inverse_created": result.inverse_created,
            }, indent=2))
        else:
            print(f"Forward ({result.forward_type}): {'created' if result.forward_created else 'existed'}")
            print(f"Inverse ({result.inverse_type}): {'created' if result.inverse_created else 'existed'}")

    elif args.action == "check":
        if not args.type:
            print("Error: --type required for check")
            return 1
        inverse = builder.get_inverse_type(args.type)
        print(f"{args.type} <-> {inverse}")

    elif args.action == "merge":
        if not args.primary or not args.duplicate:
            print("Error: --primary and --duplicate required for merge")
            return 1
        result = builder.merge_entities(
            primary_id=args.primary, duplicate_id=args.duplicate, dry_run=args.dry_run,
        )
        if args.output == "json":
            print(json.dumps({
                "primary_id": result.primary_id, "duplicate_id": result.duplicate_id,
                "relationships_transferred": result.relationships_transferred,
                "aliases_merged": result.aliases_merged,
                "references_updated": result.references_updated,
                "body_appended": result.body_appended,
                "duplicate_deleted": result.duplicate_deleted,
                "error": result.error,
            }, indent=2))
        else:
            if result.error:
                print(f"Error: {result.error}")
                return 1
            print(f"Merge: {result.duplicate_id} -> {result.primary_id}")
            print(f"  Relationships transferred: {result.relationships_transferred}")
            print(f"  Aliases merged: {result.aliases_merged}")
            print(f"  References updated: {result.references_updated}")
            print(f"  Body appended: {result.body_appended}")
            print(f"  Duplicate deleted: {result.duplicate_deleted}")

    elif args.action == "detect-duplicates":
        candidates = builder.detect_duplicates(threshold=args.threshold)
        if args.output == "json":
            print(json.dumps(candidates, indent=2))
        else:
            print(f"Found {len(candidates)} potential duplicate pairs (threshold: {args.threshold}):\n")
            for c in candidates[:50]:  # Show top 50
                print(f"  {c['entity_a']}")
                print(f"    <-> {c['entity_b']}")
                print(f"    Confidence: {c['confidence']:.2f} | {c['reason']}")
                print()

    elif args.action == "batch-merge":
        if not args.manifest:
            print("Error: --manifest required for batch-merge")
            return 1
        with open(args.manifest) as f:
            manifest = json.load(f)
        pairs = [(m["primary"], m["duplicate"]) for m in manifest]
        print(f"Processing {len(pairs)} merge pairs (dry_run={args.dry_run})...")
        results = builder.batch_merge(pairs, dry_run=args.dry_run)
        success = sum(1 for r in results if not r.error)
        errors = sum(1 for r in results if r.error)
        rels = sum(r.relationships_transferred for r in results)
        aliases = sum(r.aliases_merged for r in results)
        refs = sum(r.references_updated for r in results)
        print(f"\nBatch merge complete:")
        print(f"  Success: {success}")
        print(f"  Errors: {errors}")
        print(f"  Total relationships transferred: {rels}")
        print(f"  Total aliases merged: {aliases}")
        print(f"  Total references updated: {refs}")
        if errors:
            for r in results:
                if r.error:
                    print(f"  ERROR: {r.duplicate_id} -> {r.primary_id}: {r.error}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
