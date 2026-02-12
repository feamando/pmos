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

PM-OS uses a **Git-backed, CLI-managed filesystem** with a two-folder architecture:

- **LOGIC (`$PM_OS_COMMON`):** Shared code, commands, tools, frameworks
- **CONTENT (`$PM_OS_USER`):** Your data, brain, sessions, context

### Core Structure

**In LOGIC (common/):**
- `.claude/commands/` - Claude slash commands
- `.gemini/commands/` - Gemini commands
- `tools/` - Python tools
- `frameworks/` - Document templates
- `schemas/` - Entity schemas
- `rules/` - This file and user template

**In CONTENT (user/):**
- `brain/` - Knowledge base (entities, projects, experiments)
- `context/` - Daily context files
- `sessions/` - Session persistence
- `planning/` - Meeting prep, career planning
- `config.yaml` - Your configuration
- `.env` - Your secrets

## 2. Operational Workflows (The "How")

### Discovery
- **Before answering:** Search Brain for definitions, context for current state.
- **Tools:** Use `glob` to find files, `grep` to search content.
- **Path Resolution:** Use `$PM_OS_USER` for content, `$PM_OS_COMMON` for tools.

### Document Creation
- **Templates:** NEVER create a blank file. Check `$PM_OS_COMMON/frameworks/` for templates.
- **Naming:**
    - **Dated:** `YYYY-MM-DD-topic-name.md`
    - **Living:** `kebab-case-descriptive.md`

### Document Updates
- **Append over Overwrite:** For logs, add new entries consistently.
- **Linkage:** When creating a new doc, link it appropriately.

### Context Update Workflow
1. Run `/update-context` to fetch the latest data.
2. Read the generated `$PM_OS_USER/context/YYYY-MM-DD-context.md`.
3. Synthesize into structured summary.

## 3. Style & Quality Standards
- **Format:** Standard GitHub Flavored Markdown.
- **Brevity:** Use bullet points and bold text for skimmability.
- **Tone:** Professional, objective, "Amazon 6-pager" style.
- **Filesystem Hygiene:**
    - No spaces in filenames.
    - Consistent organization.

## 4. Tool Invocation

**Python Tools:**
```bash
python3 "$PM_OS_COMMON/tools/tool_name.py" [options]
```

**Config Access:**
Tools automatically load `$PM_OS_USER/config.yaml` for settings.

**Tool Discovery:**
When unsure about tool paths or availability, run:
```bash
python3 "$PM_OS_COMMON/tools/preflight/preflight_runner.py" --list
```
This outputs all 67+ tools with paths and descriptions. Never guess tool paths - check the registry first.

## 5. FPF (First Principles Framework) - Structured Reasoning

PM-OS integrates **Quint Code** for structured reasoning.

### When to Use FPF

**Use FPF for:**
- Architectural decisions with long-term consequences
- Multiple viable approaches requiring systematic evaluation
- Decisions needing an auditable reasoning trail

**Skip FPF for:**
- Quick fixes with obvious solutions
- Easily reversible decisions
- Time-critical situations

### FPF Commands

| Command | Phase | Action |
|---------|-------|--------|
| `/q0-init` | Setup | Initialize bounded context |
| `/q1-hypothesize` | Abduction | Generate competing hypotheses |
| `/q2-verify` | Deduction | Logical verification |
| `/q3-validate` | Induction | Empirical testing |
| `/q4-audit` | Audit | Calculate trust scores (WLNK) |
| `/q5-decide` | Decision | Create Design Rationale Record |
| `/q-status` | Utility | Show current state |

### FPF Glossary

**Knowledge Layers:**
- **L0 (Conjecture):** Unverified hypothesis
- **L1 (Substantiated):** Logically verified
- **L2 (Corroborated):** Empirically validated

**Core Concepts:**
- **WLNK:** `R_eff = min(evidence)` - chain is only as strong as weakest link
- **DRR:** Design Rationale Record - persisted decision with context

## 6. AI-Generated Content Disclaimer

For ALL documents generated by agents, add at the bottom:
`Automatically generated by [[model ID]] on [[timestamp]]`

## 7. Tool Development Requirements

### Pre-Flight Test Requirement

All PM-OS tools must have pre-flight verification tests. When creating a new tool:

1. **Add tool to registry**
   - Update `$PM_OS_COMMON/tools/preflight/registry.py`
   - Specify: path, module, classes, functions, config requirements

2. **Create test cases** (if complex tool)
   - Add to appropriate `preflight/tests/test_<category>.py`
   - Include import test, class/function existence tests
   - Add config tests if tool requires configuration

3. **Verify preflight passes**
   - Run: `python3 $PM_OS_COMMON/tools/preflight/preflight_runner.py`
   - Ensure all tests pass before committing

### Tool Registry Entry Template

```python
"tool_name": {
    "path": "category/tool_name.py",
    "module": "category.tool_name",
    "classes": ["ClassName1", "ClassName2"],  # optional
    "functions": ["function1", "function2"],  # optional
    "requires_config": True,  # or False
    "env_keys": ["API_KEY"],  # optional
    "optional_connectivity": True,  # optional
    "description": "Brief description",
},
```

### Test Function Template

```python
def check_tool_import() -> Tuple[bool, str]:
    try:
        from category import tool_name
        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"

def check_tool_classes() -> Tuple[bool, str]:
    from category.tool_name import ClassName
    return True, "Classes OK"
```

### Pre-Flight Commands

```bash
# Quick check (import tests only)
python3 $PM_OS_COMMON/tools/preflight/preflight_runner.py --quick

# Full check
python3 $PM_OS_COMMON/tools/preflight/preflight_runner.py

# Check specific category
python3 $PM_OS_COMMON/tools/preflight/preflight_runner.py --category core

# JSON output
python3 $PM_OS_COMMON/tools/preflight/preflight_runner.py --json
```

---

*PM-OS v3.0 - AI Agent Operation Guide*
