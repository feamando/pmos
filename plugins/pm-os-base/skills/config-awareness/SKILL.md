---
description: When user mentions configuration, settings, or preferences, check config.yaml for current values and guide them to the right config keys.
---

# Config Awareness

## When to Apply
- User asks about PM-OS settings or configuration
- User wants to change a preference or default value
- A command fails because of a missing config key
- User mentions "config", "settings", "preferences", or specific config keys

## What to Do

1. Check config.yaml for the relevant setting:
   ```bash
   python3 tools/core/config_loader.py --get <key>
   ```

2. If the key exists, show its current value and explain what it controls.

3. If the key is missing, explain:
   - What the key controls
   - What the default value is
   - How to set it: edit config.yaml or run `/base config edit`

4. For integration settings (jira, slack, github, google), also check:
   - Whether the service is configured in `.env` or via Claude connectors
   - Whether the connector is active: `python3 tools/core/connector_bridge.py --check <service>`

## Config Key Reference

Core settings live under these namespaces:
- `user.*` — name, email, role, company
- `persona.*` — style, format, decision_framework
- `integrations.*` — jira, slack, github, google, figma, statsig
- `brain.*` — auto_create_entities, cache_ttl_hours
- `meeting_prep.*` — prep_hours, default_depth
- `pm_os.*` — fpf_enabled, confucius_enabled, default_cli

## Examples

<example>
User: "How do I change my default meeting prep time?"
Assistant: [checks config.yaml for meeting_prep.prep_hours, shows current value, explains how to change it]
</example>

<example>
User: "Why can't PM-OS access my Jira?"
Assistant: [checks connector_bridge for jira auth status, checks config for integrations.jira, guides user to set up either Claude connector or .env token]
</example>
