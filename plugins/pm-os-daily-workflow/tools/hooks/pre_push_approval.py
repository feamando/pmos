#!/usr/bin/env python3
"""PreToolUse hook on Bash -- approval gate before pushing to Google Docs.

Fires when gdocs_writer is called. Reminds Claude to get explicit user approval
before pushing any content to a live document.

Hook registration:
  event: PreToolUse
  matcher: tool_name == "Bash" and "gdocs_writer" in command

Version: 5.0.0
"""

import json
import logging
import sys

logger = logging.getLogger(__name__)

CONTEXT = """STOP -- PRE-PUSH APPROVAL GATE.
Have you shown the user what you're about to push and gotten explicit "go ahead"?
If not, draft changes in conversation first. Never push to a live stakeholder doc without approval."""


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        logger.debug("No valid JSON on stdin, exiting.")
        return

    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "")

    if "gdocs_writer" not in command:
        return

    logger.info("Pre-push approval gate triggered for command: %s", command[:80])

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": CONTEXT,
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
