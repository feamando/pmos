# Creating Your PM-OS Slackbot

> Guide to setting up a custom Slackbot with PM-OS context

## Overview

PM-OS includes a Slackbot capability that can answer questions using your Brain and context. This guide covers setting up your own bot.

## Prerequisites

- Slack workspace admin access (or ability to request app installation)
- PM-OS installed and configured
- Python 3.10+

## Step 1: Create Slack App

1. Go to https://api.slack.com/apps
2. Click "Create New App"
3. Choose "From scratch"
4. Name: "PM-OS Assistant" (or your preference)
5. Select your workspace

## Step 2: Configure OAuth Scopes

Navigate to "OAuth & Permissions" and add these **Bot Token Scopes**:

| Scope | Purpose |
|-------|---------|
| `app_mentions:read` | Receive @mentions |
| `channels:history` | Read channel messages |
| `channels:read` | List channels |
| `chat:write` | Post messages |
| `users:read` | Get user info |
| `reactions:write` | Add reactions |

Optional scopes for enhanced features:

| Scope | Purpose |
|-------|---------|
| `files:read` | Read shared files |
| `reactions:read` | Read reactions |
| `groups:history` | Private channels |

## Step 3: Enable Event Subscriptions

1. Go to "Event Subscriptions"
2. Enable Events
3. Set Request URL to your server endpoint (see Step 6)
4. Subscribe to bot events:
   - `app_mention` - When bot is @mentioned
   - `message.channels` - Messages in channels

## Step 4: Configure PM-OS

Add to `user/.env`:

```bash
# Slack Bot Token (starts with xoxb-)
SLACK_BOT_TOKEN=xoxb-your-bot-token-here

# User OAuth Token (optional, starts with xoxp-)
USER_OAUTH_TOKEN=xoxp-your-user-token-here

# Your Slack User ID (for permissions)
SLACK_USER_ID=U0YOURSLACKID

# App ID
SLACK_APP_ID=A0YOURAPPID
```

Add to `user/config.yaml`:

```yaml
integrations:
  slack:
    enabled: true
    bot_name: "PM-OS Assistant"
    channels:
      - "pm-os-support"
      - "your-team-channel"
    mention_response: true
    context_aware: true
```

## Step 5: Test Locally

Run the mention handler:

```bash
cd $PM_OS_COMMON/tools/slack
python3 slack_mention_handler.py --test
```

Post a test message in Slack:
```
@PM-OS Assistant What is the status of the payment gateway project?
```

## Step 6: Deploy for Production

### Option A: Background Process

Run handler in background:

```bash
python3 slack_mention_handler.py --daemon &
```

### Option B: Socket Mode (Recommended)

1. Enable Socket Mode in Slack App settings
2. Generate App-Level Token with `connections:write`
3. Add to `.env`:
   ```bash
   SLACK_APP_TOKEN=xapp-your-app-token
   ```
4. Run socket handler:
   ```bash
   python3 slack_mention_handler.py --socket
   ```

### Option C: Webhook Server

Deploy a web server that receives Slack events:

```python
from flask import Flask, request
from slack.slack_mention_handler import handle_mention

app = Flask(__name__)

@app.route('/slack/events', methods=['POST'])
def slack_events():
    data = request.json
    if data.get('type') == 'url_verification':
        return data['challenge']
    if data.get('event', {}).get('type') == 'app_mention':
        handle_mention(data['event'])
    return '', 200

if __name__ == '__main__':
    app.run(port=3000)
```

## Step 7: Configure Response Behavior

### Response Types

The bot can respond in different ways:

```yaml
# user/config.yaml
slack:
  response_mode: "thread"  # thread, channel, dm
  include_sources: true    # Reference Brain entities
  max_response_length: 2000
```

### Context Sources

Configure what context the bot uses:

