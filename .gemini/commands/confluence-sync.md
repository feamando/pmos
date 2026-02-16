# Confluence Sync

Search and sync Confluence pages to Brain for use in document research.

## Arguments
$ARGUMENTS

## Instructions

The user wants to sync Confluence content to Brain. Parse their request:

### Search Confluence

If `--search <query>` is provided:

```bash
python3 "$PM_OS_COMMON/tools/integrations/confluence_brain_sync.py" --search "$ARGUMENTS"
```

This will:
1. Search Confluence for pages matching the query
2. Display results with page IDs, titles, and spaces
3. Optionally sync results to Brain/Inbox/Confluence/

### Sync Specific Page

If `--page <page_id>` is provided:

```bash
python3 "$PM_OS_COMMON/tools/integrations/confluence_brain_sync.py" --page $ARGUMENTS --sync
```

This will:
1. Fetch the full content of the specified page
2. Convert HTML to markdown
3. Save to Brain/Inbox/Confluence/ with metadata

### Get Recent Pages

If `--space <SPACE_KEY> --recent <N>` is provided:

```bash
python3 "$PM_OS_COMMON/tools/integrations/confluence_brain_sync.py" --space $ARGUMENTS --recent 10 --sync
```

This will:
1. Get the N most recently modified pages in that space
2. Sync them to Brain/Inbox/Confluence/

### List Synced Pages

If `--list` is provided:

```bash
python3 "$PM_OS_COMMON/tools/integrations/confluence_brain_sync.py" --list-synced
```

This will show all pages already synced to Brain.

### Search and Sync

If `--search <query> --sync` is provided:

```bash
python3 "$PM_OS_COMMON/tools/integrations/confluence_brain_sync.py" --search "$ARGUMENTS" --sync --limit 10
```

This will:
1. Search Confluence for matching pages
2. Sync top results to Brain/Inbox/Confluence/
3. Report how many pages were synced

## Configuration

Confluence sync requires environment variables:

```bash
CONFLUENCE_URL=https://company.atlassian.net/wiki
CONFLUENCE_EMAIL=your-email@company.com
CONFLUENCE_API_TOKEN=your-api-token
CONFLUENCE_SPACES=SPACE1,SPACE2  # Optional: default spaces to search
```

To generate an API token:
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Create a new token
3. Add to your .env file

## Examples

**Search:**
- `/confluence-sync --search OTP architecture`
- `/confluence-sync --search "checkout flow"`

**Sync specific page:**
- `/confluence-sync --page 12345678`

**Recent pages from space:**
- `/confluence-sync --space PROJ --recent 10`

**Search and sync:**
- `/confluence-sync --search "BB app" --sync --limit 5`

**List synced:**
- `/confluence-sync --list`

## Output

Synced pages are saved to `$PM_OS_USER/brain/Inbox/Confluence/` with format:
- Filename: `<page_id>_<title_slug>.md`
- Frontmatter: confluence_id, title, space, url, last_modified, synced_at
- Content: Converted from HTML to markdown

## Use Cases

1. **Pre-PRD Research:** Sync relevant Confluence docs before generating PRD
2. **Architecture Context:** Pull architectural decision docs before ADR
3. **Competitor Analysis:** Sync competitive analysis pages
4. **Team Knowledge:** Keep Brain updated with latest team documentation

## Notes

- Requires `atlassian-python-api` package: `pip install atlassian-python-api`
- Synced pages are cached - re-sync to update
- HTML is converted to markdown-like text (tables, lists, formatting preserved)
- Large pages may be truncated for context window efficiency
