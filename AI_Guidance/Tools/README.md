# PM-OS Tools Reference

Python tools for context ingestion, analysis, and Brain management.

## Directory Structure

```
Tools/
├── common/                 # Shared utilities
│   ├── __init__.py
│   └── config_loader.py    # Environment/config loading
├── daily_context/          # Google Workspace integration
│   ├── daily_context_updater.py
│   ├── state.json.example
│   └── README.md
├── gdrive_mcp/             # Google Drive MCP server
│   ├── server.py
│   └── setup.ps1
├── jira_mcp/               # Jira MCP server
│   ├── server.py
│   └── config_template.json
├── meeting_prep/           # Meeting preparation
│   ├── meeting_prep.py
│   └── config.json.example
├── deep_research/          # Deep research PRD generation
│   ├── prd_generator.py
│   └── file_store_manager.py
├── repo_indexer/           # Code repository indexing
│   └── indexer.py
└── *.py                    # Standalone tools
```

## Core Tools

### Context Ingestion

| Tool | Purpose | Command |
|------|---------|---------|
| `daily_context_updater.py` | Pull GDocs, Gmail | `python3 daily_context/daily_context_updater.py` |
| `jira_brain_sync.py` | Sync Jira to Brain | `python3 jira_brain_sync.py` |
| `github_brain_sync.py` | Sync GitHub to Brain | `python3 github_brain_sync.py` |
| `slack_bulk_extractor.py` | Extract Slack history | `python3 slack_bulk_extractor.py` |
| `statsig_brain_sync.py` | Sync experiments | `python3 statsig_brain_sync.py` |

### Analysis

| Tool | Purpose | Command |
|------|---------|---------|
| `batch_llm_analyzer.py` | LLM entity extraction | `python3 batch_llm_analyzer.py` |
| `file_chunker.py` | Split large files | `python3 file_chunker.py --split <file>` |
| `unified_brain_writer.py` | Write to Brain | `python3 unified_brain_writer.py` |
| `slack_processor.py` | Process Slack data | `python3 slack_processor.py` |
| `gdocs_processor.py` | Process GDocs data | `python3 gdocs_processor.py` |

### Brain Management

| Tool | Purpose | Command |
|------|---------|---------|
| `brain_loader.py` | Load hot topics | `python3 brain_loader.py` |
| `brain_updater.py` | Update entities | `python3 brain_updater.py` |
| `synapse_builder.py` | Build relationships | `python3 synapse_builder.py` |

### FPF Reasoning

| Tool | Purpose | Command |
|------|---------|---------|
| `quint_brain_sync.py` | Sync FPF state | `python3 quint_brain_sync.py` |
| `evidence_decay_monitor.py` | Check evidence freshness | `python3 evidence_decay_monitor.py` |
| `gemini_quint_bridge.py` | Gemini FPF integration | `python3 gemini_quint_bridge.py` |

### Output Generation

| Tool | Purpose | Command |
|------|---------|---------|
| `sprint_report_generator.py` | Generate reports | `python3 sprint_report_generator.py` |
| `meeting_prep.py` | Meeting pre-reads | `python3 meeting_prep/meeting_prep.py` |
| `deep_research/prd_generator.py` | Generate PRDs | `python3 deep_research/prd_generator.py` |

## Common Options

Most tools support these flags:

| Flag | Purpose |
|------|---------|
| `--dry-run` | Preview without changes |
| `--verbose` | Detailed output |
| `--test` | Test connection only |
| `--days N` | Lookback period |
| `--summarize` | Include LLM summary |

## Configuration

### Environment Variables

Tools read from `.env` file. Key variables:

```bash
# Jira
JIRA_SERVER=https://company.atlassian.net
JIRA_EMAIL=email@company.com
JIRA_API_TOKEN=token

# GitHub
GITHUB_TOKEN=ghp_token
GITHUB_REPOS=org/repo1,org/repo2

# Slack
SLACK_BOT_TOKEN=xoxb-token
SLACK_CHANNELS=channel1,channel2

# AWS (for LLM analysis)
AWS_PROFILE=bedrock
```

### Config Files

Some tools use JSON config:
- `jira_mcp/config.json` - Jira squad mapping
- `meeting_prep/config.json` - Calendar settings
- `daily_context/state.json` - Sync state

Copy `.example` files and customize.

## Usage Examples

### Full Context Pipeline

```bash
# Pull all sources
python3 daily_context/daily_context_updater.py
python3 jira_brain_sync.py
python3 github_brain_sync.py

# Analyze
python3 batch_llm_analyzer.py --source all

# Write to Brain
python3 unified_brain_writer.py

# Build relationships
python3 synapse_builder.py
```

### Quick Jira Sync

```bash
python3 jira_brain_sync.py --squad "My Squad" --days 7
```

### Bulk Slack Import

```bash
python3 slack_bulk_extractor.py --tier all --days 90
```

### Check Evidence Freshness

```bash
python3 evidence_decay_monitor.py --threshold 30
```

## MCP Servers

PM-OS includes Model Context Protocol servers:

### Google Drive MCP

```bash
# Setup
pwsh AI_Guidance/Tools/gdrive_mcp/setup.ps1

# Run server
python3 AI_Guidance/Tools/gdrive_mcp/server.py
```

### Jira MCP

```bash
# Setup
cp AI_Guidance/Tools/jira_mcp/config_template.json AI_Guidance/Tools/jira_mcp/config.json
# Edit config.json with your settings

# Run server
python3 AI_Guidance/Tools/jira_mcp/server.py
```

## Troubleshooting

### "Module not found"

```bash
pip3 install -r requirements.txt
```

### "Authentication failed"

Check credentials in `.env` file.

### "Rate limited"

Reduce scope or add delays:
```bash
python3 slack_bulk_extractor.py --tier tier1 --delay 2
```

### "File too large"

Chunk before processing:
```bash
python3 file_chunker.py --split large_file.md
```

## Adding New Tools

1. Create Python file in `Tools/`
2. Use `common/config_loader.py` for config
3. Follow existing patterns for CLI args
4. Add to this README
5. Create command in `.claude/commands/` if user-facing
