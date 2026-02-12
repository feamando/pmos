# PM-OS Installation Guide

> How to install and configure PM-OS

## Quick Install (Recommended)

The fastest way to get PM-OS running:

```bash
# Install PM-OS CLI
pip install pm-os

# Quick setup (~5 minutes)
pm-os init --quick

# Verify installation
pm-os doctor
```

The `--quick` flag:
- Auto-detects your name/email from git config
- Only prompts for LLM API key
- Creates directory structure with sensible defaults
- Skips optional integrations (add later)

### After Quick Setup

```bash
# Add integrations as needed
pm-os setup integrations jira
pm-os setup integrations slack

# Sync your brain
pm-os brain sync

# Get help
pm-os help brain
pm-os help integrations
```

### Full Guided Setup

For complete setup with all integrations:

```bash
pm-os init  # Full wizard, ~15-20 minutes
```

---

## Prerequisites

### Required

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.10+ | Tool execution |
| pip | Latest | Package management |
| Git | Any | Repository management |
| Claude Code | Latest | AI interface (optional but recommended) |

### Optional (for integrations)

| Service | Requirement |
|---------|-------------|
| Jira | API token with read access |
| GitHub | Personal access token |
| Slack | Bot token with channel access |
| Google | OAuth credentials |
| Confluence | API token |

---

## CLI Reference

### Installation Commands

| Command | Description |
|---------|-------------|
| `pm-os init` | Full guided wizard |
| `pm-os init --quick` | Quick setup (~5 min) |
| `pm-os init --resume` | Resume interrupted setup |
| `pm-os doctor` | Verify installation |
| `pm-os doctor --fix` | Auto-fix issues |
| `pm-os uninstall` | Remove PM-OS |

### Post-Install Commands

| Command | Description |
|---------|-------------|
| `pm-os setup integrations` | List/configure integrations |
| `pm-os brain sync` | Sync from integrations |
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

## Manual Installation Steps

### Step 1: Create Directory Structure

```bash
# Create PM-OS root directory
mkdir -p ~/pm-os
cd ~/pm-os

# Clone the common repository (LOGIC)
git clone <pm-os-common-repo-url> common

# Create user directory (CONTENT)
mkdir -p user/{brain/{entities,projects,experiments,strategy,reasoning,inbox},sessions,context,planning}
```

### Step 2: Set Up User Configuration

Create `user/config.yaml`:

```yaml
# PM-OS User Configuration
version: "3.0"

user:
  name: "Your Full Name"
  email: "your.email@company.com"
  position: "Product Manager"
  tribe: "Your Tribe"
  slack_id: "U0XXXXXXXX"  # Your Slack user ID

integrations:
  jira:
    enabled: true
    project_keys:
      - "PROJ1"
      - "PROJ2"
  github:
    enabled: true
  slack:
    enabled: true
    channels:
      - "your-team-channel"
  confluence:
    enabled: true
    spaces:
      - "YOURSPACE"
  google:
    enabled: true

pm_os:
  fpf_enabled: true
  confucius_enabled: true
  auto_save_sessions: true
```

### Step 3: Configure Secrets

Create `user/.env`:

```bash
# Jira
JIRA_URL=https://your-company.atlassian.net
JIRA_USERNAME=your.email@company.com
JIRA_API_TOKEN=your_jira_api_token

# GitHub
GITHUB_ORG=your-org
GITHUB_HF_PM_OS=your_github_token

# Slack
SLACK_BOT_TOKEN=xoxb-your-bot-token
USER_OATH_TOKEN=xoxp-your-user-token
SLACK_USER_ID=U0XXXXXXXX
SLACK_APP_ID=A0XXXXXXXX

# Google (OAuth paths)
GOOGLE_CREDENTIALS_PATH=.secrets/credentials.json
GOOGLE_TOKEN_PATH=.secrets/token.json

# Confluence
CONFLUENCE_URL=https://your-company.atlassian.net/wiki
CONFLUENCE_USERNAME=your.email@company.com
CONFLUENCE_API_TOKEN=your_confluence_token

# Gemini (for meeting prep)
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.5-flash

# Statsig (optional)
STATSIG_CONSOLE_API_KEY=your_statsig_key
```

### Step 4: Set Up Google OAuth

1. Create OAuth credentials in Google Cloud Console
2. Download `credentials.json`
3. Place in `user/.secrets/credentials.json`
4. First run will prompt for OAuth consent

```bash
mkdir -p ~/pm-os/user/.secrets
mv ~/Downloads/credentials.json ~/pm-os/user/.secrets/
```

### Step 5: Install Python Dependencies

```bash
cd ~/pm-os/common
pip install -r requirements.txt
```

Or install individually:

```bash
pip install python-dotenv PyYAML requests atlassian-python-api google-auth-oauthlib
```

### Step 6: Create Marker File (Optional)

For reliable path resolution:

