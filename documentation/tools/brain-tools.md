# Brain Tools

> Tools for managing the PM-OS Brain knowledge base

## brain_loader.py

Load Brain entities into context.

### Location

`common/tools/brain/brain_loader.py`

### Purpose

- Load entities from Brain directory
- Search across Brain content
- Index entity references
- Identify hot topics from context

### CLI Usage

```bash
# Load hot topics from today's context
python3 brain_loader.py

# Load with reasoning state
python3 brain_loader.py --reasoning

# Search Brain
python3 brain_loader.py --search "payment"
```

### Python API

```python
from brain.brain_loader import (
    load_entity,
    search_brain,
    get_hot_topics,
    load_reasoning_state
)

# Load specific entity
person = load_entity("person", "alice_smith")

# Search across Brain
results = search_brain("payment gateway")

# Get hot topics from context
topics = get_hot_topics(context_file)

# Load FPF reasoning state
reasoning = load_reasoning_state()
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `--reasoning` | flag | Include FPF reasoning state |
| `--search` | str | Search query |
| `--entity` | str | Entity type to load |
| `--id` | str | Entity ID to load |

### Output

```json
{
  "hot_projects": [
    {"id": "payment_gateway", "path": "projects/feature/payment_gateway.md"}
  ],
  "hot_entities": [
    {"id": "alice_smith", "type": "person"}
  ],
  "missing_entities": ["new_contact"]
}
```

---

## brain_updater.py

Update Brain entities with new information.

### Location

`common/tools/brain/brain_updater.py`

### Purpose

- Update existing entity files
- Add new fields to entities
- Track last_updated timestamps
- Maintain entity relationships

### CLI Usage

```bash
# Update entity field
python3 brain_updater.py --entity person --id alice_smith --field last_interaction --value "2026-01-13"

# Add to list field
python3 brain_updater.py --entity person --id alice_smith --append working_on --value "new_project"
```

### Python API

```python
from brain.brain_updater import (
    update_entity,
    add_field,
    append_to_list,
    update_timestamp
)

# Update single field
update_entity("person", "alice_smith", {
    "last_interaction": "2026-01-13"
})

# Add new field
add_field("person", "alice_smith", "preferred_meeting_time", "mornings")

# Append to list
append_to_list("person", "alice_smith", "expertise", "GraphQL")

# Update timestamp
update_timestamp("person", "alice_smith")
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `--entity` | str | Entity type (person, team, project) |
| `--id` | str | Entity identifier |
| `--field` | str | Field to update |
| `--value` | str | New value |
| `--append` | str | List field to append to |

---

## unified_brain_writer.py

Write new Brain entities with validation.

### Location

`common/tools/brain/unified_brain_writer.py`

### Purpose

- Create new entity files
- Validate against schemas
- Update registry
- Maintain consistency

### CLI Usage

```bash
# Create new person
python3 unified_brain_writer.py --type person --data '{"id": "bob_jones", "name": "Bob Jones", ...}'

# Create from file
python3 unified_brain_writer.py --type project --file new_project.yaml

# Dry run (validate only)
python3 unified_brain_writer.py --type person --data '...' --dry-run
```

### Python API

```python
from brain.unified_brain_writer import (
    write_entity,
    create_from_template,
    validate_entity,
    update_registry
)

# Write new entity
write_entity("person", {
    "id": "bob_jones",
    "name": "Bob Jones",
    "email": "bob@company.com",
    "role": {
        "title": "Product Manager",
        "team": "platform_team"
    }
})

# Create from template
create_from_template("project", "feature", {
    "id": "new_feature",
    "name": "New Feature"
})

# Validate before write
errors = validate_entity("person", data)
if not errors:
    write_entity("person", data)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `--type` | str | Entity type |
| `--data` | str | JSON entity data |
| `--file` | str | YAML/JSON file path |
| `--dry-run` | flag | Validate only, don't write |
| `--force` | flag | Overwrite existing |

### Validation

Entities are validated against schemas in `common/schemas/`:

```yaml
# schemas/person.yaml
required:
  - id
  - name
  - email
