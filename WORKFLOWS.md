# PM-OS Workflows Guide

Practical workflows for Product Managers using PM-OS daily.

---

## Table of Contents

1. [Daily Routines](#daily-routines)
2. [Context Management](#context-management)
3. [Meeting Workflows](#meeting-workflows)
4. [Document Generation](#document-generation)
5. [Decision Making](#decision-making)
6. [Sprint Ceremonies](#sprint-ceremonies)
7. [Stakeholder Communication](#stakeholder-communication)

---

## Daily Routines

### Morning Boot Sequence

**Goal:** Start your day with full context loaded.

```bash
# Start Claude Code
claude

# Full boot (recommended for first session)
/boot

# Or quick boot if you've already synced today
/boot quick
```

**What happens during boot:**
1. Git pull to sync any shared context
2. Core rules loaded (AGENT.md, Persona file)
3. Daily context updater runs
4. Hot topics identified from Brain
5. FPF reasoning state checked

**Expected output:**
```
Boot Complete
- Context: 2025-01-05-context.md loaded
- Hot Projects: OTP, Mobile App, API Migration
- Hot Entities: John (Eng Lead), Sarah (Design)
- FPF: 2 active cycles, 1 pending decision
```

### Mid-Day Context Refresh

**Goal:** Catch up on context changes without full reload.

```
/update-context quick
```

Or for specific sources:
```
/create-context extract -Sources "jira,slack" -Days 1
```

### End of Day Wrap-up

**Goal:** Save context and prepare for next session.

```
/logout
```

**What happens:**
1. Uncommitted context changes identified
2. Git commit with session summary
3. Any pending action items highlighted

---

## Context Management

### Full Context Pipeline

**When to use:** Weekly, after vacation, or for major sync.

```
/create-context full
```

**Duration:** 5-15 minutes depending on data volume.

**Sources pulled:**
- Google Docs (recent documents, shared with you)
- Gmail (important threads)
- Jira (your projects' epics, tickets, blockers)
- GitHub (PRs, commits, reviews)
- Slack (priority channels)

### Quick Context Refresh

**When to use:** Daily, between meetings.

```
/create-context quick
```

**Duration:** 1-2 minutes.

**Sources pulled:**
- Google Docs only
- Jira status changes

### Bulk Historical Import

**When to use:** Initial setup, rebuilding context.

```
/create-context bulk -Days 180
```

**Duration:** 30+ minutes (runs in background).

**Note:** Resumable - if interrupted, re-run to continue.

### Context Status Check

**When to use:** Troubleshooting, verification.

```
/create-context status
```

**Shows:**
- Last run timestamps for each source
- Pending analysis items
- Brain entity counts

---

## Meeting Workflows

### Pre-Meeting Preparation

**Goal:** Generate a pre-read with relevant context for upcoming meeting.

```
/meeting-prep
```

**Output:** Creates `Planning/Meeting_Prep/YYYY-MM-DD_Meeting_Title.md`

**Pre-read includes:**
- Meeting context and history
- Related Brain entities
- Open action items for attendees
- Recent relevant decisions
- Suggested talking points

### For Specific Meetings

```
# Prepare for specific meeting type
/meeting-prep "1:1 with John"

# Extended lookahead
/meeting-prep --hours 24
```

### During Meeting: Live Notes

**Goal:** Capture decisions and action items in real-time.

```
/meeting-notes
```

**Prompts for:**
- Meeting title
- Attendees
- Key discussion points

**Output format:**
```markdown
## Topic | 2025-01-05 | Attendees: John, Sarah, Mike

### Notes/Updates
- Discussed Q1 roadmap priorities
  - Mobile app launch is P0
  - API migration moves to Q2

### Decisions
- **Decision:** Delay API migration to Q2. Rationale: Mobile launch takes priority.

### Action Items
- [ ] **John**: Share technical spec by Friday
- [ ] **Sarah**: Update roadmap slide
- [ ] **You**: Schedule follow-up with stakeholders
```

### Post-Meeting: Brain Update

After significant meetings, update relevant Brain entities:

```
# The assistant will prompt which entities to update
"Update the Mobile_App project with today's meeting decisions"
```

---

## Document Generation

### Product Requirements Document (PRD)

**Goal:** Generate a structured PRD with context from Brain.

```
/prd "Feature: User Authentication Redesign"
```

**Prompts for:**
- Customer persona
- Problem statement
- Success metrics
- Technical constraints

**Output:** Full PRD following your company's template, pre-filled with:
- Related projects from Brain
- Technical context from Architecture entities
- Stakeholder information
- Previous decisions on similar topics

### Deep Research PRD

For complex features requiring market research:

```
/prd "Feature: AI-Powered Recommendations" --deep-research
```

**Additional analysis:**
- Competitor approaches
- Industry best practices
- Technical feasibility assessment

### Four Critical Questions (4CQ)

**Goal:** Quick problem definition before detailed work.

```
/4cq "New Checkout Flow"
```

**Output:**
```markdown
## New Checkout Flow - 4CQ Definition

### 1. Who is the customer?
[First-time buyers who abandon at payment]

### 2. What is the problem?
[Complex checkout flow with 5 steps causes 40% drop-off]

### 3. What is the solution?
[Single-page checkout with saved payment methods]

### 4. What is the primary benefit?
[Reduce checkout abandonment by 20%, increase CVR]
```

### Strategic Whitepaper

**Goal:** Persuasive strategic proposal for leadership.

```
/whitepaper "Platform API Strategy 2025"
```

**Structure:**
1. Executive Summary
2. Current State / Problem
3. Strategic Vision
4. Proposed Mechanisms
5. Roadmap
6. Risks & Mitigations
7. Resource Requirements

### Performance Update (Pupdate)

**Goal:** Data-dense performance report.

```
/pupdate
```

**Prompts for:**
- Reporting period
- Key metrics to highlight
- Notable events

**Output:** Performance report with:
- Metrics with WoW/YoY comparisons
- Hypothesis for metric movements
- Channel/segment breakdowns
- Forward-looking guidance

---

## Decision Making

### Simple Decisions

For straightforward choices, just ask:

```
"Should we use PostgreSQL or MongoDB for the user service?"
```

The assistant will:
- Reference relevant Architecture entities
- Consider previous similar decisions
- Provide recommendation with rationale

### Complex Decisions: FPF Workflow

For high-stakes, ambiguous decisions, use First Principles Framework.

#### Step 1: Initialize

```
/q0-init "Should we build vs buy the recommendation engine?"
```

**Output:** Creates reasoning cycle with:
- Problem statement
- Initial constraints identified
- Stakeholders mapped

#### Step 2: Generate Hypotheses

```
/q1-hypothesize
```

**Output:** Multiple competing hypotheses:
- H1: Build in-house (full control, higher cost)
- H2: Buy vendor solution (faster, less customization)
- H3: Hybrid approach (core in-house, commodity outsourced)

#### Step 3: Add Your Hypothesis (Optional)

```
/q1-add "What about open-source with managed hosting?"
```

#### Step 4: Verify Logic

```
/q2-verify
```

**Output:** Deductive analysis:
- Logical consistency check
- Assumption identification
- Dependency mapping

#### Step 5: Validate with Evidence

```
/q3-validate
```

**Output:** Evidence collection:
- Links to supporting documents
- Data points cited
- Expert opinions referenced

#### Step 6: Audit Evidence Quality

```
/q4-audit
```

**Output:** Trust assessment:
- Evidence freshness
- Source reliability
- Confidence levels

#### Step 7: Make Decision

```
/q5-decide
```

**Output:** Design Rationale Record (DRR):
- Final recommendation
- Supporting evidence summary
- Dissenting views captured
- Implementation guidance

#### Check Status Anytime

```
/q-status
```

---

## Sprint Ceremonies

### Sprint Planning

```
# Load Jira context first
/jira-sync

# Then discuss sprint scope
"Help me plan sprint 23 based on current backlog"
```

### Sprint Report Generation

**Goal:** Create comprehensive sprint report.

```
/sprint-report
```

**Prompts for:**
- Sprint number/dates
- Key accomplishments
- Blockers encountered
- Metrics

**Output:** Sprint report with:
- Velocity analysis
- Commitment vs completion
- Carry-over items
- Retrospective themes

### Backlog Grooming

```
"Review the top 10 backlog items and suggest prioritization"
```

The assistant will:
- Pull items from Jira context
- Apply ICE/RICE scoring
- Consider dependencies
- Suggest sequencing

---

## Stakeholder Communication

### Status Email Draft

```
"Draft a status email for leadership on the Mobile App launch"
```

**Output:** Email draft following your tone/style from Persona.

### Escalation Communication

```
"Draft an escalation email about the API dependency blocker"
```

**Includes:**
- Clear problem statement
- Impact assessment
- Requested action
- Timeline

### Presentation Outline

```
"Create an outline for my Q1 roadmap presentation to executives"
```

**Output:** Slide-by-slide outline with:
- Key messages per slide
- Data points to include
- Anticipated questions

---

## Advanced Patterns

### Multi-Project Context

When working across projects:

```
"Compare progress between Mobile App and API Migration projects"
```

### Knowledge Transfer

When onboarding someone:

```
"Create an onboarding summary for the Checkout project"
```

### Historical Analysis

```
"What decisions have we made about payment processing in the past 6 months?"
```

### Relationship Mapping

```
"Show me how the Authentication system relates to other services"
```

---

## Workflow Tips

### 1. Start Every Session with /boot

Never skip the boot sequence - it ensures you have current context.

### 2. Use Brain References

When discussing topics, reference Brain entities:
```
"Update [[Projects/Mobile_App.md]] with the new timeline"
```

### 3. Capture Decisions Immediately

After any decision, ask:
```
"Add this decision to the Brain"
```

### 4. Regular Brain Maintenance

Weekly:
```
/synapse
```

This rebuilds relationship links between entities.

### 5. Evidence Decay Check

For long-running decisions:
```
/q-decay
```

Identifies evidence that may be stale.

---

## Troubleshooting Workflows

### "Context seems outdated"

```
/create-context full -Days 7
```

### "Missing project context"

```
"Create a Brain entry for [Project Name]"
```

### "Can't find previous decision"

```
/q-query "payment processing decision"
```

### "Need to reset reasoning"

```
/q-reset
```

---

*For more details, see README.md and individual command documentation in `.claude/commands/`*
