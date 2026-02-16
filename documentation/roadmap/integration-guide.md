# Roadmap Inbox Integration Guide

> **Purpose:** Technical guide for integrating with the Roadmap Inbox system.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Slack Mentions                           │
│              (@pmos-slack-bot)                          │
├─────────────────────────────────────────────────────────────┤
│               slack_mention_handler.py                      │
│         (classifies pmos_feature/pmos_bug)                 │
├─────────────────────────────────────────────────────────────┤
│              RoadmapInboxManager                            │
│        (capture → temp inbox → tmp.id)                     │
├─────────────────────────────────────────────────────────────┤
│                RoadmapParser                                │
│        (LLM enrichment → project inbox → ri.id)            │
├─────────────────────────────────────────────────────────────┤
│               RoadmapBeadsSync                              │
│        (create Beads → link → status sync)                 │
├─────────────────────────────────────────────────────────────┤
│                 BeadsWrapper                                │
│            (bd CLI integration)                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Reference

### RoadmapInboxManager

**Location:** `/developer/tools/roadmap/roadmap_inbox_manager.py`

```python
from roadmap import RoadmapInboxManager

manager = RoadmapInboxManager(project="pm-os")

# Capture from Slack mention
tmp_id = manager.capture_from_slack(mention_data)

# Get temp items
temp_items = manager.get_temp_items(status="NEW")

# Update temp status
manager.update_temp_status("tmp-a1b2", "PARSED")

# Add parsed item
manager.add_parsed_item(parsed_item)

# Get inbox items
inbox_items = manager.get_inbox_items(status="TODO")

# Update inbox status
manager.update_inbox_status("ri-c3d4", "DONE", beads_id="bd-e5f6")

# Get statistics
stats = manager.get_statistics()
```

### RoadmapParser

**Location:** `/developer/tools/roadmap/roadmap_parser.py`

```python
from roadmap import RoadmapParser

parser = RoadmapParser(model="gemini")  # or "claude"

# Parse single item
parsed_data = parser.parse_item(
    raw_text="Add OAuth2 login flow",
    context={"requester": "Jane", "classification": "pmos_feature"}
)

# Parse batch of temp items
parsed_items = parser.parse_batch(temp_items, check_duplicates=True)

# Detect duplicates
duplicates = parser.detect_duplicates(items)
```

### RoadmapSlackIntegration

**Location:** `/developer/tools/roadmap/roadmap_slack_integration.py`

```python
from roadmap import RoadmapSlackIntegration

slack = RoadmapSlackIntegration()

# Post capture reply
slack.post_capture_reply(channel, thread_ts, "tmp-a1b2")

# Post parsed reply
slack.post_parsed_reply(channel, thread_ts, "ri-c3d4", "OAuth Login")

# Post beads reply
slack.post_beads_reply(channel, thread_ts, "ri-c3d4", "bd-e5f6")

# Post done reply
slack.post_done_reply(channel, thread_ts, "ri-c3d4")

# Post inbox list to channel
slack.post_inbox_list(items, channel="CXXXXXXXXXX")
```

### RoadmapBeadsSync

**Location:** `/developer/tools/roadmap/roadmap_beads_sync.py`

```python
from roadmap import RoadmapBeadsSync

sync = RoadmapBeadsSync()

# Create Beads from roadmap
result = sync.create_beads_from_roadmap("ri-c3d4", "task")
# Returns: {"success": True, "bd_id": "bd-e5f6", ...}

# Sync status from Beads to roadmap
sync.sync_status_to_roadmap("bd-e5f6", "closed")

# Handle Beads closure (called from hook)
sync.on_beads_closed("bd-e5f6")

# Close Beads when deleting roadmap item
sync.close_beads_for_roadmap("ri-c3d4")
```

### BeadsRoadmapHook

**Location:** `/common/tools/beads/beads_roadmap_hook.py`

```python
from beads.beads_roadmap_hook import get_roadmap_hook

hook = get_roadmap_hook()

# Called when Beads item closes
hook.on_beads_closed("bd-e5f6")

# Called when Beads work starts
hook.on_beads_started("bd-e5f6")

# Check if linked
is_linked = hook.is_linked("bd-e5f6")
ri_id = hook.get_linked_roadmap_id("bd-e5f6")
```

---

## Data Models

### TempInboxItem

```python
@dataclass
class TempInboxItem:
    tmp_id: str              # tmp-a1b2
    raw_text: str            # Original Slack message
    source_channel: str      # Channel ID
    source_thread_ts: str    # For thread replies
    source_user: str         # Requester name
    classification: str      # pmos_feature / pmos_bug
    status: str              # NEW / PARSED / DELETED
    created_at: str          # ISO timestamp
    thread_link: str         # Slack permalink
    mention_id: str          # Original mention ID
```

### ParsedInboxItem

```python
@dataclass
class ParsedInboxItem:
    ri_id: str               # ri-c3d4
    tmp_id: str              # Source temp ID
    title: str               # LLM-generated title
    description: str         # Full description
    acceptance_criteria: List[str]
    priority: str            # P0 / P1 / P2 / P3
    category: str            # feature / bug
    status: str              # NEW / TODO / INPROGRESS / DONE
    source_thread_link: str  # For Slack replies
    created_at: str
    parsed_at: str
    updated_at: str
    beads_id: Optional[str]  # bd-e5f6 if linked
    merged_from: List[str]   # Merged item IDs
    source_channel: str
    source_thread_ts: str
```

---

## State File Format

