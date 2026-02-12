# Generate Outputs

Generate PRD and feature summary documents from completed feature tracks.

## Overview

This command generates output artifacts for a feature that has passed the decision gate:
1. Generates a PRD document from the feature context, BC, and engineering data
2. Saves PRD to `user/brain/Products/{Product}/PRD_{Feature_Name}.md`
3. Generates a feature summary document
4. Links back to all source artifacts (context doc, BC doc, ADRs)
5. Updates feature state to OUTPUT_GENERATION complete

## Arguments

- `<slug>` - Feature slug (optional, uses current directory if not specified)
- `--force` - Generate outputs even if decision gate not passed
- `--verbose` - Show detailed generation progress
- `--product-folder <name>` - Override product folder name in brain/Products/

**Examples:**
```
/generate-outputs
/generate-outputs mk-feature-recovery
/generate-outputs mk-feature-recovery --verbose
/generate-outputs mk-feature-recovery --force
```

## Instructions

### Step 1: Find and Load the Feature

Locate the feature folder and load all state including specialized tracks.

```python
import sys
sys.path.insert(0, "$PM_OS_COMMON/tools")
from pathlib import Path
from datetime import datetime
import re
from context_engine import FeatureEngine
from context_engine.feature_state import FeatureState, TrackStatus, FeaturePhase
from context_engine.tracks.business_case import BusinessCaseTrack, BCStatus
from context_engine.tracks.engineering import EngineeringTrack, EngineeringStatus
import config_loader

engine = FeatureEngine()
config = config_loader.get_config()

# If slug provided, use it; otherwise try to detect from cwd
if slug:
    feature_path = engine._find_feature(slug)
    if not feature_path:
        print(f"Error: Feature '{slug}' not found")
        exit(1)
else:
    # Try current directory
    cwd = Path.cwd()
    state_file = cwd / "feature-state.yaml"
    if state_file.exists():
        feature_path = cwd
        state = FeatureState.load(cwd)
        slug = state.slug
    else:
        print("Error: Not in a feature directory. Provide a feature slug.")
        exit(1)

# Load state and specialized tracks
state = FeatureState.load(feature_path)
bc_track = BusinessCaseTrack(feature_path)
eng_track = EngineeringTrack(feature_path)
```

### Step 2: Validate Decision Gate Status

Check that the feature has passed the decision gate (unless --force).

```python
# Check if in OUTPUT_GENERATION phase (decision gate passed)
if state.current_phase != FeaturePhase.OUTPUT_GENERATION and not force_flag:
    print(f"""
{'=' * 70}
 ERROR: Decision Gate Not Passed
{'=' * 70}

 Feature: {state.title}
 Current Phase: {state.current_phase.value}

 The feature must pass the decision gate before generating outputs.

 Run: /decision-gate {slug}

 To force output generation anyway, use:
   /generate-outputs {slug} --force

""")
    exit(1)

# Additional validation checks
validation_errors = []

# Check context track is complete
if state.tracks["context"].status != TrackStatus.COMPLETE:
    validation_errors.append("Context document not complete")

# Check business case is approved
if not bc_track.is_approved and not force_flag:
    validation_errors.append(f"Business case not approved (status: {bc_track.status.value})")

# Check engineering has estimate
if not eng_track.has_estimate and not force_flag:
    validation_errors.append("Engineering estimate not recorded")

if validation_errors and not force_flag:
    print(f"""
{'=' * 70}
 ERROR: Feature Not Ready for Output Generation
{'=' * 70}

 Issues:
""")
    for error in validation_errors:
        print(f"   [!] {error}")
    print(f"""
 Fix these issues or use --force to generate anyway.
""")
    exit(1)
```

### Step 3: Gather Context Document Content

Read the context document to extract problem statement and key information.

