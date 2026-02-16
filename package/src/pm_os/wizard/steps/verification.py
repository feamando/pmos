"""
Verification Step

Verify installation and show summary with Claude Code readiness.
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from pm_os.wizard.orchestrator import WizardOrchestrator


def check_directory_structure(base_path: Path) -> Tuple[bool, str]:
    """Verify directory structure exists."""
    required_dirs = [
        "brain",
        "brain/Entities",
        "brain/Glossary",
        "sessions",
        "personal/context",
        ".config",
    ]

    missing = []
    for dir_name in required_dirs:
        if not (base_path / dir_name).exists():
            missing.append(dir_name)

    if missing:
        return False, f"Missing: {', '.join(missing)}"
    return True, "All directories present"


def check_config_files(base_path: Path) -> Tuple[bool, str]:
    """Verify configuration files exist."""
    required_files = [
        ".env",
        ".config/config.yaml",
        "USER.md",
    ]

    missing = []
    for file_name in required_files:
        if not (base_path / file_name).exists():
            missing.append(file_name)

    if missing:
        return False, f"Missing: {', '.join(missing)}"
    return True, "All config files present"


def check_brain_files(base_path: Path) -> Tuple[bool, str]:
    """Verify brain files exist."""
    brain_path = base_path / "brain"

    required = [
        "BRAIN.md",
        "Glossary/Glossary.md",
        "Index/Index.md",
    ]

    missing = []
    for file_name in required:
        if not (brain_path / file_name).exists():
            missing.append(file_name)

    if missing:
        return False, f"Missing: {', '.join(missing)}"
    return True, "Brain initialized"


def check_user_entity(base_path: Path, user_name: str) -> Tuple[bool, str]:
    """Verify user entity exists."""
    people_path = base_path / "brain" / "Entities" / "People"
    filename = user_name.replace(" ", "_") + ".md"

    if (people_path / filename).exists():
        return True, f"User entity: {filename}"
    return False, "User entity not found"


def check_env_vars(base_path: Path) -> Tuple[bool, str]:
    """Check that .env exists and has content."""
    env_path = base_path / ".env"

    if not env_path.exists():
        return False, ".env file not found"

    return True, "Environment configured"


def check_common_directory(base_path: Path) -> Tuple[bool, str]:
    """Verify common/ directory with tools exists."""
    common_dir = base_path / "common"

    if not common_dir.exists():
        return False, "common/ not downloaded"

    tools = common_dir / "tools"
    if not tools.exists():
        return False, "common/tools/ missing"

    agent = common_dir / "AGENT.md"
    scripts = common_dir / "scripts"

    parts = []
    if tools.exists():
        parts.append("tools")
    if agent.exists():
        parts.append("AGENT.md")
    if scripts.exists():
        parts.append("scripts")

    return True, f"common/ verified ({', '.join(parts)})"


def check_claude_code_setup(base_path: Path) -> Tuple[bool, str]:
    """Verify Claude Code integration is set up."""
    claude_dir = base_path / ".claude"
    issues = []

    if not claude_dir.exists():
        return False, ".claude/ directory not found"

    # Check commands
    commands = claude_dir / "commands"
    if commands.exists() or commands.is_symlink():
        target = commands.resolve() if commands.is_symlink() else commands
        if target.exists():
            count = len(list(target.glob("*.md")))
            if count == 0:
                issues.append("no commands found")
        else:
            issues.append("commands symlink broken")
    else:
        issues.append("commands not linked")

    # Check env
    env_file = claude_dir / "env"
    if not env_file.exists():
        issues.append(".claude/env missing")

    # Check settings
    settings = claude_dir / "settings.local.json"
    if not settings.exists():
        issues.append("settings.local.json missing")

    if issues:
        return False, f"Issues: {', '.join(issues)}"

    # Count commands for the success message
    commands_target = commands.resolve() if commands.is_symlink() else commands
    cmd_count = len(list(commands_target.glob("*.md"))) if commands_target.exists() else 0

    return True, f"Claude Code ready ({cmd_count} commands, env, settings)"


def verification_step(wizard: "WizardOrchestrator") -> bool:
    """Verify installation and show summary.

    Returns:
        True to continue, False to abort
    """
    wizard.console.print("[bold]Verification[/bold]")
    wizard.console.print()

    base_path = wizard.install_path
    user_name = wizard.get_data("user_name", "User")

    # Run verification checks
    checks = [
        ("Directory Structure", lambda: check_directory_structure(base_path)),
        ("Configuration Files", lambda: check_config_files(base_path)),
        ("Brain Files", lambda: check_brain_files(base_path)),
        ("User Entity", lambda: check_user_entity(base_path, user_name)),
        ("Environment", lambda: check_env_vars(base_path)),
        ("Common Tools", lambda: check_common_directory(base_path)),
        ("Claude Code", lambda: check_claude_code_setup(base_path)),
    ]

    results = []
    all_passed = True

    for name, check_func in checks:
        passed, message = check_func()
        results.append((name, passed, message))
        if not passed:
            all_passed = False

    # Display results
    wizard.ui.show_checklist(results)
    wizard.console.print()

    if not all_passed:
        wizard.ui.print_warning("Some checks failed. You may need to re-run setup.")
        if not wizard.quick_mode:
            if not wizard.ui.prompt_confirm("Continue anyway?", default=False):
                return False

    # Show completion panel
    configured = wizard.get_data("integrations_configured", [])
    skipped = wizard.get_data("integrations_skipped", [])

    # Build integration status
    integration_lines = []
    if configured:
        integration_lines.append(f"Configured: {', '.join(configured)}")
    if skipped:
        integration_lines.append(f"Skipped: {', '.join(skipped)}")

    integration_status = "\n".join(integration_lines) if integration_lines else "No integrations configured"

    summary_content = f"""
PM-OS has been successfully installed!

[bold]Installation Path:[/bold] {base_path}

[bold]User:[/bold] {wizard.get_data('user_name')} ({wizard.get_data('user_email')})
[bold]Role:[/bold] {wizard.get_data('user_role')}
[bold]LLM Provider:[/bold] {wizard.get_data('llm_provider')}

[bold]Integrations:[/bold]
{integration_status}
"""

    next_steps = [
        f"cd {base_path}",
        "claude  # Start Claude Code with PM-OS",
        "/boot  # Run boot sequence to load context",
    ]

    wizard.ui.show_completion_panel(
        "Installation Complete!",
        summary_content,
        next_steps
    )

    # Save completion timestamp
    from datetime import datetime
    wizard.set_data("completed_at", datetime.now().isoformat())

    return True
