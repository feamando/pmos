#!/usr/bin/env python3
"""
HelloTech Sprint Report Sync

Syncs the HelloTech Every Other Week Squad Sprint Report to Brain.
This provides tribe-wide context across all squads in HelloTech.

Spreadsheet: Configure via config.yaml hellotech_sprint.spreadsheet_id

Usage:
    python3 hellotech_sprint_sync.py              # Full sync
    python3 hellotech_sprint_sync.py --status     # Show last sync status
    python3 hellotech_sprint_sync.py --squad "Good Chop"  # Show specific squad
    python3 hellotech_sprint_sync.py --tribe "New Ventures"  # Filter by tribe

Author: PM-OS Team
Version: 1.0.0
"""

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import re

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        _PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
        sys.path.insert(0, str(_PLUGIN_ROOT.parent / "pm-os-base" / "tools" / "core"))
        from config_loader import get_config
    except ImportError:
        get_config = None

# Import config_loader functions needed by this module
try:
    from pm_os_base.tools.core.config_loader import get_root_path, get_google_paths
except ImportError:
    try:
        from config_loader import get_root_path, get_google_paths
    except ImportError:
        get_root_path = None
        get_google_paths = None


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename on all platforms (incl. Windows).

    Handles: newlines, colons, asterisks, question marks, quotes, angle brackets,
    pipes, ampersands, and other characters that are illegal on Windows or
    problematic on Unix.
    """
    # Replace newlines with underscore (common in spreadsheet data)
    name = name.replace("\n", "_").replace("\r", "_")
    # Replace Windows-illegal characters: < > : " / \ | ? *
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    # Replace & with 'and' for readability
    name = name.replace("&", "and")
    # Replace spaces with underscores
    name = name.replace(" ", "_")
    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name)
    # Strip leading/trailing underscores and dots
    name = name.strip("_.")
    # Skip EXAMPLE rows from spreadsheet
    if name.upper().startswith("EXAMPLE"):
        return ""
    return name


# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except ImportError:
    print("Error: Google API libraries not installed")
    print("Run: pip install google-auth google-auth-oauthlib google-api-python-client")
    sys.exit(1)


# Default spreadsheet ID (can be overridden in config)
DEFAULT_SPREADSHEET_ID = os.environ.get("HELLOTECH_SPREADSHEET_ID", "YOUR_SPREADSHEET_ID_HERE")

# Column mapping (0-indexed) - matches actual Sprint-N sheet structure
COLUMNS = {
    "mega_alliance": 0,  # A: Mega-Alliance
    "tribe": 1,  # B: Tribe
    "squad_name": 2,  # C: Squad
    "squad_lead": 3,  # D: Squad Lead
    "squad_kpi": 4,  # E: Squad KPI (description)
    "kpi_movement": 5,  # F: KPI Movement (Since Last Sprint)
    "delivered": 6,  # G: What was delivered in this sprint?
    "key_learnings": 7,  # H: Key learnings from this sprint
    "planned": 8,  # I: What is planned for the next sprint?
    "demo": 9,  # J: Demo
}


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

        lines.extend(
            [
                "### KPI Movement",
                self.kpi_movement or "N/A",
                "",
                "### Delivered (This Sprint)",
                self.delivered or "N/A",
                "",
                "### Planned (Next Sprint)",
                self.planned or "N/A",
            ]
        )

        if self.key_learnings:
            lines.extend(["", "### Key Learnings", self.key_learnings])

        if self.demo:
            lines.extend(["", f"**Demo:** {self.demo}"])

        return "\n".join(lines)


class HelloTechSprintSync:
    """Syncs HelloTech Sprint Reports to Brain."""

    def __init__(self, spreadsheet_id: Optional[str] = None):
        """Initialize the sync with Google Sheets credentials."""
        self.spreadsheet_id = spreadsheet_id or self._get_spreadsheet_id()

        # Get paths
        _root = get_root_path() if get_root_path else Path.home() / "pm-os"
        self.user_path = Path(
            os.environ.get("PM_OS_USER", _root / "user")
        )
        self.brain_path = self.user_path / "brain"
        self.output_dir = self.brain_path / "Inbox" / "HelloTech_Sprint"
        self.state_file = self.output_dir / "_sync_state.json"

        # Initialize Google Sheets service
        self.sheets_service = self._init_sheets_service()

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_spreadsheet_id(self) -> str:
        """Get spreadsheet ID from config or use default."""
        try:
            _root = get_root_path() if get_root_path else Path.home() / "pm-os"
            user_path = Path(
                os.environ.get("PM_OS_USER", _root / "user")
            )
            config_path = user_path / "config.yaml"

            if config_path.exists():
                import yaml

                with open(config_path) as f:
                    config = yaml.safe_load(f)

                hellotech_config = config.get("hellotech_sprint", {})
                return hellotech_config.get("spreadsheet_id", DEFAULT_SPREADSHEET_ID)
        except Exception:
            pass

        return DEFAULT_SPREADSHEET_ID

    def _init_sheets_service(self):
        """Initialize Google Sheets API service."""
        if not get_google_paths:
            raise ValueError("config_loader not available, cannot resolve Google paths")

        google_paths = get_google_paths()
        token_path = google_paths.get("token")

        if not token_path or not Path(token_path).exists():
            raise ValueError(
                f"Google token not found at {token_path}. Run OAuth flow first."
            )

        creds = Credentials.from_authorized_user_file(token_path)
        return build("sheets", "v4", credentials=creds, cache_discovery=False)

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
            print(f"Error getting sheet names: {e}", file=sys.stderr)
            return []

    def _find_data_sheet(self) -> Optional[str]:
        """Find the current sprint sheet using the Sprint Calendar tab.

        The Sprint Calendar has columns: Sprint#, Start Date, End Date, Status, Sheet Name.
        We find the row with Status='Current', get its Sheet Name, then match against
        actual tab names (which may have prefixes like '(THIS ONE) ').
        """
        actual_sheets = self._get_sheet_names()

        # Step 1: Read Sprint Calendar to find current sprint
        calendar_tab = "Sprint Calendar"
        try:
            calendar_rows = self._read_sheet_data(
                range_name="A1:E30", sheet_name=calendar_tab
            )
        except Exception:
            calendar_rows = []

        target_sheet_name = None
        if calendar_rows:
            for row in calendar_rows[1:]:  # Skip header
                if len(row) >= 5:
                    status = row[3].strip() if len(row) > 3 else ""
                    sheet_name = row[4].strip() if len(row) > 4 else ""
                    if status.lower() == "current" and sheet_name:
                        target_sheet_name = sheet_name
                        break

        # Step 2: Match against actual tab names (handle prefixes)
        if target_sheet_name:
            # Exact match first
            if target_sheet_name in actual_sheets:
                return target_sheet_name
            # Fuzzy match, tab names may have prefixes like "(THIS ONE) "
            for sheet in actual_sheets:
                if target_sheet_name in sheet:
                    return sheet

        # Fallback: find most recent Sprint-N sheet by extracting dates
        sprint_sheets = []
        for sheet in actual_sheets:
            # Match "Sprint-N-YYYY-MM-DD" anywhere in the name
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
            # If sheet name provided, prepend it to range
            full_range = f"'{sheet_name}'!{range_name}" if sheet_name else range_name
            result = (
                self.sheets_service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=full_range)
                .execute()
            )
            return result.get("values", [])
        except Exception as e:
            print(f"Error reading sheet: {e}", file=sys.stderr)
            return []

    def _parse_row(self, row: List[str]) -> Optional[SquadSprintReport]:
        """Parse a row into a SquadSprintReport."""
        # Skip empty or header rows
        if not row or len(row) < 3:
            return None

        # Skip if no squad name
        squad_name = (
            row[COLUMNS["squad_name"]] if len(row) > COLUMNS["squad_name"] else ""
        )
        if not squad_name or squad_name.lower() in ["squad name", "squad", ""] or squad_name.upper().startswith("EXAMPLE"):
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
        """
        Sync sprint reports from the spreadsheet.

        Args:
            tribe_filter: Optional tribe name to filter by
            sheet_name: Optional specific sheet name to read from

        Returns:
            Sync result with stats
        """
        print(f"Syncing HelloTech Sprint Reports...")
        print(f"  Spreadsheet: {self.spreadsheet_id}")

        # Find the data sheet if not specified
        if not sheet_name:
            sheet_name = self._find_data_sheet()
            print(f"  Using sheet: {sheet_name}")

        # Extract sprint number and date from sheet name
        sprint_number = ""
        sprint_date = ""
        if sheet_name:
            match = re.search(r"Sprint-(\d+)-(\d{4}-\d{2}-\d{2})", sheet_name)
            if match:
                sprint_number = match.group(1)
                sprint_date = match.group(2)

        # Read data from the identified sheet
        rows = self._read_sheet_data(sheet_name=sheet_name)
        if not rows:
            return {"status": "error", "message": "No data found in spreadsheet"}

        # Parse reports
        reports: List[SquadSprintReport] = []
        for row in rows:
            report = self._parse_row(row)
            if report:
                # Apply tribe filter if specified
                if tribe_filter and tribe_filter.lower() not in report.tribe.lower():
                    continue
                reports.append(report)

        print(f"  Found {len(reports)} squad reports")

        # Group by tribe
        tribes: Dict[str, List[SquadSprintReport]] = {}
        for report in reports:
            tribe = report.tribe or "Unknown"
            if tribe not in tribes:
                tribes[tribe] = []
            tribes[tribe].append(report)

        # Generate output files
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

        # 1. Individual squad files
        for report in reports:
            safe_name = _sanitize_filename(report.squad_name)
            if not safe_name:
                continue  # Skip EXAMPLE rows or empty names
            squad_file = self.output_dir / f"{safe_name}.md"
            with open(squad_file, "w") as f:
                f.write(f"---\n")
                f.write(f"type: hellotech_sprint_report\n")
                f.write(f"squad: {report.squad_name}\n")
                f.write(f"tribe: {report.tribe}\n")
                f.write(f"mega_alliance: {report.mega_alliance}\n")
                if sprint_number:
                    f.write(f"sprint: {sprint_number}\n")
                if sprint_date:
                    f.write(f"sprint_date: {sprint_date}\n")
                f.write(f"synced_at: {report.synced_at}\n")
                f.write(f"source: HelloTech Every Other Week Squad Sprint Report\n")
                f.write(f"---\n\n")
                f.write(report.to_markdown())

        # 2. Combined tribe summary
        summary_file = self.output_dir / f"HelloTech_Sprint_Summary_{timestamp}.md"
        with open(summary_file, "w") as f:
            f.write(f"# HelloTech Sprint Summary\n\n")
            f.write(f"**Synced:** {datetime.now(tz=timezone.utc).isoformat()}\n")
            f.write(
                f"**Source:** [HelloTech Every Other Week Squad Sprint Report](https://docs.google.com/spreadsheets/d/{self.spreadsheet_id})\n"
            )
            f.write(f"**Squads:** {len(reports)}\n\n")
            f.write(f"---\n\n")

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
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

        print(f"  Saved to: {self.output_dir}")
        print(f"  Summary: {summary_file.name}")

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

        with open(self.state_file) as f:
            return json.load(f)

    def get_squad(self, squad_name: str) -> Optional[str]:
        """Get a specific squad's report."""
        safe_name = _sanitize_filename(squad_name)
        if not safe_name:
            return None
        squad_file = self.output_dir / f"{safe_name}.md"
        if squad_file.exists():
            return squad_file.read_text()
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Sync HelloTech Sprint Reports to Brain"
    )
    parser.add_argument("--status", action="store_true", help="Show last sync status")
    parser.add_argument("--squad", type=str, help="Show specific squad report")
    parser.add_argument("--tribe", type=str, help="Filter by tribe")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--spreadsheet-id", type=str, help="Override spreadsheet ID")
    args = parser.parse_args()

    try:
        syncer = HelloTechSprintSync(spreadsheet_id=args.spreadsheet_id)

        if args.status:
            status = syncer.get_status()
            print(json.dumps(status, indent=2))
        elif args.squad:
            report = syncer.get_squad(args.squad)
            if report:
                print(report)
            else:
                print(f"No report found for squad: {args.squad}")
                print("Run sync first: python3 hellotech_sprint_sync.py")
        else:
            result = syncer.sync(tribe_filter=args.tribe)
            print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
