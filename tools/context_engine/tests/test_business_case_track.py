"""
Tests for Business Case Track

Tests the BusinessCaseTrack module and FeatureEngine BC methods:
- BCStatus lifecycle (not_started -> in_progress -> pending_approval -> approved/rejected)
- Stakeholder approval management
- BC document generation
- Integration with feature-state.yaml
"""

import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import yaml

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from context_engine.tracks.business_case import (
    BCAssumptions,
    BCStatus,
    BCTrackResult,
    BusinessCaseTrack,
    StakeholderApproval,
)


@pytest.fixture
def temp_feature_path():
    """Create a temporary feature folder structure."""
    temp_dir = tempfile.mkdtemp()
    feature_path = Path(temp_dir) / "test-feature"
    feature_path.mkdir(parents=True)

    # Create minimal feature-state.yaml
    state_file = feature_path / "feature-state.yaml"
    state_data = {
        "slug": "test-feature",
        "title": "Test Feature",
        "product_id": "test-product",
        "organization": "test-org",
        "context_file": "test-feature-context.md",
        "brain_entity": "[[Entities/Test_Feature]]",
        "created": datetime.now().isoformat(),
        "created_by": "test-user",
        "engine": {
            "current_phase": "parallel_tracks",
            "tracks": {
                "context": {"status": "complete"},
                "design": {"status": "not_started"},
                "business_case": {"status": "not_started"},
                "engineering": {"status": "not_started"},
            },
        },
        "artifacts": {},
        "decisions": [],
    }
    with open(state_file, "w") as f:
        yaml.dump(state_data, f)

    yield feature_path

    # Cleanup
    shutil.rmtree(temp_dir)


class TestBCStatus:
    """Test BCStatus enum."""

    def test_status_values(self):
        """Test that all expected status values exist."""
        assert BCStatus.NOT_STARTED.value == "not_started"
        assert BCStatus.IN_PROGRESS.value == "in_progress"
        assert BCStatus.PENDING_APPROVAL.value == "pending_approval"
        assert BCStatus.APPROVED.value == "approved"
        assert BCStatus.REJECTED.value == "rejected"


class TestStakeholderApproval:
    """Test StakeholderApproval dataclass."""

    def test_create_approval(self):
        """Test creating an approval record."""
        approval = StakeholderApproval(
            approver="Jack Approver",
            approved=True,
            date=datetime.now(),
            approval_type="verbal",
            reference="Slack #meal-kit",
            notes="Approved with conditions",
        )

        assert approval.approver == "Jack Approver"
        assert approval.approved is True
        assert approval.approval_type == "verbal"

    def test_to_dict(self):
        """Test serialization to dict."""
        now = datetime.now()
        approval = StakeholderApproval(
            approver="Test User",
            approved=True,
            date=now,
            approval_type="email",
            reference="https://link.to/email",
        )

        d = approval.to_dict()
        assert d["approver"] == "Test User"
        assert d["approved"] is True
        assert d["approval_type"] == "email"
        assert d["reference"] == "https://link.to/email"

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "approver": "Test User",
            "approved": False,
            "date": "2026-02-04T10:30:00",
            "approval_type": "slack",
            "notes": "Needs more data",
        }

        approval = StakeholderApproval.from_dict(data)
        assert approval.approver == "Test User"
        assert approval.approved is False
        assert approval.approval_type == "slack"
        assert approval.notes == "Needs more data"


class TestBCAssumptions:
    """Test BCAssumptions dataclass."""

    def test_empty_assumptions(self):
        """Test default assumptions are incomplete."""
        assumptions = BCAssumptions()
        assert not assumptions.is_complete
        assert assumptions.baseline_metrics == {}
        assert assumptions.impact_assumptions == {}

    def test_complete_assumptions(self):
        """Test assumptions are complete when both metrics provided."""
        assumptions = BCAssumptions(
            baseline_metrics={"conversion": 0.65},
            impact_assumptions={"improvement": 0.10},
        )
        assert assumptions.is_complete

    def test_to_dict(self):
        """Test serialization."""
        assumptions = BCAssumptions(
            baseline_metrics={"metric1": 100},
            impact_assumptions={"delta": 10},
            investment_estimate="M",
            roi_analysis={"roi": 1.5},
        )

        d = assumptions.to_dict()
        assert d["baseline_metrics"] == {"metric1": 100}
        assert d["impact_assumptions"] == {"delta": 10}
        assert d["investment_estimate"] == "M"
        assert d["roi_analysis"] == {"roi": 1.5}


