# Delete Roadmap Inbox Item

Delete a roadmap inbox item and optionally close associated Beads item.

## Arguments
$ARGUMENTS

## Usage
/delete-roadmap-inbox ri-XXXX

## Instructions

This command deletes a roadmap inbox item.

### Parse the ID

Extract the roadmap ID from arguments:
```
Arguments: $ARGUMENTS
Expected format: ri-XXXX (e.g., ri-a1b2)
```

### Delete Process

```python
import sys
sys.path.insert(0, "$PM_OS_DEVELOPER_ROOT/tools")

from roadmap import RoadmapInboxManager, RoadmapBeadsSync, RoadmapSlackIntegration

manager = RoadmapInboxManager()
sync = RoadmapBeadsSync()
slack = RoadmapSlackIntegration()

ri_id = "$ARGUMENTS"

# Get item first
item = manager.get_inbox_item(ri_id)
if not item:
    print(f"Item not found: {ri_id}")
    exit(1)

# If linked to Beads and status is TODO/INPROGRESS, close Beads item
if item.beads_id and item.status in ["TODO", "INPROGRESS"]:
    print(f"Closing linked Beads item: {item.beads_id}")
    sync.close_beads_for_roadmap(ri_id)

# Delete from inbox
beads_id = manager.delete_inbox_item(ri_id)

# Post Slack notification
if item.source_channel and item.source_thread_ts:
    slack.post_deleted_reply(
        channel=item.source_channel,
        thread_ts=item.source_thread_ts,
        ri_id=ri_id
    )

print(f"Deleted: {ri_id}")
if beads_id:
    print(f"  Closed Beads: {beads_id}")
```

### What Happens

1. Finds the roadmap item
2. If linked to Beads and TODO/INPROGRESS:
   - Closes the Beads item with resolution "wontfix"
3. Removes item from roadmap inbox
4. Posts Slack reply: "item ri-XXXX has been deleted"

### Confirmation

Before deleting, confirm:
- Item title
- Current status
- Linked Beads ID (if any)

### After Deletion

The item is removed from:
- pm-os-roadmap-inbox.md
- roadmap_state.json
- beads_links (if was linked)

The original temp item remains marked as PARSED.
