# Session Logout

End the current session by saving context, syncing reasoning state, and pushing changes to git.

## Instructions

### Step 1: Generate Session Summary

Based on the conversation history, create a concise session summary covering:
- Key tasks completed
- Decisions made
- Files created or modified
- Blockers encountered (if any)
- **FPF reasoning activity** (if any cycles were active)

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

### Step 5: Confirm Completion

Report:
- Context file updated (filename)
- FPF sync status (if applicable)
- Commit hash
- Push status

## Execute

Generate the session summary, sync reasoning state, update context, and push changes now.
