# PM-OS

```
    ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐
    │  Cal │   │ Docs │   │Slack │   │ Jira │
    └──┬───┘   └──┬───┘   └──┬───┘   └──┬───┘
       │          │          │          │
       └────┬─────┴────┬─────┴────┬─────┘
            │          │          │
       ┌────┴──────────┴──────────┴────┐
       │       CONTEXT  ENGINE         │
       │   aggregate → synthesize →    │
       │         → deliver             │
       └──────────────┬────────────────┘
                      │
       ┌──────────────┴────────────────┐
       │                               │
  ┌────┴────┐  ┌─────────┐  ┌─────────┴──┐
  │  Brain  │  │ Meeting │  │  Documents  │
  │ ◉──◉──◉ │  │  Prep   │  │ PRD RFC ADR │
  │ ◉──◉──◉ │  │ ◈ ◈ ◈   │  │ PRFAQ  BC  │
  └─────────┘  └─────────┘  └────────────┘

    ██████╗ ███╗   ███╗       ██████╗ ███████╗
    ██╔══██╗████╗ ████║      ██╔═══██╗██╔════╝
    ██████╔╝██╔████╔██║█████╗██║   ██║███████╗
    ██╔═══╝ ██║╚██╔╝██║╚════╝██║   ██║╚════██║
    ██║     ██║ ╚═╝ ██║      ╚██████╔╝███████║
    ╚═╝     ╚═╝     ╚═╝       ╚═════╝ ╚══════╝

     AI-Native Product Management Operating System
```

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

