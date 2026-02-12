"""
Tests for Bidirectional Sync Module

Tests the three-way synchronization between:
- Master Sheet
- Context file
- Feature state

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


class TestBidirectionalSyncCore(unittest.TestCase):
    """Test core sync functionality without config_loader dependency."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temp directory for test files
        self.test_dir = Path(tempfile.mkdtemp())
        self.feature_path = self.test_dir / "test-feature"
        self.feature_path.mkdir(parents=True)

        # Create sample feature-state.yaml
        self.state_data = {
            "slug": "test-feature",
            "title": "Test Feature",
            "product_id": "meal-kit",
            "organization": "growth-division",
            "context_file": "test-feature-context.md",
            "brain_entity": "[[Entities/Test_Feature]]",
            "master_sheet_row": 10,
            "created": "2026-02-04T10:00:00Z",
            "created_by": "test_user",
            "engine": {
                "current_phase": "context_doc",
                "phase_history": [
                    {
                        "phase": "initialization",
                        "entered": "2026-02-04T10:00:00Z",
                        "completed": "2026-02-04T10:01:00Z",
                    }
                ],
                "tracks": {
                    "context": {"status": "in_progress", "current_version": 1},
                    "design": {"status": "not_started"},
                    "business_case": {"status": "not_started"},
                    "engineering": {"status": "not_started"},
                },
            },
            "artifacts": {
                "jira_epic": None,
                "figma": "https://figma.com/file/test123",
                "confluence_page": None,
                "wireframes_url": "https://figma.com/wireframes",
            },
            "decisions": [],
        }

        # Write feature-state.yaml
        state_file = self.feature_path / "feature-state.yaml"
        with open(state_file, "w") as f:
            yaml.dump(self.state_data, f)

        # Create sample context file
        self.context_content = """# Test Feature Context

**Product:** MK
**Status:** To Do
**Owner:** test_user
**Priority:** P1
**Deadline:** 2026-02-15
**Last Updated:** 2026-02-01

## Description
*Feature context auto-generated from Master Sheet*

## Stakeholders
- **test_user** (Owner)

## Action Log
| Date | Action | Status | Priority | Deadline |
|------|--------|--------|----------|----------|
| 2026-02-01 | Initial setup | To Do | P1 | 2026-02-15 |

## References
- *No links yet*

## Brain Entities
- [[Entities/Test_Feature]]

## Changelog
- **2026-02-01**: Context file created
"""

        context_file = self.feature_path / "test-feature-context.md"
        context_file.write_text(self.context_content)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_derive_status_from_tracks_all_not_started(self):
        """Test status derivation when all tracks are not started."""
        from context_engine.bidirectional_sync import BidirectionalSync

        # Manually create sync instance without config_loader
        sync = BidirectionalSync.__new__(BidirectionalSync)
        sync._user_path = self.test_dir
        sync._raw_config = {"master_sheet": {"enabled": False}}
        sync._master_sheet_config = {"enabled": False}
        sync._product_mapping = {}
        sync._master_sheet_reader = None
        sync._sheets_service = None

        state_data = {
            "engine": {
                "tracks": {
                    "context": {"status": "not_started"},
                    "design": {"status": "not_started"},
                    "business_case": {"status": "not_started"},
                    "engineering": {"status": "not_started"},
                }
            }
        }

        status = sync._derive_status_from_tracks(state_data)
        self.assertEqual(status, "To Do")

    def test_derive_status_from_tracks_in_progress(self):
        """Test status derivation when some tracks are in progress."""
        from context_engine.bidirectional_sync import BidirectionalSync

        sync = BidirectionalSync.__new__(BidirectionalSync)
        sync._user_path = self.test_dir
        sync._raw_config = {"master_sheet": {"enabled": False}}
        sync._master_sheet_config = {"enabled": False}
        sync._product_mapping = {}
        sync._master_sheet_reader = None
        sync._sheets_service = None

        state_data = {
            "engine": {
                "tracks": {
                    "context": {"status": "complete"},
                    "design": {"status": "in_progress"},
                    "business_case": {"status": "not_started"},
                    "engineering": {"status": "not_started"},
                }
            }
        }

        status = sync._derive_status_from_tracks(state_data)
        self.assertEqual(status, "In Progress")

    def test_derive_status_from_tracks_all_complete(self):
        """Test status derivation when all tracks are complete."""
        from context_engine.bidirectional_sync import BidirectionalSync

        sync = BidirectionalSync.__new__(BidirectionalSync)
        sync._user_path = self.test_dir
        sync._raw_config = {"master_sheet": {"enabled": False}}
        sync._master_sheet_config = {"enabled": False}
        sync._product_mapping = {}
        sync._master_sheet_reader = None
        sync._sheets_service = None

        state_data = {
            "engine": {
                "tracks": {
                    "context": {"status": "complete"},
                    "design": {"status": "complete"},
                    "business_case": {"status": "complete"},
                    "engineering": {"status": "complete"},
                }
            }
        }

        status = sync._derive_status_from_tracks(state_data)
        self.assertEqual(status, "Done")

    def test_derive_status_from_tracks_pending_input(self):
        """Test status derivation when a track is pending input."""
        from context_engine.bidirectional_sync import BidirectionalSync

        sync = BidirectionalSync.__new__(BidirectionalSync)
        sync._user_path = self.test_dir
        sync._raw_config = {"master_sheet": {"enabled": False}}
        sync._master_sheet_config = {"enabled": False}
        sync._product_mapping = {}
        sync._master_sheet_reader = None
        sync._sheets_service = None

        state_data = {
            "engine": {
                "tracks": {
                    "context": {"status": "complete"},
                    "design": {"status": "pending_input"},
                    "business_case": {"status": "not_started"},
                    "engineering": {"status": "not_started"},
                }
            }
        }

        status = sync._derive_status_from_tracks(state_data)
        self.assertEqual(status, "In Progress")

    def test_parse_context_field(self):
        """Test parsing fields from context file."""
        from context_engine.bidirectional_sync import BidirectionalSync

        sync = BidirectionalSync.__new__(BidirectionalSync)
        sync._user_path = self.test_dir
        sync._raw_config = {"master_sheet": {"enabled": False}}
        sync._master_sheet_config = {"enabled": False}
        sync._product_mapping = {}
        sync._master_sheet_reader = None
        sync._sheets_service = None

        status = sync._parse_context_field(self.context_content, "status")
        self.assertEqual(status, "To Do")

        priority = sync._parse_context_field(self.context_content, "priority")
        self.assertEqual(priority, "P1")

        owner = sync._parse_context_field(self.context_content, "owner")
        self.assertEqual(owner, "test_user")

        deadline = sync._parse_context_field(self.context_content, "deadline")
        self.assertEqual(deadline, "2026-02-15")

    def test_update_context_field(self):
        """Test updating fields in context file."""
        from context_engine.bidirectional_sync import BidirectionalSync

        sync = BidirectionalSync.__new__(BidirectionalSync)
        sync._user_path = self.test_dir
        sync._raw_config = {"master_sheet": {"enabled": False}}
        sync._master_sheet_config = {"enabled": False}
        sync._product_mapping = {}
        sync._master_sheet_reader = None
        sync._sheets_service = None

        updated = sync._update_context_field(
            self.context_content, "status", "In Progress"
        )
        self.assertIn("**Status:** In Progress", updated)
        self.assertNotIn("**Status:** To Do", updated)

    def test_parse_action_log(self):
        """Test parsing action log from context file."""
        from context_engine.bidirectional_sync import BidirectionalSync

        sync = BidirectionalSync.__new__(BidirectionalSync)
        sync._user_path = self.test_dir
        sync._raw_config = {"master_sheet": {"enabled": False}}
        sync._master_sheet_config = {"enabled": False}
        sync._product_mapping = {}
        sync._master_sheet_reader = None
        sync._sheets_service = None

        actions = sync._parse_action_log(self.context_content)

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["date"], "2026-02-01")
        self.assertEqual(actions[0]["action"], "Initial setup")
        self.assertEqual(actions[0]["status"], "To Do")

    def test_update_references_section(self):
        """Test updating references section with artifacts."""
        from context_engine.bidirectional_sync import BidirectionalSync

        sync = BidirectionalSync.__new__(BidirectionalSync)
        sync._user_path = self.test_dir
        sync._raw_config = {"master_sheet": {"enabled": False}}
        sync._master_sheet_config = {"enabled": False}
        sync._product_mapping = {}
        sync._master_sheet_reader = None
        sync._sheets_service = None

        artifacts = {
            "figma": "https://figma.com/design",
            "jira_epic": "https://jira.com/MK-123",
            "confluence_page": None,
            "wireframes_url": None,
        }

        updated = sync._update_references_section(self.context_content, artifacts)

        self.assertIn("[Figma](https://figma.com/design)", updated)
        self.assertIn("[Jira Epic](https://jira.com/MK-123)", updated)
        self.assertNotIn("*No links yet*", updated)

    def test_add_action_log_entry(self):
        """Test adding action log entry."""
        from context_engine.bidirectional_sync import BidirectionalSync

        sync = BidirectionalSync.__new__(BidirectionalSync)
        sync._user_path = self.test_dir
        sync._raw_config = {"master_sheet": {"enabled": False}}
        sync._master_sheet_config = {"enabled": False}
        sync._product_mapping = {}
        sync._master_sheet_reader = None
        sync._sheets_service = None

        updated = sync._add_action_log_entry(
            self.context_content, "New action", "In Progress", "P1", "2026-02-20"
        )

        self.assertIn("New action", updated)
        self.assertIn("In Progress", updated)

    def test_update_changelog(self):
        """Test updating changelog section."""
        from context_engine.bidirectional_sync import BidirectionalSync

        sync = BidirectionalSync.__new__(BidirectionalSync)
        sync._user_path = self.test_dir
        sync._raw_config = {"master_sheet": {"enabled": False}}
        sync._master_sheet_config = {"enabled": False}
        sync._product_mapping = {}
        sync._master_sheet_reader = None
        sync._sheets_service = None

        updated = sync._update_changelog(self.context_content, "Context doc v2")

        self.assertIn("Context doc v2 completed", updated)


