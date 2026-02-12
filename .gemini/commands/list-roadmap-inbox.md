# List Roadmap Inbox

Display roadmap inbox items in CLI or post to Slack.

## Arguments
$ARGUMENTS

## Usage
/list-roadmap-inbox
/list-roadmap-inbox --slack
/list-roadmap-inbox --status NEW

## Instructions

This command lists parsed roadmap inbox items.

### Parse Arguments

- `--slack` - Post list to configured Slack channel
- `--status STATUS` - Filter by status (NEW, TODO, INPROGRESS, DONE)
- `--json` - Output as JSON

### Display Inbox

```python
import sys
sys.path.insert(0, "$PM_OS_DEVELOPER_ROOT/tools")

from roadmap import RoadmapInboxManager, RoadmapSlackIntegration

manager = RoadmapInboxManager()
items = manager.get_inbox_items()  # Add status= for filtering

# Display in CLI
print(f"Roadmap Inbox ({len(items)} items)")
print("-" * 50)

for item in items:
    beads = f" -> {item.beads_id}" if item.beads_id else ""
    print(f"  {item.ri_id} [{item.status}] {item.title}{beads}")
    print(f"    Priority: {item.priority} | Category: {item.category}")
```

### Post to Slack (if --slack)

```python
slack = RoadmapSlackIntegration()
slack.post_inbox_list([item.to_dict() for item in items])
print("Posted to Slack channel")
```

### Output Format

```
Roadmap Inbox (5 items)
--------------------------------------------------
  ri-a1b2 [NEW] Add OAuth2 login flow
    Priority: P1 | Category: feature

  ri-c3d4 [TODO] Fix validation error on mobile -> bd-e5f6
    Priority: P2 | Category: bug

  ri-g7h8 [INPROGRESS] Improve dashboard performance -> bd-i9j0
    Priority: P2 | Category: feature

  ri-k1l2 [DONE] Add dark mode support -> bd-m3n4
    Priority: P3 | Category: feature
```

### Statistics Summary

At the end, show:
```
Summary:
  NEW: X | TODO: X | INPROGRESS: X | DONE: X
```
