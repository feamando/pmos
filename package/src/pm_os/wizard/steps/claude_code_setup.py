"""
Claude Code Setup Step

Configures Claude Code integration after common/ is downloaded:
- Creates user/.claude/ directory
- Symlinks commands to common/.claude/commands/
- Generates settings.local.json with starter permissions
- Generates .claude/env with PM_OS_ROOT, PM_OS_COMMON, PM_OS_USER, PYTHONPATH
- Links AGENT.md
"""

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pm_os.wizard.orchestrator import WizardOrchestrator


def claude_code_setup_step(wizard: "WizardOrchestrator") -> bool:
    """Set up Claude Code integration.

    Returns:
        True to continue, False to abort
    """
    user_dir = wizard.install_path
    common_dir_str = wizard.get_data("common_dir")

    if not common_dir_str:
        wizard.ui.print_warning("common/ not available — skipping Claude Code setup.")
        wizard.ui.print_info("Run 'pm-os init' again after downloading common/.")
        return True

    common_dir = Path(common_dir_str)
    root_dir_str = wizard.get_data("root_dir", str(user_dir))
    root_dir = Path(root_dir_str)

    wizard.console.print("[bold]Setting up Claude Code integration...[/bold]")
    wizard.console.print()

    # 1. Create .claude directory
    claude_dir = user_dir / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    # 2. Symlink commands
    _setup_commands_symlink(wizard, claude_dir, common_dir)

    # 3. Generate settings.local.json
    _generate_settings(wizard, claude_dir, common_dir)

    # 4. Generate .claude/env
    _generate_env(wizard, claude_dir, root_dir, common_dir, user_dir)

    # 5. Link AGENT.md
    _setup_agent_md(wizard, user_dir, common_dir)

    wizard.console.print()
    wizard.ui.print_success("Claude Code integration configured!")

    # Show summary
    commands_dir = claude_dir / "commands"
    command_count = 0
    if commands_dir.exists():
        target = commands_dir.resolve() if commands_dir.is_symlink() else commands_dir
        if target.exists():
            command_count = len(list(target.glob("*.md")))

    wizard.ui.show_summary_table("Claude Code Setup", {
        "Commands": f"{command_count} slash commands available",
        "Settings": str(claude_dir / "settings.local.json"),
        "Environment": str(claude_dir / "env"),
        "AGENT.md": "Linked" if (user_dir / "AGENT.md").exists() else "Not found",
    })

    return True


def _setup_commands_symlink(wizard: "WizardOrchestrator", claude_dir: Path, common_dir: Path):
    """Symlink commands directory."""
    commands_target = common_dir / ".claude" / "commands"
    commands_link = claude_dir / "commands"

    if not commands_target.exists():
        wizard.ui.print_warning("common/.claude/commands/ not found — skipping commands symlink")
        return

    # Remove existing link or directory
    if commands_link.exists() or commands_link.is_symlink():
        if commands_link.is_symlink():
            commands_link.unlink()
        else:
            import shutil
            shutil.rmtree(commands_link)

    # Create relative symlink
    try:
        rel_path = os.path.relpath(commands_target, claude_dir)
        commands_link.symlink_to(rel_path)
        command_count = len(list(commands_target.glob("*.md")))
        wizard.ui.print_success(f"Commands linked: {command_count} slash commands")
    except OSError as e:
        # Fallback: copy instead of symlink (Windows or permission issues)
        import shutil
        shutil.copytree(commands_target, commands_link)
        wizard.ui.print_success(f"Commands copied (symlink failed: {e})")


def _generate_settings(wizard: "WizardOrchestrator", claude_dir: Path, common_dir: Path):
    """Generate settings.local.json with starter permissions."""
    settings_path = claude_dir / "settings.local.json"

    # Don't overwrite if user has customized
    if settings_path.exists():
        wizard.ui.print_info("settings.local.json already exists (keeping)")
        return

    root_dir = wizard.get_data("root_dir", str(wizard.install_path))

    settings = {
        "permissions": {
            "allow": [
                # Python tool execution
                f"Bash(python3:{root_dir}/*)",
                f"Bash(python3:*pm_os*)",
                # Boot script
                f"Bash(source:{root_dir}/*/scripts/boot.sh*)",
                f"Bash(bash:{root_dir}/*/scripts/boot.sh*)",
                # Git operations
                "Bash(git:*)",
                # File operations within PM-OS
                f"Bash(ls:{root_dir}/*)",
                f"Bash(cat:{root_dir}/*)",
                # Common utilities
                "Bash(which:*)",
                "Bash(pip3:*pm-os*)",
                "Bash(pm-os:*)",
            ],
            "deny": []
        },
        "env": {
            "PM_OS_ROOT": root_dir,
            "PM_OS_COMMON": str(common_dir),
            "PM_OS_USER": str(wizard.install_path),
        }
    }

    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    wizard.ui.print_success("Generated settings.local.json (starter permissions)")


def _generate_env(
    wizard: "WizardOrchestrator",
    claude_dir: Path,
    root_dir: Path,
    common_dir: Path,
    user_dir: Path,
):
    """Generate .claude/env file for Claude Code environment."""
    env_path = claude_dir / "env"

    env_lines = [
        f"PM_OS_ROOT={root_dir}",
        f"PM_OS_COMMON={common_dir}",
        f"PM_OS_USER={user_dir}",
        f"PYTHONPATH={common_dir / 'tools'}",
    ]

    env_path.write_text("\n".join(env_lines) + "\n")
    wizard.ui.print_success("Generated .claude/env (PM_OS_ROOT, PM_OS_COMMON, PM_OS_USER, PYTHONPATH)")


def _setup_agent_md(wizard: "WizardOrchestrator", user_dir: Path, common_dir: Path):
    """Link or copy AGENT.md to user directory."""
    agent_source = common_dir / "AGENT.md"
    agent_target = user_dir / "AGENT.md"

    if not agent_source.exists():
        wizard.ui.print_warning("AGENT.md not found in common/")
        return

    if agent_target.exists() or agent_target.is_symlink():
        if agent_target.is_symlink():
            agent_target.unlink()
        else:
            agent_target.unlink()

    # Create relative symlink
    try:
        rel_path = os.path.relpath(agent_source, user_dir)
        agent_target.symlink_to(rel_path)
        wizard.ui.print_success("AGENT.md linked")
    except OSError:
        # Fallback: copy
        import shutil
        shutil.copy2(agent_source, agent_target)
        wizard.ui.print_success("AGENT.md copied")
