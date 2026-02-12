# Beads Integration Guide

> **Purpose:** Technical guide for Beads integration with PM-OS tools: Confucius, FPF, and Ralph.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      PM-OS Integration Layer                 │
├─────────────────┬─────────────────┬─────────────────────────┤
│   Confucius     │      FPF        │        Ralph            │
│   (Logging)     │   (Reasoning)   │     (Development)       │
├─────────────────┴─────────────────┴─────────────────────────┤
│                    BeadsWrapper (Python)                     │
├─────────────────────────────────────────────────────────────┤
│                      bd CLI (Go binary)                      │
├─────────────────────────────────────────────────────────────┤
│                    .beads/ (JSONL + SQLite)                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Confucius Integration

### Automatic Event Logging

All Beads actions are automatically logged to Confucius:

| Beads Action | Confucius Event | Details |
|--------------|-----------------|---------|
| `create()` | `capture_action()` | Logs issue creation with type and title |
| `close()` | `capture_decision()` | Logs closure with rationale |
| `update()` | `capture_observation()` | Logs field changes |
| `add_dependency()` | `capture_observation()` | Logs dependency creation |

### Hook Implementation

The `BeadsConfuciusHook` class provides programmatic access:

```python
from beads.beads_confucius_hook import BeadsConfuciusHook

hook = BeadsConfuciusHook()

# Manual event logging
hook.on_issue_created("bd-a1b2", "task", "Add login form")
hook.on_issue_closed("bd-a1b2", "completed", "All tests passing")
hook.on_issue_updated("bd-a1b2", {"priority": 0})

# Get session summary
summary = hook.get_beads_session_summary()
```

### Session Summary

Retrieve Beads-related Confucius notes:

```python
summary = hook.get_beads_session_summary()
# Returns:
# {
#   "session_id": "2026-01-19-abc123",
#   "beads_actions": 5,
#   "beads_observations": 3,
#   "beads_decisions": 2,
#   "recent_actions": [...],
#   "recent_decisions": [...]
# }
```

---

## FPF Integration

### Epic → FPF Trigger

When an epic is created, an FPF trigger file is generated:

```
.beads/.fpf_trigger.json
{
  "trigger": "beads_epic_created",
  "issue_id": "bd-a3f8",
  "title": "User Authentication System",
  "suggested_question": "What is the best architectural approach for: User Authentication System?",
  "timestamp": "2026-01-19T10:30:00Z",
  "status": "pending",
  "fpf_phase": "q0-init"
}
```

### FPF Hook Usage

```python
from beads.beads_fpf_hook import BeadsFPFHook

hook = BeadsFPFHook()

# Trigger FPF for an epic
hook.trigger_fpf_for_epic("bd-a3f8", "User Authentication")

# Check for pending trigger
trigger = hook.check_pending_trigger()
if trigger:
    print(f"Run /q0-init for: {trigger['title']}")

# Mark as processed
hook.mark_trigger_processed(fpf_cycle_id="fpf-2026-01-19-001")

# Link DRR to issue
hook.link_drr_to_issue("bd-a3f8", "DRR-auth-approach", "/path/to/drr.md")
```

### FPF Workflow

```
1. /bd-create "Feature X" --type epic
       │
       ▼
2. FPF trigger created (.fpf_trigger.json)
       │
       ▼
3. Prompt: "Run /q0-init for this epic?"
       │
       ▼
4. /q0-init → Q1 → Q2 → Q3 → Q4 → Q5
       │
       ▼
5. DRR created, linked to epic
       │
       ▼
6. Implementation begins with documented rationale
```

### Question Generation

The hook generates FPF questions based on epic titles:

| Title Pattern | Generated Question |
|---------------|-------------------|
| "Implement X" | "What is the best architectural approach for: X?" |
| "Fix X" | "What is the root cause and optimal solution for: X?" |
| "Improve X" | "What improvements would have the highest impact for: X?" |
| "Migrate X" | "What migration strategy minimizes risk for: X?" |
| Other | "What approach should we take for: X?" |

---

## Ralph Integration

### Bridge Architecture

The `BeadsRalphBridge` class synchronizes issues with features:

```python
from beads.beads_ralph_integration import BeadsRalphBridge

bridge = BeadsRalphBridge()

# Create Ralph feature from epic
result = bridge.create_feature_from_epic("bd-a3f8")
# Creates feature, links epic, returns feature path

# Sync ACs to Beads tasks
result = bridge.sync_ac_to_tasks("user-auth", "bd-a3f8")
# Creates tasks for each unchecked AC in PLAN.md

# On iteration complete
result = bridge.on_ralph_iteration_complete("user-auth", ac_index=1)
# Closes corresponding Beads task

# On feature complete
result = bridge.on_feature_complete("user-auth")
# Closes epic, suggests /q5-decide
```

### Workflow Integration

```
Epic (bd-a3f8)
    │
    ▼
/ralph-init user-auth
    │
    ▼
PLAN.md with ACs
    │
    ▼
sync_ac_to_tasks() → Creates bd-a3f8.1, bd-a3f8.2, bd-a3f8.3
    │
    ▼
Ralph Loop Iteration 1
    │
    ▼
on_ralph_iteration_complete(1) → Closes bd-a3f8.1
    │
    ▼
(repeat for each AC)
    │
    ▼
on_feature_complete() → Closes bd-a3f8, suggests DRR
```

### Link Storage

Links are stored in `.beads/.ralph_links/`:

```
.beads/.ralph_links/
├── user-auth.json         # Feature → Epic link + AC mappings
└── epic-bd-a3f8.json      # Epic → Feature reverse link
```

