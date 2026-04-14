#!/bin/bash
# build-release.sh — Build a versioned release of PM-OS
# Usage: bash scripts/build-release.sh [base-version]
# Example: bash scripts/build-release.sh 0.8.0

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$APP_ROOT"

# Version: base from arg or package.json, append date stamp
BASE_VERSION="${1:-$(node -p "require('./package.json').version")}"
DATE_STAMP=$(date +%Y%m%d)
FULL_VERSION="${BASE_VERSION}-${DATE_STAMP}"

echo "=== PM-OS Release Build ==="
echo "  Version: $FULL_VERSION"
echo "  App root: $APP_ROOT"
echo ""

# Temporarily set version in package.json
ORIGINAL_VERSION=$(node -p "require('./package.json').version")
npm version "$FULL_VERSION" --no-git-tag-version --allow-same-version

# Build
echo "Running npm run dist..."
npm run dist

# Restore original version
npm version "$ORIGINAL_VERSION" --no-git-tag-version --allow-same-version

# Locate output
ZIP_PATH="$APP_ROOT/dist/PM-OS-${FULL_VERSION}-mac.zip"
if [ ! -f "$ZIP_PATH" ]; then
  # electron-builder may use different naming
  ZIP_PATH=$(ls "$APP_ROOT/dist/"*mac*.zip 2>/dev/null | head -1 || echo "")
fi

if [ -z "$ZIP_PATH" ] || [ ! -f "$ZIP_PATH" ]; then
  echo "ERROR: Could not find built zip in dist/"
  exit 1
fi

# Compute SHA256
SHA256=$(shasum -a 256 "$ZIP_PATH" | awk '{print $1}')
SIZE=$(stat -f%z "$ZIP_PATH" 2>/dev/null || stat -c%s "$ZIP_PATH" 2>/dev/null)

echo ""
echo "=== Build Complete ==="
echo "  Version: $FULL_VERSION"
echo "  Zip: $ZIP_PATH"
echo "  Size: $SIZE bytes"
echo "  SHA256: $SHA256"
echo ""
echo "Next: Upload to GDrive and run scripts/update-manifest.sh"
