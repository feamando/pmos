#!/usr/bin/env python3
"""
Master Sheet Sync (v5.0)

Synchronizes Google Sheets Master Sheet with PM-OS workspace.
Creates feature folders, context files, Brain entities, and tracks actions/deadlines.
All paths via path_resolver, all auth via connector_bridge — zero hardcoded values.

Usage:
    python3 master_sheet_sync.py                # Full sync
    python3 master_sheet_sync.py --status       # Show current status
    python3 master_sheet_sync.py --overdue      # Show overdue items only
    python3 master_sheet_sync.py --week         # Show current week items
    python3 master_sheet_sync.py --daily        # Show daily plan
"""

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# v5 imports: shared utils from pm_os_base
try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
        from tools.core.config_loader import get_config
    except ImportError:
        get_config = None

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        from tools.core.path_resolver import get_paths
    except ImportError:
        get_paths = None

try:
    from pm_os_base.tools.core.connector_bridge import get_auth
except ImportError:
    try:
        from tools.core.connector_bridge import get_auth
    except ImportError:
        get_auth = None

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    HAS_GOOGLE_API = True
except ImportError:
    HAS_GOOGLE_API = False


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


def _resolve_user_path() -> Path:
    """Resolve user directory from config/paths."""
    if get_paths is not None:
        try:
            return get_paths().user
        except Exception:
            pass
    if get_config is not None:
        try:
            config = get_config()
            if config.user_path:
                return config.user_path
        except Exception:
            pass
    return Path.cwd() / "user"


def _get_google_token_path() -> Optional[str]:
    """Get Google OAuth token path from config."""
    config = get_config() if get_config else None
    if config and config.user_path:
        token_path = config.user_path / ".secrets" / "token.json"
        if token_path.exists():
            return str(token_path)
    return None


