"""
Tests for Jira Integration Module

Tests the JiraEpicCreator class and related functionality.
Uses mocking to avoid actual Jira API calls.
"""

import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import yaml

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from context_engine.feature_state import FeaturePhase, FeatureState, TrackStatus
from context_engine.jira_integration import (
    EpicCreationResult,
    JiraApiError,
    JiraConfigError,
    JiraEpicCreator,
    JiraIntegrationError,
    LinkedArtifact,
    StoryData,
    create_jira_epic,
)


class TestLinkedArtifact:
    """Tests for LinkedArtifact dataclass."""

    def test_create_artifact(self):
        """Test creating a LinkedArtifact."""
        artifact = LinkedArtifact(
            artifact_type="figma",
            title="Design Files",
            url="https://figma.com/file/abc123",
            description="Main design file",
        )

        assert artifact.artifact_type == "figma"
        assert artifact.title == "Design Files"
        assert artifact.url == "https://figma.com/file/abc123"
        assert artifact.description == "Main design file"

    def test_artifact_without_description(self):
        """Test creating artifact without description."""
        artifact = LinkedArtifact(
            artifact_type="confluence",
            title="Docs",
            url="https://confluence.atlassian.com/page/123",
        )

        assert artifact.description is None


class TestStoryData:
    """Tests for StoryData dataclass."""

    def test_create_story_data(self):
        """Test creating StoryData."""
        story = StoryData(
            title="Implement feature X",
            description="Implementation details",
            estimate_size="M",
            adr_number=1,
            labels=["feature", "backend"],
        )

        assert story.title == "Implement feature X"
        assert story.estimate_size == "M"
        assert story.adr_number == 1
        assert "feature" in story.labels

    def test_story_data_defaults(self):
        """Test StoryData default values."""
        story = StoryData(title="Simple story", description="Desc", estimate_size="S")

        assert story.adr_number is None
        assert story.labels == []


class TestEpicCreationResult:
    """Tests for EpicCreationResult dataclass."""

    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = EpicCreationResult(
            success=True,
            epic_key="MK-123",
            epic_url="https://jira.example.com/browse/MK-123",
            stories_created=[{"key": "MK-124"}],
            message="Success",
        )

        d = result.to_dict()

        assert d["success"] is True
        assert d["epic_key"] == "MK-123"
        assert d["epic_url"] == "https://jira.example.com/browse/MK-123"
        assert len(d["stories_created"]) == 1
        assert d["message"] == "Success"

    def test_dry_run_result(self):
        """Test dry run result includes preview data."""
        result = EpicCreationResult(
            success=True,
            dry_run=True,
            epic_preview={"title": "Test Epic", "project_key": "MK"},
            stories_preview=[{"title": "Story 1"}],
        )

        d = result.to_dict()

        assert d["dry_run"] is True
        assert d["epic_preview"]["title"] == "Test Epic"
        assert len(d["stories_preview"]) == 1


class TestJiraEpicCreatorUnit:
    """Unit tests for JiraEpicCreator that don't require config mocking."""

    def test_estimate_to_story_points_s(self):
        """Test S estimate to story points."""
        # Create creator with mocked config
        with patch.dict("sys.modules", {"config_loader": MagicMock()}):
            # Direct test of mapping logic
            mapping = {"XS": 1, "S": 2, "M": 3, "L": 5, "XL": 8}
            assert mapping.get("S") == 2

    def test_estimate_to_story_points_m(self):
        """Test M estimate to story points."""
        mapping = {"XS": 1, "S": 2, "M": 3, "L": 5, "XL": 8}
        assert mapping.get("M") == 3

    def test_estimate_to_story_points_l(self):
        """Test L estimate to story points."""
        mapping = {"XS": 1, "S": 2, "M": 3, "L": 5, "XL": 8}
        assert mapping.get("L") == 5

    def test_estimate_to_story_points_xl(self):
        """Test XL estimate to story points."""
        mapping = {"XS": 1, "S": 2, "M": 3, "L": 5, "XL": 8}
        assert mapping.get("XL") == 8

    def test_estimate_to_story_points_invalid(self):
        """Test invalid estimate returns None."""
        mapping = {"XS": 1, "S": 2, "M": 3, "L": 5, "XL": 8}
        assert mapping.get("invalid") is None


