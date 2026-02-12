# Integration Commands

> Commands for syncing with external tools and services

## /jira-sync

Sync Jira data to Brain.

### Arguments

| Argument | Description |
|----------|-------------|
| `--project` | Specific project key |
| `--squad` | Squad name filter |
| `--summarize` | Include AI summary |

### What It Does

1. Fetches epics, stories, and blockers
2. Updates squad entity files in Brain
3. Creates inbox entry with raw data
4. Optionally generates executive summary

### Output

- `brain/inbox/JIRA_YYYY-MM-DD.md` - Raw data
- Updates to `brain/entities/team/*.yaml`

### Usage

```
/jira-sync
/jira-sync --project PLAT
/jira-sync --squad "Platform Team" --summarize
```

---

## /github-sync

Sync GitHub activity to Brain.

### Arguments

| Argument | Description |
|----------|-------------|
| `--repo` | Specific repository |
| `--squad` | Squad filter |
| `--analyze-files` | Include file analysis |

### What It Does

1. Fetches open PRs and recent commits
2. Links PRs to Jira tickets (if linked)
3. Updates squad entities with activity
4. Tracks file change patterns

### Output

- `brain/inbox/GITHUB_YYYY-MM-DD.md`
- `brain/github/PR_Activity.md`
- `brain/github/Recent_Commits.md`

### Usage

```
/github-sync
/github-sync --repo platform-api
/github-sync --analyze-files
```

---

## /confluence-sync

Sync Confluence pages to Brain.

### Arguments

| Argument | Description |
|----------|-------------|
| `--space` | Confluence space key |
| `--page` | Specific page ID |
| `--recent` | Only recent changes |

### What It Does

1. Fetches pages from configured spaces
2. Extracts key information
3. Updates Brain with page references
4. Tracks document changes

### Usage

```
/confluence-sync
/confluence-sync --space TNV
/confluence-sync --recent --space PMOS
```

---

## /statsig-sync

Sync Statsig experiments and feature flags.

### Arguments

| Argument | Description |
|----------|-------------|
| `--experiment` | Specific experiment ID |
| `--gates` | Include feature gates |

### What It Does

1. Fetches active experiments
2. Updates experiment entities in Brain
3. Tracks status changes
4. Records metric results

### Output

- `brain/experiments/ab_test/*.yaml` updates
- `brain/experiments/flag/*.yaml` updates

### Usage

```
/statsig-sync
/statsig-sync --experiment checkout_v2
/statsig-sync --gates
```

---

## /slackbot

Capture Slack bot mentions and process.

### Arguments

| Argument | Description |
|----------|-------------|
| `--channel` | Channel to monitor |
| `--process` | Process pending mentions |

### What It Does

1. Monitors configured channels for bot mentions
2. Queues mentions for processing
3. Generates responses using Brain context
4. Posts threaded replies

### Usage

```
/slackbot --process
/slackbot --channel CXXXXXXXXXX
```

---

## /meeting-prep

Prepare for upcoming meetings.

### Arguments

| Argument | Description |
|----------|-------------|
| `--hours` | Hours to look ahead (default: 12) |
| `"Meeting Title"` | Specific meeting by title |
| `--archive` | Archive past meeting preps |

### What It Does

1. Fetches calendar events
2. Loads attendee profiles from Brain
3. Gathers related project context
4. Generates pre-read documents

### Output

Creates files in `user/planning/Meeting_Prep/`:
- Per-meeting prep documents
- Attendee backgrounds
- Related context summaries

### Usage

```
/meeting-prep
/meeting-prep --hours 24
/meeting-prep "Sprint Planning"
/meeting-prep --archive
```

---

## /sprint-report

Generate sprint report from Jira data.

### Arguments

| Argument | Description |
|----------|-------------|
| `--squad` | Squad name |
| `--sprint` | Sprint number/name |
| `--format` | Output format |

### What It Does

1. Fetches sprint data from Jira
2. Calculates velocity and metrics
3. Lists completed/incomplete items
4. Identifies blockers and risks

### Output

Sprint report includes:
- Sprint Goal
- Completed Stories
- Incomplete Items
- Velocity Metrics
- Blockers Encountered
- Team Notes

### Usage

```
/sprint-report --squad "Platform Team"
/sprint-report --sprint 12
```

---

## /sync-tech-context

Sync technical context from repositories.

### Arguments

| Argument | Description |
|----------|-------------|
| `--repo` | Repository path |
| `--scope` | Context scope |

### What It Does

1. Analyzes codebase structure
2. Extracts technical documentation
3. Identifies architecture patterns
4. Updates Brain with technical context

### Usage

```
/sync-tech-context --repo /path/to/repo
```

---

## /career-planning

Career planning system integration.

### Arguments

| Argument | Description |
|----------|-------------|
| `person` | Person to plan for |
| `--create` | Create new plan |
| `--update` | Update existing plan |

### What It Does

1. Loads person entity from Brain
2. Creates or updates career plan
3. Tracks goals and progress
4. Generates development recommendations

### Usage

```
/career-planning alice_smith
/career-planning --create bob_jones
```

---

## Integration Configuration

Integrations are configured in `user/config.yaml`:

```yaml
integrations:
  jira:
    enabled: true
    project_keys: ["PROJ1", "PROJ2"]
  github:
    enabled: true
  slack:
    enabled: true
    channels: ["channel-name"]
  confluence:
    enabled: true
    spaces: ["SPACE"]
  statsig:
    enabled: true
```

## Authentication

All integrations require tokens in `user/.env`:

| Service | Environment Variable |
|---------|---------------------|
| Jira | `JIRA_API_TOKEN` |
| GitHub | `GITHUB_HF_PM_OS` |
| Slack | `SLACK_BOT_TOKEN` |
| Confluence | `CONFLUENCE_API_TOKEN` |
| Statsig | `STATSIG_CONSOLE_API_KEY` |

---

## Related Documentation

- [Installation](../03-installation.md) - Setting up integrations
- [Architecture](../02-architecture.md) - Integration architecture
- [Integration Tools](../tools/integration-tools.md) - Underlying tools

---

*Last updated: 2026-01-13*
