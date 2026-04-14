#!/usr/bin/env python3
"""
LLM Synthesizer Abstraction (v5.0)

Model-agnostic synthesis layer for meeting prep content generation.
Supports multiple backends with config-driven model selection:
  - Gemini (Google AI)
  - Bedrock (AWS Claude)
  - Claude Code (inline session)
  - Template (no-LLM fallback)

Port from v4.x llm_synthesizer.py:
  - Hardcoded model IDs and regions replaced with config lookups
  - print() replaced with logging
  - Config access via pm_os_base.tools.core.config_loader

Usage:
    from meeting.llm_synthesizer import get_synthesizer, synthesize_meeting_prep

    synthesizer = get_synthesizer()
    result = synthesizer.synthesize(prompt, context)
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from config_loader import get_config
    except ImportError:
        get_config = None

# Optional: boto3 for Bedrock
try:
    import boto3
    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SynthesisResult:
    """Result of synthesis operation."""
    content: str
    model_id: str
    success: bool
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class LLMSynthesizer(ABC):
    """Abstract base class for LLM synthesizers."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Return identifier for this synthesizer."""

    @abstractmethod
    def synthesize(self, prompt: str, context: Dict) -> SynthesisResult:
        """Synthesize content using the LLM."""

    def is_available(self) -> bool:
        """Check if this synthesizer is available for use."""
        return True


# ---------------------------------------------------------------------------
# Gemini backend
# ---------------------------------------------------------------------------


class GeminiSynthesizer(LLMSynthesizer):
    """Synthesizer using Google Gemini API."""

    def __init__(self, config=None):
        self._config = config
        self._api_key: Optional[str] = None
        self._model = None
        self._model_name: Optional[str] = None

    @property
    def model_id(self) -> str:
        return self._model_name or "gemini"

    def is_available(self) -> bool:
        try:
            import google.generativeai  # noqa: F401
            cfg = self._get_gemini_config()
            return bool(cfg.get("api_key"))
        except ImportError:
            return False

    def _get_gemini_config(self) -> Dict:
        if self._config:
            return {
                "api_key": self._config.get("gemini.api_key", ""),
                "model": self._config.get("gemini.model", "gemini-2.5-flash"),
            }
        return {}

    def _initialize(self):
        if self._model is not None:
            return
        import google.generativeai as genai
        cfg = self._get_gemini_config()
        self._api_key = cfg.get("api_key")
        self._model_name = cfg.get("model", "gemini-2.5-flash")
        genai.configure(api_key=self._api_key)
        self._model = genai.GenerativeModel(self._model_name)

    def synthesize(self, prompt: str, context: Dict) -> SynthesisResult:
        try:
            self._initialize()
            response = self._model.generate_content(prompt)
            return SynthesisResult(
                content=response.text, model_id=self._model_name, success=True
            )
        except Exception as exc:
            logger.warning("Gemini synthesis failed: %s", exc)
            return SynthesisResult(
                content="", model_id=self.model_id, success=False, error=str(exc)
            )


# ---------------------------------------------------------------------------
# Bedrock backend
# ---------------------------------------------------------------------------


class BedrockSynthesizer(LLMSynthesizer):
    """Synthesizer using AWS Bedrock (Claude)."""

    def __init__(self, config=None):
        self._config = config
        self._client = None
        self._model_id: Optional[str] = None
        self._region: Optional[str] = None

    @property
    def model_id(self) -> str:
        if self._model_id:
            return self._model_id
        if self._config:
            return self._config.get("meeting_prep.bedrock_model", "")
        return os.environ.get("BEDROCK_MODEL_ID", "bedrock")

    def is_available(self) -> bool:
        if not BEDROCK_AVAILABLE:
            return False
        try:
            session = boto3.Session()
            credentials = session.get_credentials()
            return credentials is not None
        except Exception:
            return False

    def _initialize(self):
        if self._client is not None:
            return
        if self._config:
            self._model_id = self._config.get(
                "meeting_prep.bedrock_model", ""
            )
            self._region = self._config.get(
                "meeting_prep.aws_region",
                os.environ.get("AWS_REGION", ""),
            )
        else:
            self._model_id = os.environ.get("BEDROCK_MODEL_ID", "")
            self._region = os.environ.get("AWS_REGION", "")

        self._client = boto3.client(
            "bedrock-runtime", region_name=self._region
        )

    def synthesize(self, prompt: str, context: Dict) -> SynthesisResult:
        try:
            self._initialize()
            response = self._client.invoke_model(
                modelId=self._model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 8000,
                        "messages": [{"role": "user", "content": prompt}],
                    }
                ),
            )
            response_body = json.loads(response["body"].read())
            response_text = response_body["content"][0]["text"]
            return SynthesisResult(
                content=response_text, model_id=self._model_id, success=True
            )
        except Exception as exc:
            logger.warning("Bedrock synthesis failed: %s", exc)
            return SynthesisResult(
                content="", model_id=self.model_id, success=False, error=str(exc)
            )


# ---------------------------------------------------------------------------
# Claude Code backend
# ---------------------------------------------------------------------------


