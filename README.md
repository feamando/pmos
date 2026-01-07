# PM-OS: Product Management Operating System v2.2

A Git-backed, CLI-managed operating system for Product Managers. PM-OS transforms your daily workflow by automatically gathering context from your tools (Jira, Slack, GitHub, Google Docs, Confluence), building a semantic knowledge graph (the "Brain"), and providing AI-powered assistance tailored to your communication style.

---

## What's New in v2.2

### Technical Brain Integration

PM-OS now understands your codebase! The new **Technical Brain** (`Brain/Technical/`) gives PM-OS awareness of:
- **Tech stack** - Frameworks, libraries, and infrastructure
- **Coding conventions** - Patterns and standards from your repos
- **Repository structure** - Per-repo technical overviews

This enables PRDs, ADRs, and RFCs to reference real technical constraints and patterns.

### New Commands (+6)

| Command | Description |
|---------|-------------|
| `/analyze-codebase` | Analyze a GitHub repo and update Technical Brain |
| `/sync-tech-context` | Sync patterns from spec-machine (if available) |
| `/ralph-init` | Initialize a Ralph long-running task |
| `/ralph-loop` | Continue a Ralph iteration |
| `/ralph-status` | Check Ralph task status |
| `/ralph-specs` | Generate specs for Ralph tasks |

### New Tools (+2)

| Tool | Purpose |
|------|---------|
| `tech_context_sync.py` | Analyze repos and sync technical patterns |
| `ralph_manager.py` | Manage long-running multi-session tasks |

### Enhanced Commands

- `/prd` - Now loads Technical Brain context before generation
- `/adr` - References existing architecture patterns
- `/rfc` - Includes technical feasibility assessment

### Summary

- **Total Commands**: 50 (up from 44 in v2.1)
- **Total Tools**: 47 (up from 40 in v2.1)
- **Technical Brain**: New `Brain/Technical/` for codebase understanding
- **Ralph Mode**: Long-running task management across sessions
- **Smarter Documents**: PRDs/ADRs/RFCs reference real code patterns

---

## What's in v2.1

### New Commands (+11)

| Command | Description |
|---------|-------------|
| `/adr` | Generate Architecture Decision Records |
| `/bc` | Generate Business Cases |
| `/confluence-sync` | Sync Confluence pages to Brain |
| `/orthogonal-status` | Check orthogonal challenge status |
| `/prfaq` | Generate PR/FAQ documents (Amazon style) |
| `/rfc` | Generate Request for Comments documents |
| `/session-load` | Load a previous session |
| `/session-save` | Save current session state |
| `/session-search` | Search session history |
| `/session-status` | Show current session status |
| `/tribe-update` | Generate tribe quarterly updates |

### New Tools (+8)

| Tool | Purpose |
|------|---------|
| `confluence_brain_sync.py` | Sync Confluence spaces to Brain |
| `model_bridge.py` | Bridge between LLM providers |
| `orthogonal_challenge.py` | Devil's advocate reasoning |
| `research_aggregator.py` | Aggregate research findings |
| `session_manager.py` | Manage session state across boots |
| `slack_context_poster.py` | Post context summaries to Slack |
| `template_manager.py` | Manage document templates |
| `tribe_quarterly_update.py` | Generate quarterly update reports |

### Summary

- **Total Commands**: 44 (up from 33 in v2.0)
- **Total Tools**: 40 (up from 32 in v2.0)
- **New Document Types**: ADR, BC, PRFAQ, RFC, Tribe Update
- **Session Management**: Full session persistence across boots
- **Confluence Integration**: Native Confluence sync support
- **Orthogonal Challenges**: Devil's advocate reasoning for better decisions

---

## What is PM-OS?

PM-OS is an **AI-native productivity framework** designed specifically for Product Managers. Unlike generic AI assistants, PM-OS:

