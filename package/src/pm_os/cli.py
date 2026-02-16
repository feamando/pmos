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


def _strip_secrets_from_config(config: dict) -> dict:
    """Remove secret values (tokens, API keys) from config for safe storage.

    config.yaml should contain structure and settings, NOT credentials.
    Credentials belong in .env only.
    """
    import copy
    safe = copy.deepcopy(config)

    # Strip tokens from integrations
    secret_keys = {"token", "api_key", "api_token", "secret", "password"}
    for name, cfg in safe.get("integrations", {}).items():
        if isinstance(cfg, dict):
            for key in list(cfg.keys()):
                if key in secret_keys:
                    del cfg[key]

    # Strip API key from LLM config
    llm = safe.get("llm", {})
    for key in list(llm.keys()):
        if key in secret_keys:
            del llm[key]

    return safe


def run_silent_install(install_path: Path, config: dict, verbose: bool = False) -> bool:
    """Run silent install from template config.

    Performs a complete non-interactive install including:
    - Directory structure creation
    - Config and env file generation (using wizard generators for parity)
    - common/ download from GitHub
    - Claude Code setup (.claude/commands, settings, env)
    - Initial brain files (USER.md, BRAIN.md, Glossary.md, Index.md)
    """
    import json
    import yaml
    from pm_os.wizard.steps.directories import (
        DIRECTORY_STRUCTURE,
        create_initial_brain_files,
        generate_gitignore,
    )

    console.print("[bold blue]PM-OS Silent Installation[/bold blue]")
    console.print()

    try:
        # 1. Create full directory structure
        install_path.mkdir(parents=True, exist_ok=True)
        for dir_path in DIRECTORY_STRUCTURE:
            (install_path / dir_path).mkdir(parents=True, exist_ok=True)

        # Set secure permissions on .secrets directory
        secrets_path = install_path / ".secrets"
        if secrets_path.exists():
            os.chmod(secrets_path, 0o700)

        if verbose:
            console.print(f"[dim]Created {len(DIRECTORY_STRUCTURE)} directories[/dim]")
        console.print(f"[green]✓[/green] Directory structure created")

        # Extract user and integration data from config
        user = config.get("user", {})
        user_name = user.get("name", "User")
        user_email = user.get("email", "")
        user_role = user.get("role", "Product Manager")
        user_team = user.get("team", "")
        user_tz = user.get("timezone", "UTC")
        llm = config.get("llm", {})
        integrations = config.get("integrations", {})

        # 2. Write config.yaml — strip secrets (tokens) before writing
        safe_config = _strip_secrets_from_config(config)
        config_path = install_path / ".config" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.dump(safe_config, default_flow_style=False, sort_keys=False))
        if verbose:
            console.print(f"[dim]Wrote: {config_path}[/dim]")

        # 3. Write comprehensive .env file with all vars
        env_path = install_path / ".env"
        env_lines = [
            "# PM-OS Environment Configuration",
            f"# Generated by pm-os init --template",
            "",
            "# User Profile",
            f'PMOS_USER_NAME="{user_name}"',
            f'PMOS_USER_EMAIL="{user_email}"',
            f'PMOS_USER_ROLE="{user_role}"',
            f'PMOS_USER_TEAM="{user_team}"',
            f'PMOS_USER_TIMEZONE="{user_tz}"',
            "",
            "# LLM Configuration",
            f'PMOS_LLM_PROVIDER="{llm.get("provider", "")}"',
            f'PMOS_LLM_MODEL="{llm.get("model", "")}"',
        ]

        # Provider-specific
        if llm.get("provider") == "bedrock":
            env_lines.append(f'AWS_REGION="{llm.get("region", "us-east-1")}"')
        elif llm.get("provider") == "anthropic" and llm.get("api_key"):
            env_lines.append(f'ANTHROPIC_API_KEY="{llm["api_key"]}"')
        elif llm.get("provider") == "openai" and llm.get("api_key"):
            env_lines.append(f'OPENAI_API_KEY="{llm["api_key"]}"')

        env_lines.append("")

        # Integration secrets
        jira = integrations.get("jira", {})
        if jira.get("enabled"):
            env_lines.extend([
                "# Jira",
                f'JIRA_URL="{jira.get("url", "")}"',
                f'JIRA_USERNAME="{jira.get("email", "")}"',
                f'JIRA_API_TOKEN="{jira.get("token", "")}"',
                f'JIRA_PROJECTS="{jira.get("projects", "")}"',
                "",
            ])

        slack = integrations.get("slack", {})
        if slack.get("enabled"):
            env_lines.extend([
                "# Slack",
                f'SLACK_BOT_TOKEN="{slack.get("token", "")}"',
                f'SLACK_BOT_USER_ID="{slack.get("bot_user_id", "")}"',
                f'SLACK_CHANNELS="{slack.get("channels", "")}"',
                "",
            ])

        github = integrations.get("github", {})
        if github.get("enabled"):
            env_lines.extend([
                "# GitHub",
                f'GITHUB_TOKEN="{github.get("token", "")}"',
                f'GITHUB_REPOS="{github.get("repos", "")}"',
                "",
            ])

        confluence = integrations.get("confluence", {})
        if confluence.get("enabled"):
            env_lines.extend([
                "# Confluence",
                f'CONFLUENCE_URL="{confluence.get("url", "")}"',
                f'CONFLUENCE_EMAIL="{confluence.get("email", "")}"',
                f'CONFLUENCE_TOKEN="{confluence.get("token", "")}"',
                f'CONFLUENCE_SPACE="{confluence.get("space", "")}"',
                "",
            ])

        google = integrations.get("google", {})
        if google.get("credentials_path"):
            env_lines.extend([
                "# Google",
                f'GOOGLE_CREDENTIALS_PATH="{google.get("credentials_path", "")}"',
            ])
            if google.get("token_path"):
                env_lines.append(f'GOOGLE_TOKEN_PATH="{google["token_path"]}"')
            env_lines.append("")

        # Paths
        env_lines.extend([
            "# Paths",
            f'PM_OS_USER="{install_path}"',
            f'PM_OS_BRAIN="{install_path / "brain"}"',
        ])

        env_path.write_text("\n".join(env_lines) + "\n")
        os.chmod(env_path, 0o600)
        if verbose:
            console.print(f"[dim]Wrote: {env_path} (600 permissions)[/dim]")

        # 4. Write comprehensive .gitignore (reuse wizard generator)
        generate_gitignore(install_path)

        # 5. Write rich USER.md
        user_md_path = install_path / "USER.md"
        user_md_content = f"# {user_name}\n\n## Profile\n\n"
        user_md_content += f"- **Name**: {user_name}\n"
        user_md_content += f"- **Email**: {user_email}\n"
        user_md_content += f"- **Role**: {user_role}\n"
        if user_team:
            user_md_content += f"- **Team**: {user_team}\n"
        user_md_content += f"\n## About\n\n"
        user_md_content += f"{user_name} is a {user_role}"
        user_md_content += f" on the {user_team} team.\n" if user_team else ".\n"
        user_md_content += f"\n## Communication Style\n\n"
        user_md_content += "- Professional and clear\n"
        user_md_content += "- Data-driven decision making\n"
        user_md_content += "- Collaborative approach\n"
        user_md_content += f"\n## Key Responsibilities\n\n"
        user_md_content += "- Product strategy and roadmap\n"
        user_md_content += "- Stakeholder management\n"
        user_md_content += "- Feature prioritization\n"
        user_md_content += "- Team coordination\n"
        from datetime import datetime
        user_md_content += f"\n---\n*Generated by PM-OS on {datetime.now().strftime('%Y-%m-%d')}*\n"
        user_md_path.write_text(user_md_content)

        # 6. Write initial brain files (reuse wizard generator for rich content)
        create_initial_brain_files(install_path)

        console.print(f"[green]✓[/green] Config files created")

        # 7. Download common/ from GitHub
        common_dir = install_path / "common"
        root_dir = install_path

        if common_dir.exists() and (common_dir / "tools").exists():
            console.print(f"[green]✓[/green] common/ already exists")
        else:
            try:
                from pm_os.downloader import CommonDownloader, DownloadError

                try:
                    from importlib.metadata import version as pkg_version
                    pip_version = pkg_version("pm-os")
                except Exception:
                    pip_version = None

                version = pip_version or "latest"
                downloader = CommonDownloader(version=version, verbose=verbose)

                console.print(f"[dim]Downloading common/ (version: {version})...[/dim]")
                success = downloader.download(root_dir)

                if success:
                    valid, missing = downloader.verify_download(common_dir)
                    if valid:
                        downloader.create_markers(root_dir, install_path, common_dir)
                        downloader.pin_version(root_dir)
                        console.print(f"[green]✓[/green] common/ downloaded and verified")
                    else:
                        console.print(f"[yellow]⚠[/yellow] common/ incomplete: {', '.join(missing)}")
                else:
                    console.print(f"[yellow]⚠[/yellow] common/ download failed — run 'pm-os update' later")
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] common/ download failed: {e}")

        # 8. Set up Claude Code integration
        if common_dir.exists() and (common_dir / "tools").exists():
            claude_dir = install_path / ".claude"
            claude_dir.mkdir(parents=True, exist_ok=True)

            # Symlink commands
            commands_target = common_dir / ".claude" / "commands"
            commands_link = claude_dir / "commands"
            if commands_target.exists():
                if commands_link.exists() or commands_link.is_symlink():
                    if commands_link.is_symlink():
                        commands_link.unlink()
                    else:
                        import shutil
                        shutil.rmtree(commands_link)
                try:
                    rel_path = os.path.relpath(commands_target, claude_dir)
                    commands_link.symlink_to(rel_path)
                except OSError:
                    import shutil
                    shutil.copytree(commands_target, commands_link)

            # Generate settings.local.json
            settings_path = claude_dir / "settings.local.json"
            if not settings_path.exists():
                settings = {
                    "permissions": {
                        "allow": [
                            f"Bash(python3:{root_dir}/*)",
                            "Bash(python3:*pm_os*)",
                            f"Bash(source:{root_dir}/*/scripts/boot.sh*)",
                            f"Bash(bash:{root_dir}/*/scripts/boot.sh*)",
                            "Bash(git:*)",
                            f"Bash(ls:{root_dir}/*)",
                            f"Bash(cat:{root_dir}/*)",
                            "Bash(which:*)",
                            "Bash(pip3:*pm-os*)",
                            "Bash(pm-os:*)",
                        ],
                        "deny": []
                    },
                    "env": {
                        "PM_OS_ROOT": str(root_dir),
                        "PM_OS_COMMON": str(common_dir),
                        "PM_OS_USER": str(install_path),
                    }
                }
                settings_path.write_text(json.dumps(settings, indent=2) + "\n")

            # Generate .claude/env
            env_file = claude_dir / "env"
            env_lines = [
                f"PM_OS_ROOT={root_dir}",
                f"PM_OS_COMMON={common_dir}",
                f"PM_OS_USER={install_path}",
                f"PYTHONPATH={common_dir / 'tools'}",
            ]
            env_file.write_text("\n".join(env_lines) + "\n")

            # Link AGENT.md
            agent_source = common_dir / "AGENT.md"
            agent_target = install_path / "AGENT.md"
            if agent_source.exists() and not agent_target.exists():
                try:
                    rel_path = os.path.relpath(agent_source, install_path)
                    agent_target.symlink_to(rel_path)
                except OSError:
                    import shutil
                    shutil.copy2(agent_source, agent_target)

            cmd_count = len(list(commands_target.glob("*.md"))) if commands_target.exists() else 0
            console.print(f"[green]✓[/green] Claude Code configured ({cmd_count} commands)")

        console.print()
        console.print(f"[green]✓[/green] PM-OS installed to {install_path}")
        console.print()
        console.print("[bold]Next steps:[/bold]")
        console.print(f"  1. cd {install_path}")
        console.print("  2. claude  # Start Claude Code with PM-OS")
        console.print("  3. /boot  # Run boot sequence to load context")

        return True

    except Exception as e:
        console.print(f"[red]Silent install failed:[/red] {e}")
        return False


