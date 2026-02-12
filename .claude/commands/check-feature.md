# Check Feature

Display the status, progress, pending items, and blockers for a feature in the Context Creation Engine.

## Overview

This command provides a comprehensive status report for a feature including:
1. Overall feature status (derived from track completion states)
2. Progress percentage across all tracks
3. Pending items that need attention
4. Blockers that are preventing progress
5. Track-by-track status breakdown

## Arguments

- `<slug>` - Feature slug (optional, uses current directory if not specified)
- `--verbose` - Show detailed information for each track

**Examples:**
```
/check-feature
/check-feature mk-feature-recovery
/check-feature mk-feature-recovery --verbose
```

## Instructions

### Step 1: Find the Feature

Locate the feature folder from slug or current directory.

```python
import sys
sys.path.insert(0, "$PM_OS_COMMON/tools")
from pathlib import Path
from context_engine import FeatureEngine
from context_engine.feature_state import FeatureState, TrackStatus

engine = FeatureEngine()

# If slug provided, use it; otherwise try to detect from cwd
if slug:
    status = engine.check_feature(slug)
    if not status:
        print(f"Error: Feature '{slug}' not found")
else:
    # Try current directory
    cwd = Path.cwd()
    state_file = cwd / "feature-state.yaml"
    if state_file.exists():
        state = FeatureState.load(cwd)
        slug = state.slug
        status = engine.check_feature(slug)
    else:
        print("Error: Not in a feature directory. Provide a feature slug.")
```

### Step 2: Load Track Information

Get detailed status for each track using the specialized track classes.

```python
from context_engine.tracks.business_case import BusinessCaseTrack
from context_engine.tracks.engineering import EngineeringTrack

# Find feature path
feature_path = engine._find_feature(slug)
state = FeatureState.load(feature_path)

# Load specialized tracks for detailed info
bc_track = BusinessCaseTrack(feature_path)
eng_track = EngineeringTrack(feature_path)
```

### Step 3: Calculate Progress

Calculate overall progress as percentage of completed items.

```python
def calculate_progress(state):
    """Calculate progress percentage from track states."""
    track_weights = {
        "context": 30,      # Context docs are foundational
        "design": 20,       # Design track
        "business_case": 25, # BC approval is critical gate
        "engineering": 25,  # Engineering decisions
    }

    progress = 0
    for track_name, track in state.tracks.items():
        weight = track_weights.get(track_name, 25)
        if track.status == TrackStatus.COMPLETE:
            progress += weight
        elif track.status in (TrackStatus.IN_PROGRESS, TrackStatus.PENDING_INPUT, TrackStatus.PENDING_APPROVAL):
            progress += weight * 0.5  # Partial credit

    return int(progress)

progress_pct = calculate_progress(state)
```

### Step 4: Identify Pending Items

Collect all items that need attention across tracks.

```python
def get_pending_items(state, bc_track, eng_track):
    """Get all pending items across tracks."""
    pending = []

    # Context track
    ctx = state.tracks.get("context")
    if ctx.status == TrackStatus.PENDING_INPUT:
        pending.append("[Context] Awaiting user input for context document iteration")
    elif ctx.status == TrackStatus.NOT_STARTED:
        pending.append("[Context] Context document needs to be created")
    elif ctx.status == TrackStatus.IN_PROGRESS:
        v = ctx.current_version or 1
        pending.append(f"[Context] Context document v{v} in progress - needs completion")

    # Design track
    design = state.tracks.get("design")
    if design.status == TrackStatus.NOT_STARTED:
        pending.append("[Design] Design track not started - attach Figma/wireframes")
    elif design.status == TrackStatus.IN_PROGRESS:
        if not state.artifacts.get("figma"):
            pending.append("[Design] Figma URL not attached")
        if not state.artifacts.get("wireframes_url"):
            pending.append("[Design] Wireframes URL not attached")

    # Business Case track
    if bc_track.status.value == "not_started":
        pending.append("[Business Case] Track not started")
    elif bc_track.status.value == "in_progress":
        if not bc_track.assumptions.is_complete:
            pending.append("[Business Case] Baseline metrics and impact assumptions needed")
        else:
            pending.append("[Business Case] BC document ready for submission")
    elif bc_track.status.value == "pending_approval":
        approvers = bc_track.pending_approvers
        if approvers:
            pending.append(f"[Business Case] Awaiting approval from: {', '.join(approvers)}")

    # Engineering track
    if eng_track.status.value == "not_started":
        pending.append("[Engineering] Track not started")
    elif eng_track.status.value == "in_progress":
        if not eng_track.has_estimate:
            pending.append("[Engineering] Engineering estimate needed")
        if not eng_track.adrs and not eng_track.decisions:
            pending.append("[Engineering] No ADRs or technical decisions recorded")
    elif eng_track.status.value == "estimation_pending":
        pending.append("[Engineering] Waiting for engineering estimate")

    return pending

pending_items = get_pending_items(state, bc_track, eng_track)
```

### Step 5: Identify Blockers

Find critical blockers preventing feature progress.

