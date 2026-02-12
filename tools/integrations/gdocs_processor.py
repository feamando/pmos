#!/usr/bin/env python3
"""
Google Docs Processor - Phase 1

Parses extracted GDocs INBOX files and filters for relevant content:
- Filters by topics (Growth Division, Meal Kit, WB, Growth Platform, etc.)
- Filters by people (Jama, Deo, Beatrice, Maria, etc.)
- Classifies document types (PRD, 1:1, meeting notes, strategy)
- Creates batches for LLM analysis

Usage:
    python3 gdocs_processor.py [--dry-run] [--status]
    python3 gdocs_processor.py --list-docs
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add tools directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# ============================================================================
# CONFIGURATION
# ============================================================================

ROOT_PATH = config_loader.get_root_path()
USER_PATH = ROOT_PATH / "user"
BRAIN_DIR = USER_PATH / "brain"
INBOX_DIR = BRAIN_DIR / "Inbox"
GDOCS_OUTPUT_DIR = INBOX_DIR / "GDocs"
PROCESSED_DIR = GDOCS_OUTPUT_DIR / "Processed"
STATE_FILE = GDOCS_OUTPUT_DIR / "processing_state.json"

# Batch settings
BATCH_SIZE = 10  # Documents per batch (GDocs are larger than Slack messages)
MAX_BATCH_CHARS = 50000  # Max chars per batch for LLM context

# Date range (6 months)
LOOKBACK_DAYS = 180

# ============================================================================
# FILTERING CONFIGURATION
# ============================================================================

# Topics to filter for (case-insensitive)
TOPIC_FILTERS = [
    # Projects/Brands
    "new ventures",
    "Meal Kit",
    "goodchop",
    "goc",
    "Wellness Brand",
    "Wellness Brand",
    "tpt",
    "Growth Platform",
    "vms",
    "market innovation",
    "market integration",
    "cross-selling",
    "cross selling",
    "crossselling",
    # Features
    "otp",
    "one time purchase",
    "one-time purchase",
    "seasonal boxes",
    "seasonal box",
    "occasion boxes",
    "occasion box",
]

# People to filter for (case-insensitive, partial match)
PEOPLE_FILTERS = [
    "jama",
    "deo",
    "beatrice",
    "maria",
    "prateek",
    "hamed",
    "yarra",
    "sameer",
    "allison",
    "wander",
    "ahmed",
    "alex",
    "max",
    "daniel",
    # Also include Nikita since he's the user
    "nikita",
]

# Document type classification rules
DOC_TYPE_RULES = {
    "prd": [
        r"\bprd\b",
        r"\bmemo:",
        r"draft\s*-",
        r"\brequirements\b",
        r"\bproduct\s+requirements\b",
    ],
    "one_on_one": [
        r"1:1",
        r"1-on-1",
        r"one.on.one",
        r":nikita\b",
        r"nikita:",
    ],
    "meeting": [
        r"\bmeeting\b",
        r"\bsync\b",
        r"\bnotes\b",
        r"\bagenda\b",
        r"\buats?\b",
        r"\bretro\b",
    ],
    "strategy": [
        r"\bokr\b",
        r"\bobjectives?\b",
        r"\bstrategy\b",
        r"\b202[456]\b.*\b(plan|roadmap)\b",
        r"\broadmap\b",
        r"\byearly\s+plan\b",
    ],
    "spreadsheet": [
        r"spreadsheets",
        r"\btracker\b",
        r"\btracking\b",
    ],
}

# ============================================================================
# STATE MANAGEMENT
# ============================================================================


def load_state() -> dict:
    """Load processing state from file."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "started_at": None,
        "last_updated": None,
        "files_processed": [],
        "docs_found": 0,
        "docs_matched": 0,
        "batches_created": 0,
        "by_type": {},
    }


