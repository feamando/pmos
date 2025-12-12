# PM-OS Distribution Maintenance Guide

This document defines how to update the `Products/PM-OS_Distribution` "Golden Image" when the core system (the "Main Branch") evolves.

## The Sync Workflow

The Distribution folder is **NOT** a symlink. It is a snapshot. When you improve the core system (e.g., improve `boot.ps1` or add a new Tool), you must explicitly update the distribution package.

### 1. Update Core Files (Payload)
Run these commands to overwrite the distribution payload with your latest working versions.

```powershell
# Update Scripts
cp boot.ps1 "Products/PM-OS_Distribution/payload/"
cp logout.ps1 "Products/PM-OS_Distribution/payload/"
cp update-context.ps1 "Products/PM-OS_Distribution/payload/"
cp read_docx.py "Products/PM-OS_Distribution/payload/"

# Update Core Guidance (AGENT Rules)
# NOTE: Do NOT overwrite PERSONA_TEMPLATE.md unless you changed the *structure* of NGO.md.
cp AI_Guidance/Rules/AGENT.md "Products/PM-OS_Distribution/payload/AI_Guidance/Rules/"
cp AI_Guidance/Rules/AGENT_HOW_TO.md "Products/PM-OS_Distribution/payload/AI_Guidance/Rules/"
cp AI_Guidance/Rules/AI_AGENTS_GUIDE.md "Products/PM-OS_Distribution/payload/AI_Guidance/Rules/"

# Update Frameworks (Templates)
cp -r AI_Guidance/Frameworks/* "Products/PM-OS_Distribution/payload/AI_Guidance/Frameworks/" -Force

# Update Tools (Careful Sync)
# We use Robocopy (Windows) or rsync (Linux) logic to update tools but EXCLUDE secrets.
# PowerShell Example:
Copy-Item -Path "AI_Guidance/Tools" -Destination "Products/PM-OS_Distribution/payload/AI_Guidance/" -Recurse -Force
```

### 2. Sanitize (CRITICAL)
**ALWAYS** run the sanitization step immediately after copying tools to ensure no secrets leak into the distribution folder.

```powershell
# Remove Secrets
Remove-Item "Products/PM-OS_Distribution/payload/AI_Guidance/Tools/gdrive_mcp/credentials.json" -ErrorAction SilentlyContinue
Remove-Item "Products/PM-OS_Distribution/payload/AI_Guidance/Tools/gdrive_mcp/token.json" -ErrorAction SilentlyContinue
Remove-Item "Products/PM-OS_Distribution/payload/AI_Guidance/Tools/client_secret*.json" -ErrorAction SilentlyContinue

# Clean Python Artifacts
Get-ChildItem "Products/PM-OS_Distribution/payload" -Include "__pycache__", "*.pyc", "venv", ".git" -Recurse | Remove-Item -Force -Recurse
```

### 3. Update Templates (If Structural Changes Occurred)
If you changed the *structure* of `NGO.md` (e.g., added a new section like "12. Quick Reference"), you must update the template:

1.  Copy `AI_Guidance/Rules/NGO.md` to `Products/PM-OS_Distribution/payload/AI_Guidance/Rules/PERSONA_TEMPLATE.md`.
2.  **Manually Edit** the new template to replace your specific details with Jinja variables:
    *   `Nikita Gorshkov` -> `{{ USER_NAME }}`
    *   `Director of Product...` -> `{{ USER_ROLE }}`
    *   `New Ventures...` -> `{{ TEAM_DESCRIPTION }}`
    *   `Holger Hammel` -> `{{ REPORTS_TO }}`

### 4. Version Bump
If significant changes were made, update the `README.md` in `Products/PM-OS_Distribution` with a new version number or changelog entry.

## AI Agent Instruction
To ask an agent to perform this update, prompt:
> "Update the PM-OS Distribution package with the latest system files. Ensure all tools are sanitized and secrets are removed."
