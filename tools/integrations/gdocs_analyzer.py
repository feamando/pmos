#!/usr/bin/env python3
"""
Google Docs Analyzer - Phase 2

Analyzes processed GDocs batches using LLM to extract:
- Decisions made
- Project requirements/scope
- Action items
- Key entities and relationships
- Strategic context

Usage:
    python3 gdocs_analyzer.py [--batch BATCH_FILE] [--all]
    python3 gdocs_analyzer.py --status
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

BASE_DIR = config_loader.get_root_path() / "user" / "brain" / "Inbox" / "GDocs"
PROCESSED_DIR = BASE_DIR / "Processed"
ANALYZED_DIR = BASE_DIR / "Analyzed"
STATE_FILE = BASE_DIR / "analysis_state.json"

# ============================================================================
# ANALYSIS PROMPTS BY DOCUMENT TYPE
# ============================================================================

PROMPT_PRD = """Analyze this Product Requirements Document (PRD) and extract structured information.

## Document
Title: {title}
{content}

---

## Extract the following:

### 1. PROJECT OVERVIEW
- **Name**: Project/feature name
- **Owner**: Product manager or lead
- **Target Date**: Launch or delivery date
- **Summary**: 2-3 sentence description

### 2. REQUIREMENTS
- **Must-Have**: Critical features for launch
- **Nice-to-Have**: Desired but not blocking
- **Out of Scope**: Explicitly excluded

### 3. DECISIONS
Explicit decisions documented in this PRD:
- What was decided
- Rationale/trade-offs
- Who approved

### 4. DEPENDENCIES
- **Technical**: Systems, APIs, infrastructure
- **Team**: Other teams needed
- **External**: Third parties, vendors

### 5. SUCCESS METRICS
- KPIs or metrics to track
- Targets or thresholds

---

Respond with valid JSON only:
```json
{{
  "project_name": "...",
  "owner": "...",
  "target_date": "...",
  "summary": "...",
  "requirements": {{
    "must_have": [...],
    "nice_to_have": [...],
    "out_of_scope": [...]
  }},
  "decisions": [
    {{"what": "...", "rationale": "...", "approved_by": "..."}}
  ],
  "dependencies": {{
    "technical": [...],
    "team": [...],
    "external": [...]
  }},
  "success_metrics": [...],
  "entities": [
    {{"name": "...", "type": "person|project|system|brand", "role": "..."}}
  ]
}}
```
"""

PROMPT_ONE_ON_ONE = """Analyze these 1:1 meeting notes and extract structured information.

## Document
Title: {title}
{content}

---

## Extract the following:

### 1. PARTICIPANTS
- Who attended this 1:1

### 2. ACTION ITEMS
Tasks or commitments made:
- Task description
- Owner
- Due date (if mentioned)

### 3. DECISIONS
Agreements or approvals made:
- What was decided
- Context

### 4. FEEDBACK
Performance feedback, career discussions, or coaching points

### 5. BLOCKERS
Issues raised that need resolution

### 6. KEY TOPICS
Main themes or topics discussed

---

Respond with valid JSON only:
```json
{{
  "participants": [...],
  "action_items": [
    {{"task": "...", "owner": "...", "due": "..."}}
  ],
  "decisions": [
    {{"what": "...", "context": "..."}}
  ],
  "feedback": [...],
  "blockers": [
    {{"issue": "...", "owner": "...", "status": "..."}}
  ],
  "key_topics": [...],
  "entities": [
    {{"name": "...", "type": "person|project|system", "context": "..."}}
  ]
}}
```
"""

PROMPT_MEETING = """Analyze these meeting notes and extract structured information.

## Document
Title: {title}
{content}

---

## Extract the following:

### 1. MEETING INFO
- Purpose of meeting
- Attendees (if listed)
- Date

### 2. DECISIONS
Explicit decisions or agreements made:
- What was decided
- Who was involved
- Context

### 3. ACTION ITEMS
Tasks assigned during the meeting:
- Task
- Owner
- Timeline

### 4. KEY DISCUSSION POINTS
Main topics covered

### 5. BLOCKERS/ISSUES
Problems or blockers raised

### 6. FOLLOW-UPS
Items for future discussion

---

