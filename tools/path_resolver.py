#!/usr/bin/env python3
"""
PM-OS Path Resolver

Resolves paths to common/ and user/ directories using multiple strategies.
This is the bootstrap module that enables other tools to find their configuration.

Resolution Order:
1. Environment variables (PM_OS_ROOT, PM_OS_COMMON, PM_OS_USER)
2. Marker file walk-up (.pm-os-root)
3. Global config (~/.pm-os/config.yaml)
4. Directory structure inference

Usage:
    from path_resolver import get_paths, get_common, get_user

    paths = get_paths()
    print(paths.common)  # Path to LOGIC
    print(paths.user)    # Path to CONTENT

Author: PM-OS Team
Version: 3.0.0
"""

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional YAML import for global config
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class PathResolutionError(Exception):
    """Raised when paths cannot be resolved."""

    pass


@dataclass
class ResolvedPaths:
    """Container for resolved PM-OS paths."""

    root: Path
    common: Path
    user: Path
    strategy: str  # Which strategy succeeded

    def __repr__(self) -> str:
        return (
            f"ResolvedPaths(\n"
            f"  root={self.root}\n"
            f"  common={self.common}\n"
            f"  user={self.user}\n"
            f"  strategy='{self.strategy}'\n"
            f")"
        )


class PathResolver:
    """
    PM-OS Path Resolver.

    Resolves paths to the pm-os directory structure using multiple fallback
    strategies. Once resolved, provides convenient access to common paths.

    Marker Files:
        .pm-os-root   - In pm-os/ parent folder
        .pm-os-common - In common/ (LOGIC) folder
        .pm-os-user   - In user/ (CONTENT) folder

    Environment Variables:
        PM_OS_ROOT   - Path to pm-os/ parent folder
        PM_OS_COMMON - Direct path to common/ folder
        PM_OS_USER   - Direct path to user/ folder
    """

    # Marker file names
    ROOT_MARKER = ".pm-os-root"
    COMMON_MARKER = ".pm-os-common"
    USER_MARKER = ".pm-os-user"

    # Environment variable names
    ENV_ROOT = "PM_OS_ROOT"
    ENV_COMMON = "PM_OS_COMMON"
    ENV_USER = "PM_OS_USER"

    # Global config location
    GLOBAL_CONFIG_DIR = Path.home() / ".pm-os"
    GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.yaml"

    # V2.4 compatibility markers
    V24_MARKERS = ["AI_Guidance", ".claude", "AGENT.md"]

    def __init__(self, start_path: Optional[Path] = None):
        """
        Initialize the path resolver.

        Args:
            start_path: Starting directory for resolution. Defaults to cwd.
        """
        self.start_path = Path(start_path) if start_path else Path.cwd()
        self._resolved: Optional[ResolvedPaths] = None
        self._resolve()

    def _resolve(self) -> None:
        """
        Resolve paths using multiple strategies in order.

        Resolution order:
        1. Environment variables (highest priority)
        2. Marker file walk-up
        3. Global config file
        4. Directory structure inference (lowest priority)
        """
        strategies = [
            ("env_variables", self._try_env_variables),
            ("env_direct", self._try_env_direct),
            ("marker_walkup", self._try_marker_walkup),
            ("global_config", self._try_global_config),
            ("structure_inference", self._try_structure_inference),
            ("v24_compatibility", self._try_v24_compatibility),
        ]

        for name, strategy in strategies:
            try:
                result = strategy()
                if result and self._validate_paths(result):
                    self._resolved = ResolvedPaths(
                        root=result["root"],
                        common=result["common"],
                        user=result["user"],
                        strategy=name,
                    )
                    logger.debug(f"Resolved paths using strategy: {name}")
                    return
            except Exception as e:
                logger.debug(f"Strategy {name} failed: {e}")
                continue

        # All strategies failed
        raise PathResolutionError(
            "Could not resolve PM-OS paths. Options:\n"
            "  1. Set PM_OS_ROOT environment variable\n"
            "  2. Run from within pm-os/ directory\n"
            "  3. Create ~/.pm-os/config.yaml with root_path\n"
            "  4. Ensure .pm-os-root marker file exists in pm-os/"
        )

    def _try_env_variables(self) -> Optional[Dict[str, Path]]:
        """Strategy 1: Use PM_OS_ROOT environment variable."""
        root_path = os.getenv(self.ENV_ROOT)
        if not root_path:
            return None

        root = Path(root_path)
        return {"root": root, "common": root / "common", "user": root / "user"}

    def _try_env_direct(self) -> Optional[Dict[str, Path]]:
        """Strategy 1b: Use direct PM_OS_COMMON and PM_OS_USER variables."""
        common_path = os.getenv(self.ENV_COMMON)
        user_path = os.getenv(self.ENV_USER)

        if not common_path or not user_path:
            return None

        common = Path(common_path)
        user = Path(user_path)

        return {"root": common.parent, "common": common, "user": user}

    def _try_marker_walkup(self) -> Optional[Dict[str, Path]]:
        """Strategy 2: Walk up directory tree looking for marker."""
        current = self.start_path.resolve()

        while current != current.parent:
            marker = current / self.ROOT_MARKER
            if marker.exists():
                return {
                    "root": current,
                    "common": current / "common",
                    "user": current / "user",
                }
            current = current.parent

        return None

    def _try_global_config(self) -> Optional[Dict[str, Path]]:
        """Strategy 3: Read global config file."""
        if not YAML_AVAILABLE:
            return None

        if not self.GLOBAL_CONFIG_FILE.exists():
            return None

        try:
            with open(self.GLOBAL_CONFIG_FILE, "r") as f:
                config = yaml.safe_load(f)

            if not config or "root_path" not in config:
                return None

            root = Path(config["root_path"])
            return {"root": root, "common": root / "common", "user": root / "user"}
        except Exception as e:
            logger.debug(f"Failed to read global config: {e}")
            return None

    def _try_structure_inference(self) -> Optional[Dict[str, Path]]:
        """Strategy 4: Infer from current directory structure."""
        cwd = self.start_path.resolve()

        # Check if we're in common/
        if cwd.name == "common" and (cwd / self.COMMON_MARKER).exists():
            root = cwd.parent
            return {"root": root, "common": cwd, "user": root / "user"}

        # Check if we're in user/
        if cwd.name == "user" and (cwd / self.USER_MARKER).exists():
            root = cwd.parent
            return {"root": root, "common": root / "common", "user": cwd}

        # Check if we're inside common/ or user/
        for parent in cwd.parents:
            if parent.name == "common":
                root = parent.parent
                if (root / "user").exists():
                    return {"root": root, "common": parent, "user": root / "user"}
            if parent.name == "user":
                root = parent.parent
                if (root / "common").exists():
                    return {"root": root, "common": root / "common", "user": parent}

        # Check if cwd IS the root
        if (cwd / "common").exists() and (cwd / "user").exists():
            return {"root": cwd, "common": cwd / "common", "user": cwd / "user"}

        return None

    def _try_v24_compatibility(self) -> Optional[Dict[str, Path]]:
        """Strategy 5: V2.4 compatibility - existing structure without migration."""
        cwd = self.start_path.resolve()

        # Check for v2.4 markers in current directory
        has_v24_markers = all((cwd / marker).exists() for marker in self.V24_MARKERS)

        if has_v24_markers:
            # V2.4 structure: treat current dir as both common and user
            logger.info("Detected v2.4 structure. Running in compatibility mode.")
            return {
                "root": cwd,
                "common": cwd,  # Tools are in same dir
                "user": cwd,  # Content is in same dir
            }

        # Walk up looking for v2.4 structure
        current = cwd
        while current != current.parent:
            has_markers = all(
                (current / marker).exists() for marker in self.V24_MARKERS
            )
            if has_markers:
                logger.info(f"Detected v2.4 structure at {current}")
                return {"root": current, "common": current, "user": current}
            current = current.parent

        return None

    def _validate_paths(self, paths: Dict[str, Path]) -> bool:
        """
        Validate that resolved paths exist.

        Args:
            paths: Dictionary with root, common, user paths

        Returns:
            True if all paths are valid.
        """
        root = paths.get("root")
        common = paths.get("common")
        user = paths.get("user")

        if not all([root, common, user]):
            return False

        # Root must exist
        if not root.exists():
            return False

        # For v3.0, both common and user must exist
        # For v2.4 compatibility, they can be the same
        if common == user:
            return common.exists()

        return common.exists() and user.exists()

    @property
    def root(self) -> Path:
        """Get pm-os/ root path."""
        if not self._resolved:
            raise PathResolutionError("Paths not resolved")
        return self._resolved.root

    @property
    def common(self) -> Path:
        """Get common/ (LOGIC) path."""
        if not self._resolved:
            raise PathResolutionError("Paths not resolved")
        return self._resolved.common

    @property
    def user(self) -> Path:
        """Get user/ (CONTENT) path."""
        if not self._resolved:
            raise PathResolutionError("Paths not resolved")
        return self._resolved.user

    @property
    def is_v24_mode(self) -> bool:
        """Check if running in v2.4 compatibility mode."""
        return self._resolved and self._resolved.common == self._resolved.user

    @property
    def strategy(self) -> str:
        """Get the resolution strategy that succeeded."""
        if not self._resolved:
            return "none"
        return self._resolved.strategy

    # Convenience paths
    @property
    def config_path(self) -> Path:
        """Get path to config.yaml."""
        return self.user / "config.yaml"

    @property
    def env_path(self) -> Path:
        """Get path to .env."""
        return self.user / ".env"

    @property
    def brain(self) -> Path:
        """Get Brain directory path."""
        # V3.0 structure
        v3_path = self.user / "brain"
        if v3_path.exists():
            return v3_path

        # V2.4 fallback
        v2_path = self.user / "user" / "brain"
        if v2_path.exists():
            return v2_path

        # Default to v3.0 (may not exist yet)
        return v3_path

    @property
    def context(self) -> Path:
        """Get context directory path."""
        # V3.0 structure
        v3_path = self.user / "context"
        if v3_path.exists():
            return v3_path

        # V2.4 fallback
        v2_path = self.user / "AI_Guidance" / "Core_Context"
        if v2_path.exists():
            return v2_path

        return v3_path

    @property
    def sessions(self) -> Path:
        """Get sessions directory path."""
        # V3.0 structure
        v3_path = self.user / "sessions"
        if v3_path.exists():
            return v3_path

        # V2.4 fallback
        v2_path = self.user / "AI_Guidance" / "Sessions"
        if v2_path.exists():
            return v2_path

        return v3_path

    @property
    def tools(self) -> Path:
        """Get tools directory path."""
        # V3.0 structure
        v3_path = self.common / "tools"
        if v3_path.exists():
            return v3_path

        # V2.4 fallback
        v2_path = self.common / "AI_Guidance" / "Tools"
        if v2_path.exists():
            return v2_path

        return v3_path

    @property
    def frameworks(self) -> Path:
        """Get frameworks/templates directory path."""
        # V3.0 structure
        v3_path = self.common / "frameworks"
        if v3_path.exists():
            return v3_path

        # V2.4 fallback
        v2_path = self.common / "AI_Guidance" / "Frameworks"
        if v2_path.exists():
            return v2_path

        return v3_path

    @property
    def schemas(self) -> Path:
        """Get schemas directory path (v3.0 only)."""
        return self.common / "schemas"

    @property
    def commands_claude(self) -> Path:
        """Get Claude commands directory."""
        return self.common / ".claude" / "commands"

    @property
    def commands_gemini(self) -> Path:
        """Get Gemini commands directory."""
        return self.common / ".gemini" / "commands"

    def get_tool_path(self, tool_name: str) -> Path:
        """
        Get full path to a specific tool.

        Args:
            tool_name: Tool filename (e.g., "brain_loader.py")

        Returns:
            Full path to the tool.
        """
        return self.tools / tool_name

    def save_global_config(self) -> None:
        """Save current root path to global config for future sessions."""
        if not YAML_AVAILABLE:
            logger.warning("PyYAML not available, cannot save global config")
            return

        self.GLOBAL_CONFIG_DIR.mkdir(exist_ok=True)

        config = {"root_path": str(self.root)}

        with open(self.GLOBAL_CONFIG_FILE, "w") as f:
            yaml.dump(config, f)

        logger.info(f"Saved global config to {self.GLOBAL_CONFIG_FILE}")

    def create_markers(self) -> None:
        """Create marker files in the current structure."""
        markers = [
            (self.root / self.ROOT_MARKER, "PM-OS root directory"),
            (self.common / self.COMMON_MARKER, "PM-OS LOGIC (common) directory"),
            (self.user / self.USER_MARKER, "PM-OS CONTENT (user) directory"),
        ]

        for marker_path, description in markers:
            if not marker_path.exists():
                marker_path.touch()
                logger.info(f"Created marker: {marker_path}")


