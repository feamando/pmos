# Migrate to PM-OS 3.0

Migrate your PM-OS v2.4 installation to the v3.0 structure.

## What This Does

1. **Creates snapshot** - Full backup of your current installation
2. **Creates new structure** - Sets up pm-os/common/ and pm-os/user/
3. **Migrates content** - Moves your Brain, sessions, context to user/
4. **Generates config** - Creates config.yaml from your current settings
5. **Validates** - Verifies everything transferred correctly

## Prerequisites

- Python 3.10+
- Git (recommended)
- Clean working tree (recommended)

## Instructions

### Step 1: Run Preflight Checks

```bash
python3 AI_Guidance/Tools/migration/preflight.py
```

Review the output. Address any failures before proceeding.

### Step 2: Create Snapshot

```bash
python3 AI_Guidance/Tools/migration/snapshot.py create .
```

Note the snapshot path - you'll need this if you want to revert.

### Step 3: Get PM-OS 3.0 Common

Clone the PM-OS common repository:

```bash
cd ..
mkdir pm-os
cd pm-os
git clone https://github.com/feamando/pmos.git common
```

### Step 4: Run Migration

```bash
python3 common/tools/migration/migrate.py /path/to/your/v2.4/repo
```

Or from within your v2.4 repo:

```bash
python3 ../pm-os/common/tools/migration/migrate.py .
```

### Step 5: Validate Migration

```bash
python3 common/tools/migration/validate.py user/
```

### Step 6: Configure

Edit `pm-os/user/config.yaml`:
- Verify your name and email
- Enable/configure integrations
- Set preferences

Edit `pm-os/user/.env`:
- Add any missing API tokens
- Update paths if needed

### Step 7: Boot New Installation

```bash
cd pm-os/user
source ../common/scripts/boot.sh
```

Then in your AI CLI:
```
/boot
```

## Dry Run

To preview migration without making changes:

```bash
python3 common/tools/migration/migrate.py . --dry-run
```

## Reverting

If something goes wrong:

```bash
python3 common/tools/migration/revert.py /path/to/snapshot
```

This restores your v2.4 installation from the snapshot.

## What Migrates

| v2.4 Location | v3.0 Location |
|---------------|---------------|
| `AI_Guidance/Brain/` | `user/brain/` |
| `AI_Guidance/Core_Context/` | `user/context/` |
| `AI_Guidance/Sessions/` | `user/sessions/` |
| `AI_Guidance/Rules/NGO.md` | `user/USER.md` |
| `Planning/` | `user/planning/` |
| `Team/` | `user/team/` |
| `Products/` | `user/products/` |
| `.env` | `user/.env` |

## What Stays in Common

These are now in the shared `common/` repository:

- All slash commands (`.claude/commands/`, `.gemini/commands/`)
- All tools (`tools/`)
- Templates (`frameworks/`)
- Rules (`rules/AI_AGENTS_GUIDE.md`)
- Schemas (`schemas/`)

## After Migration

Your old repository remains untouched. You can:

1. **Archive it** - Keep as backup
2. **Delete it** - Once you're confident migration worked
3. **Use as reference** - For any custom modifications

The new structure:
```
pm-os/
├── common/     # Git repo: feamando/pmos
├── user/       # Your data (can be its own git repo)
└── snapshots/  # Migration backups
```

## Troubleshooting

**Migration fails with permission error:**
Check you have write access to the parent directory.

**Config generation fails:**
The migration creates a basic config. Edit manually after migration.

**Some files not migrated:**
Check the migration log for skipped files. Some files (like `.git`, `__pycache__`) are intentionally skipped.

**Validation fails:**
Run with `--verbose` to see details. Common issues:
- Missing directories (create them)
- Config syntax errors (fix YAML)
- Path resolution issues (check markers)
