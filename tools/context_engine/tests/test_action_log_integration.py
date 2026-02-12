"""
Tests for Action Log Integration

Tests that engine state changes automatically update the Action Log
in the context file via the bidirectional sync integration.

Author: PM-OS Team
"""

import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestActionLogIntegration(unittest.TestCase):
    """Test that state changes automatically update the action log."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temp directory
        self.test_dir = Path(tempfile.mkdtemp())
        self.user_path = self.test_dir / "user"
        self.user_path.mkdir()

        # Create products directory structure
        self.products_path = (
            self.user_path / "products" / "growth-division" / "test-product"
        )
        self.products_path.mkdir(parents=True)

        # Create feature path
        self.feature_path = self.products_path / "tes-test-feature"
        self.feature_path.mkdir(parents=True)

        # Create context-docs folder
        (self.feature_path / "context-docs").mkdir(exist_ok=True)
        (self.feature_path / "business-case").mkdir(exist_ok=True)
        (self.feature_path / "engineering").mkdir(exist_ok=True)
        (self.feature_path / "engineering" / "adrs").mkdir(exist_ok=True)

        # Create feature state
        self.state_data = {
            "slug": "tes-test-feature",
            "title": "Test Feature",
            "product_id": "test-product",
            "organization": "growth-division",
            "context_file": "tes-test-feature-context.md",
            "brain_entity": "[[Entities/Test_Feature]]",
            "master_sheet_row": None,
            "created": datetime.now().isoformat(),
            "created_by": "test_user",
            "engine": {
                "current_phase": "initialization",
                "phase_history": [
                    {"phase": "initialization", "entered": datetime.now().isoformat()}
                ],
                "tracks": {
                    "context": {"status": "not_started"},
                    "design": {"status": "not_started"},
                    "business_case": {"status": "not_started"},
                    "engineering": {"status": "not_started"},
                },
            },
            "artifacts": {
                "jira_epic": None,
                "figma": None,
                "confluence_page": None,
                "wireframes_url": None,
            },
            "decisions": [],
            "aliases": {
                "primary_name": "Test Feature",
                "known_aliases": [],
                "auto_detected": False,
            },
        }

        state_file = self.feature_path / "feature-state.yaml"
        with open(state_file, "w") as f:
            yaml.dump(self.state_data, f)

        # Create context file with action log
        self.context_content = """# Test Feature Context

**Product:** TEST
**Status:** To Do
**Owner:** test_user
**Priority:** P2
**Deadline:** TBD
**Last Updated:** 2026-02-04

## Description
*Feature context created by Context Creation Engine*

## Stakeholders
- **test_user** (Owner)

## Action Log
| Date | Action | Status | Priority | Deadline |
|------|--------|--------|----------|----------|

## References
- *No links yet*

## Brain Entities
- [[Entities/Test_Feature]]