@main.command()
@click.option("--check", is_flag=True, help="Check for updates without installing")
@click.option("--common-only", is_flag=True, help="Only update common/ directory (skip pip upgrade)")
@click.option("--path", type=click.Path(), help="PM-OS installation path")
def update(check: bool, common_only: bool, path: str):
    """Update PM-OS CLI and common/ tools to the latest version.

    Updates both the pip package and the common/ directory with tools,
    commands, and frameworks. User data is never modified.

    Examples:
        pm-os update           # Update everything
        pm-os update --check   # Check what's available
        pm-os update --common-only  # Only update tools
    """
    import subprocess

    install_path = Path(path) if path else get_default_install_path()

    if check:
        _update_check(install_path)
        return

    updated_anything = False

    # 1. Update pip package (unless --common-only)
    if not common_only:
        console.print("[bold]Updating PM-OS CLI...[/bold]")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "pm-os"],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                console.print("[green]✓[/green] CLI updated")
                updated_anything = True
            else:
                console.print(f"[yellow]⚠[/yellow] pip upgrade failed: {result.stderr[:200]}")
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] pip upgrade failed: {e}")

    # 2. Update common/ directory
    common_dir = install_path / "common"
    if common_dir.exists():
        console.print("[bold]Updating common/ tools...[/bold]")
        success = _update_common(install_path, common_dir)
        if success:
            updated_anything = True

            # 3. Refresh Claude Code symlinks
            _refresh_symlinks(install_path, common_dir)
    else:
        console.print("[dim]No common/ found. Downloading...[/dim]")
        success = _download_common_fresh(install_path)
        if success:
            updated_anything = True
            _refresh_symlinks(install_path, install_path / "common")

    if updated_anything:
        console.print()
        console.print("[green]✓ PM-OS updated successfully![/green]")
    else:
        console.print()
        console.print("[dim]Nothing to update.[/dim]")


