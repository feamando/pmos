---
description: Knowledge graph management — search, enrich, transplant entities
---

# /brain -- Knowledge Graph Management

Parse the first argument to determine which subcommand to run:

| Subcommand | Description |
|------------|-------------|
| `load` | Scan context for entity mentions and identify hot topics |
| `enrich` | Improve graph density via connector bridge enrichment |
| `search <query>` | Search Brain entities by keyword or semantic similarity |
| `query <question>` | Natural language query against the knowledge graph |
| `list [type]` | List entities with optional type/status filters |
| `cleanup` | Structural quality: orphans, stale detection, reference validation |
| `transplant <name>` | Build a pre-populated Brain package for another user |
| `synapse` | Enforce bi-directional relationships between entities |
| `analyze <type>` | Run analysis (codebase, feedback, risk, presentation, sales-call, meeting) |
| `mcp` | Manage and test the Brain MCP server |
| *(no args)* | Show available subcommands |

## Arguments
$ARGUMENTS

## No Arguments -- Show Help

If no arguments provided, display:

```
Brain -- Knowledge Graph Management

  /brain load                           - Scan context for entity mentions and hot topics
  /brain load --query "term"            - Search for specific terms
  /brain load --validate                - Check for missing Brain files
  /brain load --list-all                - List all registered entities
  /brain enrich                         - Full enrichment (connector bridge + soft edges)
  /brain enrich --quick                 - Soft edges only (fast)
  /brain enrich --report                - Analysis only, no changes
  /brain enrich --boot                  - Minimal boot-time enrichment
  /brain search <query>                 - Search entities by keyword
  /brain query "question"               - Natural language knowledge query
  /brain list                           - List all entities
  /brain list --type project --status active  - Filter by type and status
  /brain cleanup                        - Full structural cleanup pipeline
  /brain cleanup --dry-run              - Preview cleanup changes
  /brain cleanup orphans                - Find orphaned entities
  /brain cleanup stale                  - Detect stale entities
  /brain cleanup validate               - Validate references
  /brain transplant "Name"             - Start interactive transplant
  /brain transplant status              - Check in-progress transplants
  /brain transplant package "Name"     - Zip a completed transplant
  /brain synapse                        - Enforce bi-directional relationships
  /brain synapse --dry-run              - Preview relationship changes
  /brain analyze codebase <repo>        - Analyze GitHub repository
  /brain analyze feedback               - Analyze product feedback
  /brain analyze risk                   - Produce risk analysis
  /brain analyze presentation           - Analyze meeting deck
  /brain analyze sales-call             - Analyze sales call notes
  /brain analyze meeting                - Summarize meeting from transcript
  /brain mcp                            - Test Brain MCP server connectivity
  /brain mcp --cli <tool> <args>        - Run MCP tool from CLI

Usage: /brain <subcommand> [options]
```

---

## load

Scan context files for entity mentions and identify relevant Brain files to load.

**Options:**

| Flag | Description |
|------|-------------|
| `--context FILE` | Scan specific context file |
| `--query "term"` | Search for specific terms (partial match) |
| `--list-all` | List all registered entities |
| `--validate` | Check registry for missing Brain files |
| `--verbose, -v` | Show matched aliases |
| `--files-only` | Output only file paths (for scripting) |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Run Brain Loader

**Default -- scan latest context for hot topics:**
```bash
python3 "$PLUGIN_ROOT/tools/core/brain_loader.py"
```

**With options:**
```bash
# Search for specific topic
python3 "$PLUGIN_ROOT/tools/core/brain_loader.py" --query "OTP launch"

# Validate registry integrity
python3 "$PLUGIN_ROOT/tools/core/brain_loader.py" --validate

# List all entities
python3 "$PLUGIN_ROOT/tools/core/brain_loader.py" --list-all

# Get file paths only (for scripting)
python3 "$PLUGIN_ROOT/tools/core/brain_loader.py" --files-only
```

### Step 3: Present Results

- Show hot topics sorted by mention count
- List Brain files to load for deeper context
- If `--validate`: report missing files and broken references

**Use Cases:**
1. Boot sequence -- identify hot topics to load for session context
2. Search -- find Brain files related to a topic
3. Validation -- audit registry for missing files
4. Scripting -- pipe file list to other tools

