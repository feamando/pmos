#!/bin/bash
# PM-OS First-Time Setup Script
# Creates the pm-os directory structure and initializes configuration
#
# Usage: ./setup.sh [target-directory]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     PM-OS 3.0 First-Time Setup       ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════╝${NC}"
echo ""

# Determine target directory
if [ -n "$1" ]; then
    TARGET_DIR="$1"
else
    TARGET_DIR="$HOME/pm-os"
fi

# Determine script location (this is in common/scripts)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON_DIR="$(dirname "$SCRIPT_DIR")"

echo "This script will set up PM-OS in: $TARGET_DIR"
echo ""
read -p "Continue? [Y/n] " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo "Setup cancelled."
    exit 0
fi

# Create directory structure
echo -e "${GREEN}Creating directory structure...${NC}"
mkdir -p "$TARGET_DIR"

# Check if common already exists
if [ -d "$TARGET_DIR/common" ]; then
    echo -e "${YELLOW}common/ directory already exists${NC}"
    read -p "Replace with current version? [y/N] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$TARGET_DIR/common"
    else
        echo "Keeping existing common/"
    fi
fi

# Copy or link common
if [ ! -d "$TARGET_DIR/common" ]; then
    echo "Copying common/ (LOGIC)..."
    cp -r "$COMMON_DIR" "$TARGET_DIR/common"
    echo -e "${GREEN}✓${NC} common/ created"
fi

# Create user directory
USER_DIR="$TARGET_DIR/user"
if [ ! -d "$USER_DIR" ]; then
    echo "Creating user/ (CONTENT)..."
    mkdir -p "$USER_DIR"
    mkdir -p "$USER_DIR/brain/entities"
    mkdir -p "$USER_DIR/brain/projects"
    mkdir -p "$USER_DIR/brain/experiments"
    mkdir -p "$USER_DIR/context"
    mkdir -p "$USER_DIR/sessions"
    mkdir -p "$USER_DIR/planning/meeting-prep"
    mkdir -p "$USER_DIR/.secrets"

    # Copy templates
    cp "$TARGET_DIR/common/config.yaml.example" "$USER_DIR/config.yaml"
    cp "$TARGET_DIR/common/.env.example" "$USER_DIR/.env"
    cp "$TARGET_DIR/common/rules/USER_TEMPLATE.md" "$USER_DIR/USER.md"

    # Create markers
    touch "$USER_DIR/.pm-os-user"

    echo -e "${GREEN}✓${NC} user/ created"
else
    echo -e "${YELLOW}user/ directory already exists${NC}"
fi

# Create root marker
touch "$TARGET_DIR/.pm-os-root"

# Create snapshots directory for migrations
mkdir -p "$TARGET_DIR/snapshots"

# Set permissions
chmod +x "$TARGET_DIR/common/scripts/"*.sh 2>/dev/null || true

echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Setup Complete!              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
echo "Directory structure:"
echo "  $TARGET_DIR/"
echo "  ├── common/     (LOGIC - PM-OS code)"
echo "  ├── user/       (CONTENT - your data)"
echo "  └── snapshots/  (migration backups)"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Edit user/config.yaml with your details"
echo "2. Add your API tokens to user/.env"
echo "3. Boot PM-OS:"
echo ""
echo "   cd $TARGET_DIR/user"
echo "   source ../common/scripts/boot.sh"
echo ""
echo "4. In Claude Code or Gemini CLI, run: /boot"
echo ""

# Offer to add to shell profile
echo -e "${BLUE}Optional: Add boot command to shell profile?${NC}"
read -p "Add 'pmos' alias to your shell? [y/N] " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    BOOT_SCRIPT="$TARGET_DIR/common/scripts/boot.sh"
    ALIAS_LINE="alias pmos='source $BOOT_SCRIPT'"

    # Detect shell
    if [ -n "$ZSH_VERSION" ]; then
        PROFILE="$HOME/.zshrc"
    elif [ -n "$BASH_VERSION" ]; then
        if [ -f "$HOME/.bash_profile" ]; then
            PROFILE="$HOME/.bash_profile"
        else
            PROFILE="$HOME/.bashrc"
        fi
    else
        PROFILE="$HOME/.profile"
    fi

    if ! grep -q "pmos" "$PROFILE" 2>/dev/null; then
        echo "" >> "$PROFILE"
        echo "# PM-OS" >> "$PROFILE"
        echo "$ALIAS_LINE" >> "$PROFILE"
        echo -e "${GREEN}✓${NC} Added 'pmos' alias to $PROFILE"
        echo "  Run 'source $PROFILE' or restart your terminal"
    else
        echo "Alias already exists in $PROFILE"
    fi
fi

echo ""
echo -e "${GREEN}PM-OS is ready!${NC}"
