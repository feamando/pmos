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

### Step 0: Ensure Confucius Session Active

Before fetching data, ensure a Confucius note-taking session is active:

```bash
python3 "$PM_OS_COMMON/tools/session/confucius_agent.py" --ensure "Daily Work Session"
```

This will:
- Handle any stale sessions (>24h old) by auto-closing them
- Continue an existing active session if present
- Start a new session if none exists

### Step 1: Fetch External Data

**Skip if:** `no-fetch` argument provided.

Execute the daily context updater script:

```bash
# Full update (default)
python3 "$PM_OS_COMMON/tools/daily_context/daily_context_updater.py"

# Quick update (GDocs only)
python3 "$PM_OS_COMMON/tools/daily_context/daily_context_updater.py" --quick

# With Jira sync
python3 "$PM_OS_COMMON/tools/daily_context/daily_context_updater.py" --jira
```

### Step 1.5: Capture Mention Tasks

**Skip if:** `quick` or `no-fetch` argument provided.

Poll for @mention bot tasks to ensure pending tasks are included in context:

```bash
python3 "$PM_OS_COMMON/tools/slack/slack_mention_handler.py" --lookback 48
```

This captures any @pmos-slack-bot (or configured mention bot) tasks from the last 48 hours and updates the mention state. The daily_context_updater will include these in the output via the `format_mentions_for_daily_context()` integration.

**Note:** If you want to also check for completed tasks (via reactions or "DONE" replies):
```bash
python3 "$PM_OS_COMMON/tools/slack/slack_mention_handler.py" --check-complete
```

### Step 1.6: Generate Meeting Pre-Reads

**Skip if:** `quick` or `no-fetch` argument provided.

Generate pre-reads for upcoming meetings and link them to calendar events:

```bash
python3 "$PM_OS_COMMON/tools/meeting/meeting_prep.py" --upload
```

This will:
- Fetch meetings in the next 24 hours
- Generate personalized pre-reads using Brain context
- Upload pre-reads to Google Drive
- **Append pre-read links to calendar event descriptions**

To preview without generating:
```bash
python3 "$PM_OS_COMMON/tools/meeting/meeting_prep.py" --list
```

### Step 1.7: Capture Roadmap Items

**Skip if:** `quick` or `no-fetch` argument provided.

Capture PM-OS feature requests and bugs to the roadmap inbox:

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/roadmap/roadmap_inbox_manager.py" --capture
```

This captures items classified as `pmos_feature` or `pmos_bug` from mentions_state.json. Each captured item:
- Gets a temp ID (tmp-XXXX)
- Posts to the original Slack thread: "captured to temp inbox with tmp.id X"
- Appears in `/common/data/roadmap/tmp-roadmap-inbox.md`

To parse and enrich captured items, run `/parse-roadmap-inbox`.

### Step 1.8: Master Sheet Sync & Daily Planning

Sync priorities from the Google Sheets Master Sheet and generate daily plan:

```bash
# Sync master sheet data
python3 "$PM_OS_COMMON/tools/master_sheet/master_sheet_sync.py"

# Generate context sections (capture output for Step 3)
python3 "$PM_OS_COMMON/tools/master_sheet/master_sheet_context_integrator.py"
```

**Output includes:**
- Critical alerts (overdue, due today/tomorrow)
- Suggested daily plan with workload distribution
- Action items organized by timeline
- Master Sheet summary tables

**Daily Plan Logic:**
- Items are distributed across Mon-Fri based on deadlines
- Overdue items are scheduled for today (highest priority)
- P0 items are prioritized within each day
- Maximum 5 items per day to avoid overload
- Week-at-a-glance shows planned workload

**Filter by owner:**
```bash
python3 "$PM_OS_COMMON/tools/master_sheet/master_sheet_context_integrator.py" --owner "Nikita"
```

### Step 2: Analyze Raw Output

Review the raw document output from the updater. The script outputs:
- Document index with titles and links
- Email index with subjects and senders
- Slack message index with channels
- Full document contents (may be truncated for large files)

### Step 3: Synthesize Context

Create or update `$PM_OS_USER/personal/context/YYYY-MM-DD-context.md` following NGO format:

**Required sections (in order):**
1. **Critical Alerts** - From Master Sheet: overdue items, due today/tomorrow
2. **Today's Schedule** - Calendar events for today
3. **Suggested Daily Plan** - From Master Sheet integrator: today's focus, week preview
4. **Master Sheet Summary** - Tables: overdue, due today, due tomorrow, due this week
5. **Recent Documents** - From GDocs fetch
6. **Sprint Focus** - Current sprint priorities (if Jira sync ran)
7. **Blockers & Risks** - Tables with impact and owner
8. **Action Items** - Master Sheet items as checkboxes, organized by timeline:
   - Immediate (overdue)
   - Today
   - Tomorrow
   - This Week
9. **Key Dates & Milestones** - Timeline table
10. **Pending Slack Mention Tasks** - From mention handler

**Master Sheet Integration:**
- Copy Critical Alerts section from integrator output
- Include Suggested Daily Plan section
- Include Master Sheet Summary tables
- Merge Action Items with any additional items from documents

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

### Step 5: Post Context to Slack

Post context highlights to Slack channel `#pmos-slack-channel` (CXXXXXXXXXX):

```bash
python3 "$PM_OS_COMMON/tools/slack/slack_context_poster.py" $PM_OS_USER/context/YYYY-MM-DD-context.md --type update
```

Replace `YYYY-MM-DD` with the actual context file created/updated.

**Posted summary includes:**
- Critical Alerts
- Open Action Items (with owners)
- Active Blockers
- Upcoming Key Dates

**Skip if:** Slack token not configured or posting fails (non-blocking).

### Step 5.5: Regenerate Brain Index

Regenerate the compressed entity index with updated hot topics from the new context:

```bash
python3 "$PM_OS_COMMON/tools/brain/brain_index_generator.py"
```

Then re-read the updated index into context:
```
Read: user/brain/BRAIN.md
```

**Skip if:** Generator fails (non-blocking).

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
