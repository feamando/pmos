"""
Engineering Track

Manages the engineering workflow for features including:
- Status tracking (not_started, in_progress, estimation_pending, complete)
- ADR (Architecture Decision Records) generation
- Technical decision capture with rationale
- Engineering estimates (S, M, L, XL)
- Technical risks and dependencies tracking

Engineering Workflow:
    1. start() - Initialize engineering track
    2. create_adr() - Create Architecture Decision Record
    3. record_technical_decision() - Capture technical decisions
    4. record_estimate() - Record effort estimate
    5. complete() - Mark track as complete

ADR Format (following standard ADR template):
    - Title: Short descriptive title
    - Status: proposed | accepted | deprecated | superseded
    - Context: What is the issue motivating this decision?
    - Decision: What is the change being proposed?
    - Consequences: What becomes easier/harder as a result?

PRD References:
    - Section A.1: Engineering track gates
    - Section C.4: Engineering track in feature-state.yaml
    - Section D.3: Engineering Phase outputs (ADRs, estimates)

Usage:
    from tools.context_engine.tracks import EngineeringTrack

    track = EngineeringTrack(feature_path)
    track.start(initiated_by="nikita")
    track.create_adr(
        title="Use Redis for Session Storage",
        context="Need to share sessions across multiple app instances",
        decision="Use Redis as centralized session store",
        consequences="Adds infrastructure dependency but enables horizontal scaling"
    )
    track.record_estimate(estimate="M", breakdown={"frontend": "S", "backend": "M", "testing": "S"})
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class EngineeringStatus(Enum):
    """
    Engineering track status values.

    Lifecycle:
        NOT_STARTED -> IN_PROGRESS -> ESTIMATION_PENDING -> COMPLETE
                              |
                              +-> BLOCKED (if dependencies not met)
    """

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    ESTIMATION_PENDING = "estimation_pending"
    COMPLETE = "complete"
    BLOCKED = "blocked"


class ADRStatus(Enum):
    """
    Status values for Architecture Decision Records.

    Lifecycle:
        PROPOSED -> ACCEPTED
            |          |
            +--------> DEPRECATED (either state can be deprecated)
            |          |
            +--------> SUPERSEDED (by a newer ADR)
    """

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


class EstimateSize(Enum):
    """
    T-shirt size estimates for engineering effort.

    Typical effort mapping:
        S  = 1-2 days
        M  = 3-5 days (1 week)
        L  = 1-2 weeks
        XL = 2-4 weeks
    """

    S = "S"
    M = "M"
    L = "L"
    XL = "XL"

    @classmethod
    def from_string(cls, value: str) -> "EstimateSize":
        """Create from string, handling case insensitivity."""
        normalized = value.upper().strip()
        try:
            return cls(normalized)
        except ValueError:
            raise ValueError(
                f"Invalid estimate size: {value}. Valid values: S, M, L, XL"
            )


@dataclass
class TechnicalDecision:
    """
    Records a technical decision with rationale.

    Attributes:
        decision: What was decided
        rationale: Why this decision was made
        decided_by: Who made the decision
        date: When the decision was made
        category: Category (architecture, implementation, tooling, etc.)
        related_adr: Optional reference to related ADR
        metadata: Additional context
    """

    decision: str
    rationale: str
    decided_by: str
    date: datetime
    category: str = "general"
    related_adr: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result = {
            "decision": self.decision,
            "rationale": self.rationale,
            "decided_by": self.decided_by,
            "date": (
                self.date.isoformat() if isinstance(self.date, datetime) else self.date
            ),
            "category": self.category,
        }
        if self.related_adr:
            result["related_adr"] = self.related_adr
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TechnicalDecision":
        """Create from dictionary."""
        date = data.get("date")
        if isinstance(date, str):
            date = datetime.fromisoformat(date)
        elif not isinstance(date, datetime):
            date = datetime.now()

        return cls(
            decision=data["decision"],
            rationale=data.get("rationale", ""),
            decided_by=data.get("decided_by", "unknown"),
            date=date,
            category=data.get("category", "general"),
            related_adr=data.get("related_adr"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TechnicalRisk:
    """
    Records a technical risk.

    Attributes:
        risk: Description of the risk
        impact: Impact if risk materializes (high, medium, low)
        likelihood: Likelihood of occurrence (high, medium, low)
        mitigation: How to mitigate the risk
        owner: Who is responsible for monitoring/mitigating
        status: Current status (identified, mitigating, resolved)
    """

    risk: str
    impact: str = "medium"
    likelihood: str = "medium"
    mitigation: Optional[str] = None
    owner: Optional[str] = None
    status: str = "identified"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result = {
            "risk": self.risk,
            "impact": self.impact,
            "likelihood": self.likelihood,
            "status": self.status,
        }
        if self.mitigation:
            result["mitigation"] = self.mitigation
        if self.owner:
            result["owner"] = self.owner
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TechnicalRisk":
        """Create from dictionary."""
        return cls(
            risk=data["risk"],
            impact=data.get("impact", "medium"),
            likelihood=data.get("likelihood", "medium"),
            mitigation=data.get("mitigation"),
            owner=data.get("owner"),
            status=data.get("status", "identified"),
        )


@dataclass
class Dependency:
    """
    Records a technical dependency.

    Attributes:
        name: Name of the dependency
        type: Type (internal_team, external_api, infrastructure, etc.)
        description: What the dependency is
        status: Current status (pending, ready, blocked)
        eta: Expected availability date
        owner: Who owns the dependency
    """

    name: str
    type: str = "internal"
    description: str = ""
    status: str = "pending"
    eta: Optional[str] = None
    owner: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "status": self.status,
        }
        if self.eta:
            result["eta"] = self.eta
        if self.owner:
            result["owner"] = self.owner
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Dependency":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            type=data.get("type", "internal"),
            description=data.get("description", ""),
            status=data.get("status", "pending"),
            eta=data.get("eta"),
            owner=data.get("owner"),
        )


@dataclass
class EngineeringEstimate:
    """
    Engineering effort estimate.

    Attributes:
        overall: Overall T-shirt size (S, M, L, XL)
        breakdown: Component breakdown (e.g., {"frontend": "S", "backend": "M"})
        confidence: Confidence level (low, medium, high)
        assumptions: List of assumptions the estimate is based on
        estimated_by: Who provided the estimate
        date: When the estimate was provided
    """

    overall: str
    breakdown: Dict[str, str] = field(default_factory=dict)
    confidence: str = "medium"
    assumptions: List[str] = field(default_factory=list)
    estimated_by: Optional[str] = None
    date: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result = {
            "overall": self.overall,
            "breakdown": self.breakdown,
            "confidence": self.confidence,
            "assumptions": self.assumptions,
        }
        if self.estimated_by:
            result["estimated_by"] = self.estimated_by
        if self.date:
            result["date"] = (
                self.date.isoformat() if isinstance(self.date, datetime) else self.date
            )
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EngineeringEstimate":
        """Create from dictionary."""
        date = data.get("date")
        if isinstance(date, str):
            date = datetime.fromisoformat(date)
        elif not isinstance(date, datetime):
            date = None

        return cls(
            overall=data.get("overall", "M"),
            breakdown=data.get("breakdown", {}),
            confidence=data.get("confidence", "medium"),
            assumptions=data.get("assumptions", []),
            estimated_by=data.get("estimated_by"),
            date=date,
        )


@dataclass
class ADR:
    """
    Architecture Decision Record.

    Standard ADR format:
        - Number/ID
        - Title
        - Status (proposed, accepted, deprecated, superseded)
        - Context (what is the issue?)
        - Decision (what is the change?)
        - Consequences (what becomes easier/harder?)

    Attributes:
        number: Sequential ADR number
        title: Short descriptive title
        status: Current status
        context: Issue motivating this decision
        decision: The change being proposed/made
        consequences: What becomes easier/harder
        created: When ADR was created
        created_by: Who created the ADR
        superseded_by: ADR number that supersedes this one
        supersedes: ADR number this one supersedes
    """

    number: int
    title: str
    status: ADRStatus
    context: str
    decision: str
    consequences: str
    created: datetime
    created_by: str
    superseded_by: Optional[int] = None
    supersedes: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result = {
            "number": self.number,
            "title": self.title,
            "status": self.status.value,
            "context": self.context,
            "decision": self.decision,
            "consequences": self.consequences,
            "created": (
                self.created.isoformat()
                if isinstance(self.created, datetime)
                else self.created
            ),
            "created_by": self.created_by,
        }
        if self.superseded_by:
            result["superseded_by"] = self.superseded_by
        if self.supersedes:
            result["supersedes"] = self.supersedes
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ADR":
        """Create from dictionary."""
        created = data.get("created")
        if isinstance(created, str):
            created = datetime.fromisoformat(created)
        elif not isinstance(created, datetime):
            created = datetime.now()

        status_str = data.get("status", "proposed")
        try:
            status = ADRStatus(status_str)
        except ValueError:
            status = ADRStatus.PROPOSED

        return cls(
            number=data.get("number", 1),
            title=data["title"],
            status=status,
            context=data.get("context", ""),
            decision=data.get("decision", ""),
            consequences=data.get("consequences", ""),
            created=created,
            created_by=data.get("created_by", "unknown"),
            superseded_by=data.get("superseded_by"),
            supersedes=data.get("supersedes"),
        )

    def to_markdown(self) -> str:
        """Generate markdown content for ADR file."""
        now = self.created.strftime("%Y-%m-%d")
        supersedes_text = (
            f"\n**Supersedes**: ADR-{self.supersedes:03d}" if self.supersedes else ""
        )
        superseded_by_text = (
            f"\n**Superseded By**: ADR-{self.superseded_by:03d}"
            if self.superseded_by
            else ""
        )

        return f"""# ADR-{self.number:03d}: {self.title}

