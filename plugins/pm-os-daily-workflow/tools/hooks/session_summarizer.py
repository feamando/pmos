#!/usr/bin/env python3
"""Deterministic session summarizer: parses the JSONL transcript into a dense,
structured summary small enough to load at boot for full context.

No LLM calls. Extracts:
- Every user message (verbatim, trimmed to key sentences)
- Assistant responses (first ~200 chars of each text block)
- All tool calls with file paths and commands
- Decisions and plans (heuristic detection)
- Files created/modified/read

Target: ~2-5KB per session regardless of transcript size.

Usage:
    python3 session_summarizer.py <transcript.jsonl> [output.md]

v5.0: All paths from config, logging instead of print() for debug, crash-safe.
"""

import json
import logging
import re
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_decisions(text: str) -> list:
    """Heuristic: find sentences that look like decisions or conclusions."""
    decisions = []
    patterns = [
        r"(?:I'll|I will|Let me|Going to|Plan:|Decision:|We should|I recommend) .+?[.!]",
        r"(?:The (?:best|right|correct) (?:approach|way|method|option)) .+?[.!]",
        r"(?:Stick with|Switch to|Use|Keep|Drop|Remove|Add) .+?[.!]",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            d = match.group(0).strip()
            if 20 < len(d) < 200:
                decisions.append(d)
    return decisions


def summarize_transcript(jsonl_path: str, max_summary_kb: int = 15) -> str:
    """Parse JSONL transcript and produce a structured summary."""
    path = Path(jsonl_path)
    if not path.exists():
        return "_No transcript found._"

    user_messages = []
    assistant_snippets = []
    tool_calls = []
    files_touched = {"created": set(), "modified": set(), "read": set()}
    decisions = []

    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg = entry.get("message", entry)
                msg_type = entry.get("type", msg.get("type", ""))
                role = msg.get("role", "")
                content = msg.get("content", "")

                # User messages
                if msg_type == "user" and role == "user":
                    if isinstance(content, list):
                        texts = [
                            b.get("text", "")
                            for b in content
                            if isinstance(b, dict) and b.get("type") == "text"
                        ]
                        text_content = " ".join(texts)
                    elif isinstance(content, str):
                        text_content = content
                    else:
                        text_content = ""

                    if text_content.strip():
                        # Skip tool_result entries
                        if any(isinstance(b, dict) and b.get("type") == "tool_result"
                               for b in (content if isinstance(content, list) else [])):
                            continue
                        msg_text = text_content.strip()
                        # Skip system/skill expansions
                        if msg_text.startswith("<command-"):
                            continue
                        if msg_text.startswith("# ") and len(msg_text) > 200:
                            continue
                        if msg_text.startswith("---\n") and "type:" in msg_text[:100]:
                            continue
                        if len(msg_text) > 500:
                            msg_text = msg_text[:500] + "..."
                        if len(msg_text) > 5:
                            user_messages.append(msg_text)

                # Assistant messages
                elif msg_type == "assistant" and role == "assistant":
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict):
                                if block.get("type") == "text":
                                    text = block.get("text", "")
                                    if text.strip():
                                        snippet = text.strip()[:300]
                                        if len(text.strip()) > 300:
                                            snippet += "..."
                                        assistant_snippets.append(snippet)
                                        decisions.extend(extract_decisions(text))
                                elif block.get("type") == "tool_use":
                                    tool_name = block.get("name", "?")
                                    tool_input = block.get("input", {})
                                    fp = tool_input.get("file_path", "")
                                    cmd = tool_input.get("command", "")
                                    pattern = tool_input.get("pattern", "")
                                    desc = tool_input.get("description", "")

                                    summary = ""
                                    if tool_name == "Read":
                                        summary = fp[-60:] if fp else ""
                                        if fp:
                                            files_touched["read"].add(fp)
                                    elif tool_name == "Edit":
                                        summary = fp[-60:] if fp else ""
                                        if fp:
                                            files_touched["modified"].add(fp)
                                    elif tool_name == "Write":
                                        summary = fp[-60:] if fp else ""
                                        if fp:
                                            files_touched["created"].add(fp)
                                    elif tool_name == "Bash":
                                        summary = cmd[:80].replace("\n", " ")
                                    elif tool_name in ("Glob", "Grep"):
                                        summary = pattern[:60] if pattern else ""
                                    elif tool_name == "Agent":
                                        summary = desc[:60] if desc else ""
                                    else:
                                        summary = str(tool_input)[:60]

                                    tool_calls.append(f"{tool_name}: {summary}")
                    elif isinstance(content, str) and content.strip():
                        snippet = content.strip()[:300]
                        if len(content.strip()) > 300:
                            snippet += "..."
                        assistant_snippets.append(snippet)
                        decisions.extend(extract_decisions(content))

    except Exception as e:
        return f"_Error parsing transcript: {e}_"

    # --- Build summary ---
    parts = []

    if user_messages:
        parts.append("## User Messages")
        for i, msg in enumerate(user_messages, 1):
            parts.append(f"{i}. {msg}")
        parts.append("")

    if assistant_snippets:
        parts.append("## Key Assistant Responses")
        seen = set()
        count = 0
        for snippet in assistant_snippets:
            key = snippet[:50]
            if key not in seen and count < 20:
                seen.add(key)
                parts.append(f"- {snippet}")
                count += 1
        parts.append("")

    if decisions:
        unique_decisions = list(dict.fromkeys(decisions))[:10]
        parts.append("## Decisions & Plans")
        for d in unique_decisions:
            parts.append(f"- {d}")
        parts.append("")

    all_files = files_touched["created"] | files_touched["modified"]
    if all_files:
        parts.append("## Files Changed")
        for f in sorted(files_touched["created"]):
            parts.append(f"- [NEW] `{f}`")
        for f in sorted(files_touched["modified"]):
            parts.append(f"- [MOD] `{f}`")
        parts.append("")

    summary = "\n".join(parts)

    # Enforce size limit
    max_bytes = max_summary_kb * 1024
    if len(summary.encode()) > max_bytes:
        summary = summary[:max_bytes]
        summary = summary.rsplit("\n", 1)[0] + "\n\n_[Summary truncated to fit size limit]_"

    return summary


def main():
    if len(sys.argv) < 2:
        print("Usage: session_summarizer.py <transcript.jsonl> [output.md]")
        sys.exit(1)

    jsonl_path = sys.argv[1]
    summary = summarize_transcript(jsonl_path)

    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
        Path(output_path).write_text(summary)
        logger.info("Summary written to %s (%d bytes)", output_path, len(summary))
    else:
        print(summary)


if __name__ == "__main__":
    main()
