---
description: When asked about team dynamics, project ownership, or who to contact about a topic, query Brain relationships
---

# Relationship Awareness

## When to Apply
- User asks "who should I talk to about X?"
- User asks about team dynamics or project ownership
- User needs to understand reporting lines or stakeholder mapping
- User is preparing for a meeting and needs to understand attendee context
- User asks about dependencies between systems or projects

## What to Do
1. Query Brain relationships (use get_relationships MCP tool or read entity files)
2. Follow relationship chains: person -> owns -> project -> related_to -> system
3. Consider confidence scores (CL1-CL4) -- flag low-confidence relationships
4. Consider temporal freshness -- relationships decay over time
5. When making recommendations, cite the evidence source (jira, slack, manual, context)

## Relationship Types

| Relationship | Inverse | Description |
|-------------|---------|-------------|
| `owner` | `owns` | Person/squad owns a project or system |
| `member_of` | `has_member` | Person is member of a squad/team |
| `reports_to` | `manages` | Reporting line |
| `stakeholder_of` | `has_stakeholder` | Interested party for a project |
| `blocked_by` | `blocks` | Dependency blocker |
| `depends_on` | `dependency_for` | System or project dependency |
| `relates_to` | `relates_to` | General association |
| `part_of` | `has_part` | Component relationship |

## Chain Following Rules
- Follow up to 3 hops for relationship chains (beyond that, confidence drops too low)
- At each hop, note the relationship type and confidence
- Prefer shorter chains over longer ones for recommendations
- Always show the chain when presenting results: "A -> owns -> B -> depends_on -> C"

## Evidence Sources (in order of reliability)
1. **jira** -- Ticket assignments, project ownership
2. **confluence** -- Documented team structures, architecture decisions
3. **slack** -- Communication patterns, informal ownership signals
4. **github** -- Code ownership (CODEOWNERS), PR reviewers
5. **manual** -- User-confirmed relationships
6. **context** -- Inferred from session context (lowest reliability)

## Examples

<example>
User: "Who should I talk to about payment processing?"
Assistant: [queries Brain for payment-related system entities, follows owner relationships to find squad and person entities, recommends contacts with evidence: "Based on Brain data: payment-service is owned by Payments Squad (source: jira). Tech lead is [Name] (source: confluence). Last confirmed: 2026-03-28."]
</example>

<example>
User: "What depends on the user-service?"
Assistant: [gets relationships for user-service entity, follows dependency_for relationships, builds dependency tree showing downstream systems, flags any stale relationships]
</example>
