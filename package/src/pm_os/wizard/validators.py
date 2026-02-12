"""
PM-OS Wizard Validators

Credential and input validation utilities.
"""

import re
from typing import Tuple, Optional


def validate_anthropic_key(key: str) -> Tuple[bool, str]:
    """Validate Anthropic API key format.

    Args:
        key: The API key to validate

    Returns:
        Tuple of (is_valid, message)
    """
    if not key:
        return False, "API key is required"

    # Anthropic keys start with sk-ant- or sk-
    if key.startswith("sk-ant-"):
        if len(key) < 30:
            return False, "API key appears too short"
        return True, "Valid Anthropic API key format"
    elif key.startswith("sk-"):
        if len(key) < 20:
            return False, "API key appears too short"
        return True, "Valid API key format"

    return False, "Anthropic API keys should start with 'sk-ant-' or 'sk-'"


def validate_openai_key(key: str) -> Tuple[bool, str]:
    """Validate OpenAI API key format.

    Args:
        key: The API key to validate

    Returns:
        Tuple of (is_valid, message)
    """
    if not key:
        return False, "API key is required"

    # OpenAI keys start with sk-
    if not key.startswith("sk-"):
        return False, "OpenAI API keys should start with 'sk-'"

    if len(key) < 20:
        return False, "API key appears too short"

    return True, "Valid OpenAI API key format"


def validate_slack_token(token: str) -> Tuple[bool, str]:
    """Validate Slack bot token format.

    Args:
        token: The bot token to validate

    Returns:
        Tuple of (is_valid, message)
    """
    if not token:
        return False, "Bot token is required"

    # Slack bot tokens start with xoxb-
    if not token.startswith("xoxb-"):
        if token.startswith("xoxp-"):
            return False, "This appears to be a user token (xoxp-). Use a bot token (xoxb-) instead."
        return False, "Slack bot tokens should start with 'xoxb-'"

    if len(token) < 20:
        return False, "Token appears too short"

    return True, "Valid Slack bot token format"


def validate_github_token(token: str) -> Tuple[bool, str]:
    """Validate GitHub personal access token format.

    Args:
        token: The PAT to validate

    Returns:
        Tuple of (is_valid, message)
    """
    if not token:
        return False, "Token is required"

    # GitHub PATs can be:
    # - Classic: ghp_xxxx (40 chars after prefix)
    # - Fine-grained: github_pat_xxxx
    # - OAuth: gho_xxxx
    if token.startswith(("ghp_", "gho_", "github_pat_")):
        if len(token) < 20:
            return False, "Token appears too short"
        return True, "Valid GitHub token format"

    # Legacy tokens don't have prefix
    if len(token) == 40 and re.match(r'^[a-f0-9]+$', token):
        return True, "Valid GitHub token format (classic)"

    return False, "GitHub tokens should start with 'ghp_', 'gho_', or 'github_pat_'"


def validate_jira_token(token: str) -> Tuple[bool, str]:
    """Validate Jira/Atlassian API token format.

    Args:
        token: The API token to validate

    Returns:
        Tuple of (is_valid, message)
    """
    if not token:
        return False, "API token is required"

    # Atlassian API tokens are base64-ish strings, typically 24+ chars
    if len(token) < 20:
        return False, "API token appears too short"

    # Should be alphanumeric with possible special chars
    if not re.match(r'^[a-zA-Z0-9+/=_-]+$', token):
        return False, "Token contains invalid characters"

    return True, "Valid Atlassian API token format"


def validate_url(url: str, require_https: bool = False) -> Tuple[bool, str]:
    """Validate URL format.

    Args:
        url: The URL to validate
        require_https: If True, require HTTPS protocol

    Returns:
        Tuple of (is_valid, message)
    """
    if not url:
        return False, "URL is required"

    # Basic URL pattern
    pattern = r'^https?://[a-zA-Z0-9][-a-zA-Z0-9]*(\.[a-zA-Z0-9][-a-zA-Z0-9]*)+(/.*)?$'
    if not re.match(pattern, url):
        return False, "Invalid URL format"

    if require_https and not url.startswith("https://"):
        return False, "HTTPS is required for security"

    return True, "Valid URL format"


