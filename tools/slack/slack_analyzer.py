#!/usr/bin/env python3
"""
Slack Message Analyzer - Phase 3

Analyzes processed Slack batches using LLM to extract:
- Decisions made
- Entities mentioned
- Blockers/issues
- Action items
- Key context

Usage:
    python3 slack_analyzer.py [--batch BATCH_FILE] [--all]
    python3 slack_analyzer.py --status
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = config_loader.get_root_path() / "user" / "brain" / "Inbox" / "Slack"
PROCESSED_DIR = BASE_DIR / "Processed"
ANALYZED_DIR = BASE_DIR / "Analyzed"
STATE_FILE = BASE_DIR / "analysis_state.json"

# Analysis prompt template
ANALYSIS_PROMPT = """Analyze these Slack messages from #{channel_name} and extract structured information.

## Messages
{messages}

---

## Extract the following:

### 1. DECISIONS
Explicit agreements, choices, or approvals made. Look for phrases like "decided", "agreed", "approved", "let's go with", "confirmed".

For each decision:
- **What**: The specific decision made
- **Who**: People involved in making/approving it
- **Date**: When it was made (from message timestamp)
- **Context**: Why this decision was made
- **Confidence**: high/medium/low (how explicit was this decision?)

### 2. ENTITIES
People, projects, systems, or squads mentioned that should be tracked.

For each entity:
- **Name**: Entity name (normalize spelling)
- **Type**: person / project / system / squad / brand / metric
- **Context**: How/why they were mentioned
- **Relationships**: Other entities they're connected to

### 3. BLOCKERS
Issues blocking progress, dependencies, or problems raised.

For each blocker:
- **Description**: What is blocked and why
- **Owner**: Who owns resolving this
- **Status**: active / resolved / unknown
- **Impact**: What's affected by this blocker

### 4. ACTION ITEMS
Commitments or tasks that someone agreed to do.

For each action:
- **Task**: What needs to be done
- **Owner**: Who committed to doing it
- **Due**: Deadline if mentioned (or "unspecified")
- **Status**: pending / done / unknown

### 5. KEY CONTEXT
Important background information, strategic context, or decisions-in-progress.

For each piece of context:
- **Topic**: What this is about
- **Summary**: 1-2 sentence summary
- **Relevance**: Why this matters for the Brain

---

Respond with valid JSON only:
```json
{{
  "decisions": [...],
  "entities": [...],
  "blockers": [...],
  "action_items": [...],
  "key_context": [...],
  "summary": "1-2 sentence summary of this batch"
}}
```
"""

# ============================================================================
# STATE MANAGEMENT
# ============================================================================


def load_state() -> dict:
    """Load analysis state from file."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "started_at": None,
        "last_updated": None,
        "batches_analyzed": [],
        "total_decisions": 0,
        "total_entities": 0,
        "total_blockers": 0,
        "total_actions": 0,
    }


def save_state(state: dict):
    """Save analysis state to file."""
    state["last_updated"] = datetime.now().isoformat()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def print_status(state: dict):
    """Print current analysis status."""
    print("=" * 60)
    print("SLACK ANALYSIS STATUS")
    print("=" * 60)
    print(f"Started: {state.get('started_at', 'Not started')}")
    print(f"Last Updated: {state.get('last_updated', 'N/A')}")
    print(f"Batches Analyzed: {len(state.get('batches_analyzed', []))}")
    print(f"Decisions Found: {state.get('total_decisions', 0)}")
    print(f"Entities Found: {state.get('total_entities', 0)}")
    print(f"Blockers Found: {state.get('total_blockers', 0)}")
    print(f"Actions Found: {state.get('total_actions', 0)}")
    print("=" * 60)


# ============================================================================
# MESSAGE FORMATTING
# ============================================================================


def format_messages_for_prompt(batch: dict) -> str:
    """Format batch messages for LLM prompt."""
    lines = []

    for msg in batch.get("messages", []):
        # Header
        ts = msg.get("ts", "")
        try:
            dt = datetime.fromtimestamp(float(ts))
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            time_str = ts

        user_name = msg.get("user_name", msg.get("user", "Unknown"))
        tags = msg.get("tags", [])
        tag_str = f" [{', '.join(tags)}]" if tags else ""

        lines.append(f"**{user_name}** ({time_str}){tag_str}")
        lines.append(msg.get("text", ""))

        # Thread replies
        for reply in msg.get("thread_replies", []):
            reply_user = reply.get("user_name", reply.get("user", "Unknown"))
            try:
                reply_dt = datetime.fromtimestamp(float(reply.get("ts", "")))
                reply_time = reply_dt.strftime("%H:%M")
            except (ValueError, TypeError):
                reply_time = ""

            lines.append(
                f"  ↳ **{reply_user}** ({reply_time}): {reply.get('text', '')}"
            )

        lines.append("")

    return "\n".join(lines)


def build_prompt(batch: dict) -> str:
    """Build the analysis prompt for a batch."""
    channel_name = batch.get("channel_name", "unknown")
    messages_text = format_messages_for_prompt(batch)

    return ANALYSIS_PROMPT.format(channel_name=channel_name, messages=messages_text)


# ============================================================================
# ANALYSIS (Placeholder for LLM integration)
# ============================================================================


