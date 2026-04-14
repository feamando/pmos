#!/usr/bin/env python3
"""
Integration Orchestrator (v5.0)

Runs all enabled integrations in parallel using ThreadPoolExecutor.
Checks which integrations are enabled via config and reports results
(success/skip/fail for each).

Usage:
    python3 sync_all.py                     # Run all enabled integrations
    python3 sync_all.py --list              # List available integrations
    python3 sync_all.py --only jira,github  # Run specific integrations only
    python3 sync_all.py --exclude statsig   # Run all except specified
"""

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# v5 imports: shared utils from pm_os_base
try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
        from tools.core.config_loader import get_config
    except ImportError:
        get_config = None

try:
    from pm_os_base.tools.core.connector_bridge import is_service_available
except ImportError:
    try:
        from tools.core.connector_bridge import is_service_available
    except ImportError:
        is_service_available = None

# Integration registry — maps name to (module, run function, required service)
INTEGRATION_REGISTRY = {
    "jira": {
        "module": "jira_sync",
        "display_name": "Jira Sync",
        "config_key": "integrations.jira.enabled",
        "service": "jira",
        "description": "Sync Jira epics, in-progress, and blockers to Brain",
    },
    "github": {
        "module": "github_sync",
        "display_name": "GitHub Sync",
        "config_key": "integrations.github.enabled",
        "service": "github",
        "description": "Sync GitHub PRs and commits to Brain",
    },
    "confluence": {
        "module": "confluence_sync",
        "display_name": "Confluence Sync",
        "config_key": "integrations.confluence.enabled",
        "service": "confluence",
        "description": "Sync Confluence pages to Brain",
    },
    "statsig": {
        "module": "statsig_sync",
        "display_name": "Statsig Sync",
        "config_key": "integrations.statsig.enabled",
        "service": "statsig",
        "description": "Sync Statsig experiments to Brain",
    },
    "squad_sprint": {
        "module": "squad_sprint_sync",
        "display_name": "Squad Sprint Sync",
        "config_key": "integrations.google.sprint_sync_enabled",
        "service": "google",
        "description": "Sync sprint reports from Google Sheets to Brain",
    },
    "master_sheet": {
        "module": "master_sheet_sync",
        "display_name": "Master Sheet Sync",
        "config_key": "master_sheet.enabled",
        "service": "google",
        "description": "Sync Master Sheet actions and deadlines",
    },
    "tech_context": {
        "module": "tech_context_sync",
        "display_name": "Tech Context Sync",
        "config_key": "integrations.github.tech_context_enabled",
        "service": "github",
        "description": "Analyze repos and sync technical standards to Brain",
    },
}

# Maximum parallel workers
MAX_WORKERS = 4


def _is_integration_enabled(name: str) -> bool:
    """Check if an integration is enabled in config."""
    config = get_config() if get_config else None
    if config is None:
        return False

    reg = INTEGRATION_REGISTRY.get(name, {})
    config_key = reg.get("config_key", "")

    if config_key:
        return config.get_bool(config_key, False)

    return False


def _has_service_auth(name: str) -> bool:
    """Check if the required service has auth available."""
    reg = INTEGRATION_REGISTRY.get(name, {})
    service = reg.get("service", "")

    if not service:
        return True

    if is_service_available is not None:
        return is_service_available(service)

    return True  # Optimistic fallback


