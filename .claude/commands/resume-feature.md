# Resume Feature

Resume a paused or inactive feature in the Context Creation Engine, restoring state and detecting changes since the last session.

## Overview

This command is used to resume work on a feature that was previously started but not completed. It:
1. Loads feature state from feature-state.yaml
2. Restores engine context (current phase, pending items, track states)
3. Detects changes since last session (modified files, new artifacts, external updates)
4. Shows a summary of where the feature was left off
5. Suggests next actions based on current state

## Arguments

- `<slug>` - Feature slug (optional, uses current directory if not specified)
- `--sync` - Force sync with Master Sheet before resuming
- `--verbose` - Show detailed change detection information

**Examples:**
```
/resume-feature
/resume-feature mk-feature-recovery
/resume-feature mk-feature-recovery --sync
/resume-feature --verbose
```

## Instructions

### Step 1: Find and Load Feature State

Locate the feature folder and load the feature-state.yaml.

```python
import sys
sys.path.insert(0, "$PM_OS_COMMON/tools")
from pathlib import Path
from datetime import datetime
from context_engine import FeatureEngine
from context_engine.feature_state import FeatureState, FeaturePhase, TrackStatus
from context_engine.bidirectional_sync import BidirectionalSync

engine = FeatureEngine()

# If slug provided, use it; otherwise try to detect from cwd
if slug:
    feature_path = engine._find_feature(slug)
    if not feature_path:
        print(f"Error: Feature '{slug}' not found")
        return
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
        return

# Load full state
state = FeatureState.load(feature_path)
if not state:
    print(f"Error: Could not load feature state from {feature_path}")
    return
```

### Step 2: Detect Changes Since Last Session

Check for modifications since the feature was last worked on.

```python
import os
from datetime import datetime

def detect_changes(feature_path, state):
    """Detect changes since last session."""
    changes = {
        "modified_files": [],
        "new_artifacts": [],
        "context_changes": [],
        "master_sheet_changes": [],
        "summary": []
    }

    # Get last activity timestamp from phase history
    if state.phase_history:
        last_entry = state.phase_history[-1]
        last_activity = last_entry.completed or last_entry.entered
    else:
        last_activity = state.created

    # Check file modification times
    files_to_check = [
        (feature_path / state.context_file, "Context file"),
        (feature_path / "feature-state.yaml", "Feature state"),
    ]

    # Add context docs
    context_docs = feature_path / "context-docs"
    if context_docs.exists():
        for doc in context_docs.glob("*.md"):
            files_to_check.append((doc, f"Context doc: {doc.name}"))

    # Add business case docs
    bc_folder = feature_path / "business-case"
    if bc_folder.exists():
        for doc in bc_folder.glob("*.md"):
            files_to_check.append((doc, f"Business case: {doc.name}"))

    # Add engineering docs (ADRs)
    eng_folder = feature_path / "engineering"
    if eng_folder.exists():
        for doc in eng_folder.glob("**/*.md"):
            files_to_check.append((doc, f"Engineering: {doc.name}"))

    # Check modification times
    for file_path, label in files_to_check:
        if file_path.exists():
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if mtime > last_activity:
                changes["modified_files"].append({
                    "file": file_path.name,
                    "label": label,
                    "modified": mtime.strftime("%Y-%m-%d %H:%M"),
                    "delta": _format_time_delta(mtime - last_activity)
                })

    # Check for new artifacts
    for artifact_name, artifact_url in state.artifacts.items():
        if artifact_url:
            # This artifact was added since state was created
            changes["new_artifacts"].append({
                "type": artifact_name,
                "url": artifact_url
            })

    # Check if context file was modified externally
    context_file = feature_path / state.context_file
    if context_file.exists():
        content = context_file.read_text()

        # Parse status from context file
        import re
        status_match = re.search(r'\*\*Status:\*\*\s*(.+)', content)
        if status_match:
            context_status = status_match.group(1).strip()
            derived_status = state.get_derived_status()
            if context_status != derived_status:
                changes["context_changes"].append({
                    "field": "status",
                    "context_value": context_status,
                    "state_value": derived_status,
                    "message": f"Status mismatch: context file shows '{context_status}', state tracks derive '{derived_status}'"
                })

    # Generate summary
    if changes["modified_files"]:
        changes["summary"].append(f"{len(changes['modified_files'])} files modified since last session")
    if changes["context_changes"]:
        changes["summary"].append(f"{len(changes['context_changes'])} context changes detected")
    if not changes["summary"]:
        changes["summary"].append("No changes detected since last session")

    return changes

def _format_time_delta(delta):
    """Format a timedelta for display."""
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds} seconds ago"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif total_seconds < 86400:
        hours = total_seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = total_seconds // 86400
        return f"{days} day{'s' if days != 1 else ''} ago"

changes = detect_changes(feature_path, state)
```

