"""
Unit tests for the Quality Gates module.

Tests cover:
- Context document thresholds (60/75/85)
- Business case approval validation
- Design artifact requirements
- Engineering readiness checks
- Decision gate validation
- Custom threshold overrides
"""

import sys
from pathlib import Path

import pytest

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from context_engine.quality_gates import (
    DesignArtifactRequirement,
    EngineeringRequirement,
    GateLevel,
    GateResult,
    GateStatus,
    PhaseGateResult,
    QualityGates,
    StakeholderRequirement,
    ThresholdLevel,
    create_gates_for_product,
    get_default_gates,
    validate_business_case_approval,
    validate_context_requirements,
    validate_context_score,
    validate_decision_gate_readiness,
    validate_design_artifacts,
    validate_engineering_readiness,
)


class TestQualityGatesConfiguration:
    """Test QualityGates configuration class."""

    def test_default_thresholds(self):
        """Test default context document thresholds."""
        gates = QualityGates()
        assert gates.context_draft_threshold == 60.0
        assert gates.context_review_threshold == 75.0
        assert gates.context_approved_threshold == 85.0

    def test_get_context_threshold(self):
        """Test getting threshold by level."""
        gates = QualityGates()
        assert gates.get_context_threshold(ThresholdLevel.DRAFT) == 60.0
        assert gates.get_context_threshold(ThresholdLevel.REVIEW) == 75.0
        assert gates.get_context_threshold(ThresholdLevel.APPROVED) == 85.0

    def test_get_threshold_for_version(self):
        """Test getting threshold by version number."""
        gates = QualityGates()
        assert gates.get_threshold_for_version(1) == 60.0
        assert gates.get_threshold_for_version(2) == 75.0
        assert gates.get_threshold_for_version(3) == 85.0
        assert gates.get_threshold_for_version(4) == 85.0  # v4+ uses approved threshold

    def test_custom_thresholds(self):
        """Test custom threshold values."""
        gates = QualityGates(
            context_draft_threshold=55.0,
            context_review_threshold=70.0,
            context_approved_threshold=80.0,
        )
        assert gates.get_threshold_for_version(1) == 55.0
        assert gates.get_threshold_for_version(2) == 70.0
        assert gates.get_threshold_for_version(3) == 80.0

    def test_default_design_artifacts(self):
        """Test default design artifact requirements."""
        gates = QualityGates()
        figma = gates.get_design_artifact("figma")
        wireframes = gates.get_design_artifact("wireframes")

        assert figma is not None
        assert figma.required is True
        assert wireframes is not None
        assert wireframes.required is False

    def test_is_figma_required(self):
        """Test Figma requirement check."""
        gates = QualityGates()
        assert gates.is_figma_required() is True

    def test_is_wireframes_required(self):
        """Test wireframes requirement check (default is False)."""
        gates = QualityGates()
        assert gates.is_wireframes_required() is False

    def test_get_required_approvers(self):
        """Test getting required approver roles."""
        gates = QualityGates()
        approvers = gates.get_required_approvers()
        assert "product_lead" in approvers

    def test_to_dict_and_from_dict(self):
        """Test serialization roundtrip."""
        original = QualityGates(
            context_draft_threshold=55.0,
            context_review_threshold=70.0,
            context_approved_threshold=80.0,
        )
        data = original.to_dict()
        restored = QualityGates.from_dict(data)

        assert restored.context_draft_threshold == 55.0
        assert restored.context_review_threshold == 70.0
        assert restored.context_approved_threshold == 80.0

    def test_product_overrides(self):
        """Test applying product-specific overrides."""
        gates = QualityGates(
            product_overrides={
                "meal-kit": {
                    "context_draft_threshold": 50.0,
                    "context_review_threshold": 65.0,
                }
            }
        )
        product_gates = gates.apply_product_overrides("meal-kit")
        assert product_gates.context_draft_threshold == 50.0
        assert product_gates.context_review_threshold == 65.0


