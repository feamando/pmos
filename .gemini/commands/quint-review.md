# Review Reasoning State

Quick status check of all FPF reasoning in the repository.

## Instructions

### 1. Check Current Cycle State

```
/q-status
```

### 2. Check for Expiring Evidence

```
/q-decay
```

### 3. List Active DRRs

Review recent decisions:

```bash
ls -la $PM_OS_USER/brain/Reasoning/Decisions/
```

### 4. Check for Orphaned Hypotheses

Find L0/L1 claims that never reached L2:

```bash
ls -la .quint/knowledge/L0/
ls -la .quint/knowledge/L1/
```

### 5. Summary Report

Generate a reasoning summary:

| Metric | Count |
|--------|-------|
| Active Cycles | `ls .quint/sessions/ \| wc -l` |
| Total DRRs | `ls Brain/Reasoning/Decisions/ \| wc -l` |
| L2 Claims | `ls .quint/knowledge/L2/ \| wc -l` |
| Expiring Evidence | `/q-decay --count` |

### 6. Reconcile with Code

Check if code changes have invalidated any decisions:

```
/q-actualize
```

## When to Use

- At session start (part of `/boot`)
- Before making architectural decisions
- Weekly maintenance review
- After major code changes
