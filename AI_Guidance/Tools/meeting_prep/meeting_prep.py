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
- Cleanup: Archives orphaned meeting preps when meetings are cancelled.

Usage:
    python meeting_prep.py                    # Prep all meetings in next 24h
    python meeting_prep.py --hours 8          # Next 8 hours only
    python meeting_prep.py --meeting "1on1"   # Prep specific meeting by title
    python meeting_prep.py --list             # List upcoming meetings without prep
    python meeting_prep.py --dry-run          # Show what would be generated
    python meeting_prep.py --cleanup          # Archive orphaned meeting preps
"""

import os
import sys
import re
import json
import argparse
import shutil
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from glob import glob

# Google API imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ... (imports)

# Add common directory to path to import config_loader
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../common')))
import config_loader

HAS_YAML = False
try:
    import yaml
    HAS_YAML = True
except ImportError:
    print("Warning: PyYAML not installed. Some functionalities may be limited.", file=sys.stderr)

HAS_GEMINI = False
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    print("Warning: Google Generative AI library not installed. Gemini synthesis will not be available.", file=sys.stderr)

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

# Credentials from centralized config
google_paths = config_loader.get_google_paths()
CREDENTIALS_FILE = google_paths['credentials']
TOKEN_FILE = google_paths['token']

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
GEMINI_MODEL = config_loader.get_gemini_config()['model']


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

        # Ensure directory exists for token file
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
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


def extract_frontmatter(content: str) -> Dict:
    """Extract YAML frontmatter from markdown file."""
    if not content.startswith('---'):
        return {}
    end = content.find('---', 3)
    if end < 0:
        return {}
    try:
        return yaml.safe_load(content[3:end]) or {}
    except Exception:
        return {}


def extract_section(content: str, section_name: str) -> str:
    """Extract a markdown section by header name."""
    pattern = rf'##\s*{re.escape(section_name)}[^\n]*\n(.*?)(?=\n## |\Z)'
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()[:500]
    return ''


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

    def search_gdrive_notes_enhanced(self, meeting_title: str, participants: List[Dict]) -> Optional[Dict]:
        """Search GDrive with multiple strategies for finding meeting notes."""
        searches = []

        # Strategy 1: Original title-based search (cleaned)
        cleaned = re.sub(r'\s*(1:1s?|sync|weekly|meeting)\s*', '', meeting_title, flags=re.IGNORECASE).strip()
        if cleaned:
            searches.append(cleaned.replace(":", " ").replace("/", " "))

        # Strategy 2: Participant names + "1:1" / "Nikita"
        for p in participants:
            name = p['name'].split()[0] if p['name'] else ''  # First name
            if name and len(name) > 2:
                searches.append(f"{name} 1:1")
                searches.append(f"{name} Nikita")

        # Strategy 3: Extract names from title, search by name pair
        title_names = extract_names_from_title(meeting_title)
        if len(title_names) >= 2:
            searches.append(f"{title_names[0]} {title_names[1]}")
        elif len(title_names) == 1 and title_names[0].lower() != 'nikita':
            searches.append(f"{title_names[0]} Nikita")

        # Try each search strategy
        for query_text in searches:
            if not query_text or len(query_text) < 3:
                continue

            query = (f"name contains '{query_text}' "
                     f"and mimeType = 'application/vnd.google-apps.document' "
                     f"and trashed = false")

            try:
                results = self.drive.files().list(
                    q=query,
                    orderBy='modifiedTime desc',
                    pageSize=5,
                    fields="files(id, name, modifiedTime)"
                ).execute()

                files = results.get('files', [])
                if files:
                    # Return most recent matching file
                    print(f"  GDrive search '{query_text}' found: {files[0]['name']}", file=sys.stderr)
                    return files[0]

            except Exception as e:
                print(f"  GDrive search '{query_text}' error: {e}", file=sys.stderr)
                continue

        print(f"  No GDrive notes found for: {meeting_title}", file=sys.stderr)
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

            # Skip solo events (no other participants - typically "Busy" blocks)
            other_attendees = [a for a in attendees if not a.get('self', False)
                              and 'resource.calendar.google.com' not in a.get('email', '')]
            if len(other_attendees) == 0:
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

    def extract_action_items_for_participants(self, participant_names: List[str]) -> List[Dict]:
        """Extract action items from daily context mentioning participants."""
        ctx_file = get_latest_context_file()
        if not ctx_file:
            return []

        with open(ctx_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find Action Items section
        action_section = re.search(
            r'## Action Items.*?\n(.*?)(?=\n---|\Z)',
            content, re.DOTALL
        )
        if not action_section:
            return []

        items = []
        # Parse format: - [ ] **Name**: Task description
        pattern = r'- \[([x ])\] \*\*([^*]+)\*\*:?\s*(.+?)(?=\n- \[|\n###|\Z)'
        for match in re.finditer(pattern, action_section.group(1), re.DOTALL):
            completed = match.group(1) == 'x'
            owner = match.group(2).strip()
            task = match.group(3).strip().replace('\n', ' ')

            # Check if owner matches any participant (fuzzy match)
            for pname in participant_names:
                pname_parts = pname.lower().split()
                owner_lower = owner.lower()
                # Match if first name or full name matches
                if any(part in owner_lower for part in pname_parts) or \
                   any(part in pname.lower() for part in owner_lower.split()):
                    items.append({
                        'owner': owner,
                        'task': task[:200],
                        'completed': completed
                    })
                    break

        return items

    def get_related_projects(self, participant_names: List[str]) -> List[Dict]:
        """Find projects related to participants from Brain registry."""
        projects = []
        seen_projects = set()

        for name in participant_names:
            entity_match = resolve_participant_to_brain(name, '', self.alias_index)
            if not entity_match:
                continue

            entity_content = load_brain_file(entity_match['file_path'])
            if not entity_content:
                continue

            # Parse frontmatter for 'related' field
            frontmatter = extract_frontmatter(entity_content)
            related = frontmatter.get('related', [])

            for rel in related:
                if 'Projects/' in rel:
                    # Clean the path: remove [[ ]] and quotes
                    project_path = rel.replace('[[', '').replace(']]', '').replace('"', '')
                    if project_path in seen_projects:
                        continue
                    seen_projects.add(project_path)

                    project_content = load_brain_file(project_path)
                    if project_content:
                        project_frontmatter = extract_frontmatter(project_content)
                        # Extract executive summary or first section
                        summary = extract_section(project_content, 'Executive Summary')
                        if not summary:
                            summary = extract_section(project_content, 'Overview')
                        if not summary:
                            # Just take first 500 chars after frontmatter
                            body_start = project_content.find('---', 3)
                            if body_start > 0:
                                summary = project_content[body_start+3:body_start+503].strip()

                        projects.append({
                            'name': project_frontmatter.get('title', os.path.basename(project_path).replace('.md', '')),
                            'status': project_frontmatter.get('status', 'Unknown'),
                            'summary': summary[:400]
                        })

        return projects

    def gather_context(self, classified: Dict, with_jira: bool = False) -> Dict:
        """Gather context from Brain, Daily Context, GDrive, Series History, and optionally Jira."""
        context = {
            'participant_context': [],
            'topic_context': [],
            'action_items': [],
            'context_summary': '',
            'past_notes': '',
            'series_history': [],
            'jira_issues': []
        }

        participant_names = [p['name'] for p in classified['participants']]

        # Brain Context - Enhanced extraction
        for p in classified['participants']:
            match = resolve_participant_to_brain(p['name'], p['email'], self.alias_index)
            if match:
                content = load_brain_file(match['file_path'])
                frontmatter = extract_frontmatter(content)
                context['participant_context'].append({
                    'name': p['name'],
                    'role': frontmatter.get('role', 'Unknown'),
                    'summary': content[:1500],
                    'current_topics': extract_section(content, 'Current Discussions'),
                    'key_topics': extract_section(content, 'Key Topics')
                })

        # Topic/Project Context
        context['topic_context'] = self.get_related_projects(participant_names)

        # Action Items for participants
        context['action_items'] = self.extract_action_items_for_participants(participant_names)

        # Daily Context - Key Decisions
        ctx_file = get_latest_context_file()
        if ctx_file:
            with open(ctx_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Extract Key Decisions section
                match = re.search(r'##\s*(?:Key Decisions|Decisions)[^\n]*\n(.*?)(?=\n##|\Z)', content, re.DOTALL | re.IGNORECASE)
                if match:
                    context['context_summary'] = match.group(1)[:1500]

        # Past Meeting Notes (GDrive) - Enhanced search
        if classified['meeting_type'] in ['1on1', 'standup', 'review', 'planning', 'external']:
            notes_file = self.search_gdrive_notes_enhanced(classified['summary'], classified['participants'])
            if notes_file:
                print(f"  Found past notes in GDrive: {notes_file['name']}", file=sys.stderr)
                content = self.read_gdrive_file(notes_file['id'])
                context['past_notes'] = content[:2500]

        # Series History - for recurring meetings
        if classified['is_series']:
            slug = slugify(classified['summary'])
            context['series_history'] = self.get_series_history(slug)
            if context['series_history']:
                print(f"  Found {len(context['series_history'])} previous entries in series history", file=sys.stderr)

        # Jira Issues - optional, for participant's recent tickets
        if with_jira:
            print("  Fetching Jira issues for participants...", file=sys.stderr)
            context['jira_issues'] = self.get_participant_jira_issues(participant_names)
            if context['jira_issues']:
                print(f"  Found {len(context['jira_issues'])} recent Jira issues", file=sys.stderr)

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
        gemini_config = config_loader.get_gemini_config()
        return gemini_config.get('api_key')

    def _gemini_synthesize(self, classified: Dict, context: Dict) -> str:
        api_key = self._get_api_key()
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GEMINI_MODEL)

        # Format action items for prompt
        action_items_str = ""
        if context.get('action_items'):
            for item in context['action_items']:
                status = "[x]" if item['completed'] else "[ ]"
                action_items_str += f"- {status} **{item['owner']}**: {item['task']}\n"
        else:
            action_items_str = "None found for participants."

        # Format related projects
        projects_str = ""
        if context.get('topic_context'):
            for proj in context['topic_context']:
                projects_str += f"### {proj['name']} ({proj['status']})\n{proj['summary']}\n\n"
        else:
            projects_str = "No related projects found."

        # Format series history
        series_history_str = ""
        if context.get('series_history'):
            for entry in context['series_history']:
                series_history_str += f"### {entry['date']}\n{entry['summary'][:400]}\n\n"
        else:
            series_history_str = "No previous series entries found."

        # Format Jira issues
        jira_str = ""
        if context.get('jira_issues'):
            for issue in context['jira_issues']:
                jira_str += f"- [{issue['key']}]({issue.get('url', '')}) - {issue['summary']} ({issue['status']}, {issue.get('priority', 'N/A')}) - Assignee: {issue['assignee']}\n"
        else:
            jira_str = "No recent Jira issues found (or --with-jira not enabled)."

        prompt = f"""Generate a meeting pre-read for: {classified['summary']}
