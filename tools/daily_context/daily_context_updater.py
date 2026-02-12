#!/usr/bin/env python3
"""
Daily Context Updater

Fetches recently modified Google Docs and received Gmails (authored by or shared with user)
and outputs raw content for synthesis by Claude Code. Also supports uploading context files
back to Google Drive.

Usage:
    python daily_context_updater.py              # Fetch & output recent docs/emails
    python daily_context_updater.py --dry-run    # List items without reading content
    python daily_context_updater.py --force      # Ignore last-run, pull last 7 days
    python daily_context_updater.py --output FILE  # Write to file instead of stdout
    python daily_context_updater.py --upload FILE  # Upload context file to GDrive
    python daily_context_updater.py --reasoning  # Include FPF reasoning state
"""

import argparse
import base64
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# --- Slack Integration ---
try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False

# --- Slack Mention Handler Integration ---
try:
    sys.path.append(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "slack"))
    )
    from slack_mention_handler import (
        format_mentions_for_daily_context,
        get_pending_tasks_for_context,
    )

    MENTIONS_AVAILABLE = True
except ImportError:
    MENTIONS_AVAILABLE = False

from dotenv import load_dotenv

load_dotenv(override=True)

# --- Configuration ---
# Add common directory to path to import config_loader
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config_loader

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "state.json")

# Get paths from centralized config
google_paths = config_loader.get_google_paths()
CREDENTIALS_FILE = google_paths["credentials"]
TOKEN_FILE = google_paths["token"]

DEFAULT_LOOKBACK_DAYS = 10

# --- Constants for Content Truncation ---
# ~1500 tokens per doc, ~600 tokens per email.
# Prevents context window exhaustion when processing many files.
DEFAULT_MAX_DOC_CHARS = 6000
DEFAULT_MAX_EMAIL_CHARS = 2500
SLACK_MAX_CHARS = 1000

# FPF Reasoning paths
USER_ROOT = config_loader.get_root_path() / "user"
REASONING_DIR = USER_ROOT / "brain" / "Reasoning"
QUINT_DIR = config_loader.get_root_path() / ".quint"


def get_slack_client():
    """Get authenticated Slack client."""
    slack_config = config_loader.get_slack_config()
    token = slack_config.get("bot_token")
    if not token:
        return None
    return WebClient(token=token)


