# Confucius Status

Check the current Confucius note-taking session, review captured notes, or manage sessions.

## Arguments
$ARGUMENTS

## Instructions

The user wants to check on or manage the Confucius note-taker. Parse arguments:

- **No arguments:** Show current session status
- **`--list [N]`:** List recent sessions
- **`--export`:** Export current notes for FPF injection
- **`--end`:** End current session and save to file
- **`--start "Topic"`:** Start a new session

### Show Status (Default)

```bash
python3 "$PM_OS_COMMON/tools/session/confucius_agent.py" --status
```

This displays:
- Current session ID and topic
- Session status (active/closed)
- Note counts by type (decisions, assumptions, observations, blockers, actions)
- Linked FPF cycles and documents

### List Recent Sessions

```bash
python3 "$PM_OS_COMMON/tools/session/confucius_agent.py" --list 5
```

Shows the 5 most recent Confucius sessions with their topics and timestamps.

### Export for FPF

```bash
python3 "$PM_OS_COMMON/tools/session/confucius_agent.py" --export
```

Exports the current session notes in JSON format suitable for injection into FPF context during document generation.

### View as Markdown

```bash
python3 "$PM_OS_COMMON/tools/session/confucius_agent.py" --markdown
```

Displays the current session in human-readable markdown format.

### End Session

```bash
python3 "$PM_OS_COMMON/tools/session/confucius_agent.py" --end
```

Ends the current session and saves it to `brain/Confucius/{session_id}.md`.

### Start New Session

```bash
python3 "$PM_OS_COMMON/tools/session/confucius_agent.py" --start "Topic"
```

Starts a new note-taking session with the given topic.

## Manual Note Capture

You can manually capture notes:

```bash
# Capture a decision
python3 "$PM_OS_COMMON/tools/session/confucius_agent.py" --capture decision \
  --title "Architecture choice" \
  --choice "Microservices" \
  --rationale "Better scalability for expected growth"

# Capture an assumption
python3 "$PM_OS_COMMON/tools/session/confucius_agent.py" --capture assumption \
  --text "Users will prefer mobile over web" \
  --source "User research Q4"

# Capture an observation
python3 "$PM_OS_COMMON/tools/session/confucius_agent.py" --capture observation \
  --text "Competitor launched similar feature last week" \
  --source "Market analysis"

# Capture a blocker
python3 "$PM_OS_COMMON/tools/session/confucius_agent.py" --capture blocker \
  --text "Waiting on legal approval" \
  --owner "Legal team"

# Capture an action
python3 "$PM_OS_COMMON/tools/session/confucius_agent.py" --capture action \
  --text "Schedule architecture review" \
  --owner "Daniel" \
  --due "2026-01-15"
```

## Auto-Detection

The agent can auto-detect notes from conversation text:

```bash
python3 "$PM_OS_COMMON/tools/session/confucius_agent.py" --detect "We decided to go with React Native because it's faster to develop"
```

## Note Types

| Type | ID Prefix | Purpose |
|------|-----------|---------|
| Decision | D | Choices made during the session |
| Assumption | A | Implicit assumptions to validate |
| Observation | O | Facts and context worth preserving |
| Blocker | B | Issues blocking progress |
| Action | T | Tasks and follow-ups |

## Integration

Confucius notes are automatically loaded by document generation commands:
- `/prd` - PRD Generator
- `/4cq` - 4CQ Project Definition
- `/adr` - Architecture Decision Record
- `/rfc` - RFC Generator
- `/prfaq` - PRFAQ Generator

The notes provide context for FPF reasoning and are referenced in generated Decision Rationale Records (DRRs).
