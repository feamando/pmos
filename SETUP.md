# PM-OS Setup Guide

Detailed step-by-step guide for setting up PM-OS from scratch.

---

## Quick Setup (Recommended)

The fastest way to get PM-OS running:

```bash
# Install PM-OS CLI
pip install pm-os

# Quick setup (~5 minutes)
pm-os init --quick

# Verify installation
pm-os doctor
```

### What Quick Setup Does

1. **Auto-detects** your name and email from git config
2. **Configures** your LLM provider (prompts for API key)
3. **Creates** the PM-OS directory structure
4. **Skips** optional integrations (add later)

### Adding Integrations Later

After quick setup, add integrations as needed:

```bash
# List available integrations
pm-os setup integrations --list

# Configure specific integrations
pm-os setup integrations jira
pm-os setup integrations slack
pm-os setup integrations github

# Sync your brain
pm-os brain sync
```

### PM-OS CLI Commands

| Command | Description |
|---------|-------------|
| `pm-os init` | Full guided wizard |
| `pm-os init --quick` | Quick setup (~5 min) |
| `pm-os init --resume` | Resume interrupted setup |
| `pm-os doctor` | Verify installation health |
| `pm-os doctor --fix` | Auto-fix common issues |
| `pm-os setup integrations` | Configure integrations |
| `pm-os brain sync` | Sync brain from integrations |
| `pm-os brain status` | Show brain entity counts |
| `pm-os config show` | Display configuration |
| `pm-os config set KEY VALUE` | Update configuration |
| `pm-os help <topic>` | Get help on a topic |
| `pm-os status` | Show PM-OS status |

### Help Topics

```bash
pm-os help brain            # Brain knowledge graph
pm-os help integrations     # Setting up integrations
pm-os help troubleshoot     # Diagnosing issues
pm-os help quick-start      # Getting started
pm-os help skills           # Using PM-OS skills
```

---

## Full Manual Setup

If you prefer manual control or the CLI isn't available, follow the detailed steps below.

---

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] Python 3.10 or higher installed
- [ ] PowerShell 7+ installed (`pwsh`)
- [ ] Claude Code CLI installed and authenticated
- [ ] Git installed
- [ ] Access to your organization's:
  - [ ] Jira (with API token)
  - [ ] Slack (with app permissions)
  - [ ] GitHub (with personal access token)
  - [ ] Google Workspace (with OAuth configured)

---

## Phase 1: Repository Setup

### 1.1 Create Your PM-OS Directory

```bash
# Choose your location
mkdir ~/pm-os
cd ~/pm-os

# Initialize git repository
git init

# Copy PM-OS distribution files
# (adjust source path as needed)
cp -r /path/to/PM-OS_Distribution/* .
```

### 1.2 Configure Git Ignore

Ensure sensitive files are not committed:

```bash
cat > .gitignore << 'EOF'
# Credentials
.env
*.token.json
client_secret*.json
credentials.json
.secrets/

# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/

# OS files
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/

# Logs
*.log
EOF
```

### 1.3 Initial Commit

```bash
git add .
git commit -m "Initial PM-OS setup"
```

---

## Phase 2: Python Environment

### 2.1 Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

### 2.2 Install Dependencies

```bash
pip3 install -r requirements.txt
```

### 2.3 Verify Installation

```bash
python3 -c "import jira; import slack_sdk; print('Dependencies OK')"
```

---

## Phase 3: API Configuration

### 3.1 Create Environment File

```bash
cp .env.example .env
```

### 3.2 Google Workspace Setup

**Step 1: Create Google Cloud Project**

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click "Select Project" → "New Project"
3. Name: `pm-os-integration`
4. Click "Create"

**Step 2: Enable APIs**

1. Go to "APIs & Services" → "Library"
2. Search and enable:
   - Gmail API
   - Google Drive API
   - Google Calendar API

**Step 3: Configure OAuth Consent**

1. Go to "APIs & Services" → "OAuth consent screen"
2. Select "Internal" (if available) or "External"
3. Fill in required fields:
   - App name: `PM-OS`
   - User support email: your email
   - Developer contact: your email
4. Add scopes:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/drive.readonly`
   - `https://www.googleapis.com/auth/calendar.readonly`

**Step 4: Create Credentials**

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Application type: "Desktop app"
4. Name: `pm-os-desktop`
5. Download JSON file
6. Save as `AI_Guidance/Tools/gdrive_mcp/client_secret.json`

**Step 5: First-Time Authorization**

```bash
python3 AI_Guidance/Tools/daily_context/daily_context_updater.py --dry-run
```

This will open a browser for OAuth authorization. After authorizing, a `token.json` file is created.

### 3.3 Jira Setup

**Step 1: Get API Token**

