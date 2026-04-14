"""
PM-OS CCE Cowork Project Generator (v5.0)

Generates Claude Cowork project files for features. Extracted from
feature_engine.py to keep the engine focused on orchestration.
Creates .cowork-project.yaml with tasks, dependencies, and milestones
based on feature state and tracks.

Usage:
    from pm_os_cce.tools.feature.cowork_project_generator import CoworkProjectGenerator
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from core.config_loader import get_config
    except ImportError:
        get_config = None

logger = logging.getLogger(__name__)


@dataclass
class CoworkTask:
    """A task within a Cowork project."""

    id: str
    name: str
    description: str = ""
    status: str = "pending"  # pending, in_progress, complete, blocked
    depends_on: List[str] = field(default_factory=list)
    track: str = "general"
    estimated_minutes: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "track": self.track,
            "estimated_minutes": self.estimated_minutes,
        }
        if self.depends_on:
            result["depends_on"] = self.depends_on
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class CoworkMilestone:
    """A milestone in a Cowork project."""

    id: str
    name: str
    description: str = ""
    tasks: List[str] = field(default_factory=list)
    target_date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tasks": self.tasks,
        }
        if self.target_date:
            result["target_date"] = self.target_date
        return result


@dataclass
class CoworkProject:
    """A complete Cowork project definition."""

    name: str
    description: str = ""
    feature_slug: str = ""
    product_id: str = ""
    tasks: List[CoworkTask] = field(default_factory=list)
    milestones: List[CoworkMilestone] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "feature_slug": self.feature_slug,
            "product_id": self.product_id,
            "tasks": [t.to_dict() for t in self.tasks],
            "milestones": [m.to_dict() for m in self.milestones],
            "created_at": self.created_at,
        }


class CoworkProjectGenerator:
    """Generates Cowork project files from feature state.

    Creates structured project files that can be used by Claude Cowork
    to understand the feature context, remaining tasks, and dependencies.
    """

    def __init__(self):
        """Initialize the Cowork project generator."""
        pass

    def generate_from_feature(
        self,
        feature_path: Path,
        output_path: Optional[Path] = None,
    ) -> Optional[Path]:
        """Generate a Cowork project file from a feature's current state.

        Args:
            feature_path: Path to the feature folder
            output_path: Optional output path. Defaults to feature_path/.cowork-project.yaml

        Returns:
            Path to generated file, or None if generation failed
        """
        try:
            from pm_os_cce.tools.feature.feature_state import FeatureState
        except ImportError:
            from feature.feature_state import FeatureState

        state = FeatureState.load(feature_path)
        if not state:
            logger.error(f"Could not load feature state from {feature_path}")
            return None

        project = self._build_project(state, feature_path)

        if output_path is None:
            output_path = feature_path / ".cowork-project.yaml"

        try:
            with open(output_path, "w") as f:
                yaml.dump(
                    project.to_dict(),
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )
            logger.info(f"Generated Cowork project at {output_path}")
            return output_path
        except (IOError, OSError) as e:
            logger.error(f"Failed to write Cowork project: {e}")
            return None

    def _build_project(self, state: Any, feature_path: Path) -> CoworkProject:
        """Build a CoworkProject from feature state.

        Args:
            state: FeatureState instance
            feature_path: Path to feature folder

        Returns:
            CoworkProject with tasks and milestones
        """
        project = CoworkProject(
            name=state.title or feature_path.name,
            description=f"Feature: {state.title}. Phase: {state.current_phase.value}",
            feature_slug=state.slug or feature_path.name,
            product_id=state.product_id or "",
        )

        tasks = []
        milestones = []

        # Generate tasks based on tracks and their status
        track_task_map = {}

        for track_name, track in state.tracks.items():
            track_tasks = self._generate_track_tasks(track_name, track, state)
            tasks.extend(track_tasks)
            track_task_map[track_name] = [t.id for t in track_tasks]

        # Generate milestones from phase progression
        milestones = self._generate_milestones(state, track_task_map)

        project.tasks = tasks
        project.milestones = milestones

        return project

    def _generate_track_tasks(
        self, track_name: str, track: Any, state: Any
    ) -> List[CoworkTask]:
        """Generate tasks for a specific track.

        Args:
            track_name: Name of the track
            track: TrackState instance
            state: FeatureState instance

        Returns:
            List of CoworkTask objects
        """
        tasks = []

        try:
            from pm_os_cce.tools.feature.feature_state import TrackStatus
        except ImportError:
            from feature.feature_state import TrackStatus

        # Map track status to task status
        if track.status == TrackStatus.COMPLETE:
            task_status = "complete"
        elif track.status == TrackStatus.IN_PROGRESS:
            task_status = "in_progress"
        elif track.status == TrackStatus.BLOCKED:
            task_status = "blocked"
        else:
            task_status = "pending"

        # Create main track task
        main_task = CoworkTask(
            id=f"{track_name}-main",
            name=f"{track_name.replace('_', ' ').title()} Track",
            description=f"Complete the {track_name} track. Current step: {track.current_step or 'not started'}",
            status=task_status,
            track=track_name,
            estimated_minutes=self._estimate_track_minutes(track_name),
        )
        tasks.append(main_task)

        # Add sub-tasks based on track type
        if track_name == "context" and track.status != TrackStatus.COMPLETE:
            tasks.append(CoworkTask(
                id="context-generate",
                name="Generate context document",
                description="Create initial context document from feature info",
                status="complete" if track.current_version and track.current_version >= 1 else "pending",
                track="context",
                estimated_minutes=15,
            ))
            tasks.append(CoworkTask(
                id="context-challenge",
                name="Run orthogonal challenge",
                description="Challenge context document for quality",
                status="complete" if track.current_version and track.current_version >= 2 else "pending",
                depends_on=["context-generate"],
                track="context",
                estimated_minutes=10,
            ))
            tasks.append(CoworkTask(
                id="context-finalize",
                name="Finalize context document",
                description="Iterate and finalize context document (v3)",
                status="complete" if track.status == TrackStatus.COMPLETE else "pending",
                depends_on=["context-challenge"],
                track="context",
                estimated_minutes=20,
            ))

        elif track_name == "business_case" and track.status != TrackStatus.COMPLETE:
            tasks.append(CoworkTask(
                id="bc-assumptions",
                name="Define business case assumptions",
                description="Set baseline metrics and impact assumptions",
                status=task_status,
                track="business_case",
                estimated_minutes=20,
            ))
            tasks.append(CoworkTask(
                id="bc-approval",
                name="Get stakeholder approval",
                description="Submit business case for approval",
                status=task_status,
                depends_on=["bc-assumptions"],
                track="business_case",
                estimated_minutes=5,
            ))

        elif track_name == "engineering" and track.status != TrackStatus.COMPLETE:
            tasks.append(CoworkTask(
                id="eng-estimate",
                name="Provide engineering estimate",
                description="Add size estimate (S/M/L/XL)",
                status=task_status,
                track="engineering",
                estimated_minutes=10,
            ))
            tasks.append(CoworkTask(
                id="eng-risks",
                name="Identify and mitigate risks",
                description="Document risks and mitigation plans",
                status=task_status,
                track="engineering",
                estimated_minutes=15,
            ))

        return tasks

    def _generate_milestones(
        self, state: Any, track_task_map: Dict[str, List[str]]
    ) -> List[CoworkMilestone]:
        """Generate milestones from phase progression."""
        milestones = []

        # Context complete milestone
        context_tasks = track_task_map.get("context", [])
        if context_tasks:
            milestones.append(CoworkMilestone(
                id="ms-context-complete",
                name="Context Document Complete",
                description="Context document finalized and passed quality challenge",
                tasks=context_tasks,
            ))

        # Decision gate milestone
        all_track_tasks = []
        for tasks in track_task_map.values():
            all_track_tasks.extend(tasks)

        milestones.append(CoworkMilestone(
            id="ms-decision-gate",
            name="Decision Gate",
            description="All tracks complete, ready for go/no-go decision",
            tasks=all_track_tasks,
        ))

        return milestones

    def _estimate_track_minutes(self, track_name: str) -> int:
        """Estimate minutes for a track based on type."""
        estimates = {
            "context": 45,
            "business_case": 30,
            "engineering": 25,
            "design": 20,
        }
        return estimates.get(track_name, 30)

    def update_project_from_state(
        self, feature_path: Path
    ) -> Optional[Path]:
        """Re-generate the Cowork project file from current state.

        Convenience method that regenerates the project file,
        updating task statuses based on current feature state.

        Args:
            feature_path: Path to the feature folder

        Returns:
            Path to updated file, or None if update failed
        """
        return self.generate_from_feature(feature_path)
