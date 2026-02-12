#!/usr/bin/env python3
"""
PM-OS Configuration Loader

Loads config.yaml and .env, validates schema, provides graceful degradation.
This is the central configuration system for PM-OS 3.0.

Usage:
    from config_loader import get_config

    config = get_config()
    name = config.get("user.name")
    email = config.require("user.email", "Enter your email")
    token = config.require_secret("JIRA_API_TOKEN")

Author: PM-OS Team
Version: 3.0.0
"""

import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional imports with graceful degradation
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    logger.warning("PyYAML not installed. Install with: pip install pyyaml")

try:
    from dotenv import dotenv_values, load_dotenv

    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    logger.warning(
        "python-dotenv not installed. Install with: pip install python-dotenv"
    )


class ConfigError(Exception):
    """Base exception for configuration errors."""

    pass


class ConfigMissingError(ConfigError):
    """Raised when a required configuration value is missing."""

    pass


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails."""

    pass


class ConfigFileError(ConfigError):
    """Raised when configuration file cannot be read."""

    pass


@dataclass
class ConfigMetadata:
    """Metadata about the loaded configuration."""

    config_path: Optional[Path]
    env_path: Optional[Path]
    version: str
    loaded_at: datetime
    validation_errors: List[str]


class ConfigLoader:
    """
    PM-OS Configuration Loader.

    Handles loading and accessing configuration from config.yaml and .env files.
    Provides graceful degradation for missing optional fields and prompts for
    missing required fields.

    Attributes:
        user_path: Path to user/ directory containing config.yaml
        config: Loaded configuration dictionary
        metadata: Information about loaded configuration
    """

    # Required fields that will cause errors if missing
    REQUIRED_FIELDS = [
        "version",
        "user.name",
        "user.email",
    ]

    # Optional fields with defaults
    OPTIONAL_DEFAULTS = {
        "pm_os.fpf_enabled": True,
        "pm_os.confucius_enabled": True,
        "pm_os.auto_update": False,
        "pm_os.default_cli": "claude",
        "brain.auto_create_entities": True,
        "brain.cache_ttl_hours": 24,
    }

    def __init__(self, user_path: Optional[Path] = None, auto_load: bool = True):
        """
        Initialize the configuration loader.

        Args:
            user_path: Path to user/ directory. If None, attempts to discover.
            auto_load: If True, automatically load config on init.
        """
        self.user_path = user_path
        self.config: Dict[str, Any] = {}
        self.metadata: Optional[ConfigMetadata] = None
        self._env_loaded = False

        if auto_load:
            self._discover_and_load()

    def _discover_and_load(self) -> None:
        """Discover user path and load configuration."""
        if self.user_path is None:
            self.user_path = self._find_user_path()

        if self.user_path is None:
            logger.warning("Could not find user/ directory. Using empty config.")
            self.config = {}
            return

        self._load()

    def _find_user_path(self) -> Optional[Path]:
        """
        Find user/ directory using multiple strategies.

        Resolution order:
        1. PM_OS_USER environment variable
        2. Walk up from cwd looking for .pm-os-user marker
        3. Check if cwd contains config.yaml
        4. Check common parent folder structures

        Returns:
            Path to user/ directory, or None if not found.
        """
        # Strategy 1: Environment variable
        if os.getenv("PM_OS_USER"):
            user_path = Path(os.getenv("PM_OS_USER"))
            if user_path.exists() and (user_path / "config.yaml").exists():
                return user_path

        # Strategy 2: Walk up looking for marker
        current = Path.cwd()
        while current != current.parent:
            marker = current / ".pm-os-user"
            if marker.exists():
                return current
            current = current.parent

        # Strategy 3: Check cwd for config.yaml
        if (Path.cwd() / "config.yaml").exists():
            return Path.cwd()

        # Strategy 4: Common structures
        cwd = Path.cwd()

        # Check if we're in pm-os/user/
        if cwd.name == "user" and (cwd / "config.yaml").exists():
            return cwd

        # Check if we're in pm-os/ and user/ exists
        if (cwd / "user" / "config.yaml").exists():
            return cwd / "user"

        # Check if we're in pm-os/user/ (without config.yaml)
        if cwd.name == "user" and (cwd / ".secrets").exists():
            return cwd

        # Check if we're in pm-os/common/ and sibling user/ exists
        if cwd.name == "common" and (cwd.parent / "user").exists():
            return cwd.parent / "user"

        # Check if we're in pm-os/common/tools/ and user/ exists at root
        if cwd.name == "tools" and cwd.parent.name == "common":
            user_path = cwd.parent.parent / "user"
            if user_path.exists():
                return user_path

        # Strategy 5: Check for legacy v2.4 structure (AI_Guidance)
        if (cwd / "AI_Guidance").exists():
            # This is a v2.4 structure, return cwd
            return cwd

        return None

    def _load(self) -> None:
        """Load configuration from config.yaml and .env files."""
        if not YAML_AVAILABLE:
            raise ConfigFileError("PyYAML required. Install with: pip install pyyaml")

        config_path = self.user_path / "config.yaml"
        env_path = self.user_path / ".env"
        validation_errors = []

        # Load .env first (secrets)
        if DOTENV_AVAILABLE and env_path.exists():
            load_dotenv(env_path)
            self._env_loaded = True
            logger.debug(f"Loaded .env from {env_path}")

        # Load config.yaml
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    self.config = yaml.safe_load(f) or {}
                logger.debug(f"Loaded config.yaml from {config_path}")
            except yaml.YAMLError as e:
                raise ConfigFileError(f"Invalid YAML in {config_path}: {e}")
            except IOError as e:
                raise ConfigFileError(f"Cannot read {config_path}: {e}")
        else:
            logger.warning(f"config.yaml not found at {config_path}")
            self.config = {}

        # Validate required fields
        for field in self.REQUIRED_FIELDS:
            if self._get_nested(field) is None:
                validation_errors.append(f"Missing required field: {field}")

        # Store metadata
        self.metadata = ConfigMetadata(
            config_path=config_path if config_path.exists() else None,
            env_path=env_path if env_path.exists() else None,
            version=self.config.get("version", "unknown"),
            loaded_at=datetime.now(),
            validation_errors=validation_errors,
        )

        if validation_errors:
            logger.warning(f"Configuration validation warnings: {validation_errors}")

    def _get_nested(self, key: str) -> Any:
        """
        Get a nested value using dot notation.

        Args:
            key: Dot-separated key path (e.g., "user.name")

        Returns:
            Value at the key path, or None if not found.
        """
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None

        return value

    def _set_nested(self, key: str, value: Any) -> None:
        """
        Set a nested value using dot notation.

        Args:
            key: Dot-separated key path (e.g., "user.name")
            value: Value to set
        """
        keys = key.split(".")
        target = self.config

        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]

        target[keys[-1]] = value

    def _save(self) -> None:
        """Save current configuration to config.yaml."""
        if not YAML_AVAILABLE:
            raise ConfigFileError("PyYAML required for saving")

        if self.user_path is None:
            raise ConfigFileError("No user path configured")

        config_path = self.user_path / "config.yaml"
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Saved config to {config_path}")
        except IOError as e:
            raise ConfigFileError(f"Cannot write to {config_path}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with optional default.

        Args:
            key: Dot-separated key path (e.g., "user.name")
            default: Value to return if key not found

        Returns:
            Configuration value or default.
        """
        value = self._get_nested(key)
        if value is None:
            # Check OPTIONAL_DEFAULTS
            if key in self.OPTIONAL_DEFAULTS:
                return self.OPTIONAL_DEFAULTS[key]
            return default
        return value

    def require(self, key: str, prompt_message: Optional[str] = None) -> Any:
        """
        Get required configuration value, prompting if missing.

        Args:
            key: Dot-separated key path (e.g., "user.email")
            prompt_message: Message to show when prompting for value.
                           If None and value is missing, raises ConfigMissingError.

        Returns:
            Configuration value.

        Raises:
            ConfigMissingError: If value is missing and no prompt_message provided.
        """
        value = self._get_nested(key)

        if value is None:
            if prompt_message is not None:
                # Interactive prompt
                try:
                    value = input(f"{prompt_message}: ").strip()
                    if value:
                        self._set_nested(key, value)
                        self._save()
                        logger.info(f"Saved {key} to config")
                    else:
                        raise ConfigMissingError(f"No value provided for {key}")
                except EOFError:
                    raise ConfigMissingError(f"Required config missing: {key}")
            else:
                raise ConfigMissingError(f"Required config missing: {key}")

        return value

    def get_secret(self, key: str) -> Optional[str]:
        """
        Get secret from environment variable.

        Args:
            key: Environment variable name (e.g., "JIRA_API_TOKEN")

        Returns:
            Secret value or None if not set.
        """
        return os.getenv(key)

    def require_secret(self, key: str, prompt_message: Optional[str] = None) -> str:
        """
        Get required secret, prompting if missing.

        Args:
            key: Environment variable name
            prompt_message: Message to show when prompting

        Returns:
            Secret value.

        Raises:
            ConfigMissingError: If secret is missing and no prompt provided.
        """
        value = self.get_secret(key)

        if not value:
            if prompt_message is not None:
                try:
                    import getpass

                    value = getpass.getpass(f"{prompt_message}: ")
                    if value:
                        os.environ[key] = value
                        logger.info(f"Set {key} in environment (not persisted)")
                    else:
                        raise ConfigMissingError(f"No value provided for {key}")
                except (EOFError, ImportError):
                    raise ConfigMissingError(f"Required secret missing: {key}")
            else:
                raise ConfigMissingError(f"Required secret missing: {key}")

        return value

    def get_list(self, key: str, default: Optional[List] = None) -> List:
        """
        Get configuration value as a list.

        Args:
            key: Dot-separated key path
            default: Default list if not found

        Returns:
            List value or default.
        """
        value = self.get(key, default)
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        Get configuration value as boolean.

        Args:
            key: Dot-separated key path
            default: Default boolean if not found

        Returns:
            Boolean value.
        """
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "1", "on")
        return bool(value)

    def is_integration_enabled(self, integration: str) -> bool:
        """
        Check if an integration is enabled.

        Args:
            integration: Integration name (e.g., "jira", "slack")

        Returns:
            True if integration is enabled.
        """
        return self.get_bool(f"integrations.{integration}.enabled", False)

    def get_integration_config(self, integration: str) -> Dict[str, Any]:
        """
        Get full configuration for an integration.

        Args:
            integration: Integration name

        Returns:
            Integration configuration dictionary.
        """
        return self.get(f"integrations.{integration}", {}) or {}

    def validate(self) -> List[str]:
        """
        Validate configuration against schema.

        Returns:
            List of validation error messages (empty if valid).
        """
        errors = []

        # Check version
        version = self.get("version")
        if not version:
            errors.append("Missing version field")
        elif not version.startswith("3."):
            errors.append(f"Unsupported config version: {version}")

        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if self._get_nested(field) is None:
                errors.append(f"Missing required field: {field}")

        return errors

    def __repr__(self) -> str:
        """String representation of config loader."""
        return (
            f"ConfigLoader(user_path={self.user_path}, "
            f"version={self.get('version', 'unknown')}, "
            f"loaded={self.metadata is not None})"
        )


# Singleton instance
_config: Optional[ConfigLoader] = None


def get_config(
    user_path: Optional[Path] = None, force_reload: bool = False
) -> ConfigLoader:
    """
    Get the configuration loader singleton.

    Args:
        user_path: Override user path (optional)
        force_reload: Force reload configuration

    Returns:
        ConfigLoader instance.
    """
    global _config

    if _config is None or force_reload:
        _config = ConfigLoader(user_path)

    return _config


def reset_config() -> None:
    """Reset the configuration singleton (for testing)."""
    global _config
    _config = None


# Convenience functions
def get_user_name() -> str:
    """Get user's name from config."""
    return get_config().require("user.name", "Enter your name")


