"""
PM-OS Wizard UI Components

Reusable UI components for the installation wizard using rich library.
"""

import re
from typing import Optional, List, Callable, Any
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.style import Style
import time


# Patterns that indicate a secret value
SECRET_PATTERNS = [
    "token", "password", "secret", "key", "credential",
    "api_key", "apikey", "auth", "bearer", "jwt",
]

# Regex patterns for common secret formats
SECRET_REGEXES = [
    r'sk-ant-[a-zA-Z0-9\-]{20,}',  # Anthropic API keys (new format)
    r'sk-[a-zA-Z0-9]{20,}',  # Anthropic API keys (old format) / OpenAI
    r'xoxb-[a-zA-Z0-9\-]+',  # Slack bot tokens
    r'xoxp-[a-zA-Z0-9\-]+',  # Slack user tokens
    r'ghp_[a-zA-Z0-9]{36,}',  # GitHub PAT
    r'gho_[a-zA-Z0-9]{36,}',  # GitHub OAuth
    r'AKIA[A-Z0-9]{16}',  # AWS Access Key ID
]


def mask_secrets(text: str, mask: str = "********") -> str:
    """Mask secrets in a string.

    Args:
        text: The text that may contain secrets
        mask: The string to replace secrets with

    Returns:
        Text with secrets masked
    """
    if not text:
        return text

    result = text

    # Mask known secret patterns in key=value format
    for pattern in SECRET_PATTERNS:
        # Match pattern="value" or pattern=value
        regex = rf'({pattern}["\']?\s*[=:]\s*["\']?)([^"\'\s]+)(["\']?)'
        result = re.sub(regex, rf'\1{mask}\3', result, flags=re.IGNORECASE)

    # Mask specific secret formats
    for regex in SECRET_REGEXES:
        result = re.sub(regex, mask, result)

    return result


def is_secret_key(key: str) -> bool:
    """Check if a key name indicates it holds a secret value."""
    key_lower = key.lower()
    return any(pattern in key_lower for pattern in SECRET_PATTERNS)


class WizardUI:
    """UI components for the PM-OS installation wizard."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self._step_number = 0
        self._total_steps = 8

    def clear(self):
        """Clear the console."""
        self.console.clear()

    def print_header(self, title: str = "PM-OS Installation Wizard"):
        """Print the wizard header."""
        self.console.print()
        self.console.print(Panel(
            f"[bold blue]{title}[/bold blue]",
            border_style="blue",
            padding=(0, 2)
        ))
        self.console.print()

    def print_step_header(self, step_num: int, title: str, description: str = ""):
        """Print a step header with number and title."""
        self._step_number = step_num
        self.console.print()
        self.console.print(f"[bold cyan]Step {step_num}/{self._total_steps}:[/bold cyan] [bold]{title}[/bold]")
        if description:
            self.console.print(f"[dim]{description}[/dim]")
        self.console.print()

    def print_success(self, message: str):
        """Print a success message."""
        self.console.print(f"[green]✓[/green] {message}")

    def print_error(self, message: str):
        """Print an error message."""
        self.console.print(f"[red]✗[/red] {message}")

    def print_warning(self, message: str):
        """Print a warning message."""
        self.console.print(f"[yellow]⚠[/yellow] {message}")

    def print_info(self, message: str):
        """Print an info message."""
        self.console.print(f"[blue]ℹ[/blue] {message}")

    def print_skip(self, message: str):
        """Print a skip message."""
        self.console.print(f"[dim]○ {message} (skipped)[/dim]")

    def prompt_text(
        self,
        prompt: str,
        default: str = "",
        required: bool = False,
        validator: Optional[Callable[[str], bool]] = None,
        error_message: str = "Invalid input"
    ) -> str:
        """Prompt for text input."""
        while True:
            value = Prompt.ask(prompt, default=default if default else None)

            if required and not value:
                self.print_error("This field is required")
                continue

            if validator and value and not validator(value):
                self.print_error(error_message)
                continue

            return value

    def prompt_password(self, prompt: str, required: bool = False) -> str:
        """Prompt for password/secret input."""
        while True:
            value = Prompt.ask(prompt, password=True)

            if required and not value:
                self.print_error("This field is required")
                continue

            return value

    def prompt_confirm(self, prompt: str, default: bool = False) -> bool:
        """Prompt for yes/no confirmation."""
        return Confirm.ask(prompt, default=default)

    def prompt_choice(
        self,
        prompt: str,
        choices: List[str],
        default: Optional[str] = None
    ) -> str:
        """Prompt for a choice from a list."""
        # Display choices
        self.console.print(f"\n{prompt}")
        for i, choice in enumerate(choices, 1):
            marker = "[bold green]→[/bold green]" if choice == default else " "
            self.console.print(f"  {marker} [{i}] {choice}")

        while True:
            selection = Prompt.ask(
                "Enter number or name",
                default=str(choices.index(default) + 1) if default else None
            )

            # Try numeric selection
            try:
                idx = int(selection) - 1
                if 0 <= idx < len(choices):
                    return choices[idx]
            except ValueError:
                pass

            # Try name match
            for choice in choices:
                if choice.lower() == selection.lower():
                    return choice

            self.print_error(f"Invalid selection. Choose 1-{len(choices)}")

    def prompt_skip_or_configure(self, integration_name: str) -> bool:
        """Prompt to skip or configure an integration."""
        return self.prompt_confirm(
            f"Configure {integration_name}?",
            default=False
        )

    def show_progress(
        self,
        description: str,
        task_func: Callable[[], Any],
        total: int = 100
    ) -> Any:
        """Show a progress spinner while executing a task."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=self.console
        ) as progress:
            task = progress.add_task(description, total=total)
            result = task_func()
            progress.update(task, completed=total)
            return result

    def show_progress_bar(
        self,
        description: str,
        items: List[Any],
        processor: Callable[[Any], None]
    ):
        """Show a progress bar while processing items."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
            console=self.console
        ) as progress:
            task = progress.add_task(description, total=len(items))
            for item in items:
                processor(item)
                progress.advance(task)

    def show_sync_progress(
        self,
        description: str,
        total: int,
        update_callback: Callable[[Callable[[int, str], None]], None]
    ):
        """Show a sync progress bar with real-time updates.

        Args:
            description: Main description
            total: Total number of items
            update_callback: Called with an update function that takes (increment, message)
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
            TextColumn("[dim]{task.fields[phase]}[/dim]"),
            console=self.console
        ) as progress:
            task = progress.add_task(description, total=total, phase="")

            def update(increment: int, message: str = ""):
                progress.update(task, advance=increment, phase=message)

            update_callback(update)

    def prompt_skip_confirm(self, step_name: str, reason: str = "") -> bool:
        """Prompt for confirmation before skipping a step.

        Args:
            step_name: Name of the step being skipped
            reason: Optional reason for skipping

        Returns:
            True if user confirms skip, False to try again
        """
        self.console.print()
        self.print_warning(f"Step '{step_name}' will be skipped.")
        if reason:
            self.console.print(f"[dim]Reason: {reason}[/dim]")
        self.console.print()
        return self.prompt_confirm(
            "Skip this step and continue?",
            default=False
        )

    def show_checklist(self, items: List[tuple[str, bool, str]]):
        """Show a checklist of items with status.

        Args:
            items: List of (name, passed, message) tuples
        """
        for name, passed, message in items:
            if passed:
                self.print_success(f"{name}: {message}")
            else:
                self.print_error(f"{name}: {message}")

    def show_summary_table(self, title: str, data: dict[str, str]):
        """Show a summary table with secrets masked."""
        table = Table(title=title, border_style="blue")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")

        for key, value in data.items():
            # Mask secrets based on key name
            if is_secret_key(key):
                display_value = "********" if value else "[dim]not set[/dim]"
            else:
                # Also mask any secret patterns in the value itself
                display_value = mask_secrets(value) if value else "[dim]not set[/dim]"
            table.add_row(key, display_value)

        self.console.print(table)

    def show_completion_panel(
        self,
        title: str,
        content: str,
        next_steps: List[str]
    ):
        """Show a completion panel with next steps."""
        # Main content
        self.console.print()
        self.console.print(Panel(
            f"[bold green]{title}[/bold green]\n\n{content}",
            border_style="green",
            padding=(1, 2)
        ))

        # Next steps
        if next_steps:
            self.console.print()
            self.console.print("[bold]Next Steps:[/bold]")
            for i, step in enumerate(next_steps, 1):
                self.console.print(f"  {i}. {step}")

    def show_time_warning(self, minutes: int):
        """Show a time warning for long operations."""
        self.console.print()
        self.console.print(Panel(
            f"[yellow]⚠ This step may take {minutes}-{minutes*2} minutes.\n"
            f"Please keep this terminal open until completion.\n\n"
            f"TIP: Press Ctrl+C to skip and complete later with:[/yellow]\n"
            f"[cyan]pm-os brain sync[/cyan]",
            border_style="yellow",
            title="Time Warning"
        ))
        self.console.print()


