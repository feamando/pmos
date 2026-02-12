# Beads Close Issue

Close an issue with rationale, logging the decision to Confucius.

## Instructions

### Step 1: Verify Beads Initialized

```bash
if [ ! -d ".beads" ]; then
    echo "Beads not initialized. Run: bd init"
    exit 1
fi
```

### Step 2: Close Issue

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/beads/beads_wrapper.py" close ISSUE_ID \
    --rationale "RATIONALE" \
    --resolution RESOLUTION
```

Replace:
- `ISSUE_ID`: The issue ID to close (e.g., bd-a1b2)
- `RATIONALE`: Reason for closing (recommended)
- `RESOLUTION`: One of completed, wontfix, duplicate (default: completed)

### Step 3: Report Result

Display:
- Issue ID closed
- Resolution type
- Rationale provided
- Confucius decision logged (reference ID)

## Arguments

- `issue_id`: Issue ID to close (required, first positional argument)
- `--rationale` or `-r`: Reason for closing (recommended for audit trail)
- `--resolution`: Resolution type - completed, wontfix, duplicate (default: completed)

## Examples

```bash
# Close a completed task
/bd-close bd-a1b2 --rationale "All acceptance criteria met and tests passing"

# Close as won't fix
/bd-close bd-c3d4 --resolution wontfix --rationale "Descoped from MVP, will revisit in Q2"

# Close as duplicate
/bd-close bd-e5f6 --resolution duplicate --rationale "Duplicate of bd-a1b2"
```

## Integration Notes

- **Confucius**: Closure is logged as a decision with the rationale
- **FPF**: If this closes an epic, consider running `/q5-decide` to create a DRR
- **Ralph**: If working in a Ralph loop, closing the task may advance to next criterion
