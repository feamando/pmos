#!/usr/bin/env python3
"""
Context Enricher

Enriches Brain entities from daily context files.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_enricher import BaseEnricher


class ContextEnricher(BaseEnricher):
    """
    Enricher for daily context files.

    Processes daily context markdown files to update
    related Brain entities with activity and mentions.
    """

    # Source reliability for context (medium-high - curated daily notes)
    SOURCE_RELIABILITY = 0.75

    @property
    def source_name(self) -> str:
        return "context"

    def enrich(self, item: Dict[str, Any], dry_run: bool = False) -> int:
        """
        Enrich entities from a context file item.

        Args:
            item: Context item with content and metadata
            dry_run: If True, don't write changes

        Returns:
            Number of fields updated
        """
        fields_updated = 0

        # Extract context metadata
        content = item.get("content", "")
        date = item.get("date", "")
        filename = item.get("filename", "")

        if not content:
            return 0

        # Find entities mentioned in the context
        mentioned_entities = self.extract_mentions(content)

        # Extract structured data from context sections
        context_data = self._extract_context_data(content)

        for entity_slug in mentioned_entities:
            entity_path = self.get_entity_path(entity_slug)
            if not entity_path:
                continue

            frontmatter, body = self.read_entity(entity_path)
            if not frontmatter:
                continue

            # Generate updates based on context
            updates = self._generate_updates(entity_slug, context_data, date, content)

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
                    message=f"Mentioned in daily context: {date}",
                    changes=[
                        {"field": k, "operation": "update", "value": str(v)[:100]}
                        for k, v in updates.items()
                    ],
                    correlation_id=f"context-{date}",
                )

                # Update confidence
                completeness = self._calculate_completeness(frontmatter)
                freshness_days = self._days_since_date(date)
                frontmatter["$confidence"] = self.calculate_confidence(
                    completeness, self.SOURCE_RELIABILITY, freshness_days
                )

                self.write_entity(entity_path, frontmatter, body, dry_run)

        return fields_updated

    def _extract_context_data(self, content: str) -> Dict[str, Any]:
        """Extract structured data from context file."""
        data = {
            "key_decisions": [],
            "blockers": [],
            "action_items": [],
            "topics": [],
            "people_mentioned": [],
            "projects_mentioned": [],
        }

        lines = content.split("\n")
        current_section = None

        for line in lines:
            line_lower = line.lower().strip()

            # Detect sections
            if "key decision" in line_lower or "decision" in line_lower:
                current_section = "key_decisions"
            elif "blocker" in line_lower or "blocked" in line_lower:
                current_section = "blockers"
            elif (
                "action item" in line_lower
                or "todo" in line_lower
                or "next step" in line_lower
            ):
                current_section = "action_items"
            elif line.startswith("## ") or line.startswith("# "):
                current_section = None

            # Extract bullet points in sections
            if current_section and (
                line.strip().startswith("-") or line.strip().startswith("*")
            ):
                item = line.strip().lstrip("-*").strip()
                if item and len(item) > 5:
                    data[current_section].append(item[:200])

        # Extract topics from headers
        headers = re.findall(r"^##?\s+(.+)$", content, re.MULTILINE)
        data["topics"] = [h.strip() for h in headers[:10]]

        # Extract @mentions
        mentions = re.findall(r"@(\w+)", content)
        data["people_mentioned"] = list(set(mentions))

        # Extract [[wiki-links]]
        wiki_links = re.findall(r"\[\[([^\]]+)\]\]", content)
        data["projects_mentioned"] = list(set(wiki_links))

        return data

    def _generate_updates(
        self,
        entity_slug: str,
        context_data: Dict[str, Any],
        date: str,
        content: str,
    ) -> Dict[str, Any]:
        """Generate entity updates from context data."""
        updates = {}

        # Track context mention
        updates["_last_context_mention"] = {
            "date": date,
            "topics": context_data.get("topics", [])[:5],
        }

        # Check if entity has blockers mentioned
        blockers = context_data.get("blockers", [])
        entity_blockers = [
            b
            for b in blockers
            if entity_slug.replace("-", " ").lower() in b.lower()
            or entity_slug.replace("-", "_").lower() in b.lower()
        ]
        if entity_blockers:
            updates["_has_blocker"] = True
            updates["_blocker_details"] = entity_blockers[0][:150]

        # Check for decisions
        decisions = context_data.get("key_decisions", [])
        entity_decisions = [
            d
            for d in decisions
            if entity_slug.replace("-", " ").lower() in d.lower()
            or entity_slug.replace("-", "_").lower() in d.lower()
        ]
        if entity_decisions:
            updates["_recent_decision"] = entity_decisions[0][:150]

        # Check for action items
        action_items = context_data.get("action_items", [])
        entity_actions = [
            a
            for a in action_items
            if entity_slug.replace("-", " ").lower() in a.lower()
            or entity_slug.replace("-", "_").lower() in a.lower()
        ]
        if entity_actions:
            updates["_pending_actions"] = entity_actions[:3]

        # Count mentions for activity tracking
        slug_variants = [
            entity_slug,
            entity_slug.replace("-", " "),
            entity_slug.replace("-", "_"),
        ]
        mention_count = sum(content.lower().count(v.lower()) for v in slug_variants)
        if mention_count > 0:
            updates["_context_mention_count"] = mention_count

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

    def _days_since_date(self, date_str: str) -> int:
        """Calculate days since a date string."""
        if not date_str:
            return 30

        try:
            # Try YYYY-MM-DD format
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            return (datetime.now() - dt).days
        except (ValueError, TypeError):
            return 30
