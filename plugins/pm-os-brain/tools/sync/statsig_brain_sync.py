#!/usr/bin/env python3
"""
Statsig Brain Sync (v5.0)

Fetches experiments and feature gates from Statsig and creates/updates
Brain entity files.

Usage:
    python3 statsig_brain_sync.py                     # Sync all experiments
    python3 statsig_brain_sync.py --active-only        # Only active experiments
    python3 statsig_brain_sync.py --dry-run            # Preview without writing
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    requests = None
    logger.warning("requests not installed. Install with: pip install requests")

# v5 imports
try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from core.config_loader import get_config

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    get_paths = None

try:
    from pm_os_base.tools.core.connector_bridge import get_auth
except ImportError:
    get_auth = None


# ---------------------------------------------------------------------------
# Configuration (config-driven, zero hardcoded values)
# ---------------------------------------------------------------------------

STATSIG_API_URL = "https://statsigapi.net/console/v1"


def _resolve_brain_dir() -> Path:
    """Resolve brain directory via path_resolver or config."""
    if get_paths is not None:
        try:
            return get_paths().brain
        except Exception:
            pass
    config = get_config()
    if config.user_path:
        return config.user_path / "brain"
    return Path.cwd() / "user" / "brain"


def _get_statsig_api_key() -> str:
    """Get Statsig API key from connector_bridge, config, or env."""
    # Try connector_bridge first
    if get_auth is not None:
        auth = get_auth("statsig")
        if auth.source == "env" and auth.token:
            return auth.token

    # Try config
    config = get_config()
    key = config.get_secret("STATSIG_CONSOLE_API_KEY")
    if key:
        return key

    # Direct env fallback
    return os.getenv("STATSIG_CONSOLE_API_KEY", "")


# ---------------------------------------------------------------------------
# Statsig Sync
# ---------------------------------------------------------------------------

class StatsigSync:
    def __init__(self):
        self.api_key = _get_statsig_api_key()
        self.headers = {
            "STATSIG-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        if not self.api_key:
            logger.error("STATSIG_CONSOLE_API_KEY not found. Configure in .env or config.yaml")
            sys.exit(1)

    def fetch_experiments(self, limit: int = 100, page: int = 1) -> Dict[str, Any]:
        """Fetch experiments from Statsig API."""
        if requests is None:
            logger.error("requests library not installed")
            return {"data": [], "pagination": {}}

        url = f"{STATSIG_API_URL}/experiments"
        params = {"limit": limit, "page": page}
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Error fetching experiments: %s", e)
            return {"data": [], "pagination": {}}

    def fetch_gates(self, limit: int = 100, page: int = 1) -> Dict[str, Any]:
        """Fetch feature gates from Statsig API."""
        if requests is None:
            logger.error("requests library not installed")
            return {"data": [], "pagination": {}}

        url = f"{STATSIG_API_URL}/gates"
        params = {"limit": limit, "page": page}
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Error fetching gates: %s", e)
            return {"data": [], "pagination": {}}

    def extract_jira_keys(self, text: str) -> List[str]:
        """Extract Jira keys (e.g., PROJ-123) from text."""
        if not text:
            return []
        pattern = r"\b([A-Z]{2,}-\d+)\b"
        return sorted(list(set(re.findall(pattern, text))))

    def generate_markdown(self, item: Dict, item_type: str = "experiment") -> str:
        """Generate markdown content for the Brain entity."""
        name = item.get("name", "Unknown")
        item_id = item.get("id")
        description = item.get("description") or "No description provided."
        status = item.get("status", "unknown")

        creator = item.get("creatorEmail", "Unknown")
        created_time = item.get("createdTime", 0)
        # Handle milliseconds timestamp if needed
        if created_time > 10000000000:
            created_time = created_time / 1000
        start_date = datetime.fromtimestamp(created_time).strftime("%Y-%m-%d")

        combined_text = f"{name} {description}"
        jira_keys = self.extract_jira_keys(combined_text)

        lines = [
            "---",
            f"id: {item_id}",
            f"type: {item_type}",
            f"status: {status}",
            f"start_date: {start_date}",
            f"creator: {creator}",
        ]
        if jira_keys:
            lines.append(f"related_tickets: {json.dumps(jira_keys)}")
        lines.append("---")
        lines.append("")
        lines.append(f"# {name}")
        lines.append("")
        lines.append(f"**Description:** {description}")
        lines.append(f"**Status:** {status}")
        lines.append(f"**ID:** `{item_id}`")
        lines.append("")
        lines.append("## Linked Context")
        lines.append("")
        if jira_keys:
            for key in jira_keys:
                lines.append(f"*   **Jira:** [[{key}]]")
        else:
            lines.append("*   *No Jira tickets linked explicitly.*")
        lines.append("")
        lines.append("## Metrics & Goals")
        lines.append("")
        lines.append(f"*Last Synced: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

        return "\n".join(lines)

    def sync(
        self,
        active_only: bool = False,
        dry_run: bool = False,
        summary_file: Optional[str] = None,
    ):
        """Main sync loop."""
        brain_dir = _resolve_brain_dir()
        experiments_dir = brain_dir / "Experiments"
        experiments_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Starting Statsig Sync... (Active Only: %s)", active_only)

        # Fetch all experiments (paginated)
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

        logger.info("Fetched %d experiments.", len(all_experiments))

        # Process and save
        processed_count = 0
        summary_lines = []

        for exp in all_experiments:
            status = exp.get("status", "").lower()
            if active_only and status != "active":
                continue

            item_id = exp.get("id")
            name = exp.get("name", "Unknown")
            filename = f"EXP-{item_id}.md"
            filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
            filepath = experiments_dir / filename

            md_content = self.generate_markdown(exp, "experiment")

            if not dry_run:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(md_content)

            summary_lines.append(f"- **{name}** (`{item_id}`) - Status: {status}")
            processed_count += 1

        logger.info("Processed %d experiments.", processed_count)

        if not dry_run:
            logger.info("Files saved to %s", experiments_dir)

        if summary_file and summary_lines:
            try:
                with open(summary_file, "w", encoding="utf-8") as f:
                    f.write("### Active Statsig Experiments\n\n")
                    f.write("\n".join(summary_lines))
                    f.write("\n")
                logger.info("Summary written to %s", summary_file)
            except Exception as e:
                logger.error("Error writing summary file: %s", e)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
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

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    syncer = StatsigSync()
    syncer.sync(
        active_only=args.active_only,
        dry_run=args.dry_run,
        summary_file=args.summary_file,
    )


if __name__ == "__main__":
    main()
