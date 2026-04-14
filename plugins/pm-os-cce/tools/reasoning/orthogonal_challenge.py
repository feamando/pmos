"""
PM-OS CCE OrthogonalChallenge (v5.0)

Multi-model document quality improvement via a three-round challenge
process. Orchestrates originator, challenger, and resolver rounds to
produce rigorous, deeply-researched documents.

Rounds:
    1. Originator: Create v1 with full research + FPF reasoning
    2. Challenger: Critique v1, identify gaps, propose alternatives
    3. Resolver: Address challenges, produce final v3

Challenge sources are **config-driven**: the originator and challenger
models are resolved from config (``reasoning.orthogonal.originator``
and ``reasoning.orthogonal.challenger``). Any model supported by the
base model_bridge can serve as either role.

Merges functionality from the former ``gemini_quint_bridge.py`` — Gemini
(or any configured model) is simply one possible challenge source.

Usage:
    from pm_os_cce.tools.reasoning.orthogonal_challenge import OrthogonalChallenge
"""

import json
import logging
import shutil
from datetime import datetime
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

try:
    from pm_os_base.tools.util.model_bridge import (
        detect_active_model,
        get_challenger_model,
        invoke_model,
    )
except ImportError:
    try:
        from util.model_bridge import (
            detect_active_model,
            get_challenger_model,
            invoke_model,
        )
    except ImportError:
        detect_active_model = None
        get_challenger_model = None
        invoke_model = None

# Optional Brain plugin for syncing DRRs
try:
    from pm_os_brain.tools.brain_core.brain_updater import BrainUpdater
    HAS_BRAIN = True
except ImportError:
    HAS_BRAIN = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Supported document types (can be extended via config)
DEFAULT_SUPPORTED_TYPES = ["prd", "adr", "rfc", "4cq", "bc", "prfaq"]

# Default model roles (overridden by config)
_DEFAULT_ORIGINATOR = "claude"
_DEFAULT_CHALLENGER = "gemini"


def _resolve_config() -> Dict[str, Any]:
    """Load orthogonal challenge config with safe defaults."""
    try:
        cfg = get_config()
        section = cfg.get("reasoning.orthogonal", {})
        if isinstance(section, dict):
            return section
    except Exception:
        pass
    return {}


def _get_originator_model() -> str:
    """Resolve originator model from config or default."""
    return _resolve_config().get("originator", _DEFAULT_ORIGINATOR)


def _get_challenger_model_name() -> str:
    """Resolve challenger model from config or default."""
    return _resolve_config().get("challenger", _DEFAULT_CHALLENGER)


def _get_supported_types() -> List[str]:
    """Resolve supported document types from config or default."""
    cfg_types = _resolve_config().get("supported_types")
    if isinstance(cfg_types, list) and cfg_types:
        return cfg_types
    return DEFAULT_SUPPORTED_TYPES


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

ROUND1_SYSTEM_PROMPT = """You are creating the first draft (v1) of a {doc_type_full} document.

Your task:
1. Analyze the provided research context thoroughly
2. Apply First Principles Framework (FPF) reasoning
3. Generate a comprehensive document following the template structure
4. Document your reasoning and evidence chain

Important guidelines:
- Be thorough but concise
- Cite evidence from the research context
- Identify assumptions explicitly
- Note areas of uncertainty
- Consider stakeholder perspectives

Output the complete document in markdown format following the template structure."""

ROUND1_USER_PROMPT = """Create a {doc_type_full} for the following topic:

**Topic:** {topic}

## Research Context

{research_context}

## FPF Reasoning Requirements

1. **Hypotheses**: List 2-3 key hypotheses about the best approach
2. **Evidence**: For each section, note the evidence source and confidence level
3. **Assumptions**: Explicitly state assumptions that need validation
4. **Risks**: Identify potential failure modes

Generate the complete document now."""