**Link file format:**

```json
{
  "epic_id": "bd-a3f8",
  "feature_name": "user-auth",
  "feature_path": "data/ralph/user-auth",
  "created_at": "2026-01-19T10:30:00Z",
  "ac_mappings": {
    "1": "bd-a3f8.1",
    "2": "bd-a3f8.2",
    "3": "bd-a3f8.3"
  }
}
```

### Sync Status

Check synchronization status:

```python
status = bridge.get_sync_status("user-auth")
# Returns:
# {
#   "feature_name": "user-auth",
#   "epic_id": "bd-a3f8",
#   "total_tasks": 3,
#   "completed_tasks": 1,
#   "ralph_progress": {
#     "completed": 1,
#     "total": 3,
#     "percentage": 33
#   }
# }
```

---

## API Reference

### BeadsWrapper

**Location:** `/developer/tools/beads/beads_wrapper.py`

```python
class BeadsWrapper:
    def __init__(self, project_root=None, confucius_enabled=True)
    def create(self, title, issue_type="task", priority=1, parent=None, description="") -> Dict
    def close(self, issue_id, rationale="", resolution="completed") -> Dict
    def ready(self) -> List[Dict]
    def list_issues(self, status=None, parent=None) -> List[Dict]
    def show(self, issue_id) -> Dict
    def update(self, issue_id, **kwargs) -> Dict
    def add_dependency(self, child_id, parent_id) -> Dict
    def prime(self, issue_id=None) -> str
    def is_initialized(self) -> bool
    def init(self, mode="standard") -> Dict
```

### BeadsConfuciusHook

**Location:** `/common/tools/beads/beads_confucius_hook.py`

```python
class BeadsConfuciusHook:
    def __init__(self, enabled=True)
    def on_issue_created(self, issue_id, issue_type, title, priority=1, parent=None) -> Dict
    def on_issue_closed(self, issue_id, resolution, rationale, title=None) -> Dict
    def on_issue_updated(self, issue_id, changes, title=None) -> Dict
    def on_dependency_added(self, child_id, parent_id) -> Dict
    def on_blocker_identified(self, issue_id, blocker_description, impact="medium") -> Dict
    def get_beads_session_summary(self) -> Dict
```

### BeadsFPFHook

**Location:** `/common/tools/beads/beads_fpf_hook.py`

```python
class BeadsFPFHook:
    def __init__(self, project_root=None)
    def trigger_fpf_for_epic(self, issue_id, title, suggested_question=None) -> Dict
    def check_pending_trigger(self) -> Optional[Dict]
    def mark_trigger_processed(self, fpf_cycle_id=None) -> bool
    def clear_trigger(self) -> bool
    def link_drr_to_issue(self, issue_id, drr_id, drr_path=None) -> Dict
    def get_drrs_for_issue(self, issue_id) -> List[Dict]
    def get_fpf_status(self) -> Dict
```

### BeadsRalphBridge

**Location:** `/common/tools/beads/beads_ralph_integration.py`

```python
class BeadsRalphBridge:
    def __init__(self, project_root=None)
    def create_feature_from_epic(self, epic_id, feature_name=None) -> Dict
    def sync_ac_to_tasks(self, feature_name, epic_id) -> Dict
    def on_ralph_iteration_complete(self, feature_name, ac_index) -> Dict
    def on_feature_complete(self, feature_name) -> Dict
    def get_sync_status(self, feature_name) -> Dict
```

---

## File Locations

| Component | Developer Location | Common Location |
|-----------|-------------------|-----------------|
| BeadsWrapper | `/developer/tools/beads/beads_wrapper.py` | - |
| BeadsConfig | `/developer/tools/beads/beads_config.py` | - |
| ConfuciusHook | - | `/common/tools/beads/beads_confucius_hook.py` |
| FPFHook | - | `/common/tools/beads/beads_fpf_hook.py` |
| RalphBridge | - | `/common/tools/beads/beads_ralph_integration.py` |
| Slash Commands | `/developer/.claude/commands/bd-*.md` | `/common/.claude/commands/bd-*.md` |

---

## Custom Integration

### Adding Custom Hooks

Extend the base hooks:

```python
from beads.beads_confucius_hook import BeadsConfuciusHook

class MyCustomHook(BeadsConfuciusHook):
    def on_issue_created(self, issue_id, issue_type, title, **kwargs):
        # Custom behavior
        super().on_issue_created(issue_id, issue_type, title, **kwargs)
        # Additional logging, notifications, etc.
```

### Event Subscriptions

For advanced use, subscribe to Beads events:

```python
from beads.beads_wrapper import BeadsWrapper

wrapper = BeadsWrapper()

# Override create to add custom behavior
original_create = wrapper.create
def custom_create(*args, **kwargs):
    result = original_create(*args, **kwargs)
    # Send Slack notification, update dashboard, etc.
    return result
wrapper.create = custom_create
```

---

## Troubleshooting

### Confucius Not Logging

1. Check Confucius is enabled in config
2. Verify Confucius session is active
3. Check import: `from session.confucius_agent import ConfuciusAgent`

### FPF Trigger Not Created

1. Verify `.beads/` directory exists
2. Check write permissions
3. Ensure `--type epic` was used

### Ralph Sync Failing

1. Verify Ralph feature exists: `/ralph-status feature-name`
2. Check PLAN.md has acceptance criteria
3. Verify epic ID is valid

---

*Last Updated: 2026-01-19*
*PM-OS v3.0 - Beads Integration*
