# Tech Platform Sprint Sync

Sync the Tech Platform Every Other Week Squad Sprint Report to Brain for tribe-wide context.

## Arguments

$ARGUMENTS

Options:
- (none) - Full sync of all squads
- `--status` - Show last sync status
- `--squad "Name"` - Show specific squad's report
- `--tribe "Name"` - Filter by tribe (e.g., "Growth Division")

## Overview

The Tech Platform Sprint Report is a tribe-wide spreadsheet that captures:
- **Squad deliverables** across all Tech Platform tribes
- **KPI movements** and sprint health
- **Planned work** for upcoming sprints
- **Key learnings** and experiments

This provides invaluable cross-squad context for understanding what's happening across the organization.

## Instructions

### Full Sync (Default)

```bash
python3 "$PM_OS_COMMON/tools/integrations/tech-platform_sprint_sync.py"
```

This will:
1. Fetch all squad data from the spreadsheet
2. Parse Mega-Alliance, Squad, Tribe, KPI, Delivered, Planned, etc.
3. Save individual squad files to `brain/Inbox/Tech Platform_Sprint/`
4. Generate a combined summary file
5. Update sync state for tracking

### Check Status

```bash
python3 "$PM_OS_COMMON/tools/integrations/tech-platform_sprint_sync.py" --status
```

Shows:
- Last sync timestamp
- Number of squads synced
- Tribes captured

### View Specific Squad

```bash
python3 "$PM_OS_COMMON/tools/integrations/tech-platform_sprint_sync.py" --squad "Meal Kit"
```

### Filter by Tribe

```bash
python3 "$PM_OS_COMMON/tools/integrations/tech-platform_sprint_sync.py" --tribe "Growth Division"
```

## Output

Synced data is saved to `brain/Inbox/Tech Platform_Sprint/`:

```
brain/Inbox/Tech Platform_Sprint/
├── _sync_state.json              # Sync metadata
├── Tech Platform_Sprint_Summary_YYYY-MM-DD.md  # Combined summary
├── Meal_Kit.md                  # Individual squad files
├── Brand_B.md
├── Growth_Platform.md
└── ...
```

### Squad File Format

```markdown
---
type: tech-platform_sprint_report
squad: Meal Kit
tribe: Growth Division
mega_alliance: Consumer
synced_at: 2026-02-04T12:00:00
source: Tech Platform Every Other Week Squad Sprint Report
---

## Meal Kit
**Tribe:** Growth Division
**Mega-Alliance:** Consumer

### KPI Movement
+2.1% (Conversion Rate)

### Delivered (Last Sprint)
- OTP checkout flow shipped
- Auth guard fixes
- Dashboard improvements

### Planned (Next Sprint)
- Benefits communication
- Payment optimization
```

## Configuration

In `user/config.yaml`:

```yaml
tech-platform_sprint:
  enabled: true
  spreadsheet_id: "SPREADSHEET_ID_EXAMPLE"
  sync_on_boot: true
  sync_frequency: "biweekly"
  tribes_of_interest:
    - "Growth Division"
    - "Consumer"
```

## Integration with Boot

When `sync_on_boot: true`, the `/boot` command will automatically sync Tech Platform sprint data as part of context gathering.

## Use Cases

1. **Pre-meeting context** - Understand what other squads are working on
2. **Cross-squad dependencies** - Identify related work in other tribes
3. **Leadership prep** - Quick overview of tribe-wide progress
4. **Sprint planning** - See what others delivered for reference
5. **Brain enrichment** - Add organizational context to knowledge base

## Source

- **Spreadsheet:** [Tech Platform Every Other Week Squad Sprint Report](https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_EXAMPLE)
- **Owner:** Tech Platform Team
- **Cadence:** Bi-weekly (aligned with sprint cycles)
