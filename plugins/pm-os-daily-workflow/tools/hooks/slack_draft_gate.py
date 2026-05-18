#!/usr/bin/env python3
"""PreToolUse hook on Bash -- gate before posting to Slack.

Fires when Slack API post/chat calls are detected. Reminds Claude to show
the draft message and get approval before sending.

Hook registration:
  event: PreToolUse
  matcher: tool_name == "Bash" and slack posting detected in command

Version: 5.0.0
"""

import json
import logging
import sys

logger = logging.getLogger(__name__)

CONTEXT = """SLACK DRAFT GATE -- you're about to post to Slack.
Show the full message draft to the user and get explicit approval before sending.
Include: channel/thread, message text, any attachments or formatting."""

SLACK_POST_INDICATORS = [
    "chat.postmessage", "chat.update", "chat_postmessage",
    "slack_bot", "slackbot", "slack_context_poster",
]


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        logger.debug("No valid JSON on stdin, exiting.")
        return

    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "")
    lower_command = command.lower()

    # Must be Slack-related AND a posting operation
    is_slack = "slack" in lower_command
    is_post = any(indicator in lower_command for indicator in SLACK_POST_INDICATORS)

    # Also catch direct curl to Slack chat API
    is_slack_curl = "slack.com/api/chat" in lower_command

    if not (is_slack_curl or (is_slack and is_post)):
        return

    logger.info("Slack draft gate triggered for command: %s", command[:80])

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": CONTEXT,
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
