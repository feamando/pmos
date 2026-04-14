#!/usr/bin/env python3
"""
Context Synthesizer (v5.0)

Transforms raw daily context data into a structured context file.
Runs after daily_context_updater to produce the final context markdown.

Uses LLM synthesis (Anthropic -> Bedrock fallback) with rule-based fallback.

Port of v4.x context_synthesizer.py (~825 lines -> ~500 lines).

Key v5.0 changes:
- ZERO hardcoded identity: user name, title, org from config
- Config-driven noise patterns: config.get("context.noise_patterns", [])
- connector_bridge for LLM API auth
- Proper logging (no print() for debug)

Usage:
    python context_synthesizer.py --input raw.md           # Synthesize from file
    python context_synthesizer.py --input raw.md --no-ai   # Rule-based only
    cat raw.md | python context_synthesizer.py             # Synthesize from stdin
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from config_loader import get_config
    except ImportError:
        get_config = None

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        from path_resolver import get_paths
    except ImportError:
        get_paths = None

try:
    from pm_os_base.tools.core.connector_bridge import get_auth
except ImportError:
    try:
        from connector_bridge import get_auth
    except ImportError:
        get_auth = None

logger = logging.getLogger(__name__)

# LLM settings
SYNTHESIS_MODEL = "claude-3-5-haiku-20241022"
MAX_INPUT_CHARS = 50000
_MAX_DOC_CHARS = 4000

# Default noise patterns (can be overridden via config)
_DEFAULT_NOISE_PATTERNS = [
    "Meal & Add On Database",
    "Meal & Add-On Database",
    "CCM Recipes",
    "Customer Order Metadata",
    "Conversion Tool",
    "OKR Management tool",
    "Marketing Vouchers",
    "iTracker",
    "Reset To Trial Customers",
    "Box Price Issue",
    "Virtual Interview with",
    "Virtual Coding Interview",
    "Virtual Hiring Manager Interview",
    "Virtual Live Assessment Interview",
    "Logistics",
    "Supplier Splits",
]


# =============================================================================
# Path Resolution
# =============================================================================


def _get_context_dirs(config: Any) -> tuple:
    """Resolve context and raw directories from config.

    Args:
        config: ConfigLoader instance.

    Returns:
        Tuple of (context_dir, raw_dir) as Path objects.
    """
    try:
        if get_paths is not None:
            paths = get_paths()
            context_dir = paths.context
        else:
            from pm_os_base.tools.core.config_loader import get_root_path
            context_dir = get_root_path() / "user" / "personal" / "context"
    except Exception:
        context_dir = Path.cwd() / "context"

    raw_dir = context_dir / "raw"
    return context_dir, raw_dir


def _ensure_dirs(context_dir: Path, raw_dir: Path):
    """Ensure required directories exist."""
    context_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Pre-filtering
# =============================================================================


def prefilter_raw_content(raw_content: str, config: Any) -> str:
    """Strip noise documents and cap individual doc sizes before LLM synthesis.

    Noise patterns loaded from config, falling back to defaults.

    Args:
        raw_content: Raw context data string.
        config: ConfigLoader instance.

    Returns:
        Filtered content with noise docs removed and large docs capped.
    """
    noise_patterns = config.get("context.noise_patterns", _DEFAULT_NOISE_PATTERNS) or _DEFAULT_NOISE_PATTERNS
    max_doc_chars = config.get("context.max_doc_chars", _MAX_DOC_CHARS) or _MAX_DOC_CHARS

    lines = raw_content.split("\n")
    filtered_lines = []
    in_noise_doc = False
    current_doc_chars = 0
    doc_capped = False
    docs_removed = 0
    docs_capped = 0

    for line in lines:
        # Check for section start
        if line.startswith("### DOC: ") or line.startswith("### SLACK: ") or line.startswith("### EMAIL: "):
            in_noise_doc = False
            current_doc_chars = 0
            doc_capped = False

            if line.startswith("### DOC: "):
                for pattern in noise_patterns:
                    if pattern.lower() in line.lower():
                        in_noise_doc = True
                        docs_removed += 1
                        filtered_lines.append(line)
                        filtered_lines.append(
                            "[FILTERED: operational data, not relevant for daily context]"
                        )
                        filtered_lines.append("")
                        break

        if in_noise_doc:
            continue

        # Cap individual document size
        current_doc_chars += len(line)
        if current_doc_chars > max_doc_chars and not doc_capped:
            if not (line.startswith("### DOC: ") or line.startswith("## ")):
                filtered_lines.append(
                    f"\n[... document truncated at {max_doc_chars} chars for synthesis efficiency ...]"
                )
                doc_capped = True
                docs_capped += 1

        if not doc_capped or line.startswith("### ") or line.startswith("## ") or line.startswith("# ") or line.startswith("---"):
            if line.startswith("### DOC: ") or line.startswith("## "):
                doc_capped = False
                current_doc_chars = 0
            filtered_lines.append(line)

    result = "\n".join(filtered_lines)
    if docs_removed > 0 or docs_capped > 0:
        logger.info(
            "[PREFILTER] Removed %s noise docs, capped %s large docs",
            docs_removed, docs_capped,
        )
        original_len = len(raw_content)
        reduction = 100 - len(result) * 100 // original_len if original_len else 0
        logger.info(
            "[PREFILTER] %s -> %s chars (%s%% reduction)",
            original_len, len(result), reduction,
        )
    return result


# =============================================================================
# Previous Context
# =============================================================================


def load_previous_context(context_dir: Path, today: str) -> Optional[str]:
    """Load the most recent previous context file for carrying forward items.

    Args:
        context_dir: Path to context directory.
        today: Today's date string (YYYY-MM-DD).

    Returns:
        Previous context file content, or None.
    """
    context_files = sorted(context_dir.glob("*-context.md"), reverse=True)
    for f in context_files:
        if today not in f.name and f.is_file():
            try:
                return f.read_text(encoding="utf-8")
            except Exception:
                continue
    return None


# =============================================================================
# Synthesis Prompt
# =============================================================================


def get_synthesis_prompt(config: Any, today: str, prev_context: Optional[str]) -> str:
    """Generate the synthesis prompt for LLM.

    All identity information from config, ZERO hardcoded values.

    Args:
        config: ConfigLoader instance.
        today: Today's date string.
        prev_context: Previous context content for continuity.

    Returns:
        Full prompt string.
    """
    user_name = config.get("user.name", "User")
    user_title = config.get("user.title", "")
    user_org = config.get("user.org", "")

    identity_line = user_name
    if user_title and user_org:
        identity_line = f"{user_name}, {user_title} at {user_org}"
    elif user_title:
        identity_line = f"{user_name}, {user_title}"

    # Build team context for prompt
    team_names = []
    reports = config.get("team.reports", []) or []
    for report in reports:
        name = report.get("name", "") if isinstance(report, dict) else str(report)
        if name:
            team_names.append(name)

    team_context = ""
    if team_names:
        team_context = f"\nTeam members: {', '.join(team_names)}\n"

    prev_context_section = ""
    if prev_context:
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

    return f"""You are synthesizing a daily context file for {identity_line}.
{team_context}
## Output Format

