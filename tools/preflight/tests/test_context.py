#!/usr/bin/env python3
"""
Daily Context Tests

Tests for: daily_context_updater

Author: PM-OS Team
Version: 3.0.0
"""

import sys
from pathlib import Path
from typing import Tuple

TOOLS_DIR = Path(__file__).parent.parent.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def check_daily_context_updater_import() -> Tuple[bool, str]:
    """Check daily_context_updater can be imported."""
    try:
        from daily_context import daily_context_updater

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_daily_context_updater_classes() -> Tuple[bool, str]:
    """Check DailyContextUpdater class exists."""
    try:
        from daily_context.daily_context_updater import DailyContextUpdater

        return True, "Classes OK (DailyContextUpdater)"
    except ImportError as e:
        return False, f"Missing classes: {e}"


CONTEXT_CHECKS = {
    "daily_context_updater": [
        ("import", check_daily_context_updater_import),
        ("classes", check_daily_context_updater_classes),
    ],
}


def run_all_checks() -> dict:
    """Run all daily context checks."""
    results = {}
    for tool, checks in CONTEXT_CHECKS.items():
        results[tool] = {}
        for name, check_fn in checks:
            try:
                passed, msg = check_fn()
                results[tool][name] = (passed, msg)
            except Exception as e:
                results[tool][name] = (False, f"Check error: {e}")
    return results


if __name__ == "__main__":
    results = run_all_checks()
    for tool, checks in results.items():
        print(f"\n{tool}:")
        for name, (passed, msg) in checks.items():
            icon = "+" if passed else "X"
            print(f"  {icon} {name}: {msg}")
