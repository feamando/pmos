# Statsig Sync

Fetch experiments and feature gates from Statsig and create/update Brain entity files.

## Instructions

### Default: Sync Active Experiments

```bash
python3 "$PM_OS_COMMON/tools/integrations/statsig_brain_sync.py" --active-only
```

This will:
- Fetch experiments from Statsig Console API
- Extract Jira keys from experiment names/descriptions
- Create/update files in `Brain/Experiments/`
- Auto-link experiments to related Brain entities

### Options

| Flag | Description |
|------|-------------|
| `--active-only` | Only sync experiments with active status |
| `--deep` | Sync all experiments including finished ones |
| `--dry-run` | Fetch data but don't write files |
| `--summary-file PATH` | Write markdown summary to specified file |

### Examples

```bash
# Active experiments only
python3 "$PM_OS_COMMON/tools/integrations/statsig_brain_sync.py" --active-only

# All experiments (including finished)
python3 "$PM_OS_COMMON/tools/integrations/statsig_brain_sync.py" --deep

# Preview without writing
python3 "$PM_OS_COMMON/tools/integrations/statsig_brain_sync.py" --active-only --dry-run

# With summary output
python3 "$PM_OS_COMMON/tools/integrations/statsig_brain_sync.py" --active-only --summary-file experiments_summary.md
```

## Output Structure

Creates files in `Brain/Experiments/`:
```
Brain/Experiments/
├── EXP-gc-otp-checkout.md
├── EXP-tpt-new-pricing.md
└── EXP-ff-subscribe-save.md
```

Each file contains:
- YAML frontmatter (id, type, status, creator, dates)
- Description
- Linked Jira tickets (auto-extracted)
- Related Brain entities

## Auto-Linking

The tool automatically:
1. Extracts Jira keys from experiment name/description (e.g., `MK-123`)
2. Links experiments to squad Brain files based on project prefix
3. Enables `brain_loader.py` to find experiments in hot topics

## Prerequisites

- Statsig Console API key in `.env` (`STATSIG_CONSOLE_API_KEY`)
