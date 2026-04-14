#!/usr/bin/env python3
"""
PM-OS v5.0 Pre-Flight Check Runner

Runs verification tests for all installed plugin tools before boot.
Plugin-extensible: each plugin contributes its own checks via preflight-checks.yaml.

Usage:
    python3 preflight_runner.py                    # Run all checks
    python3 preflight_runner.py --category core    # Run specific category
    python3 preflight_runner.py --json             # JSON output
    python3 preflight_runner.py --quick            # Import tests only
    python3 preflight_runner.py --list             # Print tool inventory

Version: 5.0.0
"""

import argparse
import importlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add plugin tools directory to path
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
TOOLS_DIR = PLUGIN_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def _bootstrap_environment():
    """Bootstrap PM-OS environment if not already configured."""
    if os.environ.get("PM_OS_ROOT"):
        return

    # Walk up from plugin root to find pm-os root
    current = PLUGIN_ROOT
    for _ in range(10):
        user_dir = current / "user"
        if user_dir.exists():
            os.environ["PM_OS_ROOT"] = str(current)
            os.environ["PM_OS_USER"] = str(user_dir)
            break
        current = current.parent

    # Load .env if exists
    user_dir = os.environ.get("PM_OS_USER", "")
    if user_dir:
        env_file = Path(user_dir) / ".env"
        if env_file.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_file)
            except ImportError:
                with open(env_file) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, _, value = line.partition("=")
                            value = value.strip().strip('"').strip("'")
                            os.environ.setdefault(key.strip(), value)


_bootstrap_environment()

from preflight.registry import get_categories, get_registry, get_tool_count, get_tools_by_category
from preflight.result import CategoryResult, PreflightResult, ToolResult


