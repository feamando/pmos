"""
Tests for pm_os.google_auth module.

Tests the bundled Google OAuth credential detection, credential copying,
scope definitions, and OAuth flow helpers.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pm_os.google_auth import (
    GOOGLE_SCOPES,
    copy_credentials_to_secrets,
    get_bundled_client_secret_path,
    has_bundled_credentials,
)


class TestGoogleScopes:
    """Tests for GOOGLE_SCOPES constant."""

    def test_has_six_scopes(self):
        assert len(GOOGLE_SCOPES) == 6

    def test_required_scopes_present(self):
        scope_suffixes = [s.split("/")[-1] for s in GOOGLE_SCOPES]
        assert "drive.readonly" in scope_suffixes
        assert "drive.metadata.readonly" in scope_suffixes
        assert "drive.file" in scope_suffixes
        assert "gmail.readonly" in scope_suffixes
        assert "calendar.events" in scope_suffixes
        assert "calendar.readonly" in scope_suffixes

    def test_all_scopes_are_googleapis(self):
        for scope in GOOGLE_SCOPES:
            assert scope.startswith("https://www.googleapis.com/auth/")


class TestBundledCredentials:
    """Tests for bundled credential detection."""

    def test_has_bundled_credentials_returns_bool(self):
        result = has_bundled_credentials()
        assert isinstance(result, bool)

    def test_get_bundled_path_returns_path_or_none(self):
        result = get_bundled_client_secret_path()
        assert result is None or isinstance(result, Path)

    def test_bundled_path_points_to_data_dir(self):
        path = get_bundled_client_secret_path()
        if path is not None:
            assert "data" in path.parts
            assert path.name == "google_client_secret.json"

    def test_bundled_file_is_valid_json(self):
        path = get_bundled_client_secret_path()
        if path is not None:
            data = json.loads(path.read_text())
            assert "installed" in data or "web" in data

    def test_bundled_has_client_id(self):
        path = get_bundled_client_secret_path()
        if path is not None:
            data = json.loads(path.read_text())
            app_type = "installed" if "installed" in data else "web"
            assert "client_id" in data[app_type]


class TestCopyCredentials:
    """Tests for copy_credentials_to_secrets."""

    def test_copy_creates_directory(self):
        if not has_bundled_credentials():
            pytest.skip("No bundled credentials available")
        with tempfile.TemporaryDirectory() as tmpdir:
            secrets_dir = Path(tmpdir) / "nested" / ".secrets"
            dest = copy_credentials_to_secrets(secrets_dir)
            assert secrets_dir.exists()
            assert dest.exists()
            assert dest.name == "credentials.json"

    def test_copy_produces_valid_json(self):
        if not has_bundled_credentials():
            pytest.skip("No bundled credentials available")
        with tempfile.TemporaryDirectory() as tmpdir:
            secrets_dir = Path(tmpdir) / ".secrets"
            dest = copy_credentials_to_secrets(secrets_dir)
            data = json.loads(dest.read_text())
            assert "installed" in data or "web" in data

    def test_copy_raises_when_no_bundled(self):
        with patch("pm_os.google_auth.get_bundled_client_secret_path", return_value=None):
            with pytest.raises(FileNotFoundError):
                copy_credentials_to_secrets(Path("/tmp/nonexistent"))

    def test_copy_is_idempotent(self):
        if not has_bundled_credentials():
            pytest.skip("No bundled credentials available")
        with tempfile.TemporaryDirectory() as tmpdir:
            secrets_dir = Path(tmpdir) / ".secrets"
            dest1 = copy_credentials_to_secrets(secrets_dir)
            content1 = dest1.read_text()
            dest2 = copy_credentials_to_secrets(secrets_dir)
            content2 = dest2.read_text()
            assert content1 == content2


class TestRunOAuthFlow:
    """Tests for run_oauth_flow (mocked — no browser)."""

    def test_calls_installed_app_flow(self):
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "test"}'

        mock_flow_instance = MagicMock()
        mock_flow_instance.run_local_server.return_value = mock_creds

        with tempfile.TemporaryDirectory() as tmpdir:
            creds_path = Path(tmpdir) / "credentials.json"
            creds_path.write_text('{"installed": {}}')
            token_path = Path(tmpdir) / "token.json"

            with patch("google_auth_oauthlib.flow.InstalledAppFlow") as MockFlow:
                MockFlow.from_client_secrets_file.return_value = mock_flow_instance

                from pm_os.google_auth import run_oauth_flow
                result = run_oauth_flow(creds_path, token_path)

                MockFlow.from_client_secrets_file.assert_called_once_with(
                    str(creds_path), GOOGLE_SCOPES
                )
                mock_flow_instance.run_local_server.assert_called_once_with(port=0)
                assert token_path.exists()
                assert result == mock_creds

    def test_saves_token_to_disk(self):
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"access_token": "abc123"}'

        mock_flow_instance = MagicMock()
        mock_flow_instance.run_local_server.return_value = mock_creds

        with tempfile.TemporaryDirectory() as tmpdir:
            creds_path = Path(tmpdir) / "credentials.json"
            creds_path.write_text('{"installed": {}}')
            token_path = Path(tmpdir) / "nested" / "token.json"

            with patch("google_auth_oauthlib.flow.InstalledAppFlow") as MockFlow:
                MockFlow.from_client_secrets_file.return_value = mock_flow_instance

                from pm_os.google_auth import run_oauth_flow
                run_oauth_flow(creds_path, token_path)

                assert token_path.exists()
                saved = json.loads(token_path.read_text())
                assert saved["access_token"] == "abc123"


class TestLoadOrRefreshCredentials:
    """Tests for load_or_refresh_credentials (mocked)."""

    def test_raises_if_no_token(self):
        from pm_os.google_auth import load_or_refresh_credentials
        with pytest.raises(FileNotFoundError):
            load_or_refresh_credentials(
                Path("/nonexistent/creds.json"),
                Path("/nonexistent/token.json"),
            )

    def test_loads_valid_token(self):
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds.valid = True

        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = Path(tmpdir) / "token.json"
            token_path.write_text('{"token": "test"}')

            with patch("google.oauth2.credentials.Credentials") as MockCreds:
                MockCreds.from_authorized_user_file.return_value = mock_creds

                from pm_os.google_auth import load_or_refresh_credentials
                result = load_or_refresh_credentials(
                    Path("/dummy/creds.json"), token_path
                )
                assert result == mock_creds


class TestGoogleSyncerScopes:
    """Verify GoogleSyncer uses GOOGLE_SCOPES from google_auth."""

    def test_syncer_uses_google_auth_scopes(self):
        import inspect
        from pm_os.wizard.brain_sync.google_sync import GoogleSyncer
        src = inspect.getsource(GoogleSyncer._get_credentials)
        assert "from pm_os.google_auth import GOOGLE_SCOPES" in src
        assert "SCOPES = [" not in src  # Old 2-scope literal removed


class TestIntegrationsWizardStep:
    """Verify configure_google dispatches correctly."""

    def test_bundled_detection_in_configure_google(self):
        import inspect
        from pm_os.wizard.steps.integrations import configure_google
        src = inspect.getsource(configure_google)
        assert "has_bundled_credentials" in src
        assert "_configure_google_bundled" in src
        assert "_configure_google_manual" in src

    def test_bundled_path_already_authenticated(self):
        from pm_os.wizard.steps.integrations import _configure_google_bundled

        wizard = MagicMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            secrets_dir = Path(tmpdir) / ".secrets"
            secrets_dir.mkdir()
            creds_path = secrets_dir / "credentials.json"
            token_path = secrets_dir / "token.json"
            token_path.write_text('{"token": "existing"}')

            result = _configure_google_bundled(wizard, secrets_dir, creds_path, token_path)
            assert result is True
            wizard.update_data.assert_called_once()

    def test_manual_path_skip(self):
        from pm_os.wizard.steps.integrations import _configure_google_manual

        wizard = MagicMock()
        wizard.ui.prompt_text.return_value = ""
        result = _configure_google_manual(wizard, Path("/tmp/creds.json"))
        assert result is False


class TestEnvAndConfig:
    """Verify .env and config.yaml include Google paths."""

    def test_env_includes_token_path(self):
        from pm_os.wizard.steps.directories import generate_env_file

        wizard = MagicMock()
        wizard.get_data.side_effect = lambda k, d="": {
            "google_credentials_path": "/t/c.json",
            "google_token_path": "/t/t.json",
        }.get(k, d)

        env = generate_env_file(wizard, Path("/t"))
        assert "GOOGLE_CREDENTIALS_PATH" in env
        assert "GOOGLE_TOKEN_PATH" in env

    def test_config_google_enabled_when_authenticated(self):
        import yaml
        from pm_os.wizard.steps.directories import generate_config_yaml

        wizard = MagicMock()
        wizard.get_data.side_effect = lambda k, d="": {
            "google_authenticated": True,
        }.get(k, d)

        cfg = yaml.safe_load(generate_config_yaml(wizard))
        assert cfg["integrations"]["google"]["enabled"] is True

    def test_config_google_disabled_without_auth(self):
        import yaml
        from pm_os.wizard.steps.directories import generate_config_yaml

        wizard = MagicMock()
        wizard.get_data.side_effect = lambda k, d="": "".get(k, d) if False else d

        cfg = yaml.safe_load(generate_config_yaml(wizard))
        assert cfg["integrations"]["google"]["enabled"] is False
