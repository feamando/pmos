# Meeting Prep

Generate personalized meeting pre-reads for upcoming calendar events.

## Arguments
$ARGUMENTS

## Instructions

### Default: Generate Pre-Reads for Upcoming Meetings

Run the meeting prep tool to auto-generate pre-reads:

```bash
python3 AI_Guidance/Tools/meeting_prep/meeting_prep.py --hours 24
```

This will:
- Fetch calendar events for the next 24 hours
- Classify meetings (1:1, standup, review, external, interview)
- Gather context from Brain entities, daily context, and GDrive
- Load past meeting notes and series history
- Synthesize pre-reads using Gemini
- Save to `Planning/Meeting_Prep/Series/` (recurring) or `Planning/Meeting_Prep/AdHoc/` (one-time)

### Options

| Flag | Description |
|------|-------------|
| `--hours N` | Look ahead N hours (default: 24) |
| `--meeting "title"` | Generate for specific meeting only |
| `--list` | List upcoming meetings without generating |
| `--upload` | Upload to GDrive and link to Calendar event |
| `--with-jira` | Include recent Jira issues for participants |
| `--cleanup` | Archive orphaned meeting preps (cancelled meetings) |
| `--dry-run` | Preview what would be generated |

### Examples

```bash
# Next 8 hours only
python3 AI_Guidance/Tools/meeting_prep/meeting_prep.py --hours 8

# Specific meeting
python3 AI_Guidance/Tools/meeting_prep/meeting_prep.py --meeting "1:1 Beatrice"

# List without generating
python3 AI_Guidance/Tools/meeting_prep/meeting_prep.py --list

# Full workflow: generate, upload, and link
python3 AI_Guidance/Tools/meeting_prep/meeting_prep.py --upload

# Cleanup cancelled meetings
python3 AI_Guidance/Tools/meeting_prep/meeting_prep.py --cleanup
```

## Output Structure

- **Series files:** `Planning/Meeting_Prep/Series/Series-[slug].md` - Preserves history for recurring meetings
- **AdHoc files:** `Planning/Meeting_Prep/AdHoc/Meeting-[date]-[slug].md` - One-time meetings
- **Archive:** `Planning/Meeting_Prep/Archive/` - Past/cancelled meetings

## Context Sources

1. **Brain entities** - Participant roles, current topics
2. **Daily context** - Action items, key decisions
3. **GDrive** - Past meeting notes (auto-searched)
4. **Series history** - Previous entries for recurring meetings
5. **Jira** - Recent participant tickets (with --with-jira)
