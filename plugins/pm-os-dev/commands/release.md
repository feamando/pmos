---
description: PM-OS release pipeline — version, changelog, publish
---

# /release -- PM-OS Release Pipeline

Parse the first argument to determine which subcommand to run:

| Subcommand | Description |
|------------|-------------|
| `full --version X.Y.Z` | Full release: common + PyPI + app |
| `common --version X.Y.Z` | Release PM-OS common only |
| `app --version X.Y.Z` | Release app only |
| `status` | Show current release pipeline status |
| `resume` | Resume a paused release (after PR merge) |
| `dry-run --version X.Y.Z` | Preview release without executing |
| *(no args)* | Show available subcommands |

## Arguments
$ARGUMENTS

## No Arguments -- Show Help

If no arguments provided, display:

```
Release -- PM-OS Release Pipeline

  /release full --version 5.0.0                    - Full release pipeline
  /release full --version 5.0.0 --app-version 0.12 - With separate app version
  /release common --version 5.0.0                  - PM-OS common only
  /release app --version 0.12.0                    - App only
  /release status                                  - Show pipeline status
  /release resume                                  - Resume after PR merge
  /release dry-run --version 5.0.0                 - Preview without executing

Usage: /release <subcommand> [options]
```

---

### full / common / app

Run the release pipeline with the specified scope.

**Pipeline phases:**
1. **Preflight** — Verify gh CLI, node/npm, VERSION file, credentials
2. **Version Bump** — Update VERSION and plugin.json files
3. **Sanitization** — Content scan for sensitive data
4. **Create PR** — Publish to distribution repo via PR
5. **Wait Merge** — Pause for PR review and merge
6. **Post-Merge** — Tag for PyPI, build app (parallel)
7. **Verify** — Check GitHub Actions, pip install, manifest
8. **Slack** — Post release announcement
9. **Complete** — Final summary

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$0")")"
python3 "$PLUGIN_ROOT/tools/release/release_pipeline.py" "$SCOPE" --version "$VERSION" $APP_VERSION_FLAG
```

For dry-run:
```bash
python3 "$PLUGIN_ROOT/tools/release/release_pipeline.py" dry-run --version "$VERSION"
```

### status

```bash
python3 "$PLUGIN_ROOT/tools/release/release_pipeline.py" status
```

Display: Release ID, version, scope, current phase, completed phases, PR URL, tag, errors.

### resume

```bash
python3 "$PLUGIN_ROOT/tools/release/release_pipeline.py" resume
```

Resumes from the last checkpoint. Typically used after the PR merge phase.

## Execute

Parse arguments and run the appropriate release subcommand.
