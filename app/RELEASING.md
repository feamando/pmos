# Releasing PM-OS

## Prerequisites

- Node.js + npm installed
- Google OAuth credentials at `user/.secrets/credentials.json`
- GDrive access (for binary hosting)
- macOS (builds currently macOS-only)

## Quick Release (One Command)

```bash
bash scripts/release.sh 0.8.0 [GDRIVE_FOLDER_ID]
```

This runs the full pipeline: build → upload to GDrive → update manifest → commit.

## Manual Steps

### 1. Build

```bash
bash scripts/build-release.sh 0.8.0
```

Output: `dist/PM-OS-0.8.0-YYYYMMDD-mac.zip`

### 2. Upload to GDrive

```bash
bash scripts/upload-to-gdrive.sh dist/PM-OS-0.8.0-YYYYMMDD-mac.zip [FOLDER_ID]
```

Returns the GDrive file ID.

### 3. Update Manifest

```bash
bash scripts/update-manifest.sh 0.8.0-YYYYMMDD <FILE_ID> dist/PM-OS-0.8.0-YYYYMMDD-mac.zip
```

Updates `common/releases/pmos-manifest.json` and commits.

### 4. Push

```bash
cd /path/to/pm-os && git push origin main
```

## How Updates Work

1. User clicks "Update App" in Settings → App
2. App runs `git pull` on the PM-OS repo (updates manifest + tools)
3. Reads `common/releases/pmos-manifest.json`
4. Compares versions — if newer, downloads zip from GDrive
5. Verifies SHA256 checksum
6. Replaces the `.app` bundle
7. Relaunches

## Versioning

Format: `{semver}-{YYYYMMDD}` (e.g., `0.8.0-20260331`)

- semver tracks feature milestones
- date stamp tracks build date
- Both stored in `package.json` (at build time) and manifest

## Testing Before Publishing

```bash
# Build without uploading
bash scripts/build-release.sh 0.8.0

# Test the built app
open dist/mac/PM-OS.app

# Verify the zip
unzip -t dist/PM-OS-*-mac.zip
```
