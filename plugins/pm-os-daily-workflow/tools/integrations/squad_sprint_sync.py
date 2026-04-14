#!/usr/bin/env python3
"""
Squad Sprint Report Sync (v5.0)

Syncs the every-other-week squad sprint report from Google Sheets to Brain.
Generalized from v4.x sprint sync — all org names, spreadsheet IDs,
and tribe filters come from config. Zero hardcoded values.

Usage:
    python3 squad_sprint_sync.py                # Full sync
    python3 squad_sprint_sync.py --status       # Show last sync status
    python3 squad_sprint_sync.py --squad "My Squad"  # Show specific squad
    python3 squad_sprint_sync.py --tribe "My Tribe"  # Filter by tribe
"""

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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

# Column mapping (0-indexed) — matches actual Sprint-N sheet structure
COLUMNS = {
    "mega_alliance": 0,
    "tribe": 1,
    "squad_name": 2,
    "squad_lead": 3,
    "squad_kpi": 4,
    "kpi_movement": 5,
    "delivered": 6,
    "key_learnings": 7,
    "planned": 8,
    "demo": 9,
}


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename on all platforms."""
    name = name.replace("\n", "_").replace("\r", "_")
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = name.replace("&", "and")
    name = name.replace(" ", "_")
    name = re.sub(r"_+", "_", name)
    name = name.strip("_.")
    if name.upper().startswith("EXAMPLE"):
        return ""
    return name


def _resolve_brain_dir() -> Path:
    """Resolve brain directory from config/paths."""
    if get_paths is not None:
        try:
            return get_paths().brain
        except Exception:
            pass
    if get_config is not None:
        try:
            config = get_config()
            if config.user_path:
                return config.user_path / "brain"
        except Exception:
            pass
    return Path.cwd() / "user" / "brain"


def _get_spreadsheet_id() -> str:
    """Get sprint report spreadsheet ID from config."""
    config = get_config() if get_config else None
    if config:
        sheet_id = config.get("integrations.google.sprint_sheet_id")
        if sheet_id:
            return sheet_id
    logger.error("integrations.google.sprint_sheet_id not configured")
    return ""


def _get_google_token_path() -> Optional[str]:
    """Get Google OAuth token path from config."""
    config = get_config() if get_config else None
    if config:
        # Check connector bridge first
        if get_auth is not None:
            auth = get_auth("google")
            if auth.source == "connector":
                logger.info("Google auth via Claude connector")
                return None

        # Fall back to token file
        if config.user_path:
            token_path = config.user_path / ".secrets" / "token.json"
            if token_path.exists():
                return str(token_path)

    return None


def _init_sheets_service():
    """Initialize Google Sheets API service."""
    if not HAS_GOOGLE_API:
        logger.error(
            "Google API libraries not installed. "
            "Run: pip install google-auth google-auth-oauthlib google-api-python-client"
        )
        return None

    token_path = _get_google_token_path()
    if not token_path:
        logger.error("Google token not found. Run OAuth flow first.")
        return None

    creds = Credentials.from_authorized_user_file(token_path)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


@dataclass
class SquadSprintReport:
    """Represents a single squad's sprint report entry."""

    mega_alliance: str
    tribe: str
    squad_name: str
    squad_lead: str
    squad_kpi: str
    kpi_movement: str
    delivered: str
    key_learnings: str
    planned: str
    demo: str = ""
    synced_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_markdown(self) -> str:
        """Convert to markdown format for Brain storage."""
        lines = [
            f"## {self.squad_name}",
            f"**Tribe:** {self.tribe}",
            f"**Mega-Alliance:** {self.mega_alliance}",
        ]

        if self.squad_lead:
            lines.append(f"**Squad Lead:** {self.squad_lead}")

        lines.append("")

        if self.squad_kpi:
            lines.extend(["### Squad KPI", self.squad_kpi, ""])

        lines.extend([
            "### KPI Movement",
            self.kpi_movement or "N/A",
            "",
            "### Delivered (This Sprint)",
            self.delivered or "N/A",
            "",
            "### Planned (Next Sprint)",
            self.planned or "N/A",
        ])

        if self.key_learnings:
            lines.extend(["", "### Key Learnings", self.key_learnings])

        if self.demo:
            lines.extend(["", f"**Demo:** {self.demo}"])

        return "\n".join(lines)


