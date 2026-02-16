# PM-OS Documentation

> Comprehensive documentation for PM-OS (Product Management Operating System)

## Overview

PM-OS is an AI-powered productivity system designed for Product Managers. It integrates with your existing tools (Jira, Confluence, Slack, Google Docs, GitHub) and provides intelligent assistance through Claude Code.

## Quick Links

| Document | Description |
|----------|-------------|
| [Overview](01-overview.md) | What PM-OS is and what problems it solves |
| [Architecture](02-architecture.md) | System architecture and integrations |
| [Installation](03-installation.md) | How to install and configure PM-OS |
| [Pip Package](pip-package.md) | Package structure, extras, CLI reference |
| [Google OAuth](google-oauth-setup.md) | Google integration setup and troubleshooting |
| [Workflows](04-workflows.md) | Key workflows: boot, context, sessions |
| [Brain](05-brain.md) | Brain architecture and knowledge management |

## Reference Documentation

### Commands

All slash commands available in PM-OS:

| Guide | Commands |
|-------|----------|
| [Core Commands](commands/core-commands.md) | `/boot`, `/update-context`, `/session-*` |
| [Document Commands](commands/document-commands.md) | `/prd`, `/rfc`, `/adr`, `/bc`, `/prfaq` |
| [Integration Commands](commands/integration-commands.md) | `/jira-sync`, `/github-sync`, `/confluence-sync` |
| [FPF Commands](commands/fpf-commands.md) | `/q0-init` through `/q5-decide`, `/quint-*` |
| [Agent Commands](commands/agent-commands.md) | `/ralph-*`, `/confucius-*`, `/brain-load` |

### Tools

Python tools powering PM-OS:

| Guide | Tools |
|-------|-------|
| [Brain Tools](tools/brain-tools.md) | `brain_loader.py`, `brain_updater.py` |
| [Integration Tools](tools/integration-tools.md) | Jira, GitHub, Slack, Confluence tools |
| [Session Tools](tools/session-tools.md) | `session_manager.py`, `confucius_agent.py` |
| [Utility Tools](tools/utility-tools.md) | `config_loader.py`, `path_resolver.py` |

### Schemas

Entity schemas for Brain data:

| Guide | Content |
|-------|---------|
| [Entity Schemas](schemas/entity-schemas.md) | Person, Team, Project, Experiment schemas |

## Help & Support

- [Common Issues](troubleshooting/common-issues.md) - Known issues and solutions
- [FAQ](troubleshooting/faq.md) - Frequently asked questions
- [Creating Your Slackbot](slackbot/creating-your-bot.md) - Custom slackbot guide

## Getting Started

### Quick Start (Recommended)

```bash
pip install pm-os
pm-os init --quick    # ~5 minutes
pm-os doctor          # Verify installation
```

### CLI Help System

```bash
pm-os help                 # List all help topics
pm-os help brain           # Brain knowledge graph
pm-os help integrations    # Setting up integrations
pm-os help troubleshoot    # Diagnosing issues
```

### Full Documentation

1. **New Users**: Start with [Installation](03-installation.md)
2. **Understanding PM-OS**: Read [Overview](01-overview.md) and [Architecture](02-architecture.md)
3. **Daily Usage**: Learn [Workflows](04-workflows.md)
4. **Power Users**: Explore [Brain](05-brain.md) and command references

## Version

- **PM-OS Version**: 3.4.0
- **Documentation Version**: 1.2.0
- **Last Updated**: 2026-02-11

## Confluence

This documentation is synced to Confluence: [PMOS Space](https://your-company.atlassian.net/wiki/spaces/PMOS/overview)

---

*Maintained by PM-OS Team*
