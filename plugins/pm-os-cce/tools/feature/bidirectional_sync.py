"""
PM-OS CCE Bidirectional Sync (v5.0)

Three-way synchronization between Master Sheet (Google Sheets),
context file ({feature}-context.md), and feature-state.yaml.
Uses connector_bridge for Google Sheets auth instead of direct API.

Usage:
    from pm_os_cce.tools.feature.bidirectional_sync import BidirectionalSync, SyncResult
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from core.config_loader import get_config
    except ImportError:
        get_config = None

logger = logging.getLogger(__name__)


class SyncDirection(Enum):
    """Direction of synchronization."""

    STATE_TO_OTHERS = "state_to_others"
    CONTEXT_TO_OTHERS = "context_to_others"
    MASTER_SHEET_TO_OTHERS = "master_sheet_to_others"


class SyncField(Enum):
    """Fields that can be synchronized."""

    STATUS = "status"
    PRIORITY = "priority"
    OWNER = "owner"
    DEADLINE = "deadline"
    ACTION_LOG = "action_log"
    REFERENCES = "references"
    CHANGELOG = "changelog"


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    direction: Optional[SyncDirection] = None
    fields_updated: List[str] = field(default_factory=list)
    message: str = ""
    errors: List[str] = field(default_factory=list)
    context_file_updated: bool = False
    master_sheet_updated: bool = False
    feature_state_updated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "direction": self.direction.value if self.direction else None,
            "fields_updated": self.fields_updated,
            "message": self.message,
            "errors": self.errors,
            "context_file_updated": self.context_file_updated,
            "master_sheet_updated": self.master_sheet_updated,
            "feature_state_updated": self.feature_state_updated,
        }


@dataclass
class FieldMapping:
    """Mapping between data sources for a field."""

    state_path: str
    context_regex: str
    context_template: str
    master_sheet_column: str


# Field mappings for sync
FIELD_MAPPINGS = {
    "status": FieldMapping(
        state_path="engine.current_phase",
        context_regex=r"\*\*Status:\*\*\s*(.+)",
        context_template="**Status:** {value}",
        master_sheet_column="Current Status",
    ),
    "priority": FieldMapping(
        state_path="artifacts.priority",
        context_regex=r"\*\*Priority:\*\*\s*(.+)",
        context_template="**Priority:** {value}",
        master_sheet_column="Priority",
    ),
    "owner": FieldMapping(
        state_path="created_by",
        context_regex=r"\*\*Owner:\*\*\s*(.+)",
        context_template="**Owner:** {value}",
        master_sheet_column="Responsible",
    ),
    "deadline": FieldMapping(
        state_path="artifacts.deadline",
        context_regex=r"\*\*Deadline:\*\*\s*(.+)",
        context_template="**Deadline:** {value}",
        master_sheet_column="Deadline",
    ),
    "last_updated": FieldMapping(
        state_path="",
        context_regex=r"\*\*Last Updated:\*\*\s*(.+)",
        context_template="**Last Updated:** {value}",
        master_sheet_column="",
    ),
}


class BidirectionalSync:
    """Manages bidirectional synchronization between Master Sheet, context files,
    and feature-state.yaml. Uses connector_bridge for Google Sheets auth.
    """

    def __init__(self, user_path: Optional[Path] = None):
        """Initialize the bidirectional sync manager.

        Args:
            user_path: Path to user/ directory. If None, auto-detected from config.
        """
        self._config = None
        self._user_path = user_path
        self._raw_config = {}
        self._master_sheet_config = {}
        self._product_mapping = {}

        if get_config is not None:
            try:
                self._config = get_config()
                self._user_path = user_path or Path(self._config.user_path)
                self._raw_config = self._config.config if hasattr(self._config, "config") else {}
                self._master_sheet_config = self._raw_config.get("master_sheet", {})
                self._product_mapping = self._master_sheet_config.get("product_mapping", {})
            except Exception:
                pass

        self._master_sheet_reader = None
        self._connector_bridge = None

    def _get_master_sheet_reader(self):
        """Get or create MasterSheetReader instance."""
        if self._master_sheet_reader is None:
            try:
                from pm_os_cce.tools.integration.master_sheet_reader import MasterSheetReader
            except ImportError:
                from integration.master_sheet_reader import MasterSheetReader

            self._master_sheet_reader = MasterSheetReader()
        return self._master_sheet_reader

    def _get_connector_bridge(self):
        """Get or create connector_bridge for Google Sheets auth."""
        if self._connector_bridge is None:
            try:
                from pm_os_base.tools.core.connector_bridge import get_connector_bridge
            except ImportError:
                try:
                    from core.connector_bridge import get_connector_bridge
                except ImportError:
                    return None

            self._connector_bridge = get_connector_bridge()
        return self._connector_bridge

    def _derive_status_from_tracks(self, state_data: Dict[str, Any]) -> str:
        """Derive status from track completion states (PRD C.5 rule)."""
        engine = state_data.get("engine", {})
        tracks = engine.get("tracks", {})

        if not tracks:
            return "To Do"

        statuses = [track.get("status", "not_started") for track in tracks.values()]

        if all(s == "complete" for s in statuses):
            return "Done"

        if any(
            s in ("in_progress", "pending_input", "pending_approval") for s in statuses
        ):
            return "In Progress"

        return "To Do"

    def _load_feature_state(self, feature_path: Path) -> Optional[Dict[str, Any]]:
        """Load feature-state.yaml as a dictionary."""
        state_file = feature_path / "feature-state.yaml"
        if not state_file.exists():
            return None

        with open(state_file, "r") as f:
            return yaml.safe_load(f)

    def _save_feature_state(
        self, feature_path: Path, state_data: Dict[str, Any]
    ) -> bool:
        """Save feature-state.yaml."""
        state_file = feature_path / "feature-state.yaml"
        try:
            with open(state_file, "w") as f:
                yaml.dump(
                    state_data,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )
            return True
        except (IOError, OSError) as e:
            logger.error(f"Failed to save feature state: {e}")
            return False

    def _load_context_file(self, context_path: Path) -> Optional[str]:
        """Load context file content."""
        if not context_path.exists():
            return None
        return context_path.read_text(encoding="utf-8")

    def _save_context_file(self, context_path: Path, content: str) -> bool:
        """Save context file content."""
        try:
            context_path.write_text(content, encoding="utf-8")
            return True
        except (IOError, OSError) as e:
            logger.error(f"Failed to save context file: {e}")
            return False

    def _parse_context_field(self, content: str, field_name: str) -> Optional[str]:
        """Parse a field value from context file content."""
        mapping = FIELD_MAPPINGS.get(field_name)
        if not mapping:
            return None

        match = re.search(mapping.context_regex, content)
        if match:
            return match.group(1).strip()
        return None

    def _update_context_field(
        self, content: str, field_name: str, new_value: str
    ) -> str:
        """Update a field value in context file content."""
        mapping = FIELD_MAPPINGS.get(field_name)
        if not mapping:
            return content

        pattern = mapping.context_regex
        replacement = mapping.context_template.format(value=new_value)

        new_content, count = re.subn(pattern, replacement, content)

        if count == 0:
            logger.debug(f"Field {field_name} not found in context file")

        return new_content

    def _parse_action_log(self, content: str) -> List[Dict[str, str]]:
        """Parse action log table from context file."""
        actions = []

        log_match = re.search(
            r"## Action Log\n\| Date \| Action \| Status \| Priority \| Deadline \|\n\|[-]+\|[-]+\|[-]+\|[-]+\|[-]+\|\n((?:\|[^\n]+\|\n?)+)",
            content,
        )

        if not log_match:
            return actions

        rows = log_match.group(1).strip().split("\n")
        for row in rows:
            parts = [p.strip() for p in row.split("|") if p.strip()]
            if len(parts) >= 5:
                actions.append(
                    {
                        "date": parts[0],
                        "action": parts[1],
                        "status": parts[2],
                        "priority": parts[3],
                        "deadline": parts[4],
                    }
                )

        return actions

    def _add_action_log_entry(
        self, content: str, action: str, status: str, priority: str, deadline: str
    ) -> str:
        """Add a new entry to the action log in context file."""
        today = datetime.now().strftime("%Y-%m-%d")
        new_row = f"| {today} | {action} | {status} | {priority} | {deadline} |"

        pattern = r"(\| Date \| Action \| Status \| Priority \| Deadline \|\n\|[-]+\|[-]+\|[-]+\|[-]+\|[-]+\|)"
        match = re.search(pattern, content)

        if match:
            insert_pos = match.end()
            return content[:insert_pos] + "\n" + new_row + content[insert_pos:]

        return content

    def _update_changelog(self, content: str, phase: str) -> str:
        """Update changelog section with new phase completion."""
        today = datetime.now().strftime("%Y-%m-%d")
        new_entry = f"- **{today}**: {phase} completed"

        changelog_match = re.search(r"(## Changelog\n)", content)
        if changelog_match:
            insert_pos = changelog_match.end()
            return content[:insert_pos] + new_entry + "\n" + content[insert_pos:]

        return content

    def _update_references_section(
        self, content: str, artifacts: Dict[str, Optional[str]]
    ) -> str:
        """Update references section with artifact links."""
        ref_lines = []
        artifact_labels = {
            "jira_epic": "Jira Epic",
            "figma": "Figma",
            "confluence_page": "Confluence",
            "wireframes_url": "Wireframes",
        }

        for key, label in artifact_labels.items():
            url = artifacts.get(key)
            if url:
                ref_lines.append(f"- [{label}]({url})")

        if not ref_lines:
            ref_lines.append("- *No links yet*")

        refs_content = "\n".join(ref_lines)

        pattern = r"(## References\n)((?:- [^\n]+\n?)+)"
        replacement = f"\\1{refs_content}\n"

        new_content = re.sub(pattern, replacement, content)

        return new_content

    def sync_from_state(self, feature_path: Path) -> SyncResult:
        """Sync from feature-state.yaml to context file and Master Sheet."""
        result = SyncResult(success=False, direction=SyncDirection.STATE_TO_OTHERS)

        state_data = self._load_feature_state(feature_path)
        if not state_data:
            result.errors.append(f"Feature state not found at {feature_path}")
            return result

        context_file_name = state_data.get("context_file")
        if not context_file_name:
            context_file_name = f"{state_data.get('slug', 'feature')}-context.md"

        context_path = feature_path / context_file_name
        content = self._load_context_file(context_path)

        if content is None:
            result.errors.append(f"Context file not found at {context_path}")
            return result

        derived_status = self._derive_status_from_tracks(state_data)

        content = self._update_context_field(content, "status", derived_status)
        result.fields_updated.append("status")

        today = datetime.now().strftime("%Y-%m-%d")
        content = self._update_context_field(content, "last_updated", today)
        result.fields_updated.append("last_updated")

        artifacts = state_data.get("artifacts", {})
        content = self._update_references_section(content, artifacts)
        result.fields_updated.append("references")

        if self._save_context_file(context_path, content):
            result.context_file_updated = True
        else:
            result.errors.append("Failed to save context file")

        master_sheet_row = state_data.get("master_sheet_row")
        if master_sheet_row and self._master_sheet_config.get("enabled"):
            try:
                self._update_master_sheet_row(
                    row_number=master_sheet_row,
                    updates={"Current Status": derived_status},
                )
                result.master_sheet_updated = True
            except Exception as e:
                result.errors.append(f"Failed to update Master Sheet: {e}")

        result.success = len(result.errors) == 0
        result.message = (
            f"Synced {len(result.fields_updated)} fields from state to context file"
        )

        return result

    def sync_from_context(self, feature_path: Path) -> SyncResult:
        """Sync from context file to feature-state.yaml and Master Sheet."""
        result = SyncResult(success=False, direction=SyncDirection.CONTEXT_TO_OTHERS)

        state_data = self._load_feature_state(feature_path)
        if not state_data:
            result.errors.append(f"Feature state not found at {feature_path}")
            return result

        context_file_name = state_data.get("context_file")
        if not context_file_name:
            context_file_name = f"{state_data.get('slug', 'feature')}-context.md"

        context_path = feature_path / context_file_name
        content = self._load_context_file(context_path)

        if content is None:
            result.errors.append(f"Context file not found at {context_path}")
            return result

        context_status = self._parse_context_field(content, "status")
        context_priority = self._parse_context_field(content, "priority")
        context_owner = self._parse_context_field(content, "owner")
        context_deadline = self._parse_context_field(content, "deadline")

        master_sheet_updates = {}

        if context_status:
            master_sheet_updates["Current Status"] = context_status
            result.fields_updated.append("status")

        if context_priority:
            master_sheet_updates["Priority"] = context_priority
            result.fields_updated.append("priority")

        if context_owner:
            master_sheet_updates["Responsible"] = context_owner
            result.fields_updated.append("owner")

        if context_deadline:
            master_sheet_updates["Deadline"] = context_deadline
            result.fields_updated.append("deadline")

        master_sheet_row = state_data.get("master_sheet_row")
        if (
            master_sheet_row
            and master_sheet_updates
            and self._master_sheet_config.get("enabled")
        ):
            try:
                self._update_master_sheet_row(
                    row_number=master_sheet_row, updates=master_sheet_updates
                )
                result.master_sheet_updated = True
            except Exception as e:
                result.errors.append(f"Failed to update Master Sheet: {e}")

        result.success = len(result.errors) == 0
        result.message = f"Synced {len(result.fields_updated)} fields from context file"

        return result

    def sync_from_master_sheet(
        self, feature_name: str, product_id: str, feature_path: Optional[Path] = None
    ) -> SyncResult:
        """Sync from Master Sheet to feature-state.yaml and context file."""
        result = SyncResult(
            success=False, direction=SyncDirection.MASTER_SHEET_TO_OTHERS
        )

        if not self._master_sheet_config.get("enabled"):
            result.errors.append("Master Sheet integration not enabled")
            return result

        try:
            reader = self._get_master_sheet_reader()
            topic = reader.find_feature_by_name(feature_name, product_id)

            if not topic:
                result.errors.append(
                    f"Feature '{feature_name}' not found in Master Sheet"
                )
                return result

            if feature_path is None:
                feature_path = self._find_feature_path(feature_name, product_id)
                if feature_path is None:
                    result.errors.append(
                        f"Could not find feature folder for '{feature_name}'"
                    )
                    return result

            state_data = self._load_feature_state(feature_path)

            if state_data:
                if not state_data.get("master_sheet_row"):
                    state_data["master_sheet_row"] = topic.row_number
                    result.fields_updated.append("master_sheet_row")

                if result.fields_updated:
                    if self._save_feature_state(feature_path, state_data):
                        result.feature_state_updated = True

            context_file_name = state_data.get("context_file") if state_data else None
            if not context_file_name:
                slug = feature_name.lower().replace(" ", "-")
                context_file_name = f"{slug}-context.md"

            context_path = feature_path / context_file_name
            content = self._load_context_file(context_path)

            if content:
                if topic.status:
                    content = self._update_context_field(
                        content, "status", topic.status
                    )
                    result.fields_updated.append("status")

                if topic.priority:
                    content = self._update_context_field(
                        content, "priority", topic.priority
                    )
                    result.fields_updated.append("priority")

                if topic.owner:
                    content = self._update_context_field(content, "owner", topic.owner)
                    result.fields_updated.append("owner")

                if topic.deadline:
                    deadline_str = topic.deadline.strftime("%Y-%m-%d")
                    content = self._update_context_field(
                        content, "deadline", deadline_str
                    )
                    result.fields_updated.append("deadline")

                today = datetime.now().strftime("%Y-%m-%d")
                content = self._update_context_field(content, "last_updated", today)

                if self._save_context_file(context_path, content):
                    result.context_file_updated = True

            result.success = len(result.errors) == 0
            result.message = (
                f"Synced {len(result.fields_updated)} fields from Master Sheet"
            )

        except Exception as e:
            result.errors.append(f"Failed to sync from Master Sheet: {e}")

        return result

    def _find_feature_path(self, feature_name: str, product_id: str) -> Optional[Path]:
        """Find the feature folder path."""
        if self._user_path is None:
            return None

        products_config = self._raw_config.get("products", {})
        items = products_config.get("items", [])

        org_id = None
        for product in items:
            if product.get("id") == product_id:
                org_id = product.get("organization")
                break

        if not org_id:
            # Fall back to config default_organization
            org_id = self._raw_config.get("default_organization", "default")

        slug = feature_name.lower().replace(" ", "-")

        possible_paths = [
            self._user_path / "products" / org_id / product_id / slug,
            self._user_path / "products" / org_id / slug,
        ]

        for path in possible_paths:
            if path.exists() and path.is_dir():
                return path

        return None

    def _update_master_sheet_row(
        self, row_number: int, updates: Dict[str, str]
    ) -> bool:
        """Update a row in the Master Sheet using connector_bridge."""
        if not self._master_sheet_config.get("enabled"):
            return False

        bridge = self._get_connector_bridge()
        if bridge is None:
            logger.error("connector_bridge not available for Google Sheets update")
            return False

        try:
            spreadsheet_id = self._master_sheet_config.get("spreadsheet_id")
            tab_name = self._master_sheet_config.get("tabs", {}).get("topics", "topics")

            # Use connector_bridge to get authenticated Sheets service
            service = bridge.get_sheets_service()
            if service is None:
                logger.error("Failed to get Sheets service from connector_bridge")
                return False

            # Read header row to get column indices
            header_result = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=f"{tab_name}!A1:Z1")
                .execute()
            )

            headers = header_result.get("values", [[]])[0]
            col_map = {col.strip(): i for i, col in enumerate(headers)}

            for col_name, value in updates.items():
                col_idx = col_map.get(col_name)
                if col_idx is None:
                    for h, i in col_map.items():
                        if h.lower() == col_name.lower():
                            col_idx = i
                            break

                if col_idx is not None:
                    col_letter = chr(ord("A") + col_idx)
                    cell_range = f"{tab_name}!{col_letter}{row_number}"

                    service.spreadsheets().values().update(
                        spreadsheetId=spreadsheet_id,
                        range=cell_range,
                        valueInputOption="USER_ENTERED",
                        body={"values": [[value]]},
                    ).execute()

            return True

        except Exception as e:
            logger.error(f"Failed to update Master Sheet: {e}")
            return False

    def sync_all(self, feature_path: Path) -> SyncResult:
        """Perform full bidirectional sync for a feature."""
        return self.sync_from_state(feature_path)

    def add_action_to_log(
        self,
        feature_path: Path,
        action: str,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        deadline: Optional[str] = None,
    ) -> SyncResult:
        """Add a new action to the context file's action log."""
        result = SyncResult(success=False)

        state_data = self._load_feature_state(feature_path)
        if not state_data:
            result.errors.append(f"Feature state not found at {feature_path}")
            return result

        if status is None:
            status = self._derive_status_from_tracks(state_data)

        if priority is None:
            priority = "P2"

        if deadline is None:
            deadline = "N/A"

        context_file_name = state_data.get("context_file")
        if not context_file_name:
            context_file_name = f"{state_data.get('slug', 'feature')}-context.md"

        context_path = feature_path / context_file_name
        content = self._load_context_file(context_path)

        if content is None:
            result.errors.append(f"Context file not found at {context_path}")
            return result

        content = self._add_action_log_entry(
            content, action, status, priority, deadline
        )

        if self._save_context_file(context_path, content):
            result.context_file_updated = True
            result.fields_updated.append("action_log")
            result.success = True
            result.message = f"Added action '{action}' to log"
        else:
            result.errors.append("Failed to save context file")

        return result

    def record_phase_completion(
        self, feature_path: Path, phase_name: str
    ) -> SyncResult:
        """Record a phase completion in the context file changelog."""
        result = SyncResult(success=False)

        state_data = self._load_feature_state(feature_path)
        if not state_data:
            result.errors.append(f"Feature state not found at {feature_path}")
            return result

        context_file_name = state_data.get("context_file")
        if not context_file_name:
            context_file_name = f"{state_data.get('slug', 'feature')}-context.md"

        context_path = feature_path / context_file_name
        content = self._load_context_file(context_path)

        if content is None:
            result.errors.append(f"Context file not found at {context_path}")
            return result

        content = self._update_changelog(content, phase_name)

        if self._save_context_file(context_path, content):
            result.context_file_updated = True
            result.fields_updated.append("changelog")
            result.success = True
            result.message = f"Recorded phase '{phase_name}' in changelog"
        else:
            result.errors.append("Failed to save context file")

        return result


# Convenience functions


def sync_feature_state_to_context(feature_path: Path) -> SyncResult:
    """Quick sync from feature state to context file."""
    sync = BidirectionalSync()
    return sync.sync_from_state(feature_path)


def sync_context_to_master_sheet(feature_path: Path) -> SyncResult:
    """Quick sync from context file to Master Sheet."""
    sync = BidirectionalSync()
    return sync.sync_from_context(feature_path)


def sync_master_sheet_to_context(
    feature_name: str, product_id: str, feature_path: Optional[Path] = None
) -> SyncResult:
    """Quick sync from Master Sheet to context file."""
    sync = BidirectionalSync()
    return sync.sync_from_master_sheet(feature_name, product_id, feature_path)
