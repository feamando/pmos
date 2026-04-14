#!/usr/bin/env python3
"""
Daily Context Updater (v5.0)

Fetches data from multiple context sources in parallel, manages state,
formats raw output for synthesis by Claude Code.

Port of v4.x daily_context_updater.py (~1375 lines -> ~600 lines).

Key v5.0 changes:
- ZERO hardcoded values: all search terms, names, emails from config
- connector_bridge for auth (3-tier: connector -> .env -> error)
- Modular sources via context_sources.py
- Proper logging (no print() for debug)

Usage:
    python daily_context_updater.py              # Fetch & output recent data
    python daily_context_updater.py --dry-run    # List items without reading content
    python daily_context_updater.py --force      # Ignore last-run, pull last N days
    python daily_context_updater.py --output FILE  # Write to file instead of stdout
    python daily_context_updater.py --quick      # Docs only, skip Slack and Gmail
"""

import argparse
import base64
import io
import json
import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- Sibling imports (v5 pattern) ---
try:
    from daily_context.context_sources import (
        fetch_all_sources,
        get_enabled_sources,
        GoogleDocsContextSource,
        GmailContextSource,
        SlackContextSource,
    )
except ImportError:
    from context_sources import (
        fetch_all_sources,
        get_enabled_sources,
        GoogleDocsContextSource,
        GmailContextSource,
        SlackContextSource,
    )

try:
    from pm_os_base.tools.core.config_loader import get_config, get_root_path
except ImportError:
    try:
        from config_loader import get_config, get_root_path
    except ImportError:
        get_config = None
        get_root_path = None

try:
    from pm_os_base.tools.core.connector_bridge import get_auth
except ImportError:
    try:
        from connector_bridge import get_auth
    except ImportError:
        get_auth = None

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        from path_resolver import get_paths
    except ImportError:
        get_paths = None

logger = logging.getLogger(__name__)

# --- Constants ---
DEFAULT_LOOKBACK_DAYS = 10
DEFAULT_MAX_DOC_CHARS = 6000
DEFAULT_MAX_EMAIL_CHARS = 2500
SLACK_MAX_CHARS = 1000
MAX_WORKERS_CONTENT = 5
MAX_WORKERS_SOURCES = 3


@contextmanager
def _timer(label: str):
    """Context manager that logs elapsed time for a phase."""
    start = time.monotonic()
    yield
    elapsed = time.monotonic() - start
    logger.info("[context-update] %s: %.1fs", label, elapsed)


# =============================================================================
# State Management
# =============================================================================