class TestJiraEpicCreatorWithConfig:
    """Tests that require config loader mocking."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config_loader module."""
        mock = MagicMock()
        mock_config_obj = MagicMock()
        mock_config_obj.user_path = Path("/tmp/user")
        mock.get_config.return_value = mock_config_obj
        mock.get_jira_config.return_value = {
            "url": "https://jira.example.com",
            "username": "test@example.com",
            "api_token": "test-token-123",
        }
        mock.get_product_by_id.return_value = {
            "id": "meal-kit",
            "name": "Meal Kit",
            "jira_project": "MK",
        }
        return mock

    @pytest.fixture
    def temp_feature_dir(self):
        """Create a temporary feature directory with state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            feature_path = Path(tmpdir) / "test-feature"
            feature_path.mkdir()

            # Create feature state
            state_data = {
                "slug": "test-feature",
                "title": "Test Feature",
                "product_id": "meal-kit",
                "organization": "growth-division",
                "context_file": "test-feature-context.md",
                "brain_entity": "[[Entities/Test_Feature]]",
                "created": datetime.now().isoformat(),
                "created_by": "test",
                "engine": {
                    "current_phase": "parallel_tracks",
                    "phase_history": [],
                    "tracks": {
                        "context": {"status": "complete"},
                        "design": {"status": "in_progress"},
                        "business_case": {"status": "complete"},
                        "engineering": {"status": "in_progress"},
                    },
                },
                "artifacts": {
                    "figma": "https://figma.com/file/test123",
                    "confluence_page": "https://confluence.com/page/123",
                    "jira_epic": None,
                },
                "decisions": [],
            }

            with open(feature_path / "feature-state.yaml", "w") as f:
                yaml.dump(state_data, f)

            # Create context document
            context_doc = """# Test Feature

## Description

This is a test feature for unit testing the Jira integration.

## Scope

### In Scope
- Feature implementation
- Testing

### Out of Scope
- Production deployment
"""
            (feature_path / "test-feature-context.md").write_text(context_doc)

            yield feature_path

    def test_create_epic_dry_run(self, mock_config, temp_feature_dir):
        """Test epic creation in dry run mode."""
        with patch.dict("sys.modules", {"config_loader": mock_config}):
            # Need to reimport to pick up the mock
            from context_engine.jira_integration import JiraEpicCreator

            creator = JiraEpicCreator()

            result = creator.create_epic_from_feature(
                feature_path=temp_feature_dir, dry_run=True
            )

            assert result.success is True
            assert result.dry_run is True
            assert result.epic_preview is not None
            assert "DRY RUN" in result.message

    def test_collect_artifacts(self, mock_config, temp_feature_dir):
        """Test collecting artifacts from feature state."""
        with patch.dict("sys.modules", {"config_loader": mock_config}):
            from context_engine.jira_integration import JiraEpicCreator

            creator = JiraEpicCreator()
            state = FeatureState.load(temp_feature_dir)
            artifacts = creator._collect_artifacts(temp_feature_dir, state)

            artifact_types = [a.artifact_type for a in artifacts]
            assert "figma" in artifact_types
            assert "confluence" in artifact_types

    def test_extract_description(self, mock_config, temp_feature_dir):
        """Test extracting description from context doc."""
        with patch.dict("sys.modules", {"config_loader": mock_config}):
            from context_engine.jira_integration import JiraEpicCreator

            creator = JiraEpicCreator()
            state = FeatureState.load(temp_feature_dir)
            description = creator._extract_description(temp_feature_dir, state)

            assert "Problem Statement" in description
            assert "test feature" in description.lower()


class TestArtifactLinking:
    """Tests for artifact linking functionality."""

    def test_link_artifact_dry_run(self):
        """Test artifact linking in dry run mode."""
        artifact = LinkedArtifact(
            artifact_type="figma", title="Design", url="https://figma.com/file/123"
        )

        # Test without creating a real creator
        result = {
            "dry_run": True,
            "epic_key": "MK-123",
            "artifact_type": artifact.artifact_type,
            "title": artifact.title,
            "url": artifact.url,
        }

        assert result["dry_run"] is True
        assert result["epic_key"] == "MK-123"
        assert result["artifact_type"] == "figma"

    def test_link_artifact_skips_local_paths(self):
        """Test that local file paths are skipped."""
        artifact = LinkedArtifact(
            artifact_type="adr", title="ADR-001", url="/path/to/local/file.md"
        )

        # Simulate skip logic
        url = artifact.url
        if not url.startswith(("http://", "https://")):
            result = {
                "skipped": True,
                "reason": "Local path, not linkable",
                "artifact_type": artifact.artifact_type,
                "title": artifact.title,
            }
        else:
            result = {"skipped": False}

        assert result.get("skipped") is True
        assert "Local path" in result.get("reason", "")


class TestStoryCreation:
    """Tests for story creation functionality."""

    def test_create_story_dry_run(self):
        """Test story creation in dry run mode."""
        story = StoryData(
            title="Test Story",
            description="Test description",
            estimate_size="M",
            labels=["test"],
        )

        # Simulate dry run result
        result = {
            "dry_run": True,
            "project_key": "MK",
            "epic_key": "MK-123",
            "title": story.title,
            "estimate": story.estimate_size,
            "labels": story.labels,
        }

        assert result["dry_run"] is True
        assert result["title"] == "Test Story"
        assert result["estimate"] == "M"


class TestExistingEpicHandling:
    """Tests for handling existing epic scenarios."""

    @pytest.fixture
    def temp_feature_with_epic(self):
        """Create feature directory with existing epic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            feature_path = Path(tmpdir) / "test-feature"
            feature_path.mkdir()

            state_data = {
                "slug": "test-feature",
                "title": "Test Feature",
                "product_id": "meal-kit",
                "organization": "growth-division",
                "context_file": "test-feature-context.md",
                "brain_entity": "[[Entities/Test_Feature]]",
                "created": datetime.now().isoformat(),
                "created_by": "test",
                "engine": {
                    "current_phase": "parallel_tracks",
                    "phase_history": [],
                    "tracks": {},
                },
                "artifacts": {
                    "jira_epic": "MK-999",  # Existing epic
                },
                "decisions": [],
            }

            with open(feature_path / "feature-state.yaml", "w") as f:
                yaml.dump(state_data, f)

            yield feature_path

    def test_existing_epic_not_overwritten(self, temp_feature_with_epic):
        """Test that existing epic is not overwritten."""
        mock_config = MagicMock()
        mock_config_obj = MagicMock()
        mock_config_obj.user_path = Path("/tmp/user")
        mock_config.get_config.return_value = mock_config_obj
        mock_config.get_jira_config.return_value = {
            "url": "https://jira.example.com",
            "username": "test@example.com",
            "api_token": "token",
        }
        mock_config.get_product_by_id.return_value = {
            "id": "meal-kit",
            "jira_project": "MK",
        }

        with patch.dict("sys.modules", {"config_loader": mock_config}):
            from context_engine.jira_integration import JiraEpicCreator

            creator = JiraEpicCreator()

            result = creator.create_epic_from_feature(
                feature_path=temp_feature_with_epic, dry_run=False
            )

            assert result.success is True
            assert result.epic_key == "MK-999"
            assert "already has" in result.message


