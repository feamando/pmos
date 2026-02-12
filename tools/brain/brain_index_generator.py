#!/usr/bin/env python3
"""
PM-OS Brain Index Generator

Generates a compressed BRAIN.md index for agent context.
Two-source architecture: config for "who matters", entity files for relationship data.

Output: pipe-delimited compressed index (~8KB) with:
  - Tier 1: Team members (manager, reports, stakeholders) with full relationships
  - Tier 2: Connected entities (one-hop from Tier 1) + hot topics, compact format

Usage:
    python3 brain_index_generator.py                    # Generate to default path
    python3 brain_index_generator.py --output PATH      # Custom output path
    python3 brain_index_generator.py --brain-path PATH  # Custom brain directory
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import config_loader


class BrainIndexGenerator:
    """Generates compressed BRAIN.md index from config + entity files."""

    MAX_TIER2 = 120

    def __init__(self, brain_path: Optional[Path] = None):
        if brain_path is None:
            brain_path = config_loader.get_root_path() / "user" / "brain"
        self.brain_path = brain_path
        self.registry: Dict[str, Any] = {}
        self._load_registry()

    def _load_registry(self):
        """Load registry for ID-to-file mapping."""
        registry_file = self.brain_path / "registry.yaml"
        if registry_file.exists():
            with open(registry_file, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self.registry = data.get("entities", {})

    def _resolve_entity_path(self, entity_id: str) -> Optional[Path]:
        """Resolve entity ID to file path via registry."""
        # entity_id can be a registry key directly, or "entity/{type}/{slug}" format
        slug = entity_id
        if "/" in entity_id:
            # Extract slug from "entity/type/slug" format
            parts = entity_id.split("/")
            slug = parts[-1]

        entry = self.registry.get(slug)
        if entry and "$ref" in entry:
            return self.brain_path / entry["$ref"]

        # Try with common prefixes removed
        for key, entry in self.registry.items():
            if key == slug or key.endswith(slug):
                if "$ref" in entry:
                    return self.brain_path / entry["$ref"]

        return None

    def _parse_frontmatter(self, filepath: Path) -> Dict[str, Any]:
        """Parse YAML frontmatter from entity file."""
        if not filepath.exists():
            return {}
        try:
            content = filepath.read_text(encoding="utf-8")
            if not content.startswith("---"):
                return {}
            parts = content.split("---", 2)
            if len(parts) < 3:
                return {}
            return yaml.safe_load(parts[1]) or {}
        except Exception:
            return {}

    def _load_tier1_entities(self) -> List[Dict[str, Any]]:
        """
        Load Tier 1 entities: manager + direct reports + stakeholders + self.
        Merges config data (role, squad) with entity file data (relationships).
        """
        team_config = config_loader.get_team_config()
        user_config = config_loader.get_config().get("user", {})
        tier1 = []

        # Collect all team member configs
        members = []

        # Self
        user_id = user_config.get("name", "").lower().replace(" ", "-").replace("_", "-")
        if user_id:
            members.append({
                "id": user_id,
                "name": user_config.get("name", ""),
                "role": user_config.get("position", ""),
                "squad": "",
                "source": "self",
            })

        # Manager
        mgr = team_config.get("manager")
        if mgr:
            members.append({
                "id": mgr.get("id", ""),
                "name": mgr.get("name", ""),
                "role": mgr.get("role", ""),
                "squad": "",
                "source": "manager",
            })

        # Direct reports
        for report in team_config.get("reports", []):
            members.append({
                "id": report.get("id", ""),
                "name": report.get("name", ""),
                "role": report.get("role", ""),
                "squad": report.get("squad", ""),
                "source": "report",
            })

        # Stakeholders
        for sh in team_config.get("stakeholders", []):
            members.append({
                "id": sh.get("id", ""),
                "name": sh.get("name", ""),
                "role": sh.get("role", ""),
                "squad": "",
                "source": "stakeholder",
            })

        # For each member, load entity file for relationships
        seen_ids: Set[str] = set()
        for member in members:
            mid = member["id"]
            if not mid or mid in seen_ids:
                continue
            seen_ids.add(mid)

            entity_path = self._resolve_entity_path(mid)
            relationships = []
            entity_type = "person"

            if entity_path:
                fm = self._parse_frontmatter(entity_path)
                entity_type = fm.get("$type", "person")
                raw_rels = fm.get("$relationships", [])
                # Compress relationships: type:target pairs
                # Prioritize structural rels, filter noise
                skip_types = {"mentioned_in", "similar_to"}
                structural_types = {"reports_to", "manages", "member_of", "leads", "owns"}
                structural_rels = []
                other_rels = []
                for rel in raw_rels:
                    rel_type = rel.get("type", "related_to")
                    if rel_type in skip_types:
                        continue
                    target = rel.get("target", "")
                    if "/" in target:
                        target = target.split("/")[-1]
                    # Skip experiment entities (owns:exp-*)
                    if target.startswith("exp-"):
                        continue
                    confidence = rel.get("confidence", 1.0)
                    if confidence < 0.5:
                        continue
                    if target:
                        pair = f"{rel_type}:{target}"
                        if rel_type in structural_types:
                            structural_rels.append(pair)
                        else:
                            other_rels.append(pair)
                # Structural first, then others, capped at 12 total
                relationships = (structural_rels + other_rels)[:12]

            tier1.append({
                "id": mid,
                "name": member["name"],
                "type": entity_type,
                "role": member["role"] or "",
                "squad": member["squad"] or "",
                "status": "active",
                "relationships": relationships,
                "source": member["source"],
            })

        return tier1

    def _load_tier2_entities(self, tier1: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Load Tier 2: one-hop relationship targets from Tier 1 + hot topics.
        Compact format: id, type, name, status only.
        """
        tier1_ids = {e["id"] for e in tier1}
        tier2_ids: Set[str] = set()
        tier2 = []

        # Collect relationship targets from Tier 1
        for entity in tier1:
            for rel in entity.get("relationships", []):
                if ":" in rel:
                    target = rel.split(":", 1)[1]
                    if target and target not in tier1_ids and target not in tier2_ids:
                        tier2_ids.add(target)

        # Load hot topics from today's context
        hot_topic_ids = self._get_hot_topic_ids()
        for ht_id in hot_topic_ids:
            if ht_id not in tier1_ids and ht_id not in tier2_ids:
                tier2_ids.add(ht_id)

        # Resolve and load each Tier 2 entity (cap at MAX_TIER2)
        # Only include entities that exist in registry (skip unresolved references)
        for entity_id in sorted(tier2_ids):
            if len(tier2) >= self.MAX_TIER2:
                break

            entry = self.registry.get(entity_id, {})
            if not entry:
                continue  # Skip entities not in registry

            entity_type = entry.get("$type", "unknown")
            status = entry.get("$status", "active")
            name = entity_id.replace("-", " ").replace("_", " ").title()

            # Get name from file if available (but don't read ALL files — use registry $ref)
            ref = entry.get("$ref", "")
            if ref:
                entity_path = self.brain_path / ref
                if entity_path.exists():
                    fm = self._parse_frontmatter(entity_path)
                    name = fm.get("name", name)
                    entity_type = fm.get("$type", entity_type)
                    status = fm.get("$status", status)

            tier2.append({
                "id": entity_id,
                "type": entity_type,
                "name": name,
                "status": status,
            })

        return tier2

    def _get_hot_topic_ids(self) -> List[str]:
        """Get entity IDs from today's context via brain_loader scanning."""
        try:
            from brain_loader import build_alias_index, load_registry, scan_for_entities, get_latest_context_file

            registry = load_registry()
            if not registry:
                return []

            alias_index = build_alias_index(registry)
            context_file = get_latest_context_file()
            if not context_file:
                return []

            context_text = Path(context_file).read_text(encoding="utf-8")
            matches = scan_for_entities(context_text, alias_index)

            # Return entity IDs sorted by mention count (most mentioned first)
            sorted_entities = sorted(
                matches.items(), key=lambda x: x[1]["count"], reverse=True
            )
            return [eid for eid, _ in sorted_entities]

        except Exception:
            return []

    def _format_index(self, tier1: List[Dict], tier2: List[Dict]) -> str:
        """Format the compressed index as pipe-delimited markdown."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        total = len(tier1) + len(tier2)

        lines = [
            "# BRAIN.md — Entity Index",
            f"<!-- Generated: {now} | Entities: {total} | Tier1: {len(tier1)} | Tier2: {len(tier2)} -->",
            "",
            "## Team (Tier 1)",
            "id|type|role|squad|status|relationships",
        ]

        for e in tier1:
            rels = ",".join(e.get("relationships", []))
            line = f"{e['id']}|{e['type']}|{e.get('role', '')}|{e.get('squad', '')}|{e['status']}|{rels}"
            lines.append(line)

        lines.append("")
        lines.append("## Connected Entities (Tier 2)")
        lines.append("id|type|name|status")

        for e in tier2:
            line = f"{e['id']}|{e['type']}|{e['name']}|{e['status']}"
            lines.append(line)

        lines.append("")
        return "\n".join(lines)

    def generate(self) -> str:
        """Generate the complete BRAIN.md index."""
        tier1 = self._load_tier1_entities()
        tier2 = self._load_tier2_entities(tier1)
        return self._format_index(tier1, tier2)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate BRAIN.md compressed index")
    parser.add_argument("--brain-path", type=Path, help="Path to brain directory")
    parser.add_argument("--output", type=Path, help="Output file path")
    args = parser.parse_args()

    generator = BrainIndexGenerator(brain_path=args.brain_path)
    content = generator.generate()

    # Determine output path
    output_path = args.output
    if output_path is None:
        output_path = generator.brain_path / "BRAIN.md"

    output_path.write_text(content, encoding="utf-8")
    size_kb = len(content.encode("utf-8")) / 1024
    print(f"Generated {output_path} ({size_kb:.1f}KB)")


if __name__ == "__main__":
    main()