class TestSyncResult(unittest.TestCase):
    """Test SyncResult class."""

    def test_sync_result_to_dict(self):
        """Test SyncResult serialization."""
        from context_engine.bidirectional_sync import SyncDirection, SyncResult

        result = SyncResult(
            success=True,
            direction=SyncDirection.STATE_TO_OTHERS,
            fields_updated=["status", "references"],
            message="Test sync complete",
            context_file_updated=True,
            master_sheet_updated=False,
            feature_state_updated=False,
        )

        result_dict = result.to_dict()

        self.assertTrue(result_dict["success"])
        self.assertEqual(result_dict["direction"], "state_to_others")
        self.assertEqual(result_dict["fields_updated"], ["status", "references"])
        self.assertTrue(result_dict["context_file_updated"])

    def test_sync_result_defaults(self):
        """Test SyncResult default values."""
        from context_engine.bidirectional_sync import SyncResult

        result = SyncResult(success=False)

        self.assertFalse(result.success)
        self.assertIsNone(result.direction)
        self.assertEqual(result.fields_updated, [])
        self.assertEqual(result.message, "")
        self.assertEqual(result.errors, [])
        self.assertFalse(result.context_file_updated)
        self.assertFalse(result.master_sheet_updated)
        self.assertFalse(result.feature_state_updated)


