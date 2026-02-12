# Developer Commands

> Commands for PM-OS development, issue tracking, and roadmap management

## Overview

Developer commands are available when the `developer/` folder is installed. They auto-sync to `common/.claude/commands/` on boot.

**Total: 21 commands** in three categories:
- Beads Issue Tracking (10)
- Roadmap Management (3)
- Developer Utilities (8)

---

## Beads Commands

Beads is a lightweight, Git-based issue tracking system integrated with PM-OS.

### /bd-create

Create a new issue in the Beads tracker.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `"title"` | Issue title (required) |
| `--type` | epic, task, or subtask (default: task) |
| `--priority` | 0-3 where 0 is highest (default: 1) |
| `--parent` | Parent issue ID for hierarchy |
| `--description` | Detailed description |

**Usage:**

```
/bd-create "Add user authentication" --type epic --priority 0
/bd-create "Implement login form" --parent bd-a3f8
```

---

### /bd-list

List all issues, optionally filtered.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `--status` | Filter by status (open, closed, all) |
| `--parent` | Filter by parent issue ID |
| `--type` | Filter by type (epic, task, subtask) |

**Usage:**

```
/bd-list                    # All open issues
/bd-list --status closed    # Closed issues
/bd-list --parent bd-a3f8   # Child issues of epic
```

---

### /bd-show

View detailed information about a specific issue.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `issue-id` | Issue ID to display (required) |

**Usage:**

```
/bd-show bd-a3f8
```

---

### /bd-update

Update an existing issue's fields.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `issue-id` | Issue ID to update (required) |
| `--title` | New title |
| `--status` | New status |
| `--priority` | New priority |
| `--description` | New description |

**Usage:**

```
/bd-update bd-a3f8 --priority 0 --status in_progress
```

---

### /bd-close

Close an issue.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `issue-id` | Issue ID to close (required) |
| `--reason` | Closure reason (optional) |

**Usage:**

```
/bd-close bd-a3f8
/bd-close bd-a3f8 --reason "Shipped in v3.2"
```

---

### /bd-ready

List issues ready for development (open, no blockers).

**Arguments:**

| Argument | Description |
|----------|-------------|
| `--limit` | Max issues to show (default: 10) |

**Usage:**

```
/bd-ready
/bd-ready --limit 5
```

---

### /bd-prime

Prime Claude with full context of an issue for development.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `issue-id` | Issue ID to prime (required) |

**What It Does:**

1. Loads issue details and history
2. Loads parent epic context (if applicable)
3. Loads related Brain entities
4. Sets up development context

**Usage:**

```
/bd-prime bd-a3f8
```

---

### /bd-create-epic-roadmap

Create a Beads epic from a roadmap inbox item.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `item-id` | Roadmap item ID (required) |

**Usage:**

```
/bd-create-epic-roadmap tmp-0042
```

---

### /bd-create-story-roadmap

Create a Beads story from a roadmap inbox item.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `item-id` | Roadmap item ID (required) |
| `--parent` | Parent epic ID |

**Usage:**

```
/bd-create-story-roadmap tmp-0042 --parent bd-a3f8
```

---

### /bd-create-task-roadmap

Create a Beads task from a roadmap inbox item.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `item-id` | Roadmap item ID (required) |
| `--parent` | Parent story/epic ID |

**Usage:**

```
/bd-create-task-roadmap tmp-0042 --parent bd-a3f8.1
```

---

## Roadmap Commands

Capture and manage feature requests from Slack mentions.

### /parse-roadmap-inbox

Process NEW items from the temp inbox through LLM enrichment.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `--model` | LLM to use: gemini or claude (default: gemini) |
| `--dry-run` | Preview without saving |

**What It Does:**

1. Loads NEW items from temp inbox
2. For each item, extracts:
   - Clear, actionable title
   - Comprehensive description
   - 2-5 acceptance criteria
   - Priority (P0-P3)
   - Category (feature/bug)
3. Checks for duplicates
4. Saves enriched items

**Usage:**

```
/parse-roadmap-inbox
/parse-roadmap-inbox --model claude --dry-run
```

---

### /list-roadmap-inbox

View items in the roadmap inbox.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `--status` | Filter: NEW, PARSED, CREATED (default: all) |
| `--limit` | Max items to show |

