# Document Commands

> Commands for generating PM documents with AI assistance

## Overview

PM-OS provides commands for generating structured documents common in product management. Each command uses templates, Brain context, and AI to create professional documents.

## /prd

Generate Product Requirements Document.

### Arguments

| Argument | Description |
|----------|-------------|
| `topic` | Feature or product topic |
| `--fpf` | Use FPF structured reasoning |
| `--orthogonal` | 3-round Claude vs Gemini challenge |
| `--update <file>` | Update existing PRD |

### Modes

| Mode | Time | Use Case |
|------|------|----------|
| Standard | 2-5 min | Quick PRD generation |
| FPF | 15-30 min | Complex decisions needing audit trail |
| Orthogonal | 10-20 min | High-stakes PRDs requiring validation |

### Output

PRD includes:
- Problem Statement
- User Stories
- Requirements (functional/non-functional)
- Success Metrics
- Dependencies
- Timeline

### Usage

```
/prd Add push notifications to mobile app
/prd --fpf Payment gateway migration strategy
/prd --orthogonal New subscription model
```

---

## /rfc

Generate Request for Comments document.

### Arguments

| Argument | Description |
|----------|-------------|
| `topic` | Technical proposal topic |
| `--fpf` | Include FPF reasoning |

### Output

RFC includes:
- Summary
- Motivation
- Detailed Design
- Drawbacks
- Alternatives
- Implementation Plan

### Usage

```
/rfc API versioning strategy
/rfc --fpf Migration to microservices
```

---

## /adr

Generate Architecture Decision Record.

### Arguments

| Argument | Description |
|----------|-------------|
| `topic` | Decision topic |
| `--status` | Status (proposed/accepted/deprecated) |

### Output

ADR includes:
- Title and Date
- Status
- Context
- Decision
- Consequences
- Alternatives Considered

### Usage

```
/adr Use PostgreSQL for user data
/adr --status accepted Database sharding approach
```

---

## /bc

Generate Business Case document.

### Arguments

| Argument | Description |
|----------|-------------|
| `topic` | Business initiative |
| `--template` | Template variant |

### Output

Business Case includes:
- Executive Summary
- Problem Statement
- Proposed Solution
- Cost-Benefit Analysis
- ROI Projection
- Risk Assessment
- Implementation Timeline

### Usage

```
/bc New market expansion to Germany
/bc --template investment Platform modernization initiative
```

---

## /prfaq

Generate Amazon-style PR/FAQ document.

### Arguments

| Argument | Description |
|----------|-------------|
| `topic` | Product or feature |
| `--internal` | Internal FAQ variant |

### Output

PRFAQ includes:
- Press Release (future-dated announcement)
- Customer FAQ (external questions)
- Internal FAQ (stakeholder questions)

### Usage

```
/prfaq Launch of premium subscription tier
/prfaq --internal New developer platform
```

---

## /whitepaper

Generate strategic proposal document.

### Arguments

| Argument | Description |
|----------|-------------|
| `topic` | Strategic topic |

### Output

Whitepaper includes:
- Executive Summary
- Market Analysis
- Strategic Recommendations
- Implementation Roadmap
- Success Metrics

### Usage

```
/whitepaper AI-driven personalization strategy
```

---

## /pupdate

Generate performance update (Pupdate style).

### Arguments

| Argument | Description |
|----------|-------------|
| `topic` | Update focus area |
| `--period` | Time period (week/month/quarter) |

### Output

Performance update includes:
- Key Accomplishments
- Metrics Movement
- Challenges & Blockers
- Next Period Focus
- Support Needed

### Usage

```
/pupdate --period week
/pupdate --period quarter Q1 2026 Summary
```

---

## /4cq

Generate 4CQ project definition.

### Arguments

| Argument | Description |
|----------|-------------|
| `project` | Project name |

### Output

4CQ document includes:
- Context (Why now?)
- Challenge (What problem?)
- Choices (What options?)
- Consequences (What outcomes?)

### Usage

```
/4cq Mobile app redesign
```

---

## /meeting-notes

Create meeting notes in Deo format.

### Arguments

| Argument | Description |
|----------|-------------|
| `meeting` | Meeting title or ID |
| `--from-transcript` | Create from transcript |

### Output

Meeting notes include:
- Attendees
- Agenda Items
- Discussion Summary
- Decisions Made
- Action Items (with owners)
- Follow-ups

### Usage

```
/meeting-notes "Sprint Planning 2026-01-13"
/meeting-notes --from-transcript
```

---

## /tribe-update

Generate quarterly tribe update.

### Arguments

| Argument | Description |
|----------|-------------|
| `tribe` | Tribe name |
| `--quarter` | Quarter (Q1/Q2/Q3/Q4) |

### Output

Tribe update includes:
- Quarter Highlights
- OKR Progress
- Key Metrics
- Squad Summaries
- Next Quarter Focus
- Resource Needs

### Usage

```
/tribe-update "Growth Division" --quarter Q1
```

---

## Common Features

### Context Awareness

All document commands:
- Load relevant Brain entities
- Reference current context
- Include related decisions
- Link to existing documents

### Output Formats

Documents are generated as Markdown files in:
```
user/planning/Documents/<type>/
```

### FPF Integration

Commands with `--fpf` flag:
1. Run full FPF reasoning cycle
2. Include Decision Rationale Record
3. Store evidence in Brain
4. Link to alternatives considered

### Deep Research

PRD and RFC use Deep Research for:
- Competitor analysis
- Prior art research
- Best practices
- Technical recommendations

---

## Related Documentation

- [Workflows](../04-workflows.md) - Document generation workflows
- [FPF Commands](fpf-commands.md) - Structured reasoning
- [Brain](../05-brain.md) - Knowledge context

---

*Last updated: 2026-01-13*
