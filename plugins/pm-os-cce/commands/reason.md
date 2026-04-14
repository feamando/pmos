---
description: First Principles Framework reasoning engine
---

# /reason -- FPF Reasoning Engine

Parse the first argument to determine which FPF (First Principles Framework) phase to run:

| Subcommand | FPF Phase | Description |
|------------|-----------|-------------|
| `init` | Q0 | Initialize reasoning session with question/problem |
| `add` | Q1 | Add evidence, data points, or observations |
| `hypothesize` | Q2 | Generate hypotheses from evidence |
| `verify` | Q3 | Verify hypotheses against evidence |
| `validate` | Q4 | Validate reasoning chain integrity |
| `audit` | -- | Audit full reasoning chain for gaps |
| `decide` | Q5 | Make decision with confidence level |
| `query` | -- | Query reasoning state |
| `status` | -- | Show current reasoning status |
| `reset` | -- | Reset reasoning session |
| `decay` | -- | Apply confidence decay to stale evidence |
| `actualize` | -- | Convert decision to action plan |
| *(no args)* | -- | Show available subcommands |

## Arguments
$ARGUMENTS

## No Arguments -- Show Help

If no arguments provided, display:

```
Reason -- FPF Reasoning Engine (First Principles Framework)

  /reason init "question"                 - Initialize reasoning session (Q0)
  /reason init --context "background"     - With background context
  /reason add "evidence"                  - Add evidence point (Q1)
  /reason add --source "url" --cl 3       - Evidence with source and confidence
  /reason add --type counter              - Add counter-evidence
  /reason hypothesize                     - Generate hypotheses (Q2)
  /reason hypothesize --count 5           - Generate N hypotheses
  /reason verify                          - Verify hypotheses (Q3)
  /reason verify --hypothesis 1           - Verify specific hypothesis
  /reason validate                        - Validate reasoning chain (Q4)
  /reason validate --strict               - Strict validation mode
  /reason audit                           - Full reasoning audit
  /reason audit --depth deep              - Deep audit with bias check
  /reason decide                          - Make decision (Q5)
  /reason decide --threshold cl3          - Require minimum confidence
  /reason query "question"                - Query reasoning state
  /reason status                          - Show reasoning status
  /reason reset                           - Reset reasoning session
  /reason reset --archive                 - Archive before reset
  /reason decay                           - Apply confidence decay
  /reason decay --threshold 7d            - Custom decay threshold
  /reason actualize                       - Convert decision to actions
  /reason actualize --format jira         - Action plan for Jira

Usage: /reason <subcommand> [options]
```

---

## init (Q0)

Initialize a reasoning session with a question or problem statement.

**Arguments:**
- `"question"` -- The question or problem to reason about (required)

**Options:**

| Flag | Description |
|------|-------------|
| `--context "text"` | Background context |
| `--feature <slug>` | Link to feature workspace |
| `--framework <name>` | Suggest reasoning framework |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Initialize FPF Session

```bash
python3 "$PLUGIN_ROOT/tools/reasoning/fpf_engine.py" init --question "$ARGUMENTS"
```

### Step 3: Load Brain Context

Search Brain for relevant entities to pre-populate context:
```
Use MCP tool: search_entities(query="<question_keywords>", limit=5)
```

### Step 4: Present Results

- Session ID
- Question framed
- Initial context loaded (Brain entities)
- Suggested evidence sources
- Next step: `/reason add` to add evidence

---

## add (Q1)

Add evidence, data points, or observations to the reasoning session.

**Arguments:**
- `"evidence"` -- Evidence statement (required)

**Options:**

| Flag | Description |
|------|-------------|
| `--source <url>` | Evidence source URL or reference |
| `--cl <level>` | Confidence level: 1-4 (default: 2) |
| `--type <type>` | supporting, counter, neutral (default: supporting) |
| `--weight <n>` | Evidence weight: 1-10 (default: 5) |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Add Evidence

```bash
python3 "$PLUGIN_ROOT/tools/reasoning/fpf_engine.py" add --evidence "$ARGUMENTS"
```

### Step 3: Run Orthogonal Challenge

Automatically challenge new evidence from an orthogonal perspective:
```bash
python3 "$PLUGIN_ROOT/tools/reasoning/orthogonal_challenge.py" --evidence "$EVIDENCE_ID"
```

### Step 4: Present Results

- Evidence registered with ID
- Confidence level assigned (CL1-CL4)
- Orthogonal challenge result
- Current evidence balance (supporting vs counter)
- Suggested next: more evidence or `/reason hypothesize`

---

## hypothesize (Q2)

Generate hypotheses from collected evidence.

**Options:**

| Flag | Description |
|------|-------------|
| `--count <n>` | Number of hypotheses to generate (default: 3) |
| `--creative` | Include creative/unconventional hypotheses |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Generate Hypotheses

```bash
python3 "$PLUGIN_ROOT/tools/reasoning/fpf_engine.py" hypothesize $ARGUMENTS
```

### Step 3: Match Frameworks

```bash
python3 "$PLUGIN_ROOT/tools/reasoning/framework_matcher.py" --question "$QUESTION" --hypotheses
```

### Step 4: Present Results

For each hypothesis:
- Hypothesis statement
- Supporting evidence (with CL levels)
- Counter-evidence
- Initial plausibility score
- Suggested framework for evaluation

---

## verify (Q3)

Verify hypotheses against evidence and identify gaps.

**Options:**

| Flag | Description |
|------|-------------|
| `--hypothesis <id>` | Verify specific hypothesis |
| `--all` | Verify all hypotheses |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Run Verification

