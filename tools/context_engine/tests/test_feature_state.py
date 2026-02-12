"""
Unit tests for FeatureState save/load roundtrip and template generation.

Tests cover:
- create_initial_state() template generator
- save/load roundtrip preserves all fields
- YAML format matches PRD C.4 specification
- Edge cases (missing optional fields, datetime handling)

Run tests:
    pytest common/tools/context_engine/tests/test_feature_state.py -v
"""

import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

# Add context_engine to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from feature_state import (
    AliasInfo,
    Decision,
    FeaturePhase,
    FeatureState,
    PhaseEntry,
    TrackState,
    TrackStatus,
    generate_brain_entity_name,
    generate_slug,
)


class TestGenerateSlug:
    """Tests for slug generation."""

    def test_basic_slug(self):
        """Basic slug generation from title and product."""
        slug = generate_slug("OTP Checkout Recovery", "meal-kit")
        assert slug == "goo-otp-checkout-recovery"

    def test_slug_with_special_chars(self):
        """Slug removes special characters."""
        slug = generate_slug("User's Dashboard! Redesign", "meal-kit")
        assert "-" not in slug or slug.count("-") == slug.count("-")
        assert "'" not in slug
        assert "!" not in slug

    def test_slug_preserves_numbers(self):
        """Slug preserves numbers."""
        slug = generate_slug("Feature v2.0", "meal-kit")
        assert "v20" in slug or "2" in slug

    def test_slug_lowercase(self):
        """Slug is lowercase."""
        slug = generate_slug("UPPERCASE TITLE", "meal-kit")
        assert slug == slug.lower()


class TestGenerateBrainEntityName:
    """Tests for brain entity name generation."""

    def test_basic_entity_name(self):
        """Basic entity name from title."""
        name = generate_brain_entity_name("OTP Checkout Recovery")
        assert name == "Otp_Checkout_Recovery"

    def test_entity_name_capitalizes_words(self):
        """Entity name capitalizes each word."""
        name = generate_brain_entity_name("user dashboard redesign")
        assert name == "User_Dashboard_Redesign"


class TestAliasInfo:
    """Tests for AliasInfo dataclass."""

    def test_create_alias_info(self):
        """Create basic AliasInfo."""
        alias = AliasInfo(primary_name="OTP Recovery")
        assert alias.primary_name == "OTP Recovery"
        assert alias.known_aliases == []
        assert alias.auto_detected is False

    def test_add_alias(self):
        """Add aliases to AliasInfo."""
        alias = AliasInfo(primary_name="OTP Recovery")
        assert alias.add_alias("OTP Checkout Recovery") is True
        assert "OTP Checkout Recovery" in alias.known_aliases

    def test_add_duplicate_alias(self):
        """Adding duplicate alias returns False."""
        alias = AliasInfo(primary_name="OTP Recovery")
        alias.add_alias("OTP Checkout Recovery")
        assert alias.add_alias("OTP Checkout Recovery") is False

    def test_add_primary_as_alias(self):
        """Adding primary name as alias returns False."""
        alias = AliasInfo(primary_name="OTP Recovery")
        assert alias.add_alias("OTP Recovery") is False

    def test_to_dict(self):
        """AliasInfo serializes to dict correctly."""
        alias = AliasInfo(
            primary_name="OTP Recovery",
            known_aliases=["OTP Checkout Recovery"],
            auto_detected=True,
        )
        d = alias.to_dict()
        assert d["primary_name"] == "OTP Recovery"
        assert d["known_aliases"] == ["OTP Checkout Recovery"]
        assert d["auto_detected"] is True

    def test_from_dict(self):
        """AliasInfo deserializes from dict correctly."""
        data = {
            "primary_name": "OTP Recovery",
            "known_aliases": ["OTP Checkout Recovery"],
            "auto_detected": True,
        }
        alias = AliasInfo.from_dict(data)
        assert alias.primary_name == "OTP Recovery"
        assert alias.known_aliases == ["OTP Checkout Recovery"]
        assert alias.auto_detected is True