Meeting Type: {classified['meeting_type']}

## Participants
{json.dumps(context['participant_context'], indent=2)}

## Related Projects
{projects_str}

## Recent Context (Key Decisions from Daily Context)
{context['context_summary']}

## Past Meeting Notes (from GDrive)
{context['past_notes'] if context['past_notes'] else 'No past notes found.'}

## Previous Series History (from local files)
{series_history_str}

## Outstanding Action Items for Participants
{action_items_str}

## Recent Jira Activity
{jira_str}

---
Generate a comprehensive pre-read with these sections:

1. **Context / Why** - Meeting purpose, incorporating project context and past discussions
2. **Participant Notes** - Role-specific preparation points for each participant, include their pending action items
3. **Last Meeting Recap** - Key decisions/outcomes from past notes (if available)
4. **Agenda Suggestions** - Time-boxed agenda items (total ~30-50 min), specific to current context
5. **Key Questions** - Specific questions informed by projects, action items, and recent context

Important:
- Use participant roles correctly (from the participant context)
- Reference specific projects and their status where relevant
- Include outstanding action items as follow-up points
- Be specific rather than generic

Output clean Markdown.
"""
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Gemini error: {e}", file=sys.stderr)
            return self._template_synthesize(classified, context)

    def get_series_history(self, series_slug: str, max_entries: int = 3) -> List[Dict]:
        """Extract previous meeting entries from series file."""
        series_filepath = os.path.join(SERIES_DIR, f"Series-{series_slug}.md")
        if not os.path.exists(series_filepath):
            return []

        with open(series_filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find all date-headed sections: ## [YYYY-MM-DD]
        pattern = r'## \[(\d{4}-\d{2}-\d{2})\][^\n]*\n(.*?)(?=## \[|\Z)'
        matches = list(re.finditer(pattern, content, re.DOTALL))

        history = []
        for match in matches:
            date = match.group(1)
            entry_content = match.group(2)

            # Skip "Upcoming Meeting" entries - we want past ones
            if 'Upcoming Meeting' in match.group(0):
                continue

            # Extract key points (bullet points and key headers)
            key_points = re.findall(r'^\s*[-*]\s+(.+)$', entry_content, re.MULTILINE)[:5]

            history.append({
                'date': date,
                'summary': entry_content[:600],
                'key_points': key_points
            })

            if len(history) >= max_entries:
                break

        return history

    def get_participant_jira_issues(self, participant_names: List[str]) -> List[Dict]:
        """Fetch recent Jira issues assigned to or mentioning participants."""
        jira_config = config_loader.get_jira_config()
        if not jira_config['url'] or not jira_config['api_token']:
            return []

        try:
            from atlassian import Jira
            jira = Jira(
                url=jira_config['url'],
                username=jira_config['username'],
                password=jira_config['api_token'],
                cloud=True
            )

            issues = []
            seen_keys = set()

            for name in participant_names:
                # Try different name formats for JQL
                name_parts = name.split()
                first_name = name_parts[0] if name_parts else name

                # JQL: Issues assigned to person OR reported by person, updated in last 14 days
                # Try with display name containing first name
                jql = f'(assignee ~ "{first_name}" OR reporter ~ "{first_name}") AND updated >= -14d ORDER BY updated DESC'

                try:
                    results = jira.jql(jql, limit=5)
                    for issue in results.get('issues', []):
                        key = issue['key']
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)

                        fields = issue['fields']
                        assignee = fields.get('assignee', {})
                        assignee_name = assignee.get('displayName', 'Unassigned') if assignee else 'Unassigned'

                        issues.append({
                            'key': key,
                            'summary': fields['summary'][:100],
                            'status': fields['status']['name'],
                            'priority': fields.get('priority', {}).get('name', 'None'),
                            'assignee': assignee_name,
                            'url': f"{jira_config['url']}browse/{key}"
                        })
                except Exception as e:
                    print(f"  Jira search for '{first_name}' error: {e}", file=sys.stderr)
                    continue

            return issues[:10]  # Limit total issues

        except ImportError:
            print("  Jira integration: atlassian-python-api not installed", file=sys.stderr)
            return []
        except Exception as e:
            print(f"  Jira integration error: {e}", file=sys.stderr)
            return []

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

    def archive_file(self, filepath: str, reason: str = "cancelled") -> str:
        """Move a file to archive with timestamp prefix."""
        if not os.path.exists(filepath):
            return ""

        filename = os.path.basename(filepath)
        timestamp = datetime.now().strftime('%Y%m%d-%H%M')
        archived_name = f"{timestamp}-{reason}-{filename}"
        archive_path = os.path.join(ARCHIVE_DIR, archived_name)

        shutil.move(filepath, archive_path)
        print(f"  Archived: {filename} -> {archived_name}", file=sys.stderr)
        return archive_path

    def fetch_recurring_series_events(self, series_id: str, days_ahead: int = 90) -> List[Dict]:
        """Fetch future instances of a recurring series."""
        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=days_ahead)

        try:
            events_result = self.calendar.events().list(
                calendarId='primary',
                timeMin=now.isoformat(),
                timeMax=time_max.isoformat(),
                maxResults=10,
                singleEvents=True,
                orderBy='startTime',
                q=''  # We'll filter by recurringEventId after
            ).execute()

            events = events_result.get('items', [])
            # Filter to only events from this series
            series_events = [e for e in events if e.get('recurringEventId') == series_id]
            return series_events
        except Exception as e:
            print(f"  Error fetching series events: {e}", file=sys.stderr)
            return []

    def get_upcoming_event_summaries(self, days_ahead: int = 30) -> Dict[str, Dict]:
        """Get all upcoming event summaries for matching against prep files."""
        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=days_ahead)

        events_result = self.calendar.events().list(
            calendarId='primary',
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            maxResults=200,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        # Build lookup by slug and by series_id
        by_slug = {}
        by_series_id = {}

        for event in events:
            summary = event.get('summary', '')
            slug = slugify(summary)
            series_id = event.get('recurringEventId')

            # Check if declined
            attendees = event.get('attendees', [])
            declined = any(a.get('self') and a.get('responseStatus') == 'declined' for a in attendees)
            if declined:
                continue

            # Skip cancelled events
            if event.get('status') == 'cancelled':
                continue

            if slug not in by_slug:
                by_slug[slug] = []
            by_slug[slug].append(event)

            if series_id:
                if series_id not in by_series_id:
                    by_series_id[series_id] = []
                by_series_id[series_id].append(event)

        return {'by_slug': by_slug, 'by_series_id': by_series_id}

    def cleanup_orphaned_preps(self, dry_run: bool = False) -> Dict[str, List[str]]:
        """
        Scan for meeting prep files without corresponding calendar events.

        For ad-hoc meetings: Archive if no matching event found
        For series:
          - If entire series gone: Archive the series file
          - If just instance cancelled: Update to next instance date
        """
        results = {'archived': [], 'updated': [], 'kept': []}

        print("Fetching upcoming calendar events...", file=sys.stderr)
        event_lookup = self.get_upcoming_event_summaries(days_ahead=60)
        by_slug = event_lookup['by_slug']

        # --- Process AdHoc files ---
        print("\nChecking AdHoc meeting preps...", file=sys.stderr)
        adhoc_files = glob(os.path.join(ADHOC_DIR, "Meeting-*.md"))

        for filepath in adhoc_files:
            filename = os.path.basename(filepath)
            # Extract slug from filename: Meeting-YYYY-MM-DD-[slug].md
            match = re.match(r'Meeting-\d{4}-\d{2}-\d{2}-(.+)\.md', filename)
            if not match:
                continue

            slug = match.group(1)

            if slug in by_slug and len(by_slug[slug]) > 0:
                print(f"  ✓ {filename} - Event exists", file=sys.stderr)
                results['kept'].append(filepath)
            else:
                print(f"  ✗ {filename} - No matching event, archiving", file=sys.stderr)
                if not dry_run:
                    self.archive_file(filepath, reason="cancelled")
                results['archived'].append(filepath)

        # --- Process Series files ---
        print("\nChecking Series meeting preps...", file=sys.stderr)
        series_files = glob(os.path.join(SERIES_DIR, "Series-*.md"))

        for filepath in series_files:
            filename = os.path.basename(filepath)
            # Extract slug from filename: Series-[slug].md
            match = re.match(r'Series-(.+)\.md', filename)
            if not match:
                continue

            slug = match.group(1)

            if slug in by_slug and len(by_slug[slug]) > 0:
                # Series still has future events
                next_event = by_slug[slug][0]  # First is soonest
                next_date = next_event.get('start', {}).get('dateTime', '')

                if next_date:
                    next_dt = datetime.fromisoformat(next_date.replace('Z', '+00:00'))
                    next_date_str = next_dt.strftime('%Y-%m-%d')

                    # Check if file needs date update (current "Upcoming Meeting" date)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Find current upcoming date in file
                    date_match = re.search(r'\[(\d{4}-\d{2}-\d{2})\] Upcoming Meeting', content)
                    if date_match:
                        current_date = date_match.group(1)
                        if current_date != next_date_str:
                            print(f"  ↻ {filename} - Updating date {current_date} -> {next_date_str}", file=sys.stderr)
                            if not dry_run:
                                # Update the date in the file
                                updated_content = content.replace(
                                    f"[{current_date}] Upcoming Meeting",
                                    f"[{next_date_str}] Upcoming Meeting"
                                )
                                with open(filepath, 'w', encoding='utf-8') as f:
                                    f.write(updated_content)
                            results['updated'].append(filepath)
                        else:
                            print(f"  ✓ {filename} - Up to date", file=sys.stderr)
                            results['kept'].append(filepath)
                    else:
                        print(f"  ✓ {filename} - Event exists", file=sys.stderr)
                        results['kept'].append(filepath)
            else:
                # No future events for this series - archive it
                print(f"  ✗ {filename} - Series cancelled/ended, archiving", file=sys.stderr)
                if not dry_run:
                    self.archive_file(filepath, reason="series-ended")
                results['archived'].append(filepath)

        # --- Process any legacy files in root Meeting_Prep folder ---
        print("\nChecking root folder for legacy files...", file=sys.stderr)
        root_files = glob(os.path.join(OUTPUT_DIR, "meeting-prep-*.md"))

        for filepath in root_files:
            filename = os.path.basename(filepath)
            print(f"  ✗ {filename} - Legacy format, archiving", file=sys.stderr)
            if not dry_run:
                self.archive_file(filepath, reason="legacy")
            results['archived'].append(filepath)

        return results


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hours', type=int, default=24)
    parser.add_argument('--meeting', type=str)
    parser.add_argument('--list', action='store_true', help="List upcoming meetings without processing")
    parser.add_argument('--upload', action='store_true', help="Upload to Drive and link to Calendar")
    parser.add_argument('--cleanup', action='store_true', help="Archive orphaned meeting preps")
    parser.add_argument('--with-jira', action='store_true', help="Include recent Jira issues for participants")
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

    if args.cleanup:
        print("Running cleanup...", file=sys.stderr)
        results = manager.cleanup_orphaned_preps(dry_run=args.dry_run)
        print(f"\n## Cleanup Summary {'(DRY RUN)' if args.dry_run else ''}", file=sys.stderr)
        print(f"  Archived: {len(results['archived'])}", file=sys.stderr)
        print(f"  Updated:  {len(results['updated'])}", file=sys.stderr)
        print(f"  Kept:     {len(results['kept'])}", file=sys.stderr)
        return

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
        context = manager.gather_context(classified, with_jira=args.with_jira)

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