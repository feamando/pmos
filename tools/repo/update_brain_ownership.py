import os
import re
import sys
from pathlib import Path

# Add tools directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader


def parse_squad_map(map_path):
    """Parses the Squad Code Map markdown table."""
    mappings = {}  # {squad_name: [(repo_link, paths)]}

    with open(map_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Simple table parsing
    for line in lines:
        if not line.strip().startswith("|") or "Squad / Team" in line or "---|" in line:
            continue

        parts = [p.strip() for p in line.split("|")]
        # | Squad | Repo | Paths | Loc |
        # parts[0] is empty string if line starts with |
        if len(parts) < 5:
            continue

        squads_str = parts[1]
        repo_link = parts[2]  # [name](url)
        paths_str = parts[3]

        # Extract squad names
        # Remove markdown bold/code from squads if any, though usually clean
        squads = [s.strip().replace("@acme-corp/", "") for s in squads_str.split(",")]

        for squad in squads:
            if squad == "*Unclaimed*":
                continue

            if squad not in mappings:
                mappings[squad] = []

            mappings[squad].append((repo_link, paths_str))

    return mappings


def find_entity_file(squad_name, entities_dir):
    """Tries to find a matching entity file for a squad name."""
    # Normalize squad name for search (e.g., squad-meal-kit -> Meal Kit)
    normalized = squad_name.replace("squad-", "").replace("-", " ").lower()

    for file_path in entities_dir.glob("*.md"):
        # Check filename
        if normalized in file_path.name.lower().replace("_", " "):
            return file_path
    return None


def update_brain_entities():
    root_path = config_loader.get_root_path()
    base_dir = root_path / "user" / "brain"
    map_path = base_dir / "Architecture" / "Squad_Code_Map.md"
    entities_dir = base_dir / "Entities"

    if not map_path.exists():
        print(f"Error: {map_path} not found.")
        return

    mappings = parse_squad_map(map_path)

    print(f"Found mappings for {len(mappings)} squads.")

    for squad, repo_data in mappings.items():
        # Heuristic: try to find existing file
        candidates = [
            squad,
            squad.replace("squad-", ""),
            squad.replace("-", "_"),
            squad.replace("squad-", "").replace("-", "_"),
        ]

        target_file = None
        for cand in candidates:
            found = list(entities_dir.glob(f"*{cand}*.md"))
            if found:
                target_file = found[0]  # Pick first match
                break

        if target_file:
            print(f"Linking {squad} -> {target_file.name}")
            update_entity_file(target_file, repo_data)
        else:
            print(f"No entity found for {squad}")


def update_entity_file(file_path, repo_data):
    """Appends/Updates Codebase Ownership section."""
    # repo_data is list of (repo_link, paths_str)

    content = file_path.read_text(encoding="utf-8")

    section_header = "## Codebase Ownership"

    lines = []
    for repo_link, paths in repo_data:
        # Format: - [Repo](url): `paths`
        # If paths is ROOT, simplify
        if "**ROOT (*)**" in paths:
            lines.append(f"- {repo_link} (Owner)")
        else:
            lines.append(f"- {repo_link}")
            lines.append(f"  - Paths: {paths}")

    new_content_block = f"\n{section_header}\n" + "\n".join(lines) + "\n"

    # Regex to replace existing section (\Z = end of string)
    pattern = re.compile(rf"{section_header}.*?(?=\n#|\Z)", re.DOTALL)

    if pattern.search(content):
        content = pattern.sub(new_content_block.strip(), content)
    else:
        # Append to end if not found
        content = content.rstrip() + "\n" + new_content_block

    file_path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    update_brain_entities()