class TestContextScoreValidation:
    """Test context document score validation."""

    def test_v1_score_passes_at_60(self):
        """Test v1 passes at 60% threshold."""
        result = validate_context_score(60.0, version=1)
        assert result.status == GateStatus.PASS
        assert result.score == 60.0
        assert result.threshold == 60.0

    def test_v1_score_fails_below_60(self):
        """Test v1 fails below 60% threshold."""
        result = validate_context_score(55.0, version=1)
        assert result.status == GateStatus.FAIL
        assert result.is_blocking is True
        assert result.action is not None

    def test_v2_score_passes_at_75(self):
        """Test v2 passes at 75% threshold."""
        result = validate_context_score(75.0, version=2)
        assert result.status == GateStatus.PASS
        assert result.threshold == 75.0

    def test_v2_score_fails_below_75(self):
        """Test v2 fails below 75% threshold."""
        result = validate_context_score(70.0, version=2)
        assert result.status == GateStatus.FAIL

    def test_v3_score_passes_at_85(self):
        """Test v3 passes at 85% threshold."""
        result = validate_context_score(85.0, version=3)
        assert result.status == GateStatus.PASS
        assert result.threshold == 85.0

    def test_v3_score_fails_below_85(self):
        """Test v3 fails below 85% threshold."""
        result = validate_context_score(80.0, version=3)
        assert result.status == GateStatus.FAIL

    def test_custom_threshold(self):
        """Test with custom threshold configuration."""
        gates = QualityGates(context_review_threshold=70.0)
        result = validate_context_score(70.0, version=2, gates=gates)
        assert result.status == GateStatus.PASS

    def test_score_exceeds_threshold(self):
        """Test score well above threshold."""
        result = validate_context_score(95.0, version=3)
        assert result.status == GateStatus.PASS
        assert result.score == 95.0


class TestContextRequirementsValidation:
    """Test context document requirements validation."""

    def test_all_requirements_present(self):
        """Test when all required elements are present."""
        results = validate_context_requirements(
            has_problem_statement=True,
            has_success_metrics=True,
            has_scope=True,
            has_stakeholders=True,
        )
        # Should have 3 results (stakeholders not required by default)
        assert len(results) == 3
        assert all(r.status == GateStatus.PASS for r in results)

    def test_missing_problem_statement(self):
        """Test missing problem statement fails."""
        results = validate_context_requirements(
            has_problem_statement=False,
            has_success_metrics=True,
            has_scope=True,
        )
        problem_gate = next(
            r for r in results if r.gate_name == "problem_statement_present"
        )
        assert problem_gate.status == GateStatus.FAIL
        assert problem_gate.is_blocking is True

    def test_missing_success_metrics(self):
        """Test missing success metrics fails."""
        results = validate_context_requirements(
            has_problem_statement=True,
            has_success_metrics=False,
            has_scope=True,
        )
        metrics_gate = next(
            r for r in results if r.gate_name == "success_metrics_defined"
        )
        assert metrics_gate.status == GateStatus.FAIL

    def test_missing_scope(self):
        """Test missing scope fails."""
        results = validate_context_requirements(
            has_problem_statement=True,
            has_success_metrics=True,
            has_scope=False,
        )
        scope_gate = next(r for r in results if r.gate_name == "scope_defined")
        assert scope_gate.status == GateStatus.FAIL

    def test_stakeholders_optional_by_default(self):
        """Test stakeholders are optional by default."""
        gates = QualityGates(context_requires_stakeholders=False)
        results = validate_context_requirements(
            has_problem_statement=True,
            has_success_metrics=True,
            has_scope=True,
            has_stakeholders=False,
            gates=gates,
        )
        # Stakeholders gate should not be in results when not required
        stakeholders_gate = [
            r for r in results if r.gate_name == "stakeholders_defined"
        ]
        assert len(stakeholders_gate) == 0

    def test_stakeholders_required_when_configured(self):
        """Test stakeholders are checked when configured."""
        gates = QualityGates(context_requires_stakeholders=True)
        results = validate_context_requirements(
            has_problem_statement=True,
            has_success_metrics=True,
            has_scope=True,
            has_stakeholders=False,
            gates=gates,
        )
        stakeholders_gate = next(
            r for r in results if r.gate_name == "stakeholders_defined"
        )
        assert stakeholders_gate.status == GateStatus.INCOMPLETE
        assert stakeholders_gate.level == GateLevel.ADVISORY


