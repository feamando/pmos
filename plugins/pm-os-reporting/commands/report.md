---
description: Sprint reports, performance updates, and organizational reporting
---

# /report -- Reporting & Performance Updates

Parse the first argument to determine which subcommand to run:

| Subcommand | Description |
|------------|-------------|
| `sprint` | Generate sprint report (CSV with clustered Jira data) |
| `pupdate` | Generate performance update with metrics and WoW/YoY |
| `quarterly-update` | Generate department-level quarterly planning document |
| `sprint-learnings` | Generate sprint learnings from delivered work |
| *(no args)* | Show available subcommands |

## Arguments
$ARGUMENTS

## No Arguments -- Show Help

If no arguments provided, display:

```
Report -- Reporting & Performance Updates

  /report sprint                        - Generate sprint report (CSV)
  /report sprint --team "My Team"     - Report for specific team
  /report sprint --sprint-start 2026-03-17 --sprint-end 2026-03-31  - Historical
  /report pupdate "Product Name"        - Generate performance update
  /report pupdate "Product Name" --output path.md  - Custom output
  /report quarterly-update                       - Generate quarterly update
  /report quarterly-update --department "Dept"   - Specific department
  /report quarterly-update --orthogonal          - With orthogonal challenge review
  /report sprint-learnings              - Generate sprint learnings

Usage: /report <subcommand> [options]
```

---

## sprint

Generate a sprint report with Jira data, clustering, and narrative synthesis.

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Run Generator

```bash
python3 "$PLUGIN_ROOT/tools/sprint_report_generator.py"
```

**With options:**
```bash
# Specific team
python3 "$PLUGIN_ROOT/tools/sprint_report_generator.py" --team "My Team"

# Specific department
python3 "$PLUGIN_ROOT/tools/sprint_report_generator.py" --department "My Department"

# Historical date range
python3 "$PLUGIN_ROOT/tools/sprint_report_generator.py" --sprint-start 2026-03-17 --sprint-end 2026-03-31

# Custom output
python3 "$PLUGIN_ROOT/tools/sprint_report_generator.py" --output "/path/to/report.csv"
```

### Step 3: Synthesize Narrative Summaries

The generator produces structured data (clustered tickets, ticket keys, GitHub PRs). After running, **you must synthesize** the Delivered, Planned, and External columns into narrative prose. For each team's clusters:

#### Cluster Summary (Delivered / Planned columns)

For each priority cluster, write 1-3 flowing sentences:
- Describe WHAT was built and shipped to production (delivered) or will be built (planned)
- Explain the BUSINESS VALUE or outcome — connect to user/business impact
- For delivered: emphasize what shipped. For planned: set clear delivery expectations
- NO bullet points — write flowing, professional sentences
- DO NOT include ticket keys or numbers in the narrative — they go in separate columns
- Focus on OUTCOMES and VALUE, not technical implementation details
- Be concise — leadership reads quickly
- Avoid jargon — use business language
- Sprint Focus clusters get 1-3 sentences; Secondary clusters get 1-2 sentences

#### External Format (Delivered External / Planned External columns)

Generate a CONCISE numbered summary for external stakeholders:

```
1. [[Theme Name]]: [[One-line milestone description]], focusing on [[business metric/outcome]] and includes:
   - [[Sub-feature/experience 1]]
   - [[Sub-feature/experience 2]]

2. [[Theme Name]]: [[One-line milestone description]], focusing on [[business metric/outcome]] and includes:
   - [[Sub-feature 1]]
```

Rules: number each priority, one main sentence per priority, include "focusing on [[metric/outcome]]", 2-4 bullet sub-features per priority, NO ticket numbers, be CONCISE.

#### External Learnings (Learnings External column)

Convert internal learnings to external bullet format:
- Start each bullet with "Identified" or "Learned"
- End with "resulting in [[specific action]]"
- REMOVE all ticket numbers and evidence details
- COMBINE Learning + Action into single line
- Maximum 5 bullets

### Step 4: Present Results

Report: Output CSV path, teams processed, tickets fetched per team.

**Output format:** CSV with columns: Division, Department, Team, KPI Movement, Delivered, Delivered External, Key Learnings, Learnings External, Planned, Planned External, GitHub Activity, Active Experiments, Demo, Delivered Tickets, Planned Tickets.

---

## pupdate

Generate a performance update ("pupdate") with structured metrics.

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Run Generator

```bash
python3 "$PLUGIN_ROOT/tools/performance_updater.py" "Product Name"
```

**With options:**
```bash
# Custom output
python3 "$PLUGIN_ROOT/tools/performance_updater.py" "Product Name" --output "/path/to/pupdate.md"
```

### Step 3: Present Results

Report: Headline summary, metrics table (WoW/YoY), trend indicators, output path.

**Pupdate style rules:**
- Data density: high — include raw numbers and % changes (WoW, YoY)
- Hypothesis-driven: always explain WHY a metric moved
- Structure: Headline -> Key Metrics -> Channel Breakdown -> Hypotheses -> Looking Ahead

---

## quarterly-update

Generate a department-level quarterly planning document.

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Run Generator

```bash
python3 "$PLUGIN_ROOT/tools/tribe_quarterly_update.py"
```

**With options:**
```bash
# Specific department
python3 "$PLUGIN_ROOT/tools/tribe_quarterly_update.py" --department "My Department"

# Specific quarter
python3 "$PLUGIN_ROOT/tools/tribe_quarterly_update.py" --quarter Q2-2026 --prev-quarter Q1-2026

# With orthogonal challenge
python3 "$PLUGIN_ROOT/tools/tribe_quarterly_update.py" --orthogonal

# Custom output
python3 "$PLUGIN_ROOT/tools/tribe_quarterly_update.py" --output "/path/to/update.md"

# JSON output
python3 "$PLUGIN_ROOT/tools/tribe_quarterly_update.py" --json

# List existing updates
python3 "$PLUGIN_ROOT/tools/tribe_quarterly_update.py" --status
```

### Step 3: Present Results

Report: Department name, quarter, output path, sections populated, next steps (fill brackets, add metrics, optional orthogonal review).

**Document sections:**
1. Executive Summary with key metrics
2. Systemic Blockers with root cause analysis
3. Key Learnings and failure analysis
4. Goals and Roadmap table
5. Cross-functional dependencies
6. Hot debates / open questions

---

## sprint-learnings

Generate sprint learnings from the delivered work in the latest sprint report.

### Step 1: Locate Latest Sprint Report

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
```

Find the most recent sprint report CSV in the reporting output directory.

### Step 2: Analyze Delivered Work

For each team's delivered items:
1. Read the ticket details and synthesized summaries
2. Identify patterns: what went well, what was challenging, what was learned
3. Generate structured learnings in internal format:

```
**Learning:** [Key insight about process/technology/market]
**Evidence:** [Ticket references and data points]
**Action:** [Concrete next step to apply the learning]
```

### Step 3: Generate External Format

Convert internal learnings to external format:
- Identified [issue/opportunity], resulting in [action taken by team]
- Learned [insight], resulting in [process/behavior change]

### Step 4: Update Sprint Report

If the sprint report CSV exists, update the Key Learnings and Learnings External columns.

---

## Execute

Parse arguments and run the appropriate report subcommand. If arguments match multiple subcommands, prefer the most specific match.
