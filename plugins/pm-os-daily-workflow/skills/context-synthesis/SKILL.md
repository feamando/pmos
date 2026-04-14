---
description: Use daily context files for current state awareness — priorities, blockers, action items
---

# Context Synthesis

## When to Apply
- When the user asks about current priorities, blockers, or action items
- When the user asks "what's going on" or "catch me up"
- When generating any document that needs current project state
- When answering questions about team status or project progress

## What to Do
- **Read today's context:** The daily context file is at `user/personal/context/YYYY-MM-DD-context.md`. It contains: Critical Alerts, Schedule, Key Updates, Active Blockers, Action Items, Key Dates.
- **Carry forward:** If today's context doesn't exist yet, read the most recent context file for continuity.
- **Cross-reference:** When the user asks about a specific project or person, cross-reference the context file with Brain entities (if Brain plugin is installed).
- **Staleness:** If the context file is more than 1 day old, note this and suggest running `/session boot` or `/sync all` to refresh.

## Examples
<example>
User: "What are my blockers?"
Assistant: [reads today's context file, extracts Active Blockers table, presents with owners and status]
</example>

<example>
User: "What happened with the OTP launch?"
Assistant: [searches today's context for OTP references, cross-references with Brain if available]
</example>