class MasterSheetSync:
    """Synchronizes Master Sheet with PM-OS workspace."""

    def __init__(self):
        """Initialize sync service."""
        config = get_config() if get_config else None
        if config is None:
            raise ValueError("Config loader not available")

        self.user_path = _resolve_user_path()
        self.master_config = self._get_master_sheet_config(config)

        if not self.master_config.get("enabled"):
            raise ValueError("Master Sheet integration not enabled in config")

        self.spreadsheet_id = self.master_config.get("spreadsheet_id", "")
        if not self.spreadsheet_id:
            raise ValueError("master_sheet.spreadsheet_id not configured")

        self.product_mapping = self.master_config.get("product_mapping", {})
        self.tabs = self.master_config.get("tabs", {})

        # Google Sheets service
        self.sheets_service = self._init_sheets_service()
        if not self.sheets_service:
            raise ValueError("Could not initialize Google Sheets service")

        # Workspace paths
        self.products_path = self.user_path / "products"
        org_id = config.get("organization.id")
        self.org_id = org_id

    def _get_master_sheet_config(self, config) -> Dict[str, Any]:
        """Get master sheet config from config.yaml."""
        return config.get("master_sheet", {}) or {}

    def _init_sheets_service(self):
        """Initialize Google Sheets API service."""
        if not HAS_GOOGLE_API:
            logger.error(
                "Google API libraries not installed. "
                "Run: pip install google-auth google-api-python-client"
            )
            return None

        token_path = _get_google_token_path()
        if not token_path:
            logger.error("Google token not found. Run OAuth flow first.")
            return None

        creds = Credentials.from_authorized_user_file(token_path)
        return build("sheets", "v4", credentials=creds, cache_discovery=False)

    def _get_current_calendar_week(self) -> int:
        """Get current ISO calendar week number."""
        return datetime.now().isocalendar()[1]

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse US format date (MM/DD/YYYY) or ISO format."""
        if not date_str or date_str.strip() == "":
            return None
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
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
            logger.error("Error reading tab %s: %s", tab_name, e)
            return []

    def read_topics(self) -> List[ActionItem]:
        """Read and parse topics tab."""
        tab_name = self.tabs.get("topics", "topics")
        rows = self._read_sheet_tab(tab_name)

        if len(rows) < 2:
            return []

        header = rows[0]
        items = []
        col_map = {col.strip().lower(): i for i, col in enumerate(header)}

        for row in rows[1:]:
            if not row or len(row) < 3:
                continue

            row = row + [""] * (len(header) - len(row))

            cw_status = {}
            for col_name, idx in col_map.items():
                if col_name.startswith("cw") and idx < len(row):
                    cw_status[col_name.upper()] = row[idx]

            item = ActionItem(
                product=row[col_map.get("product", 0)].strip() if col_map.get("product", 0) < len(row) else "",
                feature=row[col_map.get("feature", 1)].strip() if col_map.get("feature", 1) < len(row) else "",
                action=row[col_map.get("action", 2)].strip() if col_map.get("action", 2) < len(row) else "",
                priority=row[col_map.get("priority", 3)].strip() if col_map.get("priority", 3) < len(row) else "P2",
                status=row[col_map.get("current status", 4)].strip() if col_map.get("current status", 4) < len(row) else "To Do",
                responsible=row[col_map.get("responsible", 5)].strip() if col_map.get("responsible", 5) < len(row) else "",
                consulted=row[col_map.get("consulted", 6)].strip() if col_map.get("consulted", 6) < len(row) else "",
                link=row[col_map.get("link", 7)].strip() if col_map.get("link", 7) < len(row) else "",
                deadline=self._parse_date(row[col_map.get("deadline", 8)]) if col_map.get("deadline", 8) < len(row) else None,
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
                domain=row[col_map.get("domain", 0)].strip() if col_map.get("domain", 0) < len(row) else "",
                project=row[col_map.get("project", 1)].strip() if col_map.get("project", 1) < len(row) else "",
                action=row[col_map.get("action", 2)].strip() if col_map.get("action", 2) < len(row) else "",
                priority=row[col_map.get("priority", 3)].strip() if col_map.get("priority", 3) < len(row) else "P2",
                responsible=row[col_map.get("responsible", 4)].strip() if col_map.get("responsible", 4) < len(row) else "",
                consulted=row[col_map.get("consulted", 5)].strip() if col_map.get("consulted", 5) < len(row) else "",
                command=row[col_map.get("command", 6)].strip() if col_map.get("command", 6) < len(row) else "",
                link=row[col_map.get("link", 7)].strip() if col_map.get("link", 7) < len(row) else "",
                recurrence=row[col_map.get("recurrance", 8)].strip() if col_map.get("recurrance", 8) < len(row) else "",
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
        """Ensure feature folder exists, create if not."""
        product_path = self._get_product_folder(item.product)
        feature_slug = self._slugify(item.feature)
        feature_path = product_path / feature_slug

        created = False
        if not feature_path.exists():
            feature_path.mkdir(parents=True, exist_ok=True)
            created = True

        return feature_path, created

    def create_or_update_feature_context(
        self, item: ActionItem, feature_path: Path
    ) -> bool:
        """Create or update feature context file."""
        context_file = feature_path / f"{self._slugify(item.feature)}-context.md"
        today = datetime.now().strftime("%Y-%m-%d")

        if context_file.exists():
            content = context_file.read_text(encoding="utf-8")

            if item.action not in content:
                deadline_str = item.deadline.strftime("%Y-%m-%d") if item.deadline else "N/A"
                new_row = f"| {today} | {item.action} | {item.status} | {item.priority} | {deadline_str} |"

                if "## Action Log" in content:
                    lines = content.split("\n")
                    for i, line in enumerate(lines):
                        if line.startswith("|---"):
                            lines.insert(i + 1, new_row)
                            break
                    content = "\n".join(lines)
                else:
                    content += (
                        f"\n\n## Action Log\n"
                        f"| Date | Action | Status | Priority | Deadline |\n"
                        f"|------|--------|--------|----------|----------|\n"
                        f"{new_row}\n"
                    )

                content = re.sub(r"\*\*Status:\*\* .*", f"**Status:** {item.status}", content)
                content = re.sub(r"\*\*Last Updated:\*\* .*", f"**Last Updated:** {today}", content)

                context_file.write_text(content, encoding="utf-8")
                return True
            return False
        else:
            deadline_str = item.deadline.strftime("%Y-%m-%d") if item.deadline else "N/A"
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

## Changelog
- **{today}**: Context file created from Master Sheet
"""
            context_file.write_text(content, encoding="utf-8")
            return True

    def sync(self) -> Dict[str, Any]:
        """Perform full sync from Master Sheet."""
        result = {
            "timestamp": datetime.now().isoformat(),
            "calendar_week": self._get_current_calendar_week(),
            "topics": {
                "total": 0,
                "folders_created": [],
                "contexts_updated": [],
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
                    feature_path, was_created = self.ensure_feature_folder(item)
                    if was_created:
                        result["topics"]["folders_created"].append(str(feature_path))

                    if self.create_or_update_feature_context(item, feature_path):
                        result["topics"]["contexts_updated"].append(item.feature)

                    if item.is_overdue:
                        result["topics"]["overdue"].append({
                            "feature": item.feature,
                            "action": item.action,
                            "deadline": item.deadline.strftime("%Y-%m-%d") if item.deadline else None,
                            "responsible": item.responsible,
                            "priority": item.priority,
                        })

                    if item.is_due_this_week:
                        result["topics"]["due_this_week"].append({
                            "feature": item.feature,
                            "action": item.action,
                            "deadline": item.deadline.strftime("%Y-%m-%d") if item.deadline else None,
                            "responsible": item.responsible,
                            "priority": item.priority,
                        })

                    if item.priority == "P0" and item.status.lower() != "done":
                        result["topics"]["p0_items"].append({
                            "feature": item.feature,
                            "action": item.action,
                            "status": item.status,
                            "responsible": item.responsible,
                        })

                    if item.status.lower() == "in progress":
                        result["topics"]["in_progress"].append({
                            "feature": item.feature,
                            "action": item.action,
                            "responsible": item.responsible,
                        })

                except Exception as e:
                    result["errors"].append(f"Error processing {item.feature}: {e}")

        except Exception as e:
            result["errors"].append(f"Error reading topics: {e}")

        # Sync recurring
        try:
            recurring = self.read_recurring()
            result["recurring"]["total"] = len(recurring)
            current_cw = f"CW{self._get_current_calendar_week()}"

            for task in recurring:
                cw_status = task.calendar_week_status.get(current_cw, "")
                if cw_status.lower() == "to do":
                    result["recurring"]["this_week"].append({
                        "project": task.project,
                        "action": task.action,
                        "command": task.command,
                        "responsible": task.responsible,
                    })

        except Exception as e:
            result["errors"].append(f"Error reading recurring: {e}")

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

        if result["topics"]["p0_items"]:
            lines.append("### P0 - Critical")
            for item in result["topics"]["p0_items"]:
                lines.append(
                    f"- [ ] **{item['action']}** - {item['feature']} "
                    f"- Owner: {item['responsible']} - Status: {item['status']}"
                )
            lines.append("")

        if result["topics"]["due_this_week"]:
            lines.append("### Due This Week")
            for item in result["topics"]["due_this_week"]:
                lines.append(
                    f"- [ ] {item['action']} - {item['feature']} "
                    f"- Due: {item['deadline']} - Owner: {item['responsible']}"
                )
            lines.append("")

        if result["topics"]["overdue"]:
            lines.append("### Overdue")
            for item in result["topics"]["overdue"]:
                lines.append(
                    f"- [!] **{item['action']}** - {item['feature']} "
                    f"- Was due: {item['deadline']} - Owner: {item['responsible']}"
                )
            lines.append("")

        if result["topics"]["in_progress"]:
            lines.append("### In Progress")
            for item in result["topics"]["in_progress"]:
                lines.append(
                    f"- [~] {item['action']} - {item['feature']} "
                    f"- Owner: {item['responsible']}"
                )
            lines.append("")

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
        """Generate a daily delivery plan by distributing weekly items across days."""
        if target_date is None:
            target_date = datetime.now()

        result = self.sync()
        today = target_date.date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=4)

        all_items = []

        for item in result["topics"]["overdue"]:
            if owner and item["responsible"].lower() != owner.lower():
                continue
            all_items.append({
                **item, "urgency": "overdue", "sort_priority": 0,
                "suggested_date": today,
            })

        for item in result["topics"]["due_this_week"]:
            if owner and item["responsible"].lower() != owner.lower():
                continue
            deadline = (
                datetime.strptime(item["deadline"], "%Y-%m-%d").date()
                if item["deadline"] else week_end
            )
            all_items.append({
                **item, "urgency": "this_week",
                "sort_priority": 1 if item["priority"] == "P0" else 2,
                "suggested_date": min(deadline - timedelta(days=1), today) if deadline > today else today,
            })

        seen_actions = {(i["action"], i["feature"]) for i in all_items}
        for item in result["topics"]["p0_items"]:
            if (item["action"], item["feature"]) in seen_actions:
                continue
            if owner and item["responsible"].lower() != owner.lower():
                continue
            all_items.append({
                **item, "deadline": None, "urgency": "p0",
                "sort_priority": 1, "suggested_date": today,
            })

        all_items.sort(key=lambda x: (x["sort_priority"], x["suggested_date"]))

        MAX_ITEMS_PER_DAY = 5
        daily_schedule = {}
        for i in range(5):
            day = week_start + timedelta(days=i)
            daily_schedule[day.isoformat()] = {
                "date": day.isoformat(),
                "day_name": day.strftime("%A"),
                "items": [],
                "is_today": day == today,
                "is_past": day < today,
            }

        for item in all_items:
            suggested = item["suggested_date"]
            if isinstance(suggested, datetime):
                suggested = suggested.date()
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
            if not assigned:
                if "overflow" not in daily_schedule:
                    daily_schedule["overflow"] = {"items": []}
                daily_schedule["overflow"]["items"].append(item)

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
        """Generate markdown-formatted daily plan."""
        plan = self.get_daily_plan(owner=owner)
        lines = [
            "## Suggested Daily Plan",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | CW{plan['calendar_week']}*",
            "",
        ]

        if plan["overdue_count"] > 0:
            lines.append(f"**{plan['overdue_count']} overdue items require immediate attention**")
            lines.append("")

        lines.append("### Today's Focus")
        if plan["todays_focus"]:
            for item in plan["todays_focus"]:
                deadline_str = f" (due {item['deadline']})" if item.get("deadline") else ""
                lines.append(
                    f"- [ ] **{item['action']}** - {item['feature']}"
                    f"{deadline_str} - {item['responsible']}"
                )
        else:
            lines.append("- No items scheduled for today")
        lines.append("")

        lines.append("### This Week")
        lines.append("| Day | Items | Key Focus |")
        lines.append("|-----|-------|-----------|")

        for day_key, day_data in sorted(plan["daily_schedule"].items()):
            if day_key == "overflow":
                continue
            marker = "**>**" if day_data["is_today"] else ("~~" if day_data["is_past"] else "")
            marker_end = "~~" if day_data["is_past"] and not day_data["is_today"] else ""
            item_count = len(day_data["items"])
            key_item = day_data["items"][0]["action"][:30] + "..." if day_data["items"] else "-"
            lines.append(
                f"| {marker}{day_data['day_name'][:3]}{marker_end} | {item_count} | {key_item} |"
            )

        lines.append("")
        return "\n".join(lines)

    def get_action_items_for_context(
        self, owner: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get action items formatted for daily context integration."""
        result = self.sync()
        items = []

        for item in result["topics"]["overdue"]:
            if owner and item["responsible"].lower() != owner.lower():
                continue
            items.append({
                "action": item["action"], "feature": item["feature"],
                "owner": item["responsible"], "deadline": item["deadline"],
                "priority": item["priority"], "status": "overdue", "category": "immediate",
            })

        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)

        for item in result["topics"]["due_this_week"]:
            if owner and item["responsible"].lower() != owner.lower():
                continue
            deadline_date = (
                datetime.strptime(item["deadline"], "%Y-%m-%d").date()
                if item["deadline"] else None
            )
            if deadline_date == today:
                category = "today"
            elif deadline_date == tomorrow:
                category = "tomorrow"
            else:
                category = "this_week"

            items.append({
                "action": item["action"], "feature": item["feature"],
                "owner": item["responsible"], "deadline": item["deadline"],
                "priority": item["priority"], "status": "pending", "category": category,
            })

        return items


def _post_weekly_summary_to_slack(summary: str) -> bool:
    """Post weekly summary to Slack channel (config-driven)."""
    config = get_config() if get_config else None
    if not config:
        return False

    channel_id = config.get("master_sheet.slack_channel", "")
    if not channel_id:
        logger.warning("master_sheet.slack_channel not configured")
        return False

    if get_auth is not None:
        auth = get_auth("slack")
        if auth.source == "connector":
            logger.info("Slack posting via Claude connector — skipping direct API")
            return False
        elif auth.source == "none":
            logger.warning("Slack auth not available: %s", auth.help_message)
            return False

    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError

        token = config.get_secret("SLACK_BOT_TOKEN")
        if not token:
            logger.warning("SLACK_BOT_TOKEN not configured")
            return False

        client = WebClient(token=token)
        slack_text = summary.replace("**", "*")
        response = client.chat_postMessage(channel=channel_id, text=slack_text, mrkdwn=True)
        return response["ok"]

    except ImportError:
        logger.warning("slack_sdk not installed")
        return False
    except Exception as e:
        logger.error("Error posting to Slack: %s", e)
        return False


def run_sync() -> Dict[str, Any]:
    """Run master sheet sync programmatically."""
    try:
        sync = MasterSheetSync()
        return sync.sync()
    except ValueError as e:
        return {"status": "error", "message": str(e)}


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="PM-OS Master Sheet Sync")
    parser.add_argument("--status", action="store_true", help="Show current sync status")
    parser.add_argument("--overdue", action="store_true", help="Show overdue items only")
    parser.add_argument("--week", action="store_true", help="Show current week summary")
    parser.add_argument("--daily", action="store_true", help="Show daily plan")
    parser.add_argument("--action-items", action="store_true", help="Get action items for context")
    parser.add_argument("--owner", type=str, help="Filter by owner name")
    parser.add_argument("--post-slack", action="store_true", help="Post weekly summary to Slack")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

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
                if _post_weekly_summary_to_slack(summary):
                    print("\n[OK] Posted to Slack")
                else:
                    print("\n[WARN] Failed to post to Slack")

        elif args.status or args.overdue:
            result = sync.sync()
            if args.overdue:
                result = {"overdue": result["topics"]["overdue"]}
            print(json.dumps(result, indent=2, default=str))
        else:
            result = sync.sync()
            print(json.dumps(result, indent=2, default=str))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
