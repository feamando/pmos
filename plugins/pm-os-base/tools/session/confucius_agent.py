#!/usr/bin/env python3
"""
Confucius Note-Taker Agent — Lightweight context capture during conversations.

Captures decisions, assumptions, observations, blockers, actions, and research
without the full FPF cycle overhead. Feeds into document generation commands.

Usage:
    python3 confucius_agent.py --start "Session topic"
    python3 confucius_agent.py --status
    python3 confucius_agent.py --export
    python3 confucius_agent.py --capture decision --title "X" --choice "Y" --rationale "Z"
    python3 confucius_agent.py --ensure "Daily Work Session"
    python3 confucius_agent.py --end
    python3 confucius_agent.py --list 5
"""

import argparse
import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Config-driven path resolution
_CONFUCIUS_DIR: Optional[Path] = None


def _get_brain_dir() -> Path:
    """Resolve brain directory from environment."""
    user_dir = os.environ.get("PM_OS_USER", "")
    if user_dir:
        return Path(user_dir) / "brain"
    # Fallback: walk up from script
    current = Path(__file__).resolve().parent
    for _ in range(10):
        candidate = current / "user" / "brain"
        if candidate.exists():
            return candidate
        current = current.parent
    return Path.home() / "pm-os" / "user" / "brain"


def _get_confucius_dir() -> Path:
    global _CONFUCIUS_DIR
    if not _CONFUCIUS_DIR:
        _CONFUCIUS_DIR = _get_brain_dir() / "Confucius"
    return _CONFUCIUS_DIR


def _state_file() -> Path:
    return _get_confucius_dir() / ".confucius_state.json"


# Note categories
NOTE_TYPES = {
    "decision": "D", "assumption": "A", "observation": "O",
    "blocker": "B", "action": "T", "research": "R",
}

RESEARCH_CATEGORIES = ["competitive", "technical", "market", "internal", "discovery"]


# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

def get_current_session() -> Optional[Dict[str, Any]]:
    """Load current session state."""
    sf = _state_file()
    if not sf.exists():
        return None
    with open(sf, "r", encoding="utf-8") as f:
        state = json.load(f)
    if state.get("status") != "active":
        return None
    return state


def is_session_stale(state: Dict[str, Any], max_hours: int = 24) -> bool:
    """Check if a session is stale (older than max_hours)."""
    created_at = state.get("created_at")
    if not created_at:
        return False
    try:
        created = datetime.fromisoformat(created_at)
        return (datetime.now() - created).total_seconds() > (max_hours * 3600)
    except (ValueError, TypeError):
        return False


def handle_stale_session() -> Optional[Path]:
    """Check for and handle stale sessions."""
    state = get_current_session()
    if state and is_session_stale(state):
        logger.info("Closing stale session: %s", state.get("session_id"))
        return end_session()
    return None


def ensure_session_active(topic: str = "Daily Work Session") -> Dict[str, Any]:
    """Ensure a Confucius session is active."""
    handle_stale_session()
    state = get_current_session()
    if state:
        return state
    return start_session(topic)


