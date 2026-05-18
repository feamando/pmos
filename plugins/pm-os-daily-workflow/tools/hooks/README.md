# Session Autosave Hooks (v5.0)

Lightweight Python hooks that provide automatic, real-time session persistence for AI-assisted PM workflows. Each hook fires on a specific Claude Code event, pattern-matches on the tool call, and performs side-effects.

## Session Autosave Hooks

These hooks work together to provide automatic, real-time session persistence. No manual save required.

| Hook | Event | Purpose |
|------|-------|---------|
| `session_starter.py` | SessionStart | Creates PM-OS session, links Claude Code session ID for transcript tracking |
| `session_prompt_logger.py` | UserPromptSubmit | Captures every user message in real-time to prompts log |
| `session_transcript_sync.py` | UserPromptSubmit, PostToolUse, PostToolUseFailure | Incremental byte-level sync of Claude JSONL transcript to PM-OS |
| `session_breadcrumb.py` | PostToolUse, PostToolUseFailure | Logs one-line tool call summaries + tracks files created/modified/read |
| `session_compact_saver.py` | PostCompact | Captures rich conversation summaries from context compaction |
| `session_archiver.py` | Stop | Compiles ALL session data into a rich archive |
| `session_retriever.py` | Utility | Searches past session transcripts for relevant context |
| `session_summarizer.py` | Utility | Deterministic transcript summarizer (no LLM) |

### How Autosave Works

```
SessionStart               session_starter.py
                            Creates session, saves Claude session ID

Every user message         session_prompt_logger.py
                            Logs exact user input

Every tool call            session_breadcrumb.py
                            One-line summary + file tracker

Multiple events            session_transcript_sync.py
                            Incremental copy of full JSONL (byte offset tracking)

PreCompact                 session_transcript_sync.py
                            Checkpoints transcript before context is compacted

Context compaction         session_compact_saver.py
                            Saves rich summaries (decisions, reasoning, context)
```

**Result:** When a session ends or the laptop lid closes, everything is already saved:
- Every user message (prompts.md)
- Every tool call (current.md breadcrumbs)
- Full verbatim transcript (Transcripts/*.jsonl)
- Rich conversation summaries (compaction_history.md)
- Files touched (file_tracker.json)

## Registration

These hooks are registered in the plugin manifest (`plugin.json`) under the `"hooks"` key. Claude Code reads the manifest and wires the hooks automatically.

For manual override, add to `.claude/settings.local.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "python3 <plugin-path>/tools/hooks/session_starter.py",
        "timeout": 5000,
        "statusMessage": "Starting session..."
      }
    ],
    "UserPromptSubmit": [
      {
        "type": "command",
        "command": "python3 <plugin-path>/tools/hooks/session_prompt_logger.py; python3 <plugin-path>/tools/hooks/session_transcript_sync.py",
        "timeout": 5000
      }
    ],
    "PostToolUse": [
      {
        "type": "command",
        "command": "python3 <plugin-path>/tools/hooks/session_breadcrumb.py; python3 <plugin-path>/tools/hooks/session_transcript_sync.py",
        "timeout": 5000
      }
    ],
    "PostToolUseFailure": [
      {
        "type": "command",
        "command": "python3 <plugin-path>/tools/hooks/session_breadcrumb.py; python3 <plugin-path>/tools/hooks/session_transcript_sync.py",
        "timeout": 5000
      }
    ],
    "PreCompact": [
      {
        "type": "command",
        "command": "python3 <plugin-path>/tools/hooks/session_transcript_sync.py",
        "timeout": 10000,
        "statusMessage": "Checkpointing session..."
      }
    ],
    "PostCompact": [
      {
        "type": "command",
        "command": "python3 <plugin-path>/tools/hooks/session_compact_saver.py",
        "timeout": 15000,
        "statusMessage": "Saving conversation context..."
      }
    ],
    "Stop": [
      {
        "type": "command",
        "command": "python3 <plugin-path>/tools/hooks/session_archiver.py",
        "timeout": 15000,
        "statusMessage": "Archiving session..."
      }
    ]
  }
}
```

## How They Work

Each hook:
1. Reads JSON from stdin (event data from Claude Code)
2. Pattern-matches on tool name, command content, or file type
3. Either outputs JSON with `additionalContext` to inject, or performs a side-effect (file write)

No external dependencies. No network calls. Fast (<100ms per hook).

## v5.0 Conventions

- All paths resolved from config via `path_resolver.get_paths()` (no hardcoded paths)
- Uses `logging` module (no `print()` for debug output)
- Relative imports with fallbacks
- PyYAML optional (has built-in fallback parser)
- Crash-safe: all hooks silently exit on error rather than blocking Claude Code
