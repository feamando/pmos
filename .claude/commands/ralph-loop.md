# Ralph Loop

Start the background iteration loop for a Ralph feature.

## Arguments

- `<feature>` - Feature name OR Beads epic ID (e.g., `bd-a3f8`) (required)
- `--max-iterations N` - Maximum iterations (default: 20)
- `--dry-run` - Show what would happen without executing

**Examples:**
```
/ralph-loop user-authentication
/ralph-loop bd-cd44                    # NEW: Use Beads epic directly
/ralph-loop shopify-integration --max-iterations 30
/ralph-loop tpt-app --dry-run
```

## Instructions

### Step 0: Beads Integration Check (NEW)

If the argument starts with `bd-`, it's a Beads epic ID. Generate PLAN.md from Beads:

```bash
python3 "$PM_OS_COMMON/tools/beads/beads_ralph_integration.py" ensure-plan <epic_id>
```

This will:
- Create Ralph feature directory if needed
- Generate PLAN.md from Beads epic's child tasks
- Link Beads tasks to acceptance criteria
- Return the feature name to use for remaining steps

If the argument doesn't start with `bd-`, proceed to Step 1 as normal.

### Step 1: Pre-Flight Checks

Verify the feature is ready:

```bash
python3 "$PM_OS_COMMON/tools/ralph/ralph_manager.py" status <feature>
```

**Check:**
1. Feature exists
2. PLAN.md has acceptance criteria (not just placeholder)
3. At least one unchecked `- [ ]` item exists
4. Feature not already marked COMPLETED

If checks fail, report what's missing and suggest fix.

### Step 2: Read Iteration Context

Read the feature's PROMPT.md to get the iteration instructions.
Read PLAN.md to identify the current (first unchecked) item.

### Step 3: Execute Iteration

For each iteration:

1. **Start iteration**
   - Note the start time
   - Identify the target criterion

2. **Work on ONE criterion**
   - Follow PROMPT.md instructions
   - Complete the acceptance criterion
   - Test/verify the work

3. **Commit progress**
   - Stage changes: `git add -A`
   - Commit with descriptive message
   - Note the commit hash

4. **Update PLAN.md**
   - Mark criterion as `- [x]`
   - Update progress line at bottom

4b. **Sync to Beads** (if linked to Beads epic)
   ```bash
   python3 "$PM_OS_COMMON/tools/beads/beads_ralph_integration.py" sync-completion <feature>
   ```
   This closes the corresponding Beads task when the acceptance criterion is checked.

5. **Log iteration**
   ```bash
   python3 "$PM_OS_COMMON/tools/ralph/ralph_manager.py" iteration <feature> \
     --summary "What was completed" \
     --files "file1.py,file2.md" \
     --commit "abc123" \
     --message "Commit message"
   ```

6. **Post to Slack**
   ```bash
   python3 "$PM_OS_COMMON/tools/ralph/ralph_manager.py" post-slack <feature>
   ```

7. **Check completion**
   ```bash
   python3 "$PM_OS_COMMON/tools/ralph/ralph_manager.py" check-complete <feature>
   ```
   - If COMPLETE: Stop loop, report success
   - If IN_PROGRESS: Continue to next iteration

### Step 4: Loop Control

**Stop conditions:**
- All criteria complete (COMPLETED marker found)
- Max iterations reached
- Blocker encountered (requires user input)
- Error during iteration

**On blocker:**
- Log the blocker in iteration report
- Post to Slack with blocker details
- Pause and notify user
- Wait for `/ralph-loop <feature>` to resume

### Step 5: Final Report

When loop completes or stops:

```
Ralph Loop Complete: <feature>

Status: <COMPLETED | PAUSED | MAX_ITERATIONS>
Iterations: <N>
Progress: <checked>/<total> (<percentage>%)

<Summary of work completed>

<If paused: reason and how to resume>
```

## Background Execution

The loop runs as a background Task agent. To check status:
- `/ralph-status <feature>` - See current progress
- Check Slack for iteration updates
- View `logs/iteration-NNN.md` files

## Resuming a Paused Loop

If the loop paused due to a blocker:
1. Resolve the blocker
2. Run `/ralph-loop <feature>` to resume
3. Loop continues from where it left off

## Manual Iteration (Alternative)

If you prefer manual control:
1. Read PLAN.md, find next item
2. Complete the work
3. Update PLAN.md
4. Run: `python3 "$PM_OS_COMMON/tools/ralph/ralph_manager.py" iteration <feature> --summary "..."`
5. Repeat

## Execute

Verify the feature is ready, then start the iteration loop. Work through acceptance criteria one at a time until complete or blocked.
