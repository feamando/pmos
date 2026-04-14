#!/bin/bash
# release.sh — Full release pipeline: build → upload → update manifest
# Usage: bash scripts/release.sh [base-version] [gdrive-folder-id]
# Example: bash scripts/release.sh 0.8.0 1ABC123folderID

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="$(dirname "$SCRIPT_DIR")"

BASE_VERSION="${1:-$(node -p "require('$APP_ROOT/package.json').version")}"
FOLDER_ID="${2:-}"
DATE_STAMP=$(date +%Y%m%d)
FULL_VERSION="${BASE_VERSION}-${DATE_STAMP}"

echo "=========================================="
echo "  PM-OS Release Pipeline"
echo "  Version: $FULL_VERSION"
echo "=========================================="
echo ""

# Step 1: Build
echo "--- Step 1/3: Building release ---"
bash "$SCRIPT_DIR/build-release.sh" "$BASE_VERSION"

# Find the zip
ZIP_PATH=$(ls "$APP_ROOT/dist/"*mac*.zip 2>/dev/null | head -1)
if [ -z "$ZIP_PATH" ]; then
  echo "ERROR: No zip found after build"
  exit 1
fi

# Step 2: Upload to GDrive
echo ""
echo "--- Step 2/3: Uploading to GDrive ---"
if [ -n "$FOLDER_ID" ]; then
  FILE_ID=$(bash "$SCRIPT_DIR/upload-to-gdrive.sh" "$ZIP_PATH" "$FOLDER_ID")
else
  FILE_ID=$(bash "$SCRIPT_DIR/upload-to-gdrive.sh" "$ZIP_PATH")
fi

if [ -z "$FILE_ID" ]; then
  echo "ERROR: Upload failed — no file ID returned"
  exit 1
fi
echo "  GDrive File ID: $FILE_ID"

# Step 3: Update manifest
echo ""
echo "--- Step 3/3: Updating manifest ---"
bash "$SCRIPT_DIR/update-manifest.sh" "$FULL_VERSION" "$FILE_ID" "$ZIP_PATH"

SHA256=$(shasum -a 256 "$ZIP_PATH" | awk '{print $1}')
SIZE=$(stat -f%z "$ZIP_PATH" 2>/dev/null || stat -c%s "$ZIP_PATH" 2>/dev/null)

echo ""
echo "=========================================="
echo "  Release Complete!"
echo "  Version:  $FULL_VERSION"
echo "  File ID:  $FILE_ID"
echo "  SHA256:   $SHA256"
echo "  Size:     $SIZE bytes"
echo "=========================================="
echo ""
echo "To publish: cd to PM-OS root and run 'git push origin main'"
