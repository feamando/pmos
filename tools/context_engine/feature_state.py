"""
Feature State Management

Manages the feature-state.yaml file that tracks engine-specific state
without modifying the existing context file format.

State File Structure:
    slug: feature-slug
    title: "Feature Title"
    product_id: meal-kit
    organization: growth-division
    context_file: feature-slug-context.md
    brain_entity: "[[Entities/Feature_Slug]]"
    master_sheet_row: 15
    created: 2026-02-02T10:30:00Z
    created_by: user
    engine:
        current_phase: design_track
        phase_history: [...]
        tracks:
            context: {status: complete, current_version: 3}
            design: {status: in_progress}
            business_case: {status: complete}
            engineering: {status: not_started}
    artifacts: {...}
    decisions: [...]
    aliases: {...}
"""

import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class FeaturePhase(Enum):
    """Feature lifecycle phases."""

    INITIALIZATION = "initialization"
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

        # Extract metadata (everything except phase, entered, completed)
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
    """
    Alias information for feature name matching.

    Stores primary name from Master Sheet and known aliases from various sources:
    - Manual consolidation (user confirmed)
    - Slack mentions with similar keywords
    - Jira ticket titles referencing same epic
    - Brain entity aliases

    Schema (from PRD C.7):
        aliases:
          primary_name: "MK OTP Flow Improvements"  # From Master Sheet
          known_aliases:
            - "OTP Checkout Recovery"
            - "OTP Recovery"
            - "checkout otp fix"  # From Slack mention
          auto_detected: true  # Whether aliases were auto-consolidated
    """

    primary_name: str
    known_aliases: List[str] = field(default_factory=list)
    auto_detected: bool = False
    # Track sources for each alias (optional metadata)
    alias_sources: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result = {
            "primary_name": self.primary_name,
            "known_aliases": self.known_aliases,
            "auto_detected": self.auto_detected,
        }
        # Only include alias_sources if non-empty (keeps YAML clean)
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
        """
        Add a new alias if not already known.

        Args:
            alias_name: The alias to add
            source: Optional source of the alias (e.g., "slack", "jira", "user", "auto")

        Returns:
            True if alias was added, False if already exists
        """
        # Normalize for comparison
        normalized = alias_name.strip()

        # Check if this is the primary name
        if normalized.lower() == self.primary_name.lower():
            return False

        # Check if already in known_aliases (case-insensitive)
        for existing in self.known_aliases:
            if existing.lower() == normalized.lower():
                return False

        # Add the alias
        self.known_aliases.append(normalized)

        # Track source if provided
        if source:
            self.alias_sources[normalized] = source

        return True

    def get_all_names(self) -> List[str]:
        """
        Get all known names for this feature.

        Returns:
            List containing primary_name followed by all known_aliases
        """
        return [self.primary_name] + self.known_aliases

    def is_known_alias(self, name: str) -> bool:
        """
        Check if a name matches the primary name or any known alias.

        Args:
            name: The name to check

        Returns:
            True if name matches primary_name or any alias (case-insensitive)
        """
        normalized = name.strip().lower()

        # Check primary name
        if normalized == self.primary_name.lower():
            return True

        # Check known aliases
        for alias in self.known_aliases:
            if normalized == alias.lower():
                return True

        return False

    def set_primary_name(
        self, new_primary: str, keep_old_as_alias: bool = True
    ) -> None:
        """
        Update the primary name, optionally keeping the old one as an alias.

        Args:
            new_primary: The new primary name
            keep_old_as_alias: If True, move old primary to known_aliases
        """
        if keep_old_as_alias and self.primary_name:
            self.add_alias(self.primary_name, source="primary_change")
        self.primary_name = new_primary.strip()

    def merge_aliases(self, other: "AliasInfo") -> None:
        """
        Merge aliases from another AliasInfo into this one.

        Useful when consolidating duplicate features.

        Args:
            other: Another AliasInfo to merge from
        """
        # Add other's primary as alias
        if other.primary_name:
            self.add_alias(other.primary_name, source="merge")

        # Add all of other's aliases
        for alias in other.known_aliases:
            source = other.alias_sources.get(alias, "merge")
            self.add_alias(alias, source=source)


