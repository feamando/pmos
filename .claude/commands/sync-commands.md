# Sync Developer Commands

Manually sync slash commands from developer/ to common/.claude/commands/

## Instructions

### Step 1: Check Developer Folder

```bash
if [ ! -d "$PM_OS_ROOT/developer" ]; then
    echo "No developer folder found at $PM_OS_ROOT/developer"
    exit 0
fi
```

### Step 2: Run Sync

```bash
python3 "$PM_OS_COMMON/tools/util/command_sync.py"
```

### Step 3: Show Status

If `--status` flag provided:

```bash
python3 "$PM_OS_COMMON/tools/util/command_sync.py" --status
```

### Step 4: Clean (if requested)

If `--clean` flag provided, remove synced commands:

```bash
python3 "$PM_OS_COMMON/tools/util/command_sync.py" --clean
```

## Usage

```
/sync-commands           # Sync developer commands to common
/sync-commands --status  # Show sync status
/sync-commands --clean   # Remove synced commands
```

## What Gets Synced

Commands from `$PM_OS_ROOT/developer/.claude/commands/`:
- Beads commands: `/bd-create`, `/bd-list`, `/bd-show`, etc.
- Roadmap commands: `/parse-roadmap-inbox`, `/list-roadmap-inbox`, etc.
- Developer utilities: `/boot-dev`, `/preflight`

## Notes

- Sync is idempotent - safe to run multiple times
- Won't overwrite commands that exist in common but weren't synced by this tool
- Manifest tracks which files were synced for clean removal
- Automatically runs on `/boot` when developer folder exists
