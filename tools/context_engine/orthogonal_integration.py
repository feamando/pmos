"""
Orthogonal Challenge Integration for Context Documents

Integrates the orthogonal challenge runner (common/tools/quint/orthogonal_challenge.py)
with the context creation engine for automated context document validation.

The orthogonal challenge process uses multiple AI models (Claude + Gemini) to:
1. Critique the context document for gaps, biases, and missing perspectives
2. Propose improvements and alternative approaches
3. Score the document quality

Thresholds (from PRD):
    Score >= 85: Ready for v3 (final)
    Score >= 75: Ready for v2
    Score >= 60: Needs minor revisions
    Score < 60: Needs major revisions

Output Location:
    {feature-folder}/context-docs/v1-challenge.md
    {feature-folder}/context-docs/v2-challenge.md (if applicable)

Usage:
    from tools.context_engine import OrthogonalIntegration

    integration = OrthogonalIntegration()

    # Run challenge on a context document
    result = integration.run_challenge(
        context_doc_path=Path("/path/to/feature/context-docs/v1-draft.md"),
        feature_path=Path("/path/to/feature")
    )

    print(f"Score: {result.score}")
    print(f"Issues found: {result.issues_count}")
    print(f"Ready for: {result.readiness_level}")

Author: PM-OS Team
Version: 1.0.0
"""

import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logger = logging.getLogger(__name__)


class ReadinessLevel(Enum):
    """Context document readiness levels based on challenge score."""

    READY_FOR_V3 = "ready_for_v3"  # Score >= 85
    READY_FOR_V2 = "ready_for_v2"  # Score >= 75
    NEEDS_MINOR_REVISIONS = "needs_minor_revisions"  # Score >= 60
    NEEDS_MAJOR_REVISIONS = "needs_major_revisions"  # Score < 60


# Score thresholds from PRD
SCORE_THRESHOLDS = {
    ReadinessLevel.READY_FOR_V3: 85,
    ReadinessLevel.READY_FOR_V2: 75,
    ReadinessLevel.NEEDS_MINOR_REVISIONS: 60,
}


@dataclass
class ChallengeIssue:
    """
    A single issue found during orthogonal challenge.

    Attributes:
        text: Description of the issue
        severity: critical, major, or minor
        category: Category of issue (logical_gap, evidence_weakness, bias, etc.)
        suggestion: Suggested fix or improvement
    """

    text: str
    severity: str = "minor"  # critical, major, minor
    category: str = ""
    suggestion: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "severity": self.severity,
            "category": self.category,
            "suggestion": self.suggestion,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChallengeIssue":
        """Create from dictionary."""
        return cls(
            text=data.get("text", ""),
            severity=data.get("severity", "minor"),
            category=data.get("category", ""),
            suggestion=data.get("suggestion", ""),
        )


