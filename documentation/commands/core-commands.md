# Core Commands

> Essential commands for PM-OS session management and initialization

## /boot

Initialize PM-OS environment and load context.

### Arguments

| Argument | Description |
|----------|-------------|
| (none) | Full boot with all features |
| `--quick` | Fast startup - skip context update, preflight, meeting prep |
| `--quiet` | Skip Slack notifications |

### What It Does

1. **Sync Developer Commands** - Auto-sync commands from developer/ if present
2. **Pre-Flight Checks** - Verify all tools working (unless --quick)
3. **Validate OAuth** - Check Google scopes (unless --quick)
4. **Update Daily Context** - Fetch from integrations (unless --quick)
5. **Load Brain Hot Topics** - Brain entities from context
6. **Brain Enrichment** - Run quick density boost (unless --quick)
7. **Start Confucius Session** - Initialize session notes
8. **Capture Roadmap Items** - From Slack mentions (unless --quick)
9. **Generate Meeting Pre-reads** - Upcoming meetings (unless --quick)
10. **Post to Slack** - Boot summary (unless --quiet)

### Usage

```
/boot              # Full boot
/boot --quick      # Fast startup
/boot --quiet      # Skip Slack posting
```

---

## /logout

End PM-OS session and clean up state.

### Arguments

None

### What It Does

1. Archives active session
2. Clears session state
3. Optionally syncs unsaved changes
4. Reports session summary

### Usage

```
/logout
```

---

## /update-context

Sync daily context from external integrations.

### Arguments

| Argument | Description |
|----------|-------------|
| `full` | All sources: GDocs, Slack, Gmail (default) |
| `quick` | GDocs only |
| `no-fetch` | Synthesize from existing raw data |
| `gdocs` | Only Google Docs |
| `slack` | Only Slack messages |
| `jira` | Include Jira sync |

### What It Does

1. Fetches data from configured integrations
2. Synthesizes into structured context file
3. Creates versioned context if today's exists
4. Posts summary to Slack

### Output

Creates `user/context/YYYY-MM-DD-context.md` with:
- Critical Alerts
- Key Decisions & Updates
- Blockers & Risks
- Action Items
- Key Dates

### Usage

```
/update-context           # Full update
/update-context quick     # Fast - GDocs only
/update-context jira      # Include Jira
```

---

## /create-context

Consolidated context creation pipeline - extract, analyze, and write to Brain.

### Arguments

**Modes:**

| Mode | Description |
|------|-------------|
| `full` | Complete pipeline: extract + analyze + write + load (default) |
| `quick` | Fast refresh: GDocs + Jira only, no LLM analysis |
| `bulk` | Bulk historical extraction (6 months, resumable) |
| `preprocess` | Chunk large files (> 1500 lines) for processing |
| `extract` | Extract only from all sources |
| `analyze` | Analyze only (requires prior extraction) |
| `write` | Write to Brain only (requires prior analysis) |
| `load` | Load hot topics only |
| `status` | Show pipeline status |

**Flags:**

| Flag | Description |
|------|-------------|
| `-Sources` | Comma-separated: gdocs,jira,github,slack,statsig |
| `-Days` | Lookback period (default: 7 for daily, 180 for bulk) |
| `-EnrichMode` | quick, full, external, or skip (default: quick) |
| `-DryRun` | Preview without changes |
| `-NoPull` | Skip git pull |
| `-NoWrite` | Extract and analyze but don't write |

### What It Does

1. **EXTRACT** - Fetch from GDocs, Jira, GitHub, Slack, Statsig
2. **PREPROCESS** - Chunk large files for LLM processing
3. **ANALYZE** - Run batch LLM analysis
4. **WRITE** - Write entities to Brain
5. **ENRICH** - Run brain enrichment (body text, relationships)
6. **LOAD** - Load hot topics, build synapse

### Usage

```
/create-context              # Full pipeline
/create-context quick        # Fast - GDocs + Jira only
/create-context bulk         # Historical extraction
/create-context status       # Check pipeline state
/create-context extract -Sources "jira,github" -NoPull
```

---

## /session-save

Save current session for persistence.

### Arguments

| Argument | Description |
|----------|-------------|
| `"Title"` | Create new session with title |
| `--log "entry"` | Add work log entry |
| `--decision "d|r|a"` | Record decision with rationale |
| `--question "q"` | Add open question |

### What It Does

1. Checks for active session
2. Creates or updates session file
3. Records files touched, decisions, work log
4. Stores in `user/sessions/`

### Session File Contents

```yaml
session_id: 2026-01-13-001
title: Session Title
started: ISO timestamp
status: active
tags: [tag1, tag2]
files_created: [...]
decisions: [...]
```

### Usage

```
/session-save                           # Update current
/session-save "Feature Development"     # Create new
/session-save --log "Completed phase 1"
```

---

## /session-load

Resume a previous session.

### Arguments

| Argument | Description |
|----------|-------------|
| `session-id` | Specific session to load |
| None | List recent sessions |

### What It Does

1. If ID provided, loads specific session
2. If no ID, lists recent sessions for selection
3. Restores context and state
4. Marks session as active

### Usage

