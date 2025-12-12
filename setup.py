import os
import sys
import shutil
import datetime
import subprocess
from pathlib import Path

# --- Configuration ---
MIN_PYTHON_VERSION = (3, 8)
PAYLOAD_DIR = Path("payload")
TARGET_DIR = Path(".")

def check_python_version():
    if sys.version_info < MIN_PYTHON_VERSION:
        print(f"Error: Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}+ is required.")
        sys.exit(1)

def prompt_user(prompt, default=None):
    if default:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    else:
        while True:
            user_input = input(f"{prompt}: ").strip()
            if user_input:
                return user_input

def install_dependencies():
    print("\n--- Installing Dependencies ---")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    except subprocess.CalledProcessError:
        print("Warning: Dependency installation failed. You may need to run 'pip install -r requirements.txt' manually.")

def process_templates(context):
    print("\n--- Configuring System ---")
    
    # Process Persona Template
    rules_dir = TARGET_DIR / "AI_Guidance" / "Rules"
    persona_template = rules_dir / "PERSONA_TEMPLATE.md"
    
    # Determine new filename based on last name (e.g., Gorshkov -> NGO.md style, or just USER.md)
    # We will stick to USER.md for simplicity, or initials
    initials = "".join([n[0] for n in context["USER_NAME"].split()]).upper()
    persona_file = rules_dir / f"{initials}.md"
    
    if persona_template.exists():
        content = persona_template.read_text(encoding="utf-8")
        for key, value in context.items():
            content = content.replace(f"{{{{ {key} }}}}", str(value))
        
        persona_file.write_text(content, encoding="utf-8")
        print(f"Created Persona: {persona_file}")
        persona_template.unlink() # Remove template
        
        # Update boot.ps1 and AGENT.md to reference the new persona file
        # This is a basic find-replace
        for file_to_update in [TARGET_DIR / "boot.ps1", TARGET_DIR / "AI_Guidance" / "Rules" / "AGENT.md"]:
            if file_to_update.exists():
                txt = file_to_update.read_text(encoding="utf-8")
                txt = txt.replace("NGO.md", f"{initials}.md")
                file_to_update.write_text(txt, encoding="utf-8")
                print(f"Updated reference in: {file_to_update}")

    # Process Brain Registry
    registry_template = TARGET_DIR / "AI_Guidance" / "Brain" / "registry_template.yaml"
    registry_file = TARGET_DIR / "AI_Guidance" / "Brain" / "registry.yaml"
    
    if registry_template.exists():
        content = registry_template.read_text(encoding="utf-8")
        for key, value in context.items():
            content = content.replace(f"{{{{ {key} }}}}", str(value))
        
        registry_file.write_text(content, encoding="utf-8")
        print(f"Created Registry: {registry_file}")
        registry_template.unlink()

    # Process Example User Entity
    user_entity_template = TARGET_DIR / "AI_Guidance" / "Brain" / "Entities" / "Example_User.md"
    user_entity_file = TARGET_DIR / "AI_Guidance" / "Brain" / "Entities" / f"{context['USER_NAME_UNDERSCORE']}.md"
    
    if user_entity_template.exists():
        content = user_entity_template.read_text(encoding="utf-8")
        for key, value in context.items():
            content = content.replace(f"{{{{ {key} }}}}", str(value))
        
        user_entity_file.write_text(content, encoding="utf-8")
        print(f"Created User Entity: {user_entity_file}")
        user_entity_template.unlink()
        
    # Process Example Project
    project_template = TARGET_DIR / "AI_Guidance" / "Brain" / "Projects" / "Example_Project.md"
    if project_template.exists():
        content = project_template.read_text(encoding="utf-8")
        for key, value in context.items():
            content = content.replace(f"{{{{ {key} }}}}", str(value))
        project_template.write_text(content, encoding="utf-8")


def main():
    print("========================================")
    print("PM-OS: AI-Native Product Operating System")
    print("           Installation Wizard          ")
    print("========================================")
    
    check_python_version()
    
    # 1. Gather User Context
    print("\n--- Personalization ---")
    context = {}
    context["USER_NAME"] = prompt_user("Your Full Name")
    context["USER_NAME_UNDERSCORE"] = context["USER_NAME"].replace(" ", "_")
    context["USER_ROLE"] = prompt_user("Your Job Title")
    context["TEAM_DESCRIPTION"] = prompt_user("Your Team/Squad Name")
    context["LEADERSHIP_PARTNER"] = prompt_user("Your Main Tech/Design Partner")
    context["REPORTS_TO"] = prompt_user("Your Manager's Name")
    context["PROFESSIONAL_BACKGROUND"] = prompt_user("Brief Professional Background (1 sentence)", default="Product Leader")
    context["DATE"] = datetime.date.today().isoformat()
    
    # 2. Deploy Payload
    print("\n--- Deploying Files ---")
    # In a real install, we copy from payload to current dir. 
    # Since we run this FROM the distribution folder usually, we check.
    
    if not (Path("payload").exists()):
        print("Error: 'payload' directory not found. Run this script from the distribution root.")
        sys.exit(1)

    # Copy recursively
    for item in PAYLOAD_DIR.iterdir():
        target = TARGET_DIR / item.name
        if target.exists():
            print(f"Skipping {item.name} (Already exists)")
        else:
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)
            print(f"Deployed: {item.name}")

    # 3. Process Templates
    process_templates(context)
    
    # 4. Install Deps
    install_dependencies()

    # 5. Environment Setup
    print("\n--- Environment Setup ---")
    env_example = TARGET_DIR / ".env.example"
    env_target = TARGET_DIR / ".env"
    
    if env_example.exists() and not env_target.exists():
        shutil.copy2(env_example, env_target)
        print("Created .env from .env.example")
        print("IMPORTANT: Please edit .env to add your API keys and configuration.")
    elif env_target.exists():
        print(".env already exists. Skipping creation.")
    
    # Create .secrets directory
    secrets_dir = TARGET_DIR / ".secrets"
    if not secrets_dir.exists():
        secrets_dir.mkdir()
        print("Created .secrets directory for Google credentials.")
    
    print("\n========================================")
    print("       Installation Complete!           ")
    print("========================================")
    print("Next Steps:")
    print("1. Review 'AI_Guidance/mcp_client_config.json' (if using MCPs)")
    print("2. Set up Google Credentials in 'AI_Guidance/Tools/gdrive_mcp/'")
    print("3. Run './boot.ps1' to start your first session.")

if __name__ == "__main__":
    main()