- **Maintains persistent context** across sessions via the Brain knowledge graph
- **Integrates with your actual tools** (Jira, Slack, GitHub, Google Workspace, Confluence)
- **Learns your communication style** through a personalized persona file
- **Provides structured workflows** via 50 specialized slash commands
- **Tracks decisions and reasoning** with the FPF (First Principles Framework)

### Who is PM-OS For?

- Product Managers who work across multiple tools and need unified context
- PMs who use Claude Code / AI assistants and want persistent memory
- Teams that value documentation and decision traceability
- Anyone who wants to reduce context-switching overhead

---

## Architecture Overview

```
                                 PM-OS Architecture
    +---------------------------------------------------------------------+
    |                        EXTERNAL SOURCES                              |
    |    +---------+  +---------+  +---------+  +---------+  +---------+  |
    |    | Google  |  |  Jira   |  | GitHub  |  |  Slack  |  |Confluence| |
    |    |Docs/Mail|  |         |  |         |  |         |  |         |  |
    |    +----+----+  +----+----+  +----+----+  +----+----+  +----+----+  |
    +---------|-----------|-----------|-----------|-----------|----------+
              |           |           |           |           |
              v           v           v           v           v
    +---------------------------------------------------------------------+
    |                      INGESTION LAYER                                 |
    |                                                                      |
    |    /create-context  -------------------------------------------------|
    |         |                                                            |
    |         +-- daily_context_updater.py (GDocs, Gmail)                 |
    |         +-- jira_brain_sync.py (Jira epics, tickets)                |
    |         +-- github_brain_sync.py (PRs, commits)                     |
    |         +-- slack_bulk_extractor.py (Channel history)               |
    |         +-- confluence_brain_sync.py (Confluence pages) [NEW]       |
    |         +-- statsig_brain_sync.py (Experiments)                     |
    |                                                                      |
    +------------------------+--------------------------------------------+
                             |
                             v
    +---------------------------------------------------------------------+
    |                       ANALYSIS LAYER                                 |
    |                                                                      |
    |    batch_llm_analyzer.py ----> LLM-powered entity extraction        |
    |    file_chunker.py ----------> Large file processing                |
    |    unified_brain_writer.py --> Structured Brain population          |
    |    research_aggregator.py ---> Research findings aggregation [NEW]  |
    |                                                                      |
    +------------------------+--------------------------------------------+
                             |
                             v
    +---------------------------------------------------------------------+
    |                     THE BRAIN (Knowledge Core)                       |
    |                                                                      |
    |    Brain/                                                           |
    |    +-- Entities/      <- People, teams, systems                     |
    |    +-- Projects/      <- Active initiatives, features               |
    |    +-- Architecture/  <- Technical systems, services                |
    |    +-- Decisions/     <- Decision records                           |
    |    +-- Reasoning/     <- FPF hypotheses, evidence                   |
    |    |   +-- Decisions/                                               |
    |    |   +-- Hypotheses/                                              |
    |    |   +-- Evidence/                                                |
    |    +-- Synapses/      <- Cross-references, relationships            |
    |    +-- Inbox/         <- Raw ingested data                          |
    |    +-- Strategy/      <- Strategic documents                        |
    |                                                                      |
    +------------------------+--------------------------------------------+
                             |
                             v
    +---------------------------------------------------------------------+
    |                      CONTEXT LAYER                                   |
    |                                                                      |
    |    Core_Context/                                                    |
    |    +-- YYYY-MM-DD-context.md  <- Daily synthesized context          |
    |                                                                      |
    |    Sessions/                                                        |
    |    +-- YYYY-MM-DD-NNN/        <- Session state [NEW]                |
    |                                                                      |
    |    brain_loader.py ----------> Identifies "hot topics"              |
    |    synapse_builder.py --------> Builds entity relationships         |
    |    session_manager.py --------> Session persistence [NEW]           |
    |                                                                      |
    +------------------------+--------------------------------------------+
                             |
                             v
    +---------------------------------------------------------------------+
    |                       OUTPUT LAYER                                   |
    |                                                                      |
    |    /boot -------------> Initialize session with full context        |
    |    /pm ---------------> PM Assistant mode                           |
    |    /meeting-prep -----> Generate meeting pre-reads                  |
    |    /prd --------------> Generate PRDs with context                  |
    |    /adr --------------> Generate ADRs [NEW]                         |
    |    /prfaq ------------> Generate PR/FAQs [NEW]                      |
    |    /rfc --------------> Generate RFCs [NEW]                         |
    |    /tribe-update -----> Generate quarterly updates [NEW]            |
    |    /q* commands ------> FPF reasoning workflows                     |
    |                                                                      |
    +---------------------------------------------------------------------+
```

