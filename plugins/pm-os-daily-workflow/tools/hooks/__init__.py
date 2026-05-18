"""PM-OS Daily Workflow Hooks (v5.0)

Claude Code hooks for session persistence and quality gates.

Session Hooks:
    session_starter - SessionStart: creates PM-OS session, links Claude session ID
    session_prompt_logger - UserPromptSubmit: captures every user message in real-time
    session_breadcrumb - PostToolUse/PostToolUseFailure: one-line tool call summaries
    session_transcript_sync - Multiple events: incremental byte-level JSONL sync
    session_compact_saver - PostCompact: captures rich conversation summaries
    session_archiver - Stop: compiles all session data into rich archive
    session_retriever - Utility: searches past session transcripts
    session_summarizer - Utility: deterministic transcript summarizer

Quality Gate Hooks:
    meeting_creation_gate - PreToolUse: approval gate before creating calendar events
    pre_push_approval - PreToolUse: approval gate before pushing to Google Docs
    post_push_verify - PostToolUse: verification reminder after Google Docs push
    screenshot_extract - PostToolUse: data extraction reminder for screenshots
    slack_draft_gate - PreToolUse: approval gate before posting to Slack

Hook Registration:
    Register in .claude/settings.local.json under "hooks" key.
    See README.md for the full registration block.

v5.0 Changes:
    - All paths resolved from config (no hardcoded paths)
    - Uses logging module (no print() for debug)
    - Relative imports where possible
    - PyYAML optional (has fallback)
"""
