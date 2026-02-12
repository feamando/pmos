# Jira Sync

Fetch Jira activity (epics, in-progress, blockers) for Growth Division squads and enrich Brain context.

## Instructions

### Default: Sync All Squads

```bash
python3 "$PM_OS_COMMON/tools/integrations/jira_brain_sync.py"
```

This will:
- Fetch active epics, in-progress items, and blockers for each squad
- Write raw data to `Brain/Inbox/JIRA_YYYY-MM-DD.md`
- Update `Brain/Entities/Squad_*.md` with Jira status section

### Options

| Flag | Description |
|------|-------------|
| `--squad "Name"` | Sync specific squad only |
| `--summarize` | Include Gemini-generated executive summary |
| `--github` | Include GitHub PR links for blockers (Phase 2) |
| `--no-entities` | Skip updating squad entity files |
| `--output PATH` | Custom output path for inbox file |

### Examples

```bash
# All squads with summary
python3 "$PM_OS_COMMON/tools/integrations/jira_brain_sync.py" --summarize

# Specific squad
python3 "$PM_OS_COMMON/tools/integrations/jira_brain_sync.py" --squad "Meal Kit"

# With GitHub PR links
python3 "$PM_OS_COMMON/tools/integrations/jira_brain_sync.py" --github

# Full enrichment
python3 "$PM_OS_COMMON/tools/integrations/jira_brain_sync.py" --summarize --github
```

## Output Structure

- **Inbox:** `Brain/Inbox/JIRA_YYYY-MM-DD.md` - Raw fetch data
- **Entities:** `Brain/Entities/Squad_*.md` - Jira Status section with:
  - Active Epics count
  - In Progress count
  - Blockers count
  - Current Focus (top 3 items)
  - Blocker details

## JQL Queries Used

| Category | JQL |
|----------|-----|
| Epics | `project = X AND issuetype = Epic AND status NOT IN (Done, Closed)` |
| In Progress | `project = X AND status = "In Progress"` |
| Blockers | `project = X AND (priority = High OR labels = blocked) AND status NOT IN (Done)` |

## Prerequisites

- Jira API credentials in `.env` (`JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`)
- `squad_registry.yaml` with squad definitions including `jira_project`