def get_user_email() -> str:
    """Get user's email from config."""
    return get_config().require("user.email", "Enter your email")


def is_fpf_enabled() -> bool:
    """Check if FPF (First Principles Framework) is enabled."""
    return get_config().get_bool("pm_os.fpf_enabled", True)


def is_confucius_enabled() -> bool:
    """Check if Confucius note-taker is enabled."""
    return get_config().get_bool("pm_os.confucius_enabled", True)


# ============================================================================
# BACKWARD COMPATIBILITY FUNCTIONS (v2.4 API)
# These functions provide compatibility with tools written for the old API
# ============================================================================


def get_google_paths() -> dict:
    """
    Get Google OAuth credential paths.

    Returns:
        Dict with 'credentials' and 'token' paths.
    """
    config = get_config()
    user_path = config.user_path or Path.cwd()
    secrets_dir = user_path / ".secrets"

    return {
        "credentials": str(secrets_dir / "credentials.json"),
        "token": str(secrets_dir / "token.json"),
    }


def get_jira_config() -> dict:
    """
    Get Jira API configuration.

    Returns:
        Dict with 'url', 'username', 'api_token'.
    """
    config = get_config()
    return {
        "url": config.get("integrations.jira.url") or os.getenv("JIRA_URL"),
        "username": config.get("integrations.jira.username")
        or os.getenv("JIRA_USERNAME"),
        "api_token": config.get_secret("JIRA_API_TOKEN"),
    }