class TestBusinessCaseApproval:
    """Test business case approval validation."""

    def test_approved_by_required_approver(self):
        """Test approval passes when required approver approves."""
        approvals = [
            {"approver": "product_lead", "approved": True},
        ]
        result = validate_business_case_approval(
            approvals=approvals,
            required_approvers=["product_lead"],
        )
        assert result.status == GateStatus.PASS

    def test_no_approvals_yet(self):
        """Test status when no approvals recorded."""
        result = validate_business_case_approval(approvals=[])
        assert result.status == GateStatus.INCOMPLETE
        assert result.is_blocking is True

    def test_pending_approval(self):
        """Test pending approval status."""
        approvals = [
            {"approver": "product_lead", "approved": True},
        ]
        result = validate_business_case_approval(
            approvals=approvals,
            required_approvers=["product_lead", "engineering_lead"],
        )
        assert result.status == GateStatus.INCOMPLETE
        assert "engineering_lead" in result.action

    def test_rejected_fails_immediately(self):
        """Test rejection fails the gate."""
        approvals = [
            {"approver": "product_lead", "approved": False},
        ]
        result = validate_business_case_approval(
            approvals=approvals,
            required_approvers=["product_lead"],
        )
        assert result.status == GateStatus.FAIL

    def test_multiple_approvers_all_approved(self):
        """Test multiple approvers all approved."""
        approvals = [
            {"approver": "product_lead", "approved": True},
            {"approver": "engineering_lead", "approved": True},
            {"approver": "finance", "approved": True},
        ]
        result = validate_business_case_approval(
            approvals=approvals,
            required_approvers=["product_lead", "engineering_lead"],
        )
        assert result.status == GateStatus.PASS


class TestDesignArtifactValidation:
    """Test design artifact validation."""

    def test_figma_required_and_present(self):
        """Test Figma passes when present and required."""
        artifacts = {
            "figma": "https://www.figma.com/file/abc123",
        }
        results = validate_design_artifacts(artifacts)
        figma_gate = next(r for r in results if r.gate_name == "figma_provided")
        assert figma_gate.status == GateStatus.PASS

    def test_figma_required_and_missing(self):
        """Test Figma fails when missing and required."""
        artifacts = {
            "figma": None,
        }
        results = validate_design_artifacts(artifacts)
        figma_gate = next(r for r in results if r.gate_name == "figma_provided")
        assert figma_gate.status == GateStatus.FAIL
        assert figma_gate.is_blocking is True

    def test_wireframes_optional_and_missing(self):
        """Test wireframes incomplete when missing (not fail since optional)."""
        artifacts = {
            "figma": "https://www.figma.com/file/abc123",
            "wireframes": None,
        }
        results = validate_design_artifacts(artifacts)
        wireframes_gate = next(
            r for r in results if r.gate_name == "wireframes_provided"
        )
        assert wireframes_gate.status == GateStatus.INCOMPLETE
        assert wireframes_gate.is_blocking is False

    def test_wireframes_present(self):
        """Test wireframes pass when present."""
        artifacts = {
            "figma": "https://www.figma.com/file/abc123",
            "wireframes": "https://example.com/wireframes",
        }
        results = validate_design_artifacts(artifacts)
        wireframes_gate = next(
            r for r in results if r.gate_name == "wireframes_provided"
        )
        assert wireframes_gate.status == GateStatus.PASS

    def test_figma_url_pattern_validation(self):
        """Test Figma URL pattern validation."""
        artifacts = {
            "figma": "https://example.com/not-figma",
        }
        results = validate_design_artifacts(artifacts)
        figma_gate = next(r for r in results if r.gate_name == "figma_provided")
        # Should have a warning since URL pattern doesn't match
        assert figma_gate.status == GateStatus.WARNING


class TestEngineeringReadinessValidation:
    """Test engineering readiness validation."""

    def test_estimate_required_and_present(self):
        """Test estimate passes when present."""
        results = validate_engineering_readiness(
            has_estimate=True,
            estimate_value="M",
        )
        estimate_gate = next(r for r in results if r.gate_name == "estimate_provided")
        assert estimate_gate.status == GateStatus.PASS
        assert estimate_gate.evidence == "M"

    def test_estimate_required_and_missing(self):
        """Test estimate fails when missing."""
        results = validate_engineering_readiness(
            has_estimate=False,
        )
        estimate_gate = next(r for r in results if r.gate_name == "estimate_provided")
        assert estimate_gate.status == GateStatus.FAIL
        assert estimate_gate.is_blocking is True

    def test_adrs_decided(self):
        """Test ADRs pass when all decided."""
        results = validate_engineering_readiness(
            has_estimate=True,
            adr_count=3,
            proposed_adr_count=0,
        )
        adr_gate = next(r for r in results if r.gate_name == "adrs_decided")
        assert adr_gate.status == GateStatus.PASS

    def test_adrs_pending_decision(self):
        """Test ADRs fail when some still proposed."""
        results = validate_engineering_readiness(
            has_estimate=True,
            adr_count=3,
            proposed_adr_count=1,
        )
        adr_gate = next(r for r in results if r.gate_name == "adrs_decided")
        assert adr_gate.status == GateStatus.FAIL

    def test_no_adrs_is_fine(self):
        """Test no ADRs is acceptable."""
        results = validate_engineering_readiness(
            has_estimate=True,
            adr_count=0,
            proposed_adr_count=0,
        )
        adr_gate = next(r for r in results if r.gate_name == "adrs_decided")
        assert adr_gate.status == GateStatus.PASS

    def test_blocking_dependencies_fail(self):
        """Test blocking dependencies fail the gate."""
        results = validate_engineering_readiness(
            has_estimate=True,
            blocking_dep_count=2,
        )
        dep_gate = next(r for r in results if r.gate_name == "no_blocking_dependencies")
        assert dep_gate.status == GateStatus.FAIL

    def test_no_blocking_dependencies(self):
        """Test no blocking dependencies passes."""
        results = validate_engineering_readiness(
            has_estimate=True,
            blocking_dep_count=0,
        )
        dep_gate = next(r for r in results if r.gate_name == "no_blocking_dependencies")
        assert dep_gate.status == GateStatus.PASS

    def test_high_risks_unmitigated_fail(self):
        """Test unmitigated high-impact risks fail."""
        results = validate_engineering_readiness(
            has_estimate=True,
            high_risk_unmitigated_count=1,
        )
        risk_gate = next(r for r in results if r.gate_name == "high_risks_mitigated")
        assert risk_gate.status == GateStatus.FAIL

    def test_risks_mitigated_pass(self):
        """Test all risks mitigated passes."""
        results = validate_engineering_readiness(
            has_estimate=True,
            high_risk_unmitigated_count=0,
        )
        risk_gate = next(r for r in results if r.gate_name == "high_risks_mitigated")
        assert risk_gate.status == GateStatus.PASS


