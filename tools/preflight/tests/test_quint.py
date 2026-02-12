#!/usr/bin/env python3
"""
Quint/FPF Tests

Tests for: evidence_decay_monitor, gemini_quint_bridge, orthogonal_challenge, quint_brain_sync

Author: PM-OS Team
Version: 3.0.0
"""

import sys
from pathlib import Path
from typing import Tuple

TOOLS_DIR = Path(__file__).parent.parent.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def check_evidence_decay_monitor_import() -> Tuple[bool, str]:
    """Check evidence_decay_monitor can be imported."""
    try:
        from quint import evidence_decay_monitor

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_evidence_decay_monitor_classes() -> Tuple[bool, str]:
    """Check EvidenceDecayMonitor class exists."""
    try:
        from quint.evidence_decay_monitor import EvidenceDecayMonitor

        return True, "Classes OK (EvidenceDecayMonitor)"
    except ImportError as e:
        return False, f"Missing classes: {e}"


def check_gemini_quint_bridge_import() -> Tuple[bool, str]:
    """Check gemini_quint_bridge can be imported."""
    try:
        from quint import gemini_quint_bridge

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_gemini_quint_bridge_classes() -> Tuple[bool, str]:
    """Check GeminiQuintBridge class exists."""
    try:
        from quint.gemini_quint_bridge import GeminiQuintBridge

        return True, "Classes OK (GeminiQuintBridge)"
    except ImportError as e:
        return False, f"Missing classes: {e}"


def check_orthogonal_challenge_import() -> Tuple[bool, str]:
    """Check orthogonal_challenge can be imported."""
    try:
        from quint import orthogonal_challenge

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_orthogonal_challenge_classes() -> Tuple[bool, str]:
    """Check OrthogonalChallenge class exists."""
    try:
        from quint.orthogonal_challenge import OrthogonalChallenge

        return True, "Classes OK (OrthogonalChallenge)"
    except ImportError as e:
        return False, f"Missing classes: {e}"


def check_quint_brain_sync_import() -> Tuple[bool, str]:
    """Check quint_brain_sync can be imported."""
    try:
        from quint import quint_brain_sync

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_quint_brain_sync_classes() -> Tuple[bool, str]:
    """Check QuintBrainSync class exists."""
    try:
        from quint.quint_brain_sync import QuintBrainSync

        return True, "Classes OK (QuintBrainSync)"
    except ImportError as e:
        return False, f"Missing classes: {e}"


QUINT_CHECKS = {
    "evidence_decay_monitor": [
        ("import", check_evidence_decay_monitor_import),
        ("classes", check_evidence_decay_monitor_classes),
    ],
    "gemini_quint_bridge": [
        ("import", check_gemini_quint_bridge_import),
        ("classes", check_gemini_quint_bridge_classes),
    ],
    "orthogonal_challenge": [
        ("import", check_orthogonal_challenge_import),
        ("classes", check_orthogonal_challenge_classes),
    ],
    "quint_brain_sync": [
        ("import", check_quint_brain_sync_import),
        ("classes", check_quint_brain_sync_classes),
    ],
}


def run_all_checks() -> dict:
    """Run all Quint/FPF checks."""
    results = {}
    for tool, checks in QUINT_CHECKS.items():
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
