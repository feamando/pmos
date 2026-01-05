# AI Agent Operation Guide

## 0. Agent Reasoning and Planning Principles

You are a very strong reasoner and planner. Use these critical instructions to structure your plans, thoughts, and responses.

Before taking any action (either, tool calls *or*, responses to the user), you must proactively, methodically, and independently plan and reason about:

1) Logical dependencies and constraints: Analyze the intended action against the following factors. Resolve conflicts in order of importance:
* 1.1) Policy-based rules, mandatory prerequisites, and constraints.
* 1.2) Order of operations: Ensure taking an action does not prevent a subsequent necessary action.
    * 1.2.1) The user may request actions in a random order, but you may need to reorder operations to maximize successful completion of the task.
    * 1.3) Other prerequisite information and/or actions needed.
    * 1.4) Explicit user constraints or preferences.

2) Risk assessment: What are the consequences of taking the action? Will the new state cause any future issues?
* 2.1) For exploratory tasks (like searches), missing 'optional' parameters is a LOW risk. **Prefer calling the tool with the available information over asking the user, unless** your 'Rule 1' (Logical Dependencies) reasoning determines that optional information is required for a later step in your plan.

3) Abductive reasoning and hypothesis exploration: At each step, identify the most logical and likely reason for any gap you encountered.
* 3.1) Look beyond immediate or obvious causes. The most likely reason may not be the simplest and may require deeper inference.
* 3.2) Hypotheses may require additional research. Each hypothesis may take multiple steps to test.
* 3.3) Prioritize hypotheses based on likelihood, but do not discard less likely ones prematurely. A low-probability event may still be the root cause.

4) Outcome evaluation and adaptability: Does the previous observation require any changes to your plan?
* 4.1) If your initial hypotheses are disproven, actively generate new ones based on the gathered information.

5) Information availability: Incorporate all applicable and alternative sources of information, including:
* 5.1) Using available tools and their capabilities
* 5.2) All policies, rules, checklists, and constraints
* 5.3) Previous observations and conversation history
* 5.4) Information only available by asking the user

6) Precision and grounding: Ensure your reasoning is extremely precise and relevant to each exact ongoing situation.
* 6.1) Verify your claims by quoting the exact applicable information (including policies) when referring to them.

7) Completeness: Ensure that all requirements, constraints, options, and preferences are exhaustively incorporated into your plan.
* 7.1) Resolve conflicts using the order of importance in #1.
* 7.2) Avoid premature conclusions: There may be multiple relevant options for a given situation.
    * 7.2.1) To check for whether an option is relevant, reason about all information sources from #5.
    * 7.2.2) You may need to consult the user to even know whether something is applicable. Do not assume it is not applicable without checking.
* 7.3) Review applicable sources of information from #5 to confirm which are relevant to the current state.

8) Persistence and patience: Do not give up unless all the reasoning above is exhausted.
* 8.1) Don't be dissuaded by time taken or user frustration.
* 8.2) This persistence must be intelligent: On transient errors (e.g. please try again) you **must** retry **unless an explicit retry limit (e.g., max $x$ tries) has been reached**. If such a limit is hit: You **must** stop. On "other" errors, you must change your strategy or arguments, not repeat the same failing call.

9) Inhibit your response: only take an action after all the above reasoning is completed. Once you've taken an action, you cannot take it back.

## 1. Context & Architecture (The "What")
This repository replaces Google Drive/Notion with a **Git-backed, CLI-managed filesystem**.
- **Stack:** Markdown files, Git for version control, CLI agents (Gemini, other compatible agents).
- **Core Structure:**
    - `AI_Guidance/`: **START HERE.** Contains Rules, Templates (`Frameworks/`), and Business Context (`Core_Context/`).
    - `Products/`: The source of truth for all product work. Organized by `Product > Project`.
    - `Team/`: 1:1s, feedback, and recruiting.
    - `Reporting/` & `Planning/`: Temporal cycles (Weekly, Monthly, Quarterly, Annual).

## 2. Operational Workflows (The "How")

### 🔍 Discovery
- **Before answering:** Search `AI_Guidance/Core_Context` for definitions and `Products/` for existing work.
- **Tools:** Use `glob` to find files, `grep` (or equivalent) to search content.
- **GDocs Fallback:** If a requested file/document is missing locally:
    1.  Search Google Drive using: `python AI_Guidance/Tools/gdrive_mcp/server.py --cli search "name contains 'query'"`
    2.  If found, read content using: `python AI_Guidance/Tools/gdrive_mcp/server.py --cli read <FILE_ID>`
    3.  *Note: Requires `token.json` in `AI_Guidance/Tools/gdrive_mcp/`.*
- **Jira & Confluence:** 
    -   **Tickets:** If a ticket key (e.g., `PROJ-123`) is mentioned, fetch details: `python AI_Guidance/Tools/jira_mcp/server.py --cli get_issue PROJ-123`.
    -   **Blockers:** To find active blockers: `python AI_Guidance/Tools/jira_mcp/server.py --cli search_issues "priority = High AND status != Done"`.
    -   **Pages:** To search wiki context: `python AI_Guidance/Tools/jira_mcp/server.py --cli search_pages "text ~ 'roadmap'"`.

### 📝 Document Creation
- **Templates:** NEVER create a blank file. Check `AI_Guidance/Frameworks` for:
    - `PRD_Template.md`
    - `Decision_Log_Template.md`
    - `Meeting_Notes_Template.md`
- **Naming:**
    - **Dated:** `YYYY-MM-DD-topic-name.md` (e.g., `2025-10-21-steerco-notes.md`)
    - **Living:** `kebab-case-descriptive.md` (e.g., `roadmap.md`, `api-specs.md`)