```python
def extract_context_doc_content(feature_path: Path, state: FeatureState) -> dict:
    """Extract key content from the context document."""
    context_doc = feature_path / state.context_file
    content = {}

    if not context_doc.exists():
        # Try to find the final version in context-docs/
        context_docs_dir = feature_path / "context-docs"
        if context_docs_dir.exists():
            # Find the latest version
            versions = sorted(context_docs_dir.glob("v*-final.md"), reverse=True)
            if versions:
                context_doc = versions[0]
            else:
                # Try any version
                versions = sorted(context_docs_dir.glob("v*.md"), reverse=True)
                if versions:
                    context_doc = versions[0]

    if context_doc.exists():
        doc_text = context_doc.read_text()

        # Extract Description/Problem Statement
        desc_match = re.search(r'## Description\n+(.*?)(?=\n## |\Z)', doc_text, re.DOTALL)
        if desc_match:
            content["problem_statement"] = desc_match.group(1).strip()

        # Extract Stakeholders
        stake_match = re.search(r'## Stakeholders\n+(.*?)(?=\n## |\Z)', doc_text, re.DOTALL)
        if stake_match:
            content["stakeholders"] = stake_match.group(1).strip()

        # Extract References
        ref_match = re.search(r'## References\n+(.*?)(?=\n## |\Z)', doc_text, re.DOTALL)
        if ref_match:
            content["references"] = ref_match.group(1).strip()

        # Extract title from first line
        title_match = re.match(r'^#\s+(.+?)(?:\s+Context)?\s*$', doc_text, re.MULTILINE)
        if title_match:
            content["title"] = title_match.group(1).strip()

    return content

context_content = extract_context_doc_content(feature_path, state)
```

### Step 4: Gather Business Case Summary

Extract key metrics and approvals from the business case track.

```python
def gather_bc_summary(bc_track: BusinessCaseTrack, feature_path: Path) -> dict:
    """Gather business case summary including metrics and approvals."""
    summary = {
        "status": bc_track.status.value,
        "baseline_metrics": bc_track.assumptions.baseline_metrics,
        "impact_assumptions": bc_track.assumptions.impact_assumptions,
        "investment_estimate": bc_track.assumptions.investment_estimate,
        "roi_analysis": bc_track.assumptions.roi_analysis,
        "approvals": [a.to_dict() for a in bc_track.approvals],
        "is_approved": bc_track.is_approved,
        "content": None,
    }

    # Try to read BC document content
    bc_dir = feature_path / "business-case"
    if bc_dir.exists():
        # Find the latest approved BC or latest version
        bc_files = sorted(bc_dir.glob("bc-v*-approved.md"), reverse=True)
        if not bc_files:
            bc_files = sorted(bc_dir.glob("bc-v*.md"), reverse=True)

        if bc_files:
            bc_doc = bc_files[0]
            summary["bc_file"] = str(bc_doc.relative_to(feature_path))
            bc_text = bc_doc.read_text()

            # Extract executive summary if present
            exec_match = re.search(r'## Executive Summary\n+(.*?)(?=\n## |\Z)', bc_text, re.DOTALL)
            if exec_match:
                summary["executive_summary"] = exec_match.group(1).strip()

    return summary

bc_summary = gather_bc_summary(bc_track, feature_path)
```

### Step 5: Gather Engineering Summary

Extract key information from the engineering track including ADRs and estimate.

```python
def gather_engineering_summary(eng_track: EngineeringTrack, feature_path: Path) -> dict:
    """Gather engineering summary including ADRs, estimate, and risks."""
    summary = {
        "status": eng_track.status.value,
        "estimate": eng_track.estimate.to_dict() if eng_track.estimate else None,
        "adrs": [],
        "risks": [r.to_dict() for r in eng_track.risks],
        "dependencies": [d.to_dict() for d in eng_track.dependencies],
        "decisions": [d.to_dict() for d in eng_track.decisions],
    }

    # Add ADR summaries
    for adr in eng_track.adrs:
        summary["adrs"].append({
            "number": adr.number,
            "title": adr.title,
            "status": adr.status.value,
            "decision": adr.decision[:200] + "..." if len(adr.decision) > 200 else adr.decision,
        })

    return summary

eng_summary = gather_engineering_summary(eng_track, feature_path)
```

### Step 6: Generate PRD Content

Generate the PRD document content combining all track information.

