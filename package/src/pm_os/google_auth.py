"""
PM-OS Google Authentication Helper

Centralizes Google OAuth logic: bundled credential detection,
OAuth browser flow, token management, and scope definitions.

The client secret is bundled in the pip package for Acme Corp internal
users (pmos). Public releases (feamando/pmos) omit the file, and
the code falls back gracefully.
"""

import json
import shutil
from pathlib import Path
from typing import Optional

# The canonical 6 scopes required by PM-OS.
# This is the single source of truth — google_sync.py, google_scope_validator.py,
# and daily_context_updater.py all need these.
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def get_bundled_client_secret_path() -> Optional[Path]:
    """Return the path to the bundled client secret, or None if not present.

    The file is included in the pmos (private) pip package but omitted
    from the feamando/pmos (public) release.
    """
    bundled = Path(__file__).parent / "data" / "google_client_secret.json"
    if bundled.exists():
        return bundled
    return None


def has_bundled_credentials() -> bool:
    """Check whether bundled Google OAuth credentials are available."""
    return get_bundled_client_secret_path() is not None


def copy_credentials_to_secrets(secrets_dir: Path) -> Path:
    """Copy the bundled client secret to the user's .secrets/ directory.

    Args:
        secrets_dir: Path to the .secrets/ directory (e.g., install_path/.secrets)

    Returns:
        Path to the copied credentials.json file.

    Raises:
        FileNotFoundError: If no bundled client secret exists.
    """
    bundled = get_bundled_client_secret_path()
    if bundled is None:
        raise FileNotFoundError("No bundled Google client secret found in this package.")

    secrets_dir.mkdir(parents=True, exist_ok=True)
    dest = secrets_dir / "credentials.json"
    shutil.copy2(str(bundled), str(dest))
    return dest


def run_oauth_flow(
    credentials_path: Path,
    token_path: Path,
    scopes: Optional[list] = None,
    port: int = 0,
):
    """Run the Google OAuth browser flow and save the resulting token.

    Opens a local web server, redirects the user to Google's consent screen,
    and saves the authorized token to disk.

    Args:
        credentials_path: Path to the client_secret / credentials.json file.
        token_path: Path where token.json will be saved.
        scopes: OAuth scopes (defaults to GOOGLE_SCOPES).
        port: Local server port (0 = auto-select).

    Returns:
        The authorized google.oauth2.credentials.Credentials object.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_path),
        scopes or GOOGLE_SCOPES,
    )
    creds = flow.run_local_server(port=port)

    # Save token
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())

    return creds


def load_or_refresh_credentials(
    credentials_path: Path,
    token_path: Path,
    scopes: Optional[list] = None,
):
    """Load an existing token and refresh it if expired.

    Does NOT open a browser. If the token doesn't exist or can't be
    refreshed, raises an exception.

    Args:
        credentials_path: Path to credentials.json (needed for refresh).
        token_path: Path to token.json.
        scopes: OAuth scopes (defaults to GOOGLE_SCOPES).

    Returns:
        Valid google.oauth2.credentials.Credentials object.

    Raises:
        FileNotFoundError: If token file doesn't exist.
        google.auth.exceptions.RefreshError: If token can't be refreshed.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    effective_scopes = scopes or GOOGLE_SCOPES

    if not token_path.exists():
        raise FileNotFoundError(f"Token file not found: {token_path}")

    creds = Credentials.from_authorized_user_file(str(token_path), effective_scopes)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())

    return creds