class TestTrackState:
    """Tests for TrackState dataclass."""

    def test_default_track_state(self):
        """Default track state is NOT_STARTED."""
        track = TrackState()
        assert track.status == TrackStatus.NOT_STARTED
        assert track.current_version is None
        assert track.current_step is None

    def test_track_state_to_dict(self):
        """TrackState serializes correctly."""
        track = TrackState(
            status=TrackStatus.IN_PROGRESS,
            current_version=2,
            current_step="wireframes",
            file="context-docs/v2-revised.md",
        )
        d = track.to_dict()
        assert d["status"] == "in_progress"
        assert d["current_version"] == 2
        assert d["current_step"] == "wireframes"
        assert d["file"] == "context-docs/v2-revised.md"

    def test_track_state_from_dict(self):
        """TrackState deserializes correctly."""
        data = {
            "status": "complete",
            "current_version": 3,
            "file": "context-docs/v3-final.md",
        }
        track = TrackState.from_dict(data)
        assert track.status == TrackStatus.COMPLETE
        assert track.current_version == 3
        assert track.file == "context-docs/v3-final.md"


class TestPhaseEntry:
    """Tests for PhaseEntry dataclass."""

    def test_phase_entry_to_dict(self):
        """PhaseEntry serializes correctly."""
        now = datetime.now()
        entry = PhaseEntry(
            phase="signal_analysis", entered=now, metadata={"insights_reviewed": 5}
        )
        d = entry.to_dict()
        assert d["phase"] == "signal_analysis"
        assert d["entered"] == now.isoformat()
        assert d["insights_reviewed"] == 5

    def test_phase_entry_with_completed(self):
        """PhaseEntry with completed timestamp."""
        entered = datetime(2026, 2, 2, 10, 30, 0)
        completed = datetime(2026, 2, 2, 11, 45, 0)
        entry = PhaseEntry(
            phase="signal_analysis", entered=entered, completed=completed
        )
        d = entry.to_dict()
        assert d["completed"] == completed.isoformat()

    def test_phase_entry_from_dict(self):
        """PhaseEntry deserializes correctly."""
        data = {
            "phase": "context_doc",
            "entered": "2026-02-02T11:45:00",
            "completed": "2026-02-02T14:30:00",
            "versions": 3,
        }
        entry = PhaseEntry.from_dict(data)
        assert entry.phase == "context_doc"
        assert entry.completed is not None
        assert entry.metadata["versions"] == 3


class TestDecision:
    """Tests for Decision dataclass."""

    def test_decision_to_dict(self):
        """Decision serializes correctly."""
        now = datetime.now()
        decision = Decision(
            date=now,
            phase="context_doc",
            decision="Proceed with 'remember device' approach",
            rationale="Best balance of UX and security",
            decided_by="jane.smith",
        )
        d = decision.to_dict()
        assert d["phase"] == "context_doc"
        assert d["decision"] == "Proceed with 'remember device' approach"
        assert d["decided_by"] == "jane.smith"

    def test_decision_from_dict(self):
        """Decision deserializes correctly."""
        data = {
            "date": "2026-02-02T12:00:00",
            "phase": "context_doc",
            "decision": "Proceed with approach A",
            "rationale": "Better UX",
            "decided_by": "jane.smith",
        }
        decision = Decision.from_dict(data)
        assert decision.phase == "context_doc"
        assert decision.decision == "Proceed with approach A"