---

## enrich

Improve graph density, identify gaps, and maintain relationship health. Uses the **connector bridge** pattern: request data via connectors (GDrive, Jira, Confluence, Slack, GitHub) within the Claude session, then pass results to enrichment tools.

**Modes:**

| Mode | Description | Use Case |
|------|-------------|----------|
| `--mode full` | All enrichers, apply changes | Weekly maintenance |
| `--mode quick` | Soft edges only | Quick density boost |
| `--mode report` | Analysis only, no changes | Status check |
| `--mode boot` | Minimal, fast checks | Boot-time integration |

**Options:**

| Flag | Description |
|------|-------------|
| `--quick` | Shortcut for `--mode quick` |
| `--report` | Shortcut for `--mode report` |
| `--boot` | Shortcut for `--mode boot` (minimal, fast) |
| `--dry-run` | Preview changes without applying |
| `--verbose, -v` | Show detailed progress |
| `--source <name>` | Enrich from specific source only (gdrive, jira, confluence, slack, github) |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Run Enrichment Pipeline

**Default -- full enrichment:**
```bash
python3 "$PLUGIN_ROOT/tools/enrichment/enrichment_pipeline.py" --verbose
```

**Quick mode -- soft edges only:**
```bash
python3 "$PLUGIN_ROOT/tools/enrichment/enrichment_pipeline.py" --quick
```

**Report only -- no changes:**
```bash
python3 "$PLUGIN_ROOT/tools/enrichment/enrichment_pipeline.py" --report
```

**Boot-time mode -- fast, minimal:**
```bash
python3 "$PLUGIN_ROOT/tools/enrichment/enrichment_pipeline.py" --boot
```

**Dry run -- preview changes:**
```bash
python3 "$PLUGIN_ROOT/tools/enrichment/enrichment_pipeline.py" --dry-run --verbose
```

### Step 3: Connector Bridge Enrichment (Full Mode Only)

When running full enrichment, the pipeline coordinates with available connectors:

1. **Identify enrichment targets** -- entities with low quality scores or stale data
2. **Request data via connectors** -- use available MCP connectors (GDrive, Jira, Confluence, Slack) to fetch fresh information about target entities
3. **Pass fetched data to enrichers** -- update entity metadata, relationships, and content
4. **Score quality improvement** -- compare before/after quality scores

The connector bridge runs within the Claude session context, meaning Claude orchestrates the data flow between connectors and the enrichment pipeline.

### Step 4: Individual Tools (for targeted analysis)

```bash
# Graph Health
python3 "$PLUGIN_ROOT/tools/quality/quality_scorer.py" health           # Full report
python3 "$PLUGIN_ROOT/tools/quality/quality_scorer.py" orphans          # List orphans
python3 "$PLUGIN_ROOT/tools/quality/quality_scorer.py" density          # Density only

# Soft Edge Inference
python3 "$PLUGIN_ROOT/tools/enrichment/soft_edge_inferrer.py" scan      # Preview edges
python3 "$PLUGIN_ROOT/tools/enrichment/soft_edge_inferrer.py" apply     # Apply edges

# Extraction Hints
python3 "$PLUGIN_ROOT/tools/enrichment/extraction_hints.py"                    # All hints
python3 "$PLUGIN_ROOT/tools/enrichment/extraction_hints.py" --priority high    # High priority
```

### Step 5: Present Results

Report:
- Baseline vs. post-enrichment graph health
- New edges added (soft edge inference)
- Stale relationships flagged
- Extraction hints for manual follow-up
- Quality score improvements

---

## search

Search Brain entities by keyword, content, or semantic similarity.

### Step 1: Delegate to MCP (Preferred)

If the Brain MCP server is available (registered in `.mcp.json`), use the MCP tool directly:

```
Use MCP tool: search_entities(query="<query>", entity_type="<optional_type>", limit=10)
```

The MCP tool provides keyword + semantic search across all Brain entities.

### Step 2: Fallback to CLI Search

If MCP is not available, use the CLI search tool:

```bash
python3 "$PLUGIN_ROOT/tools/index/brain_search.py" --query "<query>" --limit 10
```

**Options:**

