"""
Master Sheet Completion Module - Mark Features as Complete

Updates the Master Sheet when a feature is completed:
1. Sets Status = "Done"
2. Adds completion date
3. Adds PRD link
4. Adds Jira epic link (if available)

This module is called at the end of /generate-outputs or /decision-gate
approval to ensure the Master Sheet reflects the feature's complete status.

Usage:
    from tools.context_engine.master_sheet_completion import MasterSheetCompleter

    completer = MasterSheetCompleter()

    # Mark feature as complete
    result = completer.mark_complete(
        feature_path=Path("/path/to/feature"),
        prd_path=Path("/path/to/PRD.md"),
        jira_epic_url="https://atlassian.net/browse/MK-1234",
    )

    # Or just update status
    result = completer.update_status(feature_path, "Done")

    # Add artifact links separately
    result = completer.add_artifact_links(
        feature_path,
        prd_path="/path/to/PRD.md",
        jira_url="https://atlassian.net/browse/MK-1234"
    )

PRD References:
    - Phase 5: Output & Integration
    - Master Sheet topics tab structure
    - Feature completion workflow

Author: PM-OS Team
Version: 1.0.0
"""

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class CompletionResult:
    """Result of a completion operation."""

    success: bool
    feature_name: str = ""
    row_number: Optional[int] = None
    fields_updated: List[str] = field(default_factory=list)
    message: str = ""
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "feature_name": self.feature_name,
            "row_number": self.row_number,
            "fields_updated": self.fields_updated,
            "message": self.message,
            "errors": self.errors,
        }


