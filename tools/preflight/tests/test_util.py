#!/usr/bin/env python3
"""
Utility Tools Tests

Tests for: batch_llm_analyzer, file_chunker, model_bridge, validate_cross_cli_sync

Author: PM-OS Team
Version: 3.0.0
"""

import sys
from pathlib import Path
from typing import Tuple

TOOLS_DIR = Path(__file__).parent.parent.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def check_batch_llm_analyzer_import() -> Tuple[bool, str]:
    """Check batch_llm_analyzer can be imported."""
    try:
        from util import batch_llm_analyzer

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_batch_llm_analyzer_classes() -> Tuple[bool, str]:
    """Check BatchLLMAnalyzer class exists."""
    try:
        from util.batch_llm_analyzer import BatchLLMAnalyzer

        return True, "Classes OK (BatchLLMAnalyzer)"
    except ImportError as e:
        return False, f"Missing classes: {e}"


def check_file_chunker_import() -> Tuple[bool, str]:
    """Check file_chunker can be imported."""
    try:
        from util import file_chunker

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_file_chunker_classes() -> Tuple[bool, str]:
    """Check FileChunker class exists."""
    try:
        from util.file_chunker import FileChunker

        return True, "Classes OK (FileChunker)"
    except ImportError as e:
        return False, f"Missing classes: {e}"


def check_model_bridge_import() -> Tuple[bool, str]:
    """Check model_bridge can be imported."""
    try:
        from util import model_bridge

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_model_bridge_classes() -> Tuple[bool, str]:
    """Check ModelBridge class exists."""
    try:
        from util.model_bridge import ModelBridge

        return True, "Classes OK (ModelBridge)"
    except ImportError as e:
        return False, f"Missing classes: {e}"


def check_validate_cross_cli_sync_import() -> Tuple[bool, str]:
    """Check validate_cross_cli_sync can be imported."""
    try:
        from util import validate_cross_cli_sync

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


UTIL_CHECKS = {
    "batch_llm_analyzer": [
        ("import", check_batch_llm_analyzer_import),
        ("classes", check_batch_llm_analyzer_classes),
    ],
    "file_chunker": [
        ("import", check_file_chunker_import),
        ("classes", check_file_chunker_classes),
    ],
    "model_bridge": [
        ("import", check_model_bridge_import),
        ("classes", check_model_bridge_classes),
    ],
    "validate_cross_cli_sync": [
        ("import", check_validate_cross_cli_sync_import),
    ],
}


def run_all_checks() -> dict:
    """Run all utility checks."""
    results = {}
    for tool, checks in UTIL_CHECKS.items():
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
