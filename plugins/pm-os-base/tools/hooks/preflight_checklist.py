#!/usr/bin/env python3
"""UserPromptSubmit hook -- fires on every user message.

Injects a mandatory pre-flight checklist before Claude processes any user message.
These are discipline-critical rules that require pausing mid-thought. The hook
forces them into context every turn.

Hook registration:
  event: UserPromptSubmit
  matcher: (always fires)

Version: 5.0.0
"""

import json
import logging
import sys

logger = logging.getLogger(__name__)

CHECKLIST = """PRE-FLIGHT -- before responding, check:
□ Any dates? Verify with `python3 -c "import datetime; print(datetime.date(Y,M,D).strftime('%A'))"`. Never compute mentally. If user stated a day, trust them -- verify silently.
□ Any facts/numbers you're about to state? Verify first or say "I haven't verified this." Never state hypotheses as facts.
□ Doc work requested? Read the FULL document FIRST. Assess structure. Present thinking BEFORE editing. Even for "just fix the phrasing."
□ Re-analysis of something you've analyzed before? Pull fresh raw data. Derive from scratch. Compare to old conclusion AFTER, not before."""


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        logger.debug("No valid JSON on stdin, exiting.")
        return

    # This hook always fires -- no filtering needed

    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": CHECKLIST,
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
