# PM-OS Installation & Demo Guide

**Version:** 3.3 | **Last Updated:** 2026-02-09

Guide for onboarding Product Managers to PM-OS.

---

## Quick Start (Recommended)

The fastest way to get PM-OS running (~5 minutes):

```bash
# Install PM-OS CLI
pip install pm-os

# Quick setup - auto-detects your profile from git
pm-os init --quick

# Verify installation
pm-os doctor
```

**What quick setup does:**
- Auto-detects name/email from git config
- Prompts only for LLM API key
- Creates directory structure with sensible defaults
- Skips optional integrations (add later)

**After quick setup:**

```bash
# Add integrations as needed
pm-os setup integrations jira
pm-os setup integrations slack

# Sync your brain
pm-os brain sync

# Get help on any topic
pm-os help brain
pm-os help integrations
```

For full guided setup with all integrations:

```bash
pm-os init    # Full wizard, ~15-20 minutes
```

---

## Part 1: Manual Installation (Alternative)

Use this approach if you prefer full control over the setup process.

### Prerequisites

- Python 3.10+
- Git
- Claude Code CLI installed (`npm install -g @anthropic-ai/claude-code`)
- Access to feamando/pmos repo

---

### Step 1: Create PM-OS Directory

```bash
mkdir ~/pm-os && cd ~/pm-os
```

### Step 2: Clone Common (LOGIC)

```bash
git clone https://github.com/feamando/pmos.git common
```

### Step 3: Create User Folder (CONTENT)

```bash
mkdir user
cp common/config.yaml.example user/config.yaml
cp common/.env.example user/.env
```

### Step 4: Configure Settings

Edit `user/config.yaml`:

```yaml
user:
  name: "FirstName LastName"
  email: "user@example.com"
  position: "Product Manager"
  team: "Your Team Name"

integrations:
  slack:
    enabled: true
    workspace: "acme-corp"
  jira:
    enabled: true
    project_keys: ["YOUR-PROJECT"]
  google:
    enabled: true
```

Edit `user/.env`:

```bash
# Get tokens from team lead or IT
SLACK_BOT_TOKEN=xoxb-...
JIRA_API_TOKEN=...
GOOGLE_CREDENTIALS_PATH=./credentials.json
```

### Step 5: Create Your User Profile (USER.md)

This file defines your persona and preferences for the AI agent.

```bash
cp common/rules/USER_TEMPLATE.md user/USER.md
```

Edit `user/USER.md` with your details:

```markdown
## Identity

**Name:** [Your Name]
**Role:** Product Manager
**Organization:** Acme Corp / [Your Tribe]

## Communication Style

### Preferred Tone
- [x] Direct and concise
- [ ] Conversational

### Writing Preferences
- Bullet points over paragraphs
- Medium level of detail
- No emojis in formal docs

## Work Context

### Current Focus Areas
1. [Your primary project]
2. [Secondary initiative]
3. [Ongoing responsibilities]

### Key Stakeholders
- [Manager Name] - Direct Manager
- [Eng Lead] - Engineering Partner
- [Designer] - Design Lead

### Reporting Structure
- Reports to: [Manager name]
- Direct reports: [Team members or "N/A"]

## Integration Priorities
1. Jira - [YOUR-PROJECT-KEY]
2. Slack - #your-team-channel
3. Google Docs - Team drive

## Custom Instructions

- Always use [your project] terminology
- Prioritize [specific focus area] in context
- Include [stakeholder] in meeting preps
```

---

### Step 6: Initialize Brain Directory Structure

```bash
mkdir -p user/brain/Entities/People
mkdir -p user/brain/Entities/Teams
mkdir -p user/brain/Projects
mkdir -p user/brain/Inbox/GDocs
mkdir -p user/brain/Inbox/Slack/Raw
mkdir -p user/context
mkdir -p user/sessions
mkdir -p user/planning
```

---

### Step 7: Source Environment

```bash
source common/scripts/boot.sh
```

Verify environment is set:

```bash
echo "Root: $PM_OS_ROOT"
echo "Common: $PM_OS_COMMON"
echo "User: $PM_OS_USER"
```

---

### Step 8: Verify Installation

```bash
python3 common/tools/preflight/preflight_runner.py --quick
```

**Expected:** All checks pass (green checkmarks)

---

### Step 9: Initial Brain Population (6 Months of Data)

This is the critical step that populates your Brain with historical context from all your integrations. **Run this once during initial setup.**

#### Option A: Full Bulk Extraction (Recommended)

Extracts 6 months of data from all sources:

```bash
pwsh common/create-context.ps1 -Mode bulk
```

