"""
Continuous Validation Hooks for Context Creation Engine

Provides a framework for running continuous validation checks on features including:
- Brain entity reference validation (linked entities exist)
- Source data freshness (Master Sheet data not stale, insights current)
- Context document internal consistency (sections match feature-state.yaml)
- Artifact URL validity (basic pattern checks)

Hooks can be run on-demand or scheduled at different frequencies.

Usage:
    from tools.context_engine.validation_hooks import (
        ValidationHookRunner,
        ValidationResult,
        HookSeverity,
        HookFrequency,
        get_default_hooks,
    )

    # Run all validation hooks for a feature
    runner = ValidationHookRunner(feature_path)
    results = runner.run_all()

    # Run specific hook
    result = runner.run_hook("brain_refs_valid")

    # Filter by severity
    critical = runner.get_failed_by_severity(HookSeverity.CRITICAL)

    # Register custom hook
    runner.register_hook(my_custom_hook)

PRD References:
    - Section A.1: Quality gates and validation
    - Section C.4: Feature state tracking
    - Section D.2: Brain entity integration
"""

import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logger = logging.getLogger(__name__)


class HookSeverity(Enum):
    """Severity levels for validation hook failures."""

    CRITICAL = "critical"  # Blocks all operations
    HIGH = "high"  # Should be fixed soon
    MEDIUM = "medium"  # Should be addressed
    LOW = "low"  # Advisory only


class HookFrequency(Enum):
    """How often a validation hook should run."""

    ALWAYS = "always"  # Run on every check
    HOURLY = "hourly"  # Run if >1 hour since last check
    DAILY = "daily"  # Run if >24 hours since last check
    ON_DEMAND = "on_demand"  # Only run when explicitly requested


class ValidationStatus(Enum):
    """Status of a validation hook result."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"  # Skipped (e.g., not applicable)
    ERROR = "error"  # Hook execution error


@dataclass
class ValidationResult:
    """
    Result of a single validation hook execution.

    Attributes:
        hook_name: Identifier for the hook
        status: Pass/fail/warn/skip/error status
        message: Human-readable description of the result
        severity: Severity level if the check failed
        details: Additional details about what was checked
        remediation: Suggested action to fix the issue
        checked_at: When the validation was performed
        metadata: Additional structured data
    """

    hook_name: str
    status: ValidationStatus
    message: str
    severity: HookSeverity = HookSeverity.MEDIUM
    details: Optional[str] = None
    remediation: Optional[str] = None
    checked_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Check if validation passed (pass or warn)."""
        return self.status in (ValidationStatus.PASS, ValidationStatus.WARN)

    @property
    def failed(self) -> bool:
        """Check if validation failed."""
        return self.status == ValidationStatus.FAIL

    @property
    def is_critical(self) -> bool:
        """Check if this is a critical failure."""
        return (
            self.status == ValidationStatus.FAIL
            and self.severity == HookSeverity.CRITICAL
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "hook_name": self.hook_name,
            "status": self.status.value,
            "message": self.message,
            "severity": self.severity.value,
            "checked_at": self.checked_at.isoformat(),
        }
        if self.details:
            result["details"] = self.details
        if self.remediation:
            result["remediation"] = self.remediation
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationResult":
        """Create from dictionary."""
        checked_at = data.get("checked_at")
        if isinstance(checked_at, str):
            checked_at = datetime.fromisoformat(checked_at)
        elif not isinstance(checked_at, datetime):
            checked_at = datetime.now()

        return cls(
            hook_name=data["hook_name"],
            status=ValidationStatus(data["status"]),
            message=data["message"],
            severity=HookSeverity(data.get("severity", "medium")),
            details=data.get("details"),
            remediation=data.get("remediation"),
            checked_at=checked_at,
            metadata=data.get("metadata", {}),
        )


@dataclass
class ValidationHook:
    """
    Definition of a validation hook.

    Attributes:
        name: Unique identifier for the hook
        description: Human-readable description of what this hook validates
        check_fn: Function that performs the validation
        frequency: How often this hook should run
        severity: Severity level if this check fails
        category: Category for grouping hooks (brain, data, consistency, artifacts)
    """

    name: str
    description: str
    check_fn: Callable[[Path, Optional["FeatureState"]], ValidationResult]
    frequency: HookFrequency = HookFrequency.ALWAYS
    severity: HookSeverity = HookSeverity.MEDIUM
    category: str = "general"


