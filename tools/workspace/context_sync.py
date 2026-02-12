#!/usr/bin/env python3
"""
PM-OS Context Sync

Bi-directional synchronization between brain entities and workspace context files.

Brain -> Context: Populates context files with entity data
Context -> Brain: Updates brain entities with context file changes

Usage:
    python3 context_sync.py --sync             # Full bi-directional sync
    python3 context_sync.py --brain-to-context # Brain populates context files
    python3 context_sync.py --context-to-brain # Context files update brain
    python3 context_sync.py --status           # Show sync status

Author: PM-OS Team
Version: 1.0.0
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_loader


class ContextSync:
    """Synchronizes brain entities with workspace context files."""

    def __init__(self, user_path: Optional[Path] = None):
        """Initialize context sync."""
        config = config_loader.get_config()
        self.user_path = user_path or config.user_path
        if self.user_path is None:
            raise ValueError("Could not determine user path")

        self.brain_path = self.user_path / "brain"
        self.products_path = self.user_path / "products"
        self.team_path = self.user_path / "team"
        self.personal_path = self.user_path / "personal"

        # Brain entity paths - entities are directly in Entities/ folder
        self.entities_path = self.brain_path / "Entities"
        # Legacy subfolders (some installs have these)
        self.people_path = self.entities_path / "People"
        self.brands_path = self.entities_path / "Brands"
        self.squads_path = self.entities_path / "Squads"
        self.registry_path = self.brain_path / "registry.yaml"

    def sync_brain_to_context(self) -> Dict[str, Any]:
        """
        Populate context files with data from brain entities.

        Returns:
            Dict with sync results.
        """
        result = {"updated_products": [], "updated_people": [], "errors": []}

        # Sync product context files
        result["updated_products"] = self._sync_products_from_brain()

        # Sync team context files
        result["updated_people"] = self._sync_team_from_brain()

        return result

    def _sync_products_from_brain(self) -> List[str]:
        """Sync product context files with brand entities."""
        updated = []

        for product in config_loader.get_products_config().get("items", []):
            product_id = product.get("id")
            product_name = product.get("name", "")

            if not product_id:
                continue

            # Find brain entity for this product
            brain_data = self._load_brand_entity(product_name)

            # Get context file path
            org_config = config_loader.get_organization_config()
            if org_config:
                context_path = (
                    self.products_path
                    / org_config["id"]
                    / product_id
                    / f"{product_id}-context.md"
                )
            else:
                context_path = (
                    self.products_path / product_id / f"{product_id}-context.md"
                )

            if context_path.exists() and brain_data:
                updated_content = self._update_product_context(
                    context_path, brain_data, product
                )
                if updated_content:
                    context_path.write_text(updated_content, encoding="utf-8")
                    updated.append(str(context_path))

        return updated

    def _load_brand_entity(self, brand_name: str) -> Optional[Dict[str, Any]]:
        """Load brain entity for a brand."""
        if not self.brands_path.exists():
            return None

        # Try various name formats
        name_variants = [
            brand_name,
            brand_name.replace(" ", "_"),
            brand_name.replace(" ", "-"),
            brand_name.replace(" ", ""),
        ]

        for variant in name_variants:
            entity_path = self.brands_path / f"{variant}.md"
            if entity_path.exists():
                return self._parse_brain_entity(entity_path)

        return None

    def _parse_brain_entity(self, path: Path) -> Dict[str, Any]:
        """Parse a brain entity markdown file."""
        content = path.read_text(encoding="utf-8")
        data = {"path": str(path), "raw_content": content}

        # Extract frontmatter if present
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    data["frontmatter"] = yaml.safe_load(parts[1])
                except:
                    pass
                data["body"] = parts[2].strip()

        # Extract key sections
        sections = {}
        current_section = None
        current_content = []

        for line in content.split("\n"):
            if line.startswith("## "):
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = line[3:].strip()
                current_content = []
            elif current_section:
                current_content.append(line)

        if current_section:
            sections[current_section] = "\n".join(current_content).strip()

        data["sections"] = sections
        return data

    def _update_product_context(
        self, context_path: Path, brain_data: Dict, config_data: Dict
    ) -> Optional[str]:
        """Update product context file with brain data."""
        content = context_path.read_text(encoding="utf-8")
        today = datetime.now().strftime("%Y-%m-%d")

        # Update last updated date
        content = re.sub(
            r"\*\*Last Updated:\*\* [\d-]+", f"**Last Updated:** {today}", content
        )

        # Update from brain sections
        if brain_data.get("sections"):
            # Update Current Focus if present in brain
            if "Current Focus" in brain_data["sections"]:
                focus_content = brain_data["sections"]["Current Focus"]
                content = re.sub(
                    r"## Current Focus\n\*Auto-updated.*?\*",
                    f"## Current Focus\n{focus_content}",
                    content,
                    flags=re.DOTALL,
                )

            # Update stakeholders if present
            if "Stakeholders" in brain_data["sections"]:
                stakeholders = brain_data["sections"]["Stakeholders"]
                content = re.sub(
                    r"## Stakeholders\n- TBD",
                    f"## Stakeholders\n{stakeholders}",
                    content,
                )

        # Add changelog entry
        if f"- **{today}**:" not in content:
            content = content.rstrip() + f"\n- **{today}**: Synced from brain\n"

        return content

    def _sync_team_from_brain(self) -> List[str]:
        """Sync team context files with people entities."""
        updated = []

        # Sync direct reports
        for report in config_loader.get_team_reports():
            report_id = report.get("id")
            report_name = report.get("name", "")

            if not report_id:
                continue

            # Find brain entity
            brain_data = self._load_person_entity(report_name)

            context_path = self.team_path / "reports" / report_id / "context.md"

            if context_path.exists() and brain_data:
                updated_content = self._update_person_context(
                    context_path, brain_data, report
                )
                if updated_content:
                    context_path.write_text(updated_content, encoding="utf-8")
                    updated.append(str(context_path))

        # Sync stakeholders
        for stakeholder in config_loader.get_stakeholders():
            s_id = stakeholder.get("id")
            s_name = stakeholder.get("name", "")

            if not s_id:
                continue

            brain_data = self._load_person_entity(s_name)
            context_path = self.team_path / "stakeholders" / s_id / "context.md"

            if context_path.exists() and brain_data:
                updated_content = self._update_person_context(
                    context_path, brain_data, stakeholder
                )
                if updated_content:
                    context_path.write_text(updated_content, encoding="utf-8")
                    updated.append(str(context_path))

        return updated

    def _load_person_entity(self, person_name: str) -> Optional[Dict[str, Any]]:
        """Load brain entity for a person."""
        # Try various name formats
        name_variants = [
            person_name,
            person_name.replace(" ", "_"),
            person_name.replace(" ", "-"),
            (
                person_name.split()[0] if " " in person_name else person_name
            ),  # First name only
        ]

        # Search in Entities folder directly (primary location)
        if self.entities_path.exists():
            for variant in name_variants:
                entity_path = self.entities_path / f"{variant}.md"
                if entity_path.exists():
                    return self._parse_brain_entity(entity_path)

        # Fallback to People subfolder (legacy)
        if self.people_path.exists():
            for variant in name_variants:
                entity_path = self.people_path / f"{variant}.md"
                if entity_path.exists():
                    return self._parse_brain_entity(entity_path)

        return None

    def _update_person_context(
        self, context_path: Path, brain_data: Dict, config_data: Dict
    ) -> Optional[str]:
        """Update person context file with brain data."""
        content = context_path.read_text(encoding="utf-8")
        today = datetime.now().strftime("%Y-%m-%d")

        # Update last updated date
        content = re.sub(
            r"\*\*Last Updated:\*\* [\d-]+", f"**Last Updated:** {today}", content
        )

        # Update from brain sections
        if brain_data.get("sections"):
            sections = brain_data["sections"]

            # Update Strengths from Working Style section
            if "Working Style (from NGO.md)" in sections:
                working_style = sections["Working Style (from NGO.md)"]
                # Replace placeholder
                content = re.sub(
                    r"## Strengths\n\*From brain/career planning observations\*",
                    f"## Strengths\n{working_style}",
                    content,
                )

            # Update Current Focus from Action Items
            if "Action Items (Current)" in sections:
                action_items = sections["Action Items (Current)"]
                content = re.sub(
                    r"## Current Focus\n\*Auto-updated from Jira assignments\*",
                    f"## Current Focus\n{action_items}",
                    content,
                )

            # Update Recent Interactions from Changelog
            if "Changelog" in sections:
                changelog = sections["Changelog"]
                # Take last 5 entries
                changelog_lines = changelog.strip().split("\n")[:5]
                recent = "\n".join(changelog_lines)
                content = re.sub(
                    r"## Recent Interactions\n\*Auto-updated from meeting notes, Slack\*",
                    f"## Recent Interactions\n{recent}",
                    content,
                )

            # Update Career Development if present
            if "Career Development" in sections:
                career = sections["Career Development"]
                content = re.sub(
                    r"## Development Areas\n\*From career planning discussions\*",
                    f"## Development Areas\n{career}",
                    content,
                )

        return content

    def sync_context_to_brain(self) -> Dict[str, Any]:
        """
        Update brain entities with changes from context files.

        Returns:
            Dict with sync results.
        """
        result = {"updated_entities": [], "new_workspace_refs": [], "errors": []}

        # Add workspace_path to relevant brain entities
        result["new_workspace_refs"] = self._add_workspace_references()

        return result

    def _add_workspace_references(self) -> List[str]:
        """Add workspace_path references to brain entities."""
        updated = []

        # Update brand entities with product workspace paths
        for product in config_loader.get_products_config().get("items", []):
            product_id = product.get("id")
            product_name = product.get("name", "")

            if not product_id or not product_name:
                continue

            # Find entity file
            name_variants = [
                product_name,
                product_name.replace(" ", "_"),
                product_name.replace(" ", "-"),
            ]

            for variant in name_variants:
                entity_path = self.brands_path / f"{variant}.md"
                if entity_path.exists():
                    if self._add_workspace_ref_to_entity(entity_path, product_id):
                        updated.append(str(entity_path))
                    break

        # Update people entities with team workspace paths
        for report in config_loader.get_team_reports():
            report_id = report.get("id")
            report_name = report.get("name", "")

            if not report_id or not report_name:
                continue

            name_variants = [
                report_name,
                report_name.replace(" ", "_"),
                report_name.replace(" ", "-"),
                report_name.split()[0] if " " in report_name else report_name,
            ]

            for variant in name_variants:
                entity_path = self.people_path / f"{variant}.md"
                if entity_path.exists():
                    workspace_path = f"team/reports/{report_id}"
                    if self._add_workspace_ref_to_entity(
                        entity_path, workspace_path, field_name="team_path"
                    ):
                        updated.append(str(entity_path))
                    break

        return updated

    def _add_workspace_ref_to_entity(
        self, entity_path: Path, workspace_id: str, field_name: str = "workspace_path"
    ) -> bool:
        """Add or update workspace reference in brain entity."""
        content = entity_path.read_text(encoding="utf-8")

        # Check if reference already exists
        ref_pattern = rf"{field_name}: "
        if ref_pattern in content:
            # Already has reference, check if it needs update
            if workspace_id in content:
                return False  # Already correct
            # Update existing reference
            content = re.sub(
                rf"{field_name}: .*", f"{field_name}: {workspace_id}", content
            )
        else:
            # Add reference after frontmatter or at start of file
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    # Add to frontmatter
                    frontmatter = (
                        parts[1].rstrip() + f"\n{field_name}: {workspace_id}\n"
                    )
                    content = f"---{frontmatter}---{parts[2]}"
                else:
                    # Add as new frontmatter
                    content = f"---\n{field_name}: {workspace_id}\n---\n\n{content}"
            else:
                # Add frontmatter
                content = f"---\n{field_name}: {workspace_id}\n---\n\n{content}"

        entity_path.write_text(content, encoding="utf-8")
        return True

    def full_sync(self) -> Dict[str, Any]:
        """
        Perform full bi-directional sync.

        Returns:
            Dict with combined results.
        """
        result = {
            "brain_to_context": {},
            "context_to_brain": {},
            "timestamp": datetime.now().isoformat(),
        }

        result["brain_to_context"] = self.sync_brain_to_context()
        result["context_to_brain"] = self.sync_context_to_brain()

        return result

    def get_status(self) -> Dict[str, Any]:
        """Get sync status."""
        status = {
            "product_contexts": [],
            "team_contexts": [],
            "brain_entities_with_workspace": [],
            "entities_missing_workspace": [],
        }

        # Check product context files
        org_config = config_loader.get_organization_config()
        if org_config:
            org_path = self.products_path / org_config["id"]
            if org_path.exists():
                for context_file in org_path.rglob("*-context.md"):
                    status["product_contexts"].append(
                        str(context_file.relative_to(self.user_path))
                    )

        # Check team context files
        if self.team_path.exists():
            for context_file in self.team_path.rglob("context.md"):
                status["team_contexts"].append(
                    str(context_file.relative_to(self.user_path))
                )

        # Check brain entities for workspace references
        if self.brands_path.exists():
            for entity in self.brands_path.glob("*.md"):
                content = entity.read_text(encoding="utf-8")
                if "workspace_path:" in content:
                    status["brain_entities_with_workspace"].append(entity.name)
                else:
                    status["entities_missing_workspace"].append(entity.name)

        return status


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="PM-OS Context Sync")
    parser.add_argument("--sync", action="store_true", help="Full bi-directional sync")
    parser.add_argument(
        "--brain-to-context", action="store_true", help="Brain populates context files"
    )
    parser.add_argument(
        "--context-to-brain", action="store_true", help="Context files update brain"
    )
    parser.add_argument("--status", action="store_true", help="Show sync status")

    args = parser.parse_args()

    try:
        sync = ContextSync()

        if args.sync:
            result = sync.full_sync()
        elif args.brain_to_context:
            result = sync.sync_brain_to_context()
        elif args.context_to_brain:
            result = sync.sync_context_to_brain()
        elif args.status:
            result = sync.get_status()
        else:
            # Default to status
            result = sync.get_status()

        print(json.dumps(result, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
