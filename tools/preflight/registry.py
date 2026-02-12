#!/usr/bin/env python3
"""
PM-OS Tool Registry

Defines all 88 PM-OS tools with their metadata for pre-flight verification.
Each tool entry specifies:
- path: relative path from tools/
- module: Python module path for import
- classes: expected classes (optional)
- functions: expected functions (optional)
- requires_config: whether tool needs config.yaml
- env_keys: required environment variables (optional)
- optional_connectivity: has optional API connectivity test
- optional_dependency: skip if dependency not installed

Author: PM-OS Team
Version: 3.0.0
"""

from typing import Any, Dict, List, Optional

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    # ==========================================================================
    # CORE INFRASTRUCTURE (4 tools)
    # ==========================================================================
    "core": {
        "config_loader": {
            "path": "config_loader.py",
            "module": "config_loader",
            "classes": ["ConfigLoader", "ConfigMetadata", "ConfigError"],
            "functions": ["get_config", "reset_config", "get_user_name"],
            "requires_config": False,
            "description": "PM-OS Configuration Loader",
        },
        "path_resolver": {
            "path": "path_resolver.py",
            "module": "path_resolver",
            "classes": ["PathResolver", "ResolvedPaths"],
            "functions": [
                "get_paths",
                "reset_paths",
                "get_root",
                "get_common",
                "get_user",
            ],
            "requires_config": False,
            "description": "Path Resolution (finds root/common/user directories)",
        },
        "entity_validator": {
            "path": "entity_validator.py",
            "module": "entity_validator",
            "classes": ["EntityValidator", "ValidationResult", "EntityType"],
            "functions": ["validate_entity", "validate_all_entities"],
            "requires_config": False,
            "description": "Entity Validator (validates Brain entity YAML frontmatter)",
        },
        "__init__": {
            "path": "__init__.py",
            "module": "",
            "skip_import": True,
            "description": "Package initialization",
        },
    },
    # ==========================================================================
    # BRAIN MANAGEMENT (15 tools - includes Brain 1.2 temporal system)
    # ==========================================================================
    "brain": {
        "brain_loader": {
            "path": "brain/brain_loader.py",
            "module": "brain.brain_loader",
            "functions": ["load_registry", "scan_for_entities", "index_experiments"],
            "requires_config": True,
            "description": "Hot topics identification and entity registry scanning",
        },
        "brain_updater": {
            "path": "brain/brain_updater.py",
            "module": "brain.brain_updater",
            "functions": [
                "load_registry",
                "scan_for_entities",
                "append_changelog_entry",
            ],
            "requires_config": True,
            "description": "Brain file updates (v1/v2 compatible)",
        },
        "unified_brain_writer": {
            "path": "brain/unified_brain_writer.py",
            "module": "brain.unified_brain_writer",
            "functions": ["load_state", "run_brain_writer", "update_entity_context"],
            "requires_config": True,
            "description": "Unified Brain writing interface (v2 schema support)",
        },
        "schema_migrator": {
            "path": "brain/schema_migrator.py",
            "module": "brain.schema_migrator",
            "classes": ["SchemaMigrator"],
            "requires_config": True,
            "description": "Brain 1.2 schema migration (v1 to v2)",
        },
        "entity_validator_brain": {
            "path": "brain/entity_validator.py",
            "module": "brain.entity_validator",
            "classes": ["EntityValidator", "ValidationResult", "SchemaVersion"],
            "requires_config": True,
            "description": "Brain entity validation (v1/v2 formats)",
        },
        "registry_v2_builder": {
            "path": "brain/registry_v2_builder.py",
            "module": "brain.registry_v2_builder",
            "classes": ["RegistryV2Builder"],
            "functions": ["build_registry_v2"],
            "requires_config": True,
            "description": "Brain v2 registry builder",
        },
        "enrichment_pipeline": {
            "path": "brain/enrichment_pipeline.py",
            "module": "brain.enrichment_pipeline",
            "classes": ["EnrichmentPipeline", "EnrichmentResult", "PipelineProgress"],
            "requires_config": True,
            "description": "Brain enrichment pipeline orchestrator",
        },
        "event_store": {
            "path": "brain/event_store.py",
            "module": "brain.event_store",
            "classes": ["Event", "EventStore"],
            "functions": ["create_event_store"],
            "requires_config": True,
            "description": "Brain event store (temporal tracking)",
        },
        "temporal_query": {
            "path": "brain/temporal_query.py",
            "module": "brain.temporal_query",
            "classes": ["EntitySnapshot", "TemporalQuery"],
            "functions": ["create_temporal_query"],
            "requires_config": True,
            "description": "Brain temporal queries (point-in-time reconstruction)",
        },
        "snapshot_manager": {
            "path": "brain/snapshot_manager.py",
            "module": "brain.snapshot_manager",
            "classes": ["SnapshotManager"],
            "functions": ["create_daily_snapshot"],
            "requires_config": True,
            "description": "Brain snapshot management",
        },
        "quality_scorer": {
            "path": "brain/quality_scorer.py",
            "module": "brain.quality_scorer",
            "classes": ["QualityScore", "QualityScorer"],
            "requires_config": True,
            "description": "Brain entity quality scoring",
        },
        "relationship_auditor": {
            "path": "brain/relationship_auditor.py",
            "module": "brain.relationship_auditor",
            "classes": ["RelationshipIssue", "AuditResult", "RelationshipAuditor"],
            "requires_config": True,
            "description": "Brain relationship auditing",
        },
        "stale_entity_detector": {
            "path": "brain/stale_entity_detector.py",
            "module": "brain.stale_entity_detector",
            "classes": ["StaleEntity", "StaleEntityDetector"],
            "requires_config": True,
            "description": "Brain stale entity detection",
        },
        "migration_runner": {
            "path": "brain/migration_runner.py",
            "module": "brain.migration_runner",
            "classes": ["MigrationRunner"],
            "requires_config": True,
            "description": "Brain 1.1 to 1.2 migration runner",
        },
        "brain___init__": {
            "path": "brain/__init__.py",
            "module": "brain",
            "skip_import": True,
            "description": "Brain package initialization",
        },
    },
    # ==========================================================================
    # DAILY CONTEXT (2 tools)
    # ==========================================================================
    "daily_context": {
        "daily_context_updater": {
            "path": "daily_context/daily_context_updater.py",
            "module": "daily_context.daily_context_updater",
            "functions": ["main", "format_output"],
            "requires_config": True,
            "description": "Daily context updates from integrations",
        },
        "daily_context___init__": {
            "path": "daily_context/__init__.py",
            "module": "daily_context",
            "skip_import": True,
            "description": "Daily context package initialization",
        },
    },
    # ==========================================================================
    # DEEP RESEARCH (3 tools)
    # ==========================================================================
    "deep_research": {
        "file_store_manager": {
            "path": "deep_research/file_store_manager.py",
            "module": "deep_research.file_store_manager",
            "requires_config": True,
            "env_keys": ["GEMINI_API_KEY"],  # Uses Gemini for deep research
            "description": "File store management for Deep Research API",
        },
        "prd_generator": {
            "path": "deep_research/prd_generator.py",
            "module": "deep_research.prd_generator",
            "requires_config": True,
            "env_keys": ["GEMINI_API_KEY"],  # Uses Gemini for PRD generation
            "description": "PRD generation using Google Deep Research API",
        },
        "deep_research___init__": {
            "path": "deep_research/__init__.py",
            "module": "deep_research",
            "skip_import": True,
            "description": "Deep research package initialization",
        },
    },
    # ==========================================================================
    # DOCUMENTATION (2 tools)
    # ==========================================================================
    "documentation": {
        "confluence_doc_sync": {
            "path": "documentation/confluence_doc_sync.py",
            "module": "documentation.confluence_doc_sync",
            "requires_config": True,
            "env_keys": [
                "JIRA_API_TOKEN"
            ],  # Uses Atlassian API token (falls back from JIRA)
            "optional_connectivity": True,
            "description": "Confluence synchronization",
        },
        "documentation___init__": {
            "path": "documentation/__init__.py",
            "module": "documentation",
            "skip_import": True,
            "description": "Documentation package initialization",
        },
    },
    # ==========================================================================
    # DOCUMENTS (5 tools)
    # ==========================================================================
    "documents": {
        "interview_processor": {
            "path": "documents/interview_processor.py",
            "module": "documents.interview_processor",
            "requires_config": False,
            "description": "Interview data processing",
        },
        "research_aggregator": {
            "path": "documents/research_aggregator.py",
            "module": "documents.research_aggregator",
            "requires_config": False,
            "description": "Research aggregation",
        },
        "synapse_builder": {
            "path": "documents/synapse_builder.py",
            "module": "documents.synapse_builder",
            "functions": ["main", "parse_frontmatter", "get_brain_files"],
            "requires_config": True,
            "description": "Bi-directional relationship enforcer",
        },
        "template_manager": {
            "path": "documents/template_manager.py",
            "module": "documents.template_manager",
            "functions": ["get_template", "render_template", "list_templates"],
            "requires_config": True,
            "description": "Template management",
        },
        "documents___init__": {
            "path": "documents/__init__.py",
            "module": "documents",
            "skip_import": True,
            "description": "Documents package initialization",
        },
    },
    # ==========================================================================
    # INTEGRATIONS (15 tools)
    # ==========================================================================
    "integrations": {
        "google_scope_validator": {
            "path": "integrations/google_scope_validator.py",
            "module": "integrations.google_scope_validator",
            "functions": ["validate_scopes", "get_token_scopes", "trigger_reauth"],
            "requires_config": True,
            "description": "Google OAuth scope validator",
        },
        "cma_brain_ingest": {
            "path": "integrations/cma_brain_ingest.py",
            "module": "integrations.cma_brain_ingest",
            "requires_config": True,
            "description": "EA data ingestion",
        },
        "confluence_brain_sync": {
            "path": "integrations/confluence_brain_sync.py",
            "module": "integrations.confluence_brain_sync",
            "functions": ["get_confluence_client", "sync_page_to_brain", "main"],
            "requires_config": True,
            "env_keys": ["JIRA_API_TOKEN"],  # Uses Atlassian API token (same as Jira)
            "optional_connectivity": True,
            "description": "Confluence brain sync",
        },
        "domain_brain_ingest": {
            "path": "integrations/domain_brain_ingest.py",
            "module": "integrations.domain_brain_ingest",
            "requires_config": True,
            "optional_dependency": True,
            "description": "Domain data ingestion (requires openpyxl)",
        },
        "download_gdrive_file": {
            "path": "integrations/download_gdrive_file.py",
            "module": "integrations.download_gdrive_file",
            "functions": ["download_file"],
            "requires_config": True,
            "env_keys": ["GOOGLE_TOKEN_PATH"],
            "optional_connectivity": True,
            "description": "Google Drive file download",
        },
        "gdocs_analyzer": {
            "path": "integrations/gdocs_analyzer.py",
            "module": "integrations.gdocs_analyzer",
            "functions": ["analyze_document_with_llm", "run_analysis", "main"],
            "requires_config": True,
            "env_keys": ["GOOGLE_TOKEN_PATH"],
            "optional_connectivity": True,
            "description": "Google Docs analysis",
        },
        "gdocs_processor": {
            "path": "integrations/gdocs_processor.py",
            "module": "integrations.gdocs_processor",
            "functions": ["run_processor", "filter_document", "main"],
            "requires_config": True,
            "env_keys": ["GOOGLE_TOKEN_PATH"],
            "optional_connectivity": True,
            "description": "Google Docs processing",
        },
        "github_brain_sync": {
            "path": "integrations/github_brain_sync.py",
            "module": "integrations.github_brain_sync",
            "functions": ["main"],
            "requires_config": True,
            "env_keys": ["GITHUB_HF_PM_OS"],  # PM-OS uses GITHUB_HF_PM_OS
            "optional_connectivity": True,
            "description": "GitHub brain sync",
        },
        "github_commit_extractor": {
            "path": "integrations/github_commit_extractor.py",
            "module": "integrations.github_commit_extractor",
            "requires_config": True,
            "env_keys": ["GITHUB_HF_PM_OS"],  # PM-OS uses GITHUB_HF_PM_OS
            "optional_connectivity": True,
            "description": "GitHub commit extraction",
        },
        "jira_brain_sync": {
            "path": "integrations/jira_brain_sync.py",
            "module": "integrations.jira_brain_sync",
            "functions": ["main"],
            "requires_config": True,
            "env_keys": ["JIRA_API_TOKEN"],
            "optional_connectivity": True,
            "description": "Jira brain sync (fetches updates and writes to Brain)",
        },
        "jira_bulk_extractor": {
            "path": "integrations/jira_bulk_extractor.py",
            "module": "integrations.jira_bulk_extractor",
            "functions": ["main"],
            "requires_config": True,
            "env_keys": ["JIRA_API_TOKEN"],
            "optional_connectivity": True,
            "description": "Jira bulk data extraction",
        },
        "statsig_brain_sync": {
            "path": "integrations/statsig_brain_sync.py",
            "module": "integrations.statsig_brain_sync",
            "classes": ["StatsigSync"],
            "functions": ["main"],
            "requires_config": True,
            "env_keys": ["STATSIG_API_KEY"],
            "optional_connectivity": True,
            "description": "Statsig (feature flags) sync",
        },
        "strategy_indexer": {
            "path": "integrations/strategy_indexer.py",
            "module": "integrations.strategy_indexer",
            "requires_config": True,
            "description": "Strategy indexing",
        },
        "tech_context_sync": {
            "path": "integrations/tech_context_sync.py",
            "module": "integrations.tech_context_sync",
            "requires_config": True,
            "description": "Tech context synchronization",
        },
        "prd_to_spec": {
            "path": "integrations/prd_to_spec.py",
            "module": "integrations.prd_to_spec",
            "classes": [
                "PRDParser",
                "QAGenerator",
                "TechStackInjector",
                "SpecFolderCreator",
                "PRDToSpecBridge",
            ],
            "functions": ["main", "get_available_repos", "interactive_repo_select"],
            "requires_config": True,
            "description": "PRD to Spec-Machine bridge (transforms PM-OS PRD to spec-machine input format)",
        },
        "integrations___init__": {
            "path": "integrations/__init__.py",
            "module": "integrations",
            "skip_import": True,
            "description": "Integrations package initialization",
        },
    },
    # ==========================================================================
    # MCP SERVERS (3 tools)
    # ==========================================================================
    "mcp": {
        "gdrive_mcp_server": {
            "path": "mcp/gdrive_mcp/server.py",
            "module": "mcp.gdrive_mcp.server",
            "requires_config": True,
            "env_keys": ["GOOGLE_TOKEN_PATH"],
            "optional_dependency": True,
            "description": "Google Drive MCP server (requires mcp.server)",
        },
        "jira_mcp_server": {
            "path": "mcp/jira_mcp/server.py",
            "module": "mcp.jira_mcp.server",
            "requires_config": True,
            "env_keys": ["JIRA_API_TOKEN"],
            "optional_dependency": True,
            "description": "Jira MCP server (requires mcp.server)",
        },
        "mcp___init__": {
            "path": "mcp/__init__.py",
            "module": "mcp",
            "skip_import": True,
            "description": "MCP package initialization",
        },
    },
    # ==========================================================================
    # MEETING (3 tools)
    # ==========================================================================
    "meeting": {
        "meeting_prep": {
            "path": "meeting/meeting_prep.py",
            "module": "meeting.meeting_prep",
            "functions": ["main"],
            "requires_config": True,
            "description": "Meeting preparation",
        },
        "meeting___init__": {
            "path": "meeting/__init__.py",
            "module": "meeting",
            "skip_import": True,
            "description": "Meeting package initialization",
        },
        "meeting_prep___init__": {
            "path": "meeting_prep/__init__.py",
            "module": "meeting_prep",
            "skip_import": True,
            "description": "Meeting prep package initialization",
        },
    },
    # ==========================================================================
    # MIGRATION (6 tools)
    # ==========================================================================
    "migration": {
        "migrate": {
            "path": "migration/migrate.py",
            "module": "migration.migrate",
            "classes": ["MigrationResult", "MigrationEngine"],
            "functions": ["run_migration"],
            "requires_config": False,
            "description": "Main migration orchestrator (maps v2.4 to v3.0 structure)",
        },
        "preflight": {
            "path": "migration/preflight.py",
            "module": "migration.preflight",
            "classes": ["PreflightCheck", "PreflightResult", "PreflightChecker"],
            "functions": ["run_preflight"],
            "requires_config": False,
            "description": "Pre-migration validation (git status, disk space, permissions)",
        },
        "revert": {
            "path": "migration/revert.py",
            "module": "migration.revert",
            "functions": ["revert_migration"],
            "requires_config": False,
            "description": "Migration rollback",
        },
        "snapshot": {
            "path": "migration/snapshot.py",
            "module": "migration.snapshot",
            "functions": ["create_snapshot"],
            "requires_config": False,
            "description": "Pre-migration snapshot",
        },
        "validate": {
            "path": "migration/validate.py",
            "module": "migration.validate",
            "classes": ["MigrationValidator", "ValidationResult"],
            "functions": ["validate_migration"],
            "requires_config": False,
            "description": "Post-migration validation",
        },
        "migration___init__": {
            "path": "migration/__init__.py",
            "module": "migration",
            "skip_import": True,
            "description": "Migration package initialization",
        },
    },
    # ==========================================================================
    # QUINT/FPF (5 tools)
    # ==========================================================================
    "quint": {
        "evidence_decay_monitor": {
            "path": "quint/evidence_decay_monitor.py",
            "module": "quint.evidence_decay_monitor",
            "classes": ["EvidenceItem"],
            "functions": ["get_all_evidence", "generate_report", "main"],
            "requires_config": True,
            "description": "Monitors evidence freshness",
        },
        "gemini_quint_bridge": {
            "path": "quint/gemini_quint_bridge.py",
            "module": "quint.gemini_quint_bridge",
            "functions": ["init_session", "hypothesize", "verify", "main"],
            "requires_config": True,
            "env_keys": ["GEMINI_API_KEY"],
            "description": "Gemini integration for Quint",
        },
        "orthogonal_challenge": {
            "path": "quint/orthogonal_challenge.py",
            "module": "quint.orthogonal_challenge",
            "requires_config": True,
            "optional_dependency": True,
            "description": "Orthogonal challenge generation (requires model_bridge)",
        },
        "quint_brain_sync": {
            "path": "quint/quint_brain_sync.py",
            "module": "quint.quint_brain_sync",
            "functions": ["sync_quint_to_brain", "sync_brain_to_quint", "main"],
            "requires_config": True,
            "description": "Syncs .quint/ and Brain/Reasoning/ bidirectionally",
        },
        "quint___init__": {
            "path": "quint/__init__.py",
            "module": "quint",
            "skip_import": True,
            "description": "Quint package initialization",
        },
    },
    # ==========================================================================
    # RALPH (2 tools)
    # ==========================================================================
    "ralph": {
        "ralph_manager": {
            "path": "ralph/ralph_manager.py",
            "module": "ralph.ralph_manager",
            "classes": ["RalphManager"],
            "requires_config": False,
            "description": "Ralph specification management",
        },
        "ralph___init__": {
            "path": "ralph/__init__.py",
            "module": "ralph",
            "skip_import": True,
            "description": "Ralph package initialization",
        },
    },
    # ==========================================================================
    # BEADS (4 tools)
    # ==========================================================================
    "beads": {
        "beads_confucius_hook": {
            "path": "beads/beads_confucius_hook.py",
            "module": "beads.beads_confucius_hook",
            "classes": ["BeadsConfuciusHook"],
            "functions": ["get_beads_confucius_hook"],
            "requires_config": False,
            "description": "Beads-Confucius integration hooks",
        },
        "beads_fpf_hook": {
            "path": "beads/beads_fpf_hook.py",
            "module": "beads.beads_fpf_hook",
            "classes": ["BeadsFPFHook"],
            "functions": [
                "get_beads_fpf_hook",
                "trigger_fpf_for_epic",
                "link_drr_to_issue",
            ],
            "requires_config": False,
            "description": "Beads-FPF integration hooks",
        },
        "beads_ralph_integration": {
            "path": "beads/beads_ralph_integration.py",
            "module": "beads.beads_ralph_integration",
            "classes": ["BeadsRalphBridge"],
            "functions": ["get_beads_ralph_bridge"],
            "requires_config": False,
            "description": "Beads-Ralph synchronization bridge",
        },
        "beads___init__": {
            "path": "beads/__init__.py",
            "module": "beads",
            "skip_import": True,
            "description": "Beads package initialization",
        },
    },
    # ==========================================================================
    # REPO (5 tools)
    # ==========================================================================
    "repo": {
        "create_missing_squads": {
            "path": "repo/create_missing_squads.py",
            "module": "repo.create_missing_squads",
            "requires_config": True,
            "description": "Squad creation utility",
        },
        "indexer": {
            "path": "repo/indexer.py",
            "module": "repo.indexer",
            "functions": ["map_structure", "map_ownership"],
            "requires_config": True,
            "description": "Repository indexing",
        },
        "search_tree": {
            "path": "repo/search_tree.py",
            "module": "repo.search_tree",
            "requires_config": True,
            "description": "Search tree generation",
        },
        "update_brain_ownership": {
            "path": "repo/update_brain_ownership.py",
            "module": "repo.update_brain_ownership",
            "requires_config": True,
            "description": "Brain ownership updates",
        },
        "repo___init__": {
            "path": "repo/__init__.py",
            "module": "repo",
            "skip_import": True,
            "description": "Repo package initialization",
        },
    },
    # ==========================================================================
    # REPORTING (3 tools)
    # ==========================================================================
    "reporting": {
        "sprint_report_generator": {
            "path": "reporting/sprint_report_generator.py",
            "module": "reporting.sprint_report_generator",
            "functions": ["main"],
            "requires_config": True,
            "env_keys": ["JIRA_API_TOKEN", "GEMINI_API_KEY"],
            "description": "Bi-weekly sprint reports (fetches Jira, summarizes with Gemini)",
        },
        "tribe_quarterly_update": {
            "path": "reporting/tribe_quarterly_update.py",
            "module": "reporting.tribe_quarterly_update",
            "functions": ["main"],
            "requires_config": True,
            "description": "Tribe quarterly updates",
        },
        "reporting___init__": {
            "path": "reporting/__init__.py",
            "module": "reporting",
            "skip_import": True,
            "description": "Reporting package initialization",
        },
    },
    # ==========================================================================
    # SESSION (3 tools)
    # ==========================================================================
    "session": {
        "confucius_agent": {
            "path": "session/confucius_agent.py",
            "module": "session.confucius_agent",
            "functions": ["main"],
            "requires_config": True,
            "description": "Confucius note-taking agent",
        },
        "session_manager": {
            "path": "session/session_manager.py",
            "module": "session.session_manager",
            "classes": ["SessionManager"],
            "requires_config": True,
            "description": "Session persistence and context management",
        },
        "session___init__": {
            "path": "session/__init__.py",
            "module": "session",
            "skip_import": True,
            "description": "Session package initialization",
        },
    },
    # ==========================================================================
    # SLACK (14 tools)
    # ==========================================================================
    "slack": {
        "slack_analyzer": {
            "path": "slack/slack_analyzer.py",
            "module": "slack.slack_analyzer",
            "functions": ["main"],
            "requires_config": True,
            "env_keys": ["SLACK_BOT_TOKEN"],
            "description": "Analyzes Slack messages",
        },
        "slack_brain_writer": {
            "path": "slack/slack_brain_writer.py",
            "module": "slack.slack_brain_writer",
            "functions": ["run_brain_writer", "process_analysis_file", "main"],
            "requires_config": True,
            "description": "Writes analyzed data to Brain",
        },
        "slack_bulk_extractor": {
            "path": "slack/slack_bulk_extractor.py",
            "module": "slack.slack_bulk_extractor",
            "functions": ["main"],
            "requires_config": True,
            "env_keys": ["SLACK_BOT_TOKEN"],
            "optional_connectivity": True,
            "description": "Bulk data extraction",
        },
        "slack_context_poster": {
            "path": "slack/slack_context_poster.py",
            "module": "slack.slack_context_poster",
            "requires_config": True,
            "env_keys": ["SLACK_BOT_TOKEN"],
            "optional_connectivity": True,
            "description": "Posts context to Slack",
        },
        "slack_extractor": {
            "path": "slack/slack_extractor.py",
            "module": "slack.slack_extractor",
            "functions": ["extract_messages", "list_bot_channels", "get_client"],
            "requires_config": True,
            "env_keys": ["SLACK_BOT_TOKEN"],
            "optional_connectivity": True,
            "description": "Message extraction",
        },
        "slack_mention_classifier": {
            "path": "slack/slack_mention_classifier.py",
            "module": "slack.slack_mention_classifier",
            "classes": ["MentionType", "ClassificationResult"],
            "requires_config": True,
            "description": "Classifies @mentions",
        },
        "slack_mention_handler": {
            "path": "slack/slack_mention_handler.py",
            "module": "slack.slack_mention_handler",
            "classes": ["MentionTask"],
            "requires_config": True,
            "env_keys": ["SLACK_BOT_TOKEN"],
            "description": "Handles @mentions",
        },
        "slack_mention_llm_processor": {
            "path": "slack/slack_mention_llm_processor.py",
            "module": "slack.slack_mention_llm_processor",
            "requires_config": True,
            "description": "LLM-based mention processing",
        },
        "slack_minimal_cache": {
            "path": "slack/slack_minimal_cache.py",
            "module": "slack.slack_minimal_cache",
            "functions": ["save_cache", "main"],
            "requires_config": False,
            "description": "Lightweight caching",
        },
        "slack_mrkdwn_parser": {
            "path": "slack/slack_mrkdwn_parser.py",
            "module": "slack.slack_mrkdwn_parser",
            "classes": ["MrkdwnParser"],
            "functions": ["parse_slack_text"],
            "requires_config": False,
            "description": "Markdown parsing",
        },
        "slack_processor": {
            "path": "slack/slack_processor.py",
            "module": "slack.slack_processor",
            "functions": ["main"],
            "requires_config": True,
            "env_keys": ["SLACK_BOT_TOKEN"],
            "optional_connectivity": True,
            "description": "Central processor",
        },
        "slack_test": {
            "path": "slack/slack_test.py",
            "module": "slack.slack_test",
            "requires_config": True,
            "env_keys": ["SLACK_BOT_TOKEN"],
            "optional_connectivity": True,
            "description": "Connection testing utility",
        },
        "slack_user_cache": {
            "path": "slack/slack_user_cache.py",
            "module": "slack.slack_user_cache",
            "functions": ["fetch_all_users", "load_user_cache", "resolve_user"],
            "requires_config": True,
            "env_keys": ["SLACK_BOT_TOKEN"],
            "description": "User caching",
        },
        "slack___init__": {
            "path": "slack/__init__.py",
            "module": "slack",
            "skip_import": True,
            "description": "Slack package initialization",
        },
    },
    # ==========================================================================
    # UTIL (5 tools)
    # ==========================================================================
    "util": {
        "batch_llm_analyzer": {
            "path": "util/batch_llm_analyzer.py",
            "module": "util.batch_llm_analyzer",
            "functions": ["main"],
            "requires_config": True,
            "description": "Batch LLM analysis",
        },
        "file_chunker": {
            "path": "util/file_chunker.py",
            "module": "util.file_chunker",
            "classes": ["FileInfo", "Chunk", "ChunkingResult"],
            "functions": ["analyze_file", "split_file", "main"],
            "requires_config": False,
            "description": "File chunking utility",
        },
        "model_bridge": {
            "path": "util/model_bridge.py",
            "module": "util.model_bridge",
            "functions": [
                "detect_active_model",
                "invoke_model",
                "invoke_challenger",
                "main",
            ],
            "requires_config": True,
            "description": "LLM model bridging",
        },
        "validate_cross_cli_sync": {
            "path": "util/validate_cross_cli_sync.py",
            "module": "util.validate_cross_cli_sync",
            "functions": ["main"],
            "requires_config": True,
            "description": "Cross-CLI validation",
        },
        "util___init__": {
            "path": "util/__init__.py",
            "module": "util",
            "skip_import": True,
            "description": "Util package initialization",
        },
    },
    # ==========================================================================
    # TESTS (1 tool - existing tests directory)
    # ==========================================================================
    "tests": {
        "tests___init__": {
            "path": "tests/__init__.py",
            "module": "tests",
            "skip_import": True,
            "description": "Tests package initialization",
        },
    },
    # ==========================================================================
    # SCHEMAS (Brain 1.2 Pydantic schemas)
    # ==========================================================================
    "schemas": {
        "brain_schemas": {
            "path": "../schemas/brain/__init__.py",
            "module": "schemas.brain",
            "classes": [
                "EntityBase",
                "EntityType",
                "EntityStatus",
                "Relationship",
                "RelationshipType",
                "ChangeEvent",
                "EventType",
                "FieldChange",
                "PersonEntity",
                "ProjectEntity",
                "TeamEntity",
                "SquadEntity",
                "RegistryEntry",
                "RegistryV2",
            ],
            "requires_config": False,
            "description": "Brain 1.2 entity schemas with temporal tracking",
        },
        "schemas___init__": {
            "path": "../schemas/__init__.py",
            "module": "schemas",
            "skip_import": True,
            "description": "Schemas package initialization",
        },
    },
}

# Category display order
CATEGORY_ORDER = [
    "core",
    "brain",
    "schemas",
    "daily_context",
    "documents",
    "integrations",
    "slack",
    "session",
    "quint",
    "reporting",
    "migration",
    "ralph",
    "beads",
    "repo",
    "mcp",
    "meeting",
    "deep_research",
    "documentation",
    "util",
    "tests",
]


def get_tools_by_category(category: str) -> Dict[str, Any]:
    """Get all tools in a category."""
    return TOOL_REGISTRY.get(category, {})


def get_all_tools() -> Dict[str, Dict[str, Any]]:
    """Get all tools organized by category."""
    return TOOL_REGISTRY


def get_tool_count() -> int:
    """Get total count of tools (excluding __init__ files)."""
    count = 0
    for category, tools in TOOL_REGISTRY.items():
        for tool_name in tools:
            if not tool_name.endswith("___init__"):
                count += 1
    return count


def get_categories() -> List[str]:
    """Get list of categories in display order."""
    return [c for c in CATEGORY_ORDER if c in TOOL_REGISTRY]


def get_tool(category: str, tool_name: str) -> Optional[Dict[str, Any]]:
    """Get a specific tool's metadata."""
    return TOOL_REGISTRY.get(category, {}).get(tool_name)