def save_state(state: dict):
    """Save processing state to file."""
    state["last_updated"] = datetime.now().isoformat()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def print_status(state: dict):
    """Print processing status."""
    print("=" * 60)
    print("GDOCS PROCESSOR STATUS")
    print("=" * 60)
    print(f"Started: {state.get('started_at', 'Not started')}")
    print(f"Last Updated: {state.get('last_updated', 'N/A')}")
    print(f"Files Processed: {len(state.get('files_processed', []))}")
    print(f"Docs Found: {state.get('docs_found', 0)}")
    print(f"Docs Matched (filtered): {state.get('docs_matched', 0)}")
    print(f"Batches Created: {state.get('batches_created', 0)}")

    by_type = state.get("by_type", {})
    if by_type:
        print("\nBy Document Type:")
        for dtype, count in sorted(by_type.items()):
            print(f"  {dtype}: {count}")
    print("=" * 60)


# ============================================================================
# INBOX FILE PARSING
# ============================================================================


def find_inbox_files() -> List[Path]:
    """Find all INBOX_*.md files."""
    files = []

    # Main inbox
    for f in INBOX_DIR.glob("INBOX_*.md"):
        files.append(f)

    # Archive
    archive_dir = INBOX_DIR / "Archive"
    if archive_dir.exists():
        for f in archive_dir.glob("INBOX_*.md"):
            files.append(f)

    # Strategy Raw
    strategy_dir = INBOX_DIR / "Strategy_Raw"
    if strategy_dir.exists():
        for f in strategy_dir.glob("*.md"):
            files.append(f)

    return sorted(files)


def parse_inbox_file(filepath: Path) -> List[Dict]:
    """
    Parse an INBOX file and extract individual documents.

    Returns list of document dicts with:
    - title, doc_id, link, content, source_file
    """
    documents = []

    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        return []

    # Find document sections
    # Pattern: ### DOC: <title>
    doc_pattern = r"(?:^|\n)#{3}\s+DOC:\s*(.+?)(?:\n)"
    separator = "----------------------------------------"

    # Split by document headers
    parts = re.split(r"\n-{30,}\n### DOC:", content)

    if len(parts) <= 1:
        # Try alternate format
        parts = re.split(r"\n### DOC:", content)

    for i, part in enumerate(parts[1:], 1):  # Skip header section
        lines = part.strip().split("\n")
        if not lines:
            continue

        # First line is title (after DOC:)
        title = lines[0].strip()

        # Find ID and Link
        doc_id = None
        link = None
        content_start = 1

        for j, line in enumerate(lines[1:], 1):
            if line.startswith("ID:"):
                doc_id = line.replace("ID:", "").strip()
            elif line.startswith("Link:"):
                link = line.replace("Link:", "").strip()
            elif line.startswith("---") or (doc_id and link):
                content_start = j + 1
                break

        # Rest is content
        doc_content = "\n".join(lines[content_start:]).strip()

        # Remove truncation markers
        doc_content = re.sub(r"\.\.\.\s*\[TRUNCATED:.*?\].*", "", doc_content)

        if title and (doc_content or doc_id):
            documents.append(
                {
                    "title": title,
                    "doc_id": doc_id,
                    "link": link,
                    "content": doc_content,
                    "source_file": str(filepath),
                    "source_date": extract_date_from_filename(filepath.name),
                }
            )

    return documents


def extract_date_from_filename(filename: str) -> Optional[str]:
    """Extract date from INBOX filename like INBOX_2025-12-30-01.md"""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    if match:
        return match.group(1)
    return None


# ============================================================================
# FILTERING LOGIC
# ============================================================================


def matches_topic_filter(doc: Dict) -> Tuple[bool, List[str]]:
    """
    Check if document matches any topic filter.
    Returns (matches, list of matched topics).
    """
    text = f"{doc.get('title', '')} {doc.get('content', '')}".lower()
    matched = []

    for topic in TOPIC_FILTERS:
        if topic.lower() in text:
            matched.append(topic)

    return len(matched) > 0, matched


