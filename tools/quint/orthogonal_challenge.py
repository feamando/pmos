#!/usr/bin/env python3
"""
Orthogonal Challenge System - Multi-model document quality improvement.

Orchestrates three-round challenge process between Claude and Gemini
to produce rigorous, deeply-researched documents.

Rounds:
    1. Originator (Claude): Create v1 with full research + FPF reasoning
    2. Challenger (Gemini): Critique v1, identify gaps, propose alternatives
    3. Resolver (Claude): Address challenges, produce final v3

Usage:
    python3 orthogonal_challenge.py --type prd --topic "Push notifications for WB"
    python3 orthogonal_challenge.py --type adr --topic "Microservices vs Monolith"
    python3 orthogonal_challenge.py --status  # Check ongoing challenges
    python3 orthogonal_challenge.py --resume <challenge_id>
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools directory to path for config_loader and submodule imports
TOOLS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, TOOLS_DIR)
sys.path.insert(0, os.path.join(TOOLS_DIR, "util"))
sys.path.insert(0, os.path.join(TOOLS_DIR, "documents"))
try:
    import config_loader
except ImportError:
    config_loader = None

# Local imports from util/ and documents/
from model_bridge import (
    detect_active_model,
    get_challenger_model,
    invoke_claude,
    invoke_gemini,
    invoke_model,
)
from research_aggregator import format_for_prompt, gather_context
from template_manager import (
    DOC_TYPES,
    get_template,
    inject_challenge_faq,
    inject_fpf_content,
    render_template,
)

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = Path(__file__).parent
ROOT_DIR = config_loader.get_root_path() if config_loader else BASE_DIR.parent.parent
USER_DIR = ROOT_DIR / "user"
BRAIN_DIR = USER_DIR / "brain"
ORTHOGONAL_DIR = BRAIN_DIR / "Reasoning" / "Orthogonal"

# Document types supported
SUPPORTED_TYPES = ["prd", "adr", "rfc", "4cq", "bc", "prfaq"]

# Default model assignments
DEFAULT_ORIGINATOR = "claude"
DEFAULT_CHALLENGER = "gemini"


# ============================================================================
# CHALLENGE STATE MANAGEMENT
# ============================================================================


def get_challenge_dir(challenge_id: str) -> Path:
    """Get the directory for a specific challenge."""
    return ORTHOGONAL_DIR / challenge_id


def create_challenge_id(doc_type: str, topic: str) -> str:
    """Generate unique challenge ID."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    topic_slug = "".join(c if c.isalnum() else "_" for c in topic.lower())[:30]
    return f"{doc_type}-{date_str}-{topic_slug}"


def save_challenge_state(challenge_id: str, state: Dict[str, Any]) -> Path:
    """Save challenge state to disk."""
    challenge_dir = get_challenge_dir(challenge_id)
    challenge_dir.mkdir(parents=True, exist_ok=True)

    state_path = challenge_dir / "state.json"
    state["last_updated"] = datetime.now().isoformat()

    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    return state_path


