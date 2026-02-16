# Ralph Init

Initialize a new Ralph feature for long-running, multi-iteration work.

## Arguments

- `<feature>` - Feature name (required, will be sanitized to kebab-case)
- `--title "..."` - Human-readable title (optional, defaults to feature name)

**Examples:**
```
/ralph-init user-authentication
/ralph-init shopify-integration --title "Meal Kit Shopify MVP"
/ralph-init tpt-app-v1 --title "BB Mobile App v1"
```

## Instructions

### Step 1: Validate Feature Name

If no feature name provided in arguments, ask user:
- What feature/project should we track?
- Suggest based on recent conversation context

Sanitize the feature name:
- Convert to lowercase
- Replace spaces with hyphens
- Remove special characters

### Step 2: Initialize Feature

Run the ralph manager to create the feature structure:

```bash
python3 "$PM_OS_COMMON/tools/ralph/ralph_manager.py" init <feature> --title "Title"
```

This creates:
```
AI_Guidance/Sessions/Ralph/<feature>/
├── PROMPT.md      # Iteration instructions (includes Brain context)
├── PLAN.md        # Acceptance criteria (placeholder)
├── specs/         # Specification files
└── logs/          # Iteration logs
```

### Step 3: Customize PROMPT.md (Optional)

If the user has specific context requirements:
1. Read the generated `PROMPT.md`
2. Update the "Context Training" section with relevant Brain paths
3. Add any feature-specific constraints

### Step 4: Report and Next Steps

Confirm initialization:
- Feature name and path
- Title
- Next step: `/ralph-specs <feature>` to create acceptance criteria

**Output format:**
```
Ralph feature initialized:
  Feature: <feature>
  Title: <title>
  Path: AI_Guidance/Sessions/Ralph/<feature>/

Next: Run /ralph-specs <feature> to define acceptance criteria
```

## What Happens Next

After initialization:
1. `/ralph-specs` - Interactively create acceptance criteria
2. `/ralph-loop` - Start background iteration loop
3. `/ralph-status` - Check progress at any time

## Notes

- Ralph is for multi-session tasks (expect >3 context windows)
- Each iteration works on ONE acceptance criterion
- Progress is tracked via checkboxes in PLAN.md
- Iterations are logged for audit trail
- Slack updates posted automatically during loop

## Execute

Initialize the Ralph feature with the provided name and optional title.
