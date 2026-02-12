# Session Search

Search across all sessions by keyword, tag, or content.

## Arguments

- `query`: Search term (required)

**Examples:**
```
/session-search "distribution"    # Search for distribution-related sessions
/session-search "OTP"             # Find sessions mentioning OTP
/session-search "decision"        # Find sessions with decisions
```

## Instructions

### Step 1: Execute Search

Run the session manager search:

```bash
python3 "$PM_OS_COMMON/tools/session/session_manager.py" --search "QUERY"
```

### Step 2: Present Results

Format results for user:

```markdown
## Session Search: "[query]"

Found [N] sessions:

### 1. [Session ID] - [Title]
- **Date:** YYYY-MM-DD
- **Tags:** tag1, tag2
- **Match:** [Where the match was found - title/tags/body]

### 2. [Session ID] - [Title]
...

---
Use `/session-load [ID]` to view full session details.
```

### Step 3: Offer Follow-up Actions

- Load a specific session for details
- Narrow search with additional terms
- List all sessions if no matches found

## Search Tips

The search checks:
1. **Tags** (highest priority) - Exact tag matches
2. **Title** (medium priority) - Title contains query
3. **Body** (lower priority) - Any content match

Results are sorted by relevance then date.

## Common Searches

| Search | Purpose |
|--------|---------|
| Project name | Find sessions about specific project |
| Person name | Find sessions involving someone |
| "decision" | Find sessions with recorded decisions |
| Date (YYYY-MM) | Find sessions from specific month |
| Tag name | Find sessions with specific tag |

## Execute

Search sessions for the provided query and present formatted results.
