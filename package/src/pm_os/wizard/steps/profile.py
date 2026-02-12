"""
Profile Step

Collect user profile information.
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pm_os.wizard.orchestrator import WizardOrchestrator


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_name(name: str) -> bool:
    """Validate name is not empty and reasonable."""
    return len(name.strip()) >= 2


def validate_timezone_input(timezone: str) -> bool:
    """Validate timezone format."""
    from pm_os.wizard.validators import validate_timezone
    is_valid, _ = validate_timezone(timezone)
    return is_valid


ROLE_CHOICES = [
    "Product Manager",
    "Senior Product Manager",
    "Group Product Manager",
    "Director of Product",
    "VP of Product",
    "Engineering Manager",
    "Software Engineer",
    "Other"
]


def profile_step(wizard: "WizardOrchestrator") -> bool:
    """Collect user profile information.

    Returns:
        True to continue, False to abort
    """
    # Quick mode: auto-detect from git and use defaults
    if wizard.quick_mode:
        return _quick_profile_step(wizard)

    wizard.console.print("[bold]Let's set up your profile.[/bold]")
    wizard.console.print("[dim]This information is used to personalize PM-OS and stored locally.[/dim]")
    wizard.console.print()

    confirmed = False
    while not confirmed:
        # Check for existing data (resume case)
        existing_name = wizard.get_data("user_name", "")
        existing_email = wizard.get_data("user_email", "")
        existing_role = wizard.get_data("user_role", "")
        existing_team = wizard.get_data("user_team", "")
        existing_timezone = wizard.get_data("user_timezone", "UTC")

        # Show current values on resume
        if any([existing_name, existing_email, existing_role]):
            wizard.console.print("[dim]Current values (press Enter to keep):[/dim]")
            if existing_name:
                wizard.console.print(f"  [dim]Name: {existing_name}[/dim]")
            if existing_email:
                wizard.console.print(f"  [dim]Email: {existing_email}[/dim]")
            if existing_role:
                wizard.console.print(f"  [dim]Role: {existing_role}[/dim]")
            if existing_team:
                wizard.console.print(f"  [dim]Team: {existing_team}[/dim]")
            if existing_timezone:
                wizard.console.print(f"  [dim]Timezone: {existing_timezone}[/dim]")
            wizard.console.print()

        # Collect name
        name = wizard.ui.prompt_text(
            "Your full name",
            default=existing_name,
            required=True,
            validator=validate_name,
            error_message="Name must be at least 2 characters"
        )

        # Collect email
        email = wizard.ui.prompt_text(
            "Your email address",
            default=existing_email,
            required=True,
            validator=validate_email,
            error_message="Please enter a valid email address"
        )

        # Collect role
        wizard.console.print()
        role = wizard.ui.prompt_choice(
            "What is your role?",
            choices=ROLE_CHOICES,
            default=existing_role if existing_role in ROLE_CHOICES else "Product Manager"
        )

        # If "Other" selected, ask for custom role
        if role == "Other":
            role = wizard.ui.prompt_text(
                "Please specify your role",
                required=True
            )

        # Optional: Team/Organization
        wizard.console.print()
        team = wizard.ui.prompt_text(
            "Your team or organization (optional)",
            default=wizard.get_data("user_team", "")
        )

        # Optional: Timezone with validation
        timezone = wizard.ui.prompt_text(
            "Your timezone (e.g., America/New_York, Europe/Berlin)",
            default=existing_timezone,
            validator=validate_timezone_input,
            error_message="Invalid timezone. Use format like 'America/New_York' or 'UTC'"
        )

        # Store profile data
        wizard.update_data({
            "user_name": name,
            "user_email": email,
            "user_role": role,
            "user_team": team,
            "user_timezone": timezone
        })

        # Show summary
        wizard.console.print()
        wizard.ui.show_summary_table("Profile Summary", {
            "Name": name,
            "Email": email,
            "Role": role,
            "Team": team or "(not set)",
            "Timezone": timezone
        })

        wizard.console.print()

        # Confirm - use while loop instead of recursion to avoid stack overflow
        confirmed = wizard.ui.prompt_confirm("Is this information correct?", default=True)
        if not confirmed:
            wizard.console.print()
            wizard.ui.print_info("Let's update your profile information.")
            wizard.console.print()

    wizard.ui.print_success("Profile saved!")
    return True


def _quick_profile_step(wizard: "WizardOrchestrator") -> bool:
    """Quick mode profile setup with git auto-detection.

    Returns:
        True to continue, False to abort
    """
    from pm_os.wizard.git_utils import get_git_user_info

    wizard.console.print("[bold]Quick Profile Setup[/bold]")
    wizard.console.print("[dim]Auto-detecting from git config...[/dim]")
    wizard.console.print()

    # Try to auto-detect from git
    git_name, git_email = get_git_user_info()

    if git_name and git_email:
        wizard.ui.print_success(f"Detected: {git_name} <{git_email}>")
        wizard.console.print()

        # Show what we found and confirm
        wizard.ui.show_summary_table("Auto-detected Profile", {
            "Name": git_name,
            "Email": git_email,
            "Role": "Product Manager (default)",
            "Timezone": "UTC (default)"
        })

        wizard.console.print()

        if wizard.ui.prompt_confirm("Use this profile?", default=True):
            wizard.update_data({
                "user_name": git_name,
                "user_email": git_email,
                "user_role": "Product Manager",
                "user_team": "",
                "user_timezone": "UTC"
            })
            wizard.ui.print_success("Profile saved!")
            return True

    # Fall back to minimal prompts if git detection failed or user declined
    wizard.console.print()
    if not git_name or not git_email:
        wizard.ui.print_info("Could not auto-detect from git. Please enter manually.")
    else:
        wizard.ui.print_info("Please enter your profile information.")
    wizard.console.print()

    # Minimal prompts - just name and email
    name = wizard.ui.prompt_text(
        "Your full name",
        default=git_name or "",
        required=True,
        validator=validate_name,
        error_message="Name must be at least 2 characters"
    )

    email = wizard.ui.prompt_text(
        "Your email address",
        default=git_email or "",
        required=True,
        validator=validate_email,
        error_message="Please enter a valid email address"
    )

    # Use defaults for other fields in quick mode
    wizard.update_data({
        "user_name": name,
        "user_email": email,
        "user_role": "Product Manager",
        "user_team": "",
        "user_timezone": "UTC"
    })

    wizard.ui.print_success("Profile saved!")
    return True
