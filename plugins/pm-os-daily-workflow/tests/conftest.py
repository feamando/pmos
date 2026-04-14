"""Shared test fixtures for pm-os-daily-workflow tests."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure plugin tools are importable
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TOOLS_ROOT = PLUGIN_ROOT / "tools"
BASE_PLUGIN = PLUGIN_ROOT.parent / "pm-os-base"

for p in [str(TOOLS_ROOT), str(BASE_PLUGIN / "tools" / "core"), str(BASE_PLUGIN / "tools")]:
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture
def mock_config():
    """Provide a mock config loader that returns sensible defaults."""
    config_data = {
        "user": {
            "name": "Test User",
            "email": "test@example.com",
            "role": "Product Manager",
            "company": "TestCorp",
            "timezone": "UTC",
        },
        "team": {
            "reports": [
                {"name": "Alice Johnson", "role": "PM"},
                {"name": "Bob Smith", "role": "PM"},
            ],
            "manager": {"name": "Carol Davis", "role": "VP"},
            "squads": [
                {"name": "Alpha Squad", "jira_prefix": "ALPHA"},
                {"name": "Beta Squad", "jira_prefix": "BETA"},
            ],
            "tribe": "Test Tribe",
        },
        "products": {
            "items": [
                {"id": "product-a", "name": "Product A", "jira_prefix": "PA"},
                {"id": "product-b", "name": "Product B", "jira_prefix": "PB"},
            ]
        },
        "integrations": {
            "jira": {"enabled": True, "url": "https://test.atlassian.net"},
            "slack": {
                "enabled": True,
                "channel": "test-channel",
                "team_domain": "testcorp",
                "bot_name": "test-bot",
                "channel_tiers": {
                    "tier1": ["channel-1", "channel-2"],
                    "tier2": ["channel-3"],
                },
            },
            "github": {
                "enabled": True,
                "repos": ["testcorp/web", "testcorp/api"],
                "default_repo": "testcorp/web",
            },
            "google": {"enabled": True},
            "figma": {"enabled": False},
            "statsig": {"enabled": True},
            "confluence": {"enabled": True},
        },
        "persona": {
            "style": "direct",
            "format": "bullets-over-prose",
        },
        "meeting_prep": {
            "internal_domains": ["testcorp.com", "testcorp.de"],
            "prep_hours": 12,
            "default_depth": "standard",
            "aws_region": "us-east-1",
            "bedrock_model": "test-model",
        },
        "context": {
            "search_terms": ["project-x", "initiative-y"],
            "noise_patterns": ["Internal Tracker", "Logistics Sheet"],
            "alert_keywords": ["critical", "blocker", "urgent", "p0"],
        },
        "brain": {
            "auto_create_entities": True,
        },
    }

    class MockConfig:
        def __init__(self):
            self.user_path = Path("/tmp/test-pm-os/user")

        def get(self, key, default=None):
            keys = key.split(".")
            value = config_data
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return value

        def require(self, key, prompt_message=None):
            val = self.get(key)
            if val is None:
                raise ValueError(f"Required config missing: {key}")
            return val

        def get_bool(self, key, default=False):
            val = self.get(key, default)
            return bool(val)

        def get_list(self, key, default=None):
            val = self.get(key, default)
            if val is None:
                return []
            return val if isinstance(val, list) else [val]

        def is_integration_enabled(self, integration):
            return self.get_bool(f"integrations.{integration}.enabled", False)

        def get_integration_config(self, integration):
            return self.get(f"integrations.{integration}", {}) or {}

        def get_secret(self, key):
            return os.getenv(key)

    mock = MockConfig()

    # Patch get_config in all modules that import it.
    # The tools use try/except fallback imports, so the actual function
    # ends up imported from config_loader (the base plugin core module).
    # We patch it everywhere it's used.
    patches = []

    # Patch the base module itself
    try:
        import config_loader
        p = patch.object(config_loader, "get_config", return_value=mock)
        patches.append(p)
    except ImportError:
        pass

    # Patch in each tool subpackage that has already imported get_config
    tool_modules = [
        "slack.slack_mention_classifier",
        "slack.slack_mention_handler",
        "slack.slack_mention_llm_processor",
        "slack.slack_extractor",
        "slack.slack_processor",
        "slack.slack_bulk_extractor",
        "slack.slack_context_poster",
        "slack.slack_mrkdwn_parser",
        "slack.slack_user_cache",
        "slack.slack_channel_sync",
        "daily_context.context_sources",
        "daily_context.daily_context_updater",
        "daily_context.context_synthesizer",
        "meeting.meeting_prep",
        "meeting.llm_synthesizer",
        "meeting.participant_context",
        "meeting.agenda_generator",
        "meeting.task_inference",
        "meeting.series_intelligence",
        "integrations.sync_all",
        "integrations.jira_sync",
        "integrations.github_sync",
        "integrations.confluence_sync",
        "integrations.statsig_sync",
        "integrations.squad_sprint_sync",
        "integrations.master_sheet_sync",
        "integrations.tech_context_sync",
    ]

    for mod_name in tool_modules:
        try:
            mod = __import__(mod_name, fromlist=["get_config"])
            if hasattr(mod, "get_config"):
                p = patch.object(mod, "get_config", return_value=mock)
                patches.append(p)
        except (ImportError, Exception):
            pass

    for p in patches:
        p.start()

    yield mock

    for p in patches:
        p.stop()


@pytest.fixture
def mock_paths(tmp_path):
    """Provide mock path resolver with temp directories."""
    user_dir = tmp_path / "user"
    common_dir = tmp_path / "common"
    brain_dir = user_dir / "brain"
    context_dir = user_dir / "personal" / "context"
    sessions_dir = user_dir / "sessions"

    for d in [user_dir, common_dir, brain_dir, context_dir, sessions_dir]:
        d.mkdir(parents=True, exist_ok=True)

    class MockPaths:
        root = tmp_path
        common = common_dir
        user = user_dir
        brain = brain_dir
        context = context_dir
        sessions = sessions_dir
        tools = common_dir / "tools"
        plugins = common_dir / "plugins"
        strategy = "test_fixture"

    mock = MockPaths()

    patches = []

    try:
        import path_resolver
        p = patch.object(path_resolver, "get_paths", return_value=mock)
        patches.append(p)
    except ImportError:
        pass

    for mod_name in [
        "meeting.meeting_prep",
        "meeting.series_intelligence",
        "meeting.task_inference",
        "slack.slack_processor",
        "slack.slack_mrkdwn_parser",
        "integrations.master_sheet_sync",
    ]:
        try:
            mod = __import__(mod_name, fromlist=["get_paths"])
            if hasattr(mod, "get_paths"):
                p = patch.object(mod, "get_paths", return_value=mock)
                patches.append(p)
        except (ImportError, Exception):
            pass

    for p in patches:
        p.start()

    yield mock

    for p in patches:
        p.stop()


@pytest.fixture
def mock_connector_bridge():
    """Mock connector bridge for auth checks."""
    try:
        from pm_os_base.tools.core.connector_bridge import ConnectorAuth
    except ImportError:
        from connector_bridge import ConnectorAuth

    def mock_get_auth(service):
        return ConnectorAuth(
            service=service,
            source="env",
            token="test-token-123",
        )

    patches = []

    try:
        import connector_bridge
        p = patch.object(connector_bridge, "get_auth", side_effect=mock_get_auth)
        patches.append(p)
    except ImportError:
        pass

    for p in patches:
        p.start()

    yield mock_get_auth

    for p in patches:
        p.stop()
