#!/usr/bin/env python3
"""
Batch LLM Analyzer

Analyzes document batches using AWS Bedrock Claude.
Supports GDocs, Slack, GitHub, and Jira data with incremental saves.

Usage:
    python3 batch_llm_analyzer.py --source gdocs [--batch BATCH_FILE] [--all] [--dry-run]
    python3 batch_llm_analyzer.py --source slack [--batch BATCH_FILE] [--all] [--dry-run]
    python3 batch_llm_analyzer.py --source github [--batch BATCH_FILE] [--all] [--dry-run]
    python3 batch_llm_analyzer.py --source jira [--batch BATCH_FILE] [--all] [--dry-run]
    python3 batch_llm_analyzer.py --status
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import boto3

# Add parent directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# ============================================================================
# CONFIGURATION
# ============================================================================

BRAIN_DIR = config_loader.get_root_path() / "user" / "brain" / "Inbox"
GDOCS_DIR = BRAIN_DIR / "GDocs"
SLACK_DIR = BRAIN_DIR / "Slack"
JIRA_DIR = BRAIN_DIR / "Jira"

# AWS Bedrock configuration
AWS_REGION = os.getenv("AWS_REGION", "eu-west-1")
AWS_PROFILE = os.getenv("AWS_PROFILE", "bedrock")
MODEL_ID = os.getenv("ANTHROPIC_MODEL", "eu.anthropic.claude-opus-4-6-v1")

# Rate limiting
REQUESTS_PER_MINUTE = 10
REQUEST_DELAY = 60 / REQUESTS_PER_MINUTE  # 6 seconds between requests

# ============================================================================
# PROMPTS
# ============================================================================

GDOCS_PROMPTS = {
    "prd": """Analyze this Product Requirements Document and extract structured information.

## Document
Title: {title}
Content:
{content}

---

Extract and return valid JSON with:
{{
  "project_name": "Name of the project",
  "owner": "Product manager or lead",
  "target_date": "Launch date if mentioned",
  "summary": "2-3 sentence description",
  "requirements": {{
    "must_have": ["list of must-have features"],
    "nice_to_have": ["list of nice-to-have features"],
    "out_of_scope": ["list of excluded items"]
  }},
  "decisions": [
    {{"what": "decision", "rationale": "why", "approved_by": "who"}}
  ],
  "dependencies": {{
    "technical": ["systems, APIs"],
    "team": ["other teams"],
    "external": ["vendors, third parties"]
  }},
  "success_metrics": ["KPIs to track"],
  "entities": [
    {{"name": "entity name", "type": "person|project|system|brand", "role": "how mentioned"}}
  ]
}}""",
    "one_on_one": """Analyze these 1:1 meeting notes and extract structured information.

## Document
Title: {title}
Content:
{content}

---

Extract and return valid JSON with:
{{
  "participants": ["list of attendees"],
  "action_items": [
    {{"task": "what", "owner": "who", "due": "when"}}
  ],
  "decisions": [
    {{"what": "decision", "context": "background"}}
  ],
  "feedback": ["performance/career discussions"],
  "blockers": [
    {{"issue": "description", "owner": "who owns it", "status": "active|resolved"}}
  ],
  "key_topics": ["main themes discussed"],
  "entities": [
    {{"name": "entity", "type": "person|project|system", "context": "how mentioned"}}
  ]
}}""",
    "meeting": """Analyze these meeting notes and extract structured information.

## Document
Title: {title}
Content:
{content}

---

Extract and return valid JSON with:
{{
  "meeting_purpose": "why the meeting was held",
  "attendees": ["list of participants"],
  "date": "meeting date if mentioned",
  "decisions": [
    {{"what": "decision", "who": ["involved"], "context": "background"}}
  ],
  "action_items": [
    {{"task": "what", "owner": "who", "timeline": "when"}}
  ],
  "key_points": ["main discussion topics"],
  "blockers": ["issues raised"],
  "follow_ups": ["items for future discussion"],
  "entities": [
    {{"name": "entity", "type": "person|project|system", "context": "how mentioned"}}
  ]
}}""",
    "strategy": """Analyze this strategy document and extract structured information.

