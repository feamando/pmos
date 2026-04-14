---
description: When a command needs external data (Jira, Slack, Google, GitHub), use the three-tier auth pattern — try Claude connector first, then .env API token, then show a helpful error with setup instructions.
---

# Connector Awareness

## When to Apply
- Any command that fetches data from an external service
- User reports auth failures or "access denied" errors
- A pipeline step fails due to missing credentials
- User asks about connecting a service

## What to Do

1. Always use the three-tier auth pattern:
   ```
   Tier 1: Claude connector (zero config for user, just enable in Settings > Connectors)
   Tier 2: .env API token (for background/pipeline tasks that run without Claude)
   Tier 3: Helpful error with setup instructions
   ```

2. When a service call fails:
   - Check which tier was attempted
   - If connector failed, suggest checking Claude > Settings > Connectors
   - If .env token failed, show the exact env var needed and where to set it
   - Never expose tokens or credentials in output

3. For background/pipeline tasks (no Claude session):
   - These MUST use .env tokens (connectors only work in interactive Claude sessions)
   - If .env token is missing, log a warning and skip gracefully

## Supported Services

| Service | Connector | .env Variable | Config Key |
|---------|-----------|---------------|------------|
| Google | google | GOOGLE_TOKEN_PATH | integrations.google |
| Jira | jira | JIRA_API_TOKEN | integrations.jira |
| Slack | slack | SLACK_BOT_TOKEN | integrations.slack |
| GitHub | github | GITHUB_TOKEN | integrations.github |
| Figma | figma | FIGMA_ACCESS_TOKEN | integrations.figma |
| Confluence | confluence | JIRA_API_TOKEN | integrations.jira |
| Statsig | statsig | STATSIG_CONSOLE_API_KEY | integrations.statsig |

## Examples

<example>
User: "Sync my Jira tickets"
Assistant: [uses connector_bridge.get_auth("jira") — tries connector first, falls back to .env, shows helpful setup message if neither works]
</example>

<example>
User: "Why did meeting prep fail?"
Assistant: [checks that meeting prep runs in background, so it needs .env tokens not connectors — guides user to set GOOGLE_TOKEN_PATH and JIRA_API_TOKEN in user/.env]
</example>
