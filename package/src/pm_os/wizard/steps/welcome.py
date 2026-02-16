"""
Welcome Step

Display PM-OS overview and what will be configured.
"""

from typing import TYPE_CHECKING
from rich.panel import Panel

if TYPE_CHECKING:
    from pm_os.wizard.orchestrator import WizardOrchestrator


WELCOME_TEXT = """
[bold]Welcome to PM-OS![/bold]

PM-OS is an AI-powered Product Management Operating System that helps you:

• [cyan]Sync daily context[/cyan] from Jira, Slack, Calendar, GitHub
• [cyan]Build a knowledge graph[/cyan] (Brain) of people, projects, and decisions
• [cyan]Generate documents[/cyan] like PRDs, meeting prep, and sprint reports
• [cyan]Maintain session continuity[/cyan] across conversations with AI

[bold]This wizard will configure:[/bold]

1. Your user profile (name, email, role)
2. LLM provider (Bedrock, Anthropic, OpenAI, or Ollama)
3. Integrations (Slack, Jira, GitHub, Google - all optional)
4. Directory structure and configuration files
5. Initial Brain population from your integrations

[dim]Estimated time: 5-10 minutes (+ optional brain sync)[/dim]
"""


QUICK_WELCOME_TEXT = """
[bold]PM-OS Quick Setup[/bold]

This quick setup will get you started in ~5 minutes:

• [cyan]Auto-detect[/cyan] your profile from git config
• [cyan]Configure[/cyan] your LLM provider (Claude, etc.)
• [cyan]Create[/cyan] the PM-OS directory structure

[bold]What's skipped (can add later):[/bold]
• Integrations (Jira, Slack, GitHub, etc.)
• Initial brain population

[dim]Run 'pm-os setup integrations' later to add integrations.[/dim]
[dim]Run 'pm-os brain sync' later to populate your brain.[/dim]
"""


def welcome_step(wizard: "WizardOrchestrator") -> bool:
    """Display welcome message and overview.

    Returns:
        True to continue, False to abort
    """
    # Show appropriate welcome message based on mode
    welcome_text = QUICK_WELCOME_TEXT if wizard.quick_mode else WELCOME_TEXT

    wizard.console.print(Panel(
        welcome_text,
        border_style="blue",
        padding=(1, 2)
    ))

    wizard.console.print()

    # Confirm user wants to proceed (skip in quick mode)
    if not wizard.quick_mode:
        if not wizard.ui.prompt_confirm("Ready to begin?", default=True):
            wizard.console.print()
            wizard.ui.print_info("Installation cancelled. Run 'pm-os init' when ready.")
            return False

    return True
