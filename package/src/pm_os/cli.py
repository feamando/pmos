"""
PM-OS Command Line Interface

Main entry point for the pm-os CLI.
"""

import os
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()


def get_default_install_path() -> Path:
    """Get the default installation path."""
    return Path(os.environ.get("PM_OS_USER", Path.home() / "pm-os"))


@click.group()
@click.version_option(package_name="pm-os")
def main():
    """PM-OS: AI-powered Product Management Operating System"""
    pass


@main.command()
@click.option("--resume", is_flag=True, help="Resume interrupted installation")
@click.option("--quick", "-q", is_flag=True, help="Quick setup - auto-detect profile, skip optional steps")
@click.option("--template", type=click.Path(exists=True), help="Use config template for silent install")
@click.option("--path", type=click.Path(), help="Installation path (default: ~/pm-os)")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def init(resume: bool, quick: bool, template: str, path: str, verbose: bool):
    """Initialize PM-OS with guided wizard.

    Use --quick for fast setup (~5 min) that:
    - Auto-detects name/email from git config
    - Skips optional integrations (can add later)
    - Skips initial brain population (can sync later)

    Examples:
        pm-os init           # Full guided setup
        pm-os init --quick   # Quick setup (~5 min)
        pm-os init --resume  # Resume interrupted setup
    """
    from pm_os.wizard import WizardOrchestrator
    from pm_os.wizard.steps import WIZARD_STEPS

    # Determine install path
    install_path = Path(path) if path else get_default_install_path()

    # Handle template-based silent install
    if template:
        import yaml
        try:
            template_path = Path(template)
            template_config = yaml.safe_load(template_path.read_text())
            success = run_silent_install(install_path, template_config, verbose)
            sys.exit(0 if success else 1)
        except Exception as e:
            console.print(f"[red]Error loading template:[/red] {e}")
            sys.exit(1)

    # Create and configure wizard
    wizard = WizardOrchestrator(console=console, install_path=install_path, quick_mode=quick)

    # Add all steps
    for step in WIZARD_STEPS:
        wizard.add_step(
            name=step["name"],
            title=step["title"],
            description=step["description"],
            handler=step["handler"],
            skippable=step.get("skippable", False),
        )

    # Run wizard
    try:
        success = wizard.run(resume=resume)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        # Already handled by signal handler
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


def run_silent_install(install_path: Path, config: dict, verbose: bool = False) -> bool:
    """Run silent install from template config."""
    import yaml

    console.print("[bold blue]PM-OS Silent Installation[/bold blue]")
    console.print()

    try:
        # Create directory structure
        dirs = ["brain", "brain/Entities", "brain/Context", ".config", ".secrets"]
        entity_dirs = ["People", "Projects", "Issues", "Channels", "Documents"]

        for d in dirs:
            (install_path / d).mkdir(parents=True, exist_ok=True)
            if verbose:
                console.print(f"[dim]Created: {install_path / d}[/dim]")

        for d in entity_dirs:
            (install_path / "brain" / "Entities" / d).mkdir(parents=True, exist_ok=True)

        # Write config.yaml
        config_path = install_path / ".config" / "config.yaml"
        config_path.write_text(yaml.dump(config, default_flow_style=False))
        if verbose:
            console.print(f"[dim]Wrote: {config_path}[/dim]")

        # Write .env file with secrets
        env_path = install_path / ".env"
        env_content = []

        # Extract LLM credentials
        llm = config.get("llm", {})
        if llm.get("provider") == "anthropic" and "api_key" in llm:
            env_content.append(f"ANTHROPIC_API_KEY={llm['api_key']}")
        elif llm.get("provider") == "openai" and "api_key" in llm:
            env_content.append(f"OPENAI_API_KEY={llm['api_key']}")

        # Extract integration credentials
        integrations = config.get("integrations", {})
        for name, cfg in integrations.items():
            if name == "jira" and cfg.get("enabled"):
                if cfg.get("token"):
                    env_content.append(f"JIRA_TOKEN={cfg['token']}")
            elif name == "slack" and cfg.get("enabled"):
                if cfg.get("token"):
                    env_content.append("SLACK_BOT_" + f"TOKEN={cfg['token']}")
            elif name == "github" and cfg.get("enabled"):
                if cfg.get("token"):
                    env_content.append(f"GITHUB_TOKEN={cfg['token']}")

        if env_content:
            env_path.write_text("\n".join(env_content) + "\n")
            os.chmod(env_path, 0o600)  # Secure permissions
            if verbose:
                console.print(f"[dim]Wrote: {env_path} (600 permissions)[/dim]")

        # Write .gitignore
        gitignore_path = install_path / ".gitignore"
        gitignore_content = ".env\n.secrets/\n*.log\n.sync_state.json\n"
        gitignore_path.write_text(gitignore_content)

        console.print()
        console.print(f"[green]✓[/green] PM-OS installed to {install_path}")
        console.print()
        console.print("[bold]Next steps:[/bold]")
        console.print("  1. Run 'pm-os doctor' to verify installation")
        console.print("  2. Run 'pm-os brain sync' to populate brain")

        return True

    except Exception as e:
        console.print(f"[red]Silent install failed:[/red] {e}")
        return False


