# PM-OS v5.0

**AI-native Product Management Operating System for Claude Code**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

PM-OS is a modular plugin system that turns [Claude Code](https://docs.anthropic.com/en/docs/claude-code) into a full product management workstation. It syncs context from Google Workspace, Jira, Slack, GitHub, and Confluence into a unified daily briefing, maintains a knowledge graph, generates structured documents, and orchestrates daily PM workflows through slash commands and skills.

> v5.0 is a plugin architecture aligned with the [Anthropic Claude Code plugin standard](https://docs.anthropic.com/en/docs/claude-code/plugins).

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/feamando/pmos.git
cd pm-os

# Set up user directory
mkdir -p user
cp templates/USER.md.template user/USER.md

# Create config and secrets
cp templates/config.yaml.example user/config.yaml   # edit with your profile
cp templates/.env.example user/.env                  # add API tokens

# Boot
# In Claude Code, run:
/session boot
```

This loads your agent context, syncs daily data, enriches the Brain knowledge graph, generates meeting pre-reads, and posts a summary to Slack.

---

## Plugin Architecture

PM-OS v5.0 is organized into 6 self-contained plugins. Each plugin provides commands, skills, and Python tools:

| Plugin | Description | Key Capabilities |
|--------|-------------|-----------------|
| **pm-os-base** | Foundation | Config management, pipeline engine, session lifecycle, plugin orchestration |
| **pm-os-brain** | Knowledge graph | Entity management, relationship mapping, enrichment pipeline, MCP search |
| **pm-os-daily-workflow** | Daily cycle | Context synthesis, meeting prep, Slack integration, external sync |
| **pm-os-cce** | Context Creation Engine | Document generation, feature lifecycle, FPF reasoning, roadmap management |
| **pm-os-reporting** | Reporting | Sprint reports, metric interpretation, status updates |
| **pm-os-career** | Career & team | Career frameworks, 1:1 prep, interview scoring, team operations |

All plugins depend on **pm-os-base** as the foundation layer.

### Plugin Structure

Each plugin follows a standard layout:

```
plugins/pm-os-{name}/
  .claude-plugin/plugin.json   # Plugin manifest (name, version, author)
  commands/                    # Slash commands (markdown)
  skills/                      # Background skills (YAML + markdown)
  tools/                       # Python tool implementations
  pipelines/                   # YAML pipeline definitions
  .mcp.json                    # MCP server config (where applicable)
```

---

## Core Commands

| Command | Description |
|---------|-------------|
| `/session boot` | Initialize session, load context, sync integrations |
| `/session logout` | End session, archive notes, sync state |
| `/brain search "query"` | Search the knowledge graph |
| `/sync all` | Update context from all integrations |
| `/doc prd` | Generate a Product Requirements Document |
| `/doc adr` | Generate an Architecture Decision Record |
| `/feature start "name"` | Start a new feature workflow |
| `/report sprint` | Generate sprint report from Jira data |
| `/team one-on-one "Name"` | Prepare for a 1:1 meeting |
| `/team career-plan -create "Name"` | Initialize a career plan |

---

## Integrations

PM-OS connects to external tools via environment variables configured in `user/.env`:

| Integration | Token | Purpose |
|-------------|-------|---------|
| Jira | `JIRA_API_TOKEN` | Sprint data, ticket sync, enrichment |
| Slack | `SLACK_BOT_TOKEN` | Channel sync, daily summaries, notifications |
| GitHub | `GITHUB_TOKEN` | PR tracking, repo sync, enrichment |
| Google | OAuth via `GOOGLE_TOKEN_PATH` | Calendar, Docs, Sheets, Drive |
| Confluence | `JIRA_API_TOKEN` (shared) | Page sync, documentation |
| Gemini | `GEMINI_API_KEY` | Meeting transcription, document analysis |

All integrations are optional. PM-OS degrades gracefully when tokens are not configured.

---

## Directory Layout

```
pm-os/
  plugins/                 # Plugin source (commands, skills, tools)
    .claude-plugin/        # Marketplace metadata
    pm-os-base/            # Foundation plugin
    pm-os-brain/           # Knowledge graph plugin
    pm-os-daily-workflow/  # Daily cycle plugin
    pm-os-cce/             # Context Creation Engine plugin
    pm-os-reporting/       # Reporting plugin
    pm-os-career/          # Career & team plugin
  migration/               # v4.x to v5.0 migration tools
  templates/               # User onboarding templates
  LICENSE                  # MIT License
```

The `user/` directory (created during setup) contains your personal data:

```
user/
  config.yaml              # Your configuration
  .env                     # API tokens (gitignored)
  USER.md                  # AI persona and style guide
  brain/                   # Knowledge graph entities
  personal/context/        # Daily context files
  products/                # Product documentation
  team/                    # Team data, 1:1s, career plans
```

---

## Migration from v4.x

If you have an existing PM-OS v4.x installation:

```bash
python3 migration/migrate_to_v5.py --dry-run   # Preview changes
python3 migration/migrate_to_v5.py              # Run migration
```

The migration script preserves all user data and converts v4.x commands to v5.0 plugin format.

---

## Requirements

- Python 3.10+
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI or IDE extension
- (Optional) API tokens for Jira, Slack, GitHub, Google, Confluence

---

## License

MIT License. See [LICENSE](LICENSE) for details.
