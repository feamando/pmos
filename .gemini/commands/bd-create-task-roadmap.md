# Create Task from Roadmap Item

Create a Beads task from a roadmap inbox item.

## Arguments
$ARGUMENTS

## Usage
/bd-create-task-roadmap ri-XXXX

## Instructions

This command creates a Beads task from a parsed roadmap inbox item.

### Parse the ID

Extract the roadmap ID from arguments:
```
Arguments: $ARGUMENTS
Expected format: ri-XXXX (e.g., ri-a1b2)
```

### Create the Task

```python
import sys
sys.path.insert(0, "$PM_OS_DEVELOPER_ROOT/tools")

from roadmap.roadmap_beads_sync import RoadmapBeadsSync

sync = RoadmapBeadsSync()
result = sync.create_beads_from_roadmap("$ARGUMENTS", "task")

if result["success"]:
    print(f"Created task: {result['bd_id']}")
    print(f"  Title: {result['title']}")
    print(f"  Linked to: {result['ri_id']}")
else:
    print(f"Error: {result['error']}")
```

### What Happens

1. Fetches the roadmap item by ri_id
2. Creates a Beads task with:
   - Title from roadmap item
   - Description with acceptance criteria
   - Priority mapped from P0-P3 to 0-3
   - Reference back to roadmap item
3. Updates roadmap status to TODO
4. Links the Beads ID to roadmap item
5. Posts Slack reply: "item id ri-XXXX in TODO with bd.id bd-YYYY"

### After Creation

- View task: `/bd-show bd-XXXX`
- Close when done: `/bd-close bd-XXXX --rationale "..."`
- View roadmap: `/list-roadmap-inbox`
