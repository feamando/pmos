# Synapse Builder

Enforce bi-directional relationships between Brain entities.

## Instructions

Run the synapse builder to scan all Brain files and ensure relationship reciprocity:

```bash
python3 "$PM_OS_COMMON/tools/documents/synapse_builder.py"
```

### What It Does

Scans Brain files for `relationships` in YAML frontmatter and ensures inverse links exist:

| Forward | Inverse |
|---------|---------|
| `owner` | `owns` |
| `member_of` | `has_member` |
| `blocked_by` | `blocks` |
| `depends_on` | `dependency_for` |
| `relates_to` | `relates_to` |
| `part_of` | `has_part` |

**Example:**
If `Projects/OTP.md` has:
```yaml
relationships:
  owner: [[Entities/Alice.md]]
```

Then `Entities/Alice.md` will be updated to include:
```yaml
relationships:
  owns: [[Projects/OTP.md]]
```

### Options

| Flag | Description |
|------|-------------|
| `--dry-run` | Preview changes without writing files |

### Examples

```bash
# Preview what would change
python3 "$PM_OS_COMMON/tools/documents/synapse_builder.py" --dry-run

# Apply changes
python3 "$PM_OS_COMMON/tools/documents/synapse_builder.py"
```

### Output

```
Scanning Brain in /path/to/Brain...
  [+] Entities/Alice.md: Adding 'owns' -> Projects/OTP.md
  [+] Entities/Team_GD.md: Adding 'has_member' -> Entities/Alice.md

Done. Modified 2 files.
```

## When to Use

- After adding new Brain entities with relationships
- After manual edits to relationship sections
- As part of Brain maintenance workflow
- Before generating meeting preps (ensures complete context)
