#!/usr/bin/env python3
"""
Brain Management Tests

Tests for: brain_loader, brain_updater, unified_brain_writer

Author: PM-OS Team
Version: 3.0.0
"""

import sys
from pathlib import Path
from typing import Tuple

TOOLS_DIR = Path(__file__).parent.parent.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def check_brain_loader_import() -> Tuple[bool, str]:
    """Check brain_loader can be imported."""
    try:
        from brain import brain_loader

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_brain_loader_classes() -> Tuple[bool, str]:
    """Check BrainLoader class exists."""
    try:
        from brain.brain_loader import BrainLoader

        return True, "Classes OK (BrainLoader)"
    except ImportError as e:
        return False, f"Missing classes: {e}"


def check_brain_updater_import() -> Tuple[bool, str]:
    """Check brain_updater can be imported."""
    try:
        from brain import brain_updater

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_unified_brain_writer_import() -> Tuple[bool, str]:
    """Check unified_brain_writer can be imported."""
    try:
        from brain import unified_brain_writer

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_unified_brain_writer_classes() -> Tuple[bool, str]:
    """Check UnifiedBrainWriter class exists."""
    try:
        from brain.unified_brain_writer import UnifiedBrainWriter

        return True, "Classes OK (UnifiedBrainWriter)"
    except ImportError as e:
        return False, f"Missing classes: {e}"


BRAIN_CHECKS = {
    "brain_loader": [
        ("import", check_brain_loader_import),
        ("classes", check_brain_loader_classes),
    ],
    "brain_updater": [
        ("import", check_brain_updater_import),
    ],
    "unified_brain_writer": [
        ("import", check_unified_brain_writer_import),
        ("classes", check_unified_brain_writer_classes),
    ],
}


def run_all_checks() -> dict:
    """Run all brain management checks."""
    results = {}
    for tool, checks in BRAIN_CHECKS.items():
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
