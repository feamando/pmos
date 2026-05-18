---
description: Multi-iteration feature development workflow
---

# /ralph -- Multi-Iteration Feature Development

Parse the first argument to determine which subcommand to run:

| Subcommand | Description |
|------------|-------------|
| `init <feature>` | Initialize a new Ralph feature with acceptance criteria |
| `status [feature]` | Show progress for a feature or all features |
| `iteration <feature>` | Record a completed iteration with summary |
| `list` | List all Ralph features and their progress |
| `specs` | Generate Ralph specs for a feature's next iteration |
| `loop` | Run a Ralph iteration loop (orient → work → record) |
| *(no args)* | Show available subcommands |

## Arguments
$ARGUMENTS

## No Arguments -- Show Help

If no arguments provided, display:

```
Ralph -- Multi-Iteration Feature Development

  /ralph init <feature> --title "Title" [--criteria "AC1" "AC2"]  - Initialize feature
  /ralph status [feature]                                          - Show feature status
  /ralph iteration <feature> --summary "What was done"             - Record iteration
  /ralph list                                                      - List all features
  /ralph specs <feature>                                           - Generate iteration specs
  /ralph loop <feature>                                            - Run iteration loop

Usage: /ralph <subcommand> [options]
```

---

### init

Initialize a new Ralph feature for multi-iteration development.

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$0")")"
python3 "$PLUGIN_ROOT/tools/ralph/ralph_manager.py" init "$FEATURE" --title "$TITLE" --criteria $CRITERIA
```

After initialization:
1. Report the feature path and initial acceptance criteria
2. Show the PLAN.md and PROMPT.md locations
3. Suggest: "Run `/ralph loop <feature>` to start the first iteration"

### status

Show progress for a specific feature or all features.

```bash
python3 "$PLUGIN_ROOT/tools/ralph/ralph_manager.py" status "$FEATURE"
```

Display: Feature title, status (in_progress/complete), progress (X/Y criteria, percentage), iteration count, path.

### iteration

Record a completed iteration with summary of work done.

```bash
python3 "$PLUGIN_ROOT/tools/ralph/ralph_manager.py" iteration "$FEATURE" --summary "$SUMMARY" --files $FILES --blockers $BLOCKERS
```

After recording:
1. Show iteration number and log path
2. Show updated progress
3. If all criteria complete, congratulate and suggest closing

### list

List all Ralph features with their status.

```bash
python3 "$PLUGIN_ROOT/tools/ralph/ralph_manager.py" list
```

Display as a table: Feature, Title, Status, Progress, Iteration count.

### specs

Generate iteration specs by reading PLAN.md and finding the next unchecked criterion.

1. Read the feature's `PLAN.md`
2. Find the FIRST unchecked `- [ ]` item
3. Read relevant source files for context
4. Generate a focused brief for completing that one criterion

### loop

Run a Ralph iteration loop:

1. **Orient**: Read PLAN.md, find next unchecked criterion
2. **Work**: Complete that single criterion (code, docs, tests)
3. **Record**: Mark criterion as `- [x]`, commit, record iteration
4. **Report**: Show progress and suggest next steps

## Execute

Parse arguments and run the appropriate Ralph subcommand. Use the tool paths shown above.
