# PM-OS Installation Guide

> How to install and configure PM-OS v3.3

## Quick Install (Recommended)

The fastest way to get PM-OS running:

```bash
# Install PM-OS CLI
pip install pm-os

# Quick setup — auto-detects name/email from git config
pm-os init --quick

# Verify installation
pm-os doctor
```

The `--quick` flag:
- Auto-detects your name and email from `git config`
- Only prompts for LLM API key (Claude/Anthropic)
- Creates the full directory structure with sensible defaults
- Skips optional integrations (add them later)
- Downloads `common/` from GitHub automatically

### After Quick Setup

```bash
# Add integrations as needed
pm-os setup integrations jira
pm-os setup integrations slack

# Sync your brain from integrations
pm-os brain sync

# Get help on any topic
pm-os help brain
pm-os help integrations
```

---

## Installation Methods

PM-OS supports three installation paths:

| Method | Command | Best For |
|--------|---------|----------|
| **Quick** | `pm-os init --quick` | First-time users, minimal config |
| **Full Wizard** | `pm-os init` | Complete setup with all integrations |
| **Template** | `pm-os init --template config.yaml` | Automated/scripted deployments |

### Full Guided Setup

For complete setup with all integrations, run the interactive 10-step wizard:

```bash
pm-os init
```

The wizard walks through these steps:

| # | Step | Description |
|---|------|-------------|
| 1 | Welcome | Overview of PM-OS and what will be configured |
| 2 | Prerequisites | Checks Python, pip, git, disk space |
| 3 | User Profile | Name, email, position, tribe |
| 4 | LLM Provider | Configure AI provider (Claude, Bedrock, Gemini) |
| 5 | Integrations | Jira, Slack, Google, GitHub, Confluence (all optional) |
| 6 | Download PM-OS Tools | Clones `common/` from GitHub with tools and commands |
| 7 | Directory Setup | Creates directory structure, config files, .env |
| 8 | Claude Code Setup | Configures Claude Code commands, settings, environment |
| 9 | Brain Population | Initial sync from configured integrations |
| 10 | Verification | Validates installation, shows next steps |

You can resume an interrupted wizard with:

```bash
pm-os init --resume
```

### Template-Based Install

For automated or scripted deployments, provide a YAML config file:

```bash
pm-os init --template config.yaml
```

The template file contains all configuration (user profile, integrations, LLM settings). PM-OS creates the full directory structure, config files, and environment without any interactive prompts.

Example template:

```yaml
version: "3.3"

user:
  name: "Jane Smith"
  email: "jane.smith@company.com"
  position: "Senior Product Manager"
  tribe: "Growth"

llm:
  provider: "anthropic"
  model: "claude-sonnet-4-20250514"
  api_key: "sk-ant-..."

integrations:
  jira:
    enabled: true
    url: "https://company.atlassian.net"
    username: "jane.smith@company.com"
    api_token: "..."
    project_keys:
      - "GROW"
      - "PLAT"
  google:
    enabled: true
  slack:
    enabled: true
    bot_token: "xoxb-..."

pm_os:
  fpf_enabled: true
  confucius_enabled: true
```

**Security note:** API tokens in the template are used during setup but are NOT written to `config.yaml`. They are stored only in `.env` and `.secrets/` with restricted permissions.

---

## Prerequisites

### Required

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.10+ | Runtime |
| pip | Latest | Package management |
| Git | Any | Repository management, user detection |
| Claude Code | Latest | AI interface (recommended) |

### Optional (for integrations)

| Service | Requirement | Wizard Step |
|---------|-------------|-------------|
| Jira | API token with read access | Step 5 |
| GitHub | Personal access token or `gh` CLI | Step 5 |
| Slack | Bot token with channel access | Step 5 |
| Google | OAuth credentials (bundled for HF users) | Step 5 |
| Confluence | API token (same as Jira) | Step 5 |

### Installation

```bash
pip install pm-os
```