### Step 3: Optional Master Sheet Sync

If --sync flag is provided, sync with Master Sheet to detect external updates.

```python
if sync_flag:
    sync = BidirectionalSync()

    # Try to sync from Master Sheet
    sync_result = sync.sync_from_master_sheet(
        feature_name=state.title,
        product_id=state.product_id,
        feature_path=feature_path
    )

    if sync_result.success:
        changes["master_sheet_changes"] = sync_result.fields_updated
        if sync_result.fields_updated:
            changes["summary"].append(f"Synced {len(sync_result.fields_updated)} fields from Master Sheet")
    else:
        print(f"Note: Master Sheet sync failed: {sync_result.errors}")
```

### Step 4: Calculate Progress and Pending Items

Get comprehensive status information.

```python
from context_engine.tracks.business_case import BusinessCaseTrack
from context_engine.tracks.engineering import EngineeringTrack

# Load specialized tracks
bc_track = BusinessCaseTrack(feature_path)
eng_track = EngineeringTrack(feature_path)

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
        pending.append(f"[Context] Context document v{v} in progress")

    # Design track
    design = state.tracks.get("design")
    if design.status == TrackStatus.NOT_STARTED:
        pending.append("[Design] Design track not started")
    elif design.status == TrackStatus.IN_PROGRESS:
        if not state.artifacts.get("figma"):
            pending.append("[Design] Figma URL not attached")

    # Business Case track
    if bc_track.status.value == "not_started":
        pending.append("[Business Case] Track not started")
    elif bc_track.status.value == "in_progress":
        if not bc_track.assumptions.is_complete:
            pending.append("[Business Case] Baseline metrics and impact assumptions needed")
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

    return pending

progress_pct = calculate_progress(state)
pending_items = get_pending_items(state, bc_track, eng_track)
```

### Step 5: Determine Suggested Next Actions

Based on current phase and pending items, suggest what to do next.

