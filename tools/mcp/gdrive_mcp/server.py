import argparse
import io
import json
import logging
import os.path
import sys
from typing import Any, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from mcp.server.fastmcp import FastMCP

# --- Configuration ---
# Add common directory to path to import config_loader
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import config_loader

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive.file",
]

# Get paths from centralized config
google_paths = config_loader.get_google_paths()
CREDENTIALS_FILE = google_paths["credentials"]
TOKEN_FILE = google_paths["token"]

# Initialize FastMCP
mcp = FastMCP("gdrive-mcp")


# --- Google Drive Service ---
def get_drive_service():
    """Shows basic usage of the Drive v3 API.
    Prints the names and ids of the first 10 files the user has access to.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            pass

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                if os.path.exists(TOKEN_FILE):
                    os.remove(TOKEN_FILE)
                return get_drive_service()
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(
                    f"Error: Credentials file not found at {CREDENTIALS_FILE}",
                    file=sys.stderr,
                )
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Ensure directory exists for token file
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    service = build("drive", "v3", credentials=creds)
    return service


# --- Tools ---


@mcp.tool()
def gdrive_list(page_size: int = 10, folder_id: Optional[str] = None) -> str:
    """
    List files in Google Drive.

    Args:
        page_size: Number of files to return (default 10).
        folder_id: Optional ID of the folder to list files from.
    """
    try:
        service = get_drive_service()

        query = "trashed = false"
        if folder_id:
            query += f" and '{folder_id}' in parents"

        results = (
            service.files()
            .list(
                pageSize=page_size,
                fields="nextPageToken, files(id, name, mimeType, webViewLink)",
                q=query,
            )
            .execute()
        )
        items = results.get("files", [])

        if not items:
            return "No files found."

        output = []
        for item in items:
            output.append(
                f"ID: {item['id']} | Name: {item['name']} | Type: {item['mimeType']} | Link: {item['webViewLink']}"
            )

        return "\n".join(output)
    except Exception as e:
        return f"Error listing files: {str(e)}"


@mcp.tool()
def gdrive_search(query: str, page_size: int = 10) -> str:
    """
    Search for files in Google Drive.

    Args:
        query: The search query (e.g., "name contains 'project'" or "mimeType = 'application/vnd.google-apps.folder'").
               See https://developers.google.com/drive/api/guides/search-files for syntax.
        page_size: Number of results to return.
    """
    try:
        service = get_drive_service()

        # Ensure we don't search trash unless requested (basic safety)
        if "trashed" not in query:
            full_query = f"trashed = false and ({query})"
        else:
            full_query = query

        results = (
            service.files()
            .list(
                pageSize=page_size,
                fields="nextPageToken, files(id, name, mimeType, webViewLink)",
                q=full_query,
            )
            .execute()
        )
        items = results.get("files", [])

        if not items:
            return "No matching files found."

        output = []
        for item in items:
            output.append(
                f"ID: {item['id']} | Name: {item['name']} | Type: {item['mimeType']} | Link: {item['webViewLink']}"
            )

        return "\n".join(output)
    except Exception as e:
        return f"Error searching files: {str(e)}"


@mcp.tool()
def gdrive_read(file_id: str) -> str:
    """
    Read the content of a text-based file or export a Google Doc/Sheet as text.

    Args:
        file_id: The ID of the file to read.
    """
    try:
        service = get_drive_service()

        # Get file metadata to check type
        file_metadata = service.files().get(fileId=file_id).execute()
        mime_type = file_metadata.get("mimeType")
        name = file_metadata.get("name")

        # Handle Google Docs/Sheets (Export)
        if mime_type == "application/vnd.google-apps.document":
            request = service.files().export_media(
                fileId=file_id, mimeType="text/plain"
            )
        elif mime_type == "application/vnd.google-apps.spreadsheet":
            request = service.files().export_media(fileId=file_id, mimeType="text/csv")
        # Handle binary files (Download) - only if text compatible ideally, but we'll try generic download for now
        # and let the error handler catch binary blobs if they aren't decodeable
        else:
            request = service.files().get_media(fileId=file_id)

        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()

        content_bytes = file_content.getvalue()

        # Try to decode as text
        try:
            text = content_bytes.decode("utf-8")
            return f"--- Content of {name} ---\n{text}"
        except UnicodeDecodeError:
            return f"File '{name}' (ID: {file_id}) appears to be binary and cannot be read as text via this tool."

    except Exception as e:
        return f"Error reading file: {str(e)}"


@mcp.tool()
def gdrive_upload(local_path: str, folder_id: Optional[str] = None) -> str:
    """
    Upload a file to Google Drive.

    Args:
        local_path: The local path to the file to upload.
        folder_id: Optional ID of the folder to upload to.
    """
    try:
        service = get_drive_service()

        file_name = os.path.basename(local_path)
        file_metadata = {"name": file_name}
        if folder_id:
            file_metadata["parents"] = [folder_id]

        media = MediaFileUpload(local_path, resumable=True)

        file = (
            service.files()
            .create(
                body=file_metadata, media_body=media, fields="id, name, webViewLink"
            )
            .execute()
        )

        return f"File uploaded successfully. ID: {file.get('id')} | Name: {file.get('name')} | Link: {file.get('webViewLink')}"

    except Exception as e:
        return f"Error uploading file: {str(e)}"


if __name__ == "__main__":
    # Use a heuristic: if arguments are provided that match our CLI commands, use CLI mode.
    # Otherwise, default to MCP mode (which might use args like 'run', 'inspect' etc via FastMCP/Typer).

    cli_commands = ["--cli"]

    if len(sys.argv) > 1 and sys.argv[1] in cli_commands:
        # Remove the flag so argparse doesn't choke
        sys.argv.pop(1)

        parser = argparse.ArgumentParser(
            description="Google Drive MCP Server & CLI Tool"
        )
        subparsers = parser.add_subparsers(
            dest="command", help="CLI commands", required=True
        )

        list_parser = subparsers.add_parser("list", help="List files")
        list_parser.add_argument("--page_size", type=int, default=10)
        list_parser.add_argument("--folder_id", type=str, default=None)

        search_parser = subparsers.add_parser("search", help="Search files")
        search_parser.add_argument("query", type=str)
        search_parser.add_argument("--page_size", type=int, default=10)

        read_parser = subparsers.add_parser("read", help="Read file content")
        read_parser.add_argument("file_id", type=str)

        upload_parser = subparsers.add_parser("upload", help="Upload a file")
        upload_parser.add_argument("local_path", type=str)
        upload_parser.add_argument("--folder_id", type=str, default=None)

        args = parser.parse_args()

        if args.command == "list":
            print(gdrive_list(page_size=args.page_size, folder_id=args.folder_id))
        elif args.command == "search":
            print(gdrive_search(query=args.query, page_size=args.page_size))
        elif args.command == "read":
            print(gdrive_read(file_id=args.file_id))
        elif args.command == "upload":
            print(gdrive_upload(local_path=args.local_path, folder_id=args.folder_id))
    else:
        # Run as MCP Server
        mcp.run()
