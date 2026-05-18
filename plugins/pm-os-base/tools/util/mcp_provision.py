#!/usr/bin/env python3
"""
MCP Provision - ensures .mcp.json exists at project root with MCP servers.

Checks if the project root has a .mcp.json file. If missing, creates one
with the Brain and GDrive MCP servers configured. If an existing
.mcp.json exists but lacks server entries, adds them.

Usage:
    python3 mcp_provision.py              # Provision .mcp.json
    python3 mcp_provision.py --status     # Check current state
    python3 mcp_provision.py --dry-run    # Preview without changes
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from pm_os_base.tools.core.config_loader import get_config, get_google_paths
except ImportError:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
        from config_loader import get_config, get_google_paths
    except ImportError:
        get_config = None
        get_google_paths = None

# Path resolution
SCRIPT_DIR = Path(__file__).parent
PLUGIN_ROOT = SCRIPT_DIR.parent.parent
PM_OS_ROOT = Path(os.environ.get("PM_OS_ROOT", str(PLUGIN_ROOT.parent.parent)))

MCP_JSON_PATH = PM_OS_ROOT / ".mcp.json"

# MCP server configs - no secrets, no env vars, works for everyone
MCP_SERVERS = {
    "brain": {
        "command": "python3",
        "args": ["common/tools/mcp/brain_mcp/server.py"],
    },
    "gdrive": {
        "command": "python3",
        "args": ["common/tools/mcp/gdrive_mcp/server.py"],
    },
}


def provision(dry_run: bool = False, verbose: bool = True) -> dict:
    """
    Ensure .mcp.json exists at project root with all MCP servers.

    Returns:
        Dict with keys: action ("created"|"updated"|"ok"), path, servers
    """
    result = {"path": str(MCP_JSON_PATH), "servers": [], "action": "ok"}

    if MCP_JSON_PATH.exists():
        try:
            existing = json.loads(MCP_JSON_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

        if "mcpServers" not in existing:
            existing["mcpServers"] = {}

        servers = existing["mcpServers"]
        added = []

        for name, config in MCP_SERVERS.items():
            if name not in servers:
                servers[name] = config
                added.append(name)

        result["servers"] = list(servers.keys())

        if not added:
            result["action"] = "ok"
            if verbose:
                print(f"MCP config OK: {MCP_JSON_PATH}")
                print(f"  Servers: {', '.join(servers.keys())}")
            return result

        if not dry_run:
            MCP_JSON_PATH.write_text(
                json.dumps(existing, indent=2) + "\n", encoding="utf-8"
            )

        result["action"] = "updated"
        if verbose:
            prefix = "Would update" if dry_run else "Updated"
            print(f"{prefix}: {MCP_JSON_PATH}")
            print(f"  Added: {', '.join(added)}")
        return result

    # No .mcp.json at all, create with all servers
    config = {"mcpServers": dict(MCP_SERVERS)}

    if not dry_run:
        MCP_JSON_PATH.write_text(
            json.dumps(config, indent=2) + "\n", encoding="utf-8"
        )

    result["servers"] = list(MCP_SERVERS.keys())
    result["action"] = "created"
    if verbose:
        prefix = "Would create" if dry_run else "Created"
        print(f"{prefix}: {MCP_JSON_PATH}")
        print(f"  Servers: {', '.join(MCP_SERVERS.keys())}")
    return result


def show_status():
    """Show current MCP config status."""
    print(f"Project root: {PM_OS_ROOT}")
    print(f"MCP config:   {MCP_JSON_PATH}")
    print()

    if not MCP_JSON_PATH.exists():
        print("Status: NOT CONFIGURED")
        print("  .mcp.json does not exist at project root")
        print("  Run this tool or /session boot to create it")
        return

    try:
        config = json.loads(MCP_JSON_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Status: ERROR, cannot parse .mcp.json: {e}")
        return

    servers = config.get("mcpServers", {})
    print(f"Status: CONFIGURED ({len(servers)} server(s))")
    for name, cfg in servers.items():
        if isinstance(cfg, dict) and "command" in cfg:
            args_str = " ".join(cfg.get("args", []))
            print(f"  [{name}] {cfg['command']} {args_str}")
        elif not name.startswith("_"):
            print(f"  [{name}] (comment/placeholder)")

    for name in MCP_SERVERS:
        if name not in servers:
            print(f"\n  WARNING: {name} MCP server not configured")


def main():
    parser = argparse.ArgumentParser(
        description="Provision .mcp.json with MCP servers"
    )
    parser.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")

    args = parser.parse_args()

    if args.status:
        show_status()
        return 0

    result = provision(dry_run=args.dry_run, verbose=not args.quiet)

    if args.quiet and result["action"] != "ok":
        print(f"MCP: {result['action']} .mcp.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