```python
def get_suggested_actions(state, pending_items, bc_track, eng_track):
    """Generate suggested next actions based on current state."""
    suggestions = []

    phase = state.current_phase

    # Phase-based suggestions
    if phase == FeaturePhase.INITIALIZATION:
        suggestions.append("Start signal analysis with /analyze-signals")
        suggestions.append("Or create initial context document with /create-context-doc")

    elif phase == FeaturePhase.SIGNAL_ANALYSIS:
        suggestions.append("Review and select relevant signals/insights")
        suggestions.append("Then move to context document creation")

    elif phase == FeaturePhase.CONTEXT_DOC:
        ctx_track = state.tracks.get("context")
        if ctx_track.status == TrackStatus.PENDING_INPUT:
            suggestions.append("Review context document and provide feedback")
            suggestions.append("Approve, reject, or request changes")
        else:
            version = ctx_track.current_version or 1
            suggestions.append(f"Continue iterating context document (currently v{version})")

    elif phase == FeaturePhase.PARALLEL_TRACKS:
        # Check each track and suggest based on status
        if state.tracks["context"].status != TrackStatus.COMPLETE:
            suggestions.append("Complete context document review")

        if state.tracks["design"].status == TrackStatus.NOT_STARTED:
            suggestions.append("Start design track: attach Figma/wireframes")

        if bc_track.status.value == "not_started":
            suggestions.append("Start business case track")
        elif bc_track.status.value == "in_progress":
            suggestions.append("Complete business case assumptions and submit for approval")
        elif bc_track.status.value == "pending_approval":
            suggestions.append("Follow up on business case approval")

        if eng_track.status.value == "not_started":
            suggestions.append("Start engineering track")
        elif eng_track.status.value == "in_progress":
            if not eng_track.has_estimate:
                suggestions.append("Provide engineering estimate")
            if not eng_track.adrs:
                suggestions.append("Document architectural decisions (ADRs)")

    elif phase == FeaturePhase.DECISION_GATE:
        suggestions.append("Review all tracks and make final decision")
        suggestions.append("Use /decision-gate to proceed")

    elif phase == FeaturePhase.OUTPUT_GENERATION:
        suggestions.append("Generate PRD with /generate-outputs")
        suggestions.append("Export to spec machine with /export-to-spec")

    # Add generic suggestions if nothing specific
    if not suggestions:
        if pending_items:
            suggestions.append(f"Address {len(pending_items)} pending items")
        else:
            suggestions.append("Feature appears complete - consider archiving")

    return suggestions

suggested_actions = get_suggested_actions(state, pending_items, bc_track, eng_track)
```

### Step 6: Display Resume Summary

Format and display comprehensive resume information.

```python
# Status indicators
status_indicators = {
    "complete": "[DONE]",
    "in_progress": "[WORKING]",
    "pending_input": "[WAITING]",
    "pending_approval": "[REVIEW]",
    "not_started": "[TODO]",
    "blocked": "[BLOCKED]",
}

# Progress bar helper
def progress_bar(pct, width=20):
    filled = int(width * pct / 100)
    return f"[{'=' * filled}{' ' * (width - filled)}] {pct}%"

# Calculate time since last activity
if state.phase_history:
    last_entry = state.phase_history[-1]
    last_activity = last_entry.completed or last_entry.entered
else:
    last_activity = state.created

time_since = datetime.now() - last_activity
if time_since.days > 0:
    time_str = f"{time_since.days} day{'s' if time_since.days != 1 else ''}"
elif time_since.seconds >= 3600:
    hours = time_since.seconds // 3600
    time_str = f"{hours} hour{'s' if hours != 1 else ''}"
else:
    minutes = time_since.seconds // 60
    time_str = f"{minutes} minute{'s' if minutes != 1 else ''}"

# Display output
print(f"""
{'=' * 60}
 RESUME FEATURE: {state.title}
{'=' * 60}

 Slug: {state.slug}
 Product: {state.product_id}
 Created: {state.created.strftime('%Y-%m-%d')}
 Last Activity: {last_activity.strftime('%Y-%m-%d %H:%M')} ({time_str} ago)

 Current Phase: {state.current_phase.value.replace('_', ' ').title()}
 Derived Status: {state.get_derived_status()}
 Progress: {progress_bar(progress_pct)}

{'=' * 60}
 TRACK STATUS
{'=' * 60}

 Context:       {status_indicators.get(state.tracks['context'].status.value, '[?]')}
 Design:        {status_indicators.get(state.tracks['design'].status.value, '[?]')}
 Business Case: {status_indicators.get(bc_track.status.value, '[?]')}
 Engineering:   {status_indicators.get(eng_track.status.value, '[?]')}
""")

# Show changes if any
if changes["modified_files"] or changes["context_changes"]:
    print(f"""
{'=' * 60}
 CHANGES DETECTED
{'=' * 60}
""")
    for change_summary in changes["summary"]:
        print(f" - {change_summary}")

    if verbose and changes["modified_files"]:
        print("\n Modified Files:")
        for f in changes["modified_files"]:
            print(f"   - {f['label']}: modified {f['delta']}")

    if changes["context_changes"]:
        print("\n Context Discrepancies:")
        for c in changes["context_changes"]:
            print(f"   - {c['message']}")

# Show pending items
print(f"""
{'=' * 60}
 PENDING ITEMS ({len(pending_items)})
{'=' * 60}
""")

if pending_items:
    for item in pending_items:
        print(f" - {item}")
else:
    print(" No pending items!")

# Show suggested actions
print(f"""
{'=' * 60}
 SUGGESTED NEXT ACTIONS
{'=' * 60}
""")

for i, action in enumerate(suggested_actions, 1):
    print(f" {i}. {action}")

# Show artifacts
if any(state.artifacts.values()):
    print(f"""
{'=' * 60}
 LINKED ARTIFACTS
{'=' * 60}
""")
    for artifact_name, artifact_url in state.artifacts.items():
        if artifact_url:
            print(f" {artifact_name}: {artifact_url}")

# Footer
print(f"""
{'=' * 60}
 Feature folder: {feature_path}
{'=' * 60}
""")
```

