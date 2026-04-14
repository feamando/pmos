#!/usr/bin/env python3
"""
Task Completion Inference (v5.0)

Infer task/action item completion status from multiple context sources.
Cross-references action items against Slack, Jira, GitHub, Brain, and daily context.

Port from v4.x task_inference.py:
  - Hardcoded paths replaced with path_resolver
  - print() replaced with logging
  - Config access via pm_os_base.tools.core.config_loader

Usage:
    from meeting.task_inference import TaskCompletionInferrer

    inferrer = TaskCompletionInferrer.from_config()
    enriched_items = inferrer.enrich_items(action_items)
"""

import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from glob import glob
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CompletionSignal:
    """Signal indicating potential task completion."""
    source: str
    confidence: float  # 0.0 to 1.0
    evidence: str
    timestamp: Optional[str] = None


@dataclass
class CompletionStatus:
    """Aggregated completion status for a task."""
    status: str  # 'completed', 'possibly_complete', 'outstanding'
    confidence: float
    evidence: List[str]
    signals: List[CompletionSignal] = field(default_factory=list)

    @property
    def marker(self) -> str:
        if self.status == "completed":
            return "[x]"
        elif self.status == "possibly_complete":
            return "[~]"
        return "[ ]"


@dataclass
class ActionItem:
    """Represents an action item to check."""
    owner: str
    task: str
    completed: bool = False
    completion_status: Optional[CompletionStatus] = None


# ---------------------------------------------------------------------------
# Keyword extraction helper
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset({
    "the", "a", "an", "to", "for", "on", "with", "and", "or",
    "of", "in", "is", "it",
})


def _extract_keywords(text: str, max_keywords: int = 5) -> List[str]:
    """Extract significant keywords from text."""
    words = re.findall(r"\b\w{3,}\b", text.lower())
    return [w for w in words if w not in _STOP_WORDS][:max_keywords]


# ---------------------------------------------------------------------------
# Context sources
# ---------------------------------------------------------------------------


