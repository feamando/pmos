"""
Directories Step

Create the PM-OS directory structure and configuration files.
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from pm_os.wizard.orchestrator import WizardOrchestrator


# Complete PM-OS directory structure
DIRECTORY_STRUCTURE = [
    # Brain directories
    "brain/Glossary",
    "brain/Index",
    "brain/Entities/People",
    "brain/Entities/Teams",
    "brain/Entities/Products",
    "brain/Entities/Projects",
    "brain/Entities/Stakeholders",
    "brain/Entities/Decisions",
    "brain/Entities/Experiments",
    "brain/Entities/Metrics",
    "brain/Entities/Processes",
    "brain/Entities/Tools",
    "brain/Context",
    "brain/Templates",
    "brain/Inbox",
    "brain/Caches",
    "brain/Confucius",

    # Sessions
    "sessions/active",
    "sessions/archive",

    # Personal
    "personal/calendar",
    "personal/context",
    "personal/context/raw",
    "personal/emails",
    "personal/notes",
    "personal/todos",
    "personal/development",
    "personal/reflections",

    # Team
    "team/reports",
    "team/stakeholders",
    "team/meetings",
    "team/onboarding",

    # Products
    "products",

    # Planning
    "planning/Sprints",
    "planning/Reporting",
    "planning/Roadmaps",
    "planning/Templates",
    "planning/Meeting_Prep",

    # Config and secrets
    ".config",
    ".secrets",
]


def create_directory_structure(base_path: Path, ui) -> bool:
    """Create the PM-OS directory structure."""
    created = 0
    existed = 0

    for dir_path in DIRECTORY_STRUCTURE:
        full_path = base_path / dir_path
        if not full_path.exists():
            full_path.mkdir(parents=True, exist_ok=True)
            created += 1
        else:
            existed += 1

    # Set secure permissions on .secrets directory (700 - owner only)
    secrets_path = base_path / ".secrets"
    if secrets_path.exists():
        os.chmod(secrets_path, 0o700)

    return created, existed


def generate_env_file(wizard: "WizardOrchestrator", base_path: Path) -> str:
    """Generate .env file from wizard data."""
    lines = [
        "# PM-OS Environment Configuration",
        f"# Generated: {datetime.now().isoformat()}",
        "",
        "# User Profile",
        f"PMOS_USER_NAME=\"{wizard.get_data('user_name', '')}\"",
        f"PMOS_USER_EMAIL=\"{wizard.get_data('user_email', '')}\"",
        f"PMOS_USER_ROLE=\"{wizard.get_data('user_role', '')}\"",
        f"PMOS_USER_TEAM=\"{wizard.get_data('user_team', '')}\"",
        f"PMOS_USER_TIMEZONE=\"{wizard.get_data('user_timezone', 'UTC')}\"",
        "",
        "# LLM Configuration",
        f"PMOS_LLM_PROVIDER=\"{wizard.get_data('llm_provider', '')}\"",
        f"PMOS_LLM_MODEL=\"{wizard.get_data('llm_model', '')}\"",
    ]

    # Provider-specific settings
    provider = wizard.get_data("llm_provider", "")
    if provider == "bedrock":
        lines.extend([
            f"AWS_REGION=\"{wizard.get_data('aws_region', 'us-east-1')}\"",
        ])
    elif provider == "anthropic":
        lines.extend([
            f"ANTHROPIC_API_KEY=\"{wizard.get_data('anthropic_api_key', '')}\"",
        ])
    elif provider == "openai":
        lines.extend([
            f"OPENAI_API_KEY=\"{wizard.get_data('openai_api_key', '')}\"",
        ])
    elif provider == "ollama":
        lines.extend([
            f"OLLAMA_HOST=\"{wizard.get_data('ollama_host', 'http://localhost:11434')}\"",
        ])

    lines.append("")

    # Jira
    if wizard.get_data("jira_url"):
        lines.extend([
            "# Jira",
            f"JIRA_URL=\"{wizard.get_data('jira_url', '')}\"",
            f"JIRA_EMAIL=\"{wizard.get_data('jira_email', '')}\"",
            f"JIRA_TOKEN=\"{wizard.get_data('jira_token', '')}\"",
            f"JIRA_PROJECTS=\"{wizard.get_data('jira_projects', '')}\"",
            "",
        ])

    # Slack
    if wizard.get_data("slack_bot_token"):
        lines.extend([
            "# Slack",
            "SLACK_BOT_" + f"TOKEN=\"{wizard.get_data('slack_bot_token', '')}\"",
            f"SLACK_BOT_USER_ID=\"{wizard.get_data('slack_bot_user_id', '')}\"",
            f"SLACK_CHANNELS=\"{wizard.get_data('slack_channels', '')}\"",
            "",
        ])

    # GitHub
    if wizard.get_data("github_token"):
        lines.extend([
            "# GitHub",
            f"GITHUB_TOKEN=\"{wizard.get_data('github_token', '')}\"",
            f"GITHUB_REPOS=\"{wizard.get_data('github_repos', '')}\"",
            "",
        ])

    # Confluence
    if wizard.get_data("confluence_url"):
        lines.extend([
            "# Confluence",
            f"CONFLUENCE_URL=\"{wizard.get_data('confluence_url', '')}\"",
            f"CONFLUENCE_EMAIL=\"{wizard.get_data('confluence_email', '')}\"",
            f"CONFLUENCE_TOKEN=\"{wizard.get_data('confluence_token', '')}\"",
            f"CONFLUENCE_SPACE=\"{wizard.get_data('confluence_space', '')}\"",
            "",
        ])

    # Google
    if wizard.get_data("google_credentials_path"):
        lines.extend([
            "# Google",
            f"GOOGLE_CREDENTIALS_PATH=\"{wizard.get_data('google_credentials_path', '')}\"",
        ])
        if wizard.get_data("google_token_path"):
            lines.append(f"GOOGLE_TOKEN_PATH=\"{wizard.get_data('google_token_path', '')}\"")
        lines.append("")

    # Paths
    lines.extend([
        "# Paths",
        f"PM_OS_USER=\"{base_path}\"",
        f"PM_OS_BRAIN=\"{base_path / 'brain'}\"",
    ])

    return "\n".join(lines)


def generate_config_yaml(wizard: "WizardOrchestrator") -> str:
    """Generate config.yaml from wizard data."""
    import yaml

    config = {
        "version": "3.1",
        "user": {
            "name": wizard.get_data("user_name", ""),
            "email": wizard.get_data("user_email", ""),
            "role": wizard.get_data("user_role", ""),
            "team": wizard.get_data("user_team", ""),
            "timezone": wizard.get_data("user_timezone", "UTC"),
        },
        "llm": {
            "provider": wizard.get_data("llm_provider", ""),
            "model": wizard.get_data("llm_model", ""),
        },
        "integrations": {
            "jira": {
                "enabled": bool(wizard.get_data("jira_url")),
                "url": wizard.get_data("jira_url", ""),
                "projects": wizard.get_data("jira_projects", "").split(",") if wizard.get_data("jira_projects") else [],
            },
            "slack": {
                "enabled": bool(wizard.get_data("slack_bot_token")),
            },
            "github": {
                "enabled": bool(wizard.get_data("github_token") or wizard.get_data("github_auth_method") == "gh_cli"),
                "repos": wizard.get_data("github_repos", "").split(",") if wizard.get_data("github_repos") else [],
            },
            "confluence": {
                "enabled": bool(wizard.get_data("confluence_url")),
                "space": wizard.get_data("confluence_space", ""),
            },
            "google": {
                "enabled": bool(wizard.get_data("google_authenticated")),
            },
        },
        "brain": {
            "auto_sync": True,
            "sync_interval_hours": 24,
        },
    }

    return yaml.dump(config, default_flow_style=False, sort_keys=False)


def generate_user_md(wizard: "WizardOrchestrator") -> str:
    """Generate USER.md persona file."""
    name = wizard.get_data("user_name", "User")
    email = wizard.get_data("user_email", "")
    role = wizard.get_data("user_role", "Product Manager")
    team = wizard.get_data("user_team", "")

    content = f"""# {name}

