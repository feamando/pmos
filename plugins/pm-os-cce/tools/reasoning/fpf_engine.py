"""
PM-OS CCE FPFEngine (v5.0)

Consolidated First Principles Framework (FPF) cycle engine. Manages
the full Q0-Q5 lifecycle: init, add-evidence, hypothesize, verify,
validate, and decide. Tracks evidence with confidence levels (CL1-CL4),
provides an audit trail, and integrates with the Brain plugin when
available (guarded behind HAS_BRAIN).

Consolidates and replaces:
- v4 quint_brain_sync.py (brain sync is part of FPF cycle)
- v4 gemini_quint_bridge.py FPF session management
- FPF state scattered across quint/ modules

Usage:
    from pm_os_cce.tools.reasoning.fpf_engine import FPFEngine
"""

import json
import logging
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from core.config_loader import get_config

# Optional: Brain plugin for syncing reasoning artifacts
try:
    from pm_os_brain.tools.brain_core.brain_updater import BrainUpdater
    HAS_BRAIN = True
except ImportError:
    HAS_BRAIN = False

# Optional: Evidence decay monitor for decay hooks
try:
    from pm_os_cce.tools.reasoning.evidence_decay_monitor import EvidenceDecayMonitor
except ImportError:
    try:
        from reasoning.evidence_decay_monitor import EvidenceDecayMonitor
    except ImportError:
        EvidenceDecayMonitor = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and dataclasses
# ============================================================================


class FPFPhase(Enum):
    """FPF reasoning phases Q0-Q5."""

    Q0_INIT = "Q0-INIT"
    Q1_HYPOTHESIZE = "Q1-HYPOTHESIZE"
    Q2_VERIFY = "Q2-VERIFY"
    Q3_VALIDATE = "Q3-VALIDATE"
    Q4_AUDIT = "Q4-AUDIT"
    Q5_DECIDE = "Q5-DECIDE"
    COMPLETE = "COMPLETE"


class AssuranceLevel(Enum):
    """Hypothesis assurance levels."""

    L0_CONJECTURE = "L0"
    L1_SUBSTANTIATED = "L1"
    L2_VERIFIED = "L2"
    INVALID = "Invalid"


class CongruenceLevel(Enum):
    """Evidence congruence levels (CL)."""

    CL1_GENERAL = "CL1"       # General principle only
    CL2_SIMILAR = "CL2"       # Similar domain, needs adaptation
    CL3_EXACT = "CL3"         # Exact match to our context
    CL4_REPRODUCED = "CL4"    # Independently reproduced


