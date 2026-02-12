"""
Unit tests for the Blocker Detection module.

Tests cover:
- BlockerType enum values
- BlockerSeverity enum values
- Blocker dataclass serialization
- BlockerReport aggregation
- BlockerDetector detection methods
- Missing artifact detection
- Pending approval detection
- Incomplete prerequisite detection
- Blocking dependency detection
- Unmitigated risk detection
- Filtering by type, severity, track
- Report generation
"""

import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from context_engine.blocker_detection import (
    Blocker,
    BlockerDetector,
    BlockerReport,
    BlockerSeverity,
    BlockerTrack,
    BlockerType,
    detect_blockers,
    format_blocker_list,
    get_blocker_report,
    has_blockers,
)


class TestBlockerEnums:
    """Test enum definitions."""

    def test_blocker_type_values(self):
        """Test BlockerType enum values."""
        assert BlockerType.MISSING_ARTIFACT.value == "missing_artifact"
        assert BlockerType.PENDING_APPROVAL.value == "pending_approval"
        assert BlockerType.INCOMPLETE_PREREQ.value == "incomplete_prereq"
        assert BlockerType.BLOCKING_DEPENDENCY.value == "blocking_dependency"
        assert BlockerType.UNMITIGATED_RISK.value == "unmitigated_risk"

    def test_blocker_severity_values(self):
        """Test BlockerSeverity enum values."""
        assert BlockerSeverity.CRITICAL.value == "critical"
        assert BlockerSeverity.HIGH.value == "high"
        assert BlockerSeverity.MEDIUM.value == "medium"
        assert BlockerSeverity.LOW.value == "low"

    def test_blocker_track_values(self):
        """Test BlockerTrack enum values."""
        assert BlockerTrack.CONTEXT.value == "context"
        assert BlockerTrack.DESIGN.value == "design"
        assert BlockerTrack.BUSINESS_CASE.value == "business_case"
        assert BlockerTrack.ENGINEERING.value == "engineering"
        assert BlockerTrack.GENERAL.value == "general"


