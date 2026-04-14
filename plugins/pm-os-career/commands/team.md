---
description: Team management — career planning, scorecards, 1:1 prep
---

# Team

Team management — career planning, interview scorecards, 1:1 prep, and team operations.

## Arguments
$ARGUMENTS

## Instructions

Parse the first argument to determine which subcommand to run:

| Subcommand | Description |
|------------|-------------|
| `career-plan` | Career planning system |
| `interview` | Interview scorecard generation and management |
| `one-on-one` | 1:1 meeting preparation |
| `operations` | Team capacity, hiring pipeline, org chart |
| *(no args)* | Show available subcommands |

If no arguments provided, display available subcommands:
```
Team - Team management

  /team career-plan -create "Name"     - Initialize career plan
  /team career-plan -WHAT "Name" S2026 - Generate WHAT section
  /team career-plan -HOW "Name" S2026  - Generate HOW section
  /team career-plan -status "Name"     - Show tracking status
  /team career-plan -sync "Name"       - Sync projects and feedback
  /team interview --scorecard "Name"   - Generate interview scorecard
  /team interview --list               - List all scorecards
  /team interview --search "query"     - Search scorecards
  /team one-on-one "Name"              - Prep 1:1 for direct report
  /team one-on-one --list              - List upcoming 1:1s
  /team operations --capacity          - Team capacity overview
  /team operations --hiring            - Hiring pipeline status
  /team operations --org               - Org chart

Usage: /team <subcommand> [options]
```

---

### career-plan

Career planning system for team members, tracking projects and feedback over review cycles.

**Flags:**

| Flag | Example | Purpose |
|------|---------|---------|
| `-create` | `/team career-plan -create "Alex"` | Initialize career plan |
| `-WHAT` | `/team career-plan -WHAT "Alex" S2026` | Generate "What" (projects) section |
| `-HOW` | `/team career-plan -HOW "Alex" S2026` | Generate "How" (behavioral) section |
| `-status` | `/team career-plan -status "Alex"` | Show tracking status |
| `-sync` | `/team career-plan -sync "Alex"` | Force sync projects and feedback |

**Cycle Format:** Main cycles: `S2025`, `S2026` (Summer/May-to-May). Off-cycles: `W2025`, `W2026` (Winter check-ins).

#### -create {NAME}

Initialize a career plan for a team member.

**Step 1: Resolve Person**

```python
from career_plan_generator import CareerPlanGenerator
generator = CareerPlanGenerator()
person = generator.resolve_person(name)
```

If Brain plugin is available, load the person entity for additional context. Otherwise, look up the person in `get_config().get("team.reports", [])`.

**Step 2: Determine Cycle**

If no cycle provided, auto-detect based on current date:
- Jan-Apr: previous cycle (e.g., `S2025`)
- May-Dec: current cycle (e.g., `S2026`)

**Step 3: Create Plan Structure**

Create directory and files:
```
$PM_OS_USER/team/reports/{person-slug}/career/
├── Career_Plan_{CYCLE}.md
├── project_log.md
└── feedback_log.md
```

Use the career plan template with sections:
1. Background Information (table with name, title, hire date, ratings, tenure)
2. The Future Role (scope change description)
3. Promotion Case — Business Need
4. Readiness — WHAT (body of work)
5. Readiness — HOW (behavioral evidence)
6. Key Risks to Coach/Manage
7. Peer Feedback

**Step 4: Report**

Report: file paths created, person name, cycle, next steps.

---

#### -WHAT {NAME} {CYCLE}

Generate the WHAT (body of work) section.

**Step 1: Load Context**

1. Read career plan file
2. Read project_log.md
3. Gather from: 1:1 meeting notes, context documents
4. If Brain available, query person entity for project associations

**Step 2: Rank Projects**

Rank by impact: frequency of mention, ownership level, outcomes, cross-team scope, complexity.

**Step 3: Generate Narrative**