def _update_check(install_path: Path):
    """Check for available updates without installing."""
    console.print("[bold]Checking for PM-OS updates...[/bold]")
    console.print()

    # Check pip package version
    try:
        from importlib.metadata import version as pkg_version
        current_pip = pkg_version("pm-os")
    except Exception:
        current_pip = "unknown"

    console.print(f"  CLI version: {current_pip}")

    # Check common/ version
    common_dir = install_path / "common"
    from pm_os.downloader import CommonDownloader
    installed_version = CommonDownloader.get_installed_version(install_path)
    console.print(f"  Common version: {installed_version or 'not installed'}")

    # Check latest available
    try:
        downloader = CommonDownloader(version="latest", verbose=False)
        latest = downloader.get_latest_version()
        console.print(f"  Latest available: {latest}")

        if installed_version and installed_version == latest:
            console.print()
            console.print("[green]✓ You're up to date![/green]")
        else:
            console.print()
            console.print("[yellow]Update available. Run 'pm-os update' to install.[/yellow]")
    except Exception as e:
        console.print(f"  Latest available: [dim]could not check ({e})[/dim]")


def _update_common(install_path: Path, common_dir: Path) -> bool:
    """Update common/ directory, backing up old version."""
    import shutil
    from pm_os.downloader import CommonDownloader, DownloadError

    # Read current version
    installed_version = CommonDownloader.get_installed_version(install_path)

    # Determine target version (match pip package)
    try:
        from importlib.metadata import version as pkg_version
        pip_version = pkg_version("pm-os")
    except Exception:
        pip_version = None

    version = pip_version or "latest"
    downloader = CommonDownloader(version=version, verbose=False)

    # Check if update needed
    try:
        latest = downloader.get_latest_version()
        if installed_version and installed_version == latest:
            console.print(f"[dim]  common/ already at {latest}[/dim]")
            return False
    except Exception:
        pass  # Continue with update anyway

    # Backup existing common/
    backup_dir = install_path / "common.bak"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)

    console.print("[dim]  Backing up current common/...[/dim]")
    shutil.copytree(common_dir, backup_dir, symlinks=True)

    # Download new common/
    try:
        console.print(f"[dim]  Downloading common/ (version: {version})...[/dim]")
        success = downloader.download(install_path)

        if success:
            valid, missing = downloader.verify_download(common_dir)
            if valid:
                downloader.pin_version(install_path)
                console.print("[green]✓[/green] common/ updated and verified")

                # Remove backup
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
                return True
            else:
                console.print(f"[red]✗[/red] Download incomplete: {', '.join(missing)}")
                # Restore backup
                _restore_backup(install_path, common_dir, backup_dir)
                return False
        else:
            console.print("[red]✗[/red] Download failed")
            _restore_backup(install_path, common_dir, backup_dir)
            return False

    except DownloadError as e:
        console.print(f"[red]✗[/red] Update failed: {e}")
        _restore_backup(install_path, common_dir, backup_dir)
        return False


