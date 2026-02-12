"""Tests for PM-OS wizard exceptions."""

import pytest


class TestPMOSExceptions:
    """Test custom exception types."""

    def test_base_error_message(self):
        """Test base PMOSError with message only."""
        from pm_os.wizard.exceptions import PMOSError

        error = PMOSError("Something went wrong")
        assert error.message == "Something went wrong"
        assert error.remediation is None
        assert error.details is None
        assert "Something went wrong" in str(error)

    def test_base_error_with_remediation(self):
        """Test PMOSError with remediation."""
        from pm_os.wizard.exceptions import PMOSError

        error = PMOSError(
            "Something went wrong",
            remediation="Try again later"
        )
        assert "Something went wrong" in str(error)
        assert "To fix: Try again later" in str(error)

    def test_base_error_with_details(self):
        """Test PMOSError with details."""
        from pm_os.wizard.exceptions import PMOSError

        error = PMOSError(
            "Something went wrong",
            details="Connection timeout after 30s"
        )
        assert "Something went wrong" in str(error)
        assert "Details: Connection timeout" in str(error)

    def test_config_error(self):
        """Test ConfigError with config key."""
        from pm_os.wizard.exceptions import ConfigError

        error = ConfigError(
            "Invalid configuration",
            config_key="llm_provider"
        )
        assert error.config_key == "llm_provider"
        assert "llm_provider" in str(error)
        assert "config.yaml" in str(error)

    def test_credential_error(self):
        """Test CredentialError with credential type."""
        from pm_os.wizard.exceptions import CredentialError

        error = CredentialError(
            "Invalid API key",
            credential_type="Anthropic"
        )
        assert error.credential_type == "Anthropic"
        assert "Anthropic" in str(error)

    def test_sync_error(self):
        """Test SyncError with service name."""
        from pm_os.wizard.exceptions import SyncError

        error = SyncError(
            "Failed to sync",
            service="Jira"
        )
        assert error.service == "Jira"
        assert "jira" in str(error).lower()

    def test_network_error(self):
        """Test NetworkError with endpoint."""
        from pm_os.wizard.exceptions import NetworkError

        error = NetworkError(
            "Connection failed",
            endpoint="https://api.example.com"
        )
        assert error.endpoint == "https://api.example.com"
        assert "internet connection" in str(error).lower()

    def test_validation_error(self):
        """Test ValidationError with field and format."""
        from pm_os.wizard.exceptions import ValidationError

        error = ValidationError(
            "Invalid email",
            field="email",
            expected_format="user@example.com"
        )
        assert error.field == "email"
        assert error.expected_format == "user@example.com"
        assert "format" in str(error)

    def test_setup_error(self):
        """Test SetupError with step name."""
        from pm_os.wizard.exceptions import SetupError

        error = SetupError(
            "Step failed",
            step="profile"
        )
        assert error.step == "profile"
        assert "pm-os doctor" in str(error)

    def test_session_error_stale(self):
        """Test SessionError for stale session."""
        from pm_os.wizard.exceptions import SessionError

        error = SessionError(
            "Session too old",
            session_age_hours=48.5
        )
        assert error.session_age_hours == 48.5
        assert "stale" in str(error).lower()
        assert ">24h" in str(error)

    def test_cleanup_error(self):
        """Test CleanupError with partial files."""
        from pm_os.wizard.exceptions import CleanupError

        error = CleanupError(
            "Cleanup failed",
            partial_files=["/path/to/file1", "/path/to/file2"]
        )
        assert error.partial_files == ["/path/to/file1", "/path/to/file2"]
        assert "Manual cleanup" in str(error)

    def test_dependency_error_with_command(self):
        """Test DependencyError with install command."""
        from pm_os.wizard.exceptions import DependencyError

        error = DependencyError(
            "Missing boto3",
            package="boto3",
            install_command="pip install boto3"
        )
        assert error.package == "boto3"
        assert "pip install boto3" in str(error)


class TestErrorCodes:
    """Test error code mapping."""

    def test_get_error_code_known_type(self):
        """Test getting error code for known type."""
        from pm_os.wizard.exceptions import (
            ConfigError, CredentialError, SyncError,
            get_error_code
        )

        assert get_error_code(ConfigError("test")) == 10
        assert get_error_code(CredentialError("test")) == 11
        assert get_error_code(SyncError("test")) == 12

    def test_get_error_code_unknown_type(self):
        """Test getting error code for unknown type."""
        from pm_os.wizard.exceptions import get_error_code

        assert get_error_code(ValueError("test")) == 1
        assert get_error_code(RuntimeError("test")) == 1


class TestWizardStateSession:
    """Test WizardState session features."""

    def test_session_age(self):
        """Test session age calculation."""
        from pm_os.wizard.orchestrator import WizardState
        from datetime import datetime, timedelta

        # Recent session
        state = WizardState(started_at=datetime.now().isoformat())
        assert state.get_age_hours() < 1

        # Old session (25 hours ago)
        old_time = datetime.now() - timedelta(hours=25)
        state = WizardState(started_at=old_time.isoformat())
        assert state.get_age_hours() > 24

    def test_session_staleness(self):
        """Test session staleness check."""
        from pm_os.wizard.orchestrator import WizardState
        from datetime import datetime, timedelta

        # Fresh session
        state = WizardState(started_at=datetime.now().isoformat())
        assert not state.is_stale()

        # Stale session
        old_time = datetime.now() - timedelta(hours=25)
        state = WizardState(started_at=old_time.isoformat())
        assert state.is_stale()

    def test_session_staleness_custom_threshold(self):
        """Test staleness with custom threshold."""
        from pm_os.wizard.orchestrator import WizardState
        from datetime import datetime, timedelta

        # 2 hours old
        old_time = datetime.now() - timedelta(hours=2)
        state = WizardState(started_at=old_time.isoformat())

        assert not state.is_stale(threshold_hours=24)
        assert state.is_stale(threshold_hours=1)

    def test_state_from_dict_legacy(self):
        """Test loading legacy state without new fields."""
        from pm_os.wizard.orchestrator import WizardState

        legacy_data = {
            "started_at": "2026-01-01T00:00:00",
            "current_step": 2,
            "completed_steps": [0, 1],
            "data": {"key": "value"},
            "aborted": False,
            "completed": False
        }

        state = WizardState.from_dict(legacy_data)
        assert state.created_files == []
        assert state.created_dirs == []
        assert state.step_retries == {}
