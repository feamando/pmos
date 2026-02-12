# PM-OS v3.0 Onboarding Guide for Gemini CLI

**Date:** 2026-01-20
**From:** Claude Code (Mac) to Gemini CLI (Windows)
**Purpose:** Catch you up on ~3 weeks of changes since v2.x

---

## TL;DR - Critical Changes

| What | v2.x (Old) | v3.0 (New) |
|------|-----------|------------|
| **Structure** | Single folder | `common/` + `user/` + `developer/` |
| **Brain location** | `AI_Guidance/Brain/` | `user/brain/` |
| **Commands location** | Root `.claude/` or `.gemini/` | `common/.claude/commands/` |
| **Tools location** | `AI_Guidance/Tools/` | `common/tools/` |
| **Config** | Scattered `.env` | `user/config.yaml` + `user/.env` |
| **New systems** | - | Beads, Confucius, Ralph, FPF/Quint |

---

## 1. Architecture Overview

PM-OS v3.0 uses a **three-folder architecture**:

```
pm-os/                          # Root directory (you boot from here)
├── .pm-os-root                 # Marker file (identifies PM-OS root)
├── common/                     # LOGIC - Shared code (Git: pmos main)
│   ├── .claude/commands/       # 72 slash commands
│   ├── .gemini/commands/       # Gemini commands (sync needed - see below)
│   ├── tools/                  # 67+ Python tools
│   ├── frameworks/             # Document templates
│   ├── schemas/                # Entity schemas (YAML)
│   ├── rules/                  # Agent behavior rules
│   │   └── AI_AGENTS_GUIDE.md  # READ THIS FIRST
│   ├── documentation/          # Full docs
│   ├── scripts/boot.sh         # Bootstrap script
│   ├── AGENT.md                # Agent entry point
│   └── README.md               # Main overview
│
├── user/                       # CONTENT - User data (Git: private repo)
│   ├── brain/                  # Knowledge base
│   │   ├── Entities/           # People, teams, domains
│   │   ├── Projects/           # Project context files
│   │   ├── Experiments/        # A/B tests, flags
│   │   ├── Reasoning/          # FPF cycles and DRRs
│   │   └── registry.yaml       # Entity index
│   ├── context/                # Daily context files
│   ├── sessions/               # Session persistence
│   ├── planning/               # Meeting prep, career planning
│   ├── config.yaml             # Main configuration
│   ├── .env                    # Secrets (API tokens)
│   └── USER.md                 # User persona (was NGO.md)
│
├── developer/                  # DEV TOOLKIT - Optional (Git: pmos/developer)
│   ├── tools/                  # Dev-specific tools
│   │   ├── session/            # Session management, Confucius
│   │   ├── ralph/              # Feature tracking
│   │   ├── quint/              # Evidence decay
│   │   ├── beads/              # Issue tracking hooks
│   │   └── roadmap/            # Roadmap management
│   ├── .claude/commands/       # Dev commands (bd-*, ralph-*, session-*)
│   └── scripts/boot.sh         # Dev bootstrap
│
└── snapshots/                  # Migration backups
```

---

## 2. Git Repository Structure

Three separate Git repositories:

| Folder | Repository | Branch | Purpose |
|--------|------------|--------|---------|
| `common/` | `feamando/pmos` | `main` | Shared logic, commands, tools |
| `developer/` | `feamando/pmos` | `developer` | Dev toolkit (optional) |
| `user/` | Private repo | - | Personal data, brain, config |

**Workflow:**
- Updates to shared logic go to `pmos` main branch
- Developer tools go to `pmos` developer branch
- Your personal data stays in your private repo

---

## 3. First Boot Procedure

### Step 1: Environment Setup

Set environment variables (or let boot.sh detect them):

```bash
export PM_OS_ROOT="/path/to/pm-os"
export PM_OS_COMMON="$PM_OS_ROOT/common"
export PM_OS_USER="$PM_OS_ROOT/user"
export PM_OS_DEVELOPER_ROOT="$PM_OS_ROOT/developer"  # If exists
```

### Step 2: Source Boot Script

```bash
source common/scripts/boot.sh
```

This validates markers and sets up Python paths.

### Step 3: Run Preflight

```bash
python3 common/tools/preflight/preflight_runner.py --quick
```

This verifies all 67+ tools are importable.

### Step 4: Load Core Context

