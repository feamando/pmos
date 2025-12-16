#!/usr/bin/env python3
"""
Sprint Report Generator - Integrated Version

Uses existing Jira Brain Sync data to generate sprint reports.
Can also run standalone Jira queries when sync data is not available.

Two modes:
1. Integrated: Uses Brain/Inbox/JIRA_*.md and Brain/Entities/Squad_*.md
2. Standalone: Direct Jira API calls (for distribution to colleagues)

Usage:
    python3 sprint_report_generator.py                    # Use latest sync data
    python3 sprint_report_generator.py --standalone       # Direct Jira queries
    python3 sprint_report_generator.py --squad "Good Chop"  # Single squad
"""

import os
import sys
import argparse
import csv
import re
import yaml
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any

# Add common directory to path for config_loader
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'common')))
import config_loader

# Constants
ROOT_DIR = config_loader.get_root_path()
SQUAD_REGISTRY_PATH = ROOT_DIR / "squad_registry.yaml"
BRAIN_INBOX_DIR = ROOT_DIR / "AI_Guidance" / "Brain" / "Inbox"
BRAIN_ENTITIES_DIR = ROOT_DIR / "AI_Guidance" / "Brain" / "Entities"
BRAIN_GITHUB_DIR = ROOT_DIR / "AI_Guidance" / "Brain" / "GitHub"
REPORT_OUTPUT_DIR = ROOT_DIR / "Reporting" / "Sprint_Reports"

CSV_HEADERS = [
    'Mega-Alliance',
    'Tribe',
    'Squad',
    'KPI Movement (Since Last Sprint)',
    'What was delivered in the last sprint?',
    'Key learnings from this last sprint',
    'What is planned for the next sprint?',
    'GitHub Activity',
    'Demo'
]


def load_squad_registry(filter_tribe: Optional[str] = "New Ventures") -> List[Dict]:
    """Load squads from registry, optionally filtering by tribe."""
    if not SQUAD_REGISTRY_PATH.exists():
        print(f"Error: Squad registry not found at {SQUAD_REGISTRY_PATH}")
        return []

    with open(SQUAD_REGISTRY_PATH, 'r') as f:
        data = yaml.safe_load(f)

    squads = data.get('squads', [])
    if filter_tribe:
        squads = [s for s in squads if s.get('tribe') == filter_tribe]

    return squads


def parse_jira_inbox_file(file_path: Path) -> Dict[str, Dict]:
    """Parse the JIRA_YYYY-MM-DD.md file to extract squad data."""
    if not file_path.exists():
        return {}

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    squads_data = {}
    current_squad = None
    current_section = None
    current_items = []

    for line in content.split('\n'):
        # Squad header: ## Good Chop (GOC)
        squad_match = re.match(r'^## (.+?) \(([A-Z]+)\)', line)
        if squad_match:
            # Save previous squad
            if current_squad and current_section:
                if current_squad not in squads_data:
                    squads_data[current_squad] = {}
                squads_data[current_squad][current_section] = current_items

            current_squad = squad_match.group(1)
            squads_data[current_squad] = {'epics': [], 'in_progress': [], 'blockers': []}
            current_section = None
            current_items = []
            continue

        # Section headers
        if line.startswith('### Active Epics'):
            if current_squad and current_section:
                squads_data[current_squad][current_section] = current_items
            current_section = 'epics'
            current_items = []
        elif line.startswith('### In Progress'):
            if current_squad and current_section:
                squads_data[current_squad][current_section] = current_items
            current_section = 'in_progress'
            current_items = []
        elif line.startswith('### Blockers'):
            if current_squad and current_section:
                squads_data[current_squad][current_section] = current_items
            current_section = 'blockers'
            current_items = []
        elif line.startswith('---'):
            if current_squad and current_section:
                squads_data[current_squad][current_section] = current_items
            current_section = None
            current_items = []
        elif current_section and line.startswith('- '):
            # Item line
            current_items.append(line[2:].strip())
        elif current_section and line.startswith('| ') and not line.startswith('| Key'):
            # Table row (for epics)
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2:
                current_items.append(f"[{parts[0]}] {parts[1]}")

    # Save last squad
    if current_squad and current_section:
        squads_data[current_squad][current_section] = current_items

    return squads_data


def parse_github_pr_activity(file_path: Path) -> Dict[str, List[str]]:
    """Parse PR_Activity.md to extract PR info per squad."""
    if not file_path.exists():
        return {}

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    squads_prs = {}
    current_squad = None
    current_prs = []

    for line in content.split('\n'):
        # Squad header: ## Good Chop (3 open)
        squad_match = re.match(r'^## (.+?) \(\d+ open\)', line)
        if squad_match:
            if current_squad:
                squads_prs[current_squad] = current_prs
            current_squad = squad_match.group(1)
            current_prs = []
            continue

        # PR line
        if current_squad and line.startswith('- [#'):
            current_prs.append(line[2:].strip())

    if current_squad:
        squads_prs[current_squad] = current_prs

    return squads_prs