```python
def get_blockers(state, bc_track, eng_track):
    """Identify blockers preventing progress."""
    blockers = []

    # Check for blocked tracks
    for track_name, track in state.tracks.items():
        if track.status == TrackStatus.BLOCKED:
            blockers.append(f"{track_name.replace('_', ' ').title()} track is blocked")

    # Business case rejection is a blocker
    if bc_track.is_rejected:
        blockers.append("Business case was rejected - needs revision")

    # Missing artifacts that block next phase
    current_phase = state.current_phase.value
    if current_phase == "parallel_tracks":
        if state.tracks["context"].status != TrackStatus.COMPLETE:
            blockers.append("Context document must be complete before decision gate")

    if current_phase == "decision_gate":
        if not bc_track.is_approved:
            blockers.append("Business case approval required for decision gate")
        if not eng_track.has_estimate:
            blockers.append("Engineering estimate required for decision gate")

    # Blocking dependencies
    for dep in eng_track.blocking_dependencies:
        blockers.append(f"Dependency blocked: {dep.name}")

    # High-impact unmitigated risks
    for risk in eng_track.pending_risks:
        if risk.impact == "high" and not risk.mitigation:
            blockers.append(f"High-impact risk needs mitigation: {risk.risk[:50]}...")

    return blockers

blockers = get_blockers(state, bc_track, eng_track)
```

### Step 6: Display Results

Format and display the comprehensive status report.

```
# Progress bar helper
def progress_bar(pct, width=20):
    filled = int(width * pct / 100)
    return f"[{'=' * filled}{' ' * (width - filled)}] {pct}%"

# Status emoji mapping
status_indicators = {
    "complete": "[DONE]",
    "in_progress": "[WORKING]",
    "pending_input": "[WAITING]",
    "pending_approval": "[REVIEW]",
    "not_started": "[TODO]",
    "blocked": "[BLOCKED]",
}

# Display output
print(f"""
{'=' * 60}
 FEATURE STATUS: {state.title}
{'=' * 60}

 Slug: {state.slug}
 Product: {state.product_id}
 Phase: {state.current_phase.value}
 Status: {state.get_derived_status()}

 Progress: {progress_bar(progress_pct)}

{'=' * 60}
 TRACKS
{'=' * 60}

 Context:       {status_indicators.get(state.tracks['context'].status.value, '[?]')}
 Design:        {status_indicators.get(state.tracks['design'].status.value, '[?]')}
 Business Case: {status_indicators.get(bc_track.status.value, '[?]')}
 Engineering:   {status_indicators.get(eng_track.status.value, '[?]')}

{'=' * 60}
 PENDING ITEMS ({len(pending_items)})
{'=' * 60}
""")

if pending_items:
    for item in pending_items:
        print(f" - {item}")
else:
    print(" No pending items!")

print(f"""
{'=' * 60}
 BLOCKERS ({len(blockers)})
{'=' * 60}
""")

if blockers:
    for blocker in blockers:
        print(f" [!] {blocker}")
else:
    print(" No blockers!")

# Show artifacts
print(f"""
{'=' * 60}
 ARTIFACTS
{'=' * 60}
""")

for artifact_name, artifact_url in state.artifacts.items():
    if artifact_url:
        print(f" {artifact_name}: {artifact_url}")
    else:
        print(f" {artifact_name}: (not attached)")

print()
print(f"Last activity: {status.last_activity.strftime('%Y-%m-%d %H:%M')}")
```

### Step 7: Verbose Output (Optional)

If --verbose flag is provided, show additional details.

```python
if verbose:
    print(f"""
{'=' * 60}
 DETAILED TRACK INFO
{'=' * 60}

Business Case:
  - Version: {bc_track.current_version or 'N/A'}
  - Assumptions complete: {bc_track.assumptions.is_complete}
  - Required approvers: {bc_track._required_approvers or 'None set'}
  - Approvals: {len(bc_track.approvals)}

Engineering:
  - ADRs: {len(eng_track.adrs)} ({len(eng_track.active_adrs)} active)
  - Decisions: {len(eng_track.decisions)}
  - Estimate: {eng_track.estimate.overall if eng_track.estimate else 'Not set'}
  - Risks: {len(eng_track.risks)} ({len(eng_track.pending_risks)} pending)
  - Dependencies: {len(eng_track.dependencies)} ({len(eng_track.blocking_dependencies)} blocking)

Phase History:
""")
    for entry in state.phase_history:
        completed = entry.completed.strftime('%Y-%m-%d') if entry.completed else 'ongoing'
        print(f"  - {entry.phase}: {entry.entered.strftime('%Y-%m-%d')} -> {completed}")

    print(f"""
Decisions Made: {len(state.decisions)}
""")
    for decision in state.decisions[-3:]:  # Show last 3 decisions
        print(f"  - [{decision.phase}] {decision.decision[:50]}...")
```

## Error Handling

| Error | Resolution |
|-------|------------|
| Feature not found | Provide correct slug or navigate to feature directory |
| No feature-state.yaml | Initialize feature with /start-feature first |
| Track data missing | Some tracks may not be initialized yet |

## Integration Points

- **FeatureEngine**: `common/tools/context_engine/feature_engine.py`
- **FeatureState**: `common/tools/context_engine/feature_state.py`
- **BusinessCaseTrack**: `common/tools/context_engine/tracks/business_case.py`
- **EngineeringTrack**: `common/tools/context_engine/tracks/engineering.py`

## Next Steps After Check

Based on the status report, consider:
- **Pending items**: Address them to move feature forward
- **Blockers**: Resolve blockers before proceeding
- **Low progress**: Focus on incomplete tracks
- **Ready for next phase**: Use appropriate command (e.g., /decision-gate)

## Execute

Find the feature, load all track data, calculate progress, identify pending items and blockers, then display comprehensive status report.
