# Common Issues

> Known issues and their solutions

## Quick Diagnostics

The fastest way to diagnose issues is with the PM-OS doctor command:

```bash
pm-os doctor          # Check installation health
pm-os doctor --fix    # Auto-fix common issues
```

The doctor command checks:
- Directory structure
- Configuration validity
- Integration credentials
- Python dependencies

## Installation Issues

### Module not found: config_loader

**Symptom:**
```
ModuleNotFoundError: No module named 'config_loader'
```

**Cause:** Python path not set correctly.

**Solution:**

1. Run from the correct directory:
   ```bash
   cd $PM_OS_COMMON/tools
   python3 tool_name.py
   ```

2. Or set PYTHONPATH:
   ```bash
   export PYTHONPATH=$PM_OS_COMMON/tools:$PYTHONPATH
   ```

3. Or ensure the tool has correct imports:
   ```python
   import sys
   import os
   sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
   ```

---

### Cannot resolve PM-OS paths

**Symptom:**
```
PathResolutionError: Could not locate PM-OS directories
```

**Cause:** Path resolver can't find PM-OS structure.

**Solution:**

1. Create marker file:
   ```bash
   touch ~/pm-os/.pm-os-root
   ```

2. Or set environment variables:
   ```bash
   export PM_OS_ROOT=~/pm-os
   export PM_OS_COMMON=~/pm-os/common
   export PM_OS_USER=~/pm-os/user
   ```

3. Run `/boot` to set environment.

---

### python-dotenv not installed

**Symptom:**
```
Warning: python-dotenv not installed
```

**Solution:**
```bash
pip install python-dotenv
```

---

## Authentication Issues

### Jira connection failed

**Symptom:**
```
JiraError: 401 Unauthorized
```

**Cause:** Invalid Jira credentials.

**Solution:**

1. Verify credentials in `user/.env`:
   ```bash
   JIRA_URL=https://company.atlassian.net
   JIRA_USERNAME=your.email@company.com
   JIRA_API_TOKEN=your_token
   ```

2. Regenerate API token at:
   https://id.atlassian.com/manage-profile/security/api-tokens

3. Test credentials:
   ```bash
   python3 config_loader.py --jira
   ```

---

### Slack token invalid

**Symptom:**
```
slack_sdk.errors.SlackApiError: invalid_auth
```

**Cause:** Slack token expired or invalid.

**Solution:**

1. Check token in `user/.env`:
   ```bash
   SLACK_BOT_TOKEN=xoxb-your-token
   ```

2. Reinstall Slack app at:
   https://api.slack.com/apps

3. Verify scopes include:
   - `channels:history`
   - `chat:write`
   - `users:read`

---

### Google OAuth error

**Symptom:**
```
google.auth.exceptions.RefreshError: The credentials have been revoked
```

**Cause:** OAuth token expired or revoked.

**Solution:**

1. Delete existing token:
   ```bash
   rm ~/pm-os/user/.secrets/token.json
   ```

2. Re-authenticate:
   ```bash
   python3 tools/integrations/gdocs_processor.py
   ```

3. Complete OAuth flow in browser.

---

## Runtime Issues

### Context file too large

**Symptom:**
```
Context exceeds maximum size
```

**Cause:** Context file larger than can fit in context window.

**Solution:**

1. Check file size:
   ```bash
   python3 file_chunker.py --check context.md
   ```

2. Split if needed:
   ```bash
   python3 file_chunker.py --split context.md
   ```

3. Or use smaller context update:
   ```
   /update-context quick
   ```

---

### Session not saving

**Symptom:** Session save reports success but data not persisted.

**Cause:** Write permissions or path issues.

**Solution:**

1. Verify sessions directory exists:
   ```bash
   ls -la ~/pm-os/user/sessions/
   ```

2. Check permissions:
   ```bash
   chmod 755 ~/pm-os/user/sessions/
   ```

3. Verify session manager:
   ```bash
   python3 session_manager.py --status
   ```

---

### Brain entity not found

**Symptom:**
```
EntityNotFound: No entity 'alice_smith' in person/
```

**Cause:** Entity doesn't exist or ID misspelled.

**Solution:**

1. Check entity exists:
   ```bash
   ls ~/pm-os/user/brain/entities/person/
   ```

2. Verify ID matches filename (without extension).

3. Search Brain:
   ```bash
   python3 brain_loader.py --search "alice"
   ```

---

### FPF state corrupted

**Symptom:** FPF commands fail with state errors.

**Cause:** Interrupted FPF cycle or corrupted state.

**Solution:**

1. Check FPF status:
   ```
   /q-status
   ```

2. Reset if needed:
   ```
   /q-reset --archive
   ```

3. Remove corrupted state:
   ```bash
   rm ~/pm-os/user/brain/reasoning/active-cycle.yaml
   ```

---

## Integration Issues

### Jira sync returning empty

**Symptom:** `/jira-sync` completes but no data synced.

**Cause:** Project keys not configured or no recent activity.

**Solution:**

1. Verify project keys in `user/config.yaml`:
   ```yaml
   integrations:
     jira:
       project_keys: ["PROJ1", "PROJ2"]
   ```

2. Check Jira permissions for those projects.

3. Try specific project:
   ```bash
   python3 jira_brain_sync.py --project PROJ1
   ```

---

### Slack posts not appearing

**Symptom:** `/boot` completes but no Slack post.

**Cause:** Wrong channel or missing permissions.

**Solution:**

1. Verify channel ID in config or command.

2. Ensure bot is member of channel.

3. Check bot permissions include `chat:write`.

4. Test directly:
   ```bash
   python3 slack_context_poster.py context.md --channel CXXXXXXXXXX
   ```

---

### Meeting prep not finding meetings

**Symptom:** `/meeting-prep` returns no meetings.

**Cause:** Google Calendar not connected or no upcoming meetings.

**Solution:**

1. Verify Google OAuth working:
   ```bash
   python3 gdocs_processor.py  # Should prompt for OAuth
   ```

2. Check calendar permissions include Calendar API.

3. Increase time window:
   ```
   /meeting-prep --hours 48
   ```

---

## Performance Issues

### Context update very slow

**Symptom:** `/update-context` takes >5 minutes.

**Cause:** Too many sources or large date range.

**Solution:**

1. Use quick mode:
   ```
   /update-context quick
   ```

2. Check state file for stuck state:
   ```bash
   cat ~/pm-os/common/tools/daily_context/state.json
   ```

3. Reset if needed:
   ```bash
   rm ~/pm-os/common/tools/daily_context/state.json
   ```

---

### Boot taking too long

**Symptom:** `/boot` takes >2 minutes.

**Cause:** Full boot with all syncs.

**Solution:**

1. Use quick boot:
   ```
   /boot quick
   ```

2. Or context-only:
   ```
   /boot context-only
   ```

---

## Getting Help

If these solutions don't work:

1. **Run diagnostics:**
   ```bash
   pm-os doctor          # Check installation health
   pm-os help troubleshoot  # View troubleshooting guide
   ```

2. **Check logs:** Look for error details in terminal output

3. **Slack support:** Post in `#pm-os-support`

4. **GitHub issues:** Report at the PM-OS repository

5. **Provide context:**
   - PM-OS version (`cat $PM_OS_COMMON/VERSION`)
   - Python version (`python3 --version`)
   - Output from `pm-os doctor`
   - Full error message
   - Steps to reproduce

---

*Last updated: 2026-02-09*