## Profile

- **Name**: {name}
- **Email**: {email}
- **Role**: {role}
"""

    if team:
        content += f"- **Team**: {team}\n"

    content += f"""
## About

{name} is a {role}{' on the ' + team + ' team' if team else ''}.

## Communication Style

- Professional and clear
- Data-driven decision making
- Collaborative approach

## Key Responsibilities

- Product strategy and roadmap
- Stakeholder management
- Feature prioritization
- Team coordination

---
*Generated by PM-OS on {datetime.now().strftime('%Y-%m-%d')}*
"""

    return content


def create_user_entity(wizard: "WizardOrchestrator", base_path: Path) -> None:
    """Create the user entity in the brain."""
    import time
    people_path = base_path / "brain" / "Entities" / "People"
    people_path.mkdir(parents=True, exist_ok=True)

    name = wizard.get_data("user_name", "User")
    email = wizard.get_data("user_email", "")
    role = wizard.get_data("user_role", "")
    team = wizard.get_data("user_team", "")

    filename = name.replace(" ", "_") + ".md"
    filepath = people_path / filename

    # Don't overwrite if it already exists
    if filepath.exists():
        return

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
    filepath.write_text(content)
    wizard.track_file(filepath)


def generate_gitignore(base_path: Path) -> None:
    """Generate .gitignore with security-sensitive entries."""
    gitignore_content = """# PM-OS Generated .gitignore
# Security-sensitive files - DO NOT COMMIT

# Environment and secrets
.env
.env.*
.secrets/
*.secret
credentials.json
token.json

# API keys and tokens (if accidentally created as files)
*_api_key*
*_token*
*.pem
*.key

# Logs
*.log
logs/

# Session state
.pm-os-init-session.json

# Python
__pycache__/
*.py[cod]
*$py.class
.Python
*.so

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db
"""
    gitignore_path = base_path / ".gitignore"
    gitignore_path.write_text(gitignore_content)


def create_initial_brain_files(base_path: Path) -> None:
    """Create initial brain files including BRAIN.md, hot_topics.json, Glossary, and Index."""
    import json
    brain_path = base_path / "brain"

    # Glossary.md
    glossary = """# PM-OS Glossary

