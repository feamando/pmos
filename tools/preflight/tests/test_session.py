#!/usr/bin/env python3
"""
Session Management Tests

Tests for: confucius_agent, session_manager

Author: PM-OS Team
Version: 3.0.0
"""

import sys
from pathlib import Path
from typing import Tuple

TOOLS_DIR = Path(__file__).parent.parent.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def check_confucius_agent_import() -> Tuple[bool, str]:
    """Check confucius_agent can be imported."""
    try:
        from session import confucius_agent

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_confucius_agent_classes() -> Tuple[bool, str]:
    """Check ConfuciusAgent class exists."""
    try:
        from session.confucius_agent import ConfuciusAgent

        return True, "Classes OK (ConfuciusAgent)"
    except ImportError as e:
        return False, f"Missing classes: {e}"


def check_session_manager_import() -> Tuple[bool, str]:
    """Check session_manager can be imported."""
    try:
        from session import session_manager

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_session_manager_classes() -> Tuple[bool, str]:
    """Check SessionManager class exists."""
    try:
        from session.session_manager import SessionManager

        return True, "Classes OK (SessionManager)"
    except ImportError as e:
        return False, f"Missing classes: {e}"


SESSION_CHECKS = {
    "confucius_agent": [
        ("import", check_confucius_agent_import),
        ("classes", check_confucius_agent_classes),
    ],
    "session_manager": [
        ("import", check_session_manager_import),
        ("classes", check_session_manager_classes),
    ],
}


def run_all_checks() -> dict:
    """Run all session management checks."""
    results = {}
    for tool, checks in SESSION_CHECKS.items():
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