**Status**: {self.status.value}
**Date**: {now}
**Author**: {self.created_by}{supersedes_text}{superseded_by_text}

## Context

{self.context}

## Decision

{self.decision}

## Consequences

{self.consequences}

---
*Generated by Context Creation Engine*
"""


@dataclass
class EngineeringTrackResult:
    """Result of an engineering track operation."""

    success: bool
    status: EngineeringStatus
    message: str
    adr_number: Optional[int] = None
    file_path: Optional[Path] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class EngineeringTrack:
    """
    Manages the engineering track for a feature.

    The engineering track is one of four parallel tracks that run
    during feature development. It handles:

    1. **ADR Management**: Create and manage Architecture Decision Records
    2. **Technical Decisions**: Track technical decisions with rationale
    3. **Estimation**: Record effort estimates with breakdowns
    4. **Risks & Dependencies**: Track technical risks and dependencies

    Integrates with:
    - feature-state.yaml: Stores track state in engine.tracks.engineering
    - Engineering folder: ADRs stored in {feature}/engineering/adrs/
    - Context file: Updates action log on state changes

    Example:
        track = EngineeringTrack(feature_path)

        # Start the track
        result = track.start(initiated_by="nikita")

        # Create an ADR
        track.create_adr(
            title="Use Redis for Session Storage",
            context="Need to share sessions across multiple app instances",
            decision="Use Redis as centralized session store",
            consequences="Adds infrastructure dependency but enables horizontal scaling"
        )

        # Record technical decision
        track.record_technical_decision(
            decision="Use TypeScript for frontend",
            rationale="Team expertise and type safety",
            decided_by="nikita",
            category="tooling"
        )

        # Record estimate
        track.record_estimate(
            estimate="M",
            breakdown={"frontend": "S", "backend": "M", "testing": "S"},
            assumptions=["Design finalized", "API spec available"]
        )
    """

    def __init__(self, feature_path: Path):
        """
        Initialize engineering track.

        Args:
            feature_path: Path to the feature folder
        """
        self.feature_path = Path(feature_path)
        self.engineering_folder = self.feature_path / "engineering"
        self.adrs_folder = self.engineering_folder / "adrs"

        # Track state
        self._status = EngineeringStatus.NOT_STARTED
        self._adrs: List[ADR] = []
        self._decisions: List[TechnicalDecision] = []
        self._risks: List[TechnicalRisk] = []
        self._dependencies: List[Dependency] = []
        self._estimate: Optional[EngineeringEstimate] = None
        self._started_at: Optional[datetime] = None
        self._completed_at: Optional[datetime] = None
        self._started_by: Optional[str] = None
        self._next_adr_number: int = 1

        # Load existing state if available
        self._load_from_feature_state()

    @property
    def status(self) -> EngineeringStatus:
        """Current track status."""
        return self._status

    @property
    def adrs(self) -> List[ADR]:
        """List of Architecture Decision Records."""
        return self._adrs

    @property
    def decisions(self) -> List[TechnicalDecision]:
        """List of technical decisions."""
        return self._decisions

    @property
    def risks(self) -> List[TechnicalRisk]:
        """List of technical risks."""
        return self._risks

    @property
    def dependencies(self) -> List[Dependency]:
        """List of dependencies."""
        return self._dependencies

    @property
    def estimate(self) -> Optional[EngineeringEstimate]:
        """Current engineering estimate."""
        return self._estimate

    @property
    def has_estimate(self) -> bool:
        """Check if an estimate has been recorded."""
        return self._estimate is not None

    @property
    def active_adrs(self) -> List[ADR]:
        """Get ADRs that are not deprecated or superseded."""
        return [
            adr
            for adr in self._adrs
            if adr.status in (ADRStatus.PROPOSED, ADRStatus.ACCEPTED)
        ]

    @property
    def pending_risks(self) -> List[TechnicalRisk]:
        """Get risks that haven't been resolved."""
        return [r for r in self._risks if r.status != "resolved"]

    @property
    def blocking_dependencies(self) -> List[Dependency]:
        """Get dependencies that are blocking."""
        return [d for d in self._dependencies if d.status in ("pending", "blocked")]

    # ========== Lifecycle Methods ==========

    def start(self, initiated_by: str) -> EngineeringTrackResult:
        """
        Start the engineering track.

        This initializes the engineering track, creates the engineering folder
        structure if needed, and sets status to IN_PROGRESS.

        Args:
            initiated_by: Username of who started the track

        Returns:
            EngineeringTrackResult with operation outcome
        """
        if self._status != EngineeringStatus.NOT_STARTED:
            return EngineeringTrackResult(
                success=False,
                status=self._status,
                message=f"Track already started (status: {self._status.value})",
            )

        # Create engineering folder structure if needed
        self.engineering_folder.mkdir(parents=True, exist_ok=True)
        self.adrs_folder.mkdir(parents=True, exist_ok=True)

        # Update state
        self._status = EngineeringStatus.IN_PROGRESS
        self._started_at = datetime.now()
        self._started_by = initiated_by

        # Save state
        self._save_to_feature_state()

        return EngineeringTrackResult(
            success=True,
            status=EngineeringStatus.IN_PROGRESS,
            message="Engineering track started",
            metadata={
                "started_by": initiated_by,
                "started_at": self._started_at.isoformat(),
            },
        )

    def complete(self) -> EngineeringTrackResult:
        """
        Mark the engineering track as complete.

        Requires:
        - At least one ADR or technical decision recorded
        - An estimate recorded

        Returns:
            EngineeringTrackResult with operation outcome
        """
        if self._status == EngineeringStatus.NOT_STARTED:
            return EngineeringTrackResult(
                success=False,
                status=self._status,
                message="Track not started. Call start() first.",
            )

        if self._status == EngineeringStatus.COMPLETE:
            return EngineeringTrackResult(
                success=False, status=self._status, message="Track already complete"
            )

        # Check requirements
        if not self._adrs and not self._decisions:
            return EngineeringTrackResult(
                success=False,
                status=self._status,
                message="Cannot complete: No ADRs or technical decisions recorded",
            )

        if not self._estimate:
            return EngineeringTrackResult(
                success=False,
                status=self._status,
                message="Cannot complete: No estimate recorded",
            )

        # Mark complete
        self._status = EngineeringStatus.COMPLETE
        self._completed_at = datetime.now()
        self._save_to_feature_state()

        return EngineeringTrackResult(
            success=True,
            status=EngineeringStatus.COMPLETE,
            message="Engineering track completed",
            metadata={
                "completed_at": self._completed_at.isoformat(),
                "adrs_count": len(self._adrs),
                "decisions_count": len(self._decisions),
                "estimate": self._estimate.overall if self._estimate else None,
            },
        )

    # ========== ADR Methods ==========

    def create_adr(
        self,
        title: str,
        context: str,
        decision: str,
        consequences: str,
        status: ADRStatus = ADRStatus.PROPOSED,
        created_by: Optional[str] = None,
        supersedes: Optional[int] = None,
    ) -> EngineeringTrackResult:
        """
        Create a new Architecture Decision Record.

        Args:
            title: Short descriptive title
            context: What is the issue motivating this decision?
            decision: What is the change being proposed/made?
            consequences: What becomes easier/harder as a result?
            status: Initial status (default: proposed)
            created_by: Who is creating the ADR (uses started_by if not provided)
            supersedes: ADR number this new one supersedes

        Returns:
            EngineeringTrackResult with ADR details
        """
        if self._status == EngineeringStatus.NOT_STARTED:
            return EngineeringTrackResult(
                success=False,
                status=self._status,
                message="Track not started. Call start() first.",
            )

        if self._status == EngineeringStatus.COMPLETE:
            return EngineeringTrackResult(
                success=False,
                status=self._status,
                message="Cannot create ADR: track is complete",
            )

        # Use track initiator if no author specified
        author = created_by or self._started_by or "unknown"

        # Create ADR
        adr = ADR(
            number=self._next_adr_number,
            title=title,
            status=status,
            context=context,
            decision=decision,
            consequences=consequences,
            created=datetime.now(),
            created_by=author,
            supersedes=supersedes,
        )

        # If this supersedes another ADR, update that one
        if supersedes:
            for existing_adr in self._adrs:
                if existing_adr.number == supersedes:
                    existing_adr.status = ADRStatus.SUPERSEDED
                    existing_adr.superseded_by = self._next_adr_number
                    # Update the superseded ADR file
                    self._write_adr_file(existing_adr)
                    break

        # Add to list
        self._adrs.append(adr)
        self._next_adr_number += 1

        # Write ADR file
        file_path = self._write_adr_file(adr)

        # Save state
        self._save_to_feature_state()

        return EngineeringTrackResult(
            success=True,
            status=self._status,
            message=f"ADR-{adr.number:03d} created: {title}",
            adr_number=adr.number,
            file_path=file_path,
            metadata={"title": title, "status": status.value, "created_by": author},
        )

    def update_adr_status(
        self, adr_number: int, new_status: ADRStatus
    ) -> EngineeringTrackResult:
        """
        Update the status of an existing ADR.

        Args:
            adr_number: ADR number to update
            new_status: New status

        Returns:
            EngineeringTrackResult with operation outcome
        """
        # Find the ADR
        adr = None
        for a in self._adrs:
            if a.number == adr_number:
                adr = a
                break

        if not adr:
            return EngineeringTrackResult(
                success=False,
                status=self._status,
                message=f"ADR-{adr_number:03d} not found",
            )

        # Update status
        old_status = adr.status
        adr.status = new_status

        # Update file
        file_path = self._write_adr_file(adr)

        # Save state
        self._save_to_feature_state()

        return EngineeringTrackResult(
            success=True,
            status=self._status,
            message=f"ADR-{adr_number:03d} status updated: {old_status.value} -> {new_status.value}",
            adr_number=adr_number,
            file_path=file_path,
        )

    def get_adr(self, adr_number: int) -> Optional[ADR]:
        """
        Get an ADR by number.

        Args:
            adr_number: ADR number

        Returns:
            ADR or None if not found
        """
        for adr in self._adrs:
            if adr.number == adr_number:
                return adr
        return None

    def _write_adr_file(self, adr: ADR) -> Path:
        """
        Write ADR to markdown file.

        Args:
            adr: ADR to write

        Returns:
            Path to written file
        """
        filename = f"adr-{adr.number:03d}-{self._slugify(adr.title)}.md"
        file_path = self.adrs_folder / filename
        file_path.write_text(adr.to_markdown())
        return file_path

    def _slugify(self, text: str) -> str:
        """Convert text to slug format."""
        import re

        # Convert to lowercase
        slug = text.lower()
        # Replace spaces and special chars with hyphens
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        # Remove leading/trailing hyphens
        slug = slug.strip("-")
        # Limit length
        return slug[:50]

    # ========== Technical Decision Methods ==========

    def record_technical_decision(
        self,
        decision: str,
        rationale: str,
        decided_by: str,
        category: str = "general",
        related_adr: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EngineeringTrackResult:
        """
        Record a technical decision.

        Args:
            decision: What was decided
            rationale: Why this decision was made
            decided_by: Who made the decision
            category: Category (architecture, implementation, tooling, testing, etc.)
            related_adr: Optional ADR number this decision relates to
            metadata: Additional context

        Returns:
            EngineeringTrackResult with operation outcome
        """
        if self._status == EngineeringStatus.NOT_STARTED:
            return EngineeringTrackResult(
                success=False,
                status=self._status,
                message="Track not started. Call start() first.",
            )

        # Create decision record
        tech_decision = TechnicalDecision(
            decision=decision,
            rationale=rationale,
            decided_by=decided_by,
            date=datetime.now(),
            category=category,
            related_adr=f"ADR-{related_adr:03d}" if related_adr else None,
            metadata=metadata or {},
        )

        # Add to list
        self._decisions.append(tech_decision)

        # Save state
        self._save_to_feature_state()

        return EngineeringTrackResult(
            success=True,
            status=self._status,
            message=f"Technical decision recorded: {decision[:50]}...",
            metadata={
                "category": category,
                "decided_by": decided_by,
                "related_adr": related_adr,
            },
        )

    # ========== Estimate Methods ==========

    def record_estimate(
        self,
        estimate: str,
        breakdown: Optional[Dict[str, str]] = None,
        confidence: str = "medium",
        assumptions: Optional[List[str]] = None,
        estimated_by: Optional[str] = None,
    ) -> EngineeringTrackResult:
        """
        Record an engineering effort estimate.

        Args:
            estimate: Overall T-shirt size (S, M, L, XL)
            breakdown: Component breakdown (e.g., {"frontend": "S", "backend": "M"})
            confidence: Confidence level (low, medium, high)
            assumptions: List of assumptions the estimate is based on
            estimated_by: Who provided the estimate

        Returns:
            EngineeringTrackResult with operation outcome
        """
        if self._status == EngineeringStatus.NOT_STARTED:
            return EngineeringTrackResult(
                success=False,
                status=self._status,
                message="Track not started. Call start() first.",
            )

        # Validate estimate size
        try:
            EstimateSize.from_string(estimate)
        except ValueError as e:
            return EngineeringTrackResult(
                success=False, status=self._status, message=str(e)
            )

        # Validate breakdown sizes if provided
        if breakdown:
            for component, size in breakdown.items():
                try:
                    EstimateSize.from_string(size)
                except ValueError:
                    return EngineeringTrackResult(
                        success=False,
                        status=self._status,
                        message=f"Invalid estimate size '{size}' for component '{component}'",
                    )

        # Create estimate
        self._estimate = EngineeringEstimate(
            overall=estimate.upper(),
            breakdown={k: v.upper() for k, v in (breakdown or {}).items()},
            confidence=confidence,
            assumptions=assumptions or [],
            estimated_by=estimated_by or self._started_by,
            date=datetime.now(),
        )

        # Update status if was estimation pending
        if self._status == EngineeringStatus.ESTIMATION_PENDING:
            self._status = EngineeringStatus.IN_PROGRESS

        # Save state
        self._save_to_feature_state()

        return EngineeringTrackResult(
            success=True,
            status=self._status,
            message=f"Estimate recorded: {estimate.upper()}",
            metadata={
                "overall": estimate.upper(),
                "breakdown": breakdown,
                "confidence": confidence,
            },
        )

    def request_estimate(self) -> EngineeringTrackResult:
        """
        Mark that an estimate is pending/requested.

        Returns:
            EngineeringTrackResult with operation outcome
        """
        if self._status == EngineeringStatus.NOT_STARTED:
            return EngineeringTrackResult(
                success=False,
                status=self._status,
                message="Track not started. Call start() first.",
            )

        self._status = EngineeringStatus.ESTIMATION_PENDING
        self._save_to_feature_state()

        return EngineeringTrackResult(
            success=True,
            status=EngineeringStatus.ESTIMATION_PENDING,
            message="Estimation requested",
        )

    # ========== Risk Methods ==========

    def add_risk(
        self,
        risk: str,
        impact: str = "medium",
        likelihood: str = "medium",
        mitigation: Optional[str] = None,
        owner: Optional[str] = None,
    ) -> EngineeringTrackResult:
        """
        Add a technical risk.

        Args:
            risk: Description of the risk
            impact: Impact level (high, medium, low)
            likelihood: Likelihood of occurrence (high, medium, low)
            mitigation: How to mitigate
            owner: Who owns this risk

        Returns:
            EngineeringTrackResult with operation outcome
        """
        if self._status == EngineeringStatus.NOT_STARTED:
            return EngineeringTrackResult(
                success=False,
                status=self._status,
                message="Track not started. Call start() first.",
            )

        tech_risk = TechnicalRisk(
            risk=risk,
            impact=impact,
            likelihood=likelihood,
            mitigation=mitigation,
            owner=owner,
        )

        self._risks.append(tech_risk)
        self._save_to_feature_state()

        return EngineeringTrackResult(
            success=True,
            status=self._status,
            message=f"Risk added: {risk[:50]}...",
            metadata={"impact": impact, "likelihood": likelihood},
        )

    def resolve_risk(
        self, risk_index: int, resolution: str = "resolved"
    ) -> EngineeringTrackResult:
        """
        Mark a risk as resolved or mitigated.

        Args:
            risk_index: Index of the risk in the risks list
            resolution: Resolution status (resolved, mitigating, accepted)

        Returns:
            EngineeringTrackResult with operation outcome
        """
        if risk_index < 0 or risk_index >= len(self._risks):
            return EngineeringTrackResult(
                success=False,
                status=self._status,
                message=f"Invalid risk index: {risk_index}",
            )

        self._risks[risk_index].status = resolution
        self._save_to_feature_state()

        return EngineeringTrackResult(
            success=True,
            status=self._status,
            message=f"Risk status updated to: {resolution}",
        )

    # ========== Dependency Methods ==========

    def add_dependency(
        self,
        name: str,
        type: str = "internal",
        description: str = "",
        eta: Optional[str] = None,
        owner: Optional[str] = None,
    ) -> EngineeringTrackResult:
        """
        Add a technical dependency.

        Args:
            name: Name of the dependency
            type: Type (internal_team, external_api, infrastructure, library)
            description: What the dependency is
            eta: Expected availability date
            owner: Who owns the dependency

        Returns:
            EngineeringTrackResult with operation outcome
        """
        if self._status == EngineeringStatus.NOT_STARTED:
            return EngineeringTrackResult(
                success=False,
                status=self._status,
                message="Track not started. Call start() first.",
            )

        dep = Dependency(
            name=name, type=type, description=description, eta=eta, owner=owner
        )

        self._dependencies.append(dep)
        self._save_to_feature_state()

        return EngineeringTrackResult(
            success=True,
            status=self._status,
            message=f"Dependency added: {name}",
            metadata={"type": type, "status": "pending"},
        )

    def update_dependency_status(
        self, dependency_name: str, status: str
    ) -> EngineeringTrackResult:
        """
        Update the status of a dependency.

        Args:
            dependency_name: Name of the dependency
            status: New status (pending, ready, blocked)

        Returns:
            EngineeringTrackResult with operation outcome
        """
        for dep in self._dependencies:
            if dep.name == dependency_name:
                dep.status = status
                self._save_to_feature_state()
                return EngineeringTrackResult(
                    success=True,
                    status=self._status,
                    message=f"Dependency '{dependency_name}' status updated to: {status}",
                )

        return EngineeringTrackResult(
            success=False,
            status=self._status,
            message=f"Dependency not found: {dependency_name}",
        )

    # ========== State Persistence ==========

    def _load_from_feature_state(self) -> None:
        """Load track state from feature-state.yaml."""
        state_file = self.feature_path / "feature-state.yaml"
        if not state_file.exists():
            return

        try:
            with open(state_file, "r") as f:
                data = yaml.safe_load(f)
        except Exception:
            return

        if not data:
            return

        # Get track data from engine.tracks.engineering
        engine = data.get("engine", {})
        tracks = engine.get("tracks", {})
        eng_data = tracks.get("engineering", {})

        if not eng_data:
            return

        # Restore status
        status_str = eng_data.get("status", "not_started")
        try:
            self._status = EngineeringStatus(status_str)
        except ValueError:
            # Map from TrackStatus to EngineeringStatus
            status_mapping = {
                "not_started": EngineeringStatus.NOT_STARTED,
                "in_progress": EngineeringStatus.IN_PROGRESS,
                "pending_input": EngineeringStatus.ESTIMATION_PENDING,
                "complete": EngineeringStatus.COMPLETE,
                "blocked": EngineeringStatus.BLOCKED,
            }
            self._status = status_mapping.get(status_str, EngineeringStatus.NOT_STARTED)

        # Restore ADRs
        adrs_data = eng_data.get("adrs", [])
        self._adrs = [ADR.from_dict(a) for a in adrs_data]
        if self._adrs:
            self._next_adr_number = max(a.number for a in self._adrs) + 1

        # Restore decisions
        decisions_data = eng_data.get("decisions", [])
        self._decisions = [TechnicalDecision.from_dict(d) for d in decisions_data]

        # Restore risks
        risks_data = eng_data.get("risks", [])
        self._risks = [TechnicalRisk.from_dict(r) for r in risks_data]

        # Restore dependencies
        deps_data = eng_data.get("dependencies", [])
        self._dependencies = [Dependency.from_dict(d) for d in deps_data]

        # Restore estimate
        estimate_data = eng_data.get("estimate")
        if estimate_data:
            self._estimate = EngineeringEstimate.from_dict(estimate_data)

        # Restore timestamps
        started_at = eng_data.get("started_at")
        if started_at:
            self._started_at = (
                datetime.fromisoformat(started_at)
                if isinstance(started_at, str)
                else started_at
            )

        completed_at = eng_data.get("completed_at")
        if completed_at:
            self._completed_at = (
                datetime.fromisoformat(completed_at)
                if isinstance(completed_at, str)
                else completed_at
            )

        self._started_by = eng_data.get("started_by")

    def _save_to_feature_state(self) -> None:
        """Save track state to feature-state.yaml."""
        state_file = self.feature_path / "feature-state.yaml"

        # Load existing state
        data = {}
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    data = yaml.safe_load(f) or {}
            except Exception:
                pass

        # Ensure engine.tracks structure exists
        if "engine" not in data:
            data["engine"] = {}
        if "tracks" not in data["engine"]:
            data["engine"]["tracks"] = {}

        # Update engineering track
        data["engine"]["tracks"]["engineering"] = {
            "status": self._status.value,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "completed_at": (
                self._completed_at.isoformat() if self._completed_at else None
            ),
            "started_by": self._started_by,
            "adrs": [a.to_dict() for a in self._adrs],
            "decisions": [d.to_dict() for d in self._decisions],
            "risks": [r.to_dict() for r in self._risks],
            "dependencies": [d.to_dict() for d in self._dependencies],
            "estimate": self._estimate.to_dict() if self._estimate else None,
        }

        # Write back
        try:
            with open(state_file, "w") as f:
                yaml.dump(
                    data,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )
        except Exception:
            pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert track state to dictionary."""
        return {
            "status": self._status.value,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "completed_at": (
                self._completed_at.isoformat() if self._completed_at else None
            ),
            "started_by": self._started_by,
            "adrs": [a.to_dict() for a in self._adrs],
            "adrs_count": len(self._adrs),
            "active_adrs_count": len(self.active_adrs),
            "decisions": [d.to_dict() for d in self._decisions],
            "decisions_count": len(self._decisions),
            "risks": [r.to_dict() for r in self._risks],
            "pending_risks_count": len(self.pending_risks),
            "dependencies": [d.to_dict() for d in self._dependencies],
            "blocking_dependencies_count": len(self.blocking_dependencies),
            "estimate": self._estimate.to_dict() if self._estimate else None,
            "has_estimate": self.has_estimate,
        }

    @classmethod
    def from_feature_path(cls, feature_path: Path) -> "EngineeringTrack":
        """
        Create an EngineeringTrack instance from a feature path.

        Args:
            feature_path: Path to the feature folder

        Returns:
            EngineeringTrack instance with state loaded from feature-state.yaml
        """
        return cls(feature_path)


def get_engineering_status_for_feature_state(eng_status: EngineeringStatus) -> str:
    """
    Map EngineeringStatus to TrackStatus string for feature-state.yaml compatibility.

    Args:
        eng_status: EngineeringStatus enum value

    Returns:
        TrackStatus string value
    """
    mapping = {
        EngineeringStatus.NOT_STARTED: "not_started",
        EngineeringStatus.IN_PROGRESS: "in_progress",
        EngineeringStatus.ESTIMATION_PENDING: "pending_input",
        EngineeringStatus.COMPLETE: "complete",
        EngineeringStatus.BLOCKED: "blocked",
    }
    return mapping.get(eng_status, "not_started")
