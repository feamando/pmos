#!/usr/bin/env python3
"""
Session Manager - Persistent context management for Claude Code sessions.

Captures detailed session context before compaction to preserve:
- Objectives and progress
- Decisions made with rationale
- Files touched and explored
- Open questions and next steps

Usage:
    python3 session_manager.py --save              # Save current session
    python3 session_manager.py --load [session_id] # Load session context
    python3 session_manager.py --search "query"    # Search sessions
    python3 session_manager.py --archive           # Archive current session
    python3 session_manager.py --status            # Show session status
    python3 session_manager.py --list [n]          # List recent sessions
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Configuration
SESSIONS_DIR = Path(__file__).parent.parent / "Sessions"
ACTIVE_DIR = SESSIONS_DIR / "Active"
ARCHIVE_DIR = SESSIONS_DIR / "Archive"
INDEX_FILE = SESSIONS_DIR / "Index.md"
CURRENT_SESSION = ACTIVE_DIR / "current.md"


def ensure_directories():
    """Ensure session directories exist."""
    ACTIVE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


def generate_session_id() -> str:
    """Generate a unique session ID."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    # Find existing sessions for today
    existing = list(ARCHIVE_DIR.glob(f"{date_str}-*.md"))
    existing += list(ACTIVE_DIR.glob(f"{date_str}-*.md"))

    # Find next sequence number
    seq = 1
    for f in existing:
        match = re.search(r"-(\d+)\.md$", f.name)
        if match:
            seq = max(seq, int(match.group(1)) + 1)

    return f"{date_str}-{seq:03d}"


def parse_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content."""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1])
                body = parts[2].strip()
                return frontmatter or {}, body
            except yaml.YAMLError:
                pass
    return {}, content


def create_frontmatter(data: Dict[str, Any]) -> str:
    """Create YAML frontmatter string."""
    return f"---\n{yaml.dump(data, default_flow_style=False)}---\n"


class SessionManager:
    """Manages session context persistence."""

    def __init__(self):
        ensure_directories()
        self.current_session_path = CURRENT_SESSION

    def get_current_session(self) -> Optional[Dict[str, Any]]:
        """Load current active session if exists."""
        if self.current_session_path.exists():
            content = self.current_session_path.read_text()
            frontmatter, body = parse_frontmatter(content)
            return {
                "frontmatter": frontmatter,
                "body": body,
                "path": self.current_session_path,
            }
        return None

    def create_session(
        self, title: str, objectives: List[str] = None, tags: List[str] = None
    ) -> str:
        """Create a new session."""
        session_id = generate_session_id()
        now = datetime.now().isoformat()

        frontmatter = {
            "session_id": session_id,
            "title": title,
            "started": now,
            "last_updated": now,
            "status": "active",
            "tags": tags or [],
            "files_created": [],
            "files_modified": [],
            "files_explored": [],
            "decisions": [],
        }

        objectives_md = "\n".join(
            [f"- [ ] {obj}" for obj in (objectives or ["Define objectives"])]
        )

        body = f"""
# Session: {title}

## Objectives
{objectives_md}

## Work Log
<!-- Add timestamped entries as work progresses -->

## Decisions Made
| Decision | Rationale | Alternatives Rejected |
|----------|-----------|----------------------|

## Files Touched
### Created
<!-- Files created during this session -->

### Modified
<!-- Files modified during this session -->

### Explored (Not Changed)
<!-- Files read but not modified -->

## Open Questions
<!-- Questions that need resolution -->