def _get_state_file() -> str:
    """Get path to state file."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "state.json")


def load_state() -> Dict[str, Any]:
    """Read last run timestamp and processed files from state file."""
    state = {"last_run": None, "processed_files": {}}
    state_file = _get_state_file()

    if not os.path.exists(state_file):
        return state

    try:
        with open(state_file, "r") as f:
            loaded = json.load(f)
            if "last_run" in loaded and loaded["last_run"]:
                state["last_run"] = datetime.fromisoformat(
                    loaded["last_run"].replace("Z", "+00:00")
                )
            if "processed_files" in loaded:
                state["processed_files"] = loaded["processed_files"]
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("Could not load state from %s: %s", state_file, e)
        return {"last_run": None, "processed_files": {}}

    return state


def save_state(state: Dict[str, Any]):
    """Update state file with current timestamp and processed files."""
    state_file = _get_state_file()
    serializable = {
        "last_run": state["last_run"].isoformat() if state["last_run"] else None,
        "processed_files": state["processed_files"],
    }
    with open(state_file, "w") as f:
        json.dump(serializable, f, indent=2)


# =============================================================================
# FPF Reasoning State (optional)
# =============================================================================


def get_reasoning_state(config: Any) -> Dict[str, Any]:
    """Gather FPF reasoning state from Brain/Reasoning/ directories.

    All paths resolved from config, no hardcoded values.

    Args:
        config: ConfigLoader instance.

    Returns:
        Dict with active_cycles, drrs, expiring_evidence, open_hypotheses.
    """
    state = {
        "active_cycles": [],
        "drrs": [],
        "expiring_evidence": [],
        "open_hypotheses": [],
    }

    try:
        if get_paths is not None:
            paths = get_paths()
            reasoning_dir = paths.brain / "Reasoning"
        elif get_root_path is not None:
            reasoning_dir = get_root_path() / "user" / "brain" / "Reasoning"
        else:
            return state
    except Exception:
        return state

    if not reasoning_dir.exists():
        return state

    today = datetime.now()
    expiry_window = timedelta(days=7)

    # Active cycles
    active_dir = reasoning_dir / "Active"
    if active_dir.exists():
        for f in active_dir.iterdir():
            if f.suffix == ".md":
                state["active_cycles"].append({"file": f.name, "path": str(f)})

    # DRRs
    decisions_dir = reasoning_dir / "Decisions"
    if decisions_dir.exists():
        for f in decisions_dir.iterdir():
            if f.suffix == ".md" and f.name.startswith("drr-"):
                state["drrs"].append({"file": f.name, "path": str(f)})

    # Expiring evidence
    evidence_dir = reasoning_dir / "Evidence"
    if evidence_dir.exists():
        for f in evidence_dir.iterdir():
            if f.suffix == ".md":
                try:
                    content = f.read_text(encoding="utf-8")
                    match = re.search(
                        r"[Ee]xpir[ey]s?:\s*(\d{4}-\d{2}-\d{2})", content
                    )
                    if match:
                        expiry_date = datetime.strptime(match.group(1), "%Y-%m-%d")
                        if expiry_date <= today + expiry_window:
                            state["expiring_evidence"].append({
                                "file": f.name,
                                "path": str(f),
                                "expiry": match.group(1),
                            })
                except Exception:
                    pass

    # Open hypotheses (L0/L1, not L2 or Invalid)
    hypotheses_dir = reasoning_dir / "Hypotheses"
    if hypotheses_dir.exists():
        for f in hypotheses_dir.iterdir():
            if f.suffix == ".md":
                try:
                    content = f.read_text(encoding="utf-8")
                    if "L2" not in content and "Invalid" not in content:
                        state["open_hypotheses"].append({"file": f.name, "path": str(f)})
                except Exception:
                    pass

    return state


def format_reasoning_summary(reasoning_state: Dict[str, Any]) -> str:
    """Format reasoning state for inclusion in context output."""
    lines = ["## FPF REASONING STATE", ""]

    has_data = any([
        reasoning_state.get("active_cycles"),
        reasoning_state.get("drrs"),
        reasoning_state.get("expiring_evidence"),
        reasoning_state.get("open_hypotheses"),
    ])

    if not has_data:
        lines.append("No active reasoning state found.")
        lines.append("")
        return "\n".join(lines)

    if reasoning_state.get("active_cycles"):
        count = len(reasoning_state["active_cycles"])
        lines.append(f"### Active Cycles ({count})")
        for cycle in reasoning_state["active_cycles"]:
            lines.append(f"- {cycle['file']}")
        lines.append("")

    if reasoning_state.get("drrs"):
        count = len(reasoning_state["drrs"])
        lines.append(f"### Design Rationale Records ({count})")
        for drr in reasoning_state["drrs"]:
            lines.append(f"- {drr['file']}")
        lines.append("")

    if reasoning_state.get("expiring_evidence"):
        count = len(reasoning_state["expiring_evidence"])
        lines.append(f"### Expiring Evidence ({count} items within 7 days)")
        for ev in reasoning_state["expiring_evidence"]:
            lines.append(f"- {ev['file']} (expires: {ev['expiry']})")
        lines.append("")

    if reasoning_state.get("open_hypotheses"):
        count = len(reasoning_state["open_hypotheses"])
        lines.append(f"### Open Hypotheses ({count} L0/L1 claims)")
        for hyp in reasoning_state["open_hypotheses"]:
            lines.append(f"- {hyp['file']}")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# Content Reading
# =============================================================================


def read_doc_content(
    doc: Dict[str, Any],
    max_chars: int = DEFAULT_MAX_DOC_CHARS,
) -> str:
    """Read content of a Google Doc or Sheet via API, with smart truncation.

    Args:
        doc: Doc metadata dict with 'id', 'mimeType', etc.
        max_chars: Maximum characters to return.

    Returns:
        Document text content, possibly truncated.
    """
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
    except ImportError:
        return "[Google API client not installed]"

    try:
        from pm_os_base.tools.core.config_loader import get_google_paths
    except ImportError:
        try:
            from config_loader import get_google_paths
        except ImportError:
            return "[Cannot resolve Google credential paths]"

    google_paths = get_google_paths()
    token_file = google_paths.get("token")
    if not token_file or not os.path.exists(token_file):
        return "[Google token not found]"

    try:
        creds = Credentials.from_authorized_user_file(token_file)
        service = build("drive", "v3", credentials=creds)
    except Exception as e:
        return f"[Error loading credentials: {e}]"

    try:
        mime_type = doc.get("mimeType", "")
        if mime_type == "application/vnd.google-apps.spreadsheet":
            export_mime = "text/csv"
        else:
            export_mime = "text/plain"

        request = service.files().export_media(fileId=doc["id"], mimeType=export_mime)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        content = file_content.getvalue().decode("utf-8")

        # Smart truncation: keep start (60%) and end (40%)
        if len(content) > max_chars:
            keep_start = int(max_chars * 0.6)
            keep_end = int(max_chars * 0.4)
            marker = f"\n\n... [TRUNCATED: {len(content) - max_chars} chars omitted] ...\n\n"
            return content[:keep_start] + marker + content[-keep_end:]

        return content

    except Exception as e:
        return f"[Error reading document: {e}]"


def read_email_content(
    message: Dict[str, Any],
    max_chars: int = DEFAULT_MAX_EMAIL_CHARS,
) -> str:
    """Extract text content from email payload, with smart truncation.

    Args:
        message: Full Gmail message dict.
        max_chars: Maximum characters to return.

    Returns:
        Email body text, possibly truncated.
    """
    try:
        payload = message.get("payload", {})
        parts = payload.get("parts", [])
        body_data = None

        if not parts:
            body_data = payload.get("body", {}).get("data")

        if not body_data:
            for part in parts:
                if part.get("mimeType") == "text/plain":
                    body_data = part.get("body", {}).get("data")
                    break

        if not body_data and parts:
            body_data = parts[0].get("body", {}).get("data")

        if body_data:
            content = base64.urlsafe_b64decode(body_data).decode("utf-8")
            if len(content) > max_chars:
                keep_start = int(max_chars * 0.6)
                keep_end = int(max_chars * 0.4)
                marker = f"\n\n... [TRUNCATED: {len(content) - max_chars} chars omitted] ...\n\n"
                return content[:keep_start] + marker + content[-keep_end:]
            return content
        else:
            return "[No readable text content found]"

    except Exception as e:
        return f"[Error reading email: {e}]"


# =============================================================================
# Output Formatting
# =============================================================================


def format_output(
    source_results: Dict[str, Dict[str, Any]],
    doc_contents: Dict[str, str],
    email_contents: Dict[str, str],
    reasoning_state: Optional[Dict[str, Any]] = None,
) -> str:
    """Format all source data for synthesis.

    Args:
        source_results: Output from fetch_all_sources().
        doc_contents: Map of doc ID -> text content.
        email_contents: Map of email ID -> text content.
        reasoning_state: Optional FPF reasoning state.

    Returns:
        Formatted string ready for synthesis.
    """
    docs = source_results.get("google", {}).get("items", [])
    emails = source_results.get("gmail", {}).get("items", [])
    slack_msgs = source_results.get("slack", {}).get("items", [])
    jira_items = source_results.get("jira", {}).get("items", [])
    github_items = source_results.get("github", {}).get("items", [])

    lines = []
    lines.append("=" * 60)
    lines.append("DAILY CONTEXT UPDATE - RAW DATA")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Documents: {len(docs)}")
    lines.append(f"Emails: {len(emails)}")
    lines.append(f"Slack messages: {len(slack_msgs)}")
    lines.append(f"Jira issues: {len(jira_items)}")
    lines.append(f"GitHub notifications: {len(github_items)}")

    if reasoning_state:
        active = len(reasoning_state.get("active_cycles", []))
        drrs = len(reasoning_state.get("drrs", []))
        expiring = len(reasoning_state.get("expiring_evidence", []))
        lines.append(
            f"FPF State: {active} active cycles | {drrs} DRRs | {expiring} expiring evidence"
        )

    lines.append("=" * 60)
    lines.append("")

    # --- Document Index ---
    lines.append("## DOCUMENT INDEX")
    lines.append("")
    for doc in docs:
        modified = doc.get("modifiedTime", "Unknown")[:10]
        owners = doc.get("owners", [{}])
        owner_name = owners[0].get("displayName", "Unknown") if owners else "Unknown"
        lines.append(
            f"- [DOC] [{doc.get('name', 'Untitled')}]({doc.get('webViewLink', '')}) "
            f"| Modified: {modified} | Owner: {owner_name}"
        )
    lines.append("")

    # --- Email Index ---
    lines.append("## EMAIL INDEX")
    lines.append("")
    for email in emails:
        headers = email.get("payload", {}).get("headers", [])
        subject = next(
            (h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)"
        )
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
        date_ts = int(email.get("internalDate", 0)) / 1000
        date_str = datetime.fromtimestamp(date_ts).strftime("%Y-%m-%d")
        lines.append(f"- [EMAIL] {subject} | From: {sender} | Date: {date_str}")
    lines.append("")

    # --- Slack Index ---
    lines.append("## SLACK INDEX")
    lines.append("")
    for msg in slack_msgs:
        ts = float(msg.get("ts", 0))
        date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        user = msg.get("user_name", msg.get("user", "Unknown"))
        channel = msg.get("channel_name", "Unknown")
        preview = msg.get("text", "").replace("\n", " ")[:50]
        lines.append(f"- [SLACK] {channel} | {user}: {preview}...")
    lines.append("")

    # --- Jira Index ---
    if jira_items:
        lines.append("## JIRA INDEX")
        lines.append("")
        for issue in jira_items:
            lines.append(
                f"- [{issue['key']}] {issue['summary']} "
                f"| {issue['status']} | {issue['assignee']}"
            )
        lines.append("")

    # --- GitHub Index ---
    if github_items:
        lines.append("## GITHUB INDEX")
        lines.append("")
        for notif in github_items:
            lines.append(
                f"- [{notif['type']}] {notif['title']} "
                f"| {notif['repo']} | {notif['reason']}"
            )
        lines.append("")

    # --- Document Contents ---
    lines.append("=" * 60)
    lines.append("## DOCUMENT CONTENTS")
    lines.append("=" * 60)
    lines.append("")
    for doc in docs:
        doc_id = doc.get("id", "")
        lines.append("-" * 40)
        lines.append(f"### DOC: {doc.get('name', 'Untitled')}")
        lines.append(f"ID: {doc_id}")
        lines.append(f"Link: {doc.get('webViewLink', 'N/A')}")
        lines.append("-" * 40)
        lines.append("")
        lines.append(doc_contents.get(doc_id, "[Content not available]"))
        lines.append("")
        lines.append("")

    # --- Email Contents ---
    lines.append("=" * 60)
    lines.append("## EMAIL CONTENTS")
    lines.append("=" * 60)
    lines.append("")
    for email in emails:
        email_id = email.get("id", "")
        headers = email.get("payload", {}).get("headers", [])
        subject = next(
            (h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)"
        )
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
        lines.append("-" * 40)
        lines.append(f"### EMAIL: {subject}")
        lines.append(f"ID: {email_id}")
        lines.append(f"From: {sender}")
        lines.append("-" * 40)
        lines.append("")
        lines.append(email_contents.get(email_id, "[Content not available]"))
        lines.append("")
        lines.append("")

    # --- Slack Contents ---
    lines.append("=" * 60)
    lines.append("## SLACK CONTENTS")
    lines.append("=" * 60)
    lines.append("")
    for msg in slack_msgs:
        ts = float(msg.get("ts", 0))
        date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        user = msg.get("user_name", msg.get("user", "Unknown"))
        channel = msg.get("channel_name", "Unknown")
        text = msg.get("text", "")
        lines.append("-" * 40)
        lines.append(f"### SLACK: {channel} - {date_str}")
        lines.append(f"User: {user}")
        lines.append("-" * 40)
        lines.append("")
        lines.append(text)
        lines.append("")
        lines.append("")

    # --- FPF Reasoning State ---
    if reasoning_state:
        lines.append("=" * 60)
        lines.append(format_reasoning_summary(reasoning_state))

    lines.append("=" * 60)
    lines.append("END OF RAW DATA")
    lines.append("=" * 60)
    lines.append("")

    # Cutoff date (6 months)
    cutoff_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")

    lines.append("Instructions for Claude Code:")
    lines.append(
        "Synthesize the above into a structured context file."
    )
    lines.append(
        f"IMPORTANT: STRICTLY IGNORE any content dated before {cutoff_date} (6 months ago)."
    )
    lines.append(
        "Extract: Key decisions, action items, blockers, metrics, important dates."
    )
    lines.append("Format: Direct bullets, structured sections.")
    if reasoning_state:
        lines.append(
            "Include: FPF reasoning state summary (active cycles, expiring evidence, pending decisions)"
        )

    return "\n".join(lines)


# =============================================================================
# Main Orchestrator
# =============================================================================


def main():
    """Main entry point for daily context updater."""
    parser = argparse.ArgumentParser(
        description="Fetch recent context from all sources for synthesis"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="List items without reading content"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Ignore last-run timestamp, fetch last N days",
    )
    parser.add_argument(
        "--output", type=str, help="Write output to file instead of stdout"
    )
    parser.add_argument(
        "--days", type=int, default=DEFAULT_LOOKBACK_DAYS,
        help=f"Days to look back (default: {DEFAULT_LOOKBACK_DAYS})",
    )
    parser.add_argument(
        "--max-doc-chars", type=int, default=DEFAULT_MAX_DOC_CHARS,
        help=f"Max characters per document (default: {DEFAULT_MAX_DOC_CHARS})",
    )
    parser.add_argument(
        "--reasoning", action="store_true",
        help="Include FPF reasoning state",
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Quick mode: Docs only, skip Slack and Gmail",
    )
    parser.add_argument(
        "--no-slack", action="store_true", help="Skip Slack messages"
    )
    parser.add_argument(
        "--no-gmail", action="store_true", help="Skip Gmail"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging"
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    # Suppress noisy Google discovery cache warnings
    logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)

    # Quick mode
    if args.quick:
        args.no_slack = True
        args.no_gmail = True

    # Load config
    if get_config is None:
        logger.error("config_loader not available")
        sys.exit(1)

    config = get_config()

    # Load state
    state = load_state()
    last_run = state["last_run"]
    processed_files = state["processed_files"]

    # Determine time window
    if args.force:
        since = datetime.now(timezone.utc) - timedelta(days=args.days)
        processed_files = {}
        logger.info(
            "Force mode: fetching last %s days, reprocessing all", args.days
        )
    elif last_run is None:
        since = datetime.now(timezone.utc) - timedelta(days=args.days)
        logger.info("First run: fetching last %s days", args.days)
    else:
        since = last_run
        logger.info("Fetching since: %s", since.isoformat())

    # Fetch from all sources in parallel
    total_start = time.monotonic()

    with _timer(f"All source fetching"):
        source_results = fetch_all_sources(
            config, since, processed_files, max_workers=MAX_WORKERS_SOURCES,
        )

    # Remove skipped sources from results
    if args.no_slack and "slack" in source_results:
        source_results["slack"] = {"items": [], "source": "slack"}
        logger.info("Skipping Slack (--no-slack or --quick)")
    if args.no_gmail and "gmail" in source_results:
        source_results["gmail"] = {"items": [], "source": "gmail"}
        logger.info("Skipping Gmail (--no-gmail or --quick)")

    # Count total items
    total_items = sum(
        len(data.get("items", []))
        for data in source_results.values()
    )

    if total_items == 0:
        logger.info("No new items found across any source")
        state["last_run"] = datetime.now(timezone.utc)
        save_state(state)
        return

    logger.info("Found %s total items across all sources", total_items)

    # Dry run
    if args.dry_run:
        print("\n--- DRY RUN: Items that would be processed ---\n")
        for source_name, data in source_results.items():
            items = data.get("items", [])
            if items:
                print(f"{source_name.upper()} ({len(items)}):")
                for item in items[:10]:
                    if "name" in item:
                        print(f"  - {item['name']}")
                    elif "summary" in item:
                        print(f"  - [{item.get('key', '')}] {item['summary']}")
                    elif "title" in item:
                        print(f"  - {item['title']}")
                    elif "payload" in item:
                        headers = item.get("payload", {}).get("headers", [])
                        subject = next(
                            (h["value"] for h in headers if h["name"] == "Subject"),
                            "(No Subject)"
                        )
                        print(f"  - {subject}")
                    elif "text" in item:
                        ch = item.get("channel_name", "?")
                        print(f"  - [{ch}] {item['text'][:40]}...")
                print()
        return

    # --- Read document and email contents ---
    docs = source_results.get("google", {}).get("items", [])
    emails = source_results.get("gmail", {}).get("items", [])

    doc_contents = {}
    if docs:
        with _timer(f"Doc content reads ({len(docs)} docs)"):
            with ThreadPoolExecutor(max_workers=MAX_WORKERS_CONTENT) as executor:
                futures = {
                    executor.submit(read_doc_content, doc, args.max_doc_chars): doc
                    for doc in docs
                }
                for future in as_completed(futures):
                    doc = futures[future]
                    doc_contents[doc["id"]] = future.result()
                    processed_files[doc["id"]] = doc.get("modifiedTime")

    email_contents = {}
    for email in emails:
        email_contents[email["id"]] = read_email_content(email)
        processed_files[email["id"]] = email.get("internalDate")

    # Update processed state for Slack
    for msg in source_results.get("slack", {}).get("items", []):
        processed_files[msg.get("unique_id", "")] = msg.get("ts")

    # Update processed state for Jira
    for issue in source_results.get("jira", {}).get("items", []):
        processed_files[issue.get("key", "")] = issue.get("updated")

    # Update processed state for GitHub
    for notif in source_results.get("github", {}).get("items", []):
        processed_files[notif.get("id", "")] = notif.get("updated_at")

    # Reasoning state
    reasoning_state = None
    if args.reasoning:
        logger.info("Gathering FPF reasoning state...")
        reasoning_state = get_reasoning_state(config)

    # Format output
    output = format_output(source_results, doc_contents, email_contents, reasoning_state)

    # Write output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        logger.info("Output written to: %s", args.output)
    else:
        sys.stdout.buffer.write(output.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")

    # Update state
    state["last_run"] = datetime.now(timezone.utc)
    state["processed_files"] = processed_files
    save_state(state)

    total_elapsed = time.monotonic() - total_start
    logger.info("[context-update] Total: %.1fs", total_elapsed)
    logger.info("State updated. Ready for synthesis.")


if __name__ == "__main__":
    main()
