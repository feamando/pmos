import io
import os
import re
import sys
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Add tools directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# Config
ROOT_PATH = config_loader.get_root_path()
USER_PATH = ROOT_PATH / "user"
TOKEN_FILE = str(USER_PATH / ".secrets" / "gdrive_mcp" / "token.json")
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
BRAIN_DIR = USER_PATH / "brain"
ENTITIES_DIR = str(BRAIN_DIR / "Entities")
STRATEGY_DIR = str(BRAIN_DIR / "Strategy")
RAW_DIR = str(BRAIN_DIR / "Inbox" / "Strategy_Raw")

os.makedirs(STRATEGY_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)


def get_drive_service():
    if not os.path.exists(TOKEN_FILE):
        print(f"Error: Token file not found at {TOKEN_FILE}")
        return None
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    return build("drive", "v3", credentials=creds)


def search_file(service, name):
    print(f"Searching for '{name}'...")
    # Escape single quotes in name
    safe_name = name.replace("'", "'")
    query = f"name = '{safe_name}' and mimeType = 'application/vnd.google-apps.document' and trashed = false"
    try:
        results = (
            service.files()
            .list(q=query, pageSize=1, fields="files(id, name)")
            .execute()
        )
        files = results.get("files", [])
        if files:
            return files[0]
    except Exception as e:
        print(f"  Search error: {e}")
    return None


def read_file_content(service, file_id):
    try:
        request = service.files().export_media(fileId=file_id, mimeType="text/plain")
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return fh.getvalue().decode("utf-8")
    except Exception as e:
        print(f"  Read error: {e}")
        return None


def clean_filename(name):
    return re.sub(r"[\\/*?:\"<>|]", "_", name).strip().replace(" ", "_")


def extract_titles_from_entities():
    titles = set()
    for fname in os.listdir(ENTITIES_DIR):
        if not fname.startswith("Domain_"):
            continue

        path = os.path.join(ENTITIES_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Regex to find links: [Type](Title)
        # Matches: [Domain Objective Document](My Doc Title)
        matches = re.findall(
            r"\[(Domain Objective Document|Yearly Plan Document)\]\((.*?)\)", content
        )
        for type_, title in matches:
            if title and "http" not in title and len(title) > 3:
                # Split by newlines if multiple titles were captured incorrectly
                sub_titles = [t.strip() for t in title.split("\n") if t.strip()]
                for t in sub_titles:
                    if len(t) > 3:
                        titles.add(t)
    return list(titles)


def main():
    service = get_drive_service()
    if not service:
        return

    titles = extract_titles_from_entities()
    print(f"Found {len(titles)} unique documents to fetch.")

    for title in titles:
        # Check if we already have it
        safe_name = clean_filename(title)
        raw_path = os.path.join(RAW_DIR, f"{safe_name}.md")

        if os.path.exists(raw_path):
            print(f"Skipping {title} (already fetched)")
            continue

        file_meta = search_file(service, title)
        if file_meta:
            print(f"  Found ID: {file_meta['id']}")
            content = read_file_content(service, file_meta["id"])
            if content:
                # Save Raw
                with open(raw_path, "w", encoding="utf-8") as f:
                    f.write(f"# {title}\n\n{content}")

                # Create Strategy Stub (Clean version)
                strategy_path = os.path.join(STRATEGY_DIR, f"{safe_name}.md")
                if not os.path.exists(strategy_path):
                    with open(strategy_path, "w", encoding="utf-8") as f:
                        f.write(
                            f"# {title}\n\n> Auto-imported from Google Drive\n\n{content[:2000]}...\n\n[Full content in Inbox/Strategy_Raw]"
                        )
                print(f"  Saved {safe_name}.md")
        else:
            print(f"  Not found in Drive.")

        time.sleep(1)  # Rate limit nice-ness


if __name__ == "__main__":
    main()
