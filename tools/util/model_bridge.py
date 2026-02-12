#!/usr/bin/env python3
"""
Model Bridge - Cross-model invocation for Orthogonal Challenge System.

Handles invocation of Claude (via Bedrock) and Gemini (via API) for the
three-round document challenge process.

Usage:
    python3 model_bridge.py --model gemini --prompt "Review this document" --context doc.md
    python3 model_bridge.py --model claude --prompt "Resolve challenges" --context v2.md
    python3 model_bridge.py --detect  # Detect active model
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

# Add common directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    import config_loader
except ImportError:
    config_loader = None

# ============================================================================
# CONFIGURATION
# ============================================================================

# AWS Bedrock configuration
AWS_REGION = os.getenv("AWS_REGION", "eu-west-1")
AWS_PROFILE = os.getenv("AWS_PROFILE", "bedrock")
CLAUDE_MODEL_ID = os.getenv("CLAUDE_MODEL_ID", "eu.anthropic.claude-opus-4-6-v1")

# Gemini configuration
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Orthogonal configuration
DEFAULT_CHALLENGER = os.getenv("ORTHOGONAL_CHALLENGER_MODEL", "gemini")

# ============================================================================
# MODEL DETECTION
# ============================================================================


def detect_active_model() -> str:
    """
    Detect which model is currently running.

    Returns: 'claude' or 'gemini'
    """
    # Check for Claude Code environment
    if os.getenv("CLAUDE_CODE_SESSION") or os.getenv("ANTHROPIC_API_KEY"):
        return "claude"

    # Check for Gemini CLI environment
    if os.getenv("GEMINI_CLI_SESSION") or os.getenv("GOOGLE_AI_STUDIO"):
        return "gemini"

    # Check for PM-OS context files that indicate Claude Code
    claude_markers = [
        ".claude/commands",
        "AI_Guidance/Tools/session_manager.py",
    ]
    for marker in claude_markers:
        if os.path.exists(marker):
            return "claude"

    # Default to claude if running from PM-OS environment
    return "claude"


def get_challenger_model(active_model: str) -> str:
    """Get the challenger model (opposite of active)."""
    if active_model == "claude":
        return "gemini"
    else:
        return "claude"


# ============================================================================
# CLAUDE INVOCATION (via AWS Bedrock)
# ============================================================================


def invoke_claude(
    prompt: str,
    context: Optional[Dict[str, Any]] = None,
    max_tokens: int = 8192,
    temperature: float = 0.3,
) -> Dict[str, Any]:
    """
    Invoke Claude via AWS Bedrock.

    Args:
        prompt: The prompt to send to Claude
        context: Optional context dict with 'documents', 'fpf_state', etc.
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature

    Returns:
        Dict with 'response', 'model', 'tokens', 'timestamp'
    """
    try:
        import boto3
    except ImportError:
        return {
            "error": "boto3 not installed. Run: pip install boto3",
            "model": "claude",
        }

    try:
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        client = session.client("bedrock-runtime")
    except Exception as e:
        return {"error": f"Failed to connect to AWS Bedrock: {e}", "model": "claude"}

    # Build the full prompt with context
    full_prompt = prompt
    if context:
        context_parts = []
        if context.get("documents"):
            for doc in context["documents"]:
                context_parts.append(
                    f"## Document: {doc.get('name', 'Unknown')}\n{doc.get('content', '')}"
                )
        if context.get("fpf_state"):
            context_parts.append(
                f"## FPF State\n```json\n{json.dumps(context['fpf_state'], indent=2)}\n```"
            )
        if context.get("challenges"):
            context_parts.append(
                f"## Challenges\n```json\n{json.dumps(context['challenges'], indent=2)}\n```"
            )

        if context_parts:
            full_prompt = "\n\n".join(context_parts) + "\n\n---\n\n" + prompt

    # Build request body
    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": full_prompt}],
            "temperature": temperature,
        }
    )

    try:
        response = client.invoke_model(
            modelId=CLAUDE_MODEL_ID,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read())
        text = response_body.get("content", [{}])[0].get("text", "")

        return {
            "response": text,
            "model": "claude",
            "model_id": CLAUDE_MODEL_ID,
            "tokens": {
                "input": response_body.get("usage", {}).get("input_tokens", 0),
                "output": response_body.get("usage", {}).get("output_tokens", 0),
            },
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"error": f"Claude invocation failed: {e}", "model": "claude"}


# ============================================================================
# GEMINI INVOCATION (via API)
# ============================================================================


def invoke_gemini(
    prompt: str,
    context: Optional[Dict[str, Any]] = None,
    max_tokens: int = 8192,
    temperature: float = 0.3,
    use_deep_research: bool = False,
) -> Dict[str, Any]:
    """
    Invoke Gemini via Google AI API.

    Args:
        prompt: The prompt to send to Gemini
        context: Optional context dict with 'documents', 'fpf_state', etc.
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature
        use_deep_research: Use Deep Research agent (slower, more thorough)

    Returns:
        Dict with 'response', 'model', 'tokens', 'timestamp'
    """
    # Get API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key and config_loader:
        gemini_config = config_loader.get_gemini_config()
        api_key = gemini_config.get("api_key")

    if not api_key:
        return {"error": "GEMINI_API_KEY not set", "model": "gemini"}

    # Build the full prompt with context
    full_prompt = prompt
    if context:
        context_parts = []
        if context.get("documents"):
            for doc in context["documents"]:
                context_parts.append(
                    f"## Document: {doc.get('name', 'Unknown')}\n{doc.get('content', '')}"
                )
        if context.get("fpf_state"):
            context_parts.append(
                f"## FPF State\n```json\n{json.dumps(context['fpf_state'], indent=2)}\n```"
            )
        if context.get("challenges"):
            context_parts.append(
                f"## Challenges\n```json\n{json.dumps(context['challenges'], indent=2)}\n```"
            )

        if context_parts:
            full_prompt = "\n\n".join(context_parts) + "\n\n---\n\n" + prompt

    if use_deep_research:
        return _invoke_gemini_deep_research(full_prompt, api_key)
    else:
        return _invoke_gemini_standard(full_prompt, api_key, max_tokens, temperature)


def _invoke_gemini_standard(
    prompt: str, api_key: str, max_tokens: int, temperature: float
) -> Dict[str, Any]:
    """Standard Gemini invocation."""
    try:
        import google.generativeai as genai
    except ImportError:
        return {
            "error": "google-generativeai not installed. Run: pip install google-generativeai",
            "model": "gemini",
        }

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            GEMINI_MODEL,
            generation_config={
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            },
        )

        response = model.generate_content(prompt)

        return {
            "response": response.text,
            "model": "gemini",
            "model_id": GEMINI_MODEL,
            "tokens": {
                "input": getattr(response, "prompt_token_count", 0),
                "output": getattr(response, "candidates_token_count", 0),
            },
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"error": f"Gemini invocation failed: {e}", "model": "gemini"}


def _invoke_gemini_deep_research(prompt: str, api_key: str) -> Dict[str, Any]:
    """Deep Research Gemini invocation (for thorough analysis)."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return {
            "error": "google-genai not installed. Run: pip install google-genai",
            "model": "gemini",
        }

    try:
        client = genai.Client(api_key=api_key)

        # Use Deep Research agent
        agent = "deep-research-pro-preview-12-2025"

        interaction = client.interactions.create(
            input=prompt,
            agent=agent,
            background=True,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )

        # Poll for completion (simplified - full implementation in orthogonal_challenge.py)
        import time

        max_wait = 300  # 5 minutes
        start = time.time()

        while time.time() - start < max_wait:
            result = client.interactions.get(id=interaction.id)
            if result.status == "completed":
                # Extract text from outputs
                text = ""
                if result.outputs:
                    for output in result.outputs:
                        if hasattr(output, "text") and output.text:
                            text = output.text
                            break
                        elif hasattr(output, "parts"):
                            for part in output.parts:
                                if hasattr(part, "text") and part.text:
                                    text = part.text
                                    break

                return {
                    "response": text,
                    "model": "gemini",
                    "model_id": agent,
                    "deep_research": True,
                    "timestamp": datetime.now().isoformat(),
                }
            elif result.status == "failed":
                return {"error": "Deep Research failed", "model": "gemini"}

            time.sleep(10)

        return {"error": "Deep Research timed out", "model": "gemini"}

    except Exception as e:
        return {"error": f"Gemini Deep Research failed: {e}", "model": "gemini"}


