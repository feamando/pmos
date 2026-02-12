#!/usr/bin/env python3
"""
Context Synthesizer

Transforms raw daily context data into a structured context file.
Runs automatically after daily_context_updater to ensure context file is always created.

Uses Claude API for intelligent synthesis when available, with rule-based fallback.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config_loader

# Try to import Anthropic SDK
try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# Try to import boto3 for AWS Bedrock
try:
    import boto3

    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False

# Paths (WCR structure: context files in personal folder)
USER_ROOT = config_loader.get_root_path() / "user"
CONTEXT_DIR = USER_ROOT / "personal" / "context"
RAW_DIR = CONTEXT_DIR / "raw"

# Claude model for synthesis (use haiku for speed/cost)
SYNTHESIS_MODEL = "claude-3-5-haiku-20241022"
MAX_INPUT_CHARS = 80000  # Limit raw data sent to API


def ensure_dirs():
    """Ensure required directories exist."""
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def load_previous_context(today: str) -> Optional[str]:
    """Load the most recent previous context file for carrying forward items."""
    context_files = sorted(CONTEXT_DIR.glob("*-context.md"), reverse=True)
    for f in context_files:
        # Skip today's file and raw directory
        if today not in f.name and f.is_file():
            try:
                return f.read_text(encoding="utf-8")
            except Exception:
                continue
    return None


def get_synthesis_prompt(today: str, prev_context: Optional[str]) -> str:
    """Generate the synthesis prompt for Claude."""

    prev_context_section = ""
    if prev_context:
        # Extract key sections from previous context
        prev_context_section = f"""
## Previous Context (for continuity)

Carry forward unresolved items from previous context:
- Unchecked action items (- [ ])
- Active blockers not marked resolved
- Future key dates
- Pending Slack mention tasks

Previous context excerpt:
```
{prev_context[:8000]}
```
"""

    return f"""You are synthesizing a daily context file for Jane Smith, Director of Product at Acme Corp (Growth Division & Ecosystems).

## Output Format

Generate a markdown file following this EXACT structure:

```markdown
# Daily Context: {today}

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M CET')}

---

## Critical Alerts

[List P0/P1 items, overdue deadlines, production issues, urgent blockers]
[Format: - **Item**: Description (Owner)]

---

## Today's Schedule

| Time | Event |
|------|-------|
[Extract from calendar emails/meeting notes if available]

---

## Key Updates & Decisions

### [Topic 1]
- **Key point** with context
- Decision or action taken

### [Topic 2]
[Continue for major topics from docs/emails]

---

## Active Blockers

| Blocker | Impact | Owner | Status |
|---------|--------|-------|--------|
[List blockers with status]

---

## Action Items

### Today
- [ ] **Owner**: Action item

### This Week
- [ ] **Owner**: Action item

---

## Key Dates

| Date | Event |
|------|-------|
[Future dates only]

---

## Pending Slack Mention Tasks

[Carry forward from previous + new]

---

*Next update: After significant developments*
```

## Style Guide (NGO)

- Direct, functional tone - no fluff
- Bullets over prose
- Bold for key terms, names, statuses
- Explicit owners for every action item
- Dates in ISO format (YYYY-MM-DD)
- Status tags: (P0), (Critical), (In Progress)
- Extract metrics with WoW/YoY when available
- Focus on: decisions made, blockers, action items, deadlines

## Instructions

1. Extract key information from the RAW DATA below
2. Synthesize into the structured format above
3. Prioritize: blockers > decisions > metrics > updates
4. Carry forward unresolved items from previous context
5. Keep it concise - this is a working document, not a summary
6. IGNORE promotional emails, newsletters, calendar declines
7. Focus on meeting notes (especially Gemini notes), Slack threads, and work documents
{prev_context_section}