1. Go to [Atlassian API Tokens](https://id.atlassian.com/manage/api-tokens)
2. Click "Create API token"
3. Label: `pm-os`
4. Copy the token (you won't see it again)

**Step 2: Find Your Jira Server**

Your Jira server URL is typically:
- `https://your-company.atlassian.net` (Cloud)
- `https://jira.your-company.com` (Server)

**Step 3: Identify Projects**

List the Jira project keys you want to track (e.g., `PROJ`, `TEAM`, `MOBILE`).

**Step 4: Update .env**

```bash
JIRA_SERVER=https://your-company.atlassian.net
JIRA_EMAIL=your.email@company.com
JIRA_API_TOKEN=your-api-token-here
JIRA_PROJECTS=PROJ,TEAM,MOBILE
```

**Step 5: Test Connection**

```bash
python3 AI_Guidance/Tools/jira_brain_sync.py --test
```

### 3.4 GitHub Setup

**Step 1: Create Personal Access Token**

1. Go to [GitHub Settings → Tokens](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Note: `pm-os`
4. Select scopes:
   - `repo` (full repository access)
5. Generate and copy token

**Step 2: Identify Repositories**

Format: `organization/repository`

Examples:
- `my-company/backend-api`
- `my-company/mobile-app`

**Step 3: Update .env**

```bash
GITHUB_TOKEN=ghp_your-token-here
GITHUB_REPOS=my-company/backend-api,my-company/mobile-app
```

**Step 4: Test Connection**

```bash
python3 AI_Guidance/Tools/github_brain_sync.py --test
```

### 3.5 Slack Setup

**Step 1: Create Slack App**

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click "Create New App"
3. Choose "From scratch"
4. App Name: `PM-OS`
5. Select your workspace

**Step 2: Add Bot Scopes**

1. Go to "OAuth & Permissions"
2. Under "Bot Token Scopes", add:
   - `channels:history`
   - `channels:read`
   - `groups:history`
   - `groups:read`
   - `users:read`

**Step 3: Install to Workspace**

1. Click "Install to Workspace"
2. Authorize the app
3. Copy "Bot User OAuth Token" (starts with `xoxb-`)

**Step 4: Invite Bot to Channels**

For each channel you want PM-OS to read:
```
/invite @PM-OS
```

**Step 5: Get Channel Names**

List the channels PM-OS should monitor (without #):
- `engineering-updates`
- `product-team`
- `weekly-sync`

**Step 6: Update .env**

```bash
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_CHANNELS=engineering-updates,product-team,weekly-sync
```

**Step 7: Test Connection**

```bash
python3 AI_Guidance/Tools/slack_bulk_extractor.py --test
```

### 3.5.1 Slack Mention Capture Setup (New in v2.4)

For automatic capture of @mentions to your PM-OS bot:

**Step 1: Add Additional Bot Scopes**

Go to your Slack app's "OAuth & Permissions" and add these scopes:
- `app_mentions:read` - Read mentions of the bot
- `chat:write` - Reply to mention messages
- `reactions:read` - Track completion via reactions

**Step 2: Reinstall App (if needed)**

After adding new scopes, reinstall the app to your workspace.

**Step 3: Get Bot User ID**

You need your bot's user ID (not the app ID). To find it:
1. In Slack, mention your bot and click on its name
2. Click "View profile"
3. Click the "..." menu → "Copy member ID"

Or use the API:
```bash
python3 -c "
from slack_sdk import WebClient
import os
from dotenv import load_dotenv
load_dotenv()
client = WebClient(token=os.getenv('SLACK_BOT_TOKEN'))
result = client.auth_test()
print(f'Bot User ID: {result[\"user_id\"]}')
"
```

**Step 4: Update .env**

```bash
# Add bot user ID for mention capture
SLACK_BOT_USER_ID=U0XXXXXXXXX
```

**Step 5: Invite Bot to Channels**

Ensure your bot is invited to channels where you want mention capture:
```
/invite @YourBotName
```

**Step 6: Create Mentions Directory**

```bash
mkdir -p AI_Guidance/Brain/Inbox/Slack/Mentions
```

**Step 7: Test Mention Capture**

```bash
python3 AI_Guidance/Tools/slack_mention_handler.py --dry-run
```

**Step 8: (Optional) Configure LLM for Task Formalization**

The mention system can use LLM to formalize raw mentions into structured tasks.
Ensure you have either:
- Gemini API key (`GEMINI_API_KEY` in .env)
- AWS Bedrock configured (`AWS_PROFILE` and `AWS_REGION` in .env)

**Usage:**

```bash
# Run mention capture
/slackbot capture

# Check mention status
/slackbot status

# Reprocess pending mentions
/slackbot reprocess
```

### 3.6 Confluence Setup (New in v2.1)

**Step 1: Get API Token**

1. Use the same [Atlassian API Token](https://id.atlassian.com/manage/api-tokens) as Jira, or create a new one
2. Ensure you have read access to the spaces you want to sync

**Step 2: Identify Spaces**

List the Confluence space keys you want to sync (e.g., `ENG`, `PROD`, `TEAM`).

**Step 3: Update .env**

```bash
CONFLUENCE_URL=https://your-company.atlassian.net/wiki
CONFLUENCE_EMAIL=your.email@company.com
CONFLUENCE_API_TOKEN=your-api-token-here
CONFLUENCE_SPACES=ENG,PROD,TEAM
```

**Step 4: Test Connection**

```bash
python3 AI_Guidance/Tools/confluence_brain_sync.py --test
```

### 3.7 AWS Bedrock Setup (Optional)

For LLM-powered analysis using Claude on AWS Bedrock:

**Step 1: Configure AWS CLI**

```bash
aws configure --profile bedrock
# Enter: Access Key, Secret Key, Region (us-east-1)
```

**Step 2: Verify Bedrock Access**

Ensure your AWS account has Bedrock model access enabled for Claude models.

**Step 3: Update .env**

```bash
AWS_PROFILE=bedrock
AWS_REGION=us-east-1
```

---

## Phase 4: Persona Configuration

### 4.1 Create Your Persona File

```bash
# Copy template
cp AI_Guidance/Rules/PERSONA_TEMPLATE.md AI_Guidance/Rules/YOUR_NAME.md
```

### 4.2 Fill In Required Sections

Edit `AI_Guidance/Rules/YOUR_NAME.md`:

**Section 1: Professional Identity**
- Your name, role, company
- Team structure
- Key partners
- Reporting line

**Section 5: Vocabulary**
- Add your company's acronyms
- Domain-specific terms
- Project codenames

**Section 8: Team Profiles**
- Direct reports (if any)
- Key stakeholders

**Section 10: Key Projects**
- Current initiatives
- Active workstreams

### 4.3 Update AGENT.md

Edit `AGENT.md` to reference your persona:

```markdown
## Persona
See `AI_Guidance/Rules/YOUR_NAME.md` for communication style and preferences.
```

---

## Phase 5: Brain Initialization

### 5.1 Create Your User Entity

Create `AI_Guidance/Brain/Entities/Your_Name.md`:

```markdown
---
type: person
name: Your Name
role: Your Role
team: Your Team
created: 2025-01-05
---

# Your Name

## Profile
- **Role:** Your Role at Your Company
- **Team:** Your Team
- **Manager:** Your Manager's Name

## Key Projects
- Project 1
- Project 2

## Stakeholders
- Engineering Lead: [Name]
- Design Lead: [Name]
```

### 5.2 Create Initial Project Files

For each major project, create a file in `AI_Guidance/Brain/Projects/`:

```markdown
---
type: project
name: Project Name
owner: Your Name
status: Active
created: 2025-01-05
---

# Project Name

## Overview
Brief description of the project.

## Current Status
- Phase: [Planning/Development/Launch]
- Next Milestone: [Description]

## Team
- PM: Your Name
- Engineering: [Name]
- Design: [Name]
```

---

## Phase 6: First Run

### 6.1 Start Claude Code

```bash
claude
```

### 6.2 Run Setup Wizard

```
/setup
```

Follow the interactive prompts to:
- Verify profile information
- Test integrations
- Initialize Brain

### 6.3 Pull Initial Context

```
/create-context full
```

This will:
- Pull recent Google Docs
- Sync Jira tickets
- Extract GitHub activity
- Fetch Slack messages (if configured)
- Analyze and populate Brain

### 6.4 Verify Setup

```
/boot
```

You should see:
- Core context files loaded
- Hot topics from Brain identified
- FPF reasoning state (if any)

---

## Phase 7: Daily Usage

### Morning Routine

```bash
claude
/boot
```

### Throughout the Day

- Use `/pm` for general PM assistance
- Use `/meeting-prep` before meetings
- Use `/meeting-notes` after meetings
- Use `/create-context quick` for context refresh

### End of Day

```
/logout
```

---

## Verification Checklist

After setup, verify each component:

- [ ] `/boot` runs without errors
- [ ] `/create-context status` shows all integrations
- [ ] Jira sync works: `python3 AI_Guidance/Tools/jira_brain_sync.py --test`
- [ ] GitHub sync works: `python3 AI_Guidance/Tools/github_brain_sync.py --test`
- [ ] Google OAuth works: `python3 AI_Guidance/Tools/daily_context/daily_context_updater.py --dry-run`
- [ ] Brain has initial entities: `ls AI_Guidance/Brain/Entities/`
- [ ] Persona file exists: `cat AI_Guidance/Rules/YOUR_NAME.md`

---

## Next Steps

1. **Read WORKFLOWS.md** - Learn PM-OS workflow patterns
2. **Customize Persona** - Refine your communication style
3. **Grow the Brain** - Add more entities as you encounter them
4. **Explore FPF** - Try the reasoning commands for complex decisions

---

## Getting Help

- Check README.md for quick reference
- Run `/help` in Claude Code
- Review command files in `.claude/commands/`
- Check tool documentation in `AI_Guidance/Tools/README.md`