```yaml
slack:
  context_sources:
    - brain_entities     # People, teams, projects
    - daily_context      # Today's context file
    - recent_sessions    # Recent session notes
    - jira_status        # Live Jira data
```

## How the Bot Works

```mermaid
sequenceDiagram
    participant U as User
    participant S as Slack
    participant H as Handler
    participant B as Brain
    participant L as LLM

    U->>S: @bot What's the payment status?
    S->>H: app_mention event
    H->>B: Load relevant context
    B-->>H: Payment project, team, blockers
    H->>L: Query with context
    L-->>H: Response
    H->>S: Post threaded reply
    S-->>U: "Payment gateway is 70% complete..."
```

## Customizing Responses

### Custom Prompt Template

Create `user/slack/bot_prompt.md`:

```markdown
You are a PM assistant bot with access to the following context:

## Brain Entities
{brain_context}

## Daily Context
{daily_context}

## User Question
{question}

Respond helpfully and concisely. Reference specific entities when relevant.
```

### Response Formatting

Configure formatting in config:

```yaml
slack:
  format:
    use_blocks: true       # Slack Block Kit
    code_blocks: true      # Format code properly
    link_entities: true    # Link to Confluence/Jira
```

## Advanced Features

### Channel-Specific Behavior

```yaml
slack:
  channels:
    "C0TEAM123":
      name: "team-channel"
      context: ["team_projects", "sprint_status"]
    "C0SUPPORT456":
      name: "pm-os-support"
      context: ["documentation", "faq"]
```

### Scheduled Updates

Post automatic updates:

```python
from slack.slack_context_poster import post_scheduled_update

# Daily standup summary at 9am
post_scheduled_update(
    channel="C0TEAM123",
    update_type="standup",
    schedule="0 9 * * 1-5"  # Cron format
)
```

### Reaction Triggers

Respond to emoji reactions:

```yaml
slack:
  reaction_triggers:
    "question":  # ❓ emoji
      action: "answer_question"
    "brain":     # 🧠 emoji
      action: "add_to_brain"
```

## Troubleshooting

### Bot not responding

1. Check bot token is valid:
   ```bash
   python3 config_loader.py --slack
   ```

2. Verify bot is in the channel

3. Check event subscriptions are enabled

4. Look at handler logs:
   ```bash
   python3 slack_mention_handler.py --debug
   ```

### Slow responses

1. Pre-load Brain context:
   ```bash
   python3 brain_loader.py --cache
   ```

2. Use smaller context window in config

3. Consider background processing with acknowledgment

### Missing context

1. Run `/update-context` to refresh

2. Check Brain entities exist:
   ```bash
   python3 brain_loader.py --search "topic"
   ```

3. Verify context sources in config

## Security Considerations

1. **Token security**: Never commit tokens to git
2. **Channel restrictions**: Limit bot to specific channels
3. **Rate limiting**: Implement rate limits for public channels
4. **Audit logging**: Log all bot interactions

## Example Interactions

### Project Status
```
User: @bot What's the status of the payment gateway project?
Bot: 📊 **Payment Gateway Migration**

Status: In Progress (70%)
Owner: @alice_smith
Team: Platform Team

**Recent Updates:**
- API integration complete
- Testing phase started

**Blockers:**
- Waiting on vendor API documentation

See: [PLAT-100](jira-link) | [PRD](confluence-link)
```

### Person Lookup
```
User: @bot Who is working on authentication?
Bot: 🧑‍💻 **Authentication Project Team**

**Lead:** Alice Smith (@alice_smith)
- Senior Engineer, Platform Team
- Expertise: Backend, Security

**Also involved:**
- Bob Jones (Code Review)
- Charlie Dev (Testing)

Recent activity: Sprint 12 planning completed
```

---

## Related Documentation

- [Integration Commands](../commands/integration-commands.md)
- [Integration Tools](../tools/integration-tools.md)
- [Brain Architecture](../05-brain.md)

---

*Last updated: 2026-01-13*
