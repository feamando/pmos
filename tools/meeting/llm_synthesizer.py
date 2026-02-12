"""
LLM Synthesizer Abstraction

Model-agnostic synthesis layer for meeting prep content generation.
Supports multiple backends: Gemini, Claude Code, Template fallback.

Usage:
    from llm_synthesizer import get_synthesizer

    synthesizer = get_synthesizer()
    content = synthesizer.synthesize(prompt, context)
"""

import json
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional

# Add parent directory to path for config_loader
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config_loader

# Try to import boto3 for AWS Bedrock
try:
    import boto3

    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False


@dataclass
class SynthesisResult:
    """Result of synthesis operation."""

    content: str
    model_id: str
    success: bool
    error: Optional[str] = None


class LLMSynthesizer(ABC):
    """Abstract base class for LLM synthesizers."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Return identifier for this synthesizer."""
        pass

    @abstractmethod
    def synthesize(self, prompt: str, context: Dict) -> SynthesisResult:
        """
        Synthesize content using the LLM.

        Args:
            prompt: The prompt instructions for synthesis
            context: Context data for the meeting

        Returns:
            SynthesisResult with generated content
        """
        pass

    def is_available(self) -> bool:
        """Check if this synthesizer is available for use."""
        return True


class GeminiSynthesizer(LLMSynthesizer):
    """Synthesizer using Google Gemini API."""

    def __init__(self):
        self._api_key = None
        self._model = None
        self._model_name = None

    @property
    def model_id(self) -> str:
        return self._model_name or "gemini"

    def is_available(self) -> bool:
        """Check if Gemini API is available."""
        try:
            import google.generativeai as genai

            gemini_config = config_loader.get_gemini_config()
            return bool(gemini_config.get("api_key"))
        except ImportError:
            return False

    def _initialize(self):
        """Initialize Gemini model on first use."""
        if self._model is not None:
            return

        import google.generativeai as genai

        gemini_config = config_loader.get_gemini_config()
        self._api_key = gemini_config.get("api_key")
        self._model_name = gemini_config.get("model", "gemini-2.5-flash")

        genai.configure(api_key=self._api_key)
        self._model = genai.GenerativeModel(self._model_name)

    def synthesize(self, prompt: str, context: Dict) -> SynthesisResult:
        """Synthesize content using Gemini."""
        try:
            self._initialize()

            response = self._model.generate_content(prompt)

            return SynthesisResult(
                content=response.text, model_id=self._model_name, success=True
            )

        except Exception as e:
            return SynthesisResult(
                content="", model_id=self.model_id, success=False, error=str(e)
            )


class BedrockSynthesizer(LLMSynthesizer):
    """Synthesizer using AWS Bedrock (Claude)."""

    BEDROCK_MODEL_ID = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"

    def __init__(self):
        self._client = None

    @property
    def model_id(self) -> str:
        return self.BEDROCK_MODEL_ID

    def is_available(self) -> bool:
        """Check if Bedrock is available."""
        if not BEDROCK_AVAILABLE:
            return False
        try:
            session = boto3.Session()
            credentials = session.get_credentials()
            return credentials is not None
        except Exception:
            return False

    def _initialize(self):
        """Initialize Bedrock client on first use."""
        if self._client is not None:
            return
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("AWS_REGION", "eu-central-1"),
        )

    def synthesize(self, prompt: str, context: Dict) -> SynthesisResult:
        """Synthesize content using Bedrock Claude."""
        try:
            self._initialize()

            response = self._client.invoke_model(
                modelId=self.BEDROCK_MODEL_ID,
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
                content=response_text, model_id=self.BEDROCK_MODEL_ID, success=True
            )

        except Exception as e:
            return SynthesisResult(
                content="", model_id=self.model_id, success=False, error=str(e)
            )


