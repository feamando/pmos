"""
Context Document Iteration Pipeline

Orchestrates the context document iteration workflow:
    v1 generation -> orthogonal challenge -> analyze issues
    -> v2 generation (incorporating feedback) -> orthogonal challenge
    -> v3 generation (final version after passing challenge)

The pipeline:
- Tracks which version we're on (1, 2, or 3)
- Auto-advances when score thresholds are met
- Allows manual iteration requests
- Stores all versions for audit trail

Score Thresholds (from PRD F.2):
    v1 -> v2: Score >= 60 (address critical/major issues)
    v2 -> v3: Score >= 75 (ready for finalization)
    v3 complete: Score >= 85 (final version)

Output Location:
    {feature-folder}/context-docs/
    - v1-draft.md
    - v1-challenge.md
    - v2-revised.md
    - v2-challenge.md
    - v3-final.md

Usage:
    from tools.context_engine import ContextIterationPipeline

    pipeline = ContextIterationPipeline()

    # Start pipeline - generates v1 and runs challenge
    result = pipeline.start_pipeline(
        feature_path=Path("/path/to/feature"),
        insight={"problem": "...", "evidence": [...]}
    )

    # Iterate to next version based on challenge feedback
    result = pipeline.iterate(feature_path)

    # Get current pipeline status
    status = pipeline.get_pipeline_status(feature_path)

Author: PM-OS Team
Version: 1.0.0
"""

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logger = logging.getLogger(__name__)


