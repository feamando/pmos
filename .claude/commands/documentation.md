# Documentation Manager

Manage PM-OS documentation: audit, create, sync, and status.

## Arguments

$ARGUMENTS

Available options:
- `-audit` - Check if documentation needs updates
- `-create [topic]` - Create or update documentation for a topic
- `-sync` - Sync all docs to Confluence PMOS space
- `-status` - Show documentation coverage status
- No argument - Show documentation index

## Instructions

Parse the argument and execute the appropriate action:

### Status (Default / `-status`)

Show documentation coverage and status:

1. Read the status file:
   ```bash
   cat "$PM_OS_COMMON/documentation/_meta/documentation-status.json"
   ```

2. Summarize:
   - Total documents
   - Coverage percentages (commands, tools, schemas)
   - Last audit date
   - Confluence sync status

3. Display in table format:
   ```
   | Category | Documented | Total | Coverage |
   |----------|------------|-------|----------|
   | Commands | 55 | 55 | 100% |
   | Tools | 70 | 70 | 100% |
   | Schemas | 7 | 7 | 100% |
   ```

### Audit (`-audit`)

Check for documentation gaps and needed updates:

1. **Scan Commands**
   - List all files in `$PM_OS_COMMON/.claude/commands/*.md`
   - Compare against documented commands in `documentation/commands/`
   - Identify undocumented or outdated commands

2. **Scan Tools**
   - List all Python files in `$PM_OS_COMMON/tools/**/*.py`
   - Compare against documented tools in `documentation/tools/`
   - Check for new parameters or changed signatures

3. **Scan Schemas**
   - List all schema files in `$PM_OS_COMMON/schemas/*.yaml`
   - Compare against `documentation/schemas/entity-schemas.md`

4. **Generate Audit Report**

   ```markdown
   # Documentation Audit Report

   **Date:** YYYY-MM-DD
   **Status:** [Up to Date / Action Required]

   ## New Items (Need Documentation)
   | Type | File | Priority |
   |------|------|----------|
   | Command | commands/new-cmd.md | High |
   | Tool | tools/new_tool.py | Medium |

   ## Changed Items (Need Update)
   | Type | File | Changes |
   |------|------|---------|
   | Tool | tools/slack/*.py | New parameters |

   ## Confluence Sync Status
   | Document | Local | Confluence | Status |
   |----------|-------|------------|--------|
   | overview.md | 2026-01-13 | - | Needs Sync |

   ## Recommendations
   1. Create documentation for new_cmd.md
   2. Update slack tool docs with new params
   3. Initial sync to Confluence
   ```

5. Update status file with audit results

### Create (`-create [topic]`)

Create or update documentation for a specific topic:

1. **Parse Topic**
   - If topic is a command name: generate command documentation
   - If topic is a tool path: generate tool documentation
   - If topic is "all": regenerate all documentation

2. **For Commands**
   - Read the command file from `.claude/commands/<topic>.md`
   - Extract: arguments, instructions, examples
   - Generate documentation following the command docs format
   - Write to `documentation/commands/` appropriate file

3. **For Tools**
   - Read the Python tool file
   - Extract: docstrings, function signatures, CLI arguments
   - Generate documentation following tool docs format
   - Write to `documentation/tools/` appropriate file

4. **Update Status**
   - Update `_meta/documentation-status.json`
   - Add to audit history

### Sync (`-sync`)

Sync documentation to Confluence PMOS space:

1. **Check Prerequisites**
   - Verify Confluence credentials in `.env`
   - Verify PMOS space exists and is accessible

2. **For Each Document**
   ```bash
   python3 "$PM_OS_COMMON/tools/documentation/confluence_doc_sync.py" \
     --file "$PM_OS_COMMON/documentation/<path>" \
     --space PMOS \
     --parent "PM-OS Documentation"
   ```

3. **Sync Order**
   - Parent page first (README.md → PM-OS Documentation)
   - Then child pages in order
   - Maintain hierarchy:
     ```
     PM-OS Documentation
     ├── Overview
     ├── Architecture
     ├── Installation
     ├── Workflows
     ├── Brain Architecture
     ├── Commands Reference
     │   ├── Core Commands
     │   ├── Document Commands
     │   └── ...
     ├── Tools Reference
     │   └── ...
     └── Troubleshooting
     ```

4. **Update Tracking**
   - Update `_meta/confluence-sync-log.md`
   - Update page IDs in `_meta/documentation-status.json`
   - Add Confluence links to local docs

5. **Report Results**
   ```
   Confluence Sync Complete

   Pages synced: 21
   New pages: 21
   Updated pages: 0

   View at: https://your-company.atlassian.net/wiki/spaces/PMOS
   ```

## Examples

```
/documentation                    # Show documentation index
/documentation -status            # Show coverage status
/documentation -audit             # Run documentation audit
/documentation -create boot       # Create docs for /boot command
/documentation -create tools/brain/brain_loader.py  # Create tool docs
/documentation -sync              # Sync to Confluence
```

## Notes

- Documentation lives in `$PM_OS_COMMON/documentation/`
- Status tracking in `_meta/documentation-status.json`
- Confluence sync requires `CONFLUENCE_*` vars in `.env`
- Run `-audit` periodically to catch documentation drift
