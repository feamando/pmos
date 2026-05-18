#!/usr/bin/env python3
"""Lightweight breadcrumb logger for PostToolUse/PostToolUseFailure hooks.
Appends a one-line entry to the active session file after each tool use.
Also tracks files created/modified/read in a sidecar JSON for session enrichment.

Designed to be fast (<100ms) and crash-safe.

Hook registration:
  event: PostToolUse, PostToolUseFailure
  matcher: (always fires)

v5.0: All paths from config, logging instead of print(), crash-safe.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# --- v5 path resolution ---
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import get_active_session_path, get_file_tracker_path

logger = logging.getLogger(__name__)


def load_tracker(tracker_path: Path) -> dict:
    """Load or initialize file tracker."""
    if tracker_path.exists():
        try:
            return json.loads(tracker_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"created": [], "modified": [], "read": []}


def save_tracker(tracker_path: Path, tracker: dict):
    """Save file tracker atomically."""
    tracker_path.write_text(json.dumps(tracker, indent=2))


def track_file(tracker: dict, category: str, filepath: str):
    """Add a file to tracker if not already present."""
    if filepath and filepath not in tracker.get(category, []):
        tracker.setdefault(category, []).append(filepath)


def main():
    try:
        active_session = get_active_session_path()
        file_tracker_path = get_file_tracker_path()

        if not active_session.exists():
            return

        # Read tool info from stdin (PostToolUse hook input)
        try:
            data = json.load(sys.stdin)
        except (json.JSONDecodeError, EOFError):
            return

        tool = data.get("tool_name", "?")
        tool_input = data.get("tool_input", {})

        # Build a short summary based on tool type
        filepath = ""
        if tool == "Read":
            filepath = tool_input.get("file_path", "")
            summary = filepath[-60:]
        elif tool == "Edit":
            filepath = tool_input.get("file_path", "")
            summary = filepath[-60:]
        elif tool == "Write":
            filepath = tool_input.get("file_path", "")
            summary = filepath[-60:]
        elif tool == "Bash":
            cmd = tool_input.get("command", "")
            summary = cmd[:80].replace("\n", " ")
        elif tool in ("Glob", "Grep"):
            summary = tool_input.get("pattern", "")[:60]
        elif tool == "Agent":
            summary = tool_input.get("description", "")[:60]
        elif tool == "WebFetch":
            summary = tool_input.get("url", "")[:60]
        else:
            summary = tool[:30]

        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"- `{timestamp}` {tool}: {summary}\n"

        # Append breadcrumb
        with open(active_session, "a") as f:
            f.write(line)

        # Track file changes
        if filepath:
            tracker = load_tracker(file_tracker_path)
            if tool == "Write":
                if filepath not in tracker.get("modified", []):
                    track_file(tracker, "created", filepath)
                else:
                    track_file(tracker, "modified", filepath)
            elif tool == "Edit":
                track_file(tracker, "modified", filepath)
            elif tool == "Read":
                # Only track reads for non-session files
                sessions_dir = str(get_active_session_path().parent.parent)
                if sessions_dir not in filepath:
                    track_file(tracker, "read", filepath)
            save_tracker(file_tracker_path, tracker)

    except Exception as e:
        logger.debug("session_breadcrumb error (non-fatal): %s", e)


if __name__ == "__main__":
    main()