Generate 3-5 paragraphs covering:
- Scope & Influence — scale and breadth of ownership
- Impact — measurable outcomes and business results
- Ambiguity — complexity of problems tackled

Reference the career framework competencies for the target level.

**Step 4: Update Plan**

Replace the WHAT placeholder in Career_Plan_{CYCLE}.md with the generated narrative.

---

#### -HOW {NAME} {CYCLE}

Generate the HOW (behavioral evidence) section.

**Step 1: Load Context**

1. Read career plan and feedback_log.md
2. Gather from: 1:1 notes, peer feedback
3. If Brain available, query person entity for behavioral signals

**Step 2: Map to Competency Framework**

Map feedback entries to competency dimensions (configurable via `get_config().get("career.competency_dimensions")`). Default dimensions:
- Speed & Agility
- Data-Drivenness
- Egolessness
- Customer Centricity
- Ownership

**Step 3: Generate Narrative**

Generate 3-5 paragraphs describing how they achieved deliverables, referencing the competency framework.

**Step 4: Update Plan**

Replace the HOW placeholder in Career_Plan_{CYCLE}.md.

---

#### -status {NAME}

Show career tracking status: last sync date, project count, feedback count, plan completeness.

```python
from career_plan_generator import CareerPlanGenerator
generator = CareerPlanGenerator()
status = generator.get_status(name)
```

Display as a table with completeness indicators.

---

#### -sync {NAME}

Force sync project and feedback logs from 1:1 notes and context documents.

```python
from career_plan_generator import CareerPlanGenerator
generator = CareerPlanGenerator()
result = generator.sync_logs(name)
```

Report: new entries added, sources scanned, last sync timestamp.

---

### interview

Interview scorecard generation and management.

**Flags:**

| Flag | Description |
|------|-------------|
| `--scorecard "Name"` | Generate scorecard for candidate by name |
| `--list` | List all existing scorecards |
| `--search "query"` | Search scorecards by candidate name, role, or verdict |
| `--batch "Name1, Name2, Name3"` | Generate multiple scorecards in one go |

---

#### --scorecard "Name"

Generate a structured interview scorecard for a candidate.

**Step 1: Gather Context**

Ask the user (if not already provided):
1. **Candidate name** — from the flag value
2. **Role** - e.g., "Senior Product Manager, Growth Squad"
3. **Verdict** — one of: Strong Yes `(++)`, Soft Yes `(+)`, Soft No `(-)`, Strong No `(--)`.
4. **Interview date** — ask or infer from transcript

**Step 2: Find Transcript**

Search GDrive for the interview transcript:
1. Search by candidate name: `mcp__gdrive__gdrive_search` with the candidate's name
2. If no result, search by last name only
3. If no result, search meeting prep files
4. If no result, search by role title + date
5. If transcript found, read it via `mcp__gdrive__gdrive_read`

If no transcript is found, offer to:
- Generate a placeholder scorecard (marked as "pending transcript")
- Generate from the user's verbal recall

**Step 3: Generate Scorecard**

```python
from interview_scorecard import InterviewScorecardGenerator
generator = InterviewScorecardGenerator()
scorecard = generator.generate(
    candidate_name=name,
    role=role,
    verdict=verdict,
    interview_date=date,
    transcript=transcript,
)
```

Use this format:

```markdown
# [Role Title] Interview Scorecard — [Candidate Name]

**Role:** [Full role title]
**Hiring Manager Interview:** [Manager name from config]
**Date:** [Generation date]

---

## [Candidate Name] — ([Verdict Symbol])

**Interview Date:** [Date] | **Duration:** ~[N] min | **Verdict: [Verdict Text]**

### Key Take-Aways

**Conclusions:**
- [3-6 substantive paragraphs with specific transcript examples]

**Pros:**
- **[Label]:** [Evidence-backed positive signal]

**Cons:**
- **[Label]:** [Evidence-backed concern]

**Follow-ups:**
- [ ] **Recommendation:** [Advance/Do not advance]
- [ ] [Validation items for next round]

---

## Assessment Summary

| Dimension | Rating | Notes |
|-----------|--------|-------|
| **Systems Thinking** | [Rating] | [Note] |
| **Cross-Functional Influence** | [Rating] | [Note] |
| **Data Fluency** | [Rating] | [Note] |
| **Execution under Ambiguity** | [Rating] | [Note] |
| **Communication** | [Rating] | [Note] |
| **Customer Centricity** | [Rating] | [Note] |
| **AI Fluency** | [Rating] | [Note] |

**Overall: ([Symbol]) [Verdict]** — [2-3 sentence summary]
```

**Step 4: Save**

Save to configured path (default: `user/team/recruiting/interviews/`):
```
{DATE}-{role-slug}-interview-scorecard-{candidate-slug}.md
```

**Step 5: Confirm**

Report: file path, candidate name, verdict, transcript found status.

---

#### --batch "Name1, Name2, Name3"

Generate multiple scorecards. For each candidate:
1. Ask the user for role and verdict
2. Follow `--scorecard` flow for each
3. If same role/round, offer to combine into single file

---

#### --list

List all scorecards in the configured interviews directory:
```bash
ls -la "$PM_OS_USER/team/recruiting/interviews/"*.md
```

Display as table: Date | Candidate(s) | Role | Verdict.

---

#### --search "query"

Search scorecards by content. Display matching files with context.

---

### one-on-one

Prepare for 1:1 meetings with direct reports, manager, or stakeholders.

**Arguments:**
- `"Name"` — Prep 1:1 for a specific person
- `--list` — List upcoming 1:1 meetings

#### "Name"

**Step 1: Resolve Person**

Look up in config reports, manager, or stakeholders. Determine relationship type (report, manager, stakeholder).

**Step 2: Gather Context**

```python
from one_on_one_prep import OneOnOnePreparer
preparer = OneOnOnePreparer()
prep = preparer.prepare(person_name=name)
```

Sources:
1. Previous 1:1 notes from `user/team/{category}/{person-slug}/1on1s/`
2. If Brain available, load person entity for recent context
3. Open action items from previous meetings
4. Daily context for relevant updates

**Step 3: Generate Prep**

Structure:
1. **Check-in** — What's top of mind? (carry forward open items)
2. **Blockers** — Known blockers relevant to this person
3. **Projects** — Quick status on their key initiatives
4. **Development** — Coaching/feedback if relevant (career plan context)
5. **Asks** — What do you need from them / they need from you?

**Step 4: Save and Present**

Save to `user/team/{category}/{person-slug}/1on1s/{DATE}-prep.md`. Present the prep document.

---

### operations

Team capacity planning, hiring pipeline, and org chart.

**Flags:**

| Flag | Description |
|------|-------------|
| `--capacity` | Team capacity overview |
| `--hiring` | Hiring pipeline status |
| `--org` | Generate org chart |

#### --capacity

Scan team config and generate capacity overview:
- Total headcount by team
- Open positions (from config or user/team/recruiting/)
- Allocation by initiative

#### --hiring

Show hiring pipeline status from `user/team/recruiting/`:
- Open roles
- Candidates in pipeline (from scorecard files)
- Recent interview activity

#### --org

Generate a text-based org chart from config:
- Manager at top
- Direct reports with team assignments
- Stakeholders as dotted lines

---

**Examples:**
- `/team career-plan -create "Alex"` - Initialize career plan for Alex
- `/team career-plan -WHAT "Jordan" S2026` - Generate WHAT section
- `/team interview --scorecard "Sam Chen"` - Generate scorecard
- `/team interview --list` - List all scorecards
- `/team one-on-one "Taylor"` - Prep 1:1 for Taylor
- `/team operations --org` - Show org chart
