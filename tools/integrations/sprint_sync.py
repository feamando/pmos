#!/usr/bin/env python3
"""
Tech Platform Sprint Report Sync

Syncs the Tech Platform Every Other Week Squad Sprint Report to Brain.
This provides tribe-wide context across all squads in Tech Platform.

Spreadsheet: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_EXAMPLE

Usage:
    python3 tech-platform_sprint_sync.py              # Full sync
    python3 tech-platform_sprint_sync.py --status     # Show last sync status
    python3 tech-platform_sprint_sync.py --squad "Meal Kit"  # Show specific squad
    python3 tech-platform_sprint_sync.py --tribe "Growth Division"  # Filter by tribe

Author: PM-OS Team
Version: 1.0.0
"""

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_loader

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except ImportError:
    print("Error: Google API libraries not installed")
    print("Run: pip install google-auth google-auth-oauthlib google-api-python-client")
    sys.exit(1)


# Default spreadsheet ID (can be overridden in config)
DEFAULT_SPREADSHEET_ID = "SPREADSHEET_ID_EXAMPLE"

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


class Tech PlatformSprintSync:
    """Syncs Tech Platform Sprint Reports to Brain."""

    def __init__(self, spreadsheet_id: Optional[str] = None):
        """Initialize the sync with Google Sheets credentials."""
        self.spreadsheet_id = spreadsheet_id or self._get_spreadsheet_id()

        # Get paths
        self.user_path = Path(
            os.environ.get("PM_OS_USER", config_loader.get_root_path() / "user")
        )
        self.brain_path = self.user_path / "brain"
        self.output_dir = self.brain_path / "Inbox" / "Tech Platform_Sprint"
        self.state_file = self.output_dir / "_sync_state.json"

        # Initialize Google Sheets service
        self.sheets_service = self._init_sheets_service()

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_spreadsheet_id(self) -> str:
        """Get spreadsheet ID from config or use default."""
        try:
            user_path = Path(
                os.environ.get("PM_OS_USER", config_loader.get_root_path() / "user")
            )
            config_path = user_path / "config.yaml"

            if config_path.exists():
                import yaml

                with open(config_path) as f:
                    config = yaml.safe_load(f)

                tech-platform_config = config.get("tech-platform_sprint", {})
                return tech-platform_config.get("spreadsheet_id", DEFAULT_SPREADSHEET_ID)
        except Exception:
            pass

        return DEFAULT_SPREADSHEET_ID

    def _init_sheets_service(self):
        """Initialize Google Sheets API service."""
        google_paths = config_loader.get_google_paths()
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
        """Find the sheet containing squad data - prefers most recent Sprint-N sheet."""
        sheets = self._get_sheet_names()

        # Look for Sprint-N-YYYY-MM-DD pattern (most recent)
        sprint_sheets = []
        for sheet in sheets:
            if sheet.lower().startswith("sprint-") and "-" in sheet[7:]:
                # Extract date from sheet name like "Sprint-2-2026-01-19"
                sprint_sheets.append(sheet)

        if sprint_sheets:
            # Sort by name (date at end) and return most recent
            sprint_sheets.sort(reverse=True)
            return sprint_sheets[0]

        # Fallback: skip instruction sheets
        skip_patterns = ["how-to", "instructions", "template", "example", "calendar"]
        for sheet in sheets:
            sheet_lower = sheet.lower()
            if not any(p in sheet_lower for p in skip_patterns):
                return sheet

        return sheets[0] if sheets else None

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
        if not squad_name or squad_name.lower() in ["squad name", "squad", ""]:
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
        print(f"Syncing Tech Platform Sprint Reports...")
        print(f"  Spreadsheet: {self.spreadsheet_id}")

        # Find the data sheet if not specified
        if not sheet_name:
            sheets = self._get_sheet_names()
            print(f"  Available sheets: {sheets}")
            sheet_name = self._find_data_sheet()
            print(f"  Using sheet: {sheet_name}")

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
        timestamp = datetime.utcnow().strftime("%Y-%m-%d")

        # 1. Individual squad files
        for report in reports:
            squad_file = (
                self.output_dir
                / f"{report.squad_name.replace(' ', '_').replace('/', '-')}.md"
            )
            with open(squad_file, "w") as f:
                f.write(f"---\n")
                f.write(f"type: tech-platform_sprint_report\n")
                f.write(f"squad: {report.squad_name}\n")
                f.write(f"tribe: {report.tribe}\n")
                f.write(f"mega_alliance: {report.mega_alliance}\n")
                f.write(f"synced_at: {report.synced_at}\n")
                f.write(f"source: Tech Platform Every Other Week Squad Sprint Report\n")
                f.write(f"---\n\n")
                f.write(report.to_markdown())

        # 2. Combined tribe summary
        summary_file = self.output_dir / f"Tech Platform_Sprint_Summary_{timestamp}.md"
        with open(summary_file, "w") as f:
            f.write(f"# Tech Platform Sprint Summary\n\n")
            f.write(f"**Synced:** {datetime.utcnow().isoformat()}\n")
            f.write(
                f"**Source:** [Tech Platform Every Other Week Squad Sprint Report](https://docs.google.com/spreadsheets/d/{self.spreadsheet_id})\n"
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
            "last_sync": datetime.utcnow().isoformat(),
            "spreadsheet_id": self.spreadsheet_id,
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
        squad_file = (
            self.output_dir / f"{squad_name.replace(' ', '_').replace('/', '-')}.md"
        )
        if squad_file.exists():
            return squad_file.read_text()
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Sync Tech Platform Sprint Reports to Brain"
    )
    parser.add_argument("--status", action="store_true", help="Show last sync status")
    parser.add_argument("--squad", type=str, help="Show specific squad report")
    parser.add_argument("--tribe", type=str, help="Filter by tribe")
    parser.add_argument("--spreadsheet-id", type=str, help="Override spreadsheet ID")
    args = parser.parse_args()

    try:
        syncer = Tech PlatformSprintSync(spreadsheet_id=args.spreadsheet_id)

        if args.status:
            status = syncer.get_status()
            print(json.dumps(status, indent=2))
        elif args.squad:
            report = syncer.get_squad(args.squad)
            if report:
                print(report)
            else:
                print(f"No report found for squad: {args.squad}")
                print("Run sync first: python3 tech-platform_sprint_sync.py")
        else:
            result = syncer.sync(tribe_filter=args.tribe)
            print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
