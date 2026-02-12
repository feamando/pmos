"""Integration tests for PM-OS installation flow."""

import os
import tempfile
from pathlib import Path

import pytest


class TestInstallationFlow:
    """Test the full installation flow."""

    @pytest.fixture
    def temp_install_dir(self):
        """Create a temporary installation directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_directory_creation(self, temp_install_dir):
        """Test directory structure creation."""
        from pm_os.wizard.steps.directories import (
            create_directory_structure,
            DIRECTORY_STRUCTURE,
        )
        from pm_os.wizard.ui import WizardUI

        ui = WizardUI()
        created, existed = create_directory_structure(temp_install_dir, ui)

        assert created == len(DIRECTORY_STRUCTURE)
        assert existed == 0

        # Verify key directories exist
        assert (temp_install_dir / "brain").exists()
        assert (temp_install_dir / "brain" / "Entities" / "People").exists()
        assert (temp_install_dir / ".config").exists()
        assert (temp_install_dir / "sessions").exists()

    def test_secrets_directory_permissions(self, temp_install_dir):
        """Test .secrets directory has secure permissions (700)."""
        import stat
        from pm_os.wizard.steps.directories import (
            create_directory_structure,
        )
        from pm_os.wizard.ui import WizardUI

        ui = WizardUI()
        create_directory_structure(temp_install_dir, ui)

        secrets_path = temp_install_dir / ".secrets"
        assert secrets_path.exists()

        # Check permissions are 700 (owner rwx only)
        mode = secrets_path.stat().st_mode
        assert stat.S_IMODE(mode) == 0o700

    def test_env_file_permissions(self, temp_install_dir):
        """Test .env file has secure permissions (600)."""
        import stat
        from pm_os.wizard.orchestrator import WizardOrchestrator
        from pm_os.wizard.steps.directories import (
            create_directory_structure,
            generate_env_file,
        )
        from pm_os.wizard.ui import WizardUI

        ui = WizardUI()
        create_directory_structure(temp_install_dir, ui)

        wizard = WizardOrchestrator(install_path=temp_install_dir)
        wizard.update_data({
            "user_name": "Test User",
            "user_email": "test@example.com",
            "llm_provider": "bedrock",
        })

        # Write .env file and set permissions
        env_content = generate_env_file(wizard, temp_install_dir)
        env_path = temp_install_dir / ".env"
        env_path.write_text(env_content)
        os.chmod(env_path, 0o600)

        # Check permissions are 600 (owner rw only)
        mode = env_path.stat().st_mode
        assert stat.S_IMODE(mode) == 0o600

    def test_gitignore_generation(self, temp_install_dir):
        """Test .gitignore is generated with security entries."""
        from pm_os.wizard.steps.directories import generate_gitignore

        generate_gitignore(temp_install_dir)

        gitignore_path = temp_install_dir / ".gitignore"
        assert gitignore_path.exists()

        content = gitignore_path.read_text()
        # Check security-sensitive entries are present
        assert ".env" in content
        assert ".secrets/" in content
        assert "*.log" in content
        assert "credentials.json" in content
        assert ".pm-os-init-session.json" in content

    def test_env_file_generation(self, temp_install_dir):
        """Test .env file generation."""
        from pm_os.wizard.orchestrator import WizardOrchestrator
        from pm_os.wizard.steps.directories import generate_env_file

        wizard = WizardOrchestrator(install_path=temp_install_dir)
        wizard.update_data({
            "user_name": "Test User",
            "user_email": "test@example.com",
            "user_role": "Product Manager",
            "llm_provider": "bedrock",
            "llm_model": "anthropic.claude-3-5-sonnet",
        })

        env_content = generate_env_file(wizard, temp_install_dir)

        assert "PMOS_USER_NAME" in env_content
        assert "Test User" in env_content
        assert "PMOS_LLM_PROVIDER" in env_content
        assert "bedrock" in env_content

    def test_config_yaml_generation(self, temp_install_dir):
        """Test config.yaml generation."""
        import yaml
        from pm_os.wizard.orchestrator import WizardOrchestrator
        from pm_os.wizard.steps.directories import generate_config_yaml

        wizard = WizardOrchestrator(install_path=temp_install_dir)
        wizard.update_data({
            "user_name": "Test User",
            "user_email": "test@example.com",
            "user_role": "Product Manager",
            "llm_provider": "anthropic",
            "llm_model": "claude-sonnet-4-20250514",
            "jira_url": "https://example.atlassian.net",
        })

        config_content = generate_config_yaml(wizard)
        config = yaml.safe_load(config_content)

        assert config["user"]["name"] == "Test User"
        assert config["llm"]["provider"] == "anthropic"
        assert config["integrations"]["jira"]["enabled"] is True

    def test_user_md_generation(self, temp_install_dir):
        """Test USER.md generation."""
        from pm_os.wizard.orchestrator import WizardOrchestrator
        from pm_os.wizard.steps.directories import generate_user_md

        wizard = WizardOrchestrator(install_path=temp_install_dir)
        wizard.update_data({
            "user_name": "Jane Doe",
            "user_email": "jane@example.com",
            "user_role": "Senior Product Manager",
            "user_team": "Platform Team",
        })

        user_md = generate_user_md(wizard)

        assert "# Jane Doe" in user_md
        assert "jane@example.com" in user_md
        assert "Senior Product Manager" in user_md
        assert "Platform Team" in user_md

    def test_brain_files_creation(self, temp_install_dir):
        """Test initial brain files creation."""
        from pm_os.wizard.steps.directories import (
            create_directory_structure,
            create_initial_brain_files,
        )
        from pm_os.wizard.ui import WizardUI

        ui = WizardUI()
        create_directory_structure(temp_install_dir, ui)
        create_initial_brain_files(temp_install_dir)

        glossary_path = temp_install_dir / "brain" / "Glossary" / "Glossary.md"
        index_path = temp_install_dir / "brain" / "Index" / "Index.md"

        assert glossary_path.exists()
        assert index_path.exists()

        glossary_content = glossary_path.read_text()
        assert "PM-OS Glossary" in glossary_content

    def test_user_entity_creation(self, temp_install_dir):
        """Test user entity creation in brain."""
        from pm_os.wizard.orchestrator import WizardOrchestrator
        from pm_os.wizard.steps.directories import create_directory_structure
        from pm_os.wizard.steps.brain_population import create_user_entity
        from pm_os.wizard.ui import WizardUI

        ui = WizardUI()
        create_directory_structure(temp_install_dir, ui)

        wizard = WizardOrchestrator(install_path=temp_install_dir)
        wizard.update_data({
            "user_name": "John Smith",
            "user_email": "john@example.com",
            "user_role": "PM",
            "user_team": "Growth",
        })

        create_user_entity(wizard)

        entity_path = temp_install_dir / "brain" / "Entities" / "People" / "John_Smith.md"
        assert entity_path.exists()

        content = entity_path.read_text()
        assert "is_self: true" in content
        assert "john@example.com" in content


class TestVerification:
    """Test verification checks."""

    @pytest.fixture
    def complete_install(self):
        """Create a complete installation for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            install_path = Path(tmpdir)

            from pm_os.wizard.orchestrator import WizardOrchestrator
            from pm_os.wizard.steps.directories import (
                create_directory_structure,
                create_initial_brain_files,
                generate_env_file,
                generate_config_yaml,
                generate_user_md,
            )
            from pm_os.wizard.ui import WizardUI

            ui = WizardUI()
            create_directory_structure(install_path, ui)
            create_initial_brain_files(install_path)

            wizard = WizardOrchestrator(install_path=install_path)
            wizard.update_data({
                "user_name": "Test User",
                "user_email": "test@example.com",
                "user_role": "PM",
                "llm_provider": "bedrock",
                "llm_model": "claude",
            })

            # Write files
            (install_path / ".env").write_text(generate_env_file(wizard, install_path))
            (install_path / ".config" / "config.yaml").write_text(generate_config_yaml(wizard))
            (install_path / "USER.md").write_text(generate_user_md(wizard))

            yield install_path

    def test_check_directory_structure(self, complete_install):
        """Test directory structure verification."""
        from pm_os.wizard.steps.verification import check_directory_structure

        passed, message = check_directory_structure(complete_install)
        assert passed is True

    def test_check_config_files(self, complete_install):
        """Test config files verification."""
        from pm_os.wizard.steps.verification import check_config_files

        passed, message = check_config_files(complete_install)
        assert passed is True

    def test_check_brain_files(self, complete_install):
        """Test brain files verification."""
        from pm_os.wizard.steps.verification import check_brain_files

        passed, message = check_brain_files(complete_install)
        assert passed is True

    def test_check_env_vars(self, complete_install):
        """Test environment vars verification."""
        from pm_os.wizard.steps.verification import check_env_vars

        passed, message = check_env_vars(complete_install)
        assert passed is True
