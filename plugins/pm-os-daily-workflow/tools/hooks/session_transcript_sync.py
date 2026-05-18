#!/usr/bin/env python3
"""Incremental transcript sync: copies new bytes from the Claude Code JSONL
transcript to PM-OS Sessions/Transcripts/ on every invocation.

Called by UserPromptSubmit and PreCompact hooks for near-real-time backup.
Uses byte offset tracking to avoid re-copying the entire file each time.

Typical cost: <10ms for incremental append, ~50ms for initial copy.

Hook registration:
  event: UserPromptSubmit, PreCompact, PostToolUse, PostToolUseFailure
  matcher: (always fires, chained with other session hooks)

v5.0: All paths from config, logging instead of print(), crash-safe.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

# --- v5 path resolution ---
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import (
    get_active_dir,
    get_active_session_path,
    get_session_link_path,
    get_sync_state_path,
    get_transcripts_dir,
    find_project_dir,
)

logger = logging.getLogger(__name__)


def find_source_jsonl() -> Optional[Path]:
    """Find the source JSONL transcript file."""
    project_dir = find_project_dir()
    if not project_dir:
        return None

    session_link = get_session_link_path()

    # Try from session link (has exact Claude session ID)
    if session_link.exists():
        try:
            link_data = json.loads(session_link.read_text())
            claude_id = link_data.get("claude_session_id", "")
            if claude_id:
                p = project_dir / f"{claude_id}.jsonl"
                if p.exists():
                    return p
        except (json.JSONDecodeError, OSError):
            pass

    # Fallback: most recently modified .jsonl
    jsonl_files = sorted(
        project_dir.glob("*.jsonl"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    if jsonl_files:
        return jsonl_files[0]

    return None


def get_pmos_session_id() -> str:
    """Get the PM-OS session ID from the active session file."""
    active = get_active_session_path()
    if active.exists():
        content = active.read_text()
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].split("\n"):
                    if line.strip().startswith("session_id:"):
                        return line.split(":", 1)[1].strip().strip("'\"")
    return "current"


def main():
    try:
        active_dir = get_active_dir()
        if not active_dir.exists():
            return

        source = find_source_jsonl()
        if not source:
            return

        transcripts_dir = get_transcripts_dir()
        transcripts_dir.mkdir(parents=True, exist_ok=True)

        session_id = get_pmos_session_id()
        dest = transcripts_dir / f"{session_id}.jsonl"

        sync_state_path = get_sync_state_path()

        # Load sync state
        last_offset = 0
        if sync_state_path.exists():
            try:
                state = json.loads(sync_state_path.read_text())
                # Only use offset if same source file
                if state.get("source") == str(source):
                    last_offset = state.get("offset", 0)
            except (json.JSONDecodeError, OSError):
                pass

        # Get current source size
        try:
            source_size = source.stat().st_size
        except OSError:
            return

        if source_size <= last_offset:
            return  # Nothing new

        # Read new bytes and append
        with open(source, "rb") as f:
            f.seek(last_offset)
            new_data = f.read()

        with open(dest, "ab") as f:
            f.write(new_data)

        # Update sync state
        sync_state_path.write_text(json.dumps({
            "source": str(source),
            "offset": source_size,
            "dest": str(dest),
        }))

        logger.debug("Synced %d bytes to %s", len(new_data), dest)

    except Exception as e:
        logger.debug("session_transcript_sync error (non-fatal): %s", e)


if __name__ == "__main__":
    main()
