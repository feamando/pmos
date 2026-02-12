import argparse
import io
import os
import sys

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(BASE_DIR, "gdrive_mcp", "token.json")
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def get_drive_service():
    if not os.path.exists(TOKEN_FILE):
        print(f"Error: Token file not found at {TOKEN_FILE}")
        return None
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    return build("drive", "v3", credentials=creds)


def download_file(service, file_id, output_path):
    print(f"Downloading file {file_id} to {output_path}...")
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        print(f"Download {int(status.progress() * 100)}%")

    with open(output_path, "wb") as f:
        f.write(fh.getvalue())
    print("Download complete.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python download_gdrive_file.py <file_id> <output_path>")
        sys.exit(1)

    file_id = sys.argv[1]
    output_path = sys.argv[2]

    service = get_drive_service()
    if service:
        download_file(service, file_id, output_path)
