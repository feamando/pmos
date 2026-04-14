---
description: Generate structured documents — PRD, ADR, RFC, PR FAQ, 4CQ
---

# /doc -- Document Generation

Parse the first argument to determine which document type to generate:

| Subcommand | Description |
|------------|-------------|
| `prd` | Product Requirements Document |
| `rfc` | Request for Comments |
| `adr` | Architecture Decision Record |
| `4cq` | Four Critical Questions analysis |
| `bc` | Business Case |
| `prfaq` | Press Release / FAQ (Amazon-style) |
| `whitepaper` | Technical or strategic whitepaper |
| `user-story` | User story with acceptance criteria |
| `meeting-prep` | Meeting preparation brief |
| `meeting-notes` | Structured meeting notes from transcript |
| `export-to-spec` | Export feature context to specification |
| `documentation` | Technical or product documentation |
| *(no args)* | Show available document types |

## Arguments
$ARGUMENTS

## No Arguments -- Show Help

If no arguments provided, display:

```
Doc -- Document Generation

  /doc prd "Feature Name"                 - Generate PRD
  /doc prd --template lean                - Use lean PRD template
  /doc rfc "Title"                        - Generate RFC
  /doc rfc --status draft                 - RFC with specific status
  /doc adr "Decision Title"              - Generate ADR
  /doc adr --status accepted              - ADR with specific status
  /doc 4cq "Topic"                        - Four Critical Questions analysis
  /doc bc "Project Name"                  - Generate Business Case
  /doc prfaq "Feature Name"              - Generate PR/FAQ
  /doc whitepaper "Topic"                 - Generate whitepaper
  /doc user-story "As a..."              - Generate user story
  /doc user-story --epic "Epic Name"      - User story within epic
  /doc meeting-prep "Meeting Title"       - Generate meeting prep
  /doc meeting-prep --attendees "a,b,c"   - With attendee Brain lookup
  /doc meeting-notes                      - Structure meeting notes
  /doc meeting-notes --transcript FILE    - From transcript file
  /doc export-to-spec                     - Export current feature to spec
  /doc export-to-spec --format confluence - Export for Confluence
  /doc documentation "Topic"              - Generate documentation
  /doc documentation --type api           - API documentation

Usage: /doc <type> [title] [options]
```

---

## prd

Generate a Product Requirements Document.

**Arguments:**
- `"title"` -- Feature or product name (required)

**Options:**

| Flag | Description |
|------|-------------|
| `--template <name>` | Template: full, lean, one-pager (default: full) |
| `--feature <slug>` | Link to existing feature workspace |
| `--inject-brain` | Auto-inject Brain context |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Load Context

If `--feature` is provided, load feature context:
```bash
python3 "$PLUGIN_ROOT/tools/feature/context_doc_generator.py" --feature "$FEATURE_SLUG" --show
```

If `--inject-brain` or feature exists, search Brain for relevant entities:
```
Use MCP tool: search_entities(query="<title>", limit=10)
```

### Step 3: Generate PRD

```bash
python3 "$PLUGIN_ROOT/tools/documents/context_doc_generator.py" prd --title "$TITLE" $ARGUMENTS
```

### Step 4: Present Results

- Generated PRD path
- Sections included
- Brain entities referenced
- Suggested reviewers (from Brain stakeholder relationships)

---

## rfc

Generate a Request for Comments document.

**Arguments:**
- `"title"` -- RFC title (required)

**Options:**

| Flag | Description |
|------|-------------|
| `--status <status>` | draft, proposed, accepted, rejected (default: draft) |
| `--feature <slug>` | Link to existing feature |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Generate RFC

```bash
python3 "$PLUGIN_ROOT/tools/documents/context_doc_generator.py" rfc --title "$TITLE" $ARGUMENTS
```

### RFC Template Structure

1. **Context** -- Problem and background
2. **Proposal** -- Recommended approach
3. **Alternatives Considered** -- Other options evaluated
4. **Trade-offs** -- Pros/cons analysis
5. **Open Questions** -- Unresolved items
6. **Decision** -- Status and rationale

---

## adr

Generate an Architecture Decision Record.

**Arguments:**
- `"title"` -- Decision title (required)

**Options:**

| Flag | Description |
|------|-------------|
| `--status <status>` | proposed, accepted, deprecated, superseded (default: proposed) |
| `--supersedes <adr-id>` | ID of ADR this supersedes |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Generate ADR

```bash
python3 "$PLUGIN_ROOT/tools/documents/context_doc_generator.py" adr --title "$TITLE" $ARGUMENTS
```

### ADR Template Structure

1. **Title** -- Short descriptive title
2. **Status** -- Proposed / Accepted / Deprecated / Superseded
3. **Context** -- Forces at play, background
4. **Decision** -- What was decided
5. **Consequences** -- Positive, negative, and neutral outcomes

---

## 4cq

Generate a Four Critical Questions analysis.

**Arguments:**
- `"topic"` -- Topic to analyze (required)

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Generate 4CQ

```bash
python3 "$PLUGIN_ROOT/tools/documents/context_doc_generator.py" 4cq --title "$TITLE" $ARGUMENTS
```

### 4CQ Framework

1. **What problem are we solving?** -- Problem statement with evidence
2. **Who are we solving it for?** -- Target users with persona detail
3. **How do we know this is a real problem?** -- Validation evidence
4. **What does success look like?** -- Measurable outcomes

---

## bc

Generate a Business Case document.

**Arguments:**
- `"title"` -- Project or initiative name (required)

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Generate Business Case