def _restore_backup(install_path: Path, common_dir: Path, backup_dir: Path):
    """Restore common/ from backup."""
    import shutil
    if backup_dir.exists():
        console.print("[dim]  Restoring previous common/...[/dim]")
        if common_dir.exists():
            shutil.rmtree(common_dir)
        shutil.move(str(backup_dir), str(common_dir))
        console.print("[green]✓[/green] Previous version restored")


def _download_common_fresh(install_path: Path) -> bool:
    """Download common/ for the first time during update."""
    from pm_os.downloader import CommonDownloader, DownloadError

    try:
        from importlib.metadata import version as pkg_version
        pip_version = pkg_version("pm-os")
    except Exception:
        pip_version = None

    version = pip_version or "latest"
    downloader = CommonDownloader(version=version, verbose=False)

    try:
        console.print(f"[dim]  Downloading common/ (version: {version})...[/dim]")
        success = downloader.download(install_path)
        if success:
            common_dir = install_path / "common"
            valid, missing = downloader.verify_download(common_dir)
            if valid:
                downloader.create_markers(install_path, install_path, common_dir)
                downloader.pin_version(install_path)
                console.print("[green]✓[/green] common/ downloaded and verified")
                return True
            else:
                console.print(f"[yellow]⚠[/yellow] Download incomplete: {', '.join(missing)}")
        return False
    except DownloadError as e:
        console.print(f"[red]✗[/red] Download failed: {e}")
        return False


