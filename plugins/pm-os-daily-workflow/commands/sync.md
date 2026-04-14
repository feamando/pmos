---
description: Sync external tool data into PM-OS context and Brain
---

# /sync — Integration Sync

Sync external tool data into PM-OS context and Brain entities.

Parse the first argument to determine which integration to sync:

| Subcommand | Description |
|------------|-------------|
| `jira` | Sync Jira issues, epics, and blockers |
| `github` | Sync GitHub PRs, commits, and repo context |
| `confluence` | Sync Confluence pages to Brain |
| `statsig` | Sync Statsig experiments and feature flags |
| `squad-sprint` | Sync squad sprint reports from Google Sheets |
| `slack` | Sync Slack channels and mentions |
| `master-sheet` | Sync Master Sheet priorities and actions |
| `tech-context` | Sync tech stack and repo analysis |
| `all` | Run all configured integrations in parallel |

If no arguments provided, display available subcommands.

## Arguments

All subcommands accept:
- `--dry-run` — Show what would be synced without writing
- `--verbose` — Show detailed output

## jira

Fetch Jira data for configured squads and update Brain entities.

```bash
python3 tools/integrations/jira_sync.py --sync
```

Uses connector_bridge: in Claude session, data is fetched via Jira MCP connector.
In background, falls back to JIRA_API_TOKEN from .env.

## github

Fetch GitHub PRs, commits, and repo structure for configured repos.

```bash
python3 tools/integrations/github_sync.py --sync
```

Uses connector_bridge for auth. Requires `gh` CLI for some operations.

## confluence

Fetch and sync Confluence pages to Brain.

```bash
python3 tools/integrations/confluence_sync.py --sync
```

## statsig

Fetch Statsig experiments and feature gates.

```bash
python3 tools/integrations/statsig_sync.py --sync
```

## squad-sprint

Sync squad sprint reports from configured Google Sheet.

```bash
python3 tools/integrations/squad_sprint_sync.py --sync
```

Config: `integrations.google.sprint_sheet_id`

## slack

Sync Slack channel membership and process recent mentions.

```bash
python3 tools/slack/slack_channel_sync.py --sync
```

## master-sheet

Sync Master Sheet priorities and action items.

```bash
python3 tools/integrations/master_sheet_sync.py --sync
```

Config: `integrations.google.master_sheet_id`

## tech-context

Analyze GitHub repos for tech stack and sync patterns.

```bash
python3 tools/integrations/tech_context_sync.py --sync
```

## all

Run all enabled integrations in parallel:

```bash
python3 tools/integrations/sync_all.py
```

Runs each enabled integration (checked via `config.integrations.{name}.enabled`).
Reports results for each.

## Examples

```
/sync jira                    # Sync Jira data
/sync github --verbose        # Sync GitHub with details
/sync all                     # Sync everything
/sync squad-sprint --dry-run  # Preview sprint sync
```

## Execute

Parse arguments and run the appropriate sync subcommand.
