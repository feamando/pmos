# Beads User Guide

> **Purpose:** Comprehensive guide to using Beads for issue tracking in PM-OS projects.

---

## Core Concepts

### Hash-Based IDs

Beads uses hash-based identifiers instead of sequential numbers:

- **Format:** `bd-a1b2` (4-character hex suffix)
- **Benefit:** No merge conflicts when multiple agents create issues simultaneously
- **Hierarchy:** Tasks get suffix: `bd-a1b2.1`, `bd-a1b2.2`, etc.

### Issue Types

| Type | Use Case | Example |
|------|----------|---------|
| **Epic** | Large feature or initiative | "User Authentication System" |
| **Task** | Single unit of work | "Add login form" |
| **Subtask** | Breakdown of a task | "Validate email format" |

### Priority Levels

| Priority | Meaning | When to Use |
|----------|---------|-------------|
| P0 | Critical | Blockers, security issues |
| P1 | High | Core features, important bugs |
| P2 | Medium | Standard work items |
| P3 | Low | Nice-to-have, tech debt |

---

## Slash Commands Reference

### Creating Issues

#### `/bd-create "Title" [options]`

Create a new issue.

**Options:**
- `--type`: epic, task, subtask (default: task)
- `--priority` or `-p`: 0-3 (default: 1)
- `--parent`: Parent issue ID for hierarchy
- `--description` or `-d`: Detailed description

**Examples:**

```bash
# High-priority epic
/bd-create "Implement OTP Checkout" --type epic --priority 0

# Task under an epic
/bd-create "Add payment form" --parent bd-a3f8 -p 1

# Quick bug fix
/bd-create "Fix validation error on mobile" -p 2
```

### Viewing Issues

#### `/bd-ready`

List issues with no open blockers, ready to work on.

```
Ready Issues:

ID       | Priority | Title
---------|----------|---------------------------
bd-c4d5  | P0       | Security patch for auth
bd-a3f8.2| P1       | Add logout button

Total: 2 ready
```

#### `/bd-list [options]`

List all issues.

**Options:**
- `--status`: Filter by open/closed
- `--parent`: Filter by parent ID

**Examples:**

```bash
/bd-list                      # All issues
/bd-list --status open        # Only open
/bd-list --parent bd-a3f8     # Tasks under epic
```

#### `/bd-show bd-XXXX`

Show full details of a specific issue.

```bash
/bd-show bd-a3f8
```

**Output includes:**
- Title, type, status, priority
- Description
- Dependencies (blocks/blocked by)
- Child issues
- History

### Updating Issues

#### `/bd-update bd-XXXX [options]`

Update issue properties.

**Options:**
- `--title`: Change title
- `--priority`: Change priority
- `--status`: Change status

**Examples:**

```bash
# Escalate priority
/bd-update bd-c4d5 --priority 0

# Update title
/bd-update bd-a3f8.1 --title "Add login form with OAuth support"
```

### Closing Issues

#### `/bd-close bd-XXXX [options]`

Close an issue with rationale.

**Options:**
- `--rationale` or `-r`: Reason for closing
- `--resolution`: completed, wontfix, duplicate (default: completed)

**Examples:**

```bash
# Completed task
/bd-close bd-a3f8.1 --rationale "All tests passing, code reviewed"

# Won't fix
/bd-close bd-c4d5 --resolution wontfix --rationale "Descoped from MVP"

# Duplicate
/bd-close bd-e5f6 --resolution duplicate --rationale "Duplicate of bd-a3f8.2"
```

### Context Injection

#### `/bd-prime [issue_id]`

Load Beads context for focused work.

```bash
/bd-prime           # General project context
/bd-prime bd-a3f8   # Focus on specific issue
```

---

## Workflows

### Daily Workflow

```
Morning:
1. /bd-ready           → See what's ready
2. /bd-prime bd-XXXX   → Load context for task

Work:
3. Implement the task
4. Test and verify

Complete:
5. /bd-close bd-XXXX --rationale "..."
6. Repeat with next ready task
```

### Sprint Planning

```
1. Create epic:
   /bd-create "Sprint 5: OTP Launch" --type epic -p 0

2. Add tasks:
   /bd-create "Backend API" --parent bd-EPIC
   /bd-create "Frontend UI" --parent bd-EPIC
   /bd-create "Testing" --parent bd-EPIC

3. Set dependencies (if needed):
   bd dep add bd-EPIC.2 bd-EPIC.1   # UI blocked by API

4. Review:
   /bd-list --parent bd-EPIC
```

### With Ralph Loops

When working in a Ralph loop:

```
1. Create epic:
   /bd-create "User Auth" --type epic -p 0

2. Initialize Ralph feature:
   /ralph-init user-auth --title "User Authentication"

3. Create specs (generates ACs):
   /ralph-specs user-auth

4. Sync ACs to Beads tasks:
   # Done automatically or manually via bridge

5. Each Ralph iteration:
   - Complete one AC
   - Close corresponding Beads task
   - Log iteration

6. Feature complete:
   - /bd-close bd-EPIC
   - /q5-decide (create DRR)
```

---

## Best Practices

### Naming Conventions

| Good | Bad |
|------|-----|
| "Add OAuth2 login flow" | "Login stuff" |
| "Fix validation for email field" | "Fix bug" |
| "Refactor auth module for testability" | "Cleanup" |

### Priority Guidelines

- **P0**: Use sparingly. Only for genuine blockers.
- **P1**: Default for planned sprint work
- **P2**: Backlog items, tech debt
- **P3**: Ideas, future consideration

### Epic Structure

```
Epic: "User Authentication" (bd-a3f8)
├── Task: "Login flow" (bd-a3f8.1)
│   ├── Subtask: "Email validation" (bd-a3f8.1.1)
│   └── Subtask: "Password rules" (bd-a3f8.1.2)
├── Task: "Logout flow" (bd-a3f8.2)
└── Task: "Password reset" (bd-a3f8.3)
```

### Closing with Context

Always provide rationale when closing:

```bash
# Good
/bd-close bd-a3f8.1 --rationale "Login form complete with OAuth, tested on all browsers"

# Bad
/bd-close bd-a3f8.1
```

---

## Integration with PM-OS

### Automatic Logging

All Beads actions are logged to Confucius:

| Action | Confucius Type |
|--------|----------------|
| Create issue | Action |
| Update issue | Observation |
| Close issue | Decision |

### FPF for Epics

When creating an epic (`--type epic`):

1. FPF trigger file is created
2. You're prompted to run `/q0-init`
3. This establishes reasoning context for the epic

### Ralph Synchronization

Epics can be linked to Ralph features:

- Epic → Ralph feature (via bridge)
- ACs → Beads tasks (auto-sync)
- Iteration complete → Task closed

---

## Tips & Tricks

### Quick Status Check

```bash
bd stats   # Raw bd command for statistics
```

### JSON Output for Automation

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/beads/beads_wrapper.py" list
# Returns JSON for parsing
```

### Finding Issues

```bash
# All P0 issues
/bd-list --status open | grep "P0"

# Issues for specific epic
/bd-list --parent bd-a3f8
```

---

## Related Documentation

- [Installation Guide](./installation-guide.md) - Setup instructions
- [Integration Guide](./integration-guide.md) - Confucius, FPF, Ralph details
- [Ralph Workflow](../commands/ralph-loop.md) - Ralph loop documentation

---

*Last Updated: 2026-01-19*
*PM-OS v3.0 - Beads Integration*
