#!/usr/bin/env python3
"""
PM-OS v5.0 — Plugin-Extensible Preflight Check Registry

REWRITE from v4.x: Instead of 88 hardcoded tools across 20 categories,
v5.0 uses a plugin-extensible registry. Each plugin registers its own
preflight checks via a `preflight-checks.yaml` file.

Base plugin registers only its own core tools. Other plugins contribute
their checks when installed.

Usage:
    from preflight.registry import CheckRegistry

    registry = CheckRegistry()
    registry.discover_plugins()  # Auto-discover from installed plugins
    categories = registry.get_categories()

Version: 5.0.0
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


# ============================================================================
# BASE PLUGIN CHECKS (only tools that ship with pm-os-base)
# ============================================================================

BASE_CHECKS: Dict[str, Dict[str, Any]] = {
    "core": {
        "config_loader": {
            "path": "tools/core/config_loader.py",
            "module": "tools.core.config_loader",
            "classes": ["ConfigLoader", "ConfigMetadata", "ConfigError"],
            "functions": ["get_config", "reset_config", "get_user_name"],
            "description": "Configuration Loader",
        },
        "path_resolver": {
            "path": "tools/core/path_resolver.py",
            "module": "tools.core.path_resolver",
            "classes": ["PathResolver", "ResolvedPaths"],
            "functions": ["get_paths", "reset_paths", "get_root", "get_common", "get_user"],
            "description": "Path Resolution",
        },
        "entity_validator": {
            "path": "tools/core/entity_validator.py",
            "module": "tools.core.entity_validator",
            "classes": ["EntityValidator", "ValidationResult", "EntityType"],
            "functions": ["validate_entity", "validate_all_entities"],
            "description": "Entity Validator",
        },
        "plugin_deps": {
            "path": "tools/core/plugin_deps.py",
            "module": "tools.core.plugin_deps",
            "functions": ["check_plugin", "require_plugin", "get_installed_plugins"],
            "description": "Plugin Dependency Checker",
        },
        "connector_bridge": {
            "path": "tools/core/connector_bridge.py",
            "module": "tools.core.connector_bridge",
            "functions": ["get_auth", "get_data"],
            "description": "Auth Abstraction (connector/env/error)",
        },
    },
    "pipeline": {
        "pipeline_executor": {
            "path": "tools/pipeline/pipeline_executor.py",
            "module": "tools.pipeline.pipeline_executor",
            "classes": ["PipelineExecutor"],
            "description": "YAML Pipeline Runner",
        },
        "pipeline_schema": {
            "path": "tools/pipeline/pipeline_schema.py",
            "module": "tools.pipeline.pipeline_schema",
            "classes": ["PipelineStep", "PipelineDefinition", "StepResult", "PipelineResult"],
            "description": "Pipeline Schema Definitions",
        },
        "action_registry": {
            "path": "tools/pipeline/action_registry.py",
            "module": "tools.pipeline.action_registry",
            "classes": ["ActionRegistry"],
            "description": "Pipeline Action Registry",
        },
        "builtin_actions": {
            "path": "tools/pipeline/builtin_actions.py",
            "module": "tools.pipeline.builtin_actions",
            "functions": ["register_all"],
            "description": "Built-in Pipeline Actions",
        },
    },
    "session": {
        "session_manager": {
            "path": "tools/session/session_manager.py",
            "module": "tools.session.session_manager",
            "classes": ["SessionManager"],
            "description": "Session Persistence",
        },
        "confucius_agent": {
            "path": "tools/session/confucius_agent.py",
            "module": "tools.session.confucius_agent",
            "functions": ["main"],
            "description": "Confucius Note-Taking Agent",
        },
    },
    "util": {
        "model_bridge": {
            "path": "tools/util/model_bridge.py",
            "module": "tools.util.model_bridge",
            "functions": ["detect_active_model", "invoke_model", "invoke_challenger"],
            "description": "LLM Model Bridge",
        },
        "file_chunker": {
            "path": "tools/util/file_chunker.py",
            "module": "tools.util.file_chunker",
            "classes": ["FileInfo", "Chunk", "ChunkingResult"],
            "functions": ["analyze_file", "split_file"],
            "description": "File Chunking Utility",
        },
    },
}


class CheckRegistry:
    """
    Plugin-extensible preflight check registry.

    Each installed plugin can contribute checks via a `preflight-checks.yaml`
    file in its root directory. The registry merges all checks from all
    installed plugins.
    """

    def __init__(self):
        self._checks: Dict[str, Dict[str, Any]] = {}
        # Start with base checks
        for category, tools in BASE_CHECKS.items():
            self._checks[category] = dict(tools)

    def discover_plugins(self, plugins_dir: Optional[Path] = None) -> int:
        """
        Discover and load preflight checks from installed plugins.

        Returns number of additional checks loaded.
        """
        if not YAML_AVAILABLE:
            logger.warning("PyYAML not available, skipping plugin check discovery")
            return 0

        if plugins_dir is None:
            plugins_dir = self._find_plugins_dir()

        if not plugins_dir or not plugins_dir.exists():
            return 0

        added = 0
        for plugin_dir in sorted(plugins_dir.iterdir()):
            if not plugin_dir.is_dir() or not plugin_dir.name.startswith("pm-os-"):
                continue

            # Skip base — already loaded
            if plugin_dir.name == "pm-os-base":
                continue

            checks_file = plugin_dir / "preflight-checks.yaml"
            if not checks_file.exists():
                continue

            try:
                with open(checks_file, "r", encoding="utf-8") as f:
                    plugin_checks = yaml.safe_load(f)

                if not plugin_checks or not isinstance(plugin_checks, dict):
                    continue

                plugin_name = plugin_dir.name
                for category, tools in plugin_checks.items():
                    if category not in self._checks:
                        self._checks[category] = {}
                    for tool_name, tool_meta in tools.items():
                        tool_meta["_source_plugin"] = plugin_name
                        self._checks[category][tool_name] = tool_meta
                        added += 1

                logger.info("Loaded %d checks from %s", len(plugin_checks), plugin_name)

            except Exception as e:
                logger.warning("Failed to load checks from %s: %s", plugin_dir.name, e)

        return added

    def _find_plugins_dir(self) -> Optional[Path]:
        """Find the plugins directory by walking up from this file."""
        # Try PM_OS_ROOT env var first
        root = os.environ.get("PM_OS_ROOT", "")
        if root:
            # Check v5 development location
            v5_plugins = Path(root) / "v5" / "plugins"
            if v5_plugins.exists():
                return v5_plugins
            # Check production location
            prod_plugins = Path(root) / "plugins"
            if prod_plugins.exists():
                return prod_plugins

        # Walk up from this file
        current = Path(__file__).resolve().parent
        for _ in range(10):
            # Check if we're in a plugins/ directory
            if current.name == "plugins":
                return current
            candidate = current / "plugins"
            if candidate.exists():
                return candidate
            current = current.parent

        return None

    def get_checks(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered checks."""
        return self._checks

    def get_categories(self) -> List[str]:
        """Get list of check categories."""
        return sorted(self._checks.keys())

    def get_tools_by_category(self, category: str) -> Dict[str, Any]:
        """Get all tools in a category."""
        return self._checks.get(category, {})

    def get_tool_count(self) -> int:
        """Get total count of registered checks."""
        return sum(len(tools) for tools in self._checks.values())

    def register_check(self, category: str, name: str, meta: Dict[str, Any]) -> None:
        """Register a single check programmatically."""
        if category not in self._checks:
            self._checks[category] = {}
        self._checks[category][name] = meta


# Module-level convenience for backward compatibility with runner
_default_registry: Optional[CheckRegistry] = None


def get_registry() -> CheckRegistry:
    """Get or create the default registry instance."""
    global _default_registry
    if _default_registry is None:
        _default_registry = CheckRegistry()
        _default_registry.discover_plugins()
    return _default_registry


def get_categories() -> List[str]:
    """Get list of check categories."""
    return get_registry().get_categories()


def get_tools_by_category(category: str) -> Dict[str, Any]:
    """Get all tools in a category."""
    return get_registry().get_tools_by_category(category)


def get_tool_count() -> int:
    """Get total count of registered checks."""
    return get_registry().get_tool_count()
