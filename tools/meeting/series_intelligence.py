"""
Series Intelligence

Extract and synthesize intelligence from meeting series history.
Tracks commitments, decisions, recurring topics, and unresolved questions.

Usage:
    from series_intelligence import SeriesIntelligence

    si = SeriesIntelligence()
    outcomes = si.extract_outcomes(series_history)
    summary = si.synthesize_history(outcomes)
"""

import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set

# Add parent directory to path for config_loader
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config_loader


@dataclass
class Commitment:
    """Represents a commitment made in a meeting."""

    owner: str
    description: str
    due_date: Optional[str] = None
    status: str = "open"  # 'open', 'completed', 'overdue'
    source_date: str = ""  # Date of meeting where commitment was made


@dataclass
class MeetingOutcome:
    """Structured outcome from a past meeting."""

    date: str
    decisions: List[str] = field(default_factory=list)
    commitments: List[Commitment] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    topics_discussed: List[str] = field(default_factory=list)
    key_points: List[str] = field(default_factory=list)


class SeriesIntelligence:
    """Extract and synthesize intelligence from meeting series history."""

    def __init__(self):
        pass

    def extract_outcomes(self, series_history: List[Dict]) -> List[MeetingOutcome]:
        """
        Parse structured outcomes from past meeting entries.

        Args:
            series_history: List of meeting history entries with 'date', 'summary', 'key_points'

        Returns:
            List of MeetingOutcome objects
        """
        outcomes = []

        for entry in series_history:
            content = entry.get("summary", "")
            date = entry.get("date", "")
            key_points = entry.get("key_points", [])

            outcome = MeetingOutcome(
                date=date,
                decisions=self._extract_decisions(content),
                commitments=self._extract_commitments(content, date),
                recommendations=self._extract_recommendations(content),
                open_questions=self._extract_questions(content),
                topics_discussed=self._extract_topics(content, key_points),
                key_points=key_points,
            )

            outcomes.append(outcome)

        return outcomes

    def get_open_commitments(self, outcomes: List[MeetingOutcome]) -> List[Commitment]:
        """Get commitments that haven't been completed."""
        all_commitments = []

        for outcome in outcomes:
            for commitment in outcome.commitments:
                if commitment.status != "completed":
                    # Check if overdue
                    if commitment.due_date:
                        try:
                            due = datetime.strptime(commitment.due_date, "%Y-%m-%d")
                            if due < datetime.now():
                                commitment.status = "overdue"
                        except ValueError:
                            pass

                    all_commitments.append(commitment)

        # Sort by source date (oldest first for urgency)
        all_commitments.sort(key=lambda c: c.source_date)

        return all_commitments

    def get_recurring_topics(
        self, outcomes: List[MeetingOutcome], min_count: int = 3
    ) -> List[Dict]:
        """
        Identify topics that keep coming up (potential stuck issues).

        Args:
            outcomes: List of meeting outcomes
            min_count: Minimum times discussed to be considered recurring

        Returns:
            List of dicts with 'topic' and 'count' keys
        """
        topic_counts = Counter()

        for outcome in outcomes:
            for topic in outcome.topics_discussed:
                # Normalize topic for counting
                normalized = topic.lower().strip()
                if len(normalized) > 5:  # Skip very short topics
                    topic_counts[normalized] += 1

        # Return topics discussed >= min_count times
        recurring = [
            {"topic": topic, "count": count}
            for topic, count in topic_counts.items()
            if count >= min_count
        ]

        return sorted(recurring, key=lambda x: x["count"], reverse=True)

    def get_unresolved_questions(self, outcomes: List[MeetingOutcome]) -> List[str]:
        """Get questions that were raised but never resolved."""
        all_questions: Set[str] = set()
        resolved: Set[str] = set()

        for outcome in outcomes:
            # Add open questions
            all_questions.update(outcome.open_questions)

            # Check if decisions resolve any questions
            for decision in outcome.decisions:
                for q in list(all_questions):
                    if self._decision_resolves_question(decision, q):
                        resolved.add(q)

        return list(all_questions - resolved)

    def get_recent_decisions(
        self, outcomes: List[MeetingOutcome], limit: int = 5
    ) -> List[Dict]:
        """Get recent decisions from meetings."""
        decisions = []

        for outcome in sorted(outcomes, key=lambda o: o.date, reverse=True):
            for decision in outcome.decisions:
                decisions.append({"date": outcome.date, "decision": decision})

                if len(decisions) >= limit:
                    return decisions

        return decisions

    def synthesize_history(self, outcomes: List[MeetingOutcome]) -> str:
        """Generate synthesized history summary for prep doc."""
        if not outcomes:
            return ""

        open_commitments = self.get_open_commitments(outcomes)
        recurring_topics = self.get_recurring_topics(outcomes, min_count=2)
        unresolved_questions = self.get_unresolved_questions(outcomes)
        recent_decisions = self.get_recent_decisions(outcomes, limit=5)

        sections = []

        # Open Commitments
        if open_commitments:
            commitment_lines = []
            for c in open_commitments[:10]:  # Limit to 10
                status_note = f" *({c.status})* " if c.status == "overdue" else ""
                commitment_lines.append(
                    f"- **{c.owner}** (from {c.source_date}): {c.description}{status_note}"
                )
            sections.append(
                "### Open Commitments (Carry-Forward)\n" + "\n".join(commitment_lines)
            )

        # Recurring Topics
        if recurring_topics:
            topic_lines = []
            for t in recurring_topics[:5]:
                topic_lines.append(
                    f"- {t['topic'].title()} ({t['count']} meetings)\n"
                    f"  - *Pattern: This keeps coming up - may need escalation*"
                )
            sections.append(
                "### Recurring Topics (Potential Stuck Issues)\n"
                + "\n".join(topic_lines)
            )

        # Unresolved Questions
        if unresolved_questions:
            question_lines = [f"- {q}" for q in unresolved_questions[:5]]
            sections.append("### Unresolved Questions\n" + "\n".join(question_lines))

        # Recent Decisions
        if recent_decisions:
            decision_lines = []
            for d in recent_decisions[:5]:
                decision_lines.append(f"- {d['date']}: {d['decision']}")
            sections.append("### Recent Decisions\n" + "\n".join(decision_lines))

        if sections:
            return "## Series Intelligence\n\n" + "\n\n".join(sections)

        return ""

    # =========================================================================
    # Extraction Methods
    # =========================================================================

    def _extract_decisions(self, content: str) -> List[str]:
        """Extract decisions from meeting content."""
        decisions = []

        # Pattern 1: "Decided to...", "Decision:", "Agreed to..."
        patterns = [
            r"(?:decided|decision|agreed)\s*(?:to|:)\s*(.+?)(?:\.|$)",
            r"(?:we will|will)\s+(.+?)(?:\.|$)",
            r"\*\*decision\*\*:?\s*(.+?)(?:\n|$)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            decisions.extend([m.strip() for m in matches if len(m.strip()) > 10])

        # Pattern 2: Lines starting with "Decision:" or similar
        for line in content.split("\n"):
            line = line.strip()
            if line.lower().startswith(("decision:", "decided:", "agreed:")):
                decision = line.split(":", 1)[-1].strip()
                if decision and len(decision) > 10:
                    decisions.append(decision)

        return list(set(decisions))[:10]

    def _extract_commitments(self, content: str, source_date: str) -> List[Commitment]:
        """Extract commitments from meeting content."""
        commitments = []

        # Pattern 1: "X will do Y", "X to follow up on Y"
        patterns = [
            r"(\w+)\s+will\s+(.+?)(?:\.|$)",
            r"(\w+)\s+to\s+(?:follow up|check|review|send|create|update|prepare|share)\s+(.+?)(?:\.|$)",
            r"\*\*(\w+)\*\*:?\s+(?:will|to)\s+(.+?)(?:\.|$)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                owner = match[0].strip().title()
                description = match[1].strip()

                # Skip if too short or generic
                if len(description) < 10:
                    continue
                if owner.lower() in ["the", "we", "they", "it", "this"]:
                    continue

                commitments.append(
                    Commitment(
                        owner=owner,
                        description=description[:200],
                        source_date=source_date,
                        status="open",
                    )
                )

        # Pattern 2: Action item format "- [ ] **Owner**: Task"
        action_pattern = r"-\s*\[\s*([x ])\s*\]\s*\*\*([^*]+)\*\*:?\s*(.+?)(?:\n|$)"
        for match in re.finditer(action_pattern, content, re.IGNORECASE):
            completed = match.group(1).lower() == "x"
            owner = match.group(2).strip()
            description = match.group(3).strip()

            commitments.append(
                Commitment(
                    owner=owner,
                    description=description[:200],
                    source_date=source_date,
                    status="completed" if completed else "open",
                )
            )

        return commitments[:15]

    def _extract_recommendations(self, content: str) -> List[str]:
        """Extract recommendations for follow-up."""
        recommendations = []

        patterns = [
            r"(?:recommend|suggestion|should consider)\s*(?::)?\s*(.+?)(?:\.|$)",
            r"(?:next steps?|follow[- ]up)\s*(?::)?\s*(.+?)(?:\.|$)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            recommendations.extend([m.strip() for m in matches if len(m.strip()) > 10])

        return list(set(recommendations))[:5]

    def _extract_questions(self, content: str) -> List[str]:
        """Extract open questions from meeting content."""
        questions = []

        # Pattern 1: Lines ending with "?"
        for line in content.split("\n"):
            line = line.strip()
            if line.endswith("?") and len(line) > 15:
                # Clean markdown and bullets
                clean = re.sub(r"^[-*•]\s*", "", line)
                clean = re.sub(r"\*\*|\*|`", "", clean)
                questions.append(clean)

        # Pattern 2: "Question:", "TBD:", "To determine:"
        for line in content.split("\n"):
            line = line.strip()
            if line.lower().startswith(("question:", "tbd:", "open:", "unclear:")):
                question = line.split(":", 1)[-1].strip()
                if question and len(question) > 10:
                    questions.append(question)

        return list(set(questions))[:10]

    def _extract_topics(self, content: str, key_points: List[str]) -> List[str]:
        """Extract main topics discussed."""
        topics = set()

        # Add key points as topics
        for point in key_points:
            # Extract first few meaningful words
            clean = re.sub(r"^[-*•]\s*", "", point)
            clean = re.sub(r"\*\*|\*|`", "", clean)
            words = clean.split()[:5]
            if words:
                topics.add(" ".join(words))

        # Look for headers (## Topic)
        headers = re.findall(r"^##\s+(.+?)$", content, re.MULTILINE)
        for header in headers:
            if len(header) > 5 and len(header) < 100:
                topics.add(header.strip())

        # Look for bold items that might be topics
        bold_items = re.findall(r"\*\*([^*]+)\*\*", content)
        for item in bold_items:
            if 5 < len(item) < 50:
                topics.add(item.strip())

        return list(topics)[:15]

    def _decision_resolves_question(self, decision: str, question: str) -> bool:
        """Check if a decision appears to resolve a question."""
        # Simple keyword overlap check
        decision_words = set(re.findall(r"\b\w{4,}\b", decision.lower()))
        question_words = set(re.findall(r"\b\w{4,}\b", question.lower()))

        # Remove common words
        stop_words = {
            "will",
            "what",
            "when",
            "where",
            "does",
            "should",
            "could",
            "would",
            "have",
            "this",
            "that",
            "with",
            "from",
            "about",
        }
        decision_words -= stop_words
        question_words -= stop_words

        # Check overlap
        overlap = len(decision_words & question_words)
        return overlap >= 2


# CLI for testing
if __name__ == "__main__":
    import json

    # Test with sample data
    sample_history = [
        {
            "date": "2026-01-20",
            "summary": """
            Discussed Growth Platform metrics. Jane will review the dashboard.
            Decision: We will proceed with the new pricing model.
            Question: Does HIPAA compliance block current B2B roadmap?
            """,
            "key_points": [
                "Growth Platform metrics",
                "Pricing model decision",
                "HIPAA compliance question",
            ],
        },
        {
            "date": "2026-01-13",
            "summary": """
            Growth Platform metrics came up again. Alice to create shelf doc for OTP.
            Agreed to escalate payment bug to Shashir.
            """,
            "key_points": [
                "Growth Platform metrics",
                "OTP shelf doc",
                "Payment bug escalation",
            ],
        },
        {
            "date": "2026-01-06",
            "summary": """
            Growth Platform metrics discussed. Need to provide cost estimates for Juices.
            Decision: Committed to providing cost estimates by end of week.
            """,
            "key_points": ["Growth Platform metrics", "Juices cost estimates"],
        },
    ]

    si = SeriesIntelligence()
    outcomes = si.extract_outcomes(sample_history)

    print("=== Series Intelligence Test ===\n")
    print(si.synthesize_history(outcomes))
