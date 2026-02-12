# Beads List Issues

List all issues in the project, optionally filtered by status or parent.

## Instructions

### Step 1: Verify Beads Initialized

```bash
if [ ! -d ".beads" ]; then
    echo "Beads not initialized. Run: bd init"
    exit 1
fi
```

### Step 2: List Issues

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/beads/beads_wrapper.py" list \
    [--status STATUS] \
    [--parent PARENT_ID]
```

### Step 3: Format Output

Parse the JSON response and display as a table:

```
Issues:

ID       | Status | Priority | Title                    | Parent
---------|--------|----------|--------------------------|--------
bd-a3f8  | open   | P0       | User Authentication      | -
bd-a3f8.1| open   | P1       | Add login form           | bd-a3f8
bd-a3f8.2| closed | P1       | Add logout button        | bd-a3f8
bd-c4d5  | open   | P2       | Update documentation     | -

Total: 4 issues (3 open, 1 closed)
```

## Arguments

- `--status`: Filter by status - open, closed (optional)
- `--parent`: Filter by parent issue ID (optional)

## Examples

```bash
# List all issues
/bd-list

# List only open issues
/bd-list --status open

# List tasks under a specific epic
/bd-list --parent bd-a3f8

# List closed issues
/bd-list --status closed
```

## Tips

- Use `/bd-ready` to see only issues ready to work on (no blockers)
- Use `/bd-show bd-XXXX` to see full details of a specific issue
- Use `/bd-prime bd-XXXX` to load context for focused work
