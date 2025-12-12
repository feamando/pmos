# PM-OS: Product Management Operating System

A Git-backed, CLI-managed, AI-augmented system for Product Management documentation and workflows.

## Overview

PM-OS replaces Google Drive/Notion with a structured Markdown-first system designed for use with AI agents (Claude Code, Warp, etc.). It provides:

- **Semantic Knowledge Graph (Brain):** Entity-oriented memory for projects, people, decisions
- **Jira Integration:** Automated sync of epics, blockers, and sprint data
- **GitHub Integration:** PR tracking and commit history per squad
- **Sprint Reporting:** AI-summarized reports from Jira data
- **Google Drive Bridge:** Import docs from GDrive into the local system
- **Meeting Prep:** Auto-generated pre-reads from calendar and context

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials:
# - JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN
# - GEMINI_API_KEY
```

### 3. Configure Squads (for Jira/GitHub sync)

```bash
cp squad_registry.yaml.example squad_registry.yaml
# Edit squad_registry.yaml with your team's Jira projects and GitHub repos
```

### 4. Initialize Git

```bash
git init
git add .
git commit -m "Initial PM-OS setup"
```

### 5. Boot the Agent

If using Claude Code, run:
```
/boot
```

Or manually read `AGENT.md` and `AI_Guidance/Rules/AI_AGENTS_GUIDE.md`.

## Directory Structure

```
PM-OS/
├── AGENT.md                    # AI agent entry point
├── README.md                   # This file
├── .env.example                # Environment template
├── requirements.txt            # Python dependencies
├── squad_registry.yaml         # Team/squad configuration
├── generate_report.py          # Standalone sprint report generator
│
├── AI_Guidance/
│   ├── Rules/                  # Operational guidelines
│   │   └── AI_AGENTS_GUIDE.md  # Agent behavior rules
│   ├── Tools/                  # Python automation
│   │   ├── brain_loader.py     # Load relevant Brain files
│   │   ├── jira_brain_sync.py  # Sync Jira to Brain
│   │   ├── github_brain_sync.py # Sync GitHub to Brain
│   │   ├── sprint_report_generator.py # Integrated reports
│   │   ├── gdrive_mcp/         # Google Drive integration
│   │   ├── jira_mcp/           # Jira MCP server
│   │   ├── meeting_prep/       # Calendar-based prep
│   │   └── daily_context/      # Context updater
│   └── Brain/                  # Semantic knowledge graph
│       ├── Projects/           # Project documentation
│       ├── Entities/           # People, teams, squads
│       ├── Architecture/       # Technical docs
│       ├── Decisions/          # ADRs
│       ├── Inbox/              # Raw sync data
│       └── GitHub/             # PR/commit tracking
│
├── .claude/
│   └── commands/               # Slash commands
│       ├── boot.md             # /boot - Initialize context
│       ├── update-context.md   # /update-context
│       ├── logout.md           # /logout - End session
│       ├── pm.md               # /pm - PM mode
│       └── meeting-notes.md    # /meeting-notes
│
├── Products/                   # Product documentation
├── Team/                       # People management
├── Reporting/                  # Sprint reports, updates
│   └── Sprint_Reports/
└── Planning/                   # OKRs, strategy
```

## Core Tools

### Jira Brain Sync

Fetches epics, in-progress items, and blockers for your squads:

```bash
python AI_Guidance/Tools/jira_brain_sync.py

# Options:
--squad "Squad Name"    # Single squad only
--summarize             # Include AI summary
--github                # Include GitHub PR links
```

### GitHub Brain Sync

Fetches open PRs and recent commits:

```bash
python AI_Guidance/Tools/github_brain_sync.py

# Options:
--squad "Squad Name"    # Single squad only
--summarize             # Include AI summary
--analyze-files         # File change analysis
```

### Sprint Report Generator

Generate bi-weekly sprint reports:

```bash
# Standalone (direct Jira queries)
python generate_report.py

# Integrated (uses Brain sync data)
python AI_Guidance/Tools/sprint_report_generator.py
```

### Brain Loader

Find relevant Brain files based on context:

```bash
python AI_Guidance/Tools/brain_loader.py              # Scan latest context
python AI_Guidance/Tools/brain_loader.py --query "OTP" # Search specific terms
```

## Configuration

### squad_registry.yaml

Maps your squads to Jira projects and GitHub repos:

```yaml
squads:
  - name: "Engineering"
    jira_project: "ENG"
    jira_board_id: "1234"
    tribe: "Product"
    github_repos:
      - repo: "your-org/your-repo"
        pr_prefix: "ENG-"
        paths: ["/src/engineering"]
```

### .env

| Variable | Description |
|----------|-------------|
| `JIRA_URL` | Your Jira instance URL |
| `JIRA_USERNAME` | Your Jira email |
| `JIRA_API_TOKEN` | [Create API token](https://id.atlassian.com/manage-profile/security/api-tokens) |
| `GEMINI_API_KEY` | [Get Gemini key](https://makersuite.google.com/app/apikey) |

## Workflows

### Daily Boot
1. Run `/boot` or read core context files
2. Run Jira sync: `python AI_Guidance/Tools/jira_brain_sync.py`
3. Run GitHub sync: `python AI_Guidance/Tools/github_brain_sync.py`
4. Run brain loader to identify hot topics

### Sprint Reporting
1. Ensure Jira/GitHub sync is recent
2. Run `python generate_report.py`
3. Review CSV in `Reporting/Sprint_Reports/`
4. Edit KPI and Demo columns manually

### Session End
1. Run `/logout "Summary of work done"`
2. Or manually commit and push changes

## Customization

### Adding Your Style Guide

Create `AI_Guidance/Rules/YOUR_NAME.md` with:
- Communication preferences
- Document formatting rules
- Vocabulary and tone guidelines

Reference it in `AI_AGENTS_GUIDE.md`.

### Adding Custom Commands

Create `.claude/commands/your-command.md` with instructions for the AI agent.

## Requirements

- Python 3.9+
- Git
- `gh` CLI (for GitHub sync) - [Install](https://cli.github.com/)
- Claude Code, Warp, or compatible AI agent

## Support

For issues or questions, refer to the tool-specific README files in each directory.

---
*PM-OS v1.1 - December 2025*

## Changelog

### v1.1 (2025-12-12)
- Added GitHub Brain Sync for PR/commit tracking
- Added Sprint Report Generator (standalone + integrated modes)
- Fixed JQL queries to use `statusCategory` for better Kanban support
- Added GitHub Activity column to sprint reports
- Improved Brain structure with GitHub directory

### v1.0 (2025-12-10)
- Initial release with Jira integration, Brain knowledge graph, and core tools