class ContextSource(ABC):
    """Abstract base class for context sources."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        pass

    @abstractmethod
    def check_task(self, task: ActionItem) -> Optional[CompletionSignal]:
        pass


class SlackContextSource(ContextSource):
    """Check Slack mentions for task completion signals."""

    COMPLETION_KEYWORDS = [
        "done", "completed", "shipped", "merged", "finished",
        "resolved", "closed", "fixed", "delivered", "sent",
    ]
    PROGRESS_KEYWORDS = ["working on", "in progress", "started", "almost"]

    def __init__(self, mentions_state_path: Optional[str] = None):
        self.mentions_state_path = mentions_state_path

    @property
    def source_name(self) -> str:
        return "slack"

    def check_task(self, task: ActionItem) -> Optional[CompletionSignal]:
        if not self.mentions_state_path or not os.path.exists(self.mentions_state_path):
            return None
        try:
            import json
            with open(self.mentions_state_path, "r") as f:
                state = json.load(f)
            mentions = state.get("mentions", [])
            task_keywords = _extract_keywords(task.task)

            for mention in mentions[-50:]:
                text = mention.get("text", "").lower()
                if task.owner.lower().split()[0] not in text:
                    continue
                if not any(kw in text for kw in task_keywords):
                    continue
                if any(kw in text for kw in self.COMPLETION_KEYWORDS):
                    return CompletionSignal(
                        source="slack", confidence=0.7,
                        evidence=f'Slack mention: "{text[:100]}..."',
                        timestamp=mention.get("ts", ""),
                    )
                if any(kw in text for kw in self.PROGRESS_KEYWORDS):
                    return CompletionSignal(
                        source="slack", confidence=0.3,
                        evidence=f'In progress: "{text[:100]}..."',
                        timestamp=mention.get("ts", ""),
                    )
        except Exception as exc:
            logger.warning("Slack context source error: %s", exc)
        return None


class JiraContextSource(ContextSource):
    """Check Jira for linked ticket status."""

    DONE_STATUSES = frozenset({"done", "closed", "resolved", "complete"})
    IN_PROGRESS_STATUSES = frozenset({"in progress", "in review", "testing"})

    def __init__(self, jira_client=None):
        self.jira_client = jira_client

    @property
    def source_name(self) -> str:
        return "jira"

    def check_task(self, task: ActionItem) -> Optional[CompletionSignal]:
        ticket_match = re.search(r"\b([A-Z]+-\d+)\b", task.task)
        if not ticket_match:
            return None
        ticket_id = ticket_match.group(1)

        if not self.jira_client:
            return None

        try:
            issue = self.jira_client.issue(ticket_id)
            status = issue["fields"]["status"]["name"].lower()
            if status in self.DONE_STATUSES:
                return CompletionSignal(
                    source="jira", confidence=0.9,
                    evidence=f"Jira {ticket_id} status: {status}",
                    timestamp=issue["fields"].get("updated", ""),
                )
            if status in self.IN_PROGRESS_STATUSES:
                return CompletionSignal(
                    source="jira", confidence=0.4,
                    evidence=f"Jira {ticket_id} status: {status} (in progress)",
                    timestamp=issue["fields"].get("updated", ""),
                )
        except Exception as exc:
            logger.warning("Jira lookup error for %s: %s", ticket_id, exc)
        return None


class GitHubContextSource(ContextSource):
    """Check GitHub for related PRs/commits."""

    def __init__(self, github_client=None):
        self.github_client = github_client

    @property
    def source_name(self) -> str:
        return "github"

    def check_task(self, task: ActionItem) -> Optional[CompletionSignal]:
        pr_match = re.search(r"#(\d+)\b|PR[#\s]*(\d+)", task.task)
        if not pr_match:
            return None
        pr_number = pr_match.group(1) or pr_match.group(2)
        return CompletionSignal(
            source="github", confidence=0.5,
            evidence=f"Found PR reference #{pr_number} - check status manually",
        )


class BrainContextSource(ContextSource):
    """Check Brain entity updates for completion evidence."""

    def __init__(self, brain_dir: Optional[str] = None):
        self.brain_dir = brain_dir

    @property
    def source_name(self) -> str:
        return "brain"

    def check_task(self, task: ActionItem) -> Optional[CompletionSignal]:
        if not self.brain_dir or not os.path.exists(self.brain_dir):
            return None
        keywords = _extract_keywords(task.task)
        projects_dir = os.path.join(self.brain_dir, "Projects")
        if not os.path.exists(projects_dir):
            return None

        for filename in os.listdir(projects_dir):
            if not filename.endswith(".md"):
                continue
            project_name = filename.replace(".md", "").lower()
            if any(kw in project_name for kw in keywords):
                filepath = os.path.join(projects_dir, filename)
                signal = self._check_file_for_completion(filepath, task, keywords)
                if signal:
                    return signal
        return None

    def _check_file_for_completion(
        self, filepath: str, task: ActionItem, task_keywords: List[str]
    ) -> Optional[CompletionSignal]:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            for line in content.split("\n"):
                if "[x]" in line.lower():
                    if any(kw in line.lower() for kw in task_keywords):
                        return CompletionSignal(
                            source="brain", confidence=0.6,
                            evidence=f"Brain entity shows completed: {line[:100]}",
                        )
        except Exception:
            pass
        return None


class DailyContextSource(ContextSource):
    """Check daily context for completion markers."""

    def __init__(self, context_dir: Optional[str] = None):
        self.context_dir = context_dir

    @property
    def source_name(self) -> str:
        return "daily_context"

    def check_task(self, task: ActionItem) -> Optional[CompletionSignal]:
        if not self.context_dir or not os.path.exists(self.context_dir):
            return None
        pattern = os.path.join(self.context_dir, "*-context.md")
        files = sorted(glob(pattern))[-7:]
        task_keywords = _extract_keywords(task.task)

        for filepath in files:
            signal = self._check_context_file(filepath, task, task_keywords)
            if signal:
                return signal
        return None

    def _check_context_file(
        self, filepath: str, task: ActionItem, keywords: List[str]
    ) -> Optional[CompletionSignal]:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            for line in content.split("\n"):
                if "[x]" not in line:
                    continue
                if task.owner.lower().split()[0] not in line.lower():
                    continue
                if any(kw in line.lower() for kw in keywords):
                    return CompletionSignal(
                        source="daily_context", confidence=0.8,
                        evidence=f"Daily context shows completed: {line.strip()[:100]}",
                        timestamp=os.path.basename(filepath).split("-context")[0],
                    )
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# Inferrer
# ---------------------------------------------------------------------------


class TaskCompletionInferrer:
    """Infer task completion from multiple context sources."""

    def __init__(
        self,
        sources: List[ContextSource],
        confidence_threshold: float = 0.6,
    ):
        self.sources = [s for s in sources if s is not None]
        self.confidence_threshold = confidence_threshold

    @classmethod
    def from_config(cls, config=None, paths=None) -> "TaskCompletionInferrer":
        """
        Create inferrer from config settings.

        Args:
            config: PM-OS ConfigLoader (auto-loaded if None).
            paths: PM-OS ResolvedPaths (auto-loaded if None).
        """
        if config is None and get_config is not None:
            try:
                config = get_config()
            except Exception:
                pass
        if paths is None and get_paths is not None:
            try:
                paths = get_paths()
            except Exception:
                pass

        # Read sub-config
        enabled = True
        sources_config: Dict = {}
        confidence_threshold = 0.6

        if config is not None:
            enabled = config.get("meeting_prep.task_inference.enabled", True)
            sources_config = config.get("meeting_prep.task_inference.sources", {})
            confidence_threshold = config.get(
                "meeting_prep.task_inference.confidence_threshold", 0.6
            )

        if not enabled:
            return cls([], confidence_threshold)

        # Resolve user directory
        user_dir = paths.user if paths else None

        sources: List[ContextSource] = []

        if sources_config.get("slack", True) and user_dir:
            mentions_path = str(user_dir / "data" / "slack" / "mentions_state.json")
            sources.append(SlackContextSource(mentions_path))

        if sources_config.get("jira", True):
            sources.append(JiraContextSource(None))

        if sources_config.get("github", True):
            sources.append(GitHubContextSource(None))

        if sources_config.get("brain", True) and user_dir:
            sources.append(BrainContextSource(str(user_dir / "brain")))

        if sources_config.get("daily_context", True) and user_dir:
            sources.append(DailyContextSource(str(user_dir / "context")))

        return cls(sources, confidence_threshold)

    def check_completion(self, task: ActionItem) -> CompletionStatus:
        """Check if task appears completed based on context signals."""
        signals: List[CompletionSignal] = []
        for source in self.sources:
            try:
                signal = source.check_task(task)
                if signal:
                    signals.append(signal)
            except Exception as exc:
                logger.warning("Error checking %s: %s", source.source_name, exc)
        return self._aggregate_signals(signals)

    def _aggregate_signals(
        self, signals: List[CompletionSignal]
    ) -> CompletionStatus:
        if not signals:
            return CompletionStatus(
                status="outstanding", confidence=0.0, evidence=[], signals=[]
            )
        max_confidence = max(s.confidence for s in signals)
        signal_boost = min(0.1 * (len(signals) - 1), 0.2)
        aggregate_confidence = min(max_confidence + signal_boost, 1.0)

        if aggregate_confidence >= self.confidence_threshold:
            status = "completed"
        elif aggregate_confidence >= 0.3:
            status = "possibly_complete"
        else:
            status = "outstanding"

        return CompletionStatus(
            status=status,
            confidence=aggregate_confidence,
            evidence=[s.evidence for s in signals],
            signals=signals,
        )

    def enrich_items(self, items: List[Dict]) -> List[Dict]:
        """
        Enrich action items with completion status.

        Args:
            items: List of action item dicts with 'owner', 'task', 'completed' keys.

        Returns:
            Enriched items with 'completion_status' added.
        """
        enriched = []
        for item in items:
            task = ActionItem(
                owner=item.get("owner", "Unknown"),
                task=item.get("task", ""),
                completed=item.get("completed", False),
            )
            if task.completed:
                item["completion_status"] = CompletionStatus(
                    status="completed",
                    confidence=1.0,
                    evidence=["Already marked complete in source"],
                )
            else:
                item["completion_status"] = self.check_completion(task)
            enriched.append(item)
        return enriched


# ---------------------------------------------------------------------------
# CLI for testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test task completion inference")
    parser.add_argument("--owner", type=str, required=True, help="Task owner name")
    parser.add_argument("--task", type=str, required=True, help="Task description")
    args = parser.parse_args()

    inferrer = TaskCompletionInferrer.from_config()
    task = ActionItem(owner=args.owner, task=args.task)
    status = inferrer.check_completion(task)

    print(f"Status: {status.status} ({status.marker})")
    print(f"Confidence: {status.confidence:.2f}")
    print("Evidence:")
    for e in status.evidence:
        print(f"  - {e}")
