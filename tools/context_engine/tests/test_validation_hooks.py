"""
Unit tests for the Validation Hooks module.

Tests cover:
- HookSeverity enum values
- HookFrequency enum values
- ValidationStatus enum values
- ValidationResult dataclass serialization
- ValidationReport aggregation
- Built-in hooks (brain refs, data freshness, consistency, URLs)
- ValidationHookRunner functionality
- Hook registration and execution
- Filtering by category, severity
- Report generation
"""

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from context_engine.validation_hooks import (
    HookFrequency,
    HookSeverity,
    ValidationHook,
    ValidationHookRunner,
    ValidationReport,
    ValidationResult,
    ValidationStatus,
    format_validation_results,
    get_default_hooks,
    get_validation_report,
    is_feature_valid,
    run_validation_hooks,
    validate_artifact_urls,
    validate_brain_refs,
    validate_context_doc_consistency,
    validate_data_freshness,
    validate_track_status_consistency,
)


class TestEnums:
    """Test enum definitions."""

    def test_hook_severity_values(self):
        """Test HookSeverity enum values."""
        assert HookSeverity.CRITICAL.value == "critical"
        assert HookSeverity.HIGH.value == "high"
        assert HookSeverity.MEDIUM.value == "medium"
        assert HookSeverity.LOW.value == "low"

    def test_hook_frequency_values(self):
        """Test HookFrequency enum values."""
        assert HookFrequency.ALWAYS.value == "always"
        assert HookFrequency.HOURLY.value == "hourly"
        assert HookFrequency.DAILY.value == "daily"
        assert HookFrequency.ON_DEMAND.value == "on_demand"

    def test_validation_status_values(self):
        """Test ValidationStatus enum values."""
        assert ValidationStatus.PASS.value == "pass"
        assert ValidationStatus.FAIL.value == "fail"
        assert ValidationStatus.WARN.value == "warn"
        assert ValidationStatus.SKIP.value == "skip"
        assert ValidationStatus.ERROR.value == "error"


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_result_creation(self):
        """Test creating a validation result."""
        result = ValidationResult(
            hook_name="test_hook",
            status=ValidationStatus.PASS,
            message="Test passed",
        )
        assert result.hook_name == "test_hook"
        assert result.status == ValidationStatus.PASS
        assert result.message == "Test passed"
        assert result.severity == HookSeverity.MEDIUM  # Default

    def test_result_default_values(self):
        """Test default values for validation result."""
        result = ValidationResult(
            hook_name="test",
            status=ValidationStatus.FAIL,
            message="Test",
        )
        assert result.details is None
        assert result.remediation is None
        assert isinstance(result.checked_at, datetime)
        assert result.metadata == {}

    def test_result_passed_property(self):
        """Test passed property."""
        pass_result = ValidationResult(
            hook_name="t", status=ValidationStatus.PASS, message=""
        )
        warn_result = ValidationResult(
            hook_name="t", status=ValidationStatus.WARN, message=""
        )
        fail_result = ValidationResult(
            hook_name="t", status=ValidationStatus.FAIL, message=""
        )

        assert pass_result.passed is True
        assert warn_result.passed is True  # Warn counts as passed
        assert fail_result.passed is False

    def test_result_failed_property(self):
        """Test failed property."""
        fail_result = ValidationResult(
            hook_name="t", status=ValidationStatus.FAIL, message=""
        )
        pass_result = ValidationResult(
            hook_name="t", status=ValidationStatus.PASS, message=""
        )
        warn_result = ValidationResult(
            hook_name="t", status=ValidationStatus.WARN, message=""
        )

        assert fail_result.failed is True
        assert pass_result.failed is False
        assert warn_result.failed is False

    def test_result_is_critical(self):
        """Test is_critical property."""
        critical = ValidationResult(
            hook_name="t",
            status=ValidationStatus.FAIL,
            message="",
            severity=HookSeverity.CRITICAL,
        )
        high = ValidationResult(
            hook_name="t",
            status=ValidationStatus.FAIL,
            message="",
            severity=HookSeverity.HIGH,
        )
        passed = ValidationResult(
            hook_name="t",
            status=ValidationStatus.PASS,
            message="",
            severity=HookSeverity.CRITICAL,
        )

        assert critical.is_critical is True
        assert high.is_critical is False
        assert passed.is_critical is False  # Must be failed to be critical

    def test_result_to_dict(self):
        """Test to_dict serialization."""
        result = ValidationResult(
            hook_name="test_hook",
            status=ValidationStatus.FAIL,
            message="Test failed",
            severity=HookSeverity.HIGH,
            details="Details here",
            remediation="Fix it",
            metadata={"key": "value"},
        )
        data = result.to_dict()

        assert data["hook_name"] == "test_hook"
        assert data["status"] == "fail"
        assert data["message"] == "Test failed"
        assert data["severity"] == "high"
        assert data["details"] == "Details here"
        assert data["remediation"] == "Fix it"
        assert data["metadata"] == {"key": "value"}
        assert "checked_at" in data

    def test_result_from_dict(self):
        """Test from_dict deserialization."""
        data = {
            "hook_name": "test_hook",
            "status": "pass",
            "message": "All good",
            "severity": "low",
            "checked_at": "2026-02-04T10:00:00",
        }
        result = ValidationResult.from_dict(data)

        assert result.hook_name == "test_hook"
        assert result.status == ValidationStatus.PASS
        assert result.message == "All good"
        assert result.severity == HookSeverity.LOW


