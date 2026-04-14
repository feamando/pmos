---
description: Monitor and process Slack mentions for the configured bot
---

# /slackbot — Slack Mention Capture

Monitor and process Slack mentions for the configured bot.

Parse the first argument to determine which subcommand to run:

| Subcommand | Description |
|------------|-------------|
| `scan` | Scan channels for new mentions |
| `status` | Show mention processing status |
| `export` | Export pending tasks to markdown |
| `process` | Process and classify pending mentions |

If no arguments provided, run `scan`.

## scan

Scan configured Slack channels for bot mentions and classify them.

```bash
python3 tools/slack/slack_mention_handler.py --scan
```

Scans channels from `config.integrations.slack.channels` for mentions of the configured
bot user. New mentions are classified and added to the tracking state.

## status

Show current mention tracking status.

```bash
python3 tools/slack/slack_mention_handler.py --status
```

Displays: total mentions, pending tasks, completed tasks, stale items.

## export

Export pending mention tasks to markdown for context integration.

```bash
python3 tools/slack/slack_mention_handler.py --export
```

Generates markdown summary of open tasks from Slack mentions.

## process

Process and classify pending mentions with LLM assistance.

```bash
python3 tools/slack/slack_mention_handler.py --process
```

Uses LLM to formalize raw mentions into structured tasks with
owner, priority, and description.

## Examples

```
/slackbot                    # Scan for new mentions
/slackbot status             # Show mention stats
/slackbot export             # Export pending tasks
/slackbot process            # Classify with LLM
```

## Execute

Parse arguments and run the appropriate slackbot subcommand.
