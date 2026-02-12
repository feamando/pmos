# PM-OS Tools Reference

> Python tools powering PM-OS functionality

## Overview

PM-OS includes 88+ Python tools organized by function. These tools are called by slash commands and can also be used directly via CLI.

## Tool Categories

| Category | Tools | Purpose |
|----------|-------|---------|
| [Brain Tools](brain-tools.md) | 4 | Brain loading, updating, writing, enrichment |
| [Integration Tools](integration-tools.md) | 15 | Jira, GitHub, Slack, Confluence, Google |
| [Meeting Tools](meeting-tools.md) | 5 | Meeting preparation, series intelligence |
| [Session Tools](session-tools.md) | 3 | Sessions and agent management |
| [Utility Tools](utility-tools.md) | 10 | Config, paths, validation, helpers |
| [Preflight](preflight.md) | 1 | System verification checks |

## Directory Structure

```
common/tools/
├── brain/              # Brain management
│   ├── brain_loader.py
│   ├── brain_updater.py
│   └── unified_brain_writer.py
├── integrations/       # External service sync
│   ├── jira_brain_sync.py
│   ├── github_brain_sync.py
│   ├── confluence_brain_sync.py
│   ├── statsig_brain_sync.py
│   ├── gdocs_*.py
│   └── ...
├── slack/              # Slack integration
│   ├── slack_context_poster.py
│   ├── slack_mention_handler.py
│   ├── slack_processor.py
│   └── ...
├── session/            # Session management
│   ├── session_manager.py
│   └── confucius_agent.py
├── daily_context/      # Context updater
│   └── daily_context_updater.py
├── meeting/            # Meeting prep
│   └── meeting_prep.py
├── quint/              # FPF reasoning
│   ├── orthogonal_challenge.py
│   ├── gemini_quint_bridge.py
│   └── quint_brain_sync.py
├── ralph/              # Ralph agent
│   └── ralph_manager.py
├── documents/          # Document generation
│   ├── synapse_builder.py
│   └── template_manager.py
├── reporting/          # Reports
│   ├── sprint_report_generator.py
│   └── tribe_quarterly_update.py
├── deep_research/      # Deep Research
│   ├── prd_generator.py
│   └── file_store_manager.py
├── migration/          # v2.4 → v3.0 migration
│   ├── migrate.py
│   └── revert.py
├── util/               # Utilities
│   ├── file_chunker.py
│   └── batch_llm_analyzer.py
├── config_loader.py    # Configuration
├── path_resolver.py    # Path resolution
└── entity_validator.py # Schema validation
```

## Common Patterns

### Using Tools from CLI

```bash
cd $PM_OS_COMMON/tools
python3 tool_name.py [options]
```

### Using Tools from Python

```python
import sys
sys.path.insert(0, '/path/to/pm-os/common/tools')

from config_loader import get_jira_config
from brain.brain_loader import load_entity
```

### Tool Dependencies

All tools depend on:
- `config_loader.py` - Configuration access
- `path_resolver.py` - Path resolution

### Environment Requirements

Tools expect these environment variables (set by `/boot`):
- `PM_OS_ROOT`
- `PM_OS_COMMON`
- `PM_OS_USER`

## Tool Reference by Category

### Brain Tools

| Tool | Purpose |
|------|---------|
| `brain_loader.py` | Load Brain entities |
| `brain_updater.py` | Update Brain entities |
| `unified_brain_writer.py` | Write Brain files |
| `brain_enrich.py` | Brain quality improvement |

### Integration Tools

| Tool | Purpose |
|------|---------|
| `jira_brain_sync.py` | Sync Jira to Brain |
| `github_brain_sync.py` | Sync GitHub to Brain |
| `confluence_brain_sync.py` | Sync Confluence to Brain |
| `statsig_brain_sync.py` | Sync Statsig to Brain |
| `gdocs_processor.py` | Process Google Docs |
| `slack_processor.py` | Process Slack messages |
| `slack_context_poster.py` | Post context to Slack |

### Session Tools

| Tool | Purpose |
|------|---------|
| `session_manager.py` | Manage sessions |
| `confucius_agent.py` | Confucius agent |
| `meeting_prep.py` | Meeting preparation |

### Utility Tools

| Tool | Purpose |
|------|---------|
| `config_loader.py` | Load configuration |
| `path_resolver.py` | Resolve paths |
| `entity_validator.py` | Validate entities |
| `file_chunker.py` | Chunk large files |
| `daily_context_updater.py` | Update daily context |

---

## Related Documentation

- [Architecture](../02-architecture.md) - Tool architecture
- [Commands](../commands/) - Commands using these tools
- [Installation](../03-installation.md) - Tool setup

---

*Last updated: 2026-02-02*
