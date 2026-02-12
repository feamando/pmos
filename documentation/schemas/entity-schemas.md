# Entity Schemas

> Schema definitions for PM-OS Brain entities

## Overview

PM-OS uses YAML schemas to validate Brain entities. Schemas ensure data consistency and enable tooling support.

## Schema Files

Schemas are stored in `common/schemas/`:

```
schemas/
├── person.yaml
├── team.yaml
├── project.yaml
├── experiment.yaml
├── epic.yaml
├── okr.yaml
└── partner.yaml
```

## Person Schema

Represents individuals in your network.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier (lowercase_underscore) |
| `name` | string | Full name |
| `email` | string | Email address |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `slack_id` | string | Slack user ID |
| `role.title` | string | Job title |
| `role.team` | string | Team ID reference |
| `role.reports_to` | string | Manager person ID |
| `context.working_on` | array | Project IDs |
| `context.expertise` | array | Areas of expertise |
| `context.communication_style` | string | How to communicate |
| `relationships` | array | Entity relationships |
| `notes` | string | Free-form notes |
| `last_interaction` | date | Last contact date |
| `created` | date | Entity creation date |
| `updated` | date | Last update date |

### Example

```yaml
id: alice_smith
type: person
name: "Alice Smith"
email: "alice.smith@company.com"
slack_id: "U0ALICE"

role:
  title: "Senior Engineer"
  team: platform_team
  reports_to: bob_jones

context:
  working_on:
    - payment_gateway
    - auth_refactor
  expertise:
    - "Backend systems"
    - "Payment processing"
    - "Go"
  communication_style: "Direct, prefers async communication"

relationships:
  - entity: bob_jones
    type: reports_to
  - entity: platform_team
    type: member_of

notes: |
  - Strong technical background
  - Leads payment initiatives
  - Available mornings PST

last_interaction: "2026-01-10"
created: "2025-06-15"
updated: "2026-01-10"
```

---

## Team Schema

Represents teams and squads.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier |
| `name` | string | Team name |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `structure.lead` | string | Team lead person ID |
| `structure.members` | array | Member person IDs |
| `structure.size` | number | Team size |
| `responsibilities` | array | Team responsibilities |
| `rituals` | object | Meeting cadence |
| `current_focus` | array | Active project IDs |
| `slack_channels` | array | Team Slack channels |
| `jira.project_key` | string | Jira project key |
| `jira.board_id` | number | Jira board ID |

### Example

```yaml
id: platform_team
type: team
name: "Platform Team"

structure:
  lead: alice_smith
  members:
    - alice_smith
    - charlie_dev
    - dana_qa
  size: 3

responsibilities:
  - "Core platform services"
  - "Payment processing"
  - "Authentication"

rituals:
  standup: "Daily 9:30am"
  planning: "Monday 10am"
  retro: "Friday 3pm"

current_focus:
  - payment_gateway
  - auth_refactor

slack_channels:
  - "#platform-team"
  - "#platform-alerts"

jira:
  project_key: "PLAT"
  board_id: 123
```

---

## Project Schema

Represents features, initiatives, or projects.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier |
| `name` | string | Project name |
| `status` | enum | planned, in_progress, completed, on_hold |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `owner` | string | Owner person ID |
| `team` | string | Owning team ID |
| `target_date` | date | Target completion |
| `progress` | number | Completion percentage |
| `description` | string | Project description |
| `milestones` | array | Key milestones |
| `blockers` | array | Current blockers |
| `decisions` | array | Decisions made |
| `related` | array | Related entity IDs |

### Example (Markdown format)

```markdown
# Payment Gateway Migration

> Migrate from legacy gateway to new provider

## Status

| Field | Value |
|-------|-------|
| Status | In Progress |
| Owner | @alice_smith |
| Team | platform_team |
| Target | 2026-02-28 |
| Progress | 70% |

## Overview

Migrating payment processing from LegacyPay to NewPay.

## Key Milestones

- [x] Requirements complete
- [x] API integration
- [ ] Testing complete
- [ ] Production rollout

## Blockers

| Blocker | Owner | Status |
|---------|-------|--------|
| API docs outdated | @vendor | Waiting |

## Decisions

- 2026-01-05: Chose gradual rollout
```

