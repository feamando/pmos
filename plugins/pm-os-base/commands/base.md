---
description: PM-OS foundation commands — config, preflight, pipeline management
---

# /base — PM-OS Foundation

Parse the first argument to determine which subcommand to run:

| Subcommand | Description |
|------------|-------------|
| `setup` | First-time setup or re-configure PM-OS |
| `status` | Show PM-OS health, installed plugins, config status |
| `plugins` | List, install, or disable plugins |
| `config` | View or edit config.yaml |
| `preflight` | Run system health checks |
| `pipeline` | Execute a YAML pipeline |
| `dashboard` | Launch observability dashboard |

If no arguments provided, display available subcommands:
```
Base - PM-OS Foundation

  /base setup              - First-time setup or re-configure
  /base status             - Show health, plugins, config
  /base plugins            - List installed + available plugins
  /base plugins install X  - Install plugin X
  /base plugins disable X  - Disable plugin X
  /base config             - Show current config summary
  /base config edit        - Open config.yaml for editing
  /base config validate    - Validate config against plugin requirements
  /base preflight          - Run system health checks
  /base pipeline <name>    - Execute named pipeline
  /base pipeline --list    - List available pipelines
  /base dashboard          - Show observability dashboard

Usage: /base <subcommand> [options]
```

---

## setup

First-time setup or re-configure PM-OS. Idempotent: safe to run multiple times, never overwrites existing user data.

### Path Resolution

Resolve `PM_OS_ROOT` and `PLUGIN_BASE` (where pm-os-base tools live):

```bash
export PM_OS_ROOT="${PM_OS_ROOT:-$HOME/pm-os}"
# Find plugin base dir
if [ -d "$PM_OS_ROOT/common/tools" ]; then
  PLUGIN_BASE="$PM_OS_ROOT/common"
elif [ -d "$PM_OS_ROOT/v5/plugins/pm-os-base/tools" ]; then
  PLUGIN_BASE="$PM_OS_ROOT/v5/plugins/pm-os-base"
else
  for candidate in "$PM_OS_ROOT/plugins/pm-os-base" "$HOME/.claude/plugins/pm-os-base"; do
    if [ -d "$candidate/tools" ]; then
      PLUGIN_BASE="$candidate"
      break
    fi
  done
fi
TEMPLATES="$PM_OS_ROOT/v5/templates"
if [ ! -d "$TEMPLATES" ]; then
  TEMPLATES="$PLUGIN_BASE/../templates"
fi
```

### Step 1: Create Directory Structure

Only create directories that do not already exist:

```bash
mkdir -p "$PM_OS_ROOT/user/brain"
mkdir -p "$PM_OS_ROOT/user/personal/context"
mkdir -p "$PM_OS_ROOT/user/sessions"
mkdir -p "$PM_OS_ROOT/user/products"
mkdir -p "$PM_OS_ROOT/user/team"
touch "$PM_OS_ROOT/.pm-os-root"
```

### Step 2: Create Config Files (if missing)

**config.yaml** — only if `$PM_OS_ROOT/user/config.yaml` does not exist:
1. Ask user for `name` and `email`
2. Read `$TEMPLATES/config.yaml.template`
3. Replace `{{user_name}}` and `{{user_email}}` with user's answers
4. Write to `$PM_OS_ROOT/user/config.yaml`

**.env** — only if `$PM_OS_ROOT/user/.env` does not exist:
1. Copy `$TEMPLATES/.env.template` to `$PM_OS_ROOT/user/.env`
2. Tell user: "Edit user/.env to add your API tokens"

**USER.md** — only if `$PM_OS_ROOT/user/USER.md` does not exist:
1. Ask user for `role`, `company`, and `location` (optional, can skip)
2. Read `$TEMPLATES/USER.md.template`
3. Replace placeholders with user's answers (use empty string for skipped fields)
4. Replace `{{generated_date}}` with today's date (YYYY-MM-DD)
5. Write to `$PM_OS_ROOT/user/USER.md`

### Step 3: Generate CLAUDE.md

```bash
python3 "$PLUGIN_BASE/tools/util/claudemd_generator.py"
```

### Step 4: Generate Cowork Context Files

```bash
python3 "$PLUGIN_BASE/tools/util/cowork_context_generator.py"
```

### Step 5: Run Preflight

```bash
python3 "$PLUGIN_BASE/tools/preflight/preflight_runner.py" --quick
```

### Step 6: Report

Print setup summary:
- PM-OS root: `$PM_OS_ROOT`
- Config: created or already existed
- USER.md: created or already existed
- .env: created or already existed
- Installed plugins (list from plugin_deps)
- Preflight results
- Next steps: "Run `/session boot` to start your first session"
- Reminder: "Connect Google/Jira/GitHub/Slack in Claude > Settings > Connectors for full integration"

---

## status

Show PM-OS health, installed plugins, config status.

### Step 1: Gather Status

```bash
python3 tools/core/config_loader.py --check
python3 tools/core/plugin_deps.py --list
python3 tools/session/session_manager.py --status
```

### Step 2: Report

Print:
- PM-OS version (from config.yaml)
- Installed plugins (name, version, status)
- Config health (required fields present, missing keys)
- Last boot time (from session)
- Active session (if any)
- Pending background tasks

---

## plugins

List, install, or disable plugins.

### /base plugins (no args)

List installed and available plugins:

```bash
python3 tools/core/plugin_deps.py --list --available
```

Show table: Plugin Name | Version | Status (installed/available/disabled)

### /base plugins install X

Install plugin X:

1. Check if plugin exists in marketplace
2. Check dependencies (`plugin.json` → `dependencies`)
3. Copy plugin files to plugins/ directory
4. Register MCP servers if plugin has `.mcp.json`
5. Run plugin's setup command if it has one
6. Regenerate CLAUDE.md

### /base plugins disable X

Disable plugin X:

1. Check if other installed plugins depend on X
2. If yes, warn and confirm
3. Remove plugin from active list (keep files)
4. Unregister MCP servers
5. Regenerate CLAUDE.md

---

## config

View or edit config.yaml.

### /base config (no args)

Show current config summary:

```bash
python3 tools/core/config_loader.py --summary
```

### /base config edit

Open config.yaml location and show editable fields:

```bash
python3 tools/core/config_loader.py --path
```

Then read the file and show it with guidance on what each section controls.

### /base config validate

Validate config against all installed plugin requirements:

```bash
python3 tools/core/config_loader.py --validate
```

Check each installed plugin's `requires.config_keys` and report missing keys.

---

## preflight

Run all registered checks from installed plugins.

```bash
python3 tools/preflight/preflight_runner.py
```

Options:
- `--quick` — Import tests only (fast)
- `--category <name>` — Run specific category
- `--verbose` — Show progress
- `--json` — JSON output
- `--list` — Show tool inventory

---

## pipeline

Execute a YAML pipeline.

### /base pipeline <name>

```bash
python3 tools/pipeline/pipeline_executor.py --run pipelines/<name>.yaml
```

### /base pipeline --list

```bash
python3 tools/pipeline/pipeline_executor.py --list
```

### /base pipeline --dry-run <name>

```bash
python3 tools/pipeline/pipeline_executor.py --run pipelines/<name>.yaml --dry-run
```

---

## dashboard

Show PM-OS observability dashboard with key metrics:

1. Read session status
2. Read preflight last-run results
3. Read background task status
4. Read config health
5. Format as dashboard output

---

## Execute

Parse the user's arguments and execute the matching subcommand above. If the subcommand is not recognized, show the available subcommands list.
