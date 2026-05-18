#!/usr/bin/env python3
"""PostToolUseFailure hook on Bash -- detects auth failures and suggests fixes.

Fires when API calls fail. Checks for 401/403 patterns and provides specific
remediation for Google and Slack integrations.

Hook registration:
  event: PostToolUseFailure
  matcher: tool_name == "Bash"

Version: 5.0.0
"""

import json
import logging
import sys

logger = logging.getLogger(__name__)

GOOGLE_CONTEXT = """AUTH FAILURE DETECTED -- likely Google token expired.
Fix: Run google_scope_validator.py --fix or delete token.json and re-authenticate.
Ensure you're using the project venv python for all Google API calls."""

SLACK_CONTEXT = """AUTH FAILURE DETECTED -- likely Slack token issue.
Fix: Go to api.slack.com app console and regenerate the bot token.
Do NOT use OAuth popup -- Enterprise Grid blocks that flow.
Update SLACK_BOT_TOKEN in user/.env after refresh."""

GENERIC_CONTEXT = """AUTH FAILURE DETECTED -- check for 401/403 in the error output.
Identify which service failed and check credentials/tokens."""

AUTH_INDICATORS = [
    "http 401", "status 401", "401 unauthorized",
    "http 403", "status 403", "403 forbidden",
    "authentication failed", "access denied",
    "unauthorized", "forbidden", "invalid_auth",
    "token_expired", "token_revoked", "not_authed",
    "invalid credentials",
]


def detect_auth_failure(text: str) -> bool:
    """Check if text contains auth failure indicators."""
    lower_text = text.lower()
    return any(indicator in lower_text for indicator in AUTH_INDICATORS)


def determine_service(text: str) -> str:
    """Determine which service failed based on text content."""
    lower_text = text.lower()
    if any(kw in lower_text for kw in [
        "googleapis", "google", "gdocs", "gcal", "gsheets", "token.json"
    ]):
        return "google"
    elif any(kw in lower_text for kw in ["slack.com", "slack_bot", "slack"]):
        return "slack"
    return "generic"


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        logger.debug("No valid JSON on stdin, exiting.")
        return

    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "")
    error = data.get("error") or ""
    tool_response = data.get("tool_response", {})

    # Combine command and error text for pattern matching
    text = f"{command} {error} {json.dumps(tool_response)}"

    if not detect_auth_failure(text):
        return

    # Determine which service failed
    service = determine_service(text)
    context_map = {
        "google": GOOGLE_CONTEXT,
        "slack": SLACK_CONTEXT,
        "generic": GENERIC_CONTEXT,
    }
    context = context_map.get(service, GENERIC_CONTEXT)

    logger.info("Auth failure detected for service: %s", service)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUseFailure",
            "additionalContext": context,
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