**What it extracts:**
- Google Docs (6 months)
- Gmail (6 months)
- Jira issues and comments (6 months)
- GitHub commits and PRs (6 months)
- Slack messages from key channels (6 months)

**Duration:** 30-60 minutes depending on data volume

#### Option B: Source-by-Source Extraction

If you prefer to extract sources individually:

```bash
# Extract Google Docs and Gmail (6 months)
pwsh common/create-context.ps1 -Mode bulk -Sources "gdocs" -Days 180

# Extract Jira (6 months)
pwsh common/create-context.ps1 -Mode bulk -Sources "jira" -Days 180

# Extract GitHub (6 months)
pwsh common/create-context.ps1 -Mode bulk -Sources "github" -Days 180

# Extract Slack (6 months, all tiers)
pwsh common/create-context.ps1 -Mode bulk -Sources "slack" -Days 180 -SlackTier all
```

#### After Extraction: Analyze and Write to Brain

```bash
# Run LLM analysis on extracted data
pwsh common/create-context.ps1 -Mode analyze

# Write analyzed data to Brain entities
pwsh common/create-context.ps1 -Mode write

# Load hot topics to verify
pwsh common/create-context.ps1 -Mode load
```

#### Check Pipeline Status

```bash
pwsh common/create-context.ps1 -Mode status
```

**Expected output:**
- Extraction: Complete
- Analysis: Complete
- Brain: N entities created/updated
- Hot Topics: Loaded

---

### Step 10: Verify Brain Population

```bash
# Check Brain has entities
ls -la user/brain/Entities/
ls -la user/brain/Projects/

# Check registry
cat user/brain/registry.yaml | head -50
```

You should see:
- People entities from your Jira/Slack interactions
- Project entities from your docs
- Team entities from organizational data

---

## Part 2: First Boot Demo

### Start Claude Code

**Important:** Always run Claude from the `pm-os` root folder (not from `/user` or `/common`).

```bash
cd ~/pm-os
claude
```

This ensures:
- Both `common/` and `user/` are accessible
- Environment variables resolve correctly
- Slash commands from both repos are available

### Demo 1: Boot PM-OS

```
/boot
```

**What happens:**
- Pre-flight checks verify all tools
- Loads AGENT.md (agent instructions)
- Loads USER.md (your persona/style guide)
- Syncs context from integrations
- Shows hot topics from Brain
- Posts status to Slack

---

## Part 3: Core Capability Demos

### Demo 2: Daily Context Sync

```
/update-context
```

**What it does:**
- Fetches Google Docs (last 7 days)
- Fetches Gmail (unread, last 3 days)
- Fetches Slack mentions
- Fetches Jira updates
- Fetches GitHub activity
- Generates meeting pre-reads
- Synthesizes into `context/YYYY-MM-DD-context.md`

**Show the output:**

```
Read user/context/2026-01-23-context.md
```

Point out:
- Critical Alerts section
- Action Items (with owners)
- Blockers table
- Key Dates

---

### Demo 3: Meeting Prep

```
/meeting-prep "Product Review with Holger"
```

**What it does:**
- Searches calendar for matching meeting
- Loads participant profiles from Brain
- Finds relevant recent context
- Generates structured pre-read

**Output includes:**
- Attendee context (roles, recent interactions)
- Relevant topics from daily context
- Suggested talking points
- Open action items for attendees

---

### Demo 4: PRD Generation

```
/prd "Add dark mode to the mobile app"
```

**What it does:**
- Uses FPF (First Principles Framework) reasoning
- Generates 4CQ structure (Customer, Problem, Solution, Benefit)
- Creates full PRD with sections:
  - Executive Summary
  - Problem Statement
  - Proposed Solution
  - Success Metrics
  - Risks & Mitigations
  - Implementation Considerations

---

### Demo 5: Brain Knowledge Base

**Query the Brain:**

```
What do we know about the OTP project?
```

Claude searches `user/brain/` and returns context from:
- Project files
- Entity references
- Recent context mentions

**Create/Update Brain Entity:**

```
Update the Brain with a new project called "Checkout Redesign" -
it's a P1 initiative for Q2, owned by [PM Name], focused on
reducing cart abandonment by 15%.
```

---

### Demo 6: Session Persistence

```
/session-save
```

**What it does:**
- Captures current conversation context
- Saves to `user/sessions/`
- Can resume later with `/session-load`

**Later (new Claude session):**

```
/session-load
```

Restores context from previous work.

---

### Demo 7: Document Generation

**Sprint Report:**

```
/sprint-report
```

Pulls Jira data, generates formatted sprint summary.

**ADR (Architecture Decision Record):**

```
/adr "Use GraphQL for new API layer"
```

**RFC (Request for Comments):**