A glossary of terms used in your PM-OS instance.

## Terms

<!-- Add your team's terminology here -->

### PM-OS
The AI-powered Product Management Operating System.

### Brain
The knowledge graph that stores entities, relationships, and context.

### Entity
A discrete unit of knowledge (person, project, decision, etc.).

### Boot
The startup sequence that loads context, syncs integrations, and prepares your session.

### Confucius
The PM-OS knowledge synthesis engine that processes context into actionable insights.

---
*Initialized by PM-OS*
"""
    (brain_path / "Glossary" / "Glossary.md").write_text(glossary)

    # Index.md
    index = """# Brain Index

Quick reference to key entities in your PM-OS brain.

## People

<!-- People entities will be listed here after brain sync -->

## Projects

<!-- Project entities will be listed here after brain sync -->

## Decisions

<!-- Recent decisions will be listed here after brain sync -->

## How to Populate

Run `pm-os brain sync` or use `/boot` in Claude Code to populate
your brain with entities from configured integrations.

---
*Initialized by PM-OS*
"""
    (brain_path / "Index" / "Index.md").write_text(index)

    # BRAIN.md - Compressed entity index for agent context
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    brain_md = f"""# BRAIN.md — Entity Index
<!-- Generated: {now} | Entities: 0 | Tier1: 0 | Tier2: 0 -->

## Team (Tier 1)
id|type|role|squad|status|relationships

<!-- No entities yet. Run /boot or pm-os brain sync to populate. -->

## Connected Entities (Tier 2)
id|type|name|status

<!-- Entities from integrations will appear here after sync. -->
"""
    (brain_path / "BRAIN.md").write_text(brain_md)

    # hot_topics.json - Empty initial structure
    hot_topics = {
        "generated": now,
        "source": "initial",
        "entity_count": 0,
        "entities": {}
    }
    (brain_path / "hot_topics.json").write_text(json.dumps(hot_topics, indent=2) + "\n")


def directories_step(wizard: "WizardOrchestrator") -> bool:
    """Create directories and configuration files.

    Returns:
        True to continue, False to abort
    """
    wizard.console.print("[bold]Creating PM-OS directory structure...[/bold]")
    wizard.console.print()

    base_path = wizard.get_install_path()

    # Create directories
    created, existed = wizard.ui.show_progress(
        "Creating directories...",
        lambda: create_directory_structure(base_path, wizard.ui)
    )

    wizard.ui.print_success(f"Directories: {created} created, {existed} already existed")

    # Generate and write .env with secure permissions
    wizard.console.print()
    env_content = generate_env_file(wizard, base_path)
    env_path = base_path / ".env"
    env_path.write_text(env_content)
    # Set permissions to 600 (owner read/write only) for security
    os.chmod(env_path, 0o600)
    wizard.ui.print_success(f"Created: {env_path} (permissions: 600)")

    # Generate and write config.yaml
    config_content = generate_config_yaml(wizard)
    config_path = base_path / ".config" / "config.yaml"
    config_path.write_text(config_content)
    wizard.ui.print_success(f"Created: {config_path}")

    # Generate USER.md
    user_md_content = generate_user_md(wizard)
    user_md_path = base_path / "USER.md"
    user_md_path.write_text(user_md_content)
    wizard.ui.print_success(f"Created: {user_md_path}")

    # Create initial brain files
    create_initial_brain_files(base_path)
    wizard.ui.print_success("Created initial brain files (BRAIN.md, Glossary.md, Index.md, hot_topics.json)")

    # Create user entity in brain (so it exists even if brain_population is skipped)
    create_user_entity(wizard, base_path)
    wizard.ui.print_success("Created user entity in brain")

    # Generate .gitignore for security
    generate_gitignore(base_path)
    wizard.ui.print_success("Created .gitignore (protects .env, .secrets/)")

    wizard.console.print()
    wizard.ui.show_summary_table("Installation Path", {
        "Base": str(base_path),
        "Brain": str(base_path / "brain"),
        "Config": str(config_path),
        "Environment": str(env_path),
    })

    # Show security warning
    wizard.console.print()
    show_security_warning(wizard)

    return True


def show_security_warning(wizard: "WizardOrchestrator") -> None:
    """Display security warning about credential storage."""
    from rich.panel import Panel

    warning_text = """[yellow]Security Notice[/yellow]

Your API credentials are stored in [bold].env[/bold] with restricted permissions (600).

[bold]Important:[/bold]
• The .gitignore file protects .env from accidental commits
• Never share or commit your .env file to version control
• Consider using a secrets manager for production environments
• Run [cyan]pm-os doctor[/cyan] periodically to verify security settings

[dim]For enhanced security, see: pm-os.dev/docs/security[/dim]"""

    wizard.console.print(Panel(
        warning_text,
        border_style="yellow",
        title="🔒 Security",
        padding=(1, 2)
    ))