## Changelog
- **2026-02-04**: Context file created by Context Creation Engine
"""

        context_file = self.feature_path / "tes-test-feature-context.md"
        context_file.write_text(self.context_content)

        # Create mock config
        self.mock_config = MagicMock()
        self.mock_config.user_path = str(self.user_path)
        self.mock_config.raw_config = {
            "products": {
                "organization": {"id": "growth-division"},
                "items": [
                    {
                        "id": "test-product",
                        "name": "Test Product",
                        "organization": "growth-division",
                    }
                ],
            },
            "master_sheet": {"enabled": False},
        }

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("config_loader.get_config")
    @patch("config_loader.get_user_name")
    def test_phase_transition_logs_action(self, mock_get_user_name, mock_get_config):
        """Test that phase transitions add an action log entry."""
        mock_get_config.return_value = self.mock_config
        mock_get_user_name.return_value = "test_user"

        from context_engine.feature_engine import FeatureEngine
        from context_engine.feature_state import FeaturePhase

        engine = FeatureEngine(user_path=self.user_path)

        # Record a phase transition
        result = engine.record_phase_transition(
            slug="tes-test-feature",
            from_phase=FeaturePhase.INITIALIZATION,
            to_phase=FeaturePhase.SIGNAL_ANALYSIS,
            metadata={"test": "data"},
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["from_phase"], "initialization")
        self.assertEqual(result["to_phase"], "signal_analysis")

        # Verify action was logged to context file
        context_file = self.feature_path / "tes-test-feature-context.md"
        content = context_file.read_text()

        self.assertIn("Phase transition:", content)
        self.assertIn("initialization -> signal_analysis", content)

    @patch("config_loader.get_config")
    @patch("config_loader.get_user_name")
    def test_decision_logs_action(self, mock_get_user_name, mock_get_config):
        """Test that recording a decision adds an action log entry."""
        mock_get_config.return_value = self.mock_config
        mock_get_user_name.return_value = "test_user"

        from context_engine.feature_engine import FeatureEngine

        engine = FeatureEngine(user_path=self.user_path)

        # Record a decision
        result = engine.record_decision(
            slug="tes-test-feature",
            decision="Use approach A instead of B",
            rationale="Better performance",
            decided_by="test_user",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["decision"], "Use approach A instead of B")

        # Verify action was logged to context file
        context_file = self.feature_path / "tes-test-feature-context.md"
        content = context_file.read_text()

        self.assertIn("Decision:", content)
        self.assertIn("Use approach A instead of B", content)

    @patch("config_loader.get_config")
    @patch("config_loader.get_user_name")
    def test_track_status_update_logs_action(self, mock_get_user_name, mock_get_config):
        """Test that updating track status adds an action log entry."""
        mock_get_config.return_value = self.mock_config
        mock_get_user_name.return_value = "test_user"

        from context_engine.feature_engine import FeatureEngine
        from context_engine.feature_state import TrackStatus

        engine = FeatureEngine(user_path=self.user_path)

        # Update track status
        result = engine.update_track_status(
            slug="tes-test-feature",
            track_name="design",
            status=TrackStatus.IN_PROGRESS,
            current_step="wireframes",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["track_name"], "design")
        self.assertEqual(result["new_status"], "in_progress")

        # Verify action was logged to context file
        context_file = self.feature_path / "tes-test-feature-context.md"
        content = context_file.read_text()

        self.assertIn("Track 'design':", content)
        self.assertIn("not_started -> in_progress", content)

    @patch("config_loader.get_config")
    @patch("config_loader.get_user_name")
    def test_attach_artifact_logs_action(self, mock_get_user_name, mock_get_config):
        """Test that attaching an artifact adds an action log entry."""
        mock_get_config.return_value = self.mock_config
        mock_get_user_name.return_value = "test_user"

        from context_engine.feature_engine import FeatureEngine

        engine = FeatureEngine(user_path=self.user_path)

        # Attach an artifact
        result = engine.attach_artifact(
            slug="tes-test-feature",
            artifact_type="figma",
            url="https://figma.com/file/abc123",
        )

        self.assertTrue(result)

        # Verify action was logged to context file
        context_file = self.feature_path / "tes-test-feature-context.md"
        content = context_file.read_text()

        self.assertIn("Attached artifact:", content)
        self.assertIn("Figma design", content)


class TestActionLogNotFound(unittest.TestCase):
    """Test graceful handling when feature not found."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.user_path = self.test_dir / "user"
        self.user_path.mkdir()

        # Create products directory structure but NO feature
        self.products_path = (
            self.user_path / "products" / "growth-division" / "test-product"
        )
        self.products_path.mkdir(parents=True)

        self.mock_config = MagicMock()
        self.mock_config.user_path = str(self.user_path)
        self.mock_config.raw_config = {
            "products": {
                "organization": {"id": "growth-division"},
                "items": [
                    {
                        "id": "test-product",
                        "name": "Test Product",
                        "organization": "growth-division",
                    }
                ],
            },
            "master_sheet": {"enabled": False},
        }

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("config_loader.get_config")
    @patch("config_loader.get_user_name")
    def test_phase_transition_returns_none_if_not_found(
        self, mock_get_user_name, mock_get_config
    ):
        """Test that phase transition returns None for non-existent feature."""
        mock_get_config.return_value = self.mock_config
        mock_get_user_name.return_value = "test_user"

        from context_engine.feature_engine import FeatureEngine
        from context_engine.feature_state import FeaturePhase

        engine = FeatureEngine(user_path=self.user_path)

        result = engine.record_phase_transition(
            slug="non-existent-feature",
            from_phase=FeaturePhase.INITIALIZATION,
            to_phase=FeaturePhase.SIGNAL_ANALYSIS,
        )

        self.assertIsNone(result)

    @patch("config_loader.get_config")
    @patch("config_loader.get_user_name")
    def test_track_update_returns_none_if_not_found(
        self, mock_get_user_name, mock_get_config
    ):
        """Test that track update returns None for non-existent feature."""
        mock_get_config.return_value = self.mock_config
        mock_get_user_name.return_value = "test_user"

        from context_engine.feature_engine import FeatureEngine
        from context_engine.feature_state import TrackStatus

        engine = FeatureEngine(user_path=self.user_path)

        result = engine.update_track_status(
            slug="non-existent-feature",
            track_name="design",
            status=TrackStatus.IN_PROGRESS,
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