## Document
Title: {title}
Content:
{content}

---

Extract and return valid JSON with:
{{
  "goals": [
    {{"description": "goal", "timeframe": "Q1/H1/2026", "owner": "team/person"}}
  ],
  "key_results": [
    {{"metric": "what to measure", "baseline": "current", "target": "goal"}}
  ],
  "priorities": {{
    "in_scope": ["prioritized items"],
    "deprioritized": ["deferred items"]
  }},
  "dependencies": ["cross-team needs"],
  "risks": [
    {{"risk": "description", "mitigation": "plan"}}
  ],
  "initiatives": ["specific projects planned"],
  "entities": [
    {{"name": "entity", "type": "person|project|system|brand", "context": "how mentioned"}}
  ]
}}""",
    "spreadsheet": """Analyze this spreadsheet content and extract key information.

## Document
Title: {title}
Content:
{content}

---

Extract and return valid JSON with:
{{
  "purpose": "what this spreadsheet tracks",
  "data_type": "tracker|roadmap|metrics|planning|other",
  "key_data_points": ["important metrics or values"],
  "entities": [
    {{"name": "entity", "type": "person|project|system|brand", "context": "how mentioned"}}
  ],
  "insights": ["notable patterns or takeaways"]
}}""",
    "other": """Analyze this document and extract key information.

## Document
Title: {title}
Content:
{content}

---

Extract and return valid JSON with:
{{
  "summary": "2-3 sentence summary",
  "key_points": ["main takeaways"],
  "decisions": ["any decisions mentioned"],
  "action_items": ["any tasks or follow-ups"],
  "entities": [
    {{"name": "entity", "type": "person|project|system|brand", "context": "how mentioned"}}
  ]
}}""",
}

SLACK_PROMPT = """Analyze these Slack messages and extract structured information.

## Channel: {channel_name}
## Messages:
{messages}

---

Extract and return valid JSON with:
{{
  "decisions": [
    {{"what": "decision made", "who": ["participants"], "date": "when", "context": "why", "confidence": "high|medium|low"}}
  ],
  "entities": [
    {{"name": "entity name", "type": "person|project|system|squad|brand", "context": "how mentioned", "relationships": ["related entities"]}}
  ],
  "blockers": [
    {{"description": "what's blocked", "owner": "who owns it", "status": "active|resolved", "impact": "what's affected"}}
  ],
  "action_items": [
    {{"task": "what", "owner": "who", "due": "when", "status": "pending|done"}}
  ],
  "key_context": [
    {{"topic": "what", "summary": "1-2 sentences", "relevance": "why it matters"}}
  ],
  "summary": "1-2 sentence summary of this batch"
}}"""

GITHUB_PROMPT = """Analyze these GitHub commits and extract structured information about code changes, decisions, and context.

## Commits:
{commits}

---

Extract and return valid JSON with:
{{
  "changes_summary": "2-3 sentence summary of what changed across these commits",
  "features": [
    {{"name": "feature/change name", "description": "what it does", "commits": ["sha1", "sha2"], "status": "added|modified|removed"}}
  ],
  "decisions": [
    {{"what": "technical decision made", "rationale": "why (from commit message)", "ticket": "Jira ticket if mentioned"}}
  ],
  "refactors": [
    {{"area": "what was refactored", "reason": "why", "impact": "what's affected"}}
  ],
  "fixes": [
    {{"issue": "what was fixed", "ticket": "Jira ticket if mentioned"}}
  ],
  "entities": [
    {{"name": "entity", "type": "system|api|component|feature|brand", "context": "how affected"}}
  ],
  "key_patterns": ["notable coding patterns or architectural changes observed"]
}}"""

GITHUB_DIR = BRAIN_DIR / "GitHub"

JIRA_PROMPT = """Analyze these Jira issues and extract structured information about decisions, work patterns, and context.

## Issues:
{issues}

---

