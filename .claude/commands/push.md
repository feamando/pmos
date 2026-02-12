# PM-OS Push Command

Publish PM-OS components to their respective repositories and registries.

## Overview

The `/push` command publishes PM-OS components to their configured destinations:
- **common** → `feamando/pmos` (via PR)
- **brain** → `feamando/brain` (direct push)
- **user** → `feamando/user` (direct push)
- **pypi** → PyPI package registry (`pip install pm-os`)

Uses **clone-then-compare** strategy for git targets, **build-and-upload** for PyPI.

## Arguments

- `all` - Push all enabled targets (default, excludes pypi)
- `common` - Push only common/framework
- `brain` - Push only brain
- `user` - Push only user data
- `pypi` - Publish to PyPI only
- `--dry-run` - Preview without pushing
- `--status` - Show push status only
- `--skip-docs` - Skip documentation audit and Confluence sync (common target)
- `--docs-only` - Only run documentation, no git push (common target)
- `--bump <patch|minor|major>` - Bump version before PyPI publish

**Examples:**
```
/push                 # Push all enabled git targets
/push common          # Push common only (with docs)
/push user            # Push user only
/push pypi            # Publish to PyPI
/push pypi --bump patch   # Bump patch version and publish
/push pypi --bump minor   # Bump minor version and publish
/push pypi --dry-run      # Build only, don't upload
/push --dry-run       # Preview all targets
/push --status        # Show last push info
```

## Instructions

### Execute Git Push

Run the push v2 command for git targets:

```bash
python3 "$PM_OS_COMMON/tools/push/push_v2.py" [OPTIONS]
```

**Options:**
- `--target common` - Push common (PR to feamando/pmos)
- `--target user` - Push user (direct to feamando/user)
- `--target brain` - Push brain (direct to feamando/brain)
- `--dry-run` - Preview without pushing
- `--status` - Show status only
- `--output json` - JSON output format
- `--skip-docs` - Skip documentation phase (common target)
- `--docs-only` - Only run documentation, no git push

### Execute PyPI Push

Run the PyPI publisher for package releases:

```bash
python3 "$PM_OS_COMMON/tools/push/pypi_push.py" [OPTIONS]
```

**Options:**
- `--bump patch` - Bump patch version (3.1.1 → 3.1.2)
- `--bump minor` - Bump minor version (3.1.1 → 3.2.0)
- `--bump major` - Bump major version (3.1.1 → 4.0.0)
- `--dry-run` - Build only, don't upload
- `--status` - Show current version info
- `--verbose` - Show detailed output

**Requirements:**
- `PYPI_TOKEN` in environment or `user/.env`
- `build` and `twine` packages installed

The script automatically:
1. Detects pm-os root via `.pm-os-root` marker
2. Clones target repository to temp directory
3. Copies files (respecting excludes)
4. Detects changes via `git status`
5. Generates semantic release notes
6. Commits and pushes (or creates PR)
7. Posts Slack notification

### Status Check

```bash
python3 "$PM_OS_COMMON/tools/push/push_v2.py" --status
```

Shows:
- Enabled/disabled targets
- Last push timestamp
- Last commit hash
- Files changed

## Configuration

User config in `user/.config/push_config.yaml`:

```yaml
common:
  enabled: true
  repo: "feamando/pmos"
  branch: "main"
  push_method: "pr"        # Creates PR
  slack_channel: "CXXXXXXXXXX"
  slack_enabled: true

brain:
  enabled: false           # Disabled - manual push
  repo: "feamando/brain"
  push_method: "direct"

user:
  enabled: true
  repo: "feamando/user"
  push_method: "direct"    # Pushes to main
  exclude_paths:
    - "user/brain"
    - "user/.config"

pypi:
  enabled: true
  package_path: "common/package"
  package_name: "pm-os"
  version_file: "common/package/VERSION"
  slack_channel: "CXXXXXXXXXX"
  slack_enabled: true
  auto_bump: null          # "patch", "minor", "major", or null
```

## How It Works

### Clone-Then-Compare Strategy

Unlike v1 (which required pm-os to be a git repo), v2:

1. **Clones** target repo to temp directory
2. **Copies** source files to clone
3. **Detects** changes via `git status --porcelain`
4. **Generates** release notes from changes + Ralph completions
5. **Commits** with semantic message
6. **Pushes** (direct) or **Creates PR** (pr method)

### Release Notes

Automatically generated with:
- File change counts by category (docs, tools, tests, etc.)
- Recent Ralph completions extracted from PLAN.md files
- Semantic categorization (features, fixes, improvements)

### Documentation Phase (common target)

When pushing the `common` target, a documentation phase runs automatically:

1. **Documentation Audit** - Scans commands and tools for documentation coverage
   - Reports commands documented vs total
   - Reports tools documented vs total
   - Lists missing documentation items

2. **Confluence Sync** - Uploads documentation to PMOS Confluence space
   - Converts markdown to Confluence format
   - Maintains page hierarchy
   - Logs sync results

3. **Status Update** - Updates `documentation/_meta/documentation-status.json`
   - Coverage percentages
   - Last audit timestamp
   - Missing items list

Use `--skip-docs` to disable this phase, or `--docs-only` to run only documentation.

### Slack Notifications

Posted to configured channel with:
- Target and repo info
- File change counts (+added ~modified -deleted)
- PR URL or commit hash
- Change summary

## Execute

Run the push command with the specified targets. Report progress and final status.