class MasterSheetCompleter:
    """
    Handles marking features as complete in the Master Sheet.

    Updates the Master Sheet "topics" tab when a feature reaches
    completion status, adding:
    - Status = "Done"
    - Completion date
    - PRD link
    - Jira epic link
    """

    # Column names in Master Sheet
    STATUS_COLUMN = "Current Status"
    COMPLETION_DATE_COLUMN = "Completion Date"
    PRD_LINK_COLUMN = "PRD Link"
    JIRA_LINK_COLUMN = "Jira Link"
    LINK_COLUMN = "Link"  # General link column

    def __init__(self, user_path: Optional[Path] = None):
        """
        Initialize the master sheet completer.

        Args:
            user_path: Path to user/ directory. If None, auto-detected.
        """
        import config_loader

        self._config = config_loader.get_config()
        self._user_path = user_path or Path(self._config.user_path)
        self._raw_config = self._config.config

        # Master sheet config
        self._master_sheet_config = self._raw_config.get("master_sheet", {})
        self._spreadsheet_id = self._master_sheet_config.get("spreadsheet_id")
        self._tabs = self._master_sheet_config.get("tabs", {})
        self._topics_tab = self._tabs.get("topics", "topics")

        # Lazy-loaded services
        self._sheets_service = None
        self._header_map = None

    def _get_sheets_service(self):
        """Get or create Google Sheets service."""
        if self._sheets_service is None:
            import config_loader
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            google_paths = config_loader.get_google_paths()
            token_path = google_paths.get("token")

            if not token_path or not Path(token_path).exists():
                raise ValueError("Google token not found")

            creds = Credentials.from_authorized_user_file(token_path)
            self._sheets_service = build("sheets", "v4", credentials=creds)

        return self._sheets_service

    def _get_header_map(self) -> Dict[str, int]:
        """
        Get column header to index mapping.

        Returns:
            Dictionary mapping column name to column index (0-based)
        """
        if self._header_map is not None:
            return self._header_map

        if not self._master_sheet_config.get("enabled"):
            raise ValueError("Master Sheet integration not enabled")

        service = self._get_sheets_service()

        # Read header row
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=self._spreadsheet_id, range=f"{self._topics_tab}!A1:Z1")
            .execute()
        )

        headers = result.get("values", [[]])[0]
        self._header_map = {col.strip(): i for i, col in enumerate(headers)}

        return self._header_map

    def _col_letter(self, index: int) -> str:
        """Convert column index to letter (A, B, C, ...)."""
        return chr(ord("A") + index)

    def _find_column_index(self, column_name: str) -> Optional[int]:
        """
        Find column index by name, with case-insensitive fallback.

        Args:
            column_name: Column name to find

        Returns:
            Column index or None if not found
        """
        header_map = self._get_header_map()

        # Exact match first
        if column_name in header_map:
            return header_map[column_name]

        # Case-insensitive fallback
        for name, idx in header_map.items():
            if name.lower() == column_name.lower():
                return idx

        return None

    def _update_cell(self, row: int, column: str, value: str) -> bool:
        """
        Update a single cell in the Master Sheet.

        Args:
            row: Row number (1-indexed)
            column: Column name
            value: Value to set

        Returns:
            True if successful
        """
        col_idx = self._find_column_index(column)
        if col_idx is None:
            logger.warning(f"Column '{column}' not found in Master Sheet")
            return False

        service = self._get_sheets_service()
        col_letter = self._col_letter(col_idx)
        cell_range = f"{self._topics_tab}!{col_letter}{row}"

        try:
            service.spreadsheets().values().update(
                spreadsheetId=self._spreadsheet_id,
                range=cell_range,
                valueInputOption="USER_ENTERED",
                body={"values": [[value]]},
            ).execute()
            logger.info(f"Updated {cell_range} to '{value}'")
            return True
        except Exception as e:
            logger.error(f"Failed to update {cell_range}: {e}")
            return False

    def mark_complete(
        self,
        feature_path: Path,
        prd_path: Optional[Path] = None,
        jira_epic_url: Optional[str] = None,
        completion_date: Optional[datetime] = None,
    ) -> CompletionResult:
        """
        Mark a feature as complete in the Master Sheet.

        This is the main entry point for feature completion. It:
        1. Updates Status to "Done"
        2. Sets completion date
        3. Adds PRD link if provided
        4. Adds Jira epic link if provided

        Args:
            feature_path: Path to the feature folder
            prd_path: Path to generated PRD (if any)
            jira_epic_url: URL to Jira epic (if created)
            completion_date: Completion date (defaults to now)

        Returns:
            CompletionResult with operation details
        """
        result = CompletionResult(success=False)

        # Check if Master Sheet is enabled
        if not self._master_sheet_config.get("enabled"):
            result.errors.append("Master Sheet integration not enabled")
            return result

        # Load feature state
        from .feature_state import FeatureState

        state = FeatureState.load(feature_path)
        if not state:
            result.errors.append(f"Feature state not found at {feature_path}")
            return result

        result.feature_name = state.title

        # Get Master Sheet row
        row_number = state.master_sheet_row
        if not row_number:
            # Try to find the row by feature name
            row_number = self._find_feature_row(state.title, state.product_id)
            if not row_number:
                result.errors.append(
                    f"Master Sheet row not found for feature '{state.title}'. "
                    "Please set master_sheet_row in feature-state.yaml or ensure "
                    "the feature exists in the Master Sheet."
                )
                return result

        result.row_number = row_number

        # Use provided date or now
        if completion_date is None:
            completion_date = datetime.now()

        date_str = completion_date.strftime("%m/%d/%Y")  # US format for Master Sheet

        try:
            # 1. Update Status to "Done"
            if self._update_cell(row_number, self.STATUS_COLUMN, "Done"):
                result.fields_updated.append("Status")

            # 2. Update completion date
            # Try dedicated column first, then fall back to adding to notes
            if self._find_column_index(self.COMPLETION_DATE_COLUMN):
                if self._update_cell(row_number, self.COMPLETION_DATE_COLUMN, date_str):
                    result.fields_updated.append("Completion Date")

            # 3. Add PRD link if provided
            if prd_path:
                prd_link = self._format_prd_link(prd_path, state)
                if self._find_column_index(self.PRD_LINK_COLUMN):
                    if self._update_cell(row_number, self.PRD_LINK_COLUMN, prd_link):
                        result.fields_updated.append("PRD Link")
                elif self._find_column_index(self.LINK_COLUMN):
                    # Fall back to generic Link column
                    if self._update_cell(row_number, self.LINK_COLUMN, prd_link):
                        result.fields_updated.append("Link (PRD)")

            # 4. Add Jira epic link if provided
            if jira_epic_url:
                if self._find_column_index(self.JIRA_LINK_COLUMN):
                    if self._update_cell(
                        row_number, self.JIRA_LINK_COLUMN, jira_epic_url
                    ):
                        result.fields_updated.append("Jira Link")

            # Update feature state with completion info
            state.artifacts["completion_date"] = completion_date.isoformat()
            if prd_path:
                state.artifacts["prd_path"] = str(prd_path)
            if jira_epic_url:
                state.artifacts["jira_epic"] = jira_epic_url
            state.save(feature_path)

            result.success = True
            result.message = (
                f"Marked '{state.title}' as complete in Master Sheet "
                f"(row {row_number}). Updated: {', '.join(result.fields_updated)}"
            )

        except Exception as e:
            result.errors.append(f"Failed to update Master Sheet: {str(e)}")
            logger.exception("Error marking feature complete")

        return result

    def update_status(
        self,
        feature_path: Path,
        status: str = "Done",
    ) -> CompletionResult:
        """
        Update the status of a feature in the Master Sheet.

        This is a simpler method that only updates the status field.

        Args:
            feature_path: Path to the feature folder
            status: Status to set (default: "Done")

        Returns:
            CompletionResult with operation details
        """
        result = CompletionResult(success=False)

        if not self._master_sheet_config.get("enabled"):
            result.errors.append("Master Sheet integration not enabled")
            return result

        # Load feature state
        from .feature_state import FeatureState

        state = FeatureState.load(feature_path)
        if not state:
            result.errors.append(f"Feature state not found at {feature_path}")
            return result

        result.feature_name = state.title

        # Get Master Sheet row
        row_number = state.master_sheet_row
        if not row_number:
            row_number = self._find_feature_row(state.title, state.product_id)
            if not row_number:
                result.errors.append(f"Master Sheet row not found for '{state.title}'")
                return result

        result.row_number = row_number

        try:
            if self._update_cell(row_number, self.STATUS_COLUMN, status):
                result.fields_updated.append("Status")
                result.success = True
                result.message = f"Updated '{state.title}' status to '{status}'"
            else:
                result.errors.append("Failed to update status cell")

        except Exception as e:
            result.errors.append(f"Error updating status: {str(e)}")

        return result

    def add_artifact_links(
        self,
        feature_path: Path,
        prd_path: Optional[str] = None,
        jira_url: Optional[str] = None,
    ) -> CompletionResult:
        """
        Add artifact links to a feature in the Master Sheet.

        Args:
            feature_path: Path to the feature folder
            prd_path: Path or URL to PRD
            jira_url: URL to Jira epic

        Returns:
            CompletionResult with operation details
        """
        result = CompletionResult(success=False)

        if not self._master_sheet_config.get("enabled"):
            result.errors.append("Master Sheet integration not enabled")
            return result

        # Load feature state
        from .feature_state import FeatureState

        state = FeatureState.load(feature_path)
        if not state:
            result.errors.append(f"Feature state not found at {feature_path}")
            return result

        result.feature_name = state.title

        # Get Master Sheet row
        row_number = state.master_sheet_row
        if not row_number:
            row_number = self._find_feature_row(state.title, state.product_id)
            if not row_number:
                result.errors.append(f"Master Sheet row not found for '{state.title}'")
                return result

        result.row_number = row_number

        try:
            # Add PRD link
            if prd_path:
                prd_link = prd_path if prd_path.startswith("http") else str(prd_path)
                col = self._find_column_index(
                    self.PRD_LINK_COLUMN
                ) or self._find_column_index(self.LINK_COLUMN)
                if col is not None:
                    col_name = (
                        self.PRD_LINK_COLUMN
                        if self._find_column_index(self.PRD_LINK_COLUMN)
                        else self.LINK_COLUMN
                    )
                    if self._update_cell(row_number, col_name, prd_link):
                        result.fields_updated.append("PRD Link")

            # Add Jira link
            if jira_url:
                if self._find_column_index(self.JIRA_LINK_COLUMN):
                    if self._update_cell(row_number, self.JIRA_LINK_COLUMN, jira_url):
                        result.fields_updated.append("Jira Link")

            result.success = len(result.fields_updated) > 0
            result.message = (
                f"Added links to '{state.title}': {', '.join(result.fields_updated)}"
                if result.success
                else "No links added"
            )

        except Exception as e:
            result.errors.append(f"Error adding artifact links: {str(e)}")

        return result

    def _find_feature_row(self, feature_name: str, product_id: str) -> Optional[int]:
        """
        Find the row number for a feature in the Master Sheet.

        Args:
            feature_name: Feature name to search for
            product_id: Product ID to filter by

        Returns:
            Row number (1-indexed) or None if not found
        """
        try:
            from .master_sheet_reader import MasterSheetReader

            reader = MasterSheetReader()
            topic = reader.find_feature_by_name(feature_name, product_id)
            if topic:
                return topic.row_number
        except Exception as e:
            logger.error(f"Error finding feature row: {e}")

        return None

    def _format_prd_link(self, prd_path: Path, state: Any) -> str:
        """
        Format PRD path as a link for the Master Sheet.

        Args:
            prd_path: Path to the PRD file
            state: FeatureState object

        Returns:
            Formatted link string
        """
        # If it's a full path, try to make it relative to user/
        try:
            if self._user_path in prd_path.parents or prd_path == self._user_path:
                relative = prd_path.relative_to(self._user_path)
                return f"user/{relative}"
        except (ValueError, TypeError):
            pass

        return str(prd_path)


