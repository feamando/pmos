# PM-OS Entity Schema Documentation

This document describes the schema for brain entities created by PM-OS.

## Overview

Brain entities are Markdown files with YAML frontmatter. They live in the `brain/Entities/` directory, organized by type.

## Directory Structure

```
brain/
├── Entities/
│   ├── People/       # Person entities
│   ├── Projects/     # Project entities
│   ├── Issues/       # Issue/ticket entities
│   ├── Sprints/      # Sprint entities
│   ├── Channels/     # Slack/communication channels
│   ├── Repositories/ # Git repositories
│   ├── PullRequests/ # Pull request entities
│   ├── Documents/    # Documents (Confluence, Drive, etc.)
│   └── Meetings/     # Calendar events
└── Context/          # Context documents
```

## Common Frontmatter Fields

All entities share these core fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Entity type (person, project, issue, etc.) |
| `name` | string | Yes | Human-readable name |
| `source` | string | No | Source system (jira, slack, github, etc.) |
| `created` | date | No | Creation date (YYYY-MM-DD) |
| `updated` | date | No | Last update date |
| `last_sync` | datetime | No | Last sync timestamp (ISO 8601) |
| `sync_id` | string | No | External system ID for sync tracking |
| `relationships` | object | No | Map of relationship type to entity names |

## Entity Types

### Person

Location: `Entities/People/`

| Field | Type | Description |
|-------|------|-------------|
| `email` | string | Email address |
| `role` | string | Job title/role |
| `team` | string | Team or department |
| `is_self` | boolean | True for the PM-OS owner |
| `slack_id` | string | Slack user ID |
| `github_username` | string | GitHub username |
| `jira_account_id` | string | Jira account ID |

Example:
```yaml
---
type: person
name: Jane Smith
source: slack
email: jane@example.com
role: Engineering Manager
team: Platform
is_self: false
slack_id: U123ABC
---
```

### Project

Location: `Entities/Projects/`

| Field | Type | Description |
|-------|------|-------------|
| `jira_key` | string | Jira project key |
| `github_repo` | string | GitHub repository full name |
| `status` | string | Project status |
| `owner` | string | Project owner name |
| `description` | string | Project description |
| `start_date` | date | Project start date |
| `end_date` | date | Project end date |

Example:
```yaml
---
type: project
name: Authentication Service
source: jira
jira_key: AUTH
status: active
owner: Jane Smith
---
```

### Issue

Location: `Entities/Issues/`

| Field | Type | Description |
|-------|------|-------------|
| `key` | string | Issue key (e.g., AUTH-123) |
| `title` | string | Issue title |
| `status` | string | Issue status |
| `priority` | string | Priority level |
| `issue_type` | string | Type (bug, story, task, etc.) |
| `project` | string | Parent project key |
| `sprint` | string | Sprint name |
| `labels` | array | Issue labels |
| `assignee` | string | Assignee name |
| `reporter` | string | Reporter name |
| `due_date` | date | Due date |

Example:
```yaml
---
type: issue
name: "AUTH-123: Implement OAuth"
source: jira
key: AUTH-123
title: Implement OAuth
status: In Progress
priority: High
issue_type: Story
project: AUTH
relationships:
  assignee: [Jane Smith]
  project: [Authentication Service]
---
```

### Sprint

Location: `Entities/Sprints/`

| Field | Type | Description |
|-------|------|-------------|
| `project` | string | Parent project |
| `status` | string | Sprint state (active, closed, future) |
| `start_date` | date | Sprint start |
| `end_date` | date | Sprint end |
| `goal` | string | Sprint goal |
| `board_id` | string | Agile board ID |

### Channel

Location: `Entities/Channels/`

| Field | Type | Description |
|-------|------|-------------|
| `channel_id` | string | Slack channel ID |
| `is_private` | boolean | Private channel flag |
| `topic` | string | Channel topic |
| `purpose` | string | Channel purpose |
| `member_count` | integer | Number of members |

### Repository

Location: `Entities/Repositories/`

| Field | Type | Description |
|-------|------|-------------|
| `full_name` | string | Full repo name (owner/repo) |
| `url` | string | Repository URL |
| `description` | string | Repository description |
| `default_branch` | string | Default branch name |
| `is_private` | boolean | Private repository flag |
| `language` | string | Primary language |
| `stars` | integer | Star count |
| `forks` | integer | Fork count |
| `open_issues` | integer | Open issue count |

### Pull Request

Location: `Entities/PullRequests/`

| Field | Type | Description |
|-------|------|-------------|
| `number` | integer | PR number |
| `title` | string | PR title |
| `state` | string | State (open, closed, merged) |
| `repository` | string | Repository full name |
| `author` | string | PR author |
| `base_branch` | string | Target branch |
| `head_branch` | string | Source branch |
| `created_date` | date | Creation date |
| `merged_date` | date | Merge date (if merged) |
| `labels` | array | PR labels |

### Document

Location: `Entities/Documents/`

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | Document URL |
| `space` | string | Confluence space key |
| `page_id` | string | Page/document ID |
| `author` | string | Author name |
| `last_modified` | date | Last modification date |
| `parent` | string | Parent document name |

### Meeting

Location: `Entities/Meetings/`

| Field | Type | Description |
|-------|------|-------------|
| `date` | date | Meeting date |
| `start_time` | datetime | Start time |
| `end_time` | datetime | End time |
| `attendees` | array | List of attendee names |
| `location` | string | Meeting location/link |
| `recurring` | boolean | Is recurring event |
| `calendar_id` | string | Calendar ID |
| `event_id` | string | Calendar event ID |

## Relationships

Relationships connect entities to each other. They're stored as a map where:
- Key: relationship type (assignee, project, parent, etc.)
- Value: array of related entity names

Example:
```yaml
relationships:
  project: [Authentication Service]
  assignee: [Jane Smith]
  sprint: [Sprint 23]
```

## Filename Convention

Entity filenames are derived from the entity name:
- Spaces → underscores
- Special characters (/, :, <, >, |, ?, *) → removed or replaced
- Maximum length: 100 characters
- Extension: .md

Examples:
- "Authentication Service" → `Authentication_Service.md`
- "AUTH-123: Fix OAuth" → `AUTH-123-_Fix_OAuth.md`

## Sync State

The `.sync_state.json` file tracks sync progress:

```json
{
  "jira_issues_AUTH": {
    "last_sync": "2024-01-15T10:30:00",
    "cursor": null
  },
  "github_prs_owner/repo": {
    "last_sync": "2024-01-15T11:00:00"
  }
}
```

This enables incremental sync - only fetching changes since the last sync.