@dataclass
class ValidationReport:
    """
    Aggregated validation results for a feature.

    Attributes:
        feature_slug: The feature this report is for
        results: List of all validation results
        generated_at: When the report was generated
    """

    feature_slug: str
    results: List[ValidationResult] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def total_count(self) -> int:
        """Total number of validations run."""
        return len(self.results)

    @property
    def passed_count(self) -> int:
        """Number of passed validations."""
        return sum(1 for r in self.results if r.passed)

    @property
    def failed_count(self) -> int:
        """Number of failed validations."""
        return sum(1 for r in self.results if r.failed)

    @property
    def critical_count(self) -> int:
        """Number of critical failures."""
        return sum(1 for r in self.results if r.is_critical)

    @property
    def all_passed(self) -> bool:
        """Check if all validations passed."""
        return all(r.passed for r in self.results)

    @property
    def has_critical_failures(self) -> bool:
        """Check if any critical failures exist."""
        return any(r.is_critical for r in self.results)

    def get_by_status(self, status: ValidationStatus) -> List[ValidationResult]:
        """Get results filtered by status."""
        return [r for r in self.results if r.status == status]

    def get_by_severity(self, severity: HookSeverity) -> List[ValidationResult]:
        """Get failed results filtered by severity."""
        return [r for r in self.results if r.failed and r.severity == severity]

    def get_by_category(self, category: str) -> List[ValidationResult]:
        """Get results filtered by category."""
        return [r for r in self.results if r.metadata.get("category") == category]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "feature_slug": self.feature_slug,
            "generated_at": self.generated_at.isoformat(),
            "total_count": self.total_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "critical_count": self.critical_count,
            "all_passed": self.all_passed,
            "results": [r.to_dict() for r in self.results],
        }

    def to_summary(self) -> str:
        """Generate a human-readable summary."""
        if self.all_passed:
            return f"All {self.total_count} validations passed for {self.feature_slug}"

        lines = [
            f"Validation results for {self.feature_slug}: {self.passed_count}/{self.total_count} passed"
        ]
        if self.critical_count > 0:
            lines.append(f"  [CRITICAL] {self.critical_count} critical failure(s)")

        failed = self.get_by_status(ValidationStatus.FAIL)
        for result in failed[:5]:  # Show first 5 failures
            lines.append(f"  - [{result.severity.value.upper()}] {result.message}")

        if len(failed) > 5:
            lines.append(f"  ... and {len(failed) - 5} more failures")

        return "\n".join(lines)


# ========== Built-in Validation Hooks ==========


def validate_brain_refs(
    feature_path: Path, state: Optional["FeatureState"]
) -> ValidationResult:
    """
    Validate that brain entity references are valid.

    Checks that the brain_entity referenced in feature-state.yaml
    actually exists in user/brain/Entities/.
    """
    if state is None:
        return ValidationResult(
            hook_name="brain_refs_valid",
            status=ValidationStatus.SKIP,
            message="No feature state found",
            metadata={"category": "brain"},
        )

    brain_ref = state.brain_entity
    if not brain_ref:
        return ValidationResult(
            hook_name="brain_refs_valid",
            status=ValidationStatus.WARN,
            message="No brain entity reference configured",
            severity=HookSeverity.LOW,
            remediation="Add brain_entity field to feature-state.yaml",
            metadata={"category": "brain"},
        )

    # Extract entity name from wikilink format [[Entities/Name]]
    match = re.match(r"\[\[Entities/([^\]]+)\]\]", brain_ref)
    if not match:
        return ValidationResult(
            hook_name="brain_refs_valid",
            status=ValidationStatus.WARN,
            message=f"Brain entity reference format is non-standard: {brain_ref}",
            severity=HookSeverity.LOW,
            details="Expected format: [[Entities/Entity_Name]]",
            metadata={"category": "brain", "brain_ref": brain_ref},
        )

    entity_name = match.group(1)

    # Find user/brain/Entities directory
    # Walk up from feature_path to find pm-os root
    current = feature_path
    brain_entities_path = None
    for _ in range(10):  # Limit search depth
        potential_path = current / "user" / "brain" / "Entities"
        if potential_path.exists():
            brain_entities_path = potential_path
            break
        current = current.parent
        if current == current.parent:
            break

    if brain_entities_path is None:
        # Try relative from common tools location
        try:
            import config_loader

            config = config_loader.get_config()
            brain_entities_path = Path(config.user_path) / "brain" / "Entities"
        except ImportError:
            brain_entities_path = None

    if brain_entities_path is None or not brain_entities_path.exists():
        return ValidationResult(
            hook_name="brain_refs_valid",
            status=ValidationStatus.SKIP,
            message="Could not locate brain Entities directory",
            metadata={"category": "brain"},
        )

    # Check if entity file exists
    entity_file = brain_entities_path / f"{entity_name}.md"
    if entity_file.exists():
        return ValidationResult(
            hook_name="brain_refs_valid",
            status=ValidationStatus.PASS,
            message=f"Brain entity exists: {entity_name}",
            details=str(entity_file),
            metadata={"category": "brain", "entity_name": entity_name},
        )
    else:
        return ValidationResult(
            hook_name="brain_refs_valid",
            status=ValidationStatus.FAIL,
            message=f"Brain entity does not exist: {entity_name}",
            severity=HookSeverity.MEDIUM,
            details=f"Expected file: {entity_file}",
            remediation=f"Create brain entity file at user/brain/Entities/{entity_name}.md",
            metadata={
                "category": "brain",
                "entity_name": entity_name,
                "expected_path": str(entity_file),
            },
        )


