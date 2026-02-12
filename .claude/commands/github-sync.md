# GitHub Sync

Fetch GitHub activity (PRs, commits) for Growth Division squads and enrich Brain context.

## Instructions

### Default: Sync All Squads

```bash
python3 "$PM_OS_COMMON/tools/integrations/github_brain_sync.py"
```

This will:
- Fetch open PRs and recent commits for each squad (via `squad_registry.yaml`)
- Write raw data to `Brain/Inbox/GITHUB_YYYY-MM-DD.md`
- Create/update `Brain/GitHub/PR_Activity.md` and `Brain/GitHub/Recent_Commits.md`
- Update `Brain/Entities/Squad_*.md` with GitHub status section

### Options

| Flag | Description |
|------|-------------|
| `--squad "Name"` | Sync specific squad only |
| `--summarize` | Include Gemini-generated summary |
| `--analyze-files` | Include file change analysis for PRs (slower) |
| `--update-projects` | Fetch READMEs and update Project technical context |
| `--no-entities` | Skip updating squad entity files |
| `--output PATH` | Custom output path for inbox file |

### Examples

```bash
# All squads with summary
python3 "$PM_OS_COMMON/tools/integrations/github_brain_sync.py" --summarize

# Specific squad
python3 "$PM_OS_COMMON/tools/integrations/github_brain_sync.py" --squad "Meal Kit"

# Deep analysis with file changes
python3 "$PM_OS_COMMON/tools/integrations/github_brain_sync.py" --analyze-files

# Update project Technical Context from READMEs
python3 "$PM_OS_COMMON/tools/integrations/github_brain_sync.py" --update-projects
```

## Output Structure

- **Inbox:** `Brain/Inbox/GITHUB_YYYY-MM-DD.md` - Raw fetch data
- **PR Activity:** `Brain/GitHub/PR_Activity.md` - Consolidated PR list
- **Commits:** `Brain/GitHub/Recent_Commits.md` - Recent commit log
- **Entities:** `Brain/Entities/Squad_*.md` - GitHub Status section

## Prerequisites

- GitHub CLI (`gh`) installed and authenticated
- `squad_registry.yaml` with squad definitions including `github_repos`
