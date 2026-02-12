# Session Status

Show the status of the current session and recent session history.

## Arguments

- No arguments: Show current session status
- `--list [n]`: Also list n recent sessions (default: 5)

**Examples:**
```
/session-status           # Current session only
/session-status --list    # Current + recent 5
/session-status --list 10 # Current + recent 10
```

## Instructions

### Step 1: Get Current Status

```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --status
```

### Step 2: Get Recent Sessions (Optional)

```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --list 5
```

### Step 3: Present Status

**If active session exists:**

```markdown
## Current Session

| Field | Value |
|-------|-------|
| **Session ID** | 2025-01-05-001 |
| **Title** | PM-OS v2.0 Distribution |
| **Status** | Active |
| **Started** | 2025-01-05 10:30 |
| **Duration** | 45 minutes |
| **Files Created** | 15 |
| **Files Modified** | 8 |
| **Decisions** | 3 |
| **Tags** | pm-os, distribution, documentation |

### Quick Actions
- `/session-save` - Save current progress
- `/session-save --log "entry"` - Add work log
- `/session-save --decision "..."` - Record decision
- `/logout` - Archive session and end
```

**If no active session:**

```markdown
## Session Status

No active session.

### Start a Session
```
/session-save "Session Title"
```

### Recent Sessions
| ID | Title | Date | Duration |
|----|-------|------|----------|
| 2025-01-04-002 | Feature X | 2025-01-04 | 60m |
| 2025-01-04-001 | Bug Fix Y | 2025-01-04 | 25m |

Use `/session-load [ID]` to view a past session.
```

### Step 4: Recommendations

Based on status, suggest:
- If no session: Create one to track work
- If long session (>2hr): Consider saving/archiving
- If many unsaved changes: Prompt to save

## Execute

Display current session status with relevant metrics and suggested actions.
