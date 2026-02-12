"""
Task Completion Inference

Infer task/action item completion status from multiple context sources.
Cross-references action items against Slack, Jira, GitHub, Brain, and daily context.

Usage:
    from task_inference import TaskCompletionInferrer

    inferrer = TaskCompletionInferrer.from_config()
    enriched_items = inferrer.enrich_items(action_items)
"""

import os
import re
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Add parent directory to path for config_loader
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config_loader


@dataclass
class CompletionSignal:
    """Signal indicating potential task completion."""

    source: str  # Which context source found this signal
    confidence: float  # 0.0 to 1.0
    evidence: str  # Brief description of evidence found
    timestamp: Optional[str] = None  # When the signal was detected


@dataclass
class CompletionStatus:
    """Aggregated completion status for a task."""

    status: str  # 'completed', 'possibly_complete', 'outstanding'
    confidence: float  # Overall confidence (0.0 to 1.0)
    evidence: List[str]  # Evidence summaries
    signals: List[CompletionSignal] = field(default_factory=list)

    @property
    def marker(self) -> str:
        """Get checkbox marker based on status."""
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


class ContextSource(ABC):
    """Abstract base class for context sources."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return identifier for this source."""
        pass

    @abstractmethod
    def check_task(self, task: ActionItem) -> Optional[CompletionSignal]:
        """
        Check if a task appears completed based on this source.

        Args:
            task: The action item to check

        Returns:
            CompletionSignal if evidence found, None otherwise
        """
        pass


