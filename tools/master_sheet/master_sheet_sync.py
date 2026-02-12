#!/usr/bin/env python3
"""
PM-OS Master Sheet Sync

Synchronizes Google Sheets Master Sheet with PM-OS workspace.
Creates folders, context files, and tracks actions/deadlines.

Usage:
    python3 master_sheet_sync.py              # Full sync
    python3 master_sheet_sync.py --status     # Show current status
    python3 master_sheet_sync.py --overdue    # Show overdue items only
    python3 master_sheet_sync.py --week       # Show current week items

Author: PM-OS Team
Version: 1.0.0
"""

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_loader

# Google API imports
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


@dataclass
class ActionItem:
    """Represents a single action item from the sheet."""

    product: str
    feature: str
    action: str
    priority: str
    status: str
    responsible: str
    consulted: str
    link: str
    deadline: Optional[datetime]
    calendar_week_status: Dict[str, str] = field(default_factory=dict)

    @property
    def is_overdue(self) -> bool:
        if not self.deadline or self.status.lower() == "done":
            return False
        return datetime.now() > self.deadline

    @property
    def is_due_this_week(self) -> bool:
        if not self.deadline or self.status.lower() == "done":
            return False
        now = datetime.now()
        week_start = now - timedelta(days=now.weekday())
        week_end = week_start + timedelta(days=6)
        return week_start <= self.deadline <= week_end


@dataclass
class RecurringTask:
    """Represents a recurring task from the sheet."""

    domain: str
    project: str
    action: str
    priority: str
    responsible: str
    consulted: str
    command: str
    link: str
    recurrence: str
    calendar_week_status: Dict[str, str] = field(default_factory=dict)


