#!/usr/bin/env python3
"""
PM-OS Pre-Flight Verification System

Provides verification tests for all PM-OS tools to ensure system health
before boot. Run as part of /boot or standalone.

Usage:
    python3 -m preflight                    # Run all checks
    python3 -m preflight --category core    # Run specific category
    python3 -m preflight --json             # JSON output
    python3 -m preflight --quick            # Import tests only

Author: PM-OS Team
Version: 3.0.0
"""

from .registry import TOOL_REGISTRY, get_all_tools, get_tools_by_category
from .result import CategoryResult, PreflightResult

__all__ = [
    "PreflightResult",
    "CategoryResult",
    "TOOL_REGISTRY",
    "get_tools_by_category",
    "get_all_tools",
]

__version__ = "3.0.0"
