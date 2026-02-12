# Boot Developer Environment

Initialize PM-OS developer tools session.

## Instructions

### Step 1: Set Environment

```bash
export PM_OS_MODE=developer
export PM_OS_DEVELOPER_ROOT="/Users/jane.smith/pm-os/developer"
export PYTHONPATH="$PM_OS_DEVELOPER_ROOT/tools:$PYTHONPATH"
```

### Step 2: Run Preflight

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/preflight/preflight_runner.py" --quick
```

### Step 3: Check Session Status

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/session/session_manager.py" --status
```

### Step 4: Report Status

Report the environment status:
- Developer Root path
- Preflight results
- Active session (if any)
- Available tools

## Quick Reference

**Session Management:**
- Create: `python3 tools/session/session_manager.py --create "Title"`
- Status: `python3 tools/session/session_manager.py --status`
- Archive: `python3 tools/session/session_manager.py --archive`

**Confucius Notes:**
- Start: `python3 tools/session/confucius_agent.py --start "Topic"`
- Status: `python3 tools/session/confucius_agent.py --status`

**Ralph Features:**
- Init: `python3 tools/ralph/ralph_manager.py init feature-name`
- Status: `python3 tools/ralph/ralph_manager.py status feature-name`
- List: `python3 tools/ralph/ralph_manager.py list`

**Preflight:**
- Check: `python3 tools/preflight/preflight_runner.py --quick`
- List tools: `python3 tools/preflight/preflight_runner.py --list`