| Flag | Description |
|------|-------------|
| `--type <entity_type>` | Filter by entity type (person, project, squad, system, etc.) |
| `--limit <n>` | Max results (default: 10) |
| `--format json` | Machine-readable output |

### Step 3: Present Results

For each match:
1. **Entity name** and type
2. **Match context** -- snippet showing why it matched
3. **Key metadata** -- status, owner, last_enriched date
4. **Relationships** -- top 3 related entities
5. **File path** -- for deep dive

---

## query

Natural language query against the knowledge graph. Returns synthesized answers with source references.

### Step 1: Delegate to MCP (Preferred)

```
Use MCP tool: query_knowledge(question="<question>")
```

### Step 2: Fallback to CLI

```bash
python3 "$PLUGIN_ROOT/tools/index/brain_search.py" --query "<question>" --mode semantic --limit 10
```

Then synthesize an answer from the top results, citing entity sources.

### Step 3: Present Answer

- Synthesized answer to the question
- Source entities referenced (with file paths)
- Confidence assessment based on entity freshness and quality scores
- Suggested follow-up queries

---

## list

List Brain entities with optional type and status filters.

### Step 1: Delegate to MCP (Preferred)

```
Use MCP tool: list_entities(entity_type="<optional_type>", status="<optional_status>", limit=50)
```

### Step 2: Fallback to CLI

```bash
python3 "$PLUGIN_ROOT/tools/index/brain_search.py" --list --type "<type>" --status "<status>" --limit 50
```

**Options:**

| Flag | Description |
|------|-------------|
| `--type <entity_type>` | Filter: person, project, squad, system, framework, decision, etc. |
| `--status <status>` | Filter: active, archived, draft, stale |
| `--limit <n>` | Max results (default: 50) |
| `--sort <field>` | Sort by: name, last_enriched, quality_score |

### Step 3: Present Results

Display as a formatted table with columns: Name, Type, Status, Quality Score, Last Enriched.

---

## cleanup

Run the Brain structural quality cleanup pipeline. Consolidates orphan analysis, stale detection, reference validation, type checking, deduplication, and normalization.

**Subcommands:**

| Subcommand | Description |
|------------|-------------|
| *(no args)* | Full cleanup pipeline (all steps) |
| `orphans` | Find entities with no incoming relationships |
| `stale` | Detect entities not enriched in > 7 days |
| `validate` | Validate references: check all relationship targets exist |
| `--dry-run` | Preview all changes without applying |
| `--step <n>` | Run only step N (1-7) |
| `--verbose` | Show detailed progress |

### Full Pipeline Steps

| Step | Name | Description |
|------|------|-------------|
| 1 | Type Check | Detect and fix `$type` mismatches vs directory/body |
| 2 | Refile | Move misplaced entities to correct typed subdirectories |
| 3 | Normalize | Canonicalize relationship targets, remove duplicates |
| 4 | Dedup | Detect and merge duplicate entities |
| 5 | Aliases | Generate aliases for entities missing them |
| 6 | Orphan Analysis | Find entities with zero incoming relationships |
| 7 | Stale Detection | Flag entities with last_enriched > 7 days |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Run Full Cleanup (default)

```bash
# Step 1: Type check
python3 "$PLUGIN_ROOT/tools/quality/entity_validator.py" type-check --fix

# Step 2: Refile misplaced entities
python3 "$PLUGIN_ROOT/tools/quality/schema_migrator.py" refile --apply

# Step 3: Normalize relationships
python3 "$PLUGIN_ROOT/tools/quality/relationship_normalizer.py" normalize --apply

# Step 4: Detect duplicates (review output before merging)
python3 "$PLUGIN_ROOT/tools/quality/dedup_detector.py" --threshold 0.95

# Step 5: Generate aliases
python3 "$PLUGIN_ROOT/tools/quality/alias_generator.py" --apply

# Step 6: Orphan analysis
python3 "$PLUGIN_ROOT/tools/quality/quality_scorer.py" orphans

# Step 7: Stale detection
python3 "$PLUGIN_ROOT/tools/quality/quality_scorer.py" stale --threshold 7d

# Rebuild index
python3 "$PLUGIN_ROOT/tools/index/brain_index_generator.py"
```