@main.command()
@click.option("--check", is_flag=True, help="Check for updates without installing")
def update(check: bool):
    """Update PM-OS to the latest version."""
    import subprocess

    if check:
        console.print("[bold blue]Checking for PM-OS updates...[/bold blue]")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "index", "versions", "pm-os"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                console.print(result.stdout)
            else:
                # Fallback to pip show
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "show", "pm-os"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    console.print(result.stdout)
                else:
                    console.print("[yellow]Could not check for updates[/yellow]")
        except Exception as e:
            console.print(f"[red]Error checking updates:[/red] {e}")
    else:
        console.print("[bold blue]Updating PM-OS...[/bold blue]")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "pm-os"],
                capture_output=False,
                timeout=120
            )
            if result.returncode == 0:
                console.print("[green]PM-OS updated successfully![/green]")
            else:
                console.print("[red]Update failed[/red]")
                sys.exit(1)
        except Exception as e:
            console.print(f"[red]Error updating:[/red] {e}")
            sys.exit(1)


@main.command()
@click.option("--fix", is_flag=True, help="Attempt to fix common issues")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def doctor(fix: bool, verbose: bool, json_output: bool):
    """Verify PM-OS installation health."""
    from pm_os.wizard.steps.prerequisites import (
        check_python_version,
        check_pip,
        check_git,
        check_claude_code,
        check_aws_cli,
    )
    from pm_os.wizard.steps.verification import (
        check_directory_structure,
        check_config_files,
        check_brain_files,
        check_env_vars,
    )
    import json

    install_path = get_default_install_path()
    results = {"system": {}, "installation": {}, "fixed": []}
    all_passed = True

    # System checks
    system_checks = [
        ("Python", check_python_version),
        ("pip", check_pip),
        ("Git", check_git),
        ("Claude Code", check_claude_code),
        ("AWS CLI", check_aws_cli),
    ]

    if not json_output:
        console.print("[bold blue]PM-OS Doctor[/bold blue]")
        console.print()
        console.print("[bold]System Requirements:[/bold]")

    for name, check_func in system_checks:
        passed, message = check_func()
        results["system"][name] = {"passed": passed, "message": message}
        if not passed:
            all_passed = False
        if not json_output:
            icon = "[green]✓[/green]" if passed else "[red]✗[/red]"
            console.print(f"  {icon} {name}: {message}")

    if not json_output:
        console.print()

    # Installation checks
    if install_path.exists():
        if not json_output:
            console.print(f"[bold]Installation ({install_path}):[/bold]")

        install_checks = [
            ("Directories", lambda: check_directory_structure(install_path)),
            ("Config Files", lambda: check_config_files(install_path)),
            ("Brain Files", lambda: check_brain_files(install_path)),
            ("Environment", lambda: check_env_vars(install_path)),
        ]

        for name, check_func in install_checks:
            passed, message = check_func()
            results["installation"][name] = {"passed": passed, "message": message}
            if not passed:
                all_passed = False

            if not json_output:
                icon = "[green]✓[/green]" if passed else "[red]✗[/red]"
                console.print(f"  {icon} {name}: {message}")

            # Attempt fixes
            if fix and not passed:
                fixed = attempt_fix(name, install_path, verbose)
                if fixed:
                    results["fixed"].append(name)
                    if not json_output:
                        console.print(f"    [green]→ Fixed: {name}[/green]")
    else:
        results["installation"]["exists"] = {"passed": False, "message": "Not installed"}
        all_passed = False
        if not json_output:
            console.print(f"[yellow]PM-OS not installed at {install_path}[/yellow]")
            console.print("Run 'pm-os init' to install.")

    if json_output:
        results["all_passed"] = all_passed
        print(json.dumps(results, indent=2))
    else:
        console.print()
        if all_passed:
            console.print("[green]All checks passed! PM-OS is healthy.[/green]")
        else:
            console.print("[yellow]Some checks failed.[/yellow]")
            if not fix:
                console.print("[dim]Run with --fix to attempt auto-repair.[/dim]")

    sys.exit(0 if all_passed else 1)