class TestValidationReport:
    """Test ValidationReport aggregation."""

    def test_empty_report(self):
        """Test report with no results."""
        report = ValidationReport(feature_slug="test-feature")
        assert report.total_count == 0
        assert report.passed_count == 0
        assert report.failed_count == 0
        assert report.all_passed is True
        assert report.has_critical_failures is False

    def test_report_counts(self):
        """Test report count properties."""
        report = ValidationReport(
            feature_slug="test-feature",
            results=[
                ValidationResult(
                    hook_name="h1", status=ValidationStatus.PASS, message=""
                ),
                ValidationResult(
                    hook_name="h2", status=ValidationStatus.PASS, message=""
                ),
                ValidationResult(
                    hook_name="h3",
                    status=ValidationStatus.FAIL,
                    message="",
                    severity=HookSeverity.HIGH,
                ),
                ValidationResult(
                    hook_name="h4",
                    status=ValidationStatus.FAIL,
                    message="",
                    severity=HookSeverity.CRITICAL,
                ),
                ValidationResult(
                    hook_name="h5", status=ValidationStatus.WARN, message=""
                ),
            ],
        )

        assert report.total_count == 5
        assert report.passed_count == 3  # 2 pass + 1 warn
        assert report.failed_count == 2
        assert report.critical_count == 1

    def test_report_all_passed(self):
        """Test all_passed property."""
        all_pass = ValidationReport(
            feature_slug="test",
            results=[
                ValidationResult(
                    hook_name="h1", status=ValidationStatus.PASS, message=""
                ),
                ValidationResult(
                    hook_name="h2", status=ValidationStatus.WARN, message=""
                ),
            ],
        )
        with_fail = ValidationReport(
            feature_slug="test",
            results=[
                ValidationResult(
                    hook_name="h1", status=ValidationStatus.PASS, message=""
                ),
                ValidationResult(
                    hook_name="h2", status=ValidationStatus.FAIL, message=""
                ),
            ],
        )

        assert all_pass.all_passed is True
        assert with_fail.all_passed is False

    def test_report_has_critical_failures(self):
        """Test has_critical_failures property."""
        with_critical = ValidationReport(
            feature_slug="test",
            results=[
                ValidationResult(
                    hook_name="h1",
                    status=ValidationStatus.FAIL,
                    message="",
                    severity=HookSeverity.CRITICAL,
                ),
            ],
        )
        without_critical = ValidationReport(
            feature_slug="test",
            results=[
                ValidationResult(
                    hook_name="h1",
                    status=ValidationStatus.FAIL,
                    message="",
                    severity=HookSeverity.HIGH,
                ),
            ],
        )

        assert with_critical.has_critical_failures is True
        assert without_critical.has_critical_failures is False

    def test_report_get_by_status(self):
        """Test filtering by status."""
        report = ValidationReport(
            feature_slug="test",
            results=[
                ValidationResult(
                    hook_name="h1", status=ValidationStatus.PASS, message=""
                ),
                ValidationResult(
                    hook_name="h2", status=ValidationStatus.FAIL, message=""
                ),
                ValidationResult(
                    hook_name="h3", status=ValidationStatus.FAIL, message=""
                ),
            ],
        )

        passed = report.get_by_status(ValidationStatus.PASS)
        failed = report.get_by_status(ValidationStatus.FAIL)

        assert len(passed) == 1
        assert len(failed) == 2

    def test_report_get_by_severity(self):
        """Test filtering failures by severity."""
        report = ValidationReport(
            feature_slug="test",
            results=[
                ValidationResult(
                    hook_name="h1",
                    status=ValidationStatus.FAIL,
                    message="",
                    severity=HookSeverity.HIGH,
                ),
                ValidationResult(
                    hook_name="h2",
                    status=ValidationStatus.FAIL,
                    message="",
                    severity=HookSeverity.HIGH,
                ),
                ValidationResult(
                    hook_name="h3",
                    status=ValidationStatus.FAIL,
                    message="",
                    severity=HookSeverity.MEDIUM,
                ),
            ],
        )

        high = report.get_by_severity(HookSeverity.HIGH)
        medium = report.get_by_severity(HookSeverity.MEDIUM)

        assert len(high) == 2
        assert len(medium) == 1

    def test_report_to_dict(self):
        """Test to_dict serialization."""
        report = ValidationReport(
            feature_slug="test-feature",
            results=[
                ValidationResult(
                    hook_name="h1", status=ValidationStatus.PASS, message="OK"
                ),
            ],
        )
        data = report.to_dict()

        assert data["feature_slug"] == "test-feature"
        assert data["total_count"] == 1
        assert data["passed_count"] == 1
        assert data["all_passed"] is True
        assert len(data["results"]) == 1

    def test_report_to_summary(self):
        """Test summary generation."""
        report = ValidationReport(
            feature_slug="test-feature",
            results=[
                ValidationResult(
                    hook_name="h1", status=ValidationStatus.PASS, message="OK"
                ),
                ValidationResult(
                    hook_name="h2",
                    status=ValidationStatus.FAIL,
                    message="Failed",
                    severity=HookSeverity.CRITICAL,
                ),
            ],
        )
        summary = report.to_summary()

        assert "test-feature" in summary
        assert "1/2 passed" in summary
        assert "[CRITICAL]" in summary


