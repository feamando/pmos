# Integration Tools

> Tools for syncing with external services

## Jira Integration

### jira_brain_sync.py

Sync Jira data to Brain.

**Location:** `common/tools/integrations/jira_brain_sync.py`

**CLI Usage:**
```bash
python3 jira_brain_sync.py                          # Sync all configured projects
python3 jira_brain_sync.py --squad "Platform Team"  # Specific squad
python3 jira_brain_sync.py --summarize              # Include AI summary
```

**Python API:**
```python
from integrations.jira_brain_sync import sync_jira, get_sprint_status

# Full sync
results = sync_jira()

# Get sprint status
sprint = get_sprint_status(project_key="PLAT")
```

**Output:**
- `brain/inbox/JIRA_YYYY-MM-DD.md` - Raw data
- Updates to `brain/entities/team/*.yaml`

---

### jira_bulk_extractor.py

Extract bulk Jira data for analysis.

**Location:** `common/tools/integrations/jira_bulk_extractor.py`

**CLI Usage:**
```bash
python3 jira_bulk_extractor.py --project PLAT --days 30
python3 jira_bulk_extractor.py --jql "assignee = currentUser()"
```

---

## GitHub Integration

### github_brain_sync.py

Sync GitHub activity to Brain.

**Location:** `common/tools/integrations/github_brain_sync.py`

**CLI Usage:**
```bash
python3 github_brain_sync.py                       # Sync all repos
python3 github_brain_sync.py --repo platform-api   # Specific repo
python3 github_brain_sync.py --analyze-files       # Include file analysis
```

**Python API:**
```python
from integrations.github_brain_sync import sync_github, get_open_prs

# Full sync
results = sync_github()

# Get open PRs
prs = get_open_prs(repo="platform-api")
```

---

### github_commit_extractor.py

Extract commit history for analysis.

**Location:** `common/tools/integrations/github_commit_extractor.py`

**CLI Usage:**
```bash
python3 github_commit_extractor.py --repo platform-api --since 2026-01-01
```

---

## Confluence Integration

### confluence_brain_sync.py

Sync Confluence pages to Brain.

**Location:** `common/tools/integrations/confluence_brain_sync.py`

**CLI Usage:**
```bash
python3 confluence_brain_sync.py --space TNV
python3 confluence_brain_sync.py --page 123456
python3 confluence_brain_sync.py --recent
```

**Python API:**
```python
from integrations.confluence_brain_sync import sync_confluence, get_page

# Sync space
results = sync_confluence(space="TNV")

# Get specific page
page = get_page(page_id="123456")
```

---

## Slack Integration

### slack_context_poster.py

Post context summaries to Slack.

**Location:** `common/tools/slack/slack_context_poster.py`

**CLI Usage:**
```bash
python3 slack_context_poster.py context.md --type boot
python3 slack_context_poster.py context.md --type update
python3 slack_context_poster.py context.md --channel CXXXXXXXXXX
```

**Parameters:**

| Parameter | Description |
|-----------|-------------|
| `file` | Context file to post |
| `--type` | Post type (boot/update) |
| `--channel` | Channel ID (default from config) |
| `--thread` | Thread timestamp for reply |

---

### slack_mention_handler.py

Handle bot mentions in Slack.

**Location:** `common/tools/slack/slack_mention_handler.py`

**CLI Usage:**
```bash
python3 slack_mention_handler.py --process
python3 slack_mention_handler.py --channel CXXXXXXXXXX
```

---

### slack_processor.py

Process Slack messages for context.

**Location:** `common/tools/slack/slack_processor.py`

**CLI Usage:**
```bash
python3 slack_processor.py --channels "team-channel"
python3 slack_processor.py --since 2026-01-12
```

---

### slack_analyzer.py

Analyze Slack conversations.

**Location:** `common/tools/slack/slack_analyzer.py`

**CLI Usage:**
```bash
python3 slack_analyzer.py --channel team-channel --days 7
```

---

## Google Integration

### gdocs_processor.py

Process Google Docs for context.

**Location:** `common/tools/integrations/gdocs_processor.py`

**CLI Usage:**
```bash
python3 gdocs_processor.py                    # Process recent docs
python3 gdocs_processor.py --doc-id DOC_ID    # Specific document
python3 gdocs_processor.py --days 7           # Last 7 days
```

**Python API:**
```python
from integrations.gdocs_processor import process_docs, get_doc_content

# Process recent docs
results = process_docs(days=3)

# Get specific doc
content = get_doc_content(doc_id="DOC_ID")
```

---

### gdocs_analyzer.py

Analyze Google Docs content.

**Location:** `common/tools/integrations/gdocs_analyzer.py`

**CLI Usage:**
```bash
python3 gdocs_analyzer.py --doc-id DOC_ID
python3 gdocs_analyzer.py --extract-actions
```

---

## Statsig Integration

### statsig_brain_sync.py

Sync Statsig experiments to Brain.

**Location:** `common/tools/integrations/statsig_brain_sync.py`

**CLI Usage:**
```bash
python3 statsig_brain_sync.py                        # Sync all experiments
python3 statsig_brain_sync.py --experiment exp_id    # Specific experiment
python3 statsig_brain_sync.py --gates               # Include feature gates
```

**Python API:**
```python
from integrations.statsig_brain_sync import sync_statsig, get_experiment

# Full sync
results = sync_statsig()

# Get experiment details
exp = get_experiment(experiment_id="checkout_v2")
```

---

## Context Updater

### daily_context_updater.py

Main context update orchestrator.

**Location:** `common/tools/daily_context/daily_context_updater.py`

**CLI Usage:**
```bash
python3 daily_context_updater.py              # Full update
python3 daily_context_updater.py --quick      # GDocs only
python3 daily_context_updater.py --jira       # Include Jira
python3 daily_context_updater.py --dry-run    # Preview only
python3 daily_context_updater.py --upload FILE  # Upload to GDrive
```

**Parameters:**

| Parameter | Description |
|-----------|-------------|
| `--quick` | GDocs only, skip Slack/Gmail |
| `--jira` | Include Jira sync |
| `--dry-run` | Preview without writing |
| `--days N` | Force N days lookback |
| `--upload` | Upload to Google Drive |

---

## Meeting Preparation

### meeting_prep.py

Generate meeting pre-reads.

**Location:** `common/tools/meeting/meeting_prep.py`

**CLI Usage:**
```bash
python3 meeting_prep.py                    # Next 12 hours
python3 meeting_prep.py --hours 24         # Next 24 hours
python3 meeting_prep.py --meeting "Title"  # Specific meeting
python3 meeting_prep.py --archive          # Archive past preps
```

**Python API:**
```python
from meeting.meeting_prep import prepare_meetings, get_attendee_context

# Prepare all upcoming
results = prepare_meetings(hours=12)

# Get attendee context
context = get_attendee_context(email="alice@company.com")
```

---

## Authentication

All integration tools use tokens from `user/.env`:

| Service | Variable |
|---------|----------|
| Jira | `JIRA_API_TOKEN` |
| GitHub | `GITHUB_HF_PM_OS` |
| Slack | `SLACK_BOT_TOKEN` |
| Confluence | `CONFLUENCE_API_TOKEN` |
| Google | OAuth in `.secrets/` |
| Statsig | `STATSIG_CONSOLE_API_KEY` |

---

## Related Documentation

- [Integration Commands](../commands/integration-commands.md) - Command reference
- [Installation](../03-installation.md) - Setting up integrations
- [Architecture](../02-architecture.md) - Integration architecture

---

*Last updated: 2026-01-13*
