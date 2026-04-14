---
description: Session lifecycle — boot, save, load, search, logout
---

# /session — Session Lifecycle Management

Parse the first argument to determine which subcommand to run:

| Subcommand | Description |
|------------|-------------|
| `boot` | Load foundational context and initialize PM-OS session |
| `logout` | End session, archive notes, sync state, push changes |
| `save` | Save current session context for persistence |
| `load` | Load a previous session for back-reference or continuation |
| `status` | Show current session status and history |
| `search` | Search across all sessions by keyword |
| `notes` | Manage Confucius note-taking sessions |

If no arguments provided, display available subcommands.

## Arguments

- `boot` — Initialize session. Options: `--quick`, `--quiet`, `--dev`
- `logout` — End session. Options: `--quiet`
- `save [title]` — Save session. Options: `--log "entry"`, `--decision "d|r|a"`, `--question "q"`
- `load [session_id]` — Load specific or most recent session
- `status` — Current status. Options: `--list [n]`
- `search <query>` — Search sessions by keyword
- `notes` — Note session status. Options: `--list`, `--export`, `--end`, `--start "topic"`

## boot

Run the boot pipeline to initialize a PM-OS session:

```bash
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_COMMON="$PM_OS_ROOT/common"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_ROOT/user/.env" 2>/dev/null
cd "$PM_OS_COMMON/tools/pipeline"
python3 pipeline_executor.py --run "$PM_OS_COMMON/pipelines/boot.yaml" \
  --fallback "source $PM_OS_ROOT/user/.env && python3 $PM_OS_COMMON/tools/boot/boot_orchestrator.py"
```

For `--quick`: add `--var quick=true`
For `--quiet`: add `--var quiet=true`

After running the pipeline, read core context files:
1. Read: `common/AGENT.md`
2. Read: `user/brain/BRAIN.md`
3. Read: `user/USER.md`
4. Read: `user/personal/context/YYYY-MM-DD-context.md` (today's date)

## logout

Run the logout pipeline, then git sync:

```bash
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_COMMON="$PM_OS_ROOT/common"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_ROOT/user/.env" 2>/dev/null
cd "$PM_OS_COMMON/tools/pipeline"
python3 pipeline_executor.py --run "$PM_OS_COMMON/pipelines/logout.yaml" \
  --fallback "echo 'Pipeline failed'"
```

For `--quiet`: add `--var quiet=true`

Then git sync:
```bash
cd "$PM_OS_ROOT" && git pull origin main && git add . && \
  git commit -m "Session end: Context update and work save ($(date +%Y-%m-%d))" && \
  git push origin main
```

## save

Check for active session, then create or update:

```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --status
```

If no active session, create:
```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --create "Title" --objectives "obj1,obj2" --tags "tag1,tag2"
```

If active, update:
```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --save --files-created "f1,f2" --files-modified "f3" --tags "tag"
```

For `--log`: `python3 ... --log "entry"`
For `--decision`: `python3 ... --decision "choice|rationale|alternatives"`
For `--question`: `python3 ... --question "question text"`

## load

```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --load "SESSION_ID"
```

If no ID provided, list recent:
```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --list 5
```

Read session file, extract objectives, progress, decisions, open questions.

## status

```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --status
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --list 5
```

## search

```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --search "QUERY"
```

## notes

Default: `python3 "$PM_OS_COMMON/tools/session/confucius_agent.py" --status`
`--list`: `python3 ... --list 5`
`--export`: `python3 ... --export`
`--end`: `python3 ... --end`
`--start "Topic"`: `python3 ... --start "Topic"`

## Execute

Parse arguments and run the appropriate session subcommand.
