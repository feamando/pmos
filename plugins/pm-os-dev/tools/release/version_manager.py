"""
PM-OS Dev VersionManager (v5.0)

Semantic versioning, version bumping, and changelog generation.

Usage:
    from pm_os_dev.tools.release.version_manager import VersionManager
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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


class VersionManager:
    """Manages semantic versioning across PM-OS components."""

    def __init__(self, pmos_root: Optional[Path] = None):
        if pmos_root:
            self.pmos_root = pmos_root
        elif get_paths is not None:
            try:
                self.pmos_root = get_paths().root
            except Exception:
                self.pmos_root = Path.home() / "pm-os"
        else:
            self.pmos_root = Path.home() / "pm-os"

        self.config = get_config() if get_config else {}

    def get_version(self, version_file: Optional[Path] = None) -> str:
        """Get current version from VERSION file."""
        if version_file is None:
            version_file = self.pmos_root / "common" / "package" / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
        return "0.0.0"

    def bump_version(self, current: str, bump_type: str) -> str:
        """Bump a semantic version string.

        Args:
            current: Current version (e.g., "5.0.0")
            bump_type: One of "major", "minor", "patch"

        Returns:
            New version string
        """
        parts = current.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid version format: {current}")

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

    def validate_version(self, version: str) -> bool:
        """Validate semantic version format."""
        return bool(re.match(r"^\d+\.\d+\.\d+$", version))

    def write_version(self, version: str, version_file: Optional[Path] = None) -> None:
        """Write version to VERSION file."""
        if version_file is None:
            version_file = self.pmos_root / "common" / "package" / "VERSION"
        version_file.parent.mkdir(parents=True, exist_ok=True)
        version_file.write_text(version + "\n")

    def update_plugin_manifests(self, version: str) -> List[str]:
        """Update version in all plugin.json manifests.

        Returns:
            List of updated manifest paths
        """
        updated = []
        plugins_dir = self.pmos_root / "v5" / "plugins"

        if not plugins_dir.exists():
            return updated

        for manifest_path in plugins_dir.glob("pm-os-*/.claude-plugin/plugin.json"):
            try:
                manifest = json.loads(manifest_path.read_text())
                old_version = manifest.get("version", "")
                if old_version != version:
                    manifest["version"] = version
                    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
                    updated.append(str(manifest_path))
            except (json.JSONDecodeError, OSError):
                continue

        return updated

    def generate_changelog_entry(
        self,
        version: str,
        target: str,
        changes: List[Dict[str, Any]],
    ) -> str:
        """Generate a changelog entry for a release.

        Args:
            version: Release version
            target: Target name (e.g., "common")
            changes: List of change dicts with 'path' and 'change_type' keys

        Returns:
            Markdown changelog entry
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        added = sum(1 for c in changes if c.get("change_type") == "added")
        modified = sum(1 for c in changes if c.get("change_type") == "modified")
        deleted = sum(1 for c in changes if c.get("change_type") == "deleted")

        entry = (
            f"## [{timestamp}] v{version} — {target}\n\n"
            f"**Files:** {len(changes)} "
            f"({added} added, {modified} modified, {deleted} deleted)\n\n"
        )

        # Categorize changes
        categories: Dict[str, List[str]] = {}
        for change in changes:
            path = change.get("path", "")
            ctype = change.get("change_type", "modified")
            symbol = {"added": "+", "modified": "~", "deleted": "-"}.get(ctype, "?")

            if "test" in path.lower():
                cat = "Tests"
            elif path.endswith(".md"):
                cat = "Documentation"
            elif "/tools/" in path:
                cat = "Tools"
            elif "/commands/" in path:
                cat = "Commands"
            else:
                cat = "Other"

            categories.setdefault(cat, []).append(f"- {symbol} `{path}`")

        for cat, items in sorted(categories.items()):
            entry += f"**{cat}** ({len(items)})\n"
            for item in items[:5]:
                entry += f"{item}\n"
            if len(items) > 5:
                entry += f"- ... and {len(items) - 5} more\n"
            entry += "\n"

        return entry

    def accumulate_changelog(
        self,
        entry: str,
        changelog_path: Optional[Path] = None,
        max_entries: int = 50,
    ) -> None:
        """Prepend an entry to the CHANGELOG.md file."""
        if changelog_path is None:
            cl_path = self.config.get("changelog.path", "CHANGELOG.md") if self.config else "CHANGELOG.md"
            changelog_path = self.pmos_root / cl_path

        title = "# PM-OS Changelog\n\n"
        existing = ""

        if changelog_path.exists():
            existing = changelog_path.read_text()

        if existing.startswith("# PM-OS Changelog"):
            idx = existing.index("\n\n") + 2
            body = existing[idx:]
        else:
            body = existing

        new_body = entry + "---\n\n" + body

        # Trim to max entries
        sections = new_body.split("## [")
        if len(sections) > max_entries + 1:
            sections = sections[: max_entries + 1]
        new_body = "## [".join(sections)

        try:
            changelog_path.parent.mkdir(parents=True, exist_ok=True)
            changelog_path.write_text(title + new_body)
        except OSError:
            pass
