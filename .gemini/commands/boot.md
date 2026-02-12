# Boot Agent Context

Load foundational context files and initialize PM-OS session.

## Quick Start (Recommended)

Run the boot orchestrator to execute ALL steps automatically:

```bash
source user/.env && python3 common/tools/boot/boot_orchestrator.py
```

For quick boot (skip context update, meeting prep, Slack):
```bash
source user/.env && python3 common/tools/boot/boot_orchestrator.py --quick
```

For quiet boot (skip Slack posting):
```bash
source user/.env && python3 common/tools/boot/boot_orchestrator.py --quiet
```

After running the orchestrator, read the core files:
1. `Read: common/AGENT.md`
2. `Read: user/USER.md`
3. `Read: user/context/YYYY-MM-DD-context.md` (today's date)

## Manual Steps (Reference)

### Step 0: Set Environment

Ensure PM-OS environment is configured:

```bash
# Check if environment is set
if [ -z "$PM_OS_COMMON" ]; then
    # Find and source boot script
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    source "$SCRIPT_DIR/scripts/boot.sh"
fi
```

### Step 0.5: Sync Developer Commands (if developer folder exists)

If the developer folder exists, sync developer commands to common so they're visible to Claude:

```bash
if [ -d "$PM_OS_ROOT/developer" ]; then
    python3 "$PM_OS_COMMON/tools/util/command_sync.py" --quiet
fi
```

This makes beads (`/bd-*`) and roadmap (`/parse-roadmap-inbox`, etc.) commands available.

### Step 0.6: Pre-Flight Checks (unless --quick)

Run pre-flight verification to ensure all tools are working:

```bash
python3 "$PM_OS_COMMON/tools/preflight/preflight_runner.py" --quick
```

If any critical checks fail, report the failures and suggest running the full check:
```bash
python3 "$PM_OS_COMMON/tools/preflight/preflight_runner.py"
```

Skip this step if `--quick` flag is provided.

### Step 1: Load Core Files

Read these files in order:

1. **Agent Entry Point**
   ```
   Read: $PM_OS_COMMON/AGENT.md
   ```

2. **Agent Rules**
   ```
   Read: $PM_OS_COMMON/rules/AI_AGENTS_GUIDE.md
   ```

3. **User Persona** (if exists)
   ```
   Read: $PM_OS_USER/USER.md
   ```
   Or for v2.4 compatibility:
   ```
   Read: $PM_OS_USER/AI_Guidance/Rules/NGO.md
   ```

### Step 1.5: Validate Google OAuth Scopes

Ensure Google token has all required scopes (Drive, Gmail, Calendar). If scopes are missing, trigger re-authentication:

```bash
python3 "$PM_OS_COMMON/tools/integrations/google_scope_validator.py" --fix --quiet
```

This prevents "insufficient permissions" errors during context sync. The validator checks for 6 required scopes and triggers OAuth if any are missing.

Skip this step if `--quick` flag is provided.

### Step 2: Update Daily Context

Run the context update to sync from integrations:

```bash
python3 "$PM_OS_COMMON/tools/daily_context/daily_context_updater.py"
```

### Step 3: Load Latest Context

Read the daily context file:

```bash
# Find today's context
CONTEXT_FILE="$PM_OS_USER/context/$(date +%Y-%m-%d)-context.md"
# Or v2.4 path
V24_CONTEXT="$PM_OS_USER/$PM_OS_USER/context/$(date +%Y-%m-%d)-context.md"
```

Read whichever exists.

### Step 4: Load Hot Topics

Load Brain hot topics for quick reference (default behavior scans latest context):

```bash
python3 "$PM_OS_COMMON/tools/brain/brain_loader.py"
```

### Step 5: Start Session Services

Check session status and start if needed:

1. **Check Confucius status** (session notes)
   ```bash
   python3 "$PM_OS_COMMON/tools/session/confucius_agent.py" --status
   ```
   If no active session, start one:
   ```bash
   python3 "$PM_OS_COMMON/tools/session/confucius_agent.py" --start "Daily Work Session"
   ```

2. **Check session manager status**
   ```bash
   python3 "$PM_OS_COMMON/tools/session/session_manager.py" --status
   ```

### Step 5.5: Capture Roadmap Items

Capture PM-OS feature requests and bugs from recent Slack mentions to the roadmap inbox:

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/roadmap/roadmap_inbox_manager.py" --capture
```

This captures items classified as `pmos_feature` or `pmos_bug` from the mentions state file. Each captured item:
- Gets a temp ID (tmp-XXXX)
- Is posted to the original Slack thread: "captured to temp inbox with tmp.id X"
- Appears in `/common/data/roadmap/tmp-roadmap-inbox.md`

To parse captured items, run `/parse-roadmap-inbox`.

Skip this step if `--quick` flag is provided or if developer tools are not available.

### Step 6: Report Status

Summarize boot status:

```
PM-OS Boot Complete

Environment:
  - Root: $PM_OS_ROOT
  - Common: $PM_OS_COMMON (v3.0)
  - User: $PM_OS_USER
  - Developer: [enabled if /developer exists, show synced command count]

Context: [date] loaded
Hot Topics: [count] items
Confucius: [enabled/disabled]
Integrations: [list of enabled]

Ready for commands. Type /help for available commands.
```

### Step 6.5: Generate Meeting Pre-Reads

List upcoming meetings and generate pre-reads for key ones:

```bash
# List meetings in next 24 hours
python3 "$PM_OS_COMMON/tools/meeting/meeting_prep.py" --list --hours 24

# Generate pre-reads for 1:1s and important meetings
python3 "$PM_OS_COMMON/tools/meeting/meeting_prep.py" --hours 24 --with-jira
```

This creates pre-read documents in `$PM_OS_USER/planning/Meeting_Prep/` with:
- Past meeting notes from GDrive
- Participant context from Brain
- Relevant Jira issues

Skip this step if `--quick` flag is provided.

### Step 7: Post to Slack

Post boot context summary to the configured Slack channel:

```bash
python3 "$PM_OS_COMMON/tools/slack/slack_context_poster.py" "$CONTEXT_FILE" --type boot
```

This posts critical alerts, action items, blockers, and key dates to `#pmos-slack-channel` (or channel configured in `ralph_slack_channel`).

Skip this step if `--quiet` flag is provided or if Slack integration is disabled in config.

## V2.4 Compatibility

This command works with both v3.0 and v2.4 structures. Path resolution automatically detects which structure is in use.

For v2.4 installations without migration:
- Tools path: `AI_Guidance/Tools/`
- Context path: `$PM_OS_USER/context/`
- Brain path: `$PM_OS_USER/brain/`

## Quick Boot

For a minimal boot without context update:

```
/boot --quick
```

This skips Step 2 (context update) for faster startup.

## Troubleshooting

**Environment not set:**
```bash
source $PM_OS_COMMON/scripts/boot.sh  # Mac/Linux
. $PM_OS_COMMON\scripts\boot.ps1       # Windows
```

**Config not found:**
```bash
cp $PM_OS_COMMON/config.yaml.example $PM_OS_USER/config.yaml
# Then edit config.yaml with your settings
```

**Tools not found:**
Ensure PYTHONPATH includes tools directory:
```bash
export PYTHONPATH="$PM_OS_COMMON/tools:$PYTHONPATH"
```
