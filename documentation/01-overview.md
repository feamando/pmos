# PM-OS Overview

> AI-powered operating system for Product Managers

## What is PM-OS?

PM-OS (Product Management Operating System) is an intelligent productivity system that augments your workflow with AI capabilities through Claude Code. It connects your existing tools, maintains persistent context about your work, and provides specialized commands for common PM tasks.

## Problems PM-OS Solves

| Problem | PM-OS Solution |
|---------|----------------|
| **Context switching** | Automatic sync from all your tools into a unified daily context |
| **Meeting preparation** | Auto-generated pre-reads from calendar and related documents |
| **Document creation** | Structured templates for PRDs, RFCs, ADRs, Business Cases |
| **Knowledge management** | Persistent Brain storing people, teams, projects, decisions |
| **Session continuity** | Save and resume conversations with full context |
| **Decision tracking** | First Principles Framework (FPF) for structured reasoning |

## Core Capabilities

### 1. Context Management

PM-OS automatically aggregates information from:
- **Google Docs** - Recent documents you've viewed/edited
- **Slack** - Messages from configured channels
- **Jira** - Tickets and sprint status
- **GitHub** - PRs, issues, commits
- **Google Calendar** - Upcoming meetings

This creates a daily context file (`YYYY-MM-DD-context.md`) that Claude understands.

### 2. Document Generation

Create professional PM documents with context-aware AI:

| Document | Command | Use Case |
|----------|---------|----------|
| PRD | `/prd` | Product requirements for new features |
| RFC | `/rfc` | Technical proposals needing review |
| ADR | `/adr` | Architecture decision records |
| BC | `/bc` | Business case justifications |
| PRFAQ | `/prfaq` | Amazon-style PR/FAQ documents |

### 3. Knowledge Base (Brain)

The Brain is your persistent knowledge store:

```
brain/
├── entities/          # People, teams, partners
├── projects/          # Active projects and experiments
├── experiments/       # A/B tests, feature flags
├── strategy/          # OKRs, roadmaps, decisions
├── reasoning/         # FPF cycles and analysis
└── inbox/             # Unprocessed items
```

### 4. Session Persistence

- **Save sessions**: `/session-save` preserves conversation state
- **Load sessions**: `/session-load` resumes with full context
- **Session notes**: Confucius agent tracks key decisions

### 5. Meeting Preparation

`/meeting-prep` generates pre-reads including:
- Attendee backgrounds from Brain
- Related project status
- Previous meeting notes
- Suggested agenda items

### 6. Structured Reasoning (FPF)

The First Principles Framework provides rigorous decision support:

```
q0-init → q1-hypothesize → q2-verify → q3-validate → q4-audit → q5-decide
```

## Who Uses PM-OS?

PM-OS is designed for Product Managers who:
- Work with multiple squads and stakeholders
- Use Jira, Confluence, Slack, and Google Workspace
- Want AI assistance without constant context re-explaining
- Need to maintain documentation and decision records
- Value structured thinking for complex decisions

## Key Concepts

### Two-Repository Architecture

PM-OS v3.0 separates logic from content:

| Repository | Purpose | Updates |
|------------|---------|---------|
| `common/` | Code, commands, tools | `git pull` for new features |
| `user/` | Brain, sessions, config | Your data, never overwritten |

### Environment Variables

After `/boot`, these are available in your shell:

```bash
$PM_OS_ROOT     # Parent directory
$PM_OS_COMMON   # Logic repository path
$PM_OS_USER     # Content repository path
```

### Configuration

All settings are in `user/config.yaml`:

```yaml
user:
  name: "Your Name"
  email: "you@company.com"
  position: "Senior Product Manager"
  tribe: "Your Tribe"

integrations:
  jira:
    enabled: true
  github:
    enabled: true
  slack:
    enabled: true
  confluence:
    enabled: true
```

## Daily Workflow

```mermaid
graph LR
    A[Morning] --> B[/boot]
    B --> C[/update-context]
    C --> D[Work with AI]
    D --> E[/session-save]
    E --> F[End of Day]
```

1. **Start**: Run `/boot` to initialize PM-OS
2. **Sync**: Run `/update-context` to pull latest information
3. **Work**: Use commands and ask questions with full context
4. **Save**: Run `/session-save` before ending

## Getting Started

### Quick Start (Recommended)

The fastest way to get PM-OS running:

```bash
pip install pm-os
pm-os init --quick    # ~5 minutes, auto-detects profile
pm-os doctor          # Verify installation
```

Add integrations later as needed:

```bash
pm-os setup integrations jira
pm-os setup integrations slack
pm-os brain sync
```

### Manual Setup

For full control over the setup process:

1. Read [Installation](03-installation.md) for detailed steps
2. Run `/boot` to initialize your first session
3. Explore [Workflows](04-workflows.md) to learn daily usage
4. Check [Commands](commands/) for available capabilities

### Getting Help

```bash
pm-os help                 # List all help topics
pm-os help brain           # Brain knowledge graph
pm-os help integrations    # Setting up integrations
pm-os help troubleshoot    # Diagnosing issues
```

## Support

- **Slack**: `#pm-os-support` channel
- **Issues**: Report bugs via GitHub issues
- **Documentation**: This folder and Confluence PMOS space

---

*Last updated: 2026-02-09*
*Confluence: [PM-OS Overview](https://your-company.atlassian.net/wiki/spaces/PMOS/overview)*
