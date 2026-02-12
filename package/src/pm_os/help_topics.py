"""
Progressive help system content for PM-OS CLI.

Provides detailed help topics accessible via 'pm-os help <topic>'.
"""

from typing import List, Tuple, Optional


HELP_TOPICS = {
    "brain": {
        "description": "Understanding the PM-OS knowledge graph",
        "content": """
[bold]The PM-OS Brain[/bold]

The Brain is a local knowledge graph that stores and organizes your PM context:

[bold cyan]Entity Types:[/bold cyan]
  People     - Team members, stakeholders, contacts
  Projects   - Products, initiatives, workstreams
  Decisions  - Key decisions with context and rationale
  Issues     - Jira tickets, GitHub issues
  Documents  - PRDs, specs, meeting notes

[bold cyan]Directory Structure:[/bold cyan]
  brain/
  ├── Entities/       # Core entity files (.md)
  ├── Glossary/       # Team terminology
  ├── Index/          # Quick reference
  ├── Context/        # Daily context files
  └── Templates/      # Document templates

[bold cyan]Common Commands:[/bold cyan]
  pm-os brain sync              # Sync from integrations
  pm-os brain status            # Show entity counts
  pm-os brain sync --dry-run    # Preview sync changes
  pm-os brain sync -i jira      # Sync only Jira

[dim]More: https://pm-os.dev/docs/brain[/dim]
"""
    },

    "integrations": {
        "description": "Setting up and managing integrations",
        "content": """
[bold]PM-OS Integrations[/bold]

Integrations connect PM-OS to your existing tools.

[bold cyan]Supported Integrations:[/bold cyan]
  [green]Jira[/green]       - Issues, sprints, projects
  [green]Slack[/green]      - Messages, channels, mentions
  [green]GitHub[/green]     - PRs, issues, repos
  [green]Confluence[/green] - Documentation, spaces
  [green]Google[/green]     - Calendar, Drive, Gmail

[bold cyan]Setup Commands:[/bold cyan]
  pm-os setup integrations --list     # List all
  pm-os setup integrations jira       # Configure Jira
  pm-os setup integrations slack      # Configure Slack

[bold cyan]After Setup:[/bold cyan]
  pm-os brain sync --integration jira # Sync specific
  pm-os config show                   # View config

[bold cyan]Credentials:[/bold cyan]
Credentials are stored in ~/.pm-os/.env with 600 permissions.
Never commit this file to version control.

[dim]More: https://pm-os.dev/docs/integrations[/dim]
"""
    },

    "troubleshoot": {
        "description": "Diagnosing and fixing common issues",
        "content": """
[bold]Troubleshooting PM-OS[/bold]

[bold cyan]Health Check:[/bold cyan]
Run 'pm-os doctor' to diagnose issues:
  - Checks directory structure
  - Validates configuration
  - Tests credentials

[bold cyan]Common Issues:[/bold cyan]

[yellow]Config not found[/yellow]
  Run: pm-os init

[yellow]Sync fails[/yellow]
  Check: pm-os config show
  Test: pm-os brain sync --dry-run
  Fix: pm-os setup integrations <name>

[yellow]Missing directories[/yellow]
  Run: pm-os doctor --fix

[yellow]Credential errors[/yellow]
  Update: pm-os config set llm.api_key <key>

[bold cyan]Reset Installation:[/bold cyan]
  pm-os uninstall --keep-brain  # Remove config, keep data
  pm-os init                    # Fresh install

[dim]More: https://pm-os.dev/docs/troubleshooting[/dim]
"""
    },

    "quick-start": {
        "description": "Getting started quickly",
        "content": """
[bold]PM-OS Quick Start Guide[/bold]

[bold cyan]5-Minute Setup:[/bold cyan]

1. [green]Install:[/green]
   pip install pm-os

2. [green]Quick Init:[/green]
   pm-os init --quick

   This auto-detects your profile from git and
   only asks for your LLM API key.

3. [green]Verify:[/green]
   pm-os doctor

4. [green]Add Integrations (optional):[/green]
   pm-os setup integrations jira
   pm-os setup integrations slack

5. [green]Sync Brain:[/green]
   pm-os brain sync

[bold cyan]What Quick Mode Skips:[/bold cyan]
  - Integration setup (Jira, Slack, etc.)
  - Initial brain population

You can add these later with:
  pm-os setup integrations <name>
  pm-os brain sync

[dim]Full guide: https://pm-os.dev/docs/quick-start[/dim]
"""
    },

    "skills": {
        "description": "Using PM-OS skills and automation",
        "content": """
[bold]PM-OS Skills[/bold]

Skills are pre-built automations for common PM tasks.

[bold cyan]Available Skills:[/bold cyan]
  Meeting Prep      - Generate context for upcoming meetings
  Sprint Report     - Create sprint summaries
  PRD Generator     - Draft product requirements
  Context Update    - Refresh daily context

[bold cyan]Using Skills:[/bold cyan]
Skills are accessed through Claude Code when working
in your PM-OS directory. Example prompts:

  "Prepare me for my 1:1 with Sarah"
  "Generate this week's sprint report"
  "Draft a PRD for the search feature"
  "Update my context"

[bold cyan]Slash Commands:[/bold cyan]
Many skills have slash command shortcuts:
  /meeting-prep
  /sprint-report
  /update-context
  /prd

[dim]More: https://pm-os.dev/docs/skills[/dim]
"""
    },
}


def list_topics() -> List[Tuple[str, str]]:
    """List all help topics with descriptions.

    Returns:
        List of (topic_name, description) tuples
    """
    return [(name, data["description"]) for name, data in HELP_TOPICS.items()]


def get_help_content(topic: str) -> Optional[str]:
    """Get help content for a topic.

    Args:
        topic: Topic name (case-insensitive)

    Returns:
        Help content string or None if topic not found
    """
    topic_data = HELP_TOPICS.get(topic.lower())
    return topic_data["content"] if topic_data else None


def get_topic_names() -> List[str]:
    """Get list of all topic names.

    Returns:
        List of topic names
    """
    return list(HELP_TOPICS.keys())
