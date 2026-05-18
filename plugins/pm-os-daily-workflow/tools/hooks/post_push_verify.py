#!/usr/bin/env python3
"""PostToolUse hook on Bash -- verification reminder after pushing to Google Docs.

Fires after gdocs_writer batchUpdate calls. Reminds Claude to re-read and verify
that changes landed correctly.

Hook registration:
  event: PostToolUse
  matcher: tool_name == "Bash" and "gdocs_writer" in command and "batchUpdate" in command

Version: 5.0.0
"""

import json
import logging
import sys

logger = logging.getLogger(__name__)

CONTEXT_CONTENT = """POST-PUSH VERIFICATION: You just pushed content changes to Google Docs.
Re-read the section you modified. Verify: text correct, bold intact, no stray markers,
no wrong-cell replacements. Do not proceed until verified."""

CONTEXT_STYLE = """Post-push: style-only change. Quick verification -- spot-check that formatting applied correctly."""

CONTENT_KEYWORDS = [
    "insertText",
    "insertTable",
    "replaceAllText",
    "deleteContentRange",
]


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

    if "batchUpdate" not in command:
        return

    # Heuristic: content change vs style-only
    is_content = any(kw in command for kw in CONTENT_KEYWORDS)

    logger.info(
        "Post-push verify triggered (content=%s) for command: %s",
        is_content,
        command[:80],
    )

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": CONTEXT_CONTENT if is_content else CONTEXT_STYLE,
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
