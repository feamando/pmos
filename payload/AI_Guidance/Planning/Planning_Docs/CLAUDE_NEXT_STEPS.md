# Outstanding Tasks: AI Brain Migration & Automation
**Date:** 2025-12-04
**From:** Gemini CLI Agent (Phase 3 Complete)
**To:** Claude Code

We have successfully established the **structure** and **tools** for the local RAG "Brain" (`AI_Guidance/Brain`). However, the vast majority of knowledge remains trapped in the monolithic `Core_Context` files.

## 1. Critical Data Migration (High Priority)
The `Brain/Projects/OTP.md` file is the only active semantic node. You must migrate the following topics from `2025-12-04-03-context.md` into their own Markdown files in `AI_Guidance/Brain/`:

*   **Projects:**
    *   Good Chop (H1 2026 Strategy, Product Prioritization) -> `Brain/Projects/Good_Chop.md`
    *   Factor / Cross-Selling -> `Brain/Projects/Cross_Selling.md`
    *   The Pets Table (TPT) -> `Brain/Projects/TPT.md`
*   **Entities:**
    *   Nikita Gorshkov (Role, Direct Reports, Key Focus) -> `Brain/Entities/Nikita_Gorshkov.md`
    *   Team PA (Recruiting, Status) -> `Brain/Entities/Team_PA.md`
*   **Architecture:**
    *   SCM / Logistics (Katana, Odin, Demeter) -> `Brain/Architecture/Logistics.md`

**Action:** Use `read_file` on the context file, extract sections, and use `write_file` or `update-brain.ps1` to populate the new nodes.

## 2. Documentation Update
The `AGENT_HOW_TO.md` and `NGO.md` files currently reference the old "Context Update" workflow.
*   **Task:** Update these documents to explain the new **Inbox -> Refine -> Semantic File** workflow.
*   **Key Concept:** Explain that `Core_Context` is now for *Episodic* history (what happened today), while `Brain` is for *Semantic* state (what is true about the project).

## 3. Automation: The "Gardener" Script
Currently, processing the `Inbox` is manual.
*   **Goal:** Create `process-inbox.ps1`.
*   **Logic:** This script should read files in `Brain/Inbox`, prompt the Agent (you) with their content, and ask: "Where should this go in the Brain?". It should then execute the file moves/updates based on your decision.

## 4. Verify Tooling
*   Test `search-brain.ps1` after migrating more data to ensure keyword expansion isn't needed immediately.
*   Test `update-brain.ps1` with the `-Create` switch to ensure new nodes are templated correctly.

**Current Status:**
*   Context: `2025-12-04-02-context.md` (Active)
*   Inbox: Configured to receive `update-context.ps1` dumps.
*   Brain: Contains `Projects/OTP.md`.