### Step 3: Run Targeted Subcommands

**Orphans only:**
```bash
python3 "$PLUGIN_ROOT/tools/quality/quality_scorer.py" orphans
```

**Stale detection only:**
```bash
python3 "$PLUGIN_ROOT/tools/quality/quality_scorer.py" stale --threshold 7d
```

**Reference validation only:**
```bash
python3 "$PLUGIN_ROOT/tools/quality/relationship_normalizer.py" validate
```

### Step 4: Dry-Run Preview

```bash
python3 "$PLUGIN_ROOT/tools/quality/entity_validator.py" type-check
python3 "$PLUGIN_ROOT/tools/quality/schema_migrator.py" refile --dry-run
python3 "$PLUGIN_ROOT/tools/quality/relationship_normalizer.py" normalize --dry-run
python3 "$PLUGIN_ROOT/tools/quality/dedup_detector.py" --threshold 0.95 --dry-run
python3 "$PLUGIN_ROOT/tools/quality/alias_generator.py" --dry-run
python3 "$PLUGIN_ROOT/tools/quality/quality_scorer.py" orphans
python3 "$PLUGIN_ROOT/tools/quality/quality_scorer.py" stale --threshold 7d
```

### Step 5: Health Check After Cleanup

```bash
python3 "$PLUGIN_ROOT/tools/quality/quality_scorer.py" summary
python3 "$PLUGIN_ROOT/tools/index/brain_index_generator.py" --stats
```

Report: entities fixed, duplicates merged, orphans found, stale count, overall quality score delta.

---

## transplant

Build a pre-populated Brain package for another user, accelerating their PM-OS onboarding from weeks to minutes.

**Arguments:**
- `<name>` -- Start interactive transplant for a user
- `status` -- Check in-progress transplants
- `package <name>` -- Zip a completed transplant for delivery

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Start Transplant

```bash
python3 "$PLUGIN_ROOT/tools/core/brain_transplant.py" start "<name>"
```

**Interactive phases:**
1. **Gather context** -- ask about the target user's role, team, key projects
2. **Build org structure** -- create entity files for their immediate org
3. **Parallel data ingestion** -- use connector bridge to pull data from GDrive, Jira, Confluence, Slack, GitHub relevant to the target user
4. **Process inbox** -- extract entities from all ingested files
5. **Create USER.md** -- build user profile from communication patterns
6. **Create config.yaml** -- set up their PM-OS configuration
7. **Package** -- zip with transplant.sh installer

### Step 3: Check Status

```bash
python3 "$PLUGIN_ROOT/tools/core/brain_transplant.py" status
```

### Step 4: Package for Delivery

```bash
python3 "$PLUGIN_ROOT/tools/core/brain_transplant.py" package "<name>"
```

**Capture philosophy:** Push for MAXIMUM capture. Breadth first, then depth. Every named entity gets created. Follow every link. The value of the Brain scales directly with completeness.

---

## synapse

Enforce bi-directional relationships between Brain entities.

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Run Synapse Builder

**Preview changes (dry-run):**
```bash
python3 "$PLUGIN_ROOT/tools/core/synapse_builder.py" --dry-run
```

**Apply changes:**
```bash
python3 "$PLUGIN_ROOT/tools/core/synapse_builder.py"
```

### Relationship Map

| Forward | Inverse |
|---------|---------|
| `owner` | `owns` |
| `member_of` | `has_member` |
| `blocked_by` | `blocks` |
| `depends_on` | `dependency_for` |
| `relates_to` | `relates_to` |
| `part_of` | `has_part` |
| `reports_to` | `manages` |
| `stakeholder_of` | `has_stakeholder` |

### When to Use
- After adding new Brain entities with relationships
- After manual edits to relationship sections
- As part of Brain maintenance workflow
- Before generating meeting preps (ensures complete context)

---

## analyze

Run structured analysis and capture findings into Brain entities.

Parse the second argument to determine analysis type:

| Type | Description |
|------|-------------|
| `codebase <repo>` | Analyze GitHub repository |
| `feedback` | Analyze product feedback |
| `risk` | Produce risk analysis |
| `presentation` | Analyze meeting deck |
| `sales-call` | Analyze sales call notes |
| `meeting` | Summarize meeting from transcript |

