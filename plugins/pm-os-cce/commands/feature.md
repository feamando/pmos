---
description: Feature lifecycle — start, check, validate, resume features
---

# /feature -- Feature Lifecycle Management

Parse the first argument to determine which subcommand to run:

| Subcommand | Description |
|------------|-------------|
| `start "name"` | Create feature workspace with Cowork project structure |
| `resume` | Resume feature work from saved state |
| `status` | Show feature status and current phase |
| `validate` | Validate current phase completion criteria |
| `gate` | Check phase completion evidence for gate review |
| `outputs` | List feature outputs and artifacts |
| `context` | Show or update feature context |
| `prototype` | Generate prototype (delegates to Spec Machine if available) |
| `prototype-update` | Update or version existing prototype (requires Spec Machine) |
| `prototype-verify` | Run quality checks on prototype (requires Spec Machine) |
| `prototype-preflight` | Check Spec Machine prerequisites |
| *(no args)* | Show available subcommands |

## Arguments
$ARGUMENTS

## No Arguments -- Show Help

If no arguments provided, display:

```
Feature -- Feature Lifecycle Management

  /feature start "Feature Name"           - Create feature workspace
  /feature start "Name" --phase discovery - Start at specific phase
  /feature resume                         - Resume current feature work
  /feature resume --list                  - List all features with saved state
  /feature status                         - Show current feature status
  /feature status --all                   - Show all features
  /feature validate                       - Validate current phase
  /feature validate --phase definition    - Validate specific phase
  /feature gate                           - Run phase gate review
  /feature gate --phase discovery         - Gate review for specific phase
  /feature outputs                        - List feature artifacts
  /feature outputs --phase design         - Artifacts for specific phase
  /feature context                        - Show feature context
  /feature context --update               - Update feature context
  /feature context --inject "topic"       - Inject topic into context
  /feature prototype                      - Generate prototype (Spec Machine or internal)
  /feature prototype --fidelity high      - High-fidelity (strict threshold)
  /feature prototype --fidelity low       - Low-fidelity (freeform threshold)
  /feature prototype-update "changes"     - Update existing prototype
  /feature prototype-update --version     - Create new prototype version
  /feature prototype-verify               - Run quality checks on prototype
  /feature prototype-preflight            - Verify Spec Machine prerequisites

Usage: /feature <subcommand> [options]
```

---

## start

Create a new feature workspace with Cowork project structure and phase tracking.

**Arguments:**
- `"name"` -- Feature name (required)

**Options:**

| Flag | Description |
|------|-------------|
| `--phase <phase>` | Start at specific phase (default: discovery) |
| `--template <name>` | Use specific template |
| `--verbose, -v` | Show detailed setup progress |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Create Feature Workspace

```bash
python3 "$PLUGIN_ROOT/tools/feature/feature_engine.py" start "$ARGUMENTS"
```

This creates:
- Feature directory under `user/features/<feature-slug>/`
- Phase tracking file (`feature-state.yaml`)
- Context document with Brain entity injection
- Initial phase workspace (discovery by default)

### Step 3: Load Brain Context

Inject relevant Brain entities into the feature context:

```bash
python3 "$PLUGIN_ROOT/tools/feature/context_doc_generator.py" --feature "$FEATURE_SLUG" --inject
```

### Step 4: Present Results

- Feature workspace path
- Current phase and next steps
- Loaded Brain context summary
- Suggested first actions for the phase

---

## resume

Resume feature work from saved state.

**Options:**

| Flag | Description |
|------|-------------|
| `--list` | List all features with saved state |
| `--feature <slug>` | Resume specific feature (default: most recent) |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Load Feature State

```bash
python3 "$PLUGIN_ROOT/tools/feature/feature_state.py" load --feature "$FEATURE_SLUG"
```

### Step 3: Restore Context

```bash
python3 "$PLUGIN_ROOT/tools/feature/context_doc_generator.py" --feature "$FEATURE_SLUG" --restore
```

### Step 4: Present Results

- Current phase and progress
- Outstanding items from last session
- Brain context updates since last session
- Suggested next actions

---

## status

Show feature status and current phase.

**Options:**

| Flag | Description |
|------|-------------|
| `--all` | Show all features |
| `--feature <slug>` | Status for specific feature |
| `--verbose, -v` | Include phase details |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Query Feature State

