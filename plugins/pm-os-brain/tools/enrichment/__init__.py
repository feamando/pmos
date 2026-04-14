#!/usr/bin/env python3
"""
PM-OS Brain Enrichment Package (v5.0)

Source-specific enrichers for increasing entity data density.
Uses connector_bridge for external service auth.
"""

try:
    from .base_enricher import BaseEnricher
    from .context_enricher import ContextEnricher
    from .gdocs_enricher import GDocsEnricher
    from .github_enricher import GitHubEnricher
    from .jira_enricher import JiraEnricher
    from .session_enricher import SessionEnricher
    from .slack_enricher import SlackEnricher

    __all__ = [
        "BaseEnricher",
        "GDocsEnricher",
        "SlackEnricher",
        "JiraEnricher",
        "GitHubEnricher",
        "ContextEnricher",
        "SessionEnricher",
    ]
except ImportError:
    pass