---

## Experiment Schema

Represents A/B tests and feature flags.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier |
| `type` | enum | ab_test, flag |
| `name` | string | Experiment name |
| `status` | enum | draft, running, paused, completed |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `hypothesis` | string | What we're testing |
| `started` | date | Start date |
| `target_end` | date | Expected end date |
| `variants` | array | Test variants |
| `metrics.primary` | array | Primary metrics |
| `metrics.secondary` | array | Secondary metrics |
| `owner` | string | Owner person ID |
| `team` | string | Team ID |
| `statsig.experiment_id` | string | Statsig reference |
| `results` | object | Current results |

### Example

```yaml
id: checkout_flow_v2
type: ab_test
name: "Checkout Flow v2 Test"

status: running
started: "2026-01-01"
target_end: "2026-01-31"

hypothesis: |
  Simplified checkout will increase conversion by 5%

variants:
  - name: control
    allocation: 50
    description: "Current checkout flow"
  - name: treatment
    allocation: 50
    description: "Simplified 2-step flow"

metrics:
  primary:
    - name: conversion_rate
      target: "+5%"
  secondary:
    - name: cart_abandonment
      target: "-10%"

owner: alice_smith
team: platform_team

statsig:
  experiment_id: "checkout_v2_2026"

results:
  last_check: "2026-01-12"
  status: "inconclusive"
```

---

## Epic Schema

Represents large initiatives spanning multiple sprints.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier |
| `name` | string | Epic name |
| `status` | enum | planning, active, completed |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | Epic description |
| `owner` | string | Owner person ID |
| `projects` | array | Child project IDs |
| `quarter` | string | Target quarter |
| `okr` | string | Related OKR ID |
| `jira.epic_key` | string | Jira epic key |

### Example

```yaml
id: q1_migration
type: epic
name: "Q1 Platform Migration"
status: active

description: |
  Migrate all platform services to new infrastructure

owner: alice_smith
projects:
  - payment_gateway
  - auth_refactor
  - database_migration

quarter: "Q1-2026"
okr: q1_2026_platform

jira:
  epic_key: "PLAT-100"
```

---

## OKR Schema

Represents Objectives and Key Results.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier |
| `period` | string | Quarter/year |
| `objective` | string | The objective |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `key_results` | array | Key results |
| `owner` | string | Owner person/team ID |
| `status` | enum | on_track, at_risk, off_track |
| `progress` | number | Overall progress |

### Example

```yaml
id: q1_2026_platform
type: okr
period: "Q1-2026"

objective: "Modernize platform infrastructure"

key_results:
  - kr: "Migrate 100% of services to new infra"
    target: 100
    current: 70
    status: on_track
  - kr: "Reduce latency by 20%"
    target: 20
    current: 15
    status: on_track
  - kr: "Zero security incidents"
    target: 0
    current: 0
    status: on_track

owner: platform_team
status: on_track
progress: 75
```

---

## Partner Schema

Represents external partners and vendors.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier |
| `name` | string | Partner name |
| `type` | enum | vendor, partner, customer |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `contacts` | array | Contact person IDs |
| `relationship_owner` | string | Internal owner |
| `services` | array | Services provided |
| `contract.start` | date | Contract start |
| `contract.end` | date | Contract end |
| `notes` | string | Relationship notes |

### Example

```yaml
id: vendor_acme
type: partner
name: "Acme Corp"

contacts:
  - john_acme_sales
  - jane_acme_support

relationship_owner: alice_smith

services:
  - "Payment processing"
  - "Fraud detection"

contract:
  start: "2025-01-01"
  end: "2026-12-31"

notes: |
  Key payment partner
  Monthly review calls
```

---

## Validation

Use the entity validator to check schemas:

```bash
python3 entity_validator.py --type person --file entity.yaml
```

---

## Related Documentation

- [Brain Architecture](../05-brain.md) - Brain structure
- [Brain Tools](../tools/brain-tools.md) - Brain management tools

---

*Last updated: 2026-01-13*
