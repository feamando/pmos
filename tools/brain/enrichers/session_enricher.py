#!/usr/bin/env python3
"""
Session Enricher - Enriches Brain entities from Claude Code session research findings.

Processes research findings captured by Confucius during Claude Code sessions
and updates relevant Brain entities with the discovered knowledge.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add enrichers directory to path for base_enricher import
sys.path.insert(0, str(Path(__file__).parent))

# Add parent (brain tools) directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from base_enricher import BaseEnricher


class SessionEnricher(BaseEnricher):
    """
    Enriches Brain entities from Claude Code session research.

    Source reliability: 0.75 (higher than Slack at 0.65, lower than GDocs at 0.85)
    - Research from web sources is generally reliable but may be contextual
    - Competitive intelligence is time-sensitive
    """

    SOURCE_RELIABILITY = 0.75

    @property
    def source_name(self) -> str:
        return "session"

    def enrich(self, item: Dict[str, Any], dry_run: bool = False) -> int:
        """
        Enrich entities from a session research finding.

        Args:
            item: Research finding from session inbox
            dry_run: If True, don't write changes

        Returns:
            Number of entity fields updated
        """
        updates = 0

        # Extract key data from research finding
        finding_id = item.get("id", "unknown")
        title = item.get("title", "")
        finding = item.get("finding", "")
        category = item.get("category", "discovery")
        source_url = item.get("source", {}).get("url")
        confidence = item.get("confidence", "medium")
        related_entities = item.get("related_entities", [])
        timestamp = item.get("timestamp", datetime.now().isoformat())
        session_id = item.get("session_id", "unknown")

        # Process related entities
        for entity_ref in related_entities:
            canonical = self.find_entity_by_mention(entity_ref)
            if not canonical:
                # Entity doesn't exist - skip for now (could create in future)
                continue

            entity_path = self.get_entity_path(canonical)
            if not entity_path or not entity_path.exists():
                continue

            # Read entity (returns tuple of frontmatter, body)
            entity_data, body = self.read_entity(entity_path)
            if not entity_data:
                continue

            # Add research event to entity $events
            event = {
                "event_id": f"evt-session-{finding_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "timestamp": timestamp,
                "type": "research_discovery",
                "actor": f"system/{self.source_name}_enricher",
                "message": f"{title}: {finding[:200]}",
                "source": {
                    "session_id": session_id,
                    "finding_id": finding_id,
                    "category": category,
                    "url": source_url,
                },
                "confidence": confidence,
            }

            if "$events" not in entity_data:
                entity_data["$events"] = []

            entity_data["$events"].append(event)

            # Update $updated timestamp
            entity_data["$updated"] = datetime.now().isoformat()

            # Write back if not dry run
            if not dry_run:
                self.write_entity(entity_path, entity_data, body)
                updates += 1

        return updates

    def enrich_from_inbox(
        self, inbox_path: Path, dry_run: bool = False
    ) -> Dict[str, int]:
        """
        Process all research findings from the session inbox.

        Args:
            inbox_path: Path to ClaudeSession inbox directory
            dry_run: If True, don't write changes

        Returns:
            Stats dict with processed, updated, skipped counts
        """
        stats = {"processed": 0, "updated": 0, "skipped": 0, "errors": 0}

        raw_dir = inbox_path / "Raw"
        if not raw_dir.exists():
            return stats

        for json_file in raw_dir.glob("session_*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    findings = json.load(f)

                if not isinstance(findings, list):
                    findings = [findings]

                for item in findings:
                    stats["processed"] += 1

                    # Skip low-confidence findings by default
                    if item.get("confidence") == "low":
                        stats["skipped"] += 1
                        continue

                    updates = self.enrich(item, dry_run=dry_run)
                    stats["updated"] += updates

            except (json.JSONDecodeError, IOError) as e:
                print(f"Error processing {json_file}: {e}", file=sys.stderr)
                stats["errors"] += 1

        return stats


def main():
    """CLI entry point for session enricher."""
    import argparse

    parser = argparse.ArgumentParser(description="Enrich Brain from session research")
    parser.add_argument("--brain", type=str, help="Path to brain directory")
    parser.add_argument("--inbox", type=str, help="Path to ClaudeSession inbox")
    parser.add_argument("--dry-run", action="store_true", help="Don't write changes")

    args = parser.parse_args()

    # Default paths
    script_dir = Path(__file__).parent.parent.parent.parent.parent
    brain_path = Path(args.brain) if args.brain else script_dir / "user" / "brain"
    inbox_path = (
        Path(args.inbox) if args.inbox else brain_path / "Inbox" / "ClaudeSession"
    )

    enricher = SessionEnricher(brain_path)
    stats = enricher.enrich_from_inbox(inbox_path, dry_run=args.dry_run)

    print(f"Session Enrichment Complete:")
    print(f"  Processed: {stats['processed']}")
    print(f"  Updated:   {stats['updated']}")
    print(f"  Skipped:   {stats['skipped']}")
    print(f"  Errors:    {stats['errors']}")

    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