def _refresh_symlinks(install_path: Path, common_dir: Path):
    """Refresh Claude Code symlinks after common/ update."""
    claude_dir = install_path / ".claude"
    if not claude_dir.exists():
        return

    # Refresh commands symlink
    commands_target = common_dir / ".claude" / "commands"
    commands_link = claude_dir / "commands"
    if commands_target.exists():
        if commands_link.is_symlink():
            # Re-create symlink (in case target path changed)
            commands_link.unlink()
            try:
                rel_path = os.path.relpath(commands_target, claude_dir)
                commands_link.symlink_to(rel_path)
            except OSError:
                import shutil
                shutil.copytree(commands_target, commands_link)
            console.print("[green]✓[/green] Commands symlink refreshed")
        elif not commands_link.exists():
            try:
                rel_path = os.path.relpath(commands_target, claude_dir)
                commands_link.symlink_to(rel_path)
                console.print("[green]✓[/green] Commands symlink created")
            except OSError:
                pass

    # Refresh AGENT.md symlink
    agent_source = common_dir / "AGENT.md"
    agent_target = install_path / "AGENT.md"
    if agent_source.exists() and agent_target.is_symlink():
        agent_target.unlink()
        try:
            rel_path = os.path.relpath(agent_source, install_path)
            agent_target.symlink_to(rel_path)
        except OSError:
            import shutil
            shutil.copy2(agent_source, agent_target)
        console.print("[green]✓[/green] AGENT.md symlink refreshed")

    # Update .claude/env paths
    env_file = claude_dir / "env"
    if env_file.exists():
        env_lines = [
            f"PM_OS_ROOT={install_path}",
            f"PM_OS_COMMON={common_dir}",
            f"PM_OS_USER={install_path}",
            f"PYTHONPATH={common_dir / 'tools'}",
        ]
        env_file.write_text("\n".join(env_lines) + "\n")
        console.print("[green]✓[/green] .claude/env updated")


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
            # Create ALL directories expected by PM-OS
            dirs = [
                "brain", "brain/Entities", "brain/Context",
                "brain/Glossary", "brain/Index", "brain/Inbox", "brain/Templates",
                "brain/Caches", "brain/Confucius",
                "sessions/active", "sessions/archive",
                "personal/context", "personal/context/raw",
                "personal/calendar", "personal/emails",
                "personal/notes", "personal/todos",
                "personal/development", "personal/reflections",
                "team/reports", "team/stakeholders", "team/meetings", "team/onboarding",
                "products",
                "planning/Sprints", "planning/Reporting", "planning/Roadmaps",
                "planning/Templates", "planning/Meeting_Prep",
                ".config", ".secrets",
            ]
            entity_dirs = ["People", "Projects", "Issues", "Channels", "Documents"]
            for d in dirs:
                (install_path / d).mkdir(parents=True, exist_ok=True)
            for d in entity_dirs:
                (install_path / "brain" / "Entities" / d).mkdir(parents=True, exist_ok=True)

            # Create USER.md if missing
            user_md = install_path / "USER.md"
            if not user_md.exists():
                _create_user_md(install_path, verbose)

            # Create Glossary.md if missing
            glossary_md = install_path / "brain" / "Glossary" / "Glossary.md"
            if not glossary_md.exists():
                glossary_md.write_text(
                    "# Glossary\n\n"
                    "Key terms and definitions for your organization.\n\n"
                    "<!-- Add terms as you encounter them -->\n"
                )

            # Create Index.md if missing
            index_md = install_path / "brain" / "Index" / "Index.md"
            if not index_md.exists():
                index_md.write_text(
                    "# Brain Index\n\n"
                    "Auto-generated index of brain entities.\n\n"
                    "Run `/brain-load` to regenerate this file.\n"
                )

            # Create .gitignore if missing
            gitignore = install_path / ".gitignore"
            if not gitignore.exists():
                gitignore.write_text(
                    ".env\n.secrets/\n*.log\n.sync_state.json\n"
                    "__pycache__/\n.DS_Store\n"
                )

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

        elif issue_name == "Brain Files":
            # Create missing brain structure files
            glossary_dir = install_path / "brain" / "Glossary"
            glossary_dir.mkdir(parents=True, exist_ok=True)
            glossary_md = glossary_dir / "Glossary.md"
            if not glossary_md.exists():
                glossary_md.write_text(
                    "# Glossary\n\nKey terms and definitions.\n"
                )

            index_dir = install_path / "brain" / "Index"
            index_dir.mkdir(parents=True, exist_ok=True)
            index_md = index_dir / "Index.md"
            if not index_md.exists():
                index_md.write_text(
                    "# Brain Index\n\nRun `/brain-load` to regenerate.\n"
                )
            return True

    except Exception as e:
        if verbose:
            console.print(f"[dim]Fix failed for {issue_name}: {e}[/dim]")

    return False


