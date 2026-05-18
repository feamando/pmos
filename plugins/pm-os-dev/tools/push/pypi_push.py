"""
PM-OS Dev PyPI Push (v5.0)

Build and publish PM-OS package to PyPI.

Usage:
    from pm_os_dev.tools.push.pypi_push import publish_to_pypi

CLI:
    python3 pypi_push.py --bump patch --dry-run
    python3 pypi_push.py --status
"""

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        from core.path_resolver import get_paths
    except ImportError:
        get_paths = None

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from core.config_loader import get_config
    except ImportError:
        get_config = None

try:
    from pm_os_base.tools.core.connector_bridge import get_auth
except ImportError:
    try:
        from core.connector_bridge import get_auth
    except ImportError:
        get_auth = None

try:
    from pm_os_dev.tools.release.version_manager import VersionManager
except ImportError:
    try:
        from release.version_manager import VersionManager
    except ImportError:
        VersionManager = None

try:
    import yaml
except ImportError:
    yaml = None


@dataclass
class PyPIResult:
    """Result of PyPI publish operation."""

    success: bool
    package_name: str
    version: str
    previous_version: Optional[str] = None
    pypi_url: Optional[str] = None
    error: Optional[str] = None
    dry_run: bool = False


def _find_pmos_root() -> Path:
    if get_paths is not None:
        try:
            return get_paths().root
        except Exception:
            pass
    for path in [Path.cwd()] + list(Path.cwd().parents):
        if (path / ".pm-os-root").exists():
            return path
    return Path.home() / "pm-os"


def _load_push_config(pmos_root: Path) -> dict:
    config_path = pmos_root / "user" / ".config" / "push_config.yaml"
    if not config_path.exists() or yaml is None:
        return {"pypi": {"enabled": False}}
    try:
        return yaml.safe_load(config_path.read_text()) or {}
    except Exception:
        return {"pypi": {"enabled": False}}


def _get_pypi_token(pmos_root: Path) -> Optional[str]:
    """Get PyPI token via connector_bridge, env var, or .env file."""
    # Try connector_bridge
    if get_auth is not None:
        try:
            auth = get_auth("pypi")
            if auth and auth.get("token"):
                return auth["token"]
        except Exception:
            pass

    # Try environment
    token = os.environ.get("PYPI_TOKEN")
    if token:
        return token

    # Try .env file
    env_file = pmos_root / "user" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("PYPI_TOKEN="):
                return line.split("=", 1)[1].strip()

    return None


def publish_to_pypi(
    pmos_root: Optional[Path] = None,
    bump_type: Optional[str] = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> PyPIResult:
    """Main publish function."""
    pmos_root = pmos_root or _find_pmos_root()
    config = _load_push_config(pmos_root)
    pypi_config = config.get("pypi", {})

    if not pypi_config.get("enabled", False):
        return PyPIResult(
            success=False, package_name="", version="",
            error="PyPI publishing is disabled in config",
        )

    package_path = pmos_root / pypi_config.get("package_path", "v5/plugins/pm-os-base/package")
    version_file = pmos_root / pypi_config.get("version_file", "v5/plugins/pm-os-base/package/VERSION")

    # Get package name from config — never hardcoded
    cfg = get_config() if get_config else {}
    package_name = cfg.get("distribution.pypi_package", "") or pypi_config.get("package_name", "")
    if not package_name:
        return PyPIResult(
            success=False, package_name="", version="",
            error="No package name configured (distribution.pypi_package)",
        )

    if not version_file.exists():
        return PyPIResult(
            success=False, package_name=package_name, version="",
            error=f"VERSION file not found: {version_file}",
        )

    current_version = version_file.read_text().strip()
    previous_version = None

    # Bump version if requested
    if bump_type and VersionManager is not None:
        vm = VersionManager(pmos_root)
        previous_version = current_version
        current_version = vm.bump_version(current_version, bump_type)
        if not dry_run:
            vm.write_version(current_version, version_file)
        if verbose:
            print(f"Version bumped: {previous_version} -> {current_version}")

    # Build
    if verbose:
        print(f"Building {package_name} v{current_version}...")

    dist_path = package_path / "dist"
    if dist_path.exists():
        shutil.rmtree(dist_path)

    build_result = subprocess.run(
        [sys.executable, "-m", "build"],
        cwd=package_path, capture_output=not verbose, text=True,
    )
    if build_result.returncode != 0:
        return PyPIResult(
            success=False, package_name=package_name, version=current_version,
            previous_version=previous_version, error="Build failed",
        )

    if dry_run:
        return PyPIResult(
            success=True, package_name=package_name, version=current_version,
            previous_version=previous_version, dry_run=True,
        )

    # Get token
    token = _get_pypi_token(pmos_root)
    if not token:
        return PyPIResult(
            success=False, package_name=package_name, version=current_version,
            previous_version=previous_version,
            error="PYPI_TOKEN not found (connector_bridge, env, or .env)",
        )

    # Upload
    if verbose:
        print("Uploading to PyPI...")

    env = os.environ.copy()
    env["TWINE_USERNAME"] = "__token__"
    env["TWINE_PASSWORD"] = token

    upload_result = subprocess.run(
        f"{sys.executable} -m twine upload dist/*",
        shell=True, cwd=package_path, capture_output=not verbose, text=True, env=env,
    )

    if upload_result.returncode == 0:
        pypi_url = f"https://pypi.org/project/{package_name}/{current_version}/"
        return PyPIResult(
            success=True, package_name=package_name, version=current_version,
            previous_version=previous_version, pypi_url=pypi_url,
        )
    else:
        return PyPIResult(
            success=False, package_name=package_name, version=current_version,
            previous_version=previous_version, error="Upload failed",
        )


def show_status(pmos_root: Path) -> None:
    config = _load_push_config(pmos_root)
    pypi_config = config.get("pypi", {})
    version_file = pmos_root / pypi_config.get("version_file", "v5/plugins/pm-os-base/package/VERSION")

    cfg = get_config() if get_config else {}
    package_name = cfg.get("distribution.pypi_package", "") or pypi_config.get("package_name", "")
    current_version = version_file.read_text().strip() if version_file.exists() else "unknown"

    print(f"Package: {package_name}")
    print(f"Version: {current_version}")
    print(f"Enabled: {pypi_config.get('enabled', False)}")
    if package_name:
        print(f"PyPI URL: https://pypi.org/project/{package_name}/")
        print(f"Install: pip install {package_name}")


def main():
    parser = argparse.ArgumentParser(description="PM-OS PyPI Publisher")
    parser.add_argument("--bump", choices=["patch", "minor", "major"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()
    pmos_root = _find_pmos_root()

    if args.status:
        show_status(pmos_root)
        return

    result = publish_to_pypi(pmos_root, bump_type=args.bump, dry_run=args.dry_run, verbose=args.verbose)

    if result.success:
        if result.dry_run:
            print(f"Build successful (dry run): {result.package_name} v{result.version}")
        else:
            print(f"Published: {result.package_name} v{result.version}")
            if result.pypi_url:
                print(f"  URL: {result.pypi_url}")
    else:
        print(f"Failed: {result.error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
