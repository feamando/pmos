#!/usr/bin/env python3
"""
Pre-Flight Test Template

Use this template when creating tests for new PM-OS tools.
Copy this file and modify for your tool's specific requirements.

Pattern:
1. check_<tool>_import() - Can the module be imported?
2. check_<tool>_classes() - Do expected classes exist?
3. check_<tool>_functions() - Do expected functions exist?
4. check_<tool>_config() - Can the tool load config?
5. check_<tool>_connectivity() - Can the tool reach external APIs?

Author: PM-OS Team
Version: 3.0.0
"""

import os
from typing import Tuple


def check_tool_import() -> Tuple[bool, str]:
    """
    Check if the tool module can be imported.

    This is the minimum test every tool must pass.

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Replace with actual import
        # from category import tool_name
        import importlib

        module = importlib.import_module("category.tool_name")
        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"
    except Exception as e:
        return False, f"Import error: {e}"


def check_tool_classes() -> Tuple[bool, str]:
    """
    Check if expected classes exist in the module.

    Add all public classes your tool exports.

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        from category import tool_name

        required_classes = [
            "ClassName1",
            "ClassName2",
        ]

        missing = [c for c in required_classes if not hasattr(tool_name, c)]

        if missing:
            return False, f"Missing classes: {', '.join(missing)}"
        return True, f"Classes OK ({len(required_classes)})"
    except Exception as e:
        return False, f"Class check failed: {e}"


def check_tool_functions() -> Tuple[bool, str]:
    """
    Check if expected functions exist in the module.

    Add all public functions your tool exports.

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        from category import tool_name

        required_functions = [
            "function_name1",
            "function_name2",
        ]

        missing = [f for f in required_functions if not hasattr(tool_name, f)]

        if missing:
            return False, f"Missing functions: {', '.join(missing)}"
        return True, f"Functions OK ({len(required_functions)})"
    except Exception as e:
        return False, f"Function check failed: {e}"


def check_tool_config() -> Tuple[bool, str]:
    """
    Check if the tool can load its configuration.

    Only include this if your tool requires config.yaml.

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        from config_loader import load_config

        config = load_config()

        # Check for tool-specific config keys
        required_keys = [
            "integrations.tool_name.enabled",
        ]

        # Validate keys exist (this is a placeholder pattern)
        # Actual implementation would traverse the config dict

        return True, "Config OK"
    except Exception as e:
        return False, f"Config check failed: {e}"


def check_tool_env_vars() -> Tuple[bool, str]:
    """
    Check if required environment variables are set.

    Only include this if your tool requires specific env vars.

    Returns:
        Tuple of (success: bool, message: str)
    """
    required_env = [
        "TOOL_API_KEY",
        "TOOL_SECRET",
    ]

    missing = [k for k in required_env if not os.environ.get(k)]

    if missing:
        return False, f"Missing env vars: {', '.join(missing)}"
    return True, f"Env vars OK ({len(required_env)})"


def check_tool_connectivity() -> Tuple[bool, str]:
    """
    Check if the tool can connect to its external service.

    This is optional and should be skippable.
    Only include for tools with external API dependencies.

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Example: test API connection
        # from tool import create_client
        # client = create_client()
        # client.ping()  # or similar health check

        return True, "Connectivity OK"
    except Exception as e:
        return False, f"Connectivity failed: {e}"


# =============================================================================
# Test Registration
# =============================================================================

# Export all check functions for this tool
CHECKS = [
    ("import", check_tool_import),
    ("classes", check_tool_classes),
    ("functions", check_tool_functions),
    ("config", check_tool_config),
    ("env_vars", check_tool_env_vars),
    ("connectivity", check_tool_connectivity),
]


def run_all_checks() -> dict:
    """
    Run all checks and return results.

    Returns:
        Dict with check names as keys and (passed, message) as values
    """
    results = {}
    for name, check_fn in CHECKS:
        try:
            passed, msg = check_fn()
            results[name] = (passed, msg)
        except Exception as e:
            results[name] = (False, f"Check error: {e}")
    return results


# =============================================================================
# Registry Entry Template
# =============================================================================

REGISTRY_ENTRY = """
# Add this to preflight/registry.py in the appropriate category:

"tool_name": {
    "path": "category/tool_name.py",
    "module": "category.tool_name",
    "classes": ["ClassName1", "ClassName2"],
    "functions": ["function_name1", "function_name2"],
    "requires_config": True,  # or False
    "env_keys": ["TOOL_API_KEY"],  # optional
    "optional_connectivity": True,  # optional
    "description": "Brief description of what this tool does",
},
"""


if __name__ == "__main__":
    # Quick test of template
    print("Pre-Flight Test Template")
    print("=" * 40)
    print("\nThis is a template file. Copy and modify for your tool.")
    print("\nRegistry entry template:")
    print(REGISTRY_ENTRY)
