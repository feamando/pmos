"""
PM-OS CCE OrthogonalIntegration (v5.0)

Integrates orthogonal challenge runner with context document workflow.
Uses multiple AI models (Claude + Gemini) to critique context documents
for gaps, biases, and missing perspectives. Supports whole-document
and section-level (RLM decomposition) challenge modes.

Usage:
    from pm_os_cce.tools.integration.orthogonal_integration import OrthogonalIntegration
"""

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- v5 imports: base plugin ---
try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from core.config_loader import get_config

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

# --- v5 imports: CCE siblings ---
try:
    from pm_os_cce.tools.feature.feature_state import FeatureState, TrackStatus
except ImportError:
    from feature.feature_state import FeatureState, TrackStatus

# --- v5 imports: Brain (optional) ---
try:
    from pm_os_brain.tools.brain_core.brain_updater import BrainUpdater
    HAS_BRAIN = True
except ImportError:
    HAS_BRAIN = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Readiness levels
# ---------------------------------------------------------------------------

class ReadinessLevel(Enum):
    """Context document readiness levels based on challenge score."""
    READY_FOR_V3 = "ready_for_v3"          # Score >= 85
    READY_FOR_V2 = "ready_for_v2"          # Score >= 75
    NEEDS_MINOR_REVISIONS = "needs_minor_revisions"  # Score >= 60
    NEEDS_MAJOR_REVISIONS = "needs_major_revisions"  # Score < 60


SCORE_THRESHOLDS = {
    ReadinessLevel.READY_FOR_V3: 85,
    ReadinessLevel.READY_FOR_V2: 75,
    ReadinessLevel.NEEDS_MINOR_REVISIONS: 60,
}


def determine_readiness(score: int) -> ReadinessLevel:
    """Determine readiness level from score (0-100)."""
    if score >= SCORE_THRESHOLDS[ReadinessLevel.READY_FOR_V3]:
        return ReadinessLevel.READY_FOR_V3
    elif score >= SCORE_THRESHOLDS[ReadinessLevel.READY_FOR_V2]:
        return ReadinessLevel.READY_FOR_V2
    elif score >= SCORE_THRESHOLDS[ReadinessLevel.NEEDS_MINOR_REVISIONS]:
        return ReadinessLevel.NEEDS_MINOR_REVISIONS
    else:
        return ReadinessLevel.NEEDS_MAJOR_REVISIONS


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ChallengeIssue:
    """A single issue found during orthogonal challenge."""
    text: str
    severity: str = "minor"  # critical, major, minor
    category: str = ""
    suggestion: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "severity": self.severity,
            "category": self.category,
            "suggestion": self.suggestion,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChallengeIssue":
        return cls(
            text=data.get("text", ""),
            severity=data.get("severity", "minor"),
            category=data.get("category", ""),
            suggestion=data.get("suggestion", ""),
        )


@dataclass
class ChallengeResult:
    """Result of running orthogonal challenge on a context document."""
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
        return len(self.issues)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def major_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "major")

    @property
    def minor_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "minor")

    def to_dict(self) -> Dict[str, Any]:
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
        issues = [ChallengeIssue.from_dict(i) for i in data.get("issues", [])]
        readiness_str = data.get("readiness_level", "needs_major_revisions")
        try:
            readiness = ReadinessLevel(readiness_str)
        except ValueError:
            readiness = ReadinessLevel.NEEDS_MAJOR_REVISIONS
        challenge_file = Path(data["challenge_file"]) if data.get("challenge_file") else None
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


# ---------------------------------------------------------------------------
# Challenge prompt
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# OrthogonalIntegration
# ---------------------------------------------------------------------------

