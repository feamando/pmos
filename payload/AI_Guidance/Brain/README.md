# AI Brain: The Semantic Knowledge Graph

This directory serves as the **Semantic Memory** for the AI Agent. Unlike the `Core_Context` folder, which captures chronological events ("Episodic Memory"), the `Brain` folder captures **state, facts, and enduring knowledge**.

## Philosophy
*   **Markdown is the Database:** All knowledge is stored in structured Markdown files.
*   **Entity-Oriented:** Files are organized by what they *are* (Project, Team, Decision), not when they happened.
*   **Living Documents:** These files are meant to be updated, refined, and refactored over time.

## Directory Structure

### 1. `/Projects`
Long-running initiatives with defined goals, roadmaps, and statuses.
*   *Example:* `OTP.md`, `Good_Chop.md`
*   *Content:* Executive summary, milestones, blockers, key stakeholders.

### 2. `/Entities`
People, Teams, and external Companies.
*   *Example:* `Nikita_Gorshkov.md`, `Team_Payments.md`
*   *Content:* Roles, responsibilities, contact info, key relationships.

### 3. `/Architecture`
Technical systems, data flows, and platform documentation.
*   *Example:* `SCM_Integration.md`, `Billing_Flow.md`
*   *Content:* Diagrams (Mermaid), API specs, dependency maps.

### 4. `/Decisions`
Architectural Decision Records (ADRs) and strategic pivots.
*   *Example:* `ADR-001-Cart-Consolidation.md`
*   *Content:* Context, Decision, Consequences, Status (Accepted/Deprecated).

### 5. `/Inbox`
Transient storage for raw data dumps from `daily_context_updater.py`.
*   *Status:* Temporary. Files here should be processed into Semantic files and then archived/deleted.

### 6. `/Episodic`
Archive of chronological context files (`YYYY-MM-DD-context.md`).
*   *Status:* Read-Only / Append-Only. Used for historical lookups ("What happened last Tuesday?").

## Entity Registry (`registry.yaml`)

The central index mapping entities to their Brain files with aliases for flexible lookup.

```yaml
projects:
  otp:
    file: Projects/OTP.md
    aliases: ["OTP", "One-Time-Purchase", "one-time purchase"]
```

**Benefits:**
- Single source of truth for entity locations
- Alias support enables fuzzy matching (e.g., "Sameer" → `Entities/Sameer_Doda.md`)
- Machine-readable for tooling (`brain_loader.py`)

## Workflow (The "Gardener" Cycle)
1.  **Ingest:** New information arrives in `Inbox` or via User Chat.
2.  **Identify:** Run `brain_loader.py` to find which Brain files are relevant ("hot topics").
3.  **Refine:** Agent updates the relevant Semantic file (e.g., updating a Project status in `Projects/OTP.md`).
4.  **Retrieve:** Agent searches the `Brain` to answer user queries using keyword expansion and semantic mapping.

## Relationship Schema (The Synapses)

To create a dense, navigable knowledge graph, all Brain files support a `relationships` block in their YAML frontmatter.

### Supported Types

| Forward Relationship | Inverse Relationship | Usage |
|----------------------|----------------------|-------|
| `owner` | `owns` | Person -> Project/Domain |
| `member_of` | `has_member` | Person -> Team |
| `blocked_by` | `blocks` | Project -> Project/Issue |
| `depends_on` | `dependency_for` | Project -> Project |
| `relates_to` | `relates_to` | Generic connection |
| `part_of` | `has_part` | Sub-component -> System |

### Format

Use Wiki-links (`[[path/to/file]]`) for all values to ensure clicked navigation works in editors.

```yaml
---
aliases: ['OTP']
relationships:
  owner:
    - "[[Entities/Nikita_Gorshkov]]"
  blocked_by:
    - "[[Projects/Logistics_Upgrade]]"
  relates_to:
    - "[[Architecture/OWL]]"
---
```

## Tools

- **`AI_Guidance/Tools/brain_loader.py`** - Scans context files for entity mentions, identifies relevant Brain files to load.
  ```bash
  python3 AI_Guidance/Tools/brain_loader.py              # Scan latest context
  python3 AI_Guidance/Tools/brain_loader.py --query "OTP" # Search specific terms
  python3 AI_Guidance/Tools/brain_loader.py --list-all   # List all registered entities
  ```
