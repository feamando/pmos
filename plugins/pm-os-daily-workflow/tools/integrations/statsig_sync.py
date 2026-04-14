#!/usr/bin/env python3
"""
Statsig Brain Sync (v5.0)

Fetches experiments and feature gates from Statsig and creates/updates
Brain entity files. All credentials via connector_bridge — zero hardcoded values.

Usage:
    python3 statsig_sync.py                     # Sync active experiments
    python3 statsig_sync.py --active-only       # Only active experiments
    python3 statsig_sync.py --dry-run           # Fetch but do not write
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# v5 imports: shared utils from pm_os_base
try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
        from tools.core.config_loader import get_config
    except ImportError:
        get_config = None

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        from tools.core.path_resolver import get_paths
    except ImportError:
        get_paths = None

try:
    from pm_os_base.tools.core.connector_bridge import get_auth
except ImportError:
    try:
        from tools.core.connector_bridge import get_auth
    except ImportError:
        get_auth = None

# Statsig API base URL (structural constant, not org-specific)
STATSIG_API_URL = "https://statsigapi.net/console/v1"


def _resolve_brain_dir() -> Path:
    """Resolve brain directory from config/paths."""
    if get_paths is not None:
        try:
            return get_paths().brain
        except Exception:
            pass
    if get_config is not None:
        try:
            config = get_config()
            if config.user_path:
                return config.user_path / "brain"
        except Exception:
            pass
    return Path.cwd() / "user" / "brain"


def _get_statsig_headers() -> Optional[Dict[str, str]]:
    """Get Statsig API headers using connector_bridge for auth."""
    if get_auth is not None:
        auth = get_auth("statsig")
        if auth.source == "connector":
            logger.info("Statsig auth via Claude connector")
            return None
        elif auth.source == "env":
            return {
                "STATSIG-API-KEY": auth.token,
                "Content-Type": "application/json",
            }
        else:
            logger.error("Statsig auth not available: %s", auth.help_message)
            return None

    # Fallback: direct env lookup
    config = get_config() if get_config else None
    if config:
        api_key = config.get_secret("STATSIG_CONSOLE_API_KEY")
        if api_key:
            return {
                "STATSIG-API-KEY": api_key,
                "Content-Type": "application/json",
            }

    logger.error("STATSIG_CONSOLE_API_KEY not found")
    return None


class StatsigSync:
    """Fetches and syncs Statsig experiments/gates to Brain entities."""

    def __init__(self):
        self.headers = _get_statsig_headers()
        if not self.headers:
            raise ValueError("Statsig auth not configured")

        brain_dir = _resolve_brain_dir()
        self.experiments_dir = brain_dir / "Experiments"

    def _api_get(self, path: str, params: Optional[Dict] = None) -> Dict:
        """Make a GET request to the Statsig API."""
        try:
            import requests
        except ImportError:
            logger.error("requests library not installed. Run: pip install requests")
            return {"data": [], "pagination": {}}

        url = f"{STATSIG_API_URL}/{path}"
        try:
            response = requests.get(url, headers=self.headers, params=params or {})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Error fetching %s: %s", path, e)
            return {"data": [], "pagination": {}}

    def fetch_experiments(self, limit: int = 100, page: int = 1) -> Dict:
        """Fetch experiments from Statsig API."""
        return self._api_get("experiments", {"limit": limit, "page": page})

    def fetch_gates(self, limit: int = 100, page: int = 1) -> Dict:
        """Fetch feature gates from Statsig API."""
        return self._api_get("gates", {"limit": limit, "page": page})

    def extract_jira_keys(self, text: str) -> List[str]:
        """Extract Jira keys (e.g., GOC-123) from text."""
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
        if jira_keys:
            for key in jira_keys:
                lines.append(f"- **Jira:** [[{key}]]")
        else:
            lines.append("- *No Jira tickets linked explicitly.*")
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
    ) -> Dict[str, Any]:
        """Main sync loop. Returns result dict."""
        logger.info("Starting Statsig Sync... (Active Only: %s)", active_only)

        # 1. Fetch all experiments
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

        # 2. Process & Save
        processed_count = 0
        summary_lines = []

        if not dry_run:
            self.experiments_dir.mkdir(parents=True, exist_ok=True)

        for exp in all_experiments:
            status = exp.get("status", "").lower()
            if active_only and status != "active":
                continue

            item_id = exp.get("id")
            name = exp.get("name", "Unknown")
            filename = f"EXP-{item_id}.md"
            filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
            filepath = self.experiments_dir / filename

            md_content = self.generate_markdown(exp, "experiment")

            if not dry_run:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(md_content)

            summary_lines.append(f"- **{name}** (`{item_id}`) - Status: {status}")
            processed_count += 1

        logger.info("Processed %d experiments.", processed_count)

        if not dry_run:
            logger.info("Files saved to %s", self.experiments_dir)

        if summary_file and summary_lines:
            try:
                with open(summary_file, "w", encoding="utf-8") as f:
                    f.write("### Active Statsig Experiments\n\n")
                    f.write("\n".join(summary_lines))
                    f.write("\n")
                logger.info("Summary written to %s", summary_file)
            except Exception as e:
                logger.error("Error writing summary file: %s", e)

        return {
            "status": "success",
            "experiments_fetched": len(all_experiments),
            "experiments_processed": processed_count,
            "dry_run": dry_run,
            "output_dir": str(self.experiments_dir),
        }


def run_sync(
    active_only: bool = False,
    dry_run: bool = False,
    summary_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Run Statsig sync programmatically."""
    try:
        syncer = StatsigSync()
        return syncer.sync(
            active_only=active_only, dry_run=dry_run, summary_file=summary_file
        )
    except ValueError as e:
        return {"status": "error", "message": str(e)}


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Sync Statsig experiments to Brain")
    parser.add_argument("--active-only", action="store_true", help="Only sync active experiments")
    parser.add_argument("--dry-run", action="store_true", help="Fetch data but do not write files")
    parser.add_argument("--summary-file", help="Write a markdown summary to this file")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    result = run_sync(
        active_only=args.active_only,
        dry_run=args.dry_run,
        summary_file=args.summary_file,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result.get("status") == "success":
            print(f"Statsig sync complete. {result['experiments_processed']} experiments processed.")
            if not result.get("dry_run"):
                print(f"Output: {result['output_dir']}")
        else:
            print(f"Error: {result.get('message', 'Unknown error')}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