class MasterSheetSync:
    """Synchronizes Master Sheet with PM-OS workspace."""

    def __init__(self):
        """Initialize sync service."""
        self.config = config_loader.get_config()
        self.user_path = self.config.user_path
        self.master_config = self._get_master_sheet_config()

        if not self.master_config.get("enabled"):
            raise ValueError("Master Sheet integration not enabled in config")

        self.spreadsheet_id = self.master_config["spreadsheet_id"]
        self.product_mapping = self.master_config.get("product_mapping", {})
        self.tabs = self.master_config.get("tabs", {})

        # Get Google credentials
        google_paths = config_loader.get_google_paths()
        self.creds = Credentials.from_authorized_user_file(google_paths["token"])
        self.sheets_service = build("sheets", "v4", credentials=self.creds)

        # Workspace paths
        self.products_path = self.user_path / "products"
        org_config = config_loader.get_organization_config()
        self.org_id = org_config.get("id", "organization") if org_config else None

    def _get_master_sheet_config(self) -> Dict[str, Any]:
        """Get master sheet config from config.yaml."""
        # Access via raw config since we don't have a helper yet
        config_path = self.user_path / "config.yaml"
        if config_path.exists():
            import yaml

            with open(config_path) as f:
                full_config = yaml.safe_load(f)
            return full_config.get("master_sheet", {})
        return {}

    def _get_current_calendar_week(self) -> int:
        """Get current ISO calendar week number."""
        return datetime.now().isocalendar()[1]

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse US format date (MM/DD/YYYY)."""
        if not date_str or date_str.strip() == "":
            return None
        try:
            return datetime.strptime(date_str.strip(), "%m/%d/%Y")
        except ValueError:
            try:
                return datetime.strptime(date_str.strip(), "%Y-%m-%d")
            except ValueError:
                return None

    def _read_sheet_tab(self, tab_name: str) -> List[List[str]]:
        """Read all data from a sheet tab."""
        try:
            result = (
                self.sheets_service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=f"{tab_name}!A1:Z200")
                .execute()
            )
            return result.get("values", [])
        except Exception as e:
            print(f"Error reading tab {tab_name}: {e}", file=sys.stderr)
            return []

    def read_topics(self) -> List[ActionItem]:
        """Read and parse topics tab."""
        tab_name = self.tabs.get("topics", "topics")
        rows = self._read_sheet_tab(tab_name)

        if len(rows) < 2:
            return []

        header = rows[0]
        items = []

        # Find column indices
        col_map = {col.strip().lower(): i for i, col in enumerate(header)}

        for row in rows[1:]:
            if not row or len(row) < 3:
                continue

            # Pad row to match header length
            row = row + [""] * (len(header) - len(row))

            # Extract calendar week statuses
            cw_status = {}
            for col_name, idx in col_map.items():
                if col_name.startswith("cw") and idx < len(row):
                    cw_status[col_name.upper()] = row[idx]

            item = ActionItem(
                product=(
                    row[col_map.get("product", 0)].strip()
                    if col_map.get("product", 0) < len(row)
                    else ""
                ),
                feature=(
                    row[col_map.get("feature", 1)].strip()
                    if col_map.get("feature", 1) < len(row)
                    else ""
                ),
                action=(
                    row[col_map.get("action", 2)].strip()
                    if col_map.get("action", 2) < len(row)
                    else ""
                ),
                priority=(
                    row[col_map.get("priority", 3)].strip()
                    if col_map.get("priority", 3) < len(row)
                    else "P2"
                ),
                status=(
                    row[col_map.get("current status", 4)].strip()
                    if col_map.get("current status", 4) < len(row)
                    else "To Do"
                ),
                responsible=(
                    row[col_map.get("responsible", 5)].strip()
                    if col_map.get("responsible", 5) < len(row)
                    else ""
                ),
                consulted=(
                    row[col_map.get("consulted", 6)].strip()
                    if col_map.get("consulted", 6) < len(row)
                    else ""
                ),
                link=(
                    row[col_map.get("link", 7)].strip()
                    if col_map.get("link", 7) < len(row)
                    else ""
                ),
                deadline=(
                    self._parse_date(row[col_map.get("deadline", 8)])
                    if col_map.get("deadline", 8) < len(row)
                    else None
                ),
                calendar_week_status=cw_status,
            )

            if item.product and item.action:
                items.append(item)

        return items

    def read_recurring(self) -> List[RecurringTask]:
        """Read and parse recurring tab."""
        tab_name = self.tabs.get("recurring", "recurring")
        rows = self._read_sheet_tab(tab_name)

        if len(rows) < 2:
            return []

        header = rows[0]
        tasks = []

        col_map = {col.strip().lower(): i for i, col in enumerate(header)}

        for row in rows[1:]:
            if not row or len(row) < 3:
                continue

            row = row + [""] * (len(header) - len(row))

            cw_status = {}
            for col_name, idx in col_map.items():
                if col_name.startswith("cw") and idx < len(row):
                    cw_status[col_name.upper()] = row[idx]

            task = RecurringTask(
                domain=(
                    row[col_map.get("domain", 0)].strip()
                    if col_map.get("domain", 0) < len(row)
                    else ""
                ),
                project=(
                    row[col_map.get("project", 1)].strip()
                    if col_map.get("project", 1) < len(row)
                    else ""
                ),
                action=(
                    row[col_map.get("action", 2)].strip()
                    if col_map.get("action", 2) < len(row)
                    else ""
                ),
                priority=(
                    row[col_map.get("priority", 3)].strip()
                    if col_map.get("priority", 3) < len(row)
                    else "P2"
                ),
                responsible=(
                    row[col_map.get("responsible", 4)].strip()
                    if col_map.get("responsible", 4) < len(row)
                    else ""
                ),
                consulted=(
                    row[col_map.get("consulted", 5)].strip()
                    if col_map.get("consulted", 5) < len(row)
                    else ""
                ),
                command=(
                    row[col_map.get("command", 6)].strip()
                    if col_map.get("command", 6) < len(row)
                    else ""
                ),
                link=(
                    row[col_map.get("link", 7)].strip()
                    if col_map.get("link", 7) < len(row)
                    else ""
                ),
                recurrence=(
                    row[col_map.get("recurrance", 8)].strip()
                    if col_map.get("recurrance", 8) < len(row)
                    else ""
                ),
                calendar_week_status=cw_status,
            )

            if task.domain and task.action:
                tasks.append(task)

        return tasks

    def _get_product_folder(self, product_code: str) -> Path:
        """Get the folder path for a product code."""
        folder_name = self.product_mapping.get(
            product_code, product_code.lower().replace(" ", "-")
        )
        if self.org_id:
            return self.products_path / self.org_id / folder_name
        return self.products_path / folder_name

    def _slugify(self, text: str) -> str:
        """Convert text to folder-safe slug."""
        return text.lower().replace(" ", "-").replace("/", "-").replace("&", "and")

    def ensure_feature_folder(self, item: ActionItem) -> Tuple[Path, bool]:
        """
        Ensure feature folder exists, create if not.
        Returns (path, was_created).
        """
        product_path = self._get_product_folder(item.product)
        feature_slug = self._slugify(item.feature)
        feature_path = product_path / feature_slug

        created = False
        if not feature_path.exists():
            feature_path.mkdir(parents=True, exist_ok=True)
            created = True

        return feature_path, created

    def create_brain_entity(self, item: ActionItem) -> bool:
        """
        Create a brain entity for a feature if it doesn't exist.

        Args:
            item: ActionItem from master sheet

        Returns:
            True if entity was created, False if already exists
        """
        # Entity path
        entity_name = item.feature.replace(" ", "_").replace("-", "_")
        entity_file = self.user_path / "brain" / "Entities" / f"{entity_name}.md"

        if entity_file.exists():
            return False

        # Create entity directory if needed
        entity_file.parent.mkdir(parents=True, exist_ok=True)

        now = datetime.utcnow()
        today = datetime.now().strftime("%Y-%m-%d")

        # Generate entity ID
        slug = item.feature.lower().replace(" ", "-").replace("_", "-")

        # Build frontmatter
        frontmatter = f"""---
