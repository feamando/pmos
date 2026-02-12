#!/usr/bin/env python3
"""
Statsig Brain Sync
Fetches experiments and feature gates from Statsig and creates/updates Brain entity files.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from difflib import get_close_matches
from pathlib import Path

import requests

# Add parent directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# Constants
BRAIN_DIR = config_loader.get_root_path() / "user" / "brain"
EXPERIMENTS_DIR = BRAIN_DIR / "Experiments"
STATSIG_API_URL = "https://statsigapi.net/console/v1"


def parse_args():
    parser = argparse.ArgumentParser(description="Sync Statsig experiments to Brain")
    parser.add_argument(
        "--active-only", action="store_true", help="Only sync active experiments"
    )
    parser.add_argument(
        "--deep", action="store_true", help="Sync all experiments (including finished)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Fetch data but do not write files"
    )
    parser.add_argument(
        "--summary-file",
        help="Write a markdown summary of processed experiments to this file",
    )
    return parser.parse_args()


class StatsigSync:
    def __init__(self):
        self.config = config_loader.get_statsig_config()
        self.headers = {
            "STATSIG-API-KEY": self.config["api_key"],
            "Content-Type": "application/json",
        }
        if not self.config["api_key"]:
            print("Error: STATSIG_CONSOLE_API_KEY not found in .env", file=sys.stderr)
            sys.exit(1)

    def fetch_experiments(self, limit=100, page=1):
        """Fetch experiments from Statsig API."""
        url = f"{STATSIG_API_URL}/experiments"
        params = {"limit": limit, "page": page}
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching experiments: {e}", file=sys.stderr)
            return {"data": [], "pagination": {}}

    def fetch_gates(self, limit=100, page=1):
        """Fetch feature gates from Statsig API."""
        url = f"{STATSIG_API_URL}/gates"
        params = {"limit": limit, "page": page}
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching gates: {e}", file=sys.stderr)
            return {"data": [], "pagination": {}}

    def extract_jira_keys(self, text):
        """Extract Jira keys (e.g., MK-123) from text."""
        if not text:
            return []
        # Standard Jira key pattern: Project key (2+ uppercase letters) - Number (1+ digits)
        pattern = r"\b([A-Z]{2,}-\d+)\b"
        return sorted(list(set(re.findall(pattern, text))))

    def generate_markdown(self, item, item_type="experiment"):
        """Generate markdown content for the Brain entity."""
        name = item.get("name", "Unknown")
        item_id = item.get("id")
        description = item.get("description") or "No description provided."
        status = item.get("status", "unknown")

        # Extract metadata
        creator = item.get("creatorEmail", "Unknown")
        created_time = item.get("createdTime", 0)
        # Handle milliseconds timestamp if needed
        if created_time > 10000000000:
            created_time = created_time / 1000
        start_date = datetime.fromtimestamp(created_time).strftime("%Y-%m-%d")

        # Linking
        combined_text = f"{name} {description}"
        jira_keys = self.extract_jira_keys(combined_text)

        # Try to find related Brain files based on Jira keys or fuzzy match
        # (This is a simplified version, can be enhanced with Synapse Builder later)

        content = "---"
        content += f"id: {item_id}"
        content += f"type: {item_type}"
        content += f"status: {status}"
        content += f"start_date: {start_date}"
        content += f"creator: {creator}"
        if jira_keys:
            content += f"related_tickets: {json.dumps(jira_keys)}"
        content += "---"

        content += f"# {name}"
        content += f"**Description:** {description}"
        content += f"**Status:** {status}"
        content += f"**ID:** `{item_id}`"

        content += "## Linked Context"
        if jira_keys:
            for key in jira_keys:
                content += f"*   **Jira:** [[{key}]]"
        else:
            content += "*   *No Jira tickets linked explicitly.*\n"
        # Hypothesis (if stored in description or custom fields - heuristic)
        if "hypothesis" in description.lower():
            # Attempt to extract hypothesis paragraph
            pass

        content += "## Metrics & Goals"
        # If metrics info is available in the API response, add it here
        # (Statsig API v1 response structure varies, simplifying for MVP)

        content += f"\n*Last Synced: {datetime.now().strftime('%Y-%m-%d %H:%M')}*"

        return content

    def sync(self, active_only=False, dry_run=False, summary_file=None):
        """Main sync loop."""
        print(f"Starting Statsig Sync... (Active Only: {active_only})")

        # 1. Fetch Experiments
        all_experiments = []
        page = 1
        while True:
            res = self.fetch_experiments(limit=100, page=page)
            data = res.get("data", [])
            all_experiments.extend(data)

            pagination = res.get("pagination", {})
            if not pagination.get("nextPage"):
                break
            page += 1

        print(f"Fetched {len(all_experiments)} experiments.")

        # 2. Process & Save
        processed_count = 0
        summary_lines = []

        for exp in all_experiments:
            status = exp.get("status", "").lower()
            if active_only and status != "active":
                continue

            item_id = exp.get("id")
            name = exp.get("name", "Unknown")
            filename = f"EXP-{item_id}.md"
            # Sanitize filename
            filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
            filepath = EXPERIMENTS_DIR / filename

            md_content = self.generate_markdown(exp, "experiment")

            if not dry_run:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(md_content)

            summary_lines.append(f"- **{name}** (`{item_id}`) - Status: {status}")
            processed_count += 1

        print(f"Processed {processed_count} experiments.")

        if not dry_run:
            print(f"Files saved to {EXPERIMENTS_DIR}")

        if summary_file and summary_lines:
            try:
                with open(summary_file, "w", encoding="utf-8") as f:
                    f.write("### Active Statsig Experiments\n\n")
                    f.write("\n".join(summary_lines))
                    f.write("\n")
                print(f"Summary written to {summary_file}")
            except Exception as e:
                print(f"Error writing summary file: {e}", file=sys.stderr)


def main():
    args = parse_args()

    # Ensure output directory exists
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

    syncer = StatsigSync()
    syncer.sync(
        active_only=args.active_only,
        dry_run=args.dry_run,
        summary_file=args.summary_file,
    )


if __name__ == "__main__":
    main()