ROUND2_SYSTEM_PROMPT = """You are the Challenger in an orthogonal review process.

Your task is to rigorously critique and challenge the document, looking for:
1. **Logical Gaps**: Missing reasoning steps, unsupported conclusions
2. **Evidence Weakness**: Question source quality, recency, relevance
3. **Bias Detection**: Confirmation bias, missing perspectives, cherry-picked data
4. **Alternative Approaches**: Propose different solutions not considered
5. **Missing Stakeholders**: Who wasn't consulted or considered?
6. **Risk Blindspots**: Unaddressed failure modes, edge cases

For each challenge:
- Be specific about what's problematic
- Explain why it matters
- Suggest improvements or alternatives
- Rate severity: Critical / Major / Minor

Output format:
1. Executive Summary of Challenges
2. Detailed Challenges (numbered, with severity)
3. Alternative Proposals (if any)
4. Recommended Changes"""

ROUND2_USER_PROMPT = """Review and challenge this {doc_type_full}:

## Document (v1)

{v1_content}

## FPF State from Originator

{fpf_state}

---

Now provide your rigorous critique. Be thorough but constructive."""

ROUND3_SYSTEM_PROMPT = """You are the Resolver in an orthogonal review process.

Your task is to address each challenge and produce the final document (v3):

For each challenge:
1. **Accept**: Incorporate the suggested change with explanation
2. **Reject**: Provide clear rationale for not accepting
3. **Modify**: Take a hybrid approach

Requirements:
- Address EVERY challenge explicitly
- Produce the complete final document
- Include a Challenge FAQ section at the end
- Note confidence levels for each major section
- Document conditions under which this decision should be revisited

Output format:
1. Challenge Resolutions (numbered, matching challenges)
2. Final Document (v3)
3. Challenge FAQ
4. Confidence Assessment
5. Conditions for Revisiting"""

ROUND3_USER_PROMPT = """Resolve the challenges and produce the final document.

## Original Document (v1)

{v1_content}

## Challenges from Reviewer (Round 2)

{challenges_content}

## Structured Challenges

{challenges_json}

## Original FPF State

{fpf_state}

---

Address each challenge and produce the final v3 document."""


# ---------------------------------------------------------------------------
# Challenge state management
# ---------------------------------------------------------------------------


def _get_orthogonal_dir() -> Path:
    """Resolve the orthogonal challenge storage directory."""
    try:
        paths = get_paths()
        base = paths.user / "brain" / "Reasoning" / "Orthogonal"
    except Exception:
        base = Path.cwd() / "user" / "brain" / "Reasoning" / "Orthogonal"
    return base


