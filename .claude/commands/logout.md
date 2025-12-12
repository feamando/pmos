# Session Logout

End the current session by saving context and pushing changes to git.

## Instructions

### Step 1: Generate Session Summary

Based on the conversation history, create a concise session summary covering:
- Key tasks completed
- Decisions made
- Files created or modified
- Blockers encountered (if any)

### Step 2: Update Context File

1. Find the latest context file for today: `AI_Guidance/Core_Context/YYYY-MM-DD-NN-context.md`
2. Append a "Session End" section with timestamp and summary:

```markdown
## Session End (HH:MM)

[Your summary here]
```

### Step 3: Git Sync

Execute in order:
1. `git pull origin main` - sync remote changes
2. `git add .` - stage all changes
3. `git commit -m "Session end: Context update and work save (YYYY-MM-DD)"` - commit
4. `git push origin main` - push to remote

### Step 4: Confirm Completion

Report:
- Context file updated (filename)
- Commit hash
- Push status

## Execute

Generate the session summary, update context, and push changes now.
