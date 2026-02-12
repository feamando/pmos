# Ralph Status

Check the status of Ralph features.

## Arguments

- `<feature>` - Specific feature name (optional)
- `--all` - List all features with status

**Examples:**
```
/ralph-status                     # List all features
/ralph-status user-authentication # Status of specific feature
/ralph-status --all              # Detailed list of all features
```

## Instructions

### If No Feature Specified

List all Ralph features:

```bash
python3 "$PM_OS_COMMON/tools/ralph/ralph_manager.py" list
```

**Output format:**
```
Ralph Features:

  ✓ [user-auth] User Authentication System
    Progress: 8/8 (100%) | Iteration: 12 | COMPLETED

  ○ [shopify-mvp] Meal Kit Shopify Integration
    Progress: 3/10 (30%) | Iteration: 5 | IN PROGRESS
    Current: Implement product sync endpoint

  ○ [tpt-app] WB Mobile App v1
    Progress: 0/15 (0%) | Iteration: 0 | INITIALIZING

No features? Run /ralph-init <feature> to start one.
```

### If Feature Specified

Get detailed status:

```bash
python3 "$PM_OS_COMMON/tools/ralph/ralph_manager.py" status <feature>
```

Then read additional context:

1. **Read PLAN.md** - Show acceptance criteria with status
2. **Read recent logs** - Last 2-3 iteration summaries
3. **Check for blockers** - Any noted in recent logs

**Output format:**
```
Ralph Status: <feature>

Title: <title>
Status: <IN_PROGRESS | COMPLETED | BLOCKED>
Progress: <checked>/<total> (<percentage>%)
Iteration: <N>
Path: AI_Guidance/Sessions/Ralph/<feature>/

## Acceptance Criteria

### Phase 1: Foundation
- [x] Create database schema
- [x] Set up API routes

### Phase 2: Implementation
- [x] Implement login endpoint
- [ ] Add password reset flow    <-- CURRENT
- [ ] Implement session management

### Phase 3: Verification
- [ ] Add integration tests
- [ ] Update documentation

## Recent Activity

### Iteration 5 (2026-01-07 14:30)
Implemented login endpoint with JWT generation.
Files: auth_service.py, routes.py
Commit: abc123

### Iteration 4 (2026-01-07 13:45)
Set up API routes and middleware.
Files: routes.py, middleware.py

## Next Steps

Current item: Add password reset flow
Estimated remaining: 4 iterations

<If blocked: show blocker details and suggested resolution>
```

### Show Progress Bar (Visual)

For quick visual:
```
[████████░░░░░░░░░░░░] 40% (4/10)
```

## Integration with Other Commands

- `/ralph-loop <feature>` - Resume or start iteration loop
- `/ralph-specs <feature>` - Update acceptance criteria
- `/ralph-init <feature>` - Initialize new feature

## Execute

Check Ralph status and display progress for the specified feature or all features.
