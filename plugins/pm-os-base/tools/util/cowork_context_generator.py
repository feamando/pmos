#!/usr/bin/env python3
"""
Cowork Context Generator — Generates user/cowork-context/ files for Claude Cowork.

Creates context files that Claude Cowork sessions can consume to understand
the user's PM-OS setup, installed plugins, and available MCP servers.

Usage:
    python3 cowork_context_generator.py              # Generate all context files
    python3 cowork_context_generator.py --check      # Check if files are current
    python3 cowork_context_generator.py --output DIR  # Custom output directory

Version: 5.0.0
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _find_plugins_dir() -> Optional[Path]:
    """Find the plugins directory."""
    root = os.environ.get("PM_OS_ROOT", "")
    if root:
        v5_plugins = Path(root) / "v5" / "plugins"
        if v5_plugins.exists():
            return v5_plugins
        prod_plugins = Path(root) / "plugins"
        if prod_plugins.exists():
            return prod_plugins

    current = Path(__file__).resolve().parent
    for _ in range(10):
        if current.name == "plugins":
            return current
        candidate = current / "plugins"
        if candidate.exists():
            return candidate
        current = current.parent

    return None


def _get_output_dir() -> Path:
    """Get the cowork-context output directory."""
    user_dir = os.environ.get("PM_OS_USER", "")
    if user_dir:
        return Path(user_dir) / "cowork-context"

    current = Path(__file__).resolve().parent
    for _ in range(10):
        candidate = current / "user" / "cowork-context"
        if candidate.parent.exists():
            return candidate
        current = current.parent

    return Path.home() / "pm-os" / "user" / "cowork-context"


def _load_manifests(plugins_dir: Path) -> List[Dict[str, Any]]:
    """Load all plugin manifests."""
    manifests = []
    for plugin_dir in sorted(plugins_dir.iterdir()):
        if not plugin_dir.is_dir() or not plugin_dir.name.startswith("pm-os-"):
            continue

        manifest_file = plugin_dir / ".claude-plugin" / "plugin.json"
        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                manifest["_dir"] = str(plugin_dir)
                manifests.append(manifest)
            except Exception:
                pass

    return manifests


def generate_plugins_context(manifests: List[Dict[str, Any]]) -> str:
    """Generate plugins.md context file."""
    lines = [
        "# PM-OS Installed Plugins",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    for m in manifests:
        lines.append(f"## {m.get('name', 'unknown')}")
        lines.append(f"- Version: {m.get('version', '?')}")
        lines.append(f"- Description: {m.get('description', '')}")
        deps = m.get("dependencies", [])
        if deps:
            lines.append(f"- Dependencies: {', '.join(deps)}")
        commands = m.get("commands", [])
        if commands:
            lines.append(f"- Commands: {', '.join(commands)}")
        skills = m.get("skills", [])
        if skills:
            lines.append(f"- Skills: {', '.join(skills)}")
        lines.append("")

    return "\n".join(lines)


def generate_mcp_context(plugins_dir: Path, manifests: List[Dict[str, Any]]) -> str:
    """Generate mcp-servers.md context file."""
    lines = [
        "# PM-OS MCP Servers",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "These MCP servers are available for Cowork sessions.",
        "",
    ]

    for m in manifests:
        plugin_dir = Path(m["_dir"])
        mcp_file = plugin_dir / ".mcp.json"
        if not mcp_file.exists():
            continue

        try:
            with open(mcp_file, "r", encoding="utf-8") as f:
                mcp_config = json.load(f)
        except Exception:
            continue

        servers = mcp_config.get("mcpServers", {})
        if not servers:
            continue

        lines.append(f"## {m.get('name', 'unknown')}")
        for name, config in servers.items():
            lines.append(f"### {name}")
            lines.append(f"- Command: `{config.get('command', '')} {' '.join(config.get('args', []))}`")
            env = config.get("env", {})
            if env:
                lines.append(f"- Environment: {', '.join(f'{k}={v}' for k, v in env.items())}")
            lines.append("")

    if len(lines) <= 6:
        lines.append("No MCP servers configured.")
        lines.append("")

    return "\n".join(lines)


def generate_config_context() -> str:
    """Generate config-summary.md context file."""
    lines = [
        "# PM-OS Configuration Summary",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    # Try to load config
    user_dir = os.environ.get("PM_OS_USER", "")
    config_path = Path(user_dir) / "config.yaml" if user_dir else None

    if config_path and config_path.exists():
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            if config:
                lines.append("## User")
                user = config.get("user", {})
                lines.append(f"- Name: {user.get('name', 'not set')}")
                lines.append(f"- Role: {user.get('role', 'not set')}")
                lines.append(f"- Company: {user.get('company', 'not set')}")
                lines.append("")

                lines.append("## Integrations")
                integrations = config.get("integrations", {})
                for service, settings in integrations.items():
                    enabled = settings.get("enabled", True) if isinstance(settings, dict) else True
                    status = "enabled" if enabled else "disabled"
                    lines.append(f"- {service}: {status}")
                lines.append("")

        except ImportError:
            lines.append("PyYAML not available — cannot read config.yaml")
            lines.append("")
        except Exception as e:
            lines.append(f"Error reading config: {e}")
            lines.append("")
    else:
        lines.append("config.yaml not found. Run `/base setup` to create.")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate Cowork context files")
    parser.add_argument("--output", "-o", type=str, help="Output directory")
    parser.add_argument("--check", action="store_true", help="Check if files are current")

    args = parser.parse_args()

    plugins_dir = _find_plugins_dir()
    if not plugins_dir:
        print("Error: Could not find plugins directory", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output) if args.output else _get_output_dir()

    manifests = _load_manifests(plugins_dir)

    if args.check:
        if output_dir.exists() and list(output_dir.glob("*.md")):
            print("Cowork context files exist")
            sys.exit(0)
        else:
            print("Cowork context files need generation")
            sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate context files
    files = {
        "plugins.md": generate_plugins_context(manifests),
        "mcp-servers.md": generate_mcp_context(plugins_dir, manifests),
        "config-summary.md": generate_config_context(),
    }

    for filename, content in files.items():
        filepath = output_dir / filename
        filepath.write_text(content, encoding="utf-8")
        print(f"  Generated: {filepath}")

    print(f"\nCowork context files written to: {output_dir}")


if __name__ == "__main__":
    main()
