"""
PM-OS CCE Feature State Management (v5.0)

Manages the feature-state.yaml file that tracks engine-specific state
without modifying the existing context file format. Provides data classes
for feature lifecycle phases, track statuses, decisions, and aliases.

Usage:
    from pm_os_cce.tools.feature.feature_state import FeatureState, FeaturePhase
"""

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class FeaturePhase(Enum):
    """Feature lifecycle phases."""

    INITIALIZATION = "initialization"
    QUESTIONNAIRE = "questionnaire"
    DEEP_RESEARCH = "deep_research"
    SIGNAL_ANALYSIS = "signal_analysis"
    CONTEXT_DOC = "context_doc"
    PARALLEL_TRACKS = "parallel_tracks"
    DECISION_GATE = "decision_gate"
    OUTPUT_GENERATION = "output_generation"
    COMPLETE = "complete"
    ARCHIVED = "archived"
    DEFERRED = "deferred"


class TrackStatus(Enum):
    """Status values for parallel tracks."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PENDING_INPUT = "pending_input"
    PENDING_APPROVAL = "pending_approval"
    COMPLETE = "complete"
    BLOCKED = "blocked"


class GateState(Enum):
    """Input gate states."""

    DRAFT = "draft"
    PENDING_INPUT = "pending_input"
    PROCESSING = "processing"
    DEFERRED = "deferred"
    ARCHIVED = "archived"
    COMPLETE = "complete"


@dataclass
class PhaseEntry:
    """Records a phase transition in history."""

    phase: str
    entered: datetime
    completed: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result = {
            "phase": self.phase,
            "entered": self.entered.isoformat(),
        }
        if self.completed:
            result["completed"] = self.completed.isoformat()
        if self.metadata:
            result.update(self.metadata)
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhaseEntry":
        """Create from dictionary."""
        entered = datetime.fromisoformat(data["entered"])
        completed = None
        if data.get("completed"):
            completed = datetime.fromisoformat(data["completed"])
        metadata = {
            k: v for k, v in data.items() if k not in ("phase", "entered", "completed")
        }
        return cls(
            phase=data["phase"], entered=entered, completed=completed, metadata=metadata
        )


@dataclass
class TrackState:
    """State for a single track (context, design, business_case, engineering)."""

    status: TrackStatus = TrackStatus.NOT_STARTED
    current_version: Optional[int] = None
    current_step: Optional[str] = None
    file: Optional[str] = None
    artifacts: Dict[str, Optional[str]] = field(default_factory=dict)
    approvals: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result = {"status": self.status.value}
        if self.current_version is not None:
            result["current_version"] = self.current_version
        if self.current_step:
            result["current_step"] = self.current_step
        if self.file:
            result["file"] = self.file
        if self.artifacts:
            result["artifacts"] = self.artifacts
        if self.approvals:
            result["approvals"] = self.approvals
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrackState":
        """Create from dictionary."""
        return cls(
            status=TrackStatus(data.get("status", "not_started")),
            current_version=data.get("current_version"),
            current_step=data.get("current_step"),
            file=data.get("file"),
            artifacts=data.get("artifacts", {}),
            approvals=data.get("approvals", []),
        )


@dataclass
class Decision:
    """Records a decision made during feature development."""

    date: datetime
    phase: str
    decision: str
    rationale: str
    decided_by: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "date": self.date.isoformat(),
            "phase": self.phase,
            "decision": self.decision,
            "rationale": self.rationale,
            "decided_by": self.decided_by,
        }
        result.update(self.metadata)
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Decision":
        """Create from dictionary."""
        date = datetime.fromisoformat(data["date"])
        metadata = {
            k: v
            for k, v in data.items()
            if k not in ("date", "phase", "decision", "rationale", "decided_by")
        }
        return cls(
            date=date,
            phase=data["phase"],
            decision=data["decision"],
            rationale=data.get("rationale", ""),
            decided_by=data["decided_by"],
            metadata=metadata,
        )


@dataclass
class AliasInfo:
    """Alias information for feature name matching.

    Stores primary name from Master Sheet and known aliases from various sources.
    """

    primary_name: str
    known_aliases: List[str] = field(default_factory=list)
    auto_detected: bool = False
    alias_sources: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result = {
            "primary_name": self.primary_name,
            "known_aliases": self.known_aliases,
            "auto_detected": self.auto_detected,
        }
        if self.alias_sources:
            result["alias_sources"] = self.alias_sources
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AliasInfo":
        """Create from dictionary."""
        return cls(
            primary_name=data.get("primary_name", ""),
            known_aliases=data.get("known_aliases", []),
            auto_detected=data.get("auto_detected", False),
            alias_sources=data.get("alias_sources", {}),
        )

    def add_alias(self, alias_name: str, source: Optional[str] = None) -> bool:
        """Add a new alias if not already known.

        Args:
            alias_name: The alias to add.
            source: Optional source of the alias.

        Returns:
            True if alias was added, False if already exists.
        """
        normalized = alias_name.strip()
        if normalized.lower() == self.primary_name.lower():
            return False
        for existing in self.known_aliases:
            if existing.lower() == normalized.lower():
                return False
        self.known_aliases.append(normalized)
        if source:
            self.alias_sources[normalized] = source
        return True

    def get_all_names(self) -> List[str]:
        """Get all known names for this feature."""
        return [self.primary_name] + self.known_aliases

    def is_known_alias(self, name: str) -> bool:
        """Check if a name matches the primary name or any known alias."""
        normalized = name.strip().lower()
        if normalized == self.primary_name.lower():
            return True
        for alias in self.known_aliases:
            if normalized == alias.lower():
                return True
        return False

    def set_primary_name(
        self, new_primary: str, keep_old_as_alias: bool = True
    ) -> None:
        """Update the primary name, optionally keeping the old one as an alias."""
        if keep_old_as_alias and self.primary_name:
            self.add_alias(self.primary_name, source="primary_change")
        self.primary_name = new_primary.strip()

    def merge_aliases(self, other: "AliasInfo") -> None:
        """Merge aliases from another AliasInfo into this one."""
        if other.primary_name:
            self.add_alias(other.primary_name, source="merge")
        for alias in other.known_aliases:
            source = other.alias_sources.get(alias, "merge")
            self.add_alias(alias, source=source)


@dataclass
class FeatureState:
    """Complete state for a feature being processed by the Context Creation Engine.

    Stored in feature-state.yaml within the feature folder.
    """

    slug: str
    title: str
    product_id: str
    organization: str

    # Links to existing PM-OS structure
    context_file: str
    brain_entity: str
    master_sheet_row: Optional[int] = None

    # Timestamps
    created: datetime = field(default_factory=datetime.now)
    created_by: str = ""

    # Engine state
    current_phase: FeaturePhase = FeaturePhase.INITIALIZATION
    phase_history: List[PhaseEntry] = field(default_factory=list)

    # Track states
    tracks: Dict[str, TrackState] = field(
        default_factory=lambda: {
            "context": TrackState(),
            "design": TrackState(),
            "business_case": TrackState(),
            "engineering": TrackState(),
        }
    )

    # External artifacts
    artifacts: Dict[str, Optional[str]] = field(
        default_factory=lambda: {
            "jira_epic": None,
            "figma": None,
            "confluence_page": None,
            "wireframes_url": None,
        }
    )

    # Decisions made during flow
    decisions: List[Decision] = field(default_factory=list)

    # Alias information
    aliases: Optional[AliasInfo] = None

    # Discovery results summary
    discovery: Optional[Dict[str, Any]] = None

    # Questionnaire answers
    questionnaire: Optional[Dict[str, Any]] = None

    # Research plan summary
    research_plan: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result = {
            "slug": self.slug,
            "title": self.title,
            "product_id": self.product_id,
            "organization": self.organization,
            "context_file": self.context_file,
            "brain_entity": self.brain_entity,
            "created": self.created.isoformat(),
            "created_by": self.created_by,
            "engine": {
                "current_phase": self.current_phase.value,
                "phase_history": [p.to_dict() for p in self.phase_history],
                "tracks": {k: v.to_dict() for k, v in self.tracks.items()},
                **({"discovery": self.discovery} if self.discovery else {}),
            },
            "artifacts": self.artifacts,
            "decisions": [d.to_dict() for d in self.decisions],
        }
        if self.master_sheet_row is not None:
            result["master_sheet_row"] = self.master_sheet_row
        if self.aliases:
            result["aliases"] = self.aliases.to_dict()
        if self.questionnaire:
            result["questionnaire"] = self.questionnaire
        if self.research_plan:
            result["research_plan"] = self.research_plan
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeatureState":
        """Create FeatureState from dictionary."""
        engine = data.get("engine", {})
        phase_history = [
            PhaseEntry.from_dict(p) for p in engine.get("phase_history", [])
        ]
        tracks = {}
        for track_name in ["context", "design", "business_case", "engineering"]:
            track_data = engine.get("tracks", {}).get(track_name, {})
            tracks[track_name] = TrackState.from_dict(track_data)
        decisions = [Decision.from_dict(d) for d in data.get("decisions", [])]
        aliases = None
        if data.get("aliases"):
            aliases = AliasInfo.from_dict(data["aliases"])
        discovery = engine.get("discovery")
        return cls(
            slug=data["slug"],
            title=data["title"],
            product_id=data["product_id"],
            organization=data["organization"],
            context_file=data["context_file"],
            brain_entity=data["brain_entity"],
            master_sheet_row=data.get("master_sheet_row"),
            created=datetime.fromisoformat(data["created"]),
            created_by=data.get("created_by", ""),
            current_phase=FeaturePhase(engine.get("current_phase", "initialization")),
            phase_history=phase_history,
            tracks=tracks,
            artifacts=data.get("artifacts", {}),
            decisions=decisions,
            aliases=aliases,
            discovery=discovery,
            questionnaire=data.get("questionnaire"),
            research_plan=data.get("research_plan"),
        )

    def save(self, feature_path: Path) -> Path:
        """Save state to feature-state.yaml."""
        state_file = feature_path / "feature-state.yaml"
        with open(state_file, "w") as f:
            yaml.dump(
                self.to_dict(),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )
        return state_file

    @classmethod
    def load(cls, feature_path: Path) -> Optional["FeatureState"]:
        """Load state from feature-state.yaml."""
        state_file = feature_path / "feature-state.yaml"
        if not state_file.exists():
            return None
        with open(state_file, "r") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)

    def enter_phase(self, phase: FeaturePhase, metadata: Optional[Dict] = None) -> None:
        """Transition to a new phase."""
        if self.phase_history:
            self.phase_history[-1].completed = datetime.now()
        entry = PhaseEntry(
            phase=phase.value, entered=datetime.now(), metadata=metadata or {}
        )
        self.phase_history.append(entry)
        self.current_phase = phase

    def add_decision(
        self,
        decision: str,
        rationale: str,
        decided_by: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Record a decision made during feature development."""
        self.decisions.append(
            Decision(
                date=datetime.now(),
                phase=self.current_phase.value,
                decision=decision,
                rationale=rationale,
                decided_by=decided_by,
                metadata=metadata or {},
            )
        )

    def update_track(
        self, track_name: str, status: Optional[TrackStatus] = None, **kwargs
    ) -> None:
        """Update a track's state."""
        if track_name not in self.tracks:
            raise ValueError(f"Unknown track: {track_name}")
        track = self.tracks[track_name]
        if status:
            track.status = status
        for key, value in kwargs.items():
            if hasattr(track, key):
                setattr(track, key, value)

    def add_artifact(self, artifact_type: str, url: str) -> None:
        """Add an external artifact."""
        self.artifacts[artifact_type] = url

    # ========== Alias Management Methods ==========

    def init_aliases(self, primary_name: str, auto_detected: bool = False) -> None:
        """Initialize alias info for this feature."""
        self.aliases = AliasInfo(primary_name=primary_name, auto_detected=auto_detected)

    def add_alias(self, alias_name: str, source: Optional[str] = None) -> bool:
        """Add an alias to this feature."""
        if self.aliases is None:
            self.init_aliases(self.title)
        return self.aliases.add_alias(alias_name, source)

    def get_all_names(self) -> List[str]:
        """Get all known names for this feature (primary + aliases)."""
        if self.aliases is None:
            return [self.title]
        return self.aliases.get_all_names()

    def is_known_alias(self, name: str) -> bool:
        """Check if a name matches this feature (primary or any alias)."""
        if name.strip().lower() == self.title.lower():
            return True
        if self.aliases is None:
            return False
        return self.aliases.is_known_alias(name)

    def set_primary_name(
        self, new_primary: str, keep_old_as_alias: bool = True
    ) -> None:
        """Update the primary name for this feature."""
        if self.aliases is None:
            self.init_aliases(new_primary)
        else:
            self.aliases.set_primary_name(new_primary, keep_old_as_alias)

    def merge_feature_aliases(self, other: "FeatureState") -> None:
        """Merge aliases from another feature into this one."""
        if self.aliases is None:
            self.init_aliases(self.title)
        if other.aliases is not None:
            self.aliases.merge_aliases(other.aliases)
        else:
            self.aliases.add_alias(other.title, source="merge")

    # ========== Phase History and Decision Tracking ==========

    def record_phase_transition(
        self,
        from_phase: FeaturePhase,
        to_phase: FeaturePhase,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PhaseEntry:
        """Record a phase transition with optional metadata."""
        now = datetime.now()
        if self.phase_history:
            last_entry = self.phase_history[-1]
            if last_entry.phase == from_phase.value and not last_entry.completed:
                last_entry.completed = now
                if metadata:
                    last_entry.metadata.update(metadata)
        new_entry = PhaseEntry(phase=to_phase.value, entered=now, metadata={})
        self.phase_history.append(new_entry)
        self.current_phase = to_phase
        return new_entry

    def record_decision(
        self,
        phase: str,
        decision: str,
        rationale: str,
        decided_by: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """Record a decision made during feature development."""
        decision_entry = Decision(
            date=datetime.now(),
            phase=phase,
            decision=decision,
            rationale=rationale,
            decided_by=decided_by,
            metadata=metadata or {},
        )
        self.decisions.append(decision_entry)
        return decision_entry

    def get_phase_history(self) -> List[Dict[str, Any]]:
        """Get the complete phase history as a list of dictionaries."""
        return [entry.to_dict() for entry in self.phase_history]

    def get_decisions(self, phase: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get decisions, optionally filtered by phase."""
        if phase:
            return [d.to_dict() for d in self.decisions if d.phase == phase]
        return [d.to_dict() for d in self.decisions]

    def get_current_phase_duration(self) -> Optional[float]:
        """Get how long the feature has been in the current phase (in hours)."""
        if not self.phase_history:
            return None
        last_entry = self.phase_history[-1]
        if last_entry.completed:
            return None
        duration = datetime.now() - last_entry.entered
        return duration.total_seconds() / 3600

    def get_phase_summary(self) -> Dict[str, Any]:
        """Get a summary of phase progression for status display."""
        completed_phases = [e for e in self.phase_history if e.completed]
        return {
            "current_phase": self.current_phase.value,
            "phases_completed": len(completed_phases),
            "total_phases": len(self.phase_history),
            "hours_in_current_phase": self.get_current_phase_duration(),
            "last_transition": (
                self.phase_history[-1].entered.isoformat()
                if self.phase_history
                else None
            ),
        }

    @property
    def all_tracks_complete(self) -> bool:
        """Check if all tracks are complete."""
        return all(t.status == TrackStatus.COMPLETE for t in self.tracks.values())

    @property
    def any_track_in_progress(self) -> bool:
        """Check if any track is in progress (including pending states)."""
        in_progress_statuses = (
            TrackStatus.IN_PROGRESS,
            TrackStatus.PENDING_INPUT,
            TrackStatus.PENDING_APPROVAL,
        )
        return any(t.status in in_progress_statuses for t in self.tracks.values())

    def get_derived_status(self) -> str:
        """Derive overall status from track completion states."""
        if self.all_tracks_complete:
            return "Done"
        elif self.any_track_in_progress:
            return "In Progress"
        else:
            return "To Do"

    @classmethod
    def create_initial_state(
        cls,
        title: str,
        product_id: str,
        organization: str,
        created_by: str,
        master_sheet_row: Optional[int] = None,
    ) -> "FeatureState":
        """Create an initial feature state with all fields properly initialized."""
        slug = generate_slug(title, product_id)
        brain_entity = f"[[Entities/{generate_brain_entity_name(title)}]]"
        context_file = f"{slug}-context.md"
        state = cls(
            slug=slug,
            title=title,
            product_id=product_id,
            organization=organization,
            context_file=context_file,
            brain_entity=brain_entity,
            master_sheet_row=master_sheet_row,
            created=datetime.now(),
            created_by=created_by,
            current_phase=FeaturePhase.INITIALIZATION,
            phase_history=[],
            tracks={
                "context": TrackState(status=TrackStatus.NOT_STARTED),
                "design": TrackState(status=TrackStatus.NOT_STARTED),
                "business_case": TrackState(status=TrackStatus.NOT_STARTED),
                "engineering": TrackState(status=TrackStatus.NOT_STARTED),
            },
            artifacts={
                "jira_epic": None,
                "figma": None,
                "confluence_page": None,
                "wireframes_url": None,
            },
            decisions=[],
            aliases=AliasInfo(primary_name=title),
        )
        state.enter_phase(FeaturePhase.INITIALIZATION)
        return state


def generate_slug(title: str, product_id: str) -> str:
    """Generate a feature slug from title and product.

    Args:
        title: Feature title.
        product_id: Product ID.

    Returns:
        Slug like ``prefix-feature-name``.
    """
    prefix = product_id[:3] if len(product_id) >= 3 else product_id
    slug_title = title.lower()
    slug_title = slug_title.replace(" ", "-")
    slug_title = "".join(c for c in slug_title if c.isalnum() or c == "-")
    slug_title = "-".join(filter(None, slug_title.split("-")))
    return f"{prefix}-{slug_title}"


def generate_brain_entity_name(title: str) -> str:
    """Generate Brain entity name from title.

    Args:
        title: Feature title.

    Returns:
        Entity name like ``Feature_Title``.
    """
    words = title.split()
    return "_".join(word.capitalize() for word in words)
