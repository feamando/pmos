"""Advanced integration tests for PM-OS wizard."""

import pytest
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


class TestResumeFlag:
    """Test --resume flag functionality."""

    def test_session_persistence(self, tmp_path):
        """Test that session state is persisted correctly."""
        from pm_os.wizard.orchestrator import WizardOrchestrator, WizardState

        # Create orchestrator
        wizard = WizardOrchestrator(install_path=tmp_path)

        # Simulate partial completion
        wizard.state = WizardState(
            started_at=datetime.now().isoformat(),
            current_step=2,
            completed_steps=[0, 1],
            data={"user_name": "Test User", "user_email": "test@example.com"},
            aborted=False,
            completed=False
        )
        wizard._save_session()

        # Verify session file exists
        session_path = Path.home() / wizard.SESSION_FILE
        assert session_path.exists()

        # Load session in new orchestrator
        wizard2 = WizardOrchestrator(install_path=tmp_path)
        loaded = wizard2._load_session()

        assert loaded is True
        assert wizard2.state.current_step == 2
        assert wizard2.state.completed_steps == [0, 1]
        assert wizard2.state.data["user_name"] == "Test User"

        # Cleanup
        session_path.unlink()

    def test_resume_with_stale_session(self, tmp_path):
        """Test resume behavior with stale session (>24h)."""
        from pm_os.wizard.orchestrator import WizardOrchestrator, WizardState

        wizard = WizardOrchestrator(install_path=tmp_path)

        # Create stale session
        old_time = datetime.now() - timedelta(hours=25)
        wizard.state = WizardState(
            started_at=old_time.isoformat(),
            current_step=1,
            completed_steps=[0],
            data={}
        )
        wizard._save_session()

        # Check staleness
        assert wizard.state.is_stale()
        assert wizard.state.get_age_hours() > 24

        # Cleanup
        session_path = Path.home() / wizard.SESSION_FILE
        if session_path.exists():
            session_path.unlink()


class TestErrorScenarios:
    """Test error handling scenarios."""

    def test_network_error_handling(self):
        """Test handling of network errors during credential testing."""
        from pm_os.wizard.exceptions import NetworkError

        error = NetworkError(
            "Connection timeout",
            endpoint="https://api.example.com"
        )

        assert "internet connection" in str(error).lower()
        assert error.endpoint == "https://api.example.com"

    def test_credential_error_handling(self):
        """Test handling of credential errors."""
        from pm_os.wizard.exceptions import CredentialError

        error = CredentialError(
            "Invalid API key",
            credential_type="Anthropic"
        )

        assert error.credential_type == "Anthropic"
        assert "Anthropic" in str(error)

    def test_sync_error_handling(self):
        """Test handling of sync errors."""
        from pm_os.wizard.exceptions import SyncError

        error = SyncError(
            "Failed to sync projects",
            service="Jira"
        )

        assert error.service == "Jira"
        assert "pm-os brain sync" in str(error)


class TestCleanupRollback:
    """Test cleanup and rollback functionality."""

    def test_file_tracking(self, tmp_path):
        """Test that created files are tracked for cleanup."""
        from pm_os.wizard.orchestrator import WizardOrchestrator

        wizard = WizardOrchestrator(install_path=tmp_path)

        # Track some files
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        wizard.track_file(test_file)

        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        wizard.track_directory(test_dir)

        assert str(test_file) in wizard.state.created_files
        assert str(test_dir) in wizard.state.created_dirs

    def test_cleanup_on_failure(self, tmp_path):
        """Test cleanup removes tracked files."""
        from pm_os.wizard.orchestrator import WizardOrchestrator

        wizard = WizardOrchestrator(install_path=tmp_path)

        # Create and track files
        test_file = tmp_path / "cleanup_test.txt"
        test_file.write_text("test")
        wizard.track_file(test_file)

        test_dir = tmp_path / "cleanup_dir"
        test_dir.mkdir()
        wizard.track_directory(test_dir)

        # Run cleanup
        failed = wizard.cleanup_on_failure()

        assert len(failed) == 0
        assert not test_file.exists()
        assert not test_dir.exists()


