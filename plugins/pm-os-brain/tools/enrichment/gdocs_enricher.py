#!/usr/bin/env python3
"""
Google Docs Enricher (v5.0)

Enriches Brain entities from Google Docs batch data.
Uses connector_bridge for Google authentication (three-tier auth).
Config-driven: credential paths from config_loader, no hardcoded paths.

Enhanced for orphan cleanup:
- enrich_orphans(): Targets orphan entities via GDrive API
- Creates bidirectional relationships via RelationshipBuilder
- Extracts stakeholders, teams, projects from documents
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .base_enricher import BaseEnricher
except ImportError:
    from base_enricher import BaseEnricher

try:
    from pm_os_base.tools.core.connector_bridge import get_auth
except ImportError:
    get_auth = None

try:
    from pm_os_base.tools.core.config_loader import get_config, get_google_paths
except ImportError:
    get_config = None
    get_google_paths = None

logger = logging.getLogger(__name__)


@dataclass
class GDocsOrphanResult:
    """Result of orphan enrichment attempt."""

    entity_id: str
    entity_type: str
    gdocs_matches: int
    relationships_created: int
    enriched: bool
    reason: str


class GDocsEnricher(BaseEnricher):
    """
    Enricher for Google Docs data.

    Processes batch-exported Google Docs content and updates
    related Brain entities with extracted information.

    Uses connector_bridge three-tier auth:
    - connector: Data comes from Claude connector
    - env: Direct API via Google OAuth token from .secrets/
    - none: Not configured
    """

    # Source reliability for GDocs (high - direct documentation)
    SOURCE_RELIABILITY = 0.85

    @property
    def source_name(self) -> str:
        return "gdocs"

    def enrich(self, item: Dict[str, Any], dry_run: bool = False) -> int:
        """
        Enrich entities from a Google Doc item.

        Args:
            item: GDocs batch item with content and metadata
            dry_run: If True, don't write changes

        Returns:
            Number of fields updated
        """
        fields_updated = 0

        # Extract document metadata
        doc_title = item.get("title", "")
        doc_content = item.get("content", "")
        doc_id = item.get("id", item.get("doc_id", ""))
        doc_url = item.get("url", "")
        modified_at = item.get("modified_at", item.get("modifiedTime", ""))

        if not doc_content:
            return 0

        # Find entities mentioned in the document
        mentioned_entities = self.extract_mentions(doc_content)

        # Determine document type and extract structured data
        doc_type = self._classify_document(doc_title, doc_content)
        extracted_data = self._extract_structured_data(doc_content, doc_type)

        for entity_slug in mentioned_entities:
            entity_path = self.get_entity_path(entity_slug)
            if not entity_path:
                continue

            frontmatter, body = self.read_entity(entity_path)
            if not frontmatter:
                continue

            # Update entity based on document type
            updates = self._generate_updates(
                entity_slug, doc_type, extracted_data, doc_title, doc_url
            )

            if updates:
                # Check for duplicate enrichment before applying
                corr_id = f"gdocs-{doc_id}"
                if self.has_existing_event_by_correlation(frontmatter, corr_id):
                    continue

                # Apply updates
                for field, value in updates.items():
                    if field.startswith("$"):
                        frontmatter[field] = value
                    fields_updated += 1

                # Add event log entry
                self.append_event(
                    frontmatter,
                    event_type="enrichment",
                    message=f"Enriched from GDoc: {doc_title[:50]}",
                    changes=[
                        {"field": k, "operation": "update", "value": str(v)[:100]}
                        for k, v in updates.items()
                    ],
                    correlation_id=corr_id,
                )

                # Update confidence
                completeness = self._calculate_completeness(frontmatter)
                freshness_days = self._days_since(modified_at)
                frontmatter["$confidence"] = self.calculate_confidence(
                    completeness, self.SOURCE_RELIABILITY, freshness_days
                )

                self.write_entity(entity_path, frontmatter, body, dry_run)

        return fields_updated

    def _classify_document(self, title: str, content: str) -> str:
        """Classify document type from title and content."""
        title_lower = title.lower()
        content_lower = content.lower()

        if any(kw in title_lower for kw in ["prd", "product requirement", "spec"]):
            return "prd"
        elif any(kw in title_lower for kw in ["rfc", "request for comment"]):
            return "rfc"
        elif any(
            kw in title_lower for kw in ["adr", "decision record", "architecture"]
        ):
            return "adr"
        elif any(kw in title_lower for kw in ["meeting", "notes", "standup"]):
            return "meeting_notes"
        elif any(kw in title_lower for kw in ["roadmap", "planning"]):
            return "roadmap"
        elif "1-pager" in title_lower or "one pager" in title_lower:
            return "one_pager"
        elif any(kw in content_lower for kw in ["objective", "key result", "okr"]):
            return "okr"
        else:
            return "general"

    def _extract_structured_data(self, content: str, doc_type: str) -> Dict[str, Any]:
        """Extract structured data based on document type."""
        data = {}

        if doc_type == "prd":
            data.update(self._extract_prd_data(content))
        elif doc_type == "meeting_notes":
            data.update(self._extract_meeting_data(content))
        elif doc_type == "okr":
            data.update(self._extract_okr_data(content))

        # Common extractions
        data["stakeholders"] = self._extract_stakeholders(content)
        data["dates"] = self._extract_dates(content)
        data["status"] = self._extract_status(content)

        return data

    def _extract_prd_data(self, content: str) -> Dict[str, Any]:
        """Extract PRD-specific data."""
        data = {}

        problem_match = re.search(
            r"(?:problem|challenge|issue)[:\s]+(.+?)(?:\n\n|\n#)",
            content,
            re.IGNORECASE | re.DOTALL,
        )
        if problem_match:
            data["problem_statement"] = problem_match.group(1).strip()[:500]

        metrics_match = re.search(
            r"(?:success metric|kpi|measure)[:\s]+(.+?)(?:\n\n|\n#)",
            content,
            re.IGNORECASE | re.DOTALL,
        )
        if metrics_match:
            data["success_metrics"] = metrics_match.group(1).strip()[:300]

        return data

    def _extract_meeting_data(self, content: str) -> Dict[str, Any]:
        """Extract meeting notes data."""
        data = {}

        action_items = re.findall(
            r"(?:action item|todo|task)[:\s]*(.+?)(?:\n|$)", content, re.IGNORECASE
        )
        if action_items:
            data["action_items"] = [item.strip() for item in action_items[:10]]

        decisions = re.findall(
            r"(?:decision|decided|agreed)[:\s]*(.+?)(?:\n|$)", content, re.IGNORECASE
        )
        if decisions:
            data["decisions"] = [d.strip() for d in decisions[:5]]

        return data

    def _extract_okr_data(self, content: str) -> Dict[str, Any]:
        """Extract OKR data."""
        data = {}

        objectives = re.findall(
            r"(?:objective|O\d)[:\s]*(.+?)(?:\n|$)", content, re.IGNORECASE
        )
        if objectives:
            data["objectives"] = [o.strip() for o in objectives[:5]]

        key_results = re.findall(
            r"(?:key result|KR\d)[:\s]*(.+?)(?:\n|$)", content, re.IGNORECASE
        )
        if key_results:
            data["key_results"] = [kr.strip() for kr in key_results[:10]]

        return data

    def _extract_stakeholders(self, content: str) -> List[str]:
        """Extract stakeholder mentions."""
        stakeholders = []

        owner_matches = re.findall(
            r"(?:owner|lead|responsible|assignee)[:\s]*([A-Z][a-z]+\s+[A-Z][a-z]+)",
            content,
            re.IGNORECASE,
        )
        stakeholders.extend(owner_matches)

        mentions = re.findall(r"@(\w+)", content)
        stakeholders.extend(mentions)

        return list(set(stakeholders))[:10]

    def _extract_dates(self, content: str) -> Dict[str, str]:
        """Extract date references."""
        dates = {}

        target_match = re.search(
            r"(?:target|deadline|due)[:\s]*(\d{4}-\d{2}-\d{2}|\w+\s+\d+,?\s*\d{4})",
            content,
            re.IGNORECASE,
        )
        if target_match:
            dates["target_date"] = target_match.group(1)

        start_match = re.search(
            r"(?:start|begin|kick.?off)[:\s]*(\d{4}-\d{2}-\d{2}|\w+\s+\d+,?\s*\d{4})",
            content,
            re.IGNORECASE,
        )
        if start_match:
            dates["start_date"] = start_match.group(1)

        return dates

    def _extract_status(self, content: str) -> Optional[str]:
        """Extract status from content."""
        status_match = re.search(
            r"(?:status)[:\s]*(draft|in.?progress|review|approved|completed|blocked)",
            content,
            re.IGNORECASE,
        )
        if status_match:
            return status_match.group(1).lower().replace(" ", "_")
        return None

    def _generate_updates(
        self,
        entity_slug: str,
        doc_type: str,
        extracted_data: Dict[str, Any],
        doc_title: str,
        doc_url: str,
    ) -> Dict[str, Any]:
        """Generate entity updates from extracted data."""
        updates = {}

        if doc_url:
            updates["_doc_ref"] = {"title": doc_title, "url": doc_url, "type": doc_type}

        stakeholders = extracted_data.get("stakeholders", [])
        if stakeholders:
            updates["_stakeholder_mentions"] = stakeholders

        dates = extracted_data.get("dates", {})
        for date_field, date_value in dates.items():
            updates[date_field] = date_value

        status = extracted_data.get("status")
        if status:
            updates["_doc_status"] = status

        return updates

    def _calculate_completeness(self, frontmatter: Dict[str, Any]) -> float:
        """Calculate entity completeness score."""
        required_fields = ["$type", "$id", "$created"]
        optional_fields = [
            "$relationships",
            "$tags",
            "$aliases",
            "role",
            "team",
            "owner",
            "description",
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
            if "T" in date_str:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            return (datetime.now() - dt.replace(tzinfo=None)).days
        except (ValueError, TypeError):
            return 30

    # ===== Orphan Enrichment Methods =====

    def enrich_orphans(
        self,
        entity_types: Optional[List[str]] = None,
        limit: int = 500,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Enrich orphan entities by searching Google Drive for related documents.

        Uses connector_bridge for auth:
        - connector: Data comes from Claude connector
        - env: Direct API via Google OAuth token
        - none: Not configured

        Args:
            entity_types: Filter by entity types
            limit: Maximum orphans to process
            dry_run: If True, don't write changes

        Returns:
            Summary dict with counts and results
        """
        try:
            from ..relationships.relationship_builder import RelationshipBuilder
        except ImportError:
            try:
                from relationships.relationship_builder import RelationshipBuilder
            except ImportError:
                logger.error("RelationshipBuilder not available")
                return {"error": "RelationshipBuilder not available"}

        target_types = entity_types or [
            "project",
            "person",
            "system",
            "team",
            "squad",
            "experiment",
        ]

        results = {
            "total_orphans": 0,
            "processed": 0,
            "enriched": 0,
            "no_gdocs_data": 0,
            "relationships_created": 0,
            "api_calls": 0,
            "details": [],
        }

        # Check auth via connector_bridge
        if get_auth is not None:
            auth = get_auth("google")
            if auth.source == "connector":
                logger.info("Google connector available, but orphan enrichment needs API access")
            elif auth.source == "none":
                logger.warning("Google not configured: %s", auth.help_message)
                return results

        # Initialize GDrive service
        drive_service = self._get_drive_service()
        if not drive_service:
            logger.warning("Could not initialize GDrive service")
            return results

        builder = RelationshipBuilder(self.brain_path)
        orphans = self._find_orphans(target_types, limit)
        results["total_orphans"] = len(orphans)

        for orphan_path, frontmatter, body in orphans:
            entity_id = frontmatter.get("$id", "")
            entity_type = frontmatter.get("$type", "unknown")
            entity_name = frontmatter.get("name", "")
            aliases = frontmatter.get("$aliases", [])

            gdocs_matches = self._search_gdrive(drive_service, entity_name, aliases)
            results["api_calls"] += 1

            result = GDocsOrphanResult(
                entity_id=entity_id,
                entity_type=entity_type,
                gdocs_matches=len(gdocs_matches),
                relationships_created=0,
                enriched=False,
                reason="no_gdocs_data" if not gdocs_matches else "no_matches",
            )

            if gdocs_matches:
                rels_created = self._create_relationships_from_gdocs(
                    entity_id, entity_type, gdocs_matches, builder, dry_run,
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
                results["no_gdocs_data"] += 1
                if not dry_run:
                    frontmatter["$orphan_reason"] = "no_external_data"
                    self.write_entity(orphan_path, frontmatter, body, dry_run=False)

            results["processed"] += 1
            results["details"].append(result)

            # Rate limit
            if results["api_calls"] % 10 == 0:
                import time
                time.sleep(0.5)

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

    def _get_drive_service(self):
        """Initialize Google Drive service using config-driven paths."""
        try:
            import os

            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            # Get token path from config_loader
            if get_google_paths is not None:
                google_paths = get_google_paths()
                token_file = google_paths["token"]
            else:
                # Fallback: look in user/.secrets/
                try:
                    from pm_os_base.tools.core.path_resolver import get_paths
                    paths = get_paths()
                    token_file = str(paths.user / ".secrets" / "token.json")
                except Exception:
                    token_file = ""

            if not token_file or not os.path.exists(token_file):
                return None

            SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)

            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(token_file, "w") as f:
                    f.write(creds.to_json())

            return build("drive", "v3", credentials=creds)
        except Exception as e:
            logger.warning("GDrive init error: %s", e)
            return None

    def _search_gdrive(
        self,
        service,
        entity_name: str,
        aliases: List[str],
    ) -> List[Dict[str, Any]]:
        """Search Google Drive for documents mentioning entity."""
        matches = []
        search_terms = [entity_name] + [a for a in aliases if a and len(a) > 3]

        for term in search_terms[:2]:
            if len(term) < 4:
                continue

            try:
                query = f"fullText contains '{term}' and mimeType='application/vnd.google-apps.document'"
                response = (
                    service.files()
                    .list(
                        q=query,
                        pageSize=5,
                        fields="files(id, name, owners, modifiedTime, webViewLink)",
                    )
                    .execute()
                )

                for doc in response.get("files", []):
                    owners = doc.get("owners", [])
                    owner_names = [o.get("displayName", "") for o in owners]

                    matches.append(
                        {
                            "source": "gdocs",
                            "doc_id": doc.get("id"),
                            "title": doc.get("name", ""),
                            "owners": owner_names,
                            "modified": doc.get("modifiedTime", ""),
                            "url": doc.get("webViewLink", ""),
                        }
                    )
            except Exception:
                continue

        # Deduplicate by doc_id
        seen = set()
        unique = []
        for m in matches:
            if m.get("doc_id") not in seen:
                seen.add(m.get("doc_id"))
                unique.append(m)

        return unique

    def _create_relationships_from_gdocs(
        self,
        entity_id: str,
        entity_type: str,
        gdocs_matches: List[Dict[str, Any]],
        builder,
        dry_run: bool,
    ) -> int:
        """Create relationships from GDocs match data."""
        relationships_created = 0

        for match in gdocs_matches:
            for owner_name in match.get("owners", []):
                if owner_name:
                    owner_entity = self.find_entity_by_mention(owner_name)
                    if owner_entity and owner_entity != entity_id:
                        rel_type = self._infer_relationship_type(
                            entity_type, "person", "authorship"
                        )
                        if not dry_run:
                            result = builder.create_bidirectional(
                                source_id=entity_id,
                                target_id=owner_entity,
                                relationship_type=rel_type,
                                confidence=0.7,
                                source="gdocs",
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
        """Infer appropriate relationship type."""
        type_map = {
            ("project", "person", "authorship"): "has_contributor",
            ("person", "project", "authorship"): "works_on",
            ("system", "person", "authorship"): "maintained_by",
            ("experiment", "person", "authorship"): "owned_by",
            ("team", "person", "authorship"): "has_member",
            ("squad", "person", "authorship"): "has_member",
        }

        key = (source_type, target_type, context)
        return type_map.get(key, "related_to")


def main():
    """CLI entry point for GDocs orphan enrichment."""
    import argparse
    import sys

    try:
        from pm_os_base.tools.core.path_resolver import get_paths
    except ImportError:
        get_paths = None

    parser = argparse.ArgumentParser(
        description="Enrich orphan Brain entities from Google Drive"
    )
    parser.add_argument(
        "action", choices=["enrich-orphans"], nargs="?",
        default="enrich-orphans", help="Action to perform",
    )
    parser.add_argument("--brain-path", type=Path, help="Path to brain directory")
    parser.add_argument(
        "--types", type=str, default="project,person,system,team,squad,experiment",
        help="Entity types to process (comma-separated)",
    )
    parser.add_argument("--limit", type=int, default=500, help="Maximum orphans to process")
    parser.add_argument("--dry-run", action="store_true", help="Preview without applying changes")

    args = parser.parse_args()

    if not args.brain_path:
        if get_paths is not None:
            try:
                paths = get_paths()
                args.brain_path = paths.brain
            except Exception:
                args.brain_path = Path.cwd() / "user" / "brain"
        else:
            args.brain_path = Path.cwd() / "user" / "brain"

    entity_types = [t.strip() for t in args.types.split(",")]
    enricher = GDocsEnricher(args.brain_path)

    logger.info("Enriching orphans from Google Drive...")
    results = enricher.enrich_orphans(
        entity_types=entity_types, limit=args.limit, dry_run=args.dry_run,
    )

    action = "Would process" if args.dry_run else "Processed"
    print(f"\nGDocs Orphan Enrichment Results")
    print("=" * 50)
    print(f"Total orphans found: {results.get('total_orphans', 0)}")
    print(f"{action}: {results.get('processed', 0)}")
    print(f"Enriched (relationships created): {results.get('enriched', 0)}")
    print(f"No GDocs data found: {results.get('no_gdocs_data', 0)}")
    print(f"Relationships created: {results.get('relationships_created', 0)}")
    print(f"API calls made: {results.get('api_calls', 0)}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
