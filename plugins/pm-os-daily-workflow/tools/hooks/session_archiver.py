#!/usr/bin/env python3
"""Enhanced session archiver for Stop hook.
Compiles ALL session data into a rich archive:
- Breadcrumbs (every tool call)
- File tracker (created/modified/read)
- Compaction summaries (rich conversation context)
- User prompts (every message the user typed)
- JSONL transcript link (verbatim full transcript)

Hook registration:
  event: Stop
  matcher: (always fires)

Dependencies: session_transcript_sync.py, session_summarizer.py (optional).
PyYAML optional (has fallback).

v5.0: All paths from config, logging instead of print(), crash-safe.
"""

import json
import logging
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# --- v5 path resolution ---
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import (
    get_active_session_path,
    get_archive_dir,
    get_compaction_log_path,
    get_file_tracker_path,
    get_prompts_log_path,
    get_session_link_path,
    get_sync_state_path,
    get_transcripts_dir,
    find_project_dir,
)

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)


def parse_frontmatter(content: str):
    """Parse YAML frontmatter from markdown content."""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            if yaml:
                try:
                    frontmatter = yaml.safe_load(parts[1])
                    return frontmatter or {}, parts[2]
                except Exception:
                    pass
            # Fallback: basic key-value parsing
            fm = {}
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip().strip("'\"")
            return fm, parts[2]
    return {}, content


def create_frontmatter(data: dict) -> str:
    """Create YAML frontmatter string."""
    if yaml:
        return f"---\n{yaml.dump(data, default_flow_style=False)}---"
    # Fallback
    lines = ["---"]
    for k, v in data.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - '{item}'")
        else:
            lines.append(f"{k}: '{v}'")
    lines.append("---")
    return "\n".join(lines)


