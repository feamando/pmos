#!/usr/bin/env python3
"""
PM-OS Connector Bridge (v5.0)

Three-tier auth abstraction for external service access:
  1. Claude connector (MCP tool, zero config for user)
  2. .env API token (for background/pipeline tasks)
  3. Helpful error with setup instructions

Usage:
    from pm_os_base.tools.core.connector_bridge import get_auth, ConnectorAuth

    auth = get_auth("jira")
    if auth.source == "connector":
        # Claude session — data fetched via connector MCP tool
        pass
    elif auth.source == "env":
        # Background task — use token from .env
        token = auth.token
    elif auth.source == "none":
        # No auth available
        print(auth.help_message)
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ConnectorAuth:
    """Authentication result from the connector bridge."""
    service: str
    source: str  # "connector", "env", "none"
    token: Optional[str] = None
    help_message: Optional[str] = None
    connector_tool_name: Optional[str] = None


# Service configuration — maps service names to env vars and connector tool names
SERVICE_REGISTRY = {
    "google": {
        "env_keys": ["GOOGLE_APPLICATION_CREDENTIALS"],
        "connector_tool": "google",
        "display_name": "Google (Calendar, Drive, Gmail)",
        "setup_url": "Claude -> Settings -> Connectors",
    },
    "jira": {
        "env_keys": ["JIRA_API_TOKEN"],
        "connector_tool": "jira",
        "display_name": "Jira",
        "setup_url": "Claude -> Settings -> Connectors",
    },
    "slack": {
        "env_keys": ["SLACK_BOT_TOKEN"],
        "connector_tool": "slack",
        "display_name": "Slack",
        "setup_url": "Claude -> Settings -> Connectors",
    },
    "github": {
        "env_keys": ["GITHUB_TOKEN"],
        "connector_tool": "github",
        "display_name": "GitHub",
        "setup_url": "Claude -> Settings -> Connectors",
    },
    "figma": {
        "env_keys": ["FIGMA_ACCESS_TOKEN"],
        "connector_tool": "figma",
        "display_name": "Figma",
        "setup_url": "Claude -> Settings -> Connectors",
    },
    "confluence": {
        "env_keys": ["JIRA_API_TOKEN"],
        "connector_tool": "confluence",
        "display_name": "Confluence",
        "setup_url": "Claude -> Settings -> Connectors",
    },
    "statsig": {
        "env_keys": ["STATSIG_CONSOLE_API_KEY"],
        "connector_tool": "statsig",
        "display_name": "Statsig",
        "setup_url": "Claude -> Settings -> Connectors",
    },
    "tableau": {
        "env_keys": ["TABLEAU_TOKEN_NAME", "TABLEAU_TOKEN_SECRET"],
        "connector_tool": "tableau",
        "display_name": "Tableau",
        "setup_url": "Claude -> Settings -> Connectors",
    },
}


def _is_claude_session() -> bool:
    """Check if running inside a Claude session (connector tools available)."""
    return bool(os.getenv("CLAUDE_CODE_SESSION") or os.getenv("CLAUDE_SESSION"))


def _check_env_token(service: str) -> Optional[str]:
    """Check if API token exists in environment."""
    service_config = SERVICE_REGISTRY.get(service, {})
    env_keys = service_config.get("env_keys", [])

    for key in env_keys:
        value = os.getenv(key)
        if value:
            return value
    return None


def _build_help_message(service: str) -> str:
    """Build a helpful error message for missing auth."""
    service_config = SERVICE_REGISTRY.get(service, {})
    display_name = service_config.get("display_name", service)
    setup_url = service_config.get("setup_url", "Claude -> Settings -> Connectors")
    env_keys = service_config.get("env_keys", [])

    env_option = ""
    if env_keys:
        key_list = ", ".join(env_keys)
        env_option = (
            f"\n  2. Add {key_list} to your PM-OS .env file "
            f"(Connector App -> Settings -> API Connections)"
            f"\n     Option 1 works for all PM-OS commands. "
            f"Option 2 also enables background enrichment."
        )

    return (
        f"{display_name} not accessible. Two options:\n"
        f"  1. Connect {display_name} in {setup_url}"
        f"{env_option}"
    )


def get_auth(service: str) -> ConnectorAuth:
    """
    Get authentication for a service using the three-tier fallback.

    Tier 1: Claude connector (available in interactive Claude sessions)
    Tier 2: .env API token (available for background/pipeline tasks)
    Tier 3: Helpful error message

    Args:
        service: Service name (e.g., 'jira', 'slack', 'github')

    Returns:
        ConnectorAuth with source, token, and help information.
    """
    service_config = SERVICE_REGISTRY.get(service, {})
    connector_tool = service_config.get("connector_tool", service)

    # Tier 1: Claude connector
    if _is_claude_session():
        logger.debug("Claude session detected — using connector for %s", service)
        return ConnectorAuth(
            service=service,
            source="connector",
            connector_tool_name=connector_tool,
        )

    # Tier 2: .env API token
    token = _check_env_token(service)
    if token:
        logger.debug("Using .env token for %s", service)
        return ConnectorAuth(
            service=service,
            source="env",
            token=token,
        )

    # Tier 3: No auth available
    logger.warning("No auth available for %s", service)
    return ConnectorAuth(
        service=service,
        source="none",
        help_message=_build_help_message(service),
    )


def is_service_available(service: str) -> bool:
    """
    Quick check if a service has any auth available.

    Args:
        service: Service name

    Returns:
        True if connector or env token is available.
    """
    auth = get_auth(service)
    return auth.source != "none"


def get_available_services() -> dict:
    """
    Get status of all registered services.

    Returns:
        Dict mapping service name to auth source ('connector', 'env', 'none').
    """
    return {
        service: get_auth(service).source
        for service in SERVICE_REGISTRY
    }


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PM-OS Connector Bridge")
    parser.add_argument("--check", metavar="SERVICE", help="Check auth for a service")
    parser.add_argument("--status", action="store_true", help="Show all service statuses")

    args = parser.parse_args()

    if args.check:
        auth = get_auth(args.check)
        print(f"Service: {auth.service}")
        print(f"Source:  {auth.source}")
        if auth.source == "connector":
            print(f"Tool:    {auth.connector_tool_name}")
        elif auth.source == "env":
            print(f"Token:   {'*' * 8}...set")
        elif auth.source == "none":
            print(f"\n{auth.help_message}")

    elif args.status:
        print("Service Auth Status:")
        statuses = get_available_services()
        for service, source in statuses.items():
            display = SERVICE_REGISTRY[service]["display_name"]
            icon = {"connector": "C", "env": "E", "none": "-"}[source]
            print(f"  [{icon}] {display}: {source}")
        print()
        print("  C = Claude connector  E = .env token  - = not configured")

    else:
        parser.print_help()