```python
def generate_prd_content(
    state: FeatureState,
    context_content: dict,
    bc_summary: dict,
    eng_summary: dict,
    feature_path: Path,
) -> str:
    """Generate PRD markdown content from feature data."""

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")

    # Get product info
    product_name = state.product_id.replace("-", " ").title()
    product_code = state.product_id.upper()[:3]

    # Format baseline metrics
    baseline_lines = []
    for key, value in bc_summary.get("baseline_metrics", {}).items():
        baseline_lines.append(f"- **{key}**: {value}")
    baseline_text = "\n".join(baseline_lines) if baseline_lines else "- *No baseline metrics recorded*"

    # Format impact assumptions
    impact_lines = []
    for key, value in bc_summary.get("impact_assumptions", {}).items():
        impact_lines.append(f"- **{key}**: {value}")
    impact_text = "\n".join(impact_lines) if impact_lines else "- *No impact assumptions recorded*"

    # Format ROI analysis if present
    roi_section = ""
    if bc_summary.get("roi_analysis"):
        roi_lines = []
        for key, value in bc_summary["roi_analysis"].items():
            roi_lines.append(f"- **{key}**: {value}")
        roi_text = "\n".join(roi_lines)
        roi_section = f"""
### ROI Analysis

{roi_text}
"""

    # Format engineering estimate
    estimate_section = ""
    if eng_summary.get("estimate"):
        est = eng_summary["estimate"]
        estimate_section = f"""
### Effort Estimate

- **Overall**: {est.get('overall', 'TBD')}
- **Confidence**: {est.get('confidence', 'medium')}
"""
        if est.get("breakdown"):
            estimate_section += "\n**Breakdown:**\n"
            for component, size in est["breakdown"].items():
                estimate_section += f"- {component}: {size}\n"

        if est.get("assumptions"):
            estimate_section += "\n**Assumptions:**\n"
            for assumption in est["assumptions"]:
                estimate_section += f"- {assumption}\n"

    # Format ADRs
    adr_section = ""
    if eng_summary.get("adrs"):
        adr_lines = []
        for adr in eng_summary["adrs"]:
            adr_lines.append(f"- **ADR-{adr['number']:03d}**: {adr['title']} ({adr['status']})")
        adr_text = "\n".join(adr_lines)
        adr_section = f"""
### Architecture Decision Records

{adr_text}

*Full ADRs available in `{feature_path.name}/engineering/adrs/`*
"""

    # Format risks
    risks_section = ""
    if eng_summary.get("risks"):
        risk_rows = ["| Risk | Impact | Likelihood | Mitigation |", "|------|--------|------------|------------|"]
        for risk in eng_summary["risks"]:
            mitigation = risk.get("mitigation", "TBD") or "TBD"
            risk_rows.append(f"| {risk['risk'][:50]}... | {risk['impact']} | {risk['likelihood']} | {mitigation[:30]}... |")
        risks_section = f"""
### Technical Risks

{chr(10).join(risk_rows)}
"""

    # Format dependencies
    deps_section = ""
    if eng_summary.get("dependencies"):
        dep_lines = []
        for dep in eng_summary["dependencies"]:
            eta_text = f" (ETA: {dep['eta']})" if dep.get("eta") else ""
            dep_lines.append(f"- **{dep['name']}** ({dep['type']}){eta_text}: {dep.get('description', '')}")
        deps_section = f"""
### Dependencies

{chr(10).join(dep_lines)}
"""

    # Format approvals
    approvals_section = ""
    if bc_summary.get("approvals"):
        approval_rows = ["| Approver | Decision | Date | Type | Reference |", "|----------|----------|------|------|-----------|"]
        for approval in bc_summary["approvals"]:
            decision = "Approved" if approval.get("approved") else "Rejected"
            date = approval.get("date", "")[:10] if approval.get("date") else ""
            ref = approval.get("reference", "")[:30] if approval.get("reference") else ""
            approval_rows.append(f"| {approval.get('approver', '')} | {decision} | {date} | {approval.get('approval_type', '')} | {ref} |")
        approvals_section = f"""
## Stakeholder Approvals

{chr(10).join(approval_rows)}
"""

    # Format references/artifacts
    artifacts_lines = []
    if state.artifacts.get("figma"):
        artifacts_lines.append(f"- **Figma Design**: [{state.title} Designs]({state.artifacts['figma']})")
    if state.artifacts.get("wireframes_url"):
        artifacts_lines.append(f"- **Wireframes**: [Wireframes]({state.artifacts['wireframes_url']})")
    if state.artifacts.get("jira_epic"):
        artifacts_lines.append(f"- **Jira Epic**: [{product_code} Epic]({state.artifacts['jira_epic']})")
    if state.artifacts.get("confluence_page"):
        artifacts_lines.append(f"- **Confluence**: [Documentation]({state.artifacts['confluence_page']})")

    # Add links to source documents
    artifacts_lines.append(f"- **Context Document**: `{state.context_file}`")
    if bc_summary.get("bc_file"):
        artifacts_lines.append(f"- **Business Case**: `{bc_summary['bc_file']}`")

    artifacts_text = "\n".join(artifacts_lines) if artifacts_lines else "- *No artifacts linked*"

    # Format brain entity link
    brain_entity = state.brain_entity or f"[[Entities/{state.title.replace(' ', '_')}]]"

    # Get problem statement
    problem_statement = context_content.get("problem_statement", "*Problem statement to be extracted from context document*")

    # Get executive summary
    executive_summary = bc_summary.get("executive_summary", "*Executive summary to be extracted from business case*")

    # Get stakeholders
    stakeholders = context_content.get("stakeholders", f"- **{state.created_by}** (Owner)")

    # Generate the PRD
    prd_content = f"""---
title: "{state.title}"
type: prd
status: approved
author: {state.created_by}
created: {date_str}
version: 1.0
product: {state.product_id}
organization: {state.organization}
tags: [{state.product_id}, feature, prd]
---

# PRD: {state.title}

**Product:** {product_name}
**Status:** Approved
**Owner:** {state.created_by}
**Created:** {date_str}
**Feature Path:** `user/products/{state.organization}/{state.product_id}/{state.slug}/`

## Executive Summary

{executive_summary}

## Problem Statement

{problem_statement}

## Business Case Summary

### Baseline Metrics

{baseline_text}

### Expected Impact

{impact_text}

### Investment

{bc_summary.get('investment_estimate') or eng_summary.get('estimate', {}).get('overall') or 'TBD'}
{roi_section}
## Engineering Approach
{estimate_section}
{adr_section}
{risks_section}
{deps_section}
{approvals_section}
## References & Artifacts

{artifacts_text}

## Brain Entities

- {brain_entity}

## Source Documents

All source documents are available in the feature folder:

```
user/products/{state.organization}/{state.product_id}/{state.slug}/
+-- {state.context_file}       # Primary context document
+-- feature-state.yaml              # Engine state
+-- context-docs/                   # Context doc versions
+-- business-case/                  # BC documents
+-- engineering/
|   +-- adrs/                       # Architecture Decision Records
```

---
*Generated by Context Creation Engine on {now.isoformat()}*
"""

    return prd_content

prd_content = generate_prd_content(state, context_content, bc_summary, eng_summary, feature_path)
```

