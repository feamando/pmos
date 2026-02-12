# Beads Show Issue

Display full details of a specific issue including history and dependencies.

## Instructions

### Step 1: Verify Beads Initialized

```bash
if [ ! -d ".beads" ]; then
    echo "Beads not initialized. Run: bd init"
    exit 1
fi
```

### Step 2: Show Issue Details

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/beads/beads_wrapper.py" show ISSUE_ID
```

### Step 3: Format Output

Parse the JSON response and display:

```
Issue: bd-a3f8

Title:       User Authentication
Type:        epic
Status:      open
Priority:    P0
Created:     2026-01-15 10:30
Updated:     2026-01-18 14:22

Description:
  Implement full user authentication flow including login,
  logout, password reset, and session management.

Dependencies:
  - Blocks: bd-c4d5 (API endpoints)
  - Blocked by: (none)

Child Issues:
  - bd-a3f8.1 [open]  Add login form
  - bd-a3f8.2 [closed] Add logout button
  - bd-a3f8.3 [open]  Password reset flow

History:
  - 2026-01-18: Priority changed from P1 to P0
  - 2026-01-16: Added child bd-a3f8.3
  - 2026-01-15: Created
```

## Arguments

- `issue_id`: Issue ID to show (required, first positional argument)

## Examples

```bash
# Show an epic
/bd-show bd-a3f8

# Show a task
/bd-show bd-a3f8.1
```

## Related Commands

- `/bd-update bd-XXXX` - Update this issue
- `/bd-close bd-XXXX` - Close this issue
- `/bd-prime bd-XXXX` - Load context for focused work
