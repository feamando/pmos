#!/usr/bin/env python3
"""PreToolUse hook on Bash -- gate before creating calendar events.

Fires when gcal_writer create is called. Reminds Claude to show draft and
apply meeting creation defaults.

Hook registration:
  event: PreToolUse
  matcher: tool_name == "Bash" and "gcal_writer" in command and "create" in command.split()

Version: 5.0.0
"""

import json
import logging
import sys

logger = logging.getLogger(__name__)

CONTEXT = """MEETING CREATION GATE -- show the full event details to the user before creating:
- Title, date/time, duration
- Attendees list
- Description content

Checklist (apply all):
1. Google Meet link (conferenceData)
2. guestsCanModify = true
3. Self as accepted attendee
4. HTML-formatted description

Get explicit approval before creating the event."""


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        logger.debug("No valid JSON on stdin, exiting.")
        return

    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "")

    if "gcal_writer" not in command:
        return

    if "create" not in command.split():
        return

    logger.info("Meeting creation gate triggered for command: %s", command[:80])

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": CONTEXT,
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