class TestDecisionGateValidation:
    """Test decision gate readiness validation."""

    def test_all_tracks_complete(self):
        """Test decision gate passes when all tracks complete."""
        result = validate_decision_gate_readiness(
            context_passed=True,
            business_case_approved=True,
            design_acceptable=True,
            engineering_complete=True,
            has_blocking_risks=False,
        )
        assert result.status == GateStatus.PASS
        assert len(result.blockers) == 0

    def test_context_incomplete_blocks(self):
        """Test incomplete context blocks decision gate."""
        result = validate_decision_gate_readiness(
            context_passed=False,
            business_case_approved=True,
            design_acceptable=True,
            engineering_complete=True,
        )
        assert result.status == GateStatus.FAIL
        assert "Context document must be complete" in result.blockers

    def test_bc_not_approved_blocks(self):
        """Test unapproved BC blocks decision gate."""
        result = validate_decision_gate_readiness(
            context_passed=True,
            business_case_approved=False,
            design_acceptable=True,
            engineering_complete=True,
        )
        assert result.status == GateStatus.FAIL
        assert "Business case approval required" in result.blockers

    def test_design_missing_blocks(self):
        """Test missing design artifacts blocks decision gate."""
        result = validate_decision_gate_readiness(
            context_passed=True,
            business_case_approved=True,
            design_acceptable=False,
            engineering_complete=True,
        )
        assert result.status == GateStatus.FAIL
        assert "Design artifacts required" in result.blockers

    def test_engineering_incomplete_blocks(self):
        """Test incomplete engineering blocks decision gate."""
        result = validate_decision_gate_readiness(
            context_passed=True,
            business_case_approved=True,
            design_acceptable=True,
            engineering_complete=False,
        )
        assert result.status == GateStatus.FAIL
        assert "Engineering specification required" in result.blockers

    def test_blocking_risks_fail(self):
        """Test blocking risks fail decision gate."""
        result = validate_decision_gate_readiness(
            context_passed=True,
            business_case_approved=True,
            design_acceptable=True,
            engineering_complete=True,
            has_blocking_risks=True,
        )
        assert result.status == GateStatus.FAIL
        assert "High-impact risks must be mitigated" in result.blockers

    def test_multiple_blockers(self):
        """Test multiple blockers are all reported."""
        result = validate_decision_gate_readiness(
            context_passed=False,
            business_case_approved=False,
            design_acceptable=False,
            engineering_complete=False,
            has_blocking_risks=True,
        )
        assert result.status == GateStatus.FAIL
        assert len(result.blockers) == 5


