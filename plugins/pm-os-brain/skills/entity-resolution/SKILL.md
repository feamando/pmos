---
description: When any conversation mentions a person, project, team, or system by name, check Brain entities for context
---

# Entity Resolution

## When to Apply
- User mentions a person, project, team, system, or squad by name
- User asks "who is X" or "what is X" about organizational entities
- User references an entity that might exist in the knowledge graph

## What to Do
1. Check if a Brain entity exists (use brain MCP search_entities tool if available, or read user/brain/BRAIN.md index)
2. If found: use the entity's metadata (role, status, relationships) to enrich your response
3. If not found but seems like a real entity: note it as potential new entity for future enrichment
4. Always cite the entity source when referencing Brain data

## Resolution Order
1. **MCP search_entities** -- fastest, semantic match (preferred when MCP is available)
2. **BRAIN.md index** -- compressed index with entity names, types, and key metadata
3. **Entity file read** -- full entity file at `user/brain/<Type>/<Entity_Name>.md` for deep dives

## Confidence Levels
- **CL4 (Verified):** Entity confirmed from multiple sources (jira + slack + manual)
- **CL3 (High):** Entity from single authoritative source (jira, confluence)
- **CL2 (Medium):** Entity inferred from context or single mention
- **CL1 (Low):** Entity guessed or from stale data (> 30 days old)

Flag the confidence level when referencing Brain data so the user knows how trustworthy it is.

## Examples

<example>
User: "What's Alex working on?"
Assistant: [checks Brain for alex entity, finds role as Staff PM on Platform Squad, lists active projects from relationships, references recent context]
</example>

<example>
User: "Tell me about the checkout system"
Assistant: [searches Brain for checkout entities, finds system entity with architecture details, related squads, recent incidents, and active projects touching checkout]
</example>

<example>
User: "Who owns the recommendation engine?"
Assistant: [queries Brain relationships for recommendation-engine entity, follows owner relationship to person entity, checks if ownership is current via last_enriched date]
</example>
