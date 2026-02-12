"""Tests for PM-OS CLI."""

import subprocess
import sys

import pytest


class TestCLI:
    """Test CLI entry points and basic functionality."""

    def test_version(self):
        """Test --version flag."""
        result = subprocess.run(
            [sys.executable, "-m", "pm_os.cli", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "pm-os" in result.stdout.lower() or "3." in result.stdout

    def test_help(self):
        """Test --help flag."""
        result = subprocess.run(
            [sys.executable, "-m", "pm_os.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "PM-OS" in result.stdout
        assert "init" in result.stdout
        assert "doctor" in result.stdout

    def test_init_help(self):
        """Test init --help."""
        result = subprocess.run(
            [sys.executable, "-m", "pm_os.cli", "init", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--resume" in result.stdout
        assert "--path" in result.stdout

    def test_doctor_help(self):
        """Test doctor --help."""
        result = subprocess.run(
            [sys.executable, "-m", "pm_os.cli", "doctor", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--fix" in result.stdout

    def test_brain_help(self):
        """Test brain --help."""
        result = subprocess.run(
            [sys.executable, "-m", "pm_os.cli", "brain", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "sync" in result.stdout
        assert "status" in result.stdout

    def test_config_help(self):
        """Test config --help."""
        result = subprocess.run(
            [sys.executable, "-m", "pm_os.cli", "config", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "show" in result.stdout
        assert "edit" in result.stdout


class TestPrerequisites:
    """Test prerequisites checking."""

    def test_check_python_version(self):
        """Test Python version check."""
        from pm_os.wizard.steps.prerequisites import check_python_version

        passed, message = check_python_version()
        assert passed is True
        assert "Python" in message

    def test_check_pip(self):
        """Test pip check."""
        from pm_os.wizard.steps.prerequisites import check_pip

        passed, message = check_pip()
        assert passed is True
        assert "pip" in message

    def test_check_git(self):
        """Test git check."""
        from pm_os.wizard.steps.prerequisites import check_git

        passed, _ = check_git()
        # Git may or may not be installed in test env
        assert isinstance(passed, bool)


class TestSecretMasking:
    """Test secret masking functionality."""

    def test_mask_secrets_api_key(self):
        """Test masking API keys in strings."""
        from pm_os.wizard.ui import mask_secrets

        # Anthropic key pattern
        text = "Using key sk-ant-api03-abcdefghijklmnopqrstuvwxyz"
        result = mask_secrets(text)
        assert "sk-ant" not in result
        assert "********" in result

    def test_mask_secrets_slack_token(self):
        """Test masking Slack tokens."""
        from pm_os.wizard.ui import mask_secrets

        text = "Token: SLACK_BOT_TOKEN_PLACEHOLDER"
        result = mask_secrets(text)
        assert "SLACK_BOT_TOKEN" not in result

    def test_mask_secrets_key_value(self):
        """Test masking key=value patterns."""
        from pm_os.wizard.ui import mask_secrets

        text = 'api_key="my-secret-key-12345"'
        result = mask_secrets(text)
        assert "my-secret-key" not in result

    def test_mask_secrets_preserves_normal_text(self):
        """Test that normal text is not masked."""
        from pm_os.wizard.ui import mask_secrets

        text = "This is normal text with no secrets"
        result = mask_secrets(text)
        assert result == text

    def test_is_secret_key(self):
        """Test identifying secret key names."""
        from pm_os.wizard.ui import is_secret_key

        assert is_secret_key("api_token") is True
        assert is_secret_key("SLACK_TOKEN") is True
        assert is_secret_key("password") is True
        assert is_secret_key("user_name") is False
        assert is_secret_key("email") is False


class TestWizardUI:
    """Test wizard UI components."""

    def test_wizard_ui_init(self):
        """Test WizardUI initialization."""
        from pm_os.wizard.ui import WizardUI

        ui = WizardUI()
        assert ui is not None
        assert ui._total_steps == 8

    def test_progress_tracker(self):
        """Test ProgressTracker."""
        from pm_os.wizard.ui import ProgressTracker

        tracker = ProgressTracker()
        tracker.add_step("Step 1", "Description 1")
        tracker.add_step("Step 2", "Description 2")

        assert len(tracker.steps) == 2
        assert tracker.steps[0]["name"] == "Step 1"
        assert tracker.steps[0]["status"] == "pending"

        tracker.start_step(0)
        assert tracker.steps[0]["status"] == "running"

        tracker.complete_step(0, "Done")
        assert tracker.steps[0]["status"] == "done"


class TestWizardOrchestrator:
    """Test wizard orchestrator."""

    def test_orchestrator_init(self):
        """Test WizardOrchestrator initialization."""
        from pm_os.wizard.orchestrator import WizardOrchestrator

        orchestrator = WizardOrchestrator()
        assert orchestrator is not None
        assert orchestrator.state is not None

    def test_orchestrator_add_step(self):
        """Test adding steps to orchestrator."""
        from pm_os.wizard.orchestrator import WizardOrchestrator

        orchestrator = WizardOrchestrator()
        orchestrator.add_step(
            name="test",
            title="Test Step",
            description="A test step",
            handler=lambda w: True,
        )

        assert len(orchestrator.steps) == 1
        assert orchestrator.steps[0].name == "test"

    def test_wizard_state(self):
        """Test WizardState dataclass."""
        from pm_os.wizard.orchestrator import WizardState

        state = WizardState()
        assert state.current_step == 0
        assert state.completed_steps == []
        assert state.data == {}
        assert state.aborted is False
        assert state.completed is False

        # Test serialization
        data = state.to_dict()
        assert "current_step" in data
        assert "completed_steps" in data

        # Test deserialization
        state2 = WizardState.from_dict(data)
        assert state2.current_step == state.current_step


class TestDirectories:
    """Test directory structure generation."""

    def test_directory_structure_defined(self):
        """Test DIRECTORY_STRUCTURE is defined."""
        from pm_os.wizard.steps.directories import DIRECTORY_STRUCTURE

        assert isinstance(DIRECTORY_STRUCTURE, list)
        assert len(DIRECTORY_STRUCTURE) > 0
        assert "brain/Entities/People" in DIRECTORY_STRUCTURE
        assert ".config" in DIRECTORY_STRUCTURE


class TestSteps:
    """Test step definitions."""

    def test_wizard_steps_defined(self):
        """Test WIZARD_STEPS is properly defined."""
        from pm_os.wizard.steps import WIZARD_STEPS

        assert isinstance(WIZARD_STEPS, list)
        assert len(WIZARD_STEPS) == 8  # 8 steps in the wizard

        # Check step structure
        for step in WIZARD_STEPS:
            assert "name" in step
            assert "title" in step
            assert "description" in step
            assert "handler" in step
            assert callable(step["handler"])
