# Session Logout

End the current session by archiving session context, syncing reasoning state, and pushing changes to git.

## Instructions

### Step 1: Save and Archive Session Context

Check for active session and archive it:

```bash
python3 AI_Guidance/Tools/session_manager.py --status
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
python3 AI_Guidance/Tools/session_manager.py --log "Session end: [brief summary of final work]"
```

3. Archive the session:
```bash
python3 AI_Guidance/Tools/session_manager.py --archive
```

**If no active session:**

Create a quick session record before archiving:
```bash
python3 AI_Guidance/Tools/session_manager.py --create "Session Summary" --tags "quick-session"
python3 AI_Guidance/Tools/session_manager.py --log "[Summary of work done]"
python3 AI_Guidance/Tools/session_manager.py --archive
```

### Step 2: Sync FPF Reasoning State

If any FPF reasoning was performed during this session:

```bash
python3 AI_Guidance/Tools/quint_brain_sync.py --to-brain
```

This ensures:
- Active cycles are saved to `Brain/Reasoning/Active/`
- DRRs are synced to `Brain/Reasoning/Decisions/`
- Evidence and hypotheses are persisted

**Skip if:** No FPF reasoning was performed this session.

### Step 3: Update Context File

1. Find the latest context file for today: `AI_Guidance/Core_Context/YYYY-MM-DD-NN-context.md`
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

### Step 5: Post Session Summary to Slack

Post session completion summary to Slack channel `#ngo-slack-private` (C0A6ZAS1MSQ):

```bash
python3 AI_Guidance/Tools/slack_context_poster.py AI_Guidance/Core_Context/YYYY-MM-DD-context.md --type logout
```

Replace `YYYY-MM-DD` with the actual context file updated in Step 3.

**Posted summary includes:**
- Critical Alerts
- Open Action Items (with owners)
- Active Blockers
- Upcoming Key Dates
- Session Summary (work completed this session)

**Skip if:** Slack token not configured or posting fails (non-blocking).

### Step 6: Confirm Completion

Report:
- Context file updated (filename)
- FPF sync status (if applicable)
- Commit hash
- Push status
- Slack post status (posted/skipped)

## Execute

Generate the session summary, sync reasoning state, update context, and push changes now.