```bash
python3 "$PLUGIN_ROOT/tools/feature/feature_state.py" status $ARGUMENTS
```

### Step 3: Present Results

Display feature status table:

| Field | Value |
|-------|-------|
| Feature | Name |
| Phase | Discovery / Definition / Design / Delivery / Data |
| Progress | Percentage and checklist |
| Last Activity | Timestamp |
| Artifacts | Count per phase |
| Blockers | Any identified blockers |

---

## validate

Validate current phase completion criteria.

**Options:**

| Flag | Description |
|------|-------------|
| `--phase <phase>` | Validate specific phase (default: current) |
| `--strict` | Require all criteria met |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Run Validation

```bash
python3 "$PLUGIN_ROOT/tools/feature/feature_engine.py" validate --feature "$FEATURE_SLUG" $ARGUMENTS
```

### Step 3: Present Results

For each criterion:
- Status (pass/fail/warning)
- Evidence (artifact or finding that satisfies the criterion)
- Gaps (what's missing)

---

## gate

Check phase completion evidence for gate review. Determines if a feature is ready to advance to the next phase.

**Options:**

| Flag | Description |
|------|-------------|
| `--phase <phase>` | Gate review for specific phase (default: current) |
| `--advance` | Advance to next phase if gate passes |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Run Gate Review

```bash
python3 "$PLUGIN_ROOT/tools/feature/feature_engine.py" gate --feature "$FEATURE_SLUG" $ARGUMENTS
```

### Phase Gate Criteria

| Phase | Required Evidence |
|-------|-------------------|
| Discovery | Problem statement, user research, opportunity sizing |
| Definition | PRD, success metrics, technical feasibility |
| Design | Wireframes/prototype, technical design, edge cases |
| Delivery | Implementation complete, tests passing, rollout plan |
| Data | Metrics collected, hypothesis validated, learnings captured |

### Step 3: Present Results

- Gate verdict: PASS / FAIL / CONDITIONAL
- Evidence summary per criterion
- Missing items with suggested actions
- If `--advance` and gate passes: update phase

---

## outputs

List feature outputs and artifacts.

**Options:**

| Flag | Description |
|------|-------------|
| `--phase <phase>` | Artifacts for specific phase |
| `--format json` | Machine-readable output |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: List Outputs

```bash
python3 "$PLUGIN_ROOT/tools/feature/feature_engine.py" outputs --feature "$FEATURE_SLUG" $ARGUMENTS
```

### Step 3: Present Results

Display artifacts table with: Name, Type, Phase, Created, Path.

---

## context

Show or update feature context, including injected Brain entities and research findings.

**Options:**

| Flag | Description |
|------|-------------|
| `--update` | Refresh context from Brain |
| `--inject "topic"` | Inject specific topic |
| `--export` | Export context as markdown |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Manage Context

**Show context:**
```bash
python3 "$PLUGIN_ROOT/tools/feature/context_doc_generator.py" --feature "$FEATURE_SLUG" --show
```

**Update from Brain:**
```bash
python3 "$PLUGIN_ROOT/tools/feature/context_doc_generator.py" --feature "$FEATURE_SLUG" --update
```

**Inject topic:**
```bash
python3 "$PLUGIN_ROOT/tools/feature/context_doc_generator.py" --feature "$FEATURE_SLUG" --inject "$TOPIC"
```

### Step 3: Present Results

- Feature context summary
- Injected Brain entities with relevance scores
- Research findings linked to feature
- Last updated timestamp

---

## prototype

Generate a prototype for the current feature. Delegates to Spec Machine (`/create-prototype`) when available, producing production-quality output with real Zest design tokens, CDN images, and device chrome. Falls back to the internal prototype engine if Spec Machine commands are not synced.

**Options:**

| Flag | Description |
|------|-------------|
| `--fidelity <level>` | low (freeform), medium (balanced), high (strict). Default: medium |
| `--format <format>` | Output format: html, figma, markdown. Default: html |
| `--feature <slug>` | Feature to prototype. Default: current |
| `--platform <platform>` | web or mobile. Default: auto-detected from context |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Load Feature Context

```bash
python3 "$PLUGIN_ROOT/tools/feature/context_doc_generator.py" --feature "$FEATURE_SLUG" --show
```

Read the context document content for use in later steps.

### Step 3: Check Spec Machine Availability

**3a. Check if `/create-prototype` is available as a skill:**
The `/create-prototype` command is available when specx-ux commands have been synced to `.claude/commands/`. Check if it appears in the system-reminder's available skills list.

**3b. Filesystem and config check:**
```bash
python3 "$PLUGIN_ROOT/tools/prototype/specx_bridge.py" --check
```

**Routing logic:**
- If config `prototype.provider` is `"internal"`, go to Step 4b (internal engine).
- If `/create-prototype` IS available as a skill, go to Step 4a (Spec Machine).
- If `/create-prototype` is NOT available but the plugin exists on disk (specx_bridge --check shows `available: true`), **auto-sync** the commands and then proceed to Step 4a:
  ```bash
  python3 "$PM_OS_ROOT/v5/plugins/pm-os-dev/tools/dev_util/command_sync.py" -q
  ```
  This syncs specx-ux commands into `.claude/commands/` so they become available immediately. Then invoke `/create-prototype` via the Skill tool as normal.
- Otherwise, go to Step 4b (internal engine) with notice: "Using internal prototype engine (basic fidelity). For production-quality prototypes with Zest tokens, install specx-ux."

### Step 4a: Generate Prototype via Spec Machine

**Translate context to get output path and parameters:**
```bash
python3 "$PLUGIN_ROOT/tools/prototype/specx_bridge.py" --translate \
  --feature "$FEATURE_SLUG" \
  --product-id "$PRODUCT_ID" \
  --fidelity "$FIDELITY" \
  --platform "$PLATFORM" \
  --locale "$LOCALE" \
  --context-file "$CONTEXT_FILE_PATH"
```

This outputs a JSON blob with the output_path and source description.

**Invoke `/create-prototype` via the Skill tool:**
Use the Skill tool to invoke the spec-machine command directly:

```
Skill(skill="create-prototype", args="<output_path> <source_description_or_figma_url>")
```

The `/create-prototype` command handles everything internally:
- Preflight checks (repos, yarn, Figma MCP)
- Interactive platform and threshold selection
- Brand and locale context gathering
- Internal delegation to its prototype-creator agent
- Metadata generation (`prototype-metadata/source.json`)
- Quality validation (25+ Zest tokens, 800+ lines, real images)

**Link outputs to feature lifecycle:**
After `/create-prototype` completes, link the output back to the feature:
```bash
python3 "$PLUGIN_ROOT/tools/prototype/specx_bridge.py" --link \
  --feature "$FEATURE_SLUG" \
  --path "$PROTOTYPE_OUTPUT_PATH"
```

This updates `feature-state.yaml`, the context document, and optionally the Brain entity.

### Step 4b: Generate Prototype via Internal Engine (Fallback)

```bash
python3 "$PLUGIN_ROOT/tools/prototype/prototype_engine.py" --feature "$FEATURE_SLUG" $ARGUMENTS
```

This runs the existing CCE prototype pipeline (basic fidelity).

### Step 5: Optional Verification

If Spec Machine was used (Step 4a) and `/verify-prototype` is available as a skill, ask the user:

> "Run quality verification on the prototype? This checks accessibility, Zest compliance, UX writing, and copy. [Y/n]"

If yes, invoke via Skill tool:
```
Skill(skill="verify-prototype", args="<prototype_path>")
```

### Step 6: Present Results

- Prototype output path
- Provider used: "Spec Machine (specx-ux)" or "Internal Engine"
- Preview summary (screens, flows, component count)
- If Spec Machine: threshold level, brand, Zest token count, verification status
- If Internal: note that higher-fidelity prototyping is available with Spec Machine
- Design assumptions and suggested review questions

---

## prototype-update

Update or version an existing prototype. Requires Spec Machine (specx-ux).

**Options:**

| Flag | Description |
|------|-------------|
| `"changes"` | Description of changes to apply (in-place update) |
| `--version` | Create a new version (v2, v3, etc.) alongside the original |
| `--transform <threshold>` | Create a copy at a different threshold (e.g. freeform to strict) |
| `--feature <slug>` | Feature to update. Default: current |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Check Spec Machine Availability

Check if `/update-prototype` is available as a skill (in the system-reminder skills list). If not, **STOP** with message:

> "prototype-update requires Spec Machine (specx-ux). Run `/sync-commands` to sync marketplace commands, or install specx-ux."

### Step 3: Load Existing Prototype Path

Read `feature-state.yaml` for the feature and extract `artifacts.prototype.path`. If no prototype exists, **STOP** with message:

> "No prototype found for this feature. Run `/feature prototype` first."

### Step 4: Invoke `/update-prototype` via Skill tool

Determine update mode from arguments:
- If `"changes"` text provided: **update mode** (in-place changes)
- If `--version` flag: **version mode** (creates v2/v3 alongside original)
- If `--transform <threshold>`: **transform mode** (creates copy at different threshold)

```
Skill(skill="update-prototype", args="<prototype_path> <changes_or_flags>")
```

### Step 5: Link Updated Outputs

```bash
python3 "$PLUGIN_ROOT/tools/prototype/specx_bridge.py" --link \
  --feature "$FEATURE_SLUG" \
  --path "$UPDATED_PROTOTYPE_PATH"
```

### Step 6: Present Results

- Updated prototype path (or new version path)
- Changes applied summary
- Updated component/screen counts

---

## prototype-verify

Run quality checks on an existing prototype. Requires Spec Machine (specx-ux).

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Check Spec Machine Availability

Check if `/verify-prototype` is available as a skill. If not, **STOP** with message:

> "prototype-verify requires Spec Machine (specx-ux). Run `/sync-commands` to sync marketplace commands, or install specx-ux."

### Step 3: Load Existing Prototype Path

Read `feature-state.yaml` for the feature and extract `artifacts.prototype.path`. If no prototype exists, **STOP**.

### Step 4: Invoke `/verify-prototype` via Skill tool

```
Skill(skill="verify-prototype", args="<prototype_path>")
```

The `/verify-prototype` command internally runs:
1. Accessibility (WCAG 2.2 AA) compliance
2. Zest design system token and component coverage
3. UX writing quality against your organization's standards (configurable in USER.md)
4. Copy accessibility (POUR principles, inclusive language)

### Step 5: Present Results

- Overall verdict: PASS / WARN / FAIL
- Per-check results with scores
- Specific findings and recommendations
- Verification report saved path

---

## prototype-preflight

Verify that your machine is set up for Spec Machine prototyping. Checks required repositories, tools, and access.

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Run Availability Check

```bash
python3 "$PLUGIN_ROOT/tools/prototype/specx_bridge.py" --check
```

Report: whether specx-ux plugin is found, version, available agents and commands.

### Step 3: Check Command Availability

Check if these commands are available as skills (listed in system-reminder):
- `/create-prototype`
- `/update-prototype`
- `/verify-prototype`
- `/ux-preflight`

If commands are missing but plugin is on disk, suggest: "Run `/sync-commands` to sync Spec Machine commands."

### Step 4: Optionally Run Full Preflight

If `/ux-preflight` is available, offer to run it for full environment validation:

```
Skill(skill="ux-preflight")
```

This checks: HF repositories (web, ios, android, shared-mobile-modules, prototypes-playground, zest-tokens), yarn, Figma MCP, Jira CLI, npm auth.

### Step 5: Present Results

Display a preflight summary:

| Check | Status |
|-------|--------|
| specx-ux plugin on disk | Found / Not found |
| Plugin version | v1.0.0 |
| `/create-prototype` command | Synced / Not synced |
| `/update-prototype` command | Synced / Not synced |
| `/verify-prototype` command | Synced / Not synced |
| `/ux-preflight` command | Synced / Not synced |

If all checks pass: "Spec Machine is ready. Use `/feature prototype` to create production-quality prototypes."

If plugin found but commands not synced: "Spec Machine is installed but commands are not synced. Run `/sync-commands` to enable."

If plugin not found: "Spec Machine (specx-ux) not found. It should be at `claude-plugins-marketplace/plugins/specx-ux/`. Internal prototype engine will be used as fallback."

---

## Execute

Parse arguments and run the appropriate feature subcommand. If arguments match multiple subcommands, prefer the most specific match.