def analyze_batch_with_llm(batch: dict, dry_run: bool = False) -> dict:
    """
    Analyze a batch using LLM.

    This is a placeholder that shows the prompt structure.
    In production, this would call Claude/Gemini API.
    """
    prompt = build_prompt(batch)

    if dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN - Would send this prompt:")
        print("=" * 60)
        print(prompt[:2000] + "..." if len(prompt) > 2000 else prompt)
        print("=" * 60 + "\n")

        # Return mock result
        return {
            "decisions": [],
            "entities": [],
            "blockers": [],
            "action_items": [],
            "key_context": [],
            "summary": "[DRY RUN] No analysis performed",
            "_prompt_length": len(prompt),
            "_message_count": batch.get("message_count", 0),
        }

    # TODO: Implement actual LLM call
    # For now, return structure showing what would be extracted
    print(f"  Prompt length: {len(prompt)} chars", file=sys.stderr)
    print(f"  Messages: {batch.get('message_count', 0)}", file=sys.stderr)

    # Placeholder - in real implementation, call LLM here
    # response = call_llm(prompt)
    # return parse_llm_response(response)

    return {
        "decisions": [],
        "entities": [],
        "blockers": [],
        "action_items": [],
        "key_context": [],
        "summary": "[PLACEHOLDER] LLM analysis not yet implemented",
        "_prompt_length": len(prompt),
        "_needs_llm": True,
    }


def save_analysis(batch_id: str, analysis: dict, batch_metadata: dict):
    """Save analysis results."""
    ANALYZED_DIR.mkdir(parents=True, exist_ok=True)

    output = {
        "batch_id": batch_id,
        "channel_name": batch_metadata.get("channel_name"),
        "channel_id": batch_metadata.get("channel_id"),
        "analyzed_at": datetime.now().isoformat(),
        "message_count": batch_metadata.get("message_count", 0),
        **analysis,
    }

    filename = f"analysis_{batch_id}.json"
    filepath = ANALYZED_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return filepath


# ============================================================================
# MAIN PIPELINE
# ============================================================================


def find_batches() -> list:
    """Find all processed batch files."""
    if not PROCESSED_DIR.exists():
        return []

    return sorted(PROCESSED_DIR.glob("batch_*.json"))


def analyze_single_batch(batch_file: Path, state: dict, dry_run: bool = False):
    """Analyze a single batch file."""
    print(f"\nAnalyzing: {batch_file.name}", file=sys.stderr)

    with open(batch_file, "r", encoding="utf-8") as f:
        batch = json.load(f)

    batch_id = batch.get("batch_id", batch_file.stem)

    # Analyze
    analysis = analyze_batch_with_llm(batch, dry_run=dry_run)

    if not dry_run:
        # Save results
        filepath = save_analysis(batch_id, analysis, batch)
        print(f"  Saved: {filepath.name}", file=sys.stderr)

        # Update state
        state["batches_analyzed"].append(str(batch_file))
        state["total_decisions"] += len(analysis.get("decisions", []))
        state["total_entities"] += len(analysis.get("entities", []))
        state["total_blockers"] += len(analysis.get("blockers", []))
        state["total_actions"] += len(analysis.get("action_items", []))
        save_state(state)

    # Summary
    print(f"  Decisions: {len(analysis.get('decisions', []))}", file=sys.stderr)
    print(f"  Entities: {len(analysis.get('entities', []))}", file=sys.stderr)
    print(f"  Blockers: {len(analysis.get('blockers', []))}", file=sys.stderr)
    print(f"  Actions: {len(analysis.get('action_items', []))}", file=sys.stderr)

    return analysis


def run_analysis(
    batch_file: Optional[str] = None,
    analyze_all: bool = False,
    dry_run: bool = False,
    resume: bool = True,
):
    """Run the analysis pipeline."""
    state = load_state()

    if not state.get("started_at"):
        state["started_at"] = datetime.now().isoformat()
        save_state(state)

    if batch_file:
        # Analyze single batch
        batch_path = Path(batch_file)
        if not batch_path.exists():
            batch_path = PROCESSED_DIR / batch_file
        if not batch_path.exists():
            print(f"Batch file not found: {batch_file}", file=sys.stderr)
            return

        analyze_single_batch(batch_path, state, dry_run)

    elif analyze_all:
        # Analyze all batches
        batches = find_batches()
        print(f"Found {len(batches)} batch files", file=sys.stderr)

        # Filter already analyzed
        if resume:
            analyzed_set = set(state.get("batches_analyzed", []))
            batches = [b for b in batches if str(b) not in analyzed_set]
            print(f"Remaining after resume filter: {len(batches)}", file=sys.stderr)

        if not batches:
            print("No new batches to analyze", file=sys.stderr)
            return

        for batch_path in batches:
            analyze_single_batch(batch_path, state, dry_run)

        # Final summary
        print("\n" + "=" * 60, file=sys.stderr)
        print("ANALYSIS COMPLETE", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(
            f"Batches analyzed: {len(state.get('batches_analyzed', []))}",
            file=sys.stderr,
        )
        print(f"Total decisions: {state.get('total_decisions', 0)}", file=sys.stderr)
        print(f"Total entities: {state.get('total_entities', 0)}", file=sys.stderr)
        print(f"Total blockers: {state.get('total_blockers', 0)}", file=sys.stderr)
        print(f"Total actions: {state.get('total_actions', 0)}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

    else:
        print("Specify --batch FILE or --all to analyze", file=sys.stderr)


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Analyze processed Slack batches with LLM"
    )
    parser.add_argument("--batch", help="Single batch file to analyze")
    parser.add_argument(
        "--all", action="store_true", help="Analyze all unprocessed batches"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show prompts without calling LLM"
    )
    parser.add_argument(
        "--no-resume", action="store_true", help="Re-analyze all batches"
    )
    parser.add_argument(
        "--status", action="store_true", help="Show analysis status and exit"
    )

    args = parser.parse_args()

    if args.status:
        state = load_state()
        print_status(state)
        return

    run_analysis(
        batch_file=args.batch,
        analyze_all=args.all,
        dry_run=args.dry_run,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
