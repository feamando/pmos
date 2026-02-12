"""
Brain Population Step

Initial population of the PM-OS brain from configured integrations.
"""

import time
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Callable

if TYPE_CHECKING:
    from pm_os.wizard.orchestrator import WizardOrchestrator


def brain_population_step(wizard: "WizardOrchestrator") -> bool:
    """Populate the brain from integrations.

    Returns:
        True to continue, False to abort
    """
    wizard.console.print("[bold]Brain Population[/bold]")
    wizard.console.print()

    # Check what integrations are configured
    configured = wizard.get_data("integrations_configured", [])

    if not configured:
        wizard.ui.print_info("No integrations configured. Skipping brain population.")
        wizard.console.print()
        wizard.ui.print_info("You can populate the brain later with: pm-os brain sync")
        return True

    # Estimate time
    estimated_minutes = len(configured) * 2  # ~2 minutes per integration

    wizard.ui.show_time_warning(estimated_minutes)

    # Confirm population
    if not wizard.ui.prompt_confirm("Populate brain from configured integrations?", default=True):
        wizard.ui.print_skip("Brain population")
        wizard.console.print()
        wizard.ui.print_info("You can populate the brain later with: pm-os brain sync")
        return True

    wizard.console.print()

    # Create user entity first
    wizard.console.print("[bold]Creating user entity...[/bold]")
    create_user_entity(wizard)
    wizard.ui.print_success("User entity created")

    # Track results
    results = []
    brain_path = wizard.get_install_path() / "brain"

    # Jira sync
    if "Jira" in configured:
        wizard.console.print()
        wizard.console.print("[bold]Syncing from Jira...[/bold]")
        success, message = sync_jira_real(wizard, brain_path)
        results.append(("Jira", success, message))
        if success:
            wizard.ui.print_success(f"Jira: {message}")
        else:
            wizard.ui.print_warning(f"Jira: {message}")

    # Slack sync
    if "Slack" in configured:
        wizard.console.print()
        wizard.console.print("[bold]Syncing from Slack...[/bold]")
        success, message = sync_slack_real(wizard, brain_path)
        results.append(("Slack", success, message))
        if success:
            wizard.ui.print_success(f"Slack: {message}")
        else:
            wizard.ui.print_warning(f"Slack: {message}")

    # GitHub sync
    if "GitHub" in configured:
        wizard.console.print()
        wizard.console.print("[bold]Syncing from GitHub...[/bold]")
        success, message = sync_github_real(wizard, brain_path)
        results.append(("GitHub", success, message))
        if success:
            wizard.ui.print_success(f"GitHub: {message}")
        else:
            wizard.ui.print_warning(f"GitHub: {message}")

    # Google sync
    if "Google" in configured:
        wizard.console.print()
        wizard.console.print("[bold]Syncing from Google...[/bold]")
        success, message = sync_google_real(wizard, brain_path)
        results.append(("Google", success, message))
        if success:
            wizard.ui.print_success(f"Google: {message}")
        else:
            wizard.ui.print_warning(f"Google: {message}")

    # Confluence sync
    if "Confluence" in configured:
        wizard.console.print()
        wizard.console.print("[bold]Syncing from Confluence...[/bold]")
        success, message = sync_confluence_real(wizard, brain_path)
        results.append(("Confluence", success, message))
        if success:
            wizard.ui.print_success(f"Confluence: {message}")
        else:
            wizard.ui.print_warning(f"Confluence: {message}")

    # Summary
    wizard.console.print()
    successful = sum(1 for _, success, _ in results if success)
    wizard.ui.print_info(f"Brain population complete: {successful}/{len(results)} integrations synced")

    # Store results
    wizard.set_data("brain_sync_results", results)

    return True


def create_user_entity(wizard: "WizardOrchestrator") -> None:
    """Create the user entity in the brain."""
    base_path = wizard.get_install_path()
    people_path = base_path / "brain" / "Entities" / "People"
    people_path.mkdir(parents=True, exist_ok=True)

    name = wizard.get_data("user_name", "User")
    email = wizard.get_data("user_email", "")
    role = wizard.get_data("user_role", "")
    team = wizard.get_data("user_team", "")

    # Create filename from name
    filename = name.replace(" ", "_") + ".md"

    content = f"""---
type: person
name: {name}
email: {email}
role: {role}
team: {team}
is_self: true
created: {time.strftime('%Y-%m-%d')}
last_sync: {time.strftime('%Y-%m-%dT%H:%M:%S')}
---

# {name}

## Profile

- **Email**: {email}
- **Role**: {role}
{"- **Team**: " + team if team else ""}

## Relationships

<!-- Relationships will be added as entities are synced -->

## Notes

This is your user entity. PM-OS uses this to personalize interactions and track your context.

---
*Created by PM-OS installation wizard*
"""

    (people_path / filename).write_text(content)
    wizard.track_file(people_path / filename)


