# Create Context Pipeline

Consolidated context creation pipeline that extracts, analyzes, and populates the Brain with data from all external sources.

## Overview

This command runs the master `create-context.ps1` orchestration script which consolidates:
- **GDocs/Gmail** extraction (daily_context_updater.py)
- **Jira** extraction (jira_brain_sync.py)
- **GitHub** extraction (github_brain_sync.py)
- **Slack** extraction (slack_bulk_extractor.py)
- **Statsig** extraction (statsig_brain_sync.py)
- **LLM Analysis** (batch_llm_analyzer.py)
- **Brain Writing** (unified_brain_writer.py)
- **Hot Topics Loading** (brain_loader.py)
- **Synapse Building** (synapse_builder.py)

## Arguments

The command accepts optional arguments:

**Modes:**
- `full` - Run complete pipeline (extract + preprocess + analyze + write + load) **[default]**
- `quick` - Quick refresh (GDocs + Jira only, no LLM analysis)
- `bulk` - **Bulk historical extraction (6 months, resumable)**
- `preprocess` - **Chunk large files (> 1500 lines) for processing**
- `extract` - Extract only from all sources
- `analyze` - Analyze only (requires prior extraction)
- `write` - Write to Brain only (requires prior analysis)
- `load` - Load hot topics only
- `status` - Show status of all components

**Flags:**
- `-Sources <list>` - Comma-separated: gdocs,jira,github,slack,statsig
- `-Days <N>` - Lookback period (default: 7 for daily, 180 for bulk)
- `-SlackTier <tier>` - tier1, tier2, tier3, or all (default: tier1)
- `-Summarize` - Include LLM summaries
- `-DryRun` - Preview without changes
- `-NoPull` - Skip git pull before running (useful offline or to avoid conflicts)
- `-NoWrite` - Extract and analyze but don't write to Brain

**Examples:**
```
/create-context              # Full pipeline
/create-context quick        # Fast - GDocs + Jira only
/create-context status       # Check pipeline state
/create-context extract -NoPull -Sources "jira,github"  # Extract specific sources offline
```

## Instructions

### Step 1: Determine Mode

Based on the user's request or argument, determine which mode to run:

| Scenario | Mode | Command |
|----------|------|---------|
| Full Brain refresh | full | `pwsh create-context.ps1 -Mode full` |
| Quick daily update | quick | `pwsh create-context.ps1 -Mode quick` |
| **6-month historical extraction** | bulk | `pwsh create-context.ps1 -Mode bulk` |
| Extract new data only | extract | `pwsh create-context.ps1 -Mode extract` |
| Check pipeline status | status | `pwsh create-context.ps1 -Mode status` |
| Specific sources only | extract | `pwsh create-context.ps1 -Mode extract -Sources "jira,github"` |
| Bulk Slack only (3 months) | bulk | `pwsh create-context.ps1 -Mode bulk -Sources "slack" -Days 90` |

### Step 2: Execute Pipeline

Run the appropriate command based on the determined mode.

**For full pipeline:**
```bash
pwsh create-context.ps1 -Mode full -Summarize
```

**For quick refresh:**
```bash
pwsh create-context.ps1 -Mode quick
```

**For bulk historical (6 months):**
```bash
pwsh create-context.ps1 -Mode bulk
```

**For bulk specific sources (e.g., 3 months Slack):**
```bash
pwsh create-context.ps1 -Mode bulk -Sources "slack" -Days 90 -SlackTier all
```

**For status check:**
```bash
pwsh create-context.ps1 -Mode status
```

**For specific sources:**
```bash
pwsh create-context.ps1 -Mode extract -Sources "jira,github" -Days 3
```

### Step 3: Monitor Progress

The script outputs progress indicators for each phase:
1. **Extraction** - Data pulled from external sources
2. **Analysis** - LLM processes raw data (unless quick mode)
3. **Brain Writing** - Entities/projects updated in Brain
4. **Load** - Hot topics identified

Watch for:
- `[OK]` - Step completed successfully
- `[FAIL]` - Step failed (check error message)
- `[SKIP]` - Step skipped (by flag or missing dependency)

### Step 4: Report Results

