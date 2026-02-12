# Beads Update Issue

Update an existing issue's properties with automatic Confucius logging.

## Instructions

### Step 1: Verify Beads Initialized

```bash
if [ ! -d ".beads" ]; then
    echo "Beads not initialized. Run: bd init"
    exit 1
fi
```

### Step 2: Update Issue

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/beads/beads_wrapper.py" update ISSUE_ID \
    [--title "NEW_TITLE"] \
    [--priority NEW_PRIORITY] \
    [--status NEW_STATUS]
```

### Step 3: Report Result

Display:
- Issue ID updated
- Fields changed (old → new)
- Confucius observation logged

## Arguments

- `issue_id`: Issue ID to update (required, first positional argument)
- `--title`: New title (optional)
- `--priority`: New priority 0-3 (optional)
- `--status`: New status (optional)

## Examples

```bash
# Increase priority
/bd-update bd-a1b2 --priority 0

# Change title
/bd-update bd-a1b2 --title "Updated: Add login form with validation"

# Multiple updates
/bd-update bd-a1b2 --title "Critical: Security fix" --priority 0
```

## Integration Notes

- **Confucius**: All updates are logged as observations for audit trail
- Changes are tracked in the issue history
