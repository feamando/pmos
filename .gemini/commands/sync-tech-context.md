# Sync Tech Context

Sync technical standards from spec-machine to update the Technical Brain with latest coding patterns and conventions.

## Usage

```
/sync-tech-context
```

## Instructions

### Step 1: Run Sync

```bash
python3 "$PM_OS_COMMON/tools/integrations/tech_context_sync.py" --sync-spec-machine
```

### Step 2: Review Synced Categories

The tool will:
1. Fetch standards from `acme-corp/spec-machine/profiles/engagement-dau/standards/`
2. Group by category (code-quality, data-access, feature-flags, etc.)
3. Write summaries to `Brain/Technical/patterns/`

### Step 3: Report Results

Report categories synced:
- `code-quality` - TypeScript patterns, file organization
- `data-access` - GraphQL/REST patterns
- `feature-flags` - Statsig patterns
- `navigation` - Deep linking, navigation patterns
- `observability` - Analytics, error handling

### Step 4: Update Summary Files

After sync, update the main summary files if needed:

1. Read `Brain/Technical/tech-stack.md` and verify alignment
2. Read `Brain/Technical/conventions.md` and update if patterns changed

## Output

```
Spec-Machine Sync Complete
==========================
Categories Synced: 8
- code-quality: 4 files
- data-access: 5 files
- feature-flags: 1 file
- navigation: 3 files
- observability: 2 files

Files Updated:
- Brain/Technical/patterns/code-quality.md
- Brain/Technical/patterns/data-access.md
- Brain/Technical/patterns/feature-flags.md
- Brain/Technical/patterns/navigation.md
- Brain/Technical/patterns/observability.md
```

## When to Run

- After major spec-machine updates
- Before writing technical PRDs or ADRs
- When conventions seem outdated
- Periodically (monthly recommended)
