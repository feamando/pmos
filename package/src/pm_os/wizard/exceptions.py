"""
PM-OS Wizard Exceptions

Custom exception types for better error handling and remediation suggestions.
"""

from typing import Optional, List


class PMOSError(Exception):
    """Base exception for all PM-OS errors."""

    def __init__(
        self,
        message: str,
        remediation: Optional[str] = None,
        details: Optional[str] = None
    ):
        """Initialize the error.

        Args:
            message: Human-readable error message
            remediation: Suggested fix for the user
            details: Technical details for debugging
        """
        super().__init__(message)
        self.message = message
        self.remediation = remediation
        self.details = details

    def __str__(self) -> str:
        parts = [self.message]
        if self.details:
            parts.append(f"Details: {self.details}")
        if self.remediation:
            parts.append(f"To fix: {self.remediation}")
        return "\n".join(parts)


class ConfigError(PMOSError):
    """Configuration-related errors."""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        remediation: Optional[str] = None,
        details: Optional[str] = None
    ):
        self.config_key = config_key
        if not remediation and config_key:
            remediation = f"Check your configuration for '{config_key}' in config.yaml or .env"
        super().__init__(message, remediation, details)


class CredentialError(PMOSError):
    """Credential validation errors."""

    def __init__(
        self,
        message: str,
        credential_type: Optional[str] = None,
        remediation: Optional[str] = None,
        details: Optional[str] = None
    ):
        self.credential_type = credential_type
        if not remediation and credential_type:
            remediation = f"Verify your {credential_type} credentials are correct and have required permissions"
        super().__init__(message, remediation, details)


class SyncError(PMOSError):
    """Synchronization errors (Brain population, API sync, etc.)."""

    def __init__(
        self,
        message: str,
        service: Optional[str] = None,
        remediation: Optional[str] = None,
        details: Optional[str] = None
    ):
        self.service = service
        if not remediation and service:
            remediation = f"Check your {service} connection and try again with: pm-os brain sync --integration {service.lower()}"
        super().__init__(message, remediation, details)


class NetworkError(PMOSError):
    """Network-related errors (timeouts, connection issues)."""

    def __init__(
        self,
        message: str,
        endpoint: Optional[str] = None,
        remediation: Optional[str] = None,
        details: Optional[str] = None
    ):
        self.endpoint = endpoint
        if not remediation:
            remediation = "Check your internet connection and try again. If the issue persists, the service may be temporarily unavailable."
        super().__init__(message, remediation, details)


class ValidationError(PMOSError):
    """Input validation errors."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        expected_format: Optional[str] = None,
        remediation: Optional[str] = None,
        details: Optional[str] = None
    ):
        self.field = field
        self.expected_format = expected_format
        if not remediation and field and expected_format:
            remediation = f"The {field} should be in format: {expected_format}"
        super().__init__(message, remediation, details)


class SetupError(PMOSError):
    """Installation/setup errors."""

    def __init__(
        self,
        message: str,
        step: Optional[str] = None,
        remediation: Optional[str] = None,
        details: Optional[str] = None
    ):
        self.step = step
        if not remediation and step:
            remediation = f"Run 'pm-os doctor' to diagnose issues, or restart setup with 'pm-os init'"
        super().__init__(message, remediation, details)


class SessionError(PMOSError):
    """Session management errors (stale sessions, corrupted state)."""

    def __init__(
        self,
        message: str,
        session_age_hours: Optional[float] = None,
        remediation: Optional[str] = None,
        details: Optional[str] = None
    ):
        self.session_age_hours = session_age_hours
        if not remediation:
            if session_age_hours and session_age_hours > 24:
                remediation = "Your session is stale (>24h). Run 'pm-os init' to start fresh or 'pm-os init --resume' to continue anyway."
            else:
                remediation = "Run 'pm-os init' to start a fresh installation"
        super().__init__(message, remediation, details)


class CleanupError(PMOSError):
    """Errors during cleanup/rollback."""

    def __init__(
        self,
        message: str,
        partial_files: Optional[List[str]] = None,
        remediation: Optional[str] = None,
        details: Optional[str] = None
    ):
        self.partial_files = partial_files or []
        if not remediation and partial_files:
            files_str = ", ".join(partial_files[:3])
            if len(partial_files) > 3:
                files_str += f" and {len(partial_files) - 3} more"
            remediation = f"Manual cleanup may be needed for: {files_str}"
        super().__init__(message, remediation, details)


class DependencyError(PMOSError):
    """Missing or incompatible dependency errors."""

    def __init__(
        self,
        message: str,
        package: Optional[str] = None,
        install_command: Optional[str] = None,
        remediation: Optional[str] = None,
        details: Optional[str] = None
    ):
        self.package = package
        self.install_command = install_command
        if not remediation:
            if install_command:
                remediation = f"Install the required package with: {install_command}"
            elif package:
                remediation = f"Install the required package with: pip install {package}"
        super().__init__(message, remediation, details)


# Error code mapping for CLI exit codes
ERROR_CODES = {
    ConfigError: 10,
    CredentialError: 11,
    SyncError: 12,
    NetworkError: 13,
    ValidationError: 14,
    SetupError: 15,
    SessionError: 16,
    CleanupError: 17,
    DependencyError: 18,
    PMOSError: 1,
}


def get_error_code(error: Exception) -> int:
    """Get the exit code for an error type."""
    for error_type, code in ERROR_CODES.items():
        if isinstance(error, error_type):
            return code
    return 1
