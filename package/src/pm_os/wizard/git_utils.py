"""
Git utilities for auto-detecting user profile information.

Used by quick-start mode to pre-fill user profile from git config.
"""

import subprocess
from typing import Optional, Tuple


def get_git_user_info() -> Tuple[Optional[str], Optional[str]]:
    """Get user name and email from git config.

    Attempts to read git config for user.name and user.email.
    Falls back gracefully if git is not available or not configured.

    Returns:
        Tuple of (name, email), either may be None if not configured
    """
    name = _get_git_config("user.name")
    email = _get_git_config("user.email")
    return name, email


def _get_git_config(key: str) -> Optional[str]:
    """Get a git config value.

    Args:
        key: Git config key (e.g., "user.name")

    Returns:
        Config value or None if not found
    """
    try:
        result = subprocess.run(
            ["git", "config", "--global", key],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # git not installed, not in PATH, or timed out
        pass
    return None


def is_git_available() -> bool:
    """Check if git is available on the system.

    Returns:
        True if git command is available
    """
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
