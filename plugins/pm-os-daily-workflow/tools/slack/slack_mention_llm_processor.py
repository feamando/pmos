#!/usr/bin/env python3
"""
Slack Mention LLM Processor (v5.0)

Uses LLM (via connector_bridge or AWS Bedrock) to transform raw @mentions
into formalized, actionable tasks with structured metadata.

Ported from v4.x slack_mention_llm_processor.py — AWS defaults from config,
model from config, no hardcoded credentials or region.

Usage:
    from slack_mention_llm_processor import process_mention_with_llm

    enhanced_task = process_mention_with_llm(
        raw_text="@bot remind user to review the PRD before Friday",
        context={"channel": "product-team", "requester": "Alice"}
    )
"""

import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# v5 shared utils
try:
    from pm_os_base.tools.core.config_loader import get_config
    from pm_os_base.tools.core.connector_bridge import get_auth
except ImportError:
    try:
        _base = __import__("pathlib").Path(__file__).resolve().parent.parent.parent.parent
        sys.path.insert(0, str(_base / "pm-os-base" / "tools" / "core"))
        from config_loader import get_config
        from connector_bridge import get_auth
    except ImportError:
        logger.error("Cannot import pm_os_base core modules")
        raise

# Try to import model_bridge
try:
    from util.model_bridge import detect_active_model, invoke_claude, invoke_gemini
    MODEL_BRIDGE_AVAILABLE = True
except ImportError:
    MODEL_BRIDGE_AVAILABLE = False

# Try direct boto3
try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


@dataclass
class FormalizedTask:
    """A formalized, actionable task derived from a mention."""
    title: str
    description: str
    task_type: str
    assignee: Optional[str]
    delegator: Optional[str]
    deadline: Optional[str]
    urgency: str
    context_summary: str
    dependencies: list
    acceptance_criteria: list
    original_text: str
    confidence: float
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
  "title": "Short, imperative action title (max 10 words)",
  "description": "Full formalized task description with context.",
  "task_type": "One of: owner_task, team_task, pmos_feature, pmos_bug, question, fyi",
  "assignee": "Name of person who should do this (or null if unclear)",
  "delegator": "Name of person who requested this",
  "deadline": "Extracted deadline in ISO format or relative term, or null",
  "urgency": "One of: critical, high, medium, low",
  "context_summary": "1-2 sentence summary of why this task matters",
  "dependencies": ["List of things that need to happen first, or empty array"],
  "acceptance_criteria": ["List of 2-4 clear criteria for task completion"],
  "confidence": 0.0-1.0
}}