properties:
  id:
    type: string
    pattern: "^[a-z_]+$"
  name:
    type: string
  email:
    type: string
    format: email
```

---

## brain_enrich.py

Orchestrate Brain quality improvement tools.

### Location

`common/tools/brain/brain_enrich.py`

### Purpose

- Analyze graph health metrics
- Run soft edge inference to add relationships
- Identify stale or orphan entities
- Improve Brain density automatically

### CLI Usage

```bash
# Full enrichment (apply all changes)
python3 brain_enrich.py --verbose

# Quick enrichment (soft edges only)
python3 brain_enrich.py --mode quick

# Analysis only (no changes)
python3 brain_enrich.py --mode report

# Boot-time minimal check
python3 brain_enrich.py --mode boot

# Preview changes
python3 brain_enrich.py --dry-run
```

### Python API

```python
from brain.brain_enrich import BrainEnrichmentOrchestrator

orchestrator = BrainEnrichmentOrchestrator()

# Run full enrichment
results = orchestrator.run(mode="full")

# Run quick enrichment
results = orchestrator.run(mode="quick")

# Get report only
metrics = orchestrator.analyze()
```

### Modes

| Mode | Description | Duration | Use Case |
|------|-------------|----------|----------|
| `full` | All enrichers, apply changes | ~2-5 min | Weekly maintenance |
| `quick` | Body text extraction only | ~30 sec | Quick density boost |
| `report` | Analysis only, no changes | ~10 sec | Status check |
| `boot` | Minimal health check | ~5 sec | Boot integration |

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `--mode` | str | Enrichment mode (full, quick, report, boot) |
| `--quick` | flag | Shortcut for --mode quick |
| `--report` | flag | Shortcut for --mode report |
| `--boot` | flag | Shortcut for --mode boot |
| `--dry-run` | flag | Preview changes without applying |
| `--verbose` | flag | Show detailed progress |
| `--output` | str | Output format (text, json) |

### Output Metrics

```json
{
  "baseline": {
    "total_entities": 156,
    "orphan_count": 52,
    "orphan_rate": 0.333,
    "total_relationships": 284,
    "density": 1.82
  },
  "after": {
    "orphan_count": 38,
    "orphan_rate": 0.244,
    "total_relationships": 331,
    "density": 2.12,
    "new_relationships": 47
  },
  "improvement": {
    "orphan_reduction": 14,
    "density_increase": 0.30
  }
}
```

### Enrichment Pipeline

1. **Baseline Analysis** - Calculate current graph health
2. **Body Text Extraction** - Extract entities from markdown content
3. **Soft Edge Inference** - Infer relationships from co-occurrence
4. **Staleness Scan** - Identify old, unverified relationships
5. **Extraction Hints** - Generate suggestions for missing data
6. **Final Metrics** - Compare before/after

---

## Common Dependencies

All brain tools use:

```python
from config_loader import get_brain_path, get_user_path
from path_resolver import get_paths
```

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| `EntityNotFound` | Entity ID doesn't exist | Check ID spelling |
| `ValidationError` | Data doesn't match schema | Fix data per schema |
| `RegistryError` | Registry file corrupted | Run registry rebuild |

## Best Practices

1. **Always validate** before writing
2. **Update timestamps** on entity changes
3. **Use append** for list fields, not replace
4. **Run dry-run** first for new entity types
5. **Keep IDs** lowercase with underscores

---

## Related Documentation

- [Brain Architecture](../05-brain.md) - Brain structure
- [Entity Schemas](../schemas/entity-schemas.md) - Schema details
- [Core Commands](../commands/core-commands.md) - `/brain-load`, `/brain-enrich`
- [Workflows](../04-workflows.md) - Brain Enrichment workflow

---

*Last updated: 2026-02-02*
