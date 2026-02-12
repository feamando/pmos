"""
PM-OS Tools Package

Core tools for PM-OS 3.0 operations.

Usage:
    from tools import get_config, get_paths, validate_entity

    config = get_config()
    paths = get_paths()
"""

from .config_loader import (
    ConfigError,
    ConfigFileError,
    ConfigLoader,
    ConfigMissingError,
    ConfigValidationError,
    get_config,
    get_user_email,
    get_user_name,
    is_confucius_enabled,
    is_fpf_enabled,
    reset_config,
)
from .entity_validator import (
    BatchValidationResult,
    EntityType,
    EntityValidator,
    ValidationResult,
    fix_entity,
    validate_all_entities,
    validate_entity,
)
from .path_resolver import (
    PathResolutionError,
    PathResolver,
    ResolvedPaths,
    get_brain,
    get_common,
    get_paths,
    get_root,
    get_tools,
    get_user,
    is_v24_mode,
    reset_paths,
)

__version__ = "3.0.0"

__all__ = [
    # Config
    "ConfigLoader",
    "ConfigError",
    "ConfigMissingError",
    "ConfigValidationError",
    "ConfigFileError",
    "get_config",
    "reset_config",
    "get_user_name",
    "get_user_email",
    "is_fpf_enabled",
    "is_confucius_enabled",
    # Paths
    "PathResolver",
    "PathResolutionError",
    "ResolvedPaths",
    "get_paths",
    "reset_paths",
    "get_root",
    "get_common",
    "get_user",
    "get_brain",
    "get_tools",
    "is_v24_mode",
    # Validation
    "EntityValidator",
    "EntityType",
    "ValidationResult",
    "BatchValidationResult",
    "validate_entity",
    "validate_all_entities",
    "fix_entity",
]
