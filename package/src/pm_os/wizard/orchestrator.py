"""
PM-OS Wizard Orchestrator

Manages the wizard flow, step sequencing, and session state for abort/resume.
"""

import json
import shutil
import signal
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from rich.console import Console

from pm_os.wizard.ui import WizardUI
from pm_os.wizard.exceptions import (
    SessionError, SetupError, CleanupError, PMOSError, get_error_code
)


# Session staleness threshold in hours
SESSION_STALE_HOURS = 24


@dataclass
class WizardState:
    """Persistent state for wizard session."""
    started_at: str = ""
    current_step: int = 0
    completed_steps: List[int] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    aborted: bool = False
    completed: bool = False
    created_files: List[str] = field(default_factory=list)
    created_dirs: List[str] = field(default_factory=list)
    step_retries: Dict[str, int] = field(default_factory=dict)
    setup_mode: str = "standard"  # "standard" or "quick"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "WizardState":
        # Handle legacy sessions without new fields
        defaults = {
            'created_files': [],
            'created_dirs': [],
            'step_retries': {},
            'setup_mode': 'standard'
        }
        for key, default in defaults.items():
            if key not in data:
                data[key] = default
        return cls(**data)

    def get_age_hours(self) -> float:
        """Get session age in hours."""
        if not self.started_at:
            return 0
        try:
            started = datetime.fromisoformat(self.started_at)
            delta = datetime.now() - started
            return delta.total_seconds() / 3600
        except (ValueError, TypeError):
            return 0

    def is_stale(self, threshold_hours: float = SESSION_STALE_HOURS) -> bool:
        """Check if session is stale (older than threshold)."""
        return self.get_age_hours() > threshold_hours


@dataclass
class StepDefinition:
    """Definition of a wizard step."""
    name: str
    title: str
    description: str
    handler: Callable[["WizardOrchestrator"], bool]
    skippable: bool = False
    requires_steps: List[int] = field(default_factory=list)


