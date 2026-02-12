#!/usr/bin/env python3
"""
Cross-CLI Sync Validation Tool

Validates that FPF reasoning can be synchronized across:
- Claude Code (primary)
- Gemini CLI
- Mistral/Codex CLI

Usage:
    python validate_cross_cli_sync.py           # Run all validations
    python validate_cross_cli_sync.py --check   # Quick status check
    python validate_cross_cli_sync.py --fix     # Attempt to fix issues
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Add tools directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# --- Configuration ---
ROOT_PATH = config_loader.get_root_path()
COMMON_PATH = config_loader.get_common_path()
USER_PATH = ROOT_PATH / "user"
BRAIN_DIR = USER_PATH / "brain"
REASONING_DIR = BRAIN_DIR / "Reasoning"
QUINT_DIR = ROOT_PATH / ".quint"

# CLI Configuration paths
CLAUDE_COMMANDS = COMMON_PATH / ".claude" / "commands"
GEMINI_CONFIG = Path.home() / ".gemini"
GEMINI_COMMANDS = GEMINI_CONFIG / "commands"
CODEX_CONFIG = Path.home() / ".codex"
CODEX_PROMPTS = CODEX_CONFIG / "prompts"


def check_icon(passed: bool) -> str:
    return "[OK]" if passed else "[FAIL]"


def validate_quint_code_installation() -> Tuple[bool, str]:
    """Check if quint-code binary is installed."""
    try:
        result = subprocess.run(
            ["quint-code", "--version"], capture_output=True, text=True
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            return True, f"quint-code installed: {version}"
        return False, "quint-code returned error"
    except FileNotFoundError:
        return False, "quint-code not found in PATH"


def validate_quint_directory() -> Tuple[bool, str]:
    """Check .quint/ directory structure."""
    if not QUINT_DIR.exists():
        return False, ".quint/ directory does not exist"

    required = ["knowledge", "evidence", "agents"]
    missing = [d for d in required if not (QUINT_DIR / d).exists()]

    if missing:
        return False, f".quint/ missing directories: {missing}"

    return True, ".quint/ structure valid"


def validate_brain_reasoning() -> Tuple[bool, str]:
    """Check Brain/Reasoning/ directory structure."""
    if not REASONING_DIR.exists():
        return False, "Brain/Reasoning/ does not exist"

    required = ["Active", "Decisions", "Hypotheses", "Evidence"]
    missing = [d for d in required if not (REASONING_DIR / d).exists()]

    if missing:
        return False, f"Brain/Reasoning/ missing: {missing}"

    return True, "Brain/Reasoning/ structure valid"


def validate_claude_code() -> Tuple[bool, str]:
    """Check Claude Code FPF skills."""
    if not CLAUDE_COMMANDS.exists():
        return False, ".claude/commands/ does not exist"

    required_skills = [
        "q0-init.md",
        "q1-hypothesize.md",
        "q2-verify.md",
        "q3-validate.md",
        "q4-audit.md",
        "q5-decide.md",
        "quint-sync.md",
    ]

    existing = [f.name for f in CLAUDE_COMMANDS.glob("*.md")]
    missing = [s for s in required_skills if s not in existing]

    if missing:
        return False, f"Claude Code missing skills: {missing}"

    return True, f"Claude Code: {len(required_skills)} FPF skills present"


def validate_gemini_cli() -> Tuple[bool, str]:
    """Check Gemini CLI FPF setup."""
    if not GEMINI_CONFIG.exists():
        return False, "~/.gemini/ does not exist"

    # Check settings.json for MCP server
    settings_file = GEMINI_CONFIG / "settings.json"
    if settings_file.exists():
        try:
            with open(settings_file) as f:
                settings = json.load(f)
                if "mcpServers" not in settings:
                    return False, "Gemini settings missing mcpServers"
                if "quint-code" not in settings.get("mcpServers", {}):
                    return False, "Gemini settings missing quint-code MCP"
        except json.JSONDecodeError:
            return False, "Gemini settings.json invalid JSON"
    else:
        return False, "Gemini settings.json not found"

    # Check command files
    if not GEMINI_COMMANDS.exists():
        return False, "~/.gemini/commands/ does not exist"

    required_commands = [
        "fpf-init.toml",
        "fpf-hypothesize.toml",
        "fpf-verify.toml",
        "fpf-validate.toml",
        "fpf-audit.toml",
        "fpf-decide.toml",
    ]

    existing = [f.name for f in GEMINI_COMMANDS.glob("*.toml")]
    missing = [c for c in required_commands if c not in existing]

    if missing:
        return False, f"Gemini missing commands: {missing}"

    return (
        True,
        f"Gemini CLI: MCP configured, {len(required_commands)} commands present",
    )


def validate_codex_cli() -> Tuple[bool, str]:
    """Check Mistral/Codex CLI FPF setup."""
    if not CODEX_CONFIG.exists():
        return False, "~/.codex/ does not exist (Codex not installed)"

    # Check config.toml
    config_file = CODEX_CONFIG / "config.toml"
    if config_file.exists():
        content = config_file.read_text()
        if "quint-code" not in content:
            return False, "Codex config.toml missing quint-code MCP"
    else:
        return False, "Codex config.toml not found"

    # Check prompt files
    if not CODEX_PROMPTS.exists():
        return False, "~/.codex/prompts/ does not exist"

    required_prompts = [
        "fpf-init.md",
        "fpf-hypothesize.md",
        "fpf-verify.md",
        "fpf-validate.md",
        "fpf-audit.md",
        "fpf-decide.md",
    ]

    existing = [f.name for f in CODEX_PROMPTS.glob("*.md")]
    missing = [p for p in required_prompts if p not in existing]

    if missing:
        return False, f"Codex missing prompts: {missing}"

    return True, f"Codex CLI: MCP configured, {len(required_prompts)} prompts present"


def validate_sync_tool() -> Tuple[bool, str]:
    """Check quint_brain_sync.py exists and works."""
    sync_tool = BASE_DIR / "quint_brain_sync.py"

    if not sync_tool.exists():
        return False, "quint_brain_sync.py not found"

    # Try running with --status
    try:
        result = subprocess.run(
            ["python3", str(sync_tool), "--status"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        if result.returncode == 0:
            return True, "quint_brain_sync.py functional"
        return False, f"quint_brain_sync.py error: {result.stderr[:100]}"
    except Exception as e:
        return False, f"quint_brain_sync.py failed: {str(e)}"


def validate_gemini_bridge() -> Tuple[bool, str]:
    """Check gemini_quint_bridge.py exists and works."""
    bridge = BASE_DIR / "gemini_quint_bridge.py"

    if not bridge.exists():
        return False, "gemini_quint_bridge.py not found"

    # Try running with status
    try:
        result = subprocess.run(
            ["python3", str(bridge), "status", "--json"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        if result.returncode == 0:
            return True, "gemini_quint_bridge.py functional"
        return False, f"gemini_quint_bridge.py error: {result.stderr[:100]}"
    except Exception as e:
        return False, f"gemini_quint_bridge.py failed: {str(e)}"


def run_all_validations() -> Dict[str, Tuple[bool, str]]:
    """Run all validation checks."""
    validations = {
        "Quint Code Binary": validate_quint_code_installation,
        ".quint/ Directory": validate_quint_directory,
        "Brain/Reasoning/": validate_brain_reasoning,
        "Claude Code Skills": validate_claude_code,
        "Gemini CLI Setup": validate_gemini_cli,
        "Codex CLI Setup": validate_codex_cli,
        "Sync Tool": validate_sync_tool,
        "Gemini Bridge": validate_gemini_bridge,
    }

    results = {}
    for name, validator in validations.items():
        try:
            results[name] = validator()
        except Exception as e:
            results[name] = (False, f"Exception: {str(e)}")

    return results


def print_report(results: Dict[str, Tuple[bool, str]]):
    """Print validation report."""
    print("\n" + "=" * 60)
    print("CROSS-CLI SYNC VALIDATION REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    passed = 0
    failed = 0

    for name, (status, message) in results.items():
        icon = check_icon(status)
        print(f"\n{icon} {name}")
        print(f"    {message}")
        if status:
            passed += 1
        else:
            failed += 1

    print("\n" + "-" * 60)
    print(f"SUMMARY: {passed} passed, {failed} failed")

    if failed == 0:
        print("\nAll CLIs are properly configured for FPF sync!")
    else:
        print(
            "\nSome configurations need attention. Run with --fix to attempt repairs."
        )

    print("=" * 60 + "\n")

    return failed == 0


def quick_status():
    """Quick status check."""
    print("\nQuick FPF Cross-CLI Status:")
    print("-" * 40)

    checks = [
        ("quint-code", validate_quint_code_installation),
        (".quint/", validate_quint_directory),
        ("Brain/Reasoning/", validate_brain_reasoning),
        ("Claude Code", validate_claude_code),
        ("Gemini CLI", validate_gemini_cli),
        ("Codex CLI", validate_codex_cli),
    ]

    for name, check in checks:
        status, _ = check()
        icon = "[OK]" if status else "[--]"
        print(f"  {icon} {name}")

    print("-" * 40 + "\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate FPF cross-CLI sync configuration"
    )
    parser.add_argument("--check", action="store_true", help="Quick status check")
    parser.add_argument(
        "--fix", action="store_true", help="Attempt to fix issues (not implemented)"
    )

    args = parser.parse_args()

    if args.check:
        quick_status()
        return 0

    if args.fix:
        print("Auto-fix not yet implemented. Please manually fix issues.")
        return 1

    results = run_all_validations()
    success = print_report(results)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