class ProgressTracker:
    """Track progress of multi-step operations with live updates."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.steps: List[dict] = []
        self.current_step = 0

    def add_step(self, name: str, description: str = ""):
        """Add a step to track."""
        self.steps.append({
            "name": name,
            "description": description,
            "status": "pending",  # pending, running, done, failed, skipped
            "message": "",
            "duration": None
        })

    def start_step(self, index: int):
        """Mark a step as started."""
        self.current_step = index
        self.steps[index]["status"] = "running"
        self.steps[index]["start_time"] = time.time()

    def complete_step(self, index: int, message: str = ""):
        """Mark a step as completed."""
        step = self.steps[index]
        step["status"] = "done"
        step["message"] = message
        if "start_time" in step:
            step["duration"] = time.time() - step["start_time"]

    def fail_step(self, index: int, message: str = ""):
        """Mark a step as failed."""
        step = self.steps[index]
        step["status"] = "failed"
        step["message"] = message
        if "start_time" in step:
            step["duration"] = time.time() - step["start_time"]

    def skip_step(self, index: int, message: str = ""):
        """Mark a step as skipped."""
        self.steps[index]["status"] = "skipped"
        self.steps[index]["message"] = message

    def render(self) -> Table:
        """Render the progress as a table."""
        table = Table(show_header=False, box=None)
        table.add_column("Status", width=3)
        table.add_column("Name")
        table.add_column("Message", style="dim")

        status_icons = {
            "pending": "[dim]○[/dim]",
            "running": "[yellow]▶[/yellow]",
            "done": "[green]✓[/green]",
            "failed": "[red]✗[/red]",
            "skipped": "[dim]○[/dim]"
        }

        for step in self.steps:
            icon = status_icons.get(step["status"], "?")
            name = step["name"]
            message = step["message"]

            if step["status"] == "running":
                name = f"[bold]{name}[/bold]"
            elif step["status"] == "skipped":
                name = f"[dim]{name}[/dim]"
                message = f"[dim]{message}[/dim]"

            if step.get("duration"):
                message = f"{message} ({step['duration']:.1f}s)"

            table.add_row(icon, name, message)

        return table
