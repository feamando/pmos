# Sprint Report Generator

Generate bi-weekly sprint reports by actively fetching Jira data and summarizing with Gemini.

## Arguments
$ARGUMENTS

## Instructions

### Default: Generate Full Sprint Report

Run the sprint report generator for Growth Division squads:

```bash
python3 "$PM_OS_COMMON/tools/reporting/sprint_report_generator.py"
```

This will:
- Load squads from `squad_registry.yaml`
- Fetch Jira issues (Done in last 14d, Active Sprint)
- Summarize delivered work, learnings, and planned items using Gemini
- Include GitHub PR activity from Brain
- Include active experiments linked to squads
- Output CSV to `Reporting/Sprint_Reports/Sprint_Report_MM-DD-YYYY.csv`

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
| Delivered | Jira (Done, last 14d) + Gemini summary |
| Key Learnings | Gemini-extracted from delivered items |
| Planned | Jira (Active Sprint/Backlog) + Gemini summary |
| GitHub Activity | Brain/GitHub/PR_Activity.md |
| Active Experiments | Brain/Experiments/*.md |
| Demo | Manual entry |

## Prerequisites

- `squad_registry.yaml` with squad definitions
- Jira API access (via `jira_mcp/server.py`)
- Gemini API key in config
- GitHub Brain data (run `/github-sync` first)