# Singleton instance
_resolver: Optional[PathResolver] = None


def get_paths(
    start_path: Optional[Path] = None, force_reload: bool = False
) -> PathResolver:
    """
    Get the path resolver singleton.

    Args:
        start_path: Starting directory for resolution
        force_reload: Force re-resolution of paths

    Returns:
        PathResolver instance.
    """
    global _resolver

    if _resolver is None or force_reload:
        _resolver = PathResolver(start_path)

    return _resolver


def reset_paths() -> None:
    """Reset the path resolver singleton (for testing)."""
    global _resolver
    _resolver = None


# Convenience functions
def get_root() -> Path:
    """Get pm-os root path."""
    return get_paths().root


def get_common() -> Path:
    """Get common (LOGIC) path."""
    return get_paths().common


def get_user() -> Path:
    """Get user (CONTENT) path."""
    return get_paths().user


def get_brain() -> Path:
    """Get Brain directory path."""
    return get_paths().brain


def get_tools() -> Path:
    """Get tools directory path."""
    return get_paths().tools


def is_v24_mode() -> bool:
    """Check if running in v2.4 compatibility mode."""
    return get_paths().is_v24_mode


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PM-OS Path Resolver")
    parser.add_argument("--root", action="store_true", help="Print root path")
    parser.add_argument("--common", action="store_true", help="Print common path")
    parser.add_argument("--user", action="store_true", help="Print user path")
    parser.add_argument("--brain", action="store_true", help="Print brain path")
    parser.add_argument("--tools", action="store_true", help="Print tools path")
    parser.add_argument("--info", action="store_true", help="Print full path info")
    parser.add_argument(
        "--create-markers", action="store_true", help="Create marker files"
    )
    parser.add_argument(
        "--save-global", action="store_true", help="Save to global config"
    )
    parser.add_argument("--start", metavar="PATH", help="Start path for resolution")

    args = parser.parse_args()

    try:
        start_path = Path(args.start) if args.start else None
        paths = get_paths(start_path)

        if args.root:
            print(paths.root)
        elif args.common:
            print(paths.common)
        elif args.user:
            print(paths.user)
        elif args.brain:
            print(paths.brain)
        elif args.tools:
            print(paths.tools)
        elif args.create_markers:
            paths.create_markers()
            print("Markers created")
        elif args.save_global:
            paths.save_global_config()
            print(f"Saved to {paths.GLOBAL_CONFIG_FILE}")
        elif args.info:
            print(f"Root:     {paths.root}")
            print(f"Common:   {paths.common}")
            print(f"User:     {paths.user}")
            print(f"Brain:    {paths.brain}")
            print(f"Tools:    {paths.tools}")
            print(f"Strategy: {paths.strategy}")
            print(f"V2.4 Mode: {paths.is_v24_mode}")
        else:
            print(paths)

    except PathResolutionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
