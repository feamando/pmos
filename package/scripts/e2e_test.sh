#!/bin/bash
# PM-OS End-to-End Installation Test
#
# Validates the complete flow:
#   pip install pm-os → init --quick → doctor → update → verify
#
# Usage:
#   ./scripts/e2e_test.sh              # Run locally
#   ./scripts/e2e_test.sh --template   # Also test template install
#
# Requirements:
#   - Internet access (downloads common/ from GitHub)
#   - git configured (for --quick auto-detection)
#   - Python 3.10+

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
TESTDIR=""

pass() {
    echo -e "${GREEN}✓${NC} $1"
    PASS=$((PASS + 1))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    FAIL=$((FAIL + 1))
}

check() {
    if [ "$1" = "true" ]; then
        pass "$2"
    else
        fail "$2"
    fi
}

cleanup() {
    if [ -n "$TESTDIR" ] && [ -d "$TESTDIR" ]; then
        rm -rf "$TESTDIR"
    fi
}

trap cleanup EXIT

echo "=============================="
echo "PM-OS E2E Installation Test"
echo "=============================="
echo ""

# Create test directory
TESTDIR=$(mktemp -d /tmp/pmos-e2e-XXXXXX)
INSTALL_PATH="$TESTDIR/pm-os"
echo "Test directory: $TESTDIR"
echo ""

# --- Test 1: pm-os is installed ---
echo "--- Test: CLI Installation ---"
check "$(command -v pm-os >/dev/null 2>&1 && echo true || echo false)" "pm-os CLI available"
check "$(pm-os --version 2>&1 | grep -q '3\.' && echo true || echo false)" "pm-os version is 3.x"

# --- Test 2: Quick init ---
echo ""
echo "--- Test: Quick Init ---"
pm-os init --quick --path "$INSTALL_PATH" 2>&1 | tail -5

# Directory structure
check "$(test -d "$INSTALL_PATH/brain" && echo true || echo false)" "brain/ directory exists"
check "$(test -d "$INSTALL_PATH/brain/Entities/People" && echo true || echo false)" "brain/Entities/People/ exists"
check "$(test -d "$INSTALL_PATH/brain/Glossary" && echo true || echo false)" "brain/Glossary/ exists"
check "$(test -d "$INSTALL_PATH/brain/Index" && echo true || echo false)" "brain/Index/ exists"
check "$(test -d "$INSTALL_PATH/brain/Caches" && echo true || echo false)" "brain/Caches/ exists"
check "$(test -d "$INSTALL_PATH/brain/Confucius" && echo true || echo false)" "brain/Confucius/ exists"
check "$(test -d "$INSTALL_PATH/sessions/active" && echo true || echo false)" "sessions/active/ exists"
check "$(test -d "$INSTALL_PATH/personal/context/raw" && echo true || echo false)" "personal/context/raw/ exists"

# Config files
check "$(test -f "$INSTALL_PATH/.env" && echo true || echo false)" ".env exists"
check "$(test -f "$INSTALL_PATH/.config/config.yaml" && echo true || echo false)" "config.yaml exists"
check "$(test -f "$INSTALL_PATH/USER.md" && echo true || echo false)" "USER.md exists"
check "$(test -f "$INSTALL_PATH/.gitignore" && echo true || echo false)" ".gitignore exists"

# Brain files
check "$(test -f "$INSTALL_PATH/brain/BRAIN.md" && echo true || echo false)" "BRAIN.md exists"
check "$(test -f "$INSTALL_PATH/brain/hot_topics.json" && echo true || echo false)" "hot_topics.json exists"
check "$(test -f "$INSTALL_PATH/brain/Glossary/Glossary.md" && echo true || echo false)" "Glossary.md exists"
check "$(test -f "$INSTALL_PATH/brain/Index/Index.md" && echo true || echo false)" "Index.md exists"

