#!/usr/bin/env python3
"""
Sprint Report Generator - Active Fetch Version

Generates bi-weekly sprint reports by actively fetching data from Jira
and summarizing it using Gemini.

Key Features:
- Active JQL fetching (Done in last 14d, Active Sprint)
- Summarization of Delivered, Learnings, and Planned work
- Support for both Sprint and Kanban boards (via fallback)

Usage:
    python3 sprint_report_generator.py
    python3 sprint_report_generator.py --squad "Good Chop"
    python3 sprint_report_generator.py --output "my_report.csv"
"""

import os
import sys
import argparse
import csv
import re
import yaml
import subprocess
import json
import glob
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

# Add common directory to path for config_loader
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'common')))
import config_loader

# Constants
ROOT_DIR = config_loader.get_root_path()
SQUAD_REGISTRY_PATH = ROOT_DIR / "squad_registry.yaml"
REPORT_OUTPUT_DIR = ROOT_DIR / "Reporting" / "Sprint_Reports"
JIRA_SCRIPT = ROOT_DIR / "AI_Guidance" / "Tools" / "jira_mcp" / "server.py"
BRAIN_GITHUB_DIR = ROOT_DIR / "AI_Guidance" / "Brain" / "GitHub"
BRAIN_EXPERIMENTS_DIR = ROOT_DIR / "AI_Guidance" / "Brain" / "Experiments"