**Usage:**

```
/list-roadmap-inbox
/list-roadmap-inbox --status PARSED
```

---

### /delete-roadmap-inbox

Remove an item from the roadmap inbox.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `item-id` | Item ID to delete (required) |
| `--confirm` | Skip confirmation prompt |

**Usage:**

```
/delete-roadmap-inbox tmp-0042
/delete-roadmap-inbox tmp-0042 --confirm
```

---

## Developer Utilities

### /boot-dev

Initialize the developer environment.

**Arguments:**

None

**What It Does:**

1. Checks developer folder exists
2. Syncs developer commands to common
3. Initializes Beads if `.beads` exists
4. Reports developer tools status

**Usage:**

```
/boot-dev
```

---

### /sync-commands

Manually sync developer commands to common.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `--status` | Show sync status only |
| `--clean` | Remove synced commands |

**Usage:**

```
/sync-commands           # Sync commands
/sync-commands --status  # Show what's synced
/sync-commands --clean   # Remove synced commands
```

---

### /preflight

Run system verification checks.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `--quick` | Import tests only (fast) |
| `--category` | Check specific category |
| `--json` | Output as JSON |

**What It Does:**

1. Verifies all tool modules import correctly
2. Checks required classes and functions exist
3. Validates configuration and environment
4. Reports system health status

**Usage:**

```
/preflight              # Full check
/preflight --quick      # Fast check
/preflight --category core
```

---

### /push

Publish PM-OS components to repositories.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `all` | Push all enabled targets (default) |
| `common` | Push common only (via PR) |
| `brain` | Push brain only (direct) |
| `user` | Push user only (direct) |
| `--dry-run` | Preview without pushing |
| `--status` | Show push status |

**What It Does:**

- **common**: Creates PR to feamando/pmos
- **brain**: Direct push to personal brain repo
- **user**: Direct push to personal user repo

**Usage:**

```
/push                 # Push all
/push common          # Common only (PR)
/push --dry-run       # Preview
```

---

### /brain-enrich

Run Brain quality improvement tools.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `--mode` | full, quick, report, boot |
| `--quick` | Shortcut for --mode quick |
| `--report` | Shortcut for --mode report |
| `--dry-run` | Preview changes |

**Modes:**

| Mode | Description |
|------|-------------|
| `full` | All tools, apply changes |
| `quick` | Soft edges only (fast) |
| `report` | Analysis only, no changes |
| `boot` | Minimal checks for boot |

**Usage:**

```
/brain-enrich              # Full enrichment
/brain-enrich --quick      # Fast density boost
/brain-enrich --report     # Status check only
```

---

### /export-to-spec

Export a PRD to spec-machine input format.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `prd-path` | Path to PRD file (required) |
| `--repo` | Target repo alias |
| `--spec-name` | Name for spec folder |
| `--subdir` | Spec subdirectory |

**What It Does:**

1. Parses PRD sections
2. Generates Q&A format requirements
3. Creates spec folder structure
4. Injects tech stack context

**Usage:**

```
/export-to-spec path/to/prd.md --repo mobile-rn
/export-to-spec path/to/prd.md --spec-name user-auth --repo web
```

---

### /documentation

Manage PM-OS documentation.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `--sync` | Sync to Confluence |
| `--status` | Show sync status |
| `--validate` | Validate local docs |

**Usage:**

```
/documentation --sync      # Sync to Confluence
/documentation --status    # Check sync status
```

---

### /sprint-learnings

Generate sprint retrospective learnings.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `--sprint` | Sprint identifier |
| `--team` | Team filter |

**Usage:**

```
/sprint-learnings
/sprint-learnings --sprint 2026-W05 --team "Meal Kit"
```

---

## Installation

Developer commands require the `developer/` folder:

```bash
# Clone developer branch
cd ~/pm-os
git clone -b developer <pm-os-repo> developer

# Commands auto-sync on /boot
/boot
```

Or manually sync:

```bash
/sync-commands
```

---

## Related Documentation

- [Beads User Guide](../beads/user-guide.md)
- [Roadmap Inbox Guide](../roadmap/user-guide.md)
- [Pre-Flight System](../tools/preflight.md)
- [Core Commands](core-commands.md)

---

*Last updated: 2026-02-02*
