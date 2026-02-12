# AGENT.md - AI Agent Entry Point

> **For comprehensive operational guidelines, refer to: `AI_Guidance/Rules/AI_AGENTS_GUIDE.md`**

## High-Level Goals
- Manage Product Management documentation via CLI & Markdown.
- Maintain a "Single Source of Truth" in `Products/`, `Team/`, `Reporting/`.
- **Adopt Jane Smith's communication style & workflow as defined in `AI_Guidance/Rules/NGO.md`.**

## Brain
Before referencing any person, team, project, or system, check `BRAIN.md` (loaded at boot). For entities not in the index, use brain_loader or read the entity file directly from `user/brain/`.

## Key Commands & Workflows                                                  
- **Find Context:** `grep -r "Term" AI_Guidance/Core_Context`                
- **Search GDocs:** `python AI_Guidance/Tools/gdrive_mcp/server.py --cli search "Query"`
- **Jira/Confluence:** `python AI_Guidance/Tools/jira_mcp/server.py --cli [get_issue|search_issues|get_page]`
- **Update Context:** `./update-context.ps1` (Fetches & Agent synthesizes).
- **New Doc:** Check `AI_Guidance/Frameworks/` for templates first.          
- **Naming:** `kebab-case.md` or `YYYY-MM-DD-name.md`.
## Directory Map
- `AI_Guidance/`: Rules & Templates.
    - `Rules/NGO.md`: Operational Style Guide.
- `Products/`: Specs, Roadmaps, Decision Logs.
- `Reporting/`: Weekly/Monthly updates.
- `Planning/`: OKRs & Strategy.