## Context for Next Session
<!-- Key information for session resumption -->
"""

        content = create_frontmatter(frontmatter) + body
        self.current_session_path.write_text(content)

        print(f"Created session: {session_id}")
        print(f"Title: {title}")
        print(f"Path: {self.current_session_path}")

        return session_id

    def update_session(self, updates: Dict[str, Any]) -> bool:
        """Update current session with new information."""
        session = self.get_current_session()
        if not session:
            print("No active session. Create one with --create")
            return False

        frontmatter = session["frontmatter"]
        body = session["body"]

        # Update frontmatter
        frontmatter["last_updated"] = datetime.now().isoformat()

        # Merge list fields
        for field in [
            "tags",
            "files_created",
            "files_modified",
            "files_explored",
            "decisions",
        ]:
            if field in updates:
                existing = frontmatter.get(field, [])
                new_items = updates[field]
                if isinstance(new_items, list):
                    frontmatter[field] = list(set(existing + new_items))
                else:
                    frontmatter[field] = existing + [new_items]

        # Update scalar fields
        for field in ["title", "status"]:
            if field in updates:
                frontmatter[field] = updates[field]

        content = create_frontmatter(frontmatter) + body
        self.current_session_path.write_text(content)

        print(f"Updated session: {frontmatter.get('session_id')}")
        return True

    def add_work_log_entry(self, entry: str, timestamp: str = None) -> bool:
        """Add an entry to the work log section."""
        session = self.get_current_session()
        if not session:
            print("No active session.")
            return False

        frontmatter = session["frontmatter"]
        body = session["body"]

        if not timestamp:
            timestamp = datetime.now().strftime("%H:%M")

        # Find work log section and append
        work_log_marker = "## Work Log"
        if work_log_marker in body:
            parts = body.split(work_log_marker, 1)
            # Find next section
            next_section = re.search(r"\n## ", parts[1])
            if next_section:
                insert_pos = next_section.start()
                new_entry = f"\n### {timestamp}\n{entry}\n"
                parts[1] = parts[1][:insert_pos] + new_entry + parts[1][insert_pos:]
            else:
                parts[1] += f"\n### {timestamp}\n{entry}\n"
            body = work_log_marker.join(parts)

        frontmatter["last_updated"] = datetime.now().isoformat()
        content = create_frontmatter(frontmatter) + body
        self.current_session_path.write_text(content)

        print(f"Added work log entry at {timestamp}")
        return True

    def add_decision(
        self, decision: str, rationale: str, alternatives: str = ""
    ) -> bool:
        """Add a decision to the session."""
        session = self.get_current_session()
        if not session:
            print("No active session.")
            return False

        frontmatter = session["frontmatter"]
        body = session["body"]

        # Add to frontmatter decisions list
        decision_record = {
            "decision": decision,
            "rationale": rationale,
            "alternatives": alternatives,
            "timestamp": datetime.now().isoformat(),
        }
        frontmatter.setdefault("decisions", []).append(decision_record)

        # Add to decisions table in body
        table_row = f"| {decision} | {rationale} | {alternatives} |"
        decisions_marker = "## Decisions Made"
        if decisions_marker in body:
            # Find the table and append row
            table_end = body.find(
                "\n\n", body.find(decisions_marker) + len(decisions_marker)
            )
            if table_end > 0:
                body = body[:table_end] + f"\n{table_row}" + body[table_end:]

        frontmatter["last_updated"] = datetime.now().isoformat()
        content = create_frontmatter(frontmatter) + body
        self.current_session_path.write_text(content)

        print(f"Added decision: {decision[:50]}...")
        return True

    def add_open_question(self, question: str) -> bool:
        """Add an open question to the session."""
        session = self.get_current_session()
        if not session:
            print("No active session.")
            return False

        frontmatter = session["frontmatter"]
        body = session["body"]

        # Find open questions section and append
        questions_marker = "## Open Questions"
        if questions_marker in body:
            parts = body.split(questions_marker, 1)
            next_section = re.search(r"\n## ", parts[1])
            if next_section:
                insert_pos = next_section.start()
                parts[1] = (
                    parts[1][:insert_pos]
                    + f"\n- [ ] {question}"
                    + parts[1][insert_pos:]
                )
            else:
                parts[1] += f"\n- [ ] {question}"
            body = questions_marker.join(parts)

        frontmatter["last_updated"] = datetime.now().isoformat()
        content = create_frontmatter(frontmatter) + body
        self.current_session_path.write_text(content)

        print(f"Added open question: {question[:50]}...")
        return True

    def archive_session(self, summary: str = None) -> Optional[str]:
        """Archive the current session."""
        session = self.get_current_session()
        if not session:
            print("No active session to archive.")
            return None

        frontmatter = session["frontmatter"]
        body = session["body"]

        # Update status
        frontmatter["status"] = "archived"
        frontmatter["archived_at"] = datetime.now().isoformat()
        if summary:
            frontmatter["summary"] = summary

        # Calculate duration
        started = datetime.fromisoformat(
            frontmatter.get("started", datetime.now().isoformat())
        )
        duration = datetime.now() - started
        frontmatter["duration_minutes"] = int(duration.total_seconds() / 60)

        # Add summary to body if provided
        if summary:
            body = f"\n## Session Summary\n{summary}\n" + body

        content = create_frontmatter(frontmatter) + body

        # Move to archive
        session_id = frontmatter.get("session_id", generate_session_id())
        archive_path = ARCHIVE_DIR / f"{session_id}.md"
        archive_path.write_text(content)

        # Remove current session
        self.current_session_path.unlink()

        # Update index
        self._update_index(frontmatter)

        print(f"Archived session: {session_id}")
        print(f"Path: {archive_path}")
        print(f"Duration: {frontmatter['duration_minutes']} minutes")

        return session_id

    def _update_index(self, session_meta: Dict[str, Any]):
        """Update the session index file."""
        index_entry = f"""