@dataclass
class ChallengeResult:
    """
    Result of running orthogonal challenge on a context document.

    Attributes:
        success: Whether the challenge ran successfully
        score: Overall quality score (0-100)
        issues: List of issues found
        suggestions: General suggestions for improvement
        readiness_level: What the document is ready for
        challenge_file: Path to saved challenge output
        timestamp: When the challenge was run
        challenger_model: Model used for challenge (gemini)
        raw_response: Raw challenger response
    """

    success: bool
    score: int = 0
    issues: List[ChallengeIssue] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    readiness_level: ReadinessLevel = ReadinessLevel.NEEDS_MAJOR_REVISIONS
    challenge_file: Optional[Path] = None
    timestamp: datetime = field(default_factory=datetime.now)
    challenger_model: str = "gemini"
    raw_response: str = ""
    error: str = ""

    @property
    def issues_count(self) -> int:
        """Total number of issues found."""
        return len(self.issues)

    @property
    def critical_count(self) -> int:
        """Number of critical issues."""
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def major_count(self) -> int:
        """Number of major issues."""
        return sum(1 for i in self.issues if i.severity == "major")

    @property
    def minor_count(self) -> int:
        """Number of minor issues."""
        return sum(1 for i in self.issues if i.severity == "minor")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "score": self.score,
            "issues_count": self.issues_count,
            "critical_count": self.critical_count,
            "major_count": self.major_count,
            "minor_count": self.minor_count,
            "issues": [i.to_dict() for i in self.issues],
            "suggestions": self.suggestions,
            "readiness_level": self.readiness_level.value,
            "challenge_file": str(self.challenge_file) if self.challenge_file else None,
            "timestamp": self.timestamp.isoformat(),
            "challenger_model": self.challenger_model,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChallengeResult":
        """Create from dictionary."""
        issues = [ChallengeIssue.from_dict(i) for i in data.get("issues", [])]

        readiness_str = data.get("readiness_level", "needs_major_revisions")
        try:
            readiness = ReadinessLevel(readiness_str)
        except ValueError:
            readiness = ReadinessLevel.NEEDS_MAJOR_REVISIONS

        challenge_file = None
        if data.get("challenge_file"):
            challenge_file = Path(data["challenge_file"])

        return cls(
            success=data.get("success", False),
            score=data.get("score", 0),
            issues=issues,
            suggestions=data.get("suggestions", []),
            readiness_level=readiness,
            challenge_file=challenge_file,
            timestamp=(
                datetime.fromisoformat(data["timestamp"])
                if data.get("timestamp")
                else datetime.now()
            ),
            challenger_model=data.get("challenger_model", "gemini"),
            raw_response=data.get("raw_response", ""),
            error=data.get("error", ""),
        )


def determine_readiness(score: int) -> ReadinessLevel:
    """
    Determine readiness level from score.

    Args:
        score: Challenge score (0-100)

    Returns:
        ReadinessLevel enum value
    """
    if score >= SCORE_THRESHOLDS[ReadinessLevel.READY_FOR_V3]:
        return ReadinessLevel.READY_FOR_V3
    elif score >= SCORE_THRESHOLDS[ReadinessLevel.READY_FOR_V2]:
        return ReadinessLevel.READY_FOR_V2
    elif score >= SCORE_THRESHOLDS[ReadinessLevel.NEEDS_MINOR_REVISIONS]:
        return ReadinessLevel.NEEDS_MINOR_REVISIONS
    else:
        return ReadinessLevel.NEEDS_MAJOR_REVISIONS


# Challenge prompt for context documents
CONTEXT_DOC_CHALLENGE_PROMPT = """You are a rigorous product reviewer performing an orthogonal challenge on a context document.

Your task is to critically evaluate this context document for a product feature, identifying:

1. **Logical Gaps**: Missing reasoning steps, unsupported conclusions, vague requirements
2. **Evidence Weakness**: Question source quality, recency, relevance of supporting data
3. **Bias Detection**: Confirmation bias, missing user perspectives, cherry-picked data
4. **Missing Stakeholders**: Who wasn't consulted or considered?
5. **Risk Blindspots**: Unaddressed failure modes, edge cases, technical risks
6. **Scope Issues**: Is scope well-defined? Are boundaries clear?
7. **Success Metrics**: Are metrics measurable, relevant, and achievable?
8. **User Stories**: Are they complete, specific, and testable?

For each issue found:
- Be specific about what's problematic
- Explain why it matters
- Suggest improvements
- Rate severity: Critical (blocks progress) / Major (significant gap) / Minor (improvement opportunity)

At the end, provide:
1. An overall quality score from 0-100
2. A summary of the top 3 priority issues to address
3. Specific suggestions for the next revision

Output format:
```
## Executive Summary
[2-3 sentence summary of document quality]

## Overall Score: [0-100]

## Issues Found

### Critical Issues
[numbered list with severity, description, and suggestion]

### Major Issues
[numbered list with severity, description, and suggestion]

### Minor Issues
[numbered list with severity, description, and suggestion]

## Top Priority Improvements
1. [Most important fix]
2. [Second priority]
3. [Third priority]

## Suggestions for Next Revision
[Bullet list of specific improvements]
```

Now review this context document:

---

{document_content}

---

Provide your rigorous critique."""


