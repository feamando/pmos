```
                     ____  __  __           ___  ____
                    |  _ \|  \/  |         / _ \/ ___|
                    | |_) | |\/| |  ___   | | | \___ \
                    |  __/| |  | | |___|  | |_| |___) |
                    |_|   |_|  |_|         \___/|____/

          ┌─────────────────────────────────────────────────┐
          │  Product Management Operating System    v3.4    │
          │  ─────────────────────────────────────────────  │
          │  Brain · Context · Slash Commands · AI-native   │
          └─────────────────────────────────────────────────┘
```

**Version 3.4** | AI-powered operating system for product managers

[![PyPI](https://img.shields.io/pypi/v/pm-os)](https://pypi.org/project/pm-os/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

PM-OS is an AI-native productivity system for product managers. It syncs context from Google Workspace, Jira, Slack, GitHub, and Confluence into a unified daily briefing, prepares meeting pre-reads, tracks issues and action items, maintains a knowledge graph (Brain), and generates structured documents — all orchestrated through slash commands in Claude Code or Gemini CLI.

> **Full documentation:** [PM-OS Confluence Space](https://your-company.atlassian.net/wiki/spaces/PMOS/)

---

## Installation

### Option A: pip install (Recommended)

```bash
# Install PM-OS (includes all integrations)
pip install pm-os

# Quick setup — auto-detects git config, gets you running fast
pm-os init --quick

# Verify installation
pm-os doctor
```

Configure integrations:

```bash
# Configure integrations via wizard
pm-os setup integrations jira
pm-os setup integrations slack
pm-os brain sync
```

CLI help:

```bash
pm-os help                  # List help topics
pm-os help brain            # Brain documentation
pm-os help integrations     # Integration setup guide
pm-os help quick-start      # Getting started guide
```

### Option B: Manual Setup

```bash
mkdir pm-os && cd pm-os
git clone https://github.com/feamando/pmos.git common
mkdir user
cp common/config.yaml.example user/config.yaml
cp common/.env.example user/.env
```

Edit `user/config.yaml` (profile, integration settings) and `user/.env` (API tokens, OAuth credentials).

### Boot

In Claude Code or Gemini CLI:

```
/boot
```

This loads your agent context, syncs daily data, enriches the Brain, generates meeting pre-reads, and posts a summary to Slack.

---

## Core Capabilities

### Daily Context Engine

The context engine aggregates information from all connected sources into a synthesized daily briefing:

- **Google Workspace** — Recent Docs, emails, calendar events
- **Slack** — Channel messages, @mention task tracking, stale task detection
- **Master Sheet** — Priority items, deadlines, suggested daily plan
- **LLM Synthesis** — Raw data is synthesized via AWS Bedrock (Claude Haiku 4.5) or Gemini into structured context with critical alerts, blockers, action items, and metrics

Commands: `/boot`, `/update-context`, `/create-context`

### Meeting Prep System

Automated pre-reads for upcoming meetings:

- Fetches past meeting notes from Google Drive
- Pulls participant context from Brain
- Enriches with relevant Jira issues
- Generates personalized pre-reads per meeting type (1:1, interview, planning, review, standup)
- Uploads to Google Drive and links to calendar events
- **Series intelligence** — Learns patterns from recurring meetings
- **Task inference** — Extracts actionable items from meeting content

Synthesis supports multiple backends: AWS Bedrock, Gemini, Claude Code, or template fallback.

Command: `/meeting-prep`

### Brain Knowledge Graph (v1.2)

A time-series entity system that maintains your organizational knowledge:

- **Canonical references** — `entity/{type}/{slug}` normalized format
- **Typed relationships** — Bidirectional with temporal validity
- **Event sourcing** — Full change history, point-in-time queries
- **Quality scoring** — Automated completeness and freshness metrics
- **Enrichment pipeline** — Automatic relationship extraction from GDocs, Jira, GitHub, Slack, sessions
- **Graph health monitoring** — Targets <30% orphan rate

```yaml
---
$schema: "brain://entity/person/v1"
$id: "entity/person/jane-doe"
$type: "person"
$version: 5
$confidence: 0.95
$relationships:
  - type: "reports_to"
    target: "entity/person/john-smith"
    since: "2024-06-01"
  - type: "member_of"
    target: "entity/team/platform"
$aliases: ["jane", "jane.doe", "Jane Doe"]
---
```

Brain tools: `canonical_resolver`, `relationship_normalizer`, `orphan_cleaner`, `reference_validator`, `schema_migrator`, `enrichment_pipeline`, `graph_health`

Commands: `/brain-load`, `/brain-enrich`, `/synapse`, `/q-query`

### Session Management (Confucius)

Lightweight context capture during conversations:

- **5 capture types:** Decisions (D), Assumptions (A), Observations (O), Blockers (B), Tasks (T)
- **Research capture** with categories: competitive, technical, market, internal, discovery
- **Pattern detection** for automatic capture
- **Export for FPF context injection**
- **Session persistence** and searchability

Commands: `/session-save`, `/session-load`, `/session-search`, `/confucius-status`

### Document Generation

Structured documents with First Principles Framework (FPF) reasoning:

| Command | Output |
|---------|--------|
| `/prd` | Product Requirements Document |
| `/rfc` | Request for Comments |
| `/adr` | Architecture Decision Record |
| `/prfaq` | PR/FAQ (Amazon-style) |
| `/bc` | Business Case |
| `/whitepaper` | Strategic Proposal |
| `/export-to-spec` | Implementation spec for Spec Machine |

### Beads Issue Tracking

Lightweight issue management integrated with the development workflow:

- **Bidirectional Ralph sync** — Generate PLAN.md from Beads epics with `/ralph-loop bd-XXXX`
- **Checkbox completion** — Ticking items in PLAN.md closes corresponding Beads tasks
- **Task traceability** — AC items include task ID comments
- **FPF hooks** — Reasoning state integration
- **Roadmap integration** — Capture feature requests from Slack mentions

Commands: `/bd-list`, `/bd-create`, `/bd-show`, `/bd-close`, `/bd-update`, `/bd-prime`

### Push Publisher

Multi-target publication system:

- **PR-based publishing** — common framework → feamando/pmos (with Jira ticket in branch name)
- **Direct push** — brain/user → personal repos
- **PyPI publishing** — `pip install pm-os` package with version bumping
- **Slack notifications** — Release notes to configured channels
- **Semantic release notes** — Auto-generated from Ralph completions and file changes
- **Documentation audit** — Coverage tracking and Confluence sync

Command: `/push`

---

## Directory Structure

```
pm-os/
├── common/                  # Shared framework (this repo)
│   ├── .claude/commands/       # 84 Claude slash commands
│   ├── .gemini/commands/       # Gemini commands
│   ├── tools/                  # Python tools
│   │   ├── brain/              # Brain 1.2 knowledge system
│   │   ├── daily_context/      # Context sync engine
│   │   ├── meeting/            # Meeting prep system
│   │   ├── session/            # Confucius session management
│   │   ├── beads/              # Issue tracking
│   │   ├── push/               # Multi-target publisher
│   │   ├── slack/              # Slack integration
│   │   ├── integrations/       # Google, Jira, GitHub, Confluence
│   │   ├── quint/              # FPF reasoning framework
│   │   ├── master_sheet/       # Priority tracking
│   │   └── preflight/          # Health checks
│   ├── package/                # PyPI package source
│   ├── schemas/                # Pydantic entity schemas
│   ├── frameworks/             # Document templates
│   ├── rules/                  # Agent behavior rules
│   ├── documentation/          # Docs synced to Confluence
│   └── scripts/                # Boot scripts
│
├── user/                    # Your data (separate repo)
│   ├── brain/                  # Knowledge base entities
│   ├── personal/context/       # Daily context files
│   ├── sessions/               # Session persistence
│   ├── planning/               # Meeting prep, career planning
│   ├── config.yaml             # Your configuration
│   └── .env                    # Your secrets
│
└── developer/               # Developer tools (optional)
    └── tools/                  # Beads, roadmap management
```

---

## Commands Reference

PM-OS includes 84 slash commands. Key commands:

| Category | Command | Description |
|----------|---------|-------------|
| **Core** | `/boot` | Initialize PM-OS context and sync all data |
| | `/update-context` | Sync daily context from integrations |
| | `/push` | Publish components to repos and PyPI |
| | `/preflight` | Run health checks on tools and integrations |
| **Documents** | `/prd` | Generate PRD with FPF reasoning |
| | `/rfc` | Generate RFC |
| | `/adr` | Generate Architecture Decision Record |
| | `/prfaq` | Generate PR/FAQ |
| | `/export-to-spec` | Export PRD to Spec Machine format |
| **Meeting** | `/meeting-prep` | Prepare pre-reads for upcoming meetings |
| | `/meeting-notes` | Create structured meeting notes |
| **Brain** | `/brain-load` | Load Brain hot topics |
| | `/brain-enrich` | Run enrichment pipeline |
| | `/synapse` | Build bi-directional relationships |
| | `/q-query` | Query knowledge base |
| **Session** | `/session-save` | Save current session |
| | `/session-load` | Restore a previous session |
| | `/session-search` | Search across sessions |
| **Development** | `/ralph-loop` | Run feature development iteration |
| | `/start-feature` | Initialize a new feature |
| | `/check-feature` | Validate feature state |
| **Beads** | `/bd-list` | List issues |
| | `/bd-create` | Create issue |
| | `/bd-show` | Show issue details |
| | `/bd-close` | Close issue |
| **Reasoning** | `/q0-init` | Initialize FPF context |
| | `/q1-hypothesize` | Generate hypotheses |
| | `/q2-verify` | Verify logic |
| | `/q5-decide` | Finalize decision |

---

## Requirements

- Python 3.10+
- Git
- Claude Code or Gemini CLI
- (Optional) Google Workspace, Jira, Slack, GitHub, Confluence accounts
- (Optional) AWS Bedrock access for LLM synthesis

---

## Migration

### From v3.0/v3.1/v3.2

Fully backward compatible. Brain entities are automatically normalized on first access:

```bash
python3 common/tools/brain/schema_migrator.py --migrate-all
```

### From v2.4

```bash
/update-3.0
```

Creates a backup snapshot, migrates Brain/sessions/context, generates config.yaml. See [Migration Guide](https://your-company.atlassian.net/wiki/spaces/PMOS/pages/migration-guide).

---

## Documentation

Full documentation is maintained on Confluence:

- **[PM-OS Confluence Space](https://your-company.atlassian.net/wiki/spaces/PMOS/)** — Architecture, installation, workflows, troubleshooting
- [Getting Started](docs/getting-started.md)
- [Brain 1.2 Guide](docs/brain-1.2.md)
- [Command Reference](docs/command-reference.md)
- [Contributing](docs/contributing.md)

---

## Changelog

### v3.4.0 (2026-02-11)
- **Pip Install Overhaul**: Complete rewrite of the installation system with 10-step interactive wizard, `--quick` auto-detect mode, and `--template` non-interactive mode
- **Bundled Google OAuth**: Google OAuth client secret bundled in the Acme Corp pip package — one-click browser authentication during wizard, no Cloud Console setup
- **6-Scope Google Integration**: Expanded from 2 scopes to 6 (Drive, Drive metadata, Drive file, Gmail, Calendar events, Calendar read) with `google_auth.py` as single source of truth
- **Template Install Security**: `_strip_secrets_from_config()` prevents API tokens from leaking into `config.yaml` during template-based installs
- **Silent Install Parity**: `run_silent_install()` rewritten to produce the same rich output as the interactive wizard (full .env, USER.md, Glossary, brain files)
- **Directory Permissions**: `.secrets/` set to mode 700 during all install paths
- **Google Token Wiring**: Brain population reuses the OAuth token from the integrations step — no second browser popup
- **Documentation**: Updated installation guide, new Google OAuth setup guide, new pip package reference — all synced to Confluence (24 pages)

### v3.3.0 (2026-02-10)
- **Bedrock LLM Integration**: Context synthesis and meeting prep via AWS Bedrock (Claude Haiku 4.5)
- **Model-agnostic synthesis**: Bedrock, Gemini, Claude Code, and template fallback
- **Brain Density**: Enrichment orchestrator with <30% orphan rate target
- **ENRICH Phase**: New pipeline phase between WRITE and SYNAPSE
- **Push Publisher v2**: Jira ticket in branch naming, PyPI publishing with version bumping
- **CI Compliance**: Black formatting, security check fixes, Tech Platform headref rules
- **Slack Integration**: Release notes and context summaries to configured channels
- **PyPI Distribution**: `pip install pm-os` with optional dependency groups

### v3.2.0 (2026-01-22)
- **Brain 1.2**: Time-series entity system with canonical references
- **PRD to Spec Machine**: Export PRDs to implementation specs
- **Beads-Ralph Integration v2.0**: Bidirectional sync between Beads and Ralph
- **Data Quality Tools**: Canonical resolver, relationship normalizer, orphan cleaner
- **Pydantic Schemas**: Type-safe entity validation

### v3.1.0 (2026-01-16)
- Developer tools extraction
- Beads issue tracking
- Sprint learnings command

### v3.0.0 (2026-01-06)
- Complete architecture redesign (common/user split)
- Multi-model support (Claude + Gemini)
- Session persistence
- FPF reasoning framework

---

## Contributing

We welcome contributions! See [Contributing](docs/contributing.md) for guidelines.

## License

MIT License - See [LICENSE](LICENSE)

---

*PM-OS v3.4 - Built with care at Acme Corp*
