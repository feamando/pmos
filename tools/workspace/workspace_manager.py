#!/usr/bin/env python3
"""
PM-OS Workspace Manager

Manages the workflow-centric folder structure for products, team, and personal.
Creates folders, generates context files, and maintains the workspace.

Usage:
    python3 workspace_manager.py init              # Initialize full workspace from config
    python3 workspace_manager.py create-product ID # Create a new product folder
    python3 workspace_manager.py sync              # Sync context files with brain
    python3 workspace_manager.py status            # Show workspace status

Author: PM-OS Team
Version: 1.0.0
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_loader

# Templates for context files
PRODUCT_CONTEXT_TEMPLATE = """# {name} Context

**ID:** {id}
**Type:** {type}
**Status:** {status}
**Last Updated:** {updated}

## Ownership
- **Product Owner:** {product_owner}
- **Squad Lead:** {squad_lead}
- **Design Lead:** {design_lead}
- **Engineering Lead:** {eng_lead}
- **Brand:** {brand}
- **Market:** {market}

## Stakeholders
{stakeholders}

## References
- **Jira Board:** [{jira_project}](https://your-company.atlassian.net/jira/software/projects/{jira_project}/boards)
{confluence_ref}
{github_refs}
{slack_refs}

## Brain Entities
{brain_refs}

## Current Focus
*Auto-updated from Jira/context*

## Key Decisions
*Links to DRRs and decision records*

## Changelog
- **{updated}**: Context file created
"""

TEAM_CONTEXT_TEMPLATE = """# Team Overview

**Manager:** {manager_name}
**Last Updated:** {updated}

## Direct Reports

| Name | Role | Squad | 1:1 Cadence |
|------|------|-------|-------------|
{reports_table}

## Stakeholders

| Name | Role | Relationship |
|------|------|--------------|
{stakeholders_table}

## Organization
{org_chart}

## Brain Reference
[[Entities/People/]]
"""

PERSON_CONTEXT_TEMPLATE = """# {name}

**Role:** {role}
**Squad:** {squad}
**Email:** {email}
**Slack:** {slack_id}
**Relationship:** {relationship}
**Last Updated:** {updated}

## Strengths
*From brain/career planning*

## Development Areas
*From career planning*

## Current Focus
*Auto-updated from Jira assignments*

## Recent Interactions
*Auto-updated from meeting notes, Slack*

## 1:1 Cadence
{cadence}

## Brain Reference
[[Entities/People/{brain_ref}]]
"""

PERSONAL_CONTEXT_TEMPLATE = """# Personal Development

**Last Updated:** {updated}

## Current Goals
*From career planning*

## Learning Queue
*Items to read/study*

## Career Trajectory
- **Current Level:** {current_level}
- **Target Level:** {target_level}
- **Review Cycle:** {review_cycle}

## Reflections
*Weekly/monthly reflections*
"""


class WorkspaceManager:
    """Manages PM-OS workflow-centric workspace structure."""

    def __init__(self, user_path: Optional[Path] = None):
        """
        Initialize workspace manager.

        Args:
            user_path: Path to user/ directory. If None, auto-detected.
        """
        self.config = config_loader.get_config()
        self.user_path = user_path or self.config.user_path
        if self.user_path is None:
            raise ValueError("Could not determine user path")

        # Core workspace paths
        self.products_path = self.user_path / "products"
        self.team_path = self.user_path / "team"
        self.personal_path = self.user_path / "personal"

    def init_workspace(self, force: bool = False) -> Dict[str, Any]:
        """
        Initialize the full workspace structure from config.

        Args:
            force: If True, recreate folders even if they exist.

        Returns:
            Dict with created folders and status.
        """
        result = {
            "created_folders": [],
            "created_context_files": [],
            "skipped": [],
            "errors": [],
        }

        # Initialize products
        try:
            products_result = self._init_products(force)
            result["created_folders"].extend(products_result.get("folders", []))
            result["created_context_files"].extend(
                products_result.get("context_files", [])
            )
        except Exception as e:
            result["errors"].append(f"Products init failed: {e}")

        # Initialize team
        try:
            team_result = self._init_team(force)
            result["created_folders"].extend(team_result.get("folders", []))
            result["created_context_files"].extend(team_result.get("context_files", []))
        except Exception as e:
            result["errors"].append(f"Team init failed: {e}")

        # Initialize personal
        try:
            personal_result = self._init_personal(force)
            result["created_folders"].extend(personal_result.get("folders", []))
            result["created_context_files"].extend(
                personal_result.get("context_files", [])
            )
        except Exception as e:
            result["errors"].append(f"Personal init failed: {e}")

        return result

    def _init_products(self, force: bool = False) -> Dict[str, List[str]]:
        """Initialize products folder structure."""
        result = {"folders": [], "context_files": []}

        products_config = config_loader.get_products_config()
        if not products_config:
            return result

        org_config = products_config.get("organization")
        items = products_config.get("items", [])
        subfolders = config_loader.get_standard_subfolders()

        # Create organization-level folder if configured
        if org_config:
            org_id = org_config.get("id", "organization")
            org_path = self.products_path / org_id
            self._ensure_folder(org_path, result["folders"])

            # Create organization sub-folders
            for subfolder in subfolders:
                self._ensure_folder(org_path / subfolder, result["folders"])

            # Create organization context file
            context_path = org_path / f"{org_id}-context.md"
            if force or not context_path.exists():
                self._create_product_context(org_config, context_path, is_org=True)
                result["context_files"].append(str(context_path))

            # Create product folders under organization
            for item in items:
                item_id = item.get("id")
                if not item_id:
                    continue

                item_path = org_path / item_id
                self._ensure_folder(item_path, result["folders"])

                # Create product sub-folders
                for subfolder in subfolders:
                    self._ensure_folder(item_path / subfolder, result["folders"])

                # Create product context file
                context_path = item_path / f"{item_id}-context.md"
                if force or not context_path.exists():
                    self._create_product_context(item, context_path)
                    result["context_files"].append(str(context_path))
        else:
            # No organization - create products at root level
            for item in items:
                item_id = item.get("id")
                if not item_id:
                    continue

                item_path = self.products_path / item_id
                self._ensure_folder(item_path, result["folders"])

                for subfolder in subfolders:
                    self._ensure_folder(item_path / subfolder, result["folders"])

                context_path = item_path / f"{item_id}-context.md"
                if force or not context_path.exists():
                    self._create_product_context(item, context_path)
                    result["context_files"].append(str(context_path))

        return result

    def _init_team(self, force: bool = False) -> Dict[str, List[str]]:
        """Initialize team folder structure."""
        result = {"folders": [], "context_files": []}

        team_config = config_loader.get_team_config()
        if not team_config:
            return result

        # Create team root
        self._ensure_folder(self.team_path, result["folders"])

        # Manager folder
        manager = team_config.get("manager")
        if manager:
            manager_id = manager.get("id", "manager")
            manager_path = self.team_path / "manager" / manager_id
            self._ensure_folder(manager_path, result["folders"])
            self._ensure_folder(manager_path / "1on1s", result["folders"])

            context_path = manager_path / "context.md"
            if force or not context_path.exists():
                self._create_person_context(
                    manager, context_path, relationship="manager"
                )
                result["context_files"].append(str(context_path))

        # Reports folder
        reports_path = self.team_path / "reports"
        self._ensure_folder(reports_path, result["folders"])

        for report in team_config.get("reports", []):
            report_id = report.get("id")
            if not report_id:
                continue

            report_path = reports_path / report_id
            self._ensure_folder(report_path, result["folders"])
            self._ensure_folder(report_path / "1on1s", result["folders"])
            self._ensure_folder(report_path / "1on1s" / "archive", result["folders"])
            self._ensure_folder(report_path / "meetings", result["folders"])
            self._ensure_folder(report_path / "career", result["folders"])

            context_path = report_path / "context.md"
            if force or not context_path.exists():
                self._create_person_context(report, context_path, relationship="report")
                result["context_files"].append(str(context_path))

            # Create 1:1 prep file
            prep_path = report_path / "1on1s" / "1on1-prep.md"
            if force or not prep_path.exists():
                self._create_1on1_prep(report, prep_path)
                result["context_files"].append(str(prep_path))

        # Stakeholders folder
        stakeholders_path = self.team_path / "stakeholders"
        self._ensure_folder(stakeholders_path, result["folders"])

        for stakeholder in team_config.get("stakeholders", []):
            s_id = stakeholder.get("id")
            if not s_id:
                continue

            s_path = stakeholders_path / s_id
            self._ensure_folder(s_path, result["folders"])
            self._ensure_folder(s_path / "1on1s", result["folders"])

            context_path = s_path / "context.md"
            if force or not context_path.exists():
                self._create_person_context(
                    stakeholder, context_path, relationship="stakeholder"
                )
                result["context_files"].append(str(context_path))

        # Team-level context file
        team_context_path = self.team_path / "team-context.md"
        if force or not team_context_path.exists():
            self._create_team_context(team_config, team_context_path)
            result["context_files"].append(str(team_context_path))

        return result

    def _init_personal(self, force: bool = False) -> Dict[str, List[str]]:
        """Initialize personal folder structure."""
        result = {"folders": [], "context_files": []}

        self._ensure_folder(self.personal_path, result["folders"])
        self._ensure_folder(self.personal_path / "development", result["folders"])
        self._ensure_folder(
            self.personal_path / "development" / "goals", result["folders"]
        )
        self._ensure_folder(
            self.personal_path / "development" / "feedback", result["folders"]
        )
        self._ensure_folder(self.personal_path / "learning", result["folders"])
        self._ensure_folder(
            self.personal_path / "learning" / "courses", result["folders"]
        )
        self._ensure_folder(
            self.personal_path / "learning" / "notes", result["folders"]
        )
        self._ensure_folder(self.personal_path / "reflections", result["folders"])
        self._ensure_folder(
            self.personal_path / "reflections" / "weekly", result["folders"]
        )

        # Personal context file
        personal_config = config_loader.get_personal_config()
        context_path = self.personal_path / "personal-context.md"
        if force or not context_path.exists():
            self._create_personal_context(personal_config, context_path)
            result["context_files"].append(str(context_path))

        # Reading list
        reading_path = self.personal_path / "learning" / "reading-list.md"
        if force or not reading_path.exists():
            reading_path.write_text(
                "# Reading List\n\n*Articles and books to read*\n\n## Queue\n\n## Completed\n"
            )
            result["context_files"].append(str(reading_path))

        # Career plan
        career_path = self.personal_path / "development" / "career-plan.md"
        if force or not career_path.exists():
            career_path.write_text(
                "# Career Plan\n\n*Current career goals and trajectory*\n\n## Current Focus\n\n## Long-term Goals\n"
            )
            result["context_files"].append(str(career_path))

        return result

    def _ensure_folder(self, path: Path, created_list: List[str]) -> bool:
        """Create folder if it doesn't exist."""
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created_list.append(str(path))
            return True
        return False

    def _create_product_context(
        self, config: dict, path: Path, is_org: bool = False
    ) -> None:
        """Create a product context file."""
        today = datetime.now().strftime("%Y-%m-%d")

        content = PRODUCT_CONTEXT_TEMPLATE.format(
            name=config.get("name", "Unknown"),
            id=config.get("id", "unknown"),
            type="organization" if is_org else config.get("type", "product"),
            status=config.get("status", "active").upper(),
            updated=today,
            product_owner="TBD",
            squad_lead="TBD",
            design_lead="TBD",
            eng_lead="TBD",
            brand=config.get("name", "N/A"),
            market=config.get("market", "N/A"),
            stakeholders="- TBD",
            jira_project=config.get("jira_project", "N/A"),
            confluence_ref="",
            github_refs="",
            slack_refs="",
            brain_refs=f"- [[Entities/Brands/{config.get('name', 'Unknown').replace(' ', '_')}]]",
        )

        path.write_text(content, encoding="utf-8")

    def _create_person_context(
        self, config: dict, path: Path, relationship: str = "report"
    ) -> None:
        """Create a person context file."""
        today = datetime.now().strftime("%Y-%m-%d")
        name = config.get("name", "Unknown")

        content = PERSON_CONTEXT_TEMPLATE.format(
            name=name,
            role=config.get("role", "N/A"),
            squad=config.get("squad", "N/A"),
            email=config.get("email", "N/A"),
            slack_id=config.get("slack_id", "N/A"),
            relationship=relationship,
            updated=today,
            cadence=config.get("one_on_one_cadence", "weekly"),
            brain_ref=name.replace(" ", "_"),
        )

        path.write_text(content, encoding="utf-8")

    def _create_team_context(self, config: dict, path: Path) -> None:
        """Create team-level context file."""
        today = datetime.now().strftime("%Y-%m-%d")

        # Build reports table
        reports_rows = []
        for r in config.get("reports", []):
            reports_rows.append(
                f"| {r.get('name', 'N/A')} | {r.get('role', 'N/A')} | {r.get('squad', 'N/A')} | {r.get('one_on_one_cadence', 'weekly')} |"
            )
        reports_table = (
            "\n".join(reports_rows)
            if reports_rows
            else "| *No reports configured* | | | |"
        )

        # Build stakeholders table
        stakeholders_rows = []
        for s in config.get("stakeholders", []):
            stakeholders_rows.append(
                f"| {s.get('name', 'N/A')} | {s.get('role', 'N/A')} | {s.get('relationship', 'stakeholder')} |"
            )
        stakeholders_table = (
            "\n".join(stakeholders_rows)
            if stakeholders_rows
            else "| *No stakeholders configured* | | |"
        )

        manager = config.get("manager", {})
        manager_name = manager.get("name", "Not configured")

        content = TEAM_CONTEXT_TEMPLATE.format(
            manager_name=manager_name,
            updated=today,
            reports_table=reports_table,
            stakeholders_table=stakeholders_table,
            org_chart="*See config.yaml for full team structure*",
        )

        path.write_text(content, encoding="utf-8")

    def _create_personal_context(self, config: dict, path: Path) -> None:
        """Create personal context file."""
        today = datetime.now().strftime("%Y-%m-%d")
        career = config.get("career", {})

        content = PERSONAL_CONTEXT_TEMPLATE.format(
            updated=today,
            current_level=career.get("current_level", "N/A"),
            target_level=career.get("target_level", "N/A"),
            review_cycle=career.get("review_cycle", "H1/H2"),
        )

        path.write_text(content, encoding="utf-8")

    def _create_1on1_prep(self, report: dict, path: Path) -> None:
        """Create 1:1 prep file for a report."""
        today = datetime.now().strftime("%Y-%m-%d")
        name = report.get("name", "Unknown")

        content = f"""# 1:1 with {name}

**Cadence:** {report.get('one_on_one_cadence', 'weekly')}
**Last Updated:** {today}

## Running Agenda

### Check-in
- How are you doing?
- What's top of mind?

### Blockers
- What's blocking progress?

### Projects
*Status updates on key work*

### Development
*Career growth, feedback*

### Asks
- What do you need from me?

---

## Action Items
- [ ] *Add action items here*

## Notes History

### {today}
*Notes from today's 1:1*
"""

        path.write_text(content, encoding="utf-8")

    def create_product(
        self,
        product_id: str,
        name: str,
        product_type: str = "product",
        parent: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create a new product folder.

        Args:
            product_id: Unique identifier (kebab-case)
            name: Display name
            product_type: brand | product | feature | project
            parent: Parent product ID (for features under products)
            **kwargs: Additional config (jira_project, squad, market, status)

        Returns:
            Dict with created path and status.
        """
        result = {"folders": [], "context_files": [], "path": None}

        # Determine parent path
        org_config = config_loader.get_organization_config()
        if parent:
            parent_product = config_loader.get_product_by_id(parent)
            if parent_product and org_config:
                parent_path = self.products_path / org_config.get("id", "org") / parent
            else:
                parent_path = self.products_path / parent
        elif org_config:
            parent_path = self.products_path / org_config.get("id", "org")
        else:
            parent_path = self.products_path

        product_path = parent_path / product_id
        result["path"] = str(product_path)

        # Create folder structure
        self._ensure_folder(product_path, result["folders"])
        for subfolder in config_loader.get_standard_subfolders():
            self._ensure_folder(product_path / subfolder, result["folders"])

        # Create context file
        config = {
            "id": product_id,
            "name": name,
            "type": product_type,
            "status": kwargs.get("status", "active"),
            "jira_project": kwargs.get("jira_project"),
            "squad": kwargs.get("squad"),
            "market": kwargs.get("market", "N/A"),
        }
        context_path = product_path / f"{product_id}-context.md"
        self._create_product_context(config, context_path)
        result["context_files"].append(str(context_path))

        return result

    def get_status(self) -> Dict[str, Any]:
        """
        Get workspace status.

        Returns:
            Dict with folder counts and status.
        """
        status = {
            "products": {"exists": False, "count": 0, "items": []},
            "team": {"exists": False, "reports": 0, "stakeholders": 0},
            "personal": {"exists": False},
        }

        # Products
        if self.products_path.exists():
            status["products"]["exists"] = True
            org_config = config_loader.get_organization_config()
            if org_config:
                org_path = self.products_path / org_config.get("id", "org")
                if org_path.exists():
                    for item in org_path.iterdir():
                        if item.is_dir() and not item.name.startswith("."):
                            status["products"]["items"].append(item.name)
                            status["products"]["count"] += 1
            else:
                for item in self.products_path.iterdir():
                    if item.is_dir() and not item.name.startswith("."):
                        status["products"]["items"].append(item.name)
                        status["products"]["count"] += 1

        # Team
        if self.team_path.exists():
            status["team"]["exists"] = True
            reports_path = self.team_path / "reports"
            if reports_path.exists():
                status["team"]["reports"] = len(
                    [d for d in reports_path.iterdir() if d.is_dir()]
                )
            stakeholders_path = self.team_path / "stakeholders"
            if stakeholders_path.exists():
                status["team"]["stakeholders"] = len(
                    [d for d in stakeholders_path.iterdir() if d.is_dir()]
                )

        # Personal
        if self.personal_path.exists():
            status["personal"]["exists"] = True

        return status


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="PM-OS Workspace Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize workspace from config")
    init_parser.add_argument(
        "--force", action="store_true", help="Recreate existing files"
    )

    # Create-product command
    create_parser = subparsers.add_parser(
        "create-product", help="Create a new product folder"
    )
    create_parser.add_argument("id", help="Product ID (kebab-case)")
    create_parser.add_argument("--name", required=True, help="Display name")
    create_parser.add_argument(
        "--type", default="product", choices=["brand", "product", "feature", "project"]
    )
    create_parser.add_argument("--parent", help="Parent product ID")
    create_parser.add_argument("--jira", help="Jira project key")
    create_parser.add_argument("--squad", help="Squad name")
    create_parser.add_argument(
        "--market", default="N/A", help="Market (US, EU, GLOBAL)"
    )

    # Status command
    subparsers.add_parser("status", help="Show workspace status")

    args = parser.parse_args()

    try:
        manager = WorkspaceManager()

        if args.command == "init":
            result = manager.init_workspace(force=args.force)
            print(json.dumps(result, indent=2))

        elif args.command == "create-product":
            result = manager.create_product(
                product_id=args.id,
                name=args.name,
                product_type=args.type,
                parent=args.parent,
                jira_project=args.jira,
                squad=args.squad,
                market=args.market,
            )
            print(json.dumps(result, indent=2))

        elif args.command == "status":
            status = manager.get_status()
            print(json.dumps(status, indent=2))

        else:
            parser.print_help()

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