CSV_HEADERS = [
    'Mega-Alliance',
    'Tribe',
    'Squad',
    'KPI Movement (Since Last Sprint)',
    'What was delivered in the last sprint?',
    'Key learnings from this last sprint',
    'What is planned for the next sprint?',
    'GitHub Activity',
    'Active Experiments',
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

def fetch_jira_issues(jql: str, limit: int = 50) -> List[str]:
    """Execute JQL using the Jira MCP server script."""
    if not JIRA_SCRIPT.exists():
        print(f"Error: Jira script not found at {JIRA_SCRIPT}")
        return []

    cmd = [
        "python",
        str(JIRA_SCRIPT),
        "--cli",
        "search_issues",
        jql
    ]
    
    try:
        # The MCP script prints formatted text. We need to capture it.
        # Note: The MCP output format is designed for human readability (bullet points).
        # We will capture stdout and parse/clean it for the context window.
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        
        # Simple parsing: split by lines, keep non-empty ones
        # The MCP returns "- [KEY] Summary (Status)", which is perfect for LLM context.
        issues = [line for line in output.split('\n') if line.strip()]
        return issues[:limit]
        
    except subprocess.CalledProcessError as e:
        print(f"Jira fetch failed: {e}")
        return []

def get_squad_data(squad: Dict) -> Dict[str, List[str]]:
    """Fetch Delivered and Planned items for a squad."""
    project = squad.get('jira_project')
    if not project:
        return {'delivered': [], 'planned': []}

    print(f"  Fetching Jira data for {squad['name']} ({project})...")

    # 1. Delivered: Resolved in last 14 days
    delivered_jql = f'project = "{project}" AND statusCategory = Done AND resolved >= -14d ORDER BY resolved DESC'
    delivered_items = fetch_jira_issues(delivered_jql, limit=30)

    # 2. Planned: Active Sprint OR Top Backlog
    # Try Active Sprint first
    planned_jql = f'project = "{project}" AND sprint in openSprints() ORDER BY rank ASC'
    planned_items = fetch_jira_issues(planned_jql, limit=30)

    # Fallback to Backlog if no active sprint items found (Kanban mode)
    if not planned_items or "No issues found" in planned_items[0]:
        print("    No active sprint found, falling back to backlog...")
        backlog_jql = f'project = "{project}" AND statusCategory != Done ORDER BY rank ASC'
        planned_items = fetch_jira_issues(backlog_jql, limit=15)

    return {
        'delivered': delivered_items,
        'planned': planned_items
    }

def summarize_with_gemini(items: List[str], mode: str, squad_name: str) -> str:
    """Summarize items using Gemini API based on specific mode instructions."""
    if not items or "No issues found" in items[0]:
        return "No relevant items found."

    try:
        import google.generativeai as genai
    except ImportError:
        return "Gemini library not installed."

    gemini_config = config_loader.get_gemini_config()
    api_key = gemini_config.get('api_key')

    if not api_key:
        return "(No API key)"

    # Mode-specific prompts
    prompts = {
        'delivered': """
Summarize these COMPLETED Jira tickets into a concise, outcome-focused report.
- Focus on value delivered and outcomes, not just technical tasks.
- Group small bugs/tasks into single bullet points (e.g. 'Maintenance: Fixed 3 minor UI bugs').
- Use bullet points starting with *.
- CRITICAL: Append the relevant Jira ticket keys for each point in brackets at the end (e.g., "Implemented new login flow [PROJ-123, PROJ-124]").
- No intro/outro text.
""",
        'learnings': """
Extract key learnings, technical wins, or process improvements from these COMPLETED tickets.
- Highlight achievements or patterns.
- Use bullet points starting with *.
- Keep it brief.
- If nothing notable, return "No specific learnings captured."
""",
        'planned': """
Summarize these PLANNED Jira tickets, focusing on goals and strategic value.
- Group related items into themes.
- Use bullet points starting with *.
- CRITICAL: Append the relevant Jira ticket keys for each point in brackets at the end (e.g., "Launch new payment gateway [PROJ-123]").
- No intro/outro text.
"""
    }

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(gemini_config.get('model', 'gemini-1.5-flash'))

        items_str = "\n".join(items)
        full_prompt = f"""You are an expert Product Manager assistant.
Squad: {squad_name}
Task: {prompts[mode]}

Tickets:
{items_str}
"""
        response = model.generate_content(full_prompt)
        return response.text.strip()

    except Exception as e:
        print(f"  Gemini error: {e}")
        return "(Error generating summary)"

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

def get_active_experiments(squad_name: str, ticket_keys: List[str]) -> str:
    """Fetch active experiments linked to squad or tickets."""
    if not BRAIN_EXPERIMENTS_DIR.exists():
        return "No experiments found (Directory missing)."

    active_experiments = []
    
    # Normalize squad name for matching (e.g. "Good Chop" -> "good_chop")
    squad_slug = squad_name.lower().replace(" ", "_")
    
    for file_path in glob.glob(str(BRAIN_EXPERIMENTS_DIR / "*.md")):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Check Status
            if "status: active" not in content.lower():
                continue
                
            # Check Linkage
            is_linked = False
            
            # 1. Linked to Squad
            if f"[[Squad_{squad_name}]]" in content or f"[[{squad_name}]]" in content:
                is_linked = True
            
            # 2. Linked to Ticket
            if not is_linked and ticket_keys:
                for key in ticket_keys:
                    if key in content:
                        is_linked = True
                        break
            
            if is_linked:
                # Extract Name (First H1)
                match = re.search(r'^# (.+)$', content, re.MULTILINE)
                name = match.group(1) if match else Path(file_path).stem
                
                # Extract ID
                id_match = re.search(r'id: (.+)', content)
                exp_id = id_match.group(1).strip() if id_match else "unknown"
                
                active_experiments.append(f"- **{name}** (`{exp_id}`)")
                
        except Exception as e:
            continue
            
    if not active_experiments:
        return "No active experiments linked."
        
    return "\n".join(active_experiments)

def extract_keys_from_items(items: List[str]) -> List[str]:
    """Extract Jira keys [KEY] from item strings."""
    keys = []
    for item in items:
        match = re.search(r'\[([A-Z]+-\d+)\]', item)
        if match:
            keys.append(match.group(1))
    return keys

def generate_report(squads: List[Dict], output_path: Path):
    """Main generation loop."""
    
    # Load GitHub data
    pr_activity_file = BRAIN_GITHUB_DIR / "PR_Activity.md"
    github_data = parse_github_pr_activity(pr_activity_file)

    REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(CSV_HEADERS)

        for squad in squads:
            squad_name = squad['name']
            print(f"Processing: {squad_name}")

            # 1. Fetch Data
            data = get_squad_data(squad)
            
            # Extract ticket keys for matching
            all_ticket_keys = extract_keys_from_items(data['delivered'] + data['planned'])
            
            # 2. Generate Summaries
            delivered_summary = summarize_with_gemini(data['delivered'], 'delivered', squad_name)
            learnings_summary = summarize_with_gemini(data['delivered'], 'learnings', squad_name)
            planned_summary = summarize_with_gemini(data['planned'], 'planned', squad_name)

            # 3. GitHub Data
            squad_prs = github_data.get(squad_name, [])
            github_summary = "No GitHub activity."
            if squad_prs:
                github_summary = f"{len(squad_prs)} open PRs:\n" + "\n".join(squad_prs[:5])

            # 4. Active Experiments
            experiments_summary = get_active_experiments(squad_name, all_ticket_keys)

            # 5. Write Row
            writer.writerow([
                "Consumer Mega-Alliance",
                squad.get('tribe', 'New Ventures'),
                squad_name,
                "N/A (Manual Entry)",
                delivered_summary,
                learnings_summary,
                planned_summary,
                github_summary,
                experiments_summary,
                "To be confirmed"
            ])

    print(f"\nReport generated: {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Generate Sprint Report')
    parser.add_argument('--squad', type=str, help='Generate for specific squad only')
    parser.add_argument('--output', type=str, help='Custom output path')
    args = parser.parse_args()

    squads = load_squad_registry()
    if not squads:
        return 1

    if args.squad:
        squads = [s for s in squads if s['name'].lower() == args.squad.lower()]
        if not squads:
            print(f"Squad '{args.squad}' not found.")
            return 1

    date_str = datetime.now().strftime("%m-%d-%Y")
    output_path = Path(args.output) if args.output else REPORT_OUTPUT_DIR / f"Sprint_Report_{date_str}.csv"

    generate_report(squads, output_path)
    return 0

if __name__ == "__main__":
    sys.exit(main())