def validate_email(email: str) -> Tuple[bool, str]:
    """Validate email format.

    Args:
        email: The email to validate

    Returns:
        Tuple of (is_valid, message)
    """
    if not email:
        return False, "Email is required"

    # RFC 5322 simplified pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "Invalid email format"

    return True, "Valid email format"


def validate_aws_region(region: str) -> Tuple[bool, str]:
    """Validate AWS region format.

    Args:
        region: The AWS region to validate

    Returns:
        Tuple of (is_valid, message)
    """
    if not region:
        return False, "Region is required"

    # AWS regions follow pattern: us-east-1, eu-west-2, ap-southeast-1, etc.
    pattern = r'^[a-z]{2}-[a-z]+-\d$'
    if not re.match(pattern, region):
        return False, "Invalid AWS region format (e.g., us-east-1)"

    # Known Bedrock regions
    bedrock_regions = [
        "us-east-1", "us-west-2", "eu-west-1", "eu-west-3",
        "eu-central-1", "ap-southeast-1", "ap-southeast-2",
        "ap-northeast-1", "ap-south-1"
    ]

    if region not in bedrock_regions:
        return True, f"Valid format, but {region} may not support Bedrock"

    return True, "Valid Bedrock region"


# Common timezone names for validation fallback
COMMON_TIMEZONES = [
    "UTC", "GMT",
    "US/Eastern", "US/Central", "US/Mountain", "US/Pacific",
    "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "America/Toronto", "America/Vancouver", "America/Sao_Paulo", "America/Mexico_City",
    "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Amsterdam",
    "Europe/Madrid", "Europe/Rome", "Europe/Moscow",
    "Asia/Tokyo", "Asia/Shanghai", "Asia/Singapore", "Asia/Hong_Kong",
    "Asia/Seoul", "Asia/Mumbai", "Asia/Dubai", "Asia/Bangkok",
    "Australia/Sydney", "Australia/Melbourne", "Australia/Perth",
    "Pacific/Auckland", "Pacific/Honolulu",
    "Africa/Cairo", "Africa/Johannesburg", "Africa/Lagos",
]


def validate_timezone(timezone: str) -> Tuple[bool, str]:
    """Validate timezone string.

    Args:
        timezone: The timezone to validate (e.g., 'America/New_York', 'UTC')

    Returns:
        Tuple of (is_valid, message)
    """
    if not timezone:
        return True, "Using default timezone"

    # Try pytz first if available
    try:
        import pytz
        try:
            pytz.timezone(timezone)
            return True, f"Valid timezone: {timezone}"
        except pytz.exceptions.UnknownTimeZoneError:
            # Get suggestions
            suggestions = [tz for tz in pytz.all_timezones if timezone.lower() in tz.lower()][:5]
            suggestion_str = ", ".join(suggestions) if suggestions else "Try 'America/New_York' or 'UTC'"
            return False, f"Unknown timezone '{timezone}'. Did you mean: {suggestion_str}"
    except ImportError:
        pass

    # Fallback: check against common timezones
    if timezone in COMMON_TIMEZONES:
        return True, f"Valid timezone: {timezone}"

    # Check for partial match
    matches = [tz for tz in COMMON_TIMEZONES if timezone.lower() in tz.lower()]
    if matches:
        return True, f"Timezone '{timezone}' looks valid (similar to {matches[0]})"

    # Basic pattern check
    if re.match(r'^[A-Za-z_]+/[A-Za-z_]+$', timezone):
        return True, f"Timezone '{timezone}' looks valid"

    return False, f"Invalid timezone format. Use format like 'America/New_York' or 'UTC'"


# Map of credential types to validators
CREDENTIAL_VALIDATORS = {
    "anthropic_api_key": validate_anthropic_key,
    "openai_api_key": validate_openai_key,
    "slack_bot_token": validate_slack_token,
    "github_token": validate_github_token,
    "jira_token": validate_jira_token,
    "confluence_token": validate_jira_token,  # Same format as Jira
    "timezone": validate_timezone,
}


def validate_credential(cred_type: str, value: str) -> Tuple[bool, str]:
    """Validate a credential by type.

    Args:
        cred_type: The type of credential (e.g., 'anthropic_api_key')
        value: The credential value

    Returns:
        Tuple of (is_valid, message)
    """
    validator = CREDENTIAL_VALIDATORS.get(cred_type)
    if validator:
        return validator(value)
    return True, "No specific validation for this credential type"