Generate a markdown file following this EXACT structure:

```markdown
# Daily Context: {today}

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

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

## Style Guide

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
7. Focus on meeting notes, Slack threads, and work documents
{prev_context_section}

Now synthesize the following RAW DATA into the context file:
"""


# =============================================================================
# LLM Synthesis (Anthropic -> Bedrock fallback)
# =============================================================================


def synthesize_with_claude(
    raw_content: str, config: Any, today: str, prev_context: Optional[str]
) -> Optional[str]:
    """Use Anthropic Claude API to synthesize context file.

    Args:
        raw_content: Pre-filtered raw context data.
        config: ConfigLoader instance.
        today: Today's date string.
        prev_context: Previous context for continuity.

    Returns:
        Synthesized markdown, or None on failure.
    """
    try:
        import anthropic
    except ImportError:
        logger.info("Anthropic SDK not available, trying Bedrock")
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.info("ANTHROPIC_API_KEY not set, trying Bedrock")
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)

        truncated_raw = raw_content[:MAX_INPUT_CHARS]
        if len(raw_content) > MAX_INPUT_CHARS:
            truncated_raw += f"\n\n[... truncated {len(raw_content) - MAX_INPUT_CHARS} chars ...]"

        prompt = get_synthesis_prompt(config, today, prev_context)

        logger.info("Running Claude API synthesis...")

        message = client.messages.create(
            model=SYNTHESIS_MODEL,
            max_tokens=8000,
            messages=[
                {"role": "user", "content": f"{prompt}\n\n## RAW DATA\n\n{truncated_raw}"}
            ],
        )

        response_text = message.content[0].text
        response_text = _extract_markdown(response_text)

        logger.info("Claude API synthesis complete")
        return response_text

    except Exception as e:
        logger.warning("Claude API synthesis error: %s", e)
        return None


def synthesize_with_bedrock(
    raw_content: str, config: Any, today: str, prev_context: Optional[str]
) -> Optional[str]:
    """Use AWS Bedrock to synthesize context file.

    Args:
        raw_content: Pre-filtered raw context data.
        config: ConfigLoader instance.
        today: Today's date string.
        prev_context: Previous context for continuity.

    Returns:
        Synthesized markdown, or None on failure.
    """
    try:
        import boto3
    except ImportError:
        logger.debug("boto3 not available")
        return None

    try:
        session = boto3.Session()
        credentials = session.get_credentials()
        if not credentials:
            return None

        region = os.environ.get("AWS_REGION", "eu-central-1")
        client = boto3.client("bedrock-runtime", region_name=region)

        truncated_raw = raw_content[:MAX_INPUT_CHARS]
        if len(raw_content) > MAX_INPUT_CHARS:
            truncated_raw += f"\n\n[... truncated {len(raw_content) - MAX_INPUT_CHARS} chars ...]"

        prompt = get_synthesis_prompt(config, today, prev_context)
        full_prompt = f"{prompt}\n\n## RAW DATA\n\n{truncated_raw}"

        logger.info("Running AWS Bedrock synthesis...")

        bedrock_model = config.get(
            "context.bedrock_model", "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
        )

        response = client.invoke_model(
            modelId=bedrock_model,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 8000,
                "messages": [{"role": "user", "content": full_prompt}],
            }),
        )

        response_body = json.loads(response["body"].read())
        response_text = response_body["content"][0]["text"]
        response_text = _extract_markdown(response_text)

        logger.info("AWS Bedrock synthesis complete")
        return response_text

    except Exception as e:
        logger.warning("Bedrock synthesis error: %s", e)
        return None


def _extract_markdown(response_text: str) -> str:
    """Extract markdown from LLM response, stripping code fences if present."""
    if "```markdown" in response_text:
        match = re.search(r"```markdown\n(.*?)```", response_text, re.DOTALL)
        if match:
            return match.group(1)
    elif response_text.startswith("```") and response_text.endswith("```"):
        return response_text[3:-3].strip()
    return response_text


