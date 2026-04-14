#!/bin/bash
# bundle-pmos.sh — Copy PM-OS common/ into bundle/ for Electron app distribution
# Run from pm-os-app root: bash scripts/bundle-pmos.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="$(dirname "$SCRIPT_DIR")"
PMOS_ROOT="${PM_OS_ROOT:-$(cd "$APP_ROOT/../.." && pwd)}"
BUNDLE_DIR="$APP_ROOT/bundle"
COMMON_SRC="$PMOS_ROOT/common"
BUNDLE_COMMON="$BUNDLE_DIR/common"

echo "=== PM-OS Bundle Script ==="
echo "  PM-OS root: $PMOS_ROOT"
echo "  Bundle dir: $BUNDLE_DIR"
echo ""

# Clean previous bundle common (keep data/ and scripts/)
rm -rf "$BUNDLE_COMMON"
mkdir -p "$BUNDLE_COMMON"

# --- Copy common/ directories ---
echo "Copying common/tools/..."
rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' \
  --exclude='beads/' --exclude='Sessions/' --exclude='push/' \
  "$COMMON_SRC/tools/" "$BUNDLE_COMMON/tools/"

echo "Copying common/.claude/commands/..."
mkdir -p "$BUNDLE_COMMON/.claude/commands"
rsync -a --exclude='archive/' \
  "$COMMON_SRC/.claude/commands/" "$BUNDLE_COMMON/.claude/commands/"

# Copy .gemini commands if they exist
if [ -d "$COMMON_SRC/.gemini/commands" ]; then
  echo "Copying common/.gemini/commands/..."
  mkdir -p "$BUNDLE_COMMON/.gemini/commands"
  rsync -a "$COMMON_SRC/.gemini/commands/" "$BUNDLE_COMMON/.gemini/commands/"
fi

echo "Copying common/pipelines/..."
rsync -a "$COMMON_SRC/pipelines/" "$BUNDLE_COMMON/pipelines/"

if [ -d "$COMMON_SRC/schemas" ]; then
  echo "Copying common/schemas/..."
  rsync -a "$COMMON_SRC/schemas/" "$BUNDLE_COMMON/schemas/"
fi

if [ -d "$COMMON_SRC/AI_Guidance" ]; then
  echo "Copying common/AI_Guidance/..."
  rsync -a "$COMMON_SRC/AI_Guidance/" "$BUNDLE_COMMON/AI_Guidance/"
fi

if [ -d "$COMMON_SRC/templates" ]; then
  echo "Copying common/templates/..."
  rsync -a "$COMMON_SRC/templates/" "$BUNDLE_COMMON/templates/"
fi

if [ -d "$COMMON_SRC/documentation" ]; then
  echo "Copying common/documentation/..."
  rsync -a "$COMMON_SRC/documentation/" "$BUNDLE_COMMON/documentation/"
fi

# Copy root files
for f in AGENT.md AGENT_HOW_TO.md WORKFLOWS.md SETUP.md README.md squad_registry.yaml; do
  if [ -f "$COMMON_SRC/$f" ]; then
    cp "$COMMON_SRC/$f" "$BUNDLE_COMMON/"
  fi
done

# Copy example configs
for f in config.yaml.example .env.example; do
  if [ -f "$COMMON_SRC/$f" ]; then
    cp "$COMMON_SRC/$f" "$BUNDLE_COMMON/"
  fi
done

# --- Copy Google credentials if available ---
GOOGLE_CREDS="$PMOS_ROOT/common/package/src/pm_os/data/google_client_secret.json"
if [ -f "$GOOGLE_CREDS" ]; then
  echo "Copying Google OAuth credentials..."
  cp "$GOOGLE_CREDS" "$BUNDLE_DIR/data/google_client_secret.json"
fi

# --- Generate MANIFEST.json ---
echo "Generating MANIFEST.json..."
cd "$BUNDLE_COMMON"
find . -type f | sort | while read -r file; do
  cksum=$(shasum -a 256 "$file" | awk '{print $1}')
  echo "  \"${file#./}\": \"$cksum\","
done | sed '$ s/,$//' | (echo '{'; cat; echo '}') > "$BUNDLE_COMMON/MANIFEST.json"

# --- Report size ---
BUNDLE_SIZE=$(du -sh "$BUNDLE_DIR" | awk '{print $1}')
FILE_COUNT=$(find "$BUNDLE_COMMON" -type f | wc -l | tr -d ' ')
echo ""
echo "=== Bundle Complete ==="
echo "  Total size: $BUNDLE_SIZE"
echo "  Files: $FILE_COUNT"
echo "  Manifest: $BUNDLE_COMMON/MANIFEST.json"