def get_gemini_config() -> dict:
    """
    Get Gemini API configuration.

    Returns:
        Dict with 'api_key', 'model'.
    """
    config = get_config()
    return {
        "api_key": config.get_secret("GEMINI_API_KEY"),
        "model": config.get("integrations.gemini.model")
        or os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    }


def get_github_config() -> dict:
    """
    Get GitHub configuration.

    Returns:
        Dict with 'token', 'org'.
    """
    config = get_config()
    return {
        "token": config.get_secret("GITHUB_TOKEN"),
        "org": config.get("integrations.github.org")
        or os.getenv("GITHUB_ORG", "acme-corp"),
    }


def get_slack_config() -> dict:
    """
    Get Slack configuration.

    Returns:
        Dict with 'bot_token', 'user_id', 'channel'.
    """
    config = get_config()
    return {
        "bot_token": config.get_secret("SLACK_BOT_TOKEN"),
        "user_id": config.get_secret("SLACK_USER_ID"),
        "channel": config.get("integrations.slack.channel")
        or os.getenv("SLACK_CHANNEL", "CXXXXXXXXXX"),
    }


def get_confluence_config() -> dict:
    """
    Get Confluence configuration (uses same creds as Jira).

    Returns:
        Dict with 'url', 'username', 'api_token'.
    """
    return get_jira_config()