---

### analyze codebase

Analyze a GitHub repository and create/update its Technical Brain entry.

**Arguments:**
- `<repo>` -- GitHub repository in format `owner/repo` (e.g., `myorg/myapp`)
- `--all` -- Analyze all priority repositories

#### Step 1: Run Tech Context Sync

```bash
python3 "$PLUGIN_ROOT/tools/analysis/tech_context_sync.py" --analyze <repo>
```

If `--all`:
```bash
python3 "$PLUGIN_ROOT/tools/analysis/tech_context_sync.py" --all
```

#### Step 2: Present Results

Creates/updates `user/brain/Technical/repositories/<owner>_<repo>.md` with:
- Tech stack and language breakdown
- Key directories and architecture patterns
- CI/CD configuration
- Team ownership (from CODEOWNERS)
- Recent activity and health metrics

---

### analyze feedback

Analyze product feedback text for themes, sentiment, and priorities.

#### Step 1: Load Brain Context

```bash
python3 "$PLUGIN_ROOT/tools/analysis/pattern_adapter.py" inject "Analyze product feedback" --feature "$ARGUMENTS"
```

#### Step 2: Analyze the Feedback

The user provides feedback text. Analyze for:

- **Themes:** Recurring patterns, frequency, urgency (Critical/High/Medium/Low)
- **Sentiment:** Overall and per-theme, notable quotes
- **Priorities:** Ranked by business impact, mapped to Brain entities, new vs recurring

#### Step 3: Produce Structured Output

- Themes table with frequency and urgency
- Sentiment summary with representative quotes
- Priority matrix mapping themes to business impact
- Recommendations with next steps

#### Step 4: Capture Findings

```bash
python3 "$PLUGIN_ROOT/tools/analysis/pattern_adapter.py" extract /tmp/feedback-analysis.md --pattern analyze-feedback --feature "$ARGUMENTS" --capture
```

---

### analyze risk

Produce a risk analysis for a feature or project with risk matrix output.

#### Step 1: Load Brain Context

```bash
python3 "$PLUGIN_ROOT/tools/analysis/pattern_adapter.py" inject "Analyze risks for project" --feature "$ARGUMENTS"
```

#### Step 2: Gather Context

Read feature/project context. Check Brain for existing risk references.

#### Step 3: Identify Risks

Analyze across dimensions:
- **Technical:** Architecture complexity, integration dependencies, performance, security
- **Business:** Timeline pressure, resource constraints, market timing, stakeholder alignment
- **Operational:** Deployment complexity, monitoring gaps, rollback difficulty
- **External:** Vendor dependencies, regulatory requirements, competitive pressure

#### Step 4: Produce Risk Matrix

For each risk:
- Category (Technical/Business/Operational/External)
- Description
- Likelihood (Low/Medium/High)
- Impact (Low/Medium/High/Critical)
- Severity score (Likelihood x Impact)
- Mitigation strategy
- Owner

#### Step 5: Capture Findings

```bash
python3 "$PLUGIN_ROOT/tools/analysis/capture_agent.py" --capture research "Risk: [Name]" --finding "[Description]" --source-type internal --category risk --confidence medium
```

---

### analyze presentation

Analyze meeting deck or presentation content for key messages and discussion prep.

#### Step 1: Load Brain Context

```bash
python3 "$PLUGIN_ROOT/tools/analysis/pattern_adapter.py" inject "Analyze presentation content" --feature "$ARGUMENTS"
```

#### Step 2: Analyze the Presentation

Extract:
- **Key Messages:** Main thesis, core claims, call to action
- **Data Points:** Statistics cited, source quality assessment, data gaps
- **Questions to Ask:** Clarifying, challenging, strategic
- **Stakeholder Mapping:** Audience, decisions requested, affected parties

#### Step 3: Produce Structured Output

- Executive summary (3-5 sentences)
- Data points table with source quality ratings
- Discussion questions ranked by strategic value
- Pre-read supplement from Brain context (related entities, historical context)

#### Step 4: Capture Insights

Capture key insights for meeting prep context via the analysis capture tool.

---

### analyze sales-call