def attempt_fix(issue_name: str, install_path: Path, verbose: bool = False) -> bool:
    """Attempt to fix a specific issue."""
    try:
        if issue_name == "Directories":
            # Create missing directories
            dirs = ["brain", "brain/Entities", "brain/Context", ".config", ".secrets"]
            entity_dirs = ["People", "Projects", "Issues", "Channels", "Documents"]
            for d in dirs:
                (install_path / d).mkdir(parents=True, exist_ok=True)
            for d in entity_dirs:
                (install_path / "brain" / "Entities" / d).mkdir(parents=True, exist_ok=True)
            return True

        elif issue_name == "Environment":
            # Create .env if missing
            env_path = install_path / ".env"
            if not env_path.exists():
                env_path.write_text("# PM-OS Environment Variables\n")
                os.chmod(env_path, 0o600)
            return True

        elif issue_name == "Config Files":
            # Create default config if missing
            config_path = install_path / ".config" / "config.yaml"
            if not config_path.exists():
                import yaml
                default_config = {
                    "user": {"name": "", "email": "", "role": ""},
                    "llm": {"provider": "anthropic", "model": "claude-sonnet-4-20250514"},
                    "integrations": {}
                }
                config_path.parent.mkdir(parents=True, exist_ok=True)
                config_path.write_text(yaml.dump(default_config, default_flow_style=False))
            return True

    except Exception as e:
        if verbose:
            console.print(f"[dim]Fix failed for {issue_name}: {e}[/dim]")

    return False


@main.group()
def brain():
    """Brain knowledge graph commands."""
    pass


@brain.command()
@click.option("--integration", "-i", help="Sync specific integration only")
@click.option("--dry-run", is_flag=True, help="Show what would be synced")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def sync(integration: str, dry_run: bool, verbose: bool):
    """Sync brain entities from integrations."""
    console.print("[bold blue]Brain Sync[/bold blue]")
    console.print()

    install_path = get_default_install_path()
    brain_path = install_path / "brain"

    if not install_path.exists():
        console.print("[red]PM-OS not installed. Run 'pm-os init' first.[/red]")
        sys.exit(1)

    config_path = install_path / ".config" / "config.yaml"
    env_path = install_path / ".env"

    if not config_path.exists():
        console.print("[red]Configuration not found. Run 'pm-os init' first.[/red]")
        sys.exit(1)

    if dry_run:
        console.print("[dim]Dry run mode - no changes will be made[/dim]")
        console.print()

    # Load config
    import yaml
    config = yaml.safe_load(config_path.read_text())

    # Load env vars
    env_vars = {}
    if env_path.exists():
        for line in env_path.read_text().strip().split("\n"):
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()

    integrations = config.get("integrations", {})
    enabled = [name for name, cfg in integrations.items() if cfg.get("enabled")]

    if integration:
        if integration.lower() not in [e.lower() for e in enabled]:
            console.print(f"[yellow]Integration '{integration}' not enabled[/yellow]")
            sys.exit(1)
        enabled = [integration.lower()]
    else:
        enabled = [e.lower() for e in enabled]

    if not enabled:
        console.print("[yellow]No integrations enabled[/yellow]")
        console.print("Run 'pm-os config edit' to configure integrations.")
        return

    console.print(f"Syncing: {', '.join(enabled)}")
    console.print()

    results = []

    for name in enabled:
        cfg = integrations.get(name, integrations.get(name.capitalize(), {}))

        if dry_run:
            console.print(f"  [dim]○[/dim] {name}: Would sync (dry run)")
            continue

        console.print(f"[bold]Syncing {name}...[/bold]")

        try:
            success, message = run_integration_sync(
                name, cfg, env_vars, brain_path, verbose
            )
            results.append((name, success, message))
            if success:
                console.print(f"  [green]✓[/green] {message}")
            else:
                console.print(f"  [red]✗[/red] {message}")
        except Exception as e:
            results.append((name, False, str(e)))
            console.print(f"  [red]✗[/red] Error: {e}")

    # Summary
    if results:
        console.print()
        successful = sum(1 for _, s, _ in results if s)
        console.print(f"[bold]Sync complete:[/bold] {successful}/{len(results)} integrations synced")


