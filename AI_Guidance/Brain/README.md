# AI Brain: The Semantic Knowledge Graph

This directory serves as the **Semantic Memory** for the AI Agent. Unlike chronological context files, the `Brain` folder captures **state, facts, and enduring knowledge**.

## Philosophy
- **Markdown is the Database:** All knowledge is stored in structured Markdown files.
- **Entity-Oriented:** Files are organized by what they *are* (Project, Team, Decision), not when they happened.
- **Living Documents:** These files are meant to be updated, refined, and refactored over time.

## Directory Structure

### 1. `/Projects`
Long-running initiatives with defined goals, roadmaps, and statuses.
- *Example:* `OTP.md`, `Mobile_App.md`
- *Content:* Executive summary, milestones, blockers, key stakeholders.

### 2. `/Entities`
People, Teams, Squads, and external Companies.
- *Example:* `Squad_Engineering.md`, `Team_Product.md`
- *Content:* Roles, responsibilities, contact info, key relationships.

### 3. `/Architecture`
Technical systems, data flows, and platform documentation.
- *Example:* `API_Gateway.md`, `Billing_Flow.md`
- *Content:* Diagrams (Mermaid), API specs, dependency maps.

### 4. `/Decisions`
Architectural Decision Records (ADRs) and strategic pivots.
- *Example:* `ADR-001-Database-Choice.md`
- *Content:* Context, Decision, Consequences, Status (Accepted/Deprecated).

### 5. `/Inbox`
Transient storage for raw data dumps from sync tools.
- *Status:* Temporary. Files here should be processed into Semantic files and then archived/deleted.

### 6. `/GitHub`
GitHub activity tracking (PRs, commits) per squad/project.
- *Content:* `PR_Activity.md`, `Recent_Commits.md`

## Workflow (The "Gardener" Cycle)
1. **Ingest:** New information arrives in `Inbox` or via User Chat.
2. **Identify:** Run `brain_loader.py` to find which Brain files are relevant ("hot topics").
3. **Refine:** Agent updates the relevant Semantic file.
4. **Retrieve:** Agent searches the `Brain` to answer user queries.

## Tools

- **`brain_loader.py`** - Scans context files for entity mentions
  ```bash
  python3 AI_Guidance/Tools/brain_loader.py              # Scan latest context
  python3 AI_Guidance/Tools/brain_loader.py --query "OTP" # Search specific terms
  ```

- **`jira_brain_sync.py`** - Syncs Jira data to Brain
  ```bash
  python3 AI_Guidance/Tools/jira_brain_sync.py
  ```

- **`github_brain_sync.py`** - Syncs GitHub activity to Brain
  ```bash
  python3 AI_Guidance/Tools/github_brain_sync.py
  ```
