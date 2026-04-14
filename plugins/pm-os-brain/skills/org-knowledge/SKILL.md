---
description: Use Brain knowledge graph to provide organizational context about teams, projects, and ownership in responses
---

# Organizational Knowledge

## When to Apply
- When providing context about the user's work environment
- When discussing team structure, project ownership, or organizational dynamics
- When the user needs stakeholder recommendations
- When preparing meeting notes, status updates, or project summaries

## What to Do
- Reference team structure from Brain entities (who reports to whom, who owns what)
- Reference project status from Brain entities
- Use relationship data to suggest relevant stakeholders for decisions
- Check entity freshness -- flag stale information (last_enriched > 7 days)
- The knowledge graph is at user/brain/. The compressed index is user/brain/BRAIN.md.
- Always prefer BRAIN.md for quick lookups. Use full entity files for deep dives.

## Entity Types Available
- **Person:** Team members, stakeholders, external contacts (role, team, reports_to)
- **Squad/Team:** Organizational units (members, owned_systems, active_projects)
- **Project:** Initiatives and features (owner, status, squad, timeline)
- **System:** Technical systems and services (owner_squad, dependencies, tech_stack)
- **Decision:** Architectural and product decisions (rationale, approver, date)
- **Framework:** PM frameworks and methodologies (use_case, steps, category)

## Staleness Rules
- **Fresh (< 3 days):** Use confidently, no caveats needed
- **Recent (3-7 days):** Use normally, note date if critical
- **Stale (7-14 days):** Use with caveat: "Based on data from [date], may need refresh"
- **Very stale (> 14 days):** Flag explicitly: "This information is from [date] and may be outdated"

## Examples

<example>
User: "Who should review this API proposal?"
Assistant: [checks Brain for system entity related to the API, finds owner squad, lists squad members with PM and tech lead roles, suggests reviewers based on ownership relationships]
</example>

<example>
User: "Give me context on the Growth tribe"
Assistant: [reads Brain entities for Growth tribe, lists squads, their owners, active projects per squad, key systems, and recent decisions -- all from Brain with freshness dates]
</example>
