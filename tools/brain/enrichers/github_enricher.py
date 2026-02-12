#!/usr/bin/env python3
"""
GitHub Enricher

Enriches Brain entities from GitHub commits, PRs, and issues.

Enhanced for bd-3771 Orphan Cleanup:
- enrich_orphans(): Specifically targets orphan system entities
- Creates bidirectional relationships via RelationshipBuilder
- Extracts owner, contributors, and dependency relationships
- Updates orphan_reason when enrichment fails

Story: bd-ce7e
"""

import os
import re
import subprocess
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
class GitHubOrphanResult:
    """Result of orphan enrichment attempt."""

    entity_id: str
    entity_type: str
    github_matches: int
    relationships_created: int
    enriched: bool
    reason: str


class GitHubEnricher(BaseEnricher):
    """
    Enricher for GitHub data.

    Processes GitHub commits, PRs, and issues to update
    related Brain entities with development activity.
    """

    # Source reliability for GitHub (high - code artifacts)
    SOURCE_RELIABILITY = 0.85

    @property
    def source_name(self) -> str:
        return "github"

    def enrich(self, item: Dict[str, Any], dry_run: bool = False) -> int:
        """
        Enrich entities from a GitHub item.

        Args:
            item: GitHub item (commit, PR, or issue)
            dry_run: If True, don't write changes

        Returns:
            Number of fields updated
        """
        fields_updated = 0

        # Determine item type
        item_type = self._determine_item_type(item)

        if item_type == "commit":
            return self._enrich_from_commit(item, dry_run)
        elif item_type == "pull_request":
            return self._enrich_from_pr(item, dry_run)
        elif item_type == "issue":
            return self._enrich_from_issue(item, dry_run)

        return fields_updated

    def _determine_item_type(self, item: Dict[str, Any]) -> str:
        """Determine the type of GitHub item."""
        if "sha" in item or "commit" in item:
            return "commit"
        elif "pull_request" in item or "merged_at" in item:
            return "pull_request"
        elif "number" in item and "body" in item:
            return "issue"
        return "unknown"

    def _enrich_from_commit(self, item: Dict[str, Any], dry_run: bool) -> int:
        """Enrich from a commit."""
        fields_updated = 0

        sha = item.get("sha", "")[:8]
        commit_data = item.get("commit", item)
        message = commit_data.get("message", "")
        author = commit_data.get("author", {})
        author_name = author.get("name", author.get("login", ""))
        author_email = author.get("email", "")
        date = author.get("date", item.get("created_at", ""))

        # Extract files changed
        files = item.get("files", [])
        files_changed = [f.get("filename", "") for f in files]

        # Combine text for entity extraction
        full_text = f"{message} {' '.join(files_changed)}"

        # Find mentioned entities
        mentioned_entities = self.extract_mentions(full_text)

        # Also find author entity
        if author_name:
            author_slug = self.find_entity_by_mention(author_name)
            if author_slug and author_slug not in mentioned_entities:
                mentioned_entities.append(author_slug)

        github_data = {
            "sha": sha,
            "message": message,
            "author": author_name,
            "date": date,
            "files": files_changed[:10],
            "type": "commit",
        }

        for entity_slug in mentioned_entities:
            entity_path = self.get_entity_path(entity_slug)
            if not entity_path:
                continue

            frontmatter, body = self.read_entity(entity_path)
            if not frontmatter:
                continue

            updates = self._generate_commit_updates(entity_slug, github_data)

            if updates:
                for field, value in updates.items():
                    if field.startswith("$"):
                        frontmatter[field] = value
                    fields_updated += 1

                self.append_event(
                    frontmatter,
                    event_type="enrichment",
                    message=f"Commit {sha}: {message[:40]}",
                    changes=[
                        {"field": k, "operation": "update", "value": str(v)[:100]}
                        for k, v in updates.items()
                    ],
                    correlation_id=f"github-commit-{sha}",
                )

                completeness = self._calculate_completeness(frontmatter)
                freshness_days = self._days_since(date)
                frontmatter["$confidence"] = self.calculate_confidence(
                    completeness, self.SOURCE_RELIABILITY, freshness_days
                )

                self.write_entity(entity_path, frontmatter, body, dry_run)

        return fields_updated

    def _enrich_from_pr(self, item: Dict[str, Any], dry_run: bool) -> int:
        """Enrich from a pull request."""
        fields_updated = 0

        pr_number = item.get("number", "")
        title = item.get("title", "")
        body = item.get("body", "") or ""
        state = item.get("state", "")
        merged = item.get("merged", False)
        user = item.get("user", {})
        user_name = user.get("login", "") if isinstance(user, dict) else ""
        created_at = item.get("created_at", "")
        merged_at = item.get("merged_at", "")
        labels = [l.get("name", "") for l in item.get("labels", [])]

        # Extract reviewers
        reviewers = item.get("requested_reviewers", [])
        reviewer_names = [r.get("login", "") for r in reviewers]

        full_text = f"{title} {body}"
        mentioned_entities = self.extract_mentions(full_text)

        if user_name:
            user_slug = self.find_entity_by_mention(user_name)
            if user_slug and user_slug not in mentioned_entities:
                mentioned_entities.append(user_slug)

        github_data = {
            "pr_number": pr_number,
            "title": title,
            "state": state,
            "merged": merged,
            "author": user_name,
            "reviewers": reviewer_names,
            "labels": labels,
            "created_at": created_at,
            "merged_at": merged_at,
            "type": "pull_request",
        }

        for entity_slug in mentioned_entities:
            entity_path = self.get_entity_path(entity_slug)
            if not entity_path:
                continue

            frontmatter, body_content = self.read_entity(entity_path)
            if not frontmatter:
                continue

            updates = self._generate_pr_updates(entity_slug, github_data)

            if updates:
                for field, value in updates.items():
                    if field.startswith("$"):
                        frontmatter[field] = value
                    fields_updated += 1

                self.append_event(
                    frontmatter,
                    event_type="enrichment",
                    message=f"PR #{pr_number}: {title[:40]}",
                    changes=[
                        {"field": k, "operation": "update", "value": str(v)[:100]}
                        for k, v in updates.items()
                    ],
                    correlation_id=f"github-pr-{pr_number}",
                )

                completeness = self._calculate_completeness(frontmatter)
                freshness_days = self._days_since(merged_at or created_at)
                frontmatter["$confidence"] = self.calculate_confidence(
                    completeness, self.SOURCE_RELIABILITY, freshness_days
                )

                self.write_entity(entity_path, frontmatter, body_content, dry_run)

        return fields_updated

    def _enrich_from_issue(self, item: Dict[str, Any], dry_run: bool) -> int:
        """Enrich from a GitHub issue."""
        fields_updated = 0

        issue_number = item.get("number", "")
        title = item.get("title", "")
        body = item.get("body", "") or ""
        state = item.get("state", "")
        user = item.get("user", {})
        user_name = user.get("login", "") if isinstance(user, dict) else ""
        created_at = item.get("created_at", "")
        closed_at = item.get("closed_at", "")
        labels = [l.get("name", "") for l in item.get("labels", [])]
        assignees = [a.get("login", "") for a in item.get("assignees", [])]

        full_text = f"{title} {body}"
        mentioned_entities = self.extract_mentions(full_text)

        github_data = {
            "issue_number": issue_number,
            "title": title,
            "state": state,
            "author": user_name,
            "assignees": assignees,
            "labels": labels,
            "created_at": created_at,
            "closed_at": closed_at,
            "type": "issue",
        }

        for entity_slug in mentioned_entities:
            entity_path = self.get_entity_path(entity_slug)
            if not entity_path:
                continue

            frontmatter, body_content = self.read_entity(entity_path)
            if not frontmatter:
                continue

            updates = self._generate_issue_updates(entity_slug, github_data)

            if updates:
                for field, value in updates.items():
                    if field.startswith("$"):
                        frontmatter[field] = value
                    fields_updated += 1

                self.append_event(
                    frontmatter,
                    event_type="enrichment",
                    message=f"Issue #{issue_number}: {title[:40]}",
                    changes=[
                        {"field": k, "operation": "update", "value": str(v)[:100]}
                        for k, v in updates.items()
                    ],
                    correlation_id=f"github-issue-{issue_number}",
                )

                completeness = self._calculate_completeness(frontmatter)
                freshness_days = self._days_since(closed_at or created_at)
                frontmatter["$confidence"] = self.calculate_confidence(
                    completeness, self.SOURCE_RELIABILITY, freshness_days
                )

                self.write_entity(entity_path, frontmatter, body_content, dry_run)

        return fields_updated

    def _generate_commit_updates(
        self, entity_slug: str, github_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate updates from commit data."""
        updates = {}

        updates["_github_activity"] = {
            "type": "commit",
            "sha": github_data.get("sha", ""),
            "date": github_data.get("date", ""),
            "author": github_data.get("author", ""),
        }

        # Extract project/component from files
        files = github_data.get("files", [])
        if files:
            components = self._extract_components_from_files(files)
            if components:
                updates["_github_components"] = components

        return updates

    def _generate_pr_updates(
        self, entity_slug: str, github_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate updates from PR data."""
        updates = {}

        updates["_github_pr"] = {
            "number": github_data.get("pr_number", ""),
            "title": github_data.get("title", "")[:100],
            "state": github_data.get("state", ""),
            "merged": github_data.get("merged", False),
        }

        labels = github_data.get("labels", [])
        if labels:
            updates["_github_labels"] = labels

        if github_data.get("merged"):
            updates["_has_shipped_code"] = True

        return updates

    def _generate_issue_updates(
        self, entity_slug: str, github_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate updates from issue data."""
        updates = {}

        updates["_github_issue"] = {
            "number": github_data.get("issue_number", ""),
            "title": github_data.get("title", "")[:100],
            "state": github_data.get("state", ""),
        }

        labels = github_data.get("labels", [])
        if labels:
            updates["_github_labels"] = labels

        # Check for bug/feature labels
        label_lower = [l.lower() for l in labels]
        if any("bug" in l for l in label_lower):
            updates["_has_open_bugs"] = github_data.get("state") == "open"

        return updates

    def _extract_components_from_files(self, files: List[str]) -> List[str]:
        """Extract component names from file paths."""
        components = set()

        for filepath in files:
            parts = filepath.split("/")
            if len(parts) > 1:
                # Use first meaningful directory
                for part in parts[:-1]:
                    if part not in ["src", "lib", "app", "test", "tests", "spec"]:
                        components.add(part)
                        break

        return list(components)[:5]

    def _calculate_completeness(self, frontmatter: Dict[str, Any]) -> float:
        """Calculate entity completeness score."""
        required_fields = ["$type", "$id", "$created"]
        optional_fields = [
            "$relationships",
            "$tags",
            "$aliases",
            "owner",
            "team",
            "tech_stack",
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
            date_str = date_str.replace("Z", "+00:00")
            if "T" in date_str:
                dt = datetime.fromisoformat(date_str)
            else:
                dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            return (datetime.now() - dt.replace(tzinfo=None)).days
        except (ValueError, TypeError):
            return 30

    # ===== bd-ce7e: Orphan Enrichment Methods =====

    def enrich_orphans(
        self,
        repos: Optional[List[str]] = None,
        entity_types: Optional[List[str]] = None,
        limit: int = 500,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Enrich orphan entities by searching GitHub for related data.

        Uses gh CLI to search repos for matches. Targets orphan entities
        and attempts to:
        1. Find matching GitHub repos/issues/PRs by name/alias
        2. Extract owner, contributors, dependency relationships
        3. Create bidirectional relationships via RelationshipBuilder
        4. Update orphan_reason based on results

        Args:
            repos: List of repos to search (default: org/web)
            entity_types: Filter by entity types (default: system, project)
            limit: Maximum orphans to process
            dry_run: If True, don't write changes

        Returns:
            Summary dict with counts and results
        """
        from relationship_builder import RelationshipBuilder

        target_types = entity_types or ["system", "project"]
        target_repos = repos or ["acme-corp/web"]

        results = {
            "total_orphans": 0,
            "processed": 0,
            "enriched": 0,
            "no_github_data": 0,
            "relationships_created": 0,
            "api_calls": 0,
            "details": [],
        }

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

            # Search GitHub for matches
            github_matches = self._search_github(entity_name, aliases, target_repos)
            results["api_calls"] += 1

            result = GitHubOrphanResult(
                entity_id=entity_id,
                entity_type=entity_type,
                github_matches=len(github_matches),
                relationships_created=0,
                enriched=False,
                reason="no_github_data" if not github_matches else "no_matches",
            )

            if github_matches:
                # Extract and create relationships from GitHub data
                rels_created = self._create_relationships_from_github(
                    entity_id,
                    entity_type,
                    github_matches,
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
                results["no_github_data"] += 1
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

            if entity_file.name.lower() in ("readme.md", "index.md", "_index.md"):
                continue
            if ".snapshots" in str(entity_file) or ".schema" in str(entity_file):
                continue

            frontmatter, body = self.read_entity(entity_file)
            if not frontmatter:
                continue

            entity_type = frontmatter.get("$type", "unknown")
            relationships = frontmatter.get("$relationships", [])

            if not relationships and entity_type in entity_types:
                orphans.append((entity_file, frontmatter, body))

        return orphans

    def _search_github(
        self,
        entity_name: str,
        aliases: List[str],
        repos: List[str],
    ) -> List[Dict[str, Any]]:
        """Search GitHub for matches using gh CLI."""
        matches = []
        search_terms = [entity_name] + [a for a in aliases if a]

        # Check for gh CLI
        gh_path = self._get_gh_path()
        if not gh_path:
            return matches

        for term in search_terms[:2]:  # Limit API calls
            if len(term) < 4:
                continue

            for repo in repos:
                try:
                    # Search PRs with term in title
                    result = subprocess.run(
                        [
                            gh_path,
                            "api",
                            f"search/issues?q=repo:{repo}+is:pr+{term}+in:title&per_page=5",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )

                    if result.returncode == 0 and result.stdout.strip():
                        import json

                        data = json.loads(result.stdout)
                        for item in data.get("items", []):
                            matches.append(
                                {
                                    "source": "pr",
                                    "repo": repo,
                                    "number": item.get("number"),
                                    "title": item.get("title", ""),
                                    "author": item.get("user", {}).get("login", ""),
                                    "state": item.get("state"),
                                    "url": item.get("html_url"),
                                }
                            )
                except Exception:
                    continue

        # Deduplicate
        seen = set()
        unique = []
        for m in matches:
            key = (m.get("repo"), m.get("number"))
            if key not in seen:
                seen.add(key)
                unique.append(m)

        return unique

    def _get_gh_path(self) -> Optional[str]:
        """Get path to gh CLI."""
        import shutil

        return shutil.which("gh")

    def _create_relationships_from_github(
        self,
        entity_id: str,
        entity_type: str,
        github_matches: List[Dict[str, Any]],
        builder: "RelationshipBuilder",
        dry_run: bool,
    ) -> int:
        """
        Create relationships from GitHub match data.

        Extracts:
        - maintainer (PR author → person entity)
        - contributor relationships
        """
        relationships_created = 0

        for match in github_matches:
            # Extract PR author → maintains/maintained_by relationship
            author = match.get("author", "")
            if author:
                author_entity = self.find_entity_by_mention(author)
                if author_entity and author_entity != entity_id:
                    rel_type = self._infer_relationship_type(
                        entity_type, "person", "contribution"
                    )
                    if not dry_run:
                        result = builder.create_bidirectional(
                            source_id=entity_id,
                            target_id=author_entity,
                            relationship_type=rel_type,
                            confidence=0.75,
                            source="github",
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
            ("system", "person", "contribution"): "maintained_by",
            ("person", "system", "contribution"): "maintains",
            ("project", "person", "contribution"): "has_contributor",
            ("person", "project", "contribution"): "works_on",
            ("system", "system", "dependency"): "depends_on",
        }

        key = (source_type, target_type, context)
        return type_map.get(key, "related_to")


def main():
    """CLI entry point for GitHub orphan enrichment."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Enrich orphan Brain entities from GitHub data"
    )
    parser.add_argument(
        "action",
        choices=["enrich-orphans"],
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
        "--repos",
        type=str,
        default="acme-corp/web",
        help="Repos to search (comma-separated)",
    )
    parser.add_argument(
        "--types",
        type=str,
        default="system,project",
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
    repos = [r.strip() for r in args.repos.split(",")]

    enricher = GitHubEnricher(args.brain_path)

    print(f"Enriching orphans from GitHub...")
    results = enricher.enrich_orphans(
        repos=repos,
        entity_types=entity_types,
        limit=args.limit,
        dry_run=args.dry_run,
    )

    # Print results
    action = "Would process" if args.dry_run else "Processed"
    print(f"\nGitHub Orphan Enrichment Results")
    print("=" * 50)
    print(f"Total orphans found: {results['total_orphans']}")
    print(f"{action}: {results['processed']}")
    print(f"Enriched (relationships created): {results['enriched']}")
    print(f"No GitHub data found: {results['no_github_data']}")
    print(f"Relationships created: {results['relationships_created']}")
    print(f"API calls made: {results['api_calls']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