class TestFeatureStateCreateInitial:
    """Tests for FeatureState.create_initial_state() template generator."""

    def test_create_initial_state_basic(self):
        """Create initial state with required fields."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )

        assert state.title == "OTP Checkout Recovery"
        assert state.product_id == "meal-kit"
        assert state.organization == "growth-division"
        assert state.created_by == "jane.smith"

    def test_create_initial_state_generates_slug(self):
        """Initial state generates correct slug."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )

        assert state.slug == "goo-otp-checkout-recovery"

    def test_create_initial_state_generates_brain_entity(self):
        """Initial state generates brain entity reference."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )

        assert state.brain_entity == "[[Entities/Otp_Checkout_Recovery]]"

    def test_create_initial_state_generates_context_file(self):
        """Initial state generates context file name."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )

        assert state.context_file == "goo-otp-checkout-recovery-context.md"

    def test_create_initial_state_with_master_sheet_row(self):
        """Initial state includes master_sheet_row."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
            master_sheet_row=15,
        )

        assert state.master_sheet_row == 15

    def test_create_initial_state_has_initialization_phase(self):
        """Initial state starts in INITIALIZATION phase."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )

        assert state.current_phase == FeaturePhase.INITIALIZATION
        assert len(state.phase_history) == 1
        assert state.phase_history[0].phase == "initialization"

    def test_create_initial_state_has_all_tracks(self):
        """Initial state has all four tracks."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )

        assert "context" in state.tracks
        assert "design" in state.tracks
        assert "business_case" in state.tracks
        assert "engineering" in state.tracks

        for track in state.tracks.values():
            assert track.status == TrackStatus.NOT_STARTED

    def test_create_initial_state_has_artifacts(self):
        """Initial state has artifact placeholders."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )

        assert "jira_epic" in state.artifacts
        assert "figma" in state.artifacts
        assert "confluence_page" in state.artifacts
        assert "wireframes_url" in state.artifacts

        for value in state.artifacts.values():
            assert value is None

    def test_create_initial_state_has_aliases(self):
        """Initial state initializes aliases with primary name."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )

        assert state.aliases is not None
        assert state.aliases.primary_name == "OTP Checkout Recovery"

    def test_create_initial_state_has_empty_decisions(self):
        """Initial state has empty decisions list."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )

        assert state.decisions == []