class OrthogonalIntegration:
    """
    Integrates orthogonal challenge with context document workflow.

    Provides methods to:
    - Run orthogonal challenges on context documents
    - Parse challenge results and extract scores/issues
    - Save challenge output to feature folder
    - Update feature state with challenge results
    """

    def __init__(self):
        """Initialize the orthogonal integration."""
        self._invoke_gemini = None
        self._invoke_challenger = None

        # Try to load model bridge from config-driven path
        try:
            config = get_config()
            model_bridge_path = config.get("integrations.model_bridge.module", "")
            if model_bridge_path:
                # Dynamic import from configured path
                import importlib
                mod = importlib.import_module(model_bridge_path)
                self._invoke_gemini = getattr(mod, "invoke_gemini", None)
                self._invoke_challenger = getattr(mod, "invoke_challenger", None)
        except Exception:
            pass

        # Fallback: try direct import
        if self._invoke_gemini is None:
            try:
                from util.model_bridge import invoke_challenger, invoke_gemini
                self._invoke_gemini = invoke_gemini
                self._invoke_challenger = invoke_challenger
            except ImportError:
                pass

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
            context_doc_path: Path to the context document
            feature_path: Path to the feature folder
            version: Document version (1, 2, etc.)
            use_challenger: Use the challenger model (default: True)

        Returns:
            ChallengeResult with score, issues, and suggestions
        """
        if not context_doc_path.exists():
            return ChallengeResult(
                success=False, error=f"Context document not found: {context_doc_path}"
            )

        try:
            document_content = context_doc_path.read_text(encoding="utf-8")
        except (IOError, OSError) as e:
            return ChallengeResult(
                success=False, error=f"Failed to read context document: {e}"
            )

        prompt = CONTEXT_DOC_CHALLENGE_PROMPT.format(document_content=document_content)
        response = self._run_challenger(prompt, use_challenger)

        if response.get("error"):
            return ChallengeResult(
                success=False, error=f"Challenge invocation failed: {response['error']}"
            )

        raw_response = response.get("response", "")
        result = self._parse_challenge_response(raw_response)
        result.challenger_model = response.get("model", "gemini")
        result.raw_response = raw_response

        challenge_file = self._save_challenge_output(
            feature_path=feature_path,
            version=version,
            result=result,
            raw_response=raw_response,
        )
        result.challenge_file = challenge_file

        self._update_feature_state(
            feature_path=feature_path, version=version, result=result
        )

        return result

    def run_challenge_decomposed(
        self,
        context_doc_path: Path,
        feature_path: Path,
        version: int = 1,
        use_challenger: bool = True,
    ) -> ChallengeResult:
        """
        Run section-level orthogonal challenge using RLM decomposition.

        Instead of challenging the entire document at once, decomposes it
        into sections, challenges each independently, and recomposes scores
        as a weighted average by word count.
        """
        if not context_doc_path.exists():
            return ChallengeResult(
                success=False,
                error=f"Context document not found: {context_doc_path}",
            )

        try:
            document_content = context_doc_path.read_text(encoding="utf-8")
        except (IOError, OSError) as e:
            return ChallengeResult(
                success=False,
                error=f"Failed to read context document: {e}",
            )

        # Try RLM decomposition
        try:
            try:
                from pm_os_cce.tools.reasoning.rlm_engine import ByDocumentSection, RLMEngine
            except ImportError:
                from reasoning.rlm_engine import ByDocumentSection, RLMEngine
            strategy = ByDocumentSection()
            subtasks = strategy.decompose(
                "Challenge context document", document=document_content
            )
        except ImportError:
            return self.run_challenge(
                context_doc_path, feature_path, version, use_challenger
            )

        if len(subtasks) <= 1:
            return self.run_challenge(
                context_doc_path, feature_path, version, use_challenger
            )

        # Challenge each section
        section_results: List[Dict[str, Any]] = []
        total_words = 0

        for subtask in subtasks:
            section_content = subtask.metadata.get("section_content", "")
            section_title = subtask.metadata.get("section_title", "")
            word_count = subtask.metadata.get("word_count", 1)
            total_words += word_count

            prompt = CONTEXT_DOC_CHALLENGE_PROMPT.format(
                document_content=f"## {section_title}\n\n{section_content}"
            )
            response = self._run_challenger(prompt, use_challenger)

            if not response.get("error"):
                raw = response.get("response", "")
                parsed = self._parse_challenge_response(raw)
                section_results.append({
                    "title": section_title,
                    "result": parsed,
                    "word_count": word_count,
                })

        if not section_results:
            return self.run_challenge(
                context_doc_path, feature_path, version, use_challenger
            )

        # Compose: weighted average by word count
        weighted_score = 0.0
        all_issues: List[ChallengeIssue] = []
        all_suggestions: List[str] = []

        for sr in section_results:
            weight = sr["word_count"] / max(total_words, 1)
            weighted_score += sr["result"].score * weight
            for issue in sr["result"].issues:
                issue.text = f"[{sr['title']}] {issue.text}"
                all_issues.append(issue)
            all_suggestions.extend(sr["result"].suggestions)

        final_score = int(weighted_score)
        readiness = determine_readiness(final_score)

        result = ChallengeResult(
            success=True,
            score=final_score,
            issues=all_issues,
            suggestions=list(set(all_suggestions)),
            readiness_level=readiness,
            challenger_model="rlm_decomposed",
        )

        challenge_file = self._save_challenge_output(
            feature_path=feature_path,
            version=version,
            result=result,
            raw_response=f"Section-level challenge ({len(section_results)} sections)",
        )
        result.challenge_file = challenge_file
        self._update_feature_state(
            feature_path=feature_path, version=version, result=result
        )

        return result

    # ------------------------------------------------------------------
    # Internal: challenger invocation
    # ------------------------------------------------------------------

    def _run_challenger(
        self, prompt: str, use_challenger: bool = True
    ) -> Dict[str, Any]:
        """Run the challenger model."""
        if use_challenger and self._invoke_challenger:
            return self._invoke_challenger(prompt, max_tokens=10000, temperature=0.4)
        elif self._invoke_gemini:
            return self._invoke_gemini(prompt, max_tokens=10000, temperature=0.4)
        else:
            return {"error": "No challenger model available (model_bridge not configured)"}

    # ------------------------------------------------------------------
    # Internal: response parsing
    # ------------------------------------------------------------------

    def _parse_challenge_response(self, response: str) -> ChallengeResult:
        """Parse the challenger's response to extract score and issues."""
        issues: List[ChallengeIssue] = []
        suggestions: List[str] = []
        score = 0

        lines = response.split("\n")
        current_section = ""
        current_severity = "minor"

        for line in lines:
            line_stripped = line.strip()

            # Extract overall score
            if "Overall Score:" in line or "## Overall Score" in line:
                try:
                    score_str = "".join(c for c in line if c.isdigit())
                    if score_str:
                        score = int(score_str[:3])
                        score = min(100, max(0, score))
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

            # Parse issues
            if (
                current_section == "issues"
                and line_stripped
                and line_stripped[0].isdigit()
            ):
                issue_text = line_stripped
                for i, char in enumerate(line_stripped):
                    if char in ".):":
                        issue_text = line_stripped[i + 1:].strip()
                        break
                if issue_text:
                    issues.append(
                        ChallengeIssue(text=issue_text, severity=current_severity)
                    )

            # Parse suggestions
            if current_section == "suggestions" and line_stripped.startswith(
                ("-", "*", "+")
            ):
                suggestion_text = line_stripped[1:].strip()
                if suggestion_text:
                    suggestions.append(suggestion_text)

            # Parse priority improvements as suggestions
            if (
                current_section == "priorities"
                and line_stripped
                and line_stripped[0].isdigit()
            ):
                priority_text = line_stripped
                for i, char in enumerate(line_stripped):
                    if char in ".):":
                        priority_text = line_stripped[i + 1:].strip()
                        break
                if priority_text:
                    suggestions.append(f"Priority: {priority_text}")

        # Estimate score from issues if not found
        if score == 0:
            score = 100
            score -= len([i for i in issues if i.severity == "critical"]) * 15
            score -= len([i for i in issues if i.severity == "major"]) * 8
            score -= len([i for i in issues if i.severity == "minor"]) * 3
            score = max(0, min(100, score))

        readiness = determine_readiness(score)

        return ChallengeResult(
            success=True,
            score=score,
            issues=issues,
            suggestions=suggestions,
            readiness_level=readiness,
            timestamp=datetime.now(),
        )

    # ------------------------------------------------------------------
    # Internal: output persistence
    # ------------------------------------------------------------------

    def _save_challenge_output(
        self,
        feature_path: Path,
        version: int,
        result: ChallengeResult,
        raw_response: str,
    ) -> Path:
        """Save challenge output to feature folder."""
        context_docs_dir = feature_path / "context-docs"
        context_docs_dir.mkdir(parents=True, exist_ok=True)

        challenge_filename = f"v{version}-challenge.md"
        challenge_path = context_docs_dir / challenge_filename

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

        content += "---\n\n## Full Challenge Review\n\n"
        content += raw_response

        content += "\n\n---\n\n## Structured Issues Summary\n\n"

        if result.issues:
            for severity in ["critical", "major", "minor"]:
                severity_issues = [i for i in result.issues if i.severity == severity]
                if severity_issues:
                    content += f"### {severity.title()} ({len(severity_issues)})\n\n"
                    for idx, issue in enumerate(severity_issues, 1):
                        content += f"{idx}. {issue.text}\n"
                    content += "\n"
        else:
            content += "*No structured issues extracted.*\n\n"

        if result.suggestions:
            content += "## Key Suggestions\n\n"
            for suggestion in result.suggestions:
                content += f"- {suggestion}\n"
            content += "\n"

        try:
            challenge_path.write_text(content, encoding="utf-8")
        except (IOError, OSError) as e:
            logger.error("Failed to save challenge output: %s", e)

        return challenge_path

    def _update_feature_state(
        self, feature_path: Path, version: int, result: ChallengeResult
    ) -> None:
        """Update feature-state.yaml with challenge results."""
        try:
            state = FeatureState.load(feature_path)
            if not state:
                logger.warning("Feature state not found at %s", feature_path)
                return

            context_track = state.tracks.get("context")
            if context_track:
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

                if result.readiness_level == ReadinessLevel.READY_FOR_V3:
                    context_track.current_step = "v3_ready"
                elif result.readiness_level == ReadinessLevel.READY_FOR_V2:
                    context_track.current_step = "v2_ready"
                else:
                    context_track.current_step = f"v{version}_challenged"

            # Record phase history
            if state.phase_history:
                state.phase_history[-1].metadata[f"v{version}_challenge"] = {
                    "score": result.score,
                    "issues_count": result.issues_count,
                    "timestamp": result.timestamp.isoformat(),
                }

            state.save(feature_path)

        except Exception as e:
            logger.error("Failed to update feature state: %s", e)

    # ------------------------------------------------------------------
    # Public query helpers
    # ------------------------------------------------------------------

    def get_challenge_summary(
        self, feature_path: Path, version: int = 1
    ) -> Optional[Dict[str, Any]]:
        """Get summary of a previous challenge from feature state."""
        try:
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
        """Check if a challenge has been run for a specific version."""
        challenge_file = feature_path / "context-docs" / f"v{version}-challenge.md"
        return challenge_file.exists()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "OrthogonalIntegration",
    "ChallengeResult",
    "ChallengeIssue",
    "ReadinessLevel",
    "determine_readiness",
    "SCORE_THRESHOLDS",
]