```
/rfc "Proposal: Unified Customer Identity"
```

---

## Part 4: Daily Workflow Example

### Morning Routine (5 min)

```
/boot
```

→ See what's critical, what meetings are today, any blockers

### Before Important Meeting

```
/meeting-prep "Weekly Sync with Engineering"
```

→ Get participant context, relevant updates

### After Meeting (capture decisions)

```
Summarize: We decided to delay the launch by 1 week due to
QA findings. Action: [Name] to update stakeholders by EOD.
```

→ Claude updates context, creates action items

### End of Day

```
/session-save
```

→ Preserve context for tomorrow

---

## Part 5: Tips for New Users

| Tip | Why |
|-----|-----|
| Run `/boot` every morning | Syncs context, shows priorities |
| Keep Brain entities updated | Better context = better AI assistance |
| Use structured requests | "Create a PRD for X" > "help me with X" |
| Save sessions before complex work | Can resume if context is lost |
| Check `/help` for all commands | 50+ commands available |

---

## Part 6: Troubleshooting

### Quick Diagnostics

Use the CLI doctor command for fast issue detection:

```bash
pm-os doctor          # Check installation health
pm-os doctor --fix    # Auto-fix common issues
pm-os help troubleshoot  # View troubleshooting guide
```

### "Config not found"

```bash
# Using CLI (recommended)
pm-os init --quick

# Or manually
cp common/config.yaml.example user/config.yaml
# Edit with your settings
```

### "Integration failed"

```bash
# Check configuration
pm-os config show

# Reconfigure specific integration
pm-os setup integrations jira

# Or manually check tokens
cat user/.env
```

### "Tool not found"

```bash
# Ensure environment is sourced
source common/scripts/boot.sh
echo $PM_OS_COMMON  # Should show path
```

---

## Part 7: Key Commands Reference

### PM-OS CLI Commands

| Command | Purpose |
|---------|---------|
| `pm-os init --quick` | Quick setup (~5 min) |
| `pm-os init` | Full guided wizard |
| `pm-os doctor` | Verify installation health |
| `pm-os doctor --fix` | Auto-fix common issues |
| `pm-os setup integrations` | Configure integrations |
| `pm-os brain sync` | Sync brain from integrations |
| `pm-os brain status` | Show brain entity counts |
| `pm-os config show` | Display configuration |
| `pm-os help <topic>` | Get help on a topic |

### Claude Code Slash Commands

| Command | Purpose |
|---------|---------|
| `/boot` | Initialize PM-OS session |
| `/update-context` | Sync daily context from integrations |
| `/create-context` | Full context pipeline (bulk/analyze/write) |
| `/create-context bulk` | Extract 6 months historical data |
| `/meeting-prep` | Generate meeting pre-read |
| `/prd` | Generate PRD with FPF reasoning |
| `/adr` | Create Architecture Decision Record |
| `/rfc` | Create Request for Comments |
| `/sprint-report` | Generate sprint summary from Jira |
| `/session-save` | Save current session |
| `/session-load` | Resume previous session |
| `/brain-load` | Load Brain hot topics |
| `/bd-list` | List Beads issues |
| `/bd-create` | Create Beads issue |
| `/help` | Show all available commands |

---

## Part 8: Architecture Overview

```
pm-os/
├── common/              # LOGIC (shared code) - git: feamando/pmos
│   ├── .claude/commands/   # Slash commands
│   ├── tools/              # Python tools
│   ├── frameworks/         # Document templates
│   ├── schemas/            # Entity schemas (Brain 1.2)
│   └── rules/              # Agent behavior rules
│
└── user/                # CONTENT (your data) - your private repo
    ├── brain/              # Knowledge base
    │   ├── Entities/       # People, teams, domains
    │   ├── Projects/       # Project context
    │   └── registry.yaml   # Entity index
    ├── context/            # Daily context files
    ├── sessions/           # Session persistence
    ├── planning/           # Meeting prep, career planning
    ├── config.yaml         # Your configuration
    └── .env                # Your secrets (never commit!)
```

**Key Principle:** LOGIC updates independently from CONTENT. You can pull updates to `/common` without affecting your personal data in `/user`.

---

## Getting Help

**CLI Help System:**

```bash
pm-os help                 # List all help topics
pm-os help brain           # Brain knowledge graph
pm-os help integrations    # Integration setup
pm-os help troubleshoot    # Troubleshooting guide
pm-os help quick-start     # Getting started
```

**Other Resources:**

- **Slack:** #pmos-slack-channel (for PM-OS users)
- **Documentation:** `common/docs/`
- **Issues:** https://github.com/feamando/pmos/issues

---

*PM-OS v3.3 - AI-powered operating system for product managers*
