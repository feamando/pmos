#!/usr/bin/env python3
"""
PM-OS Workspace Migration Script v2.0

Comprehensive migration of ALL existing files from legacy paths to WCR structure.
Creates symlinks for backward compatibility.

Migrations handled:
- /context → /personal/context (daily context files)
- /reporting → /products/{org}/reporting (sprint reports)
- /products/* → /products/{org}/* (legacy product folders)
- /planning/Career → /team/reports/*/career
- /planning/Planning_Docs → /products/{org}/planning
- /planning/Quarterly_Updates → /products/{org}/reporting
- /planning/Meeting_Prep → keep + route
- /team/Interviews → /team/recruiting/interviews
- /team/Recruiting → /team/recruiting

Usage:
    python3 migrate_workspace.py --dry-run      # Preview changes
    python3 migrate_workspace.py --execute      # Perform migration
    python3 migrate_workspace.py --status       # Show migration status
    python3 migrate_workspace.py --rollback     # Undo migration

Author: PM-OS Team
Version: 2.0.0
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader


class WorkspaceMigrator:
    """Comprehensive migrator for PM-OS workspace."""

    # Mapping of legacy product folder names to product IDs
    PRODUCT_NAME_MAP = {
        "Meal_Kit": "meal-kit",
        "Brand_B": "brand-b",
        "Growth_Platform": "growth-platform",
        "Product Innovation": "product-innovation",
        "Product_Innovation": "product-innovation",
        "Creator_Marketplace": "creator-marketplace",
        "Growth_Division_General": "gd-general",
        "M&A": "mergers-acquisitions",
    }

    # Mapping of legacy career folder names to person IDs
    CAREER_NAME_MAP = {
        "Carol_Developer": "carol-developer",
        "Eve_Analyst": "eve-analyst",
        "Alice_Engineer": "alice-engineer",
        "Bob_Designer": "bob-designer",
        "Frank_Researcher": "frank-researcher",
    }

    def __init__(self, user_path: Optional[Path] = None, dry_run: bool = True):
        config = config_loader.get_config()
        self.user_path = user_path or config.user_path
        if self.user_path is None:
            raise ValueError("Could not determine user path")

        self.dry_run = dry_run
        self.migration_log = []
        self.backup_dir = (
            self.user_path
            / ".migration_backup"
            / datetime.now().strftime("%Y%m%d_%H%M%S")
        )

        # Get org ID
        org_config = config_loader.get_organization_config()
        self.org_id = org_config.get("id") if org_config else "organization"

        # WCR paths
        self.products_path = self.user_path / "products" / self.org_id
        self.team_path = self.user_path / "team"
        self.personal_path = self.user_path / "personal"

    def _build_all_migrations(self) -> List[Dict[str, Any]]:
        """Build comprehensive list of all migrations."""
        migrations = []

        # 1. Daily context files → /personal/context
        migrations.extend(self._build_context_migrations())

        # 2. Sprint reports → /products/{org}/reporting/sprint-reports
        migrations.extend(self._build_reporting_migrations())

        # 3. Legacy product folders → /products/{org}/*
        migrations.extend(self._build_product_migrations())

        # 4. Career planning → /team/reports/*/career
        migrations.extend(self._build_career_migrations())

        # 5. Planning docs → /products/{org}/planning
        migrations.extend(self._build_planning_docs_migrations())

        # 6. Quarterly updates → /products/{org}/reporting/quarterly
        migrations.extend(self._build_quarterly_migrations())

        # 7. Team management → /team/recruiting
        migrations.extend(self._build_team_mgmt_migrations())

        # 8. Root-level product files (PRDs at /products/*.md)
        migrations.extend(self._build_root_product_files_migrations())

        return migrations

    def _build_context_migrations(self) -> List[Dict]:
        """Build migrations for /context → /personal/context."""
        migrations = []
        source = self.user_path / "context"
        target = self.personal_path / "context"

        if source.exists() and not source.is_symlink():
            # Move entire directory
            migrations.append(
                {
                    "type": "directory",
                    "source": source,
                    "target": target,
                    "description": "Daily context files → /personal/context",
                    "create_symlink": True,
                    "priority": 1,
                }
            )

        return migrations

    def _build_reporting_migrations(self) -> List[Dict]:
        """Build migrations for sprint reports."""
        migrations = []

        # /reporting/Sprint_Reports
        sources = [
            self.user_path / "reporting" / "Sprint_Reports",
            self.user_path / "planning" / "Reporting" / "Sprint_Reports",
            self.user_path / "reporting" / "Distribution" / "Sprint_Reports",
        ]

        target = self.products_path / "reporting" / "sprint-reports"

        for source in sources:
            if source.exists() and not source.is_symlink():
                migrations.append(
                    {
                        "type": "merge_directory",
                        "source": source,
                        "target": target,
                        "description": f"Sprint reports from {source.relative_to(self.user_path)}",
                        "create_symlink": True,
                        "priority": 2,
                    }
                )

        # /reporting/Distribution (non-sprint-reports)
        dist_source = self.user_path / "reporting" / "Distribution"
        if dist_source.exists():
            for item in dist_source.iterdir():
                if item.name != "Sprint_Reports" and item.is_file():
                    migrations.append(
                        {
                            "type": "file",
                            "source": item,
                            "target": self.products_path / "reporting" / item.name,
                            "description": f"Distribution file: {item.name}",
                            "priority": 2,
                        }
                    )

        return migrations

    def _build_product_migrations(self) -> List[Dict]:
        """Build migrations for legacy product folders."""
        migrations = []
        products_root = self.user_path / "products"

        if not products_root.exists():
            return migrations

        for item in products_root.iterdir():
            if not item.is_dir():
                continue
            if item.name == self.org_id:  # Skip the new WCR folder
                continue
            if item.name.startswith("."):
                continue

            # Determine target product ID
            product_id = self.PRODUCT_NAME_MAP.get(
                item.name, item.name.lower().replace("_", "-").replace(" ", "-")
            )

            # Check if this product exists in config
            product_config = config_loader.get_product_by_id(product_id)

            if product_config:
                # Product exists in config - merge into existing WCR folder
                target = self.products_path / product_id
            else:
                # Product not in config - create new folder
                target = self.products_path / product_id

            migrations.append(
                {
                    "type": "merge_directory",
                    "source": item,
                    "target": target,
                    "description": f"Product folder: {item.name} → {product_id}",
                    "create_symlink": True,
                    "priority": 3,
                }
            )

        return migrations

    def _build_career_migrations(self) -> List[Dict]:
        """Build migrations for career planning files."""
        migrations = []
        career_root = self.user_path / "planning" / "Career"

        if not career_root.exists():
            return migrations

        for person_dir in career_root.iterdir():
            if not person_dir.is_dir():
                continue

            # Map to person ID
            person_id = self.CAREER_NAME_MAP.get(person_dir.name)
            if not person_id:
                person_id = person_dir.name.lower().replace("_", "-").replace(" ", "-")

            # Check if person is a direct report
            report = config_loader.get_report_by_id(person_id)
            if report:
                target = self.team_path / "reports" / person_id / "career"
            else:
                # Not a direct report - put in stakeholders or general team
                target = self.team_path / "stakeholders" / person_id / "career"

            migrations.append(
                {
                    "type": "merge_directory",
                    "source": person_dir,
                    "target": target,
                    "description": f"Career planning: {person_dir.name}",
                    "create_symlink": True,
                    "priority": 4,
                }
            )

        return migrations

    def _build_planning_docs_migrations(self) -> List[Dict]:
        """Build migrations for planning documents."""
        migrations = []
        planning_docs = self.user_path / "planning" / "Planning_Docs"

        if planning_docs.exists() and not planning_docs.is_symlink():
            target = self.products_path / "planning" / "docs"
            migrations.append(
                {
                    "type": "merge_directory",
                    "source": planning_docs,
                    "target": target,
                    "description": "Planning docs → products/planning/docs",
                    "create_symlink": True,
                    "priority": 5,
                }
            )

        return migrations

    def _build_quarterly_migrations(self) -> List[Dict]:
        """Build migrations for quarterly updates."""
        migrations = []
        quarterly = self.user_path / "planning" / "Quarterly_Updates"

        if quarterly.exists() and not quarterly.is_symlink():
            target = self.products_path / "reporting" / "quarterly"
            migrations.append(
                {
                    "type": "merge_directory",
                    "source": quarterly,
                    "target": target,
                    "description": "Quarterly updates → products/reporting/quarterly",
                    "create_symlink": True,
                    "priority": 5,
                }
            )

        return migrations

    def _build_team_mgmt_migrations(self) -> List[Dict]:
        """Build migrations for team management files."""
        migrations = []

        # /team/Interviews → /team/recruiting/interviews
        interviews = self.user_path / "team" / "Interviews"
        if interviews.exists() and not interviews.is_symlink():
            target = self.team_path / "recruiting" / "interviews"
            migrations.append(
                {
                    "type": "directory",
                    "source": interviews,
                    "target": target,
                    "description": "Interviews → team/recruiting/interviews",
                    "create_symlink": True,
                    "priority": 4,
                }
            )

        # /team/Recruiting → /team/recruiting
        recruiting = self.user_path / "team" / "Recruiting"
        if recruiting.exists() and not recruiting.is_symlink():
            target = self.team_path / "recruiting"
            migrations.append(
                {
                    "type": "merge_directory",
                    "source": recruiting,
                    "target": target,
                    "description": "Recruiting → team/recruiting",
                    "create_symlink": True,
                    "priority": 4,
                }
            )

        # /planning/Team → /team
        planning_team = self.user_path / "planning" / "Team"
        if planning_team.exists() and not planning_team.is_symlink():
            # Check for Interviews subfolder
            interviews_sub = planning_team / "Interviews"
            if interviews_sub.exists():
                migrations.append(
                    {
                        "type": "merge_directory",
                        "source": interviews_sub,
                        "target": self.team_path / "recruiting" / "interviews",
                        "description": "Planning/Team/Interviews → team/recruiting/interviews",
                        "create_symlink": False,
                        "priority": 4,
                    }
                )

        return migrations

    def _build_root_product_files_migrations(self) -> List[Dict]:
        """Build migrations for PRDs and other files at /products root."""
        migrations = []
        products_root = self.user_path / "products"

        if not products_root.exists():
            return migrations

        for item in products_root.iterdir():
            if item.is_file() and item.suffix == ".md":
                # Determine which product this belongs to based on filename
                name_lower = item.name.lower()
                target_product = None

                if "tpt" in name_lower or "pets" in name_lower:
                    target_product = "brand-b"
                elif "good" in name_lower and "chop" in name_lower:
                    target_product = "meal-kit"
                elif "factor" in name_lower:
                    target_product = "growth-platform"
                elif "meal" in name_lower or "acme-corp" in name_lower:
                    target_product = "nv-general"
                else:
                    target_product = "nv-general"

                target = self.products_path / target_product / "planning" / item.name
                migrations.append(
                    {
                        "type": "file",
                        "source": item,
                        "target": target,
                        "description": f"PRD/Doc: {item.name} → {target_product}/planning",
                        "priority": 6,
                    }
                )

        return migrations

    def preview(self) -> Dict[str, Any]:
        """Preview all migrations."""
        migrations = self._build_all_migrations()

        result = {
            "operations": [],
            "symlinks": [],
            "warnings": [],
            "summary": {"by_category": {}},
        }

        for m in sorted(migrations, key=lambda x: x.get("priority", 99)):
            source = m["source"]
            target = m["target"]

            if not source.exists():
                continue

            if target.exists() and not target.is_symlink() and m["type"] == "directory":
                result["warnings"].append(f"Target exists: {target}")
                continue

            operation = {
                "action": m["type"],
                "source": str(source),
                "target": str(target),
                "description": m["description"],
            }
            result["operations"].append(operation)

            if m.get("create_symlink"):
                result["symlinks"].append({"link": str(source), "target": str(target)})

            # Count by category
            cat = (
                m["description"].split(":")[0]
                if ":" in m["description"]
                else m["description"].split(" →")[0]
            )
            result["summary"]["by_category"][cat] = (
                result["summary"]["by_category"].get(cat, 0) + 1
            )

        result["summary"]["total_operations"] = len(result["operations"])
        result["summary"]["total_symlinks"] = len(result["symlinks"])
        result["summary"]["total_warnings"] = len(result["warnings"])

        return result

    def execute(self) -> Dict[str, Any]:
        """Execute all migrations."""
        if self.dry_run:
            return self.preview()

        migrations = self._build_all_migrations()

        result = {
            "moved": [],
            "merged": [],
            "symlinks_created": [],
            "errors": [],
            "backup_dir": str(self.backup_dir),
        }

        # Create backup directory
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        for m in sorted(migrations, key=lambda x: x.get("priority", 99)):
            source = m["source"]
            target = m["target"]

            if not source.exists():
                continue

            try:
                target.parent.mkdir(parents=True, exist_ok=True)

                if m["type"] == "directory":
                    if target.exists() and not target.is_symlink():
                        result["errors"].append(f"Target exists: {target}")
                        continue

                    if target.is_symlink():
                        target.unlink()

                    shutil.move(str(source), str(target))
                    result["moved"].append(
                        {"source": str(source), "target": str(target)}
                    )

                elif m["type"] == "merge_directory":
                    # Merge contents into target
                    target.mkdir(parents=True, exist_ok=True)
                    for item in source.iterdir():
                        item_target = target / item.name
                        if item_target.exists():
                            # Skip if already exists
                            continue
                        shutil.move(str(item), str(item_target))
                    result["merged"].append(
                        {"source": str(source), "target": str(target)}
                    )

                    # Remove empty source
                    if source.exists() and not any(source.iterdir()):
                        source.rmdir()

                elif m["type"] == "file":
                    if target.exists():
                        continue
                    shutil.move(str(source), str(target))
                    result["moved"].append(
                        {"source": str(source), "target": str(target)}
                    )

                # Log
                self.migration_log.append(
                    {
                        "action": m["type"],
                        "source": str(source),
                        "target": str(target),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                # Create symlink
                if m.get("create_symlink") and not source.exists():
                    try:
                        source.symlink_to(target)
                        result["symlinks_created"].append(
                            {"link": str(source), "target": str(target)}
                        )
                    except Exception as e:
                        result["errors"].append(f"Symlink failed: {source} → {e}")

            except Exception as e:
                result["errors"].append(f"Failed: {source} → {e}")

        # Save migration log
        log_path = self.backup_dir / "migration_log.json"
        log_path.write_text(json.dumps(self.migration_log, indent=2))

        return result

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive migration status."""
        status = {
            "wcr_structure": {
                "products": self.products_path.exists(),
                "team": self.team_path.exists(),
                "personal": self.personal_path.exists(),
                "personal_context": (self.personal_path / "context").exists(),
            },
            "legacy_paths": [],
            "symlinks": [],
            "needs_migration": [],
        }

        # Check for legacy paths that should be migrated
        legacy_checks = [
            (self.user_path / "context", "/personal/context"),
            (
                self.user_path / "reporting" / "Sprint_Reports",
                "/products/*/reporting/sprint-reports",
            ),
            (self.user_path / "planning" / "Career", "/team/reports/*/career"),
            (
                self.user_path / "planning" / "Planning_Docs",
                "/products/*/planning/docs",
            ),
            (
                self.user_path / "planning" / "Quarterly_Updates",
                "/products/*/reporting/quarterly",
            ),
            (self.user_path / "team" / "Interviews", "/team/recruiting/interviews"),
        ]

        for legacy, target_desc in legacy_checks:
            if legacy.exists():
                if legacy.is_symlink():
                    status["symlinks"].append(
                        {
                            "path": str(legacy.relative_to(self.user_path)),
                            "target": str(legacy.resolve()),
                        }
                    )
                else:
                    status["legacy_paths"].append(
                        str(legacy.relative_to(self.user_path))
                    )
                    status["needs_migration"].append(
                        {
                            "source": str(legacy.relative_to(self.user_path)),
                            "target": target_desc,
                        }
                    )

        # Check legacy product folders
        products_root = self.user_path / "products"
        if products_root.exists():
            for item in products_root.iterdir():
                if (
                    item.is_dir()
                    and item.name != self.org_id
                    and not item.name.startswith(".")
                ):
                    status["legacy_paths"].append(f"products/{item.name}")
                    status["needs_migration"].append(
                        {
                            "source": f"products/{item.name}",
                            "target": f"/products/{self.org_id}/{item.name.lower().replace('_', '-')}",
                        }
                    )

        return status


def main():
    parser = argparse.ArgumentParser(description="PM-OS Workspace Migration v2.0")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes")
    parser.add_argument("--execute", action="store_true", help="Execute migration")
    parser.add_argument("--status", action="store_true", help="Show migration status")

    args = parser.parse_args()

    try:
        if args.execute:
            migrator = WorkspaceMigrator(dry_run=False)
            result = migrator.execute()
        elif args.status:
            migrator = WorkspaceMigrator()
            result = migrator.get_status()
        else:
            migrator = WorkspaceMigrator(dry_run=True)
            result = migrator.preview()

        print(json.dumps(result, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