def get_slack_mention_bot_name() -> str:
    """
    Get the configured Slack mention bot name.

    Returns:
        Bot name (e.g., 'pmos-slack-bot') without the @ prefix.
        Defaults to 'bot' if not configured.
    """
    config = get_config()
    return config.get("integrations.slack.mention_bot_name", "bot")


def get_statsig_config() -> dict:
    """
    Get Statsig configuration.

    Returns:
        Dict with 'api_key'.
    """
    config = get_config()
    return {"api_key": config.get_secret("STATSIG_CONSOLE_API_KEY")}


def get_meeting_prep_config() -> dict:
    """
    Get meeting prep configuration.

    Returns:
        Dict with meeting prep settings including:
        - prep_hours: Hours before meeting to prepare (default: 12)
        - default_depth: 'standard' or 'quick' (default: 'standard')
        - preferred_model: 'auto', 'gemini', 'claude', or 'template' (default: 'auto')
        - task_inference: Settings for task completion inference
        - section_defaults: Dynamic section length defaults
        - type_overrides: Per-meeting-type configuration overrides
    """
    config = get_config()

    # Default section settings
    default_section_defaults = {
        "tldr": {"min": 3, "max": 7},
        "action_items": {"min": 0, "max": 20},
        "topics": {"min": 2, "max": 10, "relevance_threshold": 0.5},
        "questions": {"min": 0, "max": 5, "relevance_threshold": 0.7},
    }

    # Default task inference settings
    default_task_inference = {
        "enabled": True,
        "sources": {
            "slack": True,
            "jira": True,
            "github": True,
            "brain": True,
            "daily_context": True,
        },
        "confidence_threshold": 0.6,
    }

    # Default type overrides
    default_type_overrides = {
        "1on1": {"max_words": 300},
        "standup": {"max_words": 150},
        "large_meeting": {"max_words": 200},
        "external": {"max_words": 500},
        "interview": {"max_words": 1000},
        "review": {"max_words": 400},
        "planning": {"max_words": 400},
        "other": {"max_words": 400},
    }

    return {
        "prep_hours": config.get("meeting_prep.prep_hours", 12),
        "default_depth": config.get("meeting_prep.default_depth", "standard"),
        "preferred_model": config.get("meeting_prep.preferred_model", "auto"),
        "task_inference": config.get(
            "meeting_prep.task_inference", default_task_inference
        ),
        "section_defaults": config.get(
            "meeting_prep.section_defaults", default_section_defaults
        ),
        "type_overrides": config.get(
            "meeting_prep.type_overrides", default_type_overrides
        ),
    }