class TestValidationHook:
    """Test ValidationHook dataclass."""

    def test_hook_creation(self):
        """Test creating a validation hook."""

        def check_fn(path, state):
            return ValidationResult(
                hook_name="test", status=ValidationStatus.PASS, message="OK"
            )

        hook = ValidationHook(
            name="test_hook",
            description="Test validation",
            check_fn=check_fn,
            frequency=HookFrequency.ALWAYS,
            severity=HookSeverity.HIGH,
            category="test",
        )

        assert hook.name == "test_hook"
        assert hook.description == "Test validation"
        assert hook.frequency == HookFrequency.ALWAYS
        assert hook.severity == HookSeverity.HIGH
        assert hook.category == "test"


class TestBuiltInHooks:
    """Test built-in validation hooks."""

    @pytest.fixture
    def temp_feature_dir(self):
        """Create a temporary feature directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            feature_path = Path(tmpdir)
            yield feature_path

    @pytest.fixture
    def mock_state(self):
        """Create a mock feature state."""
        mock = MagicMock()
        mock.slug = "test-feature"
        mock.brain_entity = "[[Entities/Test_Feature]]"
        mock.context_file = "test-feature-context.md"
        mock.artifacts = {
            "figma": "https://www.figma.com/file/abc123",
            "jira_epic": None,
        }
        mock.tracks = {
            "context": MagicMock(status=MagicMock(value="complete")),
            "design": MagicMock(status=MagicMock(value="not_started")),
            "business_case": MagicMock(status=MagicMock(value="not_started")),
            "engineering": MagicMock(status=MagicMock(value="not_started")),
        }

        # Set up phase enum
        from context_engine.feature_state import FeaturePhase

        mock.current_phase = FeaturePhase.PARALLEL_TRACKS

        return mock

    def test_validate_brain_refs_no_state(self, temp_feature_dir):
        """Test brain refs validation with no state."""
        result = validate_brain_refs(temp_feature_dir, None)
        assert result.status == ValidationStatus.SKIP

    def test_validate_brain_refs_no_entity(self, temp_feature_dir, mock_state):
        """Test brain refs validation with no entity configured."""
        mock_state.brain_entity = None
        result = validate_brain_refs(temp_feature_dir, mock_state)
        assert result.status == ValidationStatus.WARN

    def test_validate_brain_refs_invalid_format(self, temp_feature_dir, mock_state):
        """Test brain refs validation with invalid format."""
        mock_state.brain_entity = "Invalid_Format"
        result = validate_brain_refs(temp_feature_dir, mock_state)
        assert result.status == ValidationStatus.WARN
        assert "non-standard" in result.message

    def test_validate_data_freshness_no_state(self, temp_feature_dir):
        """Test data freshness validation with no state."""
        result = validate_data_freshness(temp_feature_dir, None)
        assert result.status == ValidationStatus.SKIP

    def test_validate_data_freshness_no_file(self, temp_feature_dir, mock_state):
        """Test data freshness validation when state file doesn't exist."""
        result = validate_data_freshness(temp_feature_dir, mock_state)
        assert result.status == ValidationStatus.SKIP

    def test_validate_data_freshness_fresh_file(self, temp_feature_dir, mock_state):
        """Test data freshness validation with fresh file."""
        state_file = temp_feature_dir / "feature-state.yaml"
        state_file.write_text("slug: test")

        result = validate_data_freshness(temp_feature_dir, mock_state)
        assert result.status == ValidationStatus.PASS

    def test_validate_context_consistency_no_state(self, temp_feature_dir):
        """Test context consistency validation with no state."""
        result = validate_context_doc_consistency(temp_feature_dir, None)
        assert result.status == ValidationStatus.SKIP

    def test_validate_context_consistency_no_file_configured(
        self, temp_feature_dir, mock_state
    ):
        """Test context consistency when no file configured."""
        mock_state.context_file = None
        result = validate_context_doc_consistency(temp_feature_dir, mock_state)
        assert result.status == ValidationStatus.WARN

    def test_validate_context_consistency_file_missing(
        self, temp_feature_dir, mock_state
    ):
        """Test context consistency when file missing but should exist."""
        from context_engine.feature_state import TrackStatus

        mock_state.tracks["context"].status = TrackStatus.IN_PROGRESS

        result = validate_context_doc_consistency(temp_feature_dir, mock_state)
        assert result.status == ValidationStatus.FAIL
        assert result.severity == HookSeverity.HIGH

    def test_validate_context_consistency_file_exists(
        self, temp_feature_dir, mock_state
    ):
        """Test context consistency with valid file."""
        context_file = temp_feature_dir / "test-feature-context.md"
        context_file.write_text("""
# Test Feature Context

## Problem Statement
Users have trouble with X.

## Success Metrics
- Metric 1
- Metric 2

## Scope
In scope: A, B
Out of scope: C
""")

        result = validate_context_doc_consistency(temp_feature_dir, mock_state)
        assert result.status == ValidationStatus.PASS

    def test_validate_context_consistency_missing_sections(
        self, temp_feature_dir, mock_state
    ):
        """Test context consistency with missing sections."""
        context_file = temp_feature_dir / "test-feature-context.md"
        context_file.write_text("# Test Feature\n\nSome content.")

        result = validate_context_doc_consistency(temp_feature_dir, mock_state)
        assert result.status == ValidationStatus.WARN
        assert "missing sections" in result.message.lower()

    def test_validate_artifact_urls_no_state(self, temp_feature_dir):
        """Test artifact URL validation with no state."""
        result = validate_artifact_urls(temp_feature_dir, None)
        assert result.status == ValidationStatus.SKIP

    def test_validate_artifact_urls_valid_figma(self, temp_feature_dir, mock_state):
        """Test artifact URL validation with valid Figma URL."""
        result = validate_artifact_urls(temp_feature_dir, mock_state)
        assert result.status == ValidationStatus.PASS
        assert "1 artifact URL" in result.message

    def test_validate_artifact_urls_invalid_pattern(self, temp_feature_dir, mock_state):
        """Test artifact URL validation with invalid pattern."""
        mock_state.artifacts["figma"] = "not-a-valid-url"
        result = validate_artifact_urls(temp_feature_dir, mock_state)
        assert result.status == ValidationStatus.WARN
        assert "unexpected format" in result.message.lower()

    def test_validate_artifact_urls_no_artifacts(self, temp_feature_dir, mock_state):
        """Test artifact URL validation with no artifacts."""
        mock_state.artifacts = {}
        result = validate_artifact_urls(temp_feature_dir, mock_state)
        assert result.status == ValidationStatus.PASS
        assert "No artifact URLs" in result.message

    def test_validate_track_status_consistency_no_state(self, temp_feature_dir):
        """Test track status consistency with no state."""
        result = validate_track_status_consistency(temp_feature_dir, None)
        assert result.status == ValidationStatus.SKIP

    def test_validate_track_status_consistency_valid(
        self, temp_feature_dir, mock_state
    ):
        """Test track status consistency with valid state."""
        result = validate_track_status_consistency(temp_feature_dir, mock_state)
        assert result.status == ValidationStatus.PASS

    def test_validate_track_status_consistency_decision_gate_issues(
        self, temp_feature_dir, mock_state
    ):
        """Test track status consistency at decision gate with issues."""
        from context_engine.feature_state import FeaturePhase, TrackStatus

        mock_state.current_phase = FeaturePhase.DECISION_GATE
        mock_state.tracks["business_case"].status = TrackStatus.NOT_STARTED

        result = validate_track_status_consistency(temp_feature_dir, mock_state)
        assert result.status == ValidationStatus.WARN
        assert "business_case" in result.details


