# Master Sheet Integration Guide

> PM-OS Master Sheet Integration for Priority Tracking and Daily Planning

**Version:** 1.0.0
**Last Updated:** 2026-02-03

---

## Table of Contents

1. [Objectives](#objectives)
2. [Sheet Structure](#sheet-structure)
3. [How It Works](#how-it-works)
4. [Daily Workflow](#daily-workflow)
5. [Integration Points](#integration-points)
6. [Configuration](#configuration)
7. [CLI Reference](#cli-reference)
8. [Troubleshooting](#troubleshooting)

---

## Objectives

The Master Sheet integration serves three primary goals:

1. **Single Source of Truth**: Centralize priority tracking in Google Sheets where stakeholders can easily view and update status
2. **Automated Daily Planning**: Transform weekly commitments into actionable daily schedules
3. **Context Integration**: Ensure PM-OS daily context files always reflect current priorities and deadlines

### Key Benefits

- **Deadline visibility**: Surface overdue and upcoming items automatically
- **Workload distribution**: Suggested daily plans prevent overcommitment
- **Owner accountability**: All items have explicit owners
- **Progress tracking**: Calendar week (CW) columns show historical progress

---

## Sheet Structure

The Master Sheet consists of two main tabs:

### Topics Tab

Tracks one-time deliverables and project milestones.

| Column | Description | Required |
|--------|-------------|----------|
| Product | Product/brand code (e.g., BB, FF, MK) | Yes |
| Feature | Feature or initiative name | Yes |
| Action | Specific deliverable | Yes |
| Priority | P0, P1, P2, P3 | Yes |
| Current Status | To Do, In Progress, Done, Blocked | Yes |
| Responsible | Owner name | Yes |
| Consulted | Stakeholder(s) | No |
| Link | Reference document URL | No |
| Deadline | Due date (MM/DD/YYYY or YYYY-MM-DD) | Recommended |
| CW1, CW2... | Status per calendar week | Auto-tracked |

### Recurring Tab

Tracks recurring tasks and rituals.

| Column | Description | Required |
|--------|-------------|----------|
| Domain | Category (e.g., Operations, Planning) | Yes |
| Project | Project or team name | Yes |
| Action | Task description | Yes |
| Priority | P0, P1, P2, P3 | Yes |
| Responsible | Owner name | Yes |
| Consulted | Stakeholder(s) | No |
| Command | PM-OS command to run (e.g., `/sprint-report`) | No |
| Link | Reference URL | No |
| Recurrance | Frequency (Weekly, Bi-weekly, Monthly) | Yes |
| CW1, CW2... | To Do / Done per week | Auto-tracked |

---

## How It Works

### Sync Flow

```
Google Sheets → master_sheet_sync.py → Local Data
                        ↓
         master_sheet_context_integrator.py
                        ↓
              Daily Context File
```

### Daily Planning Algorithm

1. **Collect items**: Gather overdue + due this week + P0 items
2. **Sort by urgency**: Overdue → Due today → P0 → Due this week
3. **Distribute across days**: Max 5 items per day (Mon-Fri)
4. **Generate schedule**: Today's focus + week preview

### Priority Handling

| Priority | Treatment |
|----------|-----------|
| P0 | Always scheduled for today/tomorrow, appears in Critical Alerts |
| P1 | Scheduled based on deadline |
| P2 | Scheduled based on deadline, lower priority |
| P3 | Scheduled if capacity allows |

---

## Daily Workflow

### Morning (on /boot or /update-context)

1. Master Sheet is synced automatically
2. Context integrator generates:
   - Critical Alerts (overdue items)
   - Suggested Daily Plan
   - Master Sheet Summary tables
   - Action Items list

### During the Day

1. Complete items from "Today's Focus"
2. Update sheet directly in Google Sheets:
   - Change "Current Status" to "Done"
   - Add notes in CW column if needed

### End of Day (on /logout)

1. Final Master Sheet sync captures status changes
2. Context file updated with completion status

### Weekly Review

1. Review CW columns for progress patterns
2. Identify items that slipped multiple weeks
3. Adjust priorities as needed

---

## Integration Points

### /boot Command

```bash
# Runs automatically during boot
python3 "$PM_OS_COMMON/tools/master_sheet/master_sheet_sync.py"
```

Creates/updates:
- Feature folders in `$PM_OS_USER/products/`
- Brain entities in `$PM_OS_USER/brain/Entities/`
- Feature context files

### /update-context Command

```bash
# Step 1.8: Master Sheet Sync & Daily Planning
python3 "$PM_OS_COMMON/tools/master_sheet/master_sheet_sync.py"
python3 "$PM_OS_COMMON/tools/master_sheet/master_sheet_context_integrator.py"
```

Outputs context sections that are merged into the daily context file.

### /logout Command

```bash
# Step 4.6: Master Sheet Sync
python3 "$PM_OS_COMMON/tools/master_sheet/master_sheet_sync.py"
```

Captures any final status changes.

---

## Configuration

### config.yaml Setup

Add to `$PM_OS_USER/config.yaml`:

```yaml
master_sheet:
  enabled: true
  spreadsheet_id: "your-google-sheet-id"
  tabs:
    topics: "topics"      # Tab name for one-time items
    recurring: "recurring" # Tab name for recurring tasks
  product_mapping:
    BB: "brand-b"
    FF: "growth-platform"
    MK: "meal-kit"
    MI: "product-innovation"
  slack_channel: "CXXXXXXXXXX"  # For weekly summary posts
```

### Google OAuth

Requires Google Sheets API scope:
- `https://www.googleapis.com/auth/spreadsheets.readonly`

Run scope validator if needed:
```bash
python3 "$PM_OS_COMMON/tools/integrations/google_scope_validator.py" --fix
```

---

## CLI Reference

### master_sheet_sync.py

```bash
# Full sync (default)
python3 master_sheet_sync.py

# Show weekly summary
python3 master_sheet_sync.py --week

# Show overdue items only
python3 master_sheet_sync.py --overdue

# Show daily plan
python3 master_sheet_sync.py --daily

# Filter by owner
python3 master_sheet_sync.py --daily --owner "Jane"

# Get action items as JSON
python3 master_sheet_sync.py --action-items --json

# Post weekly summary to Slack
python3 master_sheet_sync.py --week --post-slack
```

### master_sheet_context_integrator.py

```bash
# Full context section (default)
python3 master_sheet_context_integrator.py

# Specific section only
python3 master_sheet_context_integrator.py --section alerts
python3 master_sheet_context_integrator.py --section daily
python3 master_sheet_context_integrator.py --section summary
python3 master_sheet_context_integrator.py --section actions

# Filter by owner
python3 master_sheet_context_integrator.py --owner "Jane"

# JSON output for programmatic use
python3 master_sheet_context_integrator.py --json
```

---

## Troubleshooting

### "Master Sheet integration not enabled"

**Cause**: Missing or invalid config
**Fix**: Add `master_sheet.enabled: true` and `spreadsheet_id` to config.yaml

### "Error reading tab"

**Cause**: Tab name mismatch or permissions
**Fix**:
1. Verify tab names in config match actual sheet tabs
2. Ensure Google OAuth token has sheets access

### Items not appearing in context

**Cause**: Missing required fields
**Fix**: Ensure Product, Feature/Project, and Action columns are filled

### Deadline not recognized

**Cause**: Invalid date format
**Fix**: Use MM/DD/YYYY or YYYY-MM-DD format

### Daily plan shows wrong items

**Cause**: Filter or date logic issue
**Fix**:
1. Check `--owner` filter matches sheet exactly (case-insensitive)
2. Verify deadline dates are in current week

---

## Best Practices

1. **Update sheet daily**: Mark items Done as you complete them
2. **Use consistent names**: Owner names should match across systems
3. **Set realistic deadlines**: Items without deadlines are deprioritized
4. **Review weekly**: Use CW columns to identify patterns
5. **Keep descriptions short**: Action field should be actionable (verb + noun)

---

## Related Documentation

- [Update Context Command](../common/.claude/commands/update-context.md)
- [Boot Command](../common/.claude/commands/boot.md)
- [Logout Command](../common/.claude/commands/logout.md)

---

*Generated by PM-OS Master Sheet Integration v1.0.0*
