"""
Integrations Step

Configure optional integrations (Jira, Slack, Google, GitHub, Confluence).
"""

import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pm_os.wizard.orchestrator import WizardOrchestrator


def validate_url(url: str) -> bool:
    """Validate URL format."""
    pattern = r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}.*$'
    return bool(re.match(pattern, url))


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def integrations_step(wizard: "WizardOrchestrator") -> bool:
    """Configure optional integrations.

    Returns:
        True to continue, False to abort
    """
    wizard.console.print("[bold]Configure Integrations[/bold]")
    wizard.console.print("[dim]All integrations are optional. You can configure them later.[/dim]")
    wizard.console.print()

    # Track configured integrations
    configured = []
    skipped = []

    # Jira
    if wizard.ui.prompt_skip_or_configure("Jira"):
        if configure_jira(wizard):
            configured.append("Jira")
        else:
            skipped.append("Jira")
    else:
        skipped.append("Jira")
        wizard.ui.print_skip("Jira")

    wizard.console.print()

    # Slack
    if wizard.ui.prompt_skip_or_configure("Slack"):
        if configure_slack(wizard):
            configured.append("Slack")
        else:
            skipped.append("Slack")
    else:
        skipped.append("Slack")
        wizard.ui.print_skip("Slack")

    wizard.console.print()

    # Google
    if wizard.ui.prompt_skip_or_configure("Google (Calendar, Drive, Gmail)"):
        if configure_google(wizard):
            configured.append("Google")
        else:
            skipped.append("Google")
    else:
        skipped.append("Google")
        wizard.ui.print_skip("Google")

    wizard.console.print()

    # GitHub
    if wizard.ui.prompt_skip_or_configure("GitHub"):
        if configure_github(wizard):
            configured.append("GitHub")
        else:
            skipped.append("GitHub")
    else:
        skipped.append("GitHub")
        wizard.ui.print_skip("GitHub")

    wizard.console.print()

    # Confluence
    if wizard.ui.prompt_skip_or_configure("Confluence"):
        if configure_confluence(wizard):
            configured.append("Confluence")
        else:
            skipped.append("Confluence")
    else:
        skipped.append("Confluence")
        wizard.ui.print_skip("Confluence")

    # Store integration status
    wizard.set_data("integrations_configured", configured)
    wizard.set_data("integrations_skipped", skipped)

    wizard.console.print()

    # Summary
    if configured:
        wizard.ui.print_success(f"Configured: {', '.join(configured)}")
    if skipped:
        wizard.ui.print_info(f"Skipped: {', '.join(skipped)}")

    wizard.console.print()
    wizard.ui.print_info("You can configure skipped integrations later with 'pm-os config'")

    return True


def configure_jira(wizard: "WizardOrchestrator") -> bool:
    """Configure Jira integration."""
    wizard.console.print()
    wizard.console.print("[bold]Jira Configuration[/bold]")
    wizard.console.print("[dim]Connect to Jira to sync issues and sprint data.[/dim]")
    wizard.console.print()

    # Jira URL
    url = wizard.ui.prompt_text(
        "Jira URL (e.g., https://company.atlassian.net)",
        default=wizard.get_data("jira_url") or os.environ.get("JIRA_URL", ""),
        required=True,
        validator=validate_url,
        error_message="Please enter a valid URL"
    )

    # Email
    email = wizard.ui.prompt_text(
        "Jira email",
        default=wizard.get_data("jira_email") or wizard.get_data("user_email", ""),
        required=True,
        validator=validate_email,
        error_message="Please enter a valid email"
    )

    # API Token
    wizard.console.print("[dim]Get your API token at: https://id.atlassian.com/manage-profile/security/api-tokens[/dim]")
    token = wizard.ui.prompt_password("Jira API token", required=True)

    # Projects (optional)
    projects = wizard.ui.prompt_text(
        "Jira projects to sync (comma-separated, or leave empty for all)",
        default=wizard.get_data("jira_projects", "")
    )

    wizard.update_data({
        "jira_url": url,
        "jira_email": email,
        "jira_token": token,
        "jira_projects": projects
    })

    wizard.ui.print_success("Jira configured!")
    return True


def configure_slack(wizard: "WizardOrchestrator") -> bool:
    """Configure Slack integration."""
    wizard.console.print()
    wizard.console.print("[bold]Slack Configuration[/bold]")
    wizard.console.print("[dim]Connect to Slack to capture mentions and post updates.[/dim]")
    wizard.console.print()

    # Bot token
    wizard.console.print("[dim]Create a Slack app at: https://api.slack.com/apps[/dim]")
    wizard.console.print("[dim]Required scopes: channels:history, channels:read, chat:write, users:read[/dim]")
    token = wizard.ui.prompt_password(
        "Slack Bot Token (xoxb-...)",
        required=True
    )

    # Bot user ID
    bot_user_id = wizard.ui.prompt_text(
        "Slack Bot User ID (e.g., U0123456789)",
        default=wizard.get_data("slack_bot_user_id", "")
    )

    # Channels to monitor
    channels = wizard.ui.prompt_text(
        "Slack channels to monitor (comma-separated IDs)",
        default=wizard.get_data("slack_channels", "")
    )

    wizard.update_data({
        "slack_bot_token": token,
        "slack_bot_user_id": bot_user_id,
        "slack_channels": channels
    })

    wizard.ui.print_success("Slack configured!")
    return True


