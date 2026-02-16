#!/usr/bin/env python3
"""
Slack Mention Classifier

Classifies @pmos-slack-bot mentions into actionable categories:
- JANE_TASK: Personal tasks for Jane Smith
- TEAM_TASK: Tasks delegated to team members
- PM_OS_FEATURE: PM-OS feature requests
- PM_OS_BUG: PM-OS bug reports
- GENERAL: Fallback for unclassified mentions

Usage:
    from slack_mention_classifier import classify_mention, MentionType
    result = classify_mention("@pmos-slack-bot remind Jane to review PRD")
"""

import os
import re
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

# Add parent directory for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    import config_loader

    _BOT_NAME = config_loader.get_slack_mention_bot_name()
except Exception:
    _BOT_NAME = "pmos-slack-bot"


def get_mention_bot_name() -> str:
    """Get the configured mention bot name."""
    return _BOT_NAME


class MentionType(Enum):
    """Classification types for bot mentions."""

    PM_OS_FEATURE = "pmos_feature"
    PM_OS_BUG = "pmos_bug"
    JANE_TASK = "jane_task"
    TEAM_TASK = "team_task"
    GENERAL = "general"


@dataclass
class ClassificationResult:
    """Result of mention classification."""

    mention_type: MentionType
    confidence: float
    extracted_task: str
    assignee: Optional[str] = None
    priority: str = "medium"
    matched_pattern: Optional[str] = None
    matched_keyword: Optional[str] = None


# Known team members for task delegation detection
TEAM_MEMBERS = [
    "pat",
    "alice",
    "bob",
    "frank",
    "daniel",
    "dave",
    "nora",
    "leo",
    "eve",
    "grace",
    "shay",
    "ali",
    "yury",
    "holger",
    "alexander",
    "alex",
]

# Classification rules - order matters (first match wins for same priority)
CLASSIFICATION_RULES = [
    # PM-OS Feature Requests (Priority 1)
    {
        "type": MentionType.PM_OS_FEATURE,
        "patterns": [
            r"(?i)pm-?os\s+feature",
            r"(?i)feature\s+request[:\s]",
            r"(?i)brain\s+feature",
            r"(?i)add\s+(?:a\s+)?(?:new\s+)?feature",
            r"(?i)could\s+(?:you\s+)?(?:please\s+)?add",
            r"(?i)would\s+be\s+nice\s+(?:to\s+have|if)",
            r"(?i)enhancement[:\s]",
            r"(?i)context\s+(?:updater|system)\s+(?:should|could)",
        ],
        "keywords": ["feature", "enhancement", "capability", "add support"],
        "priority_boost": 0,
    },
    # PM-OS Bugs/Issues (Priority 1)
    {
        "type": MentionType.PM_OS_BUG,
        "patterns": [
            r"(?i)pm-?os\s+bug",
            r"(?i)bug[:\s]",
            r"(?i)issue[:\s]",
            r"(?i)(?:context|updater|brain|sync)\s+(?:error|fail|crash|timeout|broke)",
            r"(?i)broken[:\s]",
            r"(?i)not\s+working",
            r"(?i)(?:throws?|raising?|getting)\s+(?:an?\s+)?error",
        ],
        "keywords": [
            "bug",
            "error",
            "crash",
            "timeout",
            "broken",
            "fails",
            "exception",
        ],
        "priority_boost": 0,
    },
    # Tasks for Team Members (Priority 2 - check before Jane to catch specific names)
    {
        "type": MentionType.TEAM_TASK,
        "patterns": [
            r"(?i)task\s+for\s+(\w+)",
            r"(?i)remind\s+(\w+)\s+(?:to|about)",
            r"(?i)follow\s+up\s+(?:with\s+)?(\w+)",
            r"(?i)(?:ask|tell|ping)\s+(\w+)\s+(?:to|about)",
            r"(?i)action\s+(?:item\s+)?for\s+(\w+)",
        ],
        "keywords": [],  # Team member names checked dynamically
        "priority_boost": 0,
        "capture_assignee": True,
    },
    # Tasks for Jane (Priority 2)
    {
        "type": MentionType.JANE_TASK,
        "patterns": [
            r"(?i)(?:remind|task\s+for|todo\s+for|action\s+for)\s+jane",
            r"(?i)jane[,:]?\s+(?:please|can\s+you|could\s+you|needs?\s+to)",
            r"(?i)for\s+jane\s+to",
            r"(?i)@jane",
            r"(?i)jane\s+should",
            r"(?i)(?:ask|tell|ping)\s+jane",
        ],
        "keywords": [],  # Remove broad keyword matching to avoid false positives
        "priority_boost": 0,
    },
]

