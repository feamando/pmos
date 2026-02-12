# Beads Prime Context

Inject Beads issue context into the conversation for focused work.

## Instructions

### Step 1: Verify Beads Initialized

```bash
if [ ! -d ".beads" ]; then
    echo "Beads not initialized. Run: bd init"
    exit 1
fi
```

### Step 2: Get Context

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/beads/beads_wrapper.py" prime [ISSUE_ID]
```

If `ISSUE_ID` is provided, context is focused on that specific issue.
If omitted, general project context is loaded.

### Step 3: Process Context

The output is designed for LLM consumption. Read and internalize:

**General context includes:**
- Total open issues count
- Ready issues (no blockers)
- Recent activity
- Top priority items

**Focused context (with issue ID) includes:**
- Full issue details
- Dependencies and blockers
- Related issues
- Suggested next actions

### Step 4: Acknowledge

Report what was loaded:

```
Beads context loaded:
- 12 open issues (5 ready)
- Current focus: bd-a3f8 "User Authentication"
- Dependencies: 2 tasks blocked on this epic
- Priority items: bd-a1b2 (P0), bd-c3d4 (P0)

Ready to work. What would you like to do?
```

## Arguments

- `issue_id`: Optional issue ID to focus on (e.g., bd-a3f8)

## Examples

```bash
# Load general project context
/bd-prime

# Focus on a specific issue
/bd-prime bd-a3f8

# Focus on a specific task
/bd-prime bd-a3f8.1
```

## When to Use

- **Starting work session**: Load context to see what's ready
- **Before implementation**: Focus on specific issue for details
- **After breaks**: Re-establish context
- **During Ralph loops**: Load context for current task

## Integration Notes

- Context is optimized for LLM consumption (~1-2k tokens)
- Works with Claude Code hooks for automatic session start
- Complements `/bd-ready` for workflow planning