class WizardOrchestrator:
    """Orchestrates the PM-OS installation wizard flow."""

    SESSION_FILE = ".pm-os-init-session.json"

    def __init__(
        self,
        console: Optional[Console] = None,
        install_path: Optional[Path] = None,
        quick_mode: bool = False
    ):
        self.console = console or Console()
        self.ui = WizardUI(self.console)
        self.install_path = install_path or Path.home() / "pm-os"
        self.state = WizardState()
        self.steps: List[StepDefinition] = []
        self._interrupted = False
        self.quick_mode = quick_mode

        # Register signal handlers for graceful abort
        signal.signal(signal.SIGINT, self._handle_interrupt)
        signal.signal(signal.SIGTERM, self._handle_interrupt)

    def _handle_interrupt(self, signum, frame):
        """Handle Ctrl+C gracefully."""
        self._interrupted = True
        self.console.print("\n")
        self.ui.print_warning("Installation interrupted. Saving progress...")
        self.state.aborted = True
        self._save_session()
        self.console.print()
        self.console.print("[yellow]To resume installation, run:[/yellow]")
        self.console.print("[cyan]  pm-os init --resume[/cyan]")
        self.console.print()
        sys.exit(130)  # Standard exit code for SIGINT

    def add_step(
        self,
        name: str,
        title: str,
        description: str,
        handler: Callable[["WizardOrchestrator"], bool],
        skippable: bool = False,
        requires_steps: Optional[List[int]] = None
    ):
        """Add a step to the wizard."""
        self.steps.append(StepDefinition(
            name=name,
            title=title,
            description=description,
            handler=handler,
            skippable=skippable,
            requires_steps=requires_steps or []
        ))

    def _get_session_path(self) -> Path:
        """Get the path to the session file."""
        return Path.home() / self.SESSION_FILE

    def _load_session(self) -> bool:
        """Load existing session state. Returns True if session exists."""
        session_path = self._get_session_path()
        if session_path.exists():
            try:
                data = json.loads(session_path.read_text())
                self.state = WizardState.from_dict(data)
                return True
            except (json.JSONDecodeError, KeyError):
                return False
        return False

    def _save_session(self):
        """Save current session state."""
        session_path = self._get_session_path()
        session_path.write_text(json.dumps(self.state.to_dict(), indent=2))

    def _clear_session(self):
        """Clear the session file."""
        session_path = self._get_session_path()
        if session_path.exists():
            session_path.unlink()

    def get_data(self, key: str, default: Any = None) -> Any:
        """Get data from wizard state."""
        return self.state.data.get(key, default)

    def set_data(self, key: str, value: Any):
        """Set data in wizard state and save."""
        self.state.data[key] = value
        self._save_session()

    def update_data(self, data: Dict[str, Any]):
        """Update multiple data values and save."""
        self.state.data.update(data)
        self._save_session()

    def run(self, resume: bool = False, max_retries: int = 3) -> bool:
        """Run the wizard.

        Args:
            resume: Whether to resume from a previous session
            max_retries: Maximum retry attempts per step

        Returns:
            True if wizard completed successfully
        """
        # Check for existing session
        has_session = self._load_session()

        if has_session and not resume:
            if self.quick_mode:
                # In quick mode, always start fresh
                self._clear_session()
                self.state = WizardState()
            else:
                # Ask if user wants to resume
                self.console.print()
                self.ui.print_warning("A previous installation session was found.")
                if self.ui.prompt_confirm("Resume previous session?", default=True):
                    resume = True
                else:
                    self._clear_session()
                    self.state = WizardState()

        # Initialize new session if not resuming
        if not resume or not has_session:
            self.state = WizardState(
                started_at=datetime.now().isoformat(),
                current_step=0,
                completed_steps=[],
                data={},
                aborted=False,
                completed=False,
                created_files=[],
                created_dirs=[],
                step_retries={},
                setup_mode="quick" if self.quick_mode else "standard"
            )
            self._save_session()

        # Show header
        self.ui.clear()
        self.ui.print_header()

        if resume and has_session:
            # Check session staleness
            if not self.check_session_staleness():
                self.ui.print_info("Starting fresh installation.")
                self._clear_session()
                self.state = WizardState(
                    started_at=datetime.now().isoformat()
                )
                self._save_session()
            else:
                self.ui.print_info(f"Resuming from step {self.state.current_step + 1}")

                # Validate session data completeness
                missing_data = self.validate_session_data()
                if missing_data:
                    self.ui.print_warning(
                        f"Some data may be incomplete: {', '.join(missing_data)}"
                    )
                    self.ui.print_info("You may need to re-enter some information.")

            self.console.print()

        # Set total steps for UI
        self.ui._total_steps = len(self.steps)

        # Run steps
        for i, step in enumerate(self.steps):
            if self._interrupted:
                break

            # Skip already completed steps
            if i in self.state.completed_steps:
                continue

            # Skip optional steps in quick mode
            if self.quick_mode and step.skippable:
                self.ui.print_skip(f"{step.title} (skipped in quick mode)")
                self.state.completed_steps.append(i)
                self._save_session()
                continue

            # Update current step
            self.state.current_step = i
            self._save_session()

            # Show step header
            self.ui.print_step_header(
                i + 1,
                step.title,
                step.description
            )

            # Run step handler with retry logic
            success = False
            retry_count = 0
            last_error = None

            while not success and retry_count < max_retries:
                try:
                    success = step.handler(self)
                    if success:
                        self.state.completed_steps.append(i)
                        self.reset_step_retry(step.name)
                        self._save_session()
                    elif step.skippable:
                        self.ui.print_skip(f"Skipped: {step.title}")
                        success = True  # Allow continuing
                    else:
                        last_error = f"Step returned failure"
                        retry_count = self.increment_step_retry(step.name)
                        if retry_count < max_retries:
                            self.ui.print_warning(
                                f"Step failed. Retry {retry_count}/{max_retries}..."
                            )
                            if self.ui.prompt_confirm("Try again?", default=True):
                                continue
                            else:
                                break
                except KeyboardInterrupt:
                    # Let the signal handler deal with it
                    raise
                except PMOSError as e:
                    last_error = e
                    retry_count = self.increment_step_retry(step.name)
                    self.ui.print_error(f"Error: {e.message}")
                    if e.remediation:
                        self.ui.print_info(f"To fix: {e.remediation}")
                    if retry_count < max_retries and not step.skippable:
                        if self.ui.prompt_confirm("Try again?", default=True):
                            continue
                    elif step.skippable:
                        self.ui.print_skip(f"Skipped: {step.title}")
                        success = True
                    break
                except Exception as e:
                    last_error = e
                    retry_count = self.increment_step_retry(step.name)
                    self.ui.print_error(f"Error in step '{step.title}': {e}")
                    if retry_count < max_retries and not step.skippable:
                        if self.ui.prompt_confirm("Try again?", default=True):
                            continue
                    elif step.skippable:
                        self.ui.print_skip(f"Skipped: {step.title}")
                        success = True
                    break

            # Handle step failure after retries exhausted
            if not success and not step.skippable:
                self.ui.print_error(
                    f"Step '{step.title}' failed after {retry_count} attempts."
                )
                if self.ui.prompt_confirm("Clean up and abort installation?", default=True):
                    failed = self.cleanup_on_failure()
                    if failed:
                        self.ui.print_warning(
                            f"Some files couldn't be cleaned up: {', '.join(failed[:3])}"
                        )
                return False

        # Mark as completed
        if not self._interrupted:
            self.state.completed = True
            self._save_session()
            self._clear_session()  # Clean up on success

        return not self._interrupted

    def get_install_path(self) -> Path:
        """Get the installation path."""
        return self.install_path

    def set_install_path(self, path: Path):
        """Set the installation path."""
        self.install_path = path
        self.set_data("install_path", str(path))

    def track_file(self, file_path: Path):
        """Track a created file for cleanup on failure."""
        path_str = str(file_path)
        if path_str not in self.state.created_files:
            self.state.created_files.append(path_str)
            self._save_session()

    def track_directory(self, dir_path: Path):
        """Track a created directory for cleanup on failure."""
        path_str = str(dir_path)
        if path_str not in self.state.created_dirs:
            self.state.created_dirs.append(path_str)
            self._save_session()

    def cleanup_on_failure(self) -> List[str]:
        """Clean up created files and directories on failure.

        Returns:
            List of paths that couldn't be cleaned up
        """
        failed_cleanups = []

        # Remove files first
        for file_path in reversed(self.state.created_files):
            try:
                path = Path(file_path)
                if path.exists():
                    path.unlink()
            except Exception as e:
                failed_cleanups.append(f"{file_path}: {e}")

        # Remove directories (in reverse order to handle nested dirs)
        for dir_path in reversed(self.state.created_dirs):
            try:
                path = Path(dir_path)
                if path.exists():
                    shutil.rmtree(path)
            except Exception as e:
                failed_cleanups.append(f"{dir_path}: {e}")

        # Clear session
        self._clear_session()

        return failed_cleanups

    def check_session_staleness(self) -> bool:
        """Check if the session is stale and warn user.

        Returns:
            True if user wants to continue, False to abort
        """
        if not self.state.is_stale():
            return True

        age_hours = self.state.get_age_hours()
        self.console.print()
        self.ui.print_warning(
            f"This session is {age_hours:.1f} hours old (started {self.state.started_at})."
        )
        self.ui.print_info(
            "Configuration and credentials may be outdated."
        )
        self.console.print()

        return self.ui.prompt_confirm(
            "Continue with this session anyway?",
            default=False
        )

    def validate_session_data(self) -> List[str]:
        """Validate that required session data is present and complete.

        Returns:
            List of missing or invalid data keys
        """
        missing = []

        # Check critical data based on completed steps
        required_by_step = {
            # Step 2 (profile): requires name, email
            2: ["user_name", "user_email"],
            # Step 3 (directories): requires install_path
            3: ["install_path"],
            # Step 4 (LLM): requires provider
            4: ["llm_provider"],
        }

        for step_idx in self.state.completed_steps:
            required_keys = required_by_step.get(step_idx, [])
            for key in required_keys:
                value = self.state.data.get(key)
                if not value or (isinstance(value, str) and not value.strip()):
                    missing.append(key)

        return missing

    def get_step_retry_count(self, step_name: str) -> int:
        """Get the retry count for a step."""
        return self.state.step_retries.get(step_name, 0)

    def increment_step_retry(self, step_name: str) -> int:
        """Increment and return the retry count for a step."""
        count = self.state.step_retries.get(step_name, 0) + 1
        self.state.step_retries[step_name] = count
        self._save_session()
        return count

    def reset_step_retry(self, step_name: str):
        """Reset the retry count for a step."""
        if step_name in self.state.step_retries:
            del self.state.step_retries[step_name]
            self._save_session()