def _create_challenge_id(doc_type: str, topic: str) -> str:
    """Generate unique challenge ID."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    topic_slug = "".join(c if c.isalnum() else "_" for c in topic.lower())[:30]
    return f"{doc_type}-{date_str}-{topic_slug}"


# ---------------------------------------------------------------------------
# Challenge parsing helpers
# ---------------------------------------------------------------------------


def _parse_challenges(content: str) -> Dict[str, Any]:
    """Parse challenge content into structured format."""
    challenges: Dict[str, Any] = {
        "challenges": [],
        "alternatives": [],
        "summary": "",
    }

    current_challenge = None
    for line in content.split("\n"):
        line = line.strip()
        if line and line[0].isdigit() and "." in line[:3]:
            if current_challenge:
                challenges["challenges"].append(current_challenge)

            severity = "minor"
            if "critical" in line.lower():
                severity = "critical"
            elif "major" in line.lower():
                severity = "major"

            current_challenge = {
                "text": line,
                "severity": severity,
                "status": "pending",
            }

    if current_challenge:
        challenges["challenges"].append(current_challenge)

    return challenges


def _extract_challenge_faq(content: str) -> str:
    """Extract Challenge FAQ section from v3 content."""
    faq_markers = ["## Challenge FAQ", "## FAQ", "# Challenge FAQ"]
    for marker in faq_markers:
        if marker in content:
            idx = content.find(marker)
            end_idx = content.find("\n## ", idx + len(marker))
            if end_idx == -1:
                end_idx = content.find("\n# ", idx + len(marker))
            if end_idx == -1:
                end_idx = len(content)
            return content[idx:end_idx].strip()
    return "No Challenge FAQ section found in document."


# ---------------------------------------------------------------------------
# OrthogonalChallenge class
# ---------------------------------------------------------------------------


class OrthogonalChallenge:
    """Orchestrates the three-round orthogonal challenge process.

    All model assignments are config-driven. The challenger model
    defaults to Gemini but can be any model supported by model_bridge.
    """

    def __init__(
        self,
        originator: Optional[str] = None,
        challenger: Optional[str] = None,
    ):
        """Initialize the challenge system.

        Args:
            originator: Model for rounds 1 and 3 (default from config).
            challenger: Model for round 2 (default from config).
        """
        self.originator = originator or _get_originator_model()
        self.challenger = challenger or _get_challenger_model_name()
        self._orthogonal_dir = _get_orthogonal_dir()

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _challenge_dir(self, challenge_id: str) -> Path:
        return self._orthogonal_dir / challenge_id

    def _save_state(self, challenge_id: str, state: Dict[str, Any]) -> Path:
        challenge_dir = self._challenge_dir(challenge_id)
        challenge_dir.mkdir(parents=True, exist_ok=True)
        state_path = challenge_dir / "state.json"
        state["last_updated"] = datetime.now().isoformat()
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        return state_path

    def _load_state(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        state_path = self._challenge_dir(challenge_id) / "state.json"
        if not state_path.exists():
            return None
        return json.loads(state_path.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_challenges(
        self, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all challenges, optionally filtered by status."""
        challenges: List[Dict[str, Any]] = []
        if not self._orthogonal_dir.exists():
            return challenges

        for challenge_dir in self._orthogonal_dir.iterdir():
            if not challenge_dir.is_dir():
                continue
            state = self._load_state(challenge_dir.name)
            if state:
                if status is None or state.get("status") == status:
                    challenges.append({"id": challenge_dir.name, **state})

        challenges.sort(key=lambda x: x.get("last_updated", ""), reverse=True)
        return challenges

    # ------------------------------------------------------------------
    # Round 1 — Originator
    # ------------------------------------------------------------------

    def run_round_1(
        self,
        challenge_id: str,
        doc_type: str,
        topic: str,
        research_context: str = "",
    ) -> Dict[str, Any]:
        """Run Round 1: Originator creates v1 with FPF reasoning.

        Args:
            challenge_id: Unique challenge identifier.
            doc_type: Document type (prd, adr, etc.).
            topic: Document topic.
            research_context: Pre-gathered research text.

        Returns:
            Dict with v1_path, fpf_state, etc.
        """
        challenge_dir = self._challenge_dir(challenge_id)
        challenge_dir.mkdir(parents=True, exist_ok=True)

        doc_type_full = doc_type.upper()

        system_prompt = ROUND1_SYSTEM_PROMPT.format(doc_type_full=doc_type_full)
        user_prompt = ROUND1_USER_PROMPT.format(
            doc_type_full=doc_type_full,
            topic=topic,
            research_context=research_context[:15000],
        )

        logger.info("Invoking originator (%s) for Round 1", self.originator)
        result = invoke_model(
            model=self.originator,
            prompt=f"{system_prompt}\n\n{user_prompt}",
            context={"topic": topic},
            max_tokens=12000,
            temperature=0.3,
        )

        if result.get("error"):
            return {"error": f"Round 1 failed: {result['error']}"}

        v1_content = result.get("response", "")

        # Save v1
        v1_path = challenge_dir / "v1.md"
        v1_path.write_text(
            f"# {doc_type_full}: {topic}\n\n"
            f"*Round 1 - Originator ({self.originator})*\n"
            f"*Generated: {datetime.now().isoformat()}*\n\n"
            f"---\n\n{v1_content}",
            encoding="utf-8",
        )

        # FPF state
        fpf_state = {
            "round": 1,
            "model": self.originator,
            "timestamp": datetime.now().isoformat(),
            "topic": topic,
            "doc_type": doc_type,
            "hypotheses": [],
            "assumptions": [],
        }
        fpf_path = challenge_dir / "round1_fpf.json"
        fpf_path.write_text(json.dumps(fpf_state, indent=2), encoding="utf-8")

        return {
            "v1_path": str(v1_path),
            "fpf_path": str(fpf_path),
            "tokens": result.get("tokens", {}),
        }

    # ------------------------------------------------------------------
    # Round 2 — Challenger
    # ------------------------------------------------------------------

    def run_round_2(self, challenge_id: str) -> Dict[str, Any]:
        """Run Round 2: Challenger critiques v1.

        Args:
            challenge_id: Unique challenge identifier.

        Returns:
            Dict with v2_path, challenges_path, counts.
        """
        challenge_dir = self._challenge_dir(challenge_id)
        state = self._load_state(challenge_id)
        if not state:
            return {"error": f"Challenge not found: {challenge_id}"}

        v1_path = challenge_dir / "v1.md"
        if not v1_path.exists():
            return {"error": "v1.md not found. Run Round 1 first."}

        v1_content = v1_path.read_text(encoding="utf-8")

        # Load FPF state
        fpf_path = challenge_dir / "round1_fpf.json"
        fpf_state: Dict[str, Any] = {}
        if fpf_path.exists():
            fpf_state = json.loads(fpf_path.read_text(encoding="utf-8"))

        doc_type_full = state.get("doc_type", "document").upper()

        user_prompt = ROUND2_USER_PROMPT.format(
            doc_type_full=doc_type_full,
            v1_content=v1_content[:20000],
            fpf_state=json.dumps(fpf_state, indent=2),
        )

        logger.info("Invoking challenger (%s) for Round 2", self.challenger)
        result = invoke_model(
            model=self.challenger,
            prompt=f"{ROUND2_SYSTEM_PROMPT}\n\n{user_prompt}",
            context={"topic": state.get("topic", "")},
            max_tokens=10000,
            temperature=0.4,
        )

        if result.get("error"):
            return {"error": f"Round 2 failed: {result['error']}"}

        challenges_content = result.get("response", "")

        # Save v2
        v2_path = challenge_dir / "v2.md"
        v2_path.write_text(
            f"# Challenger Review: {state.get('topic', 'Unknown')}\n\n"
            f"*Round 2 - Challenger ({self.challenger})*\n"
            f"*Generated: {datetime.now().isoformat()}*\n\n"
            f"---\n\n{challenges_content}",
            encoding="utf-8",
        )

        # Parse challenges
        challenges = _parse_challenges(challenges_content)
        challenges_path = challenge_dir / "round2_challenges.json"
        challenges_path.write_text(json.dumps(challenges, indent=2), encoding="utf-8")

        # Round 2 FPF state
        round2_fpf = {
            "round": 2,
            "model": self.challenger,
            "timestamp": datetime.now().isoformat(),
            "challenges_count": len(challenges.get("challenges", [])),
            "critical_count": sum(
                1
                for c in challenges.get("challenges", [])
                if c.get("severity") == "critical"
            ),
        }
        round2_fpf_path = challenge_dir / "round2_fpf.json"
        round2_fpf_path.write_text(
            json.dumps(round2_fpf, indent=2), encoding="utf-8"
        )

        return {
            "v2_path": str(v2_path),
            "challenges_path": str(challenges_path),
            "round2_fpf_path": str(round2_fpf_path),
            "challenges_count": len(challenges.get("challenges", [])),
            "tokens": result.get("tokens", {}),
        }

    # ------------------------------------------------------------------
    # Round 3 — Resolver
    # ------------------------------------------------------------------

    def run_round_3(self, challenge_id: str) -> Dict[str, Any]:
        """Run Round 3: Resolver addresses challenges and produces v3.

        Args:
            challenge_id: Unique challenge identifier.

        Returns:
            Dict with v3_path, drr_path, challenge_faq_path.
        """
        challenge_dir = self._challenge_dir(challenge_id)
        state = self._load_state(challenge_id)
        if not state:
            return {"error": f"Challenge not found: {challenge_id}"}

        v1_path = challenge_dir / "v1.md"
        if not v1_path.exists():
            return {"error": "v1.md not found"}
        v1_content = v1_path.read_text(encoding="utf-8")

        v2_path = challenge_dir / "v2.md"
        challenges_content = ""
        if v2_path.exists():
            challenges_content = v2_path.read_text(encoding="utf-8")

        challenges_path = challenge_dir / "round2_challenges.json"
        challenges_json = "{}"
        if challenges_path.exists():
            challenges_json = challenges_path.read_text(encoding="utf-8")

        fpf_path = challenge_dir / "round1_fpf.json"
        fpf_state: Dict[str, Any] = {}
        if fpf_path.exists():
            fpf_state = json.loads(fpf_path.read_text(encoding="utf-8"))

        user_prompt = ROUND3_USER_PROMPT.format(
            v1_content=v1_content[:15000],
            challenges_content=challenges_content[:8000],
            challenges_json=challenges_json[:3000],
            fpf_state=json.dumps(fpf_state, indent=2),
        )

        logger.info("Invoking resolver (%s) for Round 3", self.originator)
        result = invoke_model(
            model=self.originator,
            prompt=f"{ROUND3_SYSTEM_PROMPT}\n\n{user_prompt}",
            context={"topic": state.get("topic", "")},
            max_tokens=15000,
            temperature=0.3,
        )

        if result.get("error"):
            return {"error": f"Round 3 failed: {result['error']}"}

        v3_content = result.get("response", "")
        doc_type_full = state.get("doc_type", "document").upper()

        # Save v3
        v3_path = challenge_dir / "v3_final.md"
        v3_path.write_text(
            f"# {doc_type_full}: {state.get('topic', 'Unknown')}\n\n"
            f"*Final Version (v3) - Orthogonal Challenge Complete*\n"
            f"*Generated: {datetime.now().isoformat()}*\n\n"
            f"---\n\n{v3_content}",
            encoding="utf-8",
        )

        # Challenge FAQ
        challenge_faq = _extract_challenge_faq(v3_content)
        faq_path = challenge_dir / "challenge_faq.md"
        faq_path.write_text(
            f"# Challenge FAQ: {state.get('topic', 'Unknown')}\n\n"
            f"*Generated from Orthogonal Challenge Process*\n\n"
            f"---\n\n{challenge_faq}",
            encoding="utf-8",
        )

        # DRR (Decision Rationale Record)
        drr_content = self._create_drr(challenge_id, state)
        drr_path = challenge_dir / "drr.md"
        drr_path.write_text(drr_content, encoding="utf-8")

        # Optionally sync DRR to Brain
        drr_brain_path = str(drr_path)
        try:
            paths = get_paths()
            decisions_dir = paths.user / "brain" / "Reasoning" / "Decisions"
            decisions_dir.mkdir(parents=True, exist_ok=True)
            drr_dest = decisions_dir / f"{challenge_id}_drr.md"
            shutil.copy(drr_path, drr_dest)
            drr_brain_path = str(drr_dest)
        except Exception as exc:
            logger.warning("Could not copy DRR to Brain: %s", exc)

        return {
            "v3_path": str(v3_path),
            "drr_path": drr_brain_path,
            "challenge_faq_path": str(faq_path),
            "tokens": result.get("tokens", {}),
        }

    # ------------------------------------------------------------------
    # Full orchestration
    # ------------------------------------------------------------------

    def run(
        self,
        doc_type: str,
        topic: str,
        research_context: str = "",
    ) -> Dict[str, Any]:
        """Run full 3-round orthogonal challenge process.

        Args:
            doc_type: Document type (prd, adr, rfc, etc.).
            topic: Document topic.
            research_context: Pre-gathered research text.

        Returns:
            Dict with challenge_id, v3_path, drr_path, all artifacts.
        """
        supported = _get_supported_types()
        if doc_type not in supported:
            return {"error": f"Unsupported document type: {doc_type}. Supported: {supported}"}

        challenge_id = _create_challenge_id(doc_type, topic)
        logger.info("Starting orthogonal challenge: %s", challenge_id)

        state: Dict[str, Any] = {
            "challenge_id": challenge_id,
            "doc_type": doc_type,
            "topic": topic,
            "originator": self.originator,
            "challenger": self.challenger,
            "status": "round1_in_progress",
            "created_at": datetime.now().isoformat(),
            "rounds": {},
        }
        self._save_state(challenge_id, state)

        # Round 1
        r1 = self.run_round_1(challenge_id, doc_type, topic, research_context)
        if r1.get("error"):
            state["status"] = "round1_failed"
            state["error"] = r1["error"]
            self._save_state(challenge_id, state)
            return r1

        state["rounds"]["round1"] = r1
        state["status"] = "round2_in_progress"
        self._save_state(challenge_id, state)

        # Round 2
        r2 = self.run_round_2(challenge_id)
        if r2.get("error"):
            state["status"] = "round2_failed"
            state["error"] = r2["error"]
            self._save_state(challenge_id, state)
            return r2

        state["rounds"]["round2"] = r2
        state["status"] = "round3_in_progress"
        self._save_state(challenge_id, state)

        # Round 3
        r3 = self.run_round_3(challenge_id)
        if r3.get("error"):
            state["status"] = "round3_failed"
            state["error"] = r3["error"]
            self._save_state(challenge_id, state)
            return r3

        state["rounds"]["round3"] = r3
        state["status"] = "complete"
        state["completed_at"] = datetime.now().isoformat()
        self._save_state(challenge_id, state)

        return {
            "challenge_id": challenge_id,
            "status": "complete",
            "v3_path": r3.get("v3_path"),
            "drr_path": r3.get("drr_path"),
            "challenge_faq_path": r3.get("challenge_faq_path"),
        }

    def resume(self, challenge_id: str) -> Dict[str, Any]:
        """Resume an incomplete challenge from where it left off."""
        state = self._load_state(challenge_id)
        if not state:
            return {"error": f"Challenge not found: {challenge_id}"}

        status = state.get("status", "")
        if status == "complete":
            return {"message": "Challenge already complete", "state": state}

        if status in ("round1_in_progress", "round1_failed"):
            return self.run(
                state.get("doc_type", ""),
                state.get("topic", ""),
            )

        if status in ("round2_in_progress", "round2_failed"):
            r2 = self.run_round_2(challenge_id)
            if r2.get("error"):
                return r2
            state["rounds"]["round2"] = r2
            state["status"] = "round3_in_progress"
            self._save_state(challenge_id, state)

            r3 = self.run_round_3(challenge_id)
            if r3.get("error"):
                return r3
            state["rounds"]["round3"] = r3
            state["status"] = "complete"
            self._save_state(challenge_id, state)
            return {"challenge_id": challenge_id, "status": "complete", **r3}

        if status in ("round3_in_progress", "round3_failed"):
            r3 = self.run_round_3(challenge_id)
            if r3.get("error"):
                return r3
            state["rounds"]["round3"] = r3
            state["status"] = "complete"
            self._save_state(challenge_id, state)
            return {"challenge_id": challenge_id, "status": "complete", **r3}

        return {"error": f"Unknown status: {status}"}

    # ------------------------------------------------------------------
    # DRR generation
    # ------------------------------------------------------------------

    def _create_drr(
        self, challenge_id: str, state: Dict[str, Any]
    ) -> str:
        """Create Decision Rationale Record from challenge process."""
        return f"""# Decision Rationale Record

**DRR ID:** {challenge_id}
**Date:** {datetime.now().strftime("%Y-%m-%d")}
**Status:** Complete
**Document Type:** {state.get('doc_type', 'unknown').upper()}
**Topic:** {state.get('topic', 'Unknown')}

---

## 1. Decision Summary

This document was produced through the Orthogonal Challenge System,
involving three rounds of review between {self.originator} (Originator/Resolver)
and {self.challenger} (Challenger).

## 2. Process

| Round | Model | Purpose | Status |
|-------|-------|---------|--------|
| 1 | {self.originator} | Initial draft with FPF reasoning | Complete |
| 2 | {self.challenger} | Rigorous challenge and critique | Complete |
| 3 | {self.originator} | Resolution and final synthesis | Complete |

## 3. Key Decisions Made

(Extracted from challenge resolution process)

## 4. Evidence Chain

- Round 1 FPF: `{challenge_id}/round1_fpf.json`
- Round 2 Challenges: `{challenge_id}/round2_challenges.json`
- Final Document: `{challenge_id}/v3_final.md`

## 5. Assurance Level

**L2 Verified** - Document has undergone orthogonal challenge process
with explicit challenge/resolution cycle.

## 6. Conditions for Revisiting

- Evidence expires or becomes stale
- Key assumptions are invalidated
- Significant context changes occur
- New stakeholder requirements emerge

---

*Generated by Orthogonal Challenge System*
"""
