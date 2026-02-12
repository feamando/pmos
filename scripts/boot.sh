#!/bin/bash
# PM-OS Boot Script (Mac/Linux)
# Sets up environment variables for PM-OS 3.0
#
# Usage: source boot.sh
#        Or add to your shell profile

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}PM-OS Boot${NC}"

# Determine script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The script is in common/scripts/, so common is parent
PM_OS_COMMON="$(dirname "$SCRIPT_DIR")"
PM_OS_ROOT="$(dirname "$PM_OS_COMMON")"
PM_OS_USER="$PM_OS_ROOT/user"

# Verify structure
if [ ! -f "$PM_OS_COMMON/.pm-os-common" ]; then
    echo -e "${RED}Error: Not a valid PM-OS common directory${NC}"
    echo "Expected .pm-os-common marker in: $PM_OS_COMMON"
    return 1 2>/dev/null || exit 1
fi

if [ ! -d "$PM_OS_USER" ]; then
    echo -e "${YELLOW}Warning: user/ directory not found${NC}"
    echo "Creating user/ directory..."
    mkdir -p "$PM_OS_USER"

    # Copy example files
    if [ -f "$PM_OS_COMMON/config.yaml.example" ]; then
        cp "$PM_OS_COMMON/config.yaml.example" "$PM_OS_USER/config.yaml"
        echo "  Created config.yaml from example"
    fi
    if [ -f "$PM_OS_COMMON/.env.example" ]; then
        cp "$PM_OS_COMMON/.env.example" "$PM_OS_USER/.env"
        echo "  Created .env from example"
    fi

    # Create user marker
    touch "$PM_OS_USER/.pm-os-user"
fi

# Export environment variables
export PM_OS_ROOT
export PM_OS_COMMON
export PM_OS_USER

# Add tools to PYTHONPATH
if [[ ":$PYTHONPATH:" != *":$PM_OS_COMMON/tools:"* ]]; then
    export PYTHONPATH="$PM_OS_COMMON/tools:$PYTHONPATH"
fi

# Create root marker if needed
if [ ! -f "$PM_OS_ROOT/.pm-os-root" ]; then
    touch "$PM_OS_ROOT/.pm-os-root"
fi

# Load .env if exists
if [ -f "$PM_OS_USER/.env" ]; then
    set -a
    source "$PM_OS_USER/.env"
    set +a
    echo -e "${GREEN}✓${NC} Loaded .env"
fi

# Display status
echo -e "${GREEN}✓${NC} PM-OS environment ready"
echo "  Root:   $PM_OS_ROOT"
echo "  Common: $PM_OS_COMMON"
echo "  User:   $PM_OS_USER"

# Check for config.yaml
if [ -f "$PM_OS_USER/config.yaml" ]; then
    echo -e "${GREEN}✓${NC} Config found"
else
    echo -e "${YELLOW}!${NC} No config.yaml - run /boot in your AI CLI to set up"
fi

# Pre-flight checks (optional, skip with --skip-preflight)
SKIP_PREFLIGHT=false
for arg in "$@"; do
    if [ "$arg" = "--skip-preflight" ] || [ "$arg" = "-s" ]; then
        SKIP_PREFLIGHT=true
    fi
done

if [ "$SKIP_PREFLIGHT" = false ]; then
    echo ""
    echo "Running pre-flight checks..."
    if python3 "$PM_OS_COMMON/tools/preflight/preflight_runner.py" --quick 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Pre-flight checks passed"
    else
        echo -e "${YELLOW}!${NC} Some pre-flight checks failed (non-blocking)"
        echo "  Run 'python3 \$PM_OS_COMMON/tools/preflight/preflight_runner.py' for details"
    fi
fi

echo ""
echo "Run '/boot' in Claude Code or Gemini CLI to start"