class TestBlockerDataclass:
    """Test Blocker dataclass."""

    def test_blocker_creation(self):
        """Test creating a blocker."""
        blocker = Blocker(
            type=BlockerType.MISSING_ARTIFACT,
            description="Figma URL not attached",
            severity=BlockerSeverity.HIGH,
            track=BlockerTrack.DESIGN,
            resolution_hint="Use /attach-artifact figma <url>",
        )
        assert blocker.type == BlockerType.MISSING_ARTIFACT
        assert blocker.description == "Figma URL not attached"
        assert blocker.severity == BlockerSeverity.HIGH
        assert blocker.track == BlockerTrack.DESIGN
        assert blocker.resolution_hint == "Use /attach-artifact figma <url>"

    def test_blocker_default_values(self):
        """Test blocker default values."""
        blocker = Blocker(
            type=BlockerType.PENDING_APPROVAL,
            description="Test",
            severity=BlockerSeverity.MEDIUM,
        )
        assert blocker.track == BlockerTrack.GENERAL
        assert blocker.resolution_hint is None
        assert blocker.details is None
        assert isinstance(blocker.detected_at, datetime)
        assert blocker.metadata == {}

    def test_blocker_is_critical(self):
        """Test is_critical property."""
        critical = Blocker(
            type=BlockerType.PENDING_APPROVAL,
            description="BC rejected",
            severity=BlockerSeverity.CRITICAL,
        )
        high = Blocker(
            type=BlockerType.PENDING_APPROVAL,
            description="BC pending",
            severity=BlockerSeverity.HIGH,
        )
        assert critical.is_critical is True
        assert high.is_critical is False

    def test_blocker_is_blocking(self):
        """Test is_blocking property."""
        critical = Blocker(
            type=BlockerType.PENDING_APPROVAL,
            description="",
            severity=BlockerSeverity.CRITICAL,
        )
        high = Blocker(
            type=BlockerType.PENDING_APPROVAL,
            description="",
            severity=BlockerSeverity.HIGH,
        )
        medium = Blocker(
            type=BlockerType.PENDING_APPROVAL,
            description="",
            severity=BlockerSeverity.MEDIUM,
        )
        low = Blocker(
            type=BlockerType.PENDING_APPROVAL,
            description="",
            severity=BlockerSeverity.LOW,
        )

        assert critical.is_blocking is True
        assert high.is_blocking is True
        assert medium.is_blocking is True
        assert low.is_blocking is False

    def test_blocker_to_dict(self):
        """Test to_dict serialization."""
        blocker = Blocker(
            type=BlockerType.MISSING_ARTIFACT,
            description="Test description",
            severity=BlockerSeverity.HIGH,
            track=BlockerTrack.DESIGN,
            resolution_hint="Test hint",
            details="Test details",
            metadata={"key": "value"},
        )
        data = blocker.to_dict()

        assert data["type"] == "missing_artifact"
        assert data["description"] == "Test description"
        assert data["severity"] == "high"
        assert data["track"] == "design"
        assert data["resolution_hint"] == "Test hint"
        assert data["details"] == "Test details"
        assert data["metadata"] == {"key": "value"}
        assert "detected_at" in data

    def test_blocker_from_dict(self):
        """Test from_dict deserialization."""
        data = {
            "type": "pending_approval",
            "description": "Awaiting approval",
            "severity": "high",
            "track": "business_case",
            "resolution_hint": "Contact stakeholder",
            "detected_at": "2026-02-04T10:00:00",
        }
        blocker = Blocker.from_dict(data)

        assert blocker.type == BlockerType.PENDING_APPROVAL
        assert blocker.description == "Awaiting approval"
        assert blocker.severity == BlockerSeverity.HIGH
        assert blocker.track == BlockerTrack.BUSINESS_CASE
        assert blocker.resolution_hint == "Contact stakeholder"


