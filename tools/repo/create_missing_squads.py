import os
import sys
from pathlib import Path

# Add tools directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# Add repo directory to path for sibling imports
sys.path.insert(0, str(Path(__file__).parent))
from update_brain_ownership import find_entity_file, parse_squad_map


def create_stub_content(squad_name, repo_data):
    """Generates basic content for a new Squad entity."""
    # Normalize name for title: squad-rte-vms -> RTE VMS
    clean_name = squad_name.replace("squad-", "").replace("-", " ").title()

    # Try to guess tribe or domain if possible, otherwise generic
    tribe = "TBD"

    content = f"""# Squad: {clean_name}

## Metadata
- **Type**: Squad
- **Tribe**: {tribe}
- **Status**: Active

## Focus & Scope
*Auto-generated stub. Please add details.*

## Codebase Ownership
"""
    # We let the update_brain_ownership script handle the detailed repo links
    # to keep logic centralized, but we could add them here.
    # For now, we just leave the header or let the other script append/fix it.
    # Actually, the other script appends/replaces the *whole* section.
    # So we can just leave the file without the section, or with an empty one.

    return content


def create_missing_squads():
    root_path = config_loader.get_root_path()
    base_dir = root_path / "user" / "brain"
    map_path = base_dir / "Architecture" / "Squad_Code_Map.md"
    entities_dir = base_dir / "Entities"

    if not map_path.exists():
        print(f"Error: {map_path} not found.")
        return

    mappings = parse_squad_map(map_path)
    print(f"Checking {len(mappings)} squads...")

    created_count = 0

    for squad in mappings.keys():
        # Check if exists using the same logic as the updater
        existing_file = find_entity_file(squad, entities_dir)

        if not existing_file:
            # Determine filename: Squad_[Name].md
            # Normalize: squad-rte-vms -> Squad_RTE_VMS.md
            # Or keep it simple: Squad_rte_vms.md

            # Helper to format filename nicely
            raw_name = squad.replace("squad-", "")
            # snake_case to Camel_Snake_Case roughly
            parts = raw_name.split("-")
            formatted_parts = [p.capitalize() for p in parts]
            filename = f"Squad_{'_'.join(formatted_parts)}.md"

            new_file_path = entities_dir / filename

            print(f"Creating {filename} for {squad}...")

            content = create_stub_content(squad, mappings[squad])

            with open(new_file_path, "w", encoding="utf-8") as f:
                f.write(content)

            created_count += 1

    print(f"\nCreated {created_count} new squad entities.")


if __name__ == "__main__":
    create_missing_squads()
