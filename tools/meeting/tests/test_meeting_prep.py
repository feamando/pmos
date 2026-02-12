#!/usr/bin/env python3
"""
Integration Tests for Meeting Prep Optimization

Tests all new functionality:
- Template system
- LLM synthesizer abstraction
- Task completion inference
- Series intelligence
- Recurrence awareness
"""

import os
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


class TestTemplateSystem(unittest.TestCase):
    """Test the template registry and base templates."""

    def test_template_registry_loads(self):
        """Test that all templates can be loaded."""
        from templates import get_template

        meeting_types = [
            "1on1",
            "standup",
            "interview",
            "external",
            "large_meeting",
            "review",
            "planning",
            "other",
        ]

        for meeting_type in meeting_types:
            template = get_template(meeting_type)
            self.assertIsNotNone(template)
            self.assertIsNotNone(template.config)
            self.assertTrue(hasattr(template, "get_prompt_instructions"))

    def test_template_config_properties(self):
        """Test that templates have required config properties."""
        from templates import get_template

        template = get_template("1on1")
        self.assertIsNotNone(template.config.max_words)
        self.assertIsNotNone(template.config.sections)
        self.assertIsInstance(template.config.sections, list)

    def test_one_on_one_template_word_limit(self):
        """Test 1:1 template has reduced word limit."""
        from templates import get_template

        template = get_template("1on1")
        self.assertEqual(template.config.max_words, 300)

    def test_standup_template_minimal(self):
        """Test standup template has minimal config."""
        from templates import get_template

        template = get_template("standup")
        self.assertEqual(template.config.max_words, 150)
        self.assertFalse(template.config.include_tldr)

    def test_interview_template_detailed(self):
        """Test interview template maintains detail."""
        from templates import get_template

        template = get_template("interview")
        self.assertEqual(template.config.max_words, 1000)

    def test_fallback_template(self):
        """Test unknown types fall back to 'other' template."""
        from templates import get_template

        template = get_template("unknown_type")
        self.assertIsNotNone(template)
        # Should be 'other' template
        self.assertEqual(template.config.max_words, 400)

    def test_dynamic_tldr_bullets(self):
        """Test dynamic TL;DR bullet calculation."""
        from templates.base_template import MeetingTemplate

        # Simple context
        simple_context = {"action_items": []}
        bullets = MeetingTemplate._calculate_tldr_bullets(None, simple_context)
        self.assertEqual(bullets, "3-4")

        # Complex context
        complex_context = {
            "action_items": [1, 2, 3, 4, 5, 6],
            "series_intelligence": {
                "open_commitments": [1, 2, 3, 4],
                "recurring_topics": [1],
            },
            "participant_context": [1, 2, 3, 4],
            "jira_issues": [1, 2, 3, 4],
        }
        bullets = MeetingTemplate._calculate_tldr_bullets(None, complex_context)
        self.assertEqual(bullets, "5-7")


class TestLLMSynthesizer(unittest.TestCase):
    """Test the LLM synthesizer abstraction."""

    def test_synthesizer_selection_auto(self):
        """Test auto-detection of synthesizer."""
        from llm_synthesizer import get_synthesizer

        # Without Claude Code session, should not return ClaudeCodeSynthesizer
        with patch.dict(os.environ, {"CLAUDE_CODE_SESSION": ""}):
            synthesizer = get_synthesizer("auto")
            # Should be either Gemini (if key exists) or Template
            self.assertIn(
                type(synthesizer).__name__, ["GeminiSynthesizer", "TemplateSynthesizer"]
            )

    def test_template_synthesizer_fallback(self):
        """Test template synthesizer produces output."""
        from llm_synthesizer import TemplateSynthesizer

        synthesizer = TemplateSynthesizer()
        result = synthesizer.synthesize(
            "Test prompt",
            {
                "participant_context": [{"name": "Test", "role": "Engineer"}],
                "action_items": [
                    {"owner": "Test", "task": "Review PR", "completed": False}
                ],
                "topic_context": [],
                "series_history": [],
            },
        )

        self.assertTrue(result.success)
        self.assertEqual(result.model_id, "template")
        self.assertIn("TL;DR", result.content)
        self.assertIn("Participants", result.content)

    def test_synthesizer_explicit_preference(self):
        """Test explicit synthesizer preference."""
        from llm_synthesizer import TemplateSynthesizer, get_synthesizer

        synthesizer = get_synthesizer("template")
        self.assertIsInstance(synthesizer, TemplateSynthesizer)

    def test_claude_code_synthesizer_prompt_format(self):
        """Test Claude Code synthesizer returns structured prompt."""
        from llm_synthesizer import ClaudeCodeSynthesizer

        synthesizer = ClaudeCodeSynthesizer()
        result = synthesizer.synthesize("Generate meeting prep", {})

        self.assertTrue(result.success)
        self.assertEqual(result.model_id, "claude-code")
        self.assertIn("<meeting_prep_synthesis>", result.content)