# User entity
ENTITY_COUNT=$(find "$INSTALL_PATH/brain/Entities/People" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
check "$(test "$ENTITY_COUNT" -ge 1 && echo true || echo false)" "User entity created ($ENTITY_COUNT entities)"

# --- Test 3: Common download ---
echo ""
echo "--- Test: Common Download ---"
check "$(test -d "$INSTALL_PATH/common" && echo true || echo false)" "common/ directory exists"
check "$(test -d "$INSTALL_PATH/common/tools" && echo true || echo false)" "common/tools/ exists"
check "$(test -d "$INSTALL_PATH/common/.claude/commands" && echo true || echo false)" "common/.claude/commands/ exists"
check "$(test -f "$INSTALL_PATH/common/AGENT.md" && echo true || echo false)" "common/AGENT.md exists"
check "$(test -d "$INSTALL_PATH/common/scripts" && echo true || echo false)" "common/scripts/ exists"

CMD_COUNT=$(find "$INSTALL_PATH/common/.claude/commands" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
check "$(test "$CMD_COUNT" -ge 60 && echo true || echo false)" "At least 60 slash commands ($CMD_COUNT found)"

# Version pinned
check "$(test -f "$INSTALL_PATH/.pm-os-version" && echo true || echo false)" ".pm-os-version exists"

# --- Test 4: Claude Code setup ---
echo ""
echo "--- Test: Claude Code Setup ---"
check "$(test -d "$INSTALL_PATH/.claude" && echo true || echo false)" ".claude/ directory exists"

# Commands symlink
check "$(test -e "$INSTALL_PATH/.claude/commands" && echo true || echo false)" ".claude/commands exists"
LINKED_CMDS=$(find -L "$INSTALL_PATH/.claude/commands" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
check "$(test "$LINKED_CMDS" -ge 60 && echo true || echo false)" "Commands linked ($LINKED_CMDS commands)"

# Settings
check "$(test -f "$INSTALL_PATH/.claude/settings.local.json" && echo true || echo false)" "settings.local.json exists"
check "$(python3 -c "import json; d=json.load(open('$INSTALL_PATH/.claude/settings.local.json')); assert 'permissions' in d; print('true')" 2>/dev/null || echo false)" "settings.local.json has permissions"

# Env
check "$(test -f "$INSTALL_PATH/.claude/env" && echo true || echo false)" ".claude/env exists"
check "$(grep -q 'PM_OS_ROOT=' "$INSTALL_PATH/.claude/env" && echo true || echo false)" ".claude/env has PM_OS_ROOT"
check "$(grep -q 'PM_OS_COMMON=' "$INSTALL_PATH/.claude/env" && echo true || echo false)" ".claude/env has PM_OS_COMMON"
check "$(grep -q 'PYTHONPATH=' "$INSTALL_PATH/.claude/env" && echo true || echo false)" ".claude/env has PYTHONPATH"

# AGENT.md
check "$(test -e "$INSTALL_PATH/AGENT.md" && echo true || echo false)" "AGENT.md accessible"

# --- Test 5: Update check ---
echo ""
echo "--- Test: Update Command ---"
UPDATE_OUT=$(pm-os update --check --path "$INSTALL_PATH" 2>&1)
check "$(echo "$UPDATE_OUT" | grep -q 'CLI version' && echo true || echo false)" "update --check shows CLI version"
check "$(echo "$UPDATE_OUT" | grep -q 'Common version' && echo true || echo false)" "update --check shows common version"

# --- Test 6: Update with version mismatch ---
echo "v0.0.1" > "$INSTALL_PATH/.pm-os-version"
UPDATE_OUT2=$(pm-os update --common-only --path "$INSTALL_PATH" 2>&1)
check "$(echo "$UPDATE_OUT2" | grep -q 'updated' && echo true || echo false)" "update --common-only downloads new common/"
check "$(test -f "$INSTALL_PATH/USER.md" && echo true || echo false)" "USER.md preserved after update"
check "$(test -d "$INSTALL_PATH/brain/Entities" && echo true || echo false)" "brain/ preserved after update"

# --- Test 7: Template install (if requested) ---
if [ "${1:-}" = "--template" ]; then
    echo ""
    echo "--- Test: Template Install ---"
    TEMPLATE_DIR="$TESTDIR/template-test"
    cat > "$TESTDIR/template.yaml" <<TMPL
user:
  name: Template Test
  email: template@test.local
  role: Engineering Manager
llm:
  provider: anthropic
  model: claude-sonnet-4-20250514
integrations: {}
TMPL

    pm-os init --template "$TESTDIR/template.yaml" --path "$TEMPLATE_DIR" 2>&1 | tail -3
    check "$(test -d "$TEMPLATE_DIR/brain" && echo true || echo false)" "Template: brain/ exists"
    check "$(test -d "$TEMPLATE_DIR/common/tools" && echo true || echo false)" "Template: common/ downloaded"
    check "$(test -e "$TEMPLATE_DIR/.claude/commands" && echo true || echo false)" "Template: Claude Code configured"
    check "$(test -f "$TEMPLATE_DIR/brain/BRAIN.md" && echo true || echo false)" "Template: BRAIN.md created"
fi

# --- Summary ---
echo ""
echo "=============================="
TOTAL=$((PASS + FAIL))
echo -e "Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC} (${TOTAL} total)"
echo "=============================="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi

echo ""
echo "E2E PASS"
