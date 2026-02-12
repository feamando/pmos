"""
PM-OS Credential Testing

Functions to test API credentials before saving.
"""

import time
from typing import Tuple, Optional
from functools import wraps


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator for retry with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (doubles each retry)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)
            # Return failure with last exception
            return False, f"Failed after {max_retries} attempts: {last_exception}"
        return wrapper
    return decorator


@retry_with_backoff(max_retries=2, base_delay=1.0)
def test_bedrock_credentials(region: str = "us-east-1", timeout: int = 10) -> Tuple[bool, str]:
    """Test AWS Bedrock credentials by listing models.

    Args:
        region: AWS region for Bedrock
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, message)
    """
    try:
        import boto3
        from botocore.config import Config
        from botocore.exceptions import (
            ClientError,
            NoCredentialsError,
            PartialCredentialsError,
            EndpointConnectionError
        )
    except ImportError:
        return False, "boto3 not installed. Run: pip install boto3"

    try:
        config = Config(
            connect_timeout=timeout,
            read_timeout=timeout,
            retries={'max_attempts': 1}
        )

        client = boto3.client(
            'bedrock',
            region_name=region,
            config=config
        )

        # Try to list foundation models (minimal API call)
        response = client.list_foundation_models(maxResults=1)

        if 'modelSummaries' in response:
            return True, f"Bedrock access confirmed in {region}"
        return True, "Bedrock credentials valid"

    except NoCredentialsError:
        return False, "No AWS credentials found. Run 'aws configure' or set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY"
    except PartialCredentialsError:
        return False, "Incomplete AWS credentials. Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == 'AccessDeniedException':
            return False, "Access denied. Check IAM permissions for Bedrock"
        elif error_code == 'UnrecognizedClientException':
            return False, "Invalid AWS credentials"
        return False, f"AWS error: {error_code}"
    except EndpointConnectionError:
        return False, f"Cannot connect to Bedrock in {region}. Check region and network"
    except Exception as e:
        return False, f"Bedrock test failed: {str(e)}"


@retry_with_backoff(max_retries=2, base_delay=1.0)
def test_anthropic_credentials(api_key: str, timeout: int = 10) -> Tuple[bool, str]:
    """Test Anthropic API credentials.

    Args:
        api_key: Anthropic API key
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, message)
    """
    try:
        import requests
    except ImportError:
        return False, "requests not installed"

    if not api_key:
        return False, "API key is required"

    try:
        response = requests.get(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01"
            },
            timeout=timeout
        )

        if response.status_code == 200:
            return True, "Anthropic API key valid"
        elif response.status_code == 401:
            return False, "Invalid API key"
        elif response.status_code == 403:
            return False, "API key does not have access"
        else:
            return False, f"API returned status {response.status_code}"

    except requests.Timeout:
        return False, "Connection timed out"
    except requests.ConnectionError:
        return False, "Cannot connect to Anthropic API"
    except Exception as e:
        return False, f"Test failed: {str(e)}"


@retry_with_backoff(max_retries=2, base_delay=1.0)
def test_openai_credentials(api_key: str, timeout: int = 10) -> Tuple[bool, str]:
    """Test OpenAI API credentials.

    Args:
        api_key: OpenAI API key
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, message)
    """
    try:
        import requests
    except ImportError:
        return False, "requests not installed"

    if not api_key:
        return False, "API key is required"

    try:
        response = requests.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout
        )

        if response.status_code == 200:
            return True, "OpenAI API key valid"
        elif response.status_code == 401:
            return False, "Invalid API key"
        elif response.status_code == 429:
            return True, "API key valid (rate limited)"
        else:
            return False, f"API returned status {response.status_code}"

    except requests.Timeout:
        return False, "Connection timed out"
    except requests.ConnectionError:
        return False, "Cannot connect to OpenAI API"
    except Exception as e:
        return False, f"Test failed: {str(e)}"


@retry_with_backoff(max_retries=2, base_delay=1.0)
def test_ollama_connection(host: str = "http://localhost:11434", timeout: int = 5) -> Tuple[bool, str]:
    """Test Ollama connectivity.

    Args:
        host: Ollama host URL
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, message)
    """
    try:
        import requests
    except ImportError:
        return False, "requests not installed"

    try:
        # Try the tags endpoint to list models
        response = requests.get(
            f"{host.rstrip('/')}/api/tags",
            timeout=timeout
        )

        if response.status_code == 200:
            data = response.json()
            model_count = len(data.get('models', []))
            return True, f"Ollama connected ({model_count} models available)"
        else:
            return False, f"Ollama returned status {response.status_code}"

    except requests.Timeout:
        return False, "Connection timed out. Is Ollama running?"
    except requests.ConnectionError:
        return False, f"Cannot connect to Ollama at {host}. Is it running?"
    except Exception as e:
        return False, f"Test failed: {str(e)}"


