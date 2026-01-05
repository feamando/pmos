# Update Context

Run the daily context updater to pull recent Google Docs and synthesize into a context file.

## Arguments

The command accepts optional arguments:

- `full` - Full update: fetch from all sources (GDocs, Gmail, Slack) **[default]**
- `quick` - Quick update: GDocs only, skip Slack and Gmail
- `no-fetch` - Skip external fetching, just synthesize from existing raw data
- `gdocs` - Fetch only Google Docs
- `slack` - Fetch only Slack messages
- `jira` - Include Jira sync

**Examples:**
```
/update-context          # Full update from all sources
/update-context quick    # Fast - GDocs only
/update-context no-fetch # Synthesize existing data without fetching
/update-context jira     # Include Jira sync with GDocs
```

## Instructions

### Step 1: Fetch External Data

**Skip if:** `no-fetch` argument provided.

Execute the daily context updater script:

```bash
# Full update (default)
python3 AI_Guidance/Tools/daily_context/daily_context_updater.py

# Quick update (GDocs only)
python3 AI_Guidance/Tools/daily_context/daily_context_updater.py --quick

# With Jira sync
python3 AI_Guidance/Tools/daily_context/daily_context_updater.py --jira
```

### Step 2: Analyze Raw Output

Review the raw document output from the updater. The script outputs:
- Document index with titles and links
- Email index with subjects and senders
- Slack message index with channels
- Full document contents (may be truncated for large files)

### Step 3: Synthesize Context

Create or update `AI_Guidance/Core_Context/YYYY-MM-DD-context.md` following NGO format:

**Required sections:**
- **Critical Alerts** - Urgent items requiring attention
- **Key Decisions & Updates** - Organized by project/workstream
- **Blockers & Risks** - Tables with impact and owner
- **Action Items** - Checkbox format with owners
- **Key Dates & Milestones** - Timeline table
- **Documents Processed** - Table with links

**Style guidelines:**
- Bullet points over prose
- Bold for emphasis on names, statuses, blockers
- Explicit owners for all action items
- ISO dates (YYYY-MM-DD)
- Status tags: (P0), (Critical), (In Progress), (Planned WNN)

### Step 4: Version Management

If a context file already exists for today:
1. Check for existing `YYYY-MM-DD-NN-context.md` versions
2. Create the next increment (e.g., `-02` exists → create `-03`)
3. Merge with previous version, retaining unresolved blockers/decisions

## Options Reference

| Option | Effect |
|--------|--------|
| `--dry-run` | Preview which docs would be fetched |
| `--force --days N` | Override last-run and pull last N days |
| `--quick` | GDocs only, skip Slack/Gmail |
| `--jira` | Include Jira squad sync |
| `--upload FILE` | Upload context file to GDrive |

## Execute

Run the context updater with the specified options. Synthesize the raw data into structured context following NGO format.
