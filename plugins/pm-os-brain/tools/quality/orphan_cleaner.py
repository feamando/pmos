#!/usr/bin/env python3
"""
PM-OS Brain Orphan Cleaner (v5)

Categorizes and cleans up orphan relationship targets.

Categories:
- auto_remove: Known placeholders (entity/unknown/*, nid, TBD)
- inbox_artifact: Inbox paths that are temporary
- likely_typo: Close matches to existing entities
- manual_review: Unknown references requiring human review

Version: 5.0.0
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

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

try:
    from pm_os_brain.tools.brain_core.event_helpers import EventHelper
except ImportError:
    try:
        from tools.core.event_helpers import EventHelper
    except ImportError:
        EventHelper = None

logger = logging.getLogger(__name__)


@dataclass
class OrphanTarget:
    """Represents an orphan relationship target."""

    source_entity: str
    source_path: Path
    target: str
    relationship_type: str
    category: str  # auto_remove, inbox_artifact, likely_typo, manual_review
    suggestion: Optional[str] = None  # Suggested correction
    confidence: float = 0.0


@dataclass
class CleanupResult:
    """Result of orphan cleanup."""

    total_orphans: int
    auto_removed: int
    inbox_removed: int
    typos_fixed: int
    manual_review: int
    entities_modified: int
    changes: List[Dict[str, Any]] = field(default_factory=list)


class OrphanCleaner:
    """
    Categorizes and cleans up orphan relationship targets.

    Categories:
    - auto_remove: Known placeholders (entity/unknown/*, nid, TBD)
    - inbox_artifact: Inbox paths that are temporary
    - likely_typo: Close matches to existing entities
    - manual_review: Unknown references requiring human review
    """

    # Patterns for auto-removal
    AUTO_REMOVE_PATTERNS = [
        r"^entity/unknown/.*$",
        r"^unknown$",
        r"^nid$",
        r"^TBD$",
        r"^tbd$",
        r"^TODO$",
        r"^todo$",
        r"^N/A$",
        r"^n/a$",
        r"^none$",
        r"^None$",
        r"^placeholder.*$",
        r"^test.*$",
        r"^example.*$",
    ]

    # Patterns for inbox artifacts
    INBOX_PATTERNS = [
        r"^Inbox/.*$",
        r"^inbox/.*$",
        r"^inbox-.*$",
        r".*\.inbox\..*$",
    ]

    def __init__(self, brain_path: Path):
        """
        Initialize the cleaner.

        Args:
            brain_path: Path to the brain directory
        """
        self.brain_path = brain_path

        # Initialize resolver if available
        self.resolver = None
        if CanonicalResolver is not None:
            try:
                self.resolver = CanonicalResolver(brain_path)
            except Exception as e:
                logger.warning("Failed to initialize CanonicalResolver: %s", e)

    def analyze_orphans(self) -> List[OrphanTarget]:
        """
        Analyze all entities and categorize orphan targets.

        Returns:
            List of OrphanTarget with categorization
        """
        if self.resolver is not None:
            self.resolver.build_index()

        orphans = []
        entity_files = list(self.brain_path.rglob("*.md"))
        entity_files = [
            f
            for f in entity_files
            if f.name.lower() not in ("readme.md", "index.md", "_index.md")
            and ".snapshots" not in str(f)
            and ".schema" not in str(f)
            and ".events" not in str(f)
        ]

        for entity_path in entity_files:
            entity_orphans = self._find_entity_orphans(entity_path)
            orphans.extend(entity_orphans)

        return orphans

    def _find_entity_orphans(self, entity_path: Path) -> List[OrphanTarget]:
        """Find orphan targets in a single entity."""
        orphans = []

        try:
            content = entity_path.read_text(encoding="utf-8")
            frontmatter = self._parse_frontmatter(content)
        except Exception:
            return []

        canonical_id = frontmatter.get("$id", str(entity_path))
        relationships = frontmatter.get("$relationships", [])

        for rel in relationships:
            if not isinstance(rel, dict):
                continue

            target = rel.get("target", "")
            rel_type = rel.get("type", "")

            if not target:
                continue

            # Check if resolvable
            resolved = self._resolve(target)
            if resolved:
                continue  # Not an orphan

            # Categorize the orphan
            category, suggestion, confidence = self._categorize_orphan(target)

            orphans.append(
                OrphanTarget(
                    source_entity=canonical_id,
                    source_path=entity_path,
                    target=target,
                    relationship_type=rel_type,
                    category=category,
                    suggestion=suggestion,
                    confidence=confidence,
                )
            )

        return orphans

    def _resolve(self, target: str) -> Optional[str]:
        """Resolve a reference using the canonical resolver if available."""
        if self.resolver is not None:
            return self.resolver.resolve(target)
        return None

    def _find_similar(
        self, target: str, max_results: int = 3
    ) -> List[Tuple[str, float]]:
        """Find similar references using the resolver if available."""
        if self.resolver is not None:
            return self.resolver.find_similar(target, max_results=max_results)
        return []

    def _categorize_orphan(
        self,
        target: str,
    ) -> Tuple[str, Optional[str], float]:
        """
        Categorize an orphan target.

        Returns:
            Tuple of (category, suggestion, confidence)
        """
        # Check auto-remove patterns
        for pattern in self.AUTO_REMOVE_PATTERNS:
            if re.match(pattern, target, re.IGNORECASE):
                return ("auto_remove", None, 1.0)

        # Check inbox patterns
        for pattern in self.INBOX_PATTERNS:
            if re.match(pattern, target, re.IGNORECASE):
                return ("inbox_artifact", None, 0.9)

        # Check for likely typos (fuzzy match)
        similar = self._find_similar(target, max_results=3)
        if similar:
            best_match, score = similar[0]
            if score > 0.7:
                return ("likely_typo", best_match, score)

        # Default to manual review
        return ("manual_review", None, 0.0)

    def cleanup(
        self,
        orphans: List[OrphanTarget],
        auto_remove: bool = True,
        remove_inbox: bool = True,
        fix_typos: bool = False,
        typo_confidence_threshold: float = 0.8,
        dry_run: bool = True,
    ) -> CleanupResult:
        """
        Clean up orphan targets based on their categories.

        Args:
            orphans: List of orphan targets to clean
            auto_remove: Remove auto-remove category orphans
            remove_inbox: Remove inbox artifact orphans
            fix_typos: Auto-fix likely typos
            typo_confidence_threshold: Minimum confidence for typo fixes
            dry_run: If True, don't write changes

        Returns:
            CleanupResult with summary
        """
        result = CleanupResult(
            total_orphans=len(orphans),
            auto_removed=0,
            inbox_removed=0,
            typos_fixed=0,
            manual_review=0,
            entities_modified=0,
        )

        # Group orphans by source entity
        by_entity: Dict[Path, List[OrphanTarget]] = {}
        for orphan in orphans:
            if orphan.source_path not in by_entity:
                by_entity[orphan.source_path] = []
            by_entity[orphan.source_path].append(orphan)

        # Process each entity
        for entity_path, entity_orphans in by_entity.items():
            changes_for_entity = []

            for orphan in entity_orphans:
                action = None

                if orphan.category == "auto_remove" and auto_remove:
                    action = "remove"
                    result.auto_removed += 1
                elif orphan.category == "inbox_artifact" and remove_inbox:
                    action = "remove"
                    result.inbox_removed += 1
                elif orphan.category == "likely_typo" and fix_typos:
                    if (
                        orphan.confidence >= typo_confidence_threshold
                        and orphan.suggestion
                    ):
                        action = "fix"
                        result.typos_fixed += 1
                    else:
                        result.manual_review += 1
                else:
                    result.manual_review += 1

                if action:
                    changes_for_entity.append(
                        {
                            "action": action,
                            "target": orphan.target,
                            "rel_type": orphan.relationship_type,
                            "suggestion": orphan.suggestion,
                        }
                    )
                    result.changes.append(
                        {
                            "entity": orphan.source_entity,
                            "action": action,
                            "target": orphan.target,
                            "suggestion": orphan.suggestion,
                        }
                    )

            # Apply changes to entity
            if changes_for_entity and not dry_run:
                self._apply_changes(entity_path, changes_for_entity)
                result.entities_modified += 1

        return result

    def _apply_changes(
        self,
        entity_path: Path,
        changes: List[Dict[str, Any]],
    ):
        """Apply cleanup changes to an entity."""
        try:
            content = entity_path.read_text(encoding="utf-8")
            frontmatter, body = self._parse_content(content)
        except Exception:
            return

        relationships = frontmatter.get("$relationships", [])
        new_relationships = []

        for rel in relationships:
            if not isinstance(rel, dict):
                new_relationships.append(rel)
                continue

            target = rel.get("target", "")
            rel_type = rel.get("type", "")

            # Check if this relationship should be changed
            change = None
            for c in changes:
                if c["target"] == target and c["rel_type"] == rel_type:
                    change = c
                    break

            if change:
                if change["action"] == "remove":
                    # Skip this relationship (remove it)
                    continue
                elif change["action"] == "fix" and change["suggestion"]:
                    # Fix the target
                    new_rel = dict(rel)
                    new_rel["target"] = change["suggestion"]
                    new_relationships.append(new_rel)
            else:
                new_relationships.append(rel)

        # Update frontmatter
        frontmatter["$relationships"] = new_relationships

        # Add cleanup event via EventHelper if available
        if EventHelper is not None:
            event = EventHelper.create_event(
                event_type="relationship_remove",
                actor="system/orphan_cleaner",
                changes=[
                    {
                        "field": "$relationships",
                        "operation": "remove",
                        "value": f"Cleaned {len(changes)} orphan reference(s)",
                    }
                ],
                message=f"Removed {len(changes)} orphan relationship(s)",
            )
            EventHelper.append_to_frontmatter(frontmatter, event)

        # Write back
        new_content = self._rebuild_content(frontmatter, body)
        entity_path.write_text(new_content, encoding="utf-8")

    def generate_report(
        self,
        orphans: List[OrphanTarget],
    ) -> str:
        """Generate a human-readable orphan report."""
        # Count by category
        by_category: Dict[str, List[OrphanTarget]] = {
            "auto_remove": [],
            "inbox_artifact": [],
            "likely_typo": [],
            "manual_review": [],
        }

        for orphan in orphans:
            by_category[orphan.category].append(orphan)

        lines = [
            "# Orphan Targets Report",
            "",
            f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "## Summary",
            "",
            "| Category | Count | Action |",
            "|----------|-------|--------|",
            f"| Auto-remove | {len(by_category['auto_remove'])} | Safe to remove |",
            f"| Inbox artifacts | {len(by_category['inbox_artifact'])} | Safe to remove |",
            f"| Likely typos | {len(by_category['likely_typo'])} | Review suggestions |",
            f"| Manual review | {len(by_category['manual_review'])} | Human decision |",
            f"| **Total** | {len(orphans)} | |",
            "",
        ]

        # Auto-remove section
        if by_category["auto_remove"]:
            lines.extend(
                [
                    "## Auto-Remove (Placeholders)",
                    "",
                    "These are placeholder targets that can be safely removed:",
                    "",
                ]
            )
            for orphan in by_category["auto_remove"][:20]:
                lines.append(f"- `{orphan.target}` in {orphan.source_entity}")
            if len(by_category["auto_remove"]) > 20:
                lines.append(f"- ... ({len(by_category['auto_remove']) - 20} more)")
            lines.append("")

        # Inbox artifacts section
        if by_category["inbox_artifact"]:
            lines.extend(
                [
                    "## Inbox Artifacts",
                    "",
                    "These reference temporary inbox items:",
                    "",
                ]
            )
            for orphan in by_category["inbox_artifact"][:20]:
                lines.append(f"- `{orphan.target}` in {orphan.source_entity}")
            if len(by_category["inbox_artifact"]) > 20:
                lines.append(f"- ... ({len(by_category['inbox_artifact']) - 20} more)")
            lines.append("")

        # Likely typos section
        if by_category["likely_typo"]:
            lines.extend(
                [
                    "## Likely Typos",
                    "",
                    "These appear to be typos with suggested corrections:",
                    "",
                    "| Target | Suggestion | Confidence | Source |",
                    "|--------|------------|------------|--------|",
                ]
            )
            for orphan in by_category["likely_typo"][:30]:
                lines.append(
                    f"| `{orphan.target}` | `{orphan.suggestion}` | "
                    f"{orphan.confidence:.0%} | {orphan.source_entity} |"
                )
            if len(by_category["likely_typo"]) > 30:
                lines.append(
                    f"| ... | | | ({len(by_category['likely_typo']) - 30} more) |"
                )
            lines.append("")

        # Manual review section
        if by_category["manual_review"]:
            lines.extend(
                [
                    "## Manual Review Required",
                    "",
                    "These orphans require human review:",
                    "",
                ]
            )
            for orphan in by_category["manual_review"][:50]:
                lines.append(
                    f"- `{orphan.target}` ({orphan.relationship_type}) "
                    f"in {orphan.source_entity}"
                )
            if len(by_category["manual_review"]) > 50:
                lines.append(f"- ... ({len(by_category['manual_review']) - 50} more)")
            lines.append("")

        return "\n".join(lines)

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

    def _rebuild_content(self, frontmatter: Dict[str, Any], body: str) -> str:
        """Rebuild file content from frontmatter and body."""
        yaml_content = yaml.dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
        return f"---\n{yaml_content}---{body}"