# =============================================================================
# Rule-based Fallback
# =============================================================================


def extract_section(content: str, section_name: str) -> List[str]:
    """Extract unchecked action items from a section in previous context.

    Args:
        content: Previous context file content.
        section_name: Section header to search for.

    Returns:
        List of unchecked action item lines.
    """
    lines = []
    in_section = False
    for line in content.split("\n"):
        if line.startswith("## ") or line.startswith("### "):
            in_section = section_name.lower() in line.lower()
        elif in_section and "- [ ]" in line:
            lines.append(line.strip())
    return lines


def extract_blockers_table(content: str) -> List[Dict[str, str]]:
    """Extract blockers from previous context table."""
    blockers = []
    in_blockers = False
    for line in content.split("\n"):
        if "## Blockers" in line or "## Active Blockers" in line:
            in_blockers = True
            continue
        if in_blockers:
            if line.startswith("## ") or line.startswith("---"):
                break
            if "|" in line and not line.strip().startswith("|--"):
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3 and parts[0] and parts[0] != "Blocker":
                    blockers.append({
                        "blocker": parts[0],
                        "impact": parts[1] if len(parts) > 1 else "",
                        "owner": parts[2] if len(parts) > 2 else "TBD",
                        "status": parts[3] if len(parts) > 3 else "Open",
                    })
    return blockers