**Location:** `/common/data/roadmap/roadmap_state.json`

```json
{
  "version": "1.0",
  "project": "pm-os",
  "last_capture": "2026-01-19T10:00:00",
  "temp_items": {
    "tmp-a1b2": {
      "tmp_id": "tmp-a1b2",
      "raw_text": "Add OAuth login",
      "status": "PARSED",
      "source_channel": "CXXXXXXXXXX",
      "source_thread_ts": "1768574795.430459",
      "created_at": "2026-01-19T09:30:00"
    }
  },
  "parsed_items": {
    "ri-c3d4": {
      "ri_id": "ri-c3d4",
      "tmp_id": "tmp-a1b2",
      "title": "Add OAuth2 Login Flow",
      "status": "TODO",
      "beads_id": "bd-e5f6"
    }
  },
  "beads_links": {
    "bd-e5f6": "ri-c3d4"
  },
  "statistics": {
    "total_captured": 10,
    "total_parsed": 8,
    "total_done": 3
  }
}
```

---

## Integration with Slack Mention Handler

The roadmap capture integrates with the existing `slack_mention_handler.py`:

**After classification (add to handler):**

```python
# In process_mention() after classification:
if classification in ["pmos_feature", "pmos_bug"]:
    try:
        sys.path.insert(0, developer_root / "tools")
        from roadmap import RoadmapInboxManager

        manager = RoadmapInboxManager()
        tmp_id = manager.capture_from_slack({
            "id": mention_id,
            "raw_text": raw_text,
            "source_channel": channel_id,
            "source_ts": thread_ts,
            "requester_name": requester,
            "classification": classification,
            "thread_link": thread_link,
        })

        if tmp_id:
            logger.info(f"Captured to roadmap: {tmp_id}")
    except ImportError:
        pass  # Developer tools not available
```

---

## Integration with Beads

### Beads Wrapper Hook

Add to `/developer/tools/beads/beads_wrapper.py`:

```python
# In __init__:
self._roadmap_hook = None

@property
def roadmap_hook(self):
    if self._roadmap_hook is None:
        try:
            sys.path.insert(0, common_root / "tools" / "beads")
            from beads_roadmap_hook import get_roadmap_hook
            self._roadmap_hook = get_roadmap_hook()
        except ImportError:
            pass
    return self._roadmap_hook

# In close() method, after successful close:
if self.roadmap_hook:
    self.roadmap_hook.on_beads_closed(issue_id)
```

---

## Configuration

### config.yaml additions

```yaml
roadmap:
  enabled: true
  default_llm: "gemini"  # or "claude"
  slack:
    post_channel: "CXXXXXXXXXX"
    monitored_channels:
      - "CXXXXXXXXXX"
      - "CXXXXXXXXXX"
    auto_reply: true
  integrations:
    beads: true
    confucius: true
  auto_capture_on_boot: true
```

---

## LLM Parsing Prompt

The parser uses this prompt structure:

```
Parse the following feature request or bug report into:
- title: Clear, concise (max 80 chars)
- description: Full description
- acceptance_criteria: 2-5 measurable ACs
- priority: P0/P1/P2/P3
- category: feature/bug

Context:
- Requester: {requester}
- Classification: {classification}

Raw Input:
{raw_text}
```

### Fallback Parsing

When LLM is unavailable, fallback parsing:
- Title: First line/sentence (truncated to 80 chars)
- Description: Full raw text
- AC: Empty list
- Priority: P2
- Category: Based on classification

---

## CLI Commands

### Manager CLI

```bash
# Show statistics
python3 roadmap_inbox_manager.py --status

# List temp items
python3 roadmap_inbox_manager.py --temp

# List inbox items
python3 roadmap_inbox_manager.py --list

# Capture from mentions
python3 roadmap_inbox_manager.py --capture
```

### Parser CLI

```bash
# Parse NEW items
python3 roadmap_parser.py --parse

# Parse with Claude
python3 roadmap_parser.py --parse --model claude

# Dry run
python3 roadmap_parser.py --parse --dry-run
```

### Beads Sync CLI

```bash
# Create Beads from roadmap
python3 roadmap_beads_sync.py --create ri-c3d4 --type task

# Show sync status
python3 roadmap_beads_sync.py --status
```

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Item not found" | Invalid ri_id | Check ID format and existence |
| "Already linked" | Item has Beads ID | Use existing Beads item |
| "Beads not available" | bd CLI not installed | Install beads-cli |
| "Slack not available" | Token not configured | Set SLACK_BOT_TOKEN |
| "LLM error" | API key missing | Set GEMINI_API_KEY |

---

## File Locations Summary

| Component | Location |
|-----------|----------|
| Manager | `/developer/tools/roadmap/roadmap_inbox_manager.py` |
| Parser | `/developer/tools/roadmap/roadmap_parser.py` |
| Slack Integration | `/developer/tools/roadmap/roadmap_slack_integration.py` |
| Beads Sync | `/developer/tools/roadmap/roadmap_beads_sync.py` |
| Config | `/developer/tools/roadmap/roadmap_config.py` |
| Beads Hook | `/common/tools/beads/beads_roadmap_hook.py` |
| Temp Inbox | `/common/data/roadmap/tmp-roadmap-inbox.md` |
| Project Inbox | `/common/data/roadmap/pm-os-roadmap-inbox.md` |
| State | `/common/data/roadmap/roadmap_state.json` |

---

*Last Updated: 2026-01-19*
*PM-OS v3.0 - Roadmap Inbox Integration*