Return ONLY valid JSON, no other text."""


def _get_aws_region() -> str:
    """Get AWS region from config."""
    return get_config().get("meeting_prep.aws_region", "")


def _get_model_id() -> str:
    """Get model ID from config."""
    return get_config().get("meeting_prep.model_id", "")


def _get_aws_profile() -> str:
    """Get AWS profile from config."""
    return get_config().get("meeting_prep.aws_profile", "")


def invoke_llm(
    prompt: str, temperature: float = 0.2, max_tokens: int = 2000,
) -> Optional[str]:
    """
    Invoke LLM (Claude or Gemini) for task processing.

    Args:
        prompt: The prompt to send
        temperature: Lower = more consistent
        max_tokens: Max response length

    Returns:
        Response text or None on failure
    """
    if MODEL_BRIDGE_AVAILABLE:
        try:
            active_model = detect_active_model()
            if active_model == "claude":
                result = invoke_claude(
                    prompt, max_tokens=max_tokens, temperature=temperature
                )
            else:
                result = invoke_gemini(
                    prompt, max_tokens=max_tokens, temperature=temperature
                )

            if isinstance(result, dict):
                if result.get("error"):
                    logger.error("LLM error: %s", result["error"])
                    return None
                return result.get("response")
            return result
        except Exception as e:
            logger.warning("model_bridge invocation failed: %s", e)

    # Fallback to direct boto3 for Claude
    if BOTO3_AVAILABLE:
        try:
            return _invoke_claude_direct(prompt, max_tokens, temperature)
        except Exception as e:
            logger.warning("Direct boto3 invocation failed: %s", e)

    return None


def _invoke_claude_direct(
    prompt: str, max_tokens: int = 2000, temperature: float = 0.2,
) -> Optional[str]:
    """Direct Claude invocation via AWS Bedrock — all params from config."""
    aws_profile = _get_aws_profile()
    aws_region = _get_aws_region()
    model_id = _get_model_id()

    if not aws_region or not model_id:
        logger.error("AWS region or model ID not configured")
        return None

    try:
        session_kwargs = {"region_name": aws_region}
        if aws_profile:
            session_kwargs["profile_name"] = aws_profile

        session = boto3.Session(**session_kwargs)
        client = session.client("bedrock-runtime")

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        })

        response = client.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read())
        return response_body.get("content", [{}])[0].get("text", "")

    except Exception as e:
        logger.error("Claude direct invocation error: %s", e)
        return None


def parse_json_response(response: str) -> Optional[Dict]:
    """Extract JSON from LLM response."""
    if not response:
        return None

    try:
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            json_str = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            json_str = response[start:end].strip()
        else:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
            else:
                return None

        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning("JSON parse error: %s", e)
        return None


def process_mention_with_llm(
    raw_text: str, context: Optional[Dict[str, Any]] = None, model: str = "auto",
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

    additional_parts = []
    if context.get("thread_link"):
        additional_parts.append("Thread: %s" % context["thread_link"])
    if context.get("reply_count"):
        additional_parts.append("Thread has %s replies" % context["reply_count"])
    if context.get("thread_context"):
        additional_parts.append(
            "\n**Thread Context:**\n%s" % context["thread_context"]
        )
    if context.get("previous_tasks"):
        additional_parts.append(
            "Related pending tasks: %s" % context["previous_tasks"]
        )

    additional_context = "\n".join(additional_parts) if additional_parts else "None"

    prompt = FORMALIZE_TASK_PROMPT.format(
        requester=context.get("requester", "Unknown"),
        channel=context.get("channel", "unknown"),
        raw_text=raw_text,
        additional_context=additional_context,
    )

    logger.info("Processing with LLM...")
    response = invoke_llm(prompt, temperature=0.2, max_tokens=2000)

    if not response:
        logger.warning("LLM returned no response")
        return None

    parsed = parse_json_response(response)
    if not parsed:
        logger.warning("Failed to parse LLM response")
        return None

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
        logger.error("Failed to build FormalizedTask: %s", e)
        return None


def format_task_markdown(task: FormalizedTask) -> str:
    """Format a formalized task as markdown."""
    lines = [
        "## %s" % task.title,
        "",
        "**Type:** %s" % task.task_type,
        "**Assignee:** %s" % (task.assignee or "Unassigned"),
        "**Urgency:** %s" % task.urgency,
    ]

    if task.deadline:
        lines.append("**Deadline:** %s" % task.deadline)

    lines.extend([
        "",
        "### Description",
        task.description,
        "",
    ])

    if task.context_summary:
        lines.extend([
            "### Context",
            task.context_summary,
            "",
        ])

    if task.acceptance_criteria:
        lines.append("### Acceptance Criteria")
        for criterion in task.acceptance_criteria:
            lines.append("- [ ] %s" % criterion)
        lines.append("")

    if task.dependencies:
        lines.append("### Dependencies")
        for dep in task.dependencies:
            lines.append("- %s" % dep)
        lines.append("")

    lines.extend([
        "---",
        '*Original: "%s..."*' % task.original_text[:100],
        "*Delegator: %s | Confidence: %.0f%% | Model: %s*" % (
            task.delegator, task.confidence * 100, task.model_used,
        ),
    ])

    return "\n".join(lines)


# --- CLI for testing ---
if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="LLM Mention Processor")
    parser.add_argument("text", nargs="?", help="Mention text to process")
    parser.add_argument("--channel", default="test-channel", help="Channel name")
    parser.add_argument("--requester", default="Test User", help="Requester name")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.text:
        result = process_mention_with_llm(
            args.text,
            context={"channel": args.channel, "requester": args.requester},
        )
        if result:
            if args.json:
                print(json.dumps(asdict(result), indent=2))
            else:
                print(format_task_markdown(result))
        else:
            print("Failed to process mention")
            sys.exit(1)
    else:
        print("Usage: python slack_mention_llm_processor.py 'mention text'")
