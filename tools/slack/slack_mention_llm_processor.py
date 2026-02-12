#!/usr/bin/env python3
"""
Slack Mention LLM Processor

Uses Claude (via AWS Bedrock) or Gemini to transform raw @mentions into
formalized, actionable tasks with structured metadata.

Usage:
    from slack_mention_llm_processor import process_mention_with_llm

    enhanced_task = process_mention_with_llm(
        raw_text="@bot remind Nikita to review the PRD before Friday",
        context={"channel": "product-team", "requester": "Alice"}
    )
"""

import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Add parent for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv(override=True)

# Try to import model_bridge
try:
    from util.model_bridge import detect_active_model, invoke_claude, invoke_gemini

    MODEL_BRIDGE_AVAILABLE = True
except ImportError:
    MODEL_BRIDGE_AVAILABLE = False
    print(
        "Warning: model_bridge not available. LLM processing disabled.", file=sys.stderr
    )

# Try direct boto3 if model_bridge fails
try:
    import boto3

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


@dataclass
class FormalizedTask:
    """A formalized, actionable task derived from a mention."""

    # Core task info
    title: str  # Short, actionable title
    description: str  # Full formalized description
    task_type: str  # nikita_task, team_task, pmos_feature, pmos_bug, question, fyi

    # Assignment
    assignee: Optional[str]  # Who should do this
    delegator: Optional[str]  # Who requested it

    # Timing
    deadline: Optional[str]  # Extracted deadline (ISO format or relative)
    urgency: str  # critical, high, medium, low

    # Context
    context_summary: str  # Why this matters
    dependencies: list  # What's needed first
    acceptance_criteria: list  # How to know it's done

    # Metadata
    original_text: str
    confidence: float  # 0-1 confidence in extraction
    processed_at: str
    model_used: str


# Prompt template for task formalization
FORMALIZE_TASK_PROMPT = """You are a task formalization assistant. Transform the following Slack mention into a clear, actionable task.

## Original Message
**From:** {requester}
**Channel:** #{channel}
**Text:** {raw_text}

## Additional Context
{additional_context}

---

Analyze this message and extract a formalized task. Return valid JSON with:

{{
  "title": "Short, imperative action title (max 10 words, e.g., 'Review OTP PRD and provide feedback')",
  "description": "Full formalized task description with context. Be specific and actionable. Include what needs to be done, why, and any relevant details from the message.",
  "task_type": "One of: nikita_task, team_task, pmos_feature, pmos_bug, question, fyi",
  "assignee": "Name of person who should do this (or null if unclear)",
  "delegator": "Name of person who requested this",
  "deadline": "Extracted deadline in ISO format or relative term (e.g., '2026-01-15', 'end of week', 'ASAP') or null",
  "urgency": "One of: critical, high, medium, low - based on language and context",
  "context_summary": "1-2 sentence summary of why this task matters or what problem it solves",
  "dependencies": ["List of things that need to happen first, or empty array"],
  "acceptance_criteria": ["List of 2-4 clear criteria for task completion"],
  "confidence": 0.0-1.0
}}

## Classification Guide
- **nikita_task**: Direct task for Jane Smith
- **team_task**: Task delegated to a team member (Deo, Beatrice, Hamed, etc.)
- **pmos_feature**: Feature request for PM-OS system
- **pmos_bug**: Bug report for PM-OS system
- **question**: Question needing an answer (not a task)
- **fyi**: Informational message (no action required)

## Urgency Guide
- **critical**: Contains "urgent", "ASAP", "blocker", "today", "immediately"
- **high**: Contains "soon", "this week", "important", "priority"
- **medium**: Normal requests with no urgency markers
- **low**: Contains "when you can", "no rush", "low priority"

Return ONLY valid JSON, no other text."""


def invoke_llm(
    prompt: str, temperature: float = 0.2, max_tokens: int = 2000
) -> Optional[str]:
    """
    Invoke LLM (Claude or Gemini) for task processing.

    Args:
        prompt: The prompt to send
        temperature: Lower = more consistent (0.2 for extraction)
        max_tokens: Max response length

    Returns:
        Response text or None on failure
    """
    if MODEL_BRIDGE_AVAILABLE:
        try:
            # Use model_bridge's unified interface
            active_model = detect_active_model()
            if active_model == "claude":
                result = invoke_claude(
                    prompt, max_tokens=max_tokens, temperature=temperature
                )
            else:
                result = invoke_gemini(
                    prompt, max_tokens=max_tokens, temperature=temperature
                )

            # model_bridge returns dict with 'response' key
            if isinstance(result, dict):
                if result.get("error"):
                    print(f"LLM error: {result['error']}", file=sys.stderr)
                    return None
                return result.get("response")
            return result
        except Exception as e:
            print(f"model_bridge invocation failed: {e}", file=sys.stderr)

    # Fallback to direct boto3 for Claude
    if BOTO3_AVAILABLE:
        try:
            return invoke_claude_direct(prompt, max_tokens, temperature)
        except Exception as e:
            print(f"Direct boto3 invocation failed: {e}", file=sys.stderr)

    return None


def invoke_claude_direct(
    prompt: str, max_tokens: int = 2000, temperature: float = 0.2
) -> Optional[str]:
    """Direct Claude invocation via AWS Bedrock."""
    aws_profile = os.getenv("AWS_PROFILE", "bedrock")
    aws_region = os.getenv("AWS_REGION", "eu-west-1")
    model_id = os.getenv("CLAUDE_MODEL_ID", "eu.anthropic.claude-opus-4-6-v1")

    try:
        session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
        client = session.client("bedrock-runtime")

        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            }
        )

        response = client.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read())
        return response_body.get("content", [{}])[0].get("text", "")

    except Exception as e:
        print(f"Claude direct invocation error: {e}", file=sys.stderr)
        return None