# Convenience functions


def mark_feature_complete(
    feature_path: Path,
    prd_path: Optional[Path] = None,
    jira_epic_url: Optional[str] = None,
) -> CompletionResult:
    """
    Mark a feature as complete in the Master Sheet.

    Convenience function for the common completion workflow.

    Args:
        feature_path: Path to the feature folder
        prd_path: Path to generated PRD
        jira_epic_url: URL to Jira epic

    Returns:
        CompletionResult with operation details
    """
    completer = MasterSheetCompleter()
    return completer.mark_complete(
        feature_path=feature_path,
        prd_path=prd_path,
        jira_epic_url=jira_epic_url,
    )


def update_feature_status(
    feature_path: Path,
    status: str = "Done",
) -> CompletionResult:
    """
    Update feature status in the Master Sheet.

    Args:
        feature_path: Path to the feature folder
        status: Status to set

    Returns:
        CompletionResult with operation details
    """
    completer = MasterSheetCompleter()
    return completer.update_status(feature_path, status)


def add_feature_links(
    feature_path: Path,
    prd_path: Optional[str] = None,
    jira_url: Optional[str] = None,
) -> CompletionResult:
    """
    Add artifact links to a feature in the Master Sheet.

    Args:
        feature_path: Path to the feature folder
        prd_path: Path or URL to PRD
        jira_url: URL to Jira epic

    Returns:
        CompletionResult with operation details
    """
    completer = MasterSheetCompleter()
    return completer.add_artifact_links(
        feature_path=feature_path,
        prd_path=prd_path,
        jira_url=jira_url,
    )