class TestSyncFromState(unittest.TestCase):
    """Test syncing from feature state to context file."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.feature_path = self.test_dir / "test-feature"
        self.feature_path.mkdir(parents=True)

        # Create feature state
        state_data = {
            "slug": "test-feature",
            "title": "Test Feature",
            "context_file": "test-feature-context.md",
            "master_sheet_row": None,
            "engine": {
                "tracks": {
                    "context": {"status": "in_progress"},
                    "design": {"status": "not_started"},
                    "business_case": {"status": "not_started"},
                    "engineering": {"status": "not_started"},
                }
            },
            "artifacts": {
                "figma": "https://figma.com/test",
                "jira_epic": None,
                "confluence_page": None,
                "wireframes_url": None,
            },
        }

        state_file = self.feature_path / "feature-state.yaml"
        with open(state_file, "w") as f:
            yaml.dump(state_data, f)

        # Create context file
        context_content = """# Test Feature Context

**Status:** To Do
**Owner:** test_user
**Last Updated:** 2026-02-01

## References
- *No links yet*
"""
        context_file = self.feature_path / "test-feature-context.md"
        context_file.write_text(context_content)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sync_from_state(self):
        """Test syncing from feature state to context file."""
        from context_engine.bidirectional_sync import BidirectionalSync, SyncDirection

        sync = BidirectionalSync.__new__(BidirectionalSync)
        sync._user_path = self.test_dir
        sync._raw_config = {"master_sheet": {"enabled": False}}
        sync._master_sheet_config = {"enabled": False}
        sync._product_mapping = {}
        sync._master_sheet_reader = None
        sync._sheets_service = None

        result = sync.sync_from_state(self.feature_path)

        self.assertTrue(result.success)
        self.assertEqual(result.direction, SyncDirection.STATE_TO_OTHERS)
        self.assertTrue(result.context_file_updated)
        self.assertIn("status", result.fields_updated)

        # Verify context file was updated
        context_file = self.feature_path / "test-feature-context.md"
        content = context_file.read_text()
        self.assertIn("**Status:** In Progress", content)

    def test_sync_from_state_updates_references(self):
        """Test that references section is updated with artifacts."""
        from context_engine.bidirectional_sync import BidirectionalSync

        sync = BidirectionalSync.__new__(BidirectionalSync)
        sync._user_path = self.test_dir
        sync._raw_config = {"master_sheet": {"enabled": False}}
        sync._master_sheet_config = {"enabled": False}
        sync._product_mapping = {}
        sync._master_sheet_reader = None
        sync._sheets_service = None

        result = sync.sync_from_state(self.feature_path)

        self.assertTrue(result.success)

        # Verify references were updated
        context_file = self.feature_path / "test-feature-context.md"
        content = context_file.read_text()
        self.assertIn("Figma", content)
        self.assertIn("https://figma.com/test", content)

    def test_sync_from_state_missing_state_file(self):
        """Test sync from state when state file is missing."""
        from context_engine.bidirectional_sync import BidirectionalSync

        # Create empty feature path
        empty_path = self.test_dir / "empty-feature"
        empty_path.mkdir()

        sync = BidirectionalSync.__new__(BidirectionalSync)
        sync._user_path = self.test_dir
        sync._raw_config = {"master_sheet": {"enabled": False}}
        sync._master_sheet_config = {"enabled": False}
        sync._product_mapping = {}
        sync._master_sheet_reader = None
        sync._sheets_service = None

        result = sync.sync_from_state(empty_path)

        self.assertFalse(result.success)
        self.assertTrue(len(result.errors) > 0)


class TestAddActionToLog(unittest.TestCase):
    """Test adding actions to context file log."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.feature_path = self.test_dir / "test-feature"
        self.feature_path.mkdir(parents=True)

        # Create feature state
        state_data = {
            "slug": "test-feature",
            "context_file": "test-feature-context.md",
            "engine": {
                "tracks": {
                    "context": {"status": "in_progress"},
                    "design": {"status": "not_started"},
                    "business_case": {"status": "not_started"},
                    "engineering": {"status": "not_started"},
                }
            },
        }

        state_file = self.feature_path / "feature-state.yaml"
        with open(state_file, "w") as f:
            yaml.dump(state_data, f)

        # Create context file with action log
        context_content = """# Test Feature Context

**Status:** To Do

## Action Log
| Date | Action | Status | Priority | Deadline |
|------|--------|--------|----------|----------|
| 2026-02-01 | Initial setup | To Do | P1 | 2026-02-15 |

## References
- *No links yet*
"""
        context_file = self.feature_path / "test-feature-context.md"
        context_file.write_text(context_content)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_add_action_to_log(self):
        """Test adding action log entry."""
        from context_engine.bidirectional_sync import BidirectionalSync

        sync = BidirectionalSync.__new__(BidirectionalSync)
        sync._user_path = self.test_dir
        sync._raw_config = {"master_sheet": {"enabled": False}}
        sync._master_sheet_config = {"enabled": False}
        sync._product_mapping = {}
        sync._master_sheet_reader = None
        sync._sheets_service = None

        result = sync.add_action_to_log(
            self.feature_path,
            action="Context doc v1 complete",
            status="In Progress",
            priority="P1",
            deadline="2026-02-15",
        )

        self.assertTrue(result.success)
        self.assertTrue(result.context_file_updated)
        self.assertIn("action_log", result.fields_updated)

        # Verify action was added
        context_file = self.feature_path / "test-feature-context.md"
        content = context_file.read_text()
        self.assertIn("Context doc v1 complete", content)