@dataclass
class Evidence:
    """A piece of evidence supporting or refuting a hypothesis.

    Attributes:
        id: Unique evidence identifier.
        description: What this evidence shows.
        source: Where the evidence came from.
        congruence_level: How well it matches our context (CL1-CL4).
        confidence: Confidence score 0.0-1.0.
        valid_until: Expiry date for this evidence.
        hypothesis_ids: Which hypotheses this evidence supports/refutes.
        supports: Whether evidence supports (True) or refutes (False).
        metadata: Additional data.
    """

    id: str
    description: str
    source: str = ""
    congruence_level: str = "CL1"
    confidence: float = 0.0
    valid_until: Optional[str] = None
    hypothesis_ids: List[str] = field(default_factory=list)
    supports: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Hypothesis:
    """A falsifiable claim within an FPF cycle.

    Attributes:
        id: Unique hypothesis identifier (e.g., H1, H2).
        claim: The falsifiable claim text.
        assurance_level: Current assurance level (L0/L1/L2/Invalid).
        confidence: Aggregated confidence score 0.0-1.0.
        evidence_ids: Evidence items linked to this hypothesis.
        status: active, promoted, rejected, or invalidated.
        reasoning: Explanation for current assurance level.
    """

    id: str
    claim: str
    assurance_level: str = "L0"
    confidence: float = 0.0
    evidence_ids: List[str] = field(default_factory=list)
    status: str = "active"
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BiasCheck:
    """Record of a cognitive bias check during Q4 audit.

    Attributes:
        bias_type: Name of the bias checked.
        risk: Risk level (low, medium, high).
        mitigation: What mitigation was applied.
        mitigated: Whether the bias was successfully mitigated.
    """

    bias_type: str
    risk: str = "low"
    mitigation: str = ""
    mitigated: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditEntry:
    """Immutable audit trail entry for an FPF cycle."""

    timestamp: str
    phase: str
    action: str
    detail: str = ""
    actor: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FPFState:
    """Complete state of an FPF reasoning cycle.

    Serializable to JSON for persistence and Brain sync.
    """

    session_id: str
    question: str = ""
    phase: str = FPFPhase.Q0_INIT.value
    hypotheses: List[Hypothesis] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    bias_checks: List[BiasCheck] = field(default_factory=list)
    audit_trail: List[AuditEntry] = field(default_factory=list)
    drr_path: Optional[str] = None
    created: str = ""
    last_updated: str = ""
    source_model: str = ""
    wlnk_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "question": self.question,
            "phase": self.phase,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "evidence": [e.to_dict() for e in self.evidence],
            "bias_checks": [b.to_dict() for b in self.bias_checks],
            "audit_trail": [a.to_dict() for a in self.audit_trail],
            "drr_path": self.drr_path,
            "created": self.created,
            "last_updated": self.last_updated,
            "source_model": self.source_model,
            "wlnk_score": self.wlnk_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FPFState":
        """Reconstruct FPFState from a serialized dictionary."""
        state = cls(session_id=data.get("session_id", ""))
        state.question = data.get("question", "")
        state.phase = data.get("phase", FPFPhase.Q0_INIT.value)
        state.hypotheses = [
            Hypothesis(**h) for h in data.get("hypotheses", [])
        ]
        state.evidence = [Evidence(**e) for e in data.get("evidence", [])]
        state.bias_checks = [
            BiasCheck(**b) for b in data.get("bias_checks", [])
        ]
        state.audit_trail = [
            AuditEntry(**a) for a in data.get("audit_trail", [])
        ]
        state.drr_path = data.get("drr_path")
        state.created = data.get("created", "")
        state.last_updated = data.get("last_updated", "")
        state.source_model = data.get("source_model", "")
        state.wlnk_score = data.get("wlnk_score")
        return state


# ============================================================================
# FPF Engine
# ============================================================================