### Step 7: Determine PRD Output Location

Determine where to save the PRD based on product and create necessary folders.

```python
def get_prd_output_path(state: FeatureState, config, product_folder_override: str = None) -> Path:
    """Determine the PRD output path in brain/Products/{Product}/."""

    # Get user path from config
    user_path = Path(config.user_path)
    brain_products = user_path / "brain" / "Products"

    # Determine product folder name
    if product_folder_override:
        product_folder = product_folder_override
    else:
        # Convert product_id to proper folder name
        # e.g., "meal-kit" -> "Meal_Kit" or use as-is if folder exists
        product_id = state.product_id

        # Check if folder already exists with various naming conventions
        candidates = [
            product_id,  # meal-kit
            product_id.replace("-", "_"),  # Meal_Kit
            product_id.replace("-", " ").title().replace(" ", "_"),  # Meal_Kit
            product_id.replace("-", " ").title().replace(" ", "-"),  # Meal-Kit
            product_id.upper(),  # MEAL-KIT
        ]

        product_folder = None
        for candidate in candidates:
            candidate_path = brain_products / candidate
            if candidate_path.exists():
                product_folder = candidate
                break

        if not product_folder:
            # Use title case with underscores as default
            product_folder = product_id.replace("-", " ").title().replace(" ", "-")

    # Create folder if it doesn't exist
    product_path = brain_products / product_folder
    product_path.mkdir(parents=True, exist_ok=True)

    # Generate PRD filename
    # Clean feature name for filename
    feature_name = state.title.replace(" ", "_").replace("-", "_")
    feature_name = re.sub(r'[^a-zA-Z0-9_]', '', feature_name)

    prd_filename = f"PRD_{feature_name}.md"

    return product_path / prd_filename

prd_path = get_prd_output_path(state, config, product_folder_override)
```