class ClaudeCodeSynthesizer(LLMSynthesizer):
    """
    Synthesizer for Claude Code sessions.

    Returns structured prompts that Claude Code will process inline.
    """

    @property
    def model_id(self) -> str:
        return "claude-code"

    def is_available(self) -> bool:
        return bool(os.environ.get("CLAUDE_CODE_SESSION"))

    def synthesize(self, prompt: str, context: Dict) -> SynthesisResult:
        structured_prompt = (
            "<meeting_prep_synthesis>\n"
            f"{prompt}\n"
            "</meeting_prep_synthesis>\n\n"
            "Please synthesize the meeting prep content based on the above instructions.\n"
        )
        return SynthesisResult(
            content=structured_prompt, model_id="claude-code", success=True
        )


# ---------------------------------------------------------------------------
# Template fallback
# ---------------------------------------------------------------------------


class TemplateSynthesizer(LLMSynthesizer):
    """
    Fallback template-based synthesizer.

    Used when no LLM is available. Generates basic structured output
    using template filling without AI synthesis.
    """

    @property
    def model_id(self) -> str:
        return "template"

    def synthesize(self, prompt: str, context: Dict) -> SynthesisResult:
        participants = context.get("participant_context", [])
        action_items = context.get("action_items", [])
        topics = context.get("topic_context", [])
        past_notes = context.get("past_notes", "")
        series_history = context.get("series_history", [])

        participant_lines = [
            f"- **{p.get('name', 'Unknown')}**: {p.get('role', '')}"
            for p in participants
        ]
        action_lines = [
            f"- {'[x]' if item.get('completed') else '[ ]'} "
            f"**{item.get('owner', 'Unknown')}**: {item.get('task', '')}"
            for item in action_items
        ]
        topic_lines = [
            f"### {t.get('name', 'Unknown')} ({t.get('status', '')})\n"
            f"{t.get('summary', '')[:200]}"
            for t in topics
        ]
        history_lines = [
            f"### {entry.get('date', '')}\n{entry.get('summary', '')[:300]}"
            for entry in series_history[:3]
        ]

        content = f"""## TL;DR

- Meeting prep generated using template (no AI synthesis available)
- {len(participants)} participants
- {len(action_items)} outstanding action items
- {len(topics)} related topics/projects

## Participants

{chr(10).join(participant_lines) if participant_lines else "No participant data available."}

## Outstanding Action Items

{chr(10).join(action_lines) if action_lines else "No action items found for participants."}

## Related Topics/Projects

{chr(10).join(topic_lines) if topic_lines else "No related topics found."}

## Previous Meeting History

{chr(10).join(history_lines) if history_lines else "No previous meeting history found."}

## Past Notes Summary

{past_notes[:500] if past_notes else "No past meeting notes found."}

---
*Note: This content was generated using template fallback. For richer synthesis, configure an LLM backend.*
"""
        return SynthesisResult(content=content, model_id="template", success=True)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_synthesizer(
    preferred: Optional[str] = None, config=None
) -> LLMSynthesizer:
    """
    Get the appropriate synthesizer for the current runtime environment.

    Args:
        preferred: Optional preferred synthesizer
            ("auto", "gemini", "claude", "bedrock", "template")
        config: PM-OS ConfigLoader instance (auto-loaded if None).

    Returns:
        LLMSynthesizer instance.

    Resolution order (when auto):
        1. Claude Code session
        2. Bedrock credentials
        3. Gemini API key
        4. Template fallback
    """
    if config is None and get_config is not None:
        try:
            config = get_config()
        except Exception:
            pass

    if preferred is None and config is not None:
        preferred = config.get("meeting_prep.preferred_model", "auto")
    preferred = preferred or "auto"

    # Check PMOS_LLM_PROVIDER env var
    if preferred == "auto":
        llm_provider = os.environ.get("PMOS_LLM_PROVIDER", "").lower()
        if llm_provider in ("bedrock", "gemini", "claude", "template"):
            preferred = llm_provider

    # Explicit preference
    _explicit_map = {
        "bedrock": lambda: BedrockSynthesizer(config),
        "gemini": lambda: GeminiSynthesizer(config),
        "claude": lambda: ClaudeCodeSynthesizer(),
        "template": lambda: TemplateSynthesizer(),
    }

    if preferred in _explicit_map and preferred != "auto":
        synth = _explicit_map[preferred]()
        if synth.is_available():
            logger.info("Synthesizer: %s (%s)", type(synth).__name__, synth.model_id)
            return synth
        logger.info(
            "%s unavailable, falling back to auto-detection",
            type(synth).__name__,
        )
        preferred = "auto"

    # Auto-detection chain
    for factory in [
        ClaudeCodeSynthesizer,
        lambda: BedrockSynthesizer(config),
        lambda: GeminiSynthesizer(config),
    ]:
        synth = factory()
        if synth.is_available():
            logger.info(
                "Synthesizer: %s (%s) [auto]",
                type(synth).__name__,
                synth.model_id,
            )
            return synth

    logger.info("Synthesizer: TemplateSynthesizer (template) [fallback]")
    return TemplateSynthesizer()


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def synthesize_meeting_prep(
    prompt: str, context: Dict, preferred: Optional[str] = None, config=None
) -> str:
    """
    Synthesize meeting prep content using the best available backend.

    Args:
        prompt: Synthesis prompt instructions.
        context: Meeting context data.
        preferred: Optional preferred synthesizer.
        config: PM-OS ConfigLoader instance.

    Returns:
        Generated content string.
    """
    synthesizer = get_synthesizer(preferred, config=config)
    result = synthesizer.synthesize(prompt, context)

    if not result.success:
        logger.warning("Synthesis error (%s): %s", result.model_id, result.error)
        fallback = TemplateSynthesizer()
        result = fallback.synthesize(prompt, context)

    return result.content
