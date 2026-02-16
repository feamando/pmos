# PM-OS Google OAuth Integration

> Connecting Google Calendar, Drive, and Gmail to PM-OS

## Overview

PM-OS integrates with three Google services:

| Service | What PM-OS Uses It For |
|---------|----------------------|
| Google Calendar | Syncs upcoming events, meeting context for `/meeting-prep` |
| Google Drive | Reads documents referenced in brain entities, PRDs, specs |
| Gmail | Scans for relevant threads, action items, mentions |

The integration uses OAuth 2.0 with 6 scopes. Authentication happens during the installation wizard (Step 5: Integrations) or can be configured later.

---

## Setup Paths

### Path A: Bundled Credentials (Acme Corp Internal)

**Applies to:** Users who install from the private `pmos` repository.

The Google OAuth client secret (`google_client_secret.json`) is bundled directly in the pip package. No Google Cloud Console setup is needed.

**During `pm-os init`:**

1. At Step 5 (Integrations), the wizard asks to configure Google
2. Select "Configure" (or press Enter for default)
3. The wizard prints: `Google OAuth credentials found in package.`
4. Say "Yes" to authenticate now
5. Your default browser opens to Google's sign-in page
6. Sign in with your Google account and grant access to the requested scopes
7. The browser shows "Authentication successful" — you can close it
8. The wizard confirms: `Google authenticated! Token saved to .secrets/token.json`

The token is immediately available for brain population in Step 9.

**If you skip authentication during the wizard:**
- Credentials are still copied to `.secrets/credentials.json`
- You can authenticate later with `pm-os config google-auth`

### Path B: Manual Setup (Public Repository)

**Applies to:** Users who install from the public `feamando/pmos` repository.

You need to create your own Google Cloud OAuth credentials:

1. **Create a Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Click "New Project" or select an existing one

2. **Enable Required APIs**
   - In the project dashboard, go to "APIs & Services" > "Library"
   - Enable these three APIs:
     - Google Drive API
     - Google Calendar API
     - Gmail API

3. **Configure OAuth Consent Screen**
   - Go to "APIs & Services" > "OAuth consent screen"
   - Choose "Internal" (if Google Workspace) or "External"
   - Fill in app name (e.g., "PM-OS"), support email
   - Add the 6 scopes listed below
   - Add yourself as a test user (if External)

4. **Create OAuth Credentials**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth 2.0 Client ID"
   - Application type: **Desktop app**
   - Name: "PM-OS" (or any name)
   - Click "Create"

5. **Download the JSON File**
   - Click the download icon next to your new credential
   - Save the file (it will be named `client_secret_*.json`)

6. **Provide During Wizard**
   - Run `pm-os init`
   - At the Google integration step, enter the path to your downloaded JSON file
   - PM-OS copies it to `.secrets/credentials.json`

---

## OAuth Scopes

PM-OS requests 6 Google OAuth scopes:

| Scope | Access Level | Used By |
|-------|-------------|---------|
| `drive.readonly` | Read Google Drive files | Brain population, document sync |
| `drive.metadata.readonly` | Read Drive file metadata | Brain indexing, file discovery |
| `drive.file` | Access files created by PM-OS | Document output (PRDs, specs) |
| `gmail.readonly` | Read Gmail messages | Context updates, mention detection |
| `calendar.events` | Read/write calendar events | Meeting prep, calendar sync |
| `calendar.readonly` | Read calendar data | Event listing, availability |

These scopes are defined as a single source of truth in `pm_os.google_auth.GOOGLE_SCOPES` and used by:
- The OAuth flow during installation
- `GoogleSyncer` during brain population
- `google_scope_validator.py` during `/boot`
- `daily_context_updater.py` for context refresh

---

## Token Management

### Token Location

```
{install_path}/.secrets/
├── credentials.json    # OAuth client secret (from package or manual setup)
└── token.json          # User's OAuth token (generated after browser auth)
```

The `.secrets/` directory is created with mode `700` (owner-only access).

### Token Lifecycle