Now synthesize the following RAW DATA into the context file:
"""


def synthesize_with_claude(
    raw_content: str, today: str, prev_context: Optional[str]
) -> Optional[str]:
    """Use Claude API to synthesize context file."""
    if not ANTHROPIC_AVAILABLE:
        print(
            "  [INFO] Anthropic SDK not available, using rule-based synthesis",
            file=sys.stderr,
        )
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "  [INFO] ANTHROPIC_API_KEY not set, using rule-based synthesis",
            file=sys.stderr,
        )
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)

        # Truncate raw content if too long
        truncated_raw = raw_content[:MAX_INPUT_CHARS]
        if len(raw_content) > MAX_INPUT_CHARS:
            truncated_raw += (
                f"\n\n[... truncated {len(raw_content) - MAX_INPUT_CHARS} chars ...]"
            )

        prompt = get_synthesis_prompt(today, prev_context)

        print("  [RUN] Claude API synthesis...", file=sys.stderr)

        message = client.messages.create(
            model=SYNTHESIS_MODEL,
            max_tokens=8000,
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}\n\n## RAW DATA\n\n{truncated_raw}",
                }
            ],
        )

        response_text = message.content[0].text

        # Extract markdown if wrapped in code blocks
        if "```markdown" in response_text:
            match = re.search(r"```markdown\n(.*?)```", response_text, re.DOTALL)
            if match:
                response_text = match.group(1)
        elif response_text.startswith("```") and response_text.endswith("```"):
            response_text = response_text[3:-3].strip()

        print("  [OK] Claude API synthesis complete", file=sys.stderr)
        return response_text

    except anthropic.APIError as e:
        print(f"  [WARN] Claude API error: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  [WARN] Synthesis error: {e}", file=sys.stderr)
        return None


def synthesize_with_bedrock(
    raw_content: str, today: str, prev_context: Optional[str]
) -> Optional[str]:
    """Use AWS Bedrock to synthesize context file."""
    if not BEDROCK_AVAILABLE:
        return None

    try:
        # Check for AWS credentials
        session = boto3.Session()
        credentials = session.get_credentials()
        if not credentials:
            return None

        client = boto3.client(
            "bedrock-runtime", region_name=os.environ.get("AWS_REGION", "eu-central-1")
        )

        # Truncate raw content if too long
        truncated_raw = raw_content[:MAX_INPUT_CHARS]
        if len(raw_content) > MAX_INPUT_CHARS:
            truncated_raw += (
                f"\n\n[... truncated {len(raw_content) - MAX_INPUT_CHARS} chars ...]"
            )

        prompt = get_synthesis_prompt(today, prev_context)
        full_prompt = f"{prompt}\n\n## RAW DATA\n\n{truncated_raw}"

        print("  [RUN] AWS Bedrock synthesis...", file=sys.stderr)

        # Use Claude on Bedrock
        response = client.invoke_model(
            modelId="eu.anthropic.claude-haiku-4-5-20251001-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 8000,
                    "messages": [{"role": "user", "content": full_prompt}],
                }
            ),
        )

        response_body = json.loads(response["body"].read())
        response_text = response_body["content"][0]["text"]

        # Extract markdown if wrapped in code blocks
        if "```markdown" in response_text:
            match = re.search(r"```markdown\n(.*?)```", response_text, re.DOTALL)
            if match:
                response_text = match.group(1)
        elif response_text.startswith("```") and response_text.endswith("```"):
            response_text = response_text[3:-3].strip()

        print("  [OK] AWS Bedrock synthesis complete", file=sys.stderr)
        return response_text

    except Exception as e:
        print(f"  [WARN] Bedrock synthesis error: {e}", file=sys.stderr)
        return None


# ============================================================================
# Rule-based fallback functions (existing logic)
# ============================================================================


def extract_section(content: str, section_name: str) -> List[str]:
    """Extract bullet points from a section in previous context."""
    lines = []
    in_section = False
    for line in content.split("\n"):
        if line.startswith("## ") or line.startswith("### "):
            if section_name.lower() in line.lower():
                in_section = True
            else:
                in_section = False
        elif in_section and line.strip().startswith("- ["):
            # Unchecked action items
            if "- [ ]" in line:
                lines.append(line.strip())
    return lines


def extract_blockers_table(content: str) -> List[Dict[str, str]]:
    """Extract blockers from previous context table."""
    blockers = []
    in_blockers = False
    for line in content.split("\n"):
        if (
            "## Blockers" in line
            or "### Blockers" in line
            or "## Active Blockers" in line
        ):
            in_blockers = True
            continue
        if in_blockers:
            if (
                line.startswith("## ")
                or line.startswith("### ")
                or line.startswith("---")
            ):
                break
            if "|" in line and not line.strip().startswith("|--"):
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3 and parts[0] and parts[0] != "Blocker":
                    blockers.append(
                        {
                            "blocker": parts[0],
                            "impact": parts[1] if len(parts) > 1 else "",
                            "owner": parts[2] if len(parts) > 2 else "TBD",
                            "status": parts[3] if len(parts) > 3 else "Open",
                        }
                    )
    return blockers


def extract_key_dates(content: str) -> List[Dict[str, str]]:
    """Extract key dates from previous context."""
    dates = []
    in_dates = False
    for line in content.split("\n"):
        if "## Key Dates" in line or "### Key Dates" in line or "## Upcoming" in line:
            in_dates = True
            continue
        if in_dates:
            if (
                line.startswith("## ")
                or line.startswith("### ")
                or line.startswith("---")
            ):
                break
            if "|" in line and not line.strip().startswith("|--"):
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 2 and parts[0] and parts[0] != "Date":
                    date_str = parts[0].split("(")[0].strip()
                    try:
                        if re.match(r"\d{4}-\d{2}-\d{2}", date_str):
                            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                            if date_obj.date() >= datetime.now().date():
                                dates.append(
                                    {
                                        "date": parts[0],
                                        "event": parts[1] if len(parts) > 1 else "",
                                    }
                                )
                    except ValueError:
                        dates.append(
                            {
                                "date": parts[0],
                                "event": parts[1] if len(parts) > 1 else "",
                            }
                        )
    return dates


def parse_raw_data(raw_content: str) -> Dict[str, Any]:
    """Parse the raw output from daily_context_updater."""
    data = {
        "documents": [],
        "emails": [],
        "slack_messages": [],
        "mention_tasks": [],
        "doc_contents": {},
        "generated_time": datetime.now().strftime("%Y-%m-%d %H:%M CET"),
    }

    # Extract document index
    doc_pattern = (
        r"\[DOC\] \[([^\]]+)\]\(([^\)]+)\) \| Modified: ([^\|]+) \| Owner: (.+)"
    )
    for match in re.finditer(doc_pattern, raw_content):
        data["documents"].append(
            {
                "name": match.group(1),
                "link": match.group(2),
                "modified": match.group(3).strip(),
                "owner": match.group(4).strip(),
            }
        )

    # Extract email index
    email_pattern = r"\[EMAIL\] (.+?) \| From: (.+?) \| Date: (\d{4}-\d{2}-\d{2})"
    for match in re.finditer(email_pattern, raw_content):
        data["emails"].append(
            {"subject": match.group(1), "from": match.group(2), "date": match.group(3)}
        )

    # Extract mention tasks
    mention_section = re.search(
        r"## MENTION TASKS.*?(?=={60}|$)", raw_content, re.DOTALL
    )
    if mention_section:
        task_pattern = r"- \[ \] \*\*([^*]+)\*\*: (.+?)(?=\n  - From:|$)"
        for match in re.finditer(task_pattern, mention_section.group(0)):
            data["mention_tasks"].append(
                {"owner": match.group(1), "task": match.group(2).strip()}
            )

    # Extract document contents (for key insights)
    doc_content_pattern = (
        r"### DOC: (.+?)\nID: .+?\nLink: .+?\n-+\n\n(.+?)(?=\n-{40}|\n={60})"
    )
    for match in re.finditer(doc_content_pattern, raw_content, re.DOTALL):
        data["doc_contents"][match.group(1)] = match.group(2).strip()[:2000]

    return data


def extract_critical_alerts(
    raw_data: Dict[str, Any], prev_context: Optional[str]
) -> List[str]:
    """Extract critical alerts from raw data and previous context."""
    alerts = []

    # Carry forward critical alerts from previous context
    if prev_context:
        in_alerts = False
        for line in prev_context.split("\n"):
            if "## Critical Alerts" in line:
                in_alerts = True
                continue
            if in_alerts:
                if line.startswith("## ") or line.startswith("---"):
                    break
                if line.strip().startswith("- **"):
                    alerts.append(line.strip())

    # Look for new alerts in document contents (keywords)
    alert_keywords = [
        "critical",
        "blocker",
        "urgent",
        "production issue",
        "p0",
        "p1",
        "failed",
        "down",
        "overdue",
    ]
    for doc_name, content in raw_data.get("doc_contents", {}).items():
        content_lower = content.lower()
        for keyword in alert_keywords:
            if keyword in content_lower:
                idx = content_lower.find(keyword)
                snippet = (
                    content[max(0, idx - 50) : idx + 100].replace("\n", " ").strip()
                )
                if snippet and len(snippet) > 20:
                    alert = f"- **{doc_name}**: ...{snippet}..."
                    if alert not in alerts:
                        alerts.append(alert)
                break

    return alerts[:10]


def generate_context_file_rulebased(
    raw_content: str, output_path: Path, today: str
) -> bool:
    """Generate context file using rule-based extraction (fallback)."""
    print("  [RUN] Rule-based synthesis (fallback)...", file=sys.stderr)

    raw_data = parse_raw_data(raw_content)
    prev_context = load_previous_context(today)

    # Extract carried forward items
    carried_action_items = []
    carried_blockers = []
    carried_dates = []

    if prev_context:
        carried_action_items = extract_section(prev_context, "Action Items")
        carried_blockers = extract_blockers_table(prev_context)
        carried_dates = extract_key_dates(prev_context)

    critical_alerts = extract_critical_alerts(raw_data, prev_context)

    # Build the context file
    lines = []
    lines.append(f"# Daily Context: {today}")
    lines.append("")
    lines.append(f"**Generated:** {raw_data['generated_time']}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Critical Alerts
    lines.append("## Critical Alerts")
    lines.append("")
    if critical_alerts:
        for alert in critical_alerts:
            lines.append(alert)
    else:
        lines.append("- No critical alerts detected")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Today's Schedule
    lines.append("## Today's Schedule")
    lines.append("")
    lines.append("| Time | Event |")
    lines.append("|------|-------|")
    lines.append("| - | Check calendar for meetings |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Key Updates - Documents processed
    lines.append("## Key Updates")
    lines.append("")
    if raw_data["documents"]:
        lines.append("### Recent Documents")
        for doc in raw_data["documents"][:10]:
            lines.append(f"- **{doc['name']}** ({doc['owner']}) - {doc['modified']}")
        lines.append("")

    if raw_data["emails"]:
        lines.append("### Recent Emails")
        for email in raw_data["emails"][:5]:
            if (
                "declined" not in email["subject"].lower()
                and "promotional" not in email.get("from", "").lower()
            ):
                lines.append(f"- **{email['subject']}** from {email['from']}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Blockers
    lines.append("## Active Blockers")
    lines.append("")
    if carried_blockers:
        lines.append("| Blocker | Impact | Owner | Status |")
        lines.append("|---------|--------|-------|--------|")
        for b in carried_blockers:
            lines.append(
                f"| {b['blocker']} | {b['impact']} | {b['owner']} | {b['status']} |"
            )
    else:
        lines.append("No active blockers recorded.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Action Items
    lines.append("## Action Items")
    lines.append("")
    if carried_action_items:
        lines.append("### Carried Forward")
        for item in carried_action_items:
            lines.append(item)
    else:
        lines.append("No pending action items.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Key Dates
    lines.append("## Key Dates")
    lines.append("")
    if carried_dates:
        lines.append("| Date | Event |")
        lines.append("|------|-------|")
        for d in carried_dates:
            lines.append(f"| {d['date']} | {d['event']} |")
    else:
        lines.append("No upcoming dates recorded.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Pending Mention Tasks
    if raw_data["mention_tasks"]:
        lines.append("## Pending Slack Mention Tasks")
        lines.append("")
        for task in raw_data["mention_tasks"]:
            lines.append(f"- [ ] **{task['owner']}**: {task['task']}")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("*Synthesized via rule-based extraction*")

    try:
        output_path.write_text("\n".join(lines), encoding="utf-8")
        print("  [OK] Rule-based synthesis complete", file=sys.stderr)
        return True
    except Exception as e:
        print(f"  [ERROR] Writing context file: {e}", file=sys.stderr)
        return False


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Synthesize context from raw data")
    parser.add_argument(
        "--input", type=str, help="Input raw data file (default: stdin)"
    )
    parser.add_argument("--output", type=str, help="Output context file path")
    parser.add_argument("--date", type=str, help="Date for context file (YYYY-MM-DD)")
    parser.add_argument(
        "--no-ai", action="store_true", help="Skip AI synthesis, use rule-based only"
    )
    args = parser.parse_args()

    ensure_dirs()

    # Determine date
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")

    # Read raw input
    if args.input:
        raw_path = Path(args.input)
        if not raw_path.exists():
            print(f"Error: Input file not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        raw_content = raw_path.read_text(encoding="utf-8")
    else:
        raw_content = sys.stdin.read()

    if not raw_content.strip():
        print("Error: No raw content provided", file=sys.stderr)
        sys.exit(1)

    # Save raw content to raw directory
    raw_file = RAW_DIR / f"{date_str}-raw.md"
    raw_file.write_text(raw_content, encoding="utf-8")
    print(f"Raw data saved to: {raw_file}", file=sys.stderr)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = CONTEXT_DIR / f"{date_str}-context.md"

    print(f"Synthesizing context file: {output_path}", file=sys.stderr)

    # Load previous context for continuity
    prev_context = load_previous_context(date_str)

    # Try AI synthesis first (unless --no-ai)
    success = False
    ai_result = None

    if not args.no_ai:
        # Try Anthropic API first
        ai_result = synthesize_with_claude(raw_content, date_str, prev_context)

        # Try AWS Bedrock if Anthropic failed
        if not ai_result:
            ai_result = synthesize_with_bedrock(raw_content, date_str, prev_context)

        if ai_result:
            try:
                output_path.write_text(ai_result, encoding="utf-8")
                success = True
            except Exception as e:
                print(f"  [WARN] Failed to write AI result: {e}", file=sys.stderr)

    # Fall back to rule-based if AI failed
    if not success:
        success = generate_context_file_rulebased(raw_content, output_path, date_str)

    if success:
        print(f"SUCCESS: Context file created: {output_path}", file=sys.stderr)
        print(str(output_path))  # Output path to stdout for orchestrator
        sys.exit(0)
    else:
        print("FAILED: Could not create context file", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
