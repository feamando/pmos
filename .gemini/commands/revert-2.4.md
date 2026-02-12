# Revert to PM-OS 2.4

Revert a v3.0 migration back to your original v2.4 installation.

## When to Use

- Migration didn't work as expected
- You need to go back to v2.4 for compatibility
- Something broke during migration

## Prerequisites

- A valid snapshot from the migration
- Know the snapshot path (e.g., `../snapshots/snapshot-20260112-143052`)

## Instructions

### Step 1: List Available Snapshots

```bash
python3 "$PM_OS_COMMON/tools/migration/snapshot.py" list --dir ../snapshots
```

This shows all available snapshots with dates and sizes.

### Step 2: Verify Snapshot Integrity

```bash
python3 "$PM_OS_COMMON/tools/migration/snapshot.py" verify /path/to/snapshot
```

Ensure the snapshot is complete and uncorrupted.

### Step 3: Preview Revert (Dry Run)

```bash
python3 "$PM_OS_COMMON/tools/migration/revert.py" /path/to/snapshot --dry-run
```

Review what will be restored.

### Step 4: Run Revert

```bash
python3 "$PM_OS_COMMON/tools/migration/revert.py" /path/to/snapshot
```

Confirm when prompted.

### Step 5: Verify Restoration

After revert:

1. Check your files are back:
   ```bash
   ls $PM_OS_USER/brain/
   ls AI_Guidance/Sessions/
   ```

2. Verify git status (if applicable):
   ```bash
   git status
   ```

3. Try booting the old way:
   ```
   /boot
   ```

## Options

### Force Revert (Skip Confirmation)

```bash
python3 revert.py /path/to/snapshot --force
```

### Also Clean v3.0 Structure

Remove the pm-os/ directory structure after revert:

```bash
python3 revert.py /path/to/snapshot --clean-v30
```

### Restore to Different Location

```bash
python3 revert.py /path/to/snapshot --target /new/location
```

## What Gets Restored

Everything in the snapshot:
- All files from `AI_Guidance/`
- Brain entities
- Sessions
- Context files
- Rules and templates
- .env (if it was included)

## What Doesn't Get Restored

- `.git` directory (unless `--include-git` was used during snapshot)
- Files excluded from snapshot (node_modules, __pycache__, etc.)

## After Revert

1. **Your v2.4 installation is restored** at the original location
2. **The v3.0 structure remains** (unless you used `--clean-v30`)
3. **The snapshot is preserved** for future use

You can:
- Continue using v2.4 as before
- Try migration again later
- Keep both versions (v2.4 and v3.0 can coexist)

## Troubleshooting

**Snapshot not found:**
Check the path. Snapshots are typically in `../snapshots/` relative to your repo.

**Checksum mismatch:**
The snapshot may be corrupted. Check disk for errors.

**Permission denied:**
Run with appropriate permissions or check directory ownership.

**Files missing after revert:**
Some files may not have been in the snapshot. Check snapshot metadata:
```bash
cat /path/to/snapshot/metadata.json
```

## Emergency Revert

If the normal revert fails, you can manually restore:

```bash
# 1. Go to snapshot
cd /path/to/snapshot/content

# 2. Copy everything to target
cp -r * /path/to/your/v2.4/repo/

# 3. Verify
ls /path/to/your/v2.4/repo/AI_Guidance/
```