def validate_data_freshness(
    feature_path: Path, state: Optional["FeatureState"]
) -> ValidationResult:
    """
    Validate source data freshness.

    Checks:
    - Feature state file was updated recently (within 7 days for active features)
    - Master Sheet row is still valid (if configured)
    """
    if state is None:
        return ValidationResult(
            hook_name="data_freshness",
            status=ValidationStatus.SKIP,
            message="No feature state found",
            metadata={"category": "data"},
        )

    # Check feature-state.yaml modification time
    state_file = feature_path / "feature-state.yaml"
    if not state_file.exists():
        return ValidationResult(
            hook_name="data_freshness",
            status=ValidationStatus.SKIP,
            message="Feature state file not found",
            metadata={"category": "data"},
        )

    # Get file modification time
    mtime = datetime.fromtimestamp(state_file.stat().st_mtime)
    age_days = (datetime.now() - mtime).days

    # Check if feature is complete (complete features don't need freshness checks)
    from .feature_state import FeaturePhase

    if state.current_phase in (
        FeaturePhase.COMPLETE,
        FeaturePhase.ARCHIVED,
        FeaturePhase.DEFERRED,
    ):
        return ValidationResult(
            hook_name="data_freshness",
            status=ValidationStatus.PASS,
            message=f"Feature is {state.current_phase.value}, freshness check not required",
            metadata={"category": "data", "phase": state.current_phase.value},
        )

    # For active features, warn if state is older than 7 days
    if age_days > 7:
        return ValidationResult(
            hook_name="data_freshness",
            status=ValidationStatus.WARN,
            message=f"Feature state not updated in {age_days} days",
            severity=HookSeverity.LOW,
            details=f"Last modified: {mtime.isoformat()}",
            remediation="Review and update feature state if still active",
            metadata={
                "category": "data",
                "age_days": age_days,
                "last_modified": mtime.isoformat(),
            },
        )

    # For features not touched in 30+ days, this is more serious
    if age_days > 30:
        return ValidationResult(
            hook_name="data_freshness",
            status=ValidationStatus.FAIL,
            message=f"Feature state stale ({age_days} days old)",
            severity=HookSeverity.MEDIUM,
            details=f"Last modified: {mtime.isoformat()}",
            remediation="Update feature status or archive if no longer active",
            metadata={
                "category": "data",
                "age_days": age_days,
                "last_modified": mtime.isoformat(),
            },
        )

    return ValidationResult(
        hook_name="data_freshness",
        status=ValidationStatus.PASS,
        message=f"Feature state is fresh ({age_days} days old)",
        metadata={"category": "data", "age_days": age_days},
    )