def extract_key_dates(content: str) -> List[Dict[str, str]]:
    """Extract future key dates from previous context."""
    dates = []
    in_dates = False
    for line in content.split("\n"):
        if "## Key Dates" in line or "## Upcoming" in line:
            in_dates = True
            continue
        if in_dates:
            if line.startswith("## ") or line.startswith("---"):
                break
            if "|" in line and not line.strip().startswith("|--"):
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 2 and parts[0] and parts[0] != "Date":
                    date_str = parts[0].split("(")[0].strip()
                    try:
                        if re.match(r"\d{4}-\d{2}-\d{2}", date_str):
                            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                            if date_obj.date() >= datetime.now().date():
                                dates.append({
                                    "date": parts[0],
                                    "event": parts[1] if len(parts) > 1 else "",
                                })
                    except ValueError:
                        dates.append({
                            "date": parts[0],
                            "event": parts[1] if len(parts) > 1 else "",
                        })
    return dates


def extract_critical_alerts(
    raw_data: Dict[str, Any], prev_context: Optional[str], config: Any
) -> List[str]:
    """Extract critical alerts from raw data and previous context.

    Alert keywords loaded from config.

    Args:
        raw_data: Parsed raw data dict.
        prev_context: Previous context content.
        config: ConfigLoader instance.

    Returns:
        List of alert strings.
    """
    alerts = []

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

    alert_keywords = config.get("context.alert_keywords", [
        "critical", "blocker", "urgent", "production issue",
        "p0", "p1", "failed", "down", "overdue",
    ])

    for doc_name, content in raw_data.get("doc_contents", {}).items():
        content_lower = content.lower()
        for keyword in alert_keywords:
            if keyword in content_lower:
                idx = content_lower.find(keyword)
                snippet = content[max(0, idx - 50): idx + 100].replace("\n", " ").strip()
                if snippet and len(snippet) > 20:
                    alert = f"- **{doc_name}**: ...{snippet}..."
                    if alert not in alerts:
                        alerts.append(alert)
                break

    return alerts[:10]


