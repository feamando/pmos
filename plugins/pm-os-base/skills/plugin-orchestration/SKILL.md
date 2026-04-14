---
description: When a feature from another plugin is needed but not installed, suggest installation instead of failing. Gracefully degrade when optional plugins are missing.
---

# Plugin Orchestration

## When to Apply
- A command references a feature that belongs to another plugin
- An import or tool call fails because a plugin is not installed
- User asks about a feature that requires a specific plugin
- A pipeline step is skipped because its plugin is missing

## What to Do

1. Check if the needed plugin is installed:
   ```bash
   python3 tools/core/plugin_deps.py --check pm-os-<name>
   ```

2. If NOT installed, suggest installation:
   ```
   This feature requires the pm-os-brain plugin.
   Install with: /base plugins install pm-os-brain
   ```

3. If installed but failing, check:
   - Plugin's config requirements (missing config keys)
   - Plugin's MCP server status (if applicable)
   - Plugin's preflight checks

4. Never crash on a missing optional plugin. Always provide a degraded but functional path.

## Plugin Capabilities

| Plugin | Provides |
|--------|----------|
| pm-os-base | Config, pipelines, sessions, preflight, auth |
| pm-os-brain | Knowledge graph, entity management, search, enrichment |
| pm-os-daily-workflow | Context synthesis, meeting prep, Slack integration |
| pm-os-cce | Cowork project generation, FPF reasoning |
| pm-os-reporting | Sprint reports, quarterly updates |
| pm-os-career | Career tracking, 1:1 prep, goal management |
| pm-os-dev | Developer tools, release automation, command sync |

## Examples

<example>
User: "Search my brain for Alice"
Assistant: [checks if pm-os-brain is installed — if yes, uses brain search; if no, suggests: "Install pm-os-brain for knowledge graph search: /base plugins install pm-os-brain"]
</example>

<example>
User: "Generate a sprint report"
Assistant: [checks if pm-os-reporting is installed — if yes, runs report; if no, suggests installation and explains what the plugin provides]
</example>
