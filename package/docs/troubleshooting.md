# PM-OS Troubleshooting Guide

This guide helps resolve common issues with PM-OS installation and operation.

## Quick Diagnostics

Run the doctor command to check your installation:

```bash
pm-os doctor
```

For detailed output:

```bash
pm-os doctor --verbose
```

To attempt automatic fixes:

```bash
pm-os doctor --fix
```

## Common Issues

### Installation Issues

#### "Configuration not found"

**Symptom:** Commands fail with "Run 'pm-os init' first"

**Solution:**
```bash
# Re-run initialization
pm-os init

# Or if you have a broken session
pm-os init --resume

# Or start fresh
rm ~/.pm-os-init-session.json
pm-os init
```

#### Session Stuck

**Symptom:** "A previous installation session was found" but resume fails

**Solution:**
```bash
# Clear the session file
rm ~/.pm-os-init-session.json

# Start fresh
pm-os init
```

#### Permission Denied

**Symptom:** Cannot write to installation directory

**Solution:**
```bash
# Check ownership
ls -la ~/pm-os

# Fix permissions
sudo chown -R $(whoami) ~/pm-os
chmod 755 ~/pm-os
chmod 600 ~/pm-os/.env  # Keep .env secure
```

### Credential Issues

#### Invalid API Key

**Symptom:** "Invalid API key" or "Authentication failed"

**Solutions:**

1. Verify the key format:
   - Anthropic: Starts with `sk-ant-` or `sk-`
   - OpenAI: Starts with `sk-`
   - GitHub: Starts with `ghp_`, `gho_`, or `github_pat_`
   - Slack: Starts with `xoxb-`

2. Test credentials directly:
   ```bash
   # Anthropic
   curl -H "x-api-key: YOUR_KEY" \
        -H "anthropic-version: 2023-06-01" \
        https://api.anthropic.com/v1/models

   # GitHub
   curl -H "Authorization: Bearer YOUR_TOKEN" \
        https://api.github.com/user
   ```

3. Regenerate the key in the provider's console

#### AWS Bedrock Access Denied

**Symptom:** "Access denied" or "No AWS credentials"

**Solution:**
```bash
# Verify AWS CLI is configured
aws sts get-caller-identity

# Check Bedrock access
aws bedrock list-foundation-models --region us-east-1

# If not configured
aws configure
```

### Sync Issues

#### Jira Sync Fails

**Symptom:** "Failed to fetch projects" or "401 Unauthorized"

**Solutions:**

1. Verify Jira URL format:
   ```
   https://your-domain.atlassian.net
   ```

2. Check API token (not password):
   - Generate at: https://id.atlassian.com/manage-profile/security/api-tokens

3. Verify email matches Jira account

#### Slack Sync Fails

**Symptom:** "invalid_auth" or "token_revoked"

**Solutions:**

1. Verify token type is `xoxb-` (bot token, not user token)

2. Check bot permissions in Slack app settings:
   - `channels:read`
   - `users:read`
   - `channels:history`

3. Reinstall the Slack app to your workspace

#### GitHub Sync Fails

**Symptom:** "Bad credentials" or "403 Forbidden"

**Solutions:**

1. Check token permissions (Settings > Developer settings > Personal access tokens):
   - `repo` (for private repos)
   - `read:org` (for org repos)
   - `user:read` (for user info)

2. Token may have expired - check expiration date

### Brain Issues

#### No Entities Found

**Symptom:** `pm-os brain status` shows 0 entities

**Solution:**
```bash
# Run sync
pm-os brain sync

# Or for specific integration
pm-os brain sync --integration jira
```

#### Sync State Corrupted

**Symptom:** Sync runs but doesn't update entities

**Solution:**
```bash
# Reset sync state
rm ~/pm-os/brain/.sync_state.json

# Run fresh sync
pm-os brain sync
```

## Debug Mode

Enable debug mode for verbose logging:

```bash
export PM_OS_DEBUG=1
pm-os init
```

Or for a single command:

```bash
PM_OS_DEBUG=1 pm-os brain sync
```

Debug mode shows:
- Full API request/response details
- Detailed error messages
- Step-by-step execution

## Log Files

Logs are written to:
```
~/pm-os/logs/pm-os-YYYY-MM-DD.log
```

View recent logs:
```bash
tail -f ~/pm-os/logs/pm-os-*.log
```

## Reset Installation

To completely reset PM-OS:

```bash
# Uninstall (keeps brain by default)
pm-os uninstall --yes

# Uninstall everything
pm-os uninstall --yes

# Reinstall
pm-os init
```

To preserve your brain while resetting config:

```bash
pm-os uninstall --yes --keep-brain
pm-os init
```

## Getting Help

1. Check the documentation:
   - `pm-os --help`
   - `pm-os <command> --help`

2. Run diagnostics:
   - `pm-os doctor --verbose`
   - `pm-os status --json`

3. Enable debug mode and check logs

4. Report issues: https://github.com/anthropics/pm-os/issues
