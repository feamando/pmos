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

First-time setup or re-configure PM-OS.

### Step 1: Check Config

```bash
python3 tools/core/config_loader.py --check
```

If config.yaml doesn't exist:
1. Ask user for `name` and `email`
2. Create config.yaml from template with those values
3. Set sensible defaults for all other fields

### Step 2: Generate CLAUDE.md

```bash
python3 tools/util/claudemd_generator.py
```

### Step 3: Generate Cowork Context Files

```bash
python3 tools/util/cowork_context_generator.py
```

### Step 4: Run Preflight

```bash
python3 tools/preflight/preflight_runner.py --quick
```

### Step 5: Report

Print setup summary:
- Config location and status
- Installed plugins
- CLAUDE.md generated
- Cowork context files generated
- Preflight results
- Reminder: "Connect Google/Jira/GitHub/Slack in Claude > Settings > Connectors"

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
