# Gemini FPF Bridge

Bridge for invoking FPF (First Principles Framework) reasoning from Gemini CLI.

## Arguments
$ARGUMENTS

## Instructions

This skill provides FPF reasoning capabilities for Gemini CLI sessions.

### Available Commands

Run the Gemini-Quint bridge with the specified command:

```bash
python3 "$PM_OS_COMMON/tools/quint/gemini_quint_bridge.py" <command> [question]
```

**Commands:**

| Command | Phase | Description |
|---------|-------|-------------|
| `init` | Q0 | Initialize FPF session |
| `hypothesize "Q"` | Q1 | Generate hypotheses for question Q |
| `verify` | Q2 | Verify hypotheses (deductive check) |
| `validate` | Q3 | Validate with evidence (inductive) |
| `audit` | Q4 | Audit for cognitive biases |
| `decide` | Q5 | Create Design Rationale Record |
| `status` | - | Show current reasoning state |
| `sync` | - | Sync reasoning to Brain |

### Example Workflow

```bash
# 1. Initialize session
python3 "$PM_OS_COMMON/tools/quint/gemini_quint_bridge.py" init "Should we migrate to microservices?"

# 2. Generate hypotheses
python3 "$PM_OS_COMMON/tools/quint/gemini_quint_bridge.py" hypothesize "What are the trade-offs of microservices vs monolith?"

# 3. Verify logical consistency
python3 "$PM_OS_COMMON/tools/quint/gemini_quint_bridge.py" verify

# 4. Gather evidence
python3 "$PM_OS_COMMON/tools/quint/gemini_quint_bridge.py" validate

# 5. Check for biases
python3 "$PM_OS_COMMON/tools/quint/gemini_quint_bridge.py" audit

# 6. Create decision record
python3 "$PM_OS_COMMON/tools/quint/gemini_quint_bridge.py" decide

# 7. Sync to Brain
python3 "$PM_OS_COMMON/tools/quint/gemini_quint_bridge.py" sync
```

### Output Formats

- **Human-readable:** Default output with formatted sections
- **JSON:** Add `--json` flag for machine-readable output

### Integration with Brain

All reasoning artifacts are stored in:
- **Active cycles:** `Brain/Reasoning/Active/`
- **Decisions (DRRs):** `Brain/Reasoning/Decisions/`
- **Hypotheses:** `Brain/Reasoning/Hypotheses/`
- **Evidence:** `Brain/Reasoning/Evidence/`

Run `/quint-sync` to synchronize with Quint Code database.

## Notes

- This bridge is designed for Gemini CLI but works with any command-line interface
- Session state is persisted in `.quint/gemini_fpf_state.json`
- DRR templates are created as drafts - fill in evidence and rationale