### Step 7: Verbose Output (Optional)

If --verbose flag is provided, show additional details.

```python
if verbose:
    print(f"""
{'=' * 60}
 DETAILED INFORMATION
{'=' * 60}

Phase History:
""")
    for entry in state.phase_history:
        completed = entry.completed.strftime('%Y-%m-%d %H:%M') if entry.completed else 'ongoing'
        print(f"  - {entry.phase}: {entry.entered.strftime('%Y-%m-%d %H:%M')} -> {completed}")
        if entry.metadata:
            for key, value in entry.metadata.items():
                print(f"      {key}: {value}")

    print(f"""
Recent Decisions: {len(state.decisions)}
""")
    for decision in state.decisions[-5:]:  # Show last 5 decisions
        print(f"  - [{decision.phase}] {decision.decision[:60]}...")
        print(f"    By: {decision.decided_by} on {decision.date.strftime('%Y-%m-%d')}")

    if bc_track.status.value != "not_started":
        print(f"""
Business Case Details:
  Version: {bc_track.current_version or 'N/A'}
  Assumptions complete: {bc_track.assumptions.is_complete}
  Approvals: {len(bc_track.approvals)}
""")

    if eng_track.status.value != "not_started":
        print(f"""
Engineering Details:
  ADRs: {len(eng_track.adrs)} ({len(eng_track.active_adrs)} active)
  Decisions: {len(eng_track.decisions)}
  Estimate: {eng_track.estimate.overall if eng_track.estimate else 'Not set'}
  Risks: {len(eng_track.risks)} ({len(eng_track.pending_risks)} pending)
""")
```

## Error Handling

| Error | Resolution |
|-------|------------|
| Feature not found | Provide correct slug or navigate to feature directory |
| No feature-state.yaml | Initialize feature with /start-feature first |
| Track data missing | Some tracks may not be initialized yet |
| Master Sheet sync failed | Check Google API credentials and connectivity |

## Integration Points

- **FeatureEngine**: `common/tools/context_engine/feature_engine.py`
- **FeatureState**: `common/tools/context_engine/feature_state.py`
- **BidirectionalSync**: `common/tools/context_engine/bidirectional_sync.py`
- **BusinessCaseTrack**: `common/tools/context_engine/tracks/business_case.py`
- **EngineeringTrack**: `common/tools/context_engine/tracks/engineering.py`

## Next Steps After Resume

Based on the resume summary, consider:
- **Pending items**: Address them to move feature forward
- **Suggested actions**: Follow the recommended next steps
- **Changes detected**: Review and reconcile if needed
- **Stale feature**: If inactive for long, consider updating priorities

## Execute

Find the feature, load state, detect changes since last session, calculate progress, determine suggested actions, and display comprehensive resume summary.
