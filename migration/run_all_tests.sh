#!/usr/bin/env bash
# PM-OS v5.0 — Unified Test Runner
# Usage: bash v5/migration/run_all_tests.sh [--quick]
# --quick skips Connector App tests (~30s faster)

set -uo pipefail

PM_OS_ROOT="${PM_OS_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
FAILURES=0
SUITES=0

run_suite() {
    local name="$1"
    shift
    SUITES=$((SUITES + 1))
    echo ""
    echo ">>> Suite $SUITES: $name"
    echo "-------------------------------------------"
    if "$@"; then
        echo "--- PASSED: $name"
    else
        echo "--- FAILED: $name"
        FAILURES=$((FAILURES + 1))
    fi
}

echo "=========================================="
echo "PM-OS v5.0 — Full Test Suite"
echo "Root: $PM_OS_ROOT"
echo "=========================================="

# 1. Smoke test (33 checks)
run_suite "Smoke test (installation integrity)" \
    bash "$PM_OS_ROOT/v5/migration/smoke_test_v5.sh"

# 2. Migration unit tests (10 pytest)
run_suite "Migration unit tests (pytest)" \
    python3 -m pytest "$PM_OS_ROOT/v5/migration/test_migration.py" -v

# 3. Daily Workflow plugin tests
DW_TESTS="$PM_OS_ROOT/v5/plugins/pm-os-daily-workflow/tests"
if [ -d "$DW_TESTS" ] && ls "$DW_TESTS"/test_*.py &>/dev/null; then
    run_suite "Daily Workflow plugin tests" \
        python3 -m pytest "$DW_TESTS" -v
else
    echo ""
    echo ">>> SKIPPED: Daily Workflow plugin tests (no test files)"
fi

# 4. Connector App tests (426 vitest)
if [ "${1:-}" != "--quick" ]; then
    run_suite "Connector App (vitest, 426 tests)" \
        sh -c "cd '$PM_OS_ROOT/apps/helloai-connector' && npm run test"
else
    echo ""
    echo ">>> SKIPPED: Connector App tests (--quick mode)"
fi

# Summary
echo ""
echo "=========================================="
if [ "$FAILURES" -eq 0 ]; then
    echo "ALL $SUITES SUITES PASSED"
else
    echo "$FAILURES of $SUITES SUITES FAILED"
fi
echo "=========================================="
exit "$FAILURES"