def load_challenge_state(challenge_id: str) -> Optional[Dict[str, Any]]:
    """Load challenge state from disk."""
    state_path = get_challenge_dir(challenge_id) / "state.json"
    if not state_path.exists():
        return None

    with open(state_path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_challenges(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all challenges, optionally filtered by status."""
    challenges = []

    if not ORTHOGONAL_DIR.exists():
        return challenges

    for challenge_dir in ORTHOGONAL_DIR.iterdir():
        if not challenge_dir.is_dir():
            continue

        state = load_challenge_state(challenge_dir.name)
        if state:
            if status is None or state.get("status") == status:
                challenges.append({"id": challenge_dir.name, **state})

    # Sort by last_updated descending
    challenges.sort(key=lambda x: x.get("last_updated", ""), reverse=True)

    return challenges


# ============================================================================
# ROUND 1: ORIGINATOR
# ============================================================================

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

## Template Structure

{template}

## FPF Reasoning Requirements

1. **Hypotheses**: List 2-3 key hypotheses about the best approach
2. **Evidence**: For each section, note the evidence source and confidence level
3. **Assumptions**: Explicitly state assumptions that need validation
4. **Risks**: Identify potential failure modes

Generate the complete document now."""


def run_round_1(
    challenge_id: str,
    doc_type: str,
    topic: str,
    research_sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run Round 1: Originator creates v1 with full research + FPF reasoning.

    Args:
        challenge_id: Unique challenge identifier
        doc_type: Document type (prd, adr, etc.)
        topic: Document topic
        research_sources: Sources to search for context

    Returns:
        Dict with v1_path, fpf_state, sources_used
    """
    challenge_dir = get_challenge_dir(challenge_id)
    challenge_dir.mkdir(parents=True, exist_ok=True)

    # Gather research context
    print(f"Gathering research context for: {topic}", file=sys.stderr)
    if research_sources is None:
        research_sources = ["brain", "jira", "github", "slack", "gdrive", "confluence"]

    context = gather_context(topic, research_sources)
    research_text = format_for_prompt(context, max_length=15000)

    # Save sources
    sources_path = challenge_dir / "round1_sources.json"
    with open(sources_path, "w", encoding="utf-8") as f:
        json.dump(context, f, indent=2)

    # Get template
    template = get_template(doc_type)
    if not template:
        return {"error": f"Template not found for: {doc_type}"}

    doc_type_full = DOC_TYPES.get(doc_type, doc_type.upper())

    # Build prompts
    system_prompt = ROUND1_SYSTEM_PROMPT.format(doc_type_full=doc_type_full)
    user_prompt = ROUND1_USER_PROMPT.format(
        doc_type_full=doc_type_full,
        topic=topic,
        research_context=research_text,
        template=template[:5000],  # Truncate template if needed
    )

    # Invoke originator (Claude)
    print(f"Invoking originator (Claude) for Round 1...", file=sys.stderr)
    result = invoke_claude(
        f"{system_prompt}\n\n{user_prompt}",
        context={"topic": topic},
        max_tokens=12000,
        temperature=0.3,
    )

    if result.get("error"):
        return {"error": f"Round 1 failed: {result['error']}"}

    v1_content = result.get("response", "")

    # Save v1
    v1_path = challenge_dir / "v1.md"
    with open(v1_path, "w", encoding="utf-8") as f:
        f.write(f"# {doc_type_full}: {topic}\n\n")
        f.write(f"*Round 1 - Originator (Claude)*\n")
        f.write(f"*Generated: {datetime.now().isoformat()}*\n\n")
        f.write("---\n\n")
        f.write(v1_content)

    # Extract FPF state from response (simplified)
    fpf_state = {
        "round": 1,
        "model": "claude",
        "timestamp": datetime.now().isoformat(),
        "topic": topic,
        "doc_type": doc_type,
        "hypotheses": [],  # Would be extracted from response
        "evidence_sources": context.get("summary", {}).get("sources_with_results", []),
        "assumptions": [],  # Would be extracted from response
    }

    fpf_path = challenge_dir / "round1_fpf.json"
    with open(fpf_path, "w", encoding="utf-8") as f:
        json.dump(fpf_state, f, indent=2)

    return {
        "v1_path": str(v1_path),
        "fpf_path": str(fpf_path),
        "sources_path": str(sources_path),
        "tokens": result.get("tokens", {}),
    }


# ============================================================================
# ROUND 2: CHALLENGER
# ============================================================================

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

## Original Research Sources

{sources_summary}

## FPF State from Originator

{fpf_state}

---

Now provide your rigorous critique. Be thorough but constructive."""


def run_round_2(challenge_id: str, additional_research: bool = True) -> Dict[str, Any]:
    """
    Run Round 2: Challenger critiques v1 and proposes improvements.

    Args:
        challenge_id: Unique challenge identifier
        additional_research: Whether to do additional research

    Returns:
        Dict with v2_path, challenges_path, round2_fpf
    """
    challenge_dir = get_challenge_dir(challenge_id)
    state = load_challenge_state(challenge_id)

    if not state:
        return {"error": f"Challenge not found: {challenge_id}"}

    # Load v1
    v1_path = challenge_dir / "v1.md"
    if not v1_path.exists():
        return {"error": "v1.md not found. Run Round 1 first."}

    with open(v1_path, "r", encoding="utf-8") as f:
        v1_content = f.read()

    # Load FPF state
    fpf_path = challenge_dir / "round1_fpf.json"
    fpf_state = {}
    if fpf_path.exists():
        with open(fpf_path, "r", encoding="utf-8") as f:
            fpf_state = json.load(f)

    # Load sources
    sources_path = challenge_dir / "round1_sources.json"
    sources_summary = "No sources recorded"
    if sources_path.exists():
        with open(sources_path, "r", encoding="utf-8") as f:
            sources = json.load(f)
            sources_summary = json.dumps(sources.get("summary", {}), indent=2)

    doc_type_full = DOC_TYPES.get(state.get("doc_type", ""), "Document")

    # Build prompts
    system_prompt = ROUND2_SYSTEM_PROMPT
    user_prompt = ROUND2_USER_PROMPT.format(
        doc_type_full=doc_type_full,
        v1_content=v1_content[:20000],  # Truncate if needed
        sources_summary=sources_summary,
        fpf_state=json.dumps(fpf_state, indent=2),
    )

    # Invoke challenger (Gemini)
    print(f"Invoking challenger (Gemini) for Round 2...", file=sys.stderr)
    result = invoke_gemini(
        f"{system_prompt}\n\n{user_prompt}",
        context={"topic": state.get("topic", "")},
        max_tokens=10000,
        temperature=0.4,
    )

    if result.get("error"):
        return {"error": f"Round 2 failed: {result['error']}"}

    challenges_content = result.get("response", "")

    # Save v2 (annotated version)
    v2_path = challenge_dir / "v2.md"
    with open(v2_path, "w", encoding="utf-8") as f:
        f.write(f"# Challenger Review: {state.get('topic', 'Unknown')}\n\n")
        f.write(f"*Round 2 - Challenger (Gemini)*\n")
        f.write(f"*Generated: {datetime.now().isoformat()}*\n\n")
        f.write("---\n\n")
        f.write(challenges_content)

    # Parse challenges into structured format
    challenges = _parse_challenges(challenges_content)

    challenges_path = challenge_dir / "round2_challenges.json"
    with open(challenges_path, "w", encoding="utf-8") as f:
        json.dump(challenges, f, indent=2)

    # Save round 2 FPF state
    round2_fpf = {
        "round": 2,
        "model": "gemini",
        "timestamp": datetime.now().isoformat(),
        "challenges_count": len(challenges.get("challenges", [])),
        "critical_count": sum(
            1
            for c in challenges.get("challenges", [])
            if c.get("severity") == "critical"
        ),
    }

    round2_fpf_path = challenge_dir / "round2_fpf.json"
    with open(round2_fpf_path, "w", encoding="utf-8") as f:
        json.dump(round2_fpf, f, indent=2)

    return {
        "v2_path": str(v2_path),
        "challenges_path": str(challenges_path),
        "round2_fpf_path": str(round2_fpf_path),
        "challenges_count": len(challenges.get("challenges", [])),
        "tokens": result.get("tokens", {}),
    }


def _parse_challenges(content: str) -> Dict[str, Any]:
    """Parse challenge content into structured format."""
    challenges = {
        "challenges": [],
        "alternatives": [],
        "summary": "",
    }

    # Simple parsing - in production would be more sophisticated
    lines = content.split("\n")
    current_challenge = None

    for line in lines:
        line = line.strip()

        # Look for numbered challenges
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


# ============================================================================
# ROUND 3: RESOLVER
# ============================================================================

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


def run_round_3(challenge_id: str) -> Dict[str, Any]:
    """
    Run Round 3: Resolver addresses challenges and produces final v3.

    Args:
        challenge_id: Unique challenge identifier

    Returns:
        Dict with v3_path, drr_path, challenge_faq_path
    """
    challenge_dir = get_challenge_dir(challenge_id)
    state = load_challenge_state(challenge_id)

    if not state:
        return {"error": f"Challenge not found: {challenge_id}"}

    # Load v1
    v1_path = challenge_dir / "v1.md"
    if not v1_path.exists():
        return {"error": "v1.md not found"}

    with open(v1_path, "r", encoding="utf-8") as f:
        v1_content = f.read()

    # Load v2 (challenges)
    v2_path = challenge_dir / "v2.md"
    challenges_content = ""
    if v2_path.exists():
        with open(v2_path, "r", encoding="utf-8") as f:
            challenges_content = f.read()

    # Load structured challenges
    challenges_path = challenge_dir / "round2_challenges.json"
    challenges_json = "{}"
    if challenges_path.exists():
        with open(challenges_path, "r", encoding="utf-8") as f:
            challenges_json = f.read()

    # Load FPF state
    fpf_path = challenge_dir / "round1_fpf.json"
    fpf_state = {}
    if fpf_path.exists():
        with open(fpf_path, "r", encoding="utf-8") as f:
            fpf_state = json.load(f)

    # Build prompts
    system_prompt = ROUND3_SYSTEM_PROMPT
    user_prompt = ROUND3_USER_PROMPT.format(
        v1_content=v1_content[:15000],
        challenges_content=challenges_content[:8000],
        challenges_json=challenges_json[:3000],
        fpf_state=json.dumps(fpf_state, indent=2),
    )

    # Invoke resolver (Claude)
    print(f"Invoking resolver (Claude) for Round 3...", file=sys.stderr)
    result = invoke_claude(
        f"{system_prompt}\n\n{user_prompt}",
        context={"topic": state.get("topic", "")},
        max_tokens=15000,
        temperature=0.3,
    )

    if result.get("error"):
        return {"error": f"Round 3 failed: {result['error']}"}

    v3_content = result.get("response", "")

    # Save v3 (final)
    v3_path = challenge_dir / "v3_final.md"
    with open(v3_path, "w", encoding="utf-8") as f:
        f.write(
            f"# {DOC_TYPES.get(state.get('doc_type', ''), 'Document')}: {state.get('topic', 'Unknown')}\n\n"
        )
        f.write(f"*Final Version (v3) - Orthogonal Challenge Complete*\n")
        f.write(f"*Generated: {datetime.now().isoformat()}*\n\n")
        f.write("---\n\n")
        f.write(v3_content)

    # Extract and save Challenge FAQ
    challenge_faq = _extract_challenge_faq(v3_content)
    faq_path = challenge_dir / "challenge_faq.md"
    with open(faq_path, "w", encoding="utf-8") as f:
        f.write(f"# Challenge FAQ: {state.get('topic', 'Unknown')}\n\n")
        f.write(f"*Generated from Orthogonal Challenge Process*\n\n")
        f.write("---\n\n")
        f.write(challenge_faq)

    # Create DRR (Decision Rationale Record)
    drr_content = _create_drr(challenge_id, state, v3_content)
    drr_path = challenge_dir / "drr.md"
    with open(drr_path, "w", encoding="utf-8") as f:
        f.write(drr_content)

    # Also copy to Brain/Reasoning/Decisions
    decisions_dir = BRAIN_DIR / "Reasoning" / "Decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    drr_dest = decisions_dir / f"{challenge_id}_drr.md"
    shutil.copy(drr_path, drr_dest)

    return {
        "v3_path": str(v3_path),
        "drr_path": str(drr_path),
        "challenge_faq_path": str(faq_path),
        "drr_brain_path": str(drr_dest),
        "tokens": result.get("tokens", {}),
    }


def _extract_challenge_faq(content: str) -> str:
    """Extract Challenge FAQ section from v3 content."""
    # Look for FAQ section
    faq_markers = ["## Challenge FAQ", "## FAQ", "# Challenge FAQ"]
    for marker in faq_markers:
        if marker in content:
            idx = content.find(marker)
            # Find end of section (next ## or end)
            end_idx = content.find("\n## ", idx + len(marker))
            if end_idx == -1:
                end_idx = content.find("\n# ", idx + len(marker))
            if end_idx == -1:
                end_idx = len(content)

            return content[idx:end_idx].strip()

    return "No Challenge FAQ section found in document."


def _create_drr(challenge_id: str, state: Dict[str, Any], v3_content: str) -> str:
    """Create Decision Rationale Record from challenge process."""
    drr = f"""# Decision Rationale Record

**DRR ID:** {challenge_id}
**Date:** {datetime.now().strftime("%Y-%m-%d")}
**Status:** Complete
**Document Type:** {state.get('doc_type', 'unknown').upper()}
**Topic:** {state.get('topic', 'Unknown')}

---

## 1. Decision Summary

This document was produced through the Orthogonal Challenge System,
involving three rounds of review between Claude (Originator/Resolver)
and Gemini (Challenger).

## 2. Process

| Round | Model | Purpose | Status |
|-------|-------|---------|--------|
| 1 | Claude | Initial draft with FPF reasoning | Complete |
| 2 | Gemini | Rigorous challenge and critique | Complete |
| 3 | Claude | Resolution and final synthesis | Complete |

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
    return drr


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================


def run_orthogonal(
    doc_type: str,
    topic: str,
    originator: Optional[str] = None,
    research_sources: Optional[List[str]] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run full 3-round orthogonal challenge process.

    Args:
        doc_type: Document type (prd, adr, rfc, 4cq, bc, prfaq)
        topic: Document topic
        originator: Model to use as originator (default: claude)
        research_sources: Sources to search for context
        output_dir: Custom output directory

    Returns:
        Dict with challenge_id, v3_path, drr_path, all artifacts
    """
    if doc_type not in SUPPORTED_TYPES:
        return {"error": f"Unsupported document type: {doc_type}"}

    # Create challenge ID
    challenge_id = create_challenge_id(doc_type, topic)
    print(f"Starting orthogonal challenge: {challenge_id}", file=sys.stderr)

    # Initialize state
    state = {
        "challenge_id": challenge_id,
        "doc_type": doc_type,
        "topic": topic,
        "originator": originator or DEFAULT_ORIGINATOR,
        "challenger": get_challenger_model(originator or DEFAULT_ORIGINATOR),
        "status": "round1_in_progress",
        "created_at": datetime.now().isoformat(),
        "rounds": {},
    }
    save_challenge_state(challenge_id, state)

    # Round 1: Originator
    print("\n=== ROUND 1: ORIGINATOR ===", file=sys.stderr)
    r1_result = run_round_1(challenge_id, doc_type, topic, research_sources)

    if r1_result.get("error"):
        state["status"] = "round1_failed"
        state["error"] = r1_result["error"]
        save_challenge_state(challenge_id, state)
        return r1_result

    state["rounds"]["round1"] = r1_result
    state["status"] = "round2_in_progress"
    save_challenge_state(challenge_id, state)

    # Round 2: Challenger
    print("\n=== ROUND 2: CHALLENGER ===", file=sys.stderr)
    r2_result = run_round_2(challenge_id)

    if r2_result.get("error"):
        state["status"] = "round2_failed"
        state["error"] = r2_result["error"]
        save_challenge_state(challenge_id, state)
        return r2_result

    state["rounds"]["round2"] = r2_result
    state["status"] = "round3_in_progress"
    save_challenge_state(challenge_id, state)

    # Round 3: Resolver
    print("\n=== ROUND 3: RESOLVER ===", file=sys.stderr)
    r3_result = run_round_3(challenge_id)

    if r3_result.get("error"):
        state["status"] = "round3_failed"
        state["error"] = r3_result["error"]
        save_challenge_state(challenge_id, state)
        return r3_result

    state["rounds"]["round3"] = r3_result
    state["status"] = "complete"
    state["completed_at"] = datetime.now().isoformat()
    save_challenge_state(challenge_id, state)

    print(f"\n=== ORTHOGONAL CHALLENGE COMPLETE ===", file=sys.stderr)
    print(f"Final document: {r3_result.get('v3_path')}", file=sys.stderr)
    print(f"DRR: {r3_result.get('drr_brain_path')}", file=sys.stderr)

    return {
        "challenge_id": challenge_id,
        "status": "complete",
        "v3_path": r3_result.get("v3_path"),
        "drr_path": r3_result.get("drr_brain_path"),
        "challenge_faq_path": r3_result.get("challenge_faq_path"),
        "all_artifacts": state,
    }


def resume_challenge(challenge_id: str) -> Dict[str, Any]:
    """Resume an incomplete challenge from where it left off."""
    state = load_challenge_state(challenge_id)

    if not state:
        return {"error": f"Challenge not found: {challenge_id}"}

    status = state.get("status", "")

    if status == "complete":
        return {"message": "Challenge already complete", "state": state}

    if status == "round1_in_progress" or status == "round1_failed":
        # Re-run from Round 1
        return run_orthogonal(
            state.get("doc_type"), state.get("topic"), state.get("originator")
        )

    if status == "round2_in_progress" or status == "round2_failed":
        # Continue from Round 2
        r2_result = run_round_2(challenge_id)
        if r2_result.get("error"):
            return r2_result

        state["rounds"]["round2"] = r2_result
        state["status"] = "round3_in_progress"
        save_challenge_state(challenge_id, state)

        r3_result = run_round_3(challenge_id)
        if r3_result.get("error"):
            return r3_result

        state["rounds"]["round3"] = r3_result
        state["status"] = "complete"
        save_challenge_state(challenge_id, state)
        return {"challenge_id": challenge_id, "status": "complete", **r3_result}

    if status == "round3_in_progress" or status == "round3_failed":
        # Continue from Round 3
        r3_result = run_round_3(challenge_id)
        if r3_result.get("error"):
            return r3_result

        state["rounds"]["round3"] = r3_result
        state["status"] = "complete"
        save_challenge_state(challenge_id, state)
        return {"challenge_id": challenge_id, "status": "complete", **r3_result}

    return {"error": f"Unknown status: {status}"}


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Orthogonal Challenge System - Multi-model document quality improvement"
    )
    parser.add_argument("--type", choices=SUPPORTED_TYPES, help="Document type")
    parser.add_argument("--topic", type=str, help="Document topic")
    parser.add_argument("--sources", type=str, help="Comma-separated research sources")
    parser.add_argument(
        "--status", action="store_true", help="List all challenges and their status"
    )
    parser.add_argument(
        "--resume",
        type=str,
        metavar="CHALLENGE_ID",
        help="Resume an incomplete challenge",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.status:
        challenges = list_challenges()
        if args.json:
            print(json.dumps(challenges, indent=2))
        else:
            print("Orthogonal Challenges:\n")
            if not challenges:
                print("  No challenges found.")
            for c in challenges:
                print(f"  [{c['status']}] {c['id']}")
                print(f"    Topic: {c.get('topic', 'Unknown')}")
                print(f"    Type: {c.get('doc_type', 'unknown').upper()}")
                print(f"    Last Updated: {c.get('last_updated', 'Unknown')}")
                print()
        return 0

    if args.resume:
        result = resume_challenge(args.resume)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("error"):
                print(f"Error: {result['error']}", file=sys.stderr)
                return 1
            print(f"Challenge resumed: {args.resume}")
            print(f"Status: {result.get('status')}")
            if result.get("v3_path"):
                print(f"Final document: {result.get('v3_path')}")
        return 0

    if args.type and args.topic:
        sources = None
        if args.sources:
            sources = [s.strip() for s in args.sources.split(",")]

        result = run_orthogonal(args.type, args.topic, research_sources=sources)

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("error"):
                print(f"Error: {result['error']}", file=sys.stderr)
                return 1
            print(f"\nOrthogonal Challenge Complete!")
            print(f"Challenge ID: {result.get('challenge_id')}")
            print(f"Final Document: {result.get('v3_path')}")
            print(f"DRR: {result.get('drr_path')}")
            print(f"Challenge FAQ: {result.get('challenge_faq_path')}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