def validate_context_doc_consistency(
    feature_path: Path, state: Optional["FeatureState"]
) -> ValidationResult:
    """
    Validate context document internal consistency.

    Checks that:
    - Context file referenced in state exists
    - Context document sections match expected structure
    - Context track status matches document presence
    """
    if state is None:
        return ValidationResult(
            hook_name="context_consistency",
            status=ValidationStatus.SKIP,
            message="No feature state found",
            metadata={"category": "consistency"},
        )

    context_file_name = state.context_file
    if not context_file_name:
        return ValidationResult(
            hook_name="context_consistency",
            status=ValidationStatus.WARN,
            message="No context file configured in feature state",
            severity=HookSeverity.MEDIUM,
            remediation="Set context_file field in feature-state.yaml",
            metadata={"category": "consistency"},
        )

    # Check if context file exists
    context_file = feature_path / context_file_name
    if not context_file.exists():
        # Also check in context-docs subdirectory
        context_docs_dir = feature_path / "context-docs"
        if context_docs_dir.exists():
            context_file = context_docs_dir / context_file_name

    if not context_file.exists():
        # Check if context track says it should exist
        context_track = state.tracks.get("context")
        from .feature_state import TrackStatus

        if context_track and context_track.status != TrackStatus.NOT_STARTED:
            return ValidationResult(
                hook_name="context_consistency",
                status=ValidationStatus.FAIL,
                message=f"Context file missing: {context_file_name}",
                severity=HookSeverity.HIGH,
                details=f"Context track status is {context_track.status.value} but file not found",
                remediation=f"Create context document at {feature_path}/{context_file_name}",
                metadata={
                    "category": "consistency",
                    "expected_file": context_file_name,
                },
            )
        else:
            return ValidationResult(
                hook_name="context_consistency",
                status=ValidationStatus.PASS,
                message="Context file not yet created (context track not started)",
                metadata={"category": "consistency"},
            )

    # Context file exists - validate basic structure
    try:
        content = context_file.read_text()

        # Check for key sections
        required_sections = ["Problem Statement", "Success Metrics", "Scope"]
        missing_sections = []
        for section in required_sections:
            if section.lower() not in content.lower():
                missing_sections.append(section)

        if missing_sections:
            return ValidationResult(
                hook_name="context_consistency",
                status=ValidationStatus.WARN,
                message=f"Context document missing sections: {', '.join(missing_sections)}",
                severity=HookSeverity.LOW,
                details=f"File: {context_file}",
                remediation=f"Add missing sections to context document: {', '.join(missing_sections)}",
                metadata={
                    "category": "consistency",
                    "missing_sections": missing_sections,
                },
            )

        return ValidationResult(
            hook_name="context_consistency",
            status=ValidationStatus.PASS,
            message="Context document structure is valid",
            details=f"File: {context_file}",
            metadata={"category": "consistency"},
        )

    except Exception as e:
        return ValidationResult(
            hook_name="context_consistency",
            status=ValidationStatus.ERROR,
            message=f"Error reading context file: {e}",
            metadata={"category": "consistency", "error": str(e)},
        )


def validate_artifact_urls(
    feature_path: Path, state: Optional["FeatureState"]
) -> ValidationResult:
    """
    Validate artifact URL patterns.

    Checks that artifact URLs match expected patterns:
    - Figma URLs should contain figma.com
    - Jira URLs should contain atlassian.net or jira domain
    - Confluence URLs should contain atlassian.net/wiki
    """
    if state is None:
        return ValidationResult(
            hook_name="artifact_urls_valid",
            status=ValidationStatus.SKIP,
            message="No feature state found",
            metadata={"category": "artifacts"},
        )

    artifacts = state.artifacts or {}

    # Define URL patterns for each artifact type
    url_patterns = {
        "figma": r"https?://.*figma\.com",
        "jira_epic": r"https?://.*\.(atlassian\.net|jira\.).*",
        "confluence_page": r"https?://.*atlassian\.net/wiki.*|https?://.*confluence\.",
        "wireframes_url": r"https?://",  # Basic URL check
    }

    invalid_urls = []
    valid_count = 0
    checked_count = 0

    for artifact_type, url in artifacts.items():
        if not url:
            continue

        checked_count += 1
        pattern = url_patterns.get(artifact_type, r"https?://")

        if re.match(pattern, url, re.IGNORECASE):
            valid_count += 1
        else:
            invalid_urls.append(
                {
                    "type": artifact_type,
                    "url": url,
                    "expected_pattern": pattern,
                }
            )

    if not checked_count:
        return ValidationResult(
            hook_name="artifact_urls_valid",
            status=ValidationStatus.PASS,
            message="No artifact URLs to validate",
            metadata={"category": "artifacts"},
        )

    if invalid_urls:
        return ValidationResult(
            hook_name="artifact_urls_valid",
            status=ValidationStatus.WARN,
            message=f"{len(invalid_urls)} artifact URL(s) have unexpected format",
            severity=HookSeverity.LOW,
            details=", ".join(f"{u['type']}: {u['url']}" for u in invalid_urls),
            remediation="Verify artifact URLs are correct and accessible",
            metadata={
                "category": "artifacts",
                "invalid_urls": invalid_urls,
                "valid_count": valid_count,
            },
        )

    return ValidationResult(
        hook_name="artifact_urls_valid",
        status=ValidationStatus.PASS,
        message=f"All {valid_count} artifact URL(s) have valid patterns",
        metadata={"category": "artifacts", "valid_count": valid_count},
    )


