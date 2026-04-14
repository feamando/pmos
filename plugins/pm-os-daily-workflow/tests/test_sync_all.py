"""Tests for sync_all.py — integration orchestrator."""

from unittest.mock import MagicMock, patch

import pytest


class TestIntegrationRegistry:
    """Validate the INTEGRATION_REGISTRY structure."""

    def test_registry_has_expected_keys(self):
        from integrations.sync_all import INTEGRATION_REGISTRY

        expected = {"jira", "github", "confluence", "statsig", "squad_sprint", "master_sheet", "tech_context"}
        assert set(INTEGRATION_REGISTRY.keys()) == expected

    def test_each_entry_has_required_fields(self):
        from integrations.sync_all import INTEGRATION_REGISTRY

        for name, reg in INTEGRATION_REGISTRY.items():
            assert "module" in reg, f"{name} missing module"
            assert "display_name" in reg, f"{name} missing display_name"
            assert "config_key" in reg, f"{name} missing config_key"
            assert "service" in reg, f"{name} missing service"
            assert "description" in reg, f"{name} missing description"

    def test_no_hardcoded_credentials(self):
        from integrations.sync_all import INTEGRATION_REGISTRY

        # None of the registry entries should contain tokens or URLs
        for name, reg in INTEGRATION_REGISTRY.items():
            for v in reg.values():
                if isinstance(v, str):
                    assert "http" not in v.lower(), f"{name} has URL in registry"
                    assert "token" not in v.lower() or v == "token", f"{name} has token ref"


class TestIsIntegrationEnabled:
    """Test config-driven enable/disable."""

    def test_jira_enabled(self, mock_config):
        from integrations.sync_all import _is_integration_enabled

        assert _is_integration_enabled("jira") is True

    def test_unknown_integration_disabled(self, mock_config):
        from integrations.sync_all import _is_integration_enabled

        assert _is_integration_enabled("nonexistent") is False

    def test_disabled_when_no_config(self):
        from integrations.sync_all import _is_integration_enabled

        with patch("integrations.sync_all.get_config", None):
            assert _is_integration_enabled("jira") is False


class TestRunAll:
    """Test the run_all orchestrator."""

    def test_returns_summary_structure(self, mock_config):
        from integrations.sync_all import run_all

        with patch("integrations.sync_all._has_service_auth", return_value=True), \
             patch("integrations.sync_all._run_integration", return_value={"status": "success"}):
            result = run_all()

        assert "summary" in result
        assert "results" in result
        assert "skipped" in result
        assert "timestamp" in result
        assert "total_elapsed_seconds" in result

    def test_only_filter(self, mock_config):
        from integrations.sync_all import run_all

        with patch("integrations.sync_all._has_service_auth", return_value=True), \
             patch("integrations.sync_all._run_integration", return_value={"status": "success"}):
            result = run_all(only=["jira"])

        # Only jira should be in results (if enabled)
        assert "jira" in result["results"]
        assert "github" not in result["results"]

    def test_exclude_filter(self, mock_config):
        from integrations.sync_all import run_all

        with patch("integrations.sync_all._has_service_auth", return_value=True), \
             patch("integrations.sync_all._run_integration", return_value={"status": "success"}):
            result = run_all(exclude=["jira"])

        assert "jira" not in result["results"]
        assert "jira" in result["skipped"]

    def test_skips_no_auth(self, mock_config):
        from integrations.sync_all import run_all

        with patch("integrations.sync_all._has_service_auth", return_value=False):
            result = run_all()

        # All should be skipped due to no auth
        assert result["summary"]["ran"] == 0


class TestListIntegrations:
    """Test list_integrations output."""

    def test_returns_all_integrations(self, mock_config):
        from integrations.sync_all import list_integrations, INTEGRATION_REGISTRY

        with patch("integrations.sync_all._has_service_auth", return_value=True):
            items = list_integrations()

        assert len(items) == len(INTEGRATION_REGISTRY)
        for name, info in items.items():
            assert "display_name" in info
            assert "enabled" in info
            assert "auth_available" in info
            assert "ready" in info