class TestValidationHookRunner:
    """Test ValidationHookRunner class."""

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
                        "context": {"status": "in_progress"},
                        "design": {"status": "not_started"},
                        "business_case": {"status": "not_started"},
                        "engineering": {"status": "not_started"},
                    },
                },
                "artifacts": {
                    "figma": "https://www.figma.com/file/test",
                },
            }

            with open(state_file, "w") as f:
                yaml.dump(state_data, f)

            yield feature_path

    def test_runner_initialization(self, temp_feature_dir):
        """Test runner initialization."""
        runner = ValidationHookRunner(temp_feature_dir)
        assert runner.feature_path == temp_feature_dir
        assert len(runner.hooks) == 5  # Default hooks

    def test_runner_custom_hooks(self, temp_feature_dir):
        """Test runner with custom hooks."""
        custom_hook = ValidationHook(
            name="custom",
            description="Custom hook",
            check_fn=lambda p, s: ValidationResult(
                hook_name="custom", status=ValidationStatus.PASS, message="OK"
            ),
        )
        runner = ValidationHookRunner(temp_feature_dir, hooks=[custom_hook])
        assert len(runner.hooks) == 1
        assert runner.hooks[0].name == "custom"

    def test_runner_register_hook(self, temp_feature_dir):
        """Test registering a hook."""
        runner = ValidationHookRunner(temp_feature_dir, hooks=[])
        assert len(runner.hooks) == 0

        runner.register_hook(
            ValidationHook(
                name="test",
                description="Test",
                check_fn=lambda p, s: ValidationResult(
                    hook_name="test", status=ValidationStatus.PASS, message="OK"
                ),
            )
        )
        assert len(runner.hooks) == 1

    def test_runner_unregister_hook(self, temp_feature_dir):
        """Test unregistering a hook."""
        runner = ValidationHookRunner(temp_feature_dir)
        initial_count = len(runner.hooks)

        result = runner.unregister_hook("brain_refs_valid")
        assert result is True
        assert len(runner.hooks) == initial_count - 1

        result = runner.unregister_hook("nonexistent")
        assert result is False

    def test_runner_get_hook(self, temp_feature_dir):
        """Test getting a hook by name."""
        runner = ValidationHookRunner(temp_feature_dir)

        hook = runner.get_hook("brain_refs_valid")
        assert hook is not None
        assert hook.name == "brain_refs_valid"

        hook = runner.get_hook("nonexistent")
        assert hook is None

    def test_runner_run_hook(self, temp_feature_dir):
        """Test running a specific hook."""
        runner = ValidationHookRunner(temp_feature_dir)
        result = runner.run_hook("artifact_urls_valid")

        assert result is not None
        assert result.hook_name == "artifact_urls_valid"

    def test_runner_run_hook_nonexistent(self, temp_feature_dir):
        """Test running a nonexistent hook."""
        runner = ValidationHookRunner(temp_feature_dir)
        result = runner.run_hook("nonexistent")
        assert result is None

    def test_runner_run_all(self, temp_feature_dir):
        """Test running all hooks."""
        runner = ValidationHookRunner(temp_feature_dir)
        results = runner.run_all()

        assert len(results) >= 1
        assert all(isinstance(r, ValidationResult) for r in results)

    def test_runner_run_by_category(self, temp_feature_dir):
        """Test running hooks by category."""
        runner = ValidationHookRunner(temp_feature_dir)
        results = runner.run_by_category("consistency")

        assert len(results) >= 1
        for result in results:
            assert result.metadata.get("category") == "consistency"

    def test_runner_run_by_severity(self, temp_feature_dir):
        """Test running hooks by severity."""
        runner = ValidationHookRunner(temp_feature_dir)
        results = runner.run_by_severity(HookSeverity.HIGH)

        # Should run HIGH and CRITICAL severity hooks
        assert len(results) >= 1

    def test_runner_generate_report(self, temp_feature_dir):
        """Test generating a validation report."""
        runner = ValidationHookRunner(temp_feature_dir)
        report = runner.generate_report()

        assert isinstance(report, ValidationReport)
        assert report.feature_slug == "test-feature"
        assert report.total_count >= 1

    def test_runner_has_critical_failures(self, temp_feature_dir):
        """Test checking for critical failures."""
        runner = ValidationHookRunner(temp_feature_dir)
        has_critical = runner.has_critical_failures()
        assert isinstance(has_critical, bool)

    def test_runner_is_valid(self, temp_feature_dir):
        """Test is_valid check."""
        runner = ValidationHookRunner(temp_feature_dir)
        is_valid = runner.is_valid()
        assert isinstance(is_valid, bool)

    def test_runner_frequency_skip(self, temp_feature_dir):
        """Test that hooks are skipped based on frequency."""
        # Create a hook with ON_DEMAND frequency
        on_demand_hook = ValidationHook(
            name="on_demand_test",
            description="On demand only",
            check_fn=lambda p, s: ValidationResult(
                hook_name="on_demand_test", status=ValidationStatus.PASS, message="OK"
            ),
            frequency=HookFrequency.ON_DEMAND,
        )

        runner = ValidationHookRunner(temp_feature_dir, hooks=[on_demand_hook])

        # Should skip without force
        result = runner.run_hook("on_demand_test", force=False)
        assert result.status == ValidationStatus.SKIP

        # Should run with force
        result = runner.run_hook("on_demand_test", force=True)
        assert result.status == ValidationStatus.PASS


