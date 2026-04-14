"""
PM-OS CCE EvidenceDecayMonitor (v5.0)

Monitors FPF evidence for expiration and provides alerts when refresh
is needed. Scans Brain/Reasoning directories and DRRs for evidence
items with expiry dates and reports their status.

Usage:
    from pm_os_cce.tools.reasoning.evidence_decay_monitor import EvidenceDecayMonitor
"""

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from core.config_loader import get_config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Evidence item
# ---------------------------------------------------------------------------


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
        elif days <= 7:
            return "CRITICAL"
        elif days <= 14:
            return "WARNING"
        return "OK"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_expiry_from_content(content: str) -> Optional[datetime]:
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


def _parse_description_from_content(content: str) -> str:
    """Extract a description from the file content."""
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1)[:60]
    match = re.search(r"^title:\s*(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1)[:60]
    return "Untitled"


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def _scan_evidence_directory(evidence_dir: Path) -> List[EvidenceItem]:
    """Scan a directory for evidence files with expiry dates."""
    items: List[EvidenceItem] = []
    if not evidence_dir.exists():
        return items

    for file_path in evidence_dir.glob("**/*.md"):
        try:
            content = file_path.read_text(encoding="utf-8")
            expiry = _parse_expiry_from_content(content)
            if expiry:
                description = _parse_description_from_content(content)
                items.append(
                    EvidenceItem(
                        file_path=file_path,
                        expiry_date=expiry,
                        description=description,
                    )
                )
        except Exception as exc:
            logger.warning("Could not read %s: %s", file_path, exc)

    return items


def _scan_drrs_for_evidence(decisions_dir: Path) -> List[EvidenceItem]:
    """Scan DRRs for embedded evidence with expiry dates."""
    items: List[EvidenceItem] = []
    if not decisions_dir.exists():
        return items

    for drr_path in decisions_dir.glob("drr-*.md"):
        try:
            content = drr_path.read_text(encoding="utf-8")

            # Find all evidence entries with dates in tables
            evidence_pattern = (
                r"\|\s*([^|]+)\s*\|\s*CL\d\s*\|\s*[\d.]+\s*\|"
                r"\s*(\d{4}-\d{2}-\d{2})\s*\|"
            )
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
            main_expiry = _parse_expiry_from_content(content)
            if main_expiry:
                items.append(
                    EvidenceItem(
                        file_path=drr_path,
                        expiry_date=main_expiry,
                        description=f"DRR: {_parse_description_from_content(content)}",
                        drr_ref=drr_path.stem,
                    )
                )
        except Exception as exc:
            logger.warning("Could not read %s: %s", drr_path, exc)

    return items


# ---------------------------------------------------------------------------
# Main monitor class
# ---------------------------------------------------------------------------


class EvidenceDecayMonitor:
    """Monitors FPF evidence for expiration.

    Scans Brain/Reasoning directories and DRRs for evidence with
    expiry dates, categorizes them by urgency, and generates reports.
    """

    def __init__(
        self,
        warning_days: int = 14,
        critical_days: int = 7,
    ):
        """Initialize monitor.

        Args:
            warning_days: Days threshold for WARNING status.
            critical_days: Days threshold for CRITICAL status.
        """
        self.warning_days = warning_days
        self.critical_days = critical_days

        # Resolve paths
        try:
            paths = get_paths()
            self._user_dir = paths.user
        except Exception:
            self._user_dir = Path.cwd() / "user"

        self._brain_dir = self._user_dir / "brain"
        self._reasoning_dir = self._brain_dir / "Reasoning"

    def get_all_evidence(self) -> List[EvidenceItem]:
        """Collect all evidence from Brain and Reasoning directories."""
        all_items: List[EvidenceItem] = []

        # Scan Brain/Reasoning/Evidence
        all_items.extend(_scan_evidence_directory(self._reasoning_dir / "Evidence"))

        # Scan Brain/Reasoning/Decisions for embedded evidence
        all_items.extend(_scan_drrs_for_evidence(self._reasoning_dir / "Decisions"))

        # Deduplicate by file path + description
        seen: set = set()
        unique_items: List[EvidenceItem] = []
        for item in all_items:
            key = (str(item.file_path), item.description)
            if key not in seen:
                seen.add(key)
                unique_items.append(item)

        return sorted(unique_items, key=lambda x: x.expiry_date)

    def filter_by_days(
        self, items: List[EvidenceItem], days: int
    ) -> List[EvidenceItem]:
        """Filter items expiring within *days* days."""
        return [item for item in items if item.days_until_expiry <= days]

    def get_status_summary(
        self, days: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get a structured summary of evidence decay status.

        Args:
            days: Days threshold for filtering (defaults to ``warning_days``).

        Returns:
            Dict with counts by status category and item details.
        """
        if days is None:
            days = self.warning_days

        all_items = self.get_all_evidence()
        filtered = self.filter_by_days(all_items, days)

        expired = [i for i in filtered if i.status == "EXPIRED"]
        critical = [i for i in filtered if i.status == "CRITICAL"]
        warning = [i for i in filtered if i.status == "WARNING"]

        return {
            "generated": datetime.now().isoformat(),
            "threshold_days": days,
            "total_items": len(all_items),
            "items_requiring_attention": len(filtered),
            "expired_count": len(expired),
            "critical_count": len(critical),
            "warning_count": len(warning),
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

    def generate_report(
        self, days: Optional[int] = None
    ) -> str:
        """Generate markdown report of evidence status.

        Args:
            days: Days threshold (defaults to ``warning_days``).

        Returns:
            Markdown-formatted report string.
        """
        if days is None:
            days = self.warning_days

        all_items = self.get_all_evidence()

        lines = [
            "# Evidence Decay Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Threshold:** {days} days",
            f"**Total Items:** {len(all_items)}",
            "",
        ]

        expired = [i for i in all_items if i.status == "EXPIRED"]
        critical = [i for i in all_items if i.status == "CRITICAL"]
        warning = [i for i in all_items if i.status == "WARNING"]

        if expired:
            lines.append("## Expired Evidence")
            lines.append("")
            lines.append("| Evidence | Expired | File | Action |")
            lines.append("|----------|---------|------|--------|")
            for item in expired:
                lines.append(
                    f"| {item.description} "
                    f"| {item.expiry_date.strftime('%Y-%m-%d')} "
                    f"| `{item.file_path}` "
                    f"| **Refresh immediately** |"
                )
            lines.append("")

        if critical:
            lines.append("## Critical (7 days or less)")
            lines.append("")
            lines.append("| Evidence | Expires | Days Left | File |")
            lines.append("|----------|---------|-----------|------|")
            for item in critical:
                lines.append(
                    f"| {item.description} "
                    f"| {item.expiry_date.strftime('%Y-%m-%d')} "
                    f"| {item.days_until_expiry} "
                    f"| `{item.file_path}` |"
                )
            lines.append("")

        if warning:
            lines.append("## Warning (14 days or less)")
            lines.append("")
            lines.append("| Evidence | Expires | Days Left | File |")
            lines.append("|----------|---------|-----------|------|")
            for item in warning:
                lines.append(
                    f"| {item.description} "
                    f"| {item.expiry_date.strftime('%Y-%m-%d')} "
                    f"| {item.days_until_expiry} "
                    f"| `{item.file_path}` |"
                )
            lines.append("")

        if not expired and not critical and not warning:
            lines.append("## All Evidence Fresh")
            lines.append("")
            lines.append("No evidence expiring within the threshold period.")
            lines.append("")

        lines.append("---")
        lines.append("*Run `/reason decay` to refresh expired evidence*")

        return "\n".join(lines)