def parse_raw_data(raw_content: str) -> Dict[str, Any]:
    """Parse raw output from daily_context_updater into structured data.

    Args:
        raw_content: Raw context string.

    Returns:
        Parsed data dict with documents, emails, doc_contents, etc.
    """
    data = {
        "documents": [],
        "emails": [],
        "slack_messages": [],
        "mention_tasks": [],
        "doc_contents": {},
        "generated_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    # Document index
    doc_pattern = r"\[DOC\] \[([^\]]+)\]\(([^\)]+)\) \| Modified: ([^\|]+) \| Owner: (.+)"
    for match in re.finditer(doc_pattern, raw_content):
        data["documents"].append({
            "name": match.group(1),
            "link": match.group(2),
            "modified": match.group(3).strip(),
            "owner": match.group(4).strip(),
        })

    # Email index
    email_pattern = r"\[EMAIL\] (.+?) \| From: (.+?) \| Date: (\d{4}-\d{2}-\d{2})"
    for match in re.finditer(email_pattern, raw_content):
        data["emails"].append({
            "subject": match.group(1),
            "from": match.group(2),
            "date": match.group(3),
        })

    # Mention tasks
    mention_section = re.search(r"## MENTION TASKS.*?(?=={60}|$)", raw_content, re.DOTALL)
    if mention_section:
        task_pattern = r"- \[ \] \*\*([^*]+)\*\*: (.+?)(?=\n  - From:|$)"
        for match in re.finditer(task_pattern, mention_section.group(0)):
            data["mention_tasks"].append({
                "owner": match.group(1),
                "task": match.group(2).strip(),
            })

    # Document contents
    doc_content_pattern = r"### DOC: (.+?)\nID: .+?\nLink: .+?\n-+\n\n(.+?)(?=\n-{40}|\n={60})"
    for match in re.finditer(doc_content_pattern, raw_content, re.DOTALL):
        data["doc_contents"][match.group(1)] = match.group(2).strip()[:2000]

    return data


def generate_context_file_rulebased(
    raw_content: str, output_path: Path, today: str, config: Any
) -> bool:
    """Generate context file using rule-based extraction (fallback).

    Args:
        raw_content: Raw context data.
        output_path: Where to write the context file.
        today: Date string.
        config: ConfigLoader instance.

    Returns:
        True on success.
    """
    logger.info("Running rule-based synthesis (fallback)...")

    raw_data = parse_raw_data(raw_content)

    # Resolve context dir for previous context
    context_dir, _ = _get_context_dirs(config)
    prev_context = load_previous_context(context_dir, today)

    carried_action_items = []
    carried_blockers = []
    carried_dates = []

    if prev_context:
        carried_action_items = extract_section(prev_context, "Action Items")
        carried_blockers = extract_blockers_table(prev_context)
        carried_dates = extract_key_dates(prev_context)

    critical_alerts = extract_critical_alerts(raw_data, prev_context, config)

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
        lines.extend(critical_alerts)
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

    # Key Updates
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
            if "declined" not in email["subject"].lower():
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
            lines.append(f"| {b['blocker']} | {b['impact']} | {b['owner']} | {b['status']} |")
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
        lines.extend(carried_action_items)
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

    # Mention Tasks
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
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Rule-based synthesis complete")
        return True
    except Exception as e:
        logger.error("Writing context file failed: %s", e)
        return False


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    """Main entry point for context synthesis."""
    parser = argparse.ArgumentParser(description="Synthesize context from raw data")
    parser.add_argument("--input", type=str, help="Input raw data file (default: stdin)")
    parser.add_argument("--output", type=str, help="Output context file path")
    parser.add_argument("--date", type=str, help="Date for context file (YYYY-MM-DD)")
    parser.add_argument("--no-ai", action="store_true", help="Skip AI synthesis, rule-based only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    # Load config
    if get_config is None:
        logger.error("config_loader not available")
        sys.exit(1)

    config = get_config()

    # Resolve directories
    context_dir, raw_dir = _get_context_dirs(config)
    _ensure_dirs(context_dir, raw_dir)

    # Determine date
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")

    # Read raw input
    if args.input:
        raw_path = Path(args.input)
        if not raw_path.exists():
            logger.error("Input file not found: %s", args.input)
            sys.exit(1)
        raw_content = raw_path.read_text(encoding="utf-8")
    else:
        raw_content = sys.stdin.read()

    if not raw_content.strip():
        logger.error("No raw content provided")
        sys.exit(1)

    # Save raw content
    raw_file = raw_dir / f"{date_str}-raw.md"
    raw_file.write_text(raw_content, encoding="utf-8")
    logger.info("Raw data saved to: %s", raw_file)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = context_dir / f"{date_str}-context.md"

    logger.info("Synthesizing context file: %s", output_path)

    # Load previous context
    prev_context = load_previous_context(context_dir, date_str)

    # Try AI synthesis first (unless --no-ai)
    success = False
    ai_result = None

    if not args.no_ai:
        filtered_content = prefilter_raw_content(raw_content, config)

        # Try Anthropic API first
        ai_result = synthesize_with_claude(filtered_content, config, date_str, prev_context)

        # Try AWS Bedrock if Anthropic failed
        if not ai_result:
            ai_result = synthesize_with_bedrock(filtered_content, config, date_str, prev_context)

        if ai_result:
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(ai_result, encoding="utf-8")
                success = True
            except Exception as e:
                logger.warning("Failed to write AI result: %s", e)

    # Fall back to rule-based
    if not success:
        success = generate_context_file_rulebased(raw_content, output_path, date_str, config)

    if success:
        logger.info("Context file created: %s", output_path)
        print(str(output_path))
        sys.exit(0)
    else:
        logger.error("Could not create context file")
        sys.exit(1)


if __name__ == "__main__":
    main()
