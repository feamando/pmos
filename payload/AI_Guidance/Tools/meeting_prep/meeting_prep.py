#!/usr/bin/env python3
"""
Meeting Prep Tool (Refactored)

Generates personalized meeting pre-reads, manages meeting series history,
uploads to Google Drive, and links pre-reads to Calendar events.

Features:
- Fetches calendar events.
- Classifies meetings (1:1, Team, etc.).
- Gathers context from Brain and Daily Context.
- Synthesizes pre-reads using Gemini.
- Manages "Series" files for recurring meetings (history preservation).
- Uploads to Google Drive.
- Updates Calendar events with links to pre-reads.

Usage:
    python meeting_prep.py                    # Prep all meetings in next 24h
    python meeting_prep.py --hours 8          # Next 8 hours only
    python meeting_prep.py --meeting "1on1"   # Prep specific meeting by title
    python meeting_prep.py --list             # List upcoming meetings without prep
    python meeting_prep.py --dry-run          # Show what would be generated
"""

import os
import sys
import re
import json
import argparse
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from glob import glob

# Google API imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Try to import yaml
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# Try to import Gemini
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    print("Warning: google-generativeai not installed. Synthesis disabled.", file=sys.stderr)

# --- Configuration ---
SCOPES = [
    'https://www.googleapis.com/auth/drive',            # Read/Write Drive
    'https://www.googleapis.com/auth/drive.metadata',   # Metadata
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar.events',  # Write access for description linking
    'https://www.googleapis.com/auth/calendar.readonly',
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.dirname(BASE_DIR)
AI_GUIDANCE_DIR = os.path.dirname(TOOLS_DIR)
REPO_ROOT = os.path.dirname(AI_GUIDANCE_DIR)

# Credential paths - use gdrive_mcp credentials
GDRIVE_MCP_DIR = os.path.join(TOOLS_DIR, 'gdrive_mcp')
CREDENTIALS_FILE = os.path.join(GDRIVE_MCP_DIR, 'credentials.json')
TOKEN_FILE = os.path.join(GDRIVE_MCP_DIR, 'token.json')

# Brain paths
BRAIN_DIR = os.path.join(AI_GUIDANCE_DIR, 'Brain')
REGISTRY_FILE = os.path.join(BRAIN_DIR, 'registry.yaml')
CONTEXT_DIR = os.path.join(AI_GUIDANCE_DIR, 'Core_Context')

# Output paths
OUTPUT_DIR = os.path.join(REPO_ROOT, 'Planning', 'Meeting_Prep')
SERIES_DIR = os.path.join(OUTPUT_DIR, 'Series')
ADHOC_DIR = os.path.join(OUTPUT_DIR, 'AdHoc')
ARCHIVE_DIR = os.path.join(OUTPUT_DIR, 'Archive')

# Your email domain for internal/external detection
INTERNAL_DOMAINS = [
    # HelloFresh domains
    'hellofresh.com', 'hellofresh.de', 'hellofresh.nl', 'hellofresh.be',
    'hellofresh.fr', 'hellofresh.co.uk', 'hellofresh.at', 'hellofresh.ch',
    'hellofresh.ca', 'hellofresh.com.au', 'hellofresh.co.nz', 'hellofresh.se',
    'hellofresh.dk', 'hellofresh.no', 'hellofresh.it', 'hellofresh.es',
    'hellofresh.jp', 'hellofresh.ie',
    # Factor
    'factor75.com', 'factor.com',
    # Good Chop
    'goodchop.com',
    # The Pets Table
    'thepetstable.com', 'petstable.com',
    # Other HF Group brands
    'greenchef.com', 'everyplate.com', 'chefsplate.com', 'youfoodz.com',
]

# Gemini model
GEMINI_MODEL = 'gemini-2.5-flash'


# =============================================================================
# Authentication
# =============================================================================

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
                print(f"Error: credentials.json not found at {CREDENTIALS_FILE}", file=sys.stderr)
                print("Please set up OAuth credentials first.", file=sys.stderr)
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return creds


def get_calendar_service(creds=None):
    if not creds: creds = get_credentials()
    return build('calendar', 'v3', credentials=creds)


def get_drive_service(creds=None):
    if not creds: creds = get_credentials()
    return build('drive', 'v3', credentials=creds)


# =============================================================================
# Helper Functions (Stateless)
# =============================================================================

def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    slug = text.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')[:50]
def extract_names_from_title(title: str) -> List[str]:
    """Extract potential participant names from meeting title."""
    names = []
    cleaned = re.sub(r'^\s*(1:1s?|sync|weekly|bi-weekly|meeting|call)[:\s]+', '', title, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*(1:1s?|1on1|sync|weekly|bi-weekly|meeting|call).*$', '', cleaned, flags=re.IGNORECASE)
    parts = re.split(r'[:/\-<> ]', cleaned)
    for part in parts:
        part = part.strip()
        if len(part) < 2 or re.match(r'^\d+', part): continue
        names.append(part.title())
    return names

def load_brain_registry() -> Dict:
    if not os.path.exists(REGISTRY_FILE) or not HAS_YAML: return {}
    with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

def build_alias_index(registry: Dict) -> Dict[str, Tuple[str, str, str]]:
    index = {}
    for category in ['projects', 'entities', 'architecture']:
        if category not in registry or registry[category] is None: continue
        for entity_id, entity_data in registry[category].items():
            if not isinstance(entity_data, dict): continue
            file_path = entity_data.get('file', '')
            aliases = entity_data.get('aliases', [])
            all_aliases = [entity_id] + (aliases if aliases else [])
            for alias in all_aliases:
                if alias: index[alias.lower()] = (category, entity_id, file_path)
    return index

def resolve_participant_to_brain(name: str, email: str, alias_index: Dict) -> Optional[Dict]:
    # Try name match
    name_lower = name.lower()
    if name_lower in alias_index:
        cat, eid, path = alias_index[name_lower]
        return {'entity_id': eid, 'category': cat, 'file_path': path}
    # Try first name
    first_name = name.split()[0].lower() if name else ''
    if first_name and first_name in alias_index:
        cat, eid, path = alias_index[first_name]
        return {'entity_id': eid, 'category': cat, 'file_path': path}
    # Try email prefix
    email_prefix = email.split('@')[0].lower().replace('.', '_') if email else ''
    if email_prefix in alias_index:
        cat, eid, path = alias_index[email_prefix]
        return {'entity_id': eid, 'category': cat, 'file_path': path}
    return None

def load_brain_file(file_path: str) -> str:
    full_path = os.path.join(BRAIN_DIR, file_path)
    if os.path.exists(full_path):
        with open(full_path, 'r', encoding='utf-8') as f: return f.read()
    return ''

def get_latest_context_file() -> Optional[str]:
    pattern = os.path.join(CONTEXT_DIR, "*-context.md")
    files = glob(pattern)
    if not files: return None
    files.sort()
    return files[-1]


# =============================================================================
# Meeting Manager Class
# =============================================================================

class MeetingManager:
    def __init__(self, drive_service, calendar_service, registry):
        self.drive = drive_service
        self.calendar = calendar_service
        self.registry = registry
        self.alias_index = build_alias_index(registry)
        self.prep_folder_id = self._get_or_create_drive_folder("Meeting Pre-Reads")

        # Ensure directories exist
        os.makedirs(SERIES_DIR, exist_ok=True)
        os.makedirs(ADHOC_DIR, exist_ok=True)
        os.makedirs(ARCHIVE_DIR, exist_ok=True)

    def read_gdrive_file(self, file_id: str) -> str:
        """Read content of a GDoc."""
        try:
            content = self.drive.files().export(
                fileId=file_id,
                mimeType='text/plain'
            ).execute()
            return content.decode('utf-8')
        except Exception as e:
            print(f"GDrive read error: {e}", file=sys.stderr)
            return ""

    def search_gdrive_notes(self, meeting_title: str) -> Optional[Dict]:
        """Search GDrive for past meeting notes (Doc type) matching title."""
        # Clean title: remove 1:1, sync, etc.
        cleaned = re.sub(r'\s*(1:1|sync|weekly|meeting)\s*', '', meeting_title, flags=re.IGNORECASE).strip()
        if not cleaned: cleaned = meeting_title
        
        # Remove special chars for Drive query safety
        query_text = cleaned.replace(":", " ").replace("/", " ")

        # Query: Title MUST contain the specific meeting identifiers
        query = (f"name contains '{query_text}' "
                 f"and mimeType = 'application/vnd.google-apps.document' "
                 f"and trashed = false")
        
        try:
            results = self.drive.files().list(
                q=query,
                orderBy='createdTime desc',
                pageSize=5,
                fields="files(id, name, createdTime)"
            ).execute()
            
            files = results.get('files', [])
            
            # Strict Filtering: Check if all key parts of cleaned title exist in filename
            key_parts = [p.lower() for p in cleaned.split() if len(p) > 2]
            
            for file in files:
                fname = file['name'].lower()
                # If all significant parts of the meeting title are in the filename
                if all(part in fname for part in key_parts):
                     # Exclude today's notes if they happen to exist already? 
                     # Actually, we want PAST notes.
                     # But createdTime desc means index 0 is newest.
                     return file
                    
            return None

        except Exception as e:
            print(f"GDrive search error: {e}", file=sys.stderr)
            return None

    def _get_or_create_drive_folder(self, folder_name: str) -> str:
        """Find or create a folder in Drive Root."""
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = self.drive.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])

        if files:
            return files[0]['id']
        else:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            file = self.drive.files().create(body=file_metadata, fields='id').execute()
            return file.get('id')

    def fetch_events(self, hours: int = 24) -> List[Dict]:
        """Fetch upcoming events."""
        now = datetime.now(timezone.utc)
        time_max = now + timedelta(hours=hours)

        events_result = self.calendar.events().list(
            calendarId='primary',
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            maxResults=50,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        filtered = []

        for event in events:
            # Skip declined
            attendees = event.get('attendees', [])
            declined = False
            for att in attendees:
                if att.get('self', False) and att.get('responseStatus') == 'declined':
                    declined = True
                    break
            if declined: continue

            # Skip all-day events (date only, no dateTime)
            if 'dateTime' not in event.get('start', {}):
                continue
            
            filtered.append(event)
        
        return filtered

    def classify_meeting(self, event: Dict) -> Dict:
        """Classify meeting type and extract metadata."""
        summary = event.get('summary', '').lower()
        description = event.get('description', '') or ''
        attendees = event.get('attendees', [])
        recurrence_id = event.get('recurringEventId') # ID of the series master

        title_names = extract_names_from_title(event.get('summary', ''))
        other_person_name = next((tn for tn in title_names if tn.lower() != 'nikita'), None)

        participants = []
        external_count = 0
        non_self_count = sum(1 for a in attendees if not a.get('self', False))

        for attendee in attendees:
            if attendee.get('self', False): continue
            email = attendee.get('email', '')
            if 'resource.calendar.google.com' in email: continue
            
            name = attendee.get('displayName')
            if not name and non_self_count == 1 and other_person_name:
                name = other_person_name
            if not name:
                name = email.split('@')[0]
            
            domain = email.split('@')[-1] if '@' in email else ''
            is_external = domain not in INTERNAL_DOMAINS
            if is_external: external_count += 1

            participants.append({
                'name': name,
                'email': email,
                'is_external': is_external
            })

        meeting_type = 'other'
        if len(participants) == 1: meeting_type = '1on1'
        elif external_count > 0: meeting_type = 'external'
        elif any(w in summary for w in ['standup', 'sync', 'daily']): meeting_type = 'standup'
        elif any(w in summary for w in ['review', 'retro', 'demo']): meeting_type = 'review'
        elif any(w in summary for w in ['planning', 'sprint', 'grooming']): meeting_type = 'planning'
        elif len(participants) > 5: meeting_type = 'large_meeting'

        # Recurrence check
        is_series = bool(recurrence_id)
        
        # Topic extraction
        topics = []
        topic_patterns = [
            r'(?:discuss|review|update on|status of|planning for)\s+(.+?)(?:\s*[-|,]|$)',
            r'(?:re:|regarding:?)\s*(.+?)(?:\s*[-|,]|$)',
        ]
        combined = f"{summary} {description}"
        for pattern in topic_patterns:
            topics.extend(re.findall(pattern, combined, re.IGNORECASE))
        if not any(g in summary for g in ['1:1', 'sync', 'meeting']):
            topics.insert(0, event.get('summary', ''))

        return {
            'meeting_type': meeting_type,
            'is_series': is_series,
            'series_id': recurrence_id,
            'participants': participants,
            'topics': list(set(topics))[:5],
            'summary': event.get('summary', 'Untitled'),
            'description': description,
            'start': event.get('start', {}).get('dateTime', ''),
            'event_id': event.get('id', ''),
            'html_link': event.get('htmlLink', '')
        }

    def gather_context(self, classified: Dict) -> Dict:
        """Gather context from Brain, Daily Context, and GDrive."""
        context = {
            'participant_context': [],
            'topic_context': [],
            'action_items': [],
            'context_summary': '',
            'past_notes': ''
        }

        # Brain Context
        for p in classified['participants']:
            match = resolve_participant_to_brain(p['name'], p['email'], self.alias_index)
            if match:
                content = load_brain_file(match['file_path'])
                context['participant_context'].append({'name': p['name'], 'summary': content[:500]})
        
        # Topic Context (Simplified)
        # ... (implement similar to original if needed, skipping for brevity in this refactor pass)

        # Daily Context
        ctx_file = get_latest_context_file()
        if ctx_file:
            with open(ctx_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Simple extraction of Key Decisions
                match = re.search(r'##\s*(?:Key Decisions|Decisions)[^\n]*\n(.*?)(?=\n##|\Z)', content, re.DOTALL | re.IGNORECASE)
                if match: context['context_summary'] = match.group(1)[:1000]

        # Past Meeting Notes (GDrive)
        # Only for non-trivial meetings
        if classified['meeting_type'] in ['1on1', 'standup', 'review', 'planning', 'external']:
            notes_file = self.search_gdrive_notes(classified['summary'])
            if notes_file:
                print(f"  Found past notes in GDrive: {notes_file['name']}", file=sys.stderr)
                content = self.read_gdrive_file(notes_file['id'])
                # Summarize if too long, or just take the first 2000 chars
                context['past_notes'] = content[:2000]

        return context

    def synthesize_content(self, classified: Dict, context: Dict) -> str:
        """Synthesize content using Gemini or template."""
        content = ""
        model_id = "Template"
        
        if HAS_GEMINI and self._get_api_key():
            content = self._gemini_synthesize(classified, context)
            model_id = GEMINI_MODEL
        else:
            content = self._template_synthesize(classified, context)
            
        # Standard AI Disclaimer
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        disclaimer = f"*Automatically generated by {model_id} on {timestamp}*\n\n"
        
        return disclaimer + content

    def _get_api_key(self):
        api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
        if api_key: return api_key
        
        config_file = os.path.join(BASE_DIR, 'config.json')
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    return json.load(f).get('google_api_key')
            except Exception: pass
        return None

    def _gemini_synthesize(self, classified: Dict, context: Dict) -> str:
        api_key = self._get_api_key()
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GEMINI_MODEL)
        
        prompt = f"""Generate a meeting pre-read.
        Title: {classified['summary']}
        Type: {classified['meeting_type']}
        
        Participants: {[p['name'] for p in classified['participants']]}
        
        Participant Context:
        {json.dumps(context['participant_context'], indent=2)}
        
        Recent Context:
        {context['context_summary']}
        
        Past Meeting Notes (from GDrive):
        {context['past_notes']}
        
        Task:
        1. Context/Why (Incorporate insights from past notes if available)
        2. Participant Notes
        3. Last Meeting Recap (If past notes available, summarizing key decisions/actions)
        4. Agenda Suggestions
        5. Key Questions
        
        Output Markdown.
        """
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Gemini error: {e}", file=sys.stderr)
            return self._template_synthesize(classified, context)

    def _template_synthesize(self, classified: Dict, context: Dict) -> str:
        return f"""## Pre-Read: {classified['summary']}
        **Date:** {classified['start']}
        
        ### Participants
        {', '.join([p['name'] for p in classified['participants']])}
        
        ### Context
        {context['context_summary']}
        """

    def generate_file(self, classified: Dict, content: str) -> str:
        """Generate/Update file based on meeting type (Series vs AdHoc)."""
        start_dt = datetime.fromisoformat(classified['start'].replace('Z', '+00:00'))
        date_str = start_dt.strftime('%Y-%m-%d')
        slug = slugify(classified['summary'])

        if classified['is_series']:
            # Series File: Planning/Meeting_Prep/Series/Series-[Slug].md
            # Note: We use the Slug from the summary. If summary changes, it might create a new series file.
            # Ideally we'd use series_id, but that's opaque. Slug is readable.
            filename = f"Series-{slug}.md"
            filepath = os.path.join(SERIES_DIR, filename)
            
            new_entry = f"\n## [{date_str}] Upcoming Meeting\n\n{content}\n\n---\n"
            
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
                
                # Check if entry for this date already exists to avoid duplicates
                if f"[{date_str}] Upcoming Meeting" in existing_content:
                    print(f"  Entry for {date_str} already exists in {filename}", file=sys.stderr)
                    return filepath

                # Append new entry at the top (after header)
                # Assuming header is standard. If not, just prepend.
                if existing_content.startswith("# Meeting Series"):
                    # split after first line
                    parts = existing_content.split('\n', 1)
                    final_content = parts[0] + "\n" + new_entry + parts[1]
                else:
                    final_content = f"# Meeting Series: {classified['summary']}\n\n{new_entry}\n{existing_content}"
            else:
                final_content = f"# Meeting Series: {classified['summary']}\n**Cadence:** Recurring\n\n{new_entry}"
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(final_content)
                
        else:
            # AdHoc File: Planning/Meeting_Prep/AdHoc/Meeting-[Date]-[Slug].md
            filename = f"Meeting-{date_str}-{slug}.md"
            filepath = os.path.join(ADHOC_DIR, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
                
        return filepath

    def upload_to_drive(self, filepath: str) -> str:
        """Upload file to GDrive and return WebViewLink."""
        filename = os.path.basename(filepath)
        
        # Check if file exists in folder
        query = f"name = '{filename}' and '{self.prep_folder_id}' in parents and trashed = false"
        results = self.drive.files().list(q=query, fields="files(id, webViewLink)").execute()
        files = results.get('files', [])
        
        media = MediaFileUpload(filepath, mimetype='text/markdown')
        
        if files:
            # Update
            file_id = files[0]['id']
            self.drive.files().update(
                fileId=file_id,
                media_body=media
            ).execute()
            return files[0]['webViewLink']
        else:
            # Create
            file_metadata = {
                'name': filename,
                'parents': [self.prep_folder_id],
                'mimeType': 'text/markdown'  # Drive will view as text
            }
            file = self.drive.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            return file.get('webViewLink')

    def link_to_calendar(self, event_id: str, link: str):
        """Append pre-read link to calendar event description."""
        # Get current event
        event = self.calendar.events().get(calendarId='primary', eventId=event_id).execute()
        description = event.get('description', '')
        
        if link in description:
            return # Already linked
        
        # Append link
        new_desc = f"{description}\n\n<b>AI Pre-Read:</b> <a href='{link}'>{link}</a>"
        
        # Patch event
        self.calendar.events().patch(
            calendarId='primary',
            eventId=event_id,
            body={'description': new_desc}
        ).execute()
        print(f"  Linked to calendar event.", file=sys.stderr)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hours', type=int, default=24)
    parser.add_argument('--meeting', type=str)
    parser.add_argument('--list', action='store_true', help="List upcoming meetings without processing")
    parser.add_argument('--upload', action='store_true', help="Upload to Drive and link to Calendar")
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    print("Authenticating...", file=sys.stderr)
    creds = get_credentials()
    drive_service = get_drive_service(creds)
    calendar_service = get_calendar_service(creds)
    
    print("Loading Registry...", file=sys.stderr)
    registry = load_brain_registry()
    
    manager = MeetingManager(drive_service, calendar_service, registry)
    
    print(f"Fetching meetings (next {args.hours}h)...", file=sys.stderr)
    events = manager.fetch_events(args.hours)
    
    if args.meeting:
        events = [e for e in events if args.meeting.lower() in e.get('summary', '').lower()]

    if args.list:
        print(f"\n## Upcoming Meetings (Next {args.hours}h)\n")
        for event in events:
            start = event.get('start', {}).get('dateTime', 'TBD')
            if start and 'T' in start:
                dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                start = dt.strftime('%Y-%m-%d %H:%M')
            summary = event.get('summary', 'Untitled')
            print(f"- **{start}** | {summary}")
        return

    print(f"Processing {len(events)} meetings...", file=sys.stderr)
    
    for event in events:
        print(f"Processing: {event.get('summary')}", file=sys.stderr)
        
        classified = manager.classify_meeting(event)
        context = manager.gather_context(classified)
        
        if args.dry_run:
            print(f"--- Dry Run: {classified['summary']} ---")
            print(manager.synthesize_content(classified, context)[:200] + "...")
            continue
            
        content = manager.synthesize_content(classified, context)
        filepath = manager.generate_file(classified, content)
        print(f"  Generated: {filepath}", file=sys.stderr)
        
        if args.upload:
            try:
                print("  Uploading to Drive...", file=sys.stderr)
                link = manager.upload_to_drive(filepath)
                print(f"  Drive Link: {link}", file=sys.stderr)
                
                print("  Linking to Calendar...", file=sys.stderr)
                manager.link_to_calendar(classified['event_id'], link)
            except Exception as e:
                print(f"  Upload/Link failed: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()