---

## Quick Start (5 Minutes)

### Prerequisites

- **Python 3.10+**
- **PowerShell 7+** (pwsh)
- **Claude Code CLI** ([Installation Guide](https://claude.ai/code))
- **Git** (for version control)

### Step 1: Clone/Copy Repository

```bash
git clone [your-pm-os-repo] pm-os
cd pm-os
```

Or copy the PM-OS distribution folder to your desired location.

### Step 2: Install Python Dependencies

```bash
pip3 install -r requirements.txt
```

### Step 3: Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys (see API Configuration section)
```

### Step 4: Run Setup Wizard

```bash
claude
# Then run:
/setup
```

The setup wizard will:
- Collect your profile information
- Create your personalized persona file
- Configure integrations
- Initialize your Brain

### Step 5: First Boot

```bash
/boot
```

You're ready to go! PM-OS will pull your context and initialize the assistant.

---

## Full Installation Guide

### Step 1: Repository Setup

Create your PM-OS workspace:

```bash
# Create directory
mkdir ~/pm-os && cd ~/pm-os

# Initialize git
git init

# Copy PM-OS distribution files
cp -r /path/to/PM-OS_Distribution/* .

# Create .gitignore for sensitive files
cat >> .gitignore << 'EOF'
.env
*.token.json
client_secret*.json
.secrets/
__pycache__/
*.pyc
EOF

# Initial commit
git add .
git commit -m "Initial PM-OS setup"
```

### Step 2: Python Environment

```bash
# Create virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip3 install -r requirements.txt
```

**Required packages:**
- `pyyaml` - Configuration parsing
- `python-dotenv` - Environment variable management
- `jira` - Jira API integration
- `slack-sdk` - Slack API integration
- `google-api-python-client` - Google Workspace APIs
- `google-auth-oauthlib` - Google OAuth
- `google-generativeai` - Gemini for LLM analysis (optional)

### Step 3: API Key Configuration

Copy and configure the environment file:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

#### Google Workspace (GDocs, Gmail, Calendar)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing
3. Enable APIs: Gmail API, Google Drive API, Google Calendar API
4. Create OAuth 2.0 credentials (Desktop application)
5. Download `client_secret_*.json` to `AI_Guidance/Tools/gdrive_mcp/`
6. Run first-time auth:
   ```bash
   python3 AI_Guidance/Tools/daily_context/daily_context_updater.py --dry-run
   ```

#### Jira

1. Go to [Atlassian API Tokens](https://id.atlassian.com/manage/api-tokens)
2. Create new API token
3. Add to `.env`:
   ```
   JIRA_SERVER=https://your-company.atlassian.net
   JIRA_EMAIL=your-email@company.com
   JIRA_API_TOKEN=your-api-token
   JIRA_PROJECTS=PROJ1,PROJ2
   ```

#### GitHub

1. Go to [GitHub Personal Access Tokens](https://github.com/settings/tokens)
2. Create new token with `repo` scope
3. Add to `.env`:
   ```
   GITHUB_TOKEN=ghp_your-token
   GITHUB_REPOS=org/repo1,org/repo2
   ```

#### Slack

1. Create Slack app at [api.slack.com/apps](https://api.slack.com/apps)
2. Add scopes: `channels:history`, `channels:read`, `users:read`, `chat:write`
3. Install to workspace
4. Add to `.env`:
   ```
   SLACK_BOT_TOKEN=xoxb-your-token
   SLACK_CHANNELS=channel1,channel2
   SLACK_POST_CHANNEL=your-private-channel-id
   ```

#### Confluence (New in v2.1)

1. Go to [Atlassian API Tokens](https://id.atlassian.com/manage/api-tokens)
2. Use same token as Jira or create new
3. Add to `.env`:
   ```
   CONFLUENCE_URL=https://your-company.atlassian.net/wiki
   CONFLUENCE_EMAIL=your-email@company.com
   CONFLUENCE_API_TOKEN=your-api-token
   CONFLUENCE_SPACES=SPACE1,SPACE2
   ```

#### AWS Bedrock (Optional - for LLM Analysis)

```bash
# Configure AWS CLI with bedrock profile
aws configure --profile bedrock
```

Add to `.env`:
```
AWS_PROFILE=bedrock
AWS_REGION=us-east-1
```

### Step 4: First Boot

```bash
claude
/boot
```

---

## The Brain System

The Brain is PM-OS's semantic knowledge graph - a structured collection of markdown files that represent your professional context.

### Directory Structure

```
AI_Guidance/Brain/
+-- Entities/           # People, teams, external systems
|   +-- John_Smith.md
|   +-- Engineering_Team.md
+-- Projects/           # Active initiatives and features
|   +-- Q1_Launch.md
|   +-- Mobile_App_Redesign.md
+-- Architecture/       # Technical systems and services
|   +-- Payment_Service.md
|   +-- API_Gateway.md
+-- Decisions/          # Decision records
|   +-- README.md
+-- Reasoning/          # FPF reasoning artifacts
|   +-- Decisions/      # Design Rationale Records
|   +-- Hypotheses/     # Active hypotheses
|   +-- Evidence/       # Supporting evidence
+-- Synapses/           # Cross-references
+-- Strategy/           # Strategic documents
+-- Inbox/              # Raw ingested data
    +-- GDocs/
    +-- Slack/
    +-- Jira/
    +-- GitHub/
    +-- Confluence/     # New in v2.1
```

### Entity Format

Each Brain entity follows a standard format:

```markdown
---
type: person | project | system | team
name: Entity Name
status: Active | Inactive | Complete
created: YYYY-MM-DD
last_updated: YYYY-MM-DD
related:
  - "[[path/to/related.md]]"
---

# Entity Name

## Overview
Brief description of the entity.

## Key Information
- Bullet points with important details
- Links to related entities

## Changelog
- **YYYY-MM-DD**: Update description
```

### Synapses

Synapses are automatically generated cross-references that link related entities. They're created by `synapse_builder.py` and help Claude understand relationships between concepts.

---

## Commands Reference

PM-OS includes 44 specialized slash commands:

### Core Commands

| Command | Description |
|---------|-------------|
| `/boot` | Initialize session with full context |
| `/setup` | Run setup wizard for new users |
| `/create-context` | Pull context from all sources |
| `/update-context` | Quick context refresh |
| `/logout` | End session, save context |

### Session Management (New in v2.1)

| Command | Description |
|---------|-------------|
| `/session-status` | Show current session status |
| `/session-save` | Save current session state |
| `/session-load` | Load a previous session |
| `/session-search` | Search session history |

### PM Workflows

| Command | Description |
|---------|-------------|
| `/pm` | Enter PM Assistant mode |
| `/meeting-notes` | Create structured meeting notes |
| `/meeting-prep` | Generate meeting pre-reads |
| `/prd` | Generate Product Requirements Document |
| `/4cq` | Four Critical Questions framework |
| `/pupdate` | Performance update report |
| `/whitepaper` | Strategic proposal document |
| `/sprint-report` | Generate sprint report |

### Document Generation (Expanded in v2.1)

| Command | Description |
|---------|-------------|
| `/adr` | Architecture Decision Record |
| `/bc` | Business Case document |
| `/prfaq` | PR/FAQ document (Amazon style) |
| `/rfc` | Request for Comments document |
| `/tribe-update` | Tribe quarterly update |

### Brain Management

| Command | Description |
|---------|-------------|
| `/brain-load` | Load hot topics from Brain |
| `/synapse` | Build entity relationships |
| `/jira-sync` | Sync Jira data to Brain |
| `/github-sync` | Sync GitHub data to Brain |
| `/confluence-sync` | Sync Confluence pages to Brain (New) |
| `/statsig-sync` | Sync Statsig experiments |

### FPF Reasoning (14 commands)

| Command | Description |
|---------|-------------|
| `/q0-init` | Initialize FPF reasoning cycle |
| `/q1-hypothesize` | Generate hypotheses (abduction) |
| `/q1-add` | Add user hypothesis |
| `/q2-verify` | Verify logic (deduction) |
| `/q3-validate` | Validate with evidence (induction) |
| `/q4-audit` | Audit evidence quality |
| `/q5-decide` | Finalize decision |
| `/q-status` | Show FPF status |
| `/q-reset` | Reset FPF cycle |
| `/q-query` | Search knowledge base |
| `/q-decay` | Evidence freshness check |
| `/q-actualize` | Reconcile with repo changes |
| `/quint-review` | Review reasoning state |
| `/quint-prd` | FPF-enhanced PRD |
| `/quint-sync` | Sync with Quint |
| `/gemini-fpf` | Gemini FPF bridge |
| `/orthogonal-status` | Orthogonal challenge status (New) |

---

## Tools Reference

PM-OS includes 40+ Python tools:

### Context Ingestion

| Tool | Purpose |
|------|---------|
| `daily_context_updater.py` | Pull GDocs/Gmail |
| `jira_brain_sync.py` | Sync Jira projects |
| `github_brain_sync.py` | Sync GitHub repos |
| `slack_bulk_extractor.py` | Extract Slack history |
| `confluence_brain_sync.py` | Sync Confluence pages (New) |
| `statsig_brain_sync.py` | Sync experiments |

### Analysis

| Tool | Purpose |
|------|---------|
| `batch_llm_analyzer.py` | LLM-powered entity extraction |
| `file_chunker.py` | Split large files for processing |
| `unified_brain_writer.py` | Write analyzed data to Brain |
| `research_aggregator.py` | Aggregate research findings (New) |
| `orthogonal_challenge.py` | Devil's advocate analysis (New) |

### Brain Management

| Tool | Purpose |
|------|---------|
| `brain_loader.py` | Load relevant Brain entities |
| `brain_updater.py` | Update Brain entities |
| `synapse_builder.py` | Build entity relationships |

### Session Management (New in v2.1)

| Tool | Purpose |
|------|---------|
| `session_manager.py` | Manage session persistence |
| `template_manager.py` | Manage document templates |

### Outputs

| Tool | Purpose |
|------|---------|
| `sprint_report_generator.py` | Generate sprint reports |
| `tribe_quarterly_update.py` | Generate quarterly updates (New) |
| `slack_context_poster.py` | Post context to Slack (New) |
| `model_bridge.py` | Bridge between LLM providers (New) |

---

## PM Workflows

### Daily Boot Routine

```bash
# Start Claude Code
claude

# Full boot (recommended)
/boot

# Quick boot (skip external syncs)
/boot quick

# Context only (fastest)
/boot context-only
```

### Session Management (New in v2.1)

```bash
# Check current session
/session-status

# Save session before long break
/session-save

# Resume previous session
/session-load 2025-01-05-001

# Search past sessions
/session-search "marketplace decision"
```

### Context Gathering

```bash
# Full pipeline (all sources)
/create-context

# Quick refresh (GDocs + Jira only)
/create-context quick

# Specific sources
/create-context extract -Sources "jira,github,confluence"

# Bulk historical (6 months)
/create-context bulk
```

### Meeting Preparation

```bash
# Generate pre-reads for next 12 hours
/meeting-prep

# After meeting - create notes
/meeting-notes
```

### Document Generation

```bash
# Generate PRD with Brain context
/prd "Feature: User Authentication"

# Generate Architecture Decision Record
/adr "Should we use microservices or monolith?"

# Generate PR/FAQ (Amazon style)
/prfaq "New Premium Tier Feature"

# Generate RFC
/rfc "API Versioning Strategy"

# Generate Business Case
/bc "Expansion into APAC Market"

# Strategic proposal
/whitepaper "API Platform Strategy"

# Sprint report
/sprint-report

# Tribe quarterly update
/tribe-update
```

### Decision Making with FPF

```bash
# Start reasoning cycle
/q0-init "Should we build vs buy the payment system?"

# Generate hypotheses
/q1-hypothesize

# Run orthogonal challenge (devil's advocate)
/orthogonal-status

# Verify logic
/q2-verify

# Validate with evidence
/q3-validate

# Audit quality
/q4-audit

# Make decision
/q5-decide
```

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "No module named 'jira'" | Run `pip3 install -r requirements.txt` |
| Jira 401 error | Check JIRA_API_TOKEN in .env |
| Google OAuth fails | Delete token.json, re-run auth flow |
| Slack rate limited | Reduce channels or use tier1 only |
| Brain not loading | Run `/brain-load` or check file paths |
| Context file too large | Run `/create-context preprocess` |
| Session not loading | Check AI_Guidance/Sessions/ directory |
| Confluence 403 error | Check CONFLUENCE_API_TOKEN permissions |

### Logs and Debugging

```bash
# Check tool status
/create-context status

# Check session status
/session-status

# Dry run (preview without changes)
pwsh create-context.ps1 -Mode extract -DryRun

# Verbose output
python3 AI_Guidance/Tools/jira_brain_sync.py --verbose
```

---

## FAQ

**Q: How much disk space does PM-OS use?**
A: The Brain typically uses 10-50MB depending on context volume. Historical Slack data can be larger.

**Q: Can I use PM-OS without all integrations?**
A: Yes! Configure only the integrations you need. PM-OS works with partial setups.

**Q: How do I backup my Brain?**
A: The Brain is Git-tracked. Regular commits preserve your context history.

**Q: Can multiple people share a PM-OS instance?**
A: PM-OS is designed for individual use. Each person should have their own instance.

**Q: How do I update PM-OS?**
A: Pull latest from your PM-OS repo. Brain data is preserved across updates.

**Q: What's the difference between session-save and logout?**
A: `/logout` ends the session and saves final state. `/session-save` saves a checkpoint without ending.

**Q: How do I migrate from v2.0 to v2.1?**
A: Copy new command files to `.claude/commands/` and new tools to `AI_Guidance/Tools/`. Your Brain data is preserved.

---

## Contributing

PM-OS is designed to be extended. To add a new:

- **Command**: Create `.claude/commands/your-command.md`
- **Tool**: Add Python script to `AI_Guidance/Tools/`
- **Integration**: Follow existing patterns in ingestion tools

---

## Version History

### v2.1 (Current)
- Added 11 new commands (session management, document types, confluence)
- Added 8 new tools (session manager, confluence sync, orthogonal challenge)
- Session persistence across Claude Code boots
- Confluence integration
- Orthogonal challenges for better decision-making
- Slack context posting

### v2.0
- Initial public release
- 33 commands, 32 tools
- Brain knowledge graph
- FPF reasoning framework
- Integration with Jira, GitHub, Slack, Google Workspace

---

## License

MIT License - See LICENSE file for details.

---

## Support

- **Issues**: File GitHub issues for bugs and feature requests
- **Documentation**: See SETUP.md and WORKFLOWS.md for detailed guides
- **Community**: [Link to community forum/Discord if available]

---

*PM-OS v2.1 - Built for Product Managers, by Product Managers*