def validate_track_status_consistency(
    feature_path: Path, state: Optional["FeatureState"]
) -> ValidationResult:
    """
    Validate track status consistency with phase.

    Checks that track statuses are consistent with the current phase:
    - In decision_gate, tracks should not be not_started
    - Complete tracks should have required artifacts
    """
    if state is None:
        return ValidationResult(
            hook_name="track_status_consistency",
            status=ValidationStatus.SKIP,
            message="No feature state found",
            metadata={"category": "consistency"},
        )

    from .feature_state import FeaturePhase, TrackStatus

    issues = []

    # Check for phase-track consistency
    if state.current_phase == FeaturePhase.DECISION_GATE:
        for track_name, track in state.tracks.items():
            if track.status == TrackStatus.NOT_STARTED and track_name != "design":
                issues.append(
                    f"{track_name} track not started but feature is at decision gate"
                )

    if state.current_phase == FeaturePhase.OUTPUT_GENERATION:
        for track_name, track in state.tracks.items():
            if track.status not in (TrackStatus.COMPLETE, TrackStatus.NOT_STARTED):
                if track_name != "design":  # Design can be parallel
                    issues.append(
                        f"{track_name} track incomplete ({track.status.value}) at output generation"
                    )

    if issues:
        return ValidationResult(
            hook_name="track_status_consistency",
            status=ValidationStatus.WARN,
            message=f"{len(issues)} track status inconsistency(ies) found",
            severity=HookSeverity.MEDIUM,
            details="; ".join(issues),
            remediation="Update track statuses or phase to be consistent",
            metadata={"category": "consistency", "issues": issues},
        )

    return ValidationResult(
        hook_name="track_status_consistency",
        status=ValidationStatus.PASS,
        message="Track statuses are consistent with current phase",
        metadata={"category": "consistency", "phase": state.current_phase.value},
    )


# ========== Validation Hook Runner ==========