class SlackContextSource(ContextSource):
    """Check Slack mentions for task completion signals."""

    def __init__(self, mentions_state_path: Optional[str] = None):
        self.mentions_state_path = mentions_state_path

    @property
    def source_name(self) -> str:
        return "slack"

    def check_task(self, task: ActionItem) -> Optional[CompletionSignal]:
        """Search Slack mentions for completion signals."""
        if not self.mentions_state_path or not os.path.exists(self.mentions_state_path):
            return None

        try:
            import json

            with open(self.mentions_state_path, "r") as f:
                state = json.load(f)

            mentions = state.get("mentions", [])

            # Keywords indicating completion
            completion_keywords = [
                "done",
                "completed",
                "shipped",
                "merged",
                "finished",
                "resolved",
                "closed",
                "fixed",
                "delivered",
                "sent",
            ]

            # Extract task keywords
            task_keywords = self._extract_keywords(task.task)

            for mention in mentions[-50:]:  # Check last 50 mentions
                text = mention.get("text", "").lower()

                # Check if mention references the task owner
                if task.owner.lower().split()[0] not in text:
                    continue

                # Check for task keywords
                keyword_match = any(kw in text for kw in task_keywords)
                if not keyword_match:
                    continue

                # Check for completion signals
                completion_match = any(kw in text for kw in completion_keywords)
                if completion_match:
                    return CompletionSignal(
                        source="slack",
                        confidence=0.7,
                        evidence=f'Slack mention: "{text[:100]}..."',
                        timestamp=mention.get("ts", ""),
                    )

                # Check for progress signals (lower confidence)
                progress_keywords = ["working on", "in progress", "started", "almost"]
                progress_match = any(kw in text for kw in progress_keywords)
                if progress_match:
                    return CompletionSignal(
                        source="slack",
                        confidence=0.3,
                        evidence=f'In progress: "{text[:100]}..."',
                        timestamp=mention.get("ts", ""),
                    )

        except Exception as e:
            print(f"Slack context source error: {e}", file=sys.stderr)

        return None

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract significant keywords from task description."""
        # Remove common words
        stop_words = {
            "the",
            "a",
            "an",
            "to",
            "for",
            "on",
            "with",
            "and",
            "or",
            "of",
            "in",
            "is",
            "it",
        }
        words = re.findall(r"\b\w{3,}\b", text.lower())
        return [w for w in words if w not in stop_words][:5]


class JiraContextSource(ContextSource):
    """Check Jira for linked ticket status."""

    def __init__(self, jira_client=None):
        self.jira_client = jira_client

    @property
    def source_name(self) -> str:
        return "jira"

    def check_task(self, task: ActionItem) -> Optional[CompletionSignal]:
        """Check Jira ticket status."""
        # Look for ticket ID in task description
        ticket_match = re.search(r"\b([A-Z]+-\d+)\b", task.task)
        if not ticket_match:
            return None

        ticket_id = ticket_match.group(1)

        if self.jira_client:
            try:
                issue = self.jira_client.issue(ticket_id)
                status = issue["fields"]["status"]["name"].lower()

                done_statuses = ["done", "closed", "resolved", "complete"]
                if status in done_statuses:
                    return CompletionSignal(
                        source="jira",
                        confidence=0.9,
                        evidence=f"Jira {ticket_id} status: {status}",
                        timestamp=issue["fields"].get("updated", ""),
                    )

                in_progress_statuses = ["in progress", "in review", "testing"]
                if status in in_progress_statuses:
                    return CompletionSignal(
                        source="jira",
                        confidence=0.4,
                        evidence=f"Jira {ticket_id} status: {status} (in progress)",
                        timestamp=issue["fields"].get("updated", ""),
                    )

            except Exception as e:
                print(f"Jira lookup error for {ticket_id}: {e}", file=sys.stderr)

        return None


class GitHubContextSource(ContextSource):
    """Check GitHub for related PRs/commits."""

    def __init__(self, github_client=None):
        self.github_client = github_client

    @property
    def source_name(self) -> str:
        return "github"

    def check_task(self, task: ActionItem) -> Optional[CompletionSignal]:
        """Check GitHub for related PRs."""
        # Look for PR number in task
        pr_match = re.search(r"#(\d+)\b|PR[#\s]*(\d+)", task.task)
        if not pr_match:
            return None

        pr_number = pr_match.group(1) or pr_match.group(2)

        # Without GitHub client, return low confidence signal
        return CompletionSignal(
            source="github",
            confidence=0.5,
            evidence=f"Found PR reference #{pr_number} - check status manually",
            timestamp=None,
        )


class BrainContextSource(ContextSource):
    """Check Brain entity updates for completion evidence."""

    def __init__(self, brain_dir: Optional[str] = None):
        self.brain_dir = brain_dir

    @property
    def source_name(self) -> str:
        return "brain"

    def check_task(self, task: ActionItem) -> Optional[CompletionSignal]:
        """Check Brain entities for status changes."""
        if not self.brain_dir or not os.path.exists(self.brain_dir):
            return None

        # Look for project/entity references in task
        keywords = self._extract_keywords(task.task)

        # Check Projects folder for matches
        projects_dir = os.path.join(self.brain_dir, "Projects")
        if os.path.exists(projects_dir):
            for filename in os.listdir(projects_dir):
                if not filename.endswith(".md"):
                    continue

                project_name = filename.replace(".md", "").lower()
                if any(kw in project_name for kw in keywords):
                    filepath = os.path.join(projects_dir, filename)
                    signal = self._check_file_for_completion(filepath, task)
                    if signal:
                        return signal

        return None

    def _check_file_for_completion(
        self, filepath: str, task: ActionItem
    ) -> Optional[CompletionSignal]:
        """Check a Brain file for completion signals."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Look for completion markers in recent updates
            # Check for "[x]" markers with task keywords
            task_keywords = self._extract_keywords(task.task)

            for line in content.split("\n"):
                if "[x]" in line.lower():
                    if any(kw in line.lower() for kw in task_keywords):
                        return CompletionSignal(
                            source="brain",
                            confidence=0.6,
                            evidence=f"Brain entity shows completed: {line[:100]}",
                            timestamp=None,
                        )

        except Exception:
            pass

        return None

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract significant keywords from text."""
        stop_words = {
            "the",
            "a",
            "an",
            "to",
            "for",
            "on",
            "with",
            "and",
            "or",
            "of",
            "in",
            "is",
            "it",
        }
        words = re.findall(r"\b\w{3,}\b", text.lower())
        return [w for w in words if w not in stop_words][:5]


class DailyContextSource(ContextSource):
    """Check daily context for completion markers."""

    def __init__(self, context_dir: Optional[str] = None):
        self.context_dir = context_dir

    @property
    def source_name(self) -> str:
        return "daily_context"

    def check_task(self, task: ActionItem) -> Optional[CompletionSignal]:
        """Check daily context files for completion markers."""
        if not self.context_dir or not os.path.exists(self.context_dir):
            return None

        # Check recent context files (last 7 days)
        from glob import glob

        pattern = os.path.join(self.context_dir, "*-context.md")
        files = sorted(glob(pattern))[-7:]

        task_keywords = self._extract_keywords(task.task)

        for filepath in files:
            signal = self._check_context_file(filepath, task, task_keywords)
            if signal:
                return signal

        return None

    def _check_context_file(
        self, filepath: str, task: ActionItem, keywords: List[str]
    ) -> Optional[CompletionSignal]:
        """Check a context file for completion signals."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Look for completed action items section
            # Pattern: - [x] **Owner**: Task
            for line in content.split("\n"):
                if "[x]" not in line:
                    continue

                # Check if owner matches
                owner_match = task.owner.lower().split()[0] in line.lower()
                if not owner_match:
                    continue

                # Check if task keywords match
                keyword_match = any(kw in line.lower() for kw in keywords)
                if keyword_match:
                    return CompletionSignal(
                        source="daily_context",
                        confidence=0.8,
                        evidence=f"Daily context shows completed: {line.strip()[:100]}",
                        timestamp=os.path.basename(filepath).split("-context")[0],
                    )

        except Exception:
            pass

        return None

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract significant keywords from text."""
        stop_words = {
            "the",
            "a",
            "an",
            "to",
            "for",
            "on",
            "with",
            "and",
            "or",
            "of",
            "in",
            "is",
            "it",
        }
        words = re.findall(r"\b\w{3,}\b", text.lower())
        return [w for w in words if w not in stop_words][:5]


class TaskCompletionInferrer:
    """Infer task completion from multiple context sources."""

    def __init__(self, sources: List[ContextSource], confidence_threshold: float = 0.6):
        self.sources = [s for s in sources if s is not None]
        self.confidence_threshold = confidence_threshold

    @classmethod
    def from_config(cls) -> "TaskCompletionInferrer":
        """Create inferrer from config settings."""
        meeting_config = config_loader.get_meeting_prep_config()
        inference_config = meeting_config.get("task_inference", {})

        if not inference_config.get("enabled", True):
            return cls([], 0.6)

        sources_config = inference_config.get("sources", {})
        confidence_threshold = inference_config.get("confidence_threshold", 0.6)

        # Get paths
        root_path = config_loader.get_root_path()
        user_dir = root_path / "user"

        sources = []

        if sources_config.get("slack", True):
            mentions_path = user_dir / "data" / "slack" / "mentions_state.json"
            sources.append(SlackContextSource(str(mentions_path)))

        if sources_config.get("jira", True):
            # Jira client would be passed in production
            sources.append(JiraContextSource(None))

        if sources_config.get("github", True):
            sources.append(GitHubContextSource(None))

        if sources_config.get("brain", True):
            brain_dir = user_dir / "brain"
            sources.append(BrainContextSource(str(brain_dir)))

        if sources_config.get("daily_context", True):
            context_dir = user_dir / "context"
            sources.append(DailyContextSource(str(context_dir)))

        return cls(sources, confidence_threshold)

    def check_completion(self, task: ActionItem) -> CompletionStatus:
        """
        Check if task appears completed based on context signals.

        Returns:
            CompletionStatus with confidence and evidence
        """
        signals = []

        for source in self.sources:
            try:
                signal = source.check_task(task)
                if signal:
                    signals.append(signal)
            except Exception as e:
                print(f"Error checking {source.source_name}: {e}", file=sys.stderr)

        return self._aggregate_signals(signals)

    def _aggregate_signals(self, signals: List[CompletionSignal]) -> CompletionStatus:
        """Aggregate signals into overall completion status."""
        if not signals:
            return CompletionStatus(
                status="outstanding", confidence=0.0, evidence=[], signals=[]
            )

        # Calculate aggregate confidence
        # Use max confidence as base, boost slightly for multiple signals
        max_confidence = max(s.confidence for s in signals)
        signal_boost = min(0.1 * (len(signals) - 1), 0.2)  # Up to 0.2 boost
        aggregate_confidence = min(max_confidence + signal_boost, 1.0)

        # Determine status
        if aggregate_confidence >= self.confidence_threshold:
            status = "completed"
        elif aggregate_confidence >= 0.3:
            status = "possibly_complete"
        else:
            status = "outstanding"

        evidence = [s.evidence for s in signals]

        return CompletionStatus(
            status=status,
            confidence=aggregate_confidence,
            evidence=evidence,
            signals=signals,
        )

    def enrich_items(self, items: List[Dict]) -> List[Dict]:
        """
        Enrich action items with completion status.

        Args:
            items: List of action item dicts with 'owner', 'task', 'completed' keys

        Returns:
            Enriched items with 'completion_status' added
        """
        enriched = []
        for item in items:
            task = ActionItem(
                owner=item.get("owner", "Unknown"),
                task=item.get("task", ""),
                completed=item.get("completed", False),
            )

            # If already marked complete, skip inference
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


# CLI for testing
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
    print(f"Evidence:")
    for e in status.evidence:
        print(f"  - {e}")