Analyze sales call or stakeholder meeting notes for customer intelligence.

#### Step 1: Load Brain Context

```bash
python3 "$PLUGIN_ROOT/tools/analysis/pattern_adapter.py" inject "Analyze sales call notes" --feature "$ARGUMENTS"
```

#### Step 2: Analyze Call Notes

Extract:
- **Customer Pain Points:** Explicit complaints, implicit workarounds, severity (Blocker/Major/Minor)
- **Feature Requests:** Specific capabilities, customer priority, roadmap mapping
- **Competitive Mentions:** Competitors named, features compared, switching risks
- **Customer Context:** Company size, industry, usage patterns
- **Sentiment Signals:** Relationship health, satisfaction indicators, churn risk

#### Step 3: Produce Structured Output

- Customer profile summary
- Pain points table with severity ratings
- Feature requests mapped to roadmap items (via Brain entities)
- Competitive intelligence matrix
- Sentiment assessment with recommended actions

#### Step 4: Capture Competitive Intelligence

```bash
python3 "$PLUGIN_ROOT/tools/analysis/capture_agent.py" --capture research "Sales Call: [Customer] - [Finding]" --finding "[Insight]" --source-type internal --category competitive --confidence medium
```

---

### analyze meeting

Produce a structured meeting summary from transcript or notes.

#### Step 1: Load Brain Context

```bash
python3 "$PLUGIN_ROOT/tools/analysis/pattern_adapter.py" inject "Summarize meeting notes" --feature "$ARGUMENTS"
```

#### Step 2: Process Meeting Content

Extract:
- **Attendees:** Map to Brain entities where possible (`[[Person_Name]]`)
- **Decisions Made:** Explicit decisions with rationale, approver, alternatives discussed
- **Action Items:** Tasks assigned with owner, due date, dependencies
- **Discussion Topics:** Summary per topic, key points, open questions
- **Follow-ups Required:** Deferred items, info requests, escalations

#### Step 3: Produce Structured Output

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

#### Step 4: Capture via Analysis Tools

For each decision:
```bash
python3 "$PLUGIN_ROOT/tools/analysis/capture_agent.py" --capture decision "[Title]" --choice "[What]" --rationale "[Why]"
```

For each action item:
```bash
python3 "$PLUGIN_ROOT/tools/analysis/capture_agent.py" --capture action "[Description]" --owner "[Person]"
```

---

## mcp

Manage and test the Brain MCP server, which exposes the knowledge graph via MCP protocol.

The Brain MCP server is **pre-configured** in `.mcp.json` at the project root. Claude Code starts it automatically -- the following tools are available in every conversation:
- `search_entities(query, entity_type, limit)`
- `get_entity(entity_id)`
- `query_knowledge(question)`
- `get_relationships(entity_id)`
- `list_entities(entity_type, status, limit)`

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
export PM_OS_BRAIN_PATH="${PM_OS_USER}/brain"
```

### Step 2: Test Connectivity

```bash
python3 "$PLUGIN_ROOT/tools/mcp/brain_mcp_server.py" --cli search_entities "checkout" --limit 5
```

If the test fails with an import error:
```bash
pip3 install "mcp>=0.1.0"
```

### Step 3: CLI Mode (for testing or scripting)

```bash
python3 "$PLUGIN_ROOT/tools/mcp/brain_mcp_server.py" --cli search_entities "checkout optimization"
python3 "$PLUGIN_ROOT/tools/mcp/brain_mcp_server.py" --cli get_entity "entity/project/good-chop"
python3 "$PLUGIN_ROOT/tools/mcp/brain_mcp_server.py" --cli query_knowledge "What systems handle payment processing?"
python3 "$PLUGIN_ROOT/tools/mcp/brain_mcp_server.py" --cli list_entities --type project --status active --limit 10
```

### Brain Path Resolution

The server resolves the brain path via:
1. `PM_OS_BRAIN_PATH` env var (if set)
2. `PM_OS_USER/brain` (if `PM_OS_USER` is set)
3. Config loader root resolution -> `{root}/user/brain`
4. Fallback: `{cwd}/user/brain`

---

## Execute

Parse arguments and run the appropriate Brain subcommand. If arguments match multiple subcommands, prefer the most specific match.