def run_integration_sync(
    name: str,
    config: dict,
    env_vars: dict,
    brain_path: Path,
    verbose: bool
) -> tuple:
    """Run sync for a specific integration."""
    name_lower = name.lower()

    if name_lower == "jira":
        from pm_os.wizard.brain_sync.jira_sync import JiraSyncer

        url = config.get("url") or env_vars.get("JIRA_URL", "")
        email = config.get("email") or env_vars.get("JIRA_EMAIL", "")
        token = config.get("token") or env_vars.get("JIRA_TOKEN", "")
        projects = config.get("projects")

        if not all([url, email, token]):
            return False, "Missing Jira credentials (url, email, token)"

        project_list = [p.strip() for p in projects.split(",") if p.strip()] if projects else None

        syncer = JiraSyncer(brain_path, url, email, token, project_list)
        result = syncer.sync()
        return result.to_tuple()

    elif name_lower == "slack":
        from pm_os.wizard.brain_sync.slack_sync import SlackSyncer

        token = config.get("token") or env_vars.get("SLACK_BOT_TOKEN", "")
        channels = config.get("channels")

        if not token:
            return False, "Missing Slack bot token"

        channel_list = [c.strip() for c in channels.split(",") if c.strip()] if channels else None

        syncer = SlackSyncer(brain_path, token, channel_list)
        result = syncer.sync()
        return result.to_tuple()

    elif name_lower == "github":
        from pm_os.wizard.brain_sync.github_sync import GitHubSyncer

        token = config.get("token") or env_vars.get("GITHUB_TOKEN", "")
        repos = config.get("repos")

        if not token:
            return False, "Missing GitHub token"

        repo_list = [r.strip() for r in repos.split(",") if r.strip()] if repos else None

        syncer = GitHubSyncer(brain_path, token, repo_list)
        result = syncer.sync()
        return result.to_tuple()

    elif name_lower == "confluence":
        from pm_os.wizard.brain_sync.confluence_sync import ConfluenceSyncer

        url = config.get("url") or env_vars.get("CONFLUENCE_URL", "")
        email = config.get("email") or env_vars.get("CONFLUENCE_EMAIL", "")
        token = config.get("token") or env_vars.get("CONFLUENCE_TOKEN", "")
        spaces = config.get("spaces")

        if not all([url, email, token]):
            return False, "Missing Confluence credentials"

        space_list = [spaces] if spaces else None

        syncer = ConfluenceSyncer(brain_path, url, email, token, space_list)
        result = syncer.sync()
        return result.to_tuple()

    elif name_lower == "google":
        from pm_os.wizard.brain_sync.google_sync import GoogleSyncer

        creds_path = config.get("credentials_path")
        if not creds_path:
            return False, "Google OAuth credentials path not configured"

        syncer = GoogleSyncer(brain_path, Path(creds_path) if creds_path else None)
        result = syncer.sync()
        return result.to_tuple()

    else:
        return False, f"Unknown integration: {name}"


@brain.command()
def status():
    """Show brain entity counts."""
    console.print("[bold blue]Brain Status[/bold blue]")

    install_path = get_default_install_path()
    brain_path = install_path / "brain"

    if not brain_path.exists():
        console.print("[red]Brain not found. Run 'pm-os init' first.[/red]")
        sys.exit(1)

    entities_path = brain_path / "Entities"

    if not entities_path.exists():
        console.print("[yellow]No entities directory found[/yellow]")
        return

    # Count entities by type
    console.print()
    console.print("[bold]Entity Counts:[/bold]")

    total = 0
    for entity_type in entities_path.iterdir():
        if entity_type.is_dir():
            count = len(list(entity_type.glob("*.md")))
            total += count
            console.print(f"  {entity_type.name}: {count}")

    console.print()
    console.print(f"[bold]Total entities:[/bold] {total}")


@main.group()
def config():
    """Configuration management commands."""
    pass