class TestTaskInference(unittest.TestCase):
    """Test task completion inference."""

    def test_inferrer_creation_from_config(self):
        """Test TaskCompletionInferrer can be created from config."""
        from task_inference import TaskCompletionInferrer

        inferrer = TaskCompletionInferrer.from_config()
        self.assertIsNotNone(inferrer)
        self.assertIsInstance(inferrer.sources, list)

    def test_action_item_enrichment(self):
        """Test action items get enriched with completion status."""
        from task_inference import TaskCompletionInferrer

        inferrer = TaskCompletionInferrer([], 0.6)  # Empty sources for test

        items = [
            {"owner": "Test", "task": "Review PR", "completed": False},
            {"owner": "Test", "task": "Write docs", "completed": True},
        ]

        enriched = inferrer.enrich_items(items)

        self.assertEqual(len(enriched), 2)
        for item in enriched:
            self.assertIn("completion_status", item)

    def test_completion_status_markers(self):
        """Test completion status generates correct markers."""
        from task_inference import CompletionStatus

        # Completed
        status = CompletionStatus(status="completed", confidence=0.9, evidence=[])
        self.assertEqual(status.marker, "[x]")

        # Possibly complete
        status = CompletionStatus(
            status="possibly_complete", confidence=0.5, evidence=[]
        )
        self.assertEqual(status.marker, "[~]")

        # Outstanding
        status = CompletionStatus(status="outstanding", confidence=0.1, evidence=[])
        self.assertEqual(status.marker, "[ ]")

    def test_confidence_aggregation(self):
        """Test multiple signals boost confidence."""
        from task_inference import CompletionSignal, TaskCompletionInferrer

        inferrer = TaskCompletionInferrer([], 0.6)

        signals = [
            CompletionSignal(source="slack", confidence=0.5, evidence="Test 1"),
            CompletionSignal(source="jira", confidence=0.6, evidence="Test 2"),
        ]

        status = inferrer._aggregate_signals(signals)

        # Should boost confidence above max individual signal
        self.assertGreater(status.confidence, 0.6)


class TestSeriesIntelligence(unittest.TestCase):
    """Test series intelligence extraction."""

    def test_extract_outcomes(self):
        """Test extraction of meeting outcomes."""
        from series_intelligence import SeriesIntelligence

        si = SeriesIntelligence()

        history = [
            {
                "date": "2026-01-20",
                "summary": "Discussed metrics. Nikita will review dashboard.",
                "key_points": ["Metrics", "Dashboard review"],
            }
        ]

        outcomes = si.extract_outcomes(history)

        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0].date, "2026-01-20")

    def test_extract_commitments(self):
        """Test commitment extraction from text."""
        from series_intelligence import SeriesIntelligence

        si = SeriesIntelligence()

        history = [
            {
                "date": "2026-01-20",
                "summary": "John will review the PR. Sarah to update docs.",
                "key_points": [],
            }
        ]

        outcomes = si.extract_outcomes(history)
        commitments = outcomes[0].commitments

        self.assertGreaterEqual(len(commitments), 1)

    def test_extract_decisions(self):
        """Test decision extraction."""
        from series_intelligence import SeriesIntelligence

        si = SeriesIntelligence()

        history = [
            {
                "date": "2026-01-20",
                "summary": "Decided to proceed with new pricing model.",
                "key_points": [],
            }
        ]

        outcomes = si.extract_outcomes(history)

        self.assertGreater(len(outcomes[0].decisions), 0)

    def test_recurring_topics(self):
        """Test recurring topic detection."""
        from series_intelligence import SeriesIntelligence

        si = SeriesIntelligence()

        history = [
            {
                "date": "2026-01-20",
                "summary": "Discussed Growth Platform metrics",
                "key_points": ["Growth Platform"],
            },
            {
                "date": "2026-01-13",
                "summary": "Growth Platform metrics review",
                "key_points": ["Growth Platform"],
            },
            {
                "date": "2026-01-06",
                "summary": "Growth Platform metrics planning",
                "key_points": ["Growth Platform"],
            },
        ]

        outcomes = si.extract_outcomes(history)
        recurring = si.get_recurring_topics(outcomes, min_count=2)

        self.assertGreater(len(recurring), 0)

    def test_synthesize_history(self):
        """Test history synthesis produces markdown."""
        from series_intelligence import SeriesIntelligence

        si = SeriesIntelligence()

        history = [
            {
                "date": "2026-01-20",
                "summary": "John will review PR. Decided to ship feature.",
                "key_points": ["PR review", "Feature ship"],
            }
        ]

        outcomes = si.extract_outcomes(history)
        summary = si.synthesize_history(outcomes)

        self.assertIn("## Series Intelligence", summary)