PM-OS is an AI-native operating system for product managers. It syncs context from Google Workspace, Jira, Slack, GitHub, and Confluence into a unified daily briefing, prepares meeting pre-reads, maintains a knowledge graph ([Brain](https://github.com/feamando/brain)), tracks issues and action items, and generates structured documents — all orchestrated through slash commands in [Claude Code](https://docs.anthropic.com/en/docs/build-with-claude/claude-code) or [Gemini CLI](https://github.com/google-gemini/gemini-cli).

---

## Installation

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

### Context Creation Engine

The Context Creation Engine is the heart of PM-OS. It's a multi-stage data pipeline that aggregates information from 6+ external sources, synthesizes it with LLMs, populates a knowledge graph, and delivers a structured daily briefing — all in a single command.

#### Architecture

```
                    ┌─────────────┐
                    │  /boot or   │
                    │ /update-ctx │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   ┌───────────┐   ┌───────────┐   ┌───────────┐
   │  Google   │   │   Slack   │   │   Jira    │
   │Docs/Gmail │   │ Channels  │   │ Projects  │
   │ Calendar  │   │ @Mentions │   │  Sprints  │
   └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
         │               │               │
         └───────────┬───┴───────────────┘
                     ▼
            ┌────────────────┐
            │   EXTRACTION   │  Raw data → Brain/Inbox/
            └────────┬───────┘
                     ▼
            ┌────────────────┐
            │    ANALYSIS    │  LLM-powered structured extraction
            │  (Bedrock /    │  Document type detection
            │   Gemini)      │  Entity + relationship extraction
            └────────┬───────┘
                     ▼
            ┌────────────────┐
            │   SYNTHESIS    │  Daily context file generation
            │  (Claude /     │  Alerts, blockers, action items
            │   Bedrock)     │  Previous context carry-forward
            └────────┬───────┘
                     ▼
            ┌────────────────┐
            │  BRAIN WRITE   │  Entity creation/update
            │                │  Decision logging
            │                │  Project context
            └────────┬───────┘
                     ▼
            ┌────────────────┐
            │  ENRICHMENT    │  Relationship extraction
            │                │  5 independent strategies
            │                │  Target: <30% orphan rate
            └────────┬───────┘
                     ▼
            ┌────────────────┐
            │     LOAD       │  Hot topics identification
            │                │  Compressed Brain index
            │                │  Meeting pre-reads
            └────────────────┘
```

#### Data Sources

| Source | What It Fetches | Tool |
|--------|----------------|------|
| **Google Docs** | Recently modified documents (7-day lookback) | `daily_context_updater.py` |
| **Gmail** | Emails authored by or shared with you | `daily_context_updater.py` |
| **Google Calendar** | Upcoming meetings, attendees, links | `meeting_prep.py` |
| **Slack** | Channel messages across configurable tiers (tier1/tier2/tier3), @mention task tracking | `slack_bulk_extractor.py` |
| **Jira** | Project status, sprint data, owner/team relationships | `jira_brain_sync.py` |
| **GitHub** | PR activity, commit history, maintainer/contributor data | `github_brain_sync.py` |
| **Statsig** | Active/inactive feature flag experiments | `statsig_brain_sync.py` |
| **Master Sheet** | Priority items, deadlines, owner assignments, weekly plan | `master_sheet_sync.py` |

#### LLM Synthesis

The engine supports multiple LLM backends with automatic fallback:

| Backend | Model | Use Case |
|---------|-------|----------|
| **AWS Bedrock** | Claude Opus 4.6 | Batch document analysis (rate-limited: 10 req/min) |
| **Anthropic API** | Claude Haiku 4.5 | Fast context synthesis |
| **Google Gemini** | Gemini 2.5 Flash | Meeting prep synthesis, orthogonal challenge |
| **Template** | Rule-based | Fallback when no LLM available |

During analysis, each document is classified by type (PRD, 1:1 meeting, standup, review, etc.) and processed with type-specific structured extraction prompts that produce JSON output with entities, decisions, action items, and dependencies.

The synthesis phase carries forward unresolved items from the previous day's context and produces a structured daily briefing:

```markdown
## Critical Alerts
## Today's Schedule
## Key Updates & Decisions
## Active Blockers (table: Blocker | Impact | Owner | Status)
## Action Items (organized by timeline)
## Key Dates
## Recent Documents
## Sprint Focus
## Pending Slack Tasks
```

#### Execution Modes

| Mode | Command | Pipeline | Use Case |
|------|---------|----------|----------|
| `full` | `/create-context` | Extract → Analyze → Write → Enrich → Load | Complete refresh |
| `quick` | `/create-context quick` | GDocs + Jira only, no analysis | Daily boot |
| `bulk` | `/create-context bulk` | 6-month extraction, resumable | Historical population |
| `extract` | `/create-context extract` | Extraction only | Data gathering |
| `analyze` | `/create-context analyze` | Analysis only (pre-extracted data) | LLM processing |
| `write` | `/create-context write` | Brain population only | Entity creation |
| `load` | `/create-context load` | Hot topics and index only | Quick reload |

All modes support incremental execution with state tracking. Bulk mode processes 6 months of data with resumability — if interrupted, it picks up where it left off.

#### Output Files

| Output | Location | Purpose |
|--------|----------|---------|
| Daily context | `user/personal/context/YYYY-MM-DD-context.md` | Synthesized daily briefing |
| Raw documents | `user/brain/Inbox/GDocs/` | Source document archive |
| Analyzed docs | `user/brain/Inbox/GDocs/Analyzed/` | Structured JSON extraction |
| Entity files | `user/brain/Entities/{type}/` | People, teams, squads, systems |
| Project pages | `user/brain/Projects/` | Project/feature context |
| Decision log | `user/brain/Reasoning/Decisions/` | Decision audit trail |
| Brain index | `user/brain/BRAIN.md` | Compressed entity index for agent context |
| Writer state | `user/brain/brain_writer_state.json` | Pipeline progress tracking |

Commands: `/boot`, `/update-context`, `/create-context`

---

### Meeting Prep System

Automated pre-reads for upcoming meetings, integrated with the Context Engine.

#### How It Works

1. **Fetch** — Pulls calendar events for the next N hours (default: 24)
2. **Classify** — Categorizes each meeting by type with per-type word limits:

| Type | Max Words | Focus |
|------|-----------|-------|
| 1:1 | 300 | Action items first, quick context |
| Standup | 150 | Team status |
| Interview | 1000 | Detailed assessment |
| External | 500 | Company context, talking points |
| Large Meeting | 200 | Why am I here? |
| Review/Retro | 400 | Your prep, discussion points |
| Planning | 400 | Sprint context |

3. **Gather context** — Pulls participant info from Brain, relevant Jira issues, recent documents
4. **Synthesize** — LLM generates a personalized pre-read (Bedrock, Gemini, Claude, or template fallback)
5. **Upload** — Writes pre-read to Google Drive and links it to the calendar event
6. **Archive** — Cleans up cancelled/orphaned preps

#### Series Intelligence

For recurring meetings, the system maintains a `Series-{slug}.md` file that tracks outcomes over time:

- Extracts decisions, commitments, recommendations, open questions from each occurrence
- Synthesizes patterns and recurring themes across the series
- Carries forward open items automatically
- Detects task completion using signals from Jira, GitHub, Slack, and Brain (with confidence scores)

#### Output Routing

Pre-reads are automatically routed based on meeting type:

```
user/planning/Meeting_Prep/
├── Series/           # Recurring meetings (Series-{slug}.md)
├── AdHoc/            # One-time meetings
└── Archive/          # Past/cancelled
```

1:1s additionally route to `user/team/reports/{person}/1on1s/` or `user/team/manager/{person}/1on1s/`.

Command: `/meeting-prep`

---

### Brain Knowledge Graph (v3.0.0)

A time-series entity system that maintains your organizational knowledge. See [pmos-brain](https://github.com/feamando/brain) for the standalone library.

- **Canonical references** — `entity/{type}/{slug}` normalized format
- **Typed relationships** — Bidirectional with temporal validity
- **Event sourcing** — Full change history, point-in-time queries
- **Quality scoring** — Automated completeness and freshness metrics
- **Enrichment pipeline** — 5 independent strategies: body text extraction, GDocs, Jira, GitHub, embedding similarity
- **Graph health monitoring** — Targets <30% orphan rate, >56% relationship coverage

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

### First Principles Framework (FPF)

A 5-step reasoning framework for structured decision-making:

| Step | Command | Purpose |
|------|---------|---------|
| Q0 | `/q0-init` | Initialize context |
| Q1 | `/q1-hypothesize` | Generate hypotheses (Abduction) |
| Q2 | `/q2-verify` | Verify logic (Deduction) |
| Q3 | `/q3-validate` | Validate evidence (Induction) |
| Q4 | `/q4-audit` | Audit trust (Trust Calculus) |
| Q5 | `/q5-decide` | Finalize decision |

FPF integrates into document generation (`/prd`, `/rfc`, `/adr`) to produce reasoning-backed artifacts.

### Session Management (Confucius)

Lightweight context capture during conversations:

- **5 capture types:** Decisions (D), Assumptions (A), Observations (O), Blockers (B), Tasks (T)
- **Research capture** with categories: competitive, technical, market, internal, discovery
- **Pattern detection** for automatic capture
- **Export for FPF context injection**
- **Session persistence** and searchability

Commands: `/session-save`, `/session-load`, `/session-search`, `/confucius-status`

### Document Generation

Structured documents with FPF reasoning:

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

### Ralph (Long-Running Features)

Multi-iteration feature development across context windows:

- **Spec-driven development** — PLAN.md with acceptance criteria drives each loop
- **Background execution** — Iterations continue while you work on other tasks
- **Progress tracking** — Checkboxes and iteration logs
- **Slack updates** — Automatic progress notifications

Commands: `/ralph-init`, `/ralph-specs`, `/ralph-loop`, `/ralph-status`

---

## Directory Structure

```
pm-os/
├── common/                  # Shared framework (this repo)
│   ├── .claude/commands/       # 84 Claude slash commands
│   ├── .gemini/commands/       # Gemini commands
│   ├── tools/                  # Python tools
│   │   ├── boot/               # Boot orchestrator
│   │   ├── brain/              # Brain v3.0.0 knowledge system
│   │   ├── daily_context/      # Context sync engine
│   │   ├── meeting/            # Meeting prep system
│   │   ├── session/            # Confucius session management
│   │   ├── beads/              # Issue tracking
│   │   ├── slack/              # Slack integration
│   │   ├── integrations/       # Google, Jira, GitHub, Confluence
│   │   ├── quint/              # FPF reasoning framework
│   │   ├── master_sheet/       # Priority tracking
│   │   └── preflight/          # Health checks
│   ├── schemas/                # Pydantic entity schemas
│   ├── frameworks/             # Document templates
│   ├── rules/                  # Agent behavior rules
│   ├── documentation/          # System documentation
│   └── scripts/                # Boot scripts
│
├── user/                    # Your data (separate repo)
│   ├── brain/                  # Knowledge base entities
│   │   ├── Entities/           # People, teams, squads, systems
│   │   ├── Projects/           # Project/feature pages
│   │   ├── Reasoning/          # Decision log
│   │   ├── Inbox/              # Raw ingested data
│   │   └── BRAIN.md            # Compressed entity index
│   ├── personal/context/       # Daily context files
│   ├── planning/               # Meeting prep, career planning
│   │   └── Meeting_Prep/       # Series/, AdHoc/, Archive/
│   ├── sessions/               # Session persistence
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
| | `/create-context` | Full context pipeline (extract/analyze/write/enrich/load) |
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
| **Development** | `/ralph-init` | Initialize feature for multi-iteration work |
| | `/ralph-loop` | Run feature development iteration |
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

## Configuration

### config.yaml

```yaml
version: "3.3.0"

user:
  name: "Your Name"
  email: "you@company.com"
  position: "Product Manager"
  tribe: null
  team: null

integrations:
  google:
    enabled: true
    scopes: ["drive", "calendar", "gmail", "docs"]
  slack:
    enabled: true
    mention_bot_name: "your-slack-bot"
  jira:
    enabled: true
    url: "https://your-company.atlassian.net"
    tracked_projects: ["PROJ1", "PROJ2"]
    default_project: "PROJ1"
  github:
    enabled: true
    org: "your-org"
    tracked_repos: ["repo1", "repo2"]
  confluence:
    enabled: true
    url: "https://your-company.atlassian.net/wiki"
    space_key: "SPACE"
  statsig:
    enabled: false

brain:
  entity_types: [person, team, project, domain, experiment]
  hot_topics_limit: 10
  validate_on_load: true
  enrichment:
    auto_enrich: true
    orphan_threshold: 0.30

context:
  synthesis_backend: "bedrock"   # bedrock | gemini | claude | template
  retention_days: 30
  output_dir: "personal/context/"

meeting_prep:
  prep_hours: 24
  include_competitors: false
  include_recent_context: true

pm_os:
  fpf_enabled: true
  confucius_enabled: true
  ralph_enabled: true
```

### .env

```bash
# Required
ANTHROPIC_API_KEY=sk-...

# Google Workspace
GOOGLE_CREDENTIALS_FILE=credentials.json

# Slack
SLACK_BOT_TOKEN=
SLACK_APP_TOKEN=

# Jira
JIRA_API_TOKEN=...
JIRA_EMAIL=you@company.com
JIRA_SERVER=https://your-company.atlassian.net

# GitHub
GITHUB_TOKEN=...

# AWS Bedrock (for LLM synthesis)
AWS_REGION=us-east-1
AWS_PROFILE=default

# Master Sheet (optional)
MASTER_SHEET_SPREADSHEET_ID=
MASTER_SHEET_ENABLED=false
```

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

Creates a backup snapshot, migrates Brain/sessions/context, and generates config.yaml.

---

## Changelog

### v3.3.0 (2026-02-10)
- **Bedrock LLM Integration**: Context synthesis and meeting prep via AWS Bedrock (Claude Haiku 4.5)
- **Model-agnostic synthesis**: Bedrock, Gemini, Claude Code, and template fallback
- **Brain Density**: Enrichment orchestrator with <30% orphan rate target
- **ENRICH Phase**: New pipeline phase between WRITE and SYNAPSE
- **CI Compliance**: Black formatting, security check fixes
- **Slack Integration**: Context summaries to configured channels

### v3.2.0 (2026-01-22)
- **Brain v3.0.0**: Time-series entity system with canonical references and event sourcing
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

Contributions are welcome. Please open an issue first to discuss what you'd like to change.

## License

MIT License - See [LICENSE](LICENSE)