Respond with valid JSON only:
```json
{{
  "meeting_purpose": "...",
  "attendees": [...],
  "date": "...",
  "decisions": [
    {{"what": "...", "who": [...], "context": "..."}}
  ],
  "action_items": [
    {{"task": "...", "owner": "...", "timeline": "..."}}
  ],
  "key_points": [...],
  "blockers": [...],
  "follow_ups": [...],
  "entities": [
    {{"name": "...", "type": "person|project|system", "context": "..."}}
  ]
}}
```
"""

PROMPT_STRATEGY = """Analyze this strategy document and extract structured information.

## Document
Title: {title}
{content}

---

## Extract the following:

### 1. GOALS/OBJECTIVES
What is being targeted:
- Goal description
- Timeframe (Q1, H1, 2026, etc.)
- Owner/team

### 2. KEY RESULTS
Measurable outcomes:
- Metric
- Baseline (if mentioned)
- Target

### 3. PRIORITIES
- What's prioritized/in scope
- What's deprioritized/deferred

### 4. DEPENDENCIES
Cross-team needs or resource constraints

### 5. RISKS
Identified risks and mitigations

### 6. INITIATIVES
Specific projects or workstreams planned

---

Respond with valid JSON only:
```json
{{
  "goals": [
    {{"description": "...", "timeframe": "...", "owner": "..."}}
  ],
  "key_results": [
    {{"metric": "...", "baseline": "...", "target": "..."}}
  ],
  "priorities": {{
    "in_scope": [...],
    "deprioritized": [...]
  }},
  "dependencies": [...],
  "risks": [
    {{"risk": "...", "mitigation": "..."}}
  ],
  "initiatives": [...],
  "entities": [
    {{"name": "...", "type": "person|project|system|brand", "context": "..."}}
  ]
}}
```
"""

PROMPT_SPREADSHEET = """Analyze this spreadsheet content and extract structured information.

## Document
Title: {title}
{content}

---

## Extract the following:

### 1. PURPOSE
What is this spreadsheet tracking?

### 2. KEY DATA POINTS
Important metrics, statuses, or values

### 3. ENTITIES
People, projects, or systems mentioned

### 4. INSIGHTS
Notable patterns or takeaways

---

Respond with valid JSON only:
```json
{{
  "purpose": "...",
  "data_type": "tracker|roadmap|metrics|planning|other",
  "key_data_points": [...],
  "entities": [
    {{"name": "...", "type": "person|project|system|brand", "context": "..."}}
  ],
  "insights": [...]
}}
```
"""

PROMPT_OTHER = """Analyze this document and extract structured information.

## Document
Title: {title}
{content}

---

## Extract the following:

### 1. SUMMARY
2-3 sentence summary of the document

### 2. KEY POINTS
Main takeaways

### 3. DECISIONS
Any decisions or agreements mentioned

### 4. ACTION ITEMS
Any tasks or follow-ups

### 5. ENTITIES
People, projects, systems mentioned with context

---

Respond with valid JSON only:
```json
{{
  "summary": "...",
  "key_points": [...],
  "decisions": [...],
  "action_items": [...],
  "entities": [
    {{"name": "...", "type": "person|project|system|brand", "context": "..."}}
  ]
}}
```
"""

PROMPTS = {
    "prd": PROMPT_PRD,
    "one_on_one": PROMPT_ONE_ON_ONE,
    "meeting": PROMPT_MEETING,
    "strategy": PROMPT_STRATEGY,
    "spreadsheet": PROMPT_SPREADSHEET,
    "other": PROMPT_OTHER,
}

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
        "docs_analyzed": 0,
        "decisions_found": 0,
        "entities_found": 0,
        "actions_found": 0,
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
    print("GDOCS ANALYSIS STATUS")
    print("=" * 60)
    print(f"Started: {state.get('started_at', 'Not started')}")
    print(f"Last Updated: {state.get('last_updated', 'N/A')}")
    print(f"Batches Analyzed: {len(state.get('batches_analyzed', []))}")
    print(f"Documents Analyzed: {state.get('docs_analyzed', 0)}")
    print(f"Decisions Found: {state.get('decisions_found', 0)}")
    print(f"Entities Found: {state.get('entities_found', 0)}")
    print(f"Actions Found: {state.get('actions_found', 0)}")
    print("=" * 60)


# ============================================================================
# PROMPT BUILDING
# ============================================================================


def build_prompt(doc: dict, doc_type: str) -> str:
    """Build analysis prompt for a document."""
    template = PROMPTS.get(doc_type, PROMPT_OTHER)

    # Truncate content if too long
    content = doc.get("content", "")
    if len(content) > 15000:
        content = content[:15000] + "\n\n[TRUNCATED]"

    return template.format(title=doc.get("title", "Unknown"), content=content)


def build_batch_prompt(batch: dict) -> str:
    """Build a combined prompt for a batch of documents."""
    doc_type = batch.get("doc_type", "other")
    documents = batch.get("documents", [])

    prompts = []
    for i, doc in enumerate(documents, 1):
        prompt = f"\n{'='*40}\nDOCUMENT {i}: {doc.get('title', 'Unknown')}\n{'='*40}\n"
        prompt += build_prompt(doc, doc_type)
        prompts.append(prompt)

    header = f"""Analyze the following {len(documents)} {doc_type} documents.