class ClaudeCodeSynthesizer(LLMSynthesizer):
    """
    Synthesizer for Claude Code sessions.

    Instead of making API calls, this returns structured prompts
    that Claude Code will process inline in the same session.
    """

    @property
    def model_id(self) -> str:
        return "claude-code"

    def is_available(self) -> bool:
        """Check if running in Claude Code session."""
        return config_loader.is_claude_code_session()

    def synthesize(self, prompt: str, context: Dict) -> SynthesisResult:
        """
        Return prompt for Claude Code to process inline.

        Since we're already in a Claude session, we return the prompt
        as structured content for the calling context to handle.
        """
        # For Claude Code, we return the prompt as-is
        # The calling code (meeting_prep.py or skill) will handle
        # passing this to Claude for inline completion

        structured_prompt = f"""
<meeting_prep_synthesis>
{prompt}
</meeting_prep_synthesis>

Please synthesize the meeting prep content based on the above instructions.
"""

        return SynthesisResult(
            content=structured_prompt, model_id="claude-code", success=True
        )


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
        """Generate content using basic templates."""

        # Extract key information from context
        participants = context.get("participant_context", [])
        action_items = context.get("action_items", [])
        topics = context.get("topic_context", [])
        past_notes = context.get("past_notes", "")
        series_history = context.get("series_history", [])

        # Build participant section
        participant_lines = []
        for p in participants:
            name = p.get("name", "Unknown")
            role = p.get("role", "")
            participant_lines.append(f"- **{name}**: {role}")

        # Build action items section
        action_lines = []
        for item in action_items:
            status = "[x]" if item.get("completed") else "[ ]"
            owner = item.get("owner", "Unknown")
            task = item.get("task", "")
            action_lines.append(f"- {status} **{owner}**: {task}")

        # Build topics section
        topic_lines = []
        for topic in topics:
            name = topic.get("name", "Unknown")
            status = topic.get("status", "")
            summary = topic.get("summary", "")[:200]
            topic_lines.append(f"### {name} ({status})\n{summary}")

        # Build series history section
        history_lines = []
        for entry in series_history[:3]:
            date = entry.get("date", "")
            summary = entry.get("summary", "")[:300]
            history_lines.append(f"### {date}\n{summary}")

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
*Note: This content was generated using template fallback. For richer synthesis, configure Gemini API or run in Claude Code.*
"""

        return SynthesisResult(content=content, model_id="template", success=True)


def get_synthesizer(preferred: Optional[str] = None) -> LLMSynthesizer:
    """
    Get the appropriate synthesizer for the current runtime environment.

    Args:
        preferred: Optional preferred synthesizer ("auto", "gemini", "claude", "bedrock", "template")

    Returns:
        LLMSynthesizer instance

    Resolution order:
    1. If preferred is specified (and not "auto"), use that
    2. Check PMOS_LLM_PROVIDER env var for provider hint
    3. Check for CLAUDE_CODE_SESSION env var -> ClaudeCodeSynthesizer
    4. Check for Bedrock credentials -> BedrockSynthesizer
    5. Check for Gemini API key -> GeminiSynthesizer
    6. Fall back to TemplateSynthesizer
    """
    # Get config preference
    meeting_config = config_loader.get_meeting_prep_config()
    preferred = preferred or meeting_config.get("preferred_model", "auto")

    # Check PMOS_LLM_PROVIDER env var as a hint when preferred is "auto"
    if preferred == "auto":
        llm_provider = os.environ.get("PMOS_LLM_PROVIDER", "").lower()
        if llm_provider == "bedrock":
            preferred = "bedrock"

    # Handle explicit preferences
    if preferred == "bedrock":
        synthesizer = BedrockSynthesizer()
        if synthesizer.is_available():
            return synthesizer

    if preferred == "gemini":
        synthesizer = GeminiSynthesizer()
        if synthesizer.is_available():
            return synthesizer

    if preferred == "claude":
        synthesizer = ClaudeCodeSynthesizer()
        if synthesizer.is_available():
            return synthesizer

    if preferred == "template":
        return TemplateSynthesizer()

    # Auto-detection
    if preferred == "auto":
        # Check Claude Code first
        claude_synth = ClaudeCodeSynthesizer()
        if claude_synth.is_available():
            return claude_synth

        # Check Bedrock
        bedrock_synth = BedrockSynthesizer()
        if bedrock_synth.is_available():
            return bedrock_synth

        # Check Gemini
        gemini_synth = GeminiSynthesizer()
        if gemini_synth.is_available():
            return gemini_synth

    # Fallback to template
    return TemplateSynthesizer()


# Convenience function for direct synthesis
def synthesize_meeting_prep(
    prompt: str, context: Dict, preferred: Optional[str] = None
) -> str:
    """
    Synthesize meeting prep content using the best available backend.

    Args:
        prompt: Synthesis prompt instructions
        context: Meeting context data
        preferred: Optional preferred synthesizer

    Returns:
        Generated content string
    """
    synthesizer = get_synthesizer(preferred)
    result = synthesizer.synthesize(prompt, context)

    if not result.success:
        print(f"Synthesis error ({result.model_id}): {result.error}", file=sys.stderr)
        # Fall back to template
        fallback = TemplateSynthesizer()
        result = fallback.synthesize(prompt, context)

    return result.content