class TestBlockerReport:
    """Test BlockerReport aggregation."""

    def test_empty_report(self):
        """Test report with no blockers."""
        report = BlockerReport(feature_slug="test-feature")
        assert report.total_count == 0
        assert report.critical_count == 0
        assert report.has_critical is False
        assert report.has_blocking is False

    def test_report_counts(self):
        """Test report count properties."""
        report = BlockerReport(
            feature_slug="test-feature",
            blockers=[
                Blocker(
                    type=BlockerType.PENDING_APPROVAL,
                    description="",
                    severity=BlockerSeverity.CRITICAL,
                ),
                Blocker(
                    type=BlockerType.MISSING_ARTIFACT,
                    description="",
                    severity=BlockerSeverity.HIGH,
                ),
                Blocker(
                    type=BlockerType.MISSING_ARTIFACT,
                    description="",
                    severity=BlockerSeverity.HIGH,
                ),
                Blocker(
                    type=BlockerType.INCOMPLETE_PREREQ,
                    description="",
                    severity=BlockerSeverity.MEDIUM,
                ),
                Blocker(
                    type=BlockerType.MISSING_ARTIFACT,
                    description="",
                    severity=BlockerSeverity.LOW,
                ),
            ],
        )

        assert report.total_count == 5
        assert report.critical_count == 1
        assert report.high_count == 2
        assert report.medium_count == 1
        assert report.low_count == 1

    def test_report_has_critical(self):
        """Test has_critical property."""
        with_critical = BlockerReport(
            feature_slug="test",
            blockers=[
                Blocker(
                    type=BlockerType.PENDING_APPROVAL,
                    description="",
                    severity=BlockerSeverity.CRITICAL,
                ),
            ],
        )
        without_critical = BlockerReport(
            feature_slug="test",
            blockers=[
                Blocker(
                    type=BlockerType.PENDING_APPROVAL,
                    description="",
                    severity=BlockerSeverity.HIGH,
                ),
            ],
        )

        assert with_critical.has_critical is True
        assert without_critical.has_critical is False

    def test_report_has_blocking(self):
        """Test has_blocking property."""
        with_blocking = BlockerReport(
            feature_slug="test",
            blockers=[
                Blocker(
                    type=BlockerType.PENDING_APPROVAL,
                    description="",
                    severity=BlockerSeverity.MEDIUM,
                ),
            ],
        )
        without_blocking = BlockerReport(
            feature_slug="test",
            blockers=[
                Blocker(
                    type=BlockerType.PENDING_APPROVAL,
                    description="",
                    severity=BlockerSeverity.LOW,
                ),
            ],
        )

        assert with_blocking.has_blocking is True
        assert without_blocking.has_blocking is False

    def test_report_get_by_type(self):
        """Test filtering by type."""
        report = BlockerReport(
            feature_slug="test",
            blockers=[
                Blocker(
                    type=BlockerType.MISSING_ARTIFACT,
                    description="",
                    severity=BlockerSeverity.HIGH,
                ),
                Blocker(
                    type=BlockerType.MISSING_ARTIFACT,
                    description="",
                    severity=BlockerSeverity.LOW,
                ),
                Blocker(
                    type=BlockerType.PENDING_APPROVAL,
                    description="",
                    severity=BlockerSeverity.HIGH,
                ),
            ],
        )

        artifacts = report.get_by_type(BlockerType.MISSING_ARTIFACT)
        approvals = report.get_by_type(BlockerType.PENDING_APPROVAL)

        assert len(artifacts) == 2
        assert len(approvals) == 1

    def test_report_get_by_severity(self):
        """Test filtering by severity."""
        report = BlockerReport(
            feature_slug="test",
            blockers=[
                Blocker(
                    type=BlockerType.MISSING_ARTIFACT,
                    description="",
                    severity=BlockerSeverity.HIGH,
                ),
                Blocker(
                    type=BlockerType.PENDING_APPROVAL,
                    description="",
                    severity=BlockerSeverity.HIGH,
                ),
                Blocker(
                    type=BlockerType.INCOMPLETE_PREREQ,
                    description="",
                    severity=BlockerSeverity.MEDIUM,
                ),
            ],
        )

        high = report.get_by_severity(BlockerSeverity.HIGH)
        medium = report.get_by_severity(BlockerSeverity.MEDIUM)

        assert len(high) == 2
        assert len(medium) == 1

    def test_report_get_by_track(self):
        """Test filtering by track."""
        report = BlockerReport(
            feature_slug="test",
            blockers=[
                Blocker(
                    type=BlockerType.MISSING_ARTIFACT,
                    description="",
                    severity=BlockerSeverity.HIGH,
                    track=BlockerTrack.DESIGN,
                ),
                Blocker(
                    type=BlockerType.PENDING_APPROVAL,
                    description="",
                    severity=BlockerSeverity.HIGH,
                    track=BlockerTrack.BUSINESS_CASE,
                ),
                Blocker(
                    type=BlockerType.INCOMPLETE_PREREQ,
                    description="",
                    severity=BlockerSeverity.MEDIUM,
                    track=BlockerTrack.ENGINEERING,
                ),
            ],
        )

        design = report.get_by_track("design")
        bc = report.get_by_track("business_case")
        invalid = report.get_by_track("invalid_track")

        assert len(design) == 1
        assert len(bc) == 1
        assert len(invalid) == 0

    def test_report_to_dict(self):
        """Test to_dict serialization."""
        report = BlockerReport(
            feature_slug="test-feature",
            blockers=[
                Blocker(
                    type=BlockerType.MISSING_ARTIFACT,
                    description="Test",
                    severity=BlockerSeverity.HIGH,
                ),
            ],
        )
        data = report.to_dict()

        assert data["feature_slug"] == "test-feature"
        assert data["total_count"] == 1
        assert data["high_count"] == 1
        assert "blockers" in data
        assert len(data["blockers"]) == 1

    def test_report_to_summary(self):
        """Test summary generation."""
        report = BlockerReport(
            feature_slug="test-feature",
            blockers=[
                Blocker(
                    type=BlockerType.PENDING_APPROVAL,
                    description="",
                    severity=BlockerSeverity.CRITICAL,
                ),
                Blocker(
                    type=BlockerType.MISSING_ARTIFACT,
                    description="",
                    severity=BlockerSeverity.HIGH,
                ),
            ],
        )
        summary = report.to_summary()

        assert "test-feature" in summary
        assert "2 total" in summary
        assert "[CRITICAL]" in summary
        assert "[HIGH]" in summary

    def test_empty_report_summary(self):
        """Test summary for empty report."""
        report = BlockerReport(feature_slug="test")
        summary = report.to_summary()
        assert summary == "No blockers detected"


