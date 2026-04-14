#!/usr/bin/env python3
"""
CLAUDE.md Generator — Generates project CLAUDE.md from installed plugins.

Scans installed plugins for commands, skills, and tool descriptions,
then assembles a unified CLAUDE.md that Claude Code reads on startup.

Usage:
    python3 claudemd_generator.py                    # Generate to stdout
    python3 claudemd_generator.py --output CLAUDE.md  # Write to file
    python3 claudemd_generator.py --check             # Verify existing CLAUDE.md is current

Version: 5.0.0
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


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

    # Walk up from this file
    current = PLUGIN_ROOT
    for _ in range(10):
        if current.name == "plugins":
            return current
        candidate = current / "plugins"
        if candidate.exists():
            return candidate
        current = current.parent

    return None


def _load_plugin_manifest(plugin_dir: Path) -> Optional[Dict[str, Any]]:
    """Load plugin.json manifest."""
    manifest_file = plugin_dir / ".claude-plugin" / "plugin.json"
    if not manifest_file.exists():
        return None
    try:
        with open(manifest_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _scan_commands(plugin_dir: Path) -> List[Dict[str, str]]:
    """Scan plugin for command files."""
    commands = []
    cmd_dir = plugin_dir / "commands"
    if cmd_dir.exists():
        for cmd_file in sorted(cmd_dir.glob("*.md")):
            # Read first line for description
            try:
                first_line = cmd_file.read_text(encoding="utf-8").split("\n")[0]
                desc = first_line.lstrip("# ").strip()
            except Exception:
                desc = cmd_file.stem
            commands.append({"name": cmd_file.stem, "description": desc})
    return commands


def _scan_skills(plugin_dir: Path) -> List[Dict[str, str]]:
    """Scan plugin for skill files."""
    skills = []
    skill_dir = plugin_dir / "skills"
    if skill_dir.exists():
        for skill_file in sorted(skill_dir.glob("*.md")):
            try:
                content = skill_file.read_text(encoding="utf-8")
                # Extract description from frontmatter
                desc = skill_file.stem
                if content.startswith("---"):
                    lines = content.split("\n")
                    for line in lines[1:]:
                        if line.strip() == "---":
                            break
                        if line.startswith("description:"):
                            desc = line.split(":", 1)[1].strip()
                            break
            except Exception:
                desc = skill_file.stem
            skills.append({"name": skill_file.stem, "description": desc})
    return skills


def generate_claudemd(plugins_dir: Path) -> str:
    """Generate CLAUDE.md content from installed plugins."""
    sections = []

    sections.append("# PM-OS v5.0 — CLAUDE.md")
    sections.append("")
    sections.append(f"Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}.")
    sections.append("Do not edit manually — regenerate with: `/base setup` or `python3 tools/util/claudemd_generator.py`")
    sections.append("")

    # Scan all installed plugins
    plugins = []
    for plugin_dir in sorted(plugins_dir.iterdir()):
        if not plugin_dir.is_dir() or not plugin_dir.name.startswith("pm-os-"):
            continue

        manifest = _load_plugin_manifest(plugin_dir)
        if not manifest:
            continue

        commands = _scan_commands(plugin_dir)
        skills = _scan_skills(plugin_dir)

        plugins.append({
            "name": manifest.get("name", plugin_dir.name),
            "version": manifest.get("version", "?"),
            "description": manifest.get("description", ""),
            "dir": plugin_dir,
            "manifest": manifest,
            "commands": commands,
            "skills": skills,
        })

    # Installed plugins section
    sections.append("## Installed Plugins")
    sections.append("")
    for p in plugins:
        sections.append(f"- **{p['name']}** v{p['version']} — {p['description']}")
    sections.append("")

    # Commands section
    sections.append("## Available Commands")
    sections.append("")
    for p in plugins:
        if p["commands"]:
            for cmd in p["commands"]:
                sections.append(f"- `/{cmd['name']}` — {cmd['description']} [{p['name']}]")
    sections.append("")

    # Skills section
    sections.append("## Active Skills")
    sections.append("")
    for p in plugins:
        if p["skills"]:
            for skill in p["skills"]:
                sections.append(f"- **{skill['name']}**: {skill['description']} [{p['name']}]")
    sections.append("")

    # MCP servers section
    mcp_servers = []
    for p in plugins:
        mcp_file = p["dir"] / ".mcp.json"
        if mcp_file.exists():
            try:
                with open(mcp_file, "r", encoding="utf-8") as f:
                    mcp_config = json.load(f)
                servers = mcp_config.get("mcpServers", {})
                for name in servers:
                    mcp_servers.append(f"- `{name}` [{p['name']}]")
            except Exception:
                pass

    if mcp_servers:
        sections.append("## MCP Servers")
        sections.append("")
        sections.extend(mcp_servers)
        sections.append("")

    # Config requirements
    sections.append("## Required Config Keys")
    sections.append("")
    all_keys = set()
    for p in plugins:
        keys = p["manifest"].get("requires", {}).get("config_keys", [])
        all_keys.update(keys)
    for key in sorted(all_keys):
        sections.append(f"- `{key}`")
    sections.append("")

    return "\n".join(sections)


def main():
    parser = argparse.ArgumentParser(description="Generate CLAUDE.md from installed plugins")
    parser.add_argument("--output", "-o", type=str, help="Output file path")
    parser.add_argument("--check", action="store_true", help="Check if CLAUDE.md is current")

    args = parser.parse_args()

    plugins_dir = _find_plugins_dir()
    if not plugins_dir:
        print("Error: Could not find plugins directory", file=sys.stderr)
        sys.exit(1)

    content = generate_claudemd(plugins_dir)

    if args.check:
        # Check if existing CLAUDE.md matches
        root = os.environ.get("PM_OS_ROOT", "")
        if root:
            existing_path = Path(root) / "CLAUDE.md"
        else:
            existing_path = plugins_dir.parent / "CLAUDE.md"

        if existing_path.exists():
            existing = existing_path.read_text(encoding="utf-8")
            # Compare ignoring timestamp line
            existing_lines = [l for l in existing.split("\n") if not l.startswith("Auto-generated")]
            new_lines = [l for l in content.split("\n") if not l.startswith("Auto-generated")]
            if existing_lines == new_lines:
                print("CLAUDE.md is current")
                sys.exit(0)
            else:
                print("CLAUDE.md needs regeneration")
                sys.exit(1)
        else:
            print("CLAUDE.md does not exist")
            sys.exit(1)

    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
        print(f"Generated: {args.output}")
    else:
        print(content)


if __name__ == "__main__":
    main()
