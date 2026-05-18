#!/usr/bin/env python3
"""
Google OAuth Scope Validator

Validates that the current Google token has all required scopes.
If scopes are missing, triggers re-authentication.
"""

import json
import os
import sys
from pathlib import Path

try:
    from pm_os_base.tools.core.config_loader import get_config, get_google_paths
except ImportError:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
        from config_loader import get_config, get_google_paths
    except ImportError:
        get_config = None
        get_google_paths = None

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Required scopes for full PM-OS functionality
REQUIRED_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def get_token_scopes(token_file: str) -> list:
    """Read scopes from existing token file."""
    if not os.path.exists(token_file):
        return []

    try:
        with open(token_file, "r") as f:
            token_data = json.load(f)
        return token_data.get("scopes", [])
    except Exception:
        return []


def validate_scopes(token_file: str) -> tuple[bool, list]:
    """
    Check if token has all required scopes.
    Returns (is_valid, missing_scopes)
    """
    current_scopes = set(get_token_scopes(token_file))
    required_scopes = set(REQUIRED_SCOPES)
    missing = required_scopes - current_scopes
    return len(missing) == 0, list(missing)


def trigger_reauth(credentials_file: str, token_file: str) -> bool:
    """Trigger OAuth flow with full scopes."""
    if not os.path.exists(credentials_file):
        print(
            f"Error: Credentials file not found at {credentials_file}", file=sys.stderr
        )
        return False

    try:
        # Remove existing token to force full re-auth
        if os.path.exists(token_file):
            os.remove(token_file)

        flow = InstalledAppFlow.from_client_secrets_file(
            credentials_file, REQUIRED_SCOPES
        )
        creds = flow.run_local_server(port=0)

        # Save new token
        os.makedirs(os.path.dirname(token_file), exist_ok=True)
        with open(token_file, "w") as f:
            f.write(creds.to_json())

        return True
    except Exception as e:
        print(f"Error during re-authentication: {e}", file=sys.stderr)
        return False


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate Google OAuth scopes")
    parser.add_argument(
        "--fix", action="store_true", help="Trigger re-auth if scopes missing"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress output unless action needed"
    )
    args = parser.parse_args()

    # Get paths from config
    if not get_google_paths:
        print("Error: config_loader not available, cannot resolve Google paths", file=sys.stderr)
        return 1

    google_paths = get_google_paths()
    token_file = google_paths["token"]
    credentials_file = google_paths["credentials"]

    # Check if token exists
    if not os.path.exists(token_file):
        # Always report missing token, this is a failure, not noise
        print("Google token not found - authentication required")
        if args.fix:
            print("Triggering Google OAuth authentication...")
            if trigger_reauth(credentials_file, token_file):
                # Verify file was actually created
                if os.path.exists(token_file):
                    print("Authentication successful!")
                    return 0
                else:
                    print("Error: OAuth flow completed but token.json was not created", file=sys.stderr)
                    return 1
            else:
                print("Error: OAuth re-authentication failed", file=sys.stderr)
                return 1
        return 1

    # Validate scopes
    is_valid, missing = validate_scopes(token_file)

    if is_valid:
        if not args.quiet:
            print("Google OAuth scopes: OK (all 6 scopes present)")
        return 0

    # Scopes missing
    print(f"Google OAuth scopes: INCOMPLETE")
    print(f"Missing scopes: {len(missing)}")
    for scope in missing:
        scope_name = scope.split("/")[-1]
        print(f"  - {scope_name}")

    if args.fix:
        print("\nTriggering re-authentication with full scopes...")
        if trigger_reauth(credentials_file, token_file):
            print("Re-authentication successful! All scopes now available.")
            return 0
        else:
            return 1
    else:
        print("\nRun with --fix to trigger re-authentication")
        return 1


if __name__ == "__main__":
    sys.exit(main())
