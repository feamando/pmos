#!/usr/bin/env python3
"""
Integration Tools Tests

Tests for: jira, github, slack, confluence, google, statsig integrations

Author: PM-OS Team
Version: 3.0.0
"""

import os
import sys
from pathlib import Path
from typing import Tuple

TOOLS_DIR = Path(__file__).parent.parent.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


# =============================================================================
# JIRA INTEGRATION TESTS
# =============================================================================


def check_jira_brain_sync_import() -> Tuple[bool, str]:
    """Check jira_brain_sync can be imported."""
    try:
        from integrations import jira_brain_sync

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_jira_brain_sync_classes() -> Tuple[bool, str]:
    """Check JiraBrainSync class exists."""
    try:
        from integrations.jira_brain_sync import JiraBrainSync

        return True, "Classes OK (JiraBrainSync)"
    except ImportError as e:
        return False, f"Missing classes: {e}"


def check_jira_bulk_extractor_import() -> Tuple[bool, str]:
    """Check jira_bulk_extractor can be imported."""
    try:
        from integrations import jira_bulk_extractor

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_jira_env_vars() -> Tuple[bool, str]:
    """Check Jira environment variables."""
    required = ["JIRA_API_TOKEN", "JIRA_SERVER", "JIRA_EMAIL"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        return False, f"Missing env vars: {', '.join(missing)}"
    return True, "Env vars OK"


# =============================================================================
# GITHUB INTEGRATION TESTS
# =============================================================================


def check_github_brain_sync_import() -> Tuple[bool, str]:
    """Check github_brain_sync can be imported."""
    try:
        from integrations import github_brain_sync

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_github_commit_extractor_import() -> Tuple[bool, str]:
    """Check github_commit_extractor can be imported."""
    try:
        from integrations import github_commit_extractor

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_github_env_vars() -> Tuple[bool, str]:
    """Check GitHub environment variables."""
    required = ["GITHUB_TOKEN"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        return False, f"Missing env vars: {', '.join(missing)}"
    return True, "Env vars OK"


# =============================================================================
# GOOGLE INTEGRATION TESTS
# =============================================================================


def check_gdocs_processor_import() -> Tuple[bool, str]:
    """Check gdocs_processor can be imported."""
    try:
        from integrations import gdocs_processor

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_gdocs_analyzer_import() -> Tuple[bool, str]:
    """Check gdocs_analyzer can be imported."""
    try:
        from integrations import gdocs_analyzer

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_download_gdrive_file_import() -> Tuple[bool, str]:
    """Check download_gdrive_file can be imported."""
    try:
        from integrations import download_gdrive_file

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_google_env_vars() -> Tuple[bool, str]:
    """Check Google environment variables."""
    required = ["GOOGLE_TOKEN_PATH"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        return False, f"Missing env vars: {', '.join(missing)}"
    return True, "Env vars OK"


# =============================================================================
# CONFLUENCE INTEGRATION TESTS
# =============================================================================


def check_confluence_brain_sync_import() -> Tuple[bool, str]:
    """Check confluence_brain_sync can be imported."""
    try:
        from integrations import confluence_brain_sync

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_confluence_env_vars() -> Tuple[bool, str]:
    """Check Confluence environment variables."""
    required = ["CONFLUENCE_API_TOKEN", "CONFLUENCE_URL"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        return False, f"Missing env vars: {', '.join(missing)}"
    return True, "Env vars OK"


# =============================================================================
# OTHER INTEGRATION TESTS
# =============================================================================


def check_statsig_brain_sync_import() -> Tuple[bool, str]:
    """Check statsig_brain_sync can be imported."""
    try:
        from integrations import statsig_brain_sync

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_cma_brain_ingest_import() -> Tuple[bool, str]:
    """Check cma_brain_ingest can be imported."""
    try:
        from integrations import cma_brain_ingest

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_domain_brain_ingest_import() -> Tuple[bool, str]:
    """Check domain_brain_ingest can be imported."""
    try:
        from integrations import domain_brain_ingest

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_strategy_indexer_import() -> Tuple[bool, str]:
    """Check strategy_indexer can be imported."""
    try:
        from integrations import strategy_indexer

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_tech_context_sync_import() -> Tuple[bool, str]:
    """Check tech_context_sync can be imported."""
    try:
        from integrations import tech_context_sync

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_prd_to_spec_import() -> Tuple[bool, str]:
    """Check prd_to_spec can be imported."""
    try:
        from integrations import prd_to_spec

        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"


def check_prd_to_spec_classes() -> Tuple[bool, str]:
    """Check prd_to_spec classes exist."""
    try:
        from integrations.prd_to_spec import (
            PRDParser,
            PRDToSpecBridge,
            QAGenerator,
            SpecFolderCreator,
            TechStackInjector,
        )

        return (
            True,
            "Classes OK (PRDParser, QAGenerator, TechStackInjector, SpecFolderCreator, PRDToSpecBridge)",
        )
    except ImportError as e:
        return False, f"Missing classes: {e}"


INTEGRATIONS_CHECKS = {
    "jira_brain_sync": [
        ("import", check_jira_brain_sync_import),
        ("classes", check_jira_brain_sync_classes),
        ("env_vars", check_jira_env_vars),
    ],
    "jira_bulk_extractor": [
        ("import", check_jira_bulk_extractor_import),
    ],
    "github_brain_sync": [
        ("import", check_github_brain_sync_import),
        ("env_vars", check_github_env_vars),
    ],
    "github_commit_extractor": [
        ("import", check_github_commit_extractor_import),
    ],
    "gdocs_processor": [
        ("import", check_gdocs_processor_import),
    ],
    "gdocs_analyzer": [
        ("import", check_gdocs_analyzer_import),
    ],
    "download_gdrive_file": [
        ("import", check_download_gdrive_file_import),
        ("env_vars", check_google_env_vars),
    ],
    "confluence_brain_sync": [
        ("import", check_confluence_brain_sync_import),
        ("env_vars", check_confluence_env_vars),
    ],
    "statsig_brain_sync": [
        ("import", check_statsig_brain_sync_import),
    ],
    "cma_brain_ingest": [
        ("import", check_cma_brain_ingest_import),
    ],
    "domain_brain_ingest": [
        ("import", check_domain_brain_ingest_import),
    ],
    "strategy_indexer": [
        ("import", check_strategy_indexer_import),
    ],
    "tech_context_sync": [
        ("import", check_tech_context_sync_import),
    ],
    "prd_to_spec": [
        ("import", check_prd_to_spec_import),
        ("classes", check_prd_to_spec_classes),
    ],
}


def run_all_checks() -> dict:
    """Run all integration checks."""
    results = {}
    for tool, checks in INTEGRATIONS_CHECKS.items():
        results[tool] = {}
        for name, check_fn in checks:
            try:
                passed, msg = check_fn()
                results[tool][name] = (passed, msg)
            except Exception as e:
                results[tool][name] = (False, f"Check error: {e}")
    return results


if __name__ == "__main__":
    results = run_all_checks()
    for tool, checks in results.items():
        print(f"\n{tool}:")
        for name, (passed, msg) in checks.items():
            icon = "+" if passed else "X"
            print(f"  {icon} {name}: {msg}")