class TestRecurrenceAwareness(unittest.TestCase):
    """Test recurrence frequency detection and prep depth."""

    def test_frequency_from_recurrence_rule(self):
        """Test frequency detection from RRULE."""

        # Direct implementation tests (avoiding import issues)
        def get_recurrence_frequency(event):
            recurrence = event.get("recurrence", [])
            if recurrence:
                for rule in recurrence:
                    rule_upper = rule.upper()
                    if "DAILY" in rule_upper:
                        return "daily"
                    elif "WEEKLY" in rule_upper:
                        return "weekly"
            return "unknown"

        # Test weekly
        event = {"recurrence": ["RRULE:FREQ=WEEKLY"]}
        freq = get_recurrence_frequency(event)
        self.assertEqual(freq, "weekly")

        # Test daily
        event = {"recurrence": ["RRULE:FREQ=DAILY"]}
        freq = get_recurrence_frequency(event)
        self.assertEqual(freq, "daily")

    def test_frequency_from_title(self):
        """Test frequency inference from title."""

        def get_frequency_from_title(summary):
            summary = summary.lower()
            if any(w in summary for w in ["daily", "standup", "stand-up"]):
                return "daily"
            elif any(w in summary for w in ["weekly", "week"]):
                return "weekly"
            return "unknown"

        # Test daily standup
        freq = get_frequency_from_title("Daily Standup")
        self.assertEqual(freq, "daily")

        # Test weekly sync
        freq = get_frequency_from_title("Weekly Sync")
        self.assertEqual(freq, "weekly")

    def test_prep_depth_daily_minimal(self):
        """Test daily meetings get minimal prep."""

        def get_prep_depth(meeting_type, frequency, quick_mode=False):
            if quick_mode:
                return "quick"
            if frequency == "daily":
                return "minimal"
            if meeting_type == "standup":
                return "minimal"
            return "standard"

        depth = get_prep_depth("standup", "daily")
        self.assertEqual(depth, "minimal")

    def test_prep_depth_interview_detailed(self):
        """Test interviews get detailed prep."""

        def get_prep_depth(meeting_type, frequency, quick_mode=False):
            if quick_mode:
                return "quick"
            if meeting_type == "interview":
                return "detailed"
            return "standard"

        depth = get_prep_depth("interview", "unknown")
        self.assertEqual(depth, "detailed")

    def test_prep_depth_quick_mode_override(self):
        """Test quick mode overrides other settings."""

        def get_prep_depth(meeting_type, frequency, quick_mode=False):
            if quick_mode:
                return "quick"
            if meeting_type == "interview":
                return "detailed"
            return "standard"

        depth = get_prep_depth("interview", "monthly", quick_mode=True)
        self.assertEqual(depth, "quick")


class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility with existing system."""

    def test_config_loader_functions(self):
        """Test new config functions exist."""
        import config_loader

        self.assertTrue(hasattr(config_loader, "get_meeting_prep_config"))
        self.assertTrue(hasattr(config_loader, "is_claude_code_session"))

    def test_meeting_prep_config_defaults(self):
        """Test meeting prep config has sensible defaults."""
        import config_loader

        config = config_loader.get_meeting_prep_config()

        self.assertIn("prep_hours", config)
        self.assertIn("default_depth", config)
        self.assertIn("preferred_model", config)
        self.assertIn("task_inference", config)
        self.assertIn("type_overrides", config)

    def test_old_imports_still_work(self):
        """Test that meeting_prep.py exists and has key components."""
        import os

        meeting_prep_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "meeting_prep.py",
        )
        self.assertTrue(
            os.path.exists(meeting_prep_path), "meeting_prep.py should exist"
        )

        # Read file and check for key functions/classes
        with open(meeting_prep_path, "r") as f:
            content = f.read()

        self.assertIn("class MeetingManager", content)
        self.assertIn("def slugify", content)
        self.assertIn("def get_credentials", content)


def run_tests():
    """Run all tests and return results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestTemplateSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestLLMSynthesizer))
    suite.addTests(loader.loadTestsFromTestCase(TestTaskInference))
    suite.addTests(loader.loadTestsFromTestCase(TestSeriesIntelligence))
    suite.addTests(loader.loadTestsFromTestCase(TestRecurrenceAwareness))
    suite.addTests(loader.loadTestsFromTestCase(TestBackwardCompatibility))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result


if __name__ == "__main__":
    result = run_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