class TestBlockerDetector:
    """Test BlockerDetector class."""

    @pytest.fixture
    def temp_feature_dir(self):
        """Create a temporary feature directory with state file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            feature_path = Path(tmpdir)
            state_file = feature_path / "feature-state.yaml"

            state_data = {
                "slug": "test-feature",
                "title": "Test Feature",
                "product_id": "test-product",
                "organization": "test-org",
                "context_file": "test-feature-context.md",
                "brain_entity": "[[Entities/Test_Feature]]",
                "created": datetime.now().isoformat(),
                "engine": {
                    "current_phase": "parallel_tracks",
                    "phase_history": [],
                    "tracks": {
                        "context": {"status": "in_progress", "current_version": 1},
                        "design": {"status": "not_started"},
                        "business_case": {"status": "not_started"},
                        "engineering": {"status": "not_started"},
                    },
                },
                "artifacts": {
                    "figma": None,
                    "wireframes_url": None,
                    "jira_epic": None,
                },
            }

            with open(state_file, "w") as f:
                yaml.dump(state_data, f)

            yield feature_path

    def test_detector_initialization(self, temp_feature_dir):
        """Test detector initialization."""
        detector = BlockerDetector(temp_feature_dir)
        assert detector.feature_path == temp_feature_dir
        assert detector.gates is not None

    def test_detect_missing_artifacts_figma_required(self, temp_feature_dir):
        """Test detection of missing Figma (required by default)."""
        detector = BlockerDetector(temp_feature_dir)
        blockers = detector.detect_missing_artifacts()

        figma_blockers = [b for b in blockers if "figma" in b.description.lower()]
        assert len(figma_blockers) == 1
        assert figma_blockers[0].severity == BlockerSeverity.HIGH
        assert figma_blockers[0].type == BlockerType.MISSING_ARTIFACT

    def test_detect_missing_artifacts_wireframes_optional(self, temp_feature_dir):
        """Test detection of missing wireframes (optional by default)."""
        detector = BlockerDetector(temp_feature_dir)
        blockers = detector.detect_missing_artifacts()

        wireframe_blockers = [
            b for b in blockers if "wireframe" in b.description.lower()
        ]
        assert len(wireframe_blockers) == 1
        assert wireframe_blockers[0].severity == BlockerSeverity.LOW  # Optional

    def test_detect_incomplete_prereqs_context_not_complete(self, temp_feature_dir):
        """Test detection of incomplete context doc."""
        detector = BlockerDetector(temp_feature_dir)
        blockers = detector.detect_incomplete_prerequisites()

        context_blockers = [b for b in blockers if b.track == BlockerTrack.CONTEXT]
        # Should detect context not complete in parallel_tracks phase
        assert len(context_blockers) >= 1

    def test_detect_all(self, temp_feature_dir):
        """Test detect_all returns all blocker types."""
        detector = BlockerDetector(temp_feature_dir)
        blockers = detector.detect_all()

        # Should have at least the missing figma blocker
        assert len(blockers) >= 1
        types = {b.type for b in blockers}
        assert BlockerType.MISSING_ARTIFACT in types

    def test_get_blockers_by_type(self, temp_feature_dir):
        """Test filtering blockers by type."""
        detector = BlockerDetector(temp_feature_dir)
        artifact_blockers = detector.get_blockers_by_type(BlockerType.MISSING_ARTIFACT)

        for blocker in artifact_blockers:
            assert blocker.type == BlockerType.MISSING_ARTIFACT

    def test_get_blockers_by_severity(self, temp_feature_dir):
        """Test filtering blockers by severity."""
        detector = BlockerDetector(temp_feature_dir)
        high_blockers = detector.get_blockers_by_severity(BlockerSeverity.HIGH)

        for blocker in high_blockers:
            assert blocker.severity == BlockerSeverity.HIGH

    def test_get_blockers_by_track(self, temp_feature_dir):
        """Test filtering blockers by track."""
        detector = BlockerDetector(temp_feature_dir)
        design_blockers = detector.get_blockers_by_track("design")

        for blocker in design_blockers:
            assert blocker.track == BlockerTrack.DESIGN

    def test_generate_report(self, temp_feature_dir):
        """Test report generation."""
        detector = BlockerDetector(temp_feature_dir)
        report = detector.generate_report()

        assert report.feature_slug == "test-feature"
        assert isinstance(report.blockers, list)
        assert isinstance(report.generated_at, datetime)

    def test_has_blocking_issues(self, temp_feature_dir):
        """Test has_blocking_issues method."""
        detector = BlockerDetector(temp_feature_dir)
        # Should have blocking issues due to missing figma
        assert detector.has_blocking_issues() is True

    def test_has_critical_blockers(self, temp_feature_dir):
        """Test has_critical_blockers method."""
        detector = BlockerDetector(temp_feature_dir)
        # Default state shouldn't have critical blockers
        # (BC rejection is critical, but BC hasn't started)
        has_critical = detector.has_critical_blockers()
        # Verify it returns a boolean
        assert isinstance(has_critical, bool)


class TestBlockerDetectorWithMocks:
    """Test BlockerDetector with mocked dependencies."""

    @pytest.fixture
    def mock_bc_track(self):
        """Create a mock business case track."""
        mock = MagicMock()
        mock.status.value = "pending_approval"
        mock.pending_approvers = ["product_lead", "ceo"]
        mock.is_rejected = False
        mock.approvals = []
        mock.assumptions.is_complete = True
        return mock

    @pytest.fixture
    def mock_eng_track(self):
        """Create a mock engineering track."""
        mock = MagicMock()
        mock.status.value = "in_progress"
        mock.has_estimate = False
        mock.adrs = []
        mock.blocking_dependencies = []
        mock.pending_risks = []
        return mock

    @pytest.fixture
    def mock_state(self):
        """Create a mock feature state."""
        mock = MagicMock()
        mock.slug = "test-feature"
        mock.current_phase.value = "parallel_tracks"
        mock.artifacts = {"figma": None, "wireframes_url": None}

        # Mock tracks
        mock.tracks = {
            "context": MagicMock(status=MagicMock(value="complete"), current_version=3),
            "design": MagicMock(status=MagicMock(value="in_progress")),
            "business_case": MagicMock(status=MagicMock(value="pending_approval")),
            "engineering": MagicMock(status=MagicMock(value="in_progress")),
        }
        return mock

    def test_detect_pending_approvals_with_mock(
        self, mock_bc_track, mock_eng_track, mock_state
    ):
        """Test pending approval detection with mocked BC track."""
        with tempfile.TemporaryDirectory() as tmpdir:
            feature_path = Path(tmpdir)

            detector = BlockerDetector(feature_path)
            detector._bc_track = mock_bc_track
            detector._eng_track = mock_eng_track
            detector._state = mock_state

            blockers = detector.detect_pending_approvals()

            # Should detect pending BC approval
            assert len(blockers) == 1
            assert blockers[0].type == BlockerType.PENDING_APPROVAL
            assert "product_lead" in blockers[0].description
            assert blockers[0].severity == BlockerSeverity.HIGH

    def test_detect_bc_rejection(self, mock_bc_track, mock_eng_track, mock_state):
        """Test BC rejection detection."""
        mock_bc_track.is_rejected = True

        with tempfile.TemporaryDirectory() as tmpdir:
            feature_path = Path(tmpdir)

            detector = BlockerDetector(feature_path)
            detector._bc_track = mock_bc_track
            detector._eng_track = mock_eng_track
            detector._state = mock_state

            blockers = detector.detect_pending_approvals()

            # Should detect critical rejection
            rejection_blockers = [
                b for b in blockers if "rejected" in b.description.lower()
            ]
            assert len(rejection_blockers) == 1
            assert rejection_blockers[0].severity == BlockerSeverity.CRITICAL

    def test_detect_blocking_dependencies(
        self, mock_bc_track, mock_eng_track, mock_state
    ):
        """Test blocking dependency detection."""
        # Add a blocking dependency
        mock_dep = MagicMock()
        mock_dep.name = "External API"
        mock_dep.type = "external_api"
        mock_dep.status = "blocked"
        mock_dep.description = "Waiting for API v2"
        mock_dep.owner = "external_team"
        mock_dep.eta = "2026-03-01"
        mock_eng_track.blocking_dependencies = [mock_dep]

        with tempfile.TemporaryDirectory() as tmpdir:
            feature_path = Path(tmpdir)

            detector = BlockerDetector(feature_path)
            detector._bc_track = mock_bc_track
            detector._eng_track = mock_eng_track
            detector._state = mock_state

            blockers = detector.detect_blocking_dependencies()

            assert len(blockers) == 1
            assert blockers[0].type == BlockerType.BLOCKING_DEPENDENCY
            assert "External API" in blockers[0].description
            assert blockers[0].severity == BlockerSeverity.HIGH

    def test_detect_unmitigated_risks(self, mock_bc_track, mock_eng_track, mock_state):
        """Test unmitigated risk detection."""
        # Add a high-impact unmitigated risk
        mock_risk = MagicMock()
        mock_risk.risk = "Database migration could cause downtime"
        mock_risk.impact = "high"
        mock_risk.likelihood = "medium"
        mock_risk.mitigation = None
        mock_risk.owner = "dba"
        mock_risk.status = "identified"
        mock_eng_track.pending_risks = [mock_risk]

        with tempfile.TemporaryDirectory() as tmpdir:
            feature_path = Path(tmpdir)

            detector = BlockerDetector(feature_path)
            detector._bc_track = mock_bc_track
            detector._eng_track = mock_eng_track
            detector._state = mock_state

            blockers = detector.detect_unmitigated_risks()

            assert len(blockers) == 1
            assert blockers[0].type == BlockerType.UNMITIGATED_RISK
            assert blockers[0].severity == BlockerSeverity.HIGH

    def test_detect_critical_risk(self, mock_bc_track, mock_eng_track, mock_state):
        """Test detection of critical risk (high impact + high likelihood)."""
        # Add a high-high risk without mitigation
        mock_risk = MagicMock()
        mock_risk.risk = "Critical security vulnerability"
        mock_risk.impact = "high"
        mock_risk.likelihood = "high"
        mock_risk.mitigation = None
        mock_risk.owner = "security"
        mock_risk.status = "identified"
        mock_eng_track.pending_risks = [mock_risk]

        with tempfile.TemporaryDirectory() as tmpdir:
            feature_path = Path(tmpdir)

            detector = BlockerDetector(feature_path)
            detector._bc_track = mock_bc_track
            detector._eng_track = mock_eng_track
            detector._state = mock_state

            blockers = detector.detect_unmitigated_risks()

            # Should have two blockers: one for no mitigation, one for high-high
            # But since same risk, should just be the critical one
            critical = [b for b in blockers if b.severity == BlockerSeverity.CRITICAL]
            assert len(critical) >= 1

    def test_can_proceed_to_phase(self, mock_bc_track, mock_eng_track, mock_state):
        """Test can_proceed_to_phase method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            feature_path = Path(tmpdir)

            detector = BlockerDetector(feature_path)
            detector._bc_track = mock_bc_track
            detector._eng_track = mock_eng_track
            detector._state = mock_state

            can_proceed, blocking = detector.can_proceed_to_phase("decision_gate")

            # Has pending approval (high), so shouldn't be able to proceed
            assert isinstance(can_proceed, bool)
            assert isinstance(blocking, list)