def finalize_transcript(session_id: str) -> str:
    """Do a final incremental sync, then ensure transcript has correct name.
    Returns the path to the transcript, or empty string if not found."""
    transcripts_dir = get_transcripts_dir()
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    # Run one final incremental sync
    import subprocess
    sync_script = Path(__file__).parent / "session_transcript_sync.py"
    if sync_script.exists():
        try:
            subprocess.run(
                [sys.executable, str(sync_script)],
                capture_output=True, timeout=10,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass

    # Check if transcript exists under session ID
    dest = transcripts_dir / f"{session_id}.jsonl"
    if dest.exists():
        return str(dest)

    # Check if synced under 'current' and rename
    current_dest = transcripts_dir / "current.jsonl"
    if current_dest.exists():
        current_dest.rename(dest)
        return str(dest)

    # Fallback: copy from Claude projects dir using session link
    project_dir = find_project_dir()
    session_link = get_session_link_path()
    if project_dir and session_link.exists():
        try:
            link_data = json.loads(session_link.read_text())
            claude_id = link_data.get("claude_session_id", "")
            if claude_id:
                src = project_dir / f"{claude_id}.jsonl"
                if src.exists():
                    shutil.copy2(str(src), str(dest))
                    return str(dest)
        except (json.JSONDecodeError, OSError):
            pass

    # Last resort: most recently modified .jsonl in project dir
    if project_dir:
        jsonl_files = sorted(
            project_dir.glob("*.jsonl"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if jsonl_files:
            shutil.copy2(str(jsonl_files[0]), str(dest))
            return str(dest)

    return ""


def main():
    try:
        active_session = get_active_session_path()
        if not active_session.exists():
            return

        content = active_session.read_text()
        frontmatter, body = parse_frontmatter(content)

        file_tracker_path = get_file_tracker_path()
        compaction_log = get_compaction_log_path()
        prompts_log = get_prompts_log_path()
        session_link = get_session_link_path()
        sync_state = get_sync_state_path()
        archive_dir = get_archive_dir()

        # --- Enrich frontmatter from file tracker ---
        if file_tracker_path.exists():
            try:
                tracker = json.loads(file_tracker_path.read_text())
                frontmatter["files_created"] = tracker.get("created", [])
                frontmatter["files_modified"] = tracker.get("modified", [])
                frontmatter["files_explored"] = tracker.get("read", [])
            except (json.JSONDecodeError, OSError):
                pass

        # --- Extract breadcrumbs from the body ---
        breadcrumbs = re.findall(r"^- `\d{2}:\d{2}:\d{2}` .+$", body, re.MULTILINE)

        # --- Load compaction summaries (the rich context) ---
        compaction_content = ""
        if compaction_log.exists():
            compaction_content = compaction_log.read_text().strip()

        # --- Load user prompts ---
        prompts_content = ""
        if prompts_log.exists():
            prompts_content = prompts_log.read_text().strip()

        # --- Compute duration ---
        started = frontmatter.get("started", datetime.now().isoformat())
        try:
            start_dt = datetime.fromisoformat(str(started))
        except (ValueError, TypeError):
            start_dt = datetime.now()
        duration = int((datetime.now() - start_dt).total_seconds() / 60)

        frontmatter["status"] = "archived"
        frontmatter["archived_at"] = datetime.now().isoformat()
        frontmatter["duration_minutes"] = duration

        title = frontmatter.get("title", "Untitled Session")

        # Determine session_id
        session_id = frontmatter.get("session_id")
        if not session_id:
            date_str = datetime.now().strftime("%Y-%m-%d")
            existing = list(archive_dir.glob(f"{date_str}-*.md")) if archive_dir.exists() else []
            seq = 1
            for f in existing:
                m = re.search(r"-(\d+)\.md$", f.name)
                if m:
                    seq = max(seq, int(m.group(1)) + 1)
            session_id = f"{date_str}-{seq:03d}"
            frontmatter["session_id"] = session_id

        # --- Final transcript sync + copy ---
        transcript_path = finalize_transcript(session_id)
        if transcript_path:
            frontmatter["transcript"] = transcript_path

        # --- Generate transcript summary (optional) ---
        transcript_summary = ""
        if transcript_path:
            try:
                from session_summarizer import summarize_transcript
                transcript_summary = summarize_transcript(transcript_path)
                # Write standalone summary file
                archive_dir.mkdir(parents=True, exist_ok=True)
                summary_path = archive_dir / f"{session_id}-summary.md"
                summary_path.write_text(f"# Session Summary: {title}\n\n{transcript_summary}")
                frontmatter["summary_path"] = str(summary_path)
            except Exception as e:
                transcript_summary = f"_Summary generation failed: {e}_"

        # --- Build archive body ---
        files_created = frontmatter.get("files_created", [])
        files_modified = frontmatter.get("files_modified", [])
        files_explored = frontmatter.get("files_explored", [])

        created_md = "\n".join(f"- `{f}`" for f in files_created) if files_created else "_None_"
        modified_md = "\n".join(f"- `{f}`" for f in files_modified) if files_modified else "_None_"
        explored_md = "\n".join(f"- `{f}`" for f in files_explored[:50]) if files_explored else "_None_"
        if len(files_explored) > 50:
            explored_md += f"\n- _...and {len(files_explored) - 50} more_"

        breadcrumb_md = "\n".join(breadcrumbs) if breadcrumbs else "_No breadcrumbs recorded_"

        transcript_md = ""
        if transcript_path:
            transcript_md = f"\n> Full verbatim transcript: `{transcript_path}`\n"
        else:
            transcript_md = "\n> _Transcript not found, check `~/.claude/projects/` manually_\n"

        new_body = f"""
# Session: {title}
{transcript_md}
## Full Session Summary
{transcript_summary if transcript_summary else "_No transcript summary generated._"}

## Compaction Context
{compaction_content if compaction_content else "_No compaction summaries captured (short session)._"}

## User Messages (from prompt hook)
{prompts_content if prompts_content else "_No user prompts captured (short session or hook not yet active)._"}

## Activity Log
{breadcrumb_md}

## Files Touched
### Created
{created_md}

### Modified
{modified_md}

### Explored
{explored_md}
"""

        # Preserve manually-written sections from original body
        for section in ["## Decisions Made", "## Open Questions", "## Context for Next Session"]:
            match = re.search(
                rf"({re.escape(section)}\n.+?)(?=\n## |\Z)",
                body,
                re.DOTALL,
            )
            if match:
                section_content = match.group(1).strip()
                if "<!--" not in section_content or len(section_content) > 100:
                    new_body += f"\n{section_content}\n"

        # --- Write archive file ---
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"{session_id}.md"
        archive_content = create_frontmatter(frontmatter) + new_body
        archive_path.write_text(archive_content)

        # --- Update index ---
        index_file = get_archive_dir().parent / "Index.md"
        transcript_note = " +transcript" if transcript_path else ""
        index_entry = f"""
### {session_id}
- **Title:** {title}
- **Date:** {str(started)[:10]}
- **Duration:** {duration} minutes
- **Files:** {len(files_created)} created, {len(files_modified)} modified, {len(files_explored)} read
- **Data:** compaction summaries + prompts + breadcrumbs{transcript_note}
"""

        if index_file.exists():
            idx = index_file.read_text()
            if "## Recent Sessions" in idx:
                parts = idx.split("## Recent Sessions", 1)
                idx = parts[0] + "## Recent Sessions" + index_entry + parts[1]
            else:
                idx += f"\n## Recent Sessions{index_entry}"
            index_file.write_text(idx)
        else:
            index_file.write_text(f"# Session Index\n\n## Recent Sessions\n{index_entry}")

        # --- Cleanup active files ---
        active_session.unlink(missing_ok=True)
        file_tracker_path.unlink(missing_ok=True)
        compaction_log.unlink(missing_ok=True)
        prompts_log.unlink(missing_ok=True)
        session_link.unlink(missing_ok=True)
        sync_state.unlink(missing_ok=True)

        logger.info("Archived session: %s (duration: %d min)", session_id, duration)
        if compaction_content:
            logger.info("Rich context: %d chars from compaction summaries", len(compaction_content))
        if transcript_path:
            logger.info("Transcript: copied to %s", transcript_path)

    except Exception as e:
        logger.warning("session_archiver error: %s", e)


if __name__ == "__main__":
    main()
