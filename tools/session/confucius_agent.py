#!/usr/bin/env python3
"""
Confucius Note-Taker Agent - Lightweight context capture during conversations.

Captures decisions, assumptions, observations, blockers, and actions without
the full FPF cycle overhead. Runs automatically during sessions and feeds
into document generation commands.

Usage:
    python3 confucius_agent.py --start "Session topic"
    python3 confucius_agent.py --status
    python3 confucius_agent.py --export  # For FPF context injection
    python3 confucius_agent.py --capture decision "Title" --choice "X" --rationale "Why"
    python3 confucius_agent.py --save
    python3 confucius_agent.py --list 5  # List recent sessions
"""

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# Use config_loader for proper path resolution
ROOT_PATH = config_loader.get_root_path()
BRAIN_DIR = ROOT_PATH / "user" / "brain"

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFUCIUS_DIR = BRAIN_DIR / "Confucius"
STATE_FILE = CONFUCIUS_DIR / ".confucius_state.json"

# Note categories
NOTE_TYPES = {
    "decision": "D",
    "assumption": "A",
    "observation": "O",
    "blocker": "B",
    "action": "T",  # Task
    "research": "R",  # Research findings
}

# Research categories
RESEARCH_CATEGORIES = [
    "competitive",  # Competitor intelligence
    "technical",  # Architecture, APIs, implementations
    "market",  # User/market insights
    "internal",  # Internal PM-OS/Brain discoveries
    "discovery",  # General web discoveries
]

# Pattern detection for automatic capture
DECISION_PATTERNS = [
    r"(?:let's|we'll|going to|decided to|choosing|will use|opted for)\s+(.+)",
    r"(?:decision|chose|selected|picked):\s*(.+)",
    r"go(?:ing)? with\s+(.+)",
]

ASSUMPTION_PATTERNS = [
    r"assum(?:e|ing)\s+(?:that\s+)?(.+)",
    r"(?:I think|I believe|probably|likely)\s+(.+)",
    r"should be\s+(.+)",
]

BLOCKER_PATTERNS = [
    r"blocked (?:by|on)\s+(.+)",
    r"waiting (?:for|on)\s+(.+)",
    r"can't (?:proceed|continue) (?:until|without)\s+(.+)",
    r"blocker:\s*(.+)",
]

ACTION_PATTERNS = [
    r"(?:need to|should|must|will)\s+(.+)",
    r"todo:\s*(.+)",
    r"action:\s*(.+)",
    r"@(\w+)\s+(?:to|should|will|needs to)\s+(.+)",
]

RESEARCH_PATTERNS = [
    r"(?:I found|discovered|learned that|it turns out)\s+(.+)",
    r"(?:according to|based on)\s+(.+)\s+(?:from|via)\s+(.+)",
    r"(?:the article|documentation|page|site) (?:shows|mentions|states|says)\s+(.+)",
    r"(?:research|finding|insight|takeaway):\s*(.+)",
    r"(?:competitor|[\w]+) (?:has|offers|provides|uses)\s+(.+)",
]


# ============================================================================
# SESSION MANAGEMENT
# ============================================================================


def get_current_session() -> Optional[Dict[str, Any]]:
    """Load current session state."""
    if not STATE_FILE.exists():
        return None

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    if state.get("status") != "active":
        return None

    return state


def is_session_stale(state: Dict[str, Any], max_hours: int = 24) -> bool:
    """Check if a session is stale (older than max_hours)."""
    if not state:
        return False

    created_at = state.get("created_at")
    if not created_at:
        return False

    try:
        created = datetime.fromisoformat(created_at)
        age = datetime.now() - created
        return age.total_seconds() > (max_hours * 3600)
    except (ValueError, TypeError):
        return False


def handle_stale_session() -> Optional[Path]:
    """Check for and handle stale sessions. Returns path if session was closed."""
    state = get_current_session()
    if not state:
        return None

    if is_session_stale(state):
        print(
            f"[Confucius] Closing stale session: {state.get('session_id')} (>24h old)"
        )
        return end_session()

    return None


