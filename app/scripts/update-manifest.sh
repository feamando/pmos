#!/bin/bash
# update-manifest.sh — Update pmos-manifest.json with new release info
# Usage: bash scripts/update-manifest.sh <version> <gdrive-file-id> <zip-path>
# Example: bash scripts/update-manifest.sh 0.8.0-20260331 1ABC123def /path/to/PM-OS-0.8.0-mac.zip

set -euo pipefail

VERSION="${1:?Usage: update-manifest.sh <version> <gdrive-file-id> <zip-path>}"
FILE_ID="${2:?Missing GDrive file ID}"
ZIP_PATH="${3:?Missing zip file path}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="$(dirname "$SCRIPT_DIR")"
PMOS_ROOT="${PM_OS_ROOT:-$(cd "$APP_ROOT/../.." && pwd)}"
MANIFEST="$PMOS_ROOT/common/releases/pmos-manifest.json"

if [ ! -f "$ZIP_PATH" ]; then
  echo "ERROR: Zip file not found: $ZIP_PATH"
  exit 1
fi

SHA256=$(shasum -a 256 "$ZIP_PATH" | awk '{print $1}')
SIZE=$(stat -f%z "$ZIP_PATH" 2>/dev/null || stat -c%s "$ZIP_PATH" 2>/dev/null)
FILENAME="PM-OS-${VERSION}-mac.zip"
URL="https://drive.google.com/uc?id=${FILE_ID}&export=download"
PUBLISHED=$(date -u +%Y-%m-%dT%H:%M:%SZ)

cat > "$MANIFEST" <<EOF
{
  "version": "$VERSION",
  "platform": {
    "darwin": {
      "url": "$URL",
      "filename": "$FILENAME",
      "size": $SIZE,
      "sha256": "$SHA256"
    }
  },
  "releaseNotes": "v${VERSION%%.*}.${VERSION#*.}: App update",
  "minPmosVersion": "4.4.0",
  "publishedAt": "$PUBLISHED"
}
EOF

echo "=== Manifest Updated ==="
echo "  File: $MANIFEST"
echo "  Version: $VERSION"
echo "  SHA256: $SHA256"
echo "  Size: $SIZE"

# Commit to PM-OS repo
cd "$PMOS_ROOT"
git add common/releases/pmos-manifest.json
git commit -m "Release PM-OS $VERSION — update manifest"
echo "  Committed to PM-OS repo"
echo ""
echo "Run 'git push origin main' to publish."