1. **Created** during wizard Step 5 (or manual `pm-os config google-auth`)
2. **Used** by brain population, daily context, and sync commands
3. **Refreshed** automatically when expired (using the refresh token)
4. **Invalidated** if scopes change or user revokes access

### Token Refresh

PM-OS automatically refreshes expired tokens using `load_or_refresh_credentials()`. No user action is needed for normal token expiry.

If the refresh token itself is revoked (e.g., user changed Google password, or revoked access in Google Account settings), delete the token and re-authenticate:

```bash
rm {install_path}/.secrets/token.json
pm-os brain sync --integration google
```

---

## Integration with Brain Population

During the wizard's Step 9 (Brain Population), Google sync:

1. Reads `google_credentials_path` and `google_token_path` from wizard data
2. Creates a `GoogleSyncer` with the pre-authenticated token (no second browser popup)
3. Syncs calendar events → brain entities in `brain/entities/`
4. Syncs Drive files → brain entities with document metadata
5. Uses all 6 scopes for comprehensive data access

After initial setup, Google sync runs as part of:
- `pm-os brain sync` (all integrations)
- `pm-os brain sync --integration google` (Google only)
- Daily context updates via `/boot`

---

## Scope Migration

### Upgrading from 2-Scope Tokens

Earlier versions of PM-OS used only 2 scopes (`calendar.readonly`, `drive.readonly`). Version 3.3+ requires all 6 scopes. If you have an old token:

1. The `google_scope_validator.py` (run during `/boot`) detects the mismatch
2. Delete the old token: `rm {install_path}/.secrets/token.json`
3. Re-authenticate: `pm-os brain sync --integration google`
4. The new token will have all 6 scopes

You can verify your token's scopes:

```bash
python3 -c "
import json
token = json.load(open('{install_path}/.secrets/token.json'))
print(f'Scopes: {len(token.get(\"scopes\", []))}')
for s in token.get('scopes', []):
    print(f'  - {s}')
"
```

Expected output: 6 scopes.

---

## Troubleshooting

### "Google OAuth credentials not found"

- **HF users:** Verify package installation: `python3 -c "from pm_os.google_auth import has_bundled_credentials; print(has_bundled_credentials())"`
  - Should print `True`. If `False`, reinstall: `pip install -e ".[all]"`
- **Public users:** Ensure `credentials.json` exists in `.secrets/`

### Browser doesn't open during OAuth

- Check that a default browser is configured on your system
- The OAuth flow starts a local HTTP server on a random port — ensure no firewall blocks localhost
- Try running in a terminal with display access (not over SSH without X forwarding)

### "Access blocked: This app's request is invalid"

- The OAuth client ID may be misconfigured
- For manual setup: ensure Application type is "Desktop app", not "Web application"
- Check that all 3 APIs are enabled in your Google Cloud project

### "Token has been expired or revoked"

```bash
rm {install_path}/.secrets/token.json
pm-os brain sync --integration google
```

### "Insufficient scopes"

Old 2-scope tokens don't have enough permissions. Delete and re-authenticate:

```bash
rm {install_path}/.secrets/token.json
pm-os brain sync --integration google
```

---

## Security

### Client Secret Distribution

- The `google_client_secret.json` is included only in the private `pmos` repository
- The public `feamando/pmos` repository does NOT include this file
- The `has_bundled_credentials()` function gracefully returns `False` when the file is absent
- All code paths handle the missing-credentials case without errors

### Token Storage

- OAuth tokens are stored in `.secrets/token.json` with the `.secrets/` directory set to mode `700`
- The `credentials.json` file is also in `.secrets/` with restricted access
- Neither file is committed to git (`.gitignore` excludes `.secrets/`)

### Template Install Security

When using `pm-os init --template config.yaml`, API tokens from the template are:
- Written to `.env` (for runtime use)
- **NOT** written to `config.yaml` (stripped by `_strip_secrets_from_config()`)
- The `_strip_secrets_from_config()` function removes all keys matching: `token`, `api_key`, `api_token`, `secret`, `password`

---

*Last updated: 2026-02-11*
*PM-OS Version: 3.4.0*