### ðŸ”„ Document Updates                                                    
- **Append over Overwrite:** For logs (Decisions, Meetings), add new entries 
to the top (reverse chronological) or bottom (chronological) consistently.   
- **Linkage:** When creating a new doc, link it in the parent folder's `READM
E.md`.                                                                       

### Ã°Å¸â€â€ž Context Update Workflow
1. Run `./update-context.ps1` to fetch the latest raw data.
2. **IMMEDIATELY** read the generated `AI_Guidance/Core_Context/YYYY-MM-DD-context.md`.
3. Synthesize the raw data into a structured summary at the top of that file using `gemini-3-pro-preview`.
4. **Format:**
   - **Header:** `# Daily Context: YYYY-MM-DD`
   - **Sections:** `## 🚨 Critical Alerts`, `## 🧠 Key Decisions & Updates`, `## 📅 Meeting & Schedule Notes`, `## 📉 Market & Competitor Intel`.
   - **Style:** NGO bullets (Direct, Metric-heavy).
   - **Action:** Remove the raw data dump after synthesis or move it to a `raw/` archive if configured (default: overwrite active file with summary).

## 3. Style & Quality Standards
- **Format:** Standard GitHub Flavored Markdown.
- **Brevity:** Use bullet points and bold text for skimmability.
- **Tone:** Professional, objective, "Amazon 6-pager" style.
- **Filesystem Hygiene:**
    - No spaces in filenames.
    - No loose files in root `Products/` folders; always nest in a subfolder if it's a project.

## 4. Commands & Tools
- **Google Drive Integration:**
    - **Usage:** Use the custom MCP server located at `AI_Guidance/Tools/gdrive_mcp/server.py`.
    - **Config:** See `AI_Guidance/mcp_client_config.json` for client setup.
    - **CLI Mode:** Run `python AI_Guidance/Tools/gdrive_mcp/server.py --cli <command>` (list, search, read) to access Drive directly from the terminal without full MCP setup.
- **Refactoring:** When asked to "organize", move files to their deepest logical parent.
- **Validation:** Periodically check for orphan files using `find . -maxdepth 2 -type f`.

## 5. Progressive Disclosure
For specific sub-area rules, refer to:
- `AI_Guidance/Rules/REPORTING_RULES.md` (Future)
- `AI_Guidance/Rules/PLANNING_RULES.md` (Future)

## 6. Persona & Style Guide
For detailed instructions on writing style, tone, preferred vocabulary, and operational workflow patterns (e.g., how to structure meeting notes, performance reports, and strategic documents), refer to: `AI_Guidance/Rules/NGO.md`.

## 7. AI-Generated Content Disclaimer
For ALL documents generated by agents and models, add the following line at the bottom of the document:
`Automatically generated by [[model ID]] on [[timestamp]]`

## 8. FPF (First Principles Framework) - Structured Reasoning

This repository integrates **Quint Code** for structured reasoning using the First Principles Framework (FPF).

### When to Use FPF

**Use FPF for:**
- Architectural decisions with long-term consequences
- Multiple viable approaches requiring systematic evaluation
- Decisions needing an auditable reasoning trail
- Building up project knowledge over time

**Skip FPF for:**
- Quick fixes with obvious solutions
- Easily reversible decisions
- Time-critical situations where overhead isn't justified

### FPF Commands (Gemini CLI)

Use these commands (defined in `.gemini/commands/`) to drive the reasoning cycle:

| Command | Phase | Action |
|---------|-------|--------|
| `q0-init` | Setup | Initialize `.quint/` and bounded context |
| `q1-hypothesize` | Abduction | Generate competing hypotheses -> `L0/` |
| `q2-verify` | Deduction | Logical verification -> `L1/` |
| `q3-validate` | Induction | Empirical testing -> `L2/` |
| `q4-audit` | Audit | Calculate trust scores (WLNK) |
| `q5-decide` | Decision | Create Design Rationale Record (DRR) |
| `q-status` | Utility | Show current state |
| `q-sync` | Sync | Synchronize reasoning with Brain |

**Implementation Note:**
These commands utilize the Python bridge at `AI_Guidance/Tools/gemini_quint_bridge.py`.

### FPF Glossary

**Knowledge Layers (Epistemic Status):**

| Layer | Name | Meaning |
|-------|------|---------|
| **L0** | Conjecture | Unverified hypothesis |
| **L1** | Substantiated | Logically verified |
| **L2** | Corroborated | Empirically validated |
| **Invalid** | Falsified | Failed verification (kept for learning) |

**Core Concepts:**

- **WLNK (Weakest Link):** `R_eff = min(evidence)`, never average. A chain is only as strong as its weakest link.
- **CL (Congruence Level):** How well external evidence matches our context:
  - CL3: Same context (internal test) — no penalty
  - CL2: Similar context (related project) — minor penalty
  - CL1: Different context (external docs) — significant penalty
- **DRR (Design Rationale Record):** Persisted decision with context, rationale, and consequences.
- **R_eff (Effective Reliability):** Computed trust score (0-1), never estimated.
- **Transformer Mandate:** AI generates options; human decides. Autonomous architectural decisions = protocol violation.

**State Machine:**
```
IDLE → ABDUCTION → DEDUCTION → INDUCTION → DECISION → IDLE
       (q1)         (q2)         (q3)        (q4→q5)
```

### Storage Locations

- `.quint/` — Quint Code knowledge base (local)
- `Brain/Reasoning/Decisions/` — DRRs synced to Brain
- `Brain/Reasoning/Hypotheses/` — Historical claims at L0/L1/L2
- `Brain/Reasoning/Evidence/` — Evidence archive with expiry tracking

### Brain Integration

Run `/quint-sync` to synchronize between `.quint/` and `Brain/Reasoning/`.
