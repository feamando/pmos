# Export to Spec Machine

Export a PM-OS PRD or Context Engine feature to spec-machine input format, bypassing the interactive `/gather-requirements` session.

## Usage

```
/export-to-spec <source> [--repo <target-repo>] [--spec-name <name>] [--subdir <subdir>] [--feature]
```

## Arguments

- `source`: Either a PRD file path OR a feature slug (required)
  - PRD path: Can be relative to pm-os root or absolute
  - Feature slug: Use with `--feature` flag for context engine features
  - Supports standard PRD, Orthogonal Challenge v3_final.md, and context engine features
- `--repo`: Target repository alias from config (e.g., 'mobile-rn', 'web')
- `--spec-name`: Name for the spec folder (will be kebab-cased)
- `--subdir`: Optional spec subdirectory (e.g., 'meal-kit')
- `--feature`: Treat source as a context engine feature slug instead of PRD path

## Instructions

### Step 0: Determine Export Mode

Check if the `--feature` flag is present or if source looks like a feature slug:

```python
import sys
sys.path.insert(0, "$PM_OS_COMMON/tools")

# Determine if this is a feature export or PRD export
is_feature_export = "--feature" in args or (
    not source.endswith('.md') and
    not '/' in source and
    not source.startswith('user/') and
    not source.startswith('Products/')
)
```

If exporting a context engine feature, go to **Step 1a**. Otherwise, continue to **Step 1b**.

### Step 1a: Export Context Engine Feature

Use the spec_export module to export a feature:

```python
from context_engine.spec_export import SpecExporter
import config_loader

config = config_loader.get_config()
exporter = SpecExporter()

# Get preview first
preview = exporter.get_export_preview(feature_slug)
if not preview:
    print(f"Feature not found: {feature_slug}")
    exit(1)

# Show what will be exported
print(f"""
Feature Export Preview:
  Title: {preview['title']}
  Product: {preview['product']}
  Has Problem Statement: {preview['has_problem_statement']}
  Has Executive Summary: {preview['has_executive_summary']}
  BC Approved: {preview['bc_approved']}
  ADR Count: {preview['adr_count']}
  Estimate: {preview['estimate_size'] or 'Not recorded'}
  Risks: {preview['risk_count']}
  Dependencies: {preview['dependency_count']}
  Has Figma: {preview['has_figma']}
""")

# Resolve repo from config
repos = config.get("spec_machine.repos", {})
if repo_alias and repo_alias in repos:
    target_repo = repos[repo_alias]
elif repo_alias:
    # Treat as direct path
    target_repo = repo_alias
else:
    # Use default repo
    default_repo = config.get("spec_machine.default_repo", "")
    if default_repo and default_repo in repos:
        target_repo = repos[default_repo]
    else:
        print("No repo specified and no default configured.")
        print(f"Available repos: {list(repos.keys())}")
        exit(1)

# Export the feature
result = exporter.export_feature(
    slug=feature_slug,
    target_repo=target_repo,
    spec_name=spec_name,  # Optional, defaults to feature slug
    subdir=subdir,
    dry_run=False
)

if result.success:
    print(f"[PASS] Feature exported to spec machine")
    print(f"Spec folder: {result.spec_folder}")
    print(f"Files created: {result.files_created}")
else:
    print(f"[FAIL] Export failed: {result.message}")
    for error in result.errors:
        print(f"  Error: {error}")
```

Skip to **Step 4** after feature export.

### Step 1b: Locate PRD File (Traditional Export)

If no path provided, search for recent PRDs:

```bash
# Check Orthogonal Challenge output (preferred)
ls -la "$PM_OS_USER/brain/Reasoning/Orthogonal/"

# Check standard PRD output
ls -la "$PM_OS_USER/brain/Products/"
```

### Step 2: Determine Spec Name

If `--spec-name` not provided, derive from PRD title:
- Extract title from PRD H1 header
- Convert to kebab-case
- Truncate to reasonable length

### Step 3: Run Bridge Tool

```bash
python3 "$PM_OS_COMMON/tools/integrations/prd_to_spec.py" \
  --prd "$PRD_PATH" \
  --spec-name "$SPEC_NAME" \
  --repo "$REPO_ALIAS"
```

### Step 4: Report Results

Display the transformation summary:
- PRD title and sections found
- Target spec folder path
- Files created
- Figma links found (if any)

### Step 5: Provide Next Steps

```markdown
## Next Steps

1. Review generated files:
   - `planning/initialization.md` - Initial idea
   - `planning/requirements.md` - Q&A format context

2. Navigate to target repo:
   cd <target-repo-path>

3. Run spec-machine:
   /create-spec
```

## Examples

```bash
# Export Orthogonal Challenge output to mobile-rn
/export-to-spec user/brain/Reasoning/Orthogonal/prd-2026-01-20-feature/v3_final.md --repo mobile-rn

# Export with custom spec name
/export-to-spec Products/PRD_UserAuth_2026-01-20.md --spec-name user-authentication --repo web

# Export to specific subdirectory
/export-to-spec path/to/prd.md --repo mobile-rn --subdir meal-kit

# Interactive repo selection (no --repo)
/export-to-spec path/to/prd.md --spec-name feature-name

# Export a Context Engine feature (using --feature flag)
/export-to-spec mk-feature-recovery --feature --repo mobile-rn

# Export Context Engine feature to specific subdirectory
/export-to-spec mk-feature-recovery --feature --repo mobile-rn --subdir meal-kit

# Export Context Engine feature with custom spec name
/export-to-spec goc-user-auth --feature --spec-name authentication-v2 --repo web
```

## Configuration

Requires `spec_machine` section in `user/config.yaml`:

```yaml
spec_machine:
  enabled: true
  repos:
    mobile-rn: "~/code/acme-corp/mobile-rn"
    web: "~/code/acme-corp/web"
  default_repo: "mobile-rn"
```

## Related Commands

- `/prd` - Generate PRD from discovery
- `/orthogonal-status` - Check orthogonal challenge status
- `/create-spec` - Run in target repo after export
- `/start-feature` - Start a context engine feature
- `/check-feature` - Check context engine feature status
- `/generate-outputs` - Generate PRD from context engine feature

## Context Engine Integration

When exporting a context engine feature (using `--feature` flag), the exporter extracts:

1. **From Context Document:**
   - Problem statement
   - Scope (in/out of scope items)
   - Stakeholders
   - References

2. **From Business Case Track:**
   - Baseline metrics
   - Impact assumptions
   - ROI analysis
   - Executive summary
   - Approval status

3. **From Engineering Track:**
   - Effort estimate (T-shirt size with breakdown)
   - Architecture Decision Records (ADRs)
   - Technical decisions
   - Technical risks and mitigations
   - Dependencies

4. **From Artifacts:**
   - Figma design links
   - Jira epic URL
   - Wireframes URL

The exported files include all this context in the Q&A format expected by spec-machine.

## Beads Reference

- Epic: bd-cd39 (PM-OS to Spec-Machine Integration Bridge)
- Story: bd-90a4 (Create /export-to-spec slash command)
- Story: bd-d15c (Context Engine Output & Integration)