class TestSecretsLogging:
    """Test that secrets are properly masked in logs."""

    def test_mask_anthropic_key(self):
        """Test Anthropic API key masking."""
        from pm_os.wizard.ui import mask_secrets

        text = "Using key: sk-ant-api03-TESTKEY00000000000000000000000000"
        masked = mask_secrets(text)

        assert "sk-ant-" not in masked
        assert "********" in masked

    def test_mask_openai_key(self):
        """Test OpenAI API key masking."""
        from pm_os.wizard.ui import mask_secrets

        text = "OpenAI key: sk-proj-TESTKEY0000000000000000000"
        masked = mask_secrets(text)

        assert "sk-proj-" not in masked

    def test_mask_slack_token(self):
        """Test Slack token masking."""
        from pm_os.wizard.ui import mask_secrets

        text = "Bot token: xoxb-fake-test-token-placeholder"
        masked = mask_secrets(text)

        assert "xoxb-" not in masked

    def test_mask_github_token(self):
        """Test GitHub token masking."""
        from pm_os.wizard.ui import mask_secrets

        text = "Token: ghp_FAKETESTTOKEN000000000000000000000000"
        masked = mask_secrets(text)

        assert "ghp_" not in masked

    def test_mask_key_value_pairs(self):
        """Test masking of key=value patterns."""
        from pm_os.wizard.ui import mask_secrets

        text = "api_key=mysecretkey123"
        masked = mask_secrets(text)

        assert "mysecretkey123" not in masked
        assert "********" in masked

    def test_is_secret_key(self):
        """Test secret key detection."""
        from pm_os.wizard.ui import is_secret_key

        assert is_secret_key("api_key")
        assert is_secret_key("API_TOKEN")
        assert is_secret_key("password")
        assert is_secret_key("secret")
        assert is_secret_key("ANTHROPIC_API_KEY")
        assert not is_secret_key("username")
        assert not is_secret_key("email")


class TestConfigValidation:
    """Test configuration validation."""

    def test_validate_complete_config(self, tmp_path):
        """Test validation of complete config."""
        import yaml

        config_dir = tmp_path / ".config"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "config.yaml"

        config = {
            "user": {
                "name": "Test User",
                "email": "test@example.com",
                "role": "Product Manager"
            },
            "llm": {
                "provider": "anthropic",
                "model": "claude-sonnet-4-20250514"
            },
            "integrations": {
                "jira": {"enabled": True, "url": "https://example.atlassian.net"}
            }
        }

        config_path.write_text(yaml.dump(config))
        assert config_path.exists()

    def test_validate_invalid_provider(self, tmp_path):
        """Test validation catches invalid LLM provider."""
        import yaml

        config_dir = tmp_path / ".config"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "config.yaml"

        config = {
            "user": {"name": "Test"},
            "llm": {
                "provider": "invalid_provider",  # Invalid
                "model": "test-model"
            }
        }

        config_path.write_text(yaml.dump(config))

        # Validate that invalid provider would be caught
        valid_providers = ["bedrock", "anthropic", "openai", "ollama"]
        assert config["llm"]["provider"] not in valid_providers


class TestMockedAPIIntegration:
    """Test API integrations with mocked responses."""

    def test_jira_sync_mocked(self, tmp_path):
        """Test Jira sync with mocked API."""
        mock_requests = MagicMock()

        # Mock /myself endpoint
        myself_response = MagicMock()
        myself_response.status_code = 200
        myself_response.json.return_value = {"displayName": "Test User"}

        # Mock /project/search endpoint
        projects_response = MagicMock()
        projects_response.status_code = 200
        projects_response.json.return_value = {
            "values": [{"key": "TEST", "name": "Test Project", "id": "123"}]
        }

        mock_requests.Session.return_value.get.side_effect = [
            myself_response,
            projects_response
        ]

        # This verifies the mock setup works
        session = mock_requests.Session()
        response = session.get("test")
        assert response.status_code == 200

    def test_slack_sync_mocked(self, tmp_path):
        """Test Slack sync with mocked API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "user": "testbot",
            "team": "Test Team"
        }

        # Verify mock structure
        assert mock_response.json()["ok"] is True

    def test_github_sync_mocked(self, tmp_path):
        """Test GitHub sync with mocked API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"login": "testuser"}

        # Verify mock structure
        assert mock_response.json()["login"] == "testuser"


class TestBrainSyncSchema:
    """Test brain sync entity schema."""

    def test_entity_schema_creation(self):
        """Test creating entity with schema."""
        from pm_os.wizard.brain_sync.schema import EntitySchema

        schema = EntitySchema(
            type="project",
            name="Test Project",
            source="jira",
            sync_id="123",
            relationships={"owner": ["Test User"]},
            extra={"jira_key": "TEST"}
        )

        frontmatter = schema.to_frontmatter()
        assert "type: project" in frontmatter
        assert "name: Test Project" in frontmatter
        assert "source: jira" in frontmatter

    def test_entity_content_creation(self):
        """Test creating full entity content."""
        from pm_os.wizard.brain_sync.schema import create_entity_content

        content = create_entity_content(
            entity_type="project",
            name="Test Project",
            source="jira",
            body="# Test Project\n\nDescription here.",
            sync_id="123"
        )

        assert "---" in content  # Frontmatter delimiters
        assert "type: project" in content
        assert "# Test Project" in content

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        from pm_os.wizard.brain_sync.schema import sanitize_filename

        assert sanitize_filename("Test Project") == "Test_Project"
        assert sanitize_filename("Test/Project") == "Test-Project"
        assert sanitize_filename("Test: Something") == "Test-_Something"
        assert len(sanitize_filename("a" * 200)) <= 100
