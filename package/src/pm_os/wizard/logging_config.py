"""
PM-OS Logging Configuration

Configurable logging with debug mode support.
"""

import os
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from pm_os.wizard.ui import mask_secrets


# Check for debug mode
DEBUG_MODE = os.environ.get("PM_OS_DEBUG", "").lower() in ("1", "true", "yes")


class SecretMaskingFormatter(logging.Formatter):
    """Formatter that masks secrets in log messages."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        return mask_secrets(message)


def setup_logging(
    level: Optional[int] = None,
    log_file: Optional[Path] = None,
    quiet: bool = False
) -> logging.Logger:
    """Set up logging configuration.

    Args:
        level: Logging level (default: DEBUG if PM_OS_DEBUG, else INFO)
        log_file: Optional path to log file
        quiet: If True, suppress console output

    Returns:
        Configured logger
    """
    # Determine log level
    if level is None:
        level = logging.DEBUG if DEBUG_MODE else logging.INFO

    # Get logger
    logger = logging.getLogger("pm_os")
    logger.setLevel(level)

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler
    if not quiet:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)

        if DEBUG_MODE:
            console_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        else:
            console_format = "%(message)s"

        console_handler.setFormatter(SecretMaskingFormatter(console_format))
        logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_format = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s"
        file_handler.setFormatter(SecretMaskingFormatter(file_format))
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "pm_os") -> logging.Logger:
    """Get a logger with the PM-OS configuration.

    Args:
        name: Logger name (will be prefixed with 'pm_os.')

    Returns:
        Configured logger
    """
    if not name.startswith("pm_os"):
        name = f"pm_os.{name}"

    logger = logging.getLogger(name)

    # Ensure parent logger is configured
    parent = logging.getLogger("pm_os")
    if not parent.handlers:
        setup_logging()

    return logger


def log_debug(message: str, *args, **kwargs):
    """Log a debug message (only shown in debug mode)."""
    logger = get_logger()
    logger.debug(message, *args, **kwargs)


def log_info(message: str, *args, **kwargs):
    """Log an info message."""
    logger = get_logger()
    logger.info(message, *args, **kwargs)


def log_warning(message: str, *args, **kwargs):
    """Log a warning message."""
    logger = get_logger()
    logger.warning(message, *args, **kwargs)


def log_error(message: str, *args, **kwargs):
    """Log an error message."""
    logger = get_logger()
    logger.error(message, *args, **kwargs)


def get_log_path(install_path: Path) -> Path:
    """Get the default log file path."""
    return install_path / "logs" / f"pm-os-{datetime.now().strftime('%Y-%m-%d')}.log"


# Environment variable documentation
ENV_VARS = {
    "PM_OS_DEBUG": {
        "description": "Enable debug mode with verbose logging",
        "values": ["1", "true", "yes"],
        "default": "false"
    },
    "PM_OS_USER": {
        "description": "Override default PM-OS installation path",
        "default": "~/pm-os"
    },
    "PM_OS_LOG_LEVEL": {
        "description": "Set logging level",
        "values": ["DEBUG", "INFO", "WARNING", "ERROR"],
        "default": "INFO"
    }
}