def save_session_state(state: Dict[str, Any]) -> None:
    """Save session state to disk."""
    _get_confucius_dir().mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now().isoformat()
    with open(_state_file(), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def start_session(topic: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Start a new Confucius note-taking session."""
    if session_id is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        short_id = str(uuid.uuid4())[:8]
        session_id = f"{date_str}-{short_id}"

    state = {
        "session_id": session_id, "topic": topic,
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "notes": {
            "decisions": [], "assumptions": [], "observations": [],
            "blockers": [], "actions": [], "research": [],
        },
        "counters": {"D": 0, "A": 0, "O": 0, "B": 0, "T": 0, "R": 0},
        "linked_fpf_cycles": [], "linked_documents": [],
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
    md_path = _get_confucius_dir() / f"{state['session_id']}.md"
    md_path.write_text(export_to_markdown(state), encoding="utf-8")
    save_session_state(state)
    return md_path


# ============================================================================
# NOTE CAPTURE
# ============================================================================

def _get_or_start_session() -> Dict[str, Any]:
    state = get_current_session()
    if not state:
        state = start_session("Auto-started session")
    return state


def capture_decision(title: str, choice: str, rationale: str,
                     alternatives: Optional[List[str]] = None, confidence: str = "medium") -> Dict[str, Any]:
    state = _get_or_start_session()
    state["counters"]["D"] += 1
    decision = {
        "id": f"D{state['counters']['D']}", "title": title, "choice": choice,
        "rationale": rationale, "alternatives": alternatives or [],
        "confidence": confidence, "timestamp": datetime.now().isoformat(),
    }
    state["notes"]["decisions"].append(decision)
    save_session_state(state)
    return decision


def capture_assumption(text: str, status: str = "pending", source: Optional[str] = None) -> Dict[str, Any]:
    state = _get_or_start_session()
    state["counters"]["A"] += 1
    assumption = {
        "id": f"A{state['counters']['A']}", "text": text,
        "status": status, "source": source, "timestamp": datetime.now().isoformat(),
    }
    state["notes"]["assumptions"].append(assumption)
    save_session_state(state)
    return assumption


def capture_observation(text: str, source: Optional[str] = None, category: Optional[str] = None) -> Dict[str, Any]:
    state = _get_or_start_session()
    state["counters"]["O"] += 1
    observation = {
        "id": f"O{state['counters']['O']}", "text": text,
        "source": source, "category": category, "timestamp": datetime.now().isoformat(),
    }
    state["notes"]["observations"].append(observation)
    save_session_state(state)
    return observation


def capture_blocker(text: str, impact: Optional[str] = None, owner: Optional[str] = None) -> Dict[str, Any]:
    state = _get_or_start_session()
    state["counters"]["B"] += 1
    blocker = {
        "id": f"B{state['counters']['B']}", "text": text,
        "impact": impact, "owner": owner, "status": "open",
        "timestamp": datetime.now().isoformat(),
    }
    state["notes"]["blockers"].append(blocker)
    save_session_state(state)
    return blocker


def capture_action(text: str, owner: Optional[str] = None, due: Optional[str] = None) -> Dict[str, Any]:
    state = _get_or_start_session()
    state["counters"]["T"] += 1
    action = {
        "id": f"T{state['counters']['T']}", "text": text,
        "owner": owner, "due": due, "status": "pending",
        "timestamp": datetime.now().isoformat(),
    }
    state["notes"]["actions"].append(action)
    save_session_state(state)
    return action


def capture_research(title: str, finding: str, source_url: Optional[str] = None,
                     source_type: str = "web", category: str = "discovery",
                     confidence: str = "medium", related_entities: Optional[List[str]] = None,
                     query: Optional[str] = None) -> Dict[str, Any]:
    state = _get_or_start_session()
    if "research" not in state["notes"]:
        state["notes"]["research"] = []
    if "R" not in state["counters"]:
        state["counters"]["R"] = 0
    state["counters"]["R"] += 1
    research = {
        "id": f"R{state['counters']['R']}", "title": title, "finding": finding,
        "source": {"type": source_type, "url": source_url},
        "category": category, "confidence": confidence,
        "related_entities": related_entities or [], "query": query,
        "timestamp": datetime.now().isoformat(),
    }
    state["notes"]["research"].append(research)
    save_session_state(state)
    _write_research_to_inbox(research, state.get("session_id", ""))
    return research


def _write_research_to_inbox(research: Dict[str, Any], session_id: str) -> None:
    """Write research finding to brain inbox for later enrichment."""
    inbox_dir = _get_brain_dir() / "Inbox" / "ClaudeSession" / "Raw"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    inbox_file = inbox_dir / f"session_{date_str}.json"
    entries = []
    if inbox_file.exists():
        try:
            with open(inbox_file, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except (json.JSONDecodeError, IOError):
            entries = []
    entries.append({**research, "session_id": session_id, "inbox_created": datetime.now().isoformat()})
    with open(inbox_file, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


# ============================================================================
# EXPORT & FORMAT
# ============================================================================

def export_to_markdown(state: Optional[Dict[str, Any]] = None) -> str:
    """Export current session notes to markdown format."""
    if state is None:
        state = get_current_session()
    if not state:
        return "# No Active Session\n"

    notes = state.get("notes", {})
    md = f"# Confucius Notes: {state.get('session_id', 'unknown')}\n\n"
    md += f"**Date:** {state.get('created_at', 'unknown')[:10]}\n"
    md += f"**Topic:** {state.get('topic', 'No topic')}\n"
    md += f"**Status:** {state.get('status', 'unknown')}\n\n---\n\n"

    if notes.get("decisions"):
        md += "## Decisions\n\n"
        for d in notes["decisions"]:
            md += f"- [{d['id']}] **{d.get('title', 'Untitled')}** | Chose: {d.get('choice', 'N/A')} | Why: {d.get('rationale', 'N/A')}\n"
            if d.get("alternatives"):
                md += f"  - Alternatives: {', '.join(d['alternatives'])}\n"
            md += f"  - Confidence: {d.get('confidence', 'medium')}\n\n"

    if notes.get("assumptions"):
        md += "## Assumptions\n\n"
        for a in notes["assumptions"]:
            md += f"- [{a['id']}] {a.get('text', 'N/A')} | Status: {a.get('status', 'pending')}\n"
            if a.get("source"):
                md += f"  - Source: {a['source']}\n"
            md += "\n"

    if notes.get("observations"):
        md += "## Observations\n\n"
        for o in notes["observations"]:
            md += f"- [{o['id']}] {o.get('text', 'N/A')}"
            if o.get("source"):
                md += f" | Source: {o['source']}"
            md += "\n"
        md += "\n"

    if notes.get("blockers"):
        md += "## Blockers\n\n"
        for b in notes["blockers"]:
            md += f"- [{b['id']}] {b.get('text', 'N/A')}"
            if b.get("owner"):
                md += f" | Owner: {b['owner']}"
            md += f" | Status: {b.get('status', 'open')}\n"
        md += "\n"

    if notes.get("actions"):
        md += "## Actions\n\n"
        for t in notes["actions"]:
            marker = "x" if t.get("status") == "done" else " "
            md += f"- [{marker}] [{t['id']}] {t.get('text', 'N/A')}"
            if t.get("owner"):
                md += f" | Owner: {t['owner']}"
            if t.get("due"):
                md += f" | Due: {t['due']}"
            md += "\n"
        md += "\n"

    if notes.get("research"):
        md += "## Research Findings\n\n"
        for r in notes["research"]:
            md += f"- [{r['id']}] **{r.get('title', 'Untitled')}** | {r.get('category', 'discovery')}\n"
            md += f"  - Finding: {r.get('finding', 'N/A')}\n"
            if r.get("source", {}).get("url"):
                md += f"  - Source: {r['source']['url']}\n"
            md += f"  - Confidence: {r.get('confidence', 'medium')}\n\n"

    md += f"---\n*Generated: {datetime.now().isoformat()}*\n"
    return md


def export_for_fpf() -> Dict[str, Any]:
    """Export current session notes for FPF context injection."""
    state = get_current_session()
    if not state:
        return {"error": "No active session"}
    notes = state.get("notes", {})
    return {
        "session_id": state.get("session_id"), "topic": state.get("topic"),
        "decisions": [{"id": d["id"], "title": d.get("title"), "choice": d.get("choice"),
                       "rationale": d.get("rationale"), "confidence": d.get("confidence", "medium")}
                      for d in notes.get("decisions", [])],
        "assumptions": [{"id": a["id"], "text": a.get("text"), "status": a.get("status", "pending")}
                        for a in notes.get("assumptions", [])],
        "blockers": [{"id": b["id"], "text": b.get("text"), "status": b.get("status", "open")}
                     for b in notes.get("blockers", []) if b.get("status") != "resolved"],
        "open_actions": [{"id": t["id"], "text": t.get("text"), "owner": t.get("owner")}
                         for t in notes.get("actions", []) if t.get("status") != "done"],
        "research": [{"id": r["id"], "title": r.get("title"), "finding": r.get("finding"),
                       "category": r.get("category"), "confidence": r.get("confidence", "medium")}
                      for r in notes.get("research", [])],
    }


def list_sessions(limit: int = 10) -> List[Dict[str, Any]]:
    """List recent Confucius sessions."""
    sessions = []
    conf_dir = _get_confucius_dir()
    if conf_dir.exists():
        for md_file in conf_dir.glob("*.md"):
            if md_file.name.startswith("."):
                continue
            sessions.append({
                "session_id": md_file.stem, "path": str(md_file),
                "modified": datetime.fromtimestamp(md_file.stat().st_mtime).isoformat(),
            })
    current = get_current_session()
    if current:
        sessions.append({
            "session_id": current.get("session_id"), "path": str(_state_file()),
            "modified": current.get("last_updated"), "status": "active",
            "topic": current.get("topic"),
        })
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


def main():
    parser = argparse.ArgumentParser(description="Confucius Note-Taker")
    parser.add_argument("--start", type=str, metavar="TOPIC", help="Start a new session")
    parser.add_argument("--end", action="store_true", help="End current session")
    parser.add_argument("--status", action="store_true", help="Show session status")
    parser.add_argument("--export", action="store_true", help="Export for FPF injection")
    parser.add_argument("--markdown", action="store_true", help="Export as markdown")
    parser.add_argument("--list", type=int, nargs="?", const=5, metavar="N", help="List recent sessions")
    parser.add_argument("--capture", type=str, choices=list(NOTE_TYPES.keys()), help="Capture a note")
    parser.add_argument("--title", type=str, help="Title (for decisions/research)")
    parser.add_argument("--choice", type=str, help="Chosen option (for decisions)")
    parser.add_argument("--rationale", type=str, help="Why this choice (for decisions)")
    parser.add_argument("--text", type=str, help="Note text")
    parser.add_argument("--finding", type=str, help="Research finding text")
    parser.add_argument("--owner", type=str, help="Owner/assignee")
    parser.add_argument("--source", type=str, help="Source URL or reference")
    parser.add_argument("--due", type=str, help="Due date (for actions)")
    parser.add_argument("--category", type=str, choices=RESEARCH_CATEGORIES, default="discovery")
    parser.add_argument("--confidence", type=str, choices=["high", "medium", "low"], default="medium")
    parser.add_argument("--entities", type=str, help="Comma-separated related entity names")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--ensure", type=str, nargs="?", const="Daily Work Session", metavar="TOPIC",
                        help="Ensure session is active")

    args = parser.parse_args()

    if args.ensure:
        state = ensure_session_active(args.ensure)
        if args.json:
            print(json.dumps(state, indent=2))
        else:
            print(f"Session active: {state['session_id']} - {state['topic']}")
        return 0

    if args.start:
        state = start_session(args.start)
        print(f"Started session: {state['session_id']}")
        return 0

    if args.end:
        path = end_session()
        print(f"Session saved to: {path}" if path else "No active session to end.")
        return 0

    if args.status:
        if args.json:
            print(json.dumps(get_current_session() or {}, indent=2))
        else:
            print_status()
        return 0

    if args.export:
        print(json.dumps(export_for_fpf(), indent=2))
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
            if not (args.title and args.choice and args.rationale):
                print("Decision requires: --title, --choice, --rationale", file=sys.stderr)
                return 1
            note = capture_decision(args.title, args.choice, args.rationale, confidence=args.confidence)
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
            if not (args.title and args.finding):
                print("Research requires: --title, --finding", file=sys.stderr)
                return 1
            related = args.entities.split(",") if args.entities else None
            note = capture_research(title=args.title, finding=args.finding, source_url=args.source,
                                    category=args.category, confidence=args.confidence, related_entities=related)
        if note:
            if args.json:
                print(json.dumps(note, indent=2))
            else:
                print(f"Captured {args.capture}: [{note['id']}]")
        return 0

    print_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
