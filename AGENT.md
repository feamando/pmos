# AGENT.md - AI Agent Entry Point

> **For comprehensive operational guidelines, refer to: `AI_Guidance/Rules/AI_AGENTS_GUIDE.md`**

## High-Level Goals
- Manage Product Management documentation via CLI & Markdown.
- Maintain a "Single Source of Truth" in `Products/`, `Team/`, `Reporting/`.
- Use the Brain knowledge graph for semantic memory and context.

## Key Commands & Workflows
- **Boot:** `/boot` - Initialize agent with full context
- **Find Context:** `grep -r "Term" AI_Guidance/Core_Context`
- **Search GDocs:** `python AI_Guidance/Tools/gdrive_mcp/server.py --cli search "Query"`
- **Jira/Confluence:** `python AI_Guidance/Tools/jira_mcp/server.py --cli [get_issue|search_issues|get_page]`
- **Sync Jira:** `python AI_Guidance/Tools/jira_brain_sync.py`
- **Sync GitHub:** `python AI_Guidance/Tools/github_brain_sync.py`
- **Update Context:** Run daily context updater
- **New Doc:** Check templates first

## Directory Map
- `AI_Guidance/`: Rules, Tools, Brain, Context
  - `Rules/`: Operational guides
  - `Tools/`: Python automation scripts
  - `Brain/`: Semantic knowledge graph
- `Products/`: Specs, Roadmaps, Decision Logs
- `Reporting/`: Weekly/Monthly updates, Sprint Reports
- `Planning/`: OKRs & Strategy
- `Team/`: 1:1s, feedback, recruiting