For each document, extract the relevant structured information.

Return a JSON array with one result object per document.
"""

    return header + "\n".join(prompts)


# ============================================================================
# ANALYSIS (Placeholder for LLM integration)
# ============================================================================


def analyze_document_with_llm(doc: dict, doc_type: str, dry_run: bool = False) -> dict:
    """
    Analyze a single document using LLM.

    This is a placeholder - in production, call Claude/Gemini API.
    """
    prompt = build_prompt(doc, doc_type)

    if dry_run:
        print(f"\n[DRY RUN] Would analyze: {doc.get('title', 'Unknown')[:50]}")
        print(f"  Type: {doc_type}")
        print(f"  Prompt length: {len(prompt)} chars")
        return {
            "_dry_run": True,
            "_prompt_length": len(prompt),
        }

    # Placeholder result
    print(f"  Analyzing: {doc.get('title', 'Unknown')[:50]}", file=sys.stderr)
    print(f"    Prompt: {len(prompt)} chars", file=sys.stderr)

    return {
        "_needs_llm": True,
        "_prompt_length": len(prompt),
        "decisions": [],
        "entities": [],
        "action_items": [],
    }


def analyze_batch_with_llm(batch: dict, dry_run: bool = False) -> dict:
    """
    Analyze a batch of documents using LLM.

    Returns combined analysis for all documents in batch.
    """
    doc_type = batch.get("doc_type", "other")
    documents = batch.get("documents", [])

    if dry_run:
        prompt = build_batch_prompt(batch)
        print(f"\n[DRY RUN] Batch: {batch.get('batch_id')}")
        print(f"  Documents: {len(documents)}")
        print(f"  Type: {doc_type}")
        print(f"  Total chars: {batch.get('total_chars', 0):,}")
        print(f"  Prompt length: {len(prompt):,}")
        return {
            "_dry_run": True,
            "_doc_count": len(documents),
            "_prompt_length": len(prompt),
        }

    # Analyze each document
    results = []
    for doc in documents:
        result = analyze_document_with_llm(doc, doc_type, dry_run=False)
        result["doc_title"] = doc.get("title")
        result["doc_id"] = doc.get("doc_id")
        results.append(result)

    return {
        "batch_id": batch.get("batch_id"),
        "doc_type": doc_type,
        "doc_count": len(documents),
        "results": results,
        "_needs_llm": True,
    }


def save_analysis(batch_id: str, analysis: dict, batch_metadata: dict):
    """Save analysis results."""
    ANALYZED_DIR.mkdir(parents=True, exist_ok=True)

    output = {
        "batch_id": batch_id,
        "doc_type": batch_metadata.get("doc_type"),
        "analyzed_at": datetime.now().isoformat(),
        "doc_count": batch_metadata.get("doc_count", 0),
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
        state["docs_analyzed"] = state.get("docs_analyzed", 0) + batch.get(
            "doc_count", 0
        )
        save_state(state)

    # Count extractions
    decisions = sum(len(r.get("decisions", [])) for r in analysis.get("results", []))
    entities = sum(len(r.get("entities", [])) for r in analysis.get("results", []))
    actions = sum(len(r.get("action_items", [])) for r in analysis.get("results", []))

    print(f"  Documents: {batch.get('doc_count', 0)}", file=sys.stderr)
    print(f"  Decisions: {decisions}", file=sys.stderr)
    print(f"  Entities: {entities}", file=sys.stderr)
    print(f"  Actions: {actions}", file=sys.stderr)

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
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("ANALYSIS COMPLETE", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(
            f"Batches analyzed: {len(state.get('batches_analyzed', []))}",
            file=sys.stderr,
        )
        print(f"Documents analyzed: {state.get('docs_analyzed', 0)}", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)

    else:
        print("Specify --batch FILE or --all to analyze", file=sys.stderr)


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Analyze processed GDocs batches with LLM"
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