@config.command()
def show():
    """Show current configuration."""
    install_path = get_default_install_path()
    config_path = install_path / ".config" / "config.yaml"

    if not config_path.exists():
        console.print("[red]Configuration not found. Run 'pm-os init' first.[/red]")
        sys.exit(1)

    import yaml
    config = yaml.safe_load(config_path.read_text())

    console.print("[bold blue]PM-OS Configuration[/bold blue]")
    console.print()

    # User info
    user = config.get("user", {})
    console.print("[bold]User:[/bold]")
    console.print(f"  Name: {user.get('name', 'Not set')}")
    console.print(f"  Email: {user.get('email', 'Not set')}")
    console.print(f"  Role: {user.get('role', 'Not set')}")
    console.print()

    # LLM
    llm = config.get("llm", {})
    console.print("[bold]LLM:[/bold]")
    console.print(f"  Provider: {llm.get('provider', 'Not set')}")
    console.print(f"  Model: {llm.get('model', 'Not set')}")
    console.print()

    # Integrations
    integrations = config.get("integrations", {})
    console.print("[bold]Integrations:[/bold]")
    for name, cfg in integrations.items():
        status = "[green]enabled[/green]" if cfg.get("enabled") else "[dim]disabled[/dim]"
        console.print(f"  {name}: {status}")


@config.command()
def edit():
    """Open configuration in editor."""
    import subprocess
    import shutil

    install_path = get_default_install_path()
    config_path = install_path / ".config" / "config.yaml"

    if not config_path.exists():
        console.print("[red]Configuration not found. Run 'pm-os init' first.[/red]")
        sys.exit(1)

    # Try common editors
    editor = os.environ.get("EDITOR", "")
    if not editor:
        for ed in ["code", "vim", "nano", "vi"]:
            if shutil.which(ed):
                editor = ed
                break

    if editor:
        subprocess.run([editor, str(config_path)])
    else:
        console.print(f"[yellow]No editor found. Edit manually:[/yellow]")
        console.print(f"  {config_path}")


@config.command()
@click.argument("key")
@click.argument("value")
def set(key: str, value: str):
    """Set a configuration value.

    KEY format: section.key (e.g., user.name, llm.provider)
    """
    import yaml

    install_path = get_default_install_path()
    config_path = install_path / ".config" / "config.yaml"

    if not config_path.exists():
        console.print("[red]Configuration not found. Run 'pm-os init' first.[/red]")
        sys.exit(1)

    config = yaml.safe_load(config_path.read_text())

    # Parse key path (e.g., "user.name" -> ["user", "name"])
    key_parts = key.split(".")
    if len(key_parts) < 2:
        console.print("[red]Key must be in format: section.key (e.g., user.name)[/red]")
        sys.exit(1)

    # Navigate to the right location and set value
    current = config
    for part in key_parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]

    old_value = current.get(key_parts[-1], "(not set)")
    current[key_parts[-1]] = value

    # Write back
    config_path.write_text(yaml.dump(config, default_flow_style=False))

    console.print(f"[green]✓[/green] {key}: {old_value} → {value}")


@config.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def validate(json_output: bool):
    """Validate configuration file."""
    import yaml
    import json

    install_path = get_default_install_path()
    config_path = install_path / ".config" / "config.yaml"

    if not config_path.exists():
        if json_output:
            print(json.dumps({"valid": False, "error": "Config not found"}))
        else:
            console.print("[red]Configuration not found. Run 'pm-os init' first.[/red]")
        sys.exit(1)

    errors = []
    warnings = []

    try:
        config = yaml.safe_load(config_path.read_text())

        # Required fields
        if not config.get("user", {}).get("name"):
            warnings.append("user.name not set")
        if not config.get("user", {}).get("email"):
            warnings.append("user.email not set")
        if not config.get("llm", {}).get("provider"):
            errors.append("llm.provider is required")
        if not config.get("llm", {}).get("model"):
            errors.append("llm.model is required")

        # Validate LLM provider
        valid_providers = ["bedrock", "anthropic", "openai", "ollama"]
        provider = config.get("llm", {}).get("provider")
        if provider and provider not in valid_providers:
            errors.append(f"Invalid llm.provider: {provider} (valid: {', '.join(valid_providers)})")

        # Check integrations config
        integrations = config.get("integrations", {})
        for name, cfg in integrations.items():
            if cfg.get("enabled") and not any(cfg.get(k) for k in ["url", "token", "credentials_path"]):
                warnings.append(f"Integration '{name}' enabled but missing configuration")

    except yaml.YAMLError as e:
        errors.append(f"Invalid YAML: {e}")
    except Exception as e:
        errors.append(f"Error reading config: {e}")

    is_valid = len(errors) == 0

    if json_output:
        print(json.dumps({
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings
        }, indent=2))
    else:
        console.print("[bold blue]Configuration Validation[/bold blue]")
        console.print()

        if errors:
            console.print("[red]Errors:[/red]")
            for err in errors:
                console.print(f"  [red]✗[/red] {err}")
            console.print()

        if warnings:
            console.print("[yellow]Warnings:[/yellow]")
            for warn in warnings:
                console.print(f"  [yellow]⚠[/yellow] {warn}")
            console.print()

        if is_valid:
            console.print("[green]Configuration is valid.[/green]")
        else:
            console.print("[red]Configuration has errors.[/red]")

    sys.exit(0 if is_valid else 1)


