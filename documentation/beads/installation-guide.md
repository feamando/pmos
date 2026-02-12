# Beads Installation Guide

> **Purpose:** Step-by-step guide to install and configure Beads issue tracking for PM-OS projects.

---

## Overview

Beads is a Git-backed, distributed issue tracker designed for AI-agent workflows. It provides:

- **Hash-based IDs** (e.g., `bd-a1b2`) that prevent merge conflicts
- **Hierarchical issues**: Epics → Tasks → Subtasks
- **JSONL storage** that integrates with Git version control
- **JSON output** optimized for LLM consumption

PM-OS extends Beads with automatic integrations for Confucius, FPF, and Ralph loops.

---

## Prerequisites

Before installing, ensure you have:

| Requirement | Minimum Version | Check Command |
|-------------|-----------------|---------------|
| Git | 2.x | `git --version` |
| Python | 3.10+ | `python3 --version` |
| Node.js/npm OR Homebrew OR Go | Any recent | `npm --version` / `brew --version` / `go version` |

---

## Installation Steps

### Step 1: Install the bd CLI

Choose one of three installation methods:

#### Option A: npm (Recommended)

```bash
npm install -g beads-cli
```

#### Option B: Homebrew (macOS)

```bash
brew install steveyegge/beads/bd
```

#### Option C: Go

```bash
go install github.com/steveyegge/beads/cmd/bd@latest
```

**Verify installation:**

```bash
bd --version
```

### Step 2: Initialize Beads in Your Project

Navigate to your project root (where `.git` exists):

```bash
cd /path/to/your/project
bd init
```

This creates a `.beads/` directory with:

```
.beads/
├── issues.jsonl    # Git-tracked issue database
├── beads.db        # Local SQLite cache (gitignored)
└── config.yaml     # Project configuration
```

**For team projects:**

```bash
bd init --team
```

### Step 3: Configure Git

Add to your `.gitignore`:

```gitignore
# Beads local files
.beads/beads.db
.beads/bd.sock
.beads/daemon.log
.beads/.fpf_trigger.json
```

**Important:** Do NOT ignore `.beads/issues.jsonl` - this is the shared issue database.

### Step 4: PM-OS Integration Setup

If using PM-OS developer toolkit:

```bash
# Source PM-OS environment
source /path/to/pm-os/developer/scripts/boot.sh

# Verify beads tools
python3 "$PM_OS_DEVELOPER_ROOT/tools/beads/beads_wrapper.py" --help
```

### Step 5: (Optional) Claude Code Integration

Install hooks for automatic context injection:

```bash
bd setup claude --project
```

This adds hooks that run `bd prime` on session start.

---

## PM-OS Slash Commands

After installation, you have access to these commands:

| Command | Description |
|---------|-------------|
| `/bd-create "Title"` | Create a new issue |
| `/bd-ready` | List issues ready to work on |
| `/bd-list` | List all issues |
| `/bd-show bd-XXXX` | Show issue details |
| `/bd-update bd-XXXX` | Update an issue |
| `/bd-close bd-XXXX` | Close an issue |
| `/bd-prime` | Load context for LLM |

---

## Quick Start Example

```bash
# Create an epic
/bd-create "User Authentication System" --type epic --priority 0

# Create tasks under the epic
/bd-create "Add login form" --parent bd-a3f8
/bd-create "Add logout button" --parent bd-a3f8
/bd-create "Password reset flow" --parent bd-a3f8

# See what's ready
/bd-ready

# Work on a task, then close it
/bd-close bd-a3f8.1 --rationale "Login form implemented with validation"
```

---

## Troubleshooting

### "bd: command not found"

- Ensure the installation completed successfully
- Check your PATH includes the installation directory
- Try restarting your terminal

### "Not a beads repository"

- Run `bd init` in your project root
- Ensure you're in a directory with `.git` or `.beads`

### "Permission denied" on .beads/

```bash
chmod -R u+rw .beads/
```

### Integration not working

1. Check PM-OS environment is sourced:
   ```bash
   echo $PM_OS_DEVELOPER_ROOT
   ```

2. Run preflight check:
   ```bash
   python3 "$PM_OS_DEVELOPER_ROOT/tools/preflight/preflight_runner.py" --category beads
   ```

---

## Upgrading

### Upgrade bd CLI

```bash
# npm
npm update -g beads-cli

# Homebrew
brew upgrade bd

# Go
go install github.com/steveyegge/beads/cmd/bd@latest
```

### Upgrade PM-OS Integration

Pull latest PM-OS changes:

```bash
cd /path/to/pm-os
git pull origin main
```

---

## Related Documentation

- [Beads User Guide](./user-guide.md) - Daily workflow commands
- [Beads Integration Guide](./integration-guide.md) - Confucius, FPF, Ralph integration
- [Official Beads Documentation](https://github.com/steveyegge/beads/tree/main/docs)

---

*Last Updated: 2026-01-19*
*PM-OS v3.0 - Beads Integration*