@dataclass
class FeatureState:
    """
    Complete state for a feature being processed by the Context Creation Engine.

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
            },
            "artifacts": self.artifacts,
            "decisions": [d.to_dict() for d in self.decisions],
        }

        if self.master_sheet_row is not None:
            result["master_sheet_row"] = self.master_sheet_row

        if self.aliases:
            result["aliases"] = self.aliases.to_dict()

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeatureState":
        """Create FeatureState from dictionary."""
        engine = data.get("engine", {})

        # Parse phase history
        phase_history = [
            PhaseEntry.from_dict(p) for p in engine.get("phase_history", [])
        ]

        # Parse tracks
        tracks = {}
        for track_name in ["context", "design", "business_case", "engineering"]:
            track_data = engine.get("tracks", {}).get(track_name, {})
            tracks[track_name] = TrackState.from_dict(track_data)

        # Parse decisions
        decisions = [Decision.from_dict(d) for d in data.get("decisions", [])]

        # Parse aliases
        aliases = None
        if data.get("aliases"):
            aliases = AliasInfo.from_dict(data["aliases"])

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
        )

    def save(self, feature_path: Path) -> Path:
        """
        Save state to feature-state.yaml.

        Args:
            feature_path: Path to the feature folder

        Returns:
            Path to the saved file
        """
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
        """
        Load state from feature-state.yaml.

        Args:
            feature_path: Path to the feature folder

        Returns:
            FeatureState or None if file doesn't exist
        """
        state_file = feature_path / "feature-state.yaml"

        if not state_file.exists():
            return None

        with open(state_file, "r") as f:
            data = yaml.safe_load(f)

        return cls.from_dict(data)

    def enter_phase(self, phase: FeaturePhase, metadata: Optional[Dict] = None) -> None:
        """
        Transition to a new phase.

        Args:
            phase: The phase to enter
            metadata: Optional metadata for the transition
        """
        # Complete current phase if there is one
        if self.phase_history:
            self.phase_history[-1].completed = datetime.now()

        # Create new phase entry
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
        """
        Record a decision made during feature development.

        Args:
            decision: What was decided
            rationale: Why this decision was made
            decided_by: Who made the decision
            metadata: Optional additional data
        """
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
        """
        Update a track's state.

        Args:
            track_name: Name of track (context, design, business_case, engineering)
            status: New status for the track
            **kwargs: Additional fields to update
        """
        if track_name not in self.tracks:
            raise ValueError(f"Unknown track: {track_name}")

        track = self.tracks[track_name]

        if status:
            track.status = status

        for key, value in kwargs.items():
            if hasattr(track, key):
                setattr(track, key, value)

    def add_artifact(self, artifact_type: str, url: str) -> None:
        """
        Add an external artifact.

        Args:
            artifact_type: Type of artifact (figma, jira_epic, etc.)
            url: URL or reference to the artifact
        """
        self.artifacts[artifact_type] = url

    # ========== Alias Management Methods ==========

    def init_aliases(self, primary_name: str, auto_detected: bool = False) -> None:
        """
        Initialize alias info for this feature.

        Args:
            primary_name: The primary name (typically from Master Sheet)
            auto_detected: Whether this was auto-detected vs. manually set
        """
        self.aliases = AliasInfo(primary_name=primary_name, auto_detected=auto_detected)

    def add_alias(self, alias_name: str, source: Optional[str] = None) -> bool:
        """
        Add an alias to this feature.

        Args:
            alias_name: The alias to add
            source: Optional source (e.g., "slack", "jira", "user", "auto")

        Returns:
            True if alias was added, False if already exists or no aliases initialized
        """
        if self.aliases is None:
            # Auto-initialize with title as primary if not set
            self.init_aliases(self.title)

        return self.aliases.add_alias(alias_name, source)

    def get_all_names(self) -> List[str]:
        """
        Get all known names for this feature (primary + aliases).

        Returns:
            List of all names, or [self.title] if no aliases configured
        """
        if self.aliases is None:
            return [self.title]
        return self.aliases.get_all_names()

    def is_known_alias(self, name: str) -> bool:
        """
        Check if a name matches this feature (primary or any alias).

        Args:
            name: The name to check

        Returns:
            True if name matches primary_name, any alias, or self.title
        """
        # Always check against the feature title
        if name.strip().lower() == self.title.lower():
            return True

        if self.aliases is None:
            return False

        return self.aliases.is_known_alias(name)

    def set_primary_name(
        self, new_primary: str, keep_old_as_alias: bool = True
    ) -> None:
        """
        Update the primary name for this feature.

        Args:
            new_primary: The new primary name
            keep_old_as_alias: If True, keep old primary as an alias
        """
        if self.aliases is None:
            self.init_aliases(new_primary)
        else:
            self.aliases.set_primary_name(new_primary, keep_old_as_alias)

    def merge_feature_aliases(self, other: "FeatureState") -> None:
        """
        Merge aliases from another feature into this one.

        Useful when consolidating duplicate features.

        Args:
            other: Another FeatureState to merge aliases from
        """
        if self.aliases is None:
            self.init_aliases(self.title)

        if other.aliases is not None:
            self.aliases.merge_aliases(other.aliases)
        else:
            # At minimum add the other feature's title as an alias
            self.aliases.add_alias(other.title, source="merge")

    # ========== Phase History and Decision Tracking ==========

    def record_phase_transition(
        self,
        from_phase: FeaturePhase,
        to_phase: FeaturePhase,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PhaseEntry:
        """
        Record a phase transition with optional metadata.

        This method provides explicit from/to phase tracking as required by PRD C.4.
        It completes the previous phase entry (if matching) and creates a new entry.

        Args:
            from_phase: The phase transitioning from
            to_phase: The phase transitioning to
            metadata: Optional metadata for the transition (e.g., insights_reviewed, insight_selected)

        Returns:
            The new PhaseEntry created

        Example:
            state.record_phase_transition(
                from_phase=FeaturePhase.SIGNAL_ANALYSIS,
                to_phase=FeaturePhase.CONTEXT_DOC,
                metadata={
                    "insights_reviewed": 5,
                    "insight_selected": "insight-otp-abandonment"
                }
            )

        YAML output:
            phase_history:
              - phase: signal_analysis
                entered: 2026-02-02T10:30:15Z
                completed: 2026-02-02T11:45:00Z
                insights_reviewed: 5
                insight_selected: insight-otp-abandonment
              - phase: context_doc
                entered: 2026-02-02T11:45:00Z
        """
        now = datetime.now()

        # Complete the from_phase entry if it exists and matches
        if self.phase_history:
            last_entry = self.phase_history[-1]
            if last_entry.phase == from_phase.value and not last_entry.completed:
                last_entry.completed = now
                # Merge metadata into the completed phase entry
                if metadata:
                    last_entry.metadata.update(metadata)

        # Create new phase entry for to_phase
        new_entry = PhaseEntry(
            phase=to_phase.value,
            entered=now,
            metadata={},  # Fresh metadata for the new phase
        )
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
        """
        Record a decision made during feature development.

        This method creates a decision record as specified in PRD C.4.
        Decisions are tracked with timestamp, phase, and attribution.

        Args:
            phase: The phase during which the decision was made (string, not enum)
            decision: What was decided
            rationale: Why this decision was made
            decided_by: Who made the decision (username)
            metadata: Optional additional data

        Returns:
            The Decision object created

        Example:
            state.record_decision(
                phase="context_doc",
                decision='Proceed with "remember device" approach',
                rationale="Best balance of UX and security",
                decided_by="jane.smith"
            )

        YAML output:
            decisions:
              - date: 2026-02-02T12:00:00Z
                phase: context_doc
                decision: Proceed with "remember device" approach
                rationale: Best balance of UX and security
                decided_by: jane.smith
        """
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
        """
        Get the complete phase history as a list of dictionaries.

        Returns phase history in the format specified by PRD C.4,
        suitable for display or serialization.

        Returns:
            List of phase entry dictionaries with phase, entered, completed, and metadata

        Example return:
            [
                {
                    "phase": "initialization",
                    "entered": "2026-02-02T10:30:00Z",
                    "completed": "2026-02-02T10:30:15Z"
                },
                {
                    "phase": "signal_analysis",
                    "entered": "2026-02-02T10:30:15Z",
                    "completed": "2026-02-02T11:45:00Z",
                    "insights_reviewed": 5,
                    "insight_selected": "insight-otp-abandonment"
                }
            ]
        """
        return [entry.to_dict() for entry in self.phase_history]

    def get_decisions(self, phase: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get decisions, optionally filtered by phase.

        Returns decisions in the format specified by PRD C.4,
        suitable for display or serialization.

        Args:
            phase: Optional phase to filter decisions by

        Returns:
            List of decision dictionaries

        Example return:
            [
                {
                    "date": "2026-02-02T12:00:00Z",
                    "phase": "context_doc",
                    "decision": "Proceed with 'remember device' approach",
                    "rationale": "Best balance of UX and security",
                    "decided_by": "jane.smith"
                }
            ]
        """
        if phase:
            return [d.to_dict() for d in self.decisions if d.phase == phase]
        return [d.to_dict() for d in self.decisions]

    def get_current_phase_duration(self) -> Optional[float]:
        """
        Get how long the feature has been in the current phase (in hours).

        Useful for stale feature detection and reporting.

        Returns:
            Duration in hours, or None if no phase history exists
        """
        if not self.phase_history:
            return None

        last_entry = self.phase_history[-1]
        if last_entry.completed:
            return None  # Phase is already completed

        duration = datetime.now() - last_entry.entered
        return duration.total_seconds() / 3600  # Convert to hours

    def get_phase_summary(self) -> Dict[str, Any]:
        """
        Get a summary of phase progression for status display.

        Returns:
            Dictionary with current phase, total phases completed, and time in current phase
        """
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
        # PRD C.5: Any track in progress/pending -> "In Progress"
        in_progress_statuses = (
            TrackStatus.IN_PROGRESS,
            TrackStatus.PENDING_INPUT,
            TrackStatus.PENDING_APPROVAL,
        )
        return any(t.status in in_progress_statuses for t in self.tracks.values())

    def get_derived_status(self) -> str:
        """
        Derive overall status from track completion states (PRD C.5).

        Rules:
            - All tracks complete -> "Done"
            - Any track in progress/pending -> "In Progress"
            - All tracks not started -> "To Do"

        Returns:
            "Done", "In Progress", or "To Do"
        """
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
        """
        Create an initial feature state with all fields properly initialized.

        This is a template generator that creates a feature-state.yaml with all
        fields from PRD Section C.4. Use this method when initializing a new
        feature to ensure all required fields are present.

        Args:
            title: Feature title (e.g., "OTP Checkout Recovery")
            product_id: Product ID (e.g., "meal-kit")
            organization: Organization ID (e.g., "growth-division")
            created_by: Username of creator (e.g., "jane.smith")
            master_sheet_row: Optional row number in Master Sheet "topics" tab

        Returns:
            FeatureState with all fields initialized to appropriate defaults

        Example:
            state = FeatureState.create_initial_state(
                title="OTP Checkout Recovery",
                product_id="meal-kit",
                organization="growth-division",
                created_by="jane.smith",
                master_sheet_row=15
            )
            state.save(feature_path)

        Generated YAML structure matches PRD C.4:
            slug: mk-feature-recovery
            title: "OTP Checkout Recovery"
            product_id: meal-kit
            organization: growth-division
            context_file: mk-feature-recovery-context.md
            brain_entity: "[[Entities/Goc_Otp_Recovery]]"
            master_sheet_row: 15
            created: 2026-02-02T10:30:00Z
            created_by: jane.smith
            engine:
              current_phase: initialization
              phase_history: [...]
              tracks: {...}
            artifacts: {...}
            aliases: {...}
            decisions: [...]
        """
        # Generate slug from title and product
        slug = generate_slug(title, product_id)

        # Generate brain entity reference
        brain_entity = f"[[Entities/{generate_brain_entity_name(title)}]]"

        # Generate context file name
        context_file = f"{slug}-context.md"

        # Create state with all required fields
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

        # Record initialization phase entry
        state.enter_phase(FeaturePhase.INITIALIZATION)

        return state


def generate_slug(title: str, product_id: str) -> str:
    """
    Generate a feature slug from title and product.

    Args:
        title: Feature title
        product_id: Product ID

    Returns:
        slug like "mk-feature-recovery"
    """
    # Get product prefix from first letters
    prefix = product_id[:3] if len(product_id) >= 3 else product_id

    # Clean and slugify title
    slug_title = title.lower()
    slug_title = slug_title.replace(" ", "-")
    slug_title = "".join(c for c in slug_title if c.isalnum() or c == "-")
    slug_title = "-".join(filter(None, slug_title.split("-")))  # Remove empty parts

    return f"{prefix}-{slug_title}"


def generate_brain_entity_name(title: str) -> str:
    """
    Generate Brain entity name from title.

    Args:
        title: Feature title

    Returns:
        Entity name like "Goc_Otp_Recovery"
    """
    # Convert to title case and replace spaces with underscores
    words = title.split()
    return "_".join(word.capitalize() for word in words)