# Priority keywords that increase task urgency
PRIORITY_KEYWORDS = {
    "high": ["urgent", "asap", "critical", "blocker", "today", "eod", "immediately"],
    "medium": ["soon", "this week", "important"],
    "low": ["when you can", "no rush", "whenever", "low priority"],
}


def _extract_task_description(text: str, match: Optional[re.Match] = None) -> str:
    """Extract the actual task description from mention text."""
    # Remove bot mention pattern
    cleaned = re.sub(r"<@U[A-Z0-9]+(?:\|[^>]+)?>", "", text)
    # Remove configured bot name (with optional hyphens for variations)
    bot_name = get_mention_bot_name()
    bot_pattern = rf'@{re.escape(bot_name).replace("-", "-?")}'
    cleaned = re.sub(bot_pattern, "", cleaned, flags=re.IGNORECASE)
    # Also remove common variations
    cleaned = re.sub(r"@\w+-?slack-?connect", "", cleaned, flags=re.IGNORECASE)

    # If we have a match, try to get text after it
    if match:
        after_match = text[match.end() :].strip()
        after_match = re.sub(r"^[:\-\s]+", "", after_match)
        if after_match and len(after_match) > 10:
            return after_match.strip()

    # Clean up common prefixes
    cleaned = re.sub(r"^[:\-\s]+", "", cleaned.strip())
    return cleaned.strip() if cleaned.strip() else text.strip()


def _extract_assignee(text: str, match: Optional[re.Match] = None) -> Optional[str]:
    """Extract assignee name from text or regex match."""
    # Try to get from regex capture group
    if match and match.groups():
        potential_name = match.group(1).lower()
        for member in TEAM_MEMBERS:
            if member in potential_name or potential_name.startswith(member[:3]):
                return member.title()

    # Scan text for team member names
    text_lower = text.lower()
    for member in TEAM_MEMBERS:
        if member in text_lower:
            return member.title()

    return None


def _detect_priority(text: str) -> str:
    """Detect task priority from text."""
    text_lower = text.lower()

    for priority, keywords in PRIORITY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return priority

    return "medium"


def classify_mention(
    text: str, metadata: Optional[Dict[str, Any]] = None
) -> ClassificationResult:
    """
    Classify a bot mention into one of the predefined categories.

    Args:
        text: The mention message text
        metadata: Optional metadata (channel, user, etc.)

    Returns:
        ClassificationResult with type, confidence, and extracted info
    """
    text_lower = text.lower()

    for rule in CLASSIFICATION_RULES:
        # Check patterns first (higher confidence)
        for pattern in rule.get("patterns", []):
            match = re.search(pattern, text)
            if match:
                result = ClassificationResult(
                    mention_type=rule["type"],
                    confidence=0.9,
                    extracted_task=_extract_task_description(text, match),
                    priority=_detect_priority(text),
                    matched_pattern=pattern,
                )

                # Extract assignee for team tasks
                if rule.get("capture_assignee"):
                    assignee = _extract_assignee(text, match)
                    if assignee:
                        result.assignee = assignee
                    else:
                        # No team member found, might be general mention
                        continue
                elif rule["type"] == MentionType.JANE_TASK:
                    result.assignee = "Jane"

                return result

        # Check keywords (lower confidence)
        for keyword in rule.get("keywords", []):
            if keyword in text_lower:
                result = ClassificationResult(
                    mention_type=rule["type"],
                    confidence=0.6,
                    extracted_task=_extract_task_description(text),
                    priority=_detect_priority(text),
                    matched_keyword=keyword,
                )

                if rule["type"] == MentionType.JANE_TASK:
                    result.assignee = "Jane"
                elif rule.get("capture_assignee"):
                    result.assignee = _extract_assignee(text)

                return result

    # Check for team member mentions as fallback
    for member in TEAM_MEMBERS:
        if member in text_lower:
            return ClassificationResult(
                mention_type=MentionType.TEAM_TASK,
                confidence=0.5,
                extracted_task=_extract_task_description(text),
                assignee=member.title(),
                priority=_detect_priority(text),
            )

    # Fallback to general
    return ClassificationResult(
        mention_type=MentionType.GENERAL,
        confidence=0.3,
        extracted_task=_extract_task_description(text),
        priority="medium",
    )


