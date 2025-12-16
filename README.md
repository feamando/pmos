# PM-OS: Product Management Operating System

A Git-backed, CLI-managed, AI-augmented system for Product Management documentation and workflows.

**Version:** 1.2 (December 2025)

## Overview

PM-OS replaces Google Drive/Notion with a structured Markdown-first system designed for use with AI agents (Claude Code, Warp, etc.). It provides:

- **Semantic Knowledge Graph (Brain):** Entity-oriented memory with bi-directional relationships (Synapses).
- **Deep Research PRDs:** Generate comprehensive Product Requirements Documents using Google's Deep Research API.
- **Contextual Mirroring:** Automatically syncs technical context (READMEs) from GitHub into Brain Project files.
- **Automated Workflows:** Daily context updates, meeting prep, and brain maintenance via simple CLI commands.
- **Jira & GitHub Sync:** Automated tracking of epics, blockers, PRs, and commits.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Required keys:
- `GEMINI_API_KEY` (for context synthesis and meeting prep)
- `JIRA_API_TOKEN` & `JIRA_SERVER`
- `GITHUB_TOKEN` (optional, for repo sync)

### 3. Initialize (Daily)

Run the boot script to sync git, load context, and prepare your session:

```powershell
.\boot.ps1
```

### 4. Update Context (Continuous)

Fetch latest emails, docs, and tickets:

```powershell
.\update-context.ps1
```

## Directory Structure

- `AI_Guidance/`: **The Core.** Rules, Templates (`Frameworks/`), and Business Context.
  - `Brain/`: The Knowledge Graph.
    - `Entities/`: People, Teams.
    - `Projects/`: Initiatives.
    - `Architecture/`: Systems.
  - `Tools/`: Python scripts for automation.
- `Products/`: Product documentation source of truth.
- `Planning/`: OKRs, Meeting Prep.

## Tools

| Tool | Command | Description |
|------|---------|-------------|
| **Deep Research** | `/prd <topic>` | Generate a PRD using deep research. |
| **Brain Search** | `search-brain.ps1 <query>` | Context-aware search of the Brain. |
| **Context Update** | `.\update-context.ps1` | Fetch GDocs/Jira/GitHub and synthesize daily context. |
| **Synapse Builder** | `python AI_Guidance/Tools/synapse_builder.py` | Refresh bi-directional Brain links. |
| **Meeting Prep** | `python AI_Guidance/Tools/meeting_prep/meeting_prep.py` | Generate pre-reads for upcoming meetings. |

## License

Internal Use Only.

---

## Changelog

### v1.2 (December 2025)
- **Synapses (Relationships):** Typed, bi-directional links between Brain entities (e.g., `owner` <-> `owns`) enforced by `synapse_builder.py`.
- **Deep Research Integration:** `/prd` command generates high-quality specs by researching the web and internal docs.
- **Technical Context Mirror:** `github_brain_sync.py` now fetches repo READMEs to enrich Project documentation.
- **Slack Integration:** Foundations for Slack-based context fetching.
- **Enhanced Boot:** Faster, safer boot sequence with Git sync and auto-configuration.

### v1.1 (2025-12-12)
- Added GitHub Brain Sync for PR/commit tracking
- Added Sprint Report Generator (standalone + integrated modes)
- Fixed JQL queries to use `statusCategory` for better Kanban support
- Added GitHub Activity column to sprint reports
- Improved Brain structure with GitHub directory

### v1.0 (2025-12-10)
- Initial release with Jira integration, Brain knowledge graph, and core tools
