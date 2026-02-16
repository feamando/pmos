"""
PM-OS Google Brain Sync

Syncs calendar events and drive files from Google.

Note: Google sync requires OAuth2 authentication which is handled separately.
This module provides the sync logic once credentials are available.
"""

from pathlib import Path
from typing import Optional, Callable, Dict, List, Any
from datetime import datetime, timedelta

from pm_os.wizard.brain_sync.base import BaseSyncer, SyncResult, SyncProgress
from pm_os.wizard.exceptions import CredentialError, SyncError


class GoogleSyncer(BaseSyncer):
    """Sync brain entities from Google services."""

    def __init__(
        self,
        brain_path: Path,
        credentials_path: Optional[Path] = None,
        token_path: Optional[Path] = None
    ):
        """Initialize Google syncer.

        Args:
            brain_path: Path to brain directory
            credentials_path: Path to OAuth credentials.json
            token_path: Path to store/load auth token
        """
        super().__init__(brain_path)
        self.credentials_path = credentials_path
        # Store token in .secrets/ (sibling to brain/) instead of inside brain/
        secrets_dir = brain_path.parent / ".secrets"
        self.token_path = token_path or (secrets_dir / "token.json")
        self._calendar_service = None
        self._drive_service = None

    def _get_credentials(self):
        """Get or refresh OAuth credentials."""
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            raise SyncError(
                "Google API libraries not installed",
                service="Google",
                remediation="pip install google-auth google-auth-oauthlib google-api-python-client"
            )

        from pm_os.google_auth import GOOGLE_SCOPES

        creds = None

        # Load existing token
        if self.token_path and self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), GOOGLE_SCOPES)

        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.credentials_path or not self.credentials_path.exists():
                    raise CredentialError(
                        "Google OAuth credentials not configured",
                        credential_type="Google",
                        remediation="Download credentials.json from Google Cloud Console"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), GOOGLE_SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save token
            if self.token_path:
                self.token_path.parent.mkdir(parents=True, exist_ok=True)
                self.token_path.write_text(creds.to_json())

        return creds

    def _get_calendar_service(self):
        """Get Google Calendar service."""
        if self._calendar_service is None:
            from googleapiclient.discovery import build
            creds = self._get_credentials()
            self._calendar_service = build('calendar', 'v3', credentials=creds)
        return self._calendar_service

    def _get_drive_service(self):
        """Get Google Drive service."""
        if self._drive_service is None:
            from googleapiclient.discovery import build
            creds = self._get_credentials()
            self._drive_service = build('drive', 'v3', credentials=creds)
        return self._drive_service

    def test_connection(self) -> tuple:
        """Test connection to Google services."""
        try:
            service = self._get_calendar_service()
            # Get primary calendar
            calendar = service.calendars().get(calendarId='primary').execute()
            summary = calendar.get('summary', 'Calendar')
            return True, f"Connected to Google Calendar: {summary}"
        except CredentialError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    def sync(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        incremental: bool = True
    ) -> SyncResult:
        """Sync Google data to brain.

        Args:
            progress_callback: Progress callback (current, total, phase)
            incremental: Only sync recent/future events

        Returns:
            SyncResult with details
        """
        result = SyncResult(success=True, message="")
        progress = SyncProgress(callback=progress_callback)
        progress.total = 2  # Calendar + Drive

        try:
            # Phase 1: Sync Calendar
            progress.update(0, "Syncing calendar events")
            self._sync_calendar(result, incremental)
            progress.increment()

            # Phase 2: Sync Drive (recent files)
            progress.update(1, "Syncing recent Drive files")
            self._sync_drive(result, incremental)
            progress.increment()

            # Build summary message
            total_entities = result.entities_created + result.entities_updated
            result.message = f"Synced {total_entities} entities from Google"

        except CredentialError:
            raise
        except SyncError:
            raise
        except Exception as e:
            result.success = False
            result.message = f"Sync failed: {str(e)}"
            result.errors.append(str(e))

        return result

    def _sync_calendar(self, result: SyncResult, incremental: bool = True):
        """Sync calendar events."""
        try:
            service = self._get_calendar_service()

            # Time range
            now = datetime.utcnow()
            if incremental:
                time_min = now.isoformat() + 'Z'  # Future events only
                time_max = (now + timedelta(days=30)).isoformat() + 'Z'
            else:
                time_min = (now - timedelta(days=7)).isoformat() + 'Z'
                time_max = (now + timedelta(days=30)).isoformat() + 'Z'

            events_result = service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                maxResults=100,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            for event in events:
                self._sync_event(event, result)

        except Exception as e:
            result.errors.append(f"Error syncing calendar: {str(e)}")

    def _sync_event(self, event: Dict, result: SyncResult):
        """Sync a single calendar event."""
        event_id = event.get('id')
        title = event.get('summary', 'Untitled Event')

        start = event.get('start', {})
        end = event.get('end', {})
        start_time = start.get('dateTime') or start.get('date')
        end_time = end.get('dateTime') or end.get('date')

        # Get attendees
        attendees = event.get('attendees', [])
        attendee_names = [a.get('email', '').split('@')[0] for a in attendees[:10]]

        body = f"""# {title}

## Details

- **When**: {start_time[:16] if start_time else 'TBD'} - {end_time[11:16] if end_time and 'T' in end_time else 'TBD'}
- **Location**: {event.get('location', 'Not specified')}
- **Status**: {event.get('status', 'confirmed')}

## Attendees

{chr(10).join(f'- {a}' for a in attendee_names) or '- None'}

## Description

{(event.get('description') or 'No description')[:500]}

## Links

- [View in Google Calendar]({event.get('htmlLink', '#')})
"""

        # Parse date for frontmatter
        event_date = start_time[:10] if start_time else datetime.now().strftime('%Y-%m-%d')

        self.write_entity(
            entity_type="meeting",
            name=title,
            source="google",
            body=body,
            sync_id=event_id,
            date=event_date,
            start_time=start_time,
            end_time=end_time,
            location=event.get('location'),
            attendees=attendee_names,
            recurring=event.get('recurringEventId') is not None,
            url=event.get('htmlLink'),
            relationships={"attendees": attendee_names} if attendee_names else {}
        )

        result.entities_created += 1

    def _sync_drive(self, result: SyncResult, incremental: bool = True):
        """Sync recent Drive files."""
        try:
            service = self._get_drive_service()

            # Query for recent files
            query = "trashed=false"
            if incremental:
                # Only recently modified files
                cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat() + 'Z'
                query += f" and modifiedTime > '{cutoff}'"

            files_result = service.files().list(
                q=query,
                pageSize=50,
                orderBy='modifiedTime desc',
                fields='files(id,name,mimeType,modifiedTime,owners,webViewLink,parents)'
            ).execute()

            files = files_result.get('files', [])

            for file in files:
                self._sync_file(file, result)

        except Exception as e:
            result.errors.append(f"Error syncing Drive: {str(e)}")

    def _sync_file(self, file: Dict, result: SyncResult):
        """Sync a single Drive file."""
        file_id = file.get('id')
        name = file.get('name', 'Untitled')
        mime_type = file.get('mimeType', '')

        # Determine file type
        if 'document' in mime_type:
            file_type = 'Google Doc'
        elif 'spreadsheet' in mime_type:
            file_type = 'Google Sheet'
        elif 'presentation' in mime_type:
            file_type = 'Google Slides'
        elif 'folder' in mime_type:
            return  # Skip folders
        else:
            file_type = 'File'

        owners = file.get('owners', [])
        owner_name = owners[0].get('displayName', 'Unknown') if owners else 'Unknown'

        body = f"""# {name}

## Details

- **Type**: {file_type}
- **Owner**: {owner_name}
- **Modified**: {file.get('modifiedTime', 'Unknown')[:10]}

## Links

- [View in Google Drive]({file.get('webViewLink', '#')})
"""

        self.write_entity(
            entity_type="document",
            name=name,
            source="google",
            body=body,
            sync_id=file_id,
            file_type=file_type,
            author=owner_name,
            last_modified=file.get('modifiedTime'),
            url=file.get('webViewLink')
        )

        result.entities_created += 1
