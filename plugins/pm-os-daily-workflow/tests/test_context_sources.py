"""Tests for context_sources.py — abstract base + concrete sources."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


class TestSmartTruncate:
    """Test the _smart_truncate helper."""

    def test_short_content_unchanged(self):
        from daily_context.context_sources import _smart_truncate

        text = "short text"
        assert _smart_truncate(text, 100) == text

    def test_long_content_truncated(self):
        from daily_context.context_sources import _smart_truncate

        text = "a" * 1000
        result = _smart_truncate(text, 100)
        assert len(result) < 1000
        assert "TRUNCATED" in result

    def test_truncate_keeps_start_and_end(self):
        from daily_context.context_sources import _smart_truncate

        text = "START" + "x" * 990 + "END!!"
        result = _smart_truncate(text, 200)
        assert result.startswith("START")
        assert result.endswith("END!!")

    def test_exact_limit_unchanged(self):
        from daily_context.context_sources import _smart_truncate

        text = "a" * 100
        assert _smart_truncate(text, 100) == text


class TestContextSourceABC:
    """Test the abstract base class contract."""

    def test_cannot_instantiate_abc(self):
        from daily_context.context_sources import ContextSource

        with pytest.raises(TypeError):
            ContextSource()

    def test_concrete_subclass_needs_fetch_and_format(self):
        from daily_context.context_sources import ContextSource

        class Incomplete(ContextSource):
            service_name = "test"
            display_name = "Test"

        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_subclass_works(self):
        from daily_context.context_sources import ContextSource

        class Complete(ContextSource):
            service_name = "test"
            display_name = "Test"

            def fetch(self, config, since, processed_files=None):
                return {"items": []}

            def format(self, data):
                return ""

        src = Complete()
        assert src.service_name == "test"
        result = src.fetch(None, datetime.now(timezone.utc))
        assert result == {"items": []}

    def test_is_available_checks_service(self):
        from daily_context.context_sources import ContextSource

        class TestSource(ContextSource):
            service_name = "test_svc"
            display_name = "Test"

            def fetch(self, config, since, processed_files=None):
                return {"items": []}

            def format(self, data):
                return ""

        src = TestSource()
        with patch(
            "daily_context.context_sources.is_service_available",
            return_value=True,
        ):
            assert src.is_available() is True


class TestGoogleDocsSource:
    """Test GoogleDocsContextSource config-driven behavior."""

    def test_skips_when_no_auth(self, mock_config):
        from daily_context.context_sources import GoogleDocsContextSource

        src = GoogleDocsContextSource()
        with patch.object(src, "_get_auth", return_value=MagicMock(source="none")):
            result = src.fetch(mock_config, datetime.now(timezone.utc))
        assert result["items"] == []

    def test_format_empty(self):
        from daily_context.context_sources import GoogleDocsContextSource

        src = GoogleDocsContextSource()
        assert src.format({"items": []}) == ""


class TestSlackContextSource:
    """Test SlackContextSource."""

    def test_skips_when_no_auth(self, mock_config):
        from daily_context.context_sources import SlackContextSource

        src = SlackContextSource()
        with patch.object(src, "_get_auth", return_value=MagicMock(source="none")):
            result = src.fetch(mock_config, datetime.now(timezone.utc))
        assert result["items"] == []


class TestJiraContextSource:
    """Test JiraContextSource."""

    def test_skips_when_no_auth(self, mock_config):
        from daily_context.context_sources import JiraContextSource

        src = JiraContextSource()
        with patch.object(src, "_get_auth", return_value=MagicMock(source="none")):
            result = src.fetch(mock_config, datetime.now(timezone.utc))
        assert result["items"] == []