$schema: brain://entity/project/v1
$id: entity/project/{slug}
$type: project
$version: 1
$created: '{now.isoformat()}Z'
$updated: '{now.isoformat()}Z'
$confidence: 0.5
$source: master_sheet
$status: active
$relationships:
- type: part_of
  target: entity/brand/{self.product_mapping.get(item.product, item.product.lower())}
  since: '{today}'
$tags:
- master_sheet
- {item.priority.lower()}
$aliases:
- {item.feature.lower()}
$events:
- event_id: evt-master-sheet-{now.strftime('%Y%m%d%H%M%S')}
  timestamp: '{now.isoformat()}Z'
  type: entity_create
  actor: system/master_sheet_sync
  changes:
  - field: $schema
    operation: set
    value: brain://entity/project/v1
  message: Created from Master Sheet sync
name: {item.feature}
---

# {item.feature}

**Type:** project
**Product:** {item.product}
**Created:** {today}
**Source:** Master Sheet

## Overview

{item.action if item.action else '[Auto-generated from Master Sheet - needs manual review]'}

## Status

- **Current Status:** {item.status}
- **Priority:** {item.priority}
- **Deadline:** {item.deadline.strftime('%Y-%m-%d') if item.deadline else 'N/A'}
- **Owner:** {item.responsible}

## Context

- [{today}] Created from Master Sheet (Product: {item.product}, Feature: {item.feature})

## Related Entities

- [[{self.product_mapping.get(item.product, item.product.replace(' ', '_'))}]] (Product)
{f'- [[{item.responsible.replace(" ", "_")}]] (Owner)' if item.responsible else ''}

## References

{f'- [{item.link}]({item.link})' if item.link and item.link != 'Link' else '- *No links yet*'}

## Notes

- Created automatically from Master Sheet sync
- Review and enrich manually

---
*Last updated: {today}*
"""

        entity_file.write_text(frontmatter, encoding="utf-8")
        return True

    def create_or_update_feature_context(
        self, item: ActionItem, feature_path: Path
    ) -> bool:
        """Create or update feature context file."""
        context_file = feature_path / f"{self._slugify(item.feature)}-context.md"
        today = datetime.now().strftime("%Y-%m-%d")

        if context_file.exists():
            # Update existing - append action to log
            content = context_file.read_text(encoding="utf-8")

            # Check if action already in log
            if item.action not in content:
                # Find action log table and append
                deadline_str = (
                    item.deadline.strftime("%Y-%m-%d") if item.deadline else "N/A"
                )
                new_row = f"| {today} | {item.action} | {item.status} | {item.priority} | {deadline_str} |"

                if "## Action Log" in content:
                    # Insert after the table header
                    lines = content.split("\n")
                    for i, line in enumerate(lines):
                        if line.startswith("|---"):
                            lines.insert(i + 1, new_row)
                            break
                    content = "\n".join(lines)
                else:
                    # Add action log section
                    content += f"\n\n## Action Log\n| Date | Action | Status | Priority | Deadline |\n|------|--------|--------|----------|----------|\n{new_row}\n"

                # Update status - use regex to replace the entire status line
                import re

                content = re.sub(
                    r"\*\*Status:\*\* .*", f"**Status:** {item.status}", content
                )

                # Update Last Updated date
                content = re.sub(
                    r"\*\*Last Updated:\*\* .*", f"**Last Updated:** {today}", content
                )

                context_file.write_text(content, encoding="utf-8")
                return True
            return False
        else:
            # Create new context file
            deadline_str = (
                item.deadline.strftime("%Y-%m-%d") if item.deadline else "N/A"
            )
            content = f"""# {item.feature} Context