After pipeline completes, summarize:
- Sources processed
- Duration
- Entities created/updated
- Any failures that need attention

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    create-context.ps1                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐    │
│  │ EXTRACTION  │  │   ANALYSIS   │  │    BRAIN WRITING    │    │
│  ├─────────────┤  ├──────────────┤  ├─────────────────────┤    │
│  │ GDocs       │  │              │  │ unified_brain_      │    │
│  │ Gmail       │──│ batch_llm_   │──│ writer.py           │    │
│  │ Jira        │  │ analyzer.py  │  │                     │    │
│  │ GitHub      │  │              │  │ synapse_builder.py  │    │
│  │ Slack       │  │ (Bedrock/    │  │                     │    │
│  │ Statsig     │  │  Claude)     │  │                     │    │
│  └─────────────┘  └──────────────┘  └─────────────────────┘    │
│         │                │                    │                 │
│         ▼                ▼                    ▼                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Brain/Inbox/                          │   │
│  │  GDocs/*.json  Slack/Raw/*.json  Jira/*.md  GitHub/*.md  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                       Brain/                             │   │
│  │  Entities/  Projects/  Reasoning/Decisions/  Synapses/   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    LOAD PHASE                            │   │
│  │         brain_loader.py --reasoning                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Modes Reference

### Full Mode (default)
Runs complete pipeline. Best for:
- Weekly Brain refresh
- After extended absence
- Major data sync needed

```bash
pwsh create-context.ps1 -Mode full -Days 7 -Summarize
```

### Bulk Mode (Historical)
**6-month bulk extraction with resumability.** Best for:
- Initial Brain population
- Rebuilding context after data loss
- Deep historical analysis
- Large-scale Slack/Jira extraction

```bash
# Extract 6 months of all sources
pwsh create-context.ps1 -Mode bulk

# Extract 3 months of specific sources
pwsh create-context.ps1 -Mode bulk -Sources "slack,jira" -Days 90

# Extract all Slack tiers
pwsh create-context.ps1 -Mode bulk -Sources "slack" -SlackTier all -Days 180
```

**Features:**
- **Resumable:** Re-run to continue interrupted extraction
- **Week-by-week:** Slack extracts in weekly batches with state tracking
- **Rate-limited:** Respects API limits with automatic backoff
- **Parallel:** Jira/GitHub fetch squads in parallel

**After bulk extraction:**
```bash
# Run LLM analysis on extracted data
pwsh create-context.ps1 -Mode analyze

# Write analyzed data to Brain
pwsh create-context.ps1 -Mode write
```

### Preprocess Mode (File Chunking)
**Scan and chunk files exceeding 1500 lines.** Best for:
- Preparing large inbox files for LLM analysis
- Fixing "file too large" errors
- Manual chunking of specific directories

```bash
# Chunk all large files in inbox
pwsh create-context.ps1 -Mode preprocess

# Check what would be chunked (dry run)
pwsh create-context.ps1 -Mode preprocess -DryRun
```

**Standalone chunker usage:**
```bash
# Check if a file needs chunking
python3 "$PM_OS_COMMON/tools/util/file_chunker.py" --check <FILE>

# Split a large file
python3 "$PM_OS_COMMON/tools/util/file_chunker.py" --split <FILE>

# Scan directory for large files
python3 "$PM_OS_COMMON/tools/util/file_chunker.py" --scan $PM_OS_USER/brain/Inbox
```

**Output:** Chunks are written to a `chunks/` subdirectory with metadata headers.

### Quick Mode
Fast refresh without LLM analysis. Best for:
- Daily boot
- Quick status check
- When LLM quota is limited

```bash
pwsh create-context.ps1 -Mode quick
```

### Extract Mode
Extract only, no processing. Best for:
- Daily data gathering
- When running analysis separately
- Debugging extraction issues

```bash
pwsh create-context.ps1 -Mode extract -Sources "slack" -Days 30
```

### Status Mode
Check pipeline state without running. Best for:
- Verifying extraction completeness
- Checking Brain writer state
- Debugging issues

```bash
pwsh create-context.ps1 -Mode status
```

## Output Locations

| Phase | Output Location |
|-------|-----------------|
| GDocs Raw | `Brain/Inbox/GDocs/` |
| Slack Raw | `Brain/Inbox/Slack/Raw/` |
| Jira Raw | `Brain/Inbox/JIRA_YYYY-MM-DD.md` |
| GitHub Raw | `Brain/Inbox/GITHUB_YYYY-MM-DD.md` |
| Analyzed | `Brain/Inbox/*/Analyzed/` |
| Entities | `Brain/Entities/` |
| Projects | `Brain/Projects/` |
| Decisions | `Brain/Reasoning/Decisions/` |

## Execute

Run the pipeline with the specified mode. Report progress and final status to the user.