This installs all integrations (Google, Slack, Jira, GitHub, Confluence, AI providers, AWS Bedrock). No extras needed.

For development tools (pytest, black, ruff):

```bash
pip install "pm-os[dev]"
```

---

## Google OAuth Setup

### Acme Corp Users (Bundled Credentials)

If you installed from the `pmos` private repository, Google OAuth credentials are **bundled in the package**. During the wizard:

1. At Step 5 (Integrations), select "Configure" for Google
2. The wizard detects bundled credentials automatically
3. Say "Yes" to authenticate — your browser opens
4. Sign in with your Google account and grant access
5. Token is saved to `.secrets/token.json`

That's it. No Cloud Console setup needed. Google Calendar, Drive, and Gmail work immediately during brain population (Step 9).

**Scopes granted (6 total):**
- `drive.readonly` — Read Google Drive files
- `drive.metadata.readonly` — Read Drive file metadata
- `drive.file` — Access files created by PM-OS
- `gmail.readonly` — Read Gmail messages
- `calendar.events` — Read/write calendar events
- `calendar.readonly` — Read calendar data

### Public Users (Manual Setup)

If you installed from the public `feamando/pmos` repository, you need to create OAuth credentials manually:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable APIs: Google Drive, Google Calendar, Gmail
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
5. Application type: "Desktop app"
6. Download the JSON file
7. During the wizard, provide the path to the downloaded file

### Re-authenticating

If your Google token expires or you need to add scopes:

```bash
# Delete existing token
rm ~/.pm-os/.secrets/token.json

# Re-authenticate during next brain sync
pm-os brain sync --integration google
```

---

## CLI Reference

### Installation Commands

| Command | Description |
|---------|-------------|
| `pm-os init` | Full interactive wizard (10 steps) |
| `pm-os init --quick` | Quick setup with auto-detection |
| `pm-os init --template FILE` | Non-interactive install from config |
| `pm-os init --resume` | Resume interrupted wizard |
| `pm-os doctor` | Verify installation health |
| `pm-os doctor --fix` | Auto-fix common issues |
| `pm-os uninstall` | Remove PM-OS |

### Post-Install Commands

| Command | Description |
|---------|-------------|
| `pm-os setup integrations` | List/configure integrations |
| `pm-os brain sync` | Sync from all integrations |
| `pm-os brain sync --integration google` | Sync from specific integration |
| `pm-os brain status` | Show entity counts |
| `pm-os config show` | Display configuration |
| `pm-os config set KEY VALUE` | Update config value |
| `pm-os status` | Show PM-OS status |

### Help System

| Command | Description |
|---------|-------------|
| `pm-os help` | List all help topics |
| `pm-os help brain` | Brain knowledge graph |
| `pm-os help integrations` | Integration setup |
| `pm-os help troubleshoot` | Troubleshooting guide |
| `pm-os help quick-start` | Getting started |

---

## Directory Structure

After installation, PM-OS creates this structure:

```
~/.pm-os/                          # Default install path
├── .pm-os-root                    # Root marker file
├── .pm-os-user                    # User marker file
├── .env                           # Environment variables (tokens, paths)
├── .gitignore                     # Ignores .secrets/, .env, __pycache__
├── config.yaml                    # User configuration (no secrets)
├── USER.md                        # User profile for AI context
├── .secrets/                      # OAuth tokens, credentials (mode 700)
│   ├── credentials.json           # Google OAuth client secret
│   └── token.json                 # Google OAuth user token
├── brain/                         # Knowledge graph
│   ├── BRAIN.md                   # Brain index
│   ├── Glossary.md                # Team glossary
│   ├── registry.yaml              # Entity registry
│   ├── entities/                  # People, teams, partners
│   ├── projects/                  # Features, epics
│   ├── experiments/               # A/B tests, feature flags
│   ├── strategy/                  # OKRs, roadmaps
│   ├── reasoning/                 # FPF reasoning chains
│   └── inbox/                     # Unprocessed items
├── context/                       # Daily context files
├── sessions/                      # Session logs
├── planning/                      # Planning artifacts
├── common/                        # PM-OS framework (from GitHub)
│   ├── .claude/commands/          # Slash commands
│   ├── tools/                     # Python tools
│   ├── documentation/             # This documentation
│   └── package/                   # pip package source
└── .claude/                       # Claude Code configuration
    ├── commands/                   # Synced slash commands
    └── settings.json              # Claude Code settings
```