@retry_with_backoff(max_retries=2, base_delay=1.0)
def test_jira_credentials(url: str, email: str, token: str, timeout: int = 10) -> Tuple[bool, str]:
    """Test Jira credentials.

    Args:
        url: Jira instance URL
        email: User email
        token: API token
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, message)
    """
    try:
        import requests
        from requests.auth import HTTPBasicAuth
    except ImportError:
        return False, "requests not installed"

    if not all([url, email, token]):
        return False, "URL, email, and token are all required"

    try:
        # Use the myself endpoint to verify credentials
        api_url = f"{url.rstrip('/')}/rest/api/3/myself"

        response = requests.get(
            api_url,
            auth=HTTPBasicAuth(email, token),
            timeout=timeout,
            headers={"Accept": "application/json"}
        )

        if response.status_code == 200:
            data = response.json()
            display_name = data.get('displayName', 'User')
            return True, f"Jira authenticated as {display_name}"
        elif response.status_code == 401:
            return False, "Invalid credentials"
        elif response.status_code == 403:
            return False, "Access forbidden. Check permissions"
        elif response.status_code == 404:
            return False, "Jira API not found. Check URL"
        else:
            return False, f"Jira returned status {response.status_code}"

    except requests.Timeout:
        return False, "Connection timed out"
    except requests.ConnectionError:
        return False, f"Cannot connect to {url}"
    except Exception as e:
        return False, f"Test failed: {str(e)}"


@retry_with_backoff(max_retries=2, base_delay=1.0)
def test_slack_credentials(token: str, timeout: int = 10) -> Tuple[bool, str]:
    """Test Slack bot token.

    Args:
        token: Slack bot token (xoxb-...)
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, message)
    """
    try:
        import requests
    except ImportError:
        return False, "requests not installed"

    if not token:
        return False, "Token is required"

    try:
        response = requests.post(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                bot_name = data.get('user', 'bot')
                team = data.get('team', 'workspace')
                return True, f"Slack authenticated as @{bot_name} in {team}"
            else:
                error = data.get('error', 'Unknown error')
                if error == 'invalid_auth':
                    return False, "Invalid token"
                elif error == 'token_revoked':
                    return False, "Token has been revoked"
                return False, f"Slack error: {error}"
        else:
            return False, f"Slack returned status {response.status_code}"

    except requests.Timeout:
        return False, "Connection timed out"
    except requests.ConnectionError:
        return False, "Cannot connect to Slack API"
    except Exception as e:
        return False, f"Test failed: {str(e)}"


@retry_with_backoff(max_retries=2, base_delay=1.0)
def test_github_credentials(token: str, timeout: int = 10) -> Tuple[bool, str]:
    """Test GitHub token.

    Args:
        token: GitHub personal access token
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, message)
    """
    try:
        import requests
    except ImportError:
        return False, "requests not installed"

    if not token:
        return False, "Token is required"

    try:
        response = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json"
            },
            timeout=timeout
        )

        if response.status_code == 200:
            data = response.json()
            username = data.get('login', 'user')
            return True, f"GitHub authenticated as @{username}"
        elif response.status_code == 401:
            return False, "Invalid or expired token"
        elif response.status_code == 403:
            return False, "Token does not have required permissions"
        else:
            return False, f"GitHub returned status {response.status_code}"

    except requests.Timeout:
        return False, "Connection timed out"
    except requests.ConnectionError:
        return False, "Cannot connect to GitHub API"
    except Exception as e:
        return False, f"Test failed: {str(e)}"


@retry_with_backoff(max_retries=2, base_delay=1.0)
def test_confluence_credentials(url: str, email: str, token: str, timeout: int = 10) -> Tuple[bool, str]:
    """Test Confluence credentials.

    Args:
        url: Confluence URL
        email: User email
        token: API token
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, message)
    """
    try:
        import requests
        from requests.auth import HTTPBasicAuth
    except ImportError:
        return False, "requests not installed"

    if not all([url, email, token]):
        return False, "URL, email, and token are all required"

    try:
        # Use the current user endpoint
        api_url = f"{url.rstrip('/')}/wiki/rest/api/user/current"

        response = requests.get(
            api_url,
            auth=HTTPBasicAuth(email, token),
            timeout=timeout,
            headers={"Accept": "application/json"}
        )

        if response.status_code == 200:
            data = response.json()
            display_name = data.get('displayName', 'User')
            return True, f"Confluence authenticated as {display_name}"
        elif response.status_code == 401:
            return False, "Invalid credentials"
        elif response.status_code == 403:
            return False, "Access forbidden"
        elif response.status_code == 404:
            # Try alternative endpoint for cloud
            api_url = f"{url.rstrip('/')}/rest/api/user/current"
            response = requests.get(
                api_url,
                auth=HTTPBasicAuth(email, token),
                timeout=timeout
            )
            if response.status_code == 200:
                return True, "Confluence authenticated"
            return False, "Confluence API not found. Check URL"
        else:
            return False, f"Confluence returned status {response.status_code}"

    except requests.Timeout:
        return False, "Connection timed out"
    except requests.ConnectionError:
        return False, f"Cannot connect to {url}"
    except Exception as e:
        return False, f"Test failed: {str(e)}"
