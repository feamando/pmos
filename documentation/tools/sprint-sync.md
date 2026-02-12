# Tech Platform Sprint Sync

The Tech Platform Sprint Sync tool provides tribe-wide visibility into sprint deliverables, KPIs, and learnings across all Tech Platform squads. It automatically fetches data from the bi-weekly Sprint Report spreadsheet and stores it in Brain for context enrichment.

## Overview

| Property | Value |
|----------|-------|
| Command | `/tech-platform-sync` |
| Tool | `common/tools/integrations/tech-platform_sprint_sync.py` |
| Source | [Tech Platform Every Other Week Squad Sprint Report](https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_EXAMPLE) |
| Output | `brain/Inbox/Tech Platform_Sprint/` |
| Coverage | 98+ squads across 28 tribes |

## Usage

```bash
# Full sync of all squads
/tech-platform-sync

# Check last sync status
/tech-platform-sync --status

# View specific squad's report
/tech-platform-sync --squad "Meal Kit"

# Filter by tribe
/tech-platform-sync --tribe "Growth Division"
```

## What Gets Synced

For each squad, the sync captures:

| Field | Description |
|-------|-------------|
| **Squad Name** | Team name |
| **Tribe** | Parent tribe (e.g., Growth Division, Consumer Core) |
| **Mega-Alliance** | Top-level org (Consumer, Growth, Operations, etc.) |
| **Squad Lead** | PM and EM names |
| **Squad KPI** | Primary metric definition |
| **KPI Movement** | Target, actual, and delta |
| **Delivered** | What was shipped this sprint |
| **Key Learnings** | Retrospective insights |
| **Planned** | Next sprint commitments |
| **Demo** | Demo recording link (if available) |

## Output Structure

```
brain/Inbox/Tech Platform_Sprint/
├── _sync_state.json                        # Sync metadata
├── Tech Platform_Sprint_Summary_YYYY-MM-DD.md  # Combined summary
├── Cart.md                                 # Individual squad file
├── Meal_Kit.md
├── Growth_Platform.md
├── The_Wellness_Brand.md
├── Payments_Platform.md
└── ... (98+ squad files)
```

### Squad File Format

Each squad file includes YAML frontmatter for Brain indexing:

```markdown
---
type: tech-platform_sprint_report
squad: Cart
tribe: Shopping Foundation
mega_alliance: Consumer
synced_at: 2026-02-04T13:55:23
source: Tech Platform Every Other Week Squad Sprint Report
---

## Cart
**Tribe:** Shopping Foundation
**Mega-Alliance:** Consumer
**Squad Lead:** EM: Arbaaz Dossani, PM: Xavier Sinclair Vale-Buisson

### Squad KPI
Cart Service Adoption Rate

### KPI Movement
Target: 100%
Actual: 58.2%
Movement: 23.2%

### Delivered (This Sprint)
Global Cart Service Migration: Continued architectural migration...

### Planned (Next Sprint)
1. Complete Cart Service roll out to all remaining markets
2. Release Cart Read API across all markets
3. Release Post-lock change for P500 use

### Key Learnings
1. Load testing for save requests not just reading in the future
2. Support engineer process to be reviewed

**Demo:** Shopping Foundation Tribe Demo - Recording Link
```

## Boot Integration

Tech Platform Sprint Sync runs automatically during `/boot` as Step 4.7:

```
BOOT SEQUENCE
├── Step 4.6: Master Sheet Sync
├── Step 4.7: Tech Platform Sprint Sync  ← Automatic
└── Step 5: Session Services
```

To skip during boot (quick mode):
```bash
/boot --quick
```

## Configuration

In `user/config.yaml`:

```yaml
tech-platform_sprint:
  enabled: true
  spreadsheet_id: "SPREADSHEET_ID_EXAMPLE"
  sync_on_boot: true
  sync_frequency: "biweekly"
  output_dir: "brain/Inbox/Tech Platform_Sprint"
  tribes_of_interest:
    - "Growth Division"
    - "Consumer"
    - "Growth"
    - "Operations"
    - "Intelligent Platforms"
```

## Use Cases

### 1. Pre-Meeting Context

Before a cross-squad meeting, see what other teams are working on:

```bash
/tech-platform-sync --tribe "Consumer"
```

### 2. Cross-Squad Dependencies

Identify related work when planning features:
- Check what Payments team is delivering when planning checkout changes
- See Shopping Foundation progress for cart-dependent features

### 3. Leadership Prep

Quick overview of tribe-wide progress:

```bash
/tech-platform-sync --status
# Shows: 98 squads synced, tribes covered, last sync time
```

### 4. Sprint Planning Reference

See what similar squads delivered for benchmarking:

```bash
/tech-platform-sync --squad "Growth Platform"
```

### 5. Brain Enrichment

The synced data flows into Brain, providing:
- Squad context for meeting prep
- KPI references for business cases
- Learning patterns across organization

## Technical Details

### Sheet Detection

The tool automatically selects the most recent sprint sheet:

1. Fetches all sheet names from spreadsheet
2. Looks for `Sprint-N-YYYY-MM-DD` pattern
3. Sorts by date (newest first)
4. Uses most recent for sync

### Column Mapping

| Column | Index | Description |
|--------|-------|-------------|
| A | 0 | Mega-Alliance |
| B | 1 | Tribe |
| C | 2 | Squad Name |
| D | 3 | Squad Lead |
| E | 4 | Squad KPI |
| F | 5 | KPI Movement |
| G | 6 | Delivered |
| H | 7 | Key Learnings |
| I | 8 | Planned |
| J | 9 | Demo |

### Error Handling

| Error | Resolution |
|-------|------------|
| Google token expired | Run OAuth flow: `python3 google_auth.py` |
| Spreadsheet not found | Check `spreadsheet_id` in config |
| No data in sheet | Sheet may be empty or header-only |

## API Reference

```python
from integrations.tech-platform_sprint_sync import Tech PlatformSprintSync

syncer = Tech PlatformSprintSync()

# Full sync
result = syncer.sync()
# Returns: {"status": "success", "squads_synced": 98, "tribes": [...]}

# Filtered sync
result = syncer.sync(tribe_filter="Growth Division")

# Get status
status = syncer.get_status()
# Returns: {"last_sync": "2026-02-04T12:55:23", "squads_synced": 98, ...}

# Get specific squad
report = syncer.get_squad("Meal Kit")
# Returns: Markdown content of squad file
```

## Tribes Covered

As of Sprint-2-2026-01-19:

| Mega-Alliance | Tribes |
|---------------|--------|
| Consumer | Consumer Core, Consumer Foundation, Customer Engagement, Loyalty & Virality, Shopping Journey, Shopping Foundation |
| Growth | AdTech, Communications, Conversions, Insights |
| Operations | Plan & Procurement, Ingredient to Product, Menu to Content, Inventory Management, Order Enrichment, RTE Manufacturing, Logistics, Ops Enablement |
| Infrastructure | Global People Technology, Operations Data & Decisions |
| Growth Division | Growth Division (Meal Kit, WB, Growth Platform, Product Innovation) |

---

*Part of PM-OS v3.2.1*
