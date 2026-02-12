# Session Save

Save current session context for persistence across compaction.

## Arguments

- No arguments: Update existing session or prompt to create
- `"Title"`: Create new session with given title
- `--log "entry"`: Add work log entry
- `--decision "decision|rationale|alternatives"`: Record a decision
- `--question "question"`: Add open question

**Examples:**
```
/session-save                           # Update current session
/session-save "PM-OS v2.0 Distribution" # Create new session
/session-save --log "Completed README"  # Add work log entry
/session-save --decision "Use ASCII diagrams|Universal compatibility|Mermaid only"
```

## Instructions

### Step 1: Check for Active Session

Run the session manager to check status:

```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --status
```

### Step 2: Create or Update Session

**If no active session exists:**

1. Ask the user for a session title (or infer from current work)
2. Identify current objectives from the conversation
3. Create the session:

```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --create "Session Title" \
  --objectives "obj1,obj2,obj3" \
  --tags "tag1,tag2"
```

**If active session exists:**

1. Gather updates from the conversation:
   - Files created/modified
   - Decisions made
   - Work completed
   - Open questions

2. Update the session:

```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --save \
  --files-created "file1.md,file2.py" \
  --files-modified "existing.md" \
  --tags "additional-tag"
```

### Step 3: Add Specific Items

**For work log entries:**
```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --log "Completed Phase 1: Created directory structure and copied 34 commands"
```

**For decisions:**
```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --decision "Include FPF system|User requested full reasoning capabilities|Minimal q0/q5 only"
```

**For open questions:**
```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --question "Should /setup auto-run /create-context?"
```

### Step 4: Confirm Save

Report to user:
- Session ID
- What was saved/updated
- Path to session file

## Auto-Save Triggers

Consider saving session context when:
- User runs `/logout`
- Significant milestone completed (commit, feature done)
- Before context compaction (if detectable)
- User explicitly requests

## Session Context Template

The session file captures:

```markdown
---
session_id: 2025-01-05-001
title: Session Title
started: ISO timestamp
last_updated: ISO timestamp
status: active
tags: [tag1, tag2]
files_created: [file1, file2]
files_modified: [file3]
decisions: [{decision, rationale, alternatives}]
---

# Session: Title

## Objectives
- [ ] Objective 1
- [x] Completed objective

## Work Log
### HH:MM
- What was done
- Key details

## Decisions Made
| Decision | Rationale | Alternatives Rejected |

## Files Touched
### Created
### Modified
### Explored

## Open Questions
- [ ] Question 1

## Context for Next Session
Key information for resumption
```

## Execute

Check session status and save/create as appropriate based on current conversation context.