class TestGateResultHelpers:
    """Test GateResult helper methods and properties."""

    def test_is_blocking(self):
        """Test is_blocking property."""
        blocking = GateResult(
            gate_name="test",
            status=GateStatus.FAIL,
            message="Test",
            level=GateLevel.BLOCKING,
        )
        advisory = GateResult(
            gate_name="test",
            status=GateStatus.FAIL,
            message="Test",
            level=GateLevel.ADVISORY,
        )
        assert blocking.is_blocking is True
        assert advisory.is_blocking is False

    def test_passed_property(self):
        """Test passed property."""
        passing = GateResult(gate_name="test", status=GateStatus.PASS, message="Test")
        warning = GateResult(
            gate_name="test", status=GateStatus.WARNING, message="Test"
        )
        failing = GateResult(gate_name="test", status=GateStatus.FAIL, message="Test")

        assert passing.passed is True
        assert warning.passed is True  # Warnings still count as passed
        assert failing.passed is False

    def test_needs_attention_property(self):
        """Test needs_attention property."""
        passing = GateResult(gate_name="test", status=GateStatus.PASS, message="Test")
        failing = GateResult(gate_name="test", status=GateStatus.FAIL, message="Test")
        incomplete = GateResult(
            gate_name="test", status=GateStatus.INCOMPLETE, message="Test"
        )
        warning = GateResult(
            gate_name="test", status=GateStatus.WARNING, message="Test"
        )

        assert passing.needs_attention is False
        assert failing.needs_attention is True
        assert incomplete.needs_attention is True
        assert warning.needs_attention is True

    def test_to_dict(self):
        """Test to_dict serialization."""
        result = GateResult(
            gate_name="test_gate",
            status=GateStatus.FAIL,
            message="Test failed",
            level=GateLevel.BLOCKING,
            score=55.0,
            threshold=60.0,
            action="Fix the issue",
            evidence="Some evidence",
        )
        data = result.to_dict()

        assert data["gate_name"] == "test_gate"
        assert data["status"] == "fail"
        assert data["level"] == "blocking"
        assert data["score"] == 55.0
        assert data["threshold"] == 60.0
        assert data["action"] == "Fix the issue"
        assert data["evidence"] == "Some evidence"


class TestPhaseGateResult:
    """Test PhaseGateResult aggregation."""

    def test_passed_count(self):
        """Test passed_count calculation."""
        result = PhaseGateResult(
            phase="test",
            status=GateStatus.INCOMPLETE,
            gates=[
                GateResult(gate_name="g1", status=GateStatus.PASS, message=""),
                GateResult(gate_name="g2", status=GateStatus.PASS, message=""),
                GateResult(gate_name="g3", status=GateStatus.FAIL, message=""),
            ],
        )
        assert result.passed_count == 2
        assert result.total_count == 3

    def test_has_blockers(self):
        """Test has_blockers property."""
        with_blockers = PhaseGateResult(
            phase="test",
            status=GateStatus.FAIL,
            blockers=["Issue 1"],
        )
        without_blockers = PhaseGateResult(
            phase="test",
            status=GateStatus.PASS,
            blockers=[],
        )
        assert with_blockers.has_blockers is True
        assert without_blockers.has_blockers is False

    def test_blocking_gates_passed(self):
        """Test blocking_gates_passed property."""
        all_blocking_pass = PhaseGateResult(
            phase="test",
            status=GateStatus.PASS,
            gates=[
                GateResult(
                    gate_name="g1",
                    status=GateStatus.PASS,
                    message="",
                    level=GateLevel.BLOCKING,
                ),
                GateResult(
                    gate_name="g2",
                    status=GateStatus.FAIL,
                    message="",
                    level=GateLevel.ADVISORY,
                ),
            ],
        )
        blocking_fail = PhaseGateResult(
            phase="test",
            status=GateStatus.FAIL,
            gates=[
                GateResult(
                    gate_name="g1",
                    status=GateStatus.FAIL,
                    message="",
                    level=GateLevel.BLOCKING,
                ),
                GateResult(
                    gate_name="g2",
                    status=GateStatus.PASS,
                    message="",
                    level=GateLevel.ADVISORY,
                ),
            ],
        )
        assert all_blocking_pass.blocking_gates_passed is True
        assert blocking_fail.blocking_gates_passed is False


class TestFactoryFunctions:
    """Test factory functions."""

    def test_get_default_gates(self):
        """Test get_default_gates returns valid configuration."""
        gates = get_default_gates()
        assert gates.context_draft_threshold == 60.0
        assert gates.context_review_threshold == 75.0
        assert gates.context_approved_threshold == 85.0

    def test_create_gates_for_product(self):
        """Test create_gates_for_product with overrides."""
        gates = create_gates_for_product(
            "test-product",
            overrides={
                "context_draft_threshold": 50.0,
            },
        )
        assert gates.context_draft_threshold == 50.0

    def test_create_gates_for_product_no_overrides(self):
        """Test create_gates_for_product without overrides uses defaults."""
        gates = create_gates_for_product("test-product")
        assert gates.context_draft_threshold == 60.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