class TestBusinessCaseTrack:
    """Test BusinessCaseTrack class."""

    def test_init_creates_folder(self, temp_feature_path):
        """Test that initializing track doesn't create folder until start."""
        track = BusinessCaseTrack(temp_feature_path)
        assert track.status == BCStatus.NOT_STARTED
        assert track.current_version is None

    def test_start_track(self, temp_feature_path):
        """Test starting the BC track."""
        track = BusinessCaseTrack(temp_feature_path)
        result = track.start(initiated_by="test-user")

        assert result.success
        assert result.status == BCStatus.IN_PROGRESS
        assert track.status == BCStatus.IN_PROGRESS
        assert track.current_version == 1
        assert (temp_feature_path / "business-case").exists()

    def test_cannot_start_twice(self, temp_feature_path):
        """Test that starting twice fails."""
        track = BusinessCaseTrack(temp_feature_path)
        track.start(initiated_by="test-user")
        result = track.start(initiated_by="test-user")

        assert not result.success
        assert "already started" in result.message.lower()

    def test_update_assumptions(self, temp_feature_path):
        """Test updating assumptions."""
        track = BusinessCaseTrack(temp_feature_path)
        track.start(initiated_by="test-user")

        result = track.update_assumptions(
            baseline_metrics={"conversion_rate": 0.65},
            impact_assumptions={"improvement": 0.10},
        )

        assert result.success
        assert track.assumptions.baseline_metrics["conversion_rate"] == 0.65
        assert track.assumptions.impact_assumptions["improvement"] == 0.10
        assert track.assumptions.is_complete

    def test_set_required_approvers(self, temp_feature_path):
        """Test setting required approvers."""
        track = BusinessCaseTrack(temp_feature_path)
        track.start(initiated_by="test-user")
        track.set_required_approvers(["Jack Approver", "Other PM"])

        assert "Jack Approver" in track._required_approvers
        assert "Other PM" in track._required_approvers

    def test_generate_document(self, temp_feature_path):
        """Test generating BC document."""
        track = BusinessCaseTrack(temp_feature_path)
        track.start(initiated_by="test-user")
        track.update_assumptions(
            baseline_metrics={"metric": 100}, impact_assumptions={"delta": 10}
        )

        result = track.generate_document(version=1)

        assert result.success
        assert result.file_path.exists()
        assert "bc-v1.md" in str(result.file_path)

        content = result.file_path.read_text()
        assert "Business Case v1" in content
        assert "metric" in content

    def test_submit_for_approval(self, temp_feature_path):
        """Test submitting for approval."""
        track = BusinessCaseTrack(temp_feature_path)
        track.start(initiated_by="test-user")
        track.update_assumptions(
            baseline_metrics={"metric": 100}, impact_assumptions={"delta": 10}
        )

        result = track.submit_for_approval(approver="Jack Approver")

        assert result.success
        assert result.status == BCStatus.PENDING_APPROVAL
        assert track.status == BCStatus.PENDING_APPROVAL
        assert "Jack Approver" in track._required_approvers

    def test_record_approval_approved(self, temp_feature_path):
        """Test recording an approval."""
        track = BusinessCaseTrack(temp_feature_path)
        track.start(initiated_by="test-user")
        track.update_assumptions(
            baseline_metrics={"metric": 100}, impact_assumptions={"delta": 10}
        )
        track.submit_for_approval(approver="Jack Approver")

        result = track.record_approval(
            approver="Jack Approver",
            approved=True,
            approval_type="verbal",
            reference="Slack thread",
        )

        assert result.success
        assert track.status == BCStatus.APPROVED
        assert track.is_approved
        assert len(track.approvals) == 1
        assert track.approvals[0].approver == "Jack Approver"

    def test_record_approval_rejected(self, temp_feature_path):
        """Test recording a rejection."""
        track = BusinessCaseTrack(temp_feature_path)
        track.start(initiated_by="test-user")
        track.update_assumptions(
            baseline_metrics={"metric": 100}, impact_assumptions={"delta": 10}
        )
        track.submit_for_approval(approver="Jack Approver")

        result = track.record_approval(
            approver="Jack Approver", approved=False, notes="Need more data"
        )

        assert result.success
        assert track.status == BCStatus.REJECTED
        assert track.is_rejected
        assert not track.is_approved

    def test_pending_approvers(self, temp_feature_path):
        """Test pending approvers list."""
        track = BusinessCaseTrack(temp_feature_path)
        track.start(initiated_by="test-user")
        track.set_required_approvers(["Approver1", "Approver2"])
        track.update_assumptions(baseline_metrics={"m": 1}, impact_assumptions={"i": 1})
        track.submit_for_approval(approver="Approver1")

        # Before any approval
        assert "Approver1" in track.pending_approvers
        assert "Approver2" in track.pending_approvers

        # After one approval
        track.record_approval(approver="Approver1", approved=True)
        assert "Approver1" not in track.pending_approvers
        assert "Approver2" in track.pending_approvers

    def test_state_persistence(self, temp_feature_path):
        """Test that state persists to feature-state.yaml."""
        # Create and modify track
        track = BusinessCaseTrack(temp_feature_path)
        track.start(initiated_by="test-user")
        track.update_assumptions(
            baseline_metrics={"metric": 100}, impact_assumptions={"delta": 10}
        )
        track.submit_for_approval(approver="Test Approver")

        # Load new instance and check state was preserved
        track2 = BusinessCaseTrack(temp_feature_path)
        assert track2.status == BCStatus.PENDING_APPROVAL
        assert track2.assumptions.baseline_metrics["metric"] == 100
        assert "Test Approver" in track2._required_approvers

    def test_to_dict(self, temp_feature_path):
        """Test serialization to dict."""
        track = BusinessCaseTrack(temp_feature_path)
        track.start(initiated_by="test-user")
        track.update_assumptions(baseline_metrics={"m": 1}, impact_assumptions={"i": 1})

        d = track.to_dict()
        assert d["status"] == "in_progress"
        assert d["current_version"] == 1  # Fixed: key is current_version not version
        assert d["assumptions"]["baseline_metrics"]["m"] == 1