### Step 8: Save PRD and Feature Summary

Write the PRD and generate a feature summary document.

```python
# Write PRD
prd_path.write_text(prd_content)
print(f"[PASS] PRD saved: {prd_path}")

# Generate feature summary document
def generate_feature_summary(
    state: FeatureState,
    bc_summary: dict,
    eng_summary: dict,
    prd_path: Path,
    feature_path: Path,
) -> str:
    """Generate a concise feature summary document."""

    now = datetime.now()

    # Calculate duration
    duration = now - state.created
    days = duration.days

    # Count artifacts
    artifact_count = sum(1 for v in state.artifacts.values() if v)
    adr_count = len(eng_summary.get("adrs", []))
    approval_count = len(bc_summary.get("approvals", []))
    decision_count = len(state.decisions)

    summary = f"""# Feature Summary: {state.title}

**Generated:** {now.strftime("%Y-%m-%d %H:%M")}
**Duration:** {days} days (from {state.created.strftime("%Y-%m-%d")})

## Quick Stats

| Metric | Value |
|--------|-------|
| Product | {state.product_id} |
| Status | {state.get_derived_status()} |
| Phase | {state.current_phase.value} |
| Artifacts | {artifact_count} |
| ADRs | {adr_count} |
| Approvals | {approval_count} |
| Decisions | {decision_count} |
| Estimate | {eng_summary.get('estimate', {}).get('overall', 'TBD') if eng_summary.get('estimate') else 'TBD'} |

## Track Status

| Track | Status |
|-------|--------|
| Context | {state.tracks['context'].status.value} |
| Design | {state.tracks['design'].status.value} |
| Business Case | {state.tracks['business_case'].status.value} |
| Engineering | {state.tracks['engineering'].status.value} |

## Key Decisions

"""

    # Add recent decisions
    for decision in state.decisions[-5:]:  # Last 5 decisions
        summary += f"- **{decision.phase}**: {decision.decision}\n"

    summary += f"""
## Output Artifacts

- **PRD**: `{prd_path.relative_to(Path(config.user_path))}`
- **Feature Folder**: `user/products/{state.organization}/{state.product_id}/{state.slug}/`
- **Brain Entity**: {state.brain_entity}

## Next Steps

1. Review generated PRD for completeness
2. Run `/export-to-spec {state.slug}` if ready for spec machine
3. Create Jira epic if not already linked

---
*Generated by Context Creation Engine*
"""

    return summary

summary_content = generate_feature_summary(state, bc_summary, eng_summary, prd_path, feature_path)

# Save summary in feature folder
summary_path = feature_path / "feature-summary.md"
summary_path.write_text(summary_content)
print(f"[PASS] Feature summary saved: {summary_path}")
```

### Step 9: Finalize Context Files with Artifact Links

Update all context files with final artifact links using the OutputFinalizer.

```python
from context_engine.output_finalizer import OutputFinalizer, finalize_feature_outputs

# Get Jira epic URL from state if available
jira_epic_url = state.artifacts.get("jira_epic")

# Finalize all context files with artifact links
finalizer = OutputFinalizer()
finalization_result = finalizer.finalize_context_file(
    feature_path=feature_path,
    prd_path=prd_path,
    jira_epic_url=jira_epic_url,
    spec_export_path=None,  # Will be added if /export-to-spec is run later
)

if finalization_result.success:
    print(f"[PASS] Finalized {len(finalization_result.files_updated)} files")
    for link in finalization_result.links_added:
        print(f"       - Added: {link}")
else:
    print(f"[WARN] Finalization completed with errors:")
    for error in finalization_result.errors:
        print(f"       - {error}")
```

