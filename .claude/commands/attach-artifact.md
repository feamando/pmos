# Attach Artifact

Attach external artifacts (Figma designs, Jira tickets, Confluence pages, etc.) to a feature in the Context Creation Engine.

## Overview

This command links external artifacts to a feature by:
1. Validating the URL/reference format
2. Updating feature-state.yaml artifacts section
3. Updating the {feature}-context.md References section

## Arguments

- `<type>` - Artifact type (required): `figma`, `wireframes`, `jira`, `confluence`, `gdocs`
- `<url_or_value>` - URL or identifier (required)
- `--feature <slug>` - Feature slug (optional, uses current directory if not specified)

**Examples:**
```
/attach-artifact figma https://figma.com/file/abc123/Design-v1
/attach-artifact jira MK-1234
/attach-artifact wireframes https://figma.com/file/xyz789/Wireframes
/attach-artifact confluence https://your-company.atlassian.net/wiki/spaces/MK/pages/123456
```

## Instructions

### Step 1: Parse Arguments

Extract artifact type, URL/value, and optional feature slug.

```python
artifact_type = "figma"  # Required: figma, wireframes, jira, confluence, gdocs
url_or_value = "https://figma.com/file/abc123"  # Required
feature_slug = None  # Optional, from --feature flag
```

### Step 2: Map Artifact Type

```python
import sys
sys.path.insert(0, "$PM_OS_COMMON/tools")
from context_engine import ArtifactManager, ArtifactType

TYPE_MAP = {
    "figma": ArtifactType.FIGMA,
    "wireframes": ArtifactType.WIREFRAMES,
    "jira": ArtifactType.JIRA_EPIC,
    "confluence": ArtifactType.CONFLUENCE_PAGE,
    "gdocs": ArtifactType.GDOCS,
}

if artifact_type not in TYPE_MAP:
    print(f"Error: Unknown artifact type '{artifact_type}'")
    print(f"Valid types: {', '.join(TYPE_MAP.keys())}")

mapped_type = TYPE_MAP[artifact_type]
```

### Step 3: Normalize URL

For Jira tickets, convert ticket keys to full URLs.

```python
if artifact_type == "jira" and not url_or_value.startswith("http"):
    url_or_value = f"https://your-company.atlassian.net/browse/{url_or_value}"
    print(f"Converted to URL: {url_or_value}")
```

### Step 4: Find Feature Path

Locate the feature folder from --feature flag or current directory.

```python
from pathlib import Path

if feature_slug:
    products_path = Path("$PM_OS_USER/products")
    feature_path = None
    for org_dir in products_path.iterdir():
        if org_dir.is_dir():
            for product_dir in org_dir.iterdir():
                if product_dir.is_dir():
                    for feature_dir in product_dir.iterdir():
                        if feature_dir.is_dir() and feature_dir.name == feature_slug:
                            feature_path = feature_dir
                            break
else:
    feature_path = Path.cwd()
    if not (feature_path / "feature-state.yaml").exists():
        print("Error: Not in a feature directory. Use --feature <slug>")
```

### Step 5: Validate and Attach

```python
manager = ArtifactManager()

validation = manager.validate(mapped_type, url_or_value)
if not validation.valid:
    print(f"Error: {validation.message}")

result = manager.attach(
    feature_path=feature_path,
    artifact_type=mapped_type,
    url=url_or_value,
    attached_by="user"
)
```

### Step 6: Report Results

```
┌─────────────────────────────────────────────────────────────┐
│ ARTIFACT ATTACHED                                            │
├─────────────────────────────────────────────────────────────┤
│ Type: Figma Design                                           │
│ URL: https://figma.com/file/abc123/Design-v1                 │
│ Feature: mk-feature-recovery                                    │
│                                                              │
│ Updated:                                                     │
│   - feature-state.yaml (artifacts.figma)                     │
│   - mk-feature-recovery-context.md (References section)         │
└─────────────────────────────────────────────────────────────┘
```

## Artifact Types Reference

| Type | Description | URL Pattern |
|------|-------------|-------------|
| `figma` | Figma design files | `figma.com/file/<id>` |
| `wireframes` | Wireframe designs | Same as figma |
| `jira` | Jira tickets/epics | `atlassian.net/browse/<KEY>` or `MK-1234` |
| `confluence` | Confluence pages | `atlassian.net/wiki/spaces/<SPACE>/pages/<id>` |
| `gdocs` | Google Docs | `docs.google.com/document/d/<id>` |

## Integration Points

- **ArtifactManager**: `common/tools/context_engine/artifact_manager.py`
- **FeatureState**: `common/tools/context_engine/feature_state.py`

## Execute

Parse arguments, validate URL, attach artifact to feature, update both feature-state.yaml and context file, report results.