### Key Files

| File | Purpose |
|------|---------|
| `.env` | All environment variables: API tokens, paths, integration config |
| `config.yaml` | User preferences and integration settings (no secrets) |
| `USER.md` | Natural-language user profile consumed by AI during `/boot` |
| `.secrets/credentials.json` | Google OAuth client secret |
| `.secrets/token.json` | Google OAuth user token (6 scopes) |
| `brain/BRAIN.md` | Compressed index of all brain entities |
| `brain/Glossary.md` | Team-specific terminology |

---

## Getting API Tokens

### Jira API Token

1. Go to [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click "Create API token"
3. Copy and provide during wizard Step 5

### GitHub Token

Two options:

**Option A: GitHub CLI (recommended)**
```bash
gh auth login
```
The wizard detects `gh` CLI authentication automatically.

**Option B: Personal Access Token**
1. Go to [GitHub Token Settings](https://github.com/settings/tokens)
2. Generate new token (classic)
3. Select scopes: `repo`, `read:org`
4. Provide during wizard Step 5

### Slack Tokens

1. Create a Slack App at [api.slack.com/apps](https://api.slack.com/apps)
2. Add OAuth scopes: `channels:history`, `channels:read`, `chat:write`, `users:read`
3. Install to your workspace
4. Copy the Bot Token (`xoxb-...`) for the wizard

### Confluence Token

Uses the same Atlassian API token as Jira. If you've configured Jira, you already have this.

---

## Directory Permissions

PM-OS sets appropriate permissions during installation:

```bash
# .secrets/ directory: owner-only access
chmod 700 ~/.pm-os/.secrets

# .env file: owner-only read/write
chmod 600 ~/.pm-os/.env
```

If you need to fix permissions manually:

```bash
chmod 700 ~/.pm-os/.secrets
chmod 600 ~/.pm-os/.env
```

---

## Troubleshooting

### "Module not found" errors

Ensure pm-os is installed in your active Python environment:

```bash
pip install pm-os
pm-os doctor
```

### "Cannot resolve PM-OS paths"

Create the root marker file or set environment variables:

```bash
touch ~/.pm-os/.pm-os-root
```

Or:

```bash
export PM_OS_ROOT=~/.pm-os
export PM_OS_COMMON=~/.pm-os/common
export PM_OS_USER=~/.pm-os
```

### Google OAuth Errors

Delete the token and re-authenticate:

```bash
rm ~/.pm-os/.secrets/token.json
pm-os brain sync --integration google
```

For scope mismatch errors (e.g., old 2-scope tokens), the same fix applies — deleting the token forces re-authentication with all 6 current scopes.

### Jira Connection Failed

Verify your credentials:

```bash
pm-os doctor
```

Check that URL, username, and API token are correct in `.env`.

### Wizard Interrupted

Resume from where you left off:

```bash
pm-os init --resume
```

---

## Updating PM-OS

### Update the pip package

```bash
pip install --upgrade pm-os
```

### Update common/ tools

```bash
cd ~/.pm-os/common && git pull origin main
```

Or use the built-in update command:

```bash
pm-os update
```

Your user data (`brain/`, `sessions/`, `config.yaml`) is never modified by updates.

---

## Migration from v2.4

If upgrading from PM-OS v2.4:

```
/update-3.0
```

Or to rollback:

```
/revert-2.4
```

---

*Last updated: 2026-02-11*
*PM-OS Version: 3.4.0*
*Confluence: [PM-OS Installation](https://your-company.atlassian.net/wiki/spaces/PMOS/pages/installation)*
