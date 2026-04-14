#!/usr/bin/env bash
# PM-OS v5.0 Smoke Test — validates installation integrity
# Usage: cd ~/pm-os && bash v5/migration/smoke_test_v5.sh
# Idempotent: never modifies anything, safe to run repeatedly.

set -uo pipefail

PM_OS_ROOT="${PM_OS_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
PASS=0
FAIL=0
WARN=0

pass() { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
fail() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }
warn() { echo "  [WARN] $1"; WARN=$((WARN + 1)); }

echo "============================================"
echo "PM-OS v5.0 Smoke Test"
echo "Root: $PM_OS_ROOT"
echo "============================================"

# 1. v5/ workspace with 7 plugin directories
echo ""
echo "--- Check 1: v5 plugin directories ---"
PLUGIN_COUNT=$(find "$PM_OS_ROOT/plugins" -maxdepth 1 -type d -name "pm-os-*" 2>/dev/null | wc -l | tr -d ' ')
if [ "$PLUGIN_COUNT" -ge 7 ]; then
    pass "plugins/ has $PLUGIN_COUNT pm-os-* directories"
else
    fail "plugins/ has $PLUGIN_COUNT pm-os-* directories (expected >= 7)"
fi

# 2. Each plugin has .claude-plugin/plugin.json
echo ""
echo "--- Check 2: plugin manifests ---"
MANIFEST_OK=true
for dir in "$PM_OS_ROOT"/plugins/pm-os-*/; do
    name=$(basename "$dir")
    if [ -f "$dir/.claude-plugin/plugin.json" ]; then
        pass "$name has plugin.json"
    else
        fail "$name missing .claude-plugin/plugin.json"
        MANIFEST_OK=false
    fi
done

# 3. user/config.yaml exists, valid YAML, has version field
echo ""
echo "--- Check 3: config.yaml ---"
CONFIG="$PM_OS_ROOT/user/config.yaml"
if [ -f "$CONFIG" ]; then
    pass "user/config.yaml exists"
    if python3 -c "import yaml; yaml.safe_load(open('$CONFIG'))" 2>/dev/null; then
        pass "config.yaml is valid YAML"
        VERSION=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG')).get('version',''))" 2>/dev/null)
        if [ -n "$VERSION" ]; then
            pass "config.yaml version: $VERSION"
        else
            fail "config.yaml missing version field"
        fi
    else
        fail "config.yaml is not valid YAML"
    fi
else
    fail "user/config.yaml not found"
fi

# 4. user/brain/ exists with .md files
echo ""
echo "--- Check 4: brain directory ---"
BRAIN_DIR="$PM_OS_ROOT/user/brain"
if [ -d "$BRAIN_DIR" ]; then
    MD_COUNT=$(find "$BRAIN_DIR" -name "*.md" -type f | wc -l | tr -d ' ')
    if [ "$MD_COUNT" -gt 0 ]; then
        pass "user/brain/ has $MD_COUNT .md files"
    else
        warn "user/brain/ exists but has no .md files"
    fi
else
    fail "user/brain/ directory not found"
fi

# 5. user/.env exists
echo ""
echo "--- Check 5: .env file ---"
if [ -f "$PM_OS_ROOT/user/.env" ]; then
    pass "user/.env exists"
else
    warn "user/.env not found (API tokens may be missing)"
fi

# 6. .claude/commands/ has base.md (if plugins installed)
echo ""
echo "--- Check 6: plugin commands registered ---"
CMDS_DIR="$PM_OS_ROOT/.claude/commands"
if [ -d "$CMDS_DIR" ]; then
    if [ -f "$CMDS_DIR/base.md" ]; then
        pass "base.md registered in .claude/commands/"
    else
        warn "base.md not in .claude/commands/ (plugins may not be installed yet)"
    fi
else
    warn ".claude/commands/ not found (plugins not installed yet)"
fi

# 7. Python 3.9+ available
echo ""
echo "--- Check 7: Python version ---"
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
    PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 9 ]; then
        pass "Python $PY_VERSION (>= 3.9)"
    else
        fail "Python $PY_VERSION (need >= 3.9)"
    fi
else
    fail "python3 not found"
fi

# 8. Required Python modules importable
echo ""
echo "--- Check 8: Python modules ---"
for mod in yaml pathlib json; do
    if python3 -c "import $mod" 2>/dev/null; then
        pass "Python module: $mod"
    else
        fail "Python module not importable: $mod"
    fi
done

# 9. No dead symlinks in user/
echo ""
echo "--- Check 9: dead symlinks ---"
USER_DIR="$PM_OS_ROOT/user"
if [ -d "$USER_DIR" ]; then
    DEAD_LINKS=$(find "$USER_DIR" -type l ! -exec test -e {} \; -print 2>/dev/null | wc -l | tr -d ' ')
    if [ "$DEAD_LINKS" -eq 0 ]; then
        pass "No dead symlinks in user/"
    else
        fail "$DEAD_LINKS dead symlinks in user/"
    fi
else
    warn "user/ directory not found"
fi

# 10. No hardcoded values in plugins/ commands and skills
echo ""
echo "--- Check 10: hardcoded values audit ---"
HARDCODED=$(grep -rni "hellofresh\|helloai\|HelloAI\|@hellofresh\|Agrandir\|New Ventures\|Market Innovation" \
    "$PM_OS_ROOT/plugins/"*/commands/ "$PM_OS_ROOT/plugins/"*/skills/ \
    2>/dev/null | wc -l | tr -d ' ')
if [ "$HARDCODED" -eq 0 ]; then
    pass "No hardcoded values in plugin commands/skills"
else
    fail "$HARDCODED hardcoded values found in plugin commands/skills"
fi

# 11. All plugin.json manifests are valid JSON
echo ""
echo "--- Check 11: JSON manifest validity ---"
JSON_OK=true
for manifest in "$PM_OS_ROOT"/plugins/pm-os-*/.claude-plugin/plugin.json; do
    name=$(basename "$(dirname "$(dirname "$manifest")")")
    if python3 -c "import json; json.load(open('$manifest'))" 2>/dev/null; then
        pass "$name plugin.json is valid JSON"
    else
        fail "$name plugin.json is invalid JSON"
        JSON_OK=false
    fi
done

# 12. Plugin dependency graph is acyclic (all deps point to base or are empty)
echo ""
echo "--- Check 12: dependency graph ---"
DEP_OK=true
for manifest in "$PM_OS_ROOT"/plugins/pm-os-*/.claude-plugin/plugin.json; do
    name=$(python3 -c "import json; print(json.load(open('$manifest'))['name'])" 2>/dev/null)
    deps=$(python3 -c "import json; print(','.join(json.load(open('$manifest')).get('dependencies',[])))" 2>/dev/null)
    if [ -z "$deps" ]; then
        pass "$name: no dependencies (root)"
    elif [ "$deps" = "pm-os-base" ]; then
        pass "$name: depends on pm-os-base only"
    else
        # Check for circular or non-base deps
        warn "$name: dependencies = $deps (verify no cycles)"
    fi
done

# Summary
echo ""
echo "============================================"
echo "Results: $PASS passed, $FAIL failed, $WARN warnings"
echo "============================================"

if [ "$FAIL" -gt 0 ]; then
    exit 1
else
    exit 0
fi