class TestRecordPhaseCompletion(unittest.TestCase):
    """Test recording phase completion in changelog."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.feature_path = self.test_dir / "test-feature"
        self.feature_path.mkdir(parents=True)

        # Create feature state
        state_data = {"slug": "test-feature", "context_file": "test-feature-context.md"}

        state_file = self.feature_path / "feature-state.yaml"
        with open(state_file, "w") as f:
            yaml.dump(state_data, f)

        # Create context file with changelog
        context_content = """# Test Feature Context

**Status:** To Do

## References
- *No links yet*

## Changelog
- **2026-02-01**: Context file created
"""
        context_file = self.feature_path / "test-feature-context.md"
        context_file.write_text(context_content)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_record_phase_completion(self):
        """Test recording phase completion in changelog."""
        from context_engine.bidirectional_sync import BidirectionalSync

        sync = BidirectionalSync.__new__(BidirectionalSync)
        sync._user_path = self.test_dir
        sync._raw_config = {"master_sheet": {"enabled": False}}
        sync._master_sheet_config = {"enabled": False}
        sync._product_mapping = {}
        sync._master_sheet_reader = None
        sync._sheets_service = None

        result = sync.record_phase_completion(
            self.feature_path, phase_name="Context document v2"
        )

        self.assertTrue(result.success)
        self.assertTrue(result.context_file_updated)
        self.assertIn("changelog", result.fields_updated)

        # Verify changelog was updated
        context_file = self.feature_path / "test-feature-context.md"
        content = context_file.read_text()
        self.assertIn("Context document v2 completed", content)


if __name__ == "__main__":
    unittest.main()
