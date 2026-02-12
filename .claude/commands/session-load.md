# Session Load

Load a previous session's context for back-reference or continuation.

## Arguments

- No arguments: Load most recent archived session
- `session_id`: Load specific session by ID
- `partial`: Search by partial ID match

**Examples:**
```
/session-load                    # Load most recent
/session-load 2025-01-05-001     # Load specific session
/session-load pm-os              # Search by keyword
```

## Instructions

### Step 1: Identify Session to Load

**If session ID provided:**
```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --load "SESSION_ID"
```

**If no ID provided:**

1. List recent sessions:
```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --list 5
```

2. Show options to user and ask which to load, OR
3. Load most recent automatically:
```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --load
```

### Step 2: Read Session Content

Once identified, read the full session file:

```bash
# The --load command outputs the path
# Read the file for full context
```

Read the session file using the Read tool to get complete context.

### Step 3: Extract Key Information

From the loaded session, identify and summarize:

1. **Objectives** - What was being worked on
2. **Progress** - What was completed vs pending
3. **Decisions** - Key decisions made with rationale
4. **Open Questions** - Unresolved items
5. **Context for Continuation** - What the previous session noted for resumption

### Step 4: Present Summary

Present to user:

```markdown
## Loaded Session: [ID]

**Title:** [Session title]
**Date:** [When it occurred]
**Duration:** [How long]

### Objectives
- [x] Completed objective
- [ ] Pending objective

### Key Decisions
1. **[Decision]**: [Rationale]

### Open Questions
- [ ] [Question 1]

### Context Notes
[What was noted for continuation]

### Files from Session
- Created: [list]
- Modified: [list]

---
Would you like me to continue this work or reference specific details?
```

### Step 5: Offer Actions

After loading, offer:
- Continue the work where it left off
- Answer specific questions about what was done
- Load additional sessions for comparison
- Resume with specific objectives

## Use Cases

### Back-Reference During Work
When user asks "What did we decide about X?":
1. Search sessions for relevant context
2. Load and extract the decision
3. Present with full rationale

### Resume Previous Work
When user wants to continue past work:
1. Load the session
2. Identify pending objectives
3. Pick up where left off

### Compare Approaches
When considering alternatives:
1. Load multiple relevant sessions
2. Extract decisions and rationale
3. Compare approaches taken

## Execute

Load the specified session (or most recent) and present a summary of its context.
