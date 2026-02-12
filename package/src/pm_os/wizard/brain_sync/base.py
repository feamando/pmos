"""
PM-OS Brain Sync Base Classes

Common functionality for all sync implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
import json

from pm_os.wizard.brain_sync.schema import (
    create_entity_content,
    get_entity_path,
    sanitize_filename
)


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    message: str
    entities_created: int = 0
    entities_updated: int = 0
    entities_skipped: int = 0
    errors: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_tuple(self) -> tuple:
        """Convert to (success, message) tuple for compatibility."""
        return (self.success, self.message)


@dataclass
class SyncProgress:
    """Progress tracking for sync operations."""
    total: int = 0
    current: int = 0
    phase: str = ""
    entity_type: str = ""
    callback: Optional[Callable[[int, int, str], None]] = None

    def update(self, current: int, phase: str = ""):
        """Update progress and call callback if set."""
        self.current = current
        if phase:
            self.phase = phase
        if self.callback:
            self.callback(self.current, self.total, self.phase)

    def increment(self, phase: str = ""):
        """Increment progress by 1."""
        self.update(self.current + 1, phase)


class BaseSyncer(ABC):
    """Base class for all brain sync implementations."""

    def __init__(
        self,
        brain_path: Path,
        last_sync_file: Optional[Path] = None
    ):
        """Initialize the syncer.

        Args:
            brain_path: Path to the brain directory
            last_sync_file: Path to store last sync timestamps
        """
        self.brain_path = Path(brain_path)
        self.last_sync_file = last_sync_file or (brain_path / ".sync_state.json")
        self._sync_state: Dict[str, Any] = {}
        self._load_sync_state()

    def _load_sync_state(self):
        """Load the last sync state from disk."""
        if self.last_sync_file.exists():
            try:
                self._sync_state = json.loads(self.last_sync_file.read_text())
            except (json.JSONDecodeError, IOError):
                self._sync_state = {}

    def _save_sync_state(self):
        """Save the current sync state to disk."""
        self.last_sync_file.parent.mkdir(parents=True, exist_ok=True)
        self.last_sync_file.write_text(json.dumps(self._sync_state, indent=2))

    def get_last_sync_time(self, key: str) -> Optional[str]:
        """Get the last sync time for a specific key."""
        return self._sync_state.get(key, {}).get("last_sync")

    def set_last_sync_time(self, key: str, timestamp: Optional[str] = None):
        """Set the last sync time for a key."""
        if key not in self._sync_state:
            self._sync_state[key] = {}
        self._sync_state[key]["last_sync"] = timestamp or datetime.now().isoformat()
        self._save_sync_state()

    def get_sync_cursor(self, key: str) -> Optional[str]:
        """Get a cursor/offset for incremental sync."""
        return self._sync_state.get(key, {}).get("cursor")

    def set_sync_cursor(self, key: str, cursor: str):
        """Set a cursor/offset for incremental sync."""
        if key not in self._sync_state:
            self._sync_state[key] = {}
        self._sync_state[key]["cursor"] = cursor
        self._save_sync_state()

    def write_entity(
        self,
        entity_type: str,
        name: str,
        source: str,
        body: str = "",
        sync_id: Optional[str] = None,
        relationships: Optional[Dict[str, List[str]]] = None,
        **extra_fields
    ) -> Path:
        """Write an entity to the brain.

        Args:
            entity_type: Type of entity
            name: Entity name
            source: Source system
            body: Markdown body content
            sync_id: External ID for tracking
            relationships: Related entities
            **extra_fields: Additional frontmatter

        Returns:
            Path to the created file
        """
        # Get path for entity type
        rel_path = get_entity_path(entity_type)
        entity_dir = self.brain_path / rel_path
        entity_dir.mkdir(parents=True, exist_ok=True)

        # Create filename
        filename = sanitize_filename(name) + ".md"
        file_path = entity_dir / filename

        # Create content
        content = create_entity_content(
            entity_type=entity_type,
            name=name,
            source=source,
            body=body,
            sync_id=sync_id,
            relationships=relationships,
            **extra_fields
        )

        # Write file
        file_path.write_text(content)
        return file_path

    def entity_exists(self, entity_type: str, name: str) -> bool:
        """Check if an entity already exists."""
        rel_path = get_entity_path(entity_type)
        filename = sanitize_filename(name) + ".md"
        file_path = self.brain_path / rel_path / filename
        return file_path.exists()

    def get_entity_path_for(self, entity_type: str, name: str) -> Path:
        """Get the path for an entity."""
        rel_path = get_entity_path(entity_type)
        filename = sanitize_filename(name) + ".md"
        return self.brain_path / rel_path / filename

    @abstractmethod
    def sync(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        incremental: bool = True
    ) -> SyncResult:
        """Run the sync operation.

        Args:
            progress_callback: Called with (current, total, phase)
            incremental: If True, only sync changes since last sync

        Returns:
            SyncResult with details
        """
        pass

    @abstractmethod
    def test_connection(self) -> tuple:
        """Test the connection to the external service.

        Returns:
            Tuple of (success, message)
        """
        pass
