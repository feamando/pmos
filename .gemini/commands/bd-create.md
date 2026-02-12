# Beads Create Issue

Create a new issue in the project's Beads tracker with automatic Confucius logging.

## Instructions

### Step 1: Verify Beads Initialized

```bash
if [ ! -d ".beads" ]; then
    echo "Beads not initialized. Run: bd init"
    exit 1
fi
```

### Step 2: Create Issue

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/beads/beads_wrapper.py" create "TITLE" \
    --type TYPE \
    --priority PRIORITY \
    [--parent PARENT_ID] \
    [--description "DESCRIPTION"]
```

Replace:
- `TITLE`: Issue title (required)
- `TYPE`: epic, task, or subtask (default: task)
- `PRIORITY`: 0-3 where 0 is highest (default: 1)
- `PARENT_ID`: Parent issue ID for hierarchy (optional)
- `DESCRIPTION`: Detailed description (optional)

### Step 3: Check for FPF Trigger (Epic Only)

If `--type epic` was used:

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/beads/beads_wrapper.py" check-fpf
```

If a trigger exists, prompt the user:
"Epic created. Would you like to run `/q0-init` to establish FPF context for this epic?"

### Step 4: Report Result

Display:
- Issue ID (e.g., bd-a1b2)
- Issue type and title
- Priority level
- Parent issue (if applicable)
- Confucius action logged

## Arguments

- `title`: Issue title (required, first positional argument)
- `--type`: Issue type - epic, task, subtask (default: task)
- `--priority` or `-p`: Priority 0-3 (default: 1)
- `--parent`: Parent issue ID for hierarchical tasks
- `--description` or `-d`: Detailed issue description

## Examples

```bash
# Create a high-priority epic
/bd-create "Implement User Authentication" --type epic --priority 0

# Create a task under an epic
/bd-create "Add login form" --parent bd-a3f8 --type task

# Create a simple bug fix task
/bd-create "Fix password validation" --priority 2 -d "Passwords with special chars failing"
```

## Integration Notes

- **Confucius**: Issue creation is automatically logged as an action
- **FPF**: Epic creation triggers an FPF prompt for `/q0-init`
- **Ralph**: Epics can be linked to Ralph features
