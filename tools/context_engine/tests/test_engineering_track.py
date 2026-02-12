"""
Tests for the Engineering Track module.

Tests cover:
- EngineeringTrack lifecycle (start, complete)
- ADR creation and management
- Technical decision recording
- Engineering estimates
- Risks and dependencies
- FeatureEngine integration methods
"""

import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
import yaml
from context_engine.tracks.engineering import (
    ADR,
    ADRStatus,
    Dependency,
    EngineeringEstimate,
    EngineeringStatus,
    EngineeringTrack,
    EngineeringTrackResult,
    EstimateSize,
    TechnicalDecision,
    TechnicalRisk,
)


class TestEngineeringStatus:
    """Tests for EngineeringStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert EngineeringStatus.NOT_STARTED.value == "not_started"
        assert EngineeringStatus.IN_PROGRESS.value == "in_progress"
        assert EngineeringStatus.ESTIMATION_PENDING.value == "estimation_pending"
        assert EngineeringStatus.COMPLETE.value == "complete"
        assert EngineeringStatus.BLOCKED.value == "blocked"


class TestADRStatus:
    """Tests for ADRStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert ADRStatus.PROPOSED.value == "proposed"
        assert ADRStatus.ACCEPTED.value == "accepted"
        assert ADRStatus.DEPRECATED.value == "deprecated"
        assert ADRStatus.SUPERSEDED.value == "superseded"


class TestEstimateSize:
    """Tests for EstimateSize enum."""

    def test_from_string_valid(self):
        """Test valid estimate sizes."""
        assert EstimateSize.from_string("S") == EstimateSize.S
        assert EstimateSize.from_string("m") == EstimateSize.M
        assert EstimateSize.from_string("L") == EstimateSize.L
        assert EstimateSize.from_string("xl") == EstimateSize.XL

    def test_from_string_invalid(self):
        """Test invalid estimate sizes raise ValueError."""
        with pytest.raises(ValueError):
            EstimateSize.from_string("XXL")
        with pytest.raises(ValueError):
            EstimateSize.from_string("invalid")


class TestTechnicalDecision:
    """Tests for TechnicalDecision dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        decision = TechnicalDecision(
            decision="Use TypeScript",
            rationale="Type safety",
            decided_by="nikita",
            date=datetime(2026, 2, 4, 10, 0, 0),
            category="tooling",
            related_adr="ADR-001",
        )
        result = decision.to_dict()
        assert result["decision"] == "Use TypeScript"
        assert result["rationale"] == "Type safety"
        assert result["decided_by"] == "nikita"
        assert result["category"] == "tooling"
        assert result["related_adr"] == "ADR-001"

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "decision": "Use React",
            "rationale": "Team expertise",
            "decided_by": "john",
            "date": "2026-02-04T10:00:00",
            "category": "architecture",
        }
        decision = TechnicalDecision.from_dict(data)
        assert decision.decision == "Use React"
        assert decision.rationale == "Team expertise"
        assert decision.category == "architecture"


class TestADR:
    """Tests for ADR dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        adr = ADR(
            number=1,
            title="Use Redis for Sessions",
            status=ADRStatus.PROPOSED,
            context="Need distributed sessions",
            decision="Use Redis",
            consequences="Adds dependency",
            created=datetime(2026, 2, 4, 10, 0, 0),
            created_by="nikita",
        )
        result = adr.to_dict()
        assert result["number"] == 1
        assert result["title"] == "Use Redis for Sessions"
        assert result["status"] == "proposed"
        assert result["context"] == "Need distributed sessions"

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "number": 2,
            "title": "Use PostgreSQL",
            "status": "accepted",
            "context": "Need relational DB",
            "decision": "Use PostgreSQL",
            "consequences": "Well supported",
            "created": "2026-02-04T10:00:00",
            "created_by": "john",
        }
        adr = ADR.from_dict(data)
        assert adr.number == 2
        assert adr.status == ADRStatus.ACCEPTED
        assert adr.created_by == "john"

    def test_to_markdown(self):
        """Test markdown generation."""
        adr = ADR(
            number=1,
            title="Use Redis for Sessions",
            status=ADRStatus.PROPOSED,
            context="Need distributed sessions",
            decision="Use Redis",
            consequences="Adds dependency",
            created=datetime(2026, 2, 4, 10, 0, 0),
            created_by="nikita",
        )
        md = adr.to_markdown()
        assert "# ADR-001: Use Redis for Sessions" in md
        assert "**Status**: proposed" in md
        assert "Need distributed sessions" in md
        assert "Use Redis" in md