Extract and return valid JSON with:
{{
  "summary": "2-3 sentence summary of the work represented in these issues",
  "decisions": [
    {{"what": "decision made", "issue_key": "JIRA-123", "who": ["involved"], "rationale": "why", "date": "when"}}
  ],
  "initiatives": [
    {{"name": "initiative/epic name", "description": "what it aims to achieve", "status": "active|completed|blocked", "key_issues": ["JIRA-123"]}}
  ],
  "blockers": [
    {{"description": "what's blocked", "issue_key": "JIRA-123", "owner": "assignee", "impact": "what's affected"}}
  ],
  "entities": [
    {{"name": "entity name", "type": "person|project|system|squad|brand|feature", "context": "how mentioned", "issues": ["related keys"]}}
  ],
  "technical_patterns": [
    {{"pattern": "technical approach/decision", "context": "why it matters"}}
  ],
  "work_themes": ["main themes of work in this batch"],
  "dependencies": [
    {{"from": "team/system", "to": "team/system", "context": "nature of dependency"}}
  ]
}}"""

# ============================================================================
# BEDROCK CLIENT
# ============================================================================


def get_bedrock_client():
    """Get AWS Bedrock client."""
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    return session.client("bedrock-runtime")


def call_bedrock(client, prompt: str, max_tokens: int = 4096) -> Optional[str]:
    """
    Call AWS Bedrock Claude.

    Returns the response text or None on error.
    """
    try:
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,  # Low temperature for consistent extraction
            }
        )

        response = client.invoke_model(
            modelId=MODEL_ID,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read())
        return response_body.get("content", [{}])[0].get("text", "")

    except Exception as e:
        print(f"  Bedrock error: {e}", file=sys.stderr)
        return None


def parse_json_response(response: str) -> Optional[Dict]:
    """Extract JSON from LLM response."""
    if not response:
        return None

    # Try to find JSON block
    try:
        # Look for JSON in code blocks
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            json_str = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            json_str = response[start:end].strip()
        else:
            # Try to find JSON object directly
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
            else:
                return None

        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}", file=sys.stderr)
        return None


# ============================================================================
# STATE MANAGEMENT
# ============================================================================


def get_state_file(source: str) -> Path:
    """Get state file path for source type."""
    if source == "gdocs":
        base_dir = GDOCS_DIR
    elif source == "slack":
        base_dir = SLACK_DIR
    elif source == "jira":
        base_dir = JIRA_DIR
    else:
        base_dir = GITHUB_DIR
    return base_dir / "llm_analysis_state.json"


def load_state(source: str) -> Dict:
    """Load analysis state."""
    state_file = get_state_file(source)
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "started_at": None,
        "last_updated": None,
        "batches_analyzed": [],
        "docs_analyzed": 0,
        "decisions_found": 0,
        "entities_found": 0,
        "errors": 0,
    }


def save_state(source: str, state: Dict):
    """Save analysis state."""
    state["last_updated"] = datetime.now().isoformat()
    state_file = get_state_file(source)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def print_status(source: str):
    """Print current status."""
    state = load_state(source)
    print("=" * 60)
    print(f"{source.upper()} LLM ANALYSIS STATUS")
    print("=" * 60)
    print(f"Started: {state.get('started_at', 'Not started')}")
    print(f"Last Updated: {state.get('last_updated', 'N/A')}")
    print(f"Batches Analyzed: {len(state.get('batches_analyzed', []))}")
    print(f"Documents Analyzed: {state.get('docs_analyzed', 0)}")
    print(f"Decisions Found: {state.get('decisions_found', 0)}")
    print(f"Entities Found: {state.get('entities_found', 0)}")
    print(f"Errors: {state.get('errors', 0)}")
    print("=" * 60)


# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================


def analyze_gdocs_batch(batch: Dict, client, dry_run: bool = False) -> Dict:
    """Analyze a GDocs batch."""
    doc_type = batch.get("doc_type", "other")
    documents = batch.get("documents", [])
    prompt_template = GDOCS_PROMPTS.get(doc_type, GDOCS_PROMPTS["other"])

    results = []
    for doc in documents:
        title = doc.get("title", "Unknown")
        content = doc.get("content", "")[:12000]  # Limit content size

        if dry_run:
            print(f"  [DRY RUN] Would analyze: {title[:50]}", file=sys.stderr)
            results.append(
                {
                    "doc_title": title,
                    "doc_id": doc.get("doc_id"),
                    "_dry_run": True,
                }
            )
            continue

        prompt = prompt_template.format(title=title, content=content)
        print(f"  Analyzing: {title[:50]}...", file=sys.stderr)

        response = call_bedrock(client, prompt)
        parsed = parse_json_response(response)

        result = {
            "doc_title": title,
            "doc_id": doc.get("doc_id"),
            "doc_type": doc_type,
        }
        if parsed:
            result.update(parsed)
        else:
            result["_error"] = "Failed to parse response"
            result["_raw_response"] = response[:500] if response else None

        results.append(result)
        time.sleep(REQUEST_DELAY)  # Rate limiting

    return {
        "batch_id": batch.get("batch_id"),
        "doc_type": doc_type,
        "doc_count": len(documents),
        "results": results,
        "analyzed_at": datetime.now().isoformat(),
    }


def analyze_slack_batch(batch: Dict, client, dry_run: bool = False) -> Dict:
    """Analyze a Slack batch."""
    channel_name = batch.get("channel_name", "unknown")
    messages = batch.get("messages", [])

    # Format messages for prompt
    formatted = []
    for msg in messages:
        user = msg.get("user_name", msg.get("user", "Unknown"))
        text = msg.get("text", "")
        formatted.append(f"**{user}**: {text}")

        # Include thread replies
        for reply in msg.get("thread_replies", []):
            reply_user = reply.get("user_name", reply.get("user", "Unknown"))
            reply_text = reply.get("text", "")
            formatted.append(f"  ↳ {reply_user}: {reply_text}")

    messages_text = "\n".join(formatted)[:15000]  # Limit size

    if dry_run:
        print(
            f"  [DRY RUN] Would analyze {len(messages)} messages from #{channel_name}",
            file=sys.stderr,
        )
        return {
            "batch_id": batch.get("batch_id"),
            "channel_name": channel_name,
            "message_count": len(messages),
            "_dry_run": True,
        }

    prompt = SLACK_PROMPT.format(channel_name=channel_name, messages=messages_text)
    print(
        f"  Analyzing {len(messages)} messages from #{channel_name}...", file=sys.stderr
    )

    response = call_bedrock(client, prompt)
    parsed = parse_json_response(response)

    result = {
        "batch_id": batch.get("batch_id"),
        "channel_name": channel_name,
        "channel_id": batch.get("channel_id"),
        "message_count": len(messages),
        "analyzed_at": datetime.now().isoformat(),
    }

    if parsed:
        result.update(parsed)
    else:
        result["_error"] = "Failed to parse response"
        result["_raw_response"] = response[:500] if response else None

    time.sleep(REQUEST_DELAY)  # Rate limiting
    return result


def analyze_github_batch(batch: Dict, client, dry_run: bool = False) -> Dict:
    """Analyze a GitHub commit batch."""
    commits = batch.get("commits", [])
    batch_id = batch.get("batch_id", "unknown")

    # Format commits for prompt
    formatted = []
    for commit in commits:
        sha = commit.get("sha", "")[:8]
        author = commit.get("author", "Unknown")
        date = commit.get("date", "")[:10]
        message = commit.get("message", "").split("\n")[0][
            :200
        ]  # First line, truncated
        repo = commit.get("repo", "")

        formatted.append(f"- [{sha}] {date} by {author}: {message}")

    commits_text = "\n".join(formatted)[:15000]  # Limit size

    if dry_run:
        print(f"  [DRY RUN] Would analyze {len(commits)} commits", file=sys.stderr)
        return {
            "batch_id": batch_id,
            "commit_count": len(commits),
            "_dry_run": True,
        }

    prompt = GITHUB_PROMPT.format(commits=commits_text)
    print(f"  Analyzing {len(commits)} commits...", file=sys.stderr)

    response = call_bedrock(client, prompt)
    parsed = parse_json_response(response)

    result = {
        "batch_id": batch_id,
        "commit_count": len(commits),
        "date_range": batch.get("date_range", {}),
        "analyzed_at": datetime.now().isoformat(),
    }

    if parsed:
        result.update(parsed)
    else:
        result["_error"] = "Failed to parse response"
        result["_raw_response"] = response[:500] if response else None

    time.sleep(REQUEST_DELAY)  # Rate limiting
    return result


def analyze_jira_batch(batch: Dict, client, dry_run: bool = False) -> Dict:
    """Analyze a Jira issue batch."""
    issues = batch.get("issues", [])
    batch_id = batch.get("batch_id", "unknown")

    # Format issues for prompt
    formatted = []
    for issue in issues:
        key = issue.get("key", "")
        summary = issue.get("summary", "")
        issue_type = issue.get("issue_type", "")
        status = issue.get("status", "")
        assignee = issue.get("assignee", "Unassigned")
        description = (issue.get("description") or "")[:500]  # Truncate
        labels = ", ".join(issue.get("labels", []))
        parent = issue.get("parent_key", "")

        entry = f"- [{key}] ({issue_type}) {summary}\n"
        entry += f"  Status: {status} | Assignee: {assignee}"
        if labels:
            entry += f" | Labels: {labels}"
        if parent:
            entry += f" | Parent: {parent}"
        entry += "\n"
        if description:
            entry += f"  Description: {description[:300]}...\n"

        # Add comments summary
        comments = issue.get("comments", [])
        if comments:
            entry += f"  Comments ({len(comments)}):\n"
            for comment in comments[:2]:
                entry += f"    - {comment.get('author')}: {comment.get('body', '')[:100]}...\n"

        formatted.append(entry)

    issues_text = "\n".join(formatted)[:15000]  # Limit size

    if dry_run:
        print(f"  [DRY RUN] Would analyze {len(issues)} Jira issues", file=sys.stderr)
        return {
            "batch_id": batch_id,
            "issue_count": len(issues),
            "_dry_run": True,
        }

    prompt = JIRA_PROMPT.format(issues=issues_text)
    print(f"  Analyzing {len(issues)} Jira issues...", file=sys.stderr)

    response = call_bedrock(client, prompt)
    parsed = parse_json_response(response)

    result = {
        "batch_id": batch_id,
        "issue_count": len(issues),
        "issue_types": batch.get("issue_types", {}),
        "date_range": batch.get("date_range", {}),
        "analyzed_at": datetime.now().isoformat(),
    }

    if parsed:
        result.update(parsed)
    else:
        result["_error"] = "Failed to parse response"
        result["_raw_response"] = response[:500] if response else None

    time.sleep(REQUEST_DELAY)  # Rate limiting
    return result


def save_analysis(source: str, batch_id: str, analysis: Dict):
    """Save analysis results with incremental save."""
    if source == "gdocs":
        base_dir = GDOCS_DIR
    elif source == "slack":
        base_dir = SLACK_DIR
    elif source == "jira":
        base_dir = JIRA_DIR
    else:
        base_dir = GITHUB_DIR

    output_dir = base_dir / "Analyzed"
    output_dir.mkdir(parents=True, exist_ok=True)

    filepath = output_dir / f"analysis_{batch_id}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    return filepath


# ============================================================================
# MAIN PIPELINE
# ============================================================================


def find_batches(source: str) -> List[Path]:
    """Find all batch files for source type."""
    if source == "gdocs":
        base_dir = GDOCS_DIR
    elif source == "slack":
        base_dir = SLACK_DIR
    elif source == "jira":
        base_dir = JIRA_DIR
    else:
        base_dir = GITHUB_DIR

    processed_dir = base_dir / "Processed"

    if not processed_dir.exists():
        return []

    return sorted(processed_dir.glob("batch_*.json"))


def run_analysis(
    source: str,
    batch_file: Optional[str] = None,
    analyze_all: bool = False,
    dry_run: bool = False,
    resume: bool = True,
):
    """Run the analysis pipeline."""
    state = load_state(source)

    if not state.get("started_at"):
        state["started_at"] = datetime.now().isoformat()
        save_state(source, state)

    # Initialize client
    client = None
    if not dry_run:
        try:
            client = get_bedrock_client()
            print(f"Connected to AWS Bedrock ({AWS_REGION})", file=sys.stderr)
        except Exception as e:
            print(f"Failed to connect to Bedrock: {e}", file=sys.stderr)
            return

    if batch_file:
        # Single batch
        batch_path = Path(batch_file)
        if not batch_path.exists():
            if source == "gdocs":
                base_dir = GDOCS_DIR
            elif source == "slack":
                base_dir = SLACK_DIR
            else:
                base_dir = GITHUB_DIR
            batch_path = base_dir / "Processed" / batch_file
        if not batch_path.exists():
            print(f"Batch file not found: {batch_file}", file=sys.stderr)
            return

        batches = [batch_path]
    elif analyze_all:
        batches = find_batches(source)
        print(f"Found {len(batches)} batch files", file=sys.stderr)

        if resume:
            analyzed_set = set(state.get("batches_analyzed", []))
            batches = [b for b in batches if str(b) not in analyzed_set]
            print(f"Remaining after resume: {len(batches)}", file=sys.stderr)

        if not batches:
            print("No new batches to analyze", file=sys.stderr)
            return
    else:
        print("Specify --batch FILE or --all to analyze", file=sys.stderr)
        return

    # Process batches
    for batch_path in batches:
        print(f"\nProcessing: {batch_path.name}", file=sys.stderr)

        with open(batch_path, "r", encoding="utf-8") as f:
            batch = json.load(f)

        batch_id = batch.get("batch_id", batch_path.stem)

        # Analyze based on source type
        if source == "gdocs":
            analysis = analyze_gdocs_batch(batch, client, dry_run)
        elif source == "slack":
            analysis = analyze_slack_batch(batch, client, dry_run)
        elif source == "jira":
            analysis = analyze_jira_batch(batch, client, dry_run)
        else:
            analysis = analyze_github_batch(batch, client, dry_run)

        if not dry_run:
            # Save results immediately (incremental)
            filepath = save_analysis(source, batch_id, analysis)
            print(f"  Saved: {filepath.name}", file=sys.stderr)

            # Update state
            state["batches_analyzed"].append(str(batch_path))
            state["docs_analyzed"] += analysis.get(
                "doc_count",
                analysis.get(
                    "message_count",
                    analysis.get("commit_count", analysis.get("issue_count", 0)),
                ),
            )

            # Count extractions
            if "results" in analysis:
                for result in analysis["results"]:
                    state["decisions_found"] += len(result.get("decisions", []))
                    state["entities_found"] += len(result.get("entities", []))
                    if result.get("_error"):
                        state["errors"] += 1
            else:
                state["decisions_found"] += len(analysis.get("decisions", []))
                state["entities_found"] += len(analysis.get("entities", []))
                if analysis.get("_error"):
                    state["errors"] += 1

            save_state(source, state)

    # Summary
    print(f"\n{'=' * 60}", file=sys.stderr)
    print(
        f"{source.upper()} ANALYSIS {'COMPLETE' if not dry_run else 'DRY RUN COMPLETE'}",
        file=sys.stderr,
    )
    print(f"{'=' * 60}", file=sys.stderr)
    print(f"Batches processed: {len(batches)}", file=sys.stderr)
    print(f"Total analyzed: {state.get('docs_analyzed', 0)}", file=sys.stderr)
    print(f"Decisions found: {state.get('decisions_found', 0)}", file=sys.stderr)
    print(f"Entities found: {state.get('entities_found', 0)}", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Analyze document batches using AWS Bedrock Claude"
    )
    parser.add_argument(
        "--source",
        choices=["gdocs", "slack", "github", "jira"],
        required=True,
        help="Data source to analyze",
    )
    parser.add_argument("--batch", help="Single batch file to analyze")
    parser.add_argument(
        "--all", action="store_true", help="Analyze all unprocessed batches"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be analyzed without calling LLM",
    )
    parser.add_argument(
        "--no-resume", action="store_true", help="Re-analyze all batches"
    )
    parser.add_argument(
        "--status", action="store_true", help="Show analysis status and exit"
    )

    args = parser.parse_args()

    if args.status:
        print_status(args.source)
        return

    run_analysis(
        source=args.source,
        batch_file=args.batch,
        analyze_all=args.all,
        dry_run=args.dry_run,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