Read these files in order:
1. `common/AGENT.md` - Entry point
2. `common/rules/AI_AGENTS_GUIDE.md` - Operating rules
3. `user/USER.md` - User persona (Jane Smith operations style)

### Step 5: Update Daily Context

```bash
python3 common/tools/daily_context/daily_context_updater.py
```

This syncs from Google Drive, Gmail, Slack, etc.

### Step 6: Load Latest Context

Read: `user/context/YYYY-MM-DD-context.md` (today's date)

### Step 7: Load Hot Topics

```bash
python3 common/tools/brain/brain_loader.py
```

This identifies frequently-mentioned entities.

---

## 4. New Systems You Need to Know

### 4.1 Beads (Issue Tracking)

Hash-based issue tracking integrated with PM-OS.

**Commands:**
- `/bd-create` - Create issue (returns `bd-a1b2` style ID)
- `/bd-list` - List issues by status/priority
- `/bd-ready` - Show ready-for-work issues
- `/bd-show <id>` - View issue details
- `/bd-update <id>` - Update issue
- `/bd-close <id>` - Close issue
- `/bd-prime <id>` - Load issue context into session

**Issue Types:** Epic, Story, Task, Subtask
**Priorities:** P0 (Critical), P1 (High), P2 (Medium), P3 (Low)

**Data Location:** `.beads/` at repository root

### 4.2 Confucius (Note-Taking)

Lightweight session notes for decisions, assumptions, blockers.

**Note Types:**
- `D` - Decision made
- `A` - Assumption (implicit)
- `O` - Observation (fact)
- `B` - Blocker
- `T` - Task/action item

**Commands:**
- `/confucius-status` - View current session notes

**State Location:** `developer/data/.confucius_state.json`

### 4.3 Ralph (Feature Development)

Multi-iteration feature tracking with acceptance criteria.

**Commands:**
- `/ralph-init` - Start new feature with criteria
- `/ralph-status` - Check progress
- `/ralph-specs` - Generate specifications
- `/ralph-loop` - Iteration workflow

**State Location:** `developer/data/.ralph-state.json`

### 4.4 FPF / Quint (First Principles Framework)

Structured reasoning with evidence tracking.

**6-Phase Cycle:**

| Phase | Command | Purpose |
|-------|---------|---------|
| Q0 | `/q0-init` | Initialize bounded context |
| Q1 | `/q1-hypothesize` | Generate competing hypotheses (Abduction) |
| Q2 | `/q2-verify` | Logical verification (Deduction) |
| Q3 | `/q3-validate` | Empirical testing (Induction) |
| Q4 | `/q4-audit` | Calculate trust scores (WLNK) |
| Q5 | `/q5-decide` | Create Design Rationale Record (DRR) |

**Utility Commands:**
- `/q-status` - Show current FPF state
- `/q-decay` - Check evidence freshness
- `/q-reset` - Clear FPF cycle
- `/quint-sync` - Sync to Brain

**Gemini Bridge:**
```bash
python3 "$PM_OS_COMMON/tools/quint/gemini_quint_bridge.py" <command> [args]
```

**Output Location:** `user/brain/Reasoning/`

---

## 5. Command Sync (IMPORTANT)

Gemini commands are currently minimal in `common/.gemini/commands/`.

**Option A:** Copy from Claude commands (they're compatible):
```bash
cp -r common/.claude/commands/*.md common/.gemini/commands/
```

**Option B:** Use the v2.4 snapshot commands:
```bash
cp -r snapshots/snapshot-pre-v3-migration/content/.gemini/commands/*.md common/.gemini/commands/
```

**Option C:** Run command sync tool:
```bash
python3 common/tools/util/command_sync.py
```

---

## 6. Key Configuration Files

### user/config.yaml

```yaml
version: "3.0.0"

user:
  name: "Jane Smith"
  email: "user@example.com"
  position: "Director of Product"
  tribe: "Growth Division"

integrations:
  jira:
    enabled: true
    url: "https://your-company.atlassian.net"
    tracked_projects: ["SE", "GC", "FF"]

  slack:
    enabled: true
    mention_bot_name: "pmos-slack-bot"

  google:
    enabled: true

pm_os:
  fpf_enabled: true
  confucius_enabled: true
  ralph_enabled: true
```

### user/.env

```bash
# Jira
JIRA_API_TOKEN=<token>

# Slack
SLACK_BOT_TOKEN=xoxb-<token>
SLACK_APP_TOKEN=xapp-<token>

# Google OAuth
GOOGLE_CREDENTIALS_PATH=.secrets/credentials.json
GOOGLE_TOKEN_PATH=.secrets/token.json

# Optional: Gemini API for Orthogonal Challenge
GEMINI_API_KEY=<key>
```

---

## 7. Daily Context Structure

Context files live in `user/context/YYYY-MM-DD-context.md`:

```markdown
# Daily Context: 2026-01-20

## Critical Alerts
- [P0 items requiring immediate attention]

## Key Decisions & Updates
- [Decisions made, updates received]

## Blockers & Risks
| Blocker | Owner | Impact | Status |

## Action Items
- [ ] **Owner**: Action description

## Key Dates & Milestones
| Date | Event | Owner |

## Documents Processed
[List of documents synced from integrations]
```

---

## 8. Brain Entity Structure

Entities in `user/brain/` follow this schema:

```yaml
---
id: project-otp
type: project
title: "One-Time Purchase"
status: active
owner: beatrice
created: 2025-11-01
last_updated: 2026-01-19
related:
  - "[[Entities/Squad_Meal_Kit.md]]"
  - "[[Entities/Beatrice.md]]"
---

# One-Time Purchase (OTP)

## Overview
Strategic shift from subscription-only to e-commerce model...

## Current State
- Target: W04+ launch
- Status: Order confirmation email tested 2026-01-17

## Key Decisions
- [Decision log]

## Related Documents
- [Links]
```

---

## 9. Tool Discovery

To see all available tools:

```bash
python3 common/tools/preflight/preflight_runner.py --list
```

**Key Tool Categories:**
- `tools/integrations/` - Jira, GitHub, Slack, Google, Confluence, Statsig
- `tools/brain/` - Entity management, hot topics
- `tools/daily_context/` - Context sync and synthesis
- `tools/quint/` - FPF reasoning
- `tools/session/` - Session management
- `tools/ralph/` - Feature tracking
- `tools/beads/` - Issue tracking
- `tools/preflight/` - Tool validation

---

## 10. What's in the Snapshots

`snapshots/` contains pre-migration backups:

- `snapshot-pre-v3-migration/` - Full v2.4 state
- `pre-restructure-20260113-085844/` - Earlier backup

You can reference these for any v2.4 patterns or data that didn't migrate correctly.

---

## 11. Current State Summary (2026-01-20)

**Active Projects:**
- Meal Kit OTP - W04+ target
- Growth Platform - Shopify launch, tax issues
- Accessibility 2026 - Web 33%, Mobile 15%

**Pending Actions:**
- Factor Canada Shopify setup
- Maria promo template
- StatSig one-pager to Aurora

**Hot Topics (from Brain):**
- Growth_Platform (6 mentions)
- otp (2 mentions)
- Meal Kit squad
- Beatrice (PM)

---

## 12. Quick Reference: Most Used Commands

| Command | Purpose |
|---------|---------|
| `/boot` | Initialize PM-OS |
| `/update-context` | Sync daily context |
| `/session-save` | Save session for later |
| `/session-load` | Resume session |
| `/prd` | Generate PRD |
| `/meeting-notes` | Structure meeting notes |
| `/bd-list` | List Beads issues |
| `/q-status` | Show FPF state |
| `/preflight` | Validate tools |

---

## 13. Troubleshooting

**"Tool not found":**
```bash
export PYTHONPATH="$PM_OS_COMMON/tools:$PYTHONPATH"
```

**"Config not found":**
- Ensure `user/config.yaml` exists
- Check `.pm-os-root` marker in root

**"Permission error on Google sync":**
```bash
python3 common/tools/integrations/google_scope_validator.py --fix
```

**Commands not showing:**
- Run command sync: `python3 common/tools/util/command_sync.py`
- Check `.gemini/commands/` has `.md` files

---

## 14. Files to Read on First Boot

1. **This document** - `common/GEMINI_ONBOARDING.md`
2. **Agent rules** - `common/rules/AI_AGENTS_GUIDE.md`
3. **User persona** - `user/USER.md` (NGO style guide)
4. **Today's context** - `user/context/2026-01-XX-context.md`

---

## 15. Next Steps

1. Run `/boot` or `/boot --quick`
2. Read the daily context
3. Check `/bd-list` for any open issues
4. Resume any pending work from last session with `/session-load`

Welcome back!

---

*Generated by Claude Code (Opus 4.5) on 2026-01-20*
*For PM-OS v3.0 | Gemini CLI Onboarding*
