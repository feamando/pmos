# Brain Loader

Scan context files for entity mentions and identify relevant Brain files to load.

## Arguments
$ARGUMENTS

## Instructions

### Default: Scan Latest Context for Hot Topics

Run the brain loader to identify entities mentioned in today's context:

```bash
python3 "$PM_OS_COMMON/tools/brain/brain_loader.py"
```

This will:
- Scan the latest `*-context.md` file
- Match mentions against `registry.yaml` aliases
- Index experiments from `Brain/Experiments/`
- Output hot topics sorted by mention count
- List Brain files to load for deeper context

### Options

| Flag | Description |
|------|-------------|
| `--context FILE` | Scan specific context file |
| `--query "term"` | Search for specific terms (partial match) |
| `--list-all` | List all registered entities |
| `--validate` | Check registry for missing Brain files |
| `--verbose, -v` | Show matched aliases |
| `--files-only` | Output only file paths (for scripting) |

### Examples

```bash
# Scan latest context
python3 "$PM_OS_COMMON/tools/brain/brain_loader.py"

# Search for specific topic
python3 "$PM_OS_COMMON/tools/brain/brain_loader.py" --query "OTP launch"

# Validate registry integrity
python3 "$PM_OS_COMMON/tools/brain/brain_loader.py" --validate

# List all entities
python3 "$PM_OS_COMMON/tools/brain/brain_loader.py" --list-all

# Scripting: get file paths only
python3 "$PM_OS_COMMON/tools/brain/brain_loader.py" --files-only
```

## Output

```
============================================================
HOT TOPICS - Entities mentioned in context
============================================================

## PROJECTS
- **OTP** (25 mentions) [EXISTS]
  File: `Brain/Projects/OTP.md`

## ENTITIES
- **Alice** (8 mentions) [EXISTS]
  File: `Brain/Entities/Alice_Engineer.md`

============================================================
Files to load:
  - Brain/Projects/OTP.md
  - Brain/Entities/Alice_Engineer.md
============================================================
```

## Use Cases

1. **Boot sequence** - Identify hot topics to load for session context
2. **Search** - Find Brain files related to a topic
3. **Validation** - Audit registry for missing files
4. **Scripting** - Pipe file list to other tools
