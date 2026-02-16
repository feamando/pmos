"""Tests for PM-OS credential testers."""

import pytest
from unittest.mock import patch, MagicMock
import sys


class TestRetryDecorator:
    """Test retry with backoff decorator."""

    def test_retry_success_first_attempt(self):
        """Test function succeeds on first attempt."""
        from pm_os.wizard.credential_testers import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return True, "Success"

        result = successful_func()
        assert result == (True, "Success")
        assert call_count == 1

    def test_retry_success_after_failure(self):
        """Test function succeeds after initial failure."""
        from pm_os.wizard.credential_testers import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return True, "Success"

        result = flaky_func()
        assert result == (True, "Success")
        assert call_count == 2

    def test_retry_exhausted(self):
        """Test all retries exhausted."""
        from pm_os.wizard.credential_testers import retry_with_backoff

        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def always_fails():
            raise Exception("Always fails")

        result = always_fails()
        assert result[0] is False
        assert "Failed after 2 attempts" in result[1]


class TestBedrockCredentials:
    """Test Bedrock credential testing."""

    def test_bedrock_success(self):
        """Test successful Bedrock authentication."""
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_client.list_foundation_models.return_value = {'modelSummaries': [{'modelId': 'test'}]}
        mock_boto3.client.return_value = mock_client

        with patch.dict(sys.modules, {'boto3': mock_boto3, 'botocore.config': MagicMock(), 'botocore.exceptions': MagicMock()}):
            # Need to reimport after patching
            from pm_os.wizard import credential_testers
            import importlib
            importlib.reload(credential_testers)

            success, msg = credential_testers.test_bedrock_credentials.__wrapped__(region="us-east-1")
            assert success is True


class TestAnthropicCredentials:
    """Test Anthropic credential testing."""

    def test_anthropic_success(self):
        """Test successful Anthropic authentication."""
        mock_requests = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        mock_requests.Timeout = Exception
        mock_requests.ConnectionError = Exception

        with patch.dict(sys.modules, {'requests': mock_requests}):
            from pm_os.wizard import credential_testers
            import importlib
            importlib.reload(credential_testers)

            success, msg = credential_testers.test_anthropic_credentials.__wrapped__(
                api_key="sk-ant-test123456789012345678901234"
            )
            assert success is True
            assert "valid" in msg.lower()

    def test_anthropic_invalid_key(self):
        """Test invalid Anthropic API key."""
        mock_requests = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_requests.get.return_value = mock_response
        mock_requests.Timeout = Exception
        mock_requests.ConnectionError = Exception

        with patch.dict(sys.modules, {'requests': mock_requests}):
            from pm_os.wizard import credential_testers
            import importlib
            importlib.reload(credential_testers)

            success, msg = credential_testers.test_anthropic_credentials.__wrapped__(
                api_key="invalid-key"
            )
            assert success is False
            assert "Invalid" in msg

    def test_anthropic_empty_key(self):
        """Test empty API key."""
        from pm_os.wizard.credential_testers import test_anthropic_credentials

        success, msg = test_anthropic_credentials.__wrapped__(api_key="")
        assert success is False
        assert "required" in msg.lower()


class TestOpenAICredentials:
    """Test OpenAI credential testing."""

    def test_openai_success(self):
        """Test successful OpenAI authentication."""
        mock_requests = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        mock_requests.Timeout = Exception
        mock_requests.ConnectionError = Exception

        with patch.dict(sys.modules, {'requests': mock_requests}):
            from pm_os.wizard import credential_testers
            import importlib
            importlib.reload(credential_testers)

            success, msg = credential_testers.test_openai_credentials.__wrapped__(
                api_key="sk-test123456789"
            )
            assert success is True

    def test_openai_rate_limited(self):
        """Test rate limited still counts as valid."""
        mock_requests = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_requests.get.return_value = mock_response
        mock_requests.Timeout = Exception
        mock_requests.ConnectionError = Exception

        with patch.dict(sys.modules, {'requests': mock_requests}):
            from pm_os.wizard import credential_testers
            import importlib
            importlib.reload(credential_testers)

            success, msg = credential_testers.test_openai_credentials.__wrapped__(
                api_key="sk-test123456789"
            )
            assert success is True
            assert "rate limited" in msg.lower()


class TestOllamaConnection:
    """Test Ollama connectivity testing."""

    def test_ollama_success(self):
        """Test successful Ollama connection."""
        mock_requests = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'models': [{'name': 'llama3'}]}
        mock_requests.get.return_value = mock_response
        mock_requests.Timeout = Exception
        mock_requests.ConnectionError = Exception

        with patch.dict(sys.modules, {'requests': mock_requests}):
            from pm_os.wizard import credential_testers
            import importlib
            importlib.reload(credential_testers)

            success, msg = credential_testers.test_ollama_connection.__wrapped__(
                host="http://localhost:11434"
            )
            assert success is True
            assert "connected" in msg.lower()


