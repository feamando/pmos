"""
PM-OS Dev CrossCLIValidator (v5.0)

Validates command parity across CLI environments (Claude Code, Gemini, etc.).

Usage:
    from pm_os_dev.tools.dev_util.cross_cli_validator import CrossCLIValidator

CLI:
    python3 cross_cli_validator.py
    python3 cross_cli_validator.py --json
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        from core.path_resolver import get_paths
    except ImportError:
        get_paths = None

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from core.config_loader import get_config
    except ImportError:
        get_config = None


class CrossCLIValidator:
    """Validates command parity across CLI environments."""

    def __init__(self, pmos_root: Optional[Path] = None):
        if pmos_root:
            self.pmos_root = pmos_root
        elif get_paths is not None:
            try:
                self.pmos_root = get_paths().root
            except Exception:
                self.pmos_root = Path.home() / "pm-os"
        else:
            self.pmos_root = Path.home() / "pm-os"

        self.config = get_config() if get_config else {}

    def _get_cli_dirs(self) -> Dict[str, Path]:
        """Get known CLI command directories."""
        dirs = {}

        # Claude Code commands
        claude_dir = self.pmos_root / "common" / ".claude" / "commands"
        if claude_dir.exists():
            dirs["claude"] = claude_dir

        # Gemini commands (if configured)
        gemini_dir = self.pmos_root / "common" / ".gemini" / "commands"
        if gemini_dir.exists():
            dirs["gemini"] = gemini_dir

        # Plugin commands
        plugins_dir = self.pmos_root / "v5" / "plugins"
        if plugins_dir.exists():
            dirs["plugins"] = plugins_dir

        return dirs

    def _get_commands(self, cli_dir: Path) -> Dict[str, Path]:
        """Get all command files in a CLI directory."""
        commands = {}
        for cmd_file in sorted(cli_dir.glob("*.md")):
            commands[cmd_file.stem] = cmd_file
        return commands

    def _get_plugin_commands(self, plugins_dir: Path) -> Dict[str, Path]:
        """Get all commands across all plugins."""
        commands = {}
        for cmd_file in sorted(plugins_dir.glob("pm-os-*/commands/*.md")):
            commands[cmd_file.stem] = cmd_file
        return commands

    def validate(self) -> Dict[str, Any]:
        """Run full validation. Returns report dict."""
        cli_dirs = self._get_cli_dirs()
        report = {
            "clis_found": list(cli_dirs.keys()),
            "commands_by_cli": {},
            "missing": [],
            "divergent": [],
            "parity": True,
        }

        all_commands: Dict[str, Dict[str, Path]] = {}

        for cli_name, cli_dir in cli_dirs.items():
            if cli_name == "plugins":
                commands = self._get_plugin_commands(cli_dir)
            else:
                commands = self._get_commands(cli_dir)

            all_commands[cli_name] = commands
            report["commands_by_cli"][cli_name] = list(commands.keys())

        # Check parity between CLIs
        if len(all_commands) < 2:
            return report

        cli_names = list(all_commands.keys())
        reference_cli = cli_names[0]
        reference_cmds = set(all_commands[reference_cli].keys())

        for cli_name in cli_names[1:]:
            other_cmds = set(all_commands[cli_name].keys())

            # Commands in reference but not in other
            for cmd in reference_cmds - other_cmds:
                report["missing"].append({
                    "command": cmd,
                    "present_in": reference_cli,
                    "missing_from": cli_name,
                })

            # Commands in other but not in reference
            for cmd in other_cmds - reference_cmds:
                report["missing"].append({
                    "command": cmd,
                    "present_in": cli_name,
                    "missing_from": reference_cli,
                })

        report["parity"] = len(report["missing"]) == 0 and len(report["divergent"]) == 0
        return report

    def print_report(self, report: Dict[str, Any]) -> None:
        """Print a human-readable validation report."""
        print("=" * 60)
        print("CROSS-CLI VALIDATION REPORT")
        print("=" * 60)
        print(f"CLIs found: {', '.join(report['clis_found'])}")
        print()

        for cli, commands in report["commands_by_cli"].items():
            print(f"  {cli}: {len(commands)} commands")

        if report["missing"]:
            print(f"\nMissing ({len(report['missing'])}):")
            for m in report["missing"]:
                print(f"  - {m['command']}: in {m['present_in']}, missing from {m['missing_from']}")

        if report["divergent"]:
            print(f"\nDivergent ({len(report['divergent'])}):")
            for d in report["divergent"]:
                print(f"  - {d}")

        status = "PASS" if report["parity"] else "FAIL"
        print(f"\nResult: {status}")


def main():
    parser = argparse.ArgumentParser(description="Cross-CLI Parity Validator")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--pmos-root", type=Path, help="PM-OS root directory")

    args = parser.parse_args()

    validator = CrossCLIValidator(pmos_root=args.pmos_root)
    report = validator.validate()

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        validator.print_report(report)


if __name__ == "__main__":
    main()