# ============================================================================
# UNIFIED INVOCATION
# ============================================================================


def invoke_model(
    model: str, prompt: str, context: Optional[Dict[str, Any]] = None, **kwargs
) -> Dict[str, Any]:
    """
    Invoke the specified model.

    Args:
        model: 'claude' or 'gemini'
        prompt: The prompt to send
        context: Optional context dict
        **kwargs: Additional model-specific arguments

    Returns:
        Dict with 'response', 'model', 'tokens', 'timestamp', or 'error'
    """
    if model == "claude":
        return invoke_claude(prompt, context, **kwargs)
    elif model == "gemini":
        return invoke_gemini(prompt, context, **kwargs)
    else:
        return {
            "error": f"Unknown model: {model}. Use 'claude' or 'gemini'.",
            "model": model,
        }


def invoke_challenger(
    prompt: str, context: Optional[Dict[str, Any]] = None, **kwargs
) -> Dict[str, Any]:
    """
    Invoke the challenger model (opposite of current active model).

    Args:
        prompt: The prompt to send
        context: Optional context dict
        **kwargs: Additional model-specific arguments

    Returns:
        Dict with 'response', 'model', 'tokens', 'timestamp', or 'error'
    """
    active = detect_active_model()
    challenger = get_challenger_model(active)
    return invoke_model(challenger, prompt, context, **kwargs)


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Cross-model invocation for Orthogonal Challenge System"
    )
    parser.add_argument(
        "--model",
        choices=["claude", "gemini", "challenger"],
        help="Model to invoke (or 'challenger' for opposite of active)",
    )
    parser.add_argument("--prompt", type=str, help="Prompt to send to the model")
    parser.add_argument(
        "--context", type=str, help="Path to context file (markdown or JSON)"
    )
    parser.add_argument(
        "--detect", action="store_true", help="Detect active model and exit"
    )
    parser.add_argument(
        "--deep-research",
        action="store_true",
        help="Use Gemini Deep Research (slower, more thorough)",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.detect:
        active = detect_active_model()
        challenger = get_challenger_model(active)
        if args.json:
            print(
                json.dumps(
                    {"active_model": active, "challenger_model": challenger}, indent=2
                )
            )
        else:
            print(f"Active model: {active}")
            print(f"Challenger model: {challenger}")
        return 0

    if not args.model or not args.prompt:
        parser.print_help()
        return 1

    # Load context if provided
    context = None
    if args.context:
        context_path = args.context
        if os.path.exists(context_path):
            with open(context_path, "r", encoding="utf-8") as f:
                content = f.read()

            if context_path.endswith(".json"):
                context = json.loads(content)
            else:
                context = {
                    "documents": [
                        {"name": os.path.basename(context_path), "content": content}
                    ]
                }

    # Invoke model
    if args.model == "challenger":
        result = invoke_challenger(
            args.prompt, context, use_deep_research=args.deep_research
        )
    else:
        result = invoke_model(
            args.model, args.prompt, context, use_deep_research=args.deep_research
        )

    # Output
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result.get("error"):
            print(f"Error: {result['error']}", file=sys.stderr)
            return 1
        else:
            print(f"Model: {result.get('model')} ({result.get('model_id', 'unknown')})")
            print(f"Timestamp: {result.get('timestamp')}")
            print("-" * 60)
            print(result.get("response", ""))

    return 0


if __name__ == "__main__":
    sys.exit(main())
