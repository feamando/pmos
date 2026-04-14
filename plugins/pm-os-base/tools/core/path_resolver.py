#!/usr/bin/env python3
"""
PM-OS Path Resolver (v5.0)

Resolves paths to common/ and user/ directories using multiple strategies.
Bootstrap module that enables other tools to find their configuration.

Resolution Order:
1. Environment variables (PM_OS_ROOT, PM_OS_COMMON, PM_OS_USER)
2. Marker file walk-up (.pm-os-root)
3. Global config (~/.pm-os/config.yaml)
4. Directory structure inference

Usage:
    from pm_os_base.tools.core.path_resolver import get_paths

    paths = get_paths()
    print(paths.root)    # PM-OS root
    print(paths.common)  # Path to LOGIC
    print(paths.user)    # Path to CONTENT
"""

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class PathResolutionError(Exception):
    """Raised when paths cannot be resolved."""


@dataclass
class ResolvedPaths:
    """Container for resolved PM-OS paths."""
    root: Path
    common: Path
    user: Path
    strategy: str

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

    ROOT_MARKER = ".pm-os-root"
    COMMON_MARKER = ".pm-os-common"
    USER_MARKER = ".pm-os-user"

    ENV_ROOT = "PM_OS_ROOT"
    ENV_COMMON = "PM_OS_COMMON"
    ENV_USER = "PM_OS_USER"

    GLOBAL_CONFIG_DIR = Path.home() / ".pm-os"
    GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.yaml"

    def __init__(self, start_path: Optional[Path] = None):
        self.start_path = Path(start_path) if start_path else Path.cwd()
        self._resolved: Optional[ResolvedPaths] = None
        self._resolve()

    def _resolve(self) -> None:
        """Resolve paths using multiple strategies in order."""
        strategies = [
            ("env_variables", self._try_env_variables),
            ("env_direct", self._try_env_direct),
            ("marker_walkup", self._try_marker_walkup),
            ("global_config", self._try_global_config),
            ("structure_inference", self._try_structure_inference),
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
                    logger.debug("Resolved paths using strategy: %s", name)
                    return
            except Exception as e:
                logger.debug("Strategy %s failed: %s", name, e)
                continue

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
        if not YAML_AVAILABLE or not self.GLOBAL_CONFIG_FILE.exists():
            return None
        try:
            with open(self.GLOBAL_CONFIG_FILE, "r") as f:
                config = yaml.safe_load(f)
            if not config or "root_path" not in config:
                return None
            root = Path(config["root_path"])
            return {"root": root, "common": root / "common", "user": root / "user"}
        except Exception as e:
            logger.debug("Failed to read global config: %s", e)
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

    def _validate_paths(self, paths: Dict[str, Path]) -> bool:
        """Validate that resolved paths exist."""
        root = paths.get("root")
        common = paths.get("common")
        user = paths.get("user")
        if not all([root, common, user]):
            return False
        if not root.exists():
            return False
        return common.exists() and user.exists()

    @property
    def root(self) -> Path:
        if not self._resolved:
            raise PathResolutionError("Paths not resolved")
        return self._resolved.root

    @property
    def common(self) -> Path:
        if not self._resolved:
            raise PathResolutionError("Paths not resolved")
        return self._resolved.common

    @property
    def user(self) -> Path:
        if not self._resolved:
            raise PathResolutionError("Paths not resolved")
        return self._resolved.user

    @property
    def strategy(self) -> str:
        if not self._resolved:
            return "none"
        return self._resolved.strategy

    @property
    def config_path(self) -> Path:
        return self.user / "config.yaml"

    @property
    def env_path(self) -> Path:
        return self.user / ".env"

    @property
    def brain(self) -> Path:
        return self.user / "brain"

    @property
    def context(self) -> Path:
        return self.user / "personal" / "context"

    @property
    def sessions(self) -> Path:
        return self.user / "sessions"

    @property
    def tools(self) -> Path:
        return self.common / "tools"

    @property
    def frameworks(self) -> Path:
        return self.common / "frameworks"

    @property
    def schemas(self) -> Path:
        return self.common / "schemas"

    @property
    def plugins(self) -> Path:
        return self.common / "plugins"

    def get_tool_path(self, tool_name: str) -> Path:
        return self.tools / tool_name

    def save_global_config(self) -> None:
        """Save current root path to global config for future sessions."""
        if not YAML_AVAILABLE:
            logger.warning("PyYAML not available, cannot save global config")
            return
        self.GLOBAL_CONFIG_DIR.mkdir(exist_ok=True)
        with open(self.GLOBAL_CONFIG_FILE, "w") as f:
            yaml.dump({"root_path": str(self.root)}, f)
        logger.info("Saved global config to %s", self.GLOBAL_CONFIG_FILE)

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
                logger.info("Created marker: %s", marker_path)


# --- Singleton ---

_resolver: Optional[PathResolver] = None


def get_paths(
    start_path: Optional[Path] = None, force_reload: bool = False
) -> PathResolver:
    """Get the path resolver singleton."""
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
    return get_paths().root


def get_common() -> Path:
    return get_paths().common


def get_user() -> Path:
    return get_paths().user


def get_brain() -> Path:
    return get_paths().brain


def get_tools() -> Path:
    return get_paths().tools


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
    parser.add_argument("--create-markers", action="store_true", help="Create marker files")
    parser.add_argument("--save-global", action="store_true", help="Save to global config")
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
        else:
            print(paths)

    except PathResolutionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