def _create_user_md(install_path: Path, verbose: bool = False) -> None:
    """Create USER.md from config data."""
    import yaml

    user_md = install_path / "USER.md"
    config_path = install_path / ".config" / "config.yaml"

    name = "PM-OS User"
    email = ""
    role = ""
    team = ""
    timezone = ""

    if config_path.exists():
        try:
            config = yaml.safe_load(config_path.read_text())
            user = config.get("user", {})
            name = user.get("name", name)
            email = user.get("email", email)
            role = user.get("role", role)
            team = user.get("team", team)
            timezone = user.get("timezone", timezone)
        except Exception:
            pass

    content = f"""# {name}

## Profile
- **Name:** {name}
- **Email:** {email}
- **Role:** {role}
- **Team:** {team}
- **Timezone:** {timezone}

## About
<!-- Describe your role and responsibilities -->

## Communication Style
<!-- How you prefer to communicate -->

## Current Priorities
<!-- Your current focus areas -->

## Responsibilities
<!-- Your key responsibilities -->
"""
    user_md.write_text(content)
    if verbose:
        console.print(f"[dim]Created: {user_md}[/dim]")


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

        url = config.get("url") or env_vars.get("JIRA_URL", "") or os.environ.get("JIRA_URL", "")
        email = (config.get("email")
                 or env_vars.get("JIRA_USERNAME", "") or env_vars.get("JIRA_EMAIL", "")
                 or os.environ.get("JIRA_USERNAME", "") or os.environ.get("JIRA_EMAIL", ""))
        token = (config.get("token")
                 or env_vars.get("JIRA_API_TOKEN", "") or env_vars.get("JIRA_TOKEN", "")
                 or os.environ.get("JIRA_API_TOKEN", "") or os.environ.get("JIRA_TOKEN", ""))
        projects = config.get("projects")

        if not all([url, email, token]):
            return False, "Missing Jira credentials (url, email, token)"

        project_list = [p.strip() for p in projects.split(",") if p.strip()] if projects else None

        syncer = JiraSyncer(brain_path, url, email, token, project_list)
        result = syncer.sync()
        return result.to_tuple()

    elif name_lower == "slack":
        from pm_os.wizard.brain_sync.slack_sync import SlackSyncer

        token = (config.get("token")
                 or env_vars.get("SLACK_BOT_TOKEN", "")
                 or os.environ.get("SLACK_BOT_TOKEN", ""))
        channels = config.get("channels")

        if not token:
            return False, "Missing Slack bot token (set SLACK_BOT_TOKEN in .env)"

        channel_list = [c.strip() for c in channels.split(",") if c.strip()] if channels else None

        syncer = SlackSyncer(brain_path, token, channel_list)
        result = syncer.sync()
        return result.to_tuple()

    elif name_lower == "github":
        from pm_os.wizard.brain_sync.github_sync import GitHubSyncer

        token = (config.get("token")
                 or env_vars.get("GITHUB_TOKEN", "") or env_vars.get("GITHUB_HF_PM_OS", "")
                 or os.environ.get("GITHUB_TOKEN", "") or os.environ.get("GITHUB_HF_PM_OS", ""))
        repos = config.get("repos")

        if not token:
            return False, "Missing GitHub token (set GITHUB_TOKEN or GITHUB_HF_PM_OS in .env)"

        repo_list = [r.strip() for r in repos.split(",") if r.strip()] if repos else None

        syncer = GitHubSyncer(brain_path, token, repo_list)
        result = syncer.sync()
        return result.to_tuple()

    elif name_lower == "confluence":
        from pm_os.wizard.brain_sync.confluence_sync import ConfluenceSyncer

        url = (config.get("url")
               or env_vars.get("CONFLUENCE_URL", "")
               or os.environ.get("CONFLUENCE_URL", ""))
        email = (config.get("email")
                 or env_vars.get("CONFLUENCE_EMAIL", "") or env_vars.get("JIRA_USERNAME", "")
                 or os.environ.get("CONFLUENCE_EMAIL", "") or os.environ.get("JIRA_USERNAME", ""))
        token = (config.get("token")
                 or env_vars.get("CONFLUENCE_API_TOKEN", "") or env_vars.get("CONFLUENCE_TOKEN", "")
                 or os.environ.get("CONFLUENCE_API_TOKEN", "") or os.environ.get("CONFLUENCE_TOKEN", ""))
        spaces = config.get("spaces")

        if not all([url, email, token]):
            return False, "Missing Confluence credentials (set CONFLUENCE_URL, CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN in .env)"

        space_list = [spaces] if spaces else None

        syncer = ConfluenceSyncer(brain_path, url, email, token, space_list)
        result = syncer.sync()
        return result.to_tuple()

    elif name_lower == "google":
        from pm_os.wizard.brain_sync.google_sync import GoogleSyncer

        creds_path = config.get("credentials_path")
        if not creds_path:
            return False, "Google OAuth credentials path not configured"

        # Resolve credentials and token paths relative to install dir
        install_dir = brain_path.parent
        resolved_creds = install_dir / creds_path if creds_path else None
        token_path = install_dir / ".secrets" / "token.json"

        syncer = GoogleSyncer(brain_path, resolved_creds, token_path)
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

        # Check integrations config (also check .env for credentials)
        env_vars = {}
        env_path = install_path / ".env"
        if env_path.exists():
            for line in env_path.read_text().strip().split("\n"):
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()

        # Map integration names to env var patterns that indicate configuration
        integration_env_keys = {
            "jira": ["JIRA_URL", "JIRA_API_TOKEN", "JIRA_TOKEN"],
            "slack": ["SLACK_BOT_TOKEN"],
            "github": ["GITHUB_TOKEN", "GITHUB_HF_PM_OS"],
            "confluence": ["CONFLUENCE_URL", "CONFLUENCE_API_TOKEN", "CONFLUENCE_TOKEN"],
            "google": ["GOOGLE_CREDENTIALS_PATH"],
        }

        integrations = config.get("integrations", {})
        for name, cfg in integrations.items():
            if cfg.get("enabled"):
                has_config = any(cfg.get(k) for k in ["url", "token", "credentials_path", "email"])
                has_env = any(env_vars.get(k) or os.environ.get(k) for k in integration_env_keys.get(name, []))
                if not has_config and not has_env:
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
