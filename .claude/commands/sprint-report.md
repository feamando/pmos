# Sprint Report Generator v1.3

Generate bi-weekly sprint reports with clustered, prioritized work items and external-facing summaries.

## Arguments
$ARGUMENTS

## v1.3 Improvements

Based on leadership feedback, this version adds external-facing columns:

| Feedback | Solution |
|----------|----------|
| "Too verbose" | New External columns with concise numbered format |
| "Learnings too long" | External learnings: "Identified X, resulting in Y" |
| "Need numbered priorities" | External format uses 1., 2. numbering |

## v1.2 Improvements (Retained)

| Feedback | Solution |
|----------|----------|
| "Peanut Buttering" | Clusters work into Sprint Focus + 2 priorities max |
| Data Dumps | Synthesizes tickets into outcome-focused sentences |
| Infrastructure vs Value | Prompts emphasize business value and outcomes |
| Lack of Prioritization | Ranks by epic effort/story points |
| Ship to Prod | Explicitly mentions production deployments |

## Instructions

### Default: Generate Full Sprint Report

**Step 1:** Run the sprint report generator for Growth Division squads:

```bash
python3 "$PM_OS_COMMON/tools/reporting/sprint_report_generator.py"
```

This will:
- Load squads from `squad_registry.yaml`
- Fetch Jira issues with full details (epic links, story points, descriptions)
- **Cluster tickets by epic** into Sprint Focus, Secondary, Tertiary priorities
- **Synthesize clusters** into 1-3 sentence summaries using Gemini
- Include GitHub PR activity from Brain
- Include active experiments linked to squads
- Output CSV to `Reporting/Sprint_Reports/Sprint_Report_MM-DD-YYYY.csv`

**Step 2:** Generate Key Learnings for all squads:

After the CSV is generated, run the learnings generator:

```
/sprint-learnings all
```

This analyzes delivered items and generates structured learnings (Learning/Evidence/Action format) for each squad, saving them back to the CSV.

### Options

| Flag | Description |
|------|-------------|
| `--squad "Name"` | Generate for specific squad only |
| `--output "path"` | Custom output file path |

### Examples

```bash
# All Growth Division squads
python3 "$PM_OS_COMMON/tools/reporting/sprint_report_generator.py"

# Specific squad
python3 "$PM_OS_COMMON/tools/reporting/sprint_report_generator.py" --squad "Meal Kit"

# Custom output
python3 "$PM_OS_COMMON/tools/reporting/sprint_report_generator.py" --output "my_report.csv"
```

## Report Columns

| Column | Source |
|--------|--------|
| Mega-Alliance | Registry |
| Tribe | Registry |
| Squad | Registry |
| KPI Movement | Manual entry |
| Delivered | Jira (Done, last 14d) - **Clustered & Synthesized** (Internal) |
| **Delivered External** | v1.3: Concise numbered format for external sharing |
| Key Learnings | Claude-generated via `/sprint-learnings` (Internal) |
| **Learnings External** | v1.3: "Identified/Learned X, resulting in Y" format |
| Planned | Jira (Active Sprint/Backlog) - **Clustered & Synthesized** (Internal) |
| **Planned External** | v1.3: Concise numbered format for external sharing |
| GitHub Activity | Brain/GitHub/PR_Activity.md |
| Active Experiments | Brain/Experiments/*.md |
| Demo | Manual entry |

## Output Format (v1.3)

### Internal Columns (Delivered / Planned)

Work is presented as prioritized, synthesized summaries with full context:

```
**Sprint Focus:** Shipped the complete OTP checkout flow to production, enabling customers to place one-time purchases without a subscription. This directly addresses the 15% cart abandonment rate from users who want single purchases. [MK-3441, MK-3442, MK-3443]

**Secondary Priority:** Resolved critical security gaps in dashboard authentication by adding proper auth guards, ensuring only logged-in users can access sensitive account data. [MK-3445, MK-3446]

**Tertiary Priority:** Maintenance work including 3 bug fixes for edge cases in the payment flow. [MK-3447, MK-3448, MK-3449]
```

### External Columns (Delivered External / Planned External) - v1.3

Concise numbered format for quick scanning by leadership:

```
1. OTP Checkout: Full checkout flow shipped to production, focusing on reducing 15% cart abandonment and includes:
   - Guest checkout experience
   - Payment integration
   - Order confirmation flow

2. Security Hardening: Auth guard implementation completed, focusing on compliance requirements and includes:
   - Dashboard authentication
   - Session management fixes
```

### Internal Key Learnings Format

The Key Learnings column auto-generates structured insights from delivered tickets:

```
**Learning:** [Pattern or insight title]
**Evidence:** [Specific ticket references and what happened]
**Action:** [Recommended action]

---

**Learning:** [Next insight]
...

**Sprint Health Signals:**
- **Positive:** [What went well]
- **Watch:** [Areas needing attention]
```

### External Learnings Format (Learnings External) - v1.3

Concise bullets for external sharing:

```
- Identified need for proactive security hardening, resulting in auth guard review added to module checklist
- Learned experiment monitoring requires regular cadence, resulting in weekly health review process
- Identified data hygiene debt from rapid iteration, resulting in cleanup scripts built alongside features
```

## Clustering Logic

Tickets are automatically clustered by:

1. **Epic grouping** - Tickets under the same epic form a cluster
2. **Effort ranking** - Clusters ranked by total story points
3. **Priority assignment** - Top cluster = Sprint Focus, next = Secondary, etc.
4. **Orphan handling** - Tickets without epics grouped by type (bugs vs other)

## Prerequisites

- `squad_registry.yaml` with squad definitions including `jira_project`
- Jira API access (via config)
- Gemini API key (for synthesis)
- GitHub Brain data (run `/github-sync` first)
