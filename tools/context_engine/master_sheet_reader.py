"""
Master Sheet Reader - Google Sheets Integration for Context Engine

Reads the Master Sheet "topics" tab and parses feature data for
alias matching and feature discovery.

This module provides a lightweight interface to the Master Sheet
specifically designed for the Context Creation Engine's needs:
- Feature name lookup for alias detection
- Product/Status/Owner/Priority/Deadline extraction
- Structured data return for fuzzy matching

Configuration:
    Reads spreadsheet_id from user/config.yaml: master_sheet.spreadsheet_id
    Uses Google credentials from user/.secrets/

Usage:
    from tools.context_engine.master_sheet_reader import MasterSheetReader

    reader = MasterSheetReader()
    topics = reader.get_topics()
    topics_for_product = reader.get_topics_for_product("meal-kit")

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
class TopicEntry:
    """
    Represents a single topic/feature from the Master Sheet.

    Attributes:
        product: Product code (e.g., "MK", "BB")
        feature: Feature name
        action: Current action/task
        priority: Priority level (P0, P1, P2)
        status: Current status (To Do, In Progress, Done)
        owner: Responsible person
        consulted: People consulted
        link: Reference link
        deadline: Optional deadline date
        row_number: Row number in the sheet (for updates)
    """

    product: str
    feature: str
    action: str = ""
    priority: str = "P2"
    status: str = "To Do"
    owner: str = ""
    consulted: str = ""
    link: str = ""
    deadline: Optional[datetime] = None
    row_number: int = 0
    calendar_week_status: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "product": self.product,
            "feature": self.feature,
            "action": self.action,
            "priority": self.priority,
            "status": self.status,
            "owner": self.owner,
            "consulted": self.consulted,
            "link": self.link,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "row_number": self.row_number,
        }


class MasterSheetReaderError(Exception):
    """Base exception for Master Sheet Reader errors."""

    pass


class CredentialsError(MasterSheetReaderError):
    """Raised when Google credentials are missing or invalid."""

    pass


class ConfigurationError(MasterSheetReaderError):
    """Raised when configuration is missing or invalid."""

    pass


class NetworkError(MasterSheetReaderError):
    """Raised when network communication fails."""

    pass


class MasterSheetReader:
    """
    Reads feature/topic data from the Master Sheet for the Context Engine.

    This class provides a simplified interface to the Google Sheets API
    focused on reading the "topics" tab for feature alias matching.
    """

    def __init__(self, spreadsheet_id: Optional[str] = None):
        """
        Initialize the Master Sheet reader.

        Args:
            spreadsheet_id: Optional override for spreadsheet ID.
                          If not provided, reads from config.yaml.

        Raises:
            ConfigurationError: If master_sheet is not configured or disabled.
            CredentialsError: If Google credentials are missing.
        """
        self._spreadsheet_id = spreadsheet_id
        self._sheets_service = None
        self._config = None
        self._product_mapping: Dict[str, str] = {}
        self._tabs: Dict[str, str] = {}

        # Load configuration
        self._load_config()

    def _load_config(self) -> None:
        """
        Load configuration from config.yaml.

        Raises:
            ConfigurationError: If configuration is invalid or missing.
        """
        try:
            import config_loader

            self._config = config_loader.get_config()
            user_path = Path(self._config.user_path)

            # Load master_sheet config
            config_path = user_path / "config.yaml"
            if config_path.exists():
                import yaml

                with open(config_path) as f:
                    full_config = yaml.safe_load(f)
                master_config = full_config.get("master_sheet", {})
            else:
                raise ConfigurationError(f"config.yaml not found at {config_path}")

            # Check if enabled
            if not master_config.get("enabled", False):
                raise ConfigurationError(
                    "Master Sheet integration is not enabled in config.yaml"
                )

            # Get spreadsheet ID (can be overridden in constructor)
            if self._spreadsheet_id is None:
                self._spreadsheet_id = master_config.get("spreadsheet_id")
                if not self._spreadsheet_id:
                    raise ConfigurationError(
                        "master_sheet.spreadsheet_id not configured"
                    )

            # Get tab names
            self._tabs = master_config.get(
                "tabs",
                {
                    "topics": "topics",
                    "recurring": "recurring",
                    "instructions": "how-to",
                },
            )

            # Get product mapping
            self._product_mapping = master_config.get("product_mapping", {})

        except ImportError:
            raise ConfigurationError("config_loader module not available")

    def _get_sheets_service(self):
        """
        Get or create the Google Sheets API service.

        Returns:
            Google Sheets API service object.

        Raises:
            CredentialsError: If credentials are missing or invalid.
            NetworkError: If unable to connect to Google APIs.
        """
        if self._sheets_service is not None:
            return self._sheets_service

        try:
            import config_loader
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError

            # Get Google credential paths
            google_paths = config_loader.get_google_paths()
            token_path = google_paths.get("token")

            if not token_path or not Path(token_path).exists():
                raise CredentialsError(
                    f"Google token not found at {token_path}. "
                    "Run Google OAuth flow to generate credentials."
                )

            # Load credentials
            creds = Credentials.from_authorized_user_file(token_path)

            # Build service
            self._sheets_service = build("sheets", "v4", credentials=creds)
            return self._sheets_service

        except ImportError as e:
            raise CredentialsError(
                f"Required Google libraries not installed: {e}. "
                "Install with: pip install google-auth google-auth-oauthlib google-api-python-client"
            )
        except FileNotFoundError as e:
            raise CredentialsError(f"Credentials file not found: {e}")
        except Exception as e:
            if "HttpError" in str(type(e).__name__):
                raise NetworkError(f"Failed to connect to Google Sheets API: {e}")
            raise CredentialsError(f"Failed to authenticate with Google: {e}")

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse a date string from the sheet.

        Supports formats:
        - MM/DD/YYYY (US format)
        - YYYY-MM-DD (ISO format)

        Args:
            date_str: Date string to parse

        Returns:
            datetime object or None if parsing fails
        """
        if not date_str or date_str.strip() == "":
            return None

        date_str = date_str.strip()

        # Try US format first (common in Google Sheets)
        try:
            return datetime.strptime(date_str, "%m/%d/%Y")
        except ValueError:
            pass

        # Try ISO format
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            pass

        # Try other common formats
        for fmt in ["%d/%m/%Y", "%m-%d-%Y", "%d-%m-%Y"]:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        logger.debug(f"Could not parse date: {date_str}")
        return None

    def _read_sheet_tab(self, tab_name: str) -> List[List[str]]:
        """
        Read all data from a sheet tab.

        Args:
            tab_name: Name of the tab to read

        Returns:
            List of rows, each row is a list of cell values

        Raises:
            NetworkError: If unable to read from the sheet
        """
        try:
            service = self._get_sheets_service()
            result = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=self._spreadsheet_id, range=f"{tab_name}!A1:Z200")
                .execute()
            )
            return result.get("values", [])

        except Exception as e:
            error_str = str(e)
            if "HttpError" in str(type(e).__name__) or "HTTPError" in error_str:
                raise NetworkError(f"Failed to read sheet tab '{tab_name}': {e}")
            raise

    def get_topics(self) -> List[TopicEntry]:
        """
        Read and parse all topics from the Master Sheet.

        Returns:
            List of TopicEntry objects

        Raises:
            NetworkError: If unable to read from the sheet
            ConfigurationError: If sheet structure is unexpected
        """
        tab_name = self._tabs.get("topics", "topics")

        try:
            rows = self._read_sheet_tab(tab_name)
        except NetworkError:
            raise
        except Exception as e:
            raise NetworkError(f"Failed to read topics: {e}")

        if len(rows) < 2:
            logger.warning(f"Topics tab '{tab_name}' has no data rows")
            return []

        # Parse header to find column indices
        header = rows[0]
        col_map = {col.strip().lower(): i for i, col in enumerate(header)}

        # Map expected columns to their indices
        product_idx = col_map.get("product", 0)
        feature_idx = col_map.get("feature", 1)
        action_idx = col_map.get("action", 2)
        priority_idx = col_map.get("priority", 3)
        status_idx = col_map.get("current status", col_map.get("status", 4))
        owner_idx = col_map.get("responsible", col_map.get("owner", 5))
        consulted_idx = col_map.get("consulted", 6)
        link_idx = col_map.get("link", 7)
        deadline_idx = col_map.get("deadline", 8)

        topics = []

        for row_num, row in enumerate(rows[1:], start=2):
            if not row or len(row) < 2:
                continue

            # Pad row to match header length
            row = row + [""] * (len(header) - len(row))

            # Extract values with bounds checking
            def get_value(idx: int) -> str:
                return row[idx].strip() if idx < len(row) else ""

            product = get_value(product_idx)
            feature = get_value(feature_idx)

            # Skip rows without product or feature
            if not product or not feature:
                continue

            # Parse calendar week statuses
            cw_status = {}
            for col_name, idx in col_map.items():
                if col_name.startswith("cw") and idx < len(row):
                    cw_status[col_name.upper()] = row[idx]

            topic = TopicEntry(
                product=product,
                feature=feature,
                action=get_value(action_idx),
                priority=get_value(priority_idx) or "P2",
                status=get_value(status_idx) or "To Do",
                owner=get_value(owner_idx),
                consulted=get_value(consulted_idx),
                link=get_value(link_idx),
                deadline=self._parse_date(get_value(deadline_idx)),
                row_number=row_num,
                calendar_week_status=cw_status,
            )

            topics.append(topic)

        logger.debug(f"Loaded {len(topics)} topics from Master Sheet")
        return topics

    def get_topics_for_product(self, product_id: str) -> List[TopicEntry]:
        """
        Get topics filtered by product.

        Args:
            product_id: Product identifier (e.g., "meal-kit" or "MK")

        Returns:
            List of TopicEntry objects for the specified product
        """
        all_topics = self.get_topics()

        # Resolve product ID to abbreviation
        # Check if product_id is already an abbreviation
        abbrev = product_id.upper()

        # If it's a full ID, look up the abbreviation
        id_to_abbrev = {v: k for k, v in self._product_mapping.items()}
        if product_id.lower() in id_to_abbrev:
            abbrev = id_to_abbrev[product_id.lower()]

        # Also check exact matches
        matching_topics = []
        for topic in all_topics:
            topic_product_upper = topic.product.upper()
            if (
                topic_product_upper == abbrev
                or topic.product.lower() == product_id.lower()
                or self._product_mapping.get(topic_product_upper, "").lower()
                == product_id.lower()
            ):
                matching_topics.append(topic)

        return matching_topics

    def get_feature_names(self, product_id: Optional[str] = None) -> List[str]:
        """
        Get list of unique feature names.

        Args:
            product_id: Optional product filter

        Returns:
            List of unique feature names
        """
        if product_id:
            topics = self.get_topics_for_product(product_id)
        else:
            topics = self.get_topics()

        return list(set(topic.feature for topic in topics))

    def find_feature_by_name(
        self, feature_name: str, product_id: Optional[str] = None
    ) -> Optional[TopicEntry]:
        """
        Find a feature by exact name match.

        Args:
            feature_name: Feature name to search for
            product_id: Optional product filter

        Returns:
            TopicEntry if found, None otherwise
        """
        if product_id:
            topics = self.get_topics_for_product(product_id)
        else:
            topics = self.get_topics()

        for topic in topics:
            if topic.feature.lower() == feature_name.lower():
                return topic

        return None

    def get_features_for_alias_matching(self, product_id: str) -> List[Dict[str, Any]]:
        """
        Get feature data formatted for alias matching.

        Returns data in the format expected by AliasManager.

        Args:
            product_id: Product to get features for

        Returns:
            List of dicts with: name, slug, aliases, row, source
        """
        topics = self.get_topics_for_product(product_id)

        features = []
        for topic in topics:
            features.append(
                {
                    "name": topic.feature,
                    "slug": None,  # Master Sheet doesn't have slugs
                    "aliases": [],  # No aliases stored in Master Sheet
                    "row": topic.row_number,
                    "source": "master_sheet",
                    "product": topic.product,
                    "status": topic.status,
                    "owner": topic.owner,
                    "priority": topic.priority,
                    "deadline": topic.deadline,
                }
            )

        return features

    @property
    def product_mapping(self) -> Dict[str, str]:
        """Get the product abbreviation to ID mapping."""
        return self._product_mapping

    @property
    def spreadsheet_id(self) -> str:
        """Get the configured spreadsheet ID."""
        return self._spreadsheet_id


# Convenience function for quick access
def get_master_sheet_topics(product_id: Optional[str] = None) -> List[TopicEntry]:
    """
    Quick access to get topics from the Master Sheet.

    Args:
        product_id: Optional product filter

    Returns:
        List of TopicEntry objects

    Raises:
        MasterSheetReaderError: If unable to read from sheet
    """
    reader = MasterSheetReader()
    if product_id:
        return reader.get_topics_for_product(product_id)
    return reader.get_topics()