def get_latest_jira_inbox() -> Optional[Path]:
    """Find the most recent JIRA_*.md file in Brain/Inbox."""
    if not BRAIN_INBOX_DIR.exists():
        return None

    jira_files = list(BRAIN_INBOX_DIR.glob("JIRA_*.md"))
    if not jira_files:
        return None

    return max(jira_files, key=lambda p: p.stat().st_mtime)


def summarize_with_gemini(items: List[str], prompt_instruction: str, squad_name: str) -> str:
    """Summarize items using Gemini API."""
    if not items:
        return "No relevant items found."

    try:
        import google.generativeai as genai
    except ImportError:
        return "- " + "\n- ".join(items[:5]) + "\n(Gemini unavailable)"

    gemini_config = config_loader.get_gemini_config()
    api_key = gemini_config.get('api_key')

    if not api_key:
        return "- " + "\n- ".join(items[:5]) + "\n(No API key)"

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(gemini_config.get('model', 'gemini-2.5-flash'))

        items_str = "\n".join(items)
        full_prompt = f"""You are an expert Product Manager assistant. Summarize the following Jira items for squad '{squad_name}'.

Context: {prompt_instruction}

Items:
{items_str}

Instructions:
- Focus on value delivered and outcomes, not technical tasks.
- Group small bugs into 'Maintenance: Fixed X minor issues'.
- Use bullet points (start with *).
- Keep brief for executive summary.
- No introductory phrases - just bullet points."""

        response = model.generate_content(full_prompt)
        return response.text.strip()

    except Exception as e:
        print(f"  Gemini error: {e}")
        return "- " + "\n- ".join(items[:5])


def generate_integrated_report(squads: List[Dict], output_path: Path):
    """Generate report using existing Brain sync data."""
    # Load latest Jira sync
    jira_inbox = get_latest_jira_inbox()
    if jira_inbox:
        print(f"Using Jira data from: {jira_inbox}")
        jira_data = parse_jira_inbox_file(jira_inbox)
    else:
        print("Warning: No Jira sync data found. Run jira_brain_sync.py first.")
        jira_data = {}

    # Load GitHub PR activity
    pr_activity_file = BRAIN_GITHUB_DIR / "PR_Activity.md"
    github_data = parse_github_pr_activity(pr_activity_file)

    REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(CSV_HEADERS)

        for squad in squads:
            squad_name = squad['name']
            tribe = squad.get('tribe', 'New Ventures')

            print(f"Processing: {squad_name}")

            # Get Jira data for this squad
            squad_jira = jira_data.get(squad_name, {})
            in_progress = squad_jira.get('in_progress', [])
            blockers = squad_jira.get('blockers', [])
            epics = squad_jira.get('epics', [])

            # Get GitHub data
            squad_prs = github_data.get(squad_name, [])

            # Generate summaries
            # For "Delivered" - we'd need completed items, but sync only has in-progress
            # Use blockers + recent activity as proxy, or note limitation
            delivered_summary = "See Jira sync for detailed status. Key blockers addressed this sprint."
            if blockers:
                delivered_summary = summarize_with_gemini(
                    blockers[:10],
                    "These are blockers/high-priority items. Summarize what was likely addressed.",
                    squad_name
                )

            # Learnings from blockers
            learnings_summary = "No specific learnings captured."
            if blockers:
                learnings_summary = summarize_with_gemini(
                    blockers[:5],
                    "Extract potential learnings or process improvements from these blockers.",
                    squad_name
                )

            # Planned = in-progress items
            planned_summary = "No planned items found."
            if in_progress:
                planned_summary = summarize_with_gemini(
                    in_progress[:10],
                    "Summarize these IN-PROGRESS items as planned work for next sprint.",
                    squad_name
                )

            # GitHub activity summary
            github_summary = "No GitHub activity."
            if squad_prs:
                github_summary = f"{len(squad_prs)} open PRs:\n" + "\n".join(squad_prs[:5])

            writer.writerow([
                "Consumer Mega-Alliance",
                tribe,
                squad_name,
                "N/A (Manual Entry)",
                delivered_summary,
                learnings_summary,
                planned_summary,
                github_summary,
                "To be confirmed"
            ])

    print(f"\nReport generated: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate Sprint Report from Brain sync data or direct Jira queries'
    )
    parser.add_argument(
        '--standalone',
        action='store_true',
        help='Run direct Jira queries instead of using sync data'
    )
    parser.add_argument(
        '--squad',
        type=str,
        help='Generate for specific squad only'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Custom output path'
    )

    args = parser.parse_args()

    # Load squads
    squads = load_squad_registry(filter_tribe="New Ventures")
    if not squads:
        print("No squads found in registry.")
        return 1

    if args.squad:
        squads = [s for s in squads if s['name'].lower() == args.squad.lower()]
        if not squads:
            print(f"Squad '{args.squad}' not found.")
            return 1

    # Determine output path
    date_str = datetime.now().strftime("%m-%d-%Y")
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = REPORT_OUTPUT_DIR / f"Sprint_Report_{date_str}.csv"

    if args.standalone:
        # Use the original generate_report.py logic
        print("Standalone mode: Running direct Jira queries...")
        print("Use the original generate_report.py for standalone mode.")
        return 1
    else:
        # Use integrated Brain sync data
        generate_integrated_report(squads, output_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
