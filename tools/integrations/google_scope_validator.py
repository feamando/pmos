#!/usr/bin/env python3
"""
Google OAuth Scope Validator

Validates that the current Google token has all required scopes.
If scopes are missing, triggers re-authentication.
"""

import json
import os
import sys

# Add parent directory to path for config_loader
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config_loader
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Required scopes for full PM-OS functionality
REQUIRED_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive.file",
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
    google_paths = config_loader.get_google_paths()
    token_file = google_paths["token"]
    credentials_file = google_paths["credentials"]

    # Check if token exists
    if not os.path.exists(token_file):
        if not args.quiet:
            print("Google token not found - authentication required")
        if args.fix:
            print("Triggering Google OAuth authentication...")
            if trigger_reauth(credentials_file, token_file):
                print("Authentication successful!")
                return 0
            else:
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
