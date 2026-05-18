#!/usr/bin/env python3
"""Shared path resolution for session hooks (v5.0).

Resolves Sessions/ directory paths from config rather than hardcoding.
All hooks import from here to stay DRY and consistent.

Resolution order:
1. pm_os_base.tools.core.path_resolver.get_paths() -> paths.user / "sessions"
2. Environment variable PM_OS_USER -> $PM_OS_USER/sessions
3. Fallback: walk up from __file__ to find .pm-os-root marker
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Cache resolved paths
_resolved_sessions_dir: Optional[Path] = None


def _find_root_marker(start: Path, marker: str = ".pm-os-root") -> Optional[Path]:
    """Walk up from start looking for a marker file."""
    current = start
    for _ in range(10):
        if (current / marker).exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def get_sessions_dir() -> Path:
    """Resolve the Sessions/ directory from config.

    Returns:
        Path to the Sessions/ directory (created if needed).
    """
    global _resolved_sessions_dir
    if _resolved_sessions_dir is not None:
        return _resolved_sessions_dir

    sessions_dir = None

    # Strategy 1: path_resolver
    try:
        from pm_os_base.tools.core.path_resolver import get_paths
        paths = get_paths()
        sessions_dir = paths.user / "sessions"
    except ImportError:
        try:
            _plugin_root = Path(__file__).resolve().parent.parent.parent.parent
            sys.path.insert(0, str(_plugin_root / "pm-os-base" / "tools" / "core"))
            from path_resolver import get_paths
            paths = get_paths()
            sessions_dir = paths.user / "sessions"
        except (ImportError, Exception):
            pass

    # Strategy 2: environment variable
    if sessions_dir is None:
        user_dir = os.environ.get("PM_OS_USER")
        if user_dir:
            sessions_dir = Path(user_dir) / "sessions"

    # Strategy 3: marker file walk-up
    if sessions_dir is None:
        root = _find_root_marker(Path(__file__).resolve().parent)
        if root:
            sessions_dir = root / "user" / "sessions"

    # Strategy 4: fallback relative to plugin
    if sessions_dir is None:
        # Assume: plugins/pm-os-daily-workflow/tools/hooks/ -> ../../../../user/sessions
        plugin_root = Path(__file__).resolve().parent.parent.parent.parent
        sessions_dir = plugin_root / "user" / "sessions"
        logger.debug("Using fallback sessions dir: %s", sessions_dir)

    _resolved_sessions_dir = sessions_dir
    return sessions_dir


def get_active_dir() -> Path:
    """Get path to Sessions/Active/ directory."""
    return get_sessions_dir() / "Active"


def get_archive_dir() -> Path:
    """Get path to Sessions/Archive/ directory."""
    return get_sessions_dir() / "Archive"


def get_transcripts_dir() -> Path:
    """Get path to Sessions/Transcripts/ directory."""
    return get_sessions_dir() / "Transcripts"


def get_active_session_path() -> Path:
    """Get path to the active session file."""
    return get_active_dir() / "current.md"


def get_file_tracker_path() -> Path:
    """Get path to the file tracker JSON."""
    return get_active_dir() / "file_tracker.json"


def get_compaction_log_path() -> Path:
    """Get path to the compaction history log."""
    return get_active_dir() / "compaction_history.md"


def get_prompts_log_path() -> Path:
    """Get path to the prompts log."""
    return get_active_dir() / "prompts.md"


def get_session_link_path() -> Path:
    """Get path to the Claude session link JSON."""
    return get_active_dir() / "claude_session.json"


def get_sync_state_path() -> Path:
    """Get path to the transcript sync state."""
    return get_active_dir() / "transcript_sync.json"


def get_index_path() -> Path:
    """Get path to the session index file."""
    return get_sessions_dir() / "Index.md"


def get_claude_projects_base() -> Path:
    """Get the Claude Code projects base directory."""
    return Path.home() / ".claude" / "projects"


def find_project_dir() -> Optional[Path]:
    """Find the Claude Code projects directory (most recently modified)."""
    base = get_claude_projects_base()
    if not base.exists():
        return None
    project_dirs = [d for d in base.iterdir() if d.is_dir()]
    if not project_dirs:
        return None
    return max(project_dirs, key=lambda d: d.stat().st_mtime)
