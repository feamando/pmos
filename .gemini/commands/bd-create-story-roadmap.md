# Create Story from Roadmap Item

Create a Beads story (task with context) from a roadmap inbox item.

## Arguments
$ARGUMENTS

## Usage
/bd-create-story-roadmap ri-XXXX

## Instructions

This command creates a Beads story from a parsed roadmap inbox item.

### Parse the ID

Extract the roadmap ID from arguments:
```
Arguments: $ARGUMENTS
Expected format: ri-XXXX (e.g., ri-a1b2)
```

### Create the Story

```python
import sys
sys.path.insert(0, "$PM_OS_DEVELOPER_ROOT/tools")

from roadmap.roadmap_beads_sync import RoadmapBeadsSync

sync = RoadmapBeadsSync()
result = sync.create_beads_from_roadmap("$ARGUMENTS", "story")

if result["success"]:
    print(f"Created story: {result['bd_id']}")
    print(f"  Title: {result['title']}")
    print(f"  Linked to: {result['ri_id']}")
else:
    print(f"Error: {result['error']}")
```

### What Happens

1. Fetches the roadmap item by ri_id
2. Creates a Beads story with:
   - Title from roadmap item
   - Description with acceptance criteria
   - Priority mapped from P0-P3 to 0-3
   - Reference back to roadmap item
3. Updates roadmap status to TODO
4. Links the Beads ID to roadmap item
5. Posts Slack reply: "item id ri-XXXX in TODO with bd.id bd-YYYY"

### After Creation

- View story: `/bd-show bd-XXXX`
- Add to epic: `/bd-update bd-XXXX --parent bd-EPIC`
- View roadmap: `/list-roadmap-inbox`