```
/session-load                    # List and select
/session-load 2026-01-12-003    # Load specific
```

---

## /session-status

Show current session status.

### Arguments

None

### What It Does

Displays:
- Active session ID and title
- Start time and duration
- Files touched
- Decisions made
- Open questions

### Usage

```
/session-status
```

---

## /session-search

Search across saved sessions.

### Arguments

| Argument | Description |
|----------|-------------|
| `query` | Search term |
| `--tag` | Filter by tag |
| `--date` | Filter by date range |

### What It Does

1. Searches session titles and content
2. Returns matching sessions
3. Shows context snippets

### Usage

```
/session-search "payment"
/session-search --tag payments --date 2026-01
```

---

## /brain-load

Load Brain entities into context.

### Arguments

| Argument | Description |
|----------|-------------|
| `entity-type` | person, team, project, etc. |
| `entity-id` | Specific entity ID |

### What It Does

1. Locates entity in Brain
2. Loads full entity content
3. Makes available in current context

### Usage

```
/brain-load person alice_smith
/brain-load project payment_gateway
```

---

## /update-3.0

Migrate from PM-OS v2.4 to v3.0.

### Arguments

None

### What It Does

1. Backs up current structure
2. Creates two-repo architecture
3. Moves content to `user/`
4. Updates paths and imports

### Usage

```
/update-3.0
```

---

## /revert-2.4

Rollback to PM-OS v2.4 structure.

### Arguments

None

### What It Does

1. Restores v2.4 directory structure
2. Merges user content back
3. Updates path references

### Usage

```
/revert-2.4
```

---

## /push

Publish PM-OS components to repositories.

### Arguments

| Argument | Description |
|----------|-------------|
| `all` | Push all enabled targets (default) |
| `common` | Push common only (via PR) |
| `brain` | Push brain only (direct) |
| `user` | Push user only (direct) |
| `--dry-run` | Preview without pushing |
| `--status` | Show push status only |

### What It Does

- **common**: Creates PR to feamando/pmos (via branch + gh pr create)
- **brain**: Direct push to personal brain repo
- **user**: Direct push to personal user repo

### Usage

```
/push                 # Push all enabled
/push common          # PR to pmos
/push --dry-run       # Preview changes
/push --status        # Show last push info
```

---

## /brain-enrich

Run Brain quality improvement tools.

### Arguments

| Argument | Description |
|----------|-------------|
| `--mode` | full, quick, report, boot |
| `--quick` | Shortcut for --mode quick |
| `--report` | Shortcut for --mode report |
| `--dry-run` | Preview without changes |

### Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `full` | All tools, apply changes | Weekly maintenance |
| `quick` | Soft edges only | Quick density boost |
| `report` | Analysis only, no changes | Status check |
| `boot` | Minimal, fast checks | Boot-time integration |

### What It Does

1. Analyze baseline graph health
2. Run soft edge inference (by entity type)
3. Scan for relationship staleness
4. Generate extraction hints
5. Report density improvements

### Usage

```
/brain-enrich              # Full enrichment
/brain-enrich --quick      # Fast density boost
/brain-enrich --report     # Analysis only
```

---

## /export-to-spec

Export a PRD to spec-machine input format.

### Arguments

| Argument | Description |
|----------|-------------|
| `prd-path` | Path to PRD file (required) |
| `--repo` | Target repo alias (e.g., mobile-rn) |
| `--spec-name` | Name for spec folder |
| `--subdir` | Spec subdirectory |

### What It Does

1. Parses PRD sections (Purpose, Problem, Solution, etc.)
2. Generates Q&A format requirements
3. Creates spec folder structure in target repo
4. Injects tech stack context from target repo

### Output

Creates in target repo:
- `spec-machine/specs/{date}-{name}/planning/initialization.md`
- `spec-machine/specs/{date}-{name}/planning/requirements.md`

### Usage

```
/export-to-spec path/to/prd.md --repo mobile-rn
/export-to-spec path/to/prd.md --spec-name user-auth --repo web
```

---

## /preflight

Run system verification checks.

### Arguments

| Argument | Description |
|----------|-------------|
| `--quick` | Import tests only (fast) |
| `--category` | Check specific category (core, brain, integrations, etc.) |
| `--json` | Output as JSON |

### What It Does

1. Verifies all tool modules import correctly (88+ tools)
2. Checks required classes and functions exist
3. Validates configuration and environment variables
4. Reports system health status

### Categories

| Category | Tools |
|----------|-------|
| core | Config, path resolution, entity validation |
| brain | Brain loading, updating, writing |
| integrations | Jira, GitHub, Slack, Google, Confluence |
| session | Confucius agent, session manager |
| quint | FPF/Quint reasoning tools |

### Usage

```
/preflight              # Full check
/preflight --quick      # Fast - imports only
/preflight --category core
/preflight --json       # Machine-readable output
```

---

## Related Documentation

- [Workflows](../04-workflows.md) - Daily usage patterns
- [Architecture](../02-architecture.md) - System structure
- [Session Tools](../tools/session-tools.md) - Underlying tools
- [Developer Commands](developer-commands.md) - Beads, roadmap, dev utilities

---

*Last updated: 2026-02-02*