class FPFEngine:
    """Consolidated First Principles Framework cycle engine.

    Manages the Q0-Q5 lifecycle, evidence tracking, WLNK calculation,
    bias auditing, DRR generation, and optional Brain synchronization.
    """

    # Default cognitive biases to check during Q4
    DEFAULT_BIAS_CHECKS = [
        "Confirmation Bias",
        "Anchoring",
        "Availability Heuristic",
        "Sunk Cost Fallacy",
        "Authority Bias",
    ]

    def __init__(self, storage_dir: Optional[Path] = None):
        """Initialize FPF engine.

        Args:
            storage_dir: Directory for persisting FPF state. Defaults
                        to ``<user>/brain/Reasoning/Active``.
        """
        if storage_dir:
            self._storage_dir = Path(storage_dir)
        else:
            try:
                paths = get_paths()
                self._storage_dir = (
                    paths.user / "brain" / "Reasoning" / "Active"
                )
            except Exception:
                self._storage_dir = Path.cwd() / "fpf_sessions"

        self._storage_dir.mkdir(parents=True, exist_ok=True)

        # Resolve Brain and Reasoning directories
        try:
            paths = get_paths()
            self._user_dir = paths.user
        except Exception:
            self._user_dir = Path.cwd() / "user"

        self._brain_dir = self._user_dir / "brain"
        self._reasoning_dir = self._brain_dir / "Reasoning"

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _state_path(self, session_id: str) -> Path:
        return self._storage_dir / f"fpf-{session_id}.json"

    def save_state(self, state: FPFState) -> Path:
        """Persist FPF state to disk.

        Args:
            state: The FPFState to save.

        Returns:
            Path to the saved state file.
        """
        state.last_updated = datetime.now().isoformat()
        path = self._state_path(state.session_id)
        path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
        return path

    def load_state(self, session_id: str) -> Optional[FPFState]:
        """Load FPF state from disk.

        Args:
            session_id: The session identifier.

        Returns:
            FPFState or None if not found.
        """
        path = self._state_path(session_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return FPFState.from_dict(data)

    def list_sessions(
        self, phase: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all active FPF sessions.

        Args:
            phase: Optional phase filter.

        Returns:
            List of session summaries.
        """
        sessions: List[Dict[str, Any]] = []
        for path in self._storage_dir.glob("fpf-*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if phase and data.get("phase") != phase:
                    continue
                sessions.append({
                    "session_id": data.get("session_id"),
                    "question": data.get("question", ""),
                    "phase": data.get("phase"),
                    "hypotheses_count": len(data.get("hypotheses", [])),
                    "evidence_count": len(data.get("evidence", [])),
                    "last_updated": data.get("last_updated"),
                })
            except Exception:
                continue

        sessions.sort(key=lambda s: s.get("last_updated", ""), reverse=True)
        return sessions

    # ------------------------------------------------------------------
    # Q0 — Init
    # ------------------------------------------------------------------

    def init(
        self,
        question: str,
        source_model: str = "",
        session_id: Optional[str] = None,
    ) -> FPFState:
        """Initialize a new FPF reasoning session (Q0).

        Args:
            question: The question to reason about.
            source_model: Which model initiated the session.
            session_id: Optional custom session ID.

        Returns:
            Initialized FPFState.
        """
        if not session_id:
            session_id = datetime.now().strftime("%Y%m%d-%H%M%S")

        state = FPFState(
            session_id=session_id,
            question=question,
            phase=FPFPhase.Q0_INIT.value,
            created=datetime.now().isoformat(),
            source_model=source_model,
        )
        state.audit_trail.append(AuditEntry(
            timestamp=datetime.now().isoformat(),
            phase=FPFPhase.Q0_INIT.value,
            action="session_initialized",
            detail=f"Question: {question}",
            actor=source_model,
        ))

        self.save_state(state)
        logger.info("FPF session %s initialized", session_id)
        return state

    # ------------------------------------------------------------------
    # Q1 — Hypothesize
    # ------------------------------------------------------------------

    def add_hypothesis(
        self,
        session_id: str,
        claim: str,
        hypothesis_id: Optional[str] = None,
        confidence: float = 0.0,
    ) -> FPFState:
        """Add a hypothesis to the session (part of Q1).

        Args:
            session_id: Active session identifier.
            claim: The falsifiable claim.
            hypothesis_id: Optional custom ID (auto-generated if omitted).
            confidence: Initial confidence score.

        Returns:
            Updated FPFState.

        Raises:
            ValueError: If session not found.
        """
        state = self.load_state(session_id)
        if not state:
            raise ValueError(f"Session not found: {session_id}")

        if not hypothesis_id:
            hypothesis_id = f"H{len(state.hypotheses) + 1}"

        hypothesis = Hypothesis(
            id=hypothesis_id,
            claim=claim,
            assurance_level=AssuranceLevel.L0_CONJECTURE.value,
            confidence=confidence,
        )
        state.hypotheses.append(hypothesis)
        state.phase = FPFPhase.Q1_HYPOTHESIZE.value

        state.audit_trail.append(AuditEntry(
            timestamp=datetime.now().isoformat(),
            phase=FPFPhase.Q1_HYPOTHESIZE.value,
            action="hypothesis_added",
            detail=f"{hypothesis_id}: {claim}",
        ))

        self.save_state(state)
        return state

    def hypothesize(
        self,
        session_id: str,
        claims: List[str],
    ) -> FPFState:
        """Bulk-add hypotheses and advance to Q1 phase.

        Args:
            session_id: Active session identifier.
            claims: List of falsifiable claim strings.

        Returns:
            Updated FPFState.
        """
        state = self.load_state(session_id)
        if not state:
            raise ValueError(f"Session not found: {session_id}")

        for i, claim in enumerate(claims, start=len(state.hypotheses) + 1):
            h = Hypothesis(
                id=f"H{i}",
                claim=claim,
                assurance_level=AssuranceLevel.L0_CONJECTURE.value,
            )
            state.hypotheses.append(h)

        state.phase = FPFPhase.Q1_HYPOTHESIZE.value
        state.audit_trail.append(AuditEntry(
            timestamp=datetime.now().isoformat(),
            phase=FPFPhase.Q1_HYPOTHESIZE.value,
            action="hypotheses_bulk_added",
            detail=f"{len(claims)} hypotheses added",
        ))

        self.save_state(state)
        return state

    # ------------------------------------------------------------------
    # Evidence management (used by Q1/Q3)
    # ------------------------------------------------------------------

    def add_evidence(
        self,
        session_id: str,
        description: str,
        source: str = "",
        congruence_level: str = "CL1",
        confidence: float = 0.5,
        valid_until: Optional[str] = None,
        hypothesis_ids: Optional[List[str]] = None,
        supports: bool = True,
        evidence_id: Optional[str] = None,
    ) -> FPFState:
        """Add evidence to the session.

        Args:
            session_id: Active session identifier.
            description: What this evidence shows.
            source: Where the evidence came from.
            congruence_level: CL1-CL4 congruence rating.
            confidence: Confidence score 0.0-1.0.
            valid_until: Expiry date in YYYY-MM-DD format.
            hypothesis_ids: Which hypotheses this evidence relates to.
            supports: True if supporting, False if refuting.
            evidence_id: Optional custom ID.

        Returns:
            Updated FPFState.
        """
        state = self.load_state(session_id)
        if not state:
            raise ValueError(f"Session not found: {session_id}")

        if not evidence_id:
            evidence_id = f"E{len(state.evidence) + 1}"

        # Default expiry: 90 days from now
        if not valid_until:
            valid_until = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

        evidence = Evidence(
            id=evidence_id,
            description=description,
            source=source,
            congruence_level=congruence_level,
            confidence=confidence,
            valid_until=valid_until,
            hypothesis_ids=hypothesis_ids or [],
            supports=supports,
        )
        state.evidence.append(evidence)

        state.audit_trail.append(AuditEntry(
            timestamp=datetime.now().isoformat(),
            phase=state.phase,
            action="evidence_added",
            detail=f"{evidence_id}: {description[:60]} ({congruence_level}, {confidence})",
        ))

        self.save_state(state)
        return state

    # ------------------------------------------------------------------
    # Q2 — Verify (deductive consistency check)
    # ------------------------------------------------------------------

    def verify(
        self,
        session_id: str,
        results: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> FPFState:
        """Verify hypotheses for logical consistency (Q2).

        Promotes valid L0 hypotheses to L1 (Substantiated).
        Marks inconsistent hypotheses as Invalid.

        Args:
            session_id: Active session identifier.
            results: Optional dict mapping hypothesis ID to verification
                    result: ``{"valid": bool, "reasoning": str}``.

        Returns:
            Updated FPFState.
        """
        state = self.load_state(session_id)
        if not state:
            raise ValueError(f"Session not found: {session_id}")

        state.phase = FPFPhase.Q2_VERIFY.value

        if results:
            for h in state.hypotheses:
                if h.id in results:
                    r = results[h.id]
                    if r.get("valid", False):
                        h.assurance_level = AssuranceLevel.L1_SUBSTANTIATED.value
                        h.status = "promoted"
                        h.reasoning = r.get("reasoning", "Passed deductive check")
                    else:
                        h.assurance_level = AssuranceLevel.INVALID.value
                        h.status = "invalidated"
                        h.reasoning = r.get("reasoning", "Failed deductive check")

        state.audit_trail.append(AuditEntry(
            timestamp=datetime.now().isoformat(),
            phase=FPFPhase.Q2_VERIFY.value,
            action="verification_completed",
            detail=f"Verified {len(state.hypotheses)} hypotheses",
        ))

        self.save_state(state)
        return state

    # ------------------------------------------------------------------
    # Q3 — Validate (evidence gathering)
    # ------------------------------------------------------------------

    def validate(
        self,
        session_id: str,
        promotions: Optional[Dict[str, float]] = None,
    ) -> FPFState:
        """Validate hypotheses with evidence (Q3).

        Applies WLNK (Weakest Link) scoring and optionally promotes
        L1 hypotheses to L2 based on corroborating evidence.

        Args:
            session_id: Active session identifier.
            promotions: Optional dict mapping hypothesis ID to new
                       confidence score for L2 promotion.

        Returns:
            Updated FPFState.
        """
        state = self.load_state(session_id)
        if not state:
            raise ValueError(f"Session not found: {session_id}")

        state.phase = FPFPhase.Q3_VALIDATE.value

        # Calculate WLNK score
        if state.evidence:
            scores = [e.confidence for e in state.evidence]
            state.wlnk_score = min(scores) if scores else None

        # Apply promotions
        if promotions:
            for h in state.hypotheses:
                if h.id in promotions:
                    h.confidence = promotions[h.id]
                    if h.assurance_level == AssuranceLevel.L1_SUBSTANTIATED.value:
                        h.assurance_level = AssuranceLevel.L2_VERIFIED.value
                        h.status = "promoted"
                        h.reasoning = f"Promoted to L2 with confidence {h.confidence:.2f}"

        state.audit_trail.append(AuditEntry(
            timestamp=datetime.now().isoformat(),
            phase=FPFPhase.Q3_VALIDATE.value,
            action="validation_completed",
            detail=f"WLNK={state.wlnk_score}, evidence_count={len(state.evidence)}",
        ))

        self.save_state(state)
        return state

    # ------------------------------------------------------------------
    # Q4 — Audit (bias check)
    # ------------------------------------------------------------------

    def audit(
        self,
        session_id: str,
        bias_results: Optional[List[Dict[str, Any]]] = None,
    ) -> FPFState:
        """Audit reasoning for cognitive biases (Q4).

        Args:
            session_id: Active session identifier.
            bias_results: Optional list of bias check results, each with
                         ``bias_type``, ``risk``, ``mitigation``, ``mitigated``.

        Returns:
            Updated FPFState.
        """
        state = self.load_state(session_id)
        if not state:
            raise ValueError(f"Session not found: {session_id}")

        state.phase = FPFPhase.Q4_AUDIT.value

        if bias_results:
            state.bias_checks = [BiasCheck(**b) for b in bias_results]
        else:
            # Initialize default bias check templates
            state.bias_checks = [
                BiasCheck(bias_type=bt, risk="unknown", mitigation="", mitigated=False)
                for bt in self.DEFAULT_BIAS_CHECKS
            ]

        state.audit_trail.append(AuditEntry(
            timestamp=datetime.now().isoformat(),
            phase=FPFPhase.Q4_AUDIT.value,
            action="bias_audit_completed",
            detail=f"Checked {len(state.bias_checks)} biases",
        ))

        self.save_state(state)
        return state

    # ------------------------------------------------------------------
    # Q5 — Decide (DRR generation)
    # ------------------------------------------------------------------

    def decide(
        self,
        session_id: str,
        decision: str = "",
        rationale: str = "",
        selected_hypothesis: Optional[str] = None,
    ) -> FPFState:
        """Create Design Rationale Record and complete the cycle (Q5).

        Args:
            session_id: Active session identifier.
            decision: The decision made.
            rationale: Why this decision was made.
            selected_hypothesis: ID of the selected hypothesis.

        Returns:
            Updated FPFState with DRR path.
        """
        state = self.load_state(session_id)
        if not state:
            raise ValueError(f"Session not found: {session_id}")

        state.phase = FPFPhase.Q5_DECIDE.value

        # Generate DRR
        drr_content = self._generate_drr(state, decision, rationale, selected_hypothesis)
        drr_dir = self._reasoning_dir / "Decisions"
        drr_dir.mkdir(parents=True, exist_ok=True)

        drr_id = f"drr-{datetime.now().strftime('%Y-%m-%d')}-{session_id}"
        drr_path = drr_dir / f"{drr_id}.md"
        drr_path.write_text(drr_content, encoding="utf-8")

        state.drr_path = str(drr_path)
        state.phase = FPFPhase.COMPLETE.value

        state.audit_trail.append(AuditEntry(
            timestamp=datetime.now().isoformat(),
            phase=FPFPhase.Q5_DECIDE.value,
            action="drr_created",
            detail=f"DRR: {drr_path}",
        ))

        self.save_state(state)

        # Clean up active session file (move to completed)
        self._archive_session(state)

        # Sync to Brain if available
        if HAS_BRAIN:
            self._sync_to_brain(state)

        logger.info("FPF cycle %s complete. DRR: %s", session_id, drr_path)
        return state

    # ------------------------------------------------------------------
    # DRR generation
    # ------------------------------------------------------------------

    def _generate_drr(
        self,
        state: FPFState,
        decision: str,
        rationale: str,
        selected_hypothesis: Optional[str],
    ) -> str:
        """Generate a Design Rationale Record from FPF state."""
        # Build hypothesis table
        hyp_rows: List[str] = []
        for h in state.hypotheses:
            status = "Selected" if h.id == selected_hypothesis else h.status
            hyp_rows.append(
                f"| {h.id} | {h.claim[:60]} | {h.assurance_level} | "
                f"{h.confidence:.2f} | {status} |"
            )
        hyp_table = "\n".join(hyp_rows) if hyp_rows else "| (none) | - | - | - | - |"

        # Build evidence table
        ev_rows: List[str] = []
        for e in state.evidence:
            ev_rows.append(
                f"| {e.id} | {e.description[:50]} | {e.congruence_level} | "
                f"{e.confidence:.2f} | {e.valid_until or 'N/A'} |"
            )
        ev_table = "\n".join(ev_rows) if ev_rows else "| (none) | - | - | - | - |"

        # Build bias table
        bias_rows: List[str] = []
        for b in state.bias_checks:
            mitigated_str = "Yes" if b.mitigated else "No"
            bias_rows.append(
                f"| {b.bias_type} | {b.risk} | {b.mitigation or 'N/A'} | {mitigated_str} |"
            )
        bias_table = "\n".join(bias_rows) if bias_rows else "| (none) | - | - | - |"

        wlnk = f"{state.wlnk_score:.2f}" if state.wlnk_score is not None else "N/A"

        return f"""---
id: drr-{datetime.now().strftime('%Y-%m-%d')}-{state.session_id}
session: {state.session_id}
created: {datetime.now().isoformat()}
status: complete
source: {state.source_model or 'fpf-engine'}
---

# Design Rationale Record: {state.question}

## Context

**Question:** {state.question}
**Session:** {state.session_id}
**Model:** {state.source_model or 'N/A'}

## Decision

{decision or '(Decision pending)'}

## Rationale

{rationale or '(Rationale pending)'}

## Hypotheses Evaluated

| ID | Claim | Assurance | Confidence | Status |
|----|-------|-----------|------------|--------|
{hyp_table}

## Evidence Chain

| ID | Description | CL | Confidence | Valid Until |
|----|-------------|----|------------|-------------|
{ev_table}

## WLNK Analysis

R_eff = min(evidence confidence scores) = {wlnk}

## Bias Audit Summary

| Bias | Risk | Mitigation | Mitigated |
|------|------|------------|-----------|
{bias_table}

## Conditions for Revisiting

- Evidence expires or becomes stale
- Key assumptions are invalidated
- Significant context changes occur
- New stakeholder requirements emerge

## Audit Trail

| Timestamp | Phase | Action | Detail |
|-----------|-------|--------|--------|
""" + "\n".join(
            f"| {a.timestamp} | {a.phase} | {a.action} | {a.detail[:50]} |"
            for a in state.audit_trail
        ) + """

---

*Generated by PM-OS FPF Engine (v5.0)*
"""

    # ------------------------------------------------------------------
    # Session archival
    # ------------------------------------------------------------------

    def _archive_session(self, state: FPFState) -> None:
        """Move completed session from Active to Completed archive."""
        try:
            completed_dir = self._reasoning_dir / "Completed"
            completed_dir.mkdir(parents=True, exist_ok=True)

            source = self._state_path(state.session_id)
            if source.exists():
                dest = completed_dir / source.name
                shutil.copy2(source, dest)
                # Keep the active copy as well for easy access
                logger.debug("Archived session %s", state.session_id)
        except Exception as exc:
            logger.warning("Could not archive session %s: %s", state.session_id, exc)

    # ------------------------------------------------------------------
    # Brain sync (guarded behind HAS_BRAIN)
    # ------------------------------------------------------------------

    def _sync_to_brain(self, state: FPFState) -> None:
        """Sync FPF reasoning artifacts to Brain plugin.

        Only called when HAS_BRAIN is True.
        """
        if not HAS_BRAIN:
            return

        try:
            updater = BrainUpdater()

            # Sync DRR as a reasoning entity
            if state.drr_path:
                updater.update_entity(
                    entity_type="decision",
                    entity_id=f"fpf-{state.session_id}",
                    data={
                        "title": f"FPF Decision: {state.question[:60]}",
                        "question": state.question,
                        "phase": state.phase,
                        "wlnk_score": state.wlnk_score,
                        "drr_path": state.drr_path,
                        "hypotheses_count": len(state.hypotheses),
                        "evidence_count": len(state.evidence),
                    },
                )

            # Sync L2-verified hypotheses as knowledge claims
            for h in state.hypotheses:
                if h.assurance_level == AssuranceLevel.L2_VERIFIED.value:
                    updater.update_entity(
                        entity_type="knowledge",
                        entity_id=f"fpf-{state.session_id}-{h.id}",
                        data={
                            "title": h.claim[:80],
                            "assurance_level": h.assurance_level,
                            "confidence": h.confidence,
                            "session": state.session_id,
                        },
                    )

            logger.info("Brain sync completed for session %s", state.session_id)
        except Exception as exc:
            logger.warning("Brain sync failed for session %s: %s", state.session_id, exc)

    def sync_brain_to_fpf(self, session_id: str) -> Dict[str, Any]:
        """Import Brain context into an FPF session's bounded context.

        Reads Brain project summaries and recent context to enrich the
        FPF session. This is the reverse direction of ``_sync_to_brain``.

        Args:
            session_id: Active session identifier.

        Returns:
            Dict with import summary.
        """
        results: Dict[str, Any] = {
            "context_updated": False,
            "entities_imported": 0,
            "errors": [],
        }

        state = self.load_state(session_id)
        if not state:
            results["errors"].append(f"Session not found: {session_id}")
            return results

        # Gather Brain project context
        projects_dir = self._brain_dir / "Projects"
        imported_context: List[str] = []

        if projects_dir.exists():
            for project_file in projects_dir.glob("*.md"):
                try:
                    content = project_file.read_text(encoding="utf-8")
                    # Extract title from frontmatter or first header
                    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                    if title_match:
                        imported_context.append(title_match.group(1))
                        results["entities_imported"] += 1
                except Exception:
                    continue

        # Add context as metadata on the session
        if imported_context:
            state.audit_trail.append(AuditEntry(
                timestamp=datetime.now().isoformat(),
                phase=state.phase,
                action="brain_context_imported",
                detail=f"Imported {results['entities_imported']} project references",
            ))
            self.save_state(state)
            results["context_updated"] = True

        return results

    def sync_fpf_to_brain(self, session_id: str) -> Dict[str, Any]:
        """Export FPF artifacts to Brain/Reasoning directories.

        Copies DRRs, L2 hypotheses, and evidence to the Brain plugin's
        Reasoning directory structure.

        Args:
            session_id: Active session identifier.

        Returns:
            Dict with sync summary.
        """
        results: Dict[str, Any] = {
            "decisions_synced": 0,
            "hypotheses_synced": 0,
            "evidence_synced": 0,
            "errors": [],
        }

        state = self.load_state(session_id)
        if not state:
            results["errors"].append(f"Session not found: {session_id}")
            return results

        # Sync DRR
        if state.drr_path:
            drr_source = Path(state.drr_path)
            if drr_source.exists():
                drr_target = self._reasoning_dir / "Decisions"
                drr_target.mkdir(parents=True, exist_ok=True)
                target_file = drr_target / drr_source.name
                if not target_file.exists() or target_file != drr_source:
                    shutil.copy2(drr_source, target_file)
                results["decisions_synced"] += 1

        # Sync L2 hypotheses
        hyp_target = self._reasoning_dir / "Hypotheses"
        hyp_target.mkdir(parents=True, exist_ok=True)
        for h in state.hypotheses:
            if h.assurance_level == AssuranceLevel.L2_VERIFIED.value:
                hyp_file = hyp_target / f"L2-{state.session_id}-{h.id}.md"
                hyp_content = (
                    f"---\n"
                    f"id: {h.id}\n"
                    f"session: {state.session_id}\n"
                    f"assurance: {h.assurance_level}\n"
                    f"confidence: {h.confidence}\n"
                    f"---\n\n"
                    f"# {h.claim}\n\n"
                    f"**Reasoning:** {h.reasoning}\n"
                )
                hyp_file.write_text(hyp_content, encoding="utf-8")
                results["hypotheses_synced"] += 1

        # Sync evidence
        ev_target = self._reasoning_dir / "Evidence"
        ev_target.mkdir(parents=True, exist_ok=True)
        for e in state.evidence:
            ev_file = ev_target / f"{state.session_id}-{e.id}.md"
            ev_content = (
                f"---\n"
                f"id: {e.id}\n"
                f"session: {state.session_id}\n"
                f"congruence_level: {e.congruence_level}\n"
                f"confidence: {e.confidence}\n"
                f"valid_until: {e.valid_until or 'N/A'}\n"
                f"---\n\n"
                f"# {e.description}\n\n"
                f"**Source:** {e.source}\n"
            )
            ev_file.write_text(ev_content, encoding="utf-8")
            results["evidence_synced"] += 1

        state.audit_trail.append(AuditEntry(
            timestamp=datetime.now().isoformat(),
            phase=state.phase,
            action="brain_sync_export",
            detail=(
                f"Synced {results['decisions_synced']}d, "
                f"{results['hypotheses_synced']}h, "
                f"{results['evidence_synced']}e"
            ),
        ))
        self.save_state(state)

        return results

    def bidirectional_sync(self, session_id: str) -> Dict[str, Any]:
        """Run bidirectional sync between FPF session and Brain.

        Args:
            session_id: Active session identifier.

        Returns:
            Combined results from both directions.
        """
        import_results = self.sync_brain_to_fpf(session_id)
        export_results = self.sync_fpf_to_brain(session_id)

        return {
            "import": import_results,
            "export": export_results,
        }

    # ------------------------------------------------------------------
    # Decay monitoring hooks
    # ------------------------------------------------------------------

    def check_evidence_decay(
        self, session_id: str, days: int = 14
    ) -> Dict[str, Any]:
        """Check for expiring evidence in a session.

        Args:
            session_id: Active session identifier.
            days: Warning threshold in days.

        Returns:
            Dict with expiring evidence items.
        """
        state = self.load_state(session_id)
        if not state:
            return {"error": f"Session not found: {session_id}"}

        expiring: List[Dict[str, Any]] = []
        now = datetime.now()

        for e in state.evidence:
            if e.valid_until:
                try:
                    expiry = datetime.strptime(e.valid_until, "%Y-%m-%d")
                    days_left = (expiry - now).days
                    if days_left <= days:
                        status = "EXPIRED" if days_left < 0 else (
                            "CRITICAL" if days_left <= 7 else "WARNING"
                        )
                        expiring.append({
                            "evidence_id": e.id,
                            "description": e.description,
                            "valid_until": e.valid_until,
                            "days_left": days_left,
                            "status": status,
                        })
                except ValueError:
                    continue

        return {
            "session_id": session_id,
            "total_evidence": len(state.evidence),
            "expiring_count": len(expiring),
            "expiring": expiring,
        }

    # ------------------------------------------------------------------
    # Reasoning summary (replaces quint_brain_sync.get_reasoning_summary)
    # ------------------------------------------------------------------

    def get_reasoning_summary(self) -> Dict[str, Any]:
        """Get a summary of all FPF reasoning state.

        Returns:
            Dict with counts of sessions, DRRs, claims by level,
            and expiring evidence.
        """
        summary: Dict[str, Any] = {
            "active_sessions": 0,
            "completed_sessions": 0,
            "total_drrs": 0,
            "l0_claims": 0,
            "l1_claims": 0,
            "l2_claims": 0,
            "expiring_evidence": [],
        }

        for path in self._storage_dir.glob("fpf-*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                phase = data.get("phase", "")
                if phase == FPFPhase.COMPLETE.value:
                    summary["completed_sessions"] += 1
                else:
                    summary["active_sessions"] += 1

                if data.get("drr_path"):
                    summary["total_drrs"] += 1

                for h in data.get("hypotheses", []):
                    level = h.get("assurance_level", "L0")
                    if level == "L0":
                        summary["l0_claims"] += 1
                    elif level == "L1":
                        summary["l1_claims"] += 1
                    elif level == "L2":
                        summary["l2_claims"] += 1

                # Check evidence expiry
                for e in data.get("evidence", []):
                    valid_until = e.get("valid_until")
                    if valid_until:
                        try:
                            expiry = datetime.strptime(valid_until, "%Y-%m-%d")
                            if (expiry - datetime.now()).days <= 14:
                                summary["expiring_evidence"].append({
                                    "session": data.get("session_id"),
                                    "evidence_id": e.get("id"),
                                    "expires": valid_until,
                                })
                        except ValueError:
                            continue
            except Exception:
                continue

        return summary
