#!/usr/bin/env python3
"""PostCompact hook: captures the rich conversation summary generated during
context compaction and appends it to the active session file.

This is the primary mechanism for saving conversation context (decisions,
rationale, user instructions, reasoning), not just tool breadcrumbs.

Receives the compaction summary on stdin as JSON with a 'summary' field.
Designed to be fast and crash-safe.

Hook registration:
  event: PostCompact
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
from _paths import get_active_session_path, get_compaction_log_path

logger = logging.getLogger(__name__)


def main():
    try:
        active_session = get_active_session_path()
        compaction_log = get_compaction_log_path()

        if not active_session.exists():
            return

        # Read compaction data from stdin
        try:
            data = json.load(sys.stdin)
        except (json.JSONDecodeError, EOFError):
            return

        # PostCompact sends summary in the hook input
        summary = (
            data.get("summary", "")
            or data.get("tool_response", {}).get("summary", "")
            or data.get("result", "")
            or ""
        )

        if not summary:
            # Dump the whole payload as fallback so we never lose data
            summary = json.dumps(data, indent=2, default=str)
            if len(summary) > 5000:
                summary = summary[:5000] + "\n[truncated, full payload too large]"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        compact_type = data.get("matcher", "unknown")

        # Append to compaction history (persistent log of all compaction summaries)
        entry = f"""
---
## Compaction at {timestamp} ({compact_type})

{summary}

"""
        with open(compaction_log, "a") as f:
            f.write(entry)

        # Also inject a marker into the active session breadcrumbs
        marker = f"- `{datetime.now().strftime('%H:%M:%S')}` **COMPACTION** - rich context saved to compaction_history.md\n"
        with open(active_session, "a") as f:
            f.write(marker)

        logger.debug("Saved compaction summary (%d chars)", len(summary))

    except Exception as e:
        logger.debug("session_compact_saver error (non-fatal): %s", e)


if __name__ == "__main__":
    main()