def matches_people_filter(doc: Dict) -> Tuple[bool, List[str]]:
    """
    Check if document mentions any filtered people.
    Returns (matches, list of matched people).
    """
    text = f"{doc.get('title', '')} {doc.get('content', '')}".lower()
    matched = []

    for person in PEOPLE_FILTERS:
        # Use word boundary for better matching
        pattern = rf"\b{re.escape(person.lower())}\b"
        if re.search(pattern, text):
            matched.append(person)

    return len(matched) > 0, matched


def classify_document_type(doc: Dict) -> str:
    """Classify document into a type based on title and content."""
    text = f"{doc.get('title', '')} {doc.get('content', '')[:1000]}".lower()
    link = doc.get("link", "").lower()

    # Check link for spreadsheet
    if "spreadsheets" in link:
        return "spreadsheet"

    # Check content patterns
    for doc_type, patterns in DOC_TYPE_RULES.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return doc_type

    return "other"


def filter_document(doc: Dict) -> Tuple[bool, Dict]:
    """
    Filter a document and add metadata.
    Returns (should_include, enriched_doc).
    """
    # Check filters
    topic_match, topics = matches_topic_filter(doc)
    people_match, people = matches_people_filter(doc)

    # Must match at least one filter
    if not topic_match and not people_match:
        return False, doc

    # Classify type
    doc_type = classify_document_type(doc)

    # Enrich document
    enriched = {
        **doc,
        "doc_type": doc_type,
        "matched_topics": topics,
        "matched_people": people,
        "filter_score": len(topics) + len(people),  # Higher = more relevant
    }

    return True, enriched


def is_within_date_range(doc: Dict, lookback_days: int = LOOKBACK_DAYS) -> bool:
    """Check if document is within the date range."""
    source_date = doc.get("source_date")
    if not source_date:
        return True  # Include if no date available

    try:
        doc_date = datetime.strptime(source_date, "%Y-%m-%d")
        cutoff = datetime.now() - timedelta(days=lookback_days)
        return doc_date >= cutoff
    except ValueError:
        return True  # Include if date parsing fails


# ============================================================================
# BATCH CREATION
# ============================================================================


def create_batches(documents: List[Dict]) -> List[Dict]:
    """
    Create batches of documents for LLM analysis.
    Groups by document type and respects size limits.
    """
    # Group by type
    by_type = defaultdict(list)
    for doc in documents:
        by_type[doc.get("doc_type", "other")].append(doc)

    batches = []
    batch_counter = 0

    for doc_type, docs in by_type.items():
        # Sort by relevance score
        docs_sorted = sorted(docs, key=lambda x: x.get("filter_score", 0), reverse=True)

        current_batch = []
        current_chars = 0

        for doc in docs_sorted:
            doc_chars = len(doc.get("content", ""))

            # Check if adding this doc exceeds limits
            if (
                len(current_batch) >= BATCH_SIZE
                or current_chars + doc_chars > MAX_BATCH_CHARS
            ):
                if current_batch:
                    batch_counter += 1
                    batches.append(
                        {
                            "batch_id": f"{doc_type}_{batch_counter:03d}",
                            "doc_type": doc_type,
                            "documents": current_batch,
                            "doc_count": len(current_batch),
                            "total_chars": current_chars,
                        }
                    )
                current_batch = []
                current_chars = 0

            current_batch.append(doc)
            current_chars += doc_chars

        # Don't forget last batch
        if current_batch:
            batch_counter += 1
            batches.append(
                {
                    "batch_id": f"{doc_type}_{batch_counter:03d}",
                    "doc_type": doc_type,
                    "documents": current_batch,
                    "doc_count": len(current_batch),
                    "total_chars": current_chars,
                }
            )

    return batches


