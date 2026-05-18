"""Tests for pm-os-cce plugin structure: manifest, commands, skills, pipelines."""

import ast
import json
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


class TestPluginManifest:

    @pytest.fixture(autouse=True)
    def _load_manifest(self):
        manifest_path = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
        assert manifest_path.exists(), "plugin.json must exist"
        self.manifest = json.loads(manifest_path.read_text())

    def test_required_fields(self):
        for field in ["name", "version", "description", "author"]:
            assert field in self.manifest, f"Missing required field: {field}"

    def test_name(self):
        assert self.manifest["name"] == "pm-os-cce"

    def test_version_semver(self):
        parts = self.manifest["version"].split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_author_present(self):
        author = self.manifest["author"]
        assert author, "author must be present"
        assert isinstance(author, (str, dict))

    def test_dependencies_declare_base(self):
        deps = self.manifest.get("dependencies", [])
        assert "pm-os-base" in deps, "Must depend on pm-os-base"

    def test_commands_declared(self):
        cmds = self.manifest.get("commands", [])
        assert len(cmds) >= 4, "Must declare doc, feature, reason, roadmap commands"

    def test_skills_declared(self):
        skills = self.manifest.get("skills", [])
        assert len(skills) >= 4, "Must declare at least 4 skills"


class TestCommands:

    def test_commands_exist(self):
        cmd_dir = PLUGIN_ROOT / "commands"
        assert cmd_dir.exists()
        cmds = list(cmd_dir.glob("*.md"))
        assert len(cmds) >= 4

    def test_expected_commands(self):
        cmd_dir = PLUGIN_ROOT / "commands"
        expected = {"doc.md", "feature.md", "reason.md", "roadmap.md"}
        actual = {f.name for f in cmd_dir.glob("*.md")}
        assert expected.issubset(actual), f"Missing commands: {expected - actual}"

    def test_commands_have_frontmatter(self):
        for cmd in (PLUGIN_ROOT / "commands").glob("*.md"):
            content = cmd.read_text()
            assert content.startswith("---"), f"Missing frontmatter: {cmd.name}"


class TestSkills:

    def test_skills_exist(self):
        skills_dir = PLUGIN_ROOT / "skills"
        assert skills_dir.exists()
        skills = list(skills_dir.glob("*/SKILL.md"))
        assert len(skills) >= 4

    def test_skills_have_frontmatter(self):
        for skill in (PLUGIN_ROOT / "skills").rglob("SKILL.md"):
            content = skill.read_text()
            assert content.startswith("---"), f"Missing frontmatter: {skill}"


class TestPreflightChecks:

    def test_preflight_yaml_exists(self):
        path = PLUGIN_ROOT / "preflight-checks.yaml"
        assert path.exists(), "preflight-checks.yaml must exist"

    def test_preflight_yaml_valid(self):
        import yaml
        path = PLUGIN_ROOT / "preflight-checks.yaml"
        data = yaml.safe_load(path.read_text())
        assert isinstance(data, dict)
        assert len(data) >= 1


class TestPipelineExtensions:

    def test_boot_extension_exists(self):
        assert (PLUGIN_ROOT / "pipelines" / "boot-extension.yaml").exists()

    def test_logout_extension_exists(self):
        assert (PLUGIN_ROOT / "pipelines" / "logout-extension.yaml").exists()


class TestMcpJson:

    def test_mcp_json_exists(self):
        mcp_path = PLUGIN_ROOT / ".mcp.json"
        assert mcp_path.exists()
        data = json.loads(mcp_path.read_text())
        assert "mcpServers" in data


class TestToolModules:

    def test_all_python_files_parseable(self):
        tools_root = PLUGIN_ROOT / "tools"
        errors = []
        for py_file in tools_root.rglob("*.py"):
            try:
                ast.parse(py_file.read_text())
            except SyntaxError as e:
                errors.append(f"{py_file.relative_to(PLUGIN_ROOT)}: {e}")
        assert not errors, "Syntax errors:\n" + "\n".join(errors)

    def test_no_hardcoded_emails(self):
        tools_root = PLUGIN_ROOT / "tools"
        for py_file in tools_root.rglob("*.py"):
            content = py_file.read_text()
            assert "@hellofresh.com" not in content, f"Hardcoded email in {py_file.name}"