class ValidationHookRunner:
    """
    Runs validation hooks for a feature.

    Usage:
        runner = ValidationHookRunner(feature_path)
        results = runner.run_all()

        # Run specific hook
        result = runner.run_hook("brain_refs_valid")

        # Register custom hook
        runner.register_hook(my_hook)
    """

    def __init__(
        self, feature_path: Path, hooks: Optional[List[ValidationHook]] = None
    ):
        """
        Initialize the validation hook runner.

        Args:
            feature_path: Path to the feature folder
            hooks: Optional list of hooks to use (uses defaults if None)
        """
        self.feature_path = Path(feature_path)
        self._hooks: Dict[str, ValidationHook] = {}
        self._state: Optional["FeatureState"] = None
        self._last_run: Dict[str, datetime] = {}

        # Register default hooks if none provided
        if hooks is None:
            for hook in get_default_hooks():
                self.register_hook(hook)
        else:
            for hook in hooks:
                self.register_hook(hook)

    def _load_state(self) -> Optional["FeatureState"]:
        """Load feature state if not already loaded."""
        if self._state is None:
            from .feature_state import FeatureState

            self._state = FeatureState.load(self.feature_path)
        return self._state

    @property
    def state(self) -> Optional["FeatureState"]:
        """Get feature state (loaded on first access)."""
        return self._load_state()

    @property
    def hooks(self) -> List[ValidationHook]:
        """Get list of registered hooks."""
        return list(self._hooks.values())

    def register_hook(self, hook: ValidationHook) -> None:
        """
        Register a validation hook.

        Args:
            hook: ValidationHook to register
        """
        self._hooks[hook.name] = hook

    def unregister_hook(self, name: str) -> bool:
        """
        Unregister a validation hook by name.

        Args:
            name: Name of the hook to remove

        Returns:
            True if hook was removed, False if not found
        """
        if name in self._hooks:
            del self._hooks[name]
            return True
        return False

    def get_hook(self, name: str) -> Optional[ValidationHook]:
        """
        Get a hook by name.

        Args:
            name: Name of the hook

        Returns:
            ValidationHook or None if not found
        """
        return self._hooks.get(name)

    def _should_run_hook(self, hook: ValidationHook, force: bool = False) -> bool:
        """
        Check if a hook should run based on its frequency.

        Args:
            hook: The hook to check
            force: If True, ignore frequency settings

        Returns:
            True if the hook should run
        """
        if force:
            return True

        if hook.frequency == HookFrequency.ALWAYS:
            return True

        if hook.frequency == HookFrequency.ON_DEMAND:
            return force

        last_run = self._last_run.get(hook.name)
        if last_run is None:
            return True

        now = datetime.now()
        if hook.frequency == HookFrequency.HOURLY:
            return (now - last_run) > timedelta(hours=1)
        elif hook.frequency == HookFrequency.DAILY:
            return (now - last_run) > timedelta(days=1)

        return True

    def run_hook(self, name: str, force: bool = False) -> Optional[ValidationResult]:
        """
        Run a specific hook by name.

        Args:
            name: Name of the hook to run
            force: If True, run regardless of frequency

        Returns:
            ValidationResult or None if hook not found
        """
        hook = self._hooks.get(name)
        if hook is None:
            return None

        if not self._should_run_hook(hook, force):
            return ValidationResult(
                hook_name=name,
                status=ValidationStatus.SKIP,
                message=f"Skipped due to frequency setting ({hook.frequency.value})",
                metadata={"category": hook.category, "skipped_reason": "frequency"},
            )

        try:
            result = hook.check_fn(self.feature_path, self.state)
            result.metadata["category"] = hook.category
            self._last_run[name] = datetime.now()
            return result
        except Exception as e:
            logger.error(f"Error running validation hook '{name}': {e}")
            return ValidationResult(
                hook_name=name,
                status=ValidationStatus.ERROR,
                message=f"Hook execution error: {e}",
                metadata={"category": hook.category, "error": str(e)},
            )

    def run_all(self, force: bool = False) -> List[ValidationResult]:
        """
        Run all registered hooks.

        Args:
            force: If True, run all hooks regardless of frequency

        Returns:
            List of ValidationResults
        """
        results = []
        for hook in self._hooks.values():
            result = self.run_hook(hook.name, force)
            if result:
                results.append(result)
        return results

    def run_by_category(
        self, category: str, force: bool = False
    ) -> List[ValidationResult]:
        """
        Run all hooks in a specific category.

        Args:
            category: Category to filter by (brain, data, consistency, artifacts)
            force: If True, run regardless of frequency

        Returns:
            List of ValidationResults
        """
        results = []
        for hook in self._hooks.values():
            if hook.category == category:
                result = self.run_hook(hook.name, force)
                if result:
                    results.append(result)
        return results

    def run_by_severity(
        self, severity: HookSeverity, force: bool = False
    ) -> List[ValidationResult]:
        """
        Run all hooks at or above a specific severity level.

        Args:
            severity: Minimum severity level to include
            force: If True, run regardless of frequency

        Returns:
            List of ValidationResults
        """
        severity_order = [
            HookSeverity.CRITICAL,
            HookSeverity.HIGH,
            HookSeverity.MEDIUM,
            HookSeverity.LOW,
        ]
        min_index = severity_order.index(severity)
        target_severities = set(severity_order[: min_index + 1])

        results = []
        for hook in self._hooks.values():
            if hook.severity in target_severities:
                result = self.run_hook(hook.name, force)
                if result:
                    results.append(result)
        return results

    def generate_report(self, force: bool = False) -> ValidationReport:
        """
        Run all hooks and generate a validation report.

        Args:
            force: If True, run all hooks regardless of frequency

        Returns:
            ValidationReport with all results
        """
        results = self.run_all(force)
        slug = self.state.slug if self.state else self.feature_path.name

        return ValidationReport(
            feature_slug=slug,
            results=results,
            generated_at=datetime.now(),
        )

    def get_failed_by_severity(self, severity: HookSeverity) -> List[ValidationResult]:
        """
        Get failed results at a specific severity level.

        Runs all hooks and returns only failures at the specified severity.

        Args:
            severity: Severity level to filter

        Returns:
            List of failed ValidationResults at the specified severity
        """
        results = self.run_all()
        return [r for r in results if r.failed and r.severity == severity]

    def has_critical_failures(self) -> bool:
        """
        Check if any critical validation failures exist.

        Returns:
            True if any critical failures
        """
        results = self.run_all()
        return any(r.is_critical for r in results)

    def is_valid(self) -> bool:
        """
        Check if all validations pass.

        Returns:
            True if all validations pass (no failures)
        """
        results = self.run_all()
        return all(r.passed or r.status == ValidationStatus.SKIP for r in results)


