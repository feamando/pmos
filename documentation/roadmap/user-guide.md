# Roadmap Inbox User Guide

> **Purpose:** Comprehensive guide to using the Roadmap Inbox system for tracking PM-OS feature requests and bugs.

---

## Overview

The Roadmap Inbox system captures feature requests and bugs from Slack, processes them through LLM enrichment, and integrates with Beads for issue tracking.

### Key Flow

```
Slack Mention → Temp Inbox (tmp-a1b2) → LLM Parse → Project Inbox (ri-c3d4) → Beads (bd-e5f6)
```

### Status Lifecycle

**Temp Inbox:** NEW → PARSED → DELETED

**Project Inbox:** NEW → TODO → INPROGRESS → DONE

---

## Quick Start

### 1. Capture Items

Items are captured automatically on `/boot`, `/update-context`, and `/logout`:

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/roadmap/roadmap_inbox_manager.py" --capture
```

### 2. Parse Items

Process captured items through LLM enrichment:

```
/parse-roadmap-inbox
```

### 3. View Inbox

List all parsed items:

```
/list-roadmap-inbox
```

### 4. Create Beads Item

Create a tracked issue from a roadmap item:

```
/bd-create-task-roadmap ri-XXXX
```

---

## Slash Commands Reference

### `/parse-roadmap-inbox`

Process NEW temp items through LLM parsing.

**What happens:**
- Extracts title, description, acceptance criteria
- Assigns priority (P0-P3)
- Detects and merges duplicates
- Posts Slack reply: "parsed, inbox item id ri-XXXX"

**Options:**
- `--model gemini` - Use Gemini (default, faster)
- `--model claude` - Use Claude (more detailed)
- `--no-duplicates` - Skip duplicate checking

### `/list-roadmap-inbox`

Display inbox items.

**Options:**
- `--slack` - Post list to configured Slack channel
- `--status STATUS` - Filter by status (NEW, TODO, INPROGRESS, DONE)

**Output:**
```
ri-a1b2 [NEW] Add OAuth2 login flow
  Priority: P1 | Category: feature

ri-c3d4 [TODO] Fix validation error -> bd-e5f6
  Priority: P2 | Category: bug
```

### `/bd-create-epic-roadmap ri-XXXX`

Create a Beads epic from roadmap item.

- Creates epic with title, description, AC from roadmap
- Updates roadmap status to TODO
- Links Beads ID to roadmap item
- Posts Slack reply with Beads ID
- Triggers FPF for reasoning context

### `/bd-create-story-roadmap ri-XXXX`

Create a Beads story (task with context) from roadmap item.

### `/bd-create-task-roadmap ri-XXXX`

Create a Beads task from roadmap item.

### `/delete-roadmap-inbox ri-XXXX`

Delete a roadmap item.

- If linked to Beads (TODO/INPROGRESS), closes Beads item
- Posts Slack reply: "item ri-XXXX has been deleted"

---

## Workflows

### Daily Workflow

```
Morning:
1. /boot                    → Captures recent items
2. /parse-roadmap-inbox     → Enriches captured items
3. /list-roadmap-inbox      → Review inbox

Work:
4. /bd-create-task-roadmap ri-XXXX → Create tracked item
5. Implement the feature/fix
6. /bd-close bd-XXXX        → Close when done (auto-updates roadmap)

End:
7. /logout                  → Final capture + archive
```

### Sprint Planning

```
1. /list-roadmap-inbox --status NEW   → See unprioritized items
2. For each item:
   - Decide: epic, story, or task
   - /bd-create-[type]-roadmap ri-XXXX
3. /list-roadmap-inbox --slack       → Post to team channel
```

### Processing Backlog

```
1. /parse-roadmap-inbox              → Process all NEW temp items
2. /list-roadmap-inbox               → Review parsed items
3. Triage:
   - Create Beads for important items
   - Delete duplicates or low-priority items
```

---

## ID Formats

### Temp IDs (tmp-XXXX)

- Format: `tmp-` + 4-char hash
- Example: `tmp-a1b2`
- Used for raw captured items before parsing

### Inbox IDs (ri-XXXX)

- Format: `ri-` + 4-char hash
- Example: `ri-c3d4`
- Used for parsed/enriched items

### Beads IDs (bd-XXXX)

- Format: `bd-` + 4-char hash
- Example: `bd-e5f6`
- Created when item moves to TODO

---

## Slack Notifications

All status changes are communicated via Slack thread replies:

| Event | Reply Message |
|-------|---------------|
| Captured to temp | "captured to temp inbox with tmp.id tmp-a1b2" |
| Parsed | "parsed, inbox item id ri-c3d4" |
| Beads created | "item ri-c3d4 in TODO with bd.id bd-e5f6" |
| Beads closed | "item ri-c3d4 is DONE" |
| Deleted | "item ri-c3d4 has been deleted" |

### Monitored Channels (PM-OS)

- #pmos-slack-channel (CXXXXXXXXXX)
- CXXXXXXXXXX

---

## File Locations

### Temp Inbox
```
/common/data/roadmap/tmp-roadmap-inbox.md
```

### Project Inbox
```
/common/data/roadmap/pm-os-roadmap-inbox.md
```

### State File
```
/common/data/roadmap/roadmap_state.json
```

---

## Priority Guidelines

| Priority | Meaning | When to Use |
|----------|---------|-------------|
| P0 | Critical | Blockers, security issues |
| P1 | High | Core features, important bugs |
| P2 | Medium | Standard work items |
| P3 | Low | Nice-to-have, tech debt |

---

## Troubleshooting

### Items not being captured

1. Check if mentions_state.json exists
2. Verify classification is `pmos_feature` or `pmos_bug`
3. Run capture manually: `python3 roadmap_inbox_manager.py --capture`

### Slack replies not posting

1. Check SLACK_BOT_TOKEN is configured
2. Verify channel access
3. Check source_thread_ts is present in item

### LLM parsing fails

1. Check GEMINI_API_KEY or AWS Bedrock credentials
2. Run with `--model claude` as fallback
3. Parser falls back to simple extraction if LLM unavailable

### Beads creation fails

1. Ensure `bd` CLI is installed
2. Run `bd init` in project directory
3. Check Beads wrapper is importable

---

## Related Documentation

- [Integration Guide](./integration-guide.md) - Technical integration details
- [Beads User Guide](../beads/user-guide.md) - Issue tracking
- [FPF Commands](../commands/fpf-commands.md) - Reasoning framework

---

*Last Updated: 2026-01-19*
*PM-OS v3.0 - Roadmap Inbox*