class TestFeatureStateSaveLoad:
    """Tests for FeatureState save/load roundtrip."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir)

    def test_save_creates_yaml_file(self, temp_dir):
        """Save creates feature-state.yaml file."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )

        saved_path = state.save(temp_dir)
        assert saved_path.exists()
        assert saved_path.name == "feature-state.yaml"

    def test_load_returns_feature_state(self, temp_dir):
        """Load returns FeatureState from YAML file."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert loaded is not None
        assert loaded.title == "OTP Checkout Recovery"

    def test_save_load_roundtrip_preserves_slug(self, temp_dir):
        """Roundtrip preserves slug."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert loaded.slug == state.slug

    def test_save_load_roundtrip_preserves_title(self, temp_dir):
        """Roundtrip preserves title."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert loaded.title == state.title

    def test_save_load_roundtrip_preserves_product_id(self, temp_dir):
        """Roundtrip preserves product_id."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert loaded.product_id == state.product_id

    def test_save_load_roundtrip_preserves_organization(self, temp_dir):
        """Roundtrip preserves organization."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert loaded.organization == state.organization

    def test_save_load_roundtrip_preserves_brain_entity(self, temp_dir):
        """Roundtrip preserves brain_entity."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert loaded.brain_entity == state.brain_entity

    def test_save_load_roundtrip_preserves_master_sheet_row(self, temp_dir):
        """Roundtrip preserves master_sheet_row."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
            master_sheet_row=15,
        )
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert loaded.master_sheet_row == 15

    def test_save_load_roundtrip_preserves_created_timestamp(self, temp_dir):
        """Roundtrip preserves created timestamp."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        # Compare to second precision (microseconds may differ)
        assert loaded.created.replace(microsecond=0) == state.created.replace(
            microsecond=0
        )

    def test_save_load_roundtrip_preserves_created_by(self, temp_dir):
        """Roundtrip preserves created_by."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert loaded.created_by == "jane.smith"

    def test_save_load_roundtrip_preserves_current_phase(self, temp_dir):
        """Roundtrip preserves current_phase."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.enter_phase(FeaturePhase.SIGNAL_ANALYSIS)
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert loaded.current_phase == FeaturePhase.SIGNAL_ANALYSIS

    def test_save_load_roundtrip_preserves_phase_history(self, temp_dir):
        """Roundtrip preserves phase_history."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.enter_phase(FeaturePhase.SIGNAL_ANALYSIS, {"insights_reviewed": 5})
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert len(loaded.phase_history) == 2  # initialization + signal_analysis
        assert loaded.phase_history[1].phase == "signal_analysis"
        assert loaded.phase_history[1].metadata.get("insights_reviewed") == 5

    def test_save_load_roundtrip_preserves_tracks(self, temp_dir):
        """Roundtrip preserves track states."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.update_track("context", TrackStatus.IN_PROGRESS, current_version=1)
        state.update_track("design", TrackStatus.NOT_STARTED)
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert loaded.tracks["context"].status == TrackStatus.IN_PROGRESS
        assert loaded.tracks["context"].current_version == 1

    def test_save_load_roundtrip_preserves_artifacts(self, temp_dir):
        """Roundtrip preserves artifacts."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.add_artifact("figma", "https://figma.com/file/abc123")
        state.add_artifact("jira_epic", "MK-1234")
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert loaded.artifacts["figma"] == "https://figma.com/file/abc123"
        assert loaded.artifacts["jira_epic"] == "MK-1234"

    def test_save_load_roundtrip_preserves_decisions(self, temp_dir):
        """Roundtrip preserves decisions."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.add_decision(
            decision="Proceed with 'remember device' approach",
            rationale="Best balance of UX and security",
            decided_by="jane.smith",
        )
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert len(loaded.decisions) == 1
        assert loaded.decisions[0].decision == "Proceed with 'remember device' approach"

    def test_save_load_roundtrip_preserves_aliases(self, temp_dir):
        """Roundtrip preserves aliases."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.add_alias("OTP Recovery")
        state.add_alias("checkout otp fix", source="slack")
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert loaded.aliases is not None
        assert loaded.aliases.primary_name == "OTP Checkout Recovery"
        assert "OTP Recovery" in loaded.aliases.known_aliases
        assert "checkout otp fix" in loaded.aliases.known_aliases

    def test_load_nonexistent_returns_none(self, temp_dir):
        """Load returns None for nonexistent file."""
        loaded = FeatureState.load(temp_dir)
        assert loaded is None


class TestFeatureStateYamlFormat:
    """Tests to verify YAML output matches PRD C.4 specification."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir)

    def test_yaml_has_required_top_level_fields(self, temp_dir):
        """YAML has all required top-level fields from PRD C.4."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
            master_sheet_row=15,
        )
        state.save(temp_dir)

        yaml_content = (temp_dir / "feature-state.yaml").read_text()

        # Check required top-level fields
        assert "slug:" in yaml_content
        assert "title:" in yaml_content
        assert "product_id:" in yaml_content
        assert "organization:" in yaml_content
        assert "context_file:" in yaml_content
        assert "brain_entity:" in yaml_content
        assert "master_sheet_row:" in yaml_content
        assert "created:" in yaml_content
        assert "created_by:" in yaml_content

    def test_yaml_has_engine_section(self, temp_dir):
        """YAML has engine section with tracks and phases."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.save(temp_dir)

        yaml_content = (temp_dir / "feature-state.yaml").read_text()

        assert "engine:" in yaml_content
        assert "current_phase:" in yaml_content
        assert "phase_history:" in yaml_content
        assert "tracks:" in yaml_content

    def test_yaml_has_artifacts_section(self, temp_dir):
        """YAML has artifacts section."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.save(temp_dir)

        yaml_content = (temp_dir / "feature-state.yaml").read_text()

        assert "artifacts:" in yaml_content
        assert "jira_epic:" in yaml_content
        assert "figma:" in yaml_content

    def test_yaml_has_decisions_section(self, temp_dir):
        """YAML has decisions section."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.save(temp_dir)

        yaml_content = (temp_dir / "feature-state.yaml").read_text()

        assert "decisions:" in yaml_content

    def test_yaml_has_aliases_section(self, temp_dir):
        """YAML has aliases section."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.save(temp_dir)

        yaml_content = (temp_dir / "feature-state.yaml").read_text()

        assert "aliases:" in yaml_content
        assert "primary_name:" in yaml_content


class TestFeatureStateEdgeCases:
    """Tests for edge cases and special scenarios."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir)

    def test_title_with_special_characters(self, temp_dir):
        """Title with special characters handled correctly."""
        state = FeatureState.create_initial_state(
            title="User's Dashboard! (v2.0)",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert loaded.title == "User's Dashboard! (v2.0)"

    def test_empty_phase_history(self, temp_dir):
        """Empty phase history (edge case) handled."""
        state = FeatureState(
            slug="test-feature",
            title="Test Feature",
            product_id="meal-kit",
            organization="growth-division",
            context_file="test-feature-context.md",
            brain_entity="[[Entities/Test_Feature]]",
            created_by="jane.smith",
            phase_history=[],
        )
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert loaded.phase_history == []

    def test_missing_master_sheet_row(self, temp_dir):
        """Missing master_sheet_row handled correctly."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
            master_sheet_row=None,
        )
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert loaded.master_sheet_row is None

    def test_multiple_decisions(self, temp_dir):
        """Multiple decisions preserved in order."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.add_decision("Decision 1", "Rationale 1", "user1")
        state.add_decision("Decision 2", "Rationale 2", "user2")
        state.add_decision("Decision 3", "Rationale 3", "user1")
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert len(loaded.decisions) == 3
        assert loaded.decisions[0].decision == "Decision 1"
        assert loaded.decisions[1].decision == "Decision 2"
        assert loaded.decisions[2].decision == "Decision 3"

    def test_track_with_approvals(self, temp_dir):
        """Track approvals preserved."""
        state = FeatureState.create_initial_state(
            title="OTP Checkout Recovery",
            product_id="meal-kit",
            organization="growth-division",
            created_by="jane.smith",
        )
        state.tracks["business_case"].approvals = [
            {
                "name": "Jack Approver",
                "date": "2026-02-02",
                "type": "verbal",
                "reference": "Slack thread #meal-kit-planning",
            }
        ]
        state.save(temp_dir)

        loaded = FeatureState.load(temp_dir)
        assert len(loaded.tracks["business_case"].approvals) == 1
        assert loaded.tracks["business_case"].approvals[0]["name"] == "Jack Approver"


class TestDerivedStatus:
    """Tests for get_derived_status() method implementing PRD C.5 rules."""

    def test_derived_status_all_not_started(self):
        """All tracks not started -> 'To Do'."""
        state = FeatureState.create_initial_state(
            title="Test Feature",
            product_id="meal-kit",
            organization="growth-division",
            created_by="test_user",
        )
        # All tracks default to NOT_STARTED
        assert state.get_derived_status() == "To Do"

    def test_derived_status_all_complete(self):
        """All tracks complete -> 'Done'."""
        state = FeatureState.create_initial_state(
            title="Test Feature",
            product_id="meal-kit",
            organization="growth-division",
            created_by="test_user",
        )
        for track_name in state.tracks:
            state.update_track(track_name, status=TrackStatus.COMPLETE)

        assert state.get_derived_status() == "Done"

    def test_derived_status_any_in_progress(self):
        """Any track in progress -> 'In Progress'."""
        state = FeatureState.create_initial_state(
            title="Test Feature",
            product_id="meal-kit",
            organization="growth-division",
            created_by="test_user",
        )
        state.update_track("context", status=TrackStatus.IN_PROGRESS)

        assert state.get_derived_status() == "In Progress"

    def test_derived_status_any_pending_input(self):
        """Any track pending input -> 'In Progress'."""
        state = FeatureState.create_initial_state(
            title="Test Feature",
            product_id="meal-kit",
            organization="growth-division",
            created_by="test_user",
        )
        state.update_track("design", status=TrackStatus.PENDING_INPUT)

        assert state.get_derived_status() == "In Progress"

    def test_derived_status_any_pending_approval(self):
        """Any track pending approval -> 'In Progress'."""
        state = FeatureState.create_initial_state(
            title="Test Feature",
            product_id="meal-kit",
            organization="growth-division",
            created_by="test_user",
        )
        state.update_track("business_case", status=TrackStatus.PENDING_APPROVAL)

        assert state.get_derived_status() == "In Progress"

    def test_derived_status_mixed_complete_and_not_started(self):
        """Mixed complete and not started -> 'To Do' (no in-progress)."""
        state = FeatureState.create_initial_state(
            title="Test Feature",
            product_id="meal-kit",
            organization="growth-division",
            created_by="test_user",
        )
        state.update_track("context", status=TrackStatus.COMPLETE)
        # Other tracks remain NOT_STARTED
        # Since there's no in-progress/pending, and not all complete, it's "To Do"
        # Actually, some complete + some not started with no in-progress = "To Do"
        assert state.get_derived_status() == "To Do"

    def test_derived_status_mixed_with_in_progress(self):
        """Mixed statuses including in progress -> 'In Progress'."""
        state = FeatureState.create_initial_state(
            title="Test Feature",
            product_id="meal-kit",
            organization="growth-division",
            created_by="test_user",
        )
        state.update_track("context", status=TrackStatus.COMPLETE)
        state.update_track("design", status=TrackStatus.IN_PROGRESS)
        state.update_track("business_case", status=TrackStatus.NOT_STARTED)
        state.update_track("engineering", status=TrackStatus.NOT_STARTED)

        assert state.get_derived_status() == "In Progress"

    def test_derived_status_blocked_track(self):
        """Blocked track (not in-progress/pending) -> 'To Do'."""
        state = FeatureState.create_initial_state(
            title="Test Feature",
            product_id="meal-kit",
            organization="growth-division",
            created_by="test_user",
        )
        state.update_track("engineering", status=TrackStatus.BLOCKED)
        # BLOCKED is not counted as in-progress or pending
        assert state.get_derived_status() == "To Do"

    def test_all_tracks_complete_property(self):
        """Test all_tracks_complete property."""
        state = FeatureState.create_initial_state(
            title="Test Feature",
            product_id="meal-kit",
            organization="growth-division",
            created_by="test_user",
        )

        assert state.all_tracks_complete is False

        for track_name in state.tracks:
            state.update_track(track_name, status=TrackStatus.COMPLETE)

        assert state.all_tracks_complete is True

    def test_any_track_in_progress_property_includes_pending(self):
        """Test any_track_in_progress includes pending states."""
        state = FeatureState.create_initial_state(
            title="Test Feature",
            product_id="meal-kit",
            organization="growth-division",
            created_by="test_user",
        )

        assert state.any_track_in_progress is False

        # Test IN_PROGRESS
        state.update_track("context", status=TrackStatus.IN_PROGRESS)
        assert state.any_track_in_progress is True

        # Reset and test PENDING_INPUT
        state.update_track("context", status=TrackStatus.NOT_STARTED)
        assert state.any_track_in_progress is False
        state.update_track("design", status=TrackStatus.PENDING_INPUT)
        assert state.any_track_in_progress is True

        # Reset and test PENDING_APPROVAL
        state.update_track("design", status=TrackStatus.NOT_STARTED)
        assert state.any_track_in_progress is False
        state.update_track("business_case", status=TrackStatus.PENDING_APPROVAL)
        assert state.any_track_in_progress is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