def parse_json_response(response: str) -> Optional[Dict]:
    """Extract JSON from LLM response."""
    if not response:
        return None

    try:
        # Try code block first
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            json_str = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            json_str = response[start:end].strip()
        else:
            # Direct JSON object
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
            else:
                return None

        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}", file=sys.stderr)
        return None


def process_mention_with_llm(
    raw_text: str, context: Optional[Dict[str, Any]] = None, model: str = "auto"
) -> Optional[FormalizedTask]:
    """
    Process a raw mention through LLM to create a formalized task.

    Args:
        raw_text: The original mention text
        context: Additional context (channel, requester, thread_link, etc.)
        model: "auto", "claude", or "gemini"

    Returns:
        FormalizedTask or None on failure
    """
    context = context or {}

    # Build additional context string
    additional_parts = []
    if context.get("thread_link"):
        additional_parts.append(f"Thread: {context['thread_link']}")
    if context.get("reply_count"):
        additional_parts.append(f"Thread has {context['reply_count']} replies")
    if context.get("thread_context"):
        additional_parts.append(f"\n**Thread Context:**\n{context['thread_context']}")
    if context.get("previous_tasks"):
        additional_parts.append(f"Related pending tasks: {context['previous_tasks']}")

    additional_context = "\n".join(additional_parts) if additional_parts else "None"

    # Build prompt
    prompt = FORMALIZE_TASK_PROMPT.format(
        requester=context.get("requester", "Unknown"),
        channel=context.get("channel", "unknown"),
        raw_text=raw_text,
        additional_context=additional_context,
    )

    # Invoke LLM
    print(f"  Processing with LLM...", file=sys.stderr)
    response = invoke_llm(prompt, temperature=0.2, max_tokens=2000)

    if not response:
        print(f"  LLM returned no response", file=sys.stderr)
        return None

    # Parse response
    parsed = parse_json_response(response)
    if not parsed:
        print(f"  Failed to parse LLM response", file=sys.stderr)
        return None

    # Build FormalizedTask
    try:
        task = FormalizedTask(
            title=parsed.get("title", "Untitled Task"),
            description=parsed.get("description", raw_text),
            task_type=parsed.get("task_type", "general"),
            assignee=parsed.get("assignee"),
            delegator=parsed.get("delegator", context.get("requester")),
            deadline=parsed.get("deadline"),
            urgency=parsed.get("urgency", "medium"),
            context_summary=parsed.get("context_summary", ""),
            dependencies=parsed.get("dependencies", []),
            acceptance_criteria=parsed.get("acceptance_criteria", []),
            original_text=raw_text,
            confidence=parsed.get("confidence", 0.7),
            processed_at=datetime.now(timezone.utc).isoformat(),
            model_used=detect_active_model() if MODEL_BRIDGE_AVAILABLE else "claude",
        )
        return task
    except Exception as e:
        print(f"  Failed to build FormalizedTask: {e}", file=sys.stderr)
        return None


def format_task_markdown(task: FormalizedTask) -> str:
    """Format a formalized task as markdown."""
    lines = [
        f"## {task.title}",
        "",
        f"**Type:** {task.task_type}",
        f"**Assignee:** {task.assignee or 'Unassigned'}",
        f"**Urgency:** {task.urgency}",
    ]

    if task.deadline:
        lines.append(f"**Deadline:** {task.deadline}")

    lines.extend(
        [
            "",
            "### Description",
            task.description,
            "",
        ]
    )

    if task.context_summary:
        lines.extend(
            [
                "### Context",
                task.context_summary,
                "",
            ]
        )

    if task.acceptance_criteria:
        lines.append("### Acceptance Criteria")
        for criterion in task.acceptance_criteria:
            lines.append(f"- [ ] {criterion}")
        lines.append("")

    if task.dependencies:
        lines.append("### Dependencies")
        for dep in task.dependencies:
            lines.append(f"- {dep}")
        lines.append("")

    lines.extend(
        [
            "---",
            f'*Original: "{task.original_text[:100]}..."*',
            f"*Delegator: {task.delegator} | Confidence: {task.confidence:.0%} | Model: {task.model_used}*",
        ]
    )

    return "\n".join(lines)


# --- CLI for testing ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LLM Mention Processor")
    parser.add_argument("text", nargs="?", help="Mention text to process")
    parser.add_argument("--channel", default="test-channel", help="Channel name")
    parser.add_argument("--requester", default="Test User", help="Requester name")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.text:
        # Demo mode
        test_cases = [
            "@pmos-slack-bot remind Nikita to review the OTP PRD before Friday - this is blocking the launch",
            "@pmos-slack-bot task for Deo: follow up with engineering on the API timeline, we need this for Q1",
            "@pmos-slack-bot PM-OS feature request: add ability to sync Confluence pages automatically",
            "@pmos-slack-bot bug: the context updater times out when processing large documents over 100KB",
        ]

        print("=== LLM Mention Processor Demo ===\n")
        for text in test_cases:
            print(f"Input: {text}\n")
            result = process_mention_with_llm(
                text, context={"channel": "demo-channel", "requester": "Demo User"}
            )
            if result:
                if args.json:
                    print(json.dumps(asdict(result), indent=2))
                else:
                    print(format_task_markdown(result))
            else:
                print("  [Failed to process]")
            print("\n" + "=" * 60 + "\n")
    else:
        # Process provided text
        result = process_mention_with_llm(
            args.text, context={"channel": args.channel, "requester": args.requester}
        )
        if result:
            if args.json:
                print(json.dumps(asdict(result), indent=2))
            else:
                print(format_task_markdown(result))
        else:
            print("Failed to process mention")
            sys.exit(1)