class PipelineStatus(Enum):
    """Status of the context iteration pipeline."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    PENDING_ITERATION = "pending_iteration"
    COMPLETE = "complete"
    FAILED = "failed"


class VersionStatus(Enum):
    """Status of a single version."""

    DRAFT = "draft"
    CHALLENGED = "challenged"
    PASSED = "passed"
    SUPERSEDED = "superseded"


@dataclass
class VersionInfo:
    """
    Information about a single context document version.

    Attributes:
        version: Version number (1, 2, or 3)
        status: Current status of this version
        file_path: Path to the document file
        challenge_score: Score from orthogonal challenge (if run)
        challenge_file: Path to challenge output file
        created_at: When this version was created
        issues_addressed: Issues addressed from previous version
    """

    version: int
    status: VersionStatus
    file_path: Optional[Path] = None
    challenge_score: Optional[int] = None
    challenge_file: Optional[Path] = None
    created_at: datetime = field(default_factory=datetime.now)
    issues_addressed: List[str] = field(default_factory=list)
    critical_count: int = 0
    major_count: int = 0
    minor_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "version": self.version,
            "status": self.status.value,
            "file_path": str(self.file_path) if self.file_path else None,
            "challenge_score": self.challenge_score,
            "challenge_file": str(self.challenge_file) if self.challenge_file else None,
            "created_at": self.created_at.isoformat(),
            "issues_addressed": self.issues_addressed,
            "critical_count": self.critical_count,
            "major_count": self.major_count,
            "minor_count": self.minor_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VersionInfo":
        """Create from dictionary."""
        file_path = Path(data["file_path"]) if data.get("file_path") else None
        challenge_file = (
            Path(data["challenge_file"]) if data.get("challenge_file") else None
        )

        return cls(
            version=data["version"],
            status=VersionStatus(data.get("status", "draft")),
            file_path=file_path,
            challenge_score=data.get("challenge_score"),
            challenge_file=challenge_file,
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else datetime.now()
            ),
            issues_addressed=data.get("issues_addressed", []),
            critical_count=data.get("critical_count", 0),
            major_count=data.get("major_count", 0),
            minor_count=data.get("minor_count", 0),
        )


@dataclass
class PipelineState:
    """
    Complete state of the context iteration pipeline.

    Attributes:
        status: Current pipeline status
        current_version: Version number currently being worked on
        versions_history: History of all versions
        started_at: When the pipeline started
        completed_at: When the pipeline completed (if applicable)
        last_updated: Last update timestamp
    """

    status: PipelineStatus = PipelineStatus.NOT_STARTED
    current_version: int = 0
    versions_history: List[VersionInfo] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "status": self.status.value,
            "current_version": self.current_version,
            "versions_history": [v.to_dict() for v in self.versions_history],
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "last_updated": self.last_updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineState":
        """Create from dictionary."""
        versions_history = [
            VersionInfo.from_dict(v) for v in data.get("versions_history", [])
        ]

        started_at = None
        if data.get("started_at"):
            started_at = datetime.fromisoformat(data["started_at"])

        completed_at = None
        if data.get("completed_at"):
            completed_at = datetime.fromisoformat(data["completed_at"])

        return cls(
            status=PipelineStatus(data.get("status", "not_started")),
            current_version=data.get("current_version", 0),
            versions_history=versions_history,
            started_at=started_at,
            completed_at=completed_at,
            last_updated=(
                datetime.fromisoformat(data["last_updated"])
                if data.get("last_updated")
                else datetime.now()
            ),
        )

    def get_version_info(self, version: int) -> Optional[VersionInfo]:
        """Get info for a specific version."""
        for v in self.versions_history:
            if v.version == version:
                return v
        return None

    def get_latest_version(self) -> Optional[VersionInfo]:
        """Get the most recent version info."""
        if not self.versions_history:
            return None
        return self.versions_history[-1]


@dataclass
class PipelineResult:
    """
    Result of a pipeline operation.

    Attributes:
        success: Whether the operation succeeded
        message: Human-readable result message
        version: Version number affected
        status: Current pipeline status
        score: Challenge score (if applicable)
        next_steps: Suggested next actions
        pipeline_state: Full pipeline state
    """

    success: bool
    message: str = ""
    version: int = 0
    status: PipelineStatus = PipelineStatus.NOT_STARTED
    score: Optional[int] = None
    next_steps: List[str] = field(default_factory=list)
    pipeline_state: Optional[PipelineState] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "message": self.message,
            "version": self.version,
            "status": self.status.value,
            "score": self.score,
            "next_steps": self.next_steps,
            "pipeline_state": (
                self.pipeline_state.to_dict() if self.pipeline_state else None
            ),
        }


# Score thresholds
THRESHOLD_V1_TO_V2 = 60  # Minimum score to proceed to v2
THRESHOLD_V2_TO_V3 = 75  # Minimum score to proceed to v3
THRESHOLD_V3_COMPLETE = 85  # Minimum score for completion


class ContextIterationPipeline:
    """
    Orchestrates the context document iteration workflow.

    The pipeline manages the progression through versions:
    - v1: Initial draft from insight/feature info
    - v2: Revised based on v1 challenge feedback
    - v3: Final version after passing quality threshold

    Each version goes through:
    1. Generation (from template or previous version + feedback)
    2. Orthogonal challenge
    3. Analysis and decision (advance, iterate, or complete)
    """

    def __init__(self):
        """Initialize the context iteration pipeline."""
        from .context_doc_generator import ContextDocGenerator
        from .orthogonal_integration import OrthogonalIntegration

        self._doc_generator = ContextDocGenerator()
        self._orthogonal = OrthogonalIntegration()

    def start_pipeline(
        self,
        feature_path: Path,
        insight: Optional[Dict[str, Any]] = None,
        auto_challenge: bool = True,
    ) -> PipelineResult:
        """
        Start the context iteration pipeline.

        Generates v1 context document and optionally runs the orthogonal challenge.

        Args:
            feature_path: Path to the feature folder
            insight: Optional insight data for v1 generation
            auto_challenge: Whether to automatically run challenge after v1

        Returns:
            PipelineResult with operation outcome
        """
        from .feature_state import FeatureState, TrackStatus

        # Load feature state
        state = FeatureState.load(feature_path)
        if not state:
            return PipelineResult(
                success=False,
                message=f"Feature state not found at {feature_path}/feature-state.yaml",
            )

        # Initialize pipeline state
        pipeline_state = PipelineState(
            status=PipelineStatus.IN_PROGRESS,
            current_version=1,
            started_at=datetime.now(),
            last_updated=datetime.now(),
        )

        # Generate v1 document
        v1_result = self._doc_generator.generate_v1(feature_path, insight)

        if not v1_result.success:
            return PipelineResult(
                success=False,
                message=f"Failed to generate v1: {v1_result.message}",
                status=PipelineStatus.FAILED,
            )

        # Create version info for v1
        v1_info = VersionInfo(
            version=1,
            status=VersionStatus.DRAFT,
            file_path=v1_result.file_path,
            created_at=datetime.now(),
        )
        pipeline_state.versions_history.append(v1_info)

        # Optionally run challenge
        if auto_challenge:
            challenge_result = self._orthogonal.run_challenge(
                context_doc_path=v1_result.file_path,
                feature_path=feature_path,
                version=1,
            )

            if challenge_result.success:
                v1_info.status = VersionStatus.CHALLENGED
                v1_info.challenge_score = challenge_result.score
                v1_info.challenge_file = challenge_result.challenge_file
                v1_info.critical_count = challenge_result.critical_count
                v1_info.major_count = challenge_result.major_count
                v1_info.minor_count = challenge_result.minor_count

                # Determine next steps based on score
                if challenge_result.score >= THRESHOLD_V3_COMPLETE:
                    v1_info.status = VersionStatus.PASSED
                    pipeline_state.status = PipelineStatus.COMPLETE
                    pipeline_state.completed_at = datetime.now()
                    next_steps = ["v1 passed all quality checks - pipeline complete"]
                elif challenge_result.score >= THRESHOLD_V2_TO_V3:
                    pipeline_state.status = PipelineStatus.PENDING_ITERATION
                    next_steps = [
                        f"Score {challenge_result.score} meets threshold for finalization",
                        "Run iterate() to generate v3-final",
                        "Or manually review issues before proceeding",
                    ]
                elif challenge_result.score >= THRESHOLD_V1_TO_V2:
                    pipeline_state.status = PipelineStatus.PENDING_ITERATION
                    next_steps = [
                        f"Score {challenge_result.score} - address {challenge_result.critical_count} critical, {challenge_result.major_count} major issues",
                        "Run iterate() to generate v2-revised",
                        f"Review challenge feedback at {challenge_result.challenge_file}",
                    ]
                else:
                    pipeline_state.status = PipelineStatus.PENDING_REVIEW
                    next_steps = [
                        f"Score {challenge_result.score} below threshold - needs major revisions",
                        f"Review {challenge_result.critical_count} critical issues",
                        "Consider revising problem statement and scope",
                        f"Challenge feedback at {challenge_result.challenge_file}",
                    ]
            else:
                next_steps = [
                    f"Challenge failed: {challenge_result.error}",
                    "Run challenge manually or iterate with manual review",
                ]
        else:
            next_steps = [
                "v1 generated successfully",
                "Run orthogonal challenge to evaluate quality",
                f"Document at {v1_result.file_path}",
            ]

        # Update feature state with pipeline info
        self._update_feature_state_context_track(
            feature_path=feature_path, state=state, pipeline_state=pipeline_state
        )

        return PipelineResult(
            success=True,
            message=f"Pipeline started. v1 generated at {v1_result.file_path}",
            version=1,
            status=pipeline_state.status,
            score=v1_info.challenge_score,
            next_steps=next_steps,
            pipeline_state=pipeline_state,
        )

    def iterate(
        self,
        feature_path: Path,
        feedback_summary: Optional[str] = None,
        auto_challenge: bool = True,
    ) -> PipelineResult:
        """
        Iterate to the next version based on challenge feedback.

        Generates the next version (v2 or v3) incorporating feedback from
        the previous challenge.

        Args:
            feature_path: Path to the feature folder
            feedback_summary: Optional manual summary of changes to make
            auto_challenge: Whether to automatically run challenge after generation

        Returns:
            PipelineResult with operation outcome
        """
        from .feature_state import FeatureState, TrackStatus

        # Load feature state
        state = FeatureState.load(feature_path)
        if not state:
            return PipelineResult(
                success=False,
                message=f"Feature state not found at {feature_path}/feature-state.yaml",
            )

        # Load pipeline state from feature state
        pipeline_state = self._get_pipeline_state_from_feature(state)

        if not pipeline_state or pipeline_state.status == PipelineStatus.NOT_STARTED:
            return PipelineResult(
                success=False,
                message="Pipeline not started. Call start_pipeline() first.",
                status=PipelineStatus.NOT_STARTED,
            )

        if pipeline_state.status == PipelineStatus.COMPLETE:
            return PipelineResult(
                success=False,
                message="Pipeline already complete. No further iterations needed.",
                status=PipelineStatus.COMPLETE,
                pipeline_state=pipeline_state,
            )

        # Determine next version
        current_version = pipeline_state.current_version
        next_version = current_version + 1

        if next_version > 3:
            return PipelineResult(
                success=False,
                message="Maximum version (v3) already reached.",
                version=current_version,
                status=pipeline_state.status,
                pipeline_state=pipeline_state,
            )

        # Get previous version info and challenge feedback
        prev_version_info = pipeline_state.get_version_info(current_version)
        if not prev_version_info or not prev_version_info.file_path:
            return PipelineResult(
                success=False,
                message=f"Previous version v{current_version} document not found.",
                status=PipelineStatus.FAILED,
            )

        # Generate next version document
        new_doc_result = self._generate_next_version(
            feature_path=feature_path,
            prev_version=current_version,
            prev_doc_path=prev_version_info.file_path,
            prev_challenge_path=prev_version_info.challenge_file,
            feedback_summary=feedback_summary,
            next_version=next_version,
        )

        if not new_doc_result["success"]:
            return PipelineResult(
                success=False,
                message=new_doc_result.get("error", "Failed to generate next version"),
                status=PipelineStatus.FAILED,
            )

        # Mark previous version as superseded
        prev_version_info.status = VersionStatus.SUPERSEDED

        # Create new version info
        new_version_info = VersionInfo(
            version=next_version,
            status=VersionStatus.DRAFT,
            file_path=Path(new_doc_result["file_path"]),
            created_at=datetime.now(),
            issues_addressed=new_doc_result.get("issues_addressed", []),
        )
        pipeline_state.versions_history.append(new_version_info)
        pipeline_state.current_version = next_version
        pipeline_state.last_updated = datetime.now()

        # Run challenge on new version
        if auto_challenge:
            challenge_result = self._orthogonal.run_challenge(
                context_doc_path=new_version_info.file_path,
                feature_path=feature_path,
                version=next_version,
            )

            if challenge_result.success:
                new_version_info.status = VersionStatus.CHALLENGED
                new_version_info.challenge_score = challenge_result.score
                new_version_info.challenge_file = challenge_result.challenge_file
                new_version_info.critical_count = challenge_result.critical_count
                new_version_info.major_count = challenge_result.major_count
                new_version_info.minor_count = challenge_result.minor_count

                # Determine status and next steps
                if challenge_result.score >= THRESHOLD_V3_COMPLETE:
                    new_version_info.status = VersionStatus.PASSED
                    pipeline_state.status = PipelineStatus.COMPLETE
                    pipeline_state.completed_at = datetime.now()
                    next_steps = [
                        f"v{next_version} passed with score {challenge_result.score}",
                        "Context document finalized",
                        f"Final version at {new_version_info.file_path}",
                    ]
                elif next_version >= 3:
                    # v3 but didn't pass threshold
                    pipeline_state.status = PipelineStatus.PENDING_REVIEW
                    next_steps = [
                        f"v3 generated with score {challenge_result.score}",
                        f"Score below {THRESHOLD_V3_COMPLETE} threshold",
                        "Manual review recommended",
                        "Consider accepting with known limitations",
                    ]
                elif challenge_result.score >= THRESHOLD_V2_TO_V3:
                    pipeline_state.status = PipelineStatus.PENDING_ITERATION
                    next_steps = [
                        f"v{next_version} ready for finalization (score: {challenge_result.score})",
                        "Run iterate() to generate final version",
                        f"Review remaining issues at {challenge_result.challenge_file}",
                    ]
                else:
                    pipeline_state.status = PipelineStatus.PENDING_ITERATION
                    next_steps = [
                        f"v{next_version} needs more work (score: {challenge_result.score})",
                        f"Address {challenge_result.critical_count} critical, {challenge_result.major_count} major issues",
                        "Run iterate() again to improve",
                    ]
            else:
                next_steps = [
                    f"v{next_version} generated but challenge failed",
                    f"Error: {challenge_result.error}",
                    "Run challenge manually",
                ]
                pipeline_state.status = PipelineStatus.PENDING_REVIEW
        else:
            pipeline_state.status = PipelineStatus.PENDING_REVIEW
            next_steps = [
                f"v{next_version} generated successfully",
                "Run orthogonal challenge to evaluate",
                f"Document at {new_version_info.file_path}",
            ]

        # Update feature state
        self._update_feature_state_context_track(
            feature_path=feature_path, state=state, pipeline_state=pipeline_state
        )

        return PipelineResult(
            success=True,
            message=f"Iterated to v{next_version}",
            version=next_version,
            status=pipeline_state.status,
            score=new_version_info.challenge_score,
            next_steps=next_steps,
            pipeline_state=pipeline_state,
        )

    def get_pipeline_status(self, feature_path: Path) -> PipelineResult:
        """
        Get current status of the context iteration pipeline.

        Args:
            feature_path: Path to the feature folder

        Returns:
            PipelineResult with current status and next steps
        """
        from .feature_state import FeatureState

        # Load feature state
        state = FeatureState.load(feature_path)
        if not state:
            return PipelineResult(
                success=False,
                message=f"Feature state not found at {feature_path}/feature-state.yaml",
            )

        # Load pipeline state
        pipeline_state = self._get_pipeline_state_from_feature(state)

        if not pipeline_state or pipeline_state.status == PipelineStatus.NOT_STARTED:
            return PipelineResult(
                success=True,
                message="Pipeline not started",
                version=0,
                status=PipelineStatus.NOT_STARTED,
                next_steps=["Run start_pipeline() to begin context document creation"],
                pipeline_state=pipeline_state,
            )

        # Get current version info
        current_info = pipeline_state.get_latest_version()

        # Build status message
        if pipeline_state.status == PipelineStatus.COMPLETE:
            message = (
                f"Pipeline complete. Final version: v{pipeline_state.current_version}"
            )
            if current_info:
                message += f" (score: {current_info.challenge_score})"
            next_steps = [
                "Context document finalized",
                "Proceed to next track (design, business case, engineering)",
            ]
        elif pipeline_state.status == PipelineStatus.PENDING_REVIEW:
            message = f"Pending review at v{pipeline_state.current_version}"
            if current_info and current_info.challenge_score:
                message += f" (score: {current_info.challenge_score})"
            next_steps = [
                "Review challenge feedback",
                "Run iterate() to improve, or accept current version",
            ]
        elif pipeline_state.status == PipelineStatus.PENDING_ITERATION:
            message = f"Ready to iterate from v{pipeline_state.current_version}"
            if current_info and current_info.challenge_score:
                message += f" (score: {current_info.challenge_score})"
            next_steps = [
                "Run iterate() to generate next version",
                "Or review challenge feedback first",
            ]
        else:
            message = f"In progress at v{pipeline_state.current_version}"
            next_steps = ["Continue working on current version"]

        return PipelineResult(
            success=True,
            message=message,
            version=pipeline_state.current_version,
            status=pipeline_state.status,
            score=current_info.challenge_score if current_info else None,
            next_steps=next_steps,
            pipeline_state=pipeline_state,
        )

    def force_complete(
        self, feature_path: Path, reason: str = "Manual completion"
    ) -> PipelineResult:
        """
        Force-complete the pipeline at current version.

        Use this when the current version is acceptable despite not meeting
        the automatic threshold.

        Args:
            feature_path: Path to the feature folder
            reason: Reason for forcing completion

        Returns:
            PipelineResult with updated status
        """
        from .feature_state import FeatureState, TrackStatus

        state = FeatureState.load(feature_path)
        if not state:
            return PipelineResult(success=False, message="Feature state not found")

        pipeline_state = self._get_pipeline_state_from_feature(state)
        if not pipeline_state:
            return PipelineResult(success=False, message="Pipeline not started")

        # Mark current version as passed
        current_info = pipeline_state.get_latest_version()
        if current_info:
            current_info.status = VersionStatus.PASSED

        pipeline_state.status = PipelineStatus.COMPLETE
        pipeline_state.completed_at = datetime.now()
        pipeline_state.last_updated = datetime.now()

        # Record the decision
        state.add_decision(
            decision=f"Force-completed context pipeline at v{pipeline_state.current_version}",
            rationale=reason,
            decided_by="user",
        )

        # Update feature state
        self._update_feature_state_context_track(
            feature_path=feature_path, state=state, pipeline_state=pipeline_state
        )

        return PipelineResult(
            success=True,
            message=f"Pipeline force-completed at v{pipeline_state.current_version}",
            version=pipeline_state.current_version,
            status=PipelineStatus.COMPLETE,
            score=current_info.challenge_score if current_info else None,
            next_steps=["Context document accepted", "Proceed to next track"],
            pipeline_state=pipeline_state,
        )

    def _generate_next_version(
        self,
        feature_path: Path,
        prev_version: int,
        prev_doc_path: Path,
        prev_challenge_path: Optional[Path],
        feedback_summary: Optional[str],
        next_version: int,
    ) -> Dict[str, Any]:
        """
        Generate the next version document based on previous version and feedback.

        Args:
            feature_path: Path to feature folder
            prev_version: Previous version number
            prev_doc_path: Path to previous document
            prev_challenge_path: Path to previous challenge output
            feedback_summary: Optional manual feedback summary
            next_version: Next version number

        Returns:
            Dict with success, file_path, and issues_addressed
        """
        # Read previous document
        try:
            prev_content = prev_doc_path.read_text(encoding="utf-8")
        except (IOError, OSError) as e:
            return {"success": False, "error": f"Failed to read previous version: {e}"}

        # Read challenge feedback if available
        challenge_feedback = ""
        if prev_challenge_path and prev_challenge_path.exists():
            try:
                challenge_feedback = prev_challenge_path.read_text(encoding="utf-8")
            except (IOError, OSError):
                pass

        # Determine output filename
        if next_version == 2:
            output_filename = "v2-revised.md"
        elif next_version == 3:
            output_filename = "v3-final.md"
        else:
            output_filename = f"v{next_version}-draft.md"

        # Generate new version content
        # This uses a template approach - in a real implementation,
        # you might use an LLM to intelligently incorporate feedback
        new_content = self._create_revised_document(
            prev_content=prev_content,
            challenge_feedback=challenge_feedback,
            feedback_summary=feedback_summary,
            next_version=next_version,
        )

        # Extract addressed issues
        issues_addressed = self._extract_addressed_issues(challenge_feedback)

        # Write new document
        context_docs_dir = feature_path / "context-docs"
        context_docs_dir.mkdir(parents=True, exist_ok=True)
        output_path = context_docs_dir / output_filename

        try:
            output_path.write_text(new_content, encoding="utf-8")
        except (IOError, OSError) as e:
            return {"success": False, "error": f"Failed to write new version: {e}"}

        return {
            "success": True,
            "file_path": str(output_path),
            "issues_addressed": issues_addressed,
        }

    def _create_revised_document(
        self,
        prev_content: str,
        challenge_feedback: str,
        feedback_summary: Optional[str],
        next_version: int,
    ) -> str:
        """
        Create revised document content.

        In a production implementation, this would use an LLM to intelligently
        incorporate feedback. For now, it uses a template approach.

        Args:
            prev_content: Previous document content
            challenge_feedback: Challenge output
            feedback_summary: Manual feedback
            next_version: New version number

        Returns:
            New document content
        """
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")

        # Determine version label
        if next_version == 2:
            version_label = "2 (Revised)"
            status_label = "Revised based on challenge feedback"
        elif next_version == 3:
            version_label = "3 (Final)"
            status_label = "Final version"
        else:
            version_label = f"{next_version} (Draft)"
            status_label = "Draft"

        # Update version header in content
        lines = prev_content.split("\n")
        new_lines = []
        in_header = True

        for line in lines:
            if in_header:
                if line.startswith("**Version:**"):
                    new_lines.append(f"**Version:** {version_label}")
                    continue
                elif line.startswith("**Status:**"):
                    new_lines.append(f"**Status:** {status_label}")
                    continue
                elif line.startswith("**Last Updated:**") or line.startswith(
                    "**Created:**"
                ):
                    # Keep created, add updated
                    if "Created" in line:
                        new_lines.append(line)
                        new_lines.append(f"**Last Updated:** {date_str}")
                    continue
                elif line.startswith("## "):
                    in_header = False

            new_lines.append(line)

        new_content = "\n".join(new_lines)

        # Add revision notes section at the end
        revision_section = f"""

