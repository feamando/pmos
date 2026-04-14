#!/bin/bash
# upload-to-gdrive.sh — Upload release zip to GDrive using Python + Google API
# Usage: bash scripts/upload-to-gdrive.sh <zip-path> [folder-id]
# Returns: GDrive file ID on stdout

set -euo pipefail

ZIP_PATH="${1:?Usage: upload-to-gdrive.sh <zip-path> [folder-id]}"
FOLDER_ID="${2:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="$(dirname "$SCRIPT_DIR")"
PMOS_ROOT="${PM_OS_ROOT:-$(cd "$APP_ROOT/../.." && pwd)}"

if [ ! -f "$ZIP_PATH" ]; then
  echo "ERROR: File not found: $ZIP_PATH" >&2
  exit 1
fi

FILENAME=$(basename "$ZIP_PATH")
CREDS_PATH="$PMOS_ROOT/user/.secrets/credentials.json"
TOKEN_PATH="$PMOS_ROOT/user/.secrets/token.json"

if [ ! -f "$CREDS_PATH" ]; then
  echo "ERROR: Google credentials not found at $CREDS_PATH" >&2
  echo "Run Google OAuth setup first." >&2
  exit 1
fi

# Use PM-OS venv Python if available, otherwise system python3
VENV_PYTHON="$PMOS_ROOT/.venv/bin/python3"
if [ -f "$VENV_PYTHON" ]; then
  PYTHON="$VENV_PYTHON"
else
  PYTHON="python3"
fi

$PYTHON - "$ZIP_PATH" "$FILENAME" "$CREDS_PATH" "$TOKEN_PATH" "$FOLDER_ID" <<'PYEOF'
import sys, os, json

zip_path = sys.argv[1]
filename = sys.argv[2]
creds_path = sys.argv[3]
token_path = sys.argv[4]
folder_id = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] else None

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    print("ERROR: Google API libraries not installed. Run: pip install google-api-python-client google-auth-oauthlib", file=sys.stderr)
    sys.exit(1)

SCOPES = ['https://www.googleapis.com/auth/drive']

creds = None
if os.path.exists(token_path):
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
        creds = flow.run_local_server(port=0)
    with open(token_path, 'w') as f:
        f.write(creds.to_json())

service = build('drive', 'v3', credentials=creds)

file_metadata = {'name': filename}
if folder_id:
    file_metadata['parents'] = [folder_id]

media = MediaFileUpload(zip_path, mimetype='application/zip', resumable=True)
file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()

file_id = file.get('id')
print(file_id)
print(f"Uploaded: {filename} -> {file_id}", file=sys.stderr)
PYEOF