@main.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--keep-brain", is_flag=True, help="Keep brain directory")
def uninstall(yes: bool, keep_brain: bool):
    """Remove PM-OS installation."""
    import shutil

    install_path = get_default_install_path()

    if not install_path.exists():
        console.print("[yellow]PM-OS not installed.[/yellow]")
        sys.exit(0)

    console.print(f"[bold red]This will remove PM-OS from:[/bold red] {install_path}")
    console.print()

    # List what will be deleted
    items_to_delete = []
    for item in install_path.iterdir():
        if keep_brain and item.name == "brain":
            console.print(f"  [dim]○ {item.name}/ (keeping)[/dim]")
        else:
            items_to_delete.append(item)
            console.print(f"  [red]✗ {item.name}/[/red]")

    console.print()

    if not yes:
        if not click.confirm("Are you sure you want to uninstall PM-OS?"):
            console.print("[dim]Cancelled.[/dim]")
            sys.exit(0)

    # Delete items
    for item in items_to_delete:
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        except Exception as e:
            console.print(f"[red]Failed to delete {item}:[/red] {e}")

    # Remove empty install directory if nothing left
    if not keep_brain and install_path.exists():
        try:
            install_path.rmdir()
        except OSError:
            pass  # Directory not empty

    console.print()
    console.print("[green]PM-OS uninstalled.[/green]")
    if keep_brain:
        console.print(f"[dim]Brain preserved at: {install_path / 'brain'}[/dim]")


@main.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def status(json_output: bool):
    """Show PM-OS status dashboard."""
    import json
    from datetime import datetime

    install_path = get_default_install_path()
    status_data = {
        "installed": False,
        "path": str(install_path),
        "timestamp": datetime.now().isoformat()
    }

    if not install_path.exists():
        if json_output:
            print(json.dumps(status_data, indent=2))
        else:
            console.print("[yellow]PM-OS not installed[/yellow]")
            console.print(f"Run 'pm-os init' to install at {install_path}")
        sys.exit(1)

    status_data["installed"] = True

    # Load config
    config_path = install_path / ".config" / "config.yaml"
    if config_path.exists():
        import yaml
        config = yaml.safe_load(config_path.read_text())
        status_data["user"] = config.get("user", {}).get("name", "Unknown")
        status_data["llm_provider"] = config.get("llm", {}).get("provider", "Unknown")
        status_data["llm_model"] = config.get("llm", {}).get("model", "Unknown")

        integrations = config.get("integrations", {})
        status_data["integrations"] = {
            name: cfg.get("enabled", False) for name, cfg in integrations.items()
        }

    # Count brain entities
    brain_path = install_path / "brain" / "Entities"
    entity_counts = {}
    total_entities = 0
    if brain_path.exists():
        for entity_dir in brain_path.iterdir():
            if entity_dir.is_dir():
                count = len(list(entity_dir.glob("*.md")))
                entity_counts[entity_dir.name] = count
                total_entities += count
    status_data["entities"] = entity_counts
    status_data["total_entities"] = total_entities

    # Check sync state
    sync_state_path = install_path / "brain" / ".sync_state.json"
    if sync_state_path.exists():
        import json as json_module
        sync_state = json_module.loads(sync_state_path.read_text())
        status_data["last_sync"] = sync_state
    else:
        status_data["last_sync"] = None

    if json_output:
        print(json.dumps(status_data, indent=2))
    else:
        console.print("[bold blue]PM-OS Status[/bold blue]")
        console.print()

        # User info
        console.print(f"[bold]User:[/bold] {status_data.get('user', 'Unknown')}")
        console.print(f"[bold]Path:[/bold] {install_path}")
        console.print()

        # LLM
        console.print(f"[bold]LLM Provider:[/bold] {status_data.get('llm_provider', 'Unknown')}")
        console.print(f"[bold]Model:[/bold] {status_data.get('llm_model', 'Unknown')}")
        console.print()

        # Integrations
        integrations = status_data.get("integrations", {})
        if integrations:
            console.print("[bold]Integrations:[/bold]")
            for name, enabled in integrations.items():
                status = "[green]enabled[/green]" if enabled else "[dim]disabled[/dim]"
                console.print(f"  {name}: {status}")
            console.print()

        # Brain
        console.print(f"[bold]Brain Entities:[/bold] {total_entities} total")
        if entity_counts:
            for entity_type, count in entity_counts.items():
                console.print(f"  {entity_type}: {count}")


