#!/usr/bin/env python3
"""
PM-OS Configuration Loader (v5.0)

Loads config.yaml and .env, validates schema, provides graceful degradation.
Central configuration system for PM-OS 5.0 plugin architecture.

Usage:
    from pm_os_base.tools.core.config_loader import get_config

    config = get_config()
    name = config.get("user.name")
    email = config.require("user.email", "Enter your email")
    token = config.require_secret("JIRA_API_TOKEN")
"""

import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

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


class ConfigError(Exception):
    """Base exception for configuration errors."""


class ConfigMissingError(ConfigError):
    """Raised when a required configuration value is missing."""


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails."""


class ConfigFileError(ConfigError):
    """Raised when configuration file cannot be read."""


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
    """

    REQUIRED_FIELDS = [
        "user.name",
        "user.email",
    ]

    OPTIONAL_DEFAULTS = {
        "pm_os.fpf_enabled": True,
        "pm_os.confucius_enabled": True,
        "pm_os.auto_update": False,
        "pm_os.default_cli": "claude",
        "brain.auto_create_entities": True,
        "brain.cache_ttl_hours": 24,
        "persona.style": "direct",
        "persona.format": "bullets-over-prose",
        "persona.decision_framework": "first-principles",
    }

    def __init__(self, user_path: Optional[Path] = None, auto_load: bool = True):
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
        """
        # Strategy 1: Environment variable
        env_user = os.getenv("PM_OS_USER")
        if env_user:
            user_path = Path(env_user)
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

        if cwd.name == "user" and (cwd / "config.yaml").exists():
            return cwd

        if (cwd / "user" / "config.yaml").exists():
            return cwd / "user"

        if cwd.name == "common" and (cwd.parent / "user").exists():
            return cwd.parent / "user"

        if cwd.name == "tools" and cwd.parent.name == "common":
            user_path = cwd.parent.parent / "user"
            if user_path.exists():
                return user_path

        # Strategy 5: Check inside v5/ workspace
        for parent in [cwd] + list(cwd.parents):
            v5_marker = parent / "v5" / "plugins"
            if v5_marker.exists() and (parent / "user").exists():
                return parent / "user"

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
            logger.debug("Loaded .env from %s", env_path)

        # Load config.yaml
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    self.config = yaml.safe_load(f) or {}
                logger.debug("Loaded config.yaml from %s", config_path)
            except yaml.YAMLError as e:
                raise ConfigFileError(f"Invalid YAML in {config_path}: {e}")
            except IOError as e:
                raise ConfigFileError(f"Cannot read {config_path}: {e}")
        else:
            logger.warning("config.yaml not found at %s", config_path)
            self.config = {}

        # Validate required fields
        for field_name in self.REQUIRED_FIELDS:
            if self._get_nested(field_name) is None:
                validation_errors.append(f"Missing required field: {field_name}")

        self.metadata = ConfigMetadata(
            config_path=config_path if config_path.exists() else None,
            env_path=env_path if env_path.exists() else None,
            version=self.config.get("version", "unknown"),
            loaded_at=datetime.now(),
            validation_errors=validation_errors,
        )

        if validation_errors:
            logger.warning("Configuration validation warnings: %s", validation_errors)

    def _get_nested(self, key: str) -> Any:
        """Get a nested value using dot notation (e.g., 'user.name')."""
        keys = key.split(".")
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        return value

    def _set_nested(self, key: str, value: Any) -> None:
        """Set a nested value using dot notation."""
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
            logger.info("Saved config to %s", config_path)
        except IOError as e:
            raise ConfigFileError(f"Cannot write to {config_path}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with optional default."""
        value = self._get_nested(key)
        if value is None:
            if key in self.OPTIONAL_DEFAULTS:
                return self.OPTIONAL_DEFAULTS[key]
            return default
        return value

    def require(self, key: str, prompt_message: Optional[str] = None) -> Any:
        """Get required configuration value, prompting if missing."""
        value = self._get_nested(key)
        if value is None:
            if prompt_message is not None:
                try:
                    value = input(f"{prompt_message}: ").strip()
                    if value:
                        self._set_nested(key, value)
                        self._save()
                        logger.info("Saved %s to config", key)
                    else:
                        raise ConfigMissingError(f"No value provided for {key}")
                except EOFError:
                    raise ConfigMissingError(f"Required config missing: {key}")
            else:
                raise ConfigMissingError(f"Required config missing: {key}")
        return value

    def get_secret(self, key: str) -> Optional[str]:
        """Get secret from environment variable."""
        return os.getenv(key)

    def require_secret(self, key: str, prompt_message: Optional[str] = None) -> str:
        """Get required secret, prompting if missing."""
        value = self.get_secret(key)
        if not value:
            if prompt_message is not None:
                try:
                    import getpass
                    value = getpass.getpass(f"{prompt_message}: ")
                    if value:
                        os.environ[key] = value
                        logger.info("Set %s in environment (not persisted)", key)
                    else:
                        raise ConfigMissingError(f"No value provided for {key}")
                except (EOFError, ImportError):
                    raise ConfigMissingError(f"Required secret missing: {key}")
            else:
                raise ConfigMissingError(f"Required secret missing: {key}")
        return value

    def get_list(self, key: str, default: Optional[List] = None) -> List:
        """Get configuration value as a list."""
        value = self.get(key, default)
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get configuration value as boolean."""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "1", "on")
        return bool(value)

    def is_integration_enabled(self, integration: str) -> bool:
        """Check if an integration is enabled."""
        return self.get_bool(f"integrations.{integration}.enabled", False)

    def get_integration_config(self, integration: str) -> Dict[str, Any]:
        """Get full configuration for an integration."""
        return self.get(f"integrations.{integration}", {}) or {}

    def validate(self) -> List[str]:
        """Validate configuration against schema."""
        errors = []
        for field_name in self.REQUIRED_FIELDS:
            if self._get_nested(field_name) is None:
                errors.append(f"Missing required field: {field_name}")
        return errors

    def __repr__(self) -> str:
        return (
            f"ConfigLoader(user_path={self.user_path}, "
            f"version={self.get('version', 'unknown')}, "
            f"loaded={self.metadata is not None})"
        )


# --- Singleton ---

_config: Optional[ConfigLoader] = None


def get_config(
    user_path: Optional[Path] = None, force_reload: bool = False
) -> ConfigLoader:
    """Get the configuration loader singleton."""
    global _config
    if _config is None or force_reload:
        _config = ConfigLoader(user_path)
    return _config


def reset_config() -> None:
    """Reset the configuration singleton (for testing)."""
    global _config
    _config = None


# --- Convenience functions ---

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


def get_google_paths() -> dict:
    """Get Google OAuth credential paths."""
    config = get_config()
    user_path = config.user_path or Path.cwd()
    secrets_dir = user_path / ".secrets"
    return {
        "credentials": str(secrets_dir / "credentials.json"),
        "token": str(secrets_dir / "token.json"),
    }


def get_integration_secret(service: str, key: str) -> Optional[str]:
    """Get an integration secret from environment."""
    return get_config().get_secret(key)


def get_products_config() -> dict:
    """Get products hierarchy configuration."""
    return get_config().get("products", {}) or {}


def get_product_ids() -> List[str]:
    """Get list of configured product IDs."""
    products = get_products_config()
    items = products.get("items", [])
    return [item.get("id") for item in items if item.get("id")]


def get_product_by_id(product_id: str) -> Optional[dict]:
    """Get product configuration by ID."""
    products = get_products_config()
    for item in products.get("items", []):
        if item.get("id") == product_id:
            return item
    return None


def get_team_config() -> dict:
    """Get team structure configuration."""
    return get_config().get("team", {}) or {}


def get_team_reports() -> List[dict]:
    """Get list of direct reports."""
    team = get_team_config()
    return team.get("reports", [])


def get_manager_config() -> Optional[dict]:
    """Get manager configuration."""
    team = get_team_config()
    return team.get("manager")


def get_stakeholders() -> List[dict]:
    """Get list of key stakeholders."""
    team = get_team_config()
    return team.get("stakeholders", [])


def get_meeting_prep_config() -> dict:
    """Get meeting prep configuration."""
    config = get_config()
    return {
        "prep_hours": config.get("meeting_prep.prep_hours", 12),
        "default_depth": config.get("meeting_prep.default_depth", "standard"),
        "preferred_model": config.get("meeting_prep.preferred_model", "auto"),
        "workers": config.get("meeting_prep.workers", 10),
        "task_inference": config.get("meeting_prep.task_inference", {
            "enabled": True,
            "sources": {"slack": True, "jira": True, "github": True, "brain": True, "daily_context": True},
            "confidence_threshold": 0.6,
        }),
    }


def get_root_path() -> Path:
    """Get PM-OS root path."""
    config = get_config()
    if config.user_path:
        return config.user_path.parent
    return Path(__file__).resolve().parent.parent.parent.parent.parent


def is_claude_code_session() -> bool:
    """Check if running in a Claude Code session."""
    return bool(os.getenv("CLAUDE_CODE_SESSION"))


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