class SquadSprintSync:
    """Syncs squad sprint reports from Google Sheets to Brain."""

    def __init__(self, spreadsheet_id: Optional[str] = None):
        """Initialize sync with Google Sheets credentials."""
        self.spreadsheet_id = spreadsheet_id or _get_spreadsheet_id()
        if not self.spreadsheet_id:
            raise ValueError("Sprint spreadsheet ID not configured")

        brain_dir = _resolve_brain_dir()
        self.output_dir = brain_dir / "Inbox" / "Sprint_Report"
        self.state_file = self.output_dir / "_sync_state.json"

        self.sheets_service = _init_sheets_service()
        if not self.sheets_service:
            raise ValueError("Could not initialize Google Sheets service")

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_sheet_names(self) -> List[str]:
        """Get list of sheet names in the spreadsheet."""
        try:
            result = (
                self.sheets_service.spreadsheets()
                .get(spreadsheetId=self.spreadsheet_id)
                .execute()
            )
            sheets = result.get("sheets", [])
            return [s.get("properties", {}).get("title", "") for s in sheets]
        except Exception as e:
            logger.error("Error getting sheet names: %s", e)
            return []

    def _find_data_sheet(self) -> Optional[str]:
        """Find the current sprint sheet using the Sprint Calendar tab."""
        actual_sheets = self._get_sheet_names()

        # Read Sprint Calendar to find current sprint
        calendar_tab = "Sprint Calendar"
        try:
            calendar_rows = self._read_sheet_data(
                range_name="A1:E30", sheet_name=calendar_tab
            )
        except Exception:
            calendar_rows = []

        target_sheet_name = None
        if calendar_rows:
            for row in calendar_rows[1:]:
                if len(row) >= 5:
                    status = row[3].strip() if len(row) > 3 else ""
                    sheet_name = row[4].strip() if len(row) > 4 else ""
                    if status.lower() == "current" and sheet_name:
                        target_sheet_name = sheet_name
                        break

        # Match against actual tab names (handle prefixes)
        if target_sheet_name:
            if target_sheet_name in actual_sheets:
                return target_sheet_name
            for sheet in actual_sheets:
                if target_sheet_name in sheet:
                    return sheet

        # Fallback: find most recent Sprint-N sheet by date
        sprint_sheets = []
        for sheet in actual_sheets:
            match = re.search(r"Sprint-\d+-(\d{4}-\d{2}-\d{2})", sheet)
            if match:
                sprint_sheets.append((match.group(1), sheet))

        if sprint_sheets:
            sprint_sheets.sort(reverse=True)
            return sprint_sheets[0][1]

        return None

    def _read_sheet_data(
        self, range_name: str = "A2:L100", sheet_name: Optional[str] = None
    ) -> List[List[str]]:
        """Read data from the spreadsheet."""
        try:
            full_range = f"'{sheet_name}'!{range_name}" if sheet_name else range_name
            result = (
                self.sheets_service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=full_range)
                .execute()
            )
            return result.get("values", [])
        except Exception as e:
            logger.error("Error reading sheet: %s", e)
            return []

    def _parse_row(self, row: List[str]) -> Optional[SquadSprintReport]:
        """Parse a row into a SquadSprintReport."""
        if not row or len(row) < 3:
            return None

        squad_name = row[COLUMNS["squad_name"]] if len(row) > COLUMNS["squad_name"] else ""
        if (
            not squad_name
            or squad_name.lower() in ["squad name", "squad", ""]
            or squad_name.upper().startswith("EXAMPLE")
        ):
            return None

        def get_col(col_name: str) -> str:
            idx = COLUMNS.get(col_name, -1)
            return row[idx].strip() if idx >= 0 and len(row) > idx else ""

        return SquadSprintReport(
            mega_alliance=get_col("mega_alliance"),
            tribe=get_col("tribe"),
            squad_name=squad_name.strip(),
            squad_lead=get_col("squad_lead"),
            squad_kpi=get_col("squad_kpi"),
            kpi_movement=get_col("kpi_movement"),
            delivered=get_col("delivered"),
            key_learnings=get_col("key_learnings"),
            planned=get_col("planned"),
            demo=get_col("demo"),
        )

    def sync(
        self, tribe_filter: Optional[str] = None, sheet_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Sync sprint reports from the spreadsheet."""
        logger.info("Syncing Squad Sprint Reports...")
        logger.info("  Spreadsheet: %s", self.spreadsheet_id)

        if not sheet_name:
            sheet_name = self._find_data_sheet()
            logger.info("  Using sheet: %s", sheet_name)

        # Extract sprint metadata from sheet name
        sprint_number = ""
        sprint_date = ""
        if sheet_name:
            match = re.search(r"Sprint-(\d+)-(\d{4}-\d{2}-\d{2})", sheet_name)
            if match:
                sprint_number = match.group(1)
                sprint_date = match.group(2)

        rows = self._read_sheet_data(sheet_name=sheet_name)
        if not rows:
            return {"status": "error", "message": "No data found in spreadsheet"}

        # Parse reports
        reports: List[SquadSprintReport] = []
        for row in rows:
            report = self._parse_row(row)
            if report:
                if tribe_filter and tribe_filter.lower() not in report.tribe.lower():
                    continue
                reports.append(report)

        logger.info("  Found %d squad reports", len(reports))

        # Group by tribe
        tribes: Dict[str, List[SquadSprintReport]] = {}
        for report in reports:
            tribe = report.tribe or "Unknown"
            if tribe not in tribes:
                tribes[tribe] = []
            tribes[tribe].append(report)

        timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

        # 1. Individual squad files
        for report in reports:
            safe_name = _sanitize_filename(report.squad_name)
            if not safe_name:
                continue
            squad_file = self.output_dir / f"{safe_name}.md"
            with open(squad_file, "w", encoding="utf-8") as f:
                f.write("---\n")
                f.write("type: squad_sprint_report\n")
                f.write(f"squad: {report.squad_name}\n")
                f.write(f"tribe: {report.tribe}\n")
                f.write(f"mega_alliance: {report.mega_alliance}\n")
                if sprint_number:
                    f.write(f"sprint: {sprint_number}\n")
                if sprint_date:
                    f.write(f"sprint_date: {sprint_date}\n")
                f.write(f"synced_at: {report.synced_at}\n")
                f.write("source: Squad Sprint Report\n")
                f.write("---\n\n")
                f.write(report.to_markdown())

        # 2. Combined summary
        summary_file = self.output_dir / f"Sprint_Summary_{timestamp}.md"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write("# Squad Sprint Summary\n\n")
            f.write(f"**Synced:** {datetime.now(tz=timezone.utc).isoformat()}\n")
            f.write(
                f"**Source:** [Sprint Report](https://docs.google.com/spreadsheets/d/{self.spreadsheet_id})\n"
            )
            f.write(f"**Squads:** {len(reports)}\n\n")
            f.write("---\n\n")

            for tribe_name, tribe_reports in sorted(tribes.items()):
                f.write(f"# {tribe_name}\n\n")
                for report in tribe_reports:
                    f.write(report.to_markdown())
                    f.write("\n\n---\n\n")

        # 3. Update state file
        state = {
            "last_sync": datetime.now(tz=timezone.utc).isoformat(),
            "spreadsheet_id": self.spreadsheet_id,
            "sprint_number": sprint_number,
            "sprint_date": sprint_date,
            "sheet_name": sheet_name,
            "squads_synced": len(reports),
            "tribes": list(tribes.keys()),
            "squad_names": [r.squad_name for r in reports],
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

        logger.info("  Saved to: %s", self.output_dir)
        logger.info("  Summary: %s", summary_file.name)

        return {
            "status": "success",
            "sprint_number": sprint_number,
            "sprint_date": sprint_date,
            "squads_synced": len(reports),
            "tribes": list(tribes.keys()),
            "output_dir": str(self.output_dir),
            "summary_file": str(summary_file),
        }

    def get_status(self) -> Dict[str, Any]:
        """Get last sync status."""
        if not self.state_file.exists():
            return {"status": "never_synced"}

        with open(self.state_file, encoding="utf-8") as f:
            return json.load(f)

    def get_squad(self, squad_name: str) -> Optional[str]:
        """Get a specific squad's report."""
        safe_name = _sanitize_filename(squad_name)
        if not safe_name:
            return None
        squad_file = self.output_dir / f"{safe_name}.md"
        if squad_file.exists():
            return squad_file.read_text(encoding="utf-8")
        return None


def run_sync(
    tribe_filter: Optional[str] = None,
    spreadsheet_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run squad sprint sync programmatically."""
    try:
        syncer = SquadSprintSync(spreadsheet_id=spreadsheet_id)
        return syncer.sync(tribe_filter=tribe_filter)
    except ValueError as e:
        return {"status": "error", "message": str(e)}


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Sync Squad Sprint Reports to Brain")
    parser.add_argument("--status", action="store_true", help="Show last sync status")
    parser.add_argument("--squad", type=str, help="Show specific squad report")
    parser.add_argument("--tribe", type=str, help="Filter by tribe")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--spreadsheet-id", type=str, help="Override spreadsheet ID")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        syncer = SquadSprintSync(spreadsheet_id=args.spreadsheet_id)

        if args.status:
            status = syncer.get_status()
            print(json.dumps(status, indent=2))
        elif args.squad:
            report = syncer.get_squad(args.squad)
            if report:
                print(report)
            else:
                print(f"No report found for squad: {args.squad}")
                print("Run sync first: python3 squad_sprint_sync.py")
        else:
            result = syncer.sync(tribe_filter=args.tribe)
            print(json.dumps(result, indent=2))

    except Exception as e:
        logger.error("Error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