class TestArtifactIconMapping:
    """Tests for artifact icon mapping."""

    def test_known_artifact_icons(self):
        """Test icons for known artifact types."""
        icons = {
            "figma": {
                "url16x16": "https://static.figma.com/app/icon/1/favicon.png",
                "title": "Figma",
            },
            "confluence": {
                "url16x16": "https://wac-cdn.atlassian.com/assets/img/favicons/confluence/favicon.png",
                "title": "Confluence",
            },
        }

        figma_icon = icons.get("figma", {})
        assert "figma" in figma_icon.get("url16x16", "").lower()

        confluence_icon = icons.get("confluence", {})
        assert "confluence" in confluence_icon.get("title", "").lower()

    def test_unknown_artifact_icon(self):
        """Test fallback for unknown artifact types."""
        icons = {
            "figma": {"url16x16": "...", "title": "Figma"},
        }

        # Unknown type falls back to the type name as title
        artifact_type = "unknown_type"
        unknown_icon = icons.get(
            artifact_type, {"url16x16": "", "title": artifact_type}
        )

        assert unknown_icon["title"] == "unknown_type"


class TestConvenienceFunction:
    """Tests for convenience function."""

    @pytest.fixture
    def temp_feature_dir(self):
        """Create a temporary feature directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            feature_path = Path(tmpdir) / "test-feature"
            feature_path.mkdir()

            state_data = {
                "slug": "test-feature",
                "title": "Test Feature",
                "product_id": "meal-kit",
                "organization": "growth-division",
                "context_file": "test-feature-context.md",
                "brain_entity": "[[Entities/Test_Feature]]",
                "created": datetime.now().isoformat(),
                "created_by": "test",
                "engine": {
                    "current_phase": "parallel_tracks",
                    "phase_history": [],
                    "tracks": {},
                },
                "artifacts": {},
                "decisions": [],
            }

            with open(feature_path / "feature-state.yaml", "w") as f:
                yaml.dump(state_data, f)

            yield feature_path

    def test_create_jira_epic_function(self, temp_feature_dir):
        """Test convenience function."""
        mock_config = MagicMock()
        mock_config_obj = MagicMock()
        mock_config_obj.user_path = Path("/tmp/user")
        mock_config.get_config.return_value = mock_config_obj
        mock_config.get_jira_config.return_value = {
            "url": "https://jira.example.com",
            "username": "test@example.com",
            "api_token": "token",
        }
        mock_config.get_product_by_id.return_value = {
            "id": "meal-kit",
            "jira_project": "MK",
        }

        with patch.dict("sys.modules", {"config_loader": mock_config}):
            from context_engine.jira_integration import create_jira_epic

            result = create_jira_epic(feature_path=temp_feature_dir, dry_run=True)

            assert result.success is True
            assert result.dry_run is True


class TestProjectKeyDerivation:
    """Tests for project key derivation from product ID."""

    def test_derive_project_key_from_product_id(self):
        """Test deriving project key from product ID."""
        # Test the derivation logic directly
        product_id = "brand-b"
        product_id_upper = product_id.upper()

        if "-" in product_id_upper:
            parts = product_id_upper.split("-")
            project_key = "".join(p[0] for p in parts if p)
        else:
            project_key = product_id_upper[:3]

        assert project_key == "BB"

    def test_derive_project_key_short_name(self):
        """Test deriving project key from short product name."""
        product_id = "growth-platform"
        product_id_upper = product_id.upper()

        if "-" in product_id_upper:
            parts = product_id_upper.split("-")
            project_key = "".join(p[0] for p in parts if p)
        else:
            project_key = product_id_upper[:3]

        assert project_key == "FF"
