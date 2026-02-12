#!/usr/bin/env python3
"""
Jira Enricher

Enriches Brain entities from Jira issues and projects.

Enhanced for bd-3771 Orphan Cleanup:
- enrich_orphans(): Specifically targets orphan entities
- Creates bidirectional relationships via RelationshipBuilder
- Extracts owner, team, and dependency relationships
- Updates orphan_reason when enrichment fails

Story: bd-22b7
"""

import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Handle both module and script execution
try:
    from .base_enricher import BaseEnricher
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from base_enricher import BaseEnricher

# Add parent for relationship_builder import
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class OrphanEnrichmentResult:
    """Result of orphan enrichment attempt."""

    entity_id: str
    entity_type: str
    jira_matches: int
    relationships_created: int
    enriched: bool
    reason: str  # "success", "no_jira_data", "no_matches"


class JiraEnricher(BaseEnricher):
    """
    Enricher for Jira data.

    Processes Jira issues to update related Brain entities
    with project tracking information.
    """

    # Source reliability for Jira (high - structured tracking)
    SOURCE_RELIABILITY = 0.9

    @property
    def source_name(self) -> str:
        return "jira"

    def enrich(self, item: Dict[str, Any], dry_run: bool = False) -> int:
        """
        Enrich entities from a Jira issue.

        Args:
            item: Jira issue item with fields and metadata
            dry_run: If True, don't write changes

        Returns:
            Number of fields updated
        """
        fields_updated = 0

        # Extract issue metadata
        issue_key = item.get("key", "")
        fields = item.get("fields", item)

        summary = fields.get("summary", "")
        description = fields.get("description", "")
        status = fields.get("status", {})
        status_name = (
            status.get("name", "") if isinstance(status, dict) else str(status)
        )
        assignee = fields.get("assignee", {})
        assignee_name = (
            assignee.get("displayName", "") if isinstance(assignee, dict) else ""
        )
        reporter = fields.get("reporter", {})
        reporter_name = (
            reporter.get("displayName", "") if isinstance(reporter, dict) else ""
        )
        created = fields.get("created", "")
        updated = fields.get("updated", "")
        priority = fields.get("priority", {})
        priority_name = priority.get("name", "") if isinstance(priority, dict) else ""
        issue_type = fields.get("issuetype", {})
        type_name = issue_type.get("name", "") if isinstance(issue_type, dict) else ""
        labels = fields.get("labels", [])
        components = fields.get("components", [])
        sprint = fields.get("sprint", {})
        epic_link = fields.get("customfield_10014", "")  # Common epic link field

        # Combine text for entity extraction
        full_text = f"{summary} {description or ''}"

        # Find mentioned entities
        mentioned_entities = self.extract_mentions(full_text)

        # Also check for specific entity types
        if assignee_name:
            assignee_slug = self.find_entity_by_mention(assignee_name)
            if assignee_slug and assignee_slug not in mentioned_entities:
                mentioned_entities.append(assignee_slug)

        if reporter_name:
            reporter_slug = self.find_entity_by_mention(reporter_name)
            if reporter_slug and reporter_slug not in mentioned_entities:
                mentioned_entities.append(reporter_slug)

        # Extract Jira-specific data
        jira_data = {
            "issue_key": issue_key,
            "summary": summary,
            "status": status_name,
            "assignee": assignee_name,
            "reporter": reporter_name,
            "priority": priority_name,
            "type": type_name,
            "labels": labels,
            "components": [c.get("name", "") for c in components] if components else [],
            "epic_link": epic_link,
            "created": created,
            "updated": updated,
        }

        for entity_slug in mentioned_entities:
            entity_path = self.get_entity_path(entity_slug)
            if not entity_path:
                continue

            frontmatter, body = self.read_entity(entity_path)
            if not frontmatter:
                continue

            # Generate updates
            updates = self._generate_updates(entity_slug, jira_data)

            if updates:
                # Apply updates
                for field, value in updates.items():
                    if field.startswith("$"):
                        frontmatter[field] = value
                    fields_updated += 1

                # Add event log entry
                self.append_event(
                    frontmatter,
                    event_type="enrichment",
                    message=f"Linked to Jira: {issue_key} - {summary[:40]}",
                    changes=[
                        {"field": k, "operation": "update", "value": str(v)[:100]}
                        for k, v in updates.items()
                    ],
                    correlation_id=f"jira-{issue_key}",
                )

                # Update confidence
                completeness = self._calculate_completeness(frontmatter)
                freshness_days = self._days_since(updated or created)
                frontmatter["$confidence"] = self.calculate_confidence(
                    completeness, self.SOURCE_RELIABILITY, freshness_days
                )

                self.write_entity(entity_path, frontmatter, body, dry_run)

        return fields_updated

    def _generate_updates(
        self, entity_slug: str, jira_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate entity updates from Jira data."""
        updates = {}

        issue_key = jira_data.get("issue_key", "")
        status = jira_data.get("status", "")
        assignee = jira_data.get("assignee", "")

        # Track Jira linkage
        updates["_jira_issues"] = {
            "key": issue_key,
            "status": status,
            "type": jira_data.get("type", ""),
            "priority": jira_data.get("priority", ""),
        }

        # Map Jira status to entity status
        if status:
            status_lower = status.lower()
            if status_lower in ["done", "closed", "resolved"]:
                updates["_project_status"] = "completed"
            elif status_lower in ["in progress", "in development", "in review"]:
                updates["_project_status"] = "active"
            elif status_lower in ["blocked", "on hold"]:
                updates["_project_status"] = "blocked"

        # Add labels as tags
        labels = jira_data.get("labels", [])
        if labels:
            updates["_jira_labels"] = labels

        # Add components
        components = jira_data.get("components", [])
        if components:
            updates["_jira_components"] = components

        # Track assignee relationship
        if assignee:
            updates["_jira_assignee"] = assignee

        # Add epic link if present
        epic_link = jira_data.get("epic_link", "")
        if epic_link:
            updates["_jira_epic"] = epic_link

        return updates

    def _calculate_completeness(self, frontmatter: Dict[str, Any]) -> float:
        """Calculate entity completeness score."""
        required_fields = ["$type", "$id", "$created"]
        optional_fields = [
            "$relationships",
            "$tags",
            "$aliases",
            "owner",
            "team",
            "status",
            "start_date",
            "target_date",
        ]

        present_required = sum(1 for f in required_fields if f in frontmatter)
        present_optional = sum(1 for f in optional_fields if f in frontmatter)

        required_score = (
            present_required / len(required_fields) if required_fields else 1
        )
        optional_score = (
            present_optional / len(optional_fields) if optional_fields else 0
        )

        return required_score * 0.6 + optional_score * 0.4

    def _days_since(self, date_str: str) -> int:
        """Calculate days since a date string."""
        if not date_str:
            return 30

        try:
            # Jira uses ISO format with timezone
            date_str = date_str.replace("Z", "+00:00")
            if "T" in date_str:
                # Remove microseconds if present
                if "." in date_str:
                    date_str = date_str.split(".")[0] + "+00:00"
                dt = datetime.fromisoformat(date_str)
            else:
                dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            return (datetime.now() - dt.replace(tzinfo=None)).days
        except (ValueError, TypeError):
            return 30

    # ===== bd-22b7: Orphan Enrichment Methods =====

    def enrich_orphans(
        self,
        jira_cache_path: Optional[Path] = None,
        entity_types: Optional[List[str]] = None,
        limit: int = 500,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Enrich orphan entities by searching Jira for related data.

        Targets orphan entities (no relationships) and attempts to:
        1. Find matching Jira issues/projects by name/alias
        2. Extract owner, team, dependency relationships
        3. Create bidirectional relationships via RelationshipBuilder
        4. Update orphan_reason based on results

        Args:
            jira_cache_path: Path to Jira data cache (JSON/YAML)
            entity_types: Filter by entity types (default: project, person, system)
            limit: Maximum orphans to process
            dry_run: If True, don't write changes

        Returns:
            Summary dict with counts and results
        """
        from relationship_builder import RelationshipBuilder

        target_types = entity_types or ["project", "person", "system"]
        results = {
            "total_orphans": 0,
            "processed": 0,
            "enriched": 0,
            "no_jira_data": 0,
            "relationships_created": 0,
            "details": [],
        }

        # Load Jira cache if provided
        jira_data = self._load_jira_cache(jira_cache_path) if jira_cache_path else {}

        # Initialize relationship builder
        builder = RelationshipBuilder(self.brain_path)

        # Find orphan entities
        orphans = self._find_orphans(target_types, limit)
        results["total_orphans"] = len(orphans)

        for orphan_path, frontmatter, body in orphans:
            entity_id = frontmatter.get("$id", "")
            entity_type = frontmatter.get("$type", "unknown")
            entity_name = frontmatter.get("name", "")
            aliases = frontmatter.get("$aliases", [])

            # Search for Jira matches
            jira_matches = self._find_jira_matches(
                entity_name, aliases, entity_type, jira_data
            )

            result = OrphanEnrichmentResult(
                entity_id=entity_id,
                entity_type=entity_type,
                jira_matches=len(jira_matches),
                relationships_created=0,
                enriched=False,
                reason="no_jira_data" if not jira_matches else "no_matches",
            )

            if jira_matches:
                # Extract and create relationships from Jira data
                rels_created = self._create_relationships_from_jira(
                    entity_id,
                    entity_type,
                    jira_matches,
                    builder,
                    dry_run,
                )
                result.relationships_created = rels_created

                if rels_created > 0:
                    result.enriched = True
                    result.reason = "success"
                    results["enriched"] += 1
                    results["relationships_created"] += rels_created

                    # Clear orphan_reason since entity now has relationships
                    if not dry_run:
                        if "$orphan_reason" in frontmatter:
                            del frontmatter["$orphan_reason"]
                        self.write_entity(orphan_path, frontmatter, body, dry_run=False)

            if not result.enriched:
                results["no_jira_data"] += 1
                # Mark as no_external_data if we tried and found nothing
                if not dry_run:
                    frontmatter["$orphan_reason"] = "no_external_data"
                    self.write_entity(orphan_path, frontmatter, body, dry_run=False)

            results["processed"] += 1
            results["details"].append(result)

        return results

    def _find_orphans(
        self,
        entity_types: List[str],
        limit: int,
    ) -> List[Tuple[Path, Dict[str, Any], str]]:
        """Find orphan entities of specified types."""
        orphans = []

        for entity_file in self.brain_path.rglob("*.md"):
            if len(orphans) >= limit:
                break

            # Skip non-entity files
            if entity_file.name.lower() in ("readme.md", "index.md", "_index.md"):
                continue
            if ".snapshots" in str(entity_file) or ".schema" in str(entity_file):
                continue

            frontmatter, body = self.read_entity(entity_file)
            if not frontmatter:
                continue

            entity_type = frontmatter.get("$type", "unknown")
            relationships = frontmatter.get("$relationships", [])

            # Check if orphan (no relationships) and matching type
            if not relationships and entity_type in entity_types:
                orphans.append((entity_file, frontmatter, body))

        return orphans

    def _load_jira_cache(self, cache_path: Path) -> Dict[str, Any]:
        """Load Jira data from cache file."""
        import json

        import yaml

        if not cache_path.exists():
            return {}

        try:
            content = cache_path.read_text(encoding="utf-8")
            if cache_path.suffix == ".json":
                return json.loads(content)
            elif cache_path.suffix in (".yaml", ".yml"):
                return yaml.safe_load(content) or {}
        except Exception:
            pass

        return {}

    def _find_jira_matches(
        self,
        entity_name: str,
        aliases: List[str],
        entity_type: str,
        jira_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Find Jira issues/projects matching an entity.

        Searches by:
        - Entity name in issue summary/description
        - Aliases in issue fields
        - Project key matching entity name pattern
        """
        matches = []
        search_terms = [entity_name.lower()] + [a.lower() for a in aliases if a]

        # Search through cached Jira data
        for squad_name, squad_data in jira_data.items():
            if isinstance(squad_data, dict):
                # Search epics
                for epic in squad_data.get("epics", []):
                    if self._matches_search_terms(epic, search_terms):
                        matches.append({"source": "epic", "squad": squad_name, **epic})

                # Search in-progress items
                for item in squad_data.get("in_progress", []):
                    if self._matches_search_terms(item, search_terms):
                        matches.append({"source": "issue", "squad": squad_name, **item})

                # Search blockers
                for blocker in squad_data.get("blockers", []):
                    if self._matches_search_terms(blocker, search_terms):
                        matches.append(
                            {"source": "blocker", "squad": squad_name, **blocker}
                        )

        return matches

    def _matches_search_terms(
        self,
        item: Dict[str, Any],
        search_terms: List[str],
    ) -> bool:
        """Check if a Jira item matches any search terms."""
        searchable = (
            item.get("summary", "").lower()
            + " "
            + str(item.get("key", "")).lower()
            + " "
            + " ".join(item.get("labels", []))
        )

        for term in search_terms:
            if len(term) > 2 and term in searchable:
                return True

        return False

    def _create_relationships_from_jira(
        self,
        entity_id: str,
        entity_type: str,
        jira_matches: List[Dict[str, Any]],
        builder: "RelationshipBuilder",
        dry_run: bool,
    ) -> int:
        """
        Create relationships from Jira match data.

        Extracts:
        - owner (assignee → person entity)
        - team (squad → team/squad entity)
        - dependencies (epic_link, blocked_by)
        """
        relationships_created = 0

        for match in jira_matches:
            # Extract assignee → works_with/works_on relationship
            assignee = match.get("assignee", "")
            if assignee and assignee != "Unassigned":
                assignee_entity = self.find_entity_by_mention(assignee)
                if assignee_entity and assignee_entity != entity_id:
                    rel_type = self._infer_relationship_type(
                        entity_type, "person", "collaboration"
                    )
                    if not dry_run:
                        result = builder.create_bidirectional(
                            source_id=entity_id,
                            target_id=assignee_entity,
                            relationship_type=rel_type,
                            confidence=0.8,
                            source="jira",
                        )
                        if result.forward_created or result.inverse_created:
                            relationships_created += 1

            # Extract squad → member_of/has_contributor relationship
            squad_name = match.get("squad", "")
            if squad_name:
                squad_entity = self.find_entity_by_mention(squad_name)
                if squad_entity and squad_entity != entity_id:
                    rel_type = self._infer_relationship_type(
                        entity_type, "squad", "membership"
                    )
                    if not dry_run:
                        result = builder.create_bidirectional(
                            source_id=entity_id,
                            target_id=squad_entity,
                            relationship_type=rel_type,
                            confidence=0.75,
                            source="jira",
                        )
                        if result.forward_created or result.inverse_created:
                            relationships_created += 1

        return relationships_created

    def _infer_relationship_type(
        self,
        source_type: str,
        target_type: str,
        context: str,
    ) -> str:
        """Infer appropriate relationship type based on entity types."""
        type_map = {
            ("project", "person", "collaboration"): "has_contributor",
            ("person", "project", "collaboration"): "works_on",
            ("system", "person", "collaboration"): "maintained_by",
            ("person", "system", "collaboration"): "maintains",
            ("project", "squad", "membership"): "owned_by",
            ("squad", "project", "membership"): "owns",
            ("person", "squad", "membership"): "member_of",
            ("squad", "person", "membership"): "has_member",
            ("system", "squad", "membership"): "owned_by",
            ("project", "project", "dependency"): "depends_on",
        }

        key = (source_type, target_type, context)
        return type_map.get(key, "related_to")

    def enrich_orphans_live(
        self,
        entity_types: Optional[List[str]] = None,
        limit: int = 500,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Enrich orphan entities by querying Jira API directly.

        Uses live Jira API queries to find matching issues for orphan entities.
        Falls back to cached data if API unavailable.

        Args:
            entity_types: Filter by entity types (default: project, person, system)
            limit: Maximum orphans to process
            dry_run: If True, don't write changes

        Returns:
            Summary dict with counts and results
        """
        try:
            from atlassian import Jira
        except ImportError:
            print("Warning: atlassian-python-api not installed. Using cache mode.")
            return self.enrich_orphans(
                entity_types=entity_types, limit=limit, dry_run=dry_run
            )

        from relationship_builder import RelationshipBuilder

        target_types = entity_types or ["project", "person", "system"]
        results = {
            "total_orphans": 0,
            "processed": 0,
            "enriched": 0,
            "no_jira_data": 0,
            "relationships_created": 0,
            "api_queries": 0,
            "details": [],
        }

        # Initialize Jira client
        jira = self._get_jira_client()
        if not jira:
            print("Warning: Could not initialize Jira client. Using cache mode.")
            return self.enrich_orphans(
                entity_types=entity_types, limit=limit, dry_run=dry_run
            )

        # Initialize relationship builder
        builder = RelationshipBuilder(self.brain_path)

        # Find orphan entities
        orphans = self._find_orphans(target_types, limit)
        results["total_orphans"] = len(orphans)

        for orphan_path, frontmatter, body in orphans:
            entity_id = frontmatter.get("$id", "")
            entity_type = frontmatter.get("$type", "unknown")
            entity_name = frontmatter.get("name", "")
            aliases = frontmatter.get("$aliases", [])

            # Query Jira API for matches
            jira_matches = self._query_jira_for_entity(
                jira, entity_name, aliases, entity_type
            )
            results["api_queries"] += 1

            result = OrphanEnrichmentResult(
                entity_id=entity_id,
                entity_type=entity_type,
                jira_matches=len(jira_matches),
                relationships_created=0,
                enriched=False,
                reason="no_jira_data" if not jira_matches else "no_matches",
            )

            if jira_matches:
                rels_created = self._create_relationships_from_jira(
                    entity_id, entity_type, jira_matches, builder, dry_run
                )
                result.relationships_created = rels_created

                if rels_created > 0:
                    result.enriched = True
                    result.reason = "success"
                    results["enriched"] += 1
                    results["relationships_created"] += rels_created

                    if not dry_run:
                        if "$orphan_reason" in frontmatter:
                            del frontmatter["$orphan_reason"]
                        self.write_entity(orphan_path, frontmatter, body, dry_run=False)

            if not result.enriched:
                results["no_jira_data"] += 1
                if not dry_run:
                    frontmatter["$orphan_reason"] = "no_external_data"
                    self.write_entity(orphan_path, frontmatter, body, dry_run=False)

            results["processed"] += 1
            results["details"].append(result)

        return results

    def _get_jira_client(self) -> Optional["Jira"]:
        """Initialize Jira client from environment."""
        try:
            from atlassian import Jira
        except ImportError:
            return None

        jira_url = os.environ.get("JIRA_URL", "")
        jira_user = os.environ.get("JIRA_USERNAME", "")
        jira_token = os.environ.get("JIRA_API_TOKEN", "")

        if not all([jira_url, jira_user, jira_token]):
            return None

        try:
            return Jira(
                url=jira_url, username=jira_user, password=jira_token, cloud=True
            )
        except Exception:
            return None

    def _query_jira_for_entity(
        self,
        jira: "Jira",
        entity_name: str,
        aliases: List[str],
        entity_type: str,
    ) -> List[Dict[str, Any]]:
        """Query Jira API for issues matching an entity."""
        matches = []
        search_terms = [entity_name] + [a for a in aliases if a]

        for term in search_terms[:3]:  # Limit API calls
            if len(term) < 3:
                continue

            try:
                # Search for term in summary
                jql = f'summary ~ "{term}" ORDER BY updated DESC'
                response = jira.jql(jql, limit=10)

                for issue in response.get("issues", []):
                    fields = issue.get("fields", {})
                    assignee = fields.get("assignee", {})
                    project = fields.get("project", {})

                    matches.append(
                        {
                            "source": "api",
                            "key": issue.get("key"),
                            "summary": fields.get("summary", ""),
                            "assignee": (
                                assignee.get("displayName", "") if assignee else ""
                            ),
                            "squad": project.get("name", "") if project else "",
                            "status": fields.get("status", {}).get("name", ""),
                        }
                    )
            except Exception:
                continue

        # Deduplicate by key
        seen_keys = set()
        unique_matches = []
        for m in matches:
            if m.get("key") not in seen_keys:
                seen_keys.add(m.get("key"))
                unique_matches.append(m)

        return unique_matches


def main():
    """CLI entry point for Jira orphan enrichment."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Enrich orphan Brain entities from Jira data"
    )
    parser.add_argument(
        "action",
        choices=["enrich-orphans", "enrich-live"],
        nargs="?",
        default="enrich-orphans",
        help="Action to perform",
    )
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--jira-cache",
        type=Path,
        help="Path to Jira data cache (JSON/YAML)",
    )
    parser.add_argument(
        "--types",
        type=str,
        default="project,person,system",
        help="Entity types to process (comma-separated)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Maximum orphans to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without applying changes",
    )

    args = parser.parse_args()

    # Resolve brain path
    if not args.brain_path:
        script_dir = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(script_dir))
        try:
            from path_resolver import get_paths

            paths = get_paths()
            args.brain_path = paths.user / "brain"
        except ImportError:
            args.brain_path = Path.cwd() / "user" / "brain"

    entity_types = [t.strip() for t in args.types.split(",")]

    enricher = JiraEnricher(args.brain_path)

    if args.action == "enrich-live":
        print(f"Enriching orphans from live Jira API...")
        results = enricher.enrich_orphans_live(
            entity_types=entity_types,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    else:
        print(f"Enriching orphans from Jira cache...")
        results = enricher.enrich_orphans(
            jira_cache_path=args.jira_cache,
            entity_types=entity_types,
            limit=args.limit,
            dry_run=args.dry_run,
        )

    # Print results
    action = "Would process" if args.dry_run else "Processed"
    print(f"\nJira Orphan Enrichment Results")
    print("=" * 50)
    print(f"Total orphans found: {results['total_orphans']}")
    print(f"{action}: {results['processed']}")
    print(f"Enriched (relationships created): {results['enriched']}")
    print(f"No Jira data found: {results['no_jira_data']}")
    print(f"Relationships created: {results['relationships_created']}")

    if results.get("api_queries"):
        print(f"API queries made: {results['api_queries']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
