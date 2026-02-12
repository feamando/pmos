# PM-OS Brain 1.2 - Release Notes

**Release Date:** 2026-01-22
**Version:** PM-OS v3.2

## Overview

Brain 1.2 is a major upgrade to the PM-OS knowledge system, transforming static markdown files into a time-series capable knowledge base.

### Key Features

| Feature | Description |
|---------|-------------|
| **Canonical Reference Format** | All entity references normalized to `entity/{type}/{slug}` |
| **Relationship Tracking** | Typed, bidirectional relationships with temporal validity |
| **Event Sourcing** | Full change history with timestamps for point-in-time queries |
| **Quality Scoring** | Automated completeness and freshness scoring per entity |
| **Rich Metadata** | Confidence scores, sources, validity periods, and aliases |

## Entity Schema (v2)

Entities now use enhanced YAML frontmatter:

```yaml
---
$schema: "brain://entity/person/v1"
$id: "entity/person/jane-doe"
$type: "person"
$version: 5
$created: "2025-07-01T00:00:00Z"
$updated: "2026-01-22T10:00:00Z"
$confidence: 0.95
$source: "hr_system"

$relationships:
  - type: "reports_to"
    target: "entity/person/john-smith"
    since: "2024-06-01"
  - type: "member_of"
    target: "entity/team/platform"

$aliases: ["jane", "jane.doe", "Jane Doe"]
$tags: ["engineering", "platform"]
---

# Jane Doe

**Role:** Senior Engineer
**Team:** [[entity/team/platform|Platform]]
```

## New Tools

| Tool | Purpose |
|------|---------|
| `canonical_resolver.py` | Resolve any reference format to canonical $id |
| `relationship_normalizer.py` | Batch normalize and deduplicate relationships |
| `orphan_cleaner.py` | Identify and clean invalid references |
| `reference_validator.py` | Pre-write validation for canonical format |
| `schema_migrator.py` | Migrate v1 entities to v2 format |
| `enrichment_pipeline.py` | Re-enrich entities from data sources |
| `quality_scorer.py` | Calculate entity completeness scores |
| `relationship_auditor.py` | Verify relationship consistency |
| `event_store.py` | Event persistence and querying |
| `temporal_query.py` | Point-in-time entity reconstruction |
| `snapshot_manager.py` | Periodic registry snapshots |

## Pydantic Schemas

New type-safe schemas in `schemas/brain/`:

- `entity.py` - Base entity with all metadata fields
- `person.py` - Person entity schema
- `project.py` - Project entity schema
- `team.py` - Team/squad entity schema
- `event.py` - Change event schema
- `registry.py` - Registry entry schema
- `relationship.py` - Relationship type definitions

## Data Quality Results

Initial migration achieved:

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Orphan targets | 555 | 0 | 100% fixed |
| Relationships normalized | - | 237 | New |
| Duplicates removed | 211 | 0 | 100% fixed |

## Key Changes from Brain 1.1

| Aspect | Brain 1.1 | Brain 1.2 |
|--------|-----------|-----------|
| Reference Format | Free-form paths, wiki-links | Canonical `entity/{type}/{slug}` |
| Relationships | Unidirectional, untyped | Bidirectional, typed with dates |
| Change Tracking | Manual changelog section | `$events` array with full history |
| Validation | None | Pydantic schemas + pre-write hooks |
| Quality Metrics | None | Confidence, completeness, freshness |

## Migration Guide

### Backward Compatibility

Existing entities are backward compatible. The Brain loader supports both v1 and v2 formats.

### Full Migration

To migrate all entities to v2 format:

```bash
python3 common/tools/brain/schema_migrator.py --migrate-all
```

### Validation

To validate entities without migrating:

```bash
python3 common/tools/brain/entity_validator.py --check-all
```

## Integration with Other Features

### PRD to Spec Machine

Brain 1.2 entities can be referenced in PRDs and exported to the Spec Machine:

```bash
/export-to-spec path/to/prd.md
```

### Beads-Ralph Integration

Ralph now supports Beads issue tracking with Brain context:

```bash
/ralph-loop bd-XXXX  # Use Beads epic directly
```

## Related Links

- [PR #13: Brain 1.2 Implementation](https://github.com/feamando/pmos/pull/13)
- [PM-OS README](../README.md)
- [Entity Schema Reference](../schemas/brain/)
