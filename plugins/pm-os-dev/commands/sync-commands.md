---
description: Synchronize plugin commands across CLI environments
---

# /sync-commands -- Synchronize Commands Across CLIs

Sync plugin commands across Claude Code, Gemini, and other CLI environments.

## Arguments
$ARGUMENTS

## No Arguments -- Default Sync

If no arguments provided, run the default sync:

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$0")")"
python3 "$PLUGIN_ROOT/tools/dev_util/command_sync.py"
```

## Options

| Flag | Description |
|------|-------------|
| `--status` | Show sync status without syncing |
| `--clean` | Remove synced commands from target |
| `--dry-run` | Preview sync without making changes |
| `--validate` | Validate parity across CLIs |

### Status

```bash
python3 "$PLUGIN_ROOT/tools/dev_util/command_sync.py" --status
```

Display: Source and target directories, last sync time, synced files, pending syncs.

### Clean

```bash
python3 "$PLUGIN_ROOT/tools/dev_util/command_sync.py" --clean
```

Remove commands that were synced from plugin sources.

### Validate

```bash
python3 "$PLUGIN_ROOT/tools/dev_util/cross_cli_validator.py"
```

Check command parity across CLI environments. Report missing or divergent commands.

## Execute

Parse arguments and run the appropriate sync subcommand.
