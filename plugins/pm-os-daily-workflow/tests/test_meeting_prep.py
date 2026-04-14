"""Tests for meeting_prep.py and supporting modules."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestMeetingPrepImports:
    """Validate meeting_prep loads with fallback imports."""

    def test_module_loads(self):
        import meeting.meeting_prep as mp

        assert hasattr(mp, "get_config") or mp.get_config is None

    def test_check_plugin_fallback(self):
        """check_plugin should be callable even if plugin_deps not installed."""
        import meeting.meeting_prep as mp

        result = mp.check_plugin("pm-os-brain")
        assert isinstance(result, bool)


class TestLlmSynthesizer:
    """Test LLM synthesizer factory and template fallback."""

    def test_module_loads(self):
        from meeting.llm_synthesizer import get_synthesizer, TemplateSynthesizer

        assert get_synthesizer is not None

    def test_template_synthesizer_works(self):
        from meeting.llm_synthesizer import TemplateSynthesizer, SynthesisResult

        ts = TemplateSynthesizer()
        result = ts.synthesize(
            prompt="Prepare meeting",
            context={
                "participant_context": [{"name": "Alice", "role": "PM"}],
                "action_items": [],
                "topic_context": [],
                "past_notes": "",
                "series_history": [],
            },
        )
        assert isinstance(result, SynthesisResult)
        assert result.success is True
        assert result.model_id == "template"
        assert "Alice" in result.content

    def test_factory_fallback_to_template(self, mock_config):
        from meeting.llm_synthesizer import get_synthesizer, TemplateSynthesizer

        with patch.dict("os.environ", {}, clear=False):
            synth = get_synthesizer(preferred="template", config=mock_config)
        assert isinstance(synth, TemplateSynthesizer)


class TestParticipantContext:
    """Test participant context resolution."""

    def test_resolver_init(self, mock_config, mock_paths):
        from meeting.participant_context import ParticipantContextResolver

        resolver = ParticipantContextResolver(
            config=mock_config, paths=mock_paths, brain_available=False,
        )
        assert resolver is not None

    def test_internal_domain_detection(self, mock_config, mock_paths):
        from meeting.participant_context import ParticipantContextResolver

        resolver = ParticipantContextResolver(
            config=mock_config, paths=mock_paths, brain_available=False,
        )
        assert resolver.is_internal("alice@testcorp.com") is True
        assert resolver.is_internal("bob@testcorp.de") is True
        assert resolver.is_internal("ext@gmail.com") is False
        assert resolver.is_internal("") is False

    def test_internal_domains_from_config(self, mock_config, mock_paths):
        from meeting.participant_context import ParticipantContextResolver

        resolver = ParticipantContextResolver(
            config=mock_config, paths=mock_paths, brain_available=False,
        )
        assert "testcorp.com" in resolver.internal_domains
        assert "testcorp.de" in resolver.internal_domains


class TestAgendaGenerator:
    """Test agenda generation."""

    def test_module_loads(self):
        from meeting.agenda_generator import AgendaGenerator

        assert AgendaGenerator is not None


class TestSeriesIntelligence:
    """Test series history analysis."""

    def test_extract_outcomes_empty(self):
        from meeting.series_intelligence import SeriesIntelligence

        si = SeriesIntelligence()
        outcomes = si.extract_outcomes([])
        assert outcomes == []

    def test_extract_outcomes_basic(self):
        from meeting.series_intelligence import SeriesIntelligence

        si = SeriesIntelligence()
        history = [
            {
                "date": "2026-01-01",
                "summary": "Discussed roadmap. Decision: proceed with option A.",
                "key_points": ["Roadmap alignment"],
            }
        ]
        outcomes = si.extract_outcomes(history)
        assert len(outcomes) == 1
        assert outcomes[0].date == "2026-01-01"

    def test_get_open_commitments(self):
        from meeting.series_intelligence import SeriesIntelligence, Commitment

        si = SeriesIntelligence()
        # With no outcomes, should return empty
        assert si.get_open_commitments([]) == []


class TestTaskCompletionInferrer:
    """Test task inference."""

    def test_from_config(self, mock_config, mock_paths):
        from meeting.task_inference import TaskCompletionInferrer

        inferrer = TaskCompletionInferrer.from_config(
            config=mock_config, paths=mock_paths,
        )
        assert isinstance(inferrer, TaskCompletionInferrer)


class TestNoHardcodedValues:
    """Verify meeting module has no hardcoded personal values."""

    def test_no_hardcoded_emails(self):
        meeting_dir = Path(__file__).resolve().parent.parent / "tools" / "meeting"
        for py_file in meeting_dir.glob("*.py"):
            content = py_file.read_text()
            assert "@hellofresh.com" not in content, f"Hardcoded email in {py_file.name}"
            assert "@hellofresh.de" not in content, f"Hardcoded email in {py_file.name}"

    def test_no_hardcoded_names(self):
        meeting_dir = Path(__file__).resolve().parent.parent / "tools" / "meeting"
        forbidden = ["nikita", "gorshkov"]
        for py_file in meeting_dir.glob("*.py"):
            content = py_file.read_text().lower()
            for name in forbidden:
                assert name not in content, f"Hardcoded name '{name}' in {py_file.name}"