def save_batch(batch: Dict) -> Path:
    """Save a batch to disk."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    filepath = PROCESSED_DIR / f"batch_{batch['batch_id']}.json"

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)

    return filepath


# ============================================================================
# MAIN PIPELINE
# ============================================================================


def run_processor(dry_run: bool = False, resume: bool = True, list_docs: bool = False):
    """Run the GDocs processing pipeline."""
    state = load_state()

    if not state.get("started_at"):
        state["started_at"] = datetime.now().isoformat()

    # Find inbox files
    inbox_files = find_inbox_files()
    print(f"Found {len(inbox_files)} inbox files", file=sys.stderr)

    # Filter already processed
    if resume:
        processed_set = set(state.get("files_processed", []))
        inbox_files = [f for f in inbox_files if str(f) not in processed_set]
        print(f"Remaining after resume filter: {len(inbox_files)}", file=sys.stderr)

    if not inbox_files:
        print("No new inbox files to process", file=sys.stderr)
        return

    # Parse and filter documents
    all_docs = []
    filtered_docs = []
    type_counts = defaultdict(int)

    for filepath in inbox_files:
        print(f"\nProcessing: {filepath.name}", file=sys.stderr)

        docs = parse_inbox_file(filepath)
        print(f"  Found {len(docs)} documents", file=sys.stderr)
        all_docs.extend(docs)

        # Filter each document
        matched = 0
        for doc in docs:
            # Check date range
            if not is_within_date_range(doc):
                continue

            # Apply filters
            should_include, enriched = filter_document(doc)
            if should_include:
                filtered_docs.append(enriched)
                type_counts[enriched["doc_type"]] += 1
                matched += 1

        print(f"  Matched filters: {matched}", file=sys.stderr)

        if not dry_run:
            state.setdefault("files_processed", []).append(str(filepath))

    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"Total documents found: {len(all_docs)}", file=sys.stderr)
    print(f"Documents matching filters: {len(filtered_docs)}", file=sys.stderr)
    print(f"\nBy type:", file=sys.stderr)
    for dtype, count in sorted(type_counts.items()):
        print(f"  {dtype}: {count}", file=sys.stderr)

    if list_docs:
        print(f"\n{'=' * 60}")
        print("MATCHED DOCUMENTS")
        print("=" * 60)
        for doc in sorted(
            filtered_docs, key=lambda x: x.get("filter_score", 0), reverse=True
        ):
            topics = ", ".join(doc.get("matched_topics", [])[:3])
            people = ", ".join(doc.get("matched_people", [])[:3])
            print(f"\n[{doc['doc_type']}] {doc['title'][:60]}")
            print(f"  Topics: {topics}")
            print(f"  People: {people}")
            print(f"  Score: {doc.get('filter_score', 0)}")
        return

    if dry_run:
        print(
            f"\n[DRY RUN] Would create batches for {len(filtered_docs)} documents",
            file=sys.stderr,
        )
        return

    # Create and save batches
    batches = create_batches(filtered_docs)
    print(f"\nCreating {len(batches)} batches...", file=sys.stderr)

    for batch in batches:
        filepath = save_batch(batch)
        print(
            f"  Saved: {filepath.name} ({batch['doc_count']} docs, {batch['total_chars']:,} chars)",
            file=sys.stderr,
        )

    # Update state
    state["docs_found"] = state.get("docs_found", 0) + len(all_docs)
    state["docs_matched"] = state.get("docs_matched", 0) + len(filtered_docs)
    state["batches_created"] = state.get("batches_created", 0) + len(batches)
    state["by_type"] = dict(type_counts)
    save_state(state)

    # Summary
    print(f"\n{'=' * 60}", file=sys.stderr)
    print("PROCESSING COMPLETE", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)
    print(f"Documents processed: {len(all_docs)}", file=sys.stderr)
    print(f"Documents matched: {len(filtered_docs)}", file=sys.stderr)
    print(f"Batches created: {len(batches)}", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Process GDocs INBOX files and filter for relevant content"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without creating batches",
    )
    parser.add_argument(
        "--no-resume", action="store_true", help="Reprocess all inbox files"
    )
    parser.add_argument(
        "--list-docs", action="store_true", help="List all matched documents and exit"
    )
    parser.add_argument(
        "--status", action="store_true", help="Show processing status and exit"
    )

    args = parser.parse_args()

    if args.status:
        state = load_state()
        print_status(state)
        return

    run_processor(
        dry_run=args.dry_run,
        resume=not args.no_resume,
        list_docs=args.list_docs,
    )


if __name__ == "__main__":
    main()
