#!/usr/bin/env python3
"""
Slack Enricher

Enriches Brain entities from Slack messages and threads.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_enricher import BaseEnricher


class SlackEnricher(BaseEnricher):
    """
    Enricher for Slack data.

    Processes Slack messages and threads to update
    related Brain entities with communication insights.
    """

    # Source reliability for Slack (medium - informal communication)
    SOURCE_RELIABILITY = 0.65

    @property
    def source_name(self) -> str:
        return "slack"

    def enrich(self, item: Dict[str, Any], dry_run: bool = False) -> int:
        """
        Enrich entities from a Slack message/thread.

        Args:
            item: Slack message item with content and metadata
            dry_run: If True, don't write changes

        Returns:
            Number of fields updated
        """
        fields_updated = 0

        # Extract message metadata
        text = item.get("text", "")
        channel = item.get("channel", item.get("channel_name", ""))
        user = item.get("user", item.get("user_name", ""))
        timestamp = item.get("ts", item.get("timestamp", ""))
        thread_ts = item.get("thread_ts", "")
        replies = item.get("replies", [])

        if not text:
            return 0

        # Combine message and replies for context
        full_text = text
        if replies:
            for reply in replies:
                reply_text = reply.get("text", "")
                if reply_text:
                    full_text += "\n" + reply_text

        # Find entities mentioned
        mentioned_entities = self.extract_mentions(full_text)

        # Extract communication patterns
        comm_data = self._extract_communication_data(full_text, channel, user)

        for entity_slug in mentioned_entities:
            entity_path = self.get_entity_path(entity_slug)
            if not entity_path:
                continue

            frontmatter, body = self.read_entity(entity_path)
            if not frontmatter:
                continue

            # Generate updates based on context
            updates = self._generate_updates(
                entity_slug, comm_data, channel, user, timestamp
            )

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
                    message=f"Mentioned in #{channel} by {user}",
                    changes=[
                        {"field": k, "operation": "update", "value": str(v)[:100]}
                        for k, v in updates.items()
                    ],
                    correlation_id=f"slack-{thread_ts or timestamp}",
                )

                # Update confidence
                completeness = self._calculate_completeness(frontmatter)
                freshness_days = self._days_since_ts(timestamp)
                frontmatter["$confidence"] = self.calculate_confidence(
                    completeness, self.SOURCE_RELIABILITY, freshness_days
                )

                self.write_entity(entity_path, frontmatter, body, dry_run)

        return fields_updated

    def _extract_communication_data(
        self, text: str, channel: str, user: str
    ) -> Dict[str, Any]:
        """Extract structured data from Slack communication."""
        data = {
            "channel": channel,
            "user": user,
            "mentions": [],
            "links": [],
            "sentiment": "neutral",
            "topics": [],
        }

        # Extract @mentions
        user_mentions = re.findall(r"<@(\w+)>", text)
        data["mentions"] = user_mentions

        # Extract links
        links = re.findall(r"<(https?://[^|>]+)(?:\|[^>]+)?>", text)
        data["links"] = links[:5]

        # Extract channel references
        channel_refs = re.findall(r"<#(\w+)(?:\|[^>]+)?>", text)
        data["channel_refs"] = channel_refs

        # Simple sentiment analysis
        data["sentiment"] = self._analyze_sentiment(text)

        # Extract topics from hashtags and keywords
        data["topics"] = self._extract_topics(text, channel)

        # Check for blockers/issues
        data["is_blocker"] = any(
            kw in text.lower()
            for kw in ["blocked", "blocker", "stuck", "help needed", "urgent"]
        )

        # Check for decisions
        data["is_decision"] = any(
            kw in text.lower()
            for kw in ["decided", "decision", "agreed", "let's go with", "approved"]
        )

        # Check for action items
        data["action_items"] = self._extract_action_items(text)

        return data

    def _analyze_sentiment(self, text: str) -> str:
        """Simple sentiment analysis."""
        text_lower = text.lower()

        positive_words = [
            "great",
            "awesome",
            "perfect",
            "excellent",
            "thanks",
            "good job",
            "nice",
            "love",
            "excited",
            "shipped",
        ]
        negative_words = [
            "issue",
            "problem",
            "bug",
            "broken",
            "failed",
            "blocked",
            "stuck",
            "urgent",
            "critical",
            "wrong",
        ]

        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        return "neutral"

    def _extract_topics(self, text: str, channel: str) -> List[str]:
        """Extract discussion topics."""
        topics = []

        # Add channel as topic
        if channel:
            topics.append(channel.replace("-", "_"))

        # Extract hashtags
        hashtags = re.findall(r"#(\w+)", text)
        topics.extend(hashtags)

        # Look for common topic keywords
        topic_keywords = {
            "launch": ["launch", "release", "ship", "deploy"],
            "bug": ["bug", "issue", "fix", "broken"],
            "feature": ["feature", "enhancement", "improvement"],
            "planning": ["planning", "roadmap", "sprint", "okr"],
            "review": ["review", "feedback", "pr", "code review"],
            "meeting": ["meeting", "standup", "sync", "1:1"],
        }

        text_lower = text.lower()
        for topic, keywords in topic_keywords.items():
            if any(kw in text_lower for kw in keywords):
                topics.append(topic)

        return list(set(topics))[:10]

    def _extract_action_items(self, text: str) -> List[str]:
        """Extract action items from message."""
        action_items = []

        # Look for checkbox patterns
        checkbox_items = re.findall(r"[\[\(][ x][\]\)]\s*(.+?)(?:\n|$)", text)
        action_items.extend(checkbox_items)

        # Look for "TODO" patterns
        todos = re.findall(r"(?:TODO|todo|To do)[:\s]*(.+?)(?:\n|$)", text)
        action_items.extend(todos)

        # Look for "@person will" patterns
        will_do = re.findall(r"<@\w+>\s+will\s+(.+?)(?:\n|$)", text, re.IGNORECASE)
        action_items.extend(will_do)

        return [item.strip() for item in action_items[:5]]

    def _generate_updates(
        self,
        entity_slug: str,
        comm_data: Dict[str, Any],
        channel: str,
        user: str,
        timestamp: str,
    ) -> Dict[str, Any]:
        """Generate entity updates from communication data."""
        updates = {}

        # Track communication activity
        updates["_last_slack_mention"] = {
            "channel": channel,
            "user": user,
            "timestamp": timestamp,
            "sentiment": comm_data.get("sentiment", "neutral"),
        }

        # If blocker detected, add to status
        if comm_data.get("is_blocker"):
            updates["_has_blocker"] = True
            updates["_blocker_source"] = f"slack:{channel}:{timestamp}"

        # If decision detected, log it
        if comm_data.get("is_decision"):
            updates["_recent_decision"] = True

        # Add topics as tags
        topics = comm_data.get("topics", [])
        if topics:
            updates["_slack_topics"] = topics

        # Add action items if present
        action_items = comm_data.get("action_items", [])
        if action_items:
            updates["_action_items"] = action_items

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
            "slack_handle",
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

    def _days_since_ts(self, timestamp: str) -> int:
        """Calculate days since a Slack timestamp."""
        if not timestamp:
            return 30

        try:
            # Slack timestamps are Unix epoch with decimal
            ts = float(timestamp.split(".")[0])
            dt = datetime.fromtimestamp(ts)
            return (datetime.now() - dt).days
        except (ValueError, TypeError):
            return 30