class TestJiraCredentials:
    """Test Jira credential testing."""

    def test_jira_success(self):
        """Test successful Jira authentication."""
        mock_requests = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'displayName': 'Test User'}
        mock_requests.get.return_value = mock_response
        mock_requests.Timeout = Exception
        mock_requests.ConnectionError = Exception

        with patch.dict(sys.modules, {'requests': mock_requests}):
            from pm_os.wizard import credential_testers
            import importlib
            importlib.reload(credential_testers)

            success, msg = credential_testers.test_jira_credentials.__wrapped__(
                url="https://example.atlassian.net",
                email="user@example.com",
                token="api-token"
            )
            assert success is True
            assert "Test User" in msg

    def test_jira_invalid_credentials(self):
        """Test invalid Jira credentials."""
        mock_requests = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_requests.get.return_value = mock_response
        mock_requests.Timeout = Exception
        mock_requests.ConnectionError = Exception

        with patch.dict(sys.modules, {'requests': mock_requests}):
            from pm_os.wizard import credential_testers
            import importlib
            importlib.reload(credential_testers)

            success, msg = credential_testers.test_jira_credentials.__wrapped__(
                url="https://example.atlassian.net",
                email="user@example.com",
                token="wrong-token"
            )
            assert success is False
            assert "Invalid" in msg

    def test_jira_missing_params(self):
        """Test missing Jira parameters."""
        from pm_os.wizard.credential_testers import test_jira_credentials

        success, msg = test_jira_credentials.__wrapped__(url="", email="", token="")
        assert success is False
        assert "required" in msg.lower()


class TestSlackCredentials:
    """Test Slack credential testing."""

    def test_slack_success(self):
        """Test successful Slack authentication."""
        mock_requests = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'ok': True,
            'user': 'testbot',
            'team': 'Test Team'
        }
        mock_requests.post.return_value = mock_response
        mock_requests.Timeout = Exception
        mock_requests.ConnectionError = Exception

        with patch.dict(sys.modules, {'requests': mock_requests}):
            from pm_os.wizard import credential_testers
            import importlib
            importlib.reload(credential_testers)

            success, msg = credential_testers.test_slack_credentials.__wrapped__(
                token="xoxb-fake-test-placeholder"
            )
            assert success is True
            assert "testbot" in msg

    def test_slack_invalid_token(self):
        """Test invalid Slack token."""
        mock_requests = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'ok': False,
            'error': 'invalid_auth'
        }
        mock_requests.post.return_value = mock_response
        mock_requests.Timeout = Exception
        mock_requests.ConnectionError = Exception

        with patch.dict(sys.modules, {'requests': mock_requests}):
            from pm_os.wizard import credential_testers
            import importlib
            importlib.reload(credential_testers)

            success, msg = credential_testers.test_slack_credentials.__wrapped__(
                token="invalid-token"
            )
            assert success is False
            assert "Invalid" in msg


class TestGitHubCredentials:
    """Test GitHub credential testing."""

    def test_github_success(self):
        """Test successful GitHub authentication."""
        mock_requests = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'login': 'testuser'}
        mock_requests.get.return_value = mock_response
        mock_requests.Timeout = Exception
        mock_requests.ConnectionError = Exception

        with patch.dict(sys.modules, {'requests': mock_requests}):
            from pm_os.wizard import credential_testers
            import importlib
            importlib.reload(credential_testers)

            success, msg = credential_testers.test_github_credentials.__wrapped__(
                token="ghp_FAKETEST00000000"
            )
            assert success is True
            assert "testuser" in msg

    def test_github_invalid_token(self):
        """Test invalid GitHub token."""
        mock_requests = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_requests.get.return_value = mock_response
        mock_requests.Timeout = Exception
        mock_requests.ConnectionError = Exception

        with patch.dict(sys.modules, {'requests': mock_requests}):
            from pm_os.wizard import credential_testers
            import importlib
            importlib.reload(credential_testers)

            success, msg = credential_testers.test_github_credentials.__wrapped__(
                token="invalid"
            )
            assert success is False
            assert "Invalid" in msg or "expired" in msg.lower()


class TestConfluenceCredentials:
    """Test Confluence credential testing."""

    def test_confluence_success(self):
        """Test successful Confluence authentication."""
        mock_requests = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'displayName': 'Test User'}
        mock_requests.get.return_value = mock_response
        mock_requests.Timeout = Exception
        mock_requests.ConnectionError = Exception

        with patch.dict(sys.modules, {'requests': mock_requests}):
            from pm_os.wizard import credential_testers
            import importlib
            importlib.reload(credential_testers)

            success, msg = credential_testers.test_confluence_credentials.__wrapped__(
                url="https://example.atlassian.net",
                email="user@example.com",
                token="api-token"
            )
            assert success is True
            assert "authenticated" in msg.lower()
