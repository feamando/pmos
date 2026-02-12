#!/usr/bin/env python3
"""
Evidence Decay Monitoring Tool

Monitors FPF evidence for expiration and sends alerts when refresh is needed.
Integrates with Brain/Reasoning/ and .quint/ directories.

Usage:
    python evidence_decay_monitor.py                    # Check all evidence
    python evidence_decay_monitor.py --days 7           # Items expiring in 7 days
    python evidence_decay_monitor.py --slack            # Send Slack notification
    python evidence_decay_monitor.py --report           # Generate markdown report
    python evidence_decay_monitor.py --cron             # Output for cron scheduling
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add tools directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# --- Configuration ---
ROOT_PATH = config_loader.get_root_path()
USER_PATH = ROOT_PATH / "user"
BRAIN_DIR = USER_PATH / "brain"
REASONING_DIR = BRAIN_DIR / "Reasoning"
QUINT_DIR = ROOT_PATH / ".quint"

# Default warning thresholds
DEFAULT_WARNING_DAYS = 14
DEFAULT_CRITICAL_DAYS = 7
DEFAULT_EXPIRED_GRACE_DAYS = 0


class EvidenceItem:
    """Represents a piece of evidence with expiry tracking."""

    def __init__(
        self,
        file_path: Path,
        expiry_date: datetime,
        description: str = "",
        drr_ref: str = "",
    ):
        self.file_path = file_path
        self.expiry_date = expiry_date
        self.description = description
        self.drr_ref = drr_ref

    @property
    def days_until_expiry(self) -> int:
        return (self.expiry_date - datetime.now()).days

    @property
    def status(self) -> str:
        days = self.days_until_expiry
        if days < 0:
            return "EXPIRED"
        elif days <= DEFAULT_CRITICAL_DAYS:
            return "CRITICAL"
        elif days <= DEFAULT_WARNING_DAYS:
            return "WARNING"
        return "OK"

    @property
    def status_icon(self) -> str:
        icons = {"EXPIRED": "🔴", "CRITICAL": "🟠", "WARNING": "🟡", "OK": "🟢"}
        return icons.get(self.status, "⚪")


def parse_expiry_from_content(content: str) -> Optional[datetime]:
    """Extract expiry date from file content."""
    patterns = [
        r"valid_until:\s*(\d{4}-\d{2}-\d{2})",
        r"[Ee]xpir[ey]s?:\s*(\d{4}-\d{2}-\d{2})",
        r"[Vv]alid\s+until:\s*(\d{4}-\d{2}-\d{2})",
        r"[Ee]xpir[ey]\s+[Dd]ate:\s*(\d{4}-\d{2}-\d{2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y-%m-%d")
            except ValueError:
                continue
    return None


def parse_description_from_content(content: str) -> str:
    """Extract a description from the file content."""
    # Try to get title from markdown header
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1)[:60]

    # Try frontmatter title
    match = re.search(r"^title:\s*(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1)[:60]

    return "Untitled"


def scan_evidence_directory(evidence_dir: Path) -> List[EvidenceItem]:
    """Scan a directory for evidence files with expiry dates."""
    items = []

    if not evidence_dir.exists():
        return items

    for file_path in evidence_dir.glob("**/*.md"):
        try:
            content = file_path.read_text(encoding="utf-8")
            expiry = parse_expiry_from_content(content)

            if expiry:
                description = parse_description_from_content(content)
                items.append(
                    EvidenceItem(
                        file_path=file_path, expiry_date=expiry, description=description
                    )
                )
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)

    return items


def scan_drrs_for_evidence(decisions_dir: Path) -> List[EvidenceItem]:
    """Scan DRRs for embedded evidence with expiry dates."""
    items = []

    if not decisions_dir.exists():
        return items

    for drr_path in decisions_dir.glob("drr-*.md"):
        try:
            content = drr_path.read_text(encoding="utf-8")

            # Find all evidence entries with dates
            evidence_pattern = r"\|\s*([^|]+)\s*\|\s*CL\d\s*\|\s*[\d.]+\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|"
            matches = re.findall(evidence_pattern, content)

            for evidence_name, expiry_str in matches:
                try:
                    expiry = datetime.strptime(expiry_str, "%Y-%m-%d")
                    items.append(
                        EvidenceItem(
                            file_path=drr_path,
                            expiry_date=expiry,
                            description=evidence_name.strip(),
                            drr_ref=drr_path.stem,
                        )
                    )
                except ValueError:
                    continue

            # Also check the main valid_until
            main_expiry = parse_expiry_from_content(content)
            if main_expiry:
                items.append(
                    EvidenceItem(
                        file_path=drr_path,
                        expiry_date=main_expiry,
                        description=f"DRR: {parse_description_from_content(content)}",
                        drr_ref=drr_path.stem,
                    )
                )

        except Exception as e:
            print(f"Warning: Could not read {drr_path}: {e}", file=sys.stderr)

    return items


def get_all_evidence() -> List[EvidenceItem]:
    """Collect all evidence from Brain and Quint directories."""
    all_items = []

    # Scan Brain/Reasoning/Evidence
    all_items.extend(scan_evidence_directory(REASONING_DIR / "Evidence"))

    # Scan Brain/Reasoning/Decisions for embedded evidence
    all_items.extend(scan_drrs_for_evidence(REASONING_DIR / "Decisions"))

    # Scan .quint/evidence if exists
    if (QUINT_DIR / "evidence").exists():
        all_items.extend(scan_evidence_directory(QUINT_DIR / "evidence"))

    # Deduplicate by file path + description
    seen = set()
    unique_items = []
    for item in all_items:
        key = (str(item.file_path), item.description)
        if key not in seen:
            seen.add(key)
            unique_items.append(item)

    return sorted(unique_items, key=lambda x: x.expiry_date)


def filter_by_days(items: List[EvidenceItem], days: int) -> List[EvidenceItem]:
    """Filter items expiring within N days."""
    return [item for item in items if item.days_until_expiry <= days]


def generate_report(items: List[EvidenceItem], days: int) -> str:
    """Generate markdown report of evidence status."""
    lines = [
        f"# Evidence Decay Report",
        f"",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Threshold:** {days} days",
        f"**Total Items:** {len(items)}",
        "",
    ]

    # Group by status
    expired = [i for i in items if i.status == "EXPIRED"]
    critical = [i for i in items if i.status == "CRITICAL"]
    warning = [i for i in items if i.status == "WARNING"]

    if expired:
        lines.append("## 🔴 Expired Evidence")
        lines.append("")
        lines.append("| Evidence | Expired | File | Action |")
        lines.append("|----------|---------|------|--------|")
        for item in expired:
            rel_path = (
                item.file_path.relative_to(REPO_ROOT)
                if REPO_ROOT in item.file_path.parents
                else item.file_path
            )
            lines.append(
                f"| {item.description} | {item.expiry_date.strftime('%Y-%m-%d')} | `{rel_path}` | **Refresh immediately** |"
            )
        lines.append("")

    if critical:
        lines.append("## 🟠 Critical (≤7 days)")
        lines.append("")
        lines.append("| Evidence | Expires | Days Left | File |")
        lines.append("|----------|---------|-----------|------|")
        for item in critical:
            rel_path = (
                item.file_path.relative_to(REPO_ROOT)
                if REPO_ROOT in item.file_path.parents
                else item.file_path
            )
            lines.append(
                f"| {item.description} | {item.expiry_date.strftime('%Y-%m-%d')} | {item.days_until_expiry} | `{rel_path}` |"
            )
        lines.append("")

    if warning:
        lines.append("## 🟡 Warning (≤14 days)")
        lines.append("")
        lines.append("| Evidence | Expires | Days Left | File |")
        lines.append("|----------|---------|-----------|------|")
        for item in warning:
            rel_path = (
                item.file_path.relative_to(REPO_ROOT)
                if REPO_ROOT in item.file_path.parents
                else item.file_path
            )
            lines.append(
                f"| {item.description} | {item.expiry_date.strftime('%Y-%m-%d')} | {item.days_until_expiry} | `{rel_path}` |"
            )
        lines.append("")

    if not expired and not critical and not warning:
        lines.append("## ✅ All Evidence Fresh")
        lines.append("")
        lines.append("No evidence expiring within the threshold period.")
        lines.append("")

    lines.append("---")
    lines.append(f"*Run `/q-decay` to refresh expired evidence*")

    return "\n".join(lines)


def print_summary(items: List[EvidenceItem], days: int):
    """Print summary to console."""
    filtered = filter_by_days(items, days)

    print(f"\n{'='*60}")
    print(f"EVIDENCE DECAY STATUS")
    print(f"{'='*60}")
    print(f"Checking items expiring within {days} days")
    print(f"Total evidence items: {len(items)}")
    print(f"Items requiring attention: {len(filtered)}")
    print(f"{'='*60}\n")

    if not filtered:
        print("✅ All evidence is fresh!")
        return

    for item in filtered:
        icon = item.status_icon
        days_text = (
            f"{item.days_until_expiry}d" if item.days_until_expiry >= 0 else "EXPIRED"
        )
        print(
            f"{icon} [{item.status:8}] {item.description[:40]:40} | {days_text:8} | {item.expiry_date.strftime('%Y-%m-%d')}"
        )

    print(f"\n{'='*60}")


def send_slack_notification(items: List[EvidenceItem], days: int) -> bool:
    """Send Slack notification for expiring evidence."""
    filtered = filter_by_days(items, days)

    if not filtered:
        print("No items to report - skipping Slack notification")
        return True

    expired_count = len([i for i in filtered if i.status == "EXPIRED"])
    critical_count = len([i for i in filtered if i.status == "CRITICAL"])
    warning_count = len([i for i in filtered if i.status == "WARNING"])

    # Build Slack message
    message = {
        "text": f"🔔 FPF Evidence Decay Alert",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🔔 FPF Evidence Decay Alert"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{len(filtered)} evidence items need attention:*\n"
                    f"• 🔴 Expired: {expired_count}\n"
                    f"• 🟠 Critical: {critical_count}\n"
                    f"• 🟡 Warning: {warning_count}",
                },
            },
        ],
    }

    # Add details for critical items
    if expired_count + critical_count > 0:
        urgent_items = [i for i in filtered if i.status in ["EXPIRED", "CRITICAL"]][:5]
        items_text = "\n".join(
            [f"• {i.description[:50]} ({i.status})" for i in urgent_items]
        )

        message["blocks"].append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Urgent items:*\n{items_text}"},
            }
        )

    message["blocks"].append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "_Run `/q-decay` to refresh evidence_"},
        }
    )

    # Note: Actual Slack webhook would go here
    # For now, just print what would be sent
    print("\n[Would send to Slack:]")
    print(json.dumps(message, indent=2))
    print("\nNote: Configure SLACK_WEBHOOK_URL to enable actual notifications")

    return True


def main():
    parser = argparse.ArgumentParser(description="Monitor FPF evidence for expiration")
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_WARNING_DAYS,
        help=f"Report items expiring within N days (default: {DEFAULT_WARNING_DAYS})",
    )
    parser.add_argument("--slack", action="store_true", help="Send Slack notification")
    parser.add_argument(
        "--report", action="store_true", help="Generate markdown report"
    )
    parser.add_argument("--output", type=str, help="Write report to file")
    parser.add_argument(
        "--cron",
        action="store_true",
        help="Output suitable for cron (exit code based on status)",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Collect all evidence
    all_items = get_all_evidence()

    if args.json:
        filtered = filter_by_days(all_items, args.days)
        output = {
            "generated": datetime.now().isoformat(),
            "threshold_days": args.days,
            "total_items": len(all_items),
            "items_requiring_attention": len(filtered),
            "items": [
                {
                    "description": item.description,
                    "expiry_date": item.expiry_date.strftime("%Y-%m-%d"),
                    "days_until_expiry": item.days_until_expiry,
                    "status": item.status,
                    "file": str(item.file_path),
                    "drr_ref": item.drr_ref,
                }
                for item in filtered
            ],
        }
        print(json.dumps(output, indent=2))
        return 0

    if args.report:
        report = generate_report(all_items, args.days)
        if args.output:
            Path(args.output).write_text(report)
            print(f"Report written to {args.output}")
        else:
            print(report)
        return 0

    if args.slack:
        send_slack_notification(all_items, args.days)
        return 0

    # Default: print summary
    print_summary(all_items, args.days)

    # For cron mode, exit with code based on status
    if args.cron:
        filtered = filter_by_days(all_items, args.days)
        expired = any(i.status == "EXPIRED" for i in filtered)
        critical = any(i.status == "CRITICAL" for i in filtered)

        if expired:
            return 2  # Expired evidence
        elif critical:
            return 1  # Critical evidence
        return 0  # All OK

    return 0


if __name__ == "__main__":
    sys.exit(main())
