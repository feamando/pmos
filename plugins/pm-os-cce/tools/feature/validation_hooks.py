"""
PM-OS CCE Validation Hooks (v5.0)

Continuous validation framework for features. Runs checks on Brain entity
references, data freshness, context document consistency, artifact URLs,
track status consistency, and discovery completeness.

Usage:
    from pm_os_cce.tools.feature.validation_hooks import ValidationHookRunner, ValidationResult
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from core.config_loader import get_config
    except ImportError:
        get_config = None

logger = logging.getLogger(__name__)


class HookSeverity(Enum):
    """Severity levels for validation hook failures."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class HookFrequency(Enum):
    """How often a validation hook should run."""

    ALWAYS = "always"
    HOURLY = "hourly"
    DAILY = "daily"
    ON_DEMAND = "on_demand"


class ValidationStatus(Enum):
    """Status of a validation hook result."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class ValidationResult:
    """Result of a single validation hook execution."""

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
    """Definition of a validation hook."""

    name: str
    description: str
    check_fn: Callable[[Path, Optional[Any]], ValidationResult]
    frequency: HookFrequency = HookFrequency.ALWAYS
    severity: HookSeverity = HookSeverity.MEDIUM
    category: str = "general"


@dataclass
class ValidationReport:
    """Aggregated validation results for a feature."""

    feature_slug: str
    results: List[ValidationResult] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def total_count(self) -> int:
        return len(self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if r.failed)

    @property
    def critical_count(self) -> int:
        return sum(1 for r in self.results if r.is_critical)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def has_critical_failures(self) -> bool:
        return any(r.is_critical for r in self.results)

    def get_by_status(self, status: ValidationStatus) -> List[ValidationResult]:
        return [r for r in self.results if r.status == status]

    def get_by_severity(self, severity: HookSeverity) -> List[ValidationResult]:
        return [r for r in self.results if r.failed and r.severity == severity]

    def get_by_category(self, category: str) -> List[ValidationResult]:
        return [r for r in self.results if r.metadata.get("category") == category]

    def to_dict(self) -> Dict[str, Any]:
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
        if self.all_passed:
            return f"All {self.total_count} validations passed for {self.feature_slug}"

        lines = [
            f"Validation results for {self.feature_slug}: {self.passed_count}/{self.total_count} passed"
        ]
        if self.critical_count > 0:
            lines.append(f"  [CRITICAL] {self.critical_count} critical failure(s)")

        failed = self.get_by_status(ValidationStatus.FAIL)
        for result in failed[:5]:
            lines.append(f"  - [{result.severity.value.upper()}] {result.message}")

        if len(failed) > 5:
            lines.append(f"  ... and {len(failed) - 5} more failures")

        return "\n".join(lines)


# ========== Built-in Validation Hooks ==========


def validate_brain_refs(
    feature_path: Path, state: Optional[Any] = None
) -> ValidationResult:
    """Validate that brain entity references are valid."""
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

    # Find brain Entities directory via config
    brain_entities_path = None
    if get_config is not None:
        try:
            config = get_config()
            user_path = Path(config.user_path) if hasattr(config, "user_path") else None
            if user_path:
                brain_entities_path = user_path / "brain" / "Entities"
        except Exception:
            pass

    # Fallback: walk up from feature_path
    if brain_entities_path is None or not brain_entities_path.exists():
        current = feature_path
        for _ in range(10):
            potential_path = current / "user" / "brain" / "Entities"
            if potential_path.exists():
                brain_entities_path = potential_path
                break
            current = current.parent
            if current == current.parent:
                break

    if brain_entities_path is None or not brain_entities_path.exists():
        return ValidationResult(
            hook_name="brain_refs_valid",
            status=ValidationStatus.SKIP,
            message="Could not locate brain Entities directory",
            metadata={"category": "brain"},
        )

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
    feature_path: Path, state: Optional[Any] = None
) -> ValidationResult:
    """Validate source data freshness."""
    if state is None:
        return ValidationResult(
            hook_name="data_freshness",
            status=ValidationStatus.SKIP,
            message="No feature state found",
            metadata={"category": "data"},
        )

    state_file = feature_path / "feature-state.yaml"
    if not state_file.exists():
        return ValidationResult(
            hook_name="data_freshness",
            status=ValidationStatus.SKIP,
            message="Feature state file not found",
            metadata={"category": "data"},
        )

    mtime = datetime.fromtimestamp(state_file.stat().st_mtime)
    age_days = (datetime.now() - mtime).days

    try:
        from pm_os_cce.tools.feature.feature_state import FeaturePhase
    except ImportError:
        from feature.feature_state import FeaturePhase

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

    return ValidationResult(
        hook_name="data_freshness",
        status=ValidationStatus.PASS,
        message=f"Feature state is fresh ({age_days} days old)",
        metadata={"category": "data", "age_days": age_days},
    )


def validate_context_doc_consistency(
    feature_path: Path, state: Optional[Any] = None
) -> ValidationResult:
    """Validate context document internal consistency."""
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

    context_file = feature_path / context_file_name
    if not context_file.exists():
        context_docs_dir = feature_path / "context-docs"
        if context_docs_dir.exists():
            context_file = context_docs_dir / context_file_name

    if not context_file.exists():
        context_track = state.tracks.get("context")
        try:
            from pm_os_cce.tools.feature.feature_state import TrackStatus
        except ImportError:
            from feature.feature_state import TrackStatus

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

    try:
        content = context_file.read_text()

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
    feature_path: Path, state: Optional[Any] = None
) -> ValidationResult:
    """Validate artifact URL patterns."""
    if state is None:
        return ValidationResult(
            hook_name="artifact_urls_valid",
            status=ValidationStatus.SKIP,
            message="No feature state found",
            metadata={"category": "artifacts"},
        )

    artifacts = state.artifacts or {}

    url_patterns = {
        "figma": r"https?://.*figma\.com",
        "jira_epic": r"https?://.*\.(atlassian\.net|jira\.).*",
        "confluence_page": r"https?://.*atlassian\.net/wiki.*|https?://.*confluence\.",
        "wireframes_url": r"https?://",
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
    feature_path: Path, state: Optional[Any] = None
) -> ValidationResult:
    """Validate track status consistency with phase."""
    if state is None:
        return ValidationResult(
            hook_name="track_status_consistency",
            status=ValidationStatus.SKIP,
            message="No feature state found",
            metadata={"category": "consistency"},
        )

    try:
        from pm_os_cce.tools.feature.feature_state import FeaturePhase, TrackStatus
    except ImportError:
        from feature.feature_state import FeaturePhase, TrackStatus

    issues = []

    if state.current_phase == FeaturePhase.DECISION_GATE:
        for track_name, track in state.tracks.items():
            if track.status == TrackStatus.NOT_STARTED and track_name != "design":
                issues.append(
                    f"{track_name} track not started but feature is at decision gate"
                )

    if state.current_phase == FeaturePhase.OUTPUT_GENERATION:
        for track_name, track in state.tracks.items():
            if track.status not in (TrackStatus.COMPLETE, TrackStatus.NOT_STARTED):
                if track_name != "design":
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


def validate_discovery_completeness(
    feature_path: Path, state: Optional[Any] = None
) -> ValidationResult:
    """Validate discovery layer completeness and freshness."""
    if state is None:
        return ValidationResult(
            hook_name="discovery_completeness",
            status=ValidationStatus.SKIP,
            message="No feature state found",
            metadata={"category": "discovery"},
        )

    discovery = state.discovery
    issues: List[str] = []

    if not discovery or not discovery.get("ran_at"):
        return ValidationResult(
            hook_name="discovery_completeness",
            status=ValidationStatus.WARN,
            message="Discovery has not been run for this feature",
            severity=HookSeverity.MEDIUM,
            remediation="Run discovery via FeatureEngine._run_discovery() or re-initialize the feature",
            metadata={"category": "discovery", "discovery_ran": False},
        )

    try:
        ran_at = datetime.fromisoformat(discovery["ran_at"])
        age_days = (datetime.now() - ran_at).days
        if age_days > 7:
            issues.append(f"Discovery data is {age_days} days old (>7 day threshold)")
    except (ValueError, TypeError):
        issues.append("Discovery ran_at timestamp is invalid")

    related_entities = discovery.get("related_entities", [])
    if related_entities:
        context_file_name = state.context_file
        context_file = feature_path / context_file_name if context_file_name else None

        if context_file and context_file.exists():
            try:
                content = context_file.read_text(encoding="utf-8").lower()
                unreferenced = []
                for entity_ref in related_entities[:10]:
                    entity_name = Path(entity_ref).stem.replace("_", " ").lower()
                    if entity_name and entity_name not in content:
                        unreferenced.append(entity_ref)

                if unreferenced:
                    issues.append(
                        f"{len(unreferenced)} discovered Brain entities not referenced "
                        f"in context doc: {', '.join(unreferenced[:3])}"
                    )
            except (IOError, OSError):
                pass

    open_decisions = [
        d for d in state.decisions
        if d.metadata.get("status") == "open"
        and d.metadata.get("source", "").endswith("_challenge")
    ]
    if open_decisions:
        critical_open = [
            d for d in open_decisions if d.metadata.get("severity") == "critical"
        ]
        if critical_open:
            issues.append(
                f"{len(critical_open)} unresolved critical decision(s) from challenge"
            )
        elif len(open_decisions) > 3:
            issues.append(
                f"{len(open_decisions)} unresolved open decisions from challenge"
            )

    coverage = discovery.get("completeness_coverage", {})
    uncovered = [k for k, v in coverage.items() if not v]
    if uncovered:
        issues.append(f"Discovery coverage gaps: {', '.join(uncovered)}")

    if not issues:
        return ValidationResult(
            hook_name="discovery_completeness",
            status=ValidationStatus.PASS,
            message="Discovery is complete and up-to-date",
            metadata={
                "category": "discovery",
                "findings_count": discovery.get("findings_count", 0),
                "coverage": coverage,
            },
        )

    return ValidationResult(
        hook_name="discovery_completeness",
        status=ValidationStatus.WARN,
        message=f"Discovery completeness: {len(issues)} issue(s)",
        severity=HookSeverity.MEDIUM,
        details="; ".join(issues),
        remediation="Re-run discovery or address identified gaps",
        metadata={
            "category": "discovery",
            "issues": issues,
            "findings_count": discovery.get("findings_count", 0),
        },
    )


# ========== Validation Hook Runner ==========


class ValidationHookRunner:
    """Runs validation hooks for a feature."""

    def __init__(
        self, feature_path: Path, hooks: Optional[List[ValidationHook]] = None
    ):
        self.feature_path = Path(feature_path)
        self._hooks: Dict[str, ValidationHook] = {}
        self._state: Optional[Any] = None
        self._last_run: Dict[str, datetime] = {}

        if hooks is None:
            for hook in get_default_hooks():
                self.register_hook(hook)
        else:
            for hook in hooks:
                self.register_hook(hook)

    def _load_state(self) -> Optional[Any]:
        """Load feature state if not already loaded."""
        if self._state is None:
            try:
                from pm_os_cce.tools.feature.feature_state import FeatureState
            except ImportError:
                from feature.feature_state import FeatureState

            self._state = FeatureState.load(self.feature_path)
        return self._state

    @property
    def state(self) -> Optional[Any]:
        return self._load_state()

    @property
    def hooks(self) -> List[ValidationHook]:
        return list(self._hooks.values())

    def register_hook(self, hook: ValidationHook) -> None:
        self._hooks[hook.name] = hook

    def unregister_hook(self, name: str) -> bool:
        if name in self._hooks:
            del self._hooks[name]
            return True
        return False

    def get_hook(self, name: str) -> Optional[ValidationHook]:
        return self._hooks.get(name)

    def _should_run_hook(self, hook: ValidationHook, force: bool = False) -> bool:
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
        results = []
        for hook in self._hooks.values():
            result = self.run_hook(hook.name, force)
            if result:
                results.append(result)
        return results

    def run_by_category(
        self, category: str, force: bool = False
    ) -> List[ValidationResult]:
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
        results = self.run_all(force)
        slug = self.state.slug if self.state else self.feature_path.name

        return ValidationReport(
            feature_slug=slug,
            results=results,
            generated_at=datetime.now(),
        )

    def get_failed_by_severity(self, severity: HookSeverity) -> List[ValidationResult]:
        results = self.run_all()
        return [r for r in results if r.failed and r.severity == severity]

    def has_critical_failures(self) -> bool:
        results = self.run_all()
        return any(r.is_critical for r in results)

    def is_valid(self) -> bool:
        results = self.run_all()
        return all(r.passed or r.status == ValidationStatus.SKIP for r in results)


# ========== Default Hooks Factory ==========


def get_default_hooks() -> List[ValidationHook]:
    """Get the default set of validation hooks."""
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
        ValidationHook(
            name="discovery_completeness",
            description="Validate discovery layer completeness and freshness",
            check_fn=validate_discovery_completeness,
            frequency=HookFrequency.ALWAYS,
            severity=HookSeverity.MEDIUM,
            category="discovery",
        ),
    ]


# ========== Convenience Functions ==========


def run_validation_hooks(
    feature_path: Path, force: bool = False
) -> List[ValidationResult]:
    """Convenience function to run all validation hooks for a feature."""
    runner = ValidationHookRunner(feature_path)
    return runner.run_all(force)


def get_validation_report(feature_path: Path, force: bool = False) -> ValidationReport:
    """Convenience function to generate a validation report."""
    runner = ValidationHookRunner(feature_path)
    return runner.generate_report(force)


def is_feature_valid(feature_path: Path) -> bool:
    """Convenience function to check if a feature passes all validations."""
    runner = ValidationHookRunner(feature_path)
    return runner.is_valid()


def format_validation_results(
    results: List[ValidationResult], include_passed: bool = False
) -> str:
    """Format validation results for display."""
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
