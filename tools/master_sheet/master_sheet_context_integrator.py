#!/usr/bin/env python3
"""
PM-OS Master Sheet Context Integrator

Formats Master Sheet data for integration into daily context files.
Provides structured sections for: daily plan, action items, deadline tracking.

Usage:
    python3 master_sheet_context_integrator.py                    # Full context section
    python3 master_sheet_context_integrator.py --owner "Nikita"   # Filter by owner
    python3 master_sheet_context_integrator.py --section daily    # Daily plan only
    python3 master_sheet_context_integrator.py --json             # JSON output

Author: PM-OS Team
Version: 1.0.0
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from master_sheet.master_sheet_sync import MasterSheetSync


class MasterSheetContextIntegrator:
    """Formats Master Sheet data for context file integration."""

    def __init__(self, owner: Optional[str] = None):
        """
        Initialize the context integrator.

        Args:
            owner: Filter all data by owner name
        """
        self.owner = owner
        self.sync = MasterSheetSync()
        self._data = None

    @property
    def data(self) -> Dict[str, Any]:
        """Lazy-load sync data."""
        if self._data is None:
            self._data = self.sync.sync()
        return self._data

    def get_critical_alerts_section(self) -> str:
        """Generate Critical Alerts section for context file."""
        lines = ["## Critical Alerts", ""]

        overdue = self.data["topics"]["overdue"]
        p0_items = self.data["topics"]["p0_items"]

        if self.owner:
            overdue = [
                i for i in overdue if i["responsible"].lower() == self.owner.lower()
            ]
            p0_items = [
                i for i in p0_items if i["responsible"].lower() == self.owner.lower()
            ]

        if overdue:
            lines.append(f"- **{len(overdue)} Items NOW OVERDUE:**")
            for item in overdue[:5]:  # Limit to 5
                lines.append(
                    f"  - {item['action']} ({item['priority']}) - {item['feature']} - {item['responsible']}"
                )
            lines.append("")

        # Items due today
        today = datetime.now().date()
        due_today = [
            i
            for i in self.data["topics"]["due_this_week"]
            if i["deadline"]
            and datetime.strptime(i["deadline"], "%Y-%m-%d").date() == today
        ]
        if self.owner:
            due_today = [
                i for i in due_today if i["responsible"].lower() == self.owner.lower()
            ]

        if due_today:
            lines.append(f"- **{len(due_today)} Items due TODAY:**")
            for item in due_today[:5]:
                lines.append(
                    f"  - {item['action']} ({item['priority']}) - {item['feature']} - {item['responsible']}"
                )
            lines.append("")

        # Items due tomorrow
        tomorrow = today + timedelta(days=1)
        due_tomorrow = [
            i
            for i in self.data["topics"]["due_this_week"]
            if i["deadline"]
            and datetime.strptime(i["deadline"], "%Y-%m-%d").date() == tomorrow
        ]
        if self.owner:
            due_tomorrow = [
                i
                for i in due_tomorrow
                if i["responsible"].lower() == self.owner.lower()
            ]

        if due_tomorrow:
            lines.append(f"- **{len(due_tomorrow)} Items due tomorrow:**")
            for item in due_tomorrow[:3]:
                lines.append(
                    f"  - {item['action']} - {item['feature']} - {item['responsible']}"
                )
            lines.append("")

        if not overdue and not due_today and not due_tomorrow:
            lines.append("- No critical alerts")
            lines.append("")

        return "\n".join(lines)

    def get_daily_plan_section(self) -> str:
        """Generate Suggested Daily Plan section."""
        plan = self.sync.get_daily_plan(owner=self.owner)
        today = datetime.now().date()

        lines = [
            "## Suggested Daily Plan",
            f"*CW{plan['calendar_week']} | Generated: {datetime.now().strftime('%H:%M')}*",
            "",
        ]

        # Today's Focus
        lines.append("### Today's Focus")
        if plan["todays_focus"]:
            for idx, item in enumerate(plan["todays_focus"], 1):
                urgency = "🔴 " if item["urgency"] == "overdue" else ""
                priority = f"({item['priority']}) " if item["priority"] == "P0" else ""
                deadline = f" [due {item['deadline']}]" if item.get("deadline") else ""
                lines.append(
                    f"{idx}. {urgency}{priority}**{item['action']}** - {item['feature']}{deadline}"
                )
        else:
            lines.append("- No items scheduled for today")
        lines.append("")

        # Week at a Glance
        lines.append("### Week at a Glance")
        lines.append("| Day | Count | Top Item |")
        lines.append("|-----|-------|----------|")

        for day_key, day_data in sorted(plan["daily_schedule"].items()):
            if day_key == "overflow":
                continue
            day_name = day_data["day_name"][:3]
            marker = (
                "→ "
                if day_data["is_today"]
                else ("  " if not day_data["is_past"] else "~~")
            )
            end_marker = (
                "~~" if day_data["is_past"] and not day_data["is_today"] else ""
            )

            count = len(day_data["items"])
            top_item = (
                day_data["items"][0]["action"][:25] + "..."
                if day_data["items"]
                else "-"
            )

            lines.append(
                f"| {marker}**{day_name}**{end_marker} | {count} | {top_item} |"
            )

        lines.append("")
        return "\n".join(lines)

    def get_action_items_section(self) -> str:
        """Generate Action Items section organized by timeline."""
        items = self.sync.get_action_items_for_context(owner=self.owner)

        lines = ["## Action Items", ""]

        # Group by category
        immediate = [i for i in items if i["category"] == "immediate"]
        today_items = [i for i in items if i["category"] == "today"]
        tomorrow_items = [i for i in items if i["category"] == "tomorrow"]
        week_items = [i for i in items if i["category"] == "this_week"]

        if immediate:
            lines.append("### Immediate - OVERDUE")
            for item in immediate:
                lines.append(
                    f"- [ ] **{item['owner']}** - {item['action']} - {item['feature']} (was due {item['deadline']})"
                )
            lines.append("")

        if today_items:
            lines.append("### Today")
            for item in today_items:
                priority_marker = (
                    f"({item['priority']}) " if item["priority"] == "P0" else ""
                )
                lines.append(
                    f"- [ ] **{item['owner']}** - {priority_marker}{item['action']} - {item['feature']}"
                )
            lines.append("")

        if tomorrow_items:
            lines.append("### Tomorrow")
            for item in tomorrow_items:
                lines.append(
                    f"- [ ] **{item['owner']}** - {item['action']} - {item['feature']}"
                )
            lines.append("")

        if week_items:
            lines.append("### This Week")
            for item in week_items:
                lines.append(
                    f"- [ ] **{item['owner']}** - {item['action']} - {item['feature']} (due {item['deadline']})"
                )
            lines.append("")

        if not items:
            lines.append("- No action items from Master Sheet")
            lines.append("")

        return "\n".join(lines)

    def get_master_sheet_summary_section(self) -> str:
        """Generate Master Sheet Summary table section."""
        cw = self.data["calendar_week"]
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)

        lines = [f"## Master Sheet Summary (CW{cw})", ""]

        # Overdue table
        overdue = self.data["topics"]["overdue"]
        if self.owner:
            overdue = [
                i for i in overdue if i["responsible"].lower() == self.owner.lower()
            ]

        if overdue:
            lines.append("### NOW OVERDUE")
            lines.append("| Item | Feature | Was Due | Owner | Priority |")
            lines.append("|------|---------|---------|-------|----------|")
            for item in overdue:
                lines.append(
                    f"| {item['action']} | {item['feature']} | {item['deadline']} | {item['responsible']} | {item['priority']} |"
                )
            lines.append("")

        # Due Today
        due_today = [
            i
            for i in self.data["topics"]["due_this_week"]
            if i["deadline"]
            and datetime.strptime(i["deadline"], "%Y-%m-%d").date() == today
        ]
        if self.owner:
            due_today = [
                i for i in due_today if i["responsible"].lower() == self.owner.lower()
            ]

        if due_today:
            lines.append("### Due Today")
            lines.append("| Item | Feature | Owner | Priority |")
            lines.append("|------|---------|-------|----------|")
            for item in due_today:
                lines.append(
                    f"| {item['action']} | {item['feature']} | {item['responsible']} | {item['priority']} |"
                )
            lines.append("")

        # Due Tomorrow
        due_tomorrow = [
            i
            for i in self.data["topics"]["due_this_week"]
            if i["deadline"]
            and datetime.strptime(i["deadline"], "%Y-%m-%d").date() == tomorrow
        ]
        if self.owner:
            due_tomorrow = [
                i
                for i in due_tomorrow
                if i["responsible"].lower() == self.owner.lower()
            ]

        if due_tomorrow:
            lines.append(f"### Due Tomorrow ({tomorrow.strftime('%b %d')})")
            lines.append("| Item | Feature | Owner |")
            lines.append("|------|---------|-------|")
            for item in due_tomorrow:
                lines.append(
                    f"| {item['action']} | {item['feature']} | {item['responsible']} |"
                )
            lines.append("")

        # Due This Week (excluding today/tomorrow)
        week_items = [
            i
            for i in self.data["topics"]["due_this_week"]
            if i["deadline"]
            and datetime.strptime(i["deadline"], "%Y-%m-%d").date() > tomorrow
        ]
        if self.owner:
            week_items = [
                i for i in week_items if i["responsible"].lower() == self.owner.lower()
            ]

        if week_items:
            lines.append("### Due This Week")
            lines.append("| Item | Feature | Due | Owner |")
            lines.append("|------|---------|-----|-------|")
            for item in week_items:
                due_date = datetime.strptime(item["deadline"], "%Y-%m-%d").strftime(
                    "%b %d"
                )
                lines.append(
                    f"| {item['action']} | {item['feature']} | {due_date} | {item['responsible']} |"
                )
            lines.append("")

        return "\n".join(lines)

    def get_full_context_section(self) -> str:
        """Generate complete Master Sheet section for context file."""
        sections = [
            self.get_critical_alerts_section(),
            self.get_daily_plan_section(),
            self.get_master_sheet_summary_section(),
            self.get_action_items_section(),
        ]
        return "\n---\n\n".join(sections)

    def get_section(self, section_name: str) -> str:
        """Get a specific section by name."""
        sections = {
            "alerts": self.get_critical_alerts_section,
            "daily": self.get_daily_plan_section,
            "summary": self.get_master_sheet_summary_section,
            "actions": self.get_action_items_section,
            "full": self.get_full_context_section,
        }
        if section_name not in sections:
            raise ValueError(
                f"Unknown section: {section_name}. Valid: {list(sections.keys())}"
            )
        return sections[section_name]()

    def to_json(self) -> Dict[str, Any]:
        """Export all data as JSON for programmatic use."""
        plan = self.sync.get_daily_plan(owner=self.owner)
        action_items = self.sync.get_action_items_for_context(owner=self.owner)

        return {
            "generated_at": datetime.now().isoformat(),
            "calendar_week": self.data["calendar_week"],
            "owner_filter": self.owner,
            "stats": {
                "total_topics": self.data["topics"]["total"],
                "overdue_count": len(self.data["topics"]["overdue"]),
                "due_this_week_count": len(self.data["topics"]["due_this_week"]),
                "p0_count": len(self.data["topics"]["p0_items"]),
                "in_progress_count": len(self.data["topics"]["in_progress"]),
            },
            "daily_plan": plan,
            "action_items": action_items,
            "overdue": self.data["topics"]["overdue"],
            "p0_items": self.data["topics"]["p0_items"],
            "recurring_this_week": self.data["recurring"]["this_week"],
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PM-OS Master Sheet Context Integrator"
    )
    parser.add_argument("--owner", type=str, help="Filter by owner name")
    parser.add_argument(
        "--section",
        type=str,
        choices=["alerts", "daily", "summary", "actions", "full"],
        default="full",
        help="Which section to generate",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    try:
        integrator = MasterSheetContextIntegrator(owner=args.owner)

        if args.json:
            print(json.dumps(integrator.to_json(), indent=2, default=str))
        else:
            print(integrator.get_section(args.section))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
