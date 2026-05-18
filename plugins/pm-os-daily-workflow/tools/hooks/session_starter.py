#!/usr/bin/env python3
"""SessionStart hook: creates a new PM-OS session and captures the Claude Code
session_id so we can link the verbatim JSONL transcript at archive time.

Hook registration:
  event: SessionStart
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
from _paths import get_active_dir, get_active_session_path, get_session_link_path

logger = logging.getLogger(__name__)


def main():
    try:
        active_dir = get_active_dir()
        active_session = get_active_session_path()
        session_link = get_session_link_path()

        active_dir.mkdir(parents=True, exist_ok=True)

        # Read hook input (SessionStart sends session_id)
        claude_session_id = None
        try:
            data = json.load(sys.stdin)
            claude_session_id = data.get("session_id", "")
        except (json.JSONDecodeError, EOFError):
            pass

        # Save Claude Code session ID for transcript linking at archive time
        if claude_session_id:
            link_data = {
                "claude_session_id": claude_session_id,
                "started": datetime.now().isoformat(),
            }
            session_link.write_text(json.dumps(link_data, indent=2))

        # Create PM-OS session if none active
        if not active_session.exists():
            session_id = datetime.now().strftime("%Y-%m-%d-001")
            active_session.write_text(
                f"---\nsession_id: '{session_id}'\ntitle: Auto-session\n"
                f"started: '{datetime.now().isoformat()}'\nstatus: active\n---\n"
            )
            logger.info("Created session: %s", session_id)
            return

        logger.debug("Active session exists, continuing")

    except Exception as e:
        logger.debug("session_starter error (non-fatal): %s", e)


if __name__ == "__main__":
    main()
