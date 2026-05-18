"""PM-OS Base -- Quality gate hooks for Claude Code.

Quality Gate Hooks:
    auth_failure_detect - PostToolUseFailure: detects 401/403 auth failures, suggests fixes
    preflight_checklist - UserPromptSubmit: injects mandatory pre-flight checklist every turn

v5.0 Conventions:
    - Uses logging module (no print() for debug)
    - Crash-safe: hooks silently exit on error rather than blocking Claude Code
    - All output via JSON to stdout (hook protocol)
"""
