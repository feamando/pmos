"""
Input Gate State Machine

Manages user input gates throughout the feature lifecycle.
Each phase may require human decisions, approvals, or input.

State Transitions (from PRD A.3):
                    ┌──────────┐
                    │  DRAFT   │
                    └────┬─────┘
                         │ User initiates
                         ▼
                    ┌──────────┐
              ┌─────│ PENDING  │─────┐
              │     │  INPUT   │     │
              │     └────┬─────┘     │
         Defer│          │Approve    │Reject
              │          ▼           │
              │     ┌──────────┐     │
              │     │PROCESSING│     │
              │     └────┬─────┘     │
              │          │           │
              ▼          ▼           ▼
        ┌──────────┐┌──────────┐┌──────────┐
        │ DEFERRED ││  NEXT    ││ ARCHIVED │
        │          ││  PHASE   ││          │
        └──────────┘└──────────┘└──────────┘

Gate Actions:
    - Approve: Proceed to PROCESSING -> NEXT_PHASE (COMPLETE)
    - Request Changes: Stay in PENDING_INPUT, update content
    - Reject: Archive feature with reason (-> ARCHIVED)
    - Defer: Pause, set reminder date (-> DEFERRED)

Usage:
    from tools.context_engine import InputGate, GateAction

    gate = InputGate(
        gate_type="business_case_approval",
        feature_slug="mk-feature-recovery",
        phase="business_case"
    )

    # Check valid actions
    valid_actions = gate.get_valid_actions()

    # Check if specific action is possible
    if gate.can_transition(GateAction.APPROVE):
        result = gate.transition(GateAction.APPROVE, decided_by="user")

    # State persists to feature-state.yaml
    gate.save_to_feature_state(feature_state)
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class GateState(Enum):
    """
    States for an input gate (from PRD A.3).

    State Flow:
        DRAFT -> PENDING_INPUT -> PROCESSING -> COMPLETE (NEXT_PHASE)
                      |               |
                      +-> DEFERRED    |
                      |               |
                      +-> ARCHIVED <--+
    """

    DRAFT = "draft"
    PENDING_INPUT = "pending_input"
    PROCESSING = "processing"
    DEFERRED = "deferred"
    ARCHIVED = "archived"
    COMPLETE = "complete"  # Equivalent to NEXT_PHASE in PRD diagram


class GateAction(Enum):
    """Actions a user can take on a gate."""

    INITIATE = "initiate"  # DRAFT -> PENDING_INPUT
    APPROVE = "approve"  # PENDING_INPUT -> PROCESSING -> COMPLETE
    REQUEST_CHANGES = "request_changes"  # Stay in PENDING_INPUT
    REJECT = "reject"  # PENDING_INPUT -> ARCHIVED
    DEFER = "defer"  # PENDING_INPUT -> DEFERRED
    RESUME = "resume"  # DEFERRED -> PENDING_INPUT


# State machine transition table
# Maps (current_state, action) -> (new_state, requires_validation)
STATE_TRANSITIONS: Dict[Tuple[GateState, GateAction], Tuple[GateState, bool]] = {
    # From DRAFT
    (GateState.DRAFT, GateAction.INITIATE): (GateState.PENDING_INPUT, False),
    # From PENDING_INPUT
    (GateState.PENDING_INPUT, GateAction.APPROVE): (GateState.PROCESSING, True),
    (GateState.PENDING_INPUT, GateAction.REQUEST_CHANGES): (
        GateState.PENDING_INPUT,
        False,
    ),
    (GateState.PENDING_INPUT, GateAction.REJECT): (GateState.ARCHIVED, False),
    (GateState.PENDING_INPUT, GateAction.DEFER): (GateState.DEFERRED, False),
    # From PROCESSING (auto-transition to COMPLETE after processing)
    # PROCESSING is a transient state, automatically moves to COMPLETE
    # From DEFERRED
    (GateState.DEFERRED, GateAction.RESUME): (GateState.PENDING_INPUT, False),
    (GateState.DEFERRED, GateAction.REJECT): (GateState.ARCHIVED, False),
}


@dataclass
class StateChangeEntry:
    """Records a state change in gate history."""

    timestamp: datetime
    from_state: GateState
    to_state: GateState
    action: GateAction
    decided_by: str
    notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result = {
            "timestamp": self.timestamp.isoformat(),
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "action": self.action.value,
            "decided_by": self.decided_by,
        }
        if self.notes:
            result["notes"] = self.notes
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateChangeEntry":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            from_state=GateState(data["from_state"]),
            to_state=GateState(data["to_state"]),
            action=GateAction(data["action"]),
            decided_by=data["decided_by"],
            notes=data.get("notes"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class GateInput:
    """Defines an input required at a gate."""

    name: str
    description: str
    input_type: str  # text, url, choice, approval, date
    required: bool = True
    source: Optional[str] = None  # Where the value might come from
    default: Optional[Any] = None
    options: Optional[List[str]] = None  # For choice type
    validation: Optional[str] = None  # Validation rule name
    value: Optional[Any] = None


@dataclass
class GateResult:
    """Result of processing a gate action."""

    success: bool
    new_state: GateState
    message: str
    next_action: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class GatePhase(Enum):
    """
    Gate phases from PRD A.1.

    Each phase may have one or more gates requiring user input.
    """

    INSIGHT_SELECTION = "insight_selection"
    CONTEXT_APPROVAL = "context_approval"
    BC_APPROVAL = "bc_approval"
    DESIGN_APPROVAL = "design_approval"
    ADR_DECISIONS = "adr_decisions"
    DECISION_GATE = "decision_gate"


class InputGate:
    """
    Represents a user input gate in the feature lifecycle.

    Gates are decision points where human input is required before
    the engine can proceed. Implements a full state machine with
    transitions, validation, and history tracking.

    State Machine:
        DRAFT -> PENDING_INPUT -> PROCESSING -> COMPLETE
                      |
                      +-> DEFERRED (can resume)
                      |
                      +-> ARCHIVED (terminal)

    Usage:
        gate = InputGate(
            gate_type="business_case_approval",
            feature_slug="mk-feature-recovery",
            phase="business_case"
        )

        # Check valid actions
        valid = gate.get_valid_actions()  # ['approve', 'reject', 'defer', ...]

        # Check if transition is valid
        if gate.can_transition(GateAction.APPROVE):
            result = gate.transition(GateAction.APPROVE, decided_by="jane")

        # Save to feature state
        gate.save_to_feature_state(feature_state)
    """

    # Standard gate definitions per phase
    GATE_DEFINITIONS = {
        "insight_selection": {
            "name": "Insight Selection",
            "description": "PM decides which insight is worth pursuing",
            "blocking": True,
            "inputs": [
                GateInput(
                    name="selected_insight",
                    description="Which insight to pursue",
                    input_type="choice",
                    required=True,
                )
            ],
        },
        "enrichment_review": {
            "name": "Enrichment Review",
            "description": "Validate that context is accurate/complete",
            "blocking": True,
            "inputs": [
                GateInput(
                    name="approval",
                    description="Approve enriched context",
                    input_type="approval",
                    required=True,
                )
            ],
        },
        "context_doc_challenge": {
            "name": "Context Doc Challenge",
            "description": "Accept/reject orthogonal challenge findings",
            "blocking": True,
            "inputs": [
                GateInput(
                    name="challenge_response",
                    description="How to handle challenge findings",
                    input_type="choice",
                    options=["address_all", "address_critical", "proceed_anyway"],
                    required=True,
                )
            ],
        },
        "business_case_assumptions": {
            "name": "Business Case Assumptions",
            "description": "Provide/validate metric assumptions",
            "blocking": True,
            "inputs": [
                GateInput(
                    name="baseline_metrics",
                    description="Current state metrics",
                    input_type="text",
                    required=True,
                ),
                GateInput(
                    name="impact_assumptions",
                    description="Expected improvement",
                    input_type="text",
                    required=True,
                ),
            ],
        },
        "business_case_approval": {
            "name": "Business Case Approval",
            "description": "Stakeholder sign-off on business case",
            "blocking": True,
            "inputs": [
                GateInput(
                    name="approver_name",
                    description="Name of approver",
                    input_type="text",
                    required=True,
                ),
                GateInput(
                    name="approval_date",
                    description="Date of approval",
                    input_type="date",
                    required=True,
                ),
                GateInput(
                    name="approval_type",
                    description="Type of approval",
                    input_type="choice",
                    options=["verbal", "written", "email", "slack"],
                    required=False,
                    default="verbal",
                ),
            ],
        },
        "design_spec_review": {
            "name": "Design Spec Review",
            "description": "Validate requirements before design starts",
            "blocking": True,
            "inputs": [
                GateInput(
                    name="approval",
                    description="Approve design spec",
                    input_type="approval",
                    required=True,
                )
            ],
        },
        "wireframe_artifact": {
            "name": "Wireframe Input",
            "description": "Provide wireframe URL",
            "blocking": True,
            "inputs": [
                GateInput(
                    name="wireframe_url",
                    description="URL to wireframes",
                    input_type="url",
                    required=True,
                    validation="url_pattern",
                )
            ],
        },
        "figma_artifact": {
            "name": "Figma Design Input",
            "description": "Provide Figma design URL",
            "blocking": True,
            "inputs": [
                GateInput(
                    name="figma_url",
                    description="URL to Figma design",
                    input_type="url",
                    required=True,
                    validation="figma_url_pattern",
                )
            ],
        },
        "engineering_complexity": {
            "name": "Engineering Complexity",
            "description": "Validate effort estimates with eng lead",
            "blocking": False,  # Advisory only
            "inputs": [
                GateInput(
                    name="complexity_estimate",
                    description="T-shirt size or story points",
                    input_type="choice",
                    options=["XS", "S", "M", "L", "XL", "XXL"],
                    required=False,
                )
            ],
        },
        "adr_decision": {
            "name": "ADR Decision",
            "description": "Choose between technical options",
            "blocking": True,
            "inputs": [
                GateInput(
                    name="selected_option",
                    description="Selected option from ADR",
                    input_type="choice",
                    required=True,
                ),
                GateInput(
                    name="rationale",
                    description="Why this option was chosen",
                    input_type="text",
                    required=True,
                ),
            ],
        },
        "decision_gate": {
            "name": "Decision Gate",
            "description": "Final go/no-go decision",
            "blocking": True,
            "inputs": [
                GateInput(
                    name="decision",
                    description="Go/No-Go decision",
                    input_type="choice",
                    options=["proceed", "pivot", "kill"],
                    required=True,
                ),
                GateInput(
                    name="rationale",
                    description="Reason for decision",
                    input_type="text",
                    required=True,
                ),
            ],
        },
    }

    def __init__(
        self,
        gate_type: str,
        feature_slug: str,
        phase: str,
        state: GateState = GateState.DRAFT,
    ):
        """
        Initialize an input gate.

        Args:
            gate_type: Type of gate (from GATE_DEFINITIONS)
            feature_slug: Feature this gate belongs to
            phase: Current phase
            state: Initial state
        """
        self.gate_type = gate_type
        self.feature_slug = feature_slug
        self.phase = phase
        self.state = state

        # Get gate definition
        definition = self.GATE_DEFINITIONS.get(gate_type, {})
        self.name = definition.get("name", gate_type)
        self.description = definition.get("description", "")
        self.is_blocking = definition.get("blocking", True)

        # Initialize inputs from definition
        self.inputs: List[GateInput] = []
        for input_def in definition.get("inputs", []):
            if isinstance(input_def, GateInput):
                self.inputs.append(input_def)
            elif isinstance(input_def, dict):
                self.inputs.append(GateInput(**input_def))

        # Metadata
        self.created_at = datetime.now()
        self.completed_at: Optional[datetime] = None
        self.decided_by: Optional[str] = None
        self.notes: Optional[str] = None
        self.artifacts: List[str] = []

        # State change history
        self.state_history: List[StateChangeEntry] = []

        # Defer metadata
        self.defer_until: Optional[datetime] = None
        self.defer_reason: Optional[str] = None

    @property
    def is_complete(self) -> bool:
        """Check if all required inputs are provided."""
        for inp in self.inputs:
            if inp.required and inp.value is None:
                return False
        return True

    @property
    def missing_inputs(self) -> List[str]:
        """Get list of missing required inputs."""
        return [inp.name for inp in self.inputs if inp.required and inp.value is None]

    def set_input(self, name: str, value: Any) -> bool:
        """
        Set an input value.

        Args:
            name: Input name
            value: Value to set

        Returns:
            True if input was found and set
        """
        for inp in self.inputs:
            if inp.name == name:
                inp.value = value
                return True
        return False

    def get_input(self, name: str) -> Optional[Any]:
        """
        Get an input value.

        Args:
            name: Input name

        Returns:
            Input value or None
        """
        for inp in self.inputs:
            if inp.name == name:
                return inp.value
        return None

    # ========== State Machine Methods ==========

    def can_transition(self, action: GateAction) -> bool:
        """
        Check if a state transition is valid.

        Args:
            action: The action to check

        Returns:
            True if the transition is valid from current state
        """
        # Check if transition exists in state machine
        transition_key = (self.state, action)
        if transition_key not in STATE_TRANSITIONS:
            return False

        # For APPROVE action, check if all required inputs are provided
        _, requires_validation = STATE_TRANSITIONS[transition_key]
        if requires_validation and action == GateAction.APPROVE:
            if not self.is_complete:
                return False

        return True

    def get_valid_actions(self) -> List[GateAction]:
        """
        Get list of valid actions from current state.

        Returns:
            List of valid GateAction values
        """
        valid_actions = []

        for (state, action), (_, _) in STATE_TRANSITIONS.items():
            if state == self.state:
                # For APPROVE, only include if inputs are complete
                if action == GateAction.APPROVE and not self.is_complete:
                    continue
                valid_actions.append(action)

        return valid_actions

    def transition(
        self,
        action: GateAction,
        decided_by: str,
        notes: Optional[str] = None,
        defer_until: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GateResult:
        """
        Execute a state transition.

        This is the core state machine method that validates and executes
        transitions according to PRD A.3 state diagram.

        Args:
            action: Action to take
            decided_by: Who is taking the action
            notes: Optional notes/reason
            defer_until: For DEFER action, when to resume
            metadata: Optional additional data

        Returns:
            GateResult with transition outcome

        Example:
            result = gate.transition(GateAction.APPROVE, decided_by="jane")
            if result.success:
                print(f"New state: {result.new_state}")
        """
        # Validate transition
        if not self.can_transition(action):
            return GateResult(
                success=False,
                new_state=self.state,
                message=f"Invalid transition: {action.value} not allowed from {self.state.value}",
            )

        # Get target state
        transition_key = (self.state, action)
        target_state, _ = STATE_TRANSITIONS[transition_key]
        old_state = self.state

        # Record state change
        change_entry = StateChangeEntry(
            timestamp=datetime.now(),
            from_state=old_state,
            to_state=target_state,
            action=action,
            decided_by=decided_by,
            notes=notes,
            metadata=metadata or {},
        )
        self.state_history.append(change_entry)

        # Update state
        self.state = target_state
        self.decided_by = decided_by
        self.notes = notes

        # Handle specific actions
        if action == GateAction.APPROVE:
            # Move through PROCESSING to COMPLETE
            self.state = GateState.PROCESSING
            # Record processing state
            processing_entry = StateChangeEntry(
                timestamp=datetime.now(),
                from_state=GateState.PROCESSING,
                to_state=GateState.COMPLETE,
                action=action,
                decided_by=decided_by,
                notes="Auto-transition after approval",
                metadata={"auto_transition": True},
            )
            self.state_history.append(processing_entry)
            self.state = GateState.COMPLETE
            self.completed_at = datetime.now()

            return GateResult(
                success=True,
                new_state=GateState.COMPLETE,
                message=f"Gate '{self.name}' approved and complete",
                next_action="proceed_to_next_phase",
                metadata={
                    "transition_path": ["pending_input", "processing", "complete"]
                },
            )

        elif action == GateAction.DEFER:
            self.defer_until = defer_until
            self.defer_reason = notes
            return GateResult(
                success=True,
                new_state=GateState.DEFERRED,
                message=f"Gate '{self.name}' deferred",
                next_action="set_reminder",
                metadata={
                    "defer_until": defer_until.isoformat() if defer_until else None
                },
            )

        elif action == GateAction.REJECT:
            self.completed_at = datetime.now()
            return GateResult(
                success=True,
                new_state=GateState.ARCHIVED,
                message=f"Gate '{self.name}' rejected: {notes}",
                next_action="archive_feature",
            )

        elif action == GateAction.REQUEST_CHANGES:
            return GateResult(
                success=True,
                new_state=GateState.PENDING_INPUT,
                message=f"Changes requested for '{self.name}'",
                next_action="update_content",
                metadata={"requested_changes": notes},
            )

        elif action == GateAction.INITIATE:
            return GateResult(
                success=True,
                new_state=GateState.PENDING_INPUT,
                message=f"Gate '{self.name}' initiated, awaiting input",
                next_action="provide_inputs",
            )

        elif action == GateAction.RESUME:
            self.defer_until = None
            self.defer_reason = None
            return GateResult(
                success=True,
                new_state=GateState.PENDING_INPUT,
                message=f"Gate '{self.name}' resumed from deferred state",
                next_action="provide_inputs",
            )

        return GateResult(
            success=True,
            new_state=self.state,
            message=f"Transitioned to {self.state.value}",
        )

    def initiate(self, initiated_by: str = "system") -> GateResult:
        """
        Convenience method to initiate the gate (DRAFT -> PENDING_INPUT).

        Args:
            initiated_by: Who initiated the gate

        Returns:
            GateResult
        """
        return self.transition(GateAction.INITIATE, decided_by=initiated_by)

    def approve(self, decided_by: str, notes: Optional[str] = None) -> GateResult:
        """
        Convenience method to approve the gate.

        Args:
            decided_by: Who approved
            notes: Optional approval notes

        Returns:
            GateResult
        """
        return self.transition(GateAction.APPROVE, decided_by=decided_by, notes=notes)

    def reject(self, decided_by: str, reason: str) -> GateResult:
        """
        Convenience method to reject the gate.

        Args:
            decided_by: Who rejected
            reason: Rejection reason

        Returns:
            GateResult
        """
        return self.transition(GateAction.REJECT, decided_by=decided_by, notes=reason)

    def defer(
        self,
        decided_by: str,
        reason: Optional[str] = None,
        defer_until: Optional[datetime] = None,
    ) -> GateResult:
        """
        Convenience method to defer the gate.

        Args:
            decided_by: Who deferred
            reason: Why deferred
            defer_until: When to resume

        Returns:
            GateResult
        """
        return self.transition(
            GateAction.DEFER,
            decided_by=decided_by,
            notes=reason,
            defer_until=defer_until,
        )

    def resume(self, resumed_by: str) -> GateResult:
        """
        Convenience method to resume a deferred gate.

        Args:
            resumed_by: Who resumed

        Returns:
            GateResult
        """
        return self.transition(GateAction.RESUME, decided_by=resumed_by)

    def request_changes(self, decided_by: str, changes: str) -> GateResult:
        """
        Convenience method to request changes.

        Args:
            decided_by: Who requested changes
            changes: What changes are needed

        Returns:
            GateResult
        """
        return self.transition(
            GateAction.REQUEST_CHANGES, decided_by=decided_by, notes=changes
        )

    # ========== Gate-Specific Logic ==========

    def get_phase_specific_config(self) -> Dict[str, Any]:
        """
        Get phase-specific configuration for this gate.

        Different phases (INSIGHT_SELECTION, BC_APPROVAL, etc.) may have
        different validation rules, required inputs, and behavior.

        Returns:
            Phase-specific configuration dict
        """
        phase_configs = {
            "insight_selection": {
                "requires_single_selection": True,
                "auto_advance_on_selection": False,
                "validation_rules": ["insight_has_sources", "not_duplicate"],
            },
            "context_approval": {
                "requires_challenge_score": True,
                "min_challenge_score": 60,
                "requires_all_critical_addressed": True,
            },
            "bc_approval": {
                "requires_stakeholder": True,
                "requires_baseline_metrics": True,
                "roi_check": "warn_if_negative",
            },
            "design_approval": {
                "requires_spec_approval": True,
                "wireframes_optional": False,
                "figma_required_for_complete": True,
            },
            "adr_decisions": {
                "requires_all_adrs_decided": True,
                "requires_rationale": True,
            },
            "decision_gate": {
                "requires_all_tracks_complete": True,
                "requires_no_blocking_risks": True,
                "final_approval": True,
            },
        }
        return phase_configs.get(self.gate_type, {})

    def validate_for_phase(self) -> Tuple[bool, List[str]]:
        """
        Validate gate inputs against phase-specific requirements.

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        config = self.get_phase_specific_config()

        # Check required inputs
        for inp in self.inputs:
            if inp.required and inp.value is None:
                issues.append(f"Missing required input: {inp.name}")

        # Phase-specific validations
        if config.get("requires_challenge_score"):
            min_score = config.get("min_challenge_score", 60)
            score = self.get_input("challenge_score")
            if score is not None and score < min_score:
                issues.append(f"Challenge score {score} below minimum {min_score}")

        if config.get("requires_stakeholder"):
            approver = self.get_input("approver_name")
            if not approver:
                issues.append("Stakeholder approval required")

        if config.get("requires_rationale"):
            rationale = self.get_input("rationale")
            if not rationale:
                issues.append("Decision rationale required")

        return len(issues) == 0, issues

    # ========== State Persistence ==========

    def save_to_feature_state(self, feature_state: Any) -> None:
        """
        Save gate state to a FeatureState object.

        This integrates gate state with the feature-state.yaml persistence.

        Args:
            feature_state: FeatureState object to update
        """
        # Store gate data in feature state's engine section
        gate_data = self.to_dict()
        gate_data["state_history"] = [h.to_dict() for h in self.state_history]

        # Update the appropriate track based on gate type
        track_mapping = {
            "insight_selection": "context",
            "enrichment_review": "context",
            "context_doc_challenge": "context",
            "business_case_assumptions": "business_case",
            "business_case_approval": "business_case",
            "design_spec_review": "design",
            "wireframe_artifact": "design",
            "figma_artifact": "design",
            "engineering_complexity": "engineering",
            "adr_decision": "engineering",
            "decision_gate": None,  # Applies to overall feature
        }

        track_name = track_mapping.get(self.gate_type)
        if track_name and hasattr(feature_state, "tracks"):
            track = feature_state.tracks.get(track_name)
            if track:
                # Store gate state in track artifacts
                if not hasattr(track, "artifacts") or track.artifacts is None:
                    track.artifacts = {}
                track.artifacts[f"gate_{self.gate_type}"] = gate_data

    @classmethod
    def load_from_feature_state(
        cls, feature_state: Any, gate_type: str
    ) -> Optional["InputGate"]:
        """
        Load gate state from a FeatureState object.

        Args:
            feature_state: FeatureState object to load from
            gate_type: Type of gate to load

        Returns:
            InputGate or None if not found
        """
        track_mapping = {
            "insight_selection": "context",
            "enrichment_review": "context",
            "context_doc_challenge": "context",
            "business_case_assumptions": "business_case",
            "business_case_approval": "business_case",
            "design_spec_review": "design",
            "wireframe_artifact": "design",
            "figma_artifact": "design",
            "engineering_complexity": "engineering",
            "adr_decision": "engineering",
            "decision_gate": None,
        }

        track_name = track_mapping.get(gate_type)
        if not track_name or not hasattr(feature_state, "tracks"):
            return None

        track = feature_state.tracks.get(track_name)
        if not track or not hasattr(track, "artifacts"):
            return None

        gate_data = track.artifacts.get(f"gate_{gate_type}")
        if not gate_data:
            return None

        gate = cls.from_dict(gate_data)

        # Restore state history
        if "state_history" in gate_data:
            gate.state_history = [
                StateChangeEntry.from_dict(h) for h in gate_data["state_history"]
            ]

        return gate

    def process_action(
        self,
        action: GateAction,
        decided_by: str,
        notes: Optional[str] = None,
        defer_until: Optional[datetime] = None,
    ) -> GateResult:
        """
        Process a user action on the gate.

        Args:
            action: Action to take
            decided_by: Who is taking the action
            notes: Optional notes/reason
            defer_until: For DEFER action, when to resume

        Returns:
            GateResult with new state
        """
        self.decided_by = decided_by
        self.notes = notes

        if action == GateAction.APPROVE:
            if not self.is_complete:
                return GateResult(
                    success=False,
                    new_state=self.state,
                    message=f"Cannot approve: missing inputs {self.missing_inputs}",
                )

            self.state = GateState.COMPLETE
            self.completed_at = datetime.now()
            return GateResult(
                success=True,
                new_state=GateState.COMPLETE,
                message=f"Gate '{self.name}' approved",
                next_action="proceed_to_next_phase",
            )

        elif action == GateAction.REQUEST_CHANGES:
            self.state = GateState.PENDING_INPUT
            return GateResult(
                success=True,
                new_state=GateState.PENDING_INPUT,
                message=f"Changes requested for '{self.name}'",
                next_action="update_content",
                metadata={"requested_changes": notes},
            )

        elif action == GateAction.REJECT:
            self.state = GateState.ARCHIVED
            self.completed_at = datetime.now()
            return GateResult(
                success=True,
                new_state=GateState.ARCHIVED,
                message=f"Gate '{self.name}' rejected: {notes}",
                next_action="archive_feature",
            )

        elif action == GateAction.DEFER:
            self.state = GateState.DEFERRED
            return GateResult(
                success=True,
                new_state=GateState.DEFERRED,
                message=f"Gate '{self.name}' deferred",
                next_action="set_reminder",
                metadata={
                    "defer_until": defer_until.isoformat() if defer_until else None
                },
            )

        return GateResult(
            success=False, new_state=self.state, message=f"Unknown action: {action}"
        )

    def render(self) -> str:
        """
        Render the gate as a text interface.

        Returns:
            Formatted gate display string
        """
        lines = [
            "+" + "-" * 60 + "+",
            f"| INPUT REQUIRED: {self.name}".ljust(61) + "|",
            f"| Feature: {self.feature_slug}".ljust(61) + "|",
            f"| Phase: {self.phase}".ljust(61) + "|",
            "+" + "-" * 60 + "+",
            "|".ljust(62) + "|",
        ]

        # Description
        if self.description:
            lines.append(f"| {self.description}".ljust(61) + "|")
            lines.append("|".ljust(62) + "|")

        # Required inputs
        lines.append("| Required inputs:".ljust(61) + "|")
        for inp in self.inputs:
            if inp.required:
                status = "[x]" if inp.value else "[ ]"
                line = f"|   {status} {inp.name}: {inp.description}"
                lines.append(line.ljust(61) + "|")
        lines.append("|".ljust(62) + "|")

        # Actions
        lines.append("+" + "-" * 60 + "+")
        lines.append("| Available actions:".ljust(61) + "|")
        lines.append("|   [A] Approve - proceed to next phase".ljust(61) + "|")
        lines.append("|   [C] Request Changes".ljust(61) + "|")
        lines.append("|   [R] Reject - archive feature".ljust(61) + "|")
        lines.append("|   [D] Defer - pause, set reminder".ljust(61) + "|")
        lines.append("+" + "-" * 60 + "+")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert gate to dictionary for storage."""
        result = {
            "gate_type": self.gate_type,
            "feature_slug": self.feature_slug,
            "phase": self.phase,
            "state": self.state.value,
            "name": self.name,
            "is_blocking": self.is_blocking,
            "inputs": [
                {
                    "name": inp.name,
                    "value": inp.value,
                    "required": inp.required,
                    "input_type": inp.input_type,
                }
                for inp in self.inputs
            ],
            "created_at": self.created_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "decided_by": self.decided_by,
            "notes": self.notes,
            "state_history": [h.to_dict() for h in self.state_history],
        }

        # Add defer information if applicable
        if self.defer_until:
            result["defer_until"] = self.defer_until.isoformat()
        if self.defer_reason:
            result["defer_reason"] = self.defer_reason

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InputGate":
        """Create gate from dictionary."""
        gate = cls(
            gate_type=data["gate_type"],
            feature_slug=data["feature_slug"],
            phase=data["phase"],
            state=GateState(data.get("state", "draft")),
        )

        # Restore input values
        for inp_data in data.get("inputs", []):
            gate.set_input(inp_data["name"], inp_data.get("value"))

        gate.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("completed_at"):
            gate.completed_at = datetime.fromisoformat(data["completed_at"])
        gate.decided_by = data.get("decided_by")
        gate.notes = data.get("notes")

        # Restore state history
        if data.get("state_history"):
            gate.state_history = [
                StateChangeEntry.from_dict(h) for h in data["state_history"]
            ]

        # Restore defer information
        if data.get("defer_until"):
            gate.defer_until = datetime.fromisoformat(data["defer_until"])
        if data.get("defer_reason"):
            gate.defer_reason = data["defer_reason"]

        return gate


class GateManager:
    """
    Manages multiple gates for a feature.

    Tracks which gates are pending, complete, or blocking
    across the feature lifecycle. Provides persistence through
    feature-state.yaml integration.

    Usage:
        manager = GateManager(feature_slug="mk-feature-recovery")

        # Create and initiate a gate
        gate = manager.create_gate("business_case_approval", phase="business_case")
        manager.initiate_gate("business_case_approval", initiated_by="system")

        # Process user action
        result = manager.process_gate_action(
            "business_case_approval",
            GateAction.APPROVE,
            decided_by="jane"
        )

        # Save to feature state
        manager.save_to_feature_state(feature_state)
    """

    def __init__(self, feature_slug: str):
        """
        Initialize gate manager.

        Args:
            feature_slug: Feature to manage gates for
        """
        self.feature_slug = feature_slug
        self.gates: Dict[str, InputGate] = {}
        self._feature_state_path: Optional[Path] = None

    def create_gate(
        self, gate_type: str, phase: str, auto_initiate: bool = False
    ) -> InputGate:
        """
        Create a new gate.

        Args:
            gate_type: Type of gate
            phase: Current phase
            auto_initiate: If True, immediately initiate the gate

        Returns:
            Created gate
        """
        gate = InputGate(
            gate_type=gate_type, feature_slug=self.feature_slug, phase=phase
        )
        self.gates[gate_type] = gate

        if auto_initiate:
            gate.initiate()

        return gate

    def get_gate(self, gate_type: str) -> Optional[InputGate]:
        """
        Get a gate by type.

        Args:
            gate_type: Type of gate

        Returns:
            InputGate or None
        """
        return self.gates.get(gate_type)

    def initiate_gate(
        self, gate_type: str, initiated_by: str = "system"
    ) -> Optional[GateResult]:
        """
        Initiate a gate (DRAFT -> PENDING_INPUT).

        Args:
            gate_type: Type of gate to initiate
            initiated_by: Who initiated

        Returns:
            GateResult or None if gate not found
        """
        gate = self.gates.get(gate_type)
        if not gate:
            return None
        return gate.initiate(initiated_by)

    def process_gate_action(
        self,
        gate_type: str,
        action: GateAction,
        decided_by: str,
        notes: Optional[str] = None,
        defer_until: Optional[datetime] = None,
    ) -> Optional[GateResult]:
        """
        Process an action on a gate.

        Args:
            gate_type: Type of gate
            action: Action to take
            decided_by: Who is taking action
            notes: Optional notes
            defer_until: For DEFER action

        Returns:
            GateResult or None if gate not found
        """
        gate = self.gates.get(gate_type)
        if not gate:
            return None
        return gate.transition(
            action, decided_by=decided_by, notes=notes, defer_until=defer_until
        )

    def get_pending_gates(self) -> List[InputGate]:
        """Get all pending/blocking gates."""
        return [
            g
            for g in self.gates.values()
            if g.state in (GateState.DRAFT, GateState.PENDING_INPUT) and g.is_blocking
        ]

    def get_blocking_gates(self) -> List[InputGate]:
        """Get gates that are blocking progress."""
        return [
            g
            for g in self.gates.values()
            if g.state == GateState.PENDING_INPUT
            and g.is_blocking
            and not g.is_complete
        ]

    def get_deferred_gates(self) -> List[InputGate]:
        """Get all deferred gates."""
        return [g for g in self.gates.values() if g.state == GateState.DEFERRED]

    def get_completed_gates(self) -> List[InputGate]:
        """Get all completed gates."""
        return [g for g in self.gates.values() if g.state == GateState.COMPLETE]

    def all_gates_complete(self, gate_types: List[str]) -> bool:
        """
        Check if all specified gates are complete.

        Args:
            gate_types: List of gate types to check

        Returns:
            True if all are complete
        """
        for gate_type in gate_types:
            gate = self.gates.get(gate_type)
            if not gate or gate.state != GateState.COMPLETE:
                return False
        return True

    def get_gates_for_phase(self, phase: GatePhase) -> List[InputGate]:
        """
        Get all gates for a specific phase.

        Args:
            phase: GatePhase to filter by

        Returns:
            List of gates for that phase
        """
        phase_gate_mapping = {
            GatePhase.INSIGHT_SELECTION: ["insight_selection"],
            GatePhase.CONTEXT_APPROVAL: ["enrichment_review", "context_doc_challenge"],
            GatePhase.BC_APPROVAL: [
                "business_case_assumptions",
                "business_case_approval",
            ],
            GatePhase.DESIGN_APPROVAL: [
                "design_spec_review",
                "wireframe_artifact",
                "figma_artifact",
            ],
            GatePhase.ADR_DECISIONS: ["adr_decision"],
            GatePhase.DECISION_GATE: ["decision_gate"],
        }

        gate_types = phase_gate_mapping.get(phase, [])
        return [g for g in self.gates.values() if g.gate_type in gate_types]

    def get_status_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all gate statuses.

        Returns:
            Dict with status counts and details
        """
        summary = {
            "total": len(self.gates),
            "by_state": {},
            "blocking": [],
            "deferred": [],
            "gates": {},
        }

        for state in GateState:
            count = sum(1 for g in self.gates.values() if g.state == state)
            if count > 0:
                summary["by_state"][state.value] = count

        for gate in self.get_blocking_gates():
            summary["blocking"].append(
                {
                    "gate_type": gate.gate_type,
                    "name": gate.name,
                    "missing_inputs": gate.missing_inputs,
                }
            )

        for gate in self.get_deferred_gates():
            summary["deferred"].append(
                {
                    "gate_type": gate.gate_type,
                    "name": gate.name,
                    "defer_until": (
                        gate.defer_until.isoformat() if gate.defer_until else None
                    ),
                    "reason": gate.defer_reason,
                }
            )

        for gate_type, gate in self.gates.items():
            summary["gates"][gate_type] = {
                "state": gate.state.value,
                "is_blocking": gate.is_blocking,
                "is_complete": gate.is_complete,
                "valid_actions": [a.value for a in gate.get_valid_actions()],
            }

        return summary

    # ========== Persistence Methods ==========

    def save_to_feature_state(self, feature_state: Any) -> None:
        """
        Save all gates to a FeatureState object.

        Args:
            feature_state: FeatureState object to update
        """
        for gate in self.gates.values():
            gate.save_to_feature_state(feature_state)

    def load_from_feature_state(self, feature_state: Any) -> None:
        """
        Load all gates from a FeatureState object.

        Args:
            feature_state: FeatureState object to load from
        """
        # Try to load all known gate types
        for gate_type in InputGate.GATE_DEFINITIONS.keys():
            gate = InputGate.load_from_feature_state(feature_state, gate_type)
            if gate:
                self.gates[gate_type] = gate

    def to_dict(self) -> Dict[str, Any]:
        """Convert manager state to dictionary."""
        return {
            "feature_slug": self.feature_slug,
            "gates": {
                gate_type: gate.to_dict() for gate_type, gate in self.gates.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GateManager":
        """Create manager from dictionary."""
        manager = cls(feature_slug=data["feature_slug"])
        for gate_type, gate_data in data.get("gates", {}).items():
            manager.gates[gate_type] = InputGate.from_dict(gate_data)
        return manager

    def save_to_yaml(self, path: Path) -> None:
        """
        Save gate manager state to a YAML file.

        Args:
            path: Path to save to
        """
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)
        self._feature_state_path = path

    @classmethod
    def load_from_yaml(cls, path: Path) -> Optional["GateManager"]:
        """
        Load gate manager from a YAML file.

        Args:
            path: Path to load from

        Returns:
            GateManager or None if file doesn't exist
        """
        if not path.exists():
            return None

        with open(path, "r") as f:
            data = yaml.safe_load(f)

        manager = cls.from_dict(data)
        manager._feature_state_path = path
        return manager