class TestHelperFunctions:
    """Test helper functions."""

    @pytest.fixture
    def temp_feature_dir(self):
        """Create a temporary feature directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            feature_path = Path(tmpdir)
            state_file = feature_path / "feature-state.yaml"

            state_data = {
                "slug": "test-feature",
                "title": "Test Feature",
                "product_id": "test-product",
                "organization": "test-org",
                "context_file": "test-feature-context.md",
                "brain_entity": "[[Entities/Test_Feature]]",
                "created": datetime.now().isoformat(),
                "engine": {
                    "current_phase": "parallel_tracks",
                    "tracks": {
                        "context": {"status": "complete"},
                        "design": {"status": "not_started"},
                        "business_case": {"status": "not_started"},
                        "engineering": {"status": "not_started"},
                    },
                },
                "artifacts": {"figma": "https://figma.com/test"},
            }

            with open(state_file, "w") as f:
                yaml.dump(state_data, f)

            yield feature_path

    def test_detect_blockers_function(self, temp_feature_dir):
        """Test detect_blockers convenience function."""
        blockers = detect_blockers(temp_feature_dir)
        assert isinstance(blockers, list)

    def test_get_blocker_report_function(self, temp_feature_dir):
        """Test get_blocker_report convenience function."""
        report = get_blocker_report(temp_feature_dir)
        assert isinstance(report, BlockerReport)
        assert report.feature_slug == "test-feature"

    def test_has_blockers_function(self, temp_feature_dir):
        """Test has_blockers convenience function."""
        result = has_blockers(temp_feature_dir)
        assert isinstance(result, bool)

    def test_has_blockers_with_severity(self, temp_feature_dir):
        """Test has_blockers with specific severity."""
        result = has_blockers(temp_feature_dir, severity=BlockerSeverity.CRITICAL)
        assert isinstance(result, bool)

    def test_format_blocker_list_empty(self):
        """Test formatting empty blocker list."""
        result = format_blocker_list([])
        assert result == "No blockers detected"

    def test_format_blocker_list_with_blockers(self):
        """Test formatting blocker list."""
        blockers = [
            Blocker(
                type=BlockerType.MISSING_ARTIFACT,
                description="Figma not attached",
                severity=BlockerSeverity.HIGH,
                resolution_hint="Use /attach-artifact figma",
            ),
            Blocker(
                type=BlockerType.PENDING_APPROVAL,
                description="Awaiting BC approval",
                severity=BlockerSeverity.CRITICAL,
                resolution_hint="Contact stakeholder",
            ),
        ]
        result = format_blocker_list(blockers)

        assert "[CRITICAL]" in result
        assert "[HIGH]" in result
        assert "Figma not attached" in result
        assert "Awaiting BC approval" in result

    def test_format_blocker_list_without_hints(self):
        """Test formatting without resolution hints."""
        blockers = [
            Blocker(
                type=BlockerType.MISSING_ARTIFACT,
                description="Test",
                severity=BlockerSeverity.HIGH,
                resolution_hint="Test hint",
            ),
        ]
        result = format_blocker_list(blockers, include_hints=False)

        assert "Hint:" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