class OrthogonalIntegration:
    """
    Integrates orthogonal challenge with context document workflow.

    This class provides methods to:
    - Run orthogonal challenges on context documents
    - Parse challenge results and extract scores/issues
    - Save challenge output to feature folder
    - Update feature state with challenge results
    """

    def __init__(self):
        """Initialize the orthogonal integration."""
        # Import model bridge for challenger invocation
        try:
            from util.model_bridge import invoke_challenger, invoke_gemini

            self._invoke_gemini = invoke_gemini
            self._invoke_challenger = invoke_challenger
        except ImportError:
            # Fallback - will use local implementation
            self._invoke_gemini = None
            self._invoke_challenger = None

    def run_challenge(
        self,
        context_doc_path: Path,
        feature_path: Path,
        version: int = 1,
        use_challenger: bool = True,
    ) -> ChallengeResult:
        """
        Run orthogonal challenge on a context document.

        Args:
            context_doc_path: Path to the context document (v1-draft.md, v2-revised.md)
            feature_path: Path to the feature folder
            version: Document version (1, 2, etc.)
            use_challenger: Use the challenger model (default: True)

        Returns:
            ChallengeResult with score, issues, and suggestions
        """
        # Verify document exists
        if not context_doc_path.exists():
            return ChallengeResult(
                success=False, error=f"Context document not found: {context_doc_path}"
            )

        # Read document content
        try:
            document_content = context_doc_path.read_text(encoding="utf-8")
        except (IOError, OSError) as e:
            return ChallengeResult(
                success=False, error=f"Failed to read context document: {e}"
            )

        # Build challenge prompt
        prompt = CONTEXT_DOC_CHALLENGE_PROMPT.format(document_content=document_content)

        # Invoke challenger model
        response = self._run_challenger(prompt, use_challenger)

        if response.get("error"):
            return ChallengeResult(
                success=False, error=f"Challenge invocation failed: {response['error']}"
            )

        # Parse the response
        raw_response = response.get("response", "")
        result = self._parse_challenge_response(raw_response)
        result.challenger_model = response.get("model", "gemini")
        result.raw_response = raw_response

        # Save challenge output
        challenge_file = self._save_challenge_output(
            feature_path=feature_path,
            version=version,
            result=result,
            raw_response=raw_response,
        )
        result.challenge_file = challenge_file

        # Update feature state
        self._update_feature_state(
            feature_path=feature_path, version=version, result=result
        )

        return result

    def _run_challenger(
        self, prompt: str, use_challenger: bool = True
    ) -> Dict[str, Any]:
        """
        Run the challenger model.

        Args:
            prompt: Challenge prompt
            use_challenger: Use challenger model or default to Gemini

        Returns:
            Response dict with 'response', 'model', or 'error'
        """
        if use_challenger and self._invoke_challenger:
            return self._invoke_challenger(prompt, max_tokens=10000, temperature=0.4)
        elif self._invoke_gemini:
            return self._invoke_gemini(prompt, max_tokens=10000, temperature=0.4)
        else:
            # Fallback: import directly
            try:
                sys.path.insert(0, str(Path(__file__).parent.parent / "util"))
                from model_bridge import invoke_gemini

                return invoke_gemini(prompt, max_tokens=10000, temperature=0.4)
            except ImportError as e:
                return {"error": f"Could not import model_bridge: {e}"}

    def _parse_challenge_response(self, response: str) -> ChallengeResult:
        """
        Parse the challenger's response to extract score and issues.

        Args:
            response: Raw response from challenger model

        Returns:
            ChallengeResult with parsed data
        """
        issues = []
        suggestions = []
        score = 0

        lines = response.split("\n")
        current_section = ""
        current_severity = "minor"

        for line in lines:
            line_stripped = line.strip()

            # Extract overall score
            if "Overall Score:" in line or "## Overall Score" in line:
                try:
                    # Extract number from line
                    score_str = "".join(c for c in line if c.isdigit())
                    if score_str:
                        score = int(score_str[:3])  # Max 3 digits
                        score = min(100, max(0, score))  # Clamp to 0-100
                except (ValueError, IndexError):
                    pass

            # Track sections
            if "### Critical Issues" in line:
                current_section = "issues"
                current_severity = "critical"
            elif "### Major Issues" in line:
                current_section = "issues"
                current_severity = "major"
            elif "### Minor Issues" in line:
                current_section = "issues"
                current_severity = "minor"
            elif "## Top Priority Improvements" in line:
                current_section = "priorities"
            elif "## Suggestions for Next Revision" in line:
                current_section = "suggestions"
            elif line_stripped.startswith("## "):
                current_section = ""

            # Parse issues (numbered items)
            if (
                current_section == "issues"
                and line_stripped
                and line_stripped[0].isdigit()
            ):
                # Extract issue text (after the number and period/parenthesis)
                issue_text = line_stripped
                for i, char in enumerate(line_stripped):
                    if char in ".):":
                        issue_text = line_stripped[i + 1 :].strip()
                        break

                if issue_text:
                    issues.append(
                        ChallengeIssue(
                            text=issue_text,
                            severity=current_severity,
                        )
                    )

            # Parse suggestions
            if current_section == "suggestions" and line_stripped.startswith(
                ("-", "*", "+")
            ):
                suggestion_text = line_stripped[1:].strip()
                if suggestion_text:
                    suggestions.append(suggestion_text)

            # Parse priority improvements as suggestions too
            if (
                current_section == "priorities"
                and line_stripped
                and line_stripped[0].isdigit()
            ):
                priority_text = line_stripped
                for i, char in enumerate(line_stripped):
                    if char in ".):":
                        priority_text = line_stripped[i + 1 :].strip()
                        break
                if priority_text:
                    suggestions.append(f"Priority: {priority_text}")

        # If no score found, estimate from issues
        if score == 0:
            # Base score minus deductions
            score = 100
            score -= len([i for i in issues if i.severity == "critical"]) * 15
            score -= len([i for i in issues if i.severity == "major"]) * 8
            score -= len([i for i in issues if i.severity == "minor"]) * 3
            score = max(0, min(100, score))

        # Determine readiness level
        readiness = determine_readiness(score)

        return ChallengeResult(
            success=True,
            score=score,
            issues=issues,
            suggestions=suggestions,
            readiness_level=readiness,
            timestamp=datetime.now(),
        )

    def _save_challenge_output(
        self,
        feature_path: Path,
        version: int,
        result: ChallengeResult,
        raw_response: str,
    ) -> Path:
        """
        Save challenge output to feature folder.

        Args:
            feature_path: Path to feature folder
            version: Document version
            result: Challenge result
            raw_response: Raw challenger response

        Returns:
            Path to saved challenge file
        """
        context_docs_dir = feature_path / "context-docs"
        context_docs_dir.mkdir(parents=True, exist_ok=True)

        challenge_filename = f"v{version}-challenge.md"
        challenge_path = context_docs_dir / challenge_filename

        # Build challenge document
        now = datetime.now()

        content = f"""# Orthogonal Challenge: v{version}

**Date:** {now.strftime("%Y-%m-%d %H:%M")}
**Score:** {result.score}/100
**Readiness:** {result.readiness_level.value.replace('_', ' ').title()}
**Challenger Model:** {result.challenger_model}

---

## Summary

| Metric | Count |
|--------|-------|
| Total Issues | {result.issues_count} |
| Critical | {result.critical_count} |
| Major | {result.major_count} |
| Minor | {result.minor_count} |

### Readiness Assessment

"""

        # Add readiness assessment
        if result.readiness_level == ReadinessLevel.READY_FOR_V3:
            content += "**Status: Ready for Final Version (v3)**\n\n"
            content += "The document meets the quality threshold for finalization. "
            content += "Address any remaining minor issues and proceed to v3-final.\n\n"
        elif result.readiness_level == ReadinessLevel.READY_FOR_V2:
            content += "**Status: Ready for Revision (v2)**\n\n"
            content += "The document has solid foundations but needs refinement. "
            content += "Address the issues below and generate v2-revised.\n\n"
        elif result.readiness_level == ReadinessLevel.NEEDS_MINOR_REVISIONS:
            content += "**Status: Needs Minor Revisions**\n\n"
            content += "The document requires some improvements before proceeding. "
            content += "Focus on the critical and major issues identified.\n\n"
        else:
            content += "**Status: Needs Major Revisions**\n\n"
            content += "The document has significant gaps that need to be addressed. "
            content += (
                "Review the critical issues carefully and consider restructuring.\n\n"
            )

        # Add full challenge response
        content += "---\n\n## Full Challenge Review\n\n"
        content += raw_response

        # Add structured issues summary
        content += "\n\n---\n\n## Structured Issues Summary\n\n"

        if result.issues:
            for severity in ["critical", "major", "minor"]:
                severity_issues = [i for i in result.issues if i.severity == severity]
                if severity_issues:
                    content += f"### {severity.title()} ({len(severity_issues)})\n\n"
                    for i, issue in enumerate(severity_issues, 1):
                        content += f"{i}. {issue.text}\n"
                    content += "\n"
        else:
            content += "*No structured issues extracted.*\n\n"

        # Add suggestions
        if result.suggestions:
            content += "## Key Suggestions\n\n"
            for suggestion in result.suggestions:
                content += f"- {suggestion}\n"
            content += "\n"

        # Save file
        try:
            challenge_path.write_text(content, encoding="utf-8")
        except (IOError, OSError) as e:
            logger.error(f"Failed to save challenge output: {e}")

        return challenge_path

    def _update_feature_state(
        self, feature_path: Path, version: int, result: ChallengeResult
    ) -> None:
        """
        Update feature-state.yaml with challenge results.

        Args:
            feature_path: Path to feature folder
            version: Document version
            result: Challenge result
        """
        try:
            from .feature_state import FeatureState, TrackStatus

            state = FeatureState.load(feature_path)
            if not state:
                logger.warning(f"Feature state not found at {feature_path}")
                return

            # Update context track with challenge info
            context_track = state.tracks.get("context")
            if context_track:
                # Store challenge results in track metadata
                if not context_track.artifacts:
                    context_track.artifacts = {}

                context_track.artifacts[f"v{version}_challenge"] = {
                    "score": result.score,
                    "issues_count": result.issues_count,
                    "critical_count": result.critical_count,
                    "major_count": result.major_count,
                    "minor_count": result.minor_count,
                    "readiness_level": result.readiness_level.value,
                    "timestamp": result.timestamp.isoformat(),
                    "challenge_file": (
                        str(result.challenge_file) if result.challenge_file else None
                    ),
                }

                # Update current step based on readiness
                if result.readiness_level == ReadinessLevel.READY_FOR_V3:
                    context_track.current_step = "v3_ready"
                elif result.readiness_level == ReadinessLevel.READY_FOR_V2:
                    context_track.current_step = "v2_ready"
                else:
                    context_track.current_step = f"v{version}_challenged"

            # Record phase history
            state.phase_history[-1].metadata[f"v{version}_challenge"] = {
                "score": result.score,
                "issues_count": result.issues_count,
                "timestamp": result.timestamp.isoformat(),
            }

            # Save updated state
            state.save(feature_path)

        except Exception as e:
            logger.error(f"Failed to update feature state: {e}")

    def get_challenge_summary(
        self, feature_path: Path, version: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Get summary of a previous challenge from feature state.

        Args:
            feature_path: Path to feature folder
            version: Document version

        Returns:
            Dict with score, issues_count, readiness_level, or None if not found
        """
        try:
            from .feature_state import FeatureState

            state = FeatureState.load(feature_path)
            if not state:
                return None

            context_track = state.tracks.get("context")
            if not context_track or not context_track.artifacts:
                return None

            return context_track.artifacts.get(f"v{version}_challenge")

        except Exception:
            return None

    def challenge_exists(self, feature_path: Path, version: int = 1) -> bool:
        """
        Check if a challenge has been run for a specific version.

        Args:
            feature_path: Path to feature folder
            version: Document version

        Returns:
            True if challenge exists
        """
        challenge_file = feature_path / "context-docs" / f"v{version}-challenge.md"
        return challenge_file.exists()


# Export for __init__.py
__all__ = [
    "OrthogonalIntegration",
    "ChallengeResult",
    "ChallengeIssue",
    "ReadinessLevel",
    "determine_readiness",
    "SCORE_THRESHOLDS",
]
