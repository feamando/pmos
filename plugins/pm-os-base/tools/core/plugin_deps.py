#!/usr/bin/env python3
"""
PM-OS Plugin Dependency Checker (v5.0)

Checks whether PM-OS plugins are installed and provides graceful fallback
when optional plugins are missing.

Usage:
    from pm_os_base.tools.core.plugin_deps import check_plugin, require_plugin

    if check_plugin("pm-os-brain"):
        # Brain-enhanced path
        ...
    else:
        # Degraded but functional path
        ...
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class PluginNotInstalledError(Exception):
    """Raised when a required plugin is not installed."""


def _get_plugins_dir() -> Optional[Path]:
    """Find the plugins directory."""
    # Check environment variable
    root = os.getenv("PM_OS_ROOT")
    if root:
        root_path = Path(root)
        # Production: common/plugins/
        prod = root_path / "common" / "plugins"
        if prod.exists():
            return prod
        # Development: v5/plugins/
        dev = root_path / "v5" / "plugins"
        if dev.exists():
            return dev

    # Walk up from this file to find plugins/
    current = Path(__file__).resolve().parent
    for _ in range(10):
        # Check if we're inside a plugin (tools/core/ -> pm-os-base -> plugins)
        candidate = current / "plugins"
        if candidate.exists():
            return candidate
        # Check if parent is the plugins dir
        if current.name != "plugins" and (current.parent / "plugins").exists():
            return current.parent / "plugins"
        # Check if we're inside a plugin dir
        plugin_json = current / ".claude-plugin" / "plugin.json"
        if plugin_json.exists():
            return current.parent
        current = current.parent

    return None


def _read_plugin_json(plugin_dir: Path) -> Optional[dict]:
    """Read and parse a plugin's plugin.json."""
    plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
    if not plugin_json.exists():
        return None
    try:
        with open(plugin_json, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning("Failed to read %s: %s", plugin_json, e)
        return None


def get_installed_plugins() -> List[str]:
    """
    Get list of installed plugin IDs.

    Returns:
        List of plugin name strings (e.g., ['pm-os-base', 'pm-os-brain']).
    """
    plugins_dir = _get_plugins_dir()
    if not plugins_dir:
        logger.warning("Could not find plugins directory")
        return []

    installed = []
    for item in sorted(plugins_dir.iterdir()):
        if item.is_dir() and item.name.startswith("pm-os-"):
            manifest = _read_plugin_json(item)
            if manifest:
                installed.append(manifest.get("name", item.name))
    return installed


def get_plugin_info(plugin_id: str) -> Optional[dict]:
    """
    Get full plugin manifest info.

    Args:
        plugin_id: Plugin identifier (e.g., 'pm-os-brain')

    Returns:
        Plugin manifest dict or None if not found.
    """
    plugins_dir = _get_plugins_dir()
    if not plugins_dir:
        return None

    plugin_dir = plugins_dir / plugin_id
    if not plugin_dir.exists():
        return None

    return _read_plugin_json(plugin_dir)


def check_plugin(plugin_id: str) -> bool:
    """
    Check if a PM-OS plugin is installed. Returns False gracefully.

    Args:
        plugin_id: Plugin identifier (e.g., 'pm-os-brain' or 'brain')

    Returns:
        True if plugin is installed and has valid plugin.json.
    """
    # Normalize: accept both 'brain' and 'pm-os-brain'
    if not plugin_id.startswith("pm-os-"):
        plugin_id = f"pm-os-{plugin_id}"

    plugins_dir = _get_plugins_dir()
    if not plugins_dir:
        return False

    plugin_dir = plugins_dir / plugin_id
    return (plugin_dir / ".claude-plugin" / "plugin.json").exists()


def require_plugin(plugin_id: str) -> dict:
    """
    Require a plugin to be installed. Raises helpful error if missing.

    Args:
        plugin_id: Plugin identifier (e.g., 'pm-os-brain' or 'brain')

    Returns:
        Plugin manifest dict.

    Raises:
        PluginNotInstalledError: If plugin is not installed.
    """
    if not plugin_id.startswith("pm-os-"):
        plugin_id = f"pm-os-{plugin_id}"

    info = get_plugin_info(plugin_id)
    if info is None:
        raise PluginNotInstalledError(
            f"Plugin '{plugin_id}' is not installed.\n"
            f"Install with: /base plugins install {plugin_id}"
        )
    return info


def check_dependencies(plugin_id: str) -> Dict[str, bool]:
    """
    Check if all dependencies of a plugin are satisfied.

    Args:
        plugin_id: Plugin identifier

    Returns:
        Dict mapping dependency name to installed status.
    """
    if not plugin_id.startswith("pm-os-"):
        plugin_id = f"pm-os-{plugin_id}"

    info = get_plugin_info(plugin_id)
    if info is None:
        return {}

    deps = info.get("dependencies", [])
    return {dep: check_plugin(dep) for dep in deps}


def get_plugin_commands(plugin_id: str) -> List[str]:
    """
    Get list of command files provided by a plugin.

    Args:
        plugin_id: Plugin identifier

    Returns:
        List of command file paths relative to plugin root.
    """
    if not plugin_id.startswith("pm-os-"):
        plugin_id = f"pm-os-{plugin_id}"

    info = get_plugin_info(plugin_id)
    if info is None:
        return []

    return info.get("commands", [])


def get_plugin_skills(plugin_id: str) -> List[str]:
    """
    Get list of skill files provided by a plugin.

    Args:
        plugin_id: Plugin identifier

    Returns:
        List of skill file paths relative to plugin root.
    """
    if not plugin_id.startswith("pm-os-"):
        plugin_id = f"pm-os-{plugin_id}"

    info = get_plugin_info(plugin_id)
    if info is None:
        return []

    return info.get("skills", [])


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PM-OS Plugin Dependency Checker")
    parser.add_argument("--list", action="store_true", help="List installed plugins")
    parser.add_argument("--check", metavar="PLUGIN", help="Check if plugin is installed")
    parser.add_argument("--info", metavar="PLUGIN", help="Show plugin info")
    parser.add_argument("--deps", metavar="PLUGIN", help="Check plugin dependencies")

    args = parser.parse_args()

    if args.list:
        plugins = get_installed_plugins()
        if plugins:
            print(f"Installed plugins ({len(plugins)}):")
            for p in plugins:
                print(f"  {p}")
        else:
            print("No plugins found.")

    elif args.check:
        installed = check_plugin(args.check)
        name = args.check if args.check.startswith("pm-os-") else f"pm-os-{args.check}"
        if installed:
            print(f"{name}: installed")
        else:
            print(f"{name}: not installed")

    elif args.info:
        info = get_plugin_info(args.info if args.info.startswith("pm-os-") else f"pm-os-{args.info}")
        if info:
            print(json.dumps(info, indent=2))
        else:
            print("Plugin not found.")

    elif args.deps:
        deps = check_dependencies(args.deps)
        if deps:
            for dep, installed in deps.items():
                status = "installed" if installed else "MISSING"
                print(f"  {dep}: {status}")
        else:
            print("No dependencies or plugin not found.")

    else:
        parser.print_help()