def is_claude_code_session() -> bool:
    """
    Check if running in a Claude Code session.

    Returns:
        True if CLAUDE_CODE_SESSION environment variable is set.
    """
    return bool(os.getenv("CLAUDE_CODE_SESSION"))


def get_root_path() -> Path:
    """
    Get PM-OS root path.

    Returns:
        Path to PM-OS root (parent of common/ and user/)
    """
    config = get_config()
    if config.user_path:
        return config.user_path.parent
    # Fallback: tools dir -> common -> pm-os root
    return Path(__file__).parent.parent.parent


def get_common_path() -> Path:
    """
    Get PM-OS common directory path.

    Returns:
        Path to PM-OS common/ (contains tools, frameworks, rules)
    """
    # config_loader.py is in common/tools/, so parent.parent is common/
    return Path(__file__).parent.parent


# ============================================================================
# WORKSPACE CONFIGURATION FUNCTIONS (WCR)
# These functions provide access to the new workflow-centric config
# ============================================================================


def get_products_config() -> dict:
    """
    Get products hierarchy configuration.

    Returns:
        Dict with 'organization' (optional) and 'items' list.
        Each item has: id, name, type, jira_project, squad, market, status
    """
    config = get_config()
    return config.get("products", {}) or {}


def get_product_ids() -> List[str]:
    """
    Get list of configured product IDs.

    Returns:
        List of product ID strings (e.g., ['meal-kit', 'wellness-brand'])
    """
    products = get_products_config()
    items = products.get("items", [])
    return [item.get("id") for item in items if item.get("id")]


def get_product_by_id(product_id: str) -> Optional[dict]:
    """
    Get product configuration by ID.

    Args:
        product_id: Product identifier (e.g., 'meal-kit')

    Returns:
        Product config dict or None if not found.
    """
    products = get_products_config()
    for item in products.get("items", []):
        if item.get("id") == product_id:
            return item
    return None


def get_product_by_jira_project(jira_project: str) -> Optional[dict]:
    """
    Get product configuration by Jira project key.

    Args:
        jira_project: Jira project key (e.g., 'MK')

    Returns:
        Product config dict or None if not found.
    """
    products = get_products_config()
    for item in products.get("items", []):
        if item.get("jira_project") == jira_project:
            return item
    return None


def get_organization_config() -> Optional[dict]:
    """
    Get organization/tribe level configuration.

    Returns:
        Organization config dict or None if not configured.
    """
    products = get_products_config()
    return products.get("organization")


def get_team_config() -> dict:
    """
    Get team structure configuration.

    Returns:
        Dict with 'manager', 'reports', and 'stakeholders'.
    """
    config = get_config()
    return config.get("team", {}) or {}


