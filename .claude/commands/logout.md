# Session Logout

End the current session by archiving session context, syncing reasoning state, and pushing changes to git.

## Instructions

### Step 1: Save and Archive Session Context

Check for active session and archive it:

```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --status
```

**If active session exists:**

1. Generate a session summary from the conversation:
   - Key tasks completed
   - Decisions made
   - Files created or modified
   - Blockers encountered (if any)
   - FPF reasoning activity (if any)

2. Add final work log entry:
```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --log "Session end: [brief summary of final work]"
```

3. Archive the session:
```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --archive
```

**If no active session:**

Create a quick session record before archiving:
```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --create "Session Summary" --tags "quick-session"
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --log "[Summary of work done]"
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --archive
```

### Step 1.5: Close Confucius Note-Taking Session

End the Confucius note-taking session and export notes to markdown:

```bash
python3 "$PM_OS_COMMON/tools/session/confucius_agent.py" --end
```

This will:
- Export all notes from the session to a timestamped markdown file
- Save to `$PM_OS_USER/session/notes/YYYY-MM-DD-HH-MM-notes.md`
- Clear the active session state

**Skip if:** No Confucius session is active (command will handle gracefully).

### Step 2: Sync FPF Reasoning State

If any FPF reasoning was performed during this session:

```bash
python3 "$PM_OS_COMMON/tools/quint/quint_brain_sync.py" --to-brain
```

This ensures:
- Active cycles are saved to `Brain/Reasoning/Active/`
- DRRs are synced to `Brain/Reasoning/Decisions/`
- Evidence and hypotheses are persisted

**Skip if:** No FPF reasoning was performed this session.

### Step 3: Update Context File

1. Find the latest context file for today: `$PM_OS_USER/context/YYYY-MM-DD-NN-context.md`
2. Append a "Session End" section with timestamp and summary:

```markdown
## Session End (HH:MM)

[Your summary here]

### FPF State
- Active cycles: [N]
- DRRs created: [M]
- Evidence items: [K]
```

### Step 4: Git Sync

Execute in order:
1. `git pull origin main` - sync remote changes
2. `git add .` - stage all changes
3. `git commit -m "Session end: Context update and work save (YYYY-MM-DD)"` - commit
4. `git push origin main` - push to remote

### Step 4.5: Final Roadmap Capture

Capture any final PM-OS feature requests or bugs to the roadmap inbox before ending the session:

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/roadmap/roadmap_inbox_manager.py" --capture
```

This ensures any new requests from the session are captured with temp IDs.

**Skip if:** Developer tools are not available.

### Step 4.6: Master Sheet Sync

Sync priorities from the Google Sheets Master Sheet to capture any status changes made during the session:

```bash
python3 "$PM_OS_COMMON/tools/master_sheet/master_sheet_sync.py"
```

This will:
- Read the latest data from the topics and recurring tabs
- Update feature context files with any status changes
- Surface overdue items for end-of-day review

### Step 5: Post Session Summary to Slack

Post session completion summary to Slack channel `#pmos-slack-channel` (CXXXXXXXXXX):

```bash
python3 "$PM_OS_COMMON/tools/slack/slack_context_poster.py" $PM_OS_USER/context/YYYY-MM-DD-context.md --type logout
```

Replace `YYYY-MM-DD` with the actual context file updated in Step 3.

**Posted summary includes:**
- Critical Alerts
- Open Action Items (with owners)
- Active Blockers
- Upcoming Key Dates
- Session Summary (work completed this session)

**Skip if:** Slack token not configured or posting fails (non-blocking).

### Step 5.5: Regenerate Brain Index

Regenerate the compressed entity index so next boot starts with a fresh snapshot:

```bash
python3 "$PM_OS_COMMON/tools/brain/brain_index_generator.py"
```

**Skip if:** Generator fails (non-blocking).

### Step 6: Confirm Completion

Report:
- Context file updated (filename)
- FPF sync status (if applicable)
- Commit hash
- Push status
- Slack post status (posted/skipped)

## Execute

Generate the session summary, sync reasoning state, update context, and push changes now.
