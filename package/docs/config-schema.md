# PM-OS Configuration Schema

This document describes the `config.yaml` configuration file schema.

## Location

The configuration file is located at:
```
~/pm-os/.config/config.yaml
```

## Full Schema

```yaml
# User profile information
user:
  name: string          # Full name (required)
  email: string         # Email address (required)
  role: string          # Job title/role
  team: string          # Team or organization
  timezone: string      # Timezone (e.g., America/New_York)

# LLM provider configuration
llm:
  provider: string      # One of: bedrock, anthropic, openai, ollama (required)
  model: string         # Model name/ID (required)

# Integration configurations
integrations:
  jira:
    enabled: boolean    # Enable Jira integration
    url: string         # Jira instance URL
    email: string       # User email for auth
    projects: string    # Comma-separated project keys to sync
    # Token stored in .env as JIRA_TOKEN

  slack:
    enabled: boolean    # Enable Slack integration
    channels: string    # Comma-separated channel names
    # Token stored in .env as SLACK_BOT_TOKEN

  github:
    enabled: boolean    # Enable GitHub integration
    repos: string       # Comma-separated repo names (owner/repo)
    # Token stored in .env as GITHUB_TOKEN

  google:
    enabled: boolean    # Enable Google integration
    credentials_path: string  # Path to OAuth credentials.json

  confluence:
    enabled: boolean    # Enable Confluence integration
    url: string         # Confluence URL
    email: string       # User email for auth
    space: string       # Default space key
    # Token stored in .env as CONFLUENCE_TOKEN

# Optional: Paths configuration
paths:
  brain: string         # Custom brain directory path
  logs: string          # Custom logs directory path
```

## Example Configuration

```yaml
user:
  name: Jane Smith
  email: jane.smith@example.com
  role: Product Manager
  team: Platform
  timezone: America/New_York

llm:
  provider: anthropic
  model: claude-sonnet-4-20250514

integrations:
  jira:
    enabled: true
    url: https://example.atlassian.net
    email: jane.smith@example.com
    projects: PLAT,AUTH,API

  slack:
    enabled: true
    channels: platform-team,product-updates

  github:
    enabled: true
    repos: example-org/platform-api,example-org/docs

  google:
    enabled: false
    credentials_path: ""

  confluence:
    enabled: true
    url: https://example.atlassian.net
    email: jane.smith@example.com
    space: PLAT
```

## Environment Variables (.env)

Sensitive credentials are stored in `.env`:

```bash
# LLM API Keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Integration Tokens
JIRA_TOKEN=...
SLACK_BOT_TOKEN=xoxb-...
GITHUB_TOKEN=ghp_...
CONFLUENCE_TOKEN=...

# Optional: AWS for Bedrock
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

**Important:** The `.env` file has permissions `600` (owner read/write only).

## Field Reference

### User Section

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | User's full name |
| `email` | string | Yes | User's email address |
| `role` | string | No | Job title (e.g., "Product Manager") |
| `team` | string | No | Team or organization name |
| `timezone` | string | No | Timezone (defaults to UTC) |

### LLM Section

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `provider` | string | Yes | LLM provider name |
| `model` | string | Yes | Model identifier |

Valid providers:
- `bedrock` - AWS Bedrock (Claude)
- `anthropic` - Direct Anthropic API
- `openai` - OpenAI API
- `ollama` - Local Ollama

### Integration Sections

Each integration has these common fields:

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean | Whether integration is active |

Integration-specific fields vary (see full schema above).

## Validation

Run `pm-os config validate` to check your configuration:

```bash
$ pm-os config validate
Configuration Validation

Errors:
  ✗ llm.provider is required

Warnings:
  ⚠ user.email not set
  ⚠ Integration 'jira' enabled but missing configuration

Configuration has errors.
```

## Editing Configuration

Use these commands to manage configuration:

```bash
# View current configuration
pm-os config show

# Edit configuration file
pm-os config edit

# Set a specific value
pm-os config set user.name "Jane Smith"
pm-os config set llm.provider anthropic
pm-os config set integrations.jira.enabled true
```

## Silent Installation

For automated/CI installation, create a template file and use:

```bash
pm-os init --template /path/to/config-template.yaml
```

Template format is the same as `config.yaml` but can include credentials that will be moved to `.env`.
