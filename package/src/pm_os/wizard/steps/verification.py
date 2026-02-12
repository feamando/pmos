"""
Verification Step

Verify installation and show summary.
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
    """Check that .env has required variables."""
    env_path = base_path / ".env"

    if not env_path.exists():
        return False, ".env file not found"

    content = env_path.read_text()
    required_vars = ["PMOS_USER_NAME", "PMOS_LLM_PROVIDER"]

    missing = []
    for var in required_vars:
        if var not in content:
            missing.append(var)

    if missing:
        return False, f"Missing vars: {', '.join(missing)}"
    return True, "Environment configured"


def verification_step(wizard: "WizardOrchestrator") -> bool:
    """Verify installation and show summary.

    Returns:
        True to continue, False to abort
    """
    wizard.console.print("[bold]Verification[/bold]")
    wizard.console.print()

    base_path = wizard.get_install_path()
    user_name = wizard.get_data("user_name", "User")

    # Run verification checks
    checks = [
        ("Directory Structure", lambda: check_directory_structure(base_path)),
        ("Configuration Files", lambda: check_config_files(base_path)),
        ("Brain Files", lambda: check_brain_files(base_path)),
        ("User Entity", lambda: check_user_entity(base_path, user_name)),
        ("Environment", lambda: check_env_vars(base_path)),
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
        if not wizard.ui.prompt_confirm("Continue anyway?", default=False):
            return False

    # Show completion panel
    configured = wizard.get_data("integrations_configured", [])
    skipped = wizard.get_data("integrations_skipped", [])

    # Build integration status
    integration_lines = []
    if configured:
        integration_lines.append(f"✓ Configured: {', '.join(configured)}")
    if skipped:
        integration_lines.append(f"○ Skipped: {', '.join(skipped)}")

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
        "source .env  # Load environment variables",
        "pm-os doctor  # Verify installation",
        "pm-os brain sync  # Full brain sync (if integrations configured)",
        "claude  # Start Claude Code with PM-OS context",
    ]

    wizard.ui.show_completion_panel(
        "Installation Complete! 🎉",
        summary_content,
        next_steps
    )

    # Save completion timestamp
    from datetime import datetime
    wizard.set_data("completed_at", datetime.now().isoformat())

    return True
