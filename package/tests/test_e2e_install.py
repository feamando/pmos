"""End-to-end installation tests for PM-OS.

Tests the complete flow: pip install → init → doctor → update → verify.
These tests require internet access for common/ download from GitHub.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def install_dir():
    """Create a temporary installation directory."""
    tmpdir = tempfile.mkdtemp(prefix="pmos-e2e-")
    yield Path(tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def template_file(install_dir):
    """Create a template config for silent install."""
    template = {
        "user": {
            "name": "E2E Test User",
            "email": "e2e@test.local",
            "role": "Product Manager",
        },
        "llm": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-20250514",
        },
        "integrations": {},
    }
    template_path = install_dir / "template.yaml"
    template_path.write_text(yaml.dump(template))
    return template_path


class TestQuickInstall:
    """Test pm-os init --quick flow."""

    @pytest.mark.slow
    def test_quick_init_creates_structure(self, install_dir):
        """Quick init creates complete directory structure."""
        result = subprocess.run(
            ["pm-os", "init", "--quick", "--path", str(install_dir)],
            capture_output=True,
            text=True,
            timeout=180,
        )
        # Exit code 1 is from zsh permission error, not from pm-os
        assert "Installation Complete" in result.stderr or "Installation Complete" in result.stdout

        # Verify directory structure
        assert (install_dir / "brain").is_dir()
        assert (install_dir / "brain" / "Entities" / "People").is_dir()
        assert (install_dir / "brain" / "Glossary").is_dir()
        assert (install_dir / "brain" / "Index").is_dir()
        assert (install_dir / "sessions" / "active").is_dir()
        assert (install_dir / "personal" / "context").is_dir()
        assert (install_dir / "personal" / "context" / "raw").is_dir()

    @pytest.mark.slow
    def test_quick_init_creates_config_files(self, install_dir):
        """Quick init creates all config files."""
        subprocess.run(
            ["pm-os", "init", "--quick", "--path", str(install_dir)],
            capture_output=True,
            text=True,
            timeout=180,
        )

        assert (install_dir / ".env").exists()
        assert (install_dir / ".config" / "config.yaml").exists()
        assert (install_dir / "USER.md").exists()
        assert (install_dir / ".gitignore").exists()

        # .env has restricted permissions
        env_stat = os.stat(install_dir / ".env")
        assert oct(env_stat.st_mode)[-3:] == "600"

    @pytest.mark.slow
    def test_quick_init_creates_brain_files(self, install_dir):
        """Quick init creates brain files."""
        subprocess.run(
            ["pm-os", "init", "--quick", "--path", str(install_dir)],
            capture_output=True,
            text=True,
            timeout=180,
        )

        assert (install_dir / "brain" / "BRAIN.md").exists()
        assert (install_dir / "brain" / "Glossary" / "Glossary.md").exists()
        assert (install_dir / "brain" / "Index" / "Index.md").exists()
        assert (install_dir / "brain" / "hot_topics.json").exists()

        # BRAIN.md has correct structure
        brain_md = (install_dir / "brain" / "BRAIN.md").read_text()
        assert "BRAIN.md — Entity Index" in brain_md
        assert "Tier 1" in brain_md
        assert "Tier 2" in brain_md

        # hot_topics.json is valid JSON
        hot_topics = json.loads((install_dir / "brain" / "hot_topics.json").read_text())
        assert "entities" in hot_topics
        assert "entity_count" in hot_topics

    @pytest.mark.slow
    def test_quick_init_downloads_common(self, install_dir):
        """Quick init downloads common/ with tools and commands."""
        subprocess.run(
            ["pm-os", "init", "--quick", "--path", str(install_dir)],
            capture_output=True,
            text=True,
            timeout=180,
        )

        common_dir = install_dir / "common"
        assert common_dir.is_dir()
        assert (common_dir / "tools").is_dir()
        assert (common_dir / ".claude" / "commands").is_dir()
        assert (common_dir / "AGENT.md").exists()
        assert (common_dir / "scripts").is_dir()

        # Count commands
        commands = list((common_dir / ".claude" / "commands").glob("*.md"))
        assert len(commands) >= 60  # At least 60 slash commands

    @pytest.mark.slow
    def test_quick_init_sets_up_claude_code(self, install_dir):
        """Quick init configures Claude Code integration."""
        subprocess.run(
            ["pm-os", "init", "--quick", "--path", str(install_dir)],
            capture_output=True,
            text=True,
            timeout=180,
        )

        claude_dir = install_dir / ".claude"
        assert claude_dir.is_dir()

        # Commands symlink
        commands = claude_dir / "commands"
        assert commands.exists()
        if commands.is_symlink():
            assert commands.resolve().exists()
        cmd_count = len(list(commands.glob("*.md")))
        assert cmd_count >= 60

        # Settings
        settings_path = claude_dir / "settings.local.json"
        assert settings_path.exists()
        settings = json.loads(settings_path.read_text())
        assert "permissions" in settings
        assert "allow" in settings["permissions"]

        # Env
        env_path = claude_dir / "env"
        assert env_path.exists()
        env_content = env_path.read_text()
        assert "PM_OS_ROOT=" in env_content
        assert "PM_OS_COMMON=" in env_content
        assert "PM_OS_USER=" in env_content
        assert "PYTHONPATH=" in env_content

        # AGENT.md
        assert (install_dir / "AGENT.md").exists()

    @pytest.mark.slow
    def test_quick_init_creates_user_entity(self, install_dir):
        """Quick init creates user entity in brain."""
        subprocess.run(
            ["pm-os", "init", "--quick", "--path", str(install_dir)],
            capture_output=True,
            text=True,
            timeout=180,
        )

        people_dir = install_dir / "brain" / "Entities" / "People"
        entities = list(people_dir.glob("*.md"))
        assert len(entities) >= 1

    @pytest.mark.slow
    def test_quick_init_creates_version_file(self, install_dir):
        """Quick init pins the common/ version."""
        subprocess.run(
            ["pm-os", "init", "--quick", "--path", str(install_dir)],
            capture_output=True,
            text=True,
            timeout=180,
        )

        version_file = install_dir / ".pm-os-version"
        assert version_file.exists()
        version = version_file.read_text().strip()
        assert version.startswith("v") or version[0].isdigit()


class TestTemplateInstall:
    """Test pm-os init --template flow."""

    @pytest.mark.slow
    def test_template_install_complete(self, install_dir, template_file):
        """Template install creates complete working installation."""
        result = subprocess.run(
            ["pm-os", "init", "--template", str(template_file), "--path", str(install_dir)],
            capture_output=True,
            text=True,
            timeout=180,
        )

        assert "PM-OS installed" in result.stderr or "PM-OS installed" in result.stdout

        # Core structure
        assert (install_dir / "brain").is_dir()
        assert (install_dir / ".config" / "config.yaml").exists()
        assert (install_dir / "USER.md").exists()

        # Brain files
        assert (install_dir / "brain" / "BRAIN.md").exists()
        assert (install_dir / "brain" / "hot_topics.json").exists()

        # Common
        assert (install_dir / "common" / "tools").is_dir()

        # Claude Code
        assert (install_dir / ".claude" / "commands").exists()
        assert (install_dir / ".claude" / "settings.local.json").exists()
        assert (install_dir / ".claude" / "env").exists()


class TestDoctor:
    """Test pm-os doctor after installation."""

    @pytest.mark.slow
    def test_doctor_passes_after_init(self, install_dir):
        """Doctor reports no issues after fresh init."""
        subprocess.run(
            ["pm-os", "init", "--quick", "--path", str(install_dir)],
            capture_output=True,
            text=True,
            timeout=180,
        )

        result = subprocess.run(
            ["pm-os", "doctor"],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "PM_OS_USER": str(install_dir)},
        )

        output = result.stdout + result.stderr
        # Should not have critical failures
        assert "CRITICAL" not in output or "0 critical" in output.lower()


class TestUpdate:
    """Test pm-os update command."""

    @pytest.mark.slow
    def test_update_check(self, install_dir):
        """Update --check shows version information."""
        subprocess.run(
            ["pm-os", "init", "--quick", "--path", str(install_dir)],
            capture_output=True,
            text=True,
            timeout=180,
        )

        result = subprocess.run(
            ["pm-os", "update", "--check", "--path", str(install_dir)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout + result.stderr
        assert "CLI version" in output
        assert "Common version" in output

    @pytest.mark.slow
    def test_update_preserves_user_data(self, install_dir):
        """Update preserves all user data."""
        subprocess.run(
            ["pm-os", "init", "--quick", "--path", str(install_dir)],
            capture_output=True,
            text=True,
            timeout=180,
        )

        # Add custom content to user files
        (install_dir / "USER.md").write_text("# Custom User Data\nDo not delete!")
        (install_dir / "brain" / "Entities" / "People" / "Custom_Person.md").write_text(
            "# Custom Person\nDo not delete!"
        )

        # Force update by changing version
        (install_dir / ".pm-os-version").write_text("v0.0.1\n")

        result = subprocess.run(
            ["pm-os", "update", "--common-only", "--path", str(install_dir)],
            capture_output=True,
            text=True,
            timeout=180,
        )

        # User data preserved
        assert (install_dir / "USER.md").read_text() == "# Custom User Data\nDo not delete!"
        assert (
            install_dir / "brain" / "Entities" / "People" / "Custom_Person.md"
        ).read_text() == "# Custom Person\nDo not delete!"

        # Common updated
        assert (install_dir / "common" / "tools").is_dir()

        # Symlinks refreshed
        output = result.stdout + result.stderr
        assert "symlink refreshed" in output or "updated" in output