def get_team_reports() -> List[dict]:
    """
    Get list of direct reports.

    Returns:
        List of report configs with: id, name, email, slack_id, role, squad
    """
    team = get_team_config()
    return team.get("reports", [])


def get_report_by_id(report_id: str) -> Optional[dict]:
    """
    Get direct report configuration by ID.

    Args:
        report_id: Report identifier (e.g., 'alice-engineer')

    Returns:
        Report config dict or None if not found.
    """
    for report in get_team_reports():
        if report.get("id") == report_id:
            return report
    return None


def get_report_by_email(email: str) -> Optional[dict]:
    """
    Get direct report configuration by email.

    Args:
        email: Email address

    Returns:
        Report config dict or None if not found.
    """
    for report in get_team_reports():
        if report.get("email") == email:
            return report
    return None


def get_manager_config() -> Optional[dict]:
    """
    Get manager configuration.

    Returns:
        Manager config dict or None if not configured.
    """
    team = get_team_config()
    return team.get("manager")


def get_stakeholders() -> List[dict]:
    """
    Get list of key stakeholders (not direct reports).

    Returns:
        List of stakeholder configs.
    """
    team = get_team_config()
    return team.get("stakeholders", [])


def get_personal_config() -> dict:
    """
    Get personal development configuration.

    Returns:
        Dict with 'learning_capture' and 'career' settings.
    """
    config = get_config()
    return config.get("personal", {}) or {}


def get_workspace_config() -> dict:
    """
    Get workspace management configuration.

    Returns:
        Dict with auto_create_folders, standard_subfolders, context_sync settings.
    """
    config = get_config()
    return config.get(
        "workspace",
        {
            "auto_create_folders": True,
            "standard_subfolders": [
                "discovery",
                "planning",
                "execution",
                "reporting",
                "presentations",
                "discussions",
            ],
            "context_sync": {
                "enabled": True,
                "sync_on_boot": True,
                "bidirectional": True,
            },
        },
    )


def get_standard_subfolders() -> List[str]:
    """
    Get standard sub-folder names for products/features.

    Returns:
        List of folder names (e.g., ['discovery', 'planning', ...])
    """
    workspace = get_workspace_config()
    return workspace.get(
        "standard_subfolders",
        [
            "discovery",
            "planning",
            "execution",
            "reporting",
            "presentations",
            "discussions",
        ],
    )


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PM-OS Configuration Loader")
    parser.add_argument("--get", metavar="KEY", help="Get config value")
    parser.add_argument("--set", metavar="KEY=VALUE", help="Set config value")
    parser.add_argument("--validate", action="store_true", help="Validate config")
    parser.add_argument("--info", action="store_true", help="Show config info")
    parser.add_argument("--secret", metavar="KEY", help="Get secret from env")

    args = parser.parse_args()

    try:
        config = get_config()

        if args.get:
            value = config.get(args.get)
            if value is not None:
                print(value)
            else:
                print(f"Key not found: {args.get}", file=sys.stderr)
                sys.exit(1)

        elif args.set:
            if "=" not in args.set:
                print("Use format: KEY=VALUE", file=sys.stderr)
                sys.exit(1)
            key, value = args.set.split("=", 1)
            config._set_nested(key, value)
            config._save()
            print(f"Set {key} = {value}")

        elif args.validate:
            errors = config.validate()
            if errors:
                print("Validation errors:")
                for error in errors:
                    print(f"  - {error}")
                sys.exit(1)
            else:
                print("Configuration is valid")

        elif args.secret:
            value = config.get_secret(args.secret)
            if value:
                print(f"{args.secret} is set")
            else:
                print(f"{args.secret} is not set", file=sys.stderr)
                sys.exit(1)

        elif args.info:
            print(f"Config: {config}")
            if config.metadata:
                print(f"Config path: {config.metadata.config_path}")
                print(f"Env path: {config.metadata.env_path}")
                print(f"Version: {config.metadata.version}")
                print(f"Loaded at: {config.metadata.loaded_at}")
                if config.metadata.validation_errors:
                    print(f"Warnings: {config.metadata.validation_errors}")

        else:
            parser.print_help()

    except ConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
