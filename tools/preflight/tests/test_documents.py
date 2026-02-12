#!/usr/bin/env python3
"""
Document Processing Tests

Tests for: interview_processor, research_aggregator, synapse_builder, template_manager

Author: PM-OS Team
Version: 3.0.0
"""

import sys
from pathlib import Path
from typing import Tuple

TOOLS_DIR = Path(__file__).parent.parent.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def check_interview_processor_import() -> Tuple[bool, str]:
    """Check interview_processor can be imported."""
    try:
        from documents import interview_processor

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_research_aggregator_import() -> Tuple[bool, str]:
    """Check research_aggregator can be imported."""
    try:
        from documents import research_aggregator

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_synapse_builder_import() -> Tuple[bool, str]:
    """Check synapse_builder can be imported."""
    try:
        from documents import synapse_builder

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_synapse_builder_classes() -> Tuple[bool, str]:
    """Check SynapseBuilder class exists."""
    try:
        from documents.synapse_builder import SynapseBuilder

        return True, "Classes OK (SynapseBuilder)"
    except ImportError as e:
        return False, f"Missing classes: {e}"


def check_template_manager_import() -> Tuple[bool, str]:
    """Check template_manager can be imported."""
    try:
        from documents import template_manager

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_template_manager_classes() -> Tuple[bool, str]:
    """Check TemplateManager class exists."""
    try:
        from documents.template_manager import TemplateManager

        return True, "Classes OK (TemplateManager)"
    except ImportError as e:
        return False, f"Missing classes: {e}"


DOCUMENTS_CHECKS = {
    "interview_processor": [
        ("import", check_interview_processor_import),
    ],
    "research_aggregator": [
        ("import", check_research_aggregator_import),
    ],
    "synapse_builder": [
        ("import", check_synapse_builder_import),
        ("classes", check_synapse_builder_classes),
    ],
    "template_manager": [
        ("import", check_template_manager_import),
        ("classes", check_template_manager_classes),
    ],
}


def run_all_checks() -> dict:
    """Run all document processing checks."""
    results = {}
    for tool, checks in DOCUMENTS_CHECKS.items():
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
