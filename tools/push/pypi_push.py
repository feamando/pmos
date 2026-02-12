#!/usr/bin/env python3
"""
PM-OS PyPI Publisher

Builds and publishes the PM-OS package to PyPI.

Usage:
    python3 pypi_push.py                    # Build and publish
    python3 pypi_push.py --bump patch       # Bump version and publish
    python3 pypi_push.py --bump minor       # Bump minor version
    python3 pypi_push.py --bump major       # Bump major version
    python3 pypi_push.py --dry-run          # Build only, don't publish
    python3 pypi_push.py --status           # Show current version info
"""

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml


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


def find_pm_os_root() -> Path:
    """Find PM-OS root by looking for .pm-os-root marker."""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / ".pm-os-root").exists():
            return parent
    raise FileNotFoundError("Could not find PM-OS root (no .pm-os-root marker)")


def load_config(pm_os_root: Path) -> dict:
    """Load push configuration."""
    config_path = pm_os_root / "user" / ".config" / "push_config.yaml"
    if not config_path.exists():
        return {"pypi": {"enabled": False}}
    return yaml.safe_load(config_path.read_text())


def get_version(version_file: Path) -> str:
    """Get current version from VERSION file."""
    return version_file.read_text().strip()


def bump_version(version: str, bump_type: str) -> str:
    """Bump version number."""
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {version}")

    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")

    return f"{major}.{minor}.{patch}"


def build_package(package_path: Path, verbose: bool = False) -> bool:
    """Build the package using python -m build."""
    dist_path = package_path / "dist"

    # Clean old builds
    if dist_path.exists():
        shutil.rmtree(dist_path)

    # Build
    cmd = [sys.executable, "-m", "build"]
    result = subprocess.run(
        cmd, cwd=package_path, capture_output=not verbose, text=True
    )

    return result.returncode == 0


def upload_to_pypi(package_path: Path, token: str, verbose: bool = False) -> bool:
    """Upload to PyPI using twine."""
    dist_path = package_path / "dist"

    env = os.environ.copy()
    env["TWINE_USERNAME"] = "__token__"
    env["TWINE_PASSWORD"] = token

    cmd = [sys.executable, "-m", "twine", "upload", "dist/*"]
    result = subprocess.run(
        cmd,
        cwd=package_path,
        capture_output=not verbose,
        text=True,
        env=env,
        shell=False,
    )

    # twine upload needs glob expansion, use shell
    cmd_str = f"cd {package_path} && {sys.executable} -m twine upload dist/*"
    result = subprocess.run(
        cmd_str, shell=True, capture_output=not verbose, text=True, env=env
    )

    return result.returncode == 0


def post_slack_notification(
    webhook_or_token: str,
    channel: str,
    package_name: str,
    version: str,
    pypi_url: str,
    previous_version: Optional[str] = None,
) -> bool:
    """Post release notification to Slack."""
    try:
        # Try to use slack_sdk if available
        from slack_sdk import WebClient

        client = WebClient(token=webhook_or_token)

        version_text = (
            f"{previous_version} → {version}" if previous_version else version
        )

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📦 {package_name} Published to PyPI",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Version:*\n`{version_text}`"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Package:*\n<{pypi_url}|View on PyPI>",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Install: `pip install {package_name}=={version}`",
                },
            },
        ]

        client.chat_postMessage(
            channel=channel, blocks=blocks, text=f"{package_name} {version} published"
        )
        return True
    except Exception as e:
        print(f"Slack notification failed: {e}", file=sys.stderr)
        return False