class PreflightRunner:
    """Runs pre-flight verification checks for PM-OS tools."""

    def __init__(
        self,
        verbose: bool = False,
        quick: bool = False,
        skip_connectivity: bool = True,
        categories: Optional[List[str]] = None,
    ):
        self.verbose = verbose
        self.quick = quick
        self.skip_connectivity = skip_connectivity
        self.categories = categories or get_categories()

    def run(self) -> PreflightResult:
        """Run all pre-flight checks."""
        result = PreflightResult(
            start_time=datetime.now(),
            mode="quick" if self.quick else "full",
        )

        registry = get_registry()

        for category in self.categories:
            tools = registry.get_tools_by_category(category)
            if not tools:
                continue

            cat_result = self._check_category(category, tools)
            result.categories.append(cat_result)

            if not cat_result.success:
                result.success = False

        result.end_time = datetime.now()
        return result

    def _check_category(self, category: str, tools: Dict[str, Any]) -> CategoryResult:
        """Check all tools in a category."""
        cat_result = CategoryResult(category=category)

        for tool_name, tool_meta in tools.items():
            if tool_meta.get("skip_import", False):
                continue

            tool_result = self._check_tool(category, tool_name, tool_meta)
            cat_result.tools.append(tool_result)

            if self.verbose:
                status = "PASS" if tool_result.success else "FAIL"
                print(f"  [{status}] {tool_name}")

        return cat_result

    def _check_tool(
        self, category: str, tool_name: str, tool_meta: Dict[str, Any]
    ) -> ToolResult:
        """Check a single tool."""
        start = time.time()
        result = ToolResult(
            tool_name=tool_name,
            category=category,
            success=True,
        )

        # Check 1: Import test
        passed, msg = self._check_import(tool_meta)
        result.checks_total += 1
        if passed:
            result.checks_passed += 1
        else:
            if tool_meta.get("optional_dependency", False):
                result.skipped.append(f"Skipped (optional dependency): {msg}")
                result.checks_passed += 1
                result.duration_ms = (time.time() - start) * 1000
                return result
            result.errors.append(msg)
            result.success = False
            result.duration_ms = (time.time() - start) * 1000
            return result

        # Quick mode stops here
        if self.quick:
            result.duration_ms = (time.time() - start) * 1000
            return result

        # Check 2: Classes exist
        if tool_meta.get("classes"):
            passed, msg = self._check_classes(tool_meta)
            result.checks_total += 1
            if passed:
                result.checks_passed += 1
            else:
                result.errors.append(msg)
                result.success = False

        # Check 3: Functions exist
        if tool_meta.get("functions"):
            passed, msg = self._check_functions(tool_meta)
            result.checks_total += 1
            if passed:
                result.checks_passed += 1
            else:
                result.errors.append(msg)
                result.success = False

        # Check 4: Environment variables (warning only)
        if tool_meta.get("env_keys"):
            passed, msg = self._check_env_vars(tool_meta)
            result.checks_total += 1
            if passed:
                result.checks_passed += 1
            else:
                result.warnings.append(msg)

        # Check 5: Connectivity test (optional)
        if tool_meta.get("optional_connectivity") and not self.skip_connectivity:
            passed, msg = self._check_connectivity(tool_meta)
            result.checks_total += 1
            if passed:
                result.checks_passed += 1
            else:
                result.skipped.append(msg)

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _check_import(self, tool_meta: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if module can be imported."""
        module_path = tool_meta.get("module", "")
        if not module_path:
            return True, "No module to import"

        try:
            importlib.import_module(module_path)
            return True, "Import OK"
        except ImportError as e:
            return False, f"Import failed: {e}"
        except Exception as e:
            return False, f"Import error: {e}"

    def _check_classes(self, tool_meta: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if expected classes exist."""
        module_path = tool_meta.get("module", "")
        expected_classes = tool_meta.get("classes", [])

        try:
            module = importlib.import_module(module_path)
            missing = [c for c in expected_classes if not hasattr(module, c)]
            if missing:
                return False, f"Missing classes: {', '.join(missing)}"
            return True, f"Classes OK ({len(expected_classes)})"
        except Exception as e:
            return False, f"Class check failed: {e}"

    def _check_functions(self, tool_meta: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if expected functions exist."""
        module_path = tool_meta.get("module", "")
        expected_functions = tool_meta.get("functions", [])

        try:
            module = importlib.import_module(module_path)
            missing = [f for f in expected_functions if not hasattr(module, f)]
            if missing:
                return False, f"Missing functions: {', '.join(missing)}"
            return True, f"Functions OK ({len(expected_functions)})"
        except Exception as e:
            return False, f"Function check failed: {e}"

    def _check_env_vars(self, tool_meta: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if required environment variables are set."""
        env_keys = tool_meta.get("env_keys", [])
        missing = [k for k in env_keys if not os.environ.get(k)]
        if missing:
            return False, f"Missing env vars: {', '.join(missing)}"
        return True, f"Env vars OK ({len(env_keys)})"

    def _check_connectivity(self, tool_meta: Dict[str, Any]) -> Tuple[bool, str]:
        """Check API connectivity (placeholder)."""
        return True, "Connectivity skipped"


def print_report(result: PreflightResult) -> None:
    """Print formatted pre-flight report."""
    print()
    print("=" * 60)
    print("PM-OS Pre-Flight Check")
    print("=" * 60)
    print()

    for cat in result.categories:
        print(f"{cat.category.upper()} ({cat.passed_count}/{cat.total_count})")

        for tool in cat.tools:
            icon = "+" if tool.success else "X"
            msg = f"  {icon} {tool.tool_name}"
            if tool.checks_total > 0:
                msg += f" ({tool.checks_passed}/{tool.checks_total} checks)"
            if tool.errors:
                msg += f" - {tool.errors[0]}"
            if tool.warnings:
                msg += f" [warn: {tool.warnings[0]}]"
            print(msg)

        print()

    print("-" * 60)
    print(f"Tools: {result.tools_passed}/{result.tools_total} passed")
    print(f"Checks: {result.checks_passed}/{result.checks_total} passed")
    print(f"Duration: {result.duration_ms:.0f}ms")
    print()

    if result.all_errors:
        print("ERRORS:")
        for err in result.all_errors[:5]:
            print(f"  - {err}")
        if len(result.all_errors) > 5:
            print(f"  ... and {len(result.all_errors) - 5} more")
        print()

    if result.all_warnings:
        print("WARNINGS:")
        for warn in result.all_warnings[:5]:
            print(f"  - {warn}")
        if len(result.all_warnings) > 5:
            print(f"  ... and {len(result.all_warnings) - 5} more")
        print()

    print("=" * 60)
    if result.success:
        print("STATUS: READY")
    else:
        print("STATUS: FAILED - Boot blocked")
    print("=" * 60)
    print()


def print_tool_list() -> None:
    """Print compact tool inventory for agent consumption."""
    registry = get_registry()
    total = registry.get_tool_count()
    categories = registry.get_categories()

    print("# PM-OS Tool Inventory")
    print(f"# {total} tools across {len(categories)} categories")
    print()

    for category in categories:
        tools = registry.get_tools_by_category(category)
        print(f"## {category.upper()}")
        for tool_name, meta in tools.items():
            if meta.get("skip_import"):
                continue
            path = meta.get("path", "")
            desc = meta.get("description", "No description")
            source = meta.get("_source_plugin", "pm-os-base")
            print(f"  {path} - {desc} [{source}]")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="PM-OS Pre-Flight Check Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--category", "-c", help="Run only specific category")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--quick", "-q", action="store_true", help="Quick mode (import tests only)")
    parser.add_argument("--skip-connectivity", action="store_true", default=True)
    parser.add_argument("--with-connectivity", action="store_true")
    parser.add_argument("--list", "-l", action="store_true", help="Print tool inventory")

    args = parser.parse_args()

    if args.list:
        print_tool_list()
        sys.exit(0)

    categories = None
    if args.category:
        available = get_categories()
        if args.category not in available:
            print(f"Unknown category: {args.category}")
            print(f"Available: {', '.join(available)}")
            sys.exit(1)
        categories = [args.category]

    runner = PreflightRunner(
        verbose=args.verbose,
        quick=args.quick,
        skip_connectivity=not args.with_connectivity,
        categories=categories,
    )

    result = runner.run()

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print_report(result)

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