---

## Revision History

### Version {next_version} ({date_str})

**Changes from v{next_version - 1}:**
"""

        if feedback_summary:
            revision_section += f"\n{feedback_summary}\n"
        else:
            revision_section += (
                "\n- Addressed issues identified in orthogonal challenge\n"
            )
            revision_section += "- Refined problem statement and success metrics\n"
            revision_section += "- Clarified scope boundaries\n"

        # Append revision section if not already present
        if "## Revision History" not in new_content:
            new_content += revision_section

        # Update footer
        if "Generated by Context Creation Engine" in new_content:
            new_content = new_content.replace(
                "Generated by Context Creation Engine | Ready for orthogonal challenge",
                f"Generated by Context Creation Engine | Version {next_version}",
            )

        return new_content

    def _extract_addressed_issues(self, challenge_feedback: str) -> List[str]:
        """
        Extract issues from challenge feedback that should be addressed.

        Args:
            challenge_feedback: Challenge output content

        Returns:
            List of issue descriptions
        """
        issues = []
        lines = challenge_feedback.split("\n")
        in_issues_section = False

        for line in lines:
            if "### Critical" in line or "### Major" in line:
                in_issues_section = True
                continue
            elif "### Minor" in line:
                in_issues_section = False
                continue
            elif line.startswith("## "):
                in_issues_section = False
                continue

            if in_issues_section and line.strip() and line.strip()[0].isdigit():
                # Extract issue text
                issue_text = line.strip()
                for i, char in enumerate(issue_text):
                    if char in ".):":
                        issue_text = issue_text[i + 1 :].strip()
                        break
                if issue_text:
                    issues.append(issue_text[:100])  # Truncate long issues

        return issues[:10]  # Limit to top 10 issues

    def _get_pipeline_state_from_feature(
        self, state: "FeatureState"
    ) -> Optional[PipelineState]:
        """
        Extract pipeline state from feature state's context track.

        Args:
            state: FeatureState instance

        Returns:
            PipelineState or None if not found
        """
        context_track = state.tracks.get("context")
        if not context_track or not context_track.artifacts:
            return PipelineState()

        pipeline_data = context_track.artifacts.get("pipeline_state")
        if not pipeline_data:
            # Build from existing track data
            pipeline_state = PipelineState()

            if context_track.current_version:
                pipeline_state.current_version = context_track.current_version
                pipeline_state.status = PipelineStatus.IN_PROGRESS

                # Try to reconstruct version history from artifacts
                for v in range(1, context_track.current_version + 1):
                    challenge_data = context_track.artifacts.get(f"v{v}_challenge", {})
                    version_info = VersionInfo(
                        version=v,
                        status=(
                            VersionStatus.CHALLENGED
                            if challenge_data
                            else VersionStatus.DRAFT
                        ),
                        challenge_score=(
                            challenge_data.get("score") if challenge_data else None
                        ),
                    )
                    pipeline_state.versions_history.append(version_info)

            return pipeline_state

        return PipelineState.from_dict(pipeline_data)

    def _update_feature_state_context_track(
        self,
        feature_path: Path,
        state: "FeatureState",
        pipeline_state: PipelineState,
    ) -> None:
        """
        Update feature state's context track with pipeline state.

        Args:
            feature_path: Path to feature folder
            state: FeatureState instance
            pipeline_state: PipelineState to save
        """
        from .feature_state import TrackStatus

        context_track = state.tracks.get("context")
        if not context_track:
            return

        # Update track fields
        context_track.current_version = pipeline_state.current_version

        # Map pipeline status to track status
        if pipeline_state.status == PipelineStatus.COMPLETE:
            context_track.status = TrackStatus.COMPLETE
            context_track.current_step = "complete"
            context_track.file = f"context-docs/v{pipeline_state.current_version}-{'final' if pipeline_state.current_version == 3 else 'draft'}.md"
        elif pipeline_state.status == PipelineStatus.NOT_STARTED:
            context_track.status = TrackStatus.NOT_STARTED
        elif pipeline_state.status == PipelineStatus.PENDING_REVIEW:
            context_track.status = TrackStatus.PENDING_INPUT
            context_track.current_step = (
                f"v{pipeline_state.current_version}_pending_review"
            )
        else:
            context_track.status = TrackStatus.IN_PROGRESS
            context_track.current_step = (
                f"v{pipeline_state.current_version}_in_progress"
            )

        # Store full pipeline state in artifacts
        if not context_track.artifacts:
            context_track.artifacts = {}

        context_track.artifacts["pipeline_state"] = pipeline_state.to_dict()

        # Also update individual version challenge data for backwards compatibility
        for version_info in pipeline_state.versions_history:
            if version_info.challenge_score is not None:
                context_track.artifacts[f"v{version_info.version}_challenge"] = {
                    "score": version_info.challenge_score,
                    "critical_count": version_info.critical_count,
                    "major_count": version_info.major_count,
                    "minor_count": version_info.minor_count,
                    "timestamp": version_info.created_at.isoformat(),
                    "challenge_file": (
                        str(version_info.challenge_file)
                        if version_info.challenge_file
                        else None
                    ),
                }

        # Save feature state
        state.save(feature_path)

    def list_versions(self, feature_path: Path) -> List[Dict[str, Any]]:
        """
        List all context document versions for a feature.

        Scans the context-docs/ folder and returns information about all
        versions found, including drafts and challenge outputs.

        Args:
            feature_path: Path to the feature folder

        Returns:
            List of dicts with version info:
                - version: Version number (1, 2, 3)
                - type: "draft", "revised", "final", or "challenge"
                - file_path: Full path to file
                - file_name: File name
                - exists: True if file exists
                - modified: Last modified timestamp (if exists)

        Example:
            >>> pipeline.list_versions(feature_path)
            [
                {"version": 1, "type": "draft", "file_path": "...", "exists": True, ...},
                {"version": 1, "type": "challenge", "file_path": "...", "exists": True, ...},
                {"version": 2, "type": "revised", "file_path": "...", "exists": True, ...},
            ]
        """
        context_docs_dir = feature_path / "context-docs"
        versions = []

        # Define expected version files
        version_files = [
            {"version": 1, "type": "draft", "file_name": "v1-draft.md"},
            {"version": 1, "type": "challenge", "file_name": "v1-challenge.md"},
            {"version": 2, "type": "revised", "file_name": "v2-revised.md"},
            {"version": 2, "type": "challenge", "file_name": "v2-challenge.md"},
            {"version": 3, "type": "final", "file_name": "v3-final.md"},
        ]

        for vf in version_files:
            file_path = context_docs_dir / vf["file_name"]
            version_info = {
                "version": vf["version"],
                "type": vf["type"],
                "file_path": str(file_path),
                "file_name": vf["file_name"],
                "exists": file_path.exists(),
                "modified": None,
            }

            if file_path.exists():
                try:
                    stat = file_path.stat()
                    version_info["modified"] = datetime.fromtimestamp(
                        stat.st_mtime
                    ).isoformat()
                except OSError:
                    pass

            versions.append(version_info)

        # Also scan for any additional version files (e.g., v4+)
        if context_docs_dir.exists():
            for file in context_docs_dir.glob("v*-*.md"):
                file_name = file.name
                # Skip already processed files
                if file_name in [vf["file_name"] for vf in version_files]:
                    continue

                # Parse version number and type from filename
                try:
                    parts = file_name.replace(".md", "").split("-")
                    version_num = int(parts[0][1:])  # Remove 'v' prefix
                    version_type = parts[1] if len(parts) > 1 else "unknown"

                    version_info = {
                        "version": version_num,
                        "type": version_type,
                        "file_path": str(file),
                        "file_name": file_name,
                        "exists": True,
                        "modified": datetime.fromtimestamp(
                            file.stat().st_mtime
                        ).isoformat(),
                    }
                    versions.append(version_info)
                except (ValueError, IndexError):
                    continue

        # Sort by version then type (draft before challenge)
        type_order = {"draft": 0, "revised": 0, "final": 0, "challenge": 1}
        versions.sort(key=lambda x: (x["version"], type_order.get(x["type"], 2)))

        return versions

    def get_latest_version_file(self, feature_path: Path) -> Optional[Dict[str, Any]]:
        """
        Get the latest context document version (excluding challenge files).

        Returns information about the highest version draft/revised/final
        document that exists for this feature.

        Args:
            feature_path: Path to the feature folder

        Returns:
            Dict with version info or None if no versions exist:
                - version: Version number
                - type: "draft", "revised", or "final"
                - file_path: Full path to file
                - file_name: File name
                - modified: Last modified timestamp

        Example:
            >>> pipeline.get_latest_version_file(feature_path)
            {"version": 2, "type": "revised", "file_path": "...", ...}
        """
        versions = self.list_versions(feature_path)

        # Filter to only document versions (not challenges)
        doc_versions = [v for v in versions if v["exists"] and v["type"] != "challenge"]

        if not doc_versions:
            return None

        # Return highest version
        return doc_versions[-1]

    def archive_and_restart(
        self,
        feature_path: Path,
        reason: str = "Manual restart",
        keep_archive: bool = True,
    ) -> PipelineResult:
        """
        Archive existing context documents and restart the pipeline fresh.

        Moves existing context-docs/ contents to context-docs/archive_{timestamp}/
        and resets the pipeline state. Use this when a feature needs a complete
        restart with a new approach.

        Args:
            feature_path: Path to the feature folder
            reason: Reason for restart (logged in decision history)
            keep_archive: If True, archive old docs. If False, delete them.

        Returns:
            PipelineResult indicating success/failure

        Example:
            >>> pipeline.archive_and_restart(feature_path, reason="Scope changed significantly")
        """
        import shutil

        from .feature_state import FeatureState, TrackStatus

        context_docs_dir = feature_path / "context-docs"

        # Check if there's anything to archive
        if not context_docs_dir.exists():
            return PipelineResult(
                success=True,
                message="No existing context docs to archive. Ready for fresh start.",
                version=0,
                status=PipelineStatus.NOT_STARTED,
                next_steps=["Run start_pipeline() to begin context document creation"],
            )

        existing_files = list(context_docs_dir.glob("*.md"))
        if not existing_files:
            return PipelineResult(
                success=True,
                message="No existing context docs found. Ready for fresh start.",
                version=0,
                status=PipelineStatus.NOT_STARTED,
                next_steps=["Run start_pipeline() to begin context document creation"],
            )

        # Archive or delete existing files
        if keep_archive:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_dir = context_docs_dir / f"archive_{timestamp}"
            archive_dir.mkdir(parents=True, exist_ok=True)

            for file in existing_files:
                try:
                    shutil.move(str(file), str(archive_dir / file.name))
                except (IOError, OSError) as e:
                    logger.warning(f"Failed to archive {file.name}: {e}")

            archive_message = (
                f"Archived {len(existing_files)} files to {archive_dir.name}/"
            )
        else:
            for file in existing_files:
                try:
                    file.unlink()
                except (IOError, OSError) as e:
                    logger.warning(f"Failed to delete {file.name}: {e}")

            archive_message = f"Deleted {len(existing_files)} existing files"

        # Reset pipeline state in feature state
        state = FeatureState.load(feature_path)
        if state:
            # Reset context track
            context_track = state.tracks.get("context")
            if context_track:
                context_track.status = TrackStatus.NOT_STARTED
                context_track.current_version = 0
                context_track.current_step = "not_started"
                context_track.file = None
                context_track.artifacts = {}

            # Record the restart decision
            state.add_decision(
                decision=f"Archived context documents and restarted pipeline",
                rationale=reason,
                decided_by="user",
            )

            # Save updated state
            state.save(feature_path)

        return PipelineResult(
            success=True,
            message=f"Pipeline reset. {archive_message}. Ready for fresh start.",
            version=0,
            status=PipelineStatus.NOT_STARTED,
            next_steps=[
                "Run start_pipeline() to begin context document creation",
                f"Previous work archived due to: {reason}",
            ],
        )


# Export for __init__.py
__all__ = [
    "ContextIterationPipeline",
    "PipelineStatus",
    "PipelineState",
    "PipelineResult",
    "VersionInfo",
    "VersionStatus",
    "THRESHOLD_V1_TO_V2",
    "THRESHOLD_V2_TO_V3",
    "THRESHOLD_V3_COMPLETE",
]