def ensure_session_active(topic: str = "Daily Work Session") -> Dict[str, Any]:
    """Ensure a Confucius session is active. Handle stale sessions, start new if needed."""
    # First, handle any stale sessions
    handle_stale_session()

    # Check for existing active session
    state = get_current_session()
    if state:
        return state

    # Start new session
    return start_session(topic)


def save_session_state(state: Dict[str, Any]) -> None:
    """Save session state to disk."""
    CONFUCIUS_DIR.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now().isoformat()

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def start_session(topic: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Start a new Confucius note-taking session."""
    if session_id is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        short_id = str(uuid.uuid4())[:8]
        session_id = f"{date_str}-{short_id}"

    state = {
        "session_id": session_id,
        "topic": topic,
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "notes": {
            "decisions": [],
            "assumptions": [],
            "observations": [],
            "blockers": [],
            "actions": [],
            "research": [],
        },
        "counters": {
            "D": 0,
            "A": 0,
            "O": 0,
            "B": 0,
            "T": 0,
            "R": 0,
        },
        "linked_fpf_cycles": [],
        "linked_documents": [],
    }

    save_session_state(state)
    return state


def end_session() -> Optional[Path]:
    """End current session and save to markdown file."""
    state = get_current_session()
    if not state:
        return None

    state["status"] = "closed"
    state["closed_at"] = datetime.now().isoformat()

    # Generate markdown file
    md_path = CONFUCIUS_DIR / f"{state['session_id']}.md"
    md_content = export_to_markdown(state)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # Archive state
    save_session_state(state)

    return md_path


# ============================================================================
# NOTE CAPTURE
# ============================================================================


def capture_decision(
    title: str,
    choice: str,
    rationale: str,
    alternatives: Optional[List[str]] = None,
    confidence: str = "medium",
) -> Dict[str, Any]:
    """Capture a decision."""
    state = get_current_session()
    if not state:
        state = start_session("Auto-started session")

    state["counters"]["D"] += 1
    note_id = f"D{state['counters']['D']}"

    decision = {
        "id": note_id,
        "title": title,
        "choice": choice,
        "rationale": rationale,
        "alternatives": alternatives or [],
        "confidence": confidence,
        "timestamp": datetime.now().isoformat(),
    }

    state["notes"]["decisions"].append(decision)
    save_session_state(state)

    return decision


def capture_assumption(
    text: str, status: str = "pending", source: Optional[str] = None
) -> Dict[str, Any]:
    """Capture an assumption."""
    state = get_current_session()
    if not state:
        state = start_session("Auto-started session")

    state["counters"]["A"] += 1
    note_id = f"A{state['counters']['A']}"

    assumption = {
        "id": note_id,
        "text": text,
        "status": status,  # pending, validated, invalidated, risky
        "source": source,
        "timestamp": datetime.now().isoformat(),
    }

    state["notes"]["assumptions"].append(assumption)
    save_session_state(state)

    return assumption


def capture_observation(
    text: str, source: Optional[str] = None, category: Optional[str] = None
) -> Dict[str, Any]:
    """Capture an observation or fact."""
    state = get_current_session()
    if not state:
        state = start_session("Auto-started session")

    state["counters"]["O"] += 1
    note_id = f"O{state['counters']['O']}"

    observation = {
        "id": note_id,
        "text": text,
        "source": source,
        "category": category,
        "timestamp": datetime.now().isoformat(),
    }

    state["notes"]["observations"].append(observation)
    save_session_state(state)

    return observation


def capture_blocker(
    text: str, impact: Optional[str] = None, owner: Optional[str] = None
) -> Dict[str, Any]:
    """Capture a blocker."""
    state = get_current_session()
    if not state:
        state = start_session("Auto-started session")

    state["counters"]["B"] += 1
    note_id = f"B{state['counters']['B']}"

    blocker = {
        "id": note_id,
        "text": text,
        "impact": impact,
        "owner": owner,
        "status": "open",
        "timestamp": datetime.now().isoformat(),
    }

    state["notes"]["blockers"].append(blocker)
    save_session_state(state)

    return blocker


def capture_action(
    text: str, owner: Optional[str] = None, due: Optional[str] = None
) -> Dict[str, Any]:
    """Capture an action item."""
    state = get_current_session()
    if not state:
        state = start_session("Auto-started session")

    state["counters"]["T"] += 1
    note_id = f"T{state['counters']['T']}"

    action = {
        "id": note_id,
        "text": text,
        "owner": owner,
        "due": due,
        "status": "pending",
        "timestamp": datetime.now().isoformat(),
    }

    state["notes"]["actions"].append(action)
    save_session_state(state)

    return action


def capture_research(
    title: str,
    finding: str,
    source_url: Optional[str] = None,
    source_type: str = "web",
    category: str = "discovery",
    confidence: str = "medium",
    related_entities: Optional[List[str]] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Capture a research finding.

    Args:
        title: Brief title of the finding
        finding: The actual knowledge discovered
        source_url: URL where the finding came from (if web)
        source_type: Type of source (web, internal, conversation)
        category: Research category (competitive, technical, market, internal, discovery)
        confidence: Confidence level (high, medium, low)
        related_entities: List of related Brain entity names
        query: The question/query that led to this research

    Returns:
        The captured research note
    """
    state = get_current_session()
    if not state:
        state = start_session("Auto-started session")

    # Ensure research notes list exists (for older sessions)
    if "research" not in state["notes"]:
        state["notes"]["research"] = []
    if "R" not in state["counters"]:
        state["counters"]["R"] = 0

    state["counters"]["R"] += 1
    note_id = f"R{state['counters']['R']}"

    research = {
        "id": note_id,
        "title": title,
        "finding": finding,
        "source": {
            "type": source_type,
            "url": source_url,
        },
        "category": category,
        "confidence": confidence,
        "related_entities": related_entities or [],
        "query": query,
        "timestamp": datetime.now().isoformat(),
    }

    state["notes"]["research"].append(research)
    save_session_state(state)

    # Also write to brain inbox for enrichment
    _write_research_to_inbox(research, state.get("session_id"))

    return research


def _write_research_to_inbox(research: Dict[str, Any], session_id: str) -> None:
    """Write research finding to brain inbox for later enrichment."""
    inbox_dir = BRAIN_DIR / "Inbox" / "ClaudeSession" / "Raw"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    # Create inbox entry with full context
    inbox_entry = {
        "id": research["id"],
        "session_id": session_id,
        "title": research["title"],
        "finding": research["finding"],
        "source": research["source"],
        "category": research["category"],
        "confidence": research["confidence"],
        "related_entities": research.get("related_entities", []),
        "query": research.get("query"),
        "timestamp": research["timestamp"],
        "inbox_created": datetime.now().isoformat(),
    }

    # Write to dated file (append if exists)
    date_str = datetime.now().strftime("%Y-%m-%d")
    inbox_file = inbox_dir / f"session_{date_str}.json"

    entries = []
    if inbox_file.exists():
        try:
            with open(inbox_file, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except (json.JSONDecodeError, IOError):
            entries = []

    entries.append(inbox_entry)

    with open(inbox_file, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


# ============================================================================
# AUTOMATIC PATTERN DETECTION
# ============================================================================


def detect_and_capture(text: str) -> List[Dict[str, Any]]:
    """
    Automatically detect patterns in text and capture notes.

    Returns list of captured notes.
    """
    captured = []
    text_lower = text.lower()

    # Check for decisions
    for pattern in DECISION_PATTERNS:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        for match in matches:
            if len(match) > 10:  # Avoid capturing noise
                note = capture_decision(
                    title="Auto-detected decision",
                    choice=match.strip(),
                    rationale="Detected from conversation",
                    confidence="low",
                )
                captured.append({"type": "decision", "note": note})

    # Check for assumptions
    for pattern in ASSUMPTION_PATTERNS:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        for match in matches:
            if len(match) > 10:
                note = capture_assumption(
                    text=match.strip(), status="pending", source="auto-detected"
                )
                captured.append({"type": "assumption", "note": note})

    # Check for blockers
    for pattern in BLOCKER_PATTERNS:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        for match in matches:
            if len(match) > 5:
                note = capture_blocker(text=match.strip(), impact="unknown")
                captured.append({"type": "blocker", "note": note})

    # Check for actions
    for pattern in ACTION_PATTERNS:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                # Pattern with owner capture
                owner, action_text = match[0], match[1]
                note = capture_action(text=action_text.strip(), owner=owner)
            else:
                note = capture_action(text=match.strip())
            captured.append({"type": "action", "note": note})

    # Check for research findings
    for pattern in RESEARCH_PATTERNS:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        for match in matches:
            finding_text = match if isinstance(match, str) else match[0]
            if len(finding_text) > 15:  # Avoid noise
                note = capture_research(
                    title="Auto-detected finding",
                    finding=finding_text.strip(),
                    source_type="conversation",
                    confidence="low",
                )
                captured.append({"type": "research", "note": note})

    return captured


# ============================================================================
# EXPORT & FORMAT
# ============================================================================


def export_to_markdown(state: Optional[Dict[str, Any]] = None) -> str:
    """Export current session notes to markdown format."""
    if state is None:
        state = get_current_session()

    if not state:
        return '# No Active Session\n\nStart a session with `confucius_agent.py --start "Topic"`'

    notes = state.get("notes", {})

    md = f"""# Confucius Notes: {state.get('session_id', 'unknown')}

**Date:** {state.get('created_at', 'unknown')[:10]}
**Topic:** {state.get('topic', 'No topic')}
**Status:** {state.get('status', 'unknown')}

---

"""

    # Decisions
    if notes.get("decisions"):
        md += "## Decisions\n\n"
        for d in notes["decisions"]:
            alt_str = (
                f"Alternatives: {', '.join(d.get('alternatives', []))}"
                if d.get("alternatives")
                else ""
            )
            md += f"- [{d['id']}] **{d.get('title', 'Untitled')}** | Chose: {d.get('choice', 'N/A')} | Why: {d.get('rationale', 'N/A')}\n"
            if alt_str:
                md += f"  - {alt_str}\n"
            md += f"  - Confidence: {d.get('confidence', 'medium')}\n\n"

    # Assumptions
    if notes.get("assumptions"):
        md += "## Assumptions\n\n"
        for a in notes["assumptions"]:
            md += f"- [{a['id']}] {a.get('text', 'N/A')} | Status: {a.get('status', 'pending')}\n"
            if a.get("source"):
                md += f"  - Source: {a['source']}\n"
            md += "\n"

    # Observations
    if notes.get("observations"):
        md += "## Observations\n\n"
        for o in notes["observations"]:
            md += f"- [{o['id']}] {o.get('text', 'N/A')}"
            if o.get("source"):
                md += f" | Source: {o['source']}"
            md += "\n"
        md += "\n"

    # Blockers
    if notes.get("blockers"):
        md += "## Blockers\n\n"
        for b in notes["blockers"]:
            md += f"- [{b['id']}] {b.get('text', 'N/A')}"
            if b.get("impact"):
                md += f" | Impact: {b['impact']}"
            if b.get("owner"):
                md += f" | Owner: {b['owner']}"
            md += f" | Status: {b.get('status', 'open')}\n"
        md += "\n"

    # Actions
    if notes.get("actions"):
        md += "## Actions\n\n"
        for t in notes["actions"]:
            status_marker = "x" if t.get("status") == "done" else " "
            md += f"- [{status_marker}] [{t['id']}] {t.get('text', 'N/A')}"
            if t.get("owner"):
                md += f" | Owner: {t['owner']}"
            if t.get("due"):
                md += f" | Due: {t['due']}"
            md += "\n"
        md += "\n"

    # Research
    if notes.get("research"):
        md += "## Research Findings\n\n"
        for r in notes["research"]:
            md += f"- [{r['id']}] **{r.get('title', 'Untitled')}** | {r.get('category', 'discovery')}\n"
            md += f"  - Finding: {r.get('finding', 'N/A')}\n"
            if r.get("source", {}).get("url"):
                md += f"  - Source: {r['source']['url']}\n"
            if r.get("related_entities"):
                md += f"  - Related: {', '.join(r['related_entities'])}\n"
            md += f"  - Confidence: {r.get('confidence', 'medium')}\n\n"

    # Summary
    md += "---\n\n## Summary\n\n"
    md += f"- Decisions: {len(notes.get('decisions', []))}\n"
    md += f"- Assumptions: {len(notes.get('assumptions', []))}\n"
    md += f"- Observations: {len(notes.get('observations', []))}\n"
    md += f"- Blockers: {len(notes.get('blockers', []))}\n"
    md += f"- Actions: {len(notes.get('actions', []))}\n"
    md += f"- Research: {len(notes.get('research', []))}\n"

    if state.get("linked_fpf_cycles"):
        md += f"\n### Linked FPF Cycles\n"
        for cycle in state["linked_fpf_cycles"]:
            md += f"- {cycle}\n"

    if state.get("linked_documents"):
        md += f"\n### Linked Documents\n"
        for doc in state["linked_documents"]:
            md += f"- {doc}\n"

    md += f"\n---\n*Generated: {datetime.now().isoformat()}*\n"

    return md


def export_for_fpf() -> Dict[str, Any]:
    """
    Export current session notes in format suitable for FPF context injection.

    Returns structured data for use in document generation.
    """
    state = get_current_session()
    if not state:
        return {"error": "No active session"}

    notes = state.get("notes", {})

    return {
        "session_id": state.get("session_id"),
        "topic": state.get("topic"),
        "decisions": [
            {
                "id": d["id"],
                "title": d.get("title"),
                "choice": d.get("choice"),
                "rationale": d.get("rationale"),
                "confidence": d.get("confidence", "medium"),
            }
            for d in notes.get("decisions", [])
        ],
        "assumptions": [
            {
                "id": a["id"],
                "text": a.get("text"),
                "status": a.get("status", "pending"),
            }
            for a in notes.get("assumptions", [])
        ],
        "observations": [
            {
                "id": o["id"],
                "text": o.get("text"),
                "source": o.get("source"),
            }
            for o in notes.get("observations", [])
        ],
        "blockers": [
            {
                "id": b["id"],
                "text": b.get("text"),
                "status": b.get("status", "open"),
            }
            for b in notes.get("blockers", [])
            if b.get("status") != "resolved"
        ],
        "open_actions": [
            {
                "id": t["id"],
                "text": t.get("text"),
                "owner": t.get("owner"),
            }
            for t in notes.get("actions", [])
            if t.get("status") != "done"
        ],
        "research": [
            {
                "id": r["id"],
                "title": r.get("title"),
                "finding": r.get("finding"),
                "category": r.get("category"),
                "source_url": r.get("source", {}).get("url"),
                "confidence": r.get("confidence", "medium"),
            }
            for r in notes.get("research", [])
        ],
        "summary": {
            "total_decisions": len(notes.get("decisions", [])),
            "total_assumptions": len(notes.get("assumptions", [])),
            "unvalidated_assumptions": sum(
                1 for a in notes.get("assumptions", []) if a.get("status") == "pending"
            ),
            "open_blockers": sum(
                1 for b in notes.get("blockers", []) if b.get("status") == "open"
            ),
            "pending_actions": sum(
                1 for t in notes.get("actions", []) if t.get("status") == "pending"
            ),
            "total_research": len(notes.get("research", [])),
        },
    }


def link_to_fpf_cycle(cycle_id: str) -> None:
    """Link current session to an FPF cycle."""
    state = get_current_session()
    if not state:
        return

    if "linked_fpf_cycles" not in state:
        state["linked_fpf_cycles"] = []

    if cycle_id not in state["linked_fpf_cycles"]:
        state["linked_fpf_cycles"].append(cycle_id)
        save_session_state(state)


def link_to_document(doc_path: str) -> None:
    """Link current session to a generated document."""
    state = get_current_session()
    if not state:
        return

    if "linked_documents" not in state:
        state["linked_documents"] = []

    if doc_path not in state["linked_documents"]:
        state["linked_documents"].append(doc_path)
        save_session_state(state)


# ============================================================================
# SESSION LISTING
# ============================================================================


def list_sessions(limit: int = 10) -> List[Dict[str, Any]]:
    """List recent Confucius sessions."""
    sessions = []

    if not CONFUCIUS_DIR.exists():
        return sessions

    # Find all session files
    for md_file in CONFUCIUS_DIR.glob("*.md"):
        if md_file.name.startswith("."):
            continue

        # Parse session info from filename
        session_id = md_file.stem

        sessions.append(
            {
                "session_id": session_id,
                "path": str(md_file),
                "modified": datetime.fromtimestamp(md_file.stat().st_mtime).isoformat(),
            }
        )

    # Also check current state
    current = get_current_session()
    if current:
        sessions.append(
            {
                "session_id": current.get("session_id"),
                "path": str(STATE_FILE),
                "modified": current.get("last_updated"),
                "status": "active",
                "topic": current.get("topic"),
            }
        )

    # Sort by modified descending
    sessions.sort(key=lambda x: x.get("modified", ""), reverse=True)

    return sessions[:limit]


# ============================================================================
# CLI
# ============================================================================


def print_status():
    """Print current session status."""
    state = get_current_session()

    if not state:
        print("No active Confucius session.")
        print('\nStart one with: python3 confucius_agent.py --start "Topic"')
        return

    notes = state.get("notes", {})

    print(f"Confucius Session: {state.get('session_id')}")
    print(f"Topic: {state.get('topic', 'No topic')}")
    print(f"Status: {state.get('status', 'unknown')}")
    print(f"Started: {state.get('created_at', 'unknown')[:16]}")
    print()
    print("Notes captured:")
    print(f"  Decisions:    {len(notes.get('decisions', []))}")
    print(f"  Assumptions:  {len(notes.get('assumptions', []))}")
    print(f"  Observations: {len(notes.get('observations', []))}")
    print(f"  Blockers:     {len(notes.get('blockers', []))}")
    print(f"  Actions:      {len(notes.get('actions', []))}")
    print(f"  Research:     {len(notes.get('research', []))}")

    if state.get("linked_fpf_cycles"):
        print(f"\nLinked FPF cycles: {len(state['linked_fpf_cycles'])}")

    if state.get("linked_documents"):
        print(f"Linked documents: {len(state['linked_documents'])}")


def main():
    parser = argparse.ArgumentParser(
        description="Confucius Note-Taker - Lightweight context capture"
    )

    # Session commands
    parser.add_argument(
        "--start", type=str, metavar="TOPIC", help="Start a new note-taking session"
    )
    parser.add_argument(
        "--end", action="store_true", help="End current session and save to file"
    )
    parser.add_argument(
        "--status", action="store_true", help="Show current session status"
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export current session notes (for FPF injection)",
    )
    parser.add_argument(
        "--markdown", action="store_true", help="Export current session as markdown"
    )
    parser.add_argument(
        "--list",
        type=int,
        nargs="?",
        const=5,
        metavar="N",
        help="List recent sessions (default: 5)",
    )

    # Capture commands
    parser.add_argument(
        "--capture",
        type=str,
        choices=[
            "decision",
            "assumption",
            "observation",
            "blocker",
            "action",
            "research",
        ],
        help="Capture a note of specified type",
    )
    parser.add_argument("--title", type=str, help="Title (for decisions/research)")
    parser.add_argument("--choice", type=str, help="Chosen option (for decisions)")
    parser.add_argument("--rationale", type=str, help="Why this choice (for decisions)")
    parser.add_argument("--text", type=str, help="Note text")
    parser.add_argument("--finding", type=str, help="Research finding text")
    parser.add_argument("--owner", type=str, help="Owner/assignee")
    parser.add_argument("--source", type=str, help="Source URL or reference")
    parser.add_argument("--due", type=str, help="Due date (for actions)")
    parser.add_argument(
        "--category",
        type=str,
        choices=["competitive", "technical", "market", "internal", "discovery"],
        default="discovery",
        help="Research category",
    )
    parser.add_argument(
        "--confidence",
        type=str,
        choices=["high", "medium", "low"],
        default="medium",
        help="Confidence level",
    )
    parser.add_argument(
        "--entities",
        type=str,
        help="Comma-separated related entity names (for research)",
    )

    # Auto-detect
    parser.add_argument(
        "--detect", type=str, metavar="TEXT", help="Auto-detect notes from text"
    )

    # Output format
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Session management
    parser.add_argument(
        "--ensure",
        type=str,
        nargs="?",
        const="Daily Work Session",
        metavar="TOPIC",
        help="Ensure session is active (handle stale, start if needed)",
    )

    args = parser.parse_args()

    # Handle commands
    if args.ensure:
        state = ensure_session_active(args.ensure)
        if args.json:
            print(json.dumps(state, indent=2))
        else:
            print(f"Session active: {state['session_id']} - {state['topic']}")
        return

    if args.start:
        state = start_session(args.start)
        if args.json:
            print(json.dumps(state, indent=2))
        else:
            print(f"Started session: {state['session_id']}")
            print(f"Topic: {args.start}")
        return 0

    if args.end:
        path = end_session()
        if path:
            print(f"Session saved to: {path}")
        else:
            print("No active session to end.")
        return 0

    if args.status:
        if args.json:
            state = get_current_session()
            print(json.dumps(state or {}, indent=2))
        else:
            print_status()
        return 0

    if args.export:
        data = export_for_fpf()
        print(json.dumps(data, indent=2))
        return 0

    if args.markdown:
        print(export_to_markdown())
        return 0

    if args.list is not None:
        sessions = list_sessions(args.list)
        if args.json:
            print(json.dumps(sessions, indent=2))
        else:
            print("Recent Confucius Sessions:\n")
            for s in sessions:
                status = f" [{s.get('status', 'saved')}]" if s.get("status") else ""
                topic = f" - {s.get('topic')}" if s.get("topic") else ""
                print(f"  {s['session_id']}{status}{topic}")
                print(f"    Modified: {s.get('modified', 'unknown')[:16]}")
        return 0

    if args.capture:
        note = None

        if args.capture == "decision":
            if not args.title or not args.choice or not args.rationale:
                print(
                    "Decision requires: --title, --choice, --rationale", file=sys.stderr
                )
                return 1
            note = capture_decision(
                args.title, args.choice, args.rationale, confidence=args.confidence
            )

        elif args.capture == "assumption":
            if not args.text:
                print("Assumption requires: --text", file=sys.stderr)
                return 1
            note = capture_assumption(args.text, source=args.source)

        elif args.capture == "observation":
            if not args.text:
                print("Observation requires: --text", file=sys.stderr)
                return 1
            note = capture_observation(args.text, source=args.source)

        elif args.capture == "blocker":
            if not args.text:
                print("Blocker requires: --text", file=sys.stderr)
                return 1
            note = capture_blocker(args.text, owner=args.owner)

        elif args.capture == "action":
            if not args.text:
                print("Action requires: --text", file=sys.stderr)
                return 1
            note = capture_action(args.text, owner=args.owner, due=args.due)

        elif args.capture == "research":
            if not args.title or not args.finding:
                print("Research requires: --title, --finding", file=sys.stderr)
                return 1
            related = args.entities.split(",") if args.entities else None
            note = capture_research(
                title=args.title,
                finding=args.finding,
                source_url=args.source,
                category=args.category,
                confidence=args.confidence,
                related_entities=related,
            )

        if note:
            if args.json:
                print(json.dumps(note, indent=2))
            else:
                print(f"Captured {args.capture}: [{note['id']}]")
        return 0

    if args.detect:
        captured = detect_and_capture(args.detect)
        if args.json:
            print(json.dumps(captured, indent=2))
        else:
            if captured:
                print(f"Auto-captured {len(captured)} notes:")
                for c in captured:
                    print(f"  [{c['type']}] {c['note']['id']}")
            else:
                print("No notes detected in text.")
        return 0

    # Default: show status
    print_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