### {session_meta.get('session_id')}
- **Title:** {session_meta.get('title', 'Untitled')}
- **Date:** {session_meta.get('started', '')[:10]}
- **Duration:** {session_meta.get('duration_minutes', 0)} minutes
- **Tags:** {', '.join(session_meta.get('tags', []))}
- **Files:** {len(session_meta.get('files_created', []))} created, {len(session_meta.get('files_modified', []))} modified
- **Decisions:** {len(session_meta.get('decisions', []))}
"""

        if INDEX_FILE.exists():
            current = INDEX_FILE.read_text()
            # Insert after header
            if "## Recent Sessions" in current:
                parts = current.split("## Recent Sessions", 1)
                current = parts[0] + "## Recent Sessions" + index_entry + parts[1]
            else:
                current += f"\n## Recent Sessions{index_entry}"
            INDEX_FILE.write_text(current)
        else:
            INDEX_FILE.write_text(f"""# Session Index

Searchable index of all archived sessions.

## Recent Sessions
{index_entry}
""")

    def load_session(self, session_id: str = None) -> Optional[Dict[str, Any]]:
        """Load a session by ID or load the most recent."""
        if session_id:
            # Search in archive
            archive_path = ARCHIVE_DIR / f"{session_id}.md"
            if archive_path.exists():
                content = archive_path.read_text()
                frontmatter, body = parse_frontmatter(content)
                return {"frontmatter": frontmatter, "body": body, "path": archive_path}

            # Search by partial match
            matches = list(ARCHIVE_DIR.glob(f"*{session_id}*.md"))
            if matches:
                content = matches[0].read_text()
                frontmatter, body = parse_frontmatter(content)
                return {"frontmatter": frontmatter, "body": body, "path": matches[0]}
        else:
            # Load most recent
            sessions = sorted(ARCHIVE_DIR.glob("*.md"), reverse=True)
            if sessions:
                content = sessions[0].read_text()
                frontmatter, body = parse_frontmatter(content)
                return {"frontmatter": frontmatter, "body": body, "path": sessions[0]}

        return None

    def search_sessions(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search sessions by content or tags."""
        results = []
        query_lower = query.lower()

        # Search archive
        for session_file in ARCHIVE_DIR.glob("*.md"):
            content = session_file.read_text()
            frontmatter, body = parse_frontmatter(content)

            # Check tags
            tags = frontmatter.get("tags", [])
            tag_match = any(query_lower in tag.lower() for tag in tags)

            # Check title
            title = frontmatter.get("title", "")
            title_match = query_lower in title.lower()

            # Check body content
            body_match = query_lower in body.lower()

            if tag_match or title_match or body_match:
                # Calculate relevance score
                score = 0
                if tag_match:
                    score += 3
                if title_match:
                    score += 2
                if body_match:
                    score += 1

                results.append(
                    {
                        "session_id": frontmatter.get("session_id"),
                        "title": title,
                        "date": frontmatter.get("started", "")[:10],
                        "tags": tags,
                        "score": score,
                        "path": session_file,
                    }
                )

        # Sort by score then date
        results.sort(key=lambda x: (-x["score"], x["date"]), reverse=True)

        return results[:limit]

    def list_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List recent sessions."""
        sessions = []

        # Check active session
        if self.current_session_path.exists():
            content = self.current_session_path.read_text()
            frontmatter, _ = parse_frontmatter(content)
            sessions.append(
                {
                    "session_id": frontmatter.get("session_id", "current"),
                    "title": frontmatter.get("title", "Active Session"),
                    "date": frontmatter.get("started", "")[:10],
                    "status": "active",
                    "tags": frontmatter.get("tags", []),
                }
            )

        # Get archived sessions
        for session_file in sorted(ARCHIVE_DIR.glob("*.md"), reverse=True)[:limit]:
            content = session_file.read_text()
            frontmatter, _ = parse_frontmatter(content)
            sessions.append(
                {
                    "session_id": frontmatter.get("session_id"),
                    "title": frontmatter.get("title", "Untitled"),
                    "date": frontmatter.get("started", "")[:10],
                    "status": "archived",
                    "tags": frontmatter.get("tags", []),
                    "duration": frontmatter.get("duration_minutes", 0),
                }
            )

        return sessions[:limit]

    def get_status(self) -> Dict[str, Any]:
        """Get current session status."""
        session = self.get_current_session()
        if not session:
            return {"status": "no_active_session"}

        fm = session["frontmatter"]
        started = datetime.fromisoformat(fm.get("started", datetime.now().isoformat()))
        duration = datetime.now() - started

        return {
            "status": "active",
            "session_id": fm.get("session_id"),
            "title": fm.get("title"),
            "started": fm.get("started"),
            "duration_minutes": int(duration.total_seconds() / 60),
            "tags": fm.get("tags", []),
            "files_created": len(fm.get("files_created", [])),
            "files_modified": len(fm.get("files_modified", [])),
            "decisions": len(fm.get("decisions", [])),
            "last_updated": fm.get("last_updated"),
        }

    def generate_summary(self) -> str:
        """Generate a summary of the current session for compaction."""
        session = self.get_current_session()
        if not session:
            return "No active session."

        fm = session["frontmatter"]
        body = session["body"]

        summary_parts = [
            f"## Session Summary: {fm.get('title', 'Untitled')}",
            f"**ID:** {fm.get('session_id')}",
            f"**Duration:** {self.get_status().get('duration_minutes', 0)} minutes",
            "",
            "### Key Information",
        ]

        # Extract objectives status
        objectives = re.findall(r"- \[([ x])\] (.+)", body)
        if objectives:
            summary_parts.append("\n**Objectives:**")
            for checked, obj in objectives[:5]:  # Limit to 5
                status = "✓" if checked == "x" else "○"
                summary_parts.append(f"- {status} {obj}")

        # Decisions
        decisions = fm.get("decisions", [])
        if decisions:
            summary_parts.append(f"\n**Decisions Made:** {len(decisions)}")
            for d in decisions[:3]:  # Top 3
                summary_parts.append(f"- {d.get('decision', '')[:60]}...")

        # Files
        files_created = fm.get("files_created", [])
        files_modified = fm.get("files_modified", [])
        if files_created or files_modified:
            summary_parts.append(
                f"\n**Files:** {len(files_created)} created, {len(files_modified)} modified"
            )

        # Open questions
        questions = re.findall(r"## Open Questions\n((?:- \[ \] .+\n?)+)", body)
        if questions:
            summary_parts.append("\n**Open Questions:**")
            for q in questions[0].strip().split("\n")[:3]:
                summary_parts.append(q)

        # Context for next
        context_match = re.search(
            r"## Context for Next Session\n(.+?)(?=\n## |$)", body, re.DOTALL
        )
        if context_match and context_match.group(1).strip():
            summary_parts.append("\n**Context for Continuation:**")
            summary_parts.append(context_match.group(1).strip()[:200])

        return "\n".join(summary_parts)


def main():
    parser = argparse.ArgumentParser(description="Session Manager for Claude Code")
    parser.add_argument(
        "--create", "-c", type=str, help="Create new session with title"
    )
    parser.add_argument(
        "--save", "-s", action="store_true", help="Save/update current session"
    )
    parser.add_argument(
        "--load", "-l", type=str, nargs="?", const="", help="Load session by ID"
    )
    parser.add_argument("--search", type=str, help="Search sessions by query")
    parser.add_argument(
        "--archive", "-a", action="store_true", help="Archive current session"
    )
    parser.add_argument("--status", action="store_true", help="Show session status")
    parser.add_argument(
        "--list", "-n", type=int, nargs="?", const=10, help="List recent sessions"
    )
    parser.add_argument(
        "--summary", action="store_true", help="Generate session summary"
    )
    parser.add_argument("--log", type=str, help="Add work log entry")
    parser.add_argument(
        "--decision",
        type=str,
        help="Add decision (format: decision|rationale|alternatives)",
    )
    parser.add_argument("--question", "-q", type=str, help="Add open question")
    parser.add_argument("--tags", type=str, help="Tags (comma-separated)")
    parser.add_argument("--objectives", type=str, help="Objectives (comma-separated)")
    parser.add_argument(
        "--files-created", type=str, help="Files created (comma-separated)"
    )
    parser.add_argument(
        "--files-modified", type=str, help="Files modified (comma-separated)"
    )

    args = parser.parse_args()

    manager = SessionManager()

    if args.create:
        objectives = args.objectives.split(",") if args.objectives else None
        tags = args.tags.split(",") if args.tags else None
        manager.create_session(args.create, objectives, tags)

    elif args.save:
        updates = {}
        if args.tags:
            updates["tags"] = [t.strip() for t in args.tags.split(",")]
        if args.files_created:
            updates["files_created"] = [
                f.strip() for f in args.files_created.split(",")
            ]
        if args.files_modified:
            updates["files_modified"] = [
                f.strip() for f in args.files_modified.split(",")
            ]

        if updates:
            manager.update_session(updates)
        else:
            status = manager.get_status()
            if status["status"] == "active":
                print(f"Session active: {status['session_id']}")
                print(f"Use --tags, --files-created, --files-modified to update")
            else:
                print("No active session. Use --create to start one.")

    elif args.load is not None:
        session = manager.load_session(args.load if args.load else None)
        if session:
            print(f"Session: {session['frontmatter'].get('session_id')}")
            print(f"Title: {session['frontmatter'].get('title')}")
            print(f"Path: {session['path']}")
            print("\n--- Content Preview ---")
            print(session["body"][:1000])
        else:
            print("Session not found.")

    elif args.search:
        results = manager.search_sessions(args.search)
        if results:
            print(f"Found {len(results)} sessions matching '{args.search}':\n")
            for r in results:
                print(f"  [{r['session_id']}] {r['title']}")
                print(f"    Date: {r['date']} | Tags: {', '.join(r['tags'])}")
                print()
        else:
            print(f"No sessions found matching '{args.search}'")

    elif args.archive:
        session_id = manager.archive_session()
        if session_id:
            print(f"Session {session_id} archived successfully.")

    elif args.status:
        status = manager.get_status()
        if status["status"] == "active":
            print(f"Active Session: {status['session_id']}")
            print(f"Title: {status['title']}")
            print(f"Duration: {status['duration_minutes']} minutes")
            print(
                f"Files: {status['files_created']} created, {status['files_modified']} modified"
            )
            print(f"Decisions: {status['decisions']}")
            print(f"Tags: {', '.join(status['tags'])}")
        else:
            print("No active session.")

    elif args.list is not None:
        sessions = manager.list_sessions(args.list)
        if sessions:
            print("Recent Sessions:\n")
            for s in sessions:
                status_icon = "●" if s["status"] == "active" else "○"
                duration = f" ({s.get('duration', '?')}m)" if "duration" in s else ""
                print(f"  {status_icon} [{s['session_id']}] {s['title']}{duration}")
                print(
                    f"    {s['date']} | {', '.join(s['tags']) if s['tags'] else 'no tags'}"
                )
                print()
        else:
            print("No sessions found.")

    elif args.summary:
        print(manager.generate_summary())

    elif args.log:
        manager.add_work_log_entry(args.log)

    elif args.decision:
        parts = args.decision.split("|")
        decision = parts[0] if len(parts) > 0 else ""
        rationale = parts[1] if len(parts) > 1 else ""
        alternatives = parts[2] if len(parts) > 2 else ""
        manager.add_decision(decision, rationale, alternatives)

    elif args.question:
        manager.add_open_question(args.question)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