@main.command("help")
@click.argument("topic", required=False)
def help_topic(topic: str):
    """Show detailed help for a topic.

    Topics: brain, integrations, skills, troubleshoot, quick-start

    Examples:
        pm-os help              # List all topics
        pm-os help brain        # Show brain help
        pm-os help integrations # Show integrations help
    """
    from rich.panel import Panel
    from pm_os.help_topics import get_help_content, list_topics, get_topic_names

    if not topic:
        console.print("[bold blue]PM-OS Help Topics[/bold blue]")
        console.print()
        for topic_name, description in list_topics():
            console.print(f"  [cyan]{topic_name}[/cyan] - {description}")
        console.print()
        console.print("[dim]Run 'pm-os help <topic>' for details[/dim]")
        return

    content = get_help_content(topic.lower())
    if content:
        console.print(Panel(content, border_style="blue", title=f"Help: {topic}"))
    else:
        console.print(f"[red]Unknown topic: {topic}[/red]")
        console.print(f"[dim]Available topics: {', '.join(get_topic_names())}[/dim]")
        sys.exit(1)


@main.group()
def setup():
    """Post-installation setup commands."""
    pass


@setup.command("integrations")
@click.argument("integration", required=False)
@click.option("--list", "list_all", is_flag=True, help="List all available integrations")
def setup_integrations(integration: str, list_all: bool):
    """Configure an integration after initial setup.

    Add integrations that were skipped during quick setup,
    or reconfigure existing integrations.

    Examples:
        pm-os setup integrations --list  # List all
        pm-os setup integrations jira    # Configure Jira
        pm-os setup integrations slack   # Configure Slack
    """
    install_path = get_default_install_path()

    if not install_path.exists():
        console.print("[red]PM-OS not installed. Run 'pm-os init' first.[/red]")
        sys.exit(1)

    # Available integrations
    integrations_info = {
        "jira": "Jira - Issues, sprints, projects",
        "slack": "Slack - Messages, channels, mentions",
        "github": "GitHub - PRs, issues, repos",
        "confluence": "Confluence - Documentation, spaces",
        "google": "Google - Calendar, Drive, Gmail",
    }

    if list_all or not integration:
        console.print("[bold blue]Available Integrations[/bold blue]")
        console.print()
        for key, description in integrations_info.items():
            status = _check_integration_status(install_path, key)
            icon = "[green]✓[/green]" if status else "[dim]○[/dim]"
            console.print(f"  {icon} {description}")
        console.print()
        console.print("[dim]Run 'pm-os setup integrations <name>' to configure[/dim]")
        return

    integration = integration.lower()
    if integration not in integrations_info:
        console.print(f"[red]Unknown integration: {integration}[/red]")
        console.print(f"Available: {', '.join(integrations_info.keys())}")
        sys.exit(1)

    console.print(f"[bold blue]Configure {integration.title()}[/bold blue]")
    console.print()
    console.print("[yellow]Integration setup coming soon.[/yellow]")
    console.print("[dim]For now, edit config manually:[/dim]")
    console.print(f"  pm-os config edit")
    console.print()
    console.print("[dim]Or re-run full setup:[/dim]")
    console.print("  pm-os init")


def _check_integration_status(install_path: Path, integration: str) -> bool:
    """Check if an integration is configured."""
    import yaml

    config_path = install_path / ".config" / "config.yaml"
    if not config_path.exists():
        return False

    try:
        config = yaml.safe_load(config_path.read_text())
        integrations = config.get("integrations", {})
        return integrations.get(integration, {}).get("enabled", False)
    except Exception:
        return False


if __name__ == "__main__":
    main()
