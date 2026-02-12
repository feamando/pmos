import csv
import io
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

# Add parent directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# Configuration
ROOT_DIR = config_loader.get_root_path()
BRAIN_DIR = ROOT_DIR / "user" / "brain"
INBOX_DIR = BRAIN_DIR / "Inbox"
JIRA_TOOL = f"{sys.executable} {ROOT_DIR}/common/tools/mcp/jira_mcp/server.py --cli search_issues"
ENTITIES_DIR = str(BRAIN_DIR / "Entities")
REGISTRY_FILE = str(BRAIN_DIR / "registry.yaml")


def get_latest_inbox_file():
    """Find the most recent INBOX file in the Inbox directory."""
    inbox_files = list(INBOX_DIR.glob("INBOX_*.md"))
    if not inbox_files:
        return None
    # Sort by name (dates sort lexicographically) and get latest
    inbox_files.sort()
    return str(inbox_files[-1])


def run_jira_search(jql):
    try:
        cmd = f'{JIRA_TOOL} "{jql}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            return []
        lines = result.stdout.strip().split("\n")
        return [l for l in lines if l.startswith("[")]
    except Exception:
        return []


def parse_inbox_file():
    inbox_file = get_latest_inbox_file()
    if not inbox_file:
        print("Error: No INBOX files found in", INBOX_DIR)
        return []

    print(f"Reading from: {inbox_file}")
    with open(inbox_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the EA Squad doc section
    start_marker = "### DOC: EA Squad overview"
    end_marker = "----------------------------------------"

    start_idx = content.find(start_marker)
    if start_idx == -1:
        print("DEBUG: Could not find start marker '### DOC: EA Squad overview'")
        return []

    # Find the table header "Tribe ,Squad"
    # It might be preceded by empty lines or ",,,,,,,,"
    header_marker = "Tribe ,Squad"
    csv_start = content.find(header_marker, start_idx)

    if csv_start == -1:
        print(
            f"DEBUG: Could not find header marker '{header_marker}' after index {start_idx}"
        )
        return []

    print(f"DEBUG: Found CSV start at index {csv_start}")

    # Find the end of this section (next doc separator)
    # We look for the separator that comes *after* the content body
    # The header is followed by rows, then eventually a separator.
    # We need to find the *next* "----------------------------------------" after the csv_start
    section_end = content.find(end_marker, csv_start)

    if section_end == -1:
        csv_content = content[csv_start:]
    else:
        csv_content = content[csv_start:section_end]

    print(f"DEBUG: Extracted CSV content length: {len(csv_content)}")

    return csv_content


def clean_name(name):
    if not name:
        return None
    # Remove extra spaces, handle "(Start Date)"
    name = re.sub(r"\[.*?\]", "", name).strip()
    return name


def generate_safe_filename(name):
    return name.replace(" ", "_").replace("&", "and").replace("/", "_").replace(".", "")


def main():
    csv_text = parse_inbox_file()
    if not csv_text:
        return

    # Parse CSV using the raw string to handle multi-line cells correctly
    reader = csv.DictReader(io.StringIO(csv_text))

    # Normalize keys (remove newlines from headers)
    reader.fieldnames = [f.replace("\n", " ") for f in reader.fieldnames]

    new_registry_entries = {}

    for row in reader:
        # Check if row is valid (has Tribe/Squad)
        if not row.get("Tribe ") or not row.get("Squad"):
            continue

        tribe = row["Tribe "].strip()
        squad = row["Squad"].strip()
        kpi = row.get("Squad KPI (Q1.2026)", "").strip()
        pm = clean_name(row.get("PM", ""))
        em = clean_name(row.get("EM", ""))
        # Key might vary due to spacing or newlines
        backlog_key = next((k for k in row.keys() if "Backlog" in k), None)
        backlog_url = row.get(backlog_key, "").strip() if backlog_key else ""

        slack = row.get("Slack Channel", "").strip()

        tre_key = next((k for k in row.keys() if "Technical domain" in k), None)
        tre_link = row.get(tre_key, "").strip() if tre_key else ""

        info_key = next((k for k in row.keys() if "More information" in k), None)
        more_info = row.get(info_key, "").strip() if info_key else ""

        print(f"Processing Squad: {squad} ({tribe})")

        # 1. Fetch Epics if Backlog URL exists
        epics = []
        project_key = None
        if "projects/" in backlog_url:
            try:
                # Extract key (e.g. projects/MK/boards/...)
                match = re.search(r"projects/([A-Z0-9]+)", backlog_url)
                if match:
                    project_key = match.group(1)
                    # Limit to 5 epics to save tokens/time
                    jql = f"project = {project_key} AND issuetype = Epic AND status != Done ORDER BY created DESC"
                    # Optimization: Only fetch if we assume it's needed (omitted for speed this run, or keep it)
                    # We will keep it but maybe skip print to reduce noise
                    # epics = run_jira_search(jql)
                    # actually, let's skip fetching again to save time, unless user specifically asked "extract items".
                    # I did it once. I'll rely on the fact that I did it.
                    # But the file is being overwritten! I must fetch again.
                    epics = run_jira_search(jql)
            except Exception as e:
                print(f"  Error fetching Jira: {e}")

        # 2. Create Squad Entity
        squad_filename = f"Squad_{generate_safe_filename(squad)}.md"
        squad_path = os.path.join(ENTITIES_DIR, squad_filename)

        squad_content = f"""# Squad: {squad}

## Metadata
- **Type**: Squad
- **Tribe**: {tribe}
- **Slack**: `{slack}`
- **PM**: [[{pm}]]
- **EM**: [[{em}]]
- **KPI (Q1 2026)**: {kpi}

## Focus & Scope
Responsible for {squad} within the {tribe} tribe.

## Resources
"""
        if tre_link:
            squad_content += f"- [Technical Domain / TRE]({tre_link})\n"
        if more_info:
            squad_content += f"- [More Information]({more_info})\n"

        if project_key:
            squad_content += f"\n## Jira Project\n- Key: `{project_key}`\n- [Backlog Link]({backlog_url})\n\n"

        if epics:
            squad_content += "## Active Epics\n"
            for epic in epics[:10]:  # Limit to 10
                squad_content += f"- {epic}\n"

        with open(squad_path, "w", encoding="utf-8") as f:
            f.write(squad_content)

        # Register Squad
        new_registry_entries[squad] = {
            "type": "Team",
            "aliases": [f"{squad} Squad"],
            "file": f"Entities/{squad_filename}",
        }

        # 3. Create Person Entities (if they define a name)
        for person, role in [(pm, "Product Manager"), (em, "Engineering Manager")]:
            if person and len(person) > 2:  # Basic check
                person_filename = f"{generate_safe_filename(person)}.md"
                person_path = os.path.join(ENTITIES_DIR, person_filename)

                # Register Person
                new_registry_entries[person] = {
                    "type": "Person",
                    "file": f"Entities/{person_filename}",
                }

                # Only create if doesn't exist to avoid overwriting rich profiles
                if not os.path.exists(person_path):
                    content = f"""# {person}

## Metadata
- **Type**: Person
- **Role**: {role}
- **Team**: [[Squad_{generate_safe_filename(squad)}]] ({tribe})

## Context
{role} for the {squad} squad.
"""
                    with open(person_path, "w", encoding="utf-8") as f:
                        f.write(content)

    # 4. Append to Registry
    print("Updating Registry...")
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE, "r") as f:
            registry = yaml.safe_load(f) or {}
    else:
        registry = {}

    if "entities" not in registry:
        registry["entities"] = {}

    # Merge new entries
    for name, data in new_registry_entries.items():
        if name not in registry["entities"]:
            registry["entities"][name] = data
            print(f"  Registered: {name}")

    with open(REGISTRY_FILE, "w") as f:
        yaml.dump(registry, f, sort_keys=True)


if __name__ == "__main__":
    main()