def sync_jira_real(wizard: "WizardOrchestrator", brain_path: Path) -> tuple:
    """Sync data from Jira using the real API."""
    try:
        from pm_os.wizard.brain_sync.jira_sync import JiraSyncer

        jira_url = wizard.get_data("jira_url", "")
        jira_email = wizard.get_data("jira_email", "")
        jira_token = wizard.get_data("jira_token", "")
        projects = wizard.get_data("jira_projects", "")

        if not all([jira_url, jira_email, jira_token]):
            return False, "Missing Jira credentials"

        project_list = [p.strip() for p in projects.split(",") if p.strip()] if projects else None

        syncer = JiraSyncer(
            brain_path=brain_path,
            url=jira_url,
            email=jira_email,
            token=jira_token,
            projects=project_list
        )

        # Test connection first
        connected, msg = syncer.test_connection()
        if not connected:
            return False, msg

        # Run sync with progress
        def progress_callback(current: int, total: int, phase: str):
            wizard.console.print(f"  [dim]{phase} ({current}/{total})[/dim]", end="\r")

        result = syncer.sync(progress_callback=progress_callback)
        wizard.console.print()  # Clear progress line

        return result.to_tuple()

    except ImportError:
        return False, "Jira sync module not available"
    except Exception as e:
        return False, str(e)


def sync_slack_real(wizard: "WizardOrchestrator", brain_path: Path) -> tuple:
    """Sync data from Slack using the real API."""
    try:
        from pm_os.wizard.brain_sync.slack_sync import SlackSyncer

        slack_token = wizard.get_data("slack_token", "")
        channels = wizard.get_data("slack_channels", "")

        if not slack_token:
            return False, "Missing Slack token"

        channel_list = [c.strip() for c in channels.split(",") if c.strip()] if channels else None

        syncer = SlackSyncer(
            brain_path=brain_path,
            token=slack_token,
            channels=channel_list
        )

        # Test connection first
        connected, msg = syncer.test_connection()
        if not connected:
            return False, msg

        # Run sync with progress
        def progress_callback(current: int, total: int, phase: str):
            wizard.console.print(f"  [dim]{phase} ({current}/{total})[/dim]", end="\r")

        result = syncer.sync(progress_callback=progress_callback)
        wizard.console.print()

        return result.to_tuple()

    except ImportError:
        return False, "Slack sync module not available"
    except Exception as e:
        return False, str(e)


def sync_github_real(wizard: "WizardOrchestrator", brain_path: Path) -> tuple:
    """Sync data from GitHub using the real API."""
    try:
        from pm_os.wizard.brain_sync.github_sync import GitHubSyncer

        github_token = wizard.get_data("github_token", "")
        repos = wizard.get_data("github_repos", "")

        if not github_token:
            return False, "Missing GitHub token"

        repo_list = [r.strip() for r in repos.split(",") if r.strip()] if repos else None

        syncer = GitHubSyncer(
            brain_path=brain_path,
            token=github_token,
            repos=repo_list
        )

        # Test connection first
        connected, msg = syncer.test_connection()
        if not connected:
            return False, msg

        # Run sync with progress
        def progress_callback(current: int, total: int, phase: str):
            wizard.console.print(f"  [dim]{phase} ({current}/{total})[/dim]", end="\r")

        result = syncer.sync(progress_callback=progress_callback)
        wizard.console.print()

        return result.to_tuple()

    except ImportError:
        return False, "GitHub sync module not available"
    except Exception as e:
        return False, str(e)


def sync_google_real(wizard: "WizardOrchestrator", brain_path: Path) -> tuple:
    """Sync data from Google using the real API."""
    try:
        from pm_os.wizard.brain_sync.google_sync import GoogleSyncer

        creds_path = wizard.get_data("google_credentials_path", "")

        if not creds_path:
            return False, "Google credentials not configured. Run 'pm-os brain sync --integration google' after setting up OAuth."

        syncer = GoogleSyncer(
            brain_path=brain_path,
            credentials_path=Path(creds_path) if creds_path else None
        )

        # Test connection first
        connected, msg = syncer.test_connection()
        if not connected:
            return False, msg

        # Run sync with progress
        def progress_callback(current: int, total: int, phase: str):
            wizard.console.print(f"  [dim]{phase} ({current}/{total})[/dim]", end="\r")

        result = syncer.sync(progress_callback=progress_callback)
        wizard.console.print()

        return result.to_tuple()

    except ImportError:
        return False, "Google sync requires: pip install google-auth google-auth-oauthlib google-api-python-client"
    except Exception as e:
        return False, str(e)


def sync_confluence_real(wizard: "WizardOrchestrator", brain_path: Path) -> tuple:
    """Sync data from Confluence using the real API."""
    try:
        from pm_os.wizard.brain_sync.confluence_sync import ConfluenceSyncer

        confluence_url = wizard.get_data("confluence_url", "")
        confluence_email = wizard.get_data("confluence_email", "")
        confluence_token = wizard.get_data("confluence_token", "")
        space = wizard.get_data("confluence_space", "")

        if not all([confluence_url, confluence_email, confluence_token]):
            return False, "Missing Confluence credentials"

        space_list = [space] if space else None

        syncer = ConfluenceSyncer(
            brain_path=brain_path,
            url=confluence_url,
            email=confluence_email,
            token=confluence_token,
            spaces=space_list
        )

        # Test connection first
        connected, msg = syncer.test_connection()
        if not connected:
            return False, msg

        # Run sync with progress
        def progress_callback(current: int, total: int, phase: str):
            wizard.console.print(f"  [dim]{phase} ({current}/{total})[/dim]", end="\r")

        result = syncer.sync(progress_callback=progress_callback)
        wizard.console.print()

        return result.to_tuple()

    except ImportError:
        return False, "Confluence sync module not available"
    except Exception as e:
        return False, str(e)