class TestConvenienceFunctions:
    """Test convenience functions."""

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

    def test_run_validation_hooks_function(self, temp_feature_dir):
        """Test run_validation_hooks convenience function."""
        results = run_validation_hooks(temp_feature_dir)
        assert isinstance(results, list)
        assert all(isinstance(r, ValidationResult) for r in results)

    def test_get_validation_report_function(self, temp_feature_dir):
        """Test get_validation_report convenience function."""
        report = get_validation_report(temp_feature_dir)
        assert isinstance(report, ValidationReport)
        assert report.feature_slug == "test-feature"

    def test_is_feature_valid_function(self, temp_feature_dir):
        """Test is_feature_valid convenience function."""
        result = is_feature_valid(temp_feature_dir)
        assert isinstance(result, bool)


class TestFormatValidationResults:
    """Test format_validation_results function."""

    def test_format_empty_results(self):
        """Test formatting empty results."""
        result = format_validation_results([])
        assert result == "No validation results"

    def test_format_all_passed(self):
        """Test formatting when all passed."""
        results = [
            ValidationResult(
                hook_name="h1", status=ValidationStatus.PASS, message="OK"
            ),
            ValidationResult(
                hook_name="h2", status=ValidationStatus.PASS, message="OK"
            ),
        ]
        result = format_validation_results(results, include_passed=False)
        assert result == "All validations passed"

    def test_format_with_failures(self):
        """Test formatting with failures."""
        results = [
            ValidationResult(
                hook_name="h1",
                status=ValidationStatus.FAIL,
                message="Something failed",
                severity=HookSeverity.HIGH,
                remediation="Fix it",
            ),
            ValidationResult(
                hook_name="h2", status=ValidationStatus.PASS, message="OK"
            ),
        ]
        result = format_validation_results(results)

        assert "[FAIL]" in result
        assert "[HIGH]" in result
        assert "Something failed" in result
        assert "Fix it" in result

    def test_format_include_passed(self):
        """Test formatting with passed results included."""
        results = [
            ValidationResult(
                hook_name="h1", status=ValidationStatus.PASS, message="OK"
            ),
            ValidationResult(
                hook_name="h2",
                status=ValidationStatus.FAIL,
                message="Failed",
                severity=HookSeverity.LOW,
            ),
        ]
        result = format_validation_results(results, include_passed=True)

        assert "[PASS]" in result
        assert "[FAIL]" in result


class TestDefaultHooks:
    """Test get_default_hooks function."""

    def test_default_hooks_exist(self):
        """Test that default hooks are returned."""
        hooks = get_default_hooks()
        assert len(hooks) == 5

    def test_default_hook_names(self):
        """Test default hook names."""
        hooks = get_default_hooks()
        names = {h.name for h in hooks}

        assert "brain_refs_valid" in names
        assert "data_freshness" in names
        assert "context_consistency" in names
        assert "artifact_urls_valid" in names
        assert "track_status_consistency" in names

    def test_default_hook_categories(self):
        """Test default hook categories."""
        hooks = get_default_hooks()
        categories = {h.category for h in hooks}

        assert "brain" in categories
        assert "data" in categories
        assert "consistency" in categories
        assert "artifacts" in categories


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