# ========== Default Hooks Factory ==========


def get_default_hooks() -> List[ValidationHook]:
    """
    Get the default set of validation hooks.

    Returns:
        List of default ValidationHooks
    """
    return [
        ValidationHook(
            name="brain_refs_valid",
            description="Validate brain entity references exist",
            check_fn=validate_brain_refs,
            frequency=HookFrequency.DAILY,
            severity=HookSeverity.MEDIUM,
            category="brain",
        ),
        ValidationHook(
            name="data_freshness",
            description="Check source data freshness",
            check_fn=validate_data_freshness,
            frequency=HookFrequency.DAILY,
            severity=HookSeverity.LOW,
            category="data",
        ),
        ValidationHook(
            name="context_consistency",
            description="Validate context document consistency with state",
            check_fn=validate_context_doc_consistency,
            frequency=HookFrequency.ALWAYS,
            severity=HookSeverity.HIGH,
            category="consistency",
        ),
        ValidationHook(
            name="artifact_urls_valid",
            description="Validate artifact URL patterns",
            check_fn=validate_artifact_urls,
            frequency=HookFrequency.ALWAYS,
            severity=HookSeverity.LOW,
            category="artifacts",
        ),
        ValidationHook(
            name="track_status_consistency",
            description="Validate track status consistency with phase",
            check_fn=validate_track_status_consistency,
            frequency=HookFrequency.ALWAYS,
            severity=HookSeverity.MEDIUM,
            category="consistency",
        ),
    ]


# ========== Convenience Functions ==========


def run_validation_hooks(
    feature_path: Path, force: bool = False
) -> List[ValidationResult]:
    """
    Convenience function to run all validation hooks for a feature.

    Args:
        feature_path: Path to the feature folder
        force: If True, run all hooks regardless of frequency

    Returns:
        List of ValidationResults
    """
    runner = ValidationHookRunner(feature_path)
    return runner.run_all(force)


def get_validation_report(feature_path: Path, force: bool = False) -> ValidationReport:
    """
    Convenience function to generate a validation report.

    Args:
        feature_path: Path to the feature folder
        force: If True, run all hooks regardless of frequency

    Returns:
        ValidationReport with all results
    """
    runner = ValidationHookRunner(feature_path)
    return runner.generate_report(force)


def is_feature_valid(feature_path: Path) -> bool:
    """
    Convenience function to check if a feature passes all validations.

    Args:
        feature_path: Path to the feature folder

    Returns:
        True if all validations pass
    """
    runner = ValidationHookRunner(feature_path)
    return runner.is_valid()


def format_validation_results(
    results: List[ValidationResult], include_passed: bool = False
) -> str:
    """
    Format validation results for display.

    Args:
        results: List of ValidationResults to format
        include_passed: If True, include passed results

    Returns:
        Formatted string
    """
    if not results:
        return "No validation results"

    lines = []
    status_order = [
        ValidationStatus.FAIL,
        ValidationStatus.ERROR,
        ValidationStatus.WARN,
        ValidationStatus.PASS,
        ValidationStatus.SKIP,
    ]

    for status in status_order:
        status_results = [r for r in results if r.status == status]
        if not status_results:
            continue

        if status == ValidationStatus.PASS and not include_passed:
            continue

        if status == ValidationStatus.SKIP:
            continue

        status_label = {
            ValidationStatus.FAIL: "[FAIL]",
            ValidationStatus.ERROR: "[ERROR]",
            ValidationStatus.WARN: "[WARN]",
            ValidationStatus.PASS: "[PASS]",
        }.get(status, f"[{status.value.upper()}]")

        lines.append(f"\n{status_label}")
        for r in status_results:
            severity_tag = f"[{r.severity.value.upper()}]" if r.failed else ""
            lines.append(f"  {severity_tag} {r.message}")
            if r.remediation and r.failed:
                lines.append(f"      Remediation: {r.remediation}")

    if not lines:
        return "All validations passed"

    return "\n".join(lines)
