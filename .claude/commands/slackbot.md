# Slack Bot Mention Capture

Capture and manage @pmos-slack-bot mentions from Slack channels.

## Arguments

- `(default)` - Poll for new mentions and capture them
- `status` - Show pending/completed tasks and statistics
- `check` - Check for completion reactions on pending tasks
- `dry-run` - Poll without saving or sending acknowledgments
- `lookback <hours>` - Set lookback period (default: 24)
- `llm` - Enable LLM processing to formalize mentions into structured tasks
- `reprocess <id>` - Reprocess an existing mention with LLM formalization

## Examples

```
/slackbot              # Capture new mentions
/slackbot status       # Show current status
/slackbot check        # Check for completions
/slackbot dry-run      # Preview without saving
/slackbot lookback 48  # Look back 48 hours
/slackbot llm          # Capture with LLM formalization
/slackbot reprocess mention_C123_456  # Reprocess specific mention
```

## Instructions

Run the Slack mention handler based on the argument provided.

### Default (no argument or "capture")

```bash
python3 "$PM_OS_COMMON/tools/slack/slack_mention_handler.py"
```

After running, report:
- Number of new mentions captured
- Classifications (nikita_task, team_task, pmos_feature, pmos_bug, general)
- Any acknowledgments sent

### status

```bash
python3 "$PM_OS_COMMON/tools/slack/slack_mention_handler.py" --status
```

Display the output to the user.

### check

```bash
python3 "$PM_OS_COMMON/tools/slack/slack_mention_handler.py" --check-complete
```

Report how many tasks were marked complete.

### dry-run

```bash
python3 "$PM_OS_COMMON/tools/slack/slack_mention_handler.py" --dry-run --no-ack
```

Show what would be captured without saving state or sending replies.

### lookback <hours>

```bash
python3 "$PM_OS_COMMON/tools/slack/slack_mention_handler.py" --lookback <hours>
```

Replace `<hours>` with the number provided by the user.

### llm

```bash
python3 "$PM_OS_COMMON/tools/slack/slack_mention_handler.py" --llm
```

Capture mentions with LLM formalization. This processes each mention through Claude to generate:
- Clear actionable title
- Full description with context
- Acceptance criteria
- Dependencies
- Urgency assessment

### reprocess <id>

```bash
python3 "$PM_OS_COMMON/tools/slack/slack_mention_handler.py" --reprocess <id>
```

Replace `<id>` with the mention ID (e.g., `mention_CXXXXXXXXXX_1767948763_565469`).
This reprocesses an existing mention through the LLM to add formalized task details.

## Output Format

After running, summarize:

```
## Slack Mention Capture

**New mentions:** X
**Pending tasks:** Y
**Completed:** Z

### Captured This Run
- [type] Task description (from @User in #channel)
```

## Related Commands

- `/boot` - Includes mention capture with `--mentions` flag
- `/update-context` - Can include `--mentions` for integrated capture
