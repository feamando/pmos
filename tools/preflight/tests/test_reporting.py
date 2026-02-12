#!/usr/bin/env python3
"""
Reporting Tools Tests

Tests for: sprint_report_generator, tribe_quarterly_update

Author: PM-OS Team
Version: 3.0.0
"""

import sys
from pathlib import Path
from typing import Tuple

TOOLS_DIR = Path(__file__).parent.parent.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def check_sprint_report_generator_import() -> Tuple[bool, str]:
    """Check sprint_report_generator can be imported."""
    try:
        from reporting import sprint_report_generator

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_sprint_report_generator_classes() -> Tuple[bool, str]:
    """Check SprintReportGenerator class exists."""
    try:
        from reporting.sprint_report_generator import SprintReportGenerator

        return True, "Classes OK (SprintReportGenerator)"
    except ImportError as e:
        return False, f"Missing classes: {e}"


def check_tribe_quarterly_update_import() -> Tuple[bool, str]:
    """Check tribe_quarterly_update can be imported."""
    try:
        from reporting import tribe_quarterly_update

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_tribe_quarterly_update_classes() -> Tuple[bool, str]:
    """Check TribeQuarterlyUpdate class exists."""
    try:
        from reporting.tribe_quarterly_update import TribeQuarterlyUpdate

        return True, "Classes OK (TribeQuarterlyUpdate)"
    except ImportError as e:
        return False, f"Missing classes: {e}"


REPORTING_CHECKS = {
    "sprint_report_generator": [
        ("import", check_sprint_report_generator_import),
        ("classes", check_sprint_report_generator_classes),
    ],
    "tribe_quarterly_update": [
        ("import", check_tribe_quarterly_update_import),
        ("classes", check_tribe_quarterly_update_classes),
    ],
}


def run_all_checks() -> dict:
    """Run all reporting checks."""
    results = {}
    for tool, checks in REPORTING_CHECKS.items():
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