def publish_to_pypi(
    pm_os_root: Path,
    bump_type: Optional[str] = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> PyPIResult:
    """Main publish function."""

    config = load_config(pm_os_root)
    pypi_config = config.get("pypi", {})

    if not pypi_config.get("enabled", False):
        return PyPIResult(
            success=False,
            package_name="pm-os",
            version="",
            error="PyPI publishing is disabled in config",
        )

    package_path = pm_os_root / pypi_config.get("package_path", "common/package")
    version_file = pm_os_root / pypi_config.get(
        "version_file", "common/package/VERSION"
    )
    package_name = pypi_config.get("package_name", "pm-os")

    # Get current version
    current_version = get_version(version_file)
    previous_version = None

    # Bump version if requested
    if bump_type:
        previous_version = current_version
        current_version = bump_version(current_version, bump_type)
        version_file.write_text(current_version + "\n")
        if verbose:
            print(f"Version bumped: {previous_version} → {current_version}")

    # Build
    if verbose:
        print(f"Building {package_name} v{current_version}...")

    if not build_package(package_path, verbose):
        return PyPIResult(
            success=False,
            package_name=package_name,
            version=current_version,
            previous_version=previous_version,
            error="Build failed",
        )

    if dry_run:
        return PyPIResult(
            success=True,
            package_name=package_name,
            version=current_version,
            previous_version=previous_version,
            dry_run=True,
        )

    # Get PyPI token
    token = os.environ.get("PYPI_TOKEN")
    if not token:
        # Try loading from .env
        env_file = pm_os_root / "user" / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("PYPI_TOKEN="):
                    token = line.split("=", 1)[1].strip()
                    break

    if not token:
        return PyPIResult(
            success=False,
            package_name=package_name,
            version=current_version,
            previous_version=previous_version,
            error="PYPI_TOKEN not found in environment or user/.env",
        )

    # Upload
    if verbose:
        print(f"Uploading to PyPI...")

    if not upload_to_pypi(package_path, token, verbose):
        return PyPIResult(
            success=False,
            package_name=package_name,
            version=current_version,
            previous_version=previous_version,
            error="Upload failed",
        )

    pypi_url = f"https://pypi.org/project/{package_name}/{current_version}/"

    # Slack notification
    if pypi_config.get("slack_enabled", False):
        slack_token = os.environ.get("SLACK_BOT_TOKEN")
        if not slack_token:
            env_file = pm_os_root / "user" / ".env"
            if env_file.exists():
                for line in env_file.read_text().splitlines():
                    if line.startswith("SLACK_BOT_" + "TOKEN="):
                        slack_token = line.split("=", 1)[1].strip()
                        break

        if slack_token:
            post_slack_notification(
                slack_token,
                pypi_config.get("slack_channel", ""),
                package_name,
                current_version,
                pypi_url,
                previous_version,
            )

    return PyPIResult(
        success=True,
        package_name=package_name,
        version=current_version,
        previous_version=previous_version,
        pypi_url=pypi_url,
    )


def show_status(pm_os_root: Path):
    """Show current PyPI package status."""
    config = load_config(pm_os_root)
    pypi_config = config.get("pypi", {})

    version_file = pm_os_root / pypi_config.get(
        "version_file", "common/package/VERSION"
    )
    package_name = pypi_config.get("package_name", "pm-os")

    current_version = get_version(version_file) if version_file.exists() else "unknown"

    print(f"Package: {package_name}")
    print(f"Version: {current_version}")
    print(f"Enabled: {pypi_config.get('enabled', False)}")
    print(f"PyPI URL: https://pypi.org/project/{package_name}/")
    print(f"Install: pip install {package_name}")


def main():
    parser = argparse.ArgumentParser(description="PM-OS PyPI Publisher")
    parser.add_argument(
        "--bump",
        choices=["patch", "minor", "major"],
        help="Bump version before publishing",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Build only, don't publish"
    )
    parser.add_argument(
        "--status", action="store_true", help="Show current version info"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    try:
        pm_os_root = find_pm_os_root()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.status:
        show_status(pm_os_root)
        return

    result = publish_to_pypi(
        pm_os_root, bump_type=args.bump, dry_run=args.dry_run, verbose=args.verbose
    )

    if result.success:
        if result.dry_run:
            print(
                f"✓ Build successful (dry run): {result.package_name} v{result.version}"
            )
        else:
            print(f"✓ Published: {result.package_name} v{result.version}")
            print(f"  URL: {result.pypi_url}")
            print(f"  Install: pip install {result.package_name}=={result.version}")
    else:
        print(f"✗ Failed: {result.error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
