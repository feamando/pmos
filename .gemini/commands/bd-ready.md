# Beads Ready Issues

List issues that have no open blockers and are ready to work on.

## Instructions

### Step 1: Verify Beads Initialized

```bash
if [ ! -d ".beads" ]; then
    echo "Beads not initialized. Run: bd init"
    exit 1
fi
```

### Step 2: Get Ready Issues

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/beads/beads_wrapper.py" ready
```

### Step 3: Format Output

Parse the JSON response and display as a table:

```
Ready Issues (no open blockers):

ID       | Priority | Title
---------|----------|----------------------------------
bd-a1b2  | P0       | Critical security fix
bd-c3d4  | P1       | Add user settings page
bd-e5f6  | P1       | Refactor auth module

Total: 3 ready
```

### Step 4: Suggest Next Steps

If issues are available:
- "Use `/bd-show bd-XXXX` for full details"
- "Use `/bd-prime bd-XXXX` to load context for focused work"

If no issues are ready:
- "All issues have blockers. Use `/bd-list` to see all issues."

## Arguments

None required.

## Example

```bash
/bd-ready
```

## Integration with Ralph

If a Ralph loop is active and a ready issue matches the current acceptance criterion, suggest:
"Ready issue bd-a1b2 matches current Ralph criterion. Consider working on this task."
