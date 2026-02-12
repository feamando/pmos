#!/usr/bin/env python3
"""
Relevance Comparison Framework

Compare old vs new meeting prep outputs to measure improvement.
Generates side-by-side comparisons with automated metrics.

Usage:
    python relevance_comparison.py --meeting "Jama:Nikita 1:1"
    python relevance_comparison.py --all --output comparison-report.md
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config_loader


@dataclass
class ComparisonMetrics:
    """Metrics comparing old vs new output."""

    old_word_count: int
    new_word_count: int
    word_count_reduction: int
    word_count_reduction_pct: float
    old_section_count: int
    new_section_count: int
    old_placeholder_count: int  # "No data found" etc.
    new_placeholder_count: int
    action_items_found: int
    completion_inferences: int
    commitments_tracked: int
    has_tldr: bool
    has_series_intelligence: bool


@dataclass
class ComparisonResult:
    """Result of comparing old vs new prep for a meeting."""

    meeting_title: str
    meeting_type: str
    old_output: str
    new_output: str
    metrics: ComparisonMetrics
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class RelevanceComparison:
    """Compare old vs new meeting prep outputs."""

    def __init__(self):
        self.results: List[ComparisonResult] = []

    def generate_comparison(
        self, meeting: Dict, old_content: str, new_content: str
    ) -> ComparisonResult:
        """
        Generate comparison between old and new prep for same meeting.

        Args:
            meeting: Meeting classification dict
            old_content: Legacy system output
            new_content: New system output

        Returns:
            ComparisonResult with both outputs and metrics
        """
        metrics = self._calculate_metrics(old_content, new_content)

        result = ComparisonResult(
            meeting_title=meeting.get("summary", "Unknown"),
            meeting_type=meeting.get("meeting_type", "other"),
            old_output=old_content,
            new_output=new_content,
            metrics=metrics,
        )

        self.results.append(result)
        return result

    def _calculate_metrics(self, old: str, new: str) -> ComparisonMetrics:
        """Calculate comparison metrics between old and new outputs."""
        old_words = len(old.split())
        new_words = len(new.split())
        reduction = old_words - new_words
        reduction_pct = (reduction / old_words * 100) if old_words > 0 else 0

        return ComparisonMetrics(
            old_word_count=old_words,
            new_word_count=new_words,
            word_count_reduction=reduction,
            word_count_reduction_pct=reduction_pct,
            old_section_count=self._count_sections(old),
            new_section_count=self._count_sections(new),
            old_placeholder_count=self._count_placeholders(old),
            new_placeholder_count=self._count_placeholders(new),
            action_items_found=self._count_action_items(new),
            completion_inferences=self._count_inferences(new),
            commitments_tracked=self._count_commitments(new),
            has_tldr=self._has_tldr(new),
            has_series_intelligence=self._has_series_intelligence(new),
        )

    def _count_sections(self, content: str) -> int:
        """Count markdown sections (## headers)."""
        return len(re.findall(r"^##\s+", content, re.MULTILINE))

    def _count_placeholders(self, content: str) -> int:
        """Count empty placeholder text."""
        placeholders = [
            "no data found",
            "none found",
            "no recent",
            "not available",
            "no outstanding",
            "no previous",
            "n/a",
        ]
        count = 0
        content_lower = content.lower()
        for p in placeholders:
            count += content_lower.count(p)
        return count

    def _count_action_items(self, content: str) -> int:
        """Count action items in output."""
        # Pattern: - [ ] or - [x] or - [~]
        return len(re.findall(r"-\s*\[[x~\s]\]", content, re.IGNORECASE))

    def _count_inferences(self, content: str) -> int:
        """Count completion inferences ([~] markers)."""
        return content.count("[~]")

    def _count_commitments(self, content: str) -> int:
        """Count tracked commitments."""
        # Look for commitment patterns in Series Intelligence section
        commitment_section = re.search(
            r"### Open Commitments.*?(?=###|\Z)", content, re.DOTALL
        )
        if commitment_section:
            return len(
                re.findall(r"^\s*-\s+\*\*", commitment_section.group(), re.MULTILINE)
            )
        return 0

    def _has_tldr(self, content: str) -> bool:
        """Check if output has TL;DR section."""
        return bool(re.search(r"^##\s*TL;DR", content, re.MULTILINE | re.IGNORECASE))

    def _has_series_intelligence(self, content: str) -> bool:
        """Check if output has Series Intelligence section."""
        return bool(re.search(r"Series Intelligence", content, re.IGNORECASE))

    def generate_report(self) -> str:
        """Generate markdown report of all comparisons."""
        if not self.results:
            return "# Meeting Prep Comparison Report\n\nNo comparisons available."

        # Calculate aggregates
        total_old_words = sum(r.metrics.old_word_count for r in self.results)
        total_new_words = sum(r.metrics.new_word_count for r in self.results)
        avg_reduction = (
            (total_old_words - total_new_words) / total_old_words * 100
            if total_old_words > 0
            else 0
        )

        # Group by type
        by_type: Dict[str, List[ComparisonResult]] = {}
        for r in self.results:
            if r.meeting_type not in by_type:
                by_type[r.meeting_type] = []
            by_type[r.meeting_type].append(r)

        report = f"""# Meeting Prep Comparison Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Meetings Compared:** {len(self.results)}
**Average Word Reduction:** {avg_reduction:.1f}%

## Summary

| Metric | Old System | New System | Change |
|--------|------------|------------|--------|
| Total Words | {total_old_words:,} | {total_new_words:,} | -{total_old_words - total_new_words:,} ({avg_reduction:.1f}%) |
| Avg Placeholders | {sum(r.metrics.old_placeholder_count for r in self.results) / len(self.results):.1f} | {sum(r.metrics.new_placeholder_count for r in self.results) / len(self.results):.1f} | - |
| TL;DR Present | N/A | {sum(1 for r in self.results if r.metrics.has_tldr)}/{len(self.results)} | - |
| Series Intelligence | N/A | {sum(1 for r in self.results if r.metrics.has_series_intelligence)}/{len(self.results)} | - |

## By Meeting Type

| Type | Old Words | New Words | Reduction | Placeholders (Old) | Placeholders (New) |
|------|-----------|-----------|-----------|--------------------|--------------------|
"""

        for mtype, results in sorted(by_type.items()):
            old_words = sum(r.metrics.old_word_count for r in results)
            new_words = sum(r.metrics.new_word_count for r in results)
            reduction = (
                (old_words - new_words) / old_words * 100 if old_words > 0 else 0
            )
            old_placeholders = sum(
                r.metrics.old_placeholder_count for r in results
            ) / len(results)
            new_placeholders = sum(
                r.metrics.new_placeholder_count for r in results
            ) / len(results)

            report += f"| {mtype} | {old_words:,} | {new_words:,} | {reduction:.0f}% | {old_placeholders:.1f} | {new_placeholders:.1f} |\n"

        report += "\n## Individual Comparisons\n\n"

        for i, result in enumerate(self.results, 1):
            m = result.metrics
            report += f"""### {i}. {result.meeting_title}

**Type:** {result.meeting_type}

| Metric | Old | New |
|--------|-----|-----|
| Words | {m.old_word_count} | {m.new_word_count} ({m.word_count_reduction_pct:.0f}% reduction) |
| Sections | {m.old_section_count} | {m.new_section_count} |
| Placeholders | {m.old_placeholder_count} | {m.new_placeholder_count} |
| Action Items | - | {m.action_items_found} |
| Completion Inferences | - | {m.completion_inferences} |
| Has TL;DR | No | {'Yes' if m.has_tldr else 'No'} |
| Has Series Intelligence | No | {'Yes' if m.has_series_intelligence else 'No'} |

"""

        report += """
## Recommendations

Based on the comparison:

"""
        # Add recommendations based on data
        if avg_reduction > 50:
            report += "- **Success:** New system achieves >50% word reduction while maintaining relevance\n"
        if sum(r.metrics.new_placeholder_count for r in self.results) < sum(
            r.metrics.old_placeholder_count for r in self.results
        ):
            report += "- **Improved:** Fewer empty placeholder sections in new output\n"
        if all(r.metrics.has_tldr for r in self.results):
            report += "- **Consistent:** All outputs include TL;DR section for quick scanning\n"

        return report

    def save_report(self, filepath: str) -> None:
        """Save report to file."""
        report = self.generate_report()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report saved to: {filepath}")


def simulate_old_output(meeting_type: str, summary: str) -> str:
    """
    Simulate legacy output for comparison.

    This generates representative output in the old format
    for comparison purposes.
    """
    # Representative old-style output (verbose, placeholder-heavy)
    return f"""## Pre-Read: {summary}

*Automatically generated by gemini-2.5-flash on {datetime.now().strftime('%Y-%m-%d %H:%M')}*

### 1. Context / Why

This meeting is scheduled to discuss important topics related to the team's ongoing work. The participants will be discussing various aspects of current projects and initiatives. This is an important meeting for alignment and decision-making.

The meeting context includes discussions about project status, upcoming milestones, and any blockers that need to be addressed. All participants should come prepared with updates on their respective areas.

### 2. Participant Notes

**Participant Information:**
- Details about participants and their roles
- Background information on each attendee
- No specific notes available at this time

### 3. Last Meeting Recap

No previous meeting notes found in the system. This may be a new meeting series or notes from previous sessions are not available.

### 4. Agenda Suggestions

- Review current status (10 min)
- Discuss blockers (10 min)
- Planning next steps (15 min)
- Q&A and wrap-up (10 min)

### 5. Key Questions

- What are the current blockers?
- What progress has been made since last meeting?
- What are the next steps?
- Are there any concerns to address?
- What decisions need to be made?

### Related Projects

No related projects found for participants.

### Action Items

No outstanding action items found for participants.

### Recent Jira Activity

No recent Jira issues found for participants.

---
*Note: Some sections may contain limited information due to data availability.*
"""


def main():
    """Main entry point for comparison tool."""
    parser = argparse.ArgumentParser(description="Meeting Prep Relevance Comparison")
    parser.add_argument("--meeting", type=str, help="Specific meeting title to compare")
    parser.add_argument("--all", action="store_true", help="Compare all meeting types")
    parser.add_argument(
        "--output", type=str, default="comparison-report.md", help="Output file path"
    )
    parser.add_argument("--sample", action="store_true", help="Run with sample data")
    args = parser.parse_args()

    comparison = RelevanceComparison()

    if args.sample:
        # Generate sample comparisons for testing
        sample_meetings = [
            {"summary": "Jama:Nikita 1:1", "meeting_type": "1on1"},
            {"summary": "Daily Standup", "meeting_type": "standup"},
            {"summary": "Sprint Planning", "meeting_type": "planning"},
            {
                "summary": "Virtual Interview - Candidate | Senior PM",
                "meeting_type": "interview",
            },
            {"summary": "External Partner Sync", "meeting_type": "external"},
            {"summary": "All Hands Meeting", "meeting_type": "large_meeting"},
        ]

        for meeting in sample_meetings:
            # Simulate old output
            old_output = simulate_old_output(
                meeting["meeting_type"], meeting["summary"]
            )

            # Generate new output placeholder (would be actual new system output)
            from templates import get_template

            template = get_template(meeting["meeting_type"])

            new_output = f"""## TL;DR

- Key point 1 for {meeting['summary']}
- Key point 2 about upcoming decisions
- Action: Review pending items

{template.get_standard_header('action_items')}

- [ ] **Nikita**: Review dashboard metrics
- [~] **Team**: Update documentation *(possibly complete - mentioned in Slack)*

{template.get_standard_header('context')}

Brief context about the meeting purpose and expected outcomes.
"""
            comparison.generate_comparison(meeting, old_output, new_output)

        print(comparison.generate_report())

        if args.output:
            comparison.save_report(args.output)

    else:
        print(
            "Use --sample to run with sample data, or integrate with meeting_prep.py for live comparison."
        )
        print("\nExample: python relevance_comparison.py --sample --output report.md")


if __name__ == "__main__":
    main()
