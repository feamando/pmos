# Brain Enrich

Run TKS-derived brain quality tools to improve graph density, identify gaps, and maintain relationship health.

## Arguments
$ARGUMENTS

## Instructions

### Default: Full Enrichment

Run the full enrichment orchestrator:

```bash
python3 "$PM_OS_COMMON/tools/brain/brain_enrich.py" --verbose
```

This will:
1. Analyze baseline graph health
2. Run soft edge inference (by entity type)
3. Scan for relationship staleness
4. Generate extraction hints
5. Report density improvements

### Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `--mode full` | All tools, apply changes | Weekly maintenance |
| `--mode quick` | Soft edges only | Quick density boost |
| `--mode report` | Analysis only, no changes | Status check |
| `--mode boot` | Minimal, fast checks | Boot-time integration |

### Options

| Flag | Description |
|------|-------------|
| `--quick` | Shortcut for `--mode quick` |
| `--report` | Shortcut for `--mode report` |
| `--boot` | Shortcut for `--mode boot` (minimal, fast) |
| `--dry-run` | Preview changes without applying |
| `--verbose, -v` | Show detailed progress |
| `--output json` | Machine-readable output |

### Examples

```bash
# Full enrichment with verbose output
python3 "$PM_OS_COMMON/tools/brain/brain_enrich.py" --verbose

# Quick mode - soft edges only
python3 "$PM_OS_COMMON/tools/brain/brain_enrich.py" --quick

# Report only - no changes
python3 "$PM_OS_COMMON/tools/brain/brain_enrich.py" --report

# Boot-time mode - fast, minimal
python3 "$PM_OS_COMMON/tools/brain/brain_enrich.py" --boot

# Dry run - preview changes
python3 "$PM_OS_COMMON/tools/brain/brain_enrich.py" --dry-run --verbose

# JSON output for automation
python3 "$PM_OS_COMMON/tools/brain/brain_enrich.py" --output json
```

## Output

```
============================================================
Brain Enrichment Complete
============================================================
Mode: full
Timestamp: 2026-01-30T10:00:00

Baseline:
  Entities: 2,614
  Relationships: 96
  Orphans: 2,449
  Density: 0.027

Soft Edges Added:
  Total: 150
  - brand: 16
  - system: 50
  - squad: 34
  - experiment: 50

Final:
  Entities: 2,614
  Relationships: 246
  Orphans: 2,399
  Density: 0.043

Insights:
  Stale relationships: 127
  High-priority hints: 9,357
  Top missing: $relationships, owner, members, team, description

Improvements:
  Density: 0.027 -> 0.043 (+59.3%)
  Orphans reduced: 50
```

## Individual Tools

Run specific tools directly for targeted analysis:

### Graph Health

```bash
python3 "$PM_OS_COMMON/tools/brain/graph_health.py"              # Full report
python3 "$PM_OS_COMMON/tools/brain/graph_health.py" orphans      # List orphans
python3 "$PM_OS_COMMON/tools/brain/graph_health.py" density      # Density only
python3 "$PM_OS_COMMON/tools/brain/graph_health.py" connected    # Connectivity
```

### Relationship Decay

```bash
python3 "$PM_OS_COMMON/tools/brain/relationship_decay.py" scan   # Quick scan
python3 "$PM_OS_COMMON/tools/brain/relationship_decay.py" stale  # Stale list
python3 "$PM_OS_COMMON/tools/brain/relationship_decay.py" report # Full report
```

### Extraction Hints

```bash
python3 "$PM_OS_COMMON/tools/brain/extraction_hints.py"                    # All hints
python3 "$PM_OS_COMMON/tools/brain/extraction_hints.py" --priority high    # High priority
python3 "$PM_OS_COMMON/tools/brain/extraction_hints.py" --source jira      # Jira hints
python3 "$PM_OS_COMMON/tools/brain/extraction_hints.py" --type person      # Person entities
```

### Soft Edge Inference

```bash
python3 "$PM_OS_COMMON/tools/brain/embedding_edge_inferrer.py" scan        # Preview edges
python3 "$PM_OS_COMMON/tools/brain/embedding_edge_inferrer.py" apply       # Apply edges
python3 "$PM_OS_COMMON/tools/brain/embedding_edge_inferrer.py" --type team # Specific type
python3 "$PM_OS_COMMON/tools/brain/embedding_edge_inferrer.py" --threshold 0.9  # Higher threshold
```

## Use Cases

1. **Weekly maintenance** - Run full enrichment to improve graph density
2. **Boot sequence** - Use `--boot` mode for fast health check
3. **Status check** - Use `--report` mode to see current state
4. **Quick boost** - Use `--quick` for immediate density improvement
5. **Targeted enrichment** - Use individual tools for specific needs

## Integration

The brain enrichment can be integrated into boot by adding to the boot orchestrator:

```bash
# Boot-time enrichment (fast, minimal)
python3 "$PM_OS_COMMON/tools/brain/brain_enrich.py" --boot --output json
```
