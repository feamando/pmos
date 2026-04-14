"""Unit tests for migrate_to_v5.py using temp directories."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

# Add migration dir to path
sys.path.insert(0, str(Path(__file__).parent))

from migrate_to_v5 import (
    analyze,
    migrate,
    migrate_config,
    install_plugins,
    validate,
    rollback,
    MigrationReport,
)


@pytest.fixture
def pm_os_root(tmp_path):
    """Create a minimal PM-OS directory structure for testing."""
    (tmp_path / "user" / "brain").mkdir(parents=True)
    (tmp_path / "user" / "config.yaml").write_text(
        yaml.dump({"version": "3.0.0", "user": {"name": "Test", "email": "test@test.com"}})
    )
    (tmp_path / "user" / ".env").write_text("JIRA_API_TOKEN=test\n")
    (tmp_path / "v5" / "plugins").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def pm_os_with_plugins(pm_os_root):
    """Add plugin manifests to the PM-OS root."""
    for name, cmds, skills in [
        ("pm-os-base", ["commands/base.md"], ["skills/persona.md"]),
        ("pm-os-brain", ["commands/brain.md"], ["skills/entity-resolution.md"]),
        ("pm-os-daily-workflow", ["commands/session.md"], []),
        ("pm-os-cce", ["commands/feature.md"], []),
        ("pm-os-reporting", ["commands/report.md"], []),
        ("pm-os-career", ["commands/team.md"], []),
        ("pm-os-dev", ["commands/ralph.md"], []),
    ]:
        plugin_dir = pm_os_root / "v5" / "plugins" / name
        (plugin_dir / ".claude-plugin").mkdir(parents=True)
        for cmd in cmds:
            cmd_path = plugin_dir / cmd
            cmd_path.parent.mkdir(parents=True, exist_ok=True)
            cmd_path.write_text(f"# /{cmd.split('/')[-1].replace('.md','')} command\n")
        for skill in skills:
            skill_path = plugin_dir / skill
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.write_text(f"---\ndescription: test skill\n---\n")
        deps = [] if name == "pm-os-base" else ["pm-os-base"]
        manifest = {
            "name": name,
            "version": "5.0.0",
            "description": f"Test {name}",
            "author": "Test",
            "dependencies": deps,
            "commands": cmds,
            "skills": skills,
            "mcp_servers": [],
        }
        (plugin_dir / ".claude-plugin" / "plugin.json").write_text(json.dumps(manifest))
    return pm_os_root


def test_analyze_empty_user(pm_os_root):
    """Fresh install with minimal user/ produces near-empty report."""
    report = analyze(pm_os_root)
    # Should find config.yaml and .env in keep_paths
    keep_paths = [item.path for item in report.keep_paths]
    assert "user/config.yaml" in keep_paths
    assert "user/.env" in keep_paths
    # No archive or delete items for a clean install
    assert len(report.delete_paths) == 0


def test_analyze_with_content(pm_os_root):
    """Populates keep/archive/delete correctly."""
    # Create brain entities (keep)
    (pm_os_root / "user" / "brain" / "test-entity.md").write_text("# Test")
    # Create old sessions (archive)
    (pm_os_root / "user" / "sessions" / "Archive").mkdir(parents=True)
    (pm_os_root / "user" / "sessions" / "Archive" / "old.md").write_text("old")
    # Create dead artifacts (delete)
    (pm_os_root / "user" / "archive" / "old-backups").mkdir(parents=True)
    (pm_os_root / "user" / "archive" / "old-backups" / "junk.txt").write_text("junk")

    report = analyze(pm_os_root)
    keep_paths = [item.path for item in report.keep_paths]
    archive_paths = [item.path for item in report.archive_paths]
    delete_paths = [item.path for item in report.delete_paths]

    assert "user/brain" in keep_paths
    assert "user/sessions/Archive" in archive_paths
    assert "user/archive/old-backups" in delete_paths


def test_analyze_detects_plugins(pm_os_root):
    """Maps v4 commands to v5 plugins."""
    commands_dir = pm_os_root / "common" / ".claude" / "commands"
    commands_dir.mkdir(parents=True)
    (commands_dir / "brain.md").write_text("# brain")
    (commands_dir / "session.md").write_text("# session")
    (commands_dir / "feature.md").write_text("# feature")
    (commands_dir / "report.md").write_text("# report")
    (commands_dir / "team.md").write_text("# team")
    (commands_dir / "ralph.md").write_text("# ralph")

    report = analyze(pm_os_root)
    assert "pm-os-base" in report.plugins_to_install
    assert "pm-os-brain" in report.plugins_to_install
    assert "pm-os-daily-workflow" in report.plugins_to_install
    assert "pm-os-cce" in report.plugins_to_install
    assert "pm-os-reporting" in report.plugins_to_install
    assert "pm-os-career" in report.plugins_to_install
    assert "pm-os-dev" in report.plugins_to_install


def test_migrate_config(pm_os_root):
    """Config migration bumps version, adds plugins and persona sections."""
    migrate_config(pm_os_root)

    with open(pm_os_root / "user" / "config.yaml") as f:
        config = yaml.safe_load(f)

    assert config["version"] == "5.0.0"
    assert "plugins" in config
    assert config["plugins"]["format"] == "anthropic"
    assert config["plugins"]["source"] == "v5/plugins"
    assert "persona" in config
    assert config["persona"]["style"] == "direct"


def test_install_plugins(pm_os_with_plugins):
    """Copies commands and skills to .claude/ directories."""
    root = pm_os_with_plugins
    install_plugins(root, ["pm-os-base", "pm-os-brain"])

    commands_dir = root / ".claude" / "commands"
    skills_dir = root / ".claude" / "skills"

    assert (commands_dir / "base.md").exists()
    assert (commands_dir / "brain.md").exists()
    assert (skills_dir / "persona.md").exists()
    assert (skills_dir / "entity-resolution.md").exists()


@patch("migrate_to_v5.subprocess.run")
def test_backup_creates_tag(mock_run):
    """Backup creates a git tag."""
    from migrate_to_v5 import backup
    mock_run.return_value = MagicMock(returncode=0)
    tag = backup(Path("/fake"))
    assert tag is not None
    assert tag.startswith("v4.x-backup-")
    mock_run.assert_called_once()
    args = mock_run.call_args
    assert args[0][0][0] == "git"
    assert args[0][0][1] == "tag"


def test_validate_passes(pm_os_with_plugins):
    """All checks pass with proper structure."""
    root = pm_os_with_plugins
    # Create brain entity
    (root / "user" / "brain" / "test.md").write_text("# Test")
    # Migrate config to 5.0.0
    migrate_config(root)
    # Install base plugin
    install_plugins(root, ["pm-os-base"])

    result = validate(root)
    for name, passed, detail in result.checks:
        if name in ("Brain entities", "Config exists", "Config version",
                     "Config plugins section", "v5/ workspace",
                     "v5 plugin directories", "Base plugin installed",
                     "No dead symlinks"):
            assert passed, f"{name} failed: {detail}"


def test_validate_fails_missing_config(pm_os_root):
    """Fails gracefully when config is missing."""
    os.unlink(pm_os_root / "user" / "config.yaml")
    result = validate(pm_os_root)
    config_check = next((c for c in result.checks if c[0] == "Config exists"), None)
    assert config_check is not None
    assert config_check[1] is False


@patch("migrate_to_v5.subprocess.run")
def test_rollback(mock_run):
    """Rollback finds latest tag and checks out."""
    # First call: git tag -l (list tags)
    tag_result = MagicMock()
    tag_result.stdout = "v4.x-backup-20260401-120000\nv4.x-backup-20260402-120000\n"
    # Second call: git checkout
    checkout_result = MagicMock()
    mock_run.side_effect = [tag_result, checkout_result]

    rollback(Path("/fake"))
    assert mock_run.call_count == 2
    checkout_args = mock_run.call_args_list[1][0][0]
    assert "v4.x-backup-20260402-120000" in checkout_args


def test_dry_run_makes_no_changes(pm_os_with_plugins):
    """Verify --dry-run doesn't modify anything."""
    root = pm_os_with_plugins
    # Create something that would be archived
    (root / "user" / "sessions" / "Archive").mkdir(parents=True)
    (root / "user" / "sessions" / "Archive" / "old.md").write_text("old")

    # Snapshot state before
    config_before = (root / "user" / "config.yaml").read_text()

    # Run analyze (dry-run only runs analyze + confirm with interactive=False)
    report = analyze(root)

    # Verify nothing changed
    config_after = (root / "user" / "config.yaml").read_text()
    assert config_before == config_after
    assert (root / "user" / "sessions" / "Archive" / "old.md").exists()
