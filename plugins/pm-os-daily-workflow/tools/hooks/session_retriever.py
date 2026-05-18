#!/usr/bin/env python3
"""Session Retriever: searches past session transcripts for relevant context.

Called automatically when topic overlap with past sessions is detected.
Returns verbatim conversation excerpts, not summaries.

Usage:
    python3 session_retriever.py --query "search feature rollout"
    python3 session_retriever.py --query "business case" --sessions 5
    python3 session_retriever.py --query "google docs table" --full
    python3 session_retriever.py --list-topics

Designed for fast local search. No API calls, no external dependencies.

v5.0: All paths from config, logging instead of print(), crash-safe.
"""

import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path

# --- v5 path resolution ---
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import get_archive_dir, get_transcripts_dir

logger = logging.getLogger(__name__)


def search_transcripts(
    query: str,
    max_sessions: int = 10,
    max_excerpts_per_session: int = 5,
    context_lines: int = 3,
    full_mode: bool = False,
) -> list:
    """Search JSONL transcripts for query terms. Returns relevant excerpts."""
    results = []
    query_lower = query.lower()
    query_terms = [t.strip() for t in query_lower.split() if len(t.strip()) > 2]

    transcripts_dir = get_transcripts_dir()
    if not transcripts_dir.exists():
        return results

    # Search each transcript, newest first
    transcripts = sorted(transcripts_dir.glob("*.jsonl"), reverse=True)

    for transcript_path in transcripts[:max_sessions]:
        session_id = transcript_path.stem
        session_excerpts = []

        try:
            messages = []
            with open(transcript_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    msg = entry.get("message", entry)
                    role = msg.get("role", "")
                    content = msg.get("content", "")

                    # Extract text content
                    text = ""
                    if isinstance(content, list):
                        text_parts = []
                        for block in content:
                            if isinstance(block, dict):
                                if block.get("type") == "text":
                                    text_parts.append(block.get("text", ""))
                                elif block.get("type") == "tool_use":
                                    name = block.get("name", "")
                                    inp = block.get("input", {})
                                    fp = inp.get("file_path", "")
                                    cmd = inp.get("command", "")[:100]
                                    text_parts.append(f"[{name}: {fp or cmd}]")
                        text = " ".join(text_parts)
                    elif isinstance(content, str):
                        text = content

                    if text.strip() and role in ("user", "assistant"):
                        messages.append({
                            "role": role,
                            "text": text.strip(),
                        })

            # Search through messages for query matches
            for i, msg in enumerate(messages):
                text_lower = msg["text"].lower()
                match_score = sum(1 for term in query_terms if term in text_lower)

                if match_score == 0:
                    continue

                # Skip system-like messages
                if msg["text"].startswith("<command-"):
                    continue

                # Build excerpt with surrounding context
                excerpt_messages = []

                for j in range(max(0, i - context_lines), i):
                    m = messages[j]
                    if m["text"].startswith("<command-"):
                        continue
                    text = m["text"][:500] + ("..." if len(m["text"]) > 500 else "")
                    excerpt_messages.append(f"**{m['role'].title()}:** {text}")

                if full_mode:
                    text = msg["text"]
                else:
                    text = msg["text"][:800] + ("..." if len(msg["text"]) > 800 else "")
                excerpt_messages.append(f"**{msg['role'].title()}:** {text}")

                for j in range(i + 1, min(len(messages), i + context_lines + 1)):
                    m = messages[j]
                    if m["text"].startswith("<command-"):
                        continue
                    text = m["text"][:500] + ("..." if len(m["text"]) > 500 else "")
                    excerpt_messages.append(f"**{m['role'].title()}:** {text}")

                session_excerpts.append({
                    "score": match_score,
                    "excerpt": "\n\n".join(excerpt_messages),
                })

            # Deduplicate and take top N
            if session_excerpts:
                session_excerpts.sort(key=lambda x: -x["score"])
                seen_starts = set()
                unique_excerpts = []
                for exc in session_excerpts:
                    start = exc["excerpt"][:100]
                    if start not in seen_starts:
                        seen_starts.add(start)
                        unique_excerpts.append(exc)
                    if len(unique_excerpts) >= max_excerpts_per_session:
                        break

                # Get session title from archive
                archive_dir = get_archive_dir()
                archive_path = archive_dir / f"{session_id}.md"
                title = session_id
                if archive_path.exists():
                    arc_content = archive_path.read_text()
                    title_match = re.search(r"title:\s*(.+)", arc_content)
                    if title_match:
                        title = title_match.group(1).strip().strip("'\"")

                results.append({
                    "session_id": session_id,
                    "title": title,
                    "excerpts": [e["excerpt"] for e in unique_excerpts],
                    "total_matches": len(session_excerpts),
                })

        except Exception:
            continue

    return results


def list_topics() -> dict:
    """Extract key topics from all session summaries for quick reference."""
    topics = defaultdict(list)

    archive_dir = get_archive_dir()
    if not archive_dir.exists():
        return dict(topics)

    for summary_path in sorted(archive_dir.glob("*-summary.md"), reverse=True):
        session_id = summary_path.stem.replace("-summary", "")
        content = summary_path.read_text()

        in_user_msgs = False
        for line in content.split("\n"):
            if "## User Messages" in line:
                in_user_msgs = True
                continue
            if line.startswith("## ") and in_user_msgs:
                break
            if in_user_msgs and line.strip():
                msg = re.sub(r"^\d+\.\s*", "", line.strip())
                if len(msg) > 10:
                    topics[session_id].append(msg[:100])

    return dict(topics)


def main():
    parser = argparse.ArgumentParser(description="Session Retriever: search past sessions")
    parser.add_argument("--query", "-q", type=str, help="Search query")
    parser.add_argument("--sessions", "-n", type=int, default=10, help="Max sessions to search")
    parser.add_argument("--full", action="store_true", help="Show full excerpts (no truncation)")
    parser.add_argument("--list-topics", action="store_true", help="List topics from all sessions")
    parser.add_argument("--excerpts", type=int, default=5, help="Max excerpts per session")

    args = parser.parse_args()

    if args.list_topics:
        topics = list_topics()
        if topics:
            print("## Session Topics\n")
            for session_id, msgs in topics.items():
                print(f"### {session_id}")
                for msg in msgs[:5]:
                    print(f"- {msg}")
                print()
        else:
            print("No session summaries found.")
        return

    if not args.query:
        parser.print_help()
        return

    results = search_transcripts(
        args.query,
        max_sessions=args.sessions,
        max_excerpts_per_session=args.excerpts,
        full_mode=args.full,
    )

    if results:
        print(f"## Verbatim excerpts from {len(results)} session(s)\n")
        for r in results:
            print(f"### Session: {r['session_id']} - {r['title']}")
            print(f"_({r['total_matches']} keyword matches)_\n")
            for i, excerpt in enumerate(r["excerpts"], 1):
                print(f"#### Excerpt {i}")
                print(excerpt)
                print()
            print("---\n")
    else:
        print(f"No matches found for: \"{args.query}\"")


if __name__ == "__main__":
    main()
