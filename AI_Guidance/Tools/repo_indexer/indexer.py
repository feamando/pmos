import os
import subprocess
import json
import sys
import base64
from pathlib import Path
from datetime import datetime

# Add parent directory to path to allow importing config_loader if needed
# But for now we'll just use python-dotenv directly or manual parsing if simple
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Manual fallback if dotenv not installed (though it should be)
    env_path = Path(__file__).parents[3] / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    try:
                        key, val = line.strip().split('=', 1)
                        os.environ[key] = val
                    except ValueError:
                        continue

# Configuration
GITHUB_ORG = os.getenv('GITHUB_ORG')

def get_gh_path():
    """Returns the path to gh CLI, cross-platform."""
    import shutil
    # First try to find gh in PATH (works on macOS/Linux)
    gh_in_path = shutil.which('gh')
    if gh_in_path:
        return gh_in_path
    # Fallback to Windows default location
    windows_path = r"C:\Program Files\GitHub CLI\gh.exe"
    if os.path.exists(windows_path):
        return windows_path
    return None

GH_PATH = get_gh_path()

def run_gh_command(args):
    """Executes a gh command and returns the JSON output."""
    if not GH_PATH:
        print("Error: GitHub CLI (gh) not found. Install from https://cli.github.com/")
        sys.exit(1)

    cmd = [GH_PATH] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if result.returncode != 0:
            # Don't print error for 404s (common when checking file existence)
            if "Not Found" not in result.stderr:
                print(f"Error executing gh command: {result.stderr}")
            return None
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Exception running gh: {e}")
        return None

def fetch_file_content(repo_name, path):
    """Fetches file content from a repo using gh api."""
    # gh api repos/:owner/:repo/contents/:path
    response = run_gh_command(['api', f'repos/{GITHUB_ORG}/{repo_name}/contents/{path}'])
    if response and 'content' in response:
        return base64.b64decode(response['content']).decode('utf-8')
    return None

def map_structure():
    """Maps the organization's repositories."""
    if not GITHUB_ORG:
        print("Error: GITHUB_ORG not set in .env")
        return

    print(f"Fetching repositories for org: {GITHUB_ORG}...")
    
    # Fetch repos
    # Fields: name, description, url, language, updatedAt
    repos = run_gh_command([
        'repo', 'list', GITHUB_ORG,
        '--limit', '100',
        '--json', 'name,description,url,primaryLanguage,updatedAt'
    ])

    if not repos:
        print("No repositories found or error occurred.")
        return

    # Generate Markdown using triple quotes to avoid newline issues
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    md_output = f"""# HelloFresh Service Catalog

**Organization:** {GITHUB_ORG}
**Last Updated:** {timestamp}

| Service / Repo | Description | Primary Tech | Last Updated |
|---|---|---|---|
"""

    for repo in repos:
        name = repo.get('name', 'N/A')
        desc = repo.get('description', '') or 'No description'
        # Clean description of newlines
        desc = desc.replace('\n', ' ')
        lang = (repo.get('primaryLanguage') or {}).get('name', 'N/A')
        updated = repo.get('updatedAt', '')[:10] # YYYY-MM-DD
        url = repo.get('url', '')
        
        md_output += f"| [{name}]({url}) | {desc} | {lang} | {updated} |\n"

    # Save to Architecture folder
    output_path = Path(__file__).parents[3] / 'AI_Guidance' / 'Brain' / 'Architecture' / 'Service_Catalog.md'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_output)
    
    print(f"Successfully generated: {output_path}")

def parse_codeowners(content):
    """Parses CODEOWNERS content into a mapping of team -> paths."""
    mapping = {} # {team: [paths]}
    
    if not content:
        return mapping

    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
            
        parts = line.split()
        if len(parts) < 2:
            continue
            
        path_pattern = parts[0]
        owners = parts[1:]
        
        for owner in owners:
            if owner.startswith('@hellofresh/'):
                team = owner.replace('@hellofresh/', '')
                if team not in mapping:
                    mapping[team] = []
                mapping[team].append(path_pattern)
                
    return mapping

def map_ownership():
    """Maps CODEOWNERS to Repositories."""
    if not GITHUB_ORG:
        print("Error: GITHUB_ORG not set in .env")
        return

    print(f"Mapping ownership for org: {GITHUB_ORG}...")
    
    # Reuse fetch logic (could optimize to pass list)
    repos = run_gh_command([
        'repo', 'list', GITHUB_ORG,
        '--limit', '50', # Limit to 50 for ownership to save API calls for now
        '--json', 'name,url'
    ])

    if not repos:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    md_output = f"""# HelloFresh Squad Code Map

**Organization:** {GITHUB_ORG}
**Last Updated:** {timestamp}

| Squad / Team | Repository | Owned Paths | CODEOWNERS Location |
|---|---|---|---|
"""
    
    codeowners_locations = ['.github/CODEOWNERS', 'CODEOWNERS', 'docs/CODEOWNERS']

    for repo in repos:
        name = repo['name']
        print(f"Checking {name}...")
        
        found_owners = False
        for loc in codeowners_locations:
            content = fetch_file_content(name, loc)
            if content:
                ownership_map = parse_codeowners(content)
                
                if ownership_map:
                    found_owners = True
                    # Add row per team
                    for team, paths in ownership_map.items():
                        # Summarize paths if too many
                        if len(paths) > 5:
                            path_str = ", ".join(paths[:5]) + f" (+{len(paths)-5} more)"
                        else:
                            path_str = ", ".join(paths)
                            
                        # If path is '*', make it bold or prominent
                        if '*' in paths:
                            path_str = "**ROOT (*)**"
                        
                        md_output += f"| {team} | [{name}]({repo['url']}) | `{path_str}` | {loc} |\n"
                    
                    break # Found the file, stop checking other locations
        
        if not found_owners:
             md_output += f"| *Unclaimed* | [{name}]({repo['url']}) | N/A | N/A |\n"

    # Save to Architecture folder
    output_path = Path(__file__).parents[3] / 'AI_Guidance' / 'Brain' / 'Architecture' / 'Squad_Code_Map.md'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_output)
    
    print(f"Successfully generated: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == '--map-structure':
            map_structure()
        elif sys.argv[1] == '--map-ownership':
            map_ownership()
        else:
            print("Unknown command")
    else:
        print("Usage: python indexer.py [--map-structure | --map-ownership]")