```bash
touch ~/pm-os/.pm-os-root
```

### Step 7: Initialize Brain

Create `user/brain/registry.yaml`:

```yaml
# PM-OS Brain Registry
version: "1.0"
last_updated: "2026-01-13"

entities:
  persons: []
  teams: []
  partners: []

projects:
  features: []
  epics: []

experiments:
  ab_tests: []
  flags: []

strategy:
  okrs: []
  roadmaps: []
```

## Verification

### Test Installation

```bash
cd ~/pm-os/common
python3 tools/config_loader.py --info
```

Expected output:

```
Root:     /Users/yourname/pm-os
Common:   /Users/yourname/pm-os/common
User:     /Users/yourname/pm-os/user
Brain:    /Users/yourname/pm-os/user/brain
Context:  /Users/yourname/pm-os/user/context
Sessions: /Users/yourname/pm-os/user/sessions
Tools:    /Users/yourname/pm-os/common/tools
Strategy: marker_walkup
V2.4 Mode: False
```

### Test Boot

Open Claude Code in any directory and run:

```
/boot
```

You should see:
- Environment variables set
- Context files loaded
- Brain registry accessible

## Getting API Tokens

### Jira API Token

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Copy and save in `.env`

### GitHub Token

1. Go to https://github.com/settings/tokens
2. Generate new token (classic)
3. Select scopes: `repo`, `read:org`
4. Copy and save in `.env`

### Slack Tokens

1. Create Slack App at https://api.slack.com/apps
2. Add OAuth scopes: `channels:history`, `chat:write`, `users:read`
3. Install to workspace
4. Copy Bot and User tokens to `.env`

### Confluence Token

Same as Jira - uses Atlassian API tokens.

### Google OAuth

1. Go to https://console.cloud.google.com
2. Create project or select existing
3. Enable APIs: Drive, Calendar, Docs
4. Create OAuth 2.0 credentials
5. Download JSON and place in `.secrets/`

## Directory Permissions

Ensure proper permissions:

```bash
chmod 600 ~/pm-os/user/.env
chmod -R 700 ~/pm-os/user/.secrets
```

## Troubleshooting

### "Module not found: config_loader"

Ensure you're running from `common/tools/` or PYTHONPATH is set:

```bash
export PYTHONPATH=$PM_OS_COMMON/tools:$PYTHONPATH
```

### "Cannot resolve PM-OS paths"

Create marker file:

```bash
touch ~/pm-os/.pm-os-root
```

Or set environment variables:

```bash
export PM_OS_ROOT=~/pm-os
export PM_OS_COMMON=~/pm-os/common
export PM_OS_USER=~/pm-os/user
```

### Google OAuth Errors

Delete token and re-authenticate:

```bash
rm ~/pm-os/user/.secrets/token.json
python3 tools/gdrive/gdrive_fetcher.py  # Will prompt for consent
```

### Jira Connection Failed

Verify credentials:

```bash
python3 tools/config_loader.py --jira
```

Check that URL, username, and token are correct.

## Updating PM-OS

```bash
cd ~/pm-os/common
git pull origin main
```

Your `user/` directory is never modified by updates.

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

## Developer Tools (Optional)

For PM-OS development, install the developer folder.

### Step 1: Clone Developer Branch

```bash
cd ~/pm-os
git clone -b developer <pm-os-repo-url> developer
```

### Step 2: Verify Structure

```
pm-os/
├── common/      # Framework (existing)
├── user/        # Your data (existing)
└── developer/   # Dev tools (new)
    ├── .claude/commands/
    ├── tools/beads/
    ├── tools/roadmap/
    └── docs/
```

### Step 3: Configure Beads (Optional)

If using Beads for issue tracking:

1. Install Beads CLI:
   ```bash
   npm install -g @beads/cli
   # or
   pip install beads-cli
   ```

2. Initialize in your project:
   ```bash
   cd ~/your-project
   bd init
   ```

### Step 4: Developer Commands

Developer commands auto-sync on `/boot`. To manually sync:

```
/sync-commands
```

Available commands after setup:
- `/bd-*` - Beads issue tracking
- `/parse-roadmap-inbox` - Roadmap management
- `/boot-dev` - Developer environment boot

### Push Configuration (Optional)

To enable `/push` for publishing:

Create `user/.config/push_config.yaml`:

```yaml
common:
  enabled: true
  repo: "your-org/your-pm-os-fork"
  branch: "your-branch"
  push_method: "pr"

brain:
  enabled: true
  repo: "your-username/brain"
  push_method: "direct"

user:
  enabled: true
  repo: "your-username/user"
  push_method: "direct"
```

Authenticate with GitHub:
```bash
gh auth login
```

---

*Last updated: 2026-02-02*
*Confluence: [PM-OS Installation](https://your-company.atlassian.net/wiki/spaces/PMOS/pages/installation)*
