#!/usr/bin/env python3
"""
File Store Manager for Deep Research

Manages Google File Search stores for indexing local documents.
Used by the PRD generator to search internal documentation.

Usage:
    python3 file_store_manager.py --create    # Create new store and index docs
    python3 file_store_manager.py --sync      # Sync changes to existing store
    python3 file_store_manager.py --list      # List all stores
    python3 file_store_manager.py --delete    # Delete the configured store
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add common directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config_loader

# Constants
BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
ROOT_DIR = config_loader.get_root_path()


def load_config() -> Dict[str, Any]:
    """Load local configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def save_config(config: Dict[str, Any]):
    """Save configuration."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_client():
    """Get authenticated Gemini client."""
    from google import genai

    gemini_config = config_loader.get_gemini_config()
    api_key = gemini_config.get("api_key")

    if not api_key:
        print("Error: GEMINI_API_KEY not set in environment", file=sys.stderr)
        sys.exit(1)

    return genai.Client(api_key=api_key)


def find_files_to_index(patterns: List[str]) -> List[Path]:
    """Find all files matching the index patterns."""
    files = []
    for pattern in patterns:
        full_pattern = str(ROOT_DIR / pattern)
        matched = glob.glob(full_pattern, recursive=True)
        files.extend([Path(f) for f in matched if Path(f).is_file()])

    # Deduplicate
    return list(set(files))


def create_file_search_store(name: str) -> str:
    """Create a new File Search store."""
    client = get_client()

    print(f"Creating File Search store: {name}")

    try:
        store = client.file_search_stores.create(config={"display_name": name})
        print(f"Store created: {store.name}")
        return store.name
    except Exception as e:
        print(f"Error creating store: {e}", file=sys.stderr)
        raise


def upload_files_to_store(
    store_name: str, files: List[Path], verbose: bool = True
) -> Dict[str, str]:
    """Upload files to a File Search store."""
    client = get_client()
    uploaded = {}

    print(f"Uploading {len(files)} files to store: {store_name}")

    for i, file_path in enumerate(files):
        if verbose:
            rel_path = (
                str(file_path.relative_to(ROOT_DIR))
                if file_path.is_relative_to(ROOT_DIR)
                else file_path.name
            )
            print(f"  [{i+1}/{len(files)}] {rel_path}", end="", flush=True)

        try:
            result = client.file_search_stores.upload_to_file_search_store(
                file_search_store_name=store_name,
                file=str(file_path),
                config={"display_name": file_path.name},
            )

            # Extract document name from result
            doc_name = (
                result.response.document_name if result.response else str(result.name)
            )
            uploaded[str(file_path)] = doc_name

            if verbose:
                print(" [OK]")

        except Exception as e:
            if verbose:
                print(f" [FAILED: {e}]")

    print(f"Uploaded {len(uploaded)}/{len(files)} files")
    return uploaded


def list_file_search_stores() -> List[Dict]:
    """List all File Search stores."""
    client = get_client()
    stores = []

    try:
        result = client.file_search_stores.list()
        for store in result:
            stores.append(
                {
                    "name": store.name,
                    "display_name": getattr(store, "display_name", "N/A"),
                    "create_time": str(getattr(store, "create_time", "N/A")),
                }
            )
    except Exception as e:
        print(f"Could not list stores: {e}", file=sys.stderr)

    return stores


def delete_file_search_store(store_name: str) -> bool:
    """Delete a File Search store."""
    client = get_client()

    try:
        client.file_search_stores.delete(name=store_name)
        print(f"Store deleted: {store_name}")
        return True
    except Exception as e:
        print(f"Could not delete store: {e}", file=sys.stderr)
        return False


def list_store_documents(store_name: str) -> List[Dict]:
    """List documents in a File Search store."""
    client = get_client()
    docs = []

    try:
        result = client.file_search_stores.documents.list(
            file_search_store_name=store_name
        )
        for doc in result:
            docs.append(
                {
                    "name": doc.name,
                    "display_name": getattr(doc, "display_name", "N/A"),
                }
            )
    except Exception as e:
        print(f"Could not list documents: {e}", file=sys.stderr)

    return docs


def setup_store() -> str:
    """Full setup: create store, upload all files, save config."""
    config = load_config()
    patterns = config.get(
        "index_patterns",
        [
            "Products/**/*.md",
            "AI_Guidance/Core_Context/*.md",
            "user/brain/**/*.md",
            "Planning/**/*.md",
        ],
    )
    store_display_name = config.get("file_store_name", "pm-os-documents")

    # Check if store already exists
    existing_store = config.get("file_store_id")
    if existing_store:
        print(f"Store already exists: {existing_store}")
        print("Use --sync to add new files, or --delete first to recreate.")
        return existing_store

    # Find files
    files = find_files_to_index(patterns)
    print(f"Found {len(files)} files to index")

    if not files:
        print("No files found matching patterns:", file=sys.stderr)
        for p in patterns:
            print(f"  - {p}", file=sys.stderr)
        return ""

    # Create store
    store_name = create_file_search_store(store_display_name)

    # Upload files
    uploaded = upload_files_to_store(store_name, files)

    # Save config
    config["file_store_id"] = store_name
    config["uploaded_files"] = uploaded
    config["last_sync"] = datetime.now().isoformat()
    save_config(config)

    print(f"\nSetup complete!")
    print(f"Store: {store_name}")
    print(f"Files indexed: {len(uploaded)}")
    print(f"Config saved to: {CONFIG_FILE}")

    return store_name


def sync_store():
    """Sync new/changed files to existing store."""
    config = load_config()
    store_name = config.get("file_store_id")

    if not store_name:
        print("No store configured. Run --create first.")
        return

    patterns = config.get("index_patterns", [])
    existing_files = config.get("uploaded_files", {})

    # Find current files
    current_files = find_files_to_index(patterns)

    # Find new files
    new_files = [f for f in current_files if str(f) not in existing_files]

    if not new_files:
        print("No new files to sync")
        return

    print(f"Found {len(new_files)} new files to upload")

    # Upload new files
    uploaded = upload_files_to_store(store_name, new_files)

    # Update config
    existing_files.update(uploaded)
    config["uploaded_files"] = existing_files
    config["last_sync"] = datetime.now().isoformat()
    save_config(config)

    print(f"Sync complete! Total files: {len(existing_files)}")


def main():
    parser = argparse.ArgumentParser(
        description="Manage File Search stores for Deep Research"
    )
    parser.add_argument(
        "--create", action="store_true", help="Create new store and index all files"
    )
    parser.add_argument(
        "--sync", action="store_true", help="Sync new files to existing store"
    )
    parser.add_argument(
        "--list", action="store_true", help="List all File Search stores"
    )
    parser.add_argument(
        "--list-docs", action="store_true", help="List documents in configured store"
    )
    parser.add_argument(
        "--delete", action="store_true", help="Delete the configured store"
    )
    parser.add_argument(
        "--info", action="store_true", help="Show current configuration"
    )

    args = parser.parse_args()

    if args.create:
        setup_store()
    elif args.sync:
        sync_store()
    elif args.list:
        stores = list_file_search_stores()
        print(f"Found {len(stores)} stores:")
        for s in stores:
            print(f"  - {s['display_name']} ({s['name']})")
    elif args.list_docs:
        config = load_config()
        store_name = config.get("file_store_id")
        if store_name:
            docs = list_store_documents(store_name)
            print(f"Found {len(docs)} documents in {store_name}:")
            for d in docs[:20]:  # Show first 20
                print(f"  - {d['display_name']}")
            if len(docs) > 20:
                print(f"  ... and {len(docs) - 20} more")
        else:
            print("No store configured")
    elif args.delete:
        config = load_config()
        store_name = config.get("file_store_id")
        if store_name:
            delete_file_search_store(store_name)
            config["file_store_id"] = None
            config["uploaded_files"] = {}
            save_config(config)
        else:
            print("No store configured to delete")
    elif args.info:
        config = load_config()
        print("Current configuration:")
        print(f"  Store ID: {config.get('file_store_id', 'Not set')}")
        print(f"  Store Name: {config.get('file_store_name', 'Not set')}")
        print(f"  Last Sync: {config.get('last_sync', 'Never')}")
        print(f"  Files Indexed: {len(config.get('uploaded_files', {}))}")
        print(f"  Index Patterns:")
        for p in config.get("index_patterns", []):
            print(f"    - {p}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