def fetch_slack_messages(
    client, since: datetime, processed_files: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Fetch Slack messages from channels the bot is in, since the given timestamp.
    """
    if not client:
        return []

    messages = []
    try:
        # Get channels the bot is in
        response = client.users_conversations(types="public_channel,private_channel")
        channels = response["channels"]

        oldest = str(since.timestamp())

        for channel in channels:
            channel_id = channel["id"]
            channel_name = channel["name"]

            try:
                result = client.conversations_history(
                    channel=channel_id, oldest=oldest, limit=50
                )

                for msg in result["messages"]:
                    # Skip subtype messages (joins, leaves, etc) unless important
                    if msg.get("subtype"):
                        continue

                    msg_id = f"slack_{channel_id}_{msg['ts']}"

                    # Check if processed
                    if msg_id in processed_files:
                        continue

                    msg["channel_name"] = channel_name
                    msg["channel_id"] = channel_id
                    msg["unique_id"] = msg_id

                    # Resolve user name if possible (simple cache could be added)
                    user_id = msg.get("user")
                    if user_id:
                        try:
                            user_info = client.users_info(user=user_id)
                            msg["user_name"] = user_info["user"]["real_name"]
                        except:
                            msg["user_name"] = user_id

                    messages.append(msg)

            except SlackApiError as e:
                print(
                    f"Warning: Could not fetch history for {channel_name}: {e}",
                    file=sys.stderr,
                )

    except SlackApiError as e:
        print(f"Warning: Slack API error: {e}", file=sys.stderr)

    return messages


def get_reasoning_state() -> Dict[str, Any]:
    """
    Gather FPF reasoning state from Brain/Reasoning/ and .quint/ directories.
    Returns summary of active cycles, DRRs, expiring evidence, and open hypotheses.
    """
    state = {
        "active_cycles": [],
        "drrs": [],
        "expiring_evidence": [],
        "open_hypotheses": [],
        "quint_available": os.path.exists(QUINT_DIR),
    }

    today = datetime.now()
    expiry_window = timedelta(days=7)  # Flag evidence expiring within 7 days

    # Check Brain/Reasoning/Active/ for active cycles
    active_dir = os.path.join(REASONING_DIR, "Active")
    if os.path.exists(active_dir):
        for f in os.listdir(active_dir):
            if f.endswith(".md"):
                state["active_cycles"].append(
                    {"file": f, "path": os.path.join(active_dir, f)}
                )

    # Check Brain/Reasoning/Decisions/ for DRRs
    decisions_dir = os.path.join(REASONING_DIR, "Decisions")
    if os.path.exists(decisions_dir):
        for f in os.listdir(decisions_dir):
            if f.endswith(".md") and f.startswith("drr-"):
                state["drrs"].append(
                    {"file": f, "path": os.path.join(decisions_dir, f)}
                )

    # Check Brain/Reasoning/Evidence/ for expiring evidence
    evidence_dir = os.path.join(REASONING_DIR, "Evidence")
    if os.path.exists(evidence_dir):
        for f in os.listdir(evidence_dir):
            if f.endswith(".md"):
                filepath = os.path.join(evidence_dir, f)
                try:
                    with open(filepath, "r") as ef:
                        content = ef.read()
                        # Look for expiry date pattern: "expires: YYYY-MM-DD" or "Expiry: YYYY-MM-DD"
                        import re

                        match = re.search(
                            r"[Ee]xpir[ey]s?:\s*(\d{4}-\d{2}-\d{2})", content
                        )
                        if match:
                            expiry_date = datetime.strptime(match.group(1), "%Y-%m-%d")
                            if expiry_date <= today + expiry_window:
                                state["expiring_evidence"].append(
                                    {
                                        "file": f,
                                        "path": filepath,
                                        "expiry": match.group(1),
                                    }
                                )
                except Exception:
                    pass

    # Check Brain/Reasoning/Hypotheses/ for open hypotheses (L0/L1)
    hypotheses_dir = os.path.join(REASONING_DIR, "Hypotheses")
    if os.path.exists(hypotheses_dir):
        for f in os.listdir(hypotheses_dir):
            if f.endswith(".md"):
                filepath = os.path.join(hypotheses_dir, f)
                try:
                    with open(filepath, "r") as hf:
                        content = hf.read()
                        # Check if hypothesis is still open (L0 or L1, not L2 or Invalid)
                        if "L2" not in content and "Invalid" not in content:
                            state["open_hypotheses"].append(
                                {"file": f, "path": filepath}
                            )
                except Exception:
                    pass

    return state


def format_reasoning_summary(reasoning_state: Dict[str, Any]) -> str:
    """Format reasoning state for inclusion in context output."""
    lines = []
    lines.append("## FPF REASONING STATE")
    lines.append("")

    if not any(
        [
            reasoning_state["active_cycles"],
            reasoning_state["drrs"],
            reasoning_state["expiring_evidence"],
            reasoning_state["open_hypotheses"],
        ]
    ):
        lines.append("No active reasoning state found.")
        lines.append("")
        return "\n".join(lines)

    # Active cycles
    if reasoning_state["active_cycles"]:
        lines.append(f"### Active Cycles ({len(reasoning_state['active_cycles'])})")
        for cycle in reasoning_state["active_cycles"]:
            lines.append(f"- {cycle['file']}")
        lines.append("")

    # DRRs
    if reasoning_state["drrs"]:
        lines.append(f"### Design Rationale Records ({len(reasoning_state['drrs'])})")
        for drr in reasoning_state["drrs"]:
            lines.append(f"- {drr['file']}")
        lines.append("")

    # Expiring evidence
    if reasoning_state["expiring_evidence"]:
        lines.append(
            f"### Expiring Evidence ({len(reasoning_state['expiring_evidence'])} items expiring within 7 days)"
        )
        for ev in reasoning_state["expiring_evidence"]:
            lines.append(f"- {ev['file']} (expires: {ev['expiry']})")
        lines.append("")

    # Open hypotheses
    if reasoning_state["open_hypotheses"]:
        lines.append(
            f"### Open Hypotheses ({len(reasoning_state['open_hypotheses'])} L0/L1 claims)"
        )
        for hyp in reasoning_state["open_hypotheses"]:
            lines.append(f"- {hyp['file']}")
        lines.append("")

    # Quint status
    lines.append(
        f"**Quint Code:** {'Available' if reasoning_state['quint_available'] else 'Not initialized'}"
    )
    lines.append("")

    return "\n".join(lines)


def get_credentials():
    """Get authenticated Google credentials."""
    creds = None

    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            pass

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                if os.path.exists(TOKEN_FILE):
                    os.remove(TOKEN_FILE)
                return get_credentials()
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(
                    f"Error: Credentials file not found at {CREDENTIALS_FILE}",
                    file=sys.stderr,
                )
                return None

            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Ensure directory exists for token file
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds


def get_drive_service(creds=None):
    """Get authenticated Google Drive service."""
    if not creds:
        creds = get_credentials()
    return build("drive", "v3", credentials=creds)


def get_gmail_service(creds=None):
    """Get authenticated Gmail service."""
    if not creds:
        creds = get_credentials()
    return build("gmail", "v1", credentials=creds)


def upload_to_gdrive(
    local_path: str, folder_id: Optional[str] = None
) -> Dict[str, str]:
    """
    Upload a file to Google Drive.

    Args:
        local_path: Local path to the file to upload.
        folder_id: Optional folder ID to upload to. Uploads to root if not specified.

    Returns:
        Dict with 'id', 'name', and 'link' of uploaded file.
    """
    creds = get_credentials()
    service = get_drive_service(creds)

    file_name = os.path.basename(local_path)
    file_metadata = {"name": file_name}
    if folder_id:
        file_metadata["parents"] = [folder_id]

    media = MediaFileUpload(local_path, resumable=True)

    file = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id, name, webViewLink")
        .execute()
    )

    return {
        "id": file.get("id"),
        "name": file.get("name"),
        "link": file.get("webViewLink"),
    }


def load_state() -> Dict[str, Any]:
    """Read last run timestamp and processed files from state file."""
    state = {"last_run": None, "processed_files": {}}
    if not os.path.exists(STATE_FILE):
        return state

    try:
        with open(STATE_FILE, "r") as f:
            loaded_state = json.load(f)
            if "last_run" in loaded_state:
                state["last_run"] = datetime.fromisoformat(
                    loaded_state["last_run"].replace("Z", "+00:00")
                )
            if "processed_files" in loaded_state:
                state["processed_files"] = loaded_state["processed_files"]
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"Warning: Could not load state from {STATE_FILE}: {e}", file=sys.stderr)
        # If state file is corrupt, return initial state
        return {"last_run": None, "processed_files": {}}
    return state


def save_state(state: Dict[str, Any]):
    """Update state file with current timestamp and processed files."""
    serializable_state = {
        "last_run": state["last_run"].isoformat() if state["last_run"] else None,
        "processed_files": state["processed_files"],
    }
    with open(STATE_FILE, "w") as f:
        json.dump(serializable_state, f, indent=2)


def fetch_recent_docs(
    service, since: datetime, processed_files: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Fetch Google Docs and Sheets modified since the given timestamp.
    Queries:
    1. Owned by me
    2. Shared with me
    3. Contains specific keywords/names (Full-text search)
    """
    # Format timestamp for Drive API (RFC 3339)
    since_str = since.strftime("%Y-%m-%dT%H:%M:%S")

    # MIME types to include
    mime_types = [
        "application/vnd.google-apps.document",
        "application/vnd.google-apps.spreadsheet",
    ]
    mime_query = "(" + " or ".join([f"mimeType = '{m}'" for m in mime_types]) + ")"

    # Search terms — configure with your name and team members
    # Load from config.yaml search_terms if available
    search_terms = [
        # Add your name and team members here
        # "Your Name",
        # "Team Member",
    ]
    # Construct OR query for terms: (fullText contains 'Term1' or fullText contains 'Term2' ...)
    terms_query = (
        "("
        + " or ".join([f"fullText contains '{term}'" for term in search_terms])
        + ")"
    )

    all_docs = {}

    # Base filters
    base_filters = f"{mime_query} and modifiedTime > '{since_str}' and trashed = false"

    queries = [
        # Query 1: Owned by me
        f"'me' in owners and {base_filters}",
        # Query 2: Shared with me
        f"sharedWithMe and {base_filters}",
        # Query 3: Full text search for relevant terms (captures docs accessible but not explicitly shared)
        f"{terms_query} and {base_filters}",
    ]

    for query in queries:
        try:
            # Pagination for potentially large result sets from full-text search
            page_token = None
            while True:
                results = (
                    service.files()
                    .list(
                        pageSize=50,
                        fields="nextPageToken, files(id, name, mimeType, webViewLink, modifiedTime, owners)",
                        q=query,
                        orderBy="modifiedTime desc",
                        pageToken=page_token,
                    )
                    .execute()
                )

                for item in results.get("files", []):
                    # Check if already processed and not modified
                    item_id = item["id"]
                    item_mod_time = item.get("modifiedTime")
                    if (
                        item_id in processed_files
                        and processed_files[item_id] == item_mod_time
                    ):
                        print(
                            f"Skipping already processed document (ID: {item_id}, Name: {item['name']})",
                            file=sys.stderr,
                        )
                        continue

                    if item_id not in all_docs:
                        all_docs[item_id] = item

                page_token = results.get("nextPageToken")
                if not page_token:
                    break

        except Exception as e:
            print(f"Warning: Drive query failed - {e}", file=sys.stderr)

    return list(all_docs.values())


def is_promotional_email(message: Dict[str, Any]) -> bool:
    """
    Checks if an email is likely promotional based on subject, sender, and content.
    """
    headers = message.get("payload", {}).get("headers", [])
    subject = next((h["value"] for h in headers if h["name"] == "Subject"), "").lower()
    sender = next((h["value"] for h in headers if h["name"] == "From"), "").lower()

    # Keywords often found in promotional email subjects
    promo_subject_keywords = [
        "sale",
        "discount",
        "offer",
        "promo",
        "voucher",
        "% off",
        "cyber monday",
        "black friday",
        "save now",
        "free shipping",
        "coupon",
        "deal",
        "limited time",
        "special",
        "exclusive",
        "giveaway",
    ]

    # Keywords often found in promotional email senders
    promo_sender_keywords = [
        "noreply",
        "marketing",
        "promotions",
        "deals",
        "updates",
        "newsletter",
        "hello@g.",  # Common pattern for marketing emails from Acme Corp brands
        # "daily", "weekly update", # Too broad, might filter out legitimate updates
    ]

    # Check subject for promotional keywords
    for keyword in promo_subject_keywords:
        if keyword in subject:
            return True

    # Check sender for promotional keywords
    for keyword in promo_sender_keywords:
        if keyword in sender:
            return True

    # Check for common marketing email patterns in subject/sender that might not be explicit keywords
    if "cyber week" in subject or "cyber monday" in subject:
        return True
    if "save up to" in subject or "get your" in subject:  # e.g., "Get your deal"
        return True

    # Additional check for generic "unsubscribe" links in body could be added later if needed

    return False


def fetch_recent_emails(
    service, since: datetime, processed_files: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Fetch Gmail messages received since the given timestamp, filtering out promotional emails.
    """
    # Convert datetime to seconds since epoch for Gmail query
    since_ts = int(since.timestamp())
    query = f"after:{since_ts}"

    messages = []
    try:
        # List messages
        results = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=50)
            .execute()
        )
        message_list = results.get("messages", [])

        # Fetch details for each message and filter
        for msg in message_list:
            # Check if already processed and not modified (internalDate is the closest to modifiedTime for emails)
            msg_id = msg["id"]
            msg_internal_date = msg.get("internalDate")
            if (
                msg_id in processed_files
                and processed_files[msg_id] == msg_internal_date
            ):
                print(
                    f"Skipping already processed email (ID: {msg_id})", file=sys.stderr
                )
                continue

            try:
                # Get full message payload (snippet, headers, internalDate)
                full_msg = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg["id"], format="full")
                    .execute()
                )

                # Filter out promotional emails
                if not is_promotional_email(full_msg):
                    messages.append(full_msg)
                else:
                    # Optional: print filtered email subject for debugging
                    headers = full_msg.get("payload", {}).get("headers", [])
                    subject = next(
                        (h["value"] for h in headers if h["name"] == "Subject"),
                        "(No Subject)",
                    )
                    print(f"Skipping promotional email: {subject}", file=sys.stderr)

            except Exception as e:
                print(
                    f"Warning: Could not fetch email {msg['id']} - {e}", file=sys.stderr
                )

    except Exception as e:
        print(f"Warning: Gmail query failed - {e}", file=sys.stderr)

    return messages


def read_doc_content(
    service,
    file_id: str,
    file_name: str,
    mime_type: str = "application/vnd.google-apps.document",
    max_chars: int = DEFAULT_MAX_DOC_CHARS,
) -> str:
    """Read content of a Google Doc or Sheet, optionally truncated."""
    try:
        # Export based on MIME type
        if mime_type == "application/vnd.google-apps.spreadsheet":
            export_mime = "text/csv"
        else:
            export_mime = "text/plain"

        request = service.files().export_media(fileId=file_id, mimeType=export_mime)

        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        content = file_content.getvalue().decode("utf-8")

        # Smart Truncation: Keep Start (60%) and End (40%) to capture context + recent updates
        if len(content) > max_chars:
            keep_start = int(max_chars * 0.6)
            keep_end = int(max_chars * 0.4)
            truncated_msg = f"\n\n... [TRUNCATED: {len(content) - max_chars} chars omitted to save context] ...\n\n"

            # Ensure we don't overlap if max_chars is very small relative to content (though if logic above holds, we won't)
            # But if keep_start + keep_end >= len(content), we shouldn't be here.

            return content[:keep_start] + truncated_msg + content[-keep_end:]

        return content

    except Exception as e:
        return f"[Error reading document: {e}]"


def read_email_content(
    message: Dict[str, Any], max_chars: int = DEFAULT_MAX_EMAIL_CHARS
) -> str:
    """Extract text content from email payload, optionally truncated."""
    try:
        payload = message.get("payload", {})
        parts = payload.get("parts", [])
        body_data = None

        # 1. Check for simple body (no parts)
        if not parts:
            body_data = payload.get("body", {}).get("data")

        # 2. Check parts for text/plain
        if not body_data:
            for part in parts:
                if part.get("mimeType") == "text/plain":
                    body_data = part.get("body", {}).get("data")
                    break

        # 3. Fallback to html if no text/plain found (or first part if logic is complex)
        if not body_data and parts:
            # Just take the first part's data if available as fallback
            body_data = parts[0].get("body", {}).get("data")

        if body_data:
            # Decode base64url
            content = base64.urlsafe_b64decode(body_data).decode("utf-8")

            # Smart Truncation for Emails
            if len(content) > max_chars:
                keep_start = int(max_chars * 0.6)
                keep_end = int(max_chars * 0.4)
                truncated_msg = f"\n\n... [TRUNCATED: {len(content) - max_chars} chars omitted] ...\n\n"
                return content[:keep_start] + truncated_msg + content[-keep_end:]

            return content
        else:
            return "[No readable text content found]"

    except Exception as e:
        return f"[Error reading email: {e}]"


def format_output(
    docs: List[Dict],
    doc_contents: Dict[str, str],
    emails: List[Dict],
    email_contents: Dict[str, str],
    slack_messages: List[Dict],
    reasoning_state: Optional[Dict[str, Any]] = None,
    include_mentions: bool = True,
) -> str:
    """Format docs, emails, slack messages, and mention tasks for Claude Code synthesis."""
    lines = []
    lines.append("=" * 60)
    lines.append("DAILY CONTEXT UPDATE - RAW DATA")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Documents found: {len(docs)}")
    lines.append(f"Emails found: {len(emails)}")
    lines.append(f"Slack messages found: {len(slack_messages)}")
    if include_mentions and MENTIONS_AVAILABLE:
        try:
            mention_data = get_pending_tasks_for_context()
            owner_count = len(mention_data.get("owner_tasks", []))
            team_count = len(mention_data.get("team_tasks", []))
            lines.append(
                f"Mention tasks: {owner_count} for owner, {team_count} team tasks"
            )
        except Exception:
            pass  # Silently skip if mentions unavailable
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
            f"- [DOC] [{doc['name']}]({doc.get('webViewLink', '')}) | Modified: {modified} | Owner: {owner_name}"
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
        # internalDate is ms
        date_ts = int(email.get("internalDate", 0)) / 1000
        date_str = datetime.fromtimestamp(date_ts).strftime("%Y-%m-%d")

        lines.append(f"- [EMAIL] {subject} | From: {sender} | Date: {date_str}")
    lines.append("")

    # --- Slack Index ---
    lines.append("## SLACK INDEX")
    lines.append("")
    for msg in slack_messages:
        ts = float(msg["ts"])
        date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        user = msg.get("user_name", msg.get("user", "Unknown"))
        channel = msg.get("channel_name", "Unknown")
        preview = msg.get("text", "").replace("\n", " ")[:50]
        lines.append(f"- [SLACK] {channel} | {user}: {preview}...")
    lines.append("")

    # --- Document Contents ---
    lines.append("=" * 60)
    lines.append("## DOCUMENT CONTENTS")
    lines.append("=" * 60)
    lines.append("")

    for doc in docs:
        doc_id = doc["id"]
        lines.append("-" * 40)
        lines.append(f"### DOC: {doc['name']}")
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
        email_id = email["id"]
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

    for msg in slack_messages:
        ts = float(msg["ts"])
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

    # --- Mention Tasks (if available) ---
    if include_mentions and MENTIONS_AVAILABLE:
        lines.append("=" * 60)
        lines.append("## MENTION TASKS (Captured via Slack)")
        lines.append("=" * 60)
        lines.append("")
        try:
            mention_content = format_mentions_for_daily_context()
            lines.append(mention_content)
        except Exception as e:
            lines.append(f"[Error loading mention tasks: {e}]")
        lines.append("")

    # --- FPF Reasoning State (if included) ---
    if reasoning_state:
        lines.append("=" * 60)
        lines.append(format_reasoning_summary(reasoning_state))

    lines.append("=" * 60)
    lines.append("END OF RAW DATA")
    lines.append("=" * 60)
    lines.append("")

    # Calculate cutoff date (6 months ago)
    cutoff_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")

    lines.append("Instructions for Claude Code:")
    lines.append(
        "Synthesize the above into AI_Guidance/Core_Context/YYYY-MM-DD-context.md"
    )
    lines.append(
        f"IMPORTANT: STRICTLY IGNORE any content, meeting notes, decisions, or updates dated before {cutoff_date} (6 months ago)."
    )
    lines.append(
        "Extract: Key decisions, action items, blockers, metrics, important dates (only recent)."
    )
    lines.append("Format: NGO-style bullets, structured sections")
    if reasoning_state:
        lines.append(
            "Include: FPF reasoning state summary (active cycles, expiring evidence, pending decisions)"
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch recent Google Docs and Emails for context synthesis"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="List items without reading content"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore last-run timestamp, fetch last 7 days",
    )
    parser.add_argument(
        "--output", type=str, help="Write output to file instead of stdout"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help=f"Days to look back (default: {DEFAULT_LOOKBACK_DAYS}, used with --force or first run)",
    )
    parser.add_argument(
        "--max-doc-chars",
        type=int,
        default=DEFAULT_MAX_DOC_CHARS,
        help=f"Max characters per document to prevent context overflow (default: {DEFAULT_MAX_DOC_CHARS})",
    )
    parser.add_argument(
        "--upload",
        type=str,
        metavar="FILE_PATH",
        help="Upload a context file to Google Drive (standalone mode, skips fetch)",
    )
    parser.add_argument(
        "--upload-folder",
        type=str,
        default=None,
        help="Optional Google Drive folder ID to upload to",
    )
    parser.add_argument(
        "--jira",
        action="store_true",
        help="Also run Jira sync for Growth Division squads (writes to Brain/Inbox/)",
    )
    parser.add_argument(
        "--jira-summarize",
        action="store_true",
        help="Include Gemini summary with Jira sync (implies --jira)",
    )
    parser.add_argument(
        "--reasoning",
        action="store_true",
        help="Include FPF reasoning state (active cycles, DRRs, expiring evidence)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: GDocs only, skip Slack and Gmail for faster updates",
    )
    parser.add_argument(
        "--no-slack", action="store_true", help="Skip Slack message fetching"
    )
    parser.add_argument("--no-gmail", action="store_true", help="Skip Gmail fetching")
    parser.add_argument(
        "--no-mentions",
        action="store_true",
        help="Skip including pending Slack mention tasks",
    )

    args = parser.parse_args()

    # Quick mode implies no-slack and no-gmail
    if args.quick:
        args.no_slack = True
        args.no_gmail = True

    # --- Upload Mode (standalone) ---
    if args.upload:
        if not os.path.exists(args.upload):
            print(f"Error: File not found: {args.upload}", file=sys.stderr)
            sys.exit(1)

        print(f"Uploading {args.upload} to Google Drive...", file=sys.stderr)
        try:
            result = upload_to_gdrive(args.upload, args.upload_folder)
            print(f"Upload successful!", file=sys.stderr)
            print(f"  ID: {result['id']}", file=sys.stderr)
            print(f"  Name: {result['name']}", file=sys.stderr)
            print(f"  Link: {result['link']}", file=sys.stderr)
            # Output just the link to stdout for easy capture
            print(result["link"])
        except Exception as e:
            print(f"Upload failed: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # Load current state
    state = load_state()
    last_run = state["last_run"]
    processed_files = state["processed_files"]

    # Determine time window
    if args.force:
        since = datetime.now(timezone.utc) - timedelta(days=args.days)
        # Clear processed files if --force is used, to re-process all
        processed_files = {}
        print(
            f"Force mode: fetching items from last {args.days} days, reprocessing all documents.",
            file=sys.stderr,
        )
    else:
        if last_run is None:
            since = datetime.now(timezone.utc) - timedelta(days=args.days)
            print(
                f"First run: fetching items from last {args.days} days", file=sys.stderr
            )
        else:
            since = last_run
            print(
                f"Fetching items modified/received since: {since.isoformat()}",
                file=sys.stderr,
            )

    # Get Credentials
    print("Authenticating with Google...", file=sys.stderr)
    creds = get_credentials()
    if not creds:
        print("Authentication failed.", file=sys.stderr)
        return

    # --- Drive ---
    print("Connecting to Google Drive...", file=sys.stderr)
    drive_service = get_drive_service(creds)

    print("Fetching recent documents...", file=sys.stderr)
    docs = fetch_recent_docs(drive_service, since, processed_files)

    # --- Gmail ---
    emails = []
    if not args.no_gmail:
        print("Connecting to Gmail...", file=sys.stderr)
        gmail_service = get_gmail_service(creds)

        print("Fetching recent emails...", file=sys.stderr)
        emails = fetch_recent_emails(gmail_service, since, processed_files)
    else:
        print("Skipping Gmail (--no-gmail or --quick)", file=sys.stderr)

    # --- Slack ---
    slack_messages = []
    if not args.no_slack and SLACK_AVAILABLE:
        print("Connecting to Slack...", file=sys.stderr)
        slack_client = get_slack_client()
        if slack_client:
            print("Fetching recent Slack messages...", file=sys.stderr)
            slack_messages = fetch_slack_messages(slack_client, since, processed_files)
        else:
            print("Slack token not found, skipping Slack fetch.", file=sys.stderr)
    elif args.no_slack:
        print("Skipping Slack (--no-slack or --quick)", file=sys.stderr)

    if not docs and not emails and not slack_messages:
        print("No new documents, emails, or Slack messages found.", file=sys.stderr)
        # Always update last_run even if no new docs, to advance the window
        state["last_run"] = datetime.now(timezone.utc)
        save_state(state)
        return

    print(
        f"Found {len(docs)} document(s), {len(emails)} email(s), and {len(slack_messages)} Slack messages",
        file=sys.stderr,
    )

    # Dry run
    if args.dry_run:
        print("\n--- DRY RUN: Items that would be processed ---\n")
        if docs:
            print("DOCUMENTS:")
            for doc in docs:
                modified = doc.get("modifiedTime", "Unknown")[:10]
                print(f"  - {doc['name']} (modified: {modified})")
        if emails:
            print("\nEMAILS:")
            for email in emails:
                headers = email.get("payload", {}).get("headers", [])
                subject = next(
                    (h["value"] for h in headers if h["name"] == "Subject"),
                    "(No Subject)",
                )
                print(f"  - {subject}")
        if slack_messages:
            print("\nSLACK:")
            for msg in slack_messages:
                ts = float(msg["ts"])
                date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                print(
                    f"  - [{msg.get('channel_name')}] {msg.get('user_name')}: {msg.get('text')[:30]}..."
                )
        return

    # Read contents
    print("Reading document contents...", file=sys.stderr)
    doc_contents = {}
    for i, doc in enumerate(docs):
        print(f"  [Doc {i+1}/{len(docs)}] {doc['name']}", file=sys.stderr)
        # Pass the mimeType to handle Sheets vs Docs
        doc_contents[doc["id"]] = read_doc_content(
            drive_service,
            doc["id"],
            doc["name"],
            doc["mimeType"],
            max_chars=args.max_doc_chars,
        )
        # Update processed_files for docs that were actually read
        processed_files[doc["id"]] = doc.get("modifiedTime")

    print("Reading email contents...", file=sys.stderr)
    email_contents = {}
    for i, email in enumerate(emails):
        headers = email.get("payload", {}).get("headers", [])
        subject = next(
            (h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)"
        )
        print(f"  [Email {i+1}/{len(emails)}] {subject[:40]}...", file=sys.stderr)
        email_contents[email["id"]] = read_email_content(email)
        # Emails don't have modifiedTime, so use internalDate
        processed_files[email["id"]] = email.get("internalDate")

    # Slack messages are already fetched fully, just need to update state
    for msg in slack_messages:
        processed_files[msg["unique_id"]] = msg["ts"]

    # Get reasoning state if requested
    reasoning_state = None
    if args.reasoning:
        print("Gathering FPF reasoning state...", file=sys.stderr)
        reasoning_state = get_reasoning_state()
        active = len(reasoning_state.get("active_cycles", []))
        drrs = len(reasoning_state.get("drrs", []))
        expiring = len(reasoning_state.get("expiring_evidence", []))
        print(
            f"  Active cycles: {active}, DRRs: {drrs}, Expiring evidence: {expiring}",
            file=sys.stderr,
        )

    # Format output
    include_mentions = not args.no_mentions
    output = format_output(
        docs,
        doc_contents,
        emails,
        email_contents,
        slack_messages,
        reasoning_state,
        include_mentions,
    )

    # Write output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"\nOutput written to: {args.output}", file=sys.stderr)
    else:
        # Explicitly write to stdout in UTF-8 to prevent UnicodeEncodeError on some systems
        sys.stdout.buffer.write(output.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")  # Add a newline as print() would

    # Update and save final state
    state["last_run"] = datetime.now(timezone.utc)
    state["processed_files"] = processed_files
    save_state(state)
    print("\nState updated. Ready for synthesis.", file=sys.stderr)

    # --- Jira Sync (optional) ---
    if args.jira or args.jira_summarize:
        print("\nRunning Jira sync for Growth Division squads...", file=sys.stderr)
        try:
            import subprocess

            jira_sync_path = os.path.join(
                os.path.dirname(__file__), "..", "jira_brain_sync.py"
            )
            jira_cmd = ["python3", jira_sync_path]
            if args.jira_summarize:
                jira_cmd.append("--summarize")

            result = subprocess.run(jira_cmd, capture_output=False, text=True)
            if result.returncode == 0:
                print("Jira sync completed.", file=sys.stderr)
            else:
                print(
                    f"Jira sync failed with return code {result.returncode}",
                    file=sys.stderr,
                )
        except Exception as e:
            print(f"Jira sync error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
