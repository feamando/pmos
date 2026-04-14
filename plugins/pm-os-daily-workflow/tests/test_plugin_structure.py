"""Tests for plugin structure: manifest, commands, skills, pipelines."""

import json
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


class TestPluginManifest:
    """Validate plugin.json follows Anthropic plugin format."""

    @pytest.fixture(autouse=True)
    def _load_manifest(self):
        manifest_path = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
        assert manifest_path.exists(), "plugin.json must exist"
        self.manifest = json.loads(manifest_path.read_text())

    def test_required_fields(self):
        for field in ["name", "version", "description", "author"]:
            assert field in self.manifest, f"Missing required field: {field}"

    def test_name(self):
        assert self.manifest["name"] == "pm-os-daily-workflow"

    def test_version_semver(self):
        parts = self.manifest["version"].split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_author_is_object(self):
        author = self.manifest["author"]
        assert isinstance(author, dict), "author must be an object per HF spec"
        for field in ["name", "email", "tribe", "squad"]:
            assert field in author, f"Missing author field: {field}"

    def test_commands_discovered(self):
        """Commands are auto-discovered from commands/ directory."""
        cmd_dir = PLUGIN_ROOT / "commands"
        assert cmd_dir.exists()
        cmds = list(cmd_dir.glob("*.md"))
        assert len(cmds) >= 1, "At least one command .md expected"

    def test_skills_discovered(self):
        """Skills are auto-discovered from skills/<name>/SKILL.md pattern."""
        skills_dir = PLUGIN_ROOT / "skills"
        assert skills_dir.exists()
        skills = list(skills_dir.glob("*/SKILL.md"))
        assert len(skills) >= 1, "At least one skill SKILL.md expected"

    def test_commands_have_frontmatter(self):
        for cmd in (PLUGIN_ROOT / "commands").glob("*.md"):
            content = cmd.read_text()
            assert content.startswith("---"), f"Command missing frontmatter: {cmd.name}"

    def test_skills_have_frontmatter(self):
        for skill in (PLUGIN_ROOT / "skills").rglob("SKILL.md"):
            content = skill.read_text()
            assert content.startswith("---"), f"Skill missing frontmatter: {skill}"


class TestMcpJson:
    """Validate .mcp.json exists."""

    def test_mcp_json_exists(self):
        mcp_path = PLUGIN_ROOT / ".mcp.json"
        assert mcp_path.exists()
        data = json.loads(mcp_path.read_text())
        assert "mcpServers" in data


class TestPipelineExtensions:
    """Validate pipeline YAML extensions."""

    def test_boot_extension_exists(self):
        path = PLUGIN_ROOT / "pipelines" / "boot-extension.yaml"
        assert path.exists()

    def test_logout_extension_exists(self):
        path = PLUGIN_ROOT / "pipelines" / "logout-extension.yaml"
        assert path.exists()

    def test_boot_extension_has_extends(self):
        path = PLUGIN_ROOT / "pipelines" / "boot-extension.yaml"
        content = path.read_text()
        assert "extends:" in content

    def test_logout_extension_has_extends(self):
        path = PLUGIN_ROOT / "pipelines" / "logout-extension.yaml"
        content = path.read_text()
        assert "extends:" in content


class TestToolModules:
    """Validate all tool modules are importable (syntax check)."""

    TOOL_DIRS = ["daily_context", "meeting", "integrations", "slack"]

    def test_all_python_files_parseable(self):
        """Every .py file must be valid Python (ast.parse)."""
        import ast

        tools_root = PLUGIN_ROOT / "tools"
        errors = []
        for py_file in tools_root.rglob("*.py"):
            try:
                ast.parse(py_file.read_text())
            except SyntaxError as e:
                errors.append(f"{py_file.relative_to(PLUGIN_ROOT)}: {e}")
        assert not errors, "Syntax errors:\n" + "\n".join(errors)

    def test_tool_dirs_have_init(self):
        tools_root = PLUGIN_ROOT / "tools"
        for d in self.TOOL_DIRS:
            init = tools_root / d / "__init__.py"
            assert init.exists(), f"Missing __init__.py in tools/{d}/"

    def test_tools_root_has_init(self):
        assert (PLUGIN_ROOT / "tools" / "__init__.py").exists()