def _run_integration(name: str) -> Dict[str, Any]:
    """Import and run a single integration, returning its result."""
    reg = INTEGRATION_REGISTRY.get(name)
    if not reg:
        return {"status": "error", "message": f"Unknown integration: {name}"}

    module_name = reg["module"]

    try:
        # Dynamic import from sibling module
        import importlib
        mod = importlib.import_module(f".{module_name}", package=__package__)

        # All sync modules expose a run_sync() function
        run_fn = getattr(mod, "run_sync", None)
        if run_fn is None:
            return {"status": "error", "message": f"No run_sync() in {module_name}"}

        start = time.monotonic()
        result = run_fn()
        elapsed = time.monotonic() - start

        if isinstance(result, dict):
            result["elapsed_seconds"] = round(elapsed, 1)
        return result

    except ImportError as e:
        return {"status": "error", "message": f"Import error for {module_name}: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"Error in {module_name}: {e}"}


def run_all(
    only: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run all enabled integrations in parallel.

    Args:
        only: If specified, only run these integrations
        exclude: If specified, skip these integrations

    Returns:
        Dict with results for each integration
    """
    exclude = exclude or []

    # Determine which integrations to run
    to_run = []
    skipped = {}

    for name in INTEGRATION_REGISTRY:
        if only and name not in only:
            continue

        if name in exclude:
            skipped[name] = "excluded"
            continue

        if not _is_integration_enabled(name):
            skipped[name] = "disabled_in_config"
            continue

        if not _has_service_auth(name):
            skipped[name] = "no_auth"
            continue

        to_run.append(name)

    logger.info(
        "Running %d integrations in parallel (skipped %d)...",
        len(to_run), len(skipped),
    )

    # Run in parallel
    results = {}
    start_all = time.monotonic()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_run_integration, name): name for name in to_run
        }

        for future in as_completed(futures):
            name = futures[future]
            display = INTEGRATION_REGISTRY[name]["display_name"]
            try:
                result = future.result()
                status = result.get("status", "unknown")
                logger.info("  %s: %s", display, status)
                results[name] = result
            except Exception as e:
                logger.error("  %s: exception - %s", display, e)
                results[name] = {"status": "error", "message": str(e)}

    total_elapsed = time.monotonic() - start_all

    # Summary
    success_count = sum(1 for r in results.values() if r.get("status") == "success")
    error_count = sum(1 for r in results.values() if r.get("status") == "error")

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_elapsed_seconds": round(total_elapsed, 1),
        "summary": {
            "ran": len(to_run),
            "success": success_count,
            "error": error_count,
            "skipped": len(skipped),
        },
        "results": results,
        "skipped": skipped,
    }


def list_integrations() -> Dict[str, Dict]:
    """List all integrations with their status."""
    items = {}
    for name, reg in INTEGRATION_REGISTRY.items():
        enabled = _is_integration_enabled(name)
        has_auth = _has_service_auth(name)
        items[name] = {
            "display_name": reg["display_name"],
            "description": reg["description"],
            "service": reg["service"],
            "enabled": enabled,
            "auth_available": has_auth,
            "ready": enabled and has_auth,
        }
    return items


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="PM-OS Integration Orchestrator")
    parser.add_argument("--list", action="store_true", help="List available integrations and their status")
    parser.add_argument("--only", type=str, help="Comma-separated list of integrations to run")
    parser.add_argument("--exclude", type=str, help="Comma-separated list of integrations to skip")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.list:
        items = list_integrations()
        if args.json:
            print(json.dumps(items, indent=2))
        else:
            print("Available Integrations:")
            print("-" * 70)
            for name, info in items.items():
                status = "READY" if info["ready"] else ("AUTH?" if info["enabled"] else "OFF")
                print(
                    f"  [{status:5s}] {info['display_name']:<25s} "
                    f"({info['service']}) - {info['description']}"
                )
            print()
            print("  READY = enabled + auth available")
            print("  AUTH? = enabled but no auth configured")
            print("  OFF   = disabled in config")
        return

    only = args.only.split(",") if args.only else None
    exclude = args.exclude.split(",") if args.exclude else None

    result = run_all(only=only, exclude=exclude)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        summary = result["summary"]
        print(f"\nSync complete in {result['total_elapsed_seconds']}s")
        print(f"  Ran: {summary['ran']}, Success: {summary['success']}, "
              f"Error: {summary['error']}, Skipped: {summary['skipped']}")

        if result.get("results"):
            print("\nResults:")
            for name, res in result["results"].items():
                display = INTEGRATION_REGISTRY.get(name, {}).get("display_name", name)
                status = res.get("status", "?")
                elapsed = res.get("elapsed_seconds", "?")
                print(f"  {display}: {status} ({elapsed}s)")

        if result.get("skipped"):
            print("\nSkipped:")
            for name, reason in result["skipped"].items():
                display = INTEGRATION_REGISTRY.get(name, {}).get("display_name", name)
                print(f"  {display}: {reason}")


if __name__ == "__main__":
    main()