### Step 10: Update Feature State

Update the feature state to reflect output generation complete.

```python
# Update feature state
state.record_phase_transition(
    from_phase=FeaturePhase.OUTPUT_GENERATION,
    to_phase=FeaturePhase.COMPLETE,
    metadata={
        "prd_path": str(prd_path),
        "summary_path": str(summary_path),
        "generated_at": datetime.now().isoformat(),
        "finalization": finalization_result.to_dict(),
    }
)

# Record decision
state.record_decision(
    phase="output_generation",
    decision=f"PRD generated and saved to {prd_path.name}",
    rationale="All tracks complete, decision gate passed",
    decided_by=config_loader.get_user_name(),
)

# Save updated state
state.save(feature_path)

# Update context file's action log
engine._log_action(
    feature_path=feature_path,
    action=f"PRD generated: {prd_path.name}",
    status="Done"
)
```

### Step 11: Display Results

Format and display the generation results.

```python
print(f"""
{'=' * 70}
 OUTPUT GENERATION COMPLETE
{'=' * 70}

 Feature: {state.title}
 Product: {state.product_id}

 Generated Files:
   PRD: {prd_path}
   Summary: {summary_path}

 PRD Contents:
   - Executive Summary
   - Problem Statement
   - Business Case Summary (metrics, impact, ROI)
   - Engineering Approach (estimate, ADRs, risks)
   - Stakeholder Approvals
   - References & Artifacts

 Feature State Updated:
   - Phase: {state.current_phase.value}
   - Status: {state.get_derived_status()}

{'=' * 70}
 NEXT STEPS
{'=' * 70}

 1. Review the generated PRD:
    Read: {prd_path}

 2. Export to spec machine (if ready):
    /export-to-spec {prd_path}

 3. Create Jira epic (optional):
    /attach-artifact {slug} jira_epic <EPIC_URL>

 4. Mark feature as complete in Master Sheet

""")
```

## Error Handling

| Error | Resolution |
|-------|------------|
| Feature not found | Provide correct slug or navigate to feature directory |
| Decision gate not passed | Run /decision-gate first or use --force |
| Context document missing | Ensure context track is complete |
| Business case not approved | Complete BC approval workflow |
| Missing engineering estimate | Record estimate via engineering track |
| Cannot write to brain/Products | Check directory permissions |

## Integration Points

- **FeatureEngine**: `common/tools/context_engine/feature_engine.py`
- **FeatureState**: `common/tools/context_engine/feature_state.py`
- **BusinessCaseTrack**: `common/tools/context_engine/tracks/business_case.py`
- **EngineeringTrack**: `common/tools/context_engine/tracks/engineering.py`
- **BidirectionalSync**: `common/tools/context_engine/bidirectional_sync.py`

## PRD Contents (per PRD Section I)

The generated PRD includes:

1. **Problem Statement** - Extracted from context document
2. **Business Case Summary** - Metrics, ROI, investment estimate
3. **Engineering Approach** - Estimate with breakdown, ADRs, risks, dependencies
4. **Stakeholder Approvals** - Full approval record with dates and references
5. **References to Artifacts** - Figma, Jira, Confluence, wireframes
6. **Source Document Links** - Paths to context doc, BC doc, ADRs

## Output Locations

| Output | Location |
|--------|----------|
| PRD | `user/brain/Products/{Product}/PRD_{Feature_Name}.md` |
| Feature Summary | `user/products/{org}/{product}/{feature}/feature-summary.md` |
| Feature State | `user/products/{org}/{product}/{feature}/feature-state.yaml` |

## Execute

Find the feature, validate decision gate status, gather content from context/BC/engineering tracks, generate PRD and summary, save to brain/Products/{Product}/, update feature state to COMPLETE.
