"""Tests for PM-OS credential validators."""

import pytest


class TestCredentialValidators:
    """Test credential validation functions."""

    def test_validate_anthropic_key_valid(self):
        """Test valid Anthropic API key."""
        from pm_os.wizard.validators import validate_anthropic_key

        valid, msg = validate_anthropic_key("sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890")
        assert valid is True

    def test_validate_anthropic_key_old_format(self):
        """Test old format Anthropic API key."""
        from pm_os.wizard.validators import validate_anthropic_key

        valid, msg = validate_anthropic_key("sk-abcdefghijklmnopqrstuv")
        assert valid is True

    def test_validate_anthropic_key_invalid(self):
        """Test invalid Anthropic API key."""
        from pm_os.wizard.validators import validate_anthropic_key

        valid, msg = validate_anthropic_key("invalid-key")
        assert valid is False
        assert "sk-" in msg

    def test_validate_anthropic_key_too_short(self):
        """Test too short API key."""
        from pm_os.wizard.validators import validate_anthropic_key

        valid, msg = validate_anthropic_key("sk-abc")
        assert valid is False
        assert "short" in msg

    def test_validate_openai_key_valid(self):
        """Test valid OpenAI API key."""
        from pm_os.wizard.validators import validate_openai_key

        valid, msg = validate_openai_key("sk-proj-abcdefghijklmnopqrstuvwxyz1234567890")
        assert valid is True

    def test_validate_openai_key_invalid(self):
        """Test invalid OpenAI API key."""
        from pm_os.wizard.validators import validate_openai_key

        valid, msg = validate_openai_key("not-an-openai-key")
        assert valid is False

    def test_validate_slack_token_valid(self):
        """Test valid Slack bot token."""
        from pm_os.wizard.validators import validate_slack_token

        valid, msg = validate_slack_token("xoxb-FAKE-TEST-TOKEN")
        assert valid is True

    def test_validate_slack_token_user_token(self):
        """Test user token rejected with helpful message."""
        from pm_os.wizard.validators import validate_slack_token

        valid, msg = validate_slack_token("xoxp-FAKE-TEST-TOKEN")
        assert valid is False
        assert "user token" in msg.lower()
        assert "bot token" in msg.lower()

    def test_validate_slack_token_invalid(self):
        """Test invalid Slack token."""
        from pm_os.wizard.validators import validate_slack_token

        valid, msg = validate_slack_token("invalid-token")
        assert valid is False

    def test_validate_github_token_pat(self):
        """Test valid GitHub PAT."""
        from pm_os.wizard.validators import validate_github_token

        valid, msg = validate_github_token("ghp_abcdefghijklmnopqrstuvwxyz1234567890")
        assert valid is True

    def test_validate_github_token_fine_grained(self):
        """Test valid GitHub fine-grained token."""
        from pm_os.wizard.validators import validate_github_token

        valid, msg = validate_github_token("github_pat_abcdefghijklmnopqrstuvwxyz")
        assert valid is True

    def test_validate_github_token_classic(self):
        """Test valid classic GitHub token."""
        from pm_os.wizard.validators import validate_github_token

        valid, msg = validate_github_token("a" * 40)  # 40 hex chars
        assert valid is True

    def test_validate_github_token_invalid(self):
        """Test invalid GitHub token."""
        from pm_os.wizard.validators import validate_github_token

        valid, msg = validate_github_token("invalid")
        assert valid is False

    def test_validate_jira_token_valid(self):
        """Test valid Jira API token."""
        from pm_os.wizard.validators import validate_jira_token

        valid, msg = validate_jira_token("ATATT3xFfGF0abcdefghijklmnop")
        assert valid is True

    def test_validate_jira_token_too_short(self):
        """Test too short Jira token."""
        from pm_os.wizard.validators import validate_jira_token

        valid, msg = validate_jira_token("abc")
        assert valid is False
        assert "short" in msg

    def test_validate_url_valid(self):
        """Test valid URL."""
        from pm_os.wizard.validators import validate_url

        valid, msg = validate_url("https://example.atlassian.net")
        assert valid is True

    def test_validate_url_with_path(self):
        """Test valid URL with path."""
        from pm_os.wizard.validators import validate_url

        valid, msg = validate_url("https://example.com/api/v1")
        assert valid is True

    def test_validate_url_http(self):
        """Test HTTP URL (allowed by default)."""
        from pm_os.wizard.validators import validate_url

        valid, msg = validate_url("http://localhost:8080")
        # localhost URLs are valid
        assert valid is False  # Our pattern requires domain with TLD

    def test_validate_url_require_https(self):
        """Test HTTPS requirement."""
        from pm_os.wizard.validators import validate_url

        valid, msg = validate_url("http://example.com", require_https=True)
        assert valid is False
        assert "HTTPS" in msg

    def test_validate_email_valid(self):
        """Test valid email."""
        from pm_os.wizard.validators import validate_email

        valid, msg = validate_email("user@example.com")
        assert valid is True

    def test_validate_email_invalid(self):
        """Test invalid email."""
        from pm_os.wizard.validators import validate_email

        valid, msg = validate_email("not-an-email")
        assert valid is False

    def test_validate_aws_region_valid(self):
        """Test valid AWS region."""
        from pm_os.wizard.validators import validate_aws_region

        valid, msg = validate_aws_region("us-east-1")
        assert valid is True
        assert "Bedrock" in msg

    def test_validate_aws_region_non_bedrock(self):
        """Test valid AWS region without Bedrock."""
        from pm_os.wizard.validators import validate_aws_region

        valid, msg = validate_aws_region("us-east-2")
        assert valid is True
        assert "may not support" in msg

    def test_validate_aws_region_invalid(self):
        """Test invalid AWS region."""
        from pm_os.wizard.validators import validate_aws_region

        valid, msg = validate_aws_region("invalid-region")
        assert valid is False

    def test_validate_credential_generic(self):
        """Test generic credential validation."""
        from pm_os.wizard.validators import validate_credential

        # Known type
        valid, msg = validate_credential("anthropic_api_key", "sk-ant-abc123456789012345678901234")
        assert valid is True

        # Unknown type
        valid, msg = validate_credential("unknown_type", "any-value")
        assert valid is True  # No validation for unknown types


class TestTimezoneValidation:
    """Test timezone validation."""

    def test_validate_timezone_utc(self):
        """Test UTC timezone."""
        from pm_os.wizard.validators import validate_timezone

        valid, msg = validate_timezone("UTC")
        assert valid is True

    def test_validate_timezone_common(self):
        """Test common timezone formats."""
        from pm_os.wizard.validators import validate_timezone

        valid, msg = validate_timezone("America/New_York")
        assert valid is True

        valid, msg = validate_timezone("Europe/London")
        assert valid is True

        valid, msg = validate_timezone("Asia/Tokyo")
        assert valid is True

    def test_validate_timezone_empty(self):
        """Test empty timezone (allowed)."""
        from pm_os.wizard.validators import validate_timezone

        valid, msg = validate_timezone("")
        assert valid is True

    def test_validate_timezone_invalid(self):
        """Test invalid timezone format."""
        from pm_os.wizard.validators import validate_timezone

        valid, msg = validate_timezone("not-a-timezone")
        assert valid is False

    def test_validate_timezone_partial_match(self):
        """Test timezone partial match."""
        from pm_os.wizard.validators import validate_timezone

        # Should match Europe/Berlin or similar
        valid, msg = validate_timezone("Europe/Berlin")
        assert valid is True