**Product:** {item.product}
**Status:** {item.status}
**Owner:** {item.responsible}
**Priority:** {item.priority}
**Deadline:** {deadline_str}
**Last Updated:** {today}

## Description
*Feature context auto-generated from Master Sheet*

## Stakeholders
- **{item.responsible}** (Owner)
{f'- **{item.consulted}** (Consulted)' if item.consulted else ''}

## Action Log
| Date | Action | Status | Priority | Deadline |
|------|--------|--------|----------|----------|
| {today} | {item.action} | {item.status} | {item.priority} | {deadline_str} |

## References
{f'- [{item.link}]({item.link})' if item.link and item.link != 'Link' else '- *No links yet*'}

## Brain Entities
- [[Entities/{self._slugify(item.feature).replace('-', '_').title()}]]

## Changelog
- **{today}**: Context file created from Master Sheet
"""
            context_file.write_text(content, encoding="utf-8")
            return True

    def sync(self) -> Dict[str, Any]:
        """
        Perform full sync from Master Sheet.

        Returns:
            Dict with sync results.
        """
        result = {
            "timestamp": datetime.now().isoformat(),
            "calendar_week": self._get_current_calendar_week(),
            "topics": {
                "total": 0,
                "folders_created": [],
                "contexts_updated": [],
                "brain_entities_created": [],
                "overdue": [],
                "due_this_week": [],
                "p0_items": [],
                "in_progress": [],
            },
            "recurring": {"total": 0, "this_week": []},
            "errors": [],
        }

        # Sync topics
        try:
            topics = self.read_topics()
            result["topics"]["total"] = len(topics)

            current_cw = f"CW{self._get_current_calendar_week()}"

            for item in topics:
                try:
                    # Ensure folder exists
                    feature_path, was_created = self.ensure_feature_folder(item)
                    if was_created:
                        result["topics"]["folders_created"].append(str(feature_path))

                    # Create/update context
                    if self.create_or_update_feature_context(item, feature_path):
                        result["topics"]["contexts_updated"].append(item.feature)

                    # Create brain entity for new features
                    if self.create_brain_entity(item):
                        result["topics"]["brain_entities_created"].append(item.feature)

                    # Track overdue
                    if item.is_overdue:
                        result["topics"]["overdue"].append(
                            {
                                "feature": item.feature,
                                "action": item.action,
                                "deadline": (
                                    item.deadline.strftime("%Y-%m-%d")
                                    if item.deadline
                                    else None
                                ),
                                "responsible": item.responsible,
                                "priority": item.priority,
                            }
                        )

                    # Track due this week
                    if item.is_due_this_week:
                        result["topics"]["due_this_week"].append(
                            {
                                "feature": item.feature,
                                "action": item.action,
                                "deadline": (
                                    item.deadline.strftime("%Y-%m-%d")
                                    if item.deadline
                                    else None
                                ),
                                "responsible": item.responsible,
                                "priority": item.priority,
                            }
                        )

                    # Track P0 items
                    if item.priority == "P0" and item.status.lower() != "done":
                        result["topics"]["p0_items"].append(
                            {
                                "feature": item.feature,
                                "action": item.action,
                                "status": item.status,
                                "responsible": item.responsible,
                            }
                        )

                    # Track in progress
                    if item.status.lower() == "in progress":
                        result["topics"]["in_progress"].append(
                            {
                                "feature": item.feature,
                                "action": item.action,
                                "responsible": item.responsible,
                            }
                        )

                except Exception as e:
                    result["errors"].append(
                        f"Error processing {item.feature}: {str(e)}"
                    )

        except Exception as e:
            result["errors"].append(f"Error reading topics: {str(e)}")

        # Sync recurring
        try:
            recurring = self.read_recurring()
            result["recurring"]["total"] = len(recurring)

            current_cw = f"CW{self._get_current_calendar_week()}"

            for task in recurring:
                cw_status = task.calendar_week_status.get(current_cw, "")
                if cw_status.lower() == "to do":
                    result["recurring"]["this_week"].append(
                        {
                            "project": task.project,
                            "action": task.action,
                            "command": task.command,
                            "responsible": task.responsible,
                        }
                    )

        except Exception as e:
            result["errors"].append(f"Error reading recurring: {str(e)}")

        return result

    def get_weekly_summary(self) -> str:
        """Generate weekly summary markdown."""
        result = self.sync()
        cw = result["calendar_week"]

        lines = [
            f"## Week CW{cw} - Priority Actions",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            "",
        ]

        # P0 Critical
        if result["topics"]["p0_items"]:
            lines.append("### P0 - Critical")
            for item in result["topics"]["p0_items"]:
                lines.append(
                    f"- [ ] **{item['action']}** - {item['feature']} - Owner: {item['responsible']} - Status: {item['status']}"
                )
            lines.append("")

        # Due This Week
        if result["topics"]["due_this_week"]:
            lines.append("### Due This Week")
            for item in result["topics"]["due_this_week"]:
                lines.append(
                    f"- [ ] {item['action']} - {item['feature']} - Due: {item['deadline']} - Owner: {item['responsible']}"
                )
            lines.append("")

        # Overdue
        if result["topics"]["overdue"]:
            lines.append("### ⚠️ Overdue")
            for item in result["topics"]["overdue"]:
                lines.append(
                    f"- [!] **{item['action']}** - {item['feature']} - Was due: {item['deadline']} - Owner: {item['responsible']}"
                )
            lines.append("")

        # In Progress
        if result["topics"]["in_progress"]:
            lines.append("### In Progress")
            for item in result["topics"]["in_progress"]:
                lines.append(
                    f"- [~] {item['action']} - {item['feature']} - Owner: {item['responsible']}"
                )
            lines.append("")

        # Recurring This Week
        if result["recurring"]["this_week"]:
            lines.append("### Recurring This Week")
            for task in result["recurring"]["this_week"]:
                cmd = f" (`{task['command']}`)" if task["command"] else ""
                lines.append(f"- [ ] {task['action']} - {task['project']}{cmd}")
            lines.append("")

        return "\n".join(lines)

    def get_daily_plan(
        self, owner: Optional[str] = None, target_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate a daily delivery plan by distributing weekly items across available days.

        Args:
            owner: Filter items by owner (default: all owners)
            target_date: The date to plan for (default: today)

        Returns:
            Dict with daily plan structure
        """
        if target_date is None:
            target_date = datetime.now()

        result = self.sync()
        today = target_date.date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=4)  # Mon-Fri

        # Collect all actionable items
        all_items = []

        # Add overdue items (highest priority)
        for item in result["topics"]["overdue"]:
            if owner and item["responsible"].lower() != owner.lower():
                continue
            all_items.append(
                {
                    **item,
                    "urgency": "overdue",
                    "sort_priority": 0,
                    "suggested_date": today,
                }
            )

        # Add items due this week
        for item in result["topics"]["due_this_week"]:
            if owner and item["responsible"].lower() != owner.lower():
                continue
            deadline = (
                datetime.strptime(item["deadline"], "%Y-%m-%d").date()
                if item["deadline"]
                else week_end
            )
            all_items.append(
                {
                    **item,
                    "urgency": "this_week",
                    "sort_priority": 1 if item["priority"] == "P0" else 2,
                    "suggested_date": (
                        min(deadline - timedelta(days=1), today)
                        if deadline > today
                        else today
                    ),
                }
            )

        # Add P0 items not yet in other lists
        seen_actions = {(i["action"], i["feature"]) for i in all_items}
        for item in result["topics"]["p0_items"]:
            if (item["action"], item["feature"]) in seen_actions:
                continue
            if owner and item["responsible"].lower() != owner.lower():
                continue
            all_items.append(
                {
                    **item,
                    "deadline": None,
                    "urgency": "p0",
                    "sort_priority": 1,
                    "suggested_date": today,
                }
            )

        # Sort by priority and deadline
        all_items.sort(key=lambda x: (x["sort_priority"], x["suggested_date"]))

        # Distribute across days (max 5 items per day to avoid overload)
        MAX_ITEMS_PER_DAY = 5
        daily_schedule = {}

        for i in range(5):  # Mon-Fri
            day = week_start + timedelta(days=i)
            daily_schedule[day.isoformat()] = {
                "date": day.isoformat(),
                "day_name": day.strftime("%A"),
                "items": [],
                "is_today": day == today,
                "is_past": day < today,
            }

        # Assign items to days
        for item in all_items:
            suggested = item["suggested_date"]
            if isinstance(suggested, datetime):
                suggested = suggested.date()

            # Find the best day to schedule
            assigned = False
            for day_offset in range(5):
                candidate = suggested + timedelta(days=day_offset)
                if candidate < week_start:
                    candidate = week_start
                if candidate > week_end:
                    candidate = week_end

                day_key = candidate.isoformat()
                if day_key in daily_schedule:
                    if len(daily_schedule[day_key]["items"]) < MAX_ITEMS_PER_DAY:
                        daily_schedule[day_key]["items"].append(item)
                        assigned = True
                        break

            # If not assigned, add to overflow
            if not assigned:
                if "overflow" not in daily_schedule:
                    daily_schedule["overflow"] = {"items": []}
                daily_schedule["overflow"]["items"].append(item)

        # Build today's focus
        today_key = today.isoformat()
        todays_items = daily_schedule.get(today_key, {}).get("items", [])

        return {
            "target_date": target_date.isoformat(),
            "calendar_week": result["calendar_week"],
            "owner_filter": owner,
            "daily_schedule": daily_schedule,
            "todays_focus": todays_items,
            "total_items": len(all_items),
            "overdue_count": len(result["topics"]["overdue"]),
        }

    def get_daily_plan_markdown(self, owner: Optional[str] = None) -> str:
        """
        Generate markdown-formatted daily plan for context integration.

        Args:
            owner: Filter items by owner (default: all)

        Returns:
            Markdown string for context file integration
        """
        plan = self.get_daily_plan(owner=owner)
        today = datetime.now().date()
        lines = []

        # Today's Focus
        lines.append("## Suggested Daily Plan")
        lines.append(
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | CW{plan['calendar_week']}*"
        )
        lines.append("")

        if plan["overdue_count"] > 0:
            lines.append(
                f"**⚠️ {plan['overdue_count']} overdue items require immediate attention**"
            )
            lines.append("")

        # Today's items
        lines.append("### Today's Focus")
        if plan["todays_focus"]:
            for item in plan["todays_focus"]:
                urgency_marker = (
                    "🔴"
                    if item["urgency"] == "overdue"
                    else ("🟡" if item["priority"] == "P0" else "")
                )
                deadline_str = (
                    f" (due {item['deadline']})" if item.get("deadline") else ""
                )
                lines.append(
                    f"- [ ] {urgency_marker} **{item['action']}** - {item['feature']}{deadline_str} - {item['responsible']}"
                )
        else:
            lines.append("- No items scheduled for today")
        lines.append("")

        # Rest of week preview
        lines.append("### This Week")
        lines.append("| Day | Items | Key Focus |")
        lines.append("|-----|-------|-----------|")

        for day_key, day_data in sorted(plan["daily_schedule"].items()):
            if day_key == "overflow":
                continue
            day_date = datetime.fromisoformat(day_key).date()
            marker = (
                "**→**"
                if day_data["is_today"]
                else ("~~" if day_data["is_past"] else "")
            )
            marker_end = (
                "~~" if day_data["is_past"] and not day_data["is_today"] else ""
            )

            item_count = len(day_data["items"])
            key_item = (
                day_data["items"][0]["action"][:30] + "..."
                if day_data["items"]
                else "-"
            )

            lines.append(
                f"| {marker}{day_data['day_name'][:3]}{marker_end} | {item_count} | {key_item} |"
            )

        lines.append("")

        return "\n".join(lines)

    def get_action_items_for_context(
        self, owner: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get action items formatted for daily context integration.

        Args:
            owner: Filter by owner name

        Returns:
            List of action items with priority and deadline info
        """
        result = self.sync()
        items = []

        # Overdue items first
        for item in result["topics"]["overdue"]:
            if owner and item["responsible"].lower() != owner.lower():
                continue
            items.append(
                {
                    "action": item["action"],
                    "feature": item["feature"],
                    "owner": item["responsible"],
                    "deadline": item["deadline"],
                    "priority": item["priority"],
                    "status": "overdue",
                    "category": "immediate",
                }
            )

        # Due today/tomorrow
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)

        for item in result["topics"]["due_this_week"]:
            if owner and item["responsible"].lower() != owner.lower():
                continue
            deadline_date = (
                datetime.strptime(item["deadline"], "%Y-%m-%d").date()
                if item["deadline"]
                else None
            )

            if deadline_date == today:
                category = "today"
            elif deadline_date == tomorrow:
                category = "tomorrow"
            else:
                category = "this_week"

            items.append(
                {
                    "action": item["action"],
                    "feature": item["feature"],
                    "owner": item["responsible"],
                    "deadline": item["deadline"],
                    "priority": item["priority"],
                    "status": "pending",
                    "category": category,
                }
            )

        return items


def post_weekly_summary_to_slack(summary: str, channel_id: str) -> bool:
    """
    Post weekly summary to Slack channel.

    Args:
        summary: Markdown summary content
        channel_id: Slack channel ID

    Returns:
        True if posted successfully
    """
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError

        sys.path.insert(0, str(Path(__file__).parent.parent))
        import config_loader

        slack_config = config_loader.get_slack_config()
        token = slack_config.get("bot_token")
        if not token:
            print("SLACK_BOT_TOKEN not configured", file=sys.stderr)
            return False

        client = WebClient(token=token)

        # Convert markdown to Slack mrkdwn format
        slack_text = summary.replace("**", "*")  # Bold syntax

        response = client.chat_postMessage(
            channel=channel_id, text=slack_text, mrkdwn=True
        )
        return response["ok"]

    except ImportError:
        print("slack_sdk not installed", file=sys.stderr)
        return False
    except SlackApiError as e:
        print(f"Slack API error: {e.response['error']}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error posting to Slack: {e}", file=sys.stderr)
        return False


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="PM-OS Master Sheet Sync")
    parser.add_argument(
        "--status", action="store_true", help="Show current sync status"
    )
    parser.add_argument(
        "--overdue", action="store_true", help="Show overdue items only"
    )
    parser.add_argument("--week", action="store_true", help="Show current week summary")
    parser.add_argument(
        "--daily", action="store_true", help="Show daily plan with suggested schedule"
    )
    parser.add_argument(
        "--action-items",
        action="store_true",
        help="Get action items for context integration",
    )
    parser.add_argument("--owner", type=str, help="Filter by owner name")
    parser.add_argument(
        "--post-slack", action="store_true", help="Post weekly summary to Slack"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    try:
        sync = MasterSheetSync()

        if args.daily:
            if args.json:
                plan = sync.get_daily_plan(owner=args.owner)
                print(json.dumps(plan, indent=2, default=str))
            else:
                print(sync.get_daily_plan_markdown(owner=args.owner))

        elif args.action_items:
            items = sync.get_action_items_for_context(owner=args.owner)
            print(json.dumps(items, indent=2, default=str))

        elif args.week or args.post_slack:
            summary = sync.get_weekly_summary()
            print(summary)

            if args.post_slack:
                slack_channel = sync.master_config.get("slack_channel", "CXXXXXXXXXX")
                if post_weekly_summary_to_slack(summary, slack_channel):
                    print("\n[OK] Posted to Slack")
                else:
                    print("\n[WARN] Failed to post to Slack")

        elif args.status or args.overdue:
            result = sync.sync()
            if args.overdue:
                result = {"overdue": result["topics"]["overdue"]}
            if args.json:
                print(json.dumps(result, indent=2, default=str))
            else:
                print(json.dumps(result, indent=2, default=str))
        else:
            result = sync.sync()
            print(json.dumps(result, indent=2, default=str))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