def classify_with_all_matches(text: str) -> List[ClassificationResult]:
    """
    Return all matching classifications for a mention.
    Useful when a message matches multiple categories.

    Args:
        text: The mention message text

    Returns:
        List of ClassificationResult, sorted by confidence
    """
    matches = []
    text_lower = text.lower()

    for rule in CLASSIFICATION_RULES:
        # Check patterns
        for pattern in rule.get("patterns", []):
            match = re.search(pattern, text)
            if match:
                result = ClassificationResult(
                    mention_type=rule["type"],
                    confidence=0.9,
                    extracted_task=_extract_task_description(text, match),
                    priority=_detect_priority(text),
                    matched_pattern=pattern,
                )
                if rule.get("capture_assignee"):
                    result.assignee = _extract_assignee(text, match)
                elif rule["type"] == MentionType.JANE_TASK:
                    result.assignee = "Jane"
                matches.append(result)
                break  # Only one match per rule

        # Check keywords if no pattern matched
        if not any(m.mention_type == rule["type"] for m in matches):
            for keyword in rule.get("keywords", []):
                if keyword in text_lower:
                    result = ClassificationResult(
                        mention_type=rule["type"],
                        confidence=0.6,
                        extracted_task=_extract_task_description(text),
                        priority=_detect_priority(text),
                        matched_keyword=keyword,
                    )
                    if rule["type"] == MentionType.JANE_TASK:
                        result.assignee = "Jane"
                    matches.append(result)
                    break

    # Sort by confidence descending
    matches.sort(key=lambda x: -x.confidence)

    # Add general fallback if no matches
    if not matches:
        matches.append(
            ClassificationResult(
                mention_type=MentionType.GENERAL,
                confidence=0.3,
                extracted_task=_extract_task_description(text),
                priority="medium",
            )
        )

    return matches


# --- CLI for testing ---
if __name__ == "__main__":
    bot_name = get_mention_bot_name()

    test_cases = [
        f"@{bot_name} remind Jane to review the OTP PRD before Friday",
        f"@{bot_name} PM-OS feature request: add Confluence sync",
        f"@{bot_name} bug: context updater times out on large docs",
        f"@{bot_name} task for Pat: follow up on Meal Kit launch",
        f"@{bot_name} can you add a new dashboard feature?",
        f"@{bot_name} the brain sync is broken",
        f"@{bot_name} tell Alice about the meeting tomorrow",
        f"@{bot_name} hello there!",
    ]

    if len(sys.argv) > 1:
        test_cases = [" ".join(sys.argv[1:])]

    print("=== Slack Mention Classifier Test ===\n")

    for text in test_cases:
        result = classify_mention(text)
        print(f"Input: {text}")
        print(f"  Type: {result.mention_type.value}")
        print(f"  Confidence: {result.confidence}")
        print(f"  Task: {result.extracted_task}")
        print(f"  Assignee: {result.assignee}")
        print(f"  Priority: {result.priority}")
        print()
