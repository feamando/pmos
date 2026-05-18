#!/usr/bin/env python3
"""UserPromptSubmit hook: captures every user message in real-time.
Appends the user's exact prompt to the active session file.

Hook registration:
  event: UserPromptSubmit
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
from _paths import get_active_session_path, get_prompts_log_path

logger = logging.getLogger(__name__)


def main():
    try:
        active_session = get_active_session_path()
        prompts_log = get_prompts_log_path()

        if not active_session.exists():
            return

        # Read hook input from stdin
        try:
            data = json.load(sys.stdin)
        except (json.JSONDecodeError, EOFError):
            return

        # Extract user prompt (try multiple possible field paths)
        prompt = (
            data.get("prompt", "")
            or data.get("content", "")
            or data.get("message", "")
            or data.get("tool_input", {}).get("prompt", "")
            or ""
        )

        if not prompt:
            # Save raw payload so we never miss data
            prompt = f"[unrecognized payload format, {len(json.dumps(data, default=str))} bytes]"

        timestamp = datetime.now().strftime("%H:%M:%S")

        # Append to prompts log (dedicated file for user messages)
        with open(prompts_log, "a") as f:
            f.write(f"\n### [{timestamp}] User\n{prompt}\n")

        # Also mark in the main session breadcrumbs
        short = prompt[:80].replace("\n", " ")
        with open(active_session, "a") as f:
            f.write(f"- `{timestamp}` **USER**: {short}\n")

    except Exception as e:
        logger.debug("session_prompt_logger error (non-fatal): %s", e)


if __name__ == "__main__":
    main()