```bash
python3 "$PLUGIN_ROOT/tools/documents/context_doc_generator.py" bc --title "$TITLE" $ARGUMENTS
```

### Business Case Structure

1. **Executive Summary**
2. **Problem / Opportunity**
3. **Proposed Solution**
4. **Cost-Benefit Analysis**
5. **Risks and Mitigations**
6. **Timeline and Milestones**
7. **Recommendation**

---

## prfaq

Generate an Amazon-style Press Release / FAQ document.

**Arguments:**
- `"title"` -- Feature or product name (required)

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Generate PR/FAQ

```bash
python3 "$PLUGIN_ROOT/tools/documents/context_doc_generator.py" prfaq --title "$TITLE" $ARGUMENTS
```

### PR/FAQ Structure

**Press Release:**
1. Headline
2. Subheading (customer benefit)
3. Opening paragraph (who, what, when, where, why)
4. Problem description
5. Solution description
6. Quote from leadership
7. How it works
8. Customer quote
9. Call to action

**FAQ:**
- External FAQ (customer questions)
- Internal FAQ (stakeholder questions)

---

## whitepaper

Generate a technical or strategic whitepaper.

**Arguments:**
- `"title"` -- Whitepaper topic (required)

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Load Research Context

```bash
python3 "$PLUGIN_ROOT/tools/research/deep_research_swarm.py" --topic "$TITLE" --mode background
```

### Step 3: Generate Whitepaper

```bash
python3 "$PLUGIN_ROOT/tools/documents/context_doc_generator.py" whitepaper --title "$TITLE" $ARGUMENTS
```

---

## user-story

Generate a user story with acceptance criteria.

**Arguments:**
- `"description"` -- User story description or "As a..." format

**Options:**

| Flag | Description |
|------|-------------|
| `--epic <name>` | Parent epic |
| `--feature <slug>` | Link to feature workspace |
| `--points <n>` | Story points estimate |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Generate User Story

```bash
python3 "$PLUGIN_ROOT/tools/documents/context_doc_generator.py" user-story --title "$TITLE" $ARGUMENTS
```

### User Story Template

- **As a** [persona], **I want** [capability], **so that** [benefit]
- **Acceptance Criteria** (Given/When/Then format)
- **Edge Cases**
- **Technical Notes**
- **Dependencies**

---

## meeting-prep

Generate a meeting preparation brief.

**Arguments:**
- `"title"` -- Meeting title (required)

**Options:**

| Flag | Description |
|------|-------------|
| `--attendees "a,b,c"` | Attendee names (triggers Brain lookup) |
| `--agenda "items"` | Known agenda items |
| `--date <date>` | Meeting date |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Load Brain Context for Attendees

For each attendee, resolve Brain entities:
```
Use MCP tool: search_entities(query="<attendee_name>", entity_type="person", limit=1)
```

### Step 3: Generate Meeting Prep

```bash
python3 "$PLUGIN_ROOT/tools/documents/context_doc_generator.py" meeting-prep --title "$TITLE" $ARGUMENTS
```

### Meeting Prep Structure

1. **Meeting Context** -- Purpose, expected outcomes
2. **Attendee Profiles** -- Brain entity summaries, recent interactions
3. **Agenda with Talking Points** -- Per-item talking points and questions
4. **Pre-read Materials** -- Related Brain entities, recent decisions
5. **Goals and Success Criteria** -- What you want from this meeting

---

## meeting-notes

Generate structured meeting notes from transcript or live notes.

**Options:**

| Flag | Description |
|------|-------------|
| `--transcript <file>` | Path to transcript file |
| `--feature <slug>` | Link to feature workspace |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Process Notes

```bash
python3 "$PLUGIN_ROOT/tools/documents/context_doc_generator.py" meeting-notes $ARGUMENTS
```

### Step 3: Present Structured Output

```markdown
## [Topic] | [Date] | [Attendees]

### TL;DR
[2-3 sentence summary]

### Decisions
| Decision | Rationale | Approver |
|----------|-----------|----------|
| ... | ... | ... |

### Action Items
- [ ] **[Owner]**: [Action] (Due: [Date])

### Discussion Summary
[Per-topic summaries]

### Follow-ups
- [ ] [Deferred item or info request]
```

---

## export-to-spec

Export current feature context to a specification document.

**Options:**

| Flag | Description |
|------|-------------|
| `--format <format>` | confluence, markdown, jira (default: markdown) |
| `--feature <slug>` | Feature to export (default: current) |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Export Specification

```bash
python3 "$PLUGIN_ROOT/tools/documents/context_doc_generator.py" export-to-spec --feature "$FEATURE_SLUG" $ARGUMENTS
```

### Step 3: Present Results

- Exported spec path
- Sections included
- Format-specific notes (Confluence markup, Jira formatting)

---

## documentation

Generate technical or product documentation.

**Arguments:**
- `"topic"` -- Documentation topic (required)

**Options:**

| Flag | Description |
|------|-------------|
| `--type <type>` | api, user-guide, runbook, onboarding (default: user-guide) |
| `--audience <audience>` | engineers, pms, stakeholders (default: engineers) |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Generate Documentation

```bash
python3 "$PLUGIN_ROOT/tools/documents/context_doc_generator.py" documentation --title "$TITLE" $ARGUMENTS
```

### Step 3: Present Results

- Generated documentation path
- Table of contents
- Suggested review workflow

---

## Execute

Parse arguments and run the appropriate document generation subcommand. If arguments match multiple subcommands, prefer the most specific match.
