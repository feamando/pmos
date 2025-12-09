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
"""

import os
import sys
import json
import argparse
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import io

# --- Configuration ---
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.metadata.readonly',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.readonly'
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, 'state.json')

# Credential paths - Prioritize local directory for standalone usage
LOCAL_CREDENTIALS = os.path.join(BASE_DIR, 'credentials.json')
LOCAL_TOKEN = os.path.join(BASE_DIR, 'token.json')

# Fallback to gdrive_mcp if not found locally (Legacy/Dev environment support)
GDRIVE_MCP_DIR = os.path.join(os.path.dirname(BASE_DIR), 'gdrive_mcp')
MCP_CREDENTIALS = os.path.join(GDRIVE_MCP_DIR, 'credentials.json')
MCP_TOKEN = os.path.join(GDRIVE_MCP_DIR, 'token.json')

# --- Constants for Content Truncation ---
# ~1500 tokens per doc, ~600 tokens per email. 
# Prevents context window exhaustion when processing many files.
DEFAULT_MAX_DOC_CHARS = 6000
DEFAULT_MAX_EMAIL_CHARS = 2500 

def get_credential_paths():
    """Determine which credential files to use."""
    if os.path.exists(LOCAL_CREDENTIALS) or not os.path.exists(MCP_CREDENTIALS):
        return LOCAL_CREDENTIALS, LOCAL_TOKEN
    return MCP_CREDENTIALS, MCP_TOKEN

CREDENTIALS_FILE, TOKEN_FILE = get_credential_paths()

DEFAULT_LOOKBACK_DAYS = 10


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
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    
    return creds


def get_drive_service(creds=None):
    """Get authenticated Google Drive service."""
    if not creds:
        creds = get_credentials()
    return build('drive', 'v3', credentials=creds)


def get_gmail_service(creds=None):
    """Get authenticated Gmail service."""
    if not creds:
        creds = get_credentials()
    return build('gmail', 'v1', credentials=creds)


def upload_to_gdrive(local_path: str, folder_id: Optional[str] = None) -> Dict[str, str]:
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
    file_metadata = {'name': file_name}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaFileUpload(local_path, resumable=True)

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, name, webViewLink'
    ).execute()

    return {
        'id': file.get('id'),
        'name': file.get('name'),
        'link': file.get('webViewLink')
    }


def get_last_run_time() -> Optional[datetime]:
    """Read last run timestamp from state file."""
    if not os.path.exists(STATE_FILE):
        return None

    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            last_run = state.get('last_run')
            if last_run:
                return datetime.fromisoformat(last_run.replace('Z', '+00:00'))
    except (json.JSONDecodeError, KeyError, ValueError):
        pass

    return None


def update_last_run_time(docs_processed: List[str] = None):
    """Update state file with current timestamp."""
    state = {
        'last_run': datetime.now(timezone.utc).isoformat(),
        'docs_processed': docs_processed or []
    }

    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def fetch_recent_docs(service, since: datetime) -> List[Dict[str, Any]]:
    """
    Fetch Google Docs and Sheets modified since the given timestamp.
    Queries:
    1. Owned by me
    2. Shared with me
    3. Contains specific keywords/names (Full-text search)
    """
    # Format timestamp for Drive API (RFC 3339)
    since_str = since.strftime('%Y-%m-%dT%H:%M:%S')

    # MIME types to include
    mime_types = [
        "application/vnd.google-apps.document",
        "application/vnd.google-apps.spreadsheet"
    ]
    mime_query = "(" + " or ".join([f"mimeType = '{m}'" for m in mime_types]) + ")"

    # Search terms from user request
    search_terms = [
        "Nikita Gorshkov",
        "New Ventures",
        "New Ventures & Ecosystems",
        "TAM Expansion",
        "nikita.gorshkov@hellofresh.com",
        "Beatrice", "Hamed", "Deo", "Leo", "Alison", "Jama", "Daniel", "Maria", "Prateek"
    ]
    # Construct OR query for terms: (fullText contains 'Term1' or fullText contains 'Term2' ...)
    terms_query = "(" + " or ".join([f"fullText contains '{term}'" for term in search_terms]) + ")"

    all_docs = {}

    # Base filters
    base_filters = f"{mime_query} and modifiedTime > '{since_str}' and trashed = false"

    queries = [
        # Query 1: Owned by me
        f"'me' in owners and {base_filters}",
        
        # Query 2: Shared with me
        f"sharedWithMe and {base_filters}",
        
        # Query 3: Full text search for relevant terms (captures docs accessible but not explicitly shared)
        f"{terms_query} and {base_filters}"
    ]

    for query in queries:
        try:
            # Pagination for potentially large result sets from full-text search
            page_token = None
            while True:
                results = service.files().list(
                    pageSize=50,
                    fields="nextPageToken, files(id, name, mimeType, webViewLink, modifiedTime, owners)",
                    q=query,
                    orderBy="modifiedTime desc",
                    pageToken=page_token
                ).execute()

                for item in results.get('files', []):
                    if item['id'] not in all_docs:
                        all_docs[item['id']] = item
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                    
        except Exception as e:
            print(f"Warning: Drive query failed - {e}", file=sys.stderr)

    return list(all_docs.values())


def is_promotional_email(message: Dict[str, Any]) -> bool:
    """
    Checks if an email is likely promotional based on subject, sender, and content.
    """
    headers = message.get('payload', {}).get('headers', [])
    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '').lower()
    sender = next((h['value'] for h in headers if h['name'] == 'From'), '').lower()
    
    # Keywords often found in promotional email subjects
    promo_subject_keywords = [
        "sale", "discount", "offer", "promo", "voucher", "% off", "cyber monday", 
        "black friday", "save now", "free shipping", "coupon", "deal", 
        "limited time", "special", "exclusive", "giveaway"
    ]
    
    # Keywords often found in promotional email senders
    promo_sender_keywords = [
        "noreply", "marketing", "promotions", "deals", "updates", "newsletter",
        "hello@g.", # Common pattern for marketing emails from HelloFresh brands
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
    if "save up to" in subject or "get your" in subject: # e.g., "Get your deal"
        return True
    
    # Additional check for generic "unsubscribe" links in body could be added later if needed
    
    return False


def fetch_recent_emails(service, since: datetime) -> List[Dict[str, Any]]:
    """
    Fetch Gmail messages received since the given timestamp, filtering out promotional emails.
    """
    # Convert datetime to seconds since epoch for Gmail query
    since_ts = int(since.timestamp())
    query = f"after:{since_ts}"
    
    messages = []
    try:
        # List messages
        results = service.users().messages().list(userId='me', q=query, maxResults=50).execute()
        message_list = results.get('messages', [])
        
        # Fetch details for each message and filter
        for msg in message_list:
            try:
                # Get full message payload (snippet, headers, internalDate)
                full_msg = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
                
                # Filter out promotional emails
                if not is_promotional_email(full_msg):
                    messages.append(full_msg)
                else:
                    # Optional: print filtered email subject for debugging
                    headers = full_msg.get('payload', {}).get('headers', [])
                    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '(No Subject)')
                    print(f"Skipping promotional email: {subject}", file=sys.stderr)

            except Exception as e:
                 print(f"Warning: Could not fetch email {msg['id']} - {e}", file=sys.stderr)
                 
    except Exception as e:
        print(f"Warning: Gmail query failed - {e}", file=sys.stderr)
        
    return messages


def read_doc_content(service, file_id: str, file_name: str, mime_type: str = 'application/vnd.google-apps.document', max_chars: int = DEFAULT_MAX_DOC_CHARS) -> str:
    """Read content of a Google Doc or Sheet, optionally truncated."""
    try:
        # Export based on MIME type
        if mime_type == 'application/vnd.google-apps.spreadsheet':
            export_mime = 'text/csv'
        else:
            export_mime = 'text/plain'

        request = service.files().export_media(fileId=file_id, mimeType=export_mime)

        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        content = file_content.getvalue().decode('utf-8')
        
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


def read_email_content(message: Dict[str, Any], max_chars: int = DEFAULT_MAX_EMAIL_CHARS) -> str:
    """Extract text content from email payload, optionally truncated."""
    try:
        payload = message.get('payload', {})
        parts = payload.get('parts', [])
        body_data = None
        
        # 1. Check for simple body (no parts)
        if not parts:
             body_data = payload.get('body', {}).get('data')
             
        # 2. Check parts for text/plain
        if not body_data:
            for part in parts:
                if part.get('mimeType') == 'text/plain':
                    body_data = part.get('body', {}).get('data')
                    break
        
        # 3. Fallback to html if no text/plain found (or first part if logic is complex)
        if not body_data and parts:
             # Just take the first part's data if available as fallback
             body_data = parts[0].get('body', {}).get('data')
        
        if body_data:
            # Decode base64url
            content = base64.urlsafe_b64decode(body_data).decode('utf-8')
            
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


def format_output(docs: List[Dict], doc_contents: Dict[str, str], 
                  emails: List[Dict], email_contents: Dict[str, str]) -> str:
    """Format docs and emails for Claude Code synthesis."""
    lines = []
    lines.append("=" * 60)
    lines.append("DAILY CONTEXT UPDATE - RAW DATA")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Documents found: {len(docs)}")
    lines.append(f"Emails found: {len(emails)}")
    lines.append("=" * 60)
    lines.append("")

    # --- Document Index ---
    lines.append("## DOCUMENT INDEX")
    lines.append("")
    for doc in docs:
        modified = doc.get('modifiedTime', 'Unknown')[:10]
        owners = doc.get('owners', [{}])
        owner_name = owners[0].get('displayName', 'Unknown') if owners else 'Unknown'
        lines.append(f"- [DOC] [{doc['name']}]({doc.get('webViewLink', '')}) | Modified: {modified} | Owner: {owner_name}")
    lines.append("")

    # --- Email Index ---
    lines.append("## EMAIL INDEX")
    lines.append("")
    for email in emails:
        headers = email.get('payload', {}).get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '(No Subject)')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        # internalDate is ms
        date_ts = int(email.get('internalDate', 0)) / 1000
        date_str = datetime.fromtimestamp(date_ts).strftime('%Y-%m-%d')
        
        lines.append(f"- [EMAIL] {subject} | From: {sender} | Date: {date_str}")
    lines.append("")

    # --- Document Contents ---
    lines.append("=" * 60)
    lines.append("## DOCUMENT CONTENTS")
    lines.append("=" * 60)
    lines.append("")

    for doc in docs:
        doc_id = doc['id']
        lines.append("-" * 40)
        lines.append(f"### DOC: {doc['name']}")
        lines.append(f"ID: {doc_id}")
        lines.append(f"Link: {doc.get('webViewLink', 'N/A')}")
        lines.append("-" * 40)
        lines.append("")
        lines.append(doc_contents.get(doc_id, '[Content not available]'))
        lines.append("")
        lines.append("")

    # --- Email Contents ---
    lines.append("=" * 60)
    lines.append("## EMAIL CONTENTS")
    lines.append("=" * 60)
    lines.append("")
    
    for email in emails:
        email_id = email['id']
        headers = email.get('payload', {}).get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '(No Subject)')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        
        lines.append("-" * 40)
        lines.append(f"### EMAIL: {subject}")
        lines.append(f"ID: {email_id}")
        lines.append(f"From: {sender}")
        lines.append("-" * 40)
        lines.append("")
        lines.append(email_contents.get(email_id, '[Content not available]'))
        lines.append("")
        lines.append("")

    lines.append("=" * 60)
    lines.append("END OF RAW DATA")
    lines.append("=" * 60)
    lines.append("")
    
    # Calculate cutoff date (6 months ago)
    cutoff_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
    
    lines.append("Instructions for Claude Code:")
    lines.append("Synthesize the above into AI_Guidance/Core_Context/YYYY-MM-DD-context.md")
    lines.append(f"IMPORTANT: STRICTLY IGNORE any content, meeting notes, decisions, or updates dated before {cutoff_date} (6 months ago).")
    lines.append("Extract: Key decisions, action items, blockers, metrics, important dates (only recent).")
    lines.append("Format: NGO-style bullets, structured sections")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch recent Google Docs and Emails for context synthesis"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='List items without reading content'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Ignore last-run timestamp, fetch last 7 days'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Write output to file instead of stdout'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help=f'Days to look back (default: {DEFAULT_LOOKBACK_DAYS}, used with --force or first run)'
    )
    parser.add_argument(
        '--max-doc-chars',
        type=int,
        default=DEFAULT_MAX_DOC_CHARS,
        help=f'Max characters per document to prevent context overflow (default: {DEFAULT_MAX_DOC_CHARS})'
    )
    parser.add_argument(
        '--upload',
        type=str,
        metavar='FILE_PATH',
        help='Upload a context file to Google Drive (standalone mode, skips fetch)'
    )
    parser.add_argument(
        '--upload-folder',
        type=str,
        default=None,
        help='Optional Google Drive folder ID to upload to'
    )

    args = parser.parse_args()

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
            print(result['link'])
        except Exception as e:
            print(f"Upload failed: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # Determine time window
    if args.force:
        since = datetime.now(timezone.utc) - timedelta(days=args.days)
        print(f"Force mode: fetching items from last {args.days} days", file=sys.stderr)
    else:
        since = get_last_run_time()
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=args.days)
            print(f"First run: fetching items from last {args.days} days", file=sys.stderr)
        else:
            print(f"Fetching items modified/received since: {since.isoformat()}", file=sys.stderr)

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
    docs = fetch_recent_docs(drive_service, since)
    
    # --- Gmail ---
    print("Connecting to Gmail...", file=sys.stderr)
    gmail_service = get_gmail_service(creds)
    
    print("Fetching recent emails...", file=sys.stderr)
    emails = fetch_recent_emails(gmail_service, since)

    if not docs and not emails:
        print("No new documents or emails found.", file=sys.stderr)
        if not args.dry_run:
            update_last_run_time([])
        return

    print(f"Found {len(docs)} document(s) and {len(emails)} email(s)", file=sys.stderr)

    # Dry run
    if args.dry_run:
        print("\n--- DRY RUN: Items that would be processed ---\n")
        if docs:
            print("DOCUMENTS:")
            for doc in docs:
                modified = doc.get('modifiedTime', 'Unknown')[:10]
                print(f"  - {doc['name']} (modified: {modified})")
        if emails:
            print("\nEMAILS:")
            for email in emails:
                headers = email.get('payload', {}).get('headers', [])
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '(No Subject)')
                print(f"  - {subject}")
        return

    # Read contents
    print("Reading document contents...", file=sys.stderr)
    doc_contents = {}
    for i, doc in enumerate(docs):
        print(f"  [Doc {i+1}/{len(docs)}] {doc['name']}", file=sys.stderr)
        # Pass the mimeType to handle Sheets vs Docs
        doc_contents[doc['id']] = read_doc_content(
            drive_service, 
            doc['id'], 
            doc['name'], 
            doc['mimeType'], 
            max_chars=args.max_doc_chars
        )
        
    print("Reading email contents...", file=sys.stderr)
    email_contents = {}
    for i, email in enumerate(emails):
        headers = email.get('payload', {}).get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '(No Subject)')
        print(f"  [Email {i+1}/{len(emails)}] {subject[:40]}...", file=sys.stderr)
        email_contents[email['id']] = read_email_content(email)

    # Format output
    output = format_output(docs, doc_contents, emails, email_contents)

    # Write output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"\nOutput written to: {args.output}", file=sys.stderr)
    else:
        # Explicitly write to stdout in UTF-8 to prevent UnicodeEncodeError on some systems
        sys.stdout.buffer.write(output.encode('utf-8'))
        sys.stdout.buffer.write(b'\n') # Add a newline as print() would

    # Update state
    # We track docs processed, but technically we should track last run time.
    # The state tracking in this script is a bit simplistic (just last_run), which is fine.
    # We passed docs IDs before, we'll just pass a mix or just empty list since only time matters for next run.
    update_last_run_time([d['id'] for d in docs] + [e['id'] for e in emails])
    print("\nState updated. Ready for synthesis.", file=sys.stderr)


if __name__ == "__main__":
    main()
