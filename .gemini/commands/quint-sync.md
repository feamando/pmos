# Quint-Brain Sync

Synchronize Quint Code knowledge with PM-OS Brain.

## Instructions

### Sync .quint/ to Brain/Reasoning/

Run the sync tool to copy verified knowledge and decisions to Brain:

```bash
python3 "$PM_OS_COMMON/tools/quint/quint_brain_sync.py" --to-brain
```

This will:
- Copy DRRs from `.quint/decisions/` to `Brain/Reasoning/Decisions/`
- Copy L2 verified claims from `.quint/knowledge/L2/` to `Brain/Reasoning/Hypotheses/`
- Copy evidence from `.quint/evidence/` to `Brain/Reasoning/Evidence/`
- Update Brain entity links (Synapses)

### Sync Brain context to .quint/

Update Quint's bounded context with Brain data:

```bash
python3 "$PM_OS_COMMON/tools/quint/quint_brain_sync.py" --to-quint
```

This will:
- Update `.quint/context.md` with current project states
- Add Brain entity references to Quint knowledge base
- Import relevant daily context

### Bidirectional Sync

```bash
python3 "$PM_OS_COMMON/tools/quint/quint_brain_sync.py" --bidirectional
```

### Flags

| Flag | Description |
|------|-------------|
| `--to-brain` | Export Quint → Brain |
| `--to-quint` | Import Brain → Quint |
| `--bidirectional` | Both directions |
| `--dry-run` | Preview changes without writing |
| `--verbose` | Show detailed sync log |

## When to Use

- After completing a FPF cycle (`/q5-decide`)
- Before starting a new reasoning cycle
- As part of session end (`/logout`)
- After major Brain updates