def configure_google(wizard: "WizardOrchestrator") -> bool:
    """Configure Google integration."""
    wizard.console.print()
    wizard.console.print("[bold]Google Configuration[/bold]")
    wizard.console.print("[dim]Connect to Google Calendar, Drive, and Gmail.[/dim]")
    wizard.console.print()

    wizard.console.print("""
[yellow]Google OAuth Setup Steps:[/yellow]

1. Go to https://console.cloud.google.com/
2. Create a new project or select existing
3. Enable APIs: Calendar, Drive, Gmail
4. Create OAuth 2.0 credentials (Desktop app)
5. Download credentials.json

[dim]Place credentials.json in your PM-OS secrets folder.[/dim]
""")

    # Check if credentials file exists
    creds_path = wizard.ui.prompt_text(
        "Path to credentials.json (or press Enter to skip)",
        default=""
    )

    if creds_path:
        import os
        if os.path.exists(creds_path):
            wizard.set_data("google_credentials_path", creds_path)
            wizard.ui.print_success("Google credentials found!")
            return True
        else:
            wizard.ui.print_warning("File not found. You can add it later.")
            return False

    wizard.ui.print_info("Google integration skipped. Add credentials.json later.")
    return False


def configure_github(wizard: "WizardOrchestrator") -> bool:
    """Configure GitHub integration."""
    wizard.console.print()
    wizard.console.print("[bold]GitHub Configuration[/bold]")
    wizard.console.print("[dim]Connect to GitHub for PR and issue tracking.[/dim]")
    wizard.console.print()

    # Check for gh CLI
    import shutil
    if shutil.which("gh"):
        wizard.console.print("[dim]GitHub CLI (gh) detected. Checking authentication...[/dim]")
        import subprocess
        result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
        if result.returncode == 0:
            wizard.ui.print_success("Already authenticated with GitHub CLI!")
            wizard.set_data("github_auth_method", "gh_cli")

            # Get repositories to sync
            repos = wizard.ui.prompt_text(
                "GitHub repositories to sync (owner/repo, comma-separated)",
                default=wizard.get_data("github_repos", "")
            )
            wizard.set_data("github_repos", repos)
            return True

    # Personal access token
    wizard.console.print("[dim]Create a token at: https://github.com/settings/tokens[/dim]")
    wizard.console.print("[dim]Required scopes: repo, read:org[/dim]")
    token = wizard.ui.prompt_password("GitHub Personal Access Token", required=True)

    # Repositories
    repos = wizard.ui.prompt_text(
        "GitHub repositories to sync (owner/repo, comma-separated)",
        default=wizard.get_data("github_repos", "")
    )

    wizard.update_data({
        "github_token": token,
        "github_repos": repos,
        "github_auth_method": "token"
    })

    wizard.ui.print_success("GitHub configured!")
    return True


def configure_confluence(wizard: "WizardOrchestrator") -> bool:
    """Configure Confluence integration."""
    wizard.console.print()
    wizard.console.print("[bold]Confluence Configuration[/bold]")
    wizard.console.print("[dim]Connect to Confluence for documentation sync.[/dim]")
    wizard.console.print()

    # URL
    url = wizard.ui.prompt_text(
        "Confluence URL (e.g., https://company.atlassian.net/wiki)",
        default=wizard.get_data("confluence_url") or os.environ.get("CONFLUENCE_URL", ""),
        required=True,
        validator=validate_url,
        error_message="Please enter a valid URL"
    )

    # Email
    email = wizard.ui.prompt_text(
        "Confluence email",
        default=wizard.get_data("confluence_email") or wizard.get_data("user_email", ""),
        required=True,
        validator=validate_email,
        error_message="Please enter a valid email"
    )

    # API Token
    wizard.console.print("[dim]Use the same API token as Jira (Atlassian account)[/dim]")
    token = wizard.ui.prompt_password("Confluence API token", required=True)

    # Default space
    space = wizard.ui.prompt_text(
        "Default Confluence space key (e.g., TEAM)",
        default=wizard.get_data("confluence_space", "")
    )

    wizard.update_data({
        "confluence_url": url,
        "confluence_email": email,
        "confluence_token": token,
        "confluence_space": space
    })

    wizard.ui.print_success("Confluence configured!")
    return True