```bash
python3 "$PLUGIN_ROOT/tools/reasoning/fpf_engine.py" verify $ARGUMENTS
```

### Step 3: Orthogonal Challenge

```bash
python3 "$PLUGIN_ROOT/tools/reasoning/orthogonal_challenge.py" --hypotheses
```

### Step 4: Present Results

For each hypothesis:
- Verification status: SUPPORTED / WEAKENED / INCONCLUSIVE / REFUTED
- Evidence alignment score
- Gaps identified (what evidence is missing)
- Bias warnings (confirmation bias, availability bias, etc.)

---

## validate (Q4)

Validate the full reasoning chain integrity.

**Options:**

| Flag | Description |
|------|-------------|
| `--strict` | Require all links validated |
| `--report` | Generate validation report without fixing |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Run Validation

```bash
python3 "$PLUGIN_ROOT/tools/reasoning/fpf_engine.py" validate $ARGUMENTS
```

### Step 3: Present Results

- Chain integrity score (0-100)
- Logical gaps identified
- Circular reasoning detected
- Evidence staleness warnings
- Recommendation: ready for decision or needs more work

---

## audit

Full reasoning audit with bias detection and gap analysis.

**Options:**

| Flag | Description |
|------|-------------|
| `--depth <level>` | quick, standard, deep (default: standard) |
| `--bias-check` | Focus on cognitive bias detection |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Run Audit

```bash
python3 "$PLUGIN_ROOT/tools/reasoning/fpf_engine.py" audit $ARGUMENTS
python3 "$PLUGIN_ROOT/tools/reasoning/orthogonal_challenge.py" --full-audit
```

### Step 3: Present Results

- Evidence coverage score
- Hypothesis diversity score
- Bias risk assessment
- Gap analysis with suggested evidence to collect
- Overall reasoning quality grade (A-F)

---

## decide (Q5)

Make a decision with confidence level based on the reasoning chain.

**Options:**

| Flag | Description |
|------|-------------|
| `--threshold <cl>` | Minimum confidence: cl1, cl2, cl3, cl4 (default: cl3) |
| `--force` | Decide even if threshold not met |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Generate Decision

```bash
python3 "$PLUGIN_ROOT/tools/reasoning/fpf_engine.py" decide $ARGUMENTS
```

### Step 3: Present Results

- **Decision:** Clear statement
- **Confidence Level:** CL1-CL4 with justification
- **Key Evidence:** Top supporting and counter evidence
- **Risks:** What could invalidate this decision
- **Reversibility:** Easy / Hard / Irreversible
- **Recommended Actions:** Next steps

### Confidence Levels

| Level | Name | Criteria |
|-------|------|----------|
| CL4 | Verified | Multiple independent sources confirm, no counter-evidence |
| CL3 | High | Strong evidence from authoritative source, minimal counter |
| CL2 | Medium | Some evidence, possible gaps, some counter-evidence |
| CL1 | Low | Limited evidence, significant gaps, strong counter-evidence |

---

## query

Query the current reasoning state.

**Arguments:**
- `"question"` -- Question about the reasoning state

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Query State

```bash
python3 "$PLUGIN_ROOT/tools/reasoning/fpf_engine.py" query --question "$ARGUMENTS"
```

---

## status

Show current reasoning session status.

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Get Status

```bash
python3 "$PLUGIN_ROOT/tools/reasoning/fpf_engine.py" status
```

### Step 3: Present Results

| Field | Value |
|-------|-------|
| Session | ID |
| Question | The question being reasoned about |
| Phase | Current FPF phase (Q0-Q5) |
| Evidence | Count (supporting / counter / neutral) |
| Hypotheses | Count with top-ranked |
| Confidence | Current CL level |
| Last Activity | Timestamp |

---

## reset

Reset the reasoning session.

**Options:**

| Flag | Description |
|------|-------------|
| `--archive` | Archive current session before reset |
| `--confirm` | Skip confirmation prompt |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Reset Session

```bash
python3 "$PLUGIN_ROOT/tools/reasoning/fpf_engine.py" reset $ARGUMENTS
```

---

## decay

Apply confidence decay to evidence that has become stale.

**Options:**

| Flag | Description |
|------|-------------|
| `--threshold <duration>` | Staleness threshold (default: 7d) |
| `--dry-run` | Preview decay without applying |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Apply Decay

```bash
python3 "$PLUGIN_ROOT/tools/reasoning/fpf_engine.py" decay $ARGUMENTS
```

### Step 3: Present Results

- Evidence items decayed (count)
- Before/after confidence levels
- Suggested evidence to refresh

---

## actualize

Convert a decision into a concrete action plan.

**Options:**

| Flag | Description |
|------|-------------|
| `--format <format>` | jira, markdown, checklist (default: markdown) |
| `--feature <slug>` | Link to feature workspace |

### Step 1: Set Up Environment

```bash
PLUGIN_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
export PM_OS_ROOT="${PM_OS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/pm-os")}"
export PM_OS_USER="$PM_OS_ROOT/user"
source "$PM_OS_USER/.env" 2>/dev/null
```

### Step 2: Generate Action Plan

```bash
python3 "$PLUGIN_ROOT/tools/reasoning/fpf_engine.py" actualize $ARGUMENTS
```

### Step 3: Present Results

- Action items with owners and due dates
- Dependencies between actions
- Risk mitigations from reasoning chain
- Success criteria from decision
- If `--format jira`: ready for `/roadmap create-task`

---

## Execute

Parse arguments and run the appropriate FPF reasoning subcommand. If arguments match multiple subcommands, prefer the most specific match.