class TestApprovalWorkflow:
    """Test complete approval workflow scenarios."""

    def test_happy_path_single_approver(self, temp_feature_path):
        """Test happy path with single approver."""
        track = BusinessCaseTrack(temp_feature_path)

        # Start track
        result = track.start(initiated_by="pm-user")
        assert result.success
        assert track.status == BCStatus.IN_PROGRESS

        # Add assumptions
        track.update_assumptions(
            baseline_metrics={"conversion": 0.65, "abandonment": 0.35},
            impact_assumptions={"conversion_improvement": 0.10},
        )
        assert track.assumptions.is_complete

        # Generate document
        track.generate_document(version=1)
        assert (track.bc_folder / "bc-v1.md").exists()

        # Submit for approval
        result = track.submit_for_approval(approver="Jack Approver")
        assert result.success
        assert track.status == BCStatus.PENDING_APPROVAL

        # Record approval
        result = track.record_approval(
            approver="Jack Approver",
            approved=True,
            approval_type="verbal",
            reference="Meeting notes 2026-02-04",
        )
        assert result.success
        assert track.status == BCStatus.APPROVED
        assert track.is_approved

        # Check file was renamed
        assert (track.bc_folder / "bc-v1-approved.md").exists()

    def test_rejection_workflow(self, temp_feature_path):
        """Test rejection workflow."""
        track = BusinessCaseTrack(temp_feature_path)
        track.start(initiated_by="pm-user")
        track.update_assumptions(baseline_metrics={"m": 1}, impact_assumptions={"i": 1})
        # Generate document before submitting (needed for file rename)
        track.generate_document(version=1)
        track.submit_for_approval(approver="Stakeholder")

        result = track.record_approval(
            approver="Stakeholder", approved=False, notes="ROI not strong enough"
        )

        assert result.success
        assert track.status == BCStatus.REJECTED
        assert track.is_rejected
        assert not track.is_approved

        # Check file was renamed
        assert (track.bc_folder / "bc-v1-rejected.md").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
