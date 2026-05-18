---
description: Publish PM-OS to distribution repositories
---

# /push -- Publish PM-OS to Distribution Repositories

Parse the first argument to determine which subcommand to run:

| Subcommand | Description |
|------------|-------------|
| `common` | Push PM-OS common to distribution repo |
| `brain` | Push brain content to distribution repo |
| `user` | Push user content to distribution repo |
| `pypi [--bump patch\|minor\|major]` | Publish to PyPI |
| `all` | Push all enabled targets |
| `status` | Show push status for all targets |
| `--dry-run` | Preview without pushing (combine with any target) |
| *(no args)* | Show available subcommands |

## Arguments
$ARGUMENTS

## No Arguments -- Show Help

If no arguments provided, display:

```
Push -- Publish PM-OS to Distribution Repositories

  /push common                         - Push common to distribution repo
  /push brain                          - Push brain content
  /push user                           - Push user content
  /push pypi --bump patch              - Publish to PyPI with version bump
  /push all                            - Push all enabled targets
  /push status                         - Show push status
  /push common --dry-run               - Preview common push
  /push all --skip-sanitization        - Skip content scan
  /push common --force                 - Continue on warnings

Usage: /push <target> [options]
```

---

### Target Push (common / brain / user / all)

Clone-then-compare strategy with v3 enhancements:

1. **Pre-push validation** — Version staleness, TODO scan
2. **Content sanitization** — Regex-based sensitive data scan
3. **Clone** — Shallow clone of target repo
4. **Clear & Copy** — Clear clone working tree, copy source files
5. **Detect changes** — Git diff for adds/modifies/deletes
6. **Release notes** — Auto-generated semantic notes
7. **Push** — Direct push or PR creation

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$0")")"
python3 "$PLUGIN_ROOT/tools/push/push_publisher.py" --target "$TARGET" $DRY_RUN $SKIP_SAN $FORCE
```

### PyPI

Build and publish to PyPI:

```bash
python3 "$PLUGIN_ROOT/tools/push/pypi_push.py" --bump "$BUMP_TYPE" $DRY_RUN
```

### status

```bash
python3 "$PLUGIN_ROOT/tools/push/push_publisher.py" --status
```

Display: Each target's enabled state, repo, last push timestamp, last commit, files changed.

## Publishing Workflow

```
pm-os/          (internal dev, experiment)
  ↓
v5/plugins/     (v5.x working folder — align with HF spec)
  ↓
claude-plugins-marketplace/external_plugins/   (HF marketplace repo)
  ↓
PR → CI → EP review → merge to master
```

**Branch naming:** `PEP-{ticket}/pm-os-{plugin-name}` (e.g. `PEP-277/pm-os-base`)
**PR naming:** `[PEP-{ticket}] Publish pm-os-{plugin} to marketplace`

**What ships per plugin** (copy to `external_plugins/`):
- `.claude-plugin/plugin.json` — manifest
- `commands/*.md` — slash commands (with frontmatter)
- `skills/*/SKILL.md` — skills (subdirectory pattern)
- `tools/` — Python runtime (self-contained)
- `.mcp.json` — MCP server config

**What stays internal** (do NOT copy):
- `tests/` — dev-only test suites
- `pipelines/` — PM-OS boot/logout pipeline extensions
- `preflight-checks.yaml` — PM-OS preflight system

**Marketplace repo:** Configured in `config.yaml: dev.marketplace_repo` (no default)
**CI checks:** `claude plugin validate`, CODEOWNERS integrity, author field validation
**Required reviewer:** Configured in `config.yaml: dev.required_reviewer` (no default)

## Marketplace Tracking Tickets

Configure tracking ticket references in `config.yaml: dev.tracking_tickets` for your organization's marketplace publishing workflow.

## Execute

Parse arguments and run the appropriate push subcommand.