class TestEngineeringTrack:
    """Tests for EngineeringTrack class."""

    @pytest.fixture
    def temp_feature(self):
        """Create a temporary feature folder for testing."""
        temp_dir = tempfile.mkdtemp()
        feature_path = Path(temp_dir) / "test-feature"
        feature_path.mkdir(parents=True)

        # Create minimal feature-state.yaml
        state_file = feature_path / "feature-state.yaml"
        state_data = {
            "slug": "test-feature",
            "title": "Test Feature",
            "product_id": "test-product",
            "engine": {"tracks": {}},
        }
        with open(state_file, "w") as f:
            yaml.dump(state_data, f)

        yield feature_path

        # Cleanup
        shutil.rmtree(temp_dir)

    def test_init_creates_track(self, temp_feature):
        """Test track initialization."""
        track = EngineeringTrack(temp_feature)
        assert track.status == EngineeringStatus.NOT_STARTED
        assert track.adrs == []
        assert track.decisions == []
        assert track.estimate is None

    def test_start_track(self, temp_feature):
        """Test starting the engineering track."""
        track = EngineeringTrack(temp_feature)
        result = track.start(initiated_by="nikita")

        assert result.success
        assert result.status == EngineeringStatus.IN_PROGRESS
        assert track.status == EngineeringStatus.IN_PROGRESS
        assert track._started_by == "nikita"

        # Verify folders created
        assert (temp_feature / "engineering").exists()
        assert (temp_feature / "engineering" / "adrs").exists()

    def test_start_already_started(self, temp_feature):
        """Test starting an already started track fails."""
        track = EngineeringTrack(temp_feature)
        track.start(initiated_by="nikita")
        result = track.start(initiated_by="john")

        assert not result.success
        assert "already started" in result.message

    def test_create_adr(self, temp_feature):
        """Test ADR creation."""
        track = EngineeringTrack(temp_feature)
        track.start(initiated_by="nikita")

        result = track.create_adr(
            title="Use Redis for Sessions",
            context="Need distributed sessions",
            decision="Use Redis cluster",
            consequences="Adds infrastructure dependency",
        )

        assert result.success
        assert result.adr_number == 1
        assert len(track.adrs) == 1
        assert track.adrs[0].title == "Use Redis for Sessions"
        assert result.file_path.exists()

    def test_create_adr_before_start(self, temp_feature):
        """Test ADR creation fails before track start."""
        track = EngineeringTrack(temp_feature)
        result = track.create_adr(
            title="Test", context="Test", decision="Test", consequences="Test"
        )
        assert not result.success
        assert "not started" in result.message

    def test_create_adr_supersedes(self, temp_feature):
        """Test ADR superseding another ADR."""
        track = EngineeringTrack(temp_feature)
        track.start(initiated_by="nikita")

        # Create first ADR
        track.create_adr(
            title="Use MySQL",
            context="Need database",
            decision="Use MySQL",
            consequences="Easy setup",
        )

        # Create superseding ADR
        result = track.create_adr(
            title="Use PostgreSQL",
            context="Need better JSON support",
            decision="Switch to PostgreSQL",
            consequences="Better features",
            supersedes=1,
        )

        assert result.success
        assert result.adr_number == 2
        assert track.adrs[0].status == ADRStatus.SUPERSEDED
        assert track.adrs[0].superseded_by == 2
        assert track.adrs[1].supersedes == 1

    def test_record_estimate(self, temp_feature):
        """Test recording an estimate."""
        track = EngineeringTrack(temp_feature)
        track.start(initiated_by="nikita")

        result = track.record_estimate(
            estimate="M",
            breakdown={"frontend": "S", "backend": "M"},
            confidence="high",
            assumptions=["Design finalized"],
        )

        assert result.success
        assert track.estimate is not None
        assert track.estimate.overall == "M"
        assert track.estimate.breakdown == {"frontend": "S", "backend": "M"}
        assert track.has_estimate

    def test_record_estimate_invalid_size(self, temp_feature):
        """Test recording invalid estimate size fails."""
        track = EngineeringTrack(temp_feature)
        track.start(initiated_by="nikita")

        result = track.record_estimate(estimate="XXL")
        assert not result.success
        assert "Invalid estimate" in result.message

    def test_record_technical_decision(self, temp_feature):
        """Test recording a technical decision."""
        track = EngineeringTrack(temp_feature)
        track.start(initiated_by="nikita")

        result = track.record_technical_decision(
            decision="Use TypeScript",
            rationale="Type safety",
            decided_by="nikita",
            category="tooling",
        )

        assert result.success
        assert len(track.decisions) == 1
        assert track.decisions[0].decision == "Use TypeScript"

    def test_add_risk(self, temp_feature):
        """Test adding a technical risk."""
        track = EngineeringTrack(temp_feature)
        track.start(initiated_by="nikita")

        result = track.add_risk(
            risk="Redis may have downtime",
            impact="high",
            likelihood="low",
            mitigation="Implement fallback",
        )

        assert result.success
        assert len(track.risks) == 1
        assert track.risks[0].risk == "Redis may have downtime"

    def test_add_dependency(self, temp_feature):
        """Test adding a dependency."""
        track = EngineeringTrack(temp_feature)
        track.start(initiated_by="nikita")

        result = track.add_dependency(
            name="Payment API v2",
            type="external_api",
            description="New payment handling",
            eta="2026-03-01",
        )

        assert result.success
        assert len(track.dependencies) == 1
        assert track.dependencies[0].name == "Payment API v2"

    def test_complete_track(self, temp_feature):
        """Test completing the engineering track."""
        track = EngineeringTrack(temp_feature)
        track.start(initiated_by="nikita")

        # Add required elements
        track.create_adr(
            title="Test ADR", context="Test", decision="Test", consequences="Test"
        )
        track.record_estimate(estimate="M")

        result = track.complete()

        assert result.success
        assert track.status == EngineeringStatus.COMPLETE

    def test_complete_track_without_estimate(self, temp_feature):
        """Test completing without estimate fails."""
        track = EngineeringTrack(temp_feature)
        track.start(initiated_by="nikita")
        track.create_adr(
            title="Test ADR", context="Test", decision="Test", consequences="Test"
        )

        result = track.complete()
        assert not result.success
        assert "No estimate" in result.message

    def test_complete_track_without_decisions(self, temp_feature):
        """Test completing without ADRs or decisions fails."""
        track = EngineeringTrack(temp_feature)
        track.start(initiated_by="nikita")
        track.record_estimate(estimate="M")

        result = track.complete()
        assert not result.success
        assert "No ADRs" in result.message

    def test_state_persistence(self, temp_feature):
        """Test state is persisted to feature-state.yaml."""
        track = EngineeringTrack(temp_feature)
        track.start(initiated_by="nikita")
        track.create_adr(
            title="Test ADR",
            context="Test context",
            decision="Test decision",
            consequences="Test consequences",
        )
        track.record_estimate(estimate="L")

        # Load state file
        state_file = temp_feature / "feature-state.yaml"
        with open(state_file, "r") as f:
            data = yaml.safe_load(f)

        eng_data = data["engine"]["tracks"]["engineering"]
        assert eng_data["status"] == "in_progress"
        assert len(eng_data["adrs"]) == 1
        assert eng_data["estimate"]["overall"] == "L"

    def test_state_loading(self, temp_feature):
        """Test state is loaded from feature-state.yaml."""
        # Create track and add data
        track1 = EngineeringTrack(temp_feature)
        track1.start(initiated_by="nikita")
        track1.create_adr(
            title="Test ADR", context="Test", decision="Test", consequences="Test"
        )

        # Create new track instance - should load existing state
        track2 = EngineeringTrack(temp_feature)
        assert track2.status == EngineeringStatus.IN_PROGRESS
        assert len(track2.adrs) == 1
        assert track2.adrs[0].title == "Test ADR"

    def test_active_adrs_property(self, temp_feature):
        """Test active_adrs property filters correctly."""
        track = EngineeringTrack(temp_feature)
        track.start(initiated_by="nikita")

        # Create multiple ADRs
        track.create_adr(
            title="ADR 1",
            context="Test",
            decision="Test",
            consequences="Test",
            status=ADRStatus.ACCEPTED,
        )
        track.create_adr(
            title="ADR 2",
            context="Test",
            decision="Test",
            consequences="Test",
            supersedes=1,  # This will mark ADR 1 as superseded
        )

        assert len(track.adrs) == 2
        assert len(track.active_adrs) == 1  # Only ADR 2 is active
        assert track.active_adrs[0].number == 2

    def test_to_dict(self, temp_feature):
        """Test to_dict method."""
        track = EngineeringTrack(temp_feature)
        track.start(initiated_by="nikita")
        track.create_adr(
            title="Test", context="Test", decision="Test", consequences="Test"
        )
        track.record_estimate(estimate="M")
        track.add_risk(risk="Test risk")
        track.add_dependency(name="Test dep")

        result = track.to_dict()

        assert result["status"] == "in_progress"
        assert result["adrs_count"] == 1
        assert result["has_estimate"] == True
        assert len(result["risks"]) == 1
        assert len(result["dependencies"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
