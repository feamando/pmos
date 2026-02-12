#!/usr/bin/env python3
"""
Interview Processor
Analyzes interview transcripts against Acme Corp DNA and Career Framework.
Output: Team/Interviews/Notes/
Triggered by: update-context.ps1
"""

import argparse
import glob
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Add common directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config_loader

try:
    import google.generativeai as genai

    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    print("Warning: Google Generative AI library not installed.", file=sys.stderr)

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Configuration
ROOT_DIR = config_loader.get_root_path()
COMMON_DIR = config_loader.get_common_path()
USER_DIR = ROOT_DIR / "user"
INBOX_DIR = USER_DIR / "brain" / "Inbox"
OUTPUT_DIR = USER_DIR / "planning" / "Team" / "Interviews" / "Notes"
FRAMEWORKS_DIR = COMMON_DIR / "frameworks"

# Google Auth
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
google_paths = config_loader.get_google_paths()
CREDENTIALS_FILE = google_paths["credentials"]
TOKEN_FILE = google_paths["token"]


def get_drive_service():
    """Get authenticated Drive service."""
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
                pass
        # If still invalid, we assume token is managed by other tools (boot/meeting_prep)
        # We fail gracefully if we can't auth
        if not creds or not creds.valid:
            print(
                "Warning: Valid GDrive token not found. Skipping GDrive fetch.",
                file=sys.stderr,
            )
            return None

    return build("drive", "v3", credentials=creds)


def get_latest_inbox_file():
    """Find the most recent Inbox file."""
    files = glob.glob(str(INBOX_DIR / "INBOX_*.md"))
    if not files:
        return None
    files.sort()
    return files[-1]


def parse_inbox_for_interviews(file_path):
    """Extract interview docs from Inbox markdown."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Look for [DOC] lines with "Interview" in title
    # Format: - [DOC] [Title](Link) | Modified: ...
    pattern = r"- \[DOC\] \[(.*?[Ii]nterview.*?)\]\((.*?)\)"
    matches = re.findall(pattern, content)

    interviews = []
    for title, link in matches:
        # Extract ID from link
        # Link format: https://docs.google.com/document/d/FILE_ID/edit...
        id_match = re.search(r"/d/([a-zA-Z0-9-_]+)", link)
        if id_match:
            interviews.append({"title": title, "id": id_match.group(1), "link": link})

    return interviews


def read_gdoc(service, file_id):
    """Read content of a GDoc."""
    if not service:
        return ""
    try:
        content = (
            service.files().export(fileId=file_id, mimeType="text/plain").execute()
        )
        return content.decode("utf-8")
    except Exception as e:
        print(f"Error reading doc {file_id}: {e}", file=sys.stderr)
        return ""


def load_frameworks():
    """Load content of framework files."""
    frameworks = ""
    for fname in ["Acme Corp_DNA.md", "Product_Career_Framework.md"]:
        path = FRAMEWORKS_DIR / fname
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                frameworks += f"\n\n# {fname}\n{f.read()}"
    return frameworks


def analyze_interview(title, transcript, frameworks):
    """Use Gemini to analyze the interview."""
    if not HAS_GEMINI:
        return "Gemini not available for analysis."

    gemini_config = config_loader.get_gemini_config()
    api_key = gemini_config.get("api_key")
    if not api_key:
        return "No Gemini API key found."

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(gemini_config.get("model", "gemini-1.5-flash"))

    prompt = f"""You are an expert Hiring Manager Assistant at Acme Corp.
    
Task: Analyze the following interview transcript/notes.
    
Candidate/Context: {title}

## Reference Frameworks
{frameworks}

## Interview Transcript
{transcript[:25000]} 

---
Output a structured **Candidate Assessment** in Markdown:

1. **Executive Summary** (1-2 sentences: Recommendation & Confidence).
2. **DNA Assessment** (Analyze fit against Acme Corp DNA values: Speed, Data, Egolessness, etc. Provide evidence).
3. **Role Assessment** (Compare against Career Framework skills for the likely level).
4. **Key Strengths** (Bulleted).
5. **Red Flags / Areas of Concern** (Bulleted).
6. **Recommendation** (Strong Hire / Hire / No Hire).

Be objective, critical, and evidence-based.
"""
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error during analysis: {e}"


def main():
    parser = argparse.ArgumentParser(
        description="Analyze interview transcripts against Acme Corp DNA and Career Framework."
    )
    parser.add_argument(
        "--inbox",
        type=str,
        help="Path to specific inbox file to scan (default: latest)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without executing",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process interviews even if already processed",
    )
    args = parser.parse_args()

    print("Starting Interview Processor...")

    # 1. Find Interviews in latest Inbox
    inbox_file = args.inbox if args.inbox else get_latest_inbox_file()
    if not inbox_file:
        print("No Inbox file found.")
        return

    print(f"Scanning {os.path.basename(inbox_file)}...")
    interviews = parse_inbox_for_interviews(inbox_file)

    if not interviews:
        print("No interview documents found in latest inbox.")
        return

    print(f"Found {len(interviews)} potential interview documents.")

    if args.dry_run:
        print("\n[DRY RUN] Would process:")
        for interview in interviews:
            print(f"  - {interview['title']}")
        return

    # 2. Setup
    service = get_drive_service()
    frameworks = load_frameworks()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 3. Process
    for interview in interviews:
        title = interview["title"]
        file_id = interview["id"]

        # Check if already processed
        # Filename sanitize
        safe_title = re.sub(r"[^a-zA-Z0-9]", "_", title)
        # Check for existing files matching pattern
        # We use a glob to catch date variations if we added date
        existing = list(OUTPUT_DIR.glob(f"*{safe_title}*"))
        if existing and not args.force:
            print(f"Skipping {title} (Already processed: {existing[0].name})")
            continue

        print(f"Processing: {title}...")
        transcript = read_gdoc(service, file_id)
        if not transcript:
            continue

        # Analyze
        analysis = analyze_interview(title, transcript, frameworks)

        # Save
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{safe_title}_{date_str}.md"
        out_path = OUTPUT_DIR / filename

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"# Interview Analysis: {title}\n\n")
            f.write(f"**Date Processed:** {date_str}\n")
            f.write(f"**Source Doc:** {interview['link']}\n\n")
            f.write(analysis)

        print(f"Saved analysis to {out_path}")


if __name__ == "__main__":
    main()
