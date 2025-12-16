import os
import sys
from pathlib import Path

# Try to import dotenv, but don't fail immediately if not present (bootstrapping)
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Calculate ROOT_DIR: config_loader.py is in AI_Guidance/Tools/common
# So root is 3 levels up: common -> Tools -> AI_Guidance -> ROOT
ROOT_DIR = Path(__file__).parent.parent.parent.parent

def load_env():
    """Load .env file from root directory."""
    env_path = ROOT_DIR / ".env"
    if load_dotenv and env_path.exists():
        load_dotenv(dotenv_path=env_path)
    elif not load_dotenv:
        print("Warning: python-dotenv not installed. Environment variables might not be loaded from .env.", file=sys.stderr)

# Load on import
load_env()

def get_root_path() -> Path:
    return ROOT_DIR

def get_jira_config():
    """Return dictionary with Jira configuration."""
    return {
        "url": os.getenv("JIRA_URL"),
        "username": os.getenv("JIRA_USERNAME"),
        "api_token": os.getenv("JIRA_API_TOKEN")
    }

def get_google_paths():
    """Return dictionary with absolute paths to Google credentials."""
    # Default to .secrets directory
    secrets_dir = ROOT_DIR / ".secrets"
    if not secrets_dir.exists():
        secrets_dir.mkdir(parents=True, exist_ok=True)

    cred_path_rel = os.getenv("GOOGLE_CREDENTIALS_PATH", ".secrets/credentials.json")
    token_path_rel = os.getenv("GOOGLE_TOKEN_PATH", ".secrets/token.json")
    
    # Resolve to absolute paths
    return {
        "credentials": str(ROOT_DIR / cred_path_rel),
        "token": str(ROOT_DIR / token_path_rel)
    }

def get_gemini_config():
    """Return dictionary with Gemini configuration."""
    return {
        "api_key": os.getenv("GEMINI_API_KEY"),
        "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    }

def ensure_dependencies():
    """Check if python-dotenv is installed."""
    if load_dotenv is None:
        print("python-dotenv is missing. Please run: pip install python-dotenv")
