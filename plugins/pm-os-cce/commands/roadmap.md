---
description: Roadmap and Jira integration — sync, parse, manage items
---

# /roadmap -- Roadmap and Jira Integration

Parse the first argument to determine which subcommand to run:

| Subcommand | Description |
|------------|-------------|
| `parse` | Parse roadmap inbox items from connectors |
| `list` | List roadmap items with filters |
| `create` | Create a roadmap item |
| `delete` | Delete a roadmap item |
| `create-epic` | Create Jira epic from roadmap item |
| `create-story` | Create Jira story from roadmap item |
| `create-task` | Create Jira task from roadmap item |
| *(no args)* | Show available subcommands |

## Arguments
$ARGUMENTS

## No Arguments -- Show Help

If no arguments provided, display:

```
Roadmap -- Roadmap and Jira Integration

  /roadmap parse                          - Parse roadmap inbox items
  /roadmap parse --source gdrive          - Parse from specific source
  /roadmap parse --dry-run                - Preview parsed items
  /roadmap list                           - List all roadmap items
  /roadmap list --status active           - Filter by status
  /roadmap list --priority high           - Filter by priority
  /roadmap list --epic "Epic Name"        - Filter by epic
  /roadmap create "Title"                 - Create roadmap item
  /roadmap create --type feature          - Create with specific type
  /roadmap delete <id>                    - Delete roadmap item
  /roadmap create-epic "Epic Name"        - Create Jira epic
  /roadmap create-epic --project KEY      - Specify Jira project
  /roadmap create-story "Story Title"     - Create Jira story
  /roadmap create-story --epic KEY-123    - Under specific epic
  /roadmap create-task "Task Title"       - Create Jira task
  /roadmap create-task --story KEY-456    - Under specific story

Usage: /roadmap <subcommand> [options]
```

---

## parse

Parse roadmap inbox items from connectors (GDrive, Confluence, Slack).

**Options:**

| Flag | Description |
|------|-------------|
| `--source <name>` | Parse from specific source: gdrive, confluence, slack, all (default: all) |
| `--dry-run` | Preview parsed items without saving |
| `--verbose, -v` | Show detailed parsing progress |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Parse Inbox

```bash
python3 "$PLUGIN_ROOT/tools/integration/jira_integration.py" parse-inbox $ARGUMENTS
```

### Step 3: Present Results

- Items parsed (count by source)
- New items identified
- Duplicates detected
- Suggested categorization

---

## list

List roadmap items with optional filters.

**Options:**

| Flag | Description |
|------|-------------|
| `--status <status>` | Filter: active, planned, done, archived |
| `--priority <level>` | Filter: critical, high, medium, low |
| `--epic <name>` | Filter by parent epic |
| `--assignee <name>` | Filter by assignee |
| `--format json` | Machine-readable output |
| `--limit <n>` | Max results (default: 50) |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: List Items

```bash
python3 "$PLUGIN_ROOT/tools/integration/jira_integration.py" list $ARGUMENTS
```

### Step 3: Present Results

Display roadmap items as a formatted table:

| ID | Title | Type | Priority | Status | Epic | Assignee |
|----|-------|------|----------|--------|------|----------|
| ... | ... | ... | ... | ... | ... | ... |

---

## create

Create a roadmap item (local tracking).

**Arguments:**
- `"title"` -- Item title (required)

**Options:**

| Flag | Description |
|------|-------------|
| `--type <type>` | feature, improvement, bug, tech-debt (default: feature) |
| `--priority <level>` | critical, high, medium, low (default: medium) |
| `--epic <name>` | Parent epic |
| `--description "text"` | Item description |
| `--feature <slug>` | Link to feature workspace |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Create Item

```bash
python3 "$PLUGIN_ROOT/tools/integration/jira_integration.py" create --title "$TITLE" $ARGUMENTS
```

### Step 3: Present Results

- Item created with ID
- Suggested next: `/roadmap create-epic` or `/roadmap create-story` to push to Jira

---

## delete

Delete a roadmap item.

**Arguments:**
- `<id>` -- Item ID to delete (required)

**Options:**

| Flag | Description |
|------|-------------|
| `--confirm` | Skip confirmation prompt |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Delete Item

```bash
python3 "$PLUGIN_ROOT/tools/integration/jira_integration.py" delete --id "$ID" $ARGUMENTS
```

---

## create-epic

Create a Jira epic from a roadmap item or new specification.

**Arguments:**
- `"title"` -- Epic title (required)

**Options:**

| Flag | Description |
|------|-------------|
| `--project <key>` | Jira project key (default: from config) |
| `--description "text"` | Epic description |
| `--feature <slug>` | Link to feature workspace |
| `--labels "a,b"` | Jira labels |
| `--dry-run` | Preview without creating |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Load Feature Context (if linked)

If `--feature` is provided:
```bash
python3 "$PLUGIN_ROOT/tools/feature/context_doc_generator.py" --feature "$FEATURE_SLUG" --show
```

### Step 3: Create Epic

```bash
python3 "$PLUGIN_ROOT/tools/integration/jira_integration.py" create-epic --title "$TITLE" $ARGUMENTS
```

### Step 4: Present Results

- Jira epic key (e.g., PROJ-123)
- Epic URL
- Fields populated
- Suggested next: `/roadmap create-story` to add stories

---

## create-story

Create a Jira story, optionally under an epic.

**Arguments:**
- `"title"` -- Story title (required)

**Options:**

| Flag | Description |
|------|-------------|
| `--epic <key>` | Parent Jira epic key (e.g., PROJ-123) |
| `--project <key>` | Jira project key (default: from config) |
| `--points <n>` | Story points estimate |
| `--description "text"` | Story description |
| `--acceptance "criteria"` | Acceptance criteria |
| `--dry-run` | Preview without creating |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Create Story

```bash
python3 "$PLUGIN_ROOT/tools/integration/jira_integration.py" create-story --title "$TITLE" $ARGUMENTS
```

### Step 3: Present Results

- Jira story key
- Story URL
- Parent epic (if linked)
- Suggested next: `/roadmap create-task` to break into tasks

---

## create-task

Create a Jira task, optionally under a story.

**Arguments:**
- `"title"` -- Task title (required)

**Options:**

| Flag | Description |
|------|-------------|
| `--story <key>` | Parent Jira story key |
| `--project <key>` | Jira project key (default: from config) |
| `--assignee <name>` | Task assignee |
| `--description "text"` | Task description |
| `--dry-run` | Preview without creating |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Create Task

```bash
python3 "$PLUGIN_ROOT/tools/integration/jira_integration.py" create-task --title "$TITLE" $ARGUMENTS
```

### Step 3: Present Results

- Jira task key
- Task URL
- Parent story (if linked)

---

## Execute

Parse arguments and run the appropriate roadmap subcommand. If arguments match multiple subcommands, prefer the most specific match.
