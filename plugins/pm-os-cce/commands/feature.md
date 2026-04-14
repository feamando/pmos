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
| `prototype` | Generate prototype for current feature |
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
  /feature prototype                      - Generate prototype
  /feature prototype --format html        - HTML prototype
  /feature prototype --format figma       - Figma-compatible prototype

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

Generate a prototype for the current feature.

**Options:**

| Flag | Description |
|------|-------------|
| `--format <format>` | Output format: html, figma, markdown (default: html) |
| `--fidelity <level>` | low, medium, high (default: medium) |
| `--feature <slug>` | Feature to prototype (default: current) |

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

### Step 3: Generate Prototype

```bash
python3 "$PLUGIN_ROOT/tools/prototype/prototype_engine.py" --feature "$FEATURE_SLUG" $ARGUMENTS
```

### Step 4: Present Results

- Prototype output path
- Preview summary (screens, flows)
- Design assumptions noted
- Suggested review questions

---

## Execute

Parse arguments and run the appropriate feature subcommand. If arguments match multiple subcommands, prefer the most specific match.
