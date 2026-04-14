#!/usr/bin/env python3
"""
Slack Mention Classifier (v5.0)

Classifies bot mentions into actionable categories:
- OWNER_TASK: Personal tasks for the user
- TEAM_TASK: Tasks delegated to team members
- PM_OS_FEATURE: PM-OS feature requests
- PM_OS_BUG: PM-OS bug reports
- GENERAL: Fallback for unclassified mentions

Ported from v4.x slack_mention_classifier.py — team members from config,
bot name from config, no hardcoded values.

Usage:
    from slack_mention_classifier import classify_mention, MentionType
    result = classify_mention("@bot remind user to review PRD")
"""

import logging
import re
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# v5 shared utils
try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        _base = __import__("pathlib").Path(__file__).resolve().parent.parent.parent.parent
        sys.path.insert(0, str(_base / "pm-os-base" / "tools" / "core"))
        from config_loader import get_config
    except ImportError:
        logger.error("Cannot import pm_os_base core modules")
        raise


def _get_bot_name() -> str:
    """Get the configured mention bot name."""
    return get_config().get("integrations.slack.bot_name", "")


def _get_team_member_names() -> List[str]:
    """
    Get team member first names from config.
    Extracts first names from team.reports list.
    """
    config = get_config()
    reports = config.get("team.reports", [])
    names = []
    for member in reports:
        name = ""
        if isinstance(member, dict):
            name = member.get("name", "")
        elif isinstance(member, str):
            name = member
        if name:
            # Extract first name (lowercase)
            first_name = name.split()[0].lower() if name else ""
            if first_name:
                names.append(first_name)
    return names


def _get_user_name() -> str:
    """Get the user's first name from config."""
    full_name = get_config().get("user.name", "")
    if full_name:
        return full_name.split()[0]
    return ""


class MentionType(Enum):
    """Classification types for bot mentions."""
    PM_OS_FEATURE = "pmos_feature"
    PM_OS_BUG = "pmos_bug"
    OWNER_TASK = "owner_task"
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


# Classification rules — order matters (first match wins for same priority)
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
            "bug", "error", "crash", "timeout", "broken", "fails", "exception",
        ],
        "priority_boost": 0,
    },
    # Tasks for Team Members (Priority 2)
    {
        "type": MentionType.TEAM_TASK,
        "patterns": [
            r"(?i)task\s+for\s+(\w+)",
            r"(?i)remind\s+(\w+)\s+(?:to|about)",
            r"(?i)follow\s+up\s+(?:with\s+)?(\w+)",
            r"(?i)(?:ask|tell|ping)\s+(\w+)\s+(?:to|about)",
            r"(?i)action\s+(?:item\s+)?for\s+(\w+)",
        ],
        "keywords": [],
        "priority_boost": 0,
        "capture_assignee": True,
    },
    # Tasks for the User (Priority 2)
    {
        "type": MentionType.OWNER_TASK,
        "patterns": [],  # Populated dynamically with user name
        "keywords": [],
        "priority_boost": 0,
    },
]


# Priority keywords that increase task urgency
PRIORITY_KEYWORDS = {
    "high": ["urgent", "asap", "critical", "blocker", "today", "eod", "immediately"],
    "medium": ["soon", "this week", "important"],
    "low": ["when you can", "no rush", "whenever", "low priority"],
}


def _get_owner_task_patterns() -> List[str]:
    """Build user-specific task patterns dynamically from config."""
    user_name = _get_user_name().lower()
    if not user_name:
        return []
    return [
        r"(?i)(?:remind|task\s+for|todo\s+for|action\s+for)\s+%s" % re.escape(user_name),
        r"(?i)%s[,:]?\s+(?:please|can\s+you|could\s+you|needs?\s+to)" % re.escape(user_name),
        r"(?i)for\s+%s\s+to" % re.escape(user_name),
        r"(?i)@%s" % re.escape(user_name),
        r"(?i)%s\s+should" % re.escape(user_name),
        r"(?i)(?:ask|tell|ping)\s+%s" % re.escape(user_name),
    ]


def _extract_task_description(text: str, match: Optional[re.Match] = None) -> str:
    """Extract the actual task description from mention text."""
    cleaned = re.sub(r"<@U[A-Z0-9]+(?:\|[^>]+)?>", "", text)
    bot_name = _get_bot_name()
    if bot_name:
        bot_pattern = r"@%s" % re.escape(bot_name).replace(r"\-", "-?")
        cleaned = re.sub(bot_pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"@\w+-?slack-?connect", "", cleaned, flags=re.IGNORECASE)

    if match:
        after_match = text[match.end():].strip()
        after_match = re.sub(r"^[:\-\s]+", "", after_match)
        if after_match and len(after_match) > 10:
            return after_match.strip()

    cleaned = re.sub(r"^[:\-\s]+", "", cleaned.strip())
    return cleaned.strip() if cleaned.strip() else text.strip()


def _extract_assignee(text: str, match: Optional[re.Match] = None) -> Optional[str]:
    """Extract assignee name from text or regex match."""
    team_members = _get_team_member_names()

    if match and match.groups():
        potential_name = match.group(1).lower()
        for member in team_members:
            if member in potential_name or potential_name.startswith(member[:3]):
                return member.title()

    text_lower = text.lower()
    for member in team_members:
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
    text: str, metadata: Optional[Dict[str, Any]] = None,
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
    team_members = _get_team_member_names()
    user_first_name = _get_user_name()

    # Build dynamic rules with user-specific patterns
    rules = list(CLASSIFICATION_RULES)

    # Inject user task patterns
    for rule in rules:
        if rule["type"] == MentionType.OWNER_TASK:
            rule = dict(rule)
            rule["patterns"] = _get_owner_task_patterns()

    for rule in rules:
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
                    assignee = _extract_assignee(text, match)
                    if assignee:
                        result.assignee = assignee
                    else:
                        continue
                elif rule["type"] == MentionType.OWNER_TASK:
                    result.assignee = user_first_name or None

                return result

        for keyword in rule.get("keywords", []):
            if keyword in text_lower:
                result = ClassificationResult(
                    mention_type=rule["type"],
                    confidence=0.6,
                    extracted_task=_extract_task_description(text),
                    priority=_detect_priority(text),
                    matched_keyword=keyword,
                )

                if rule["type"] == MentionType.OWNER_TASK:
                    result.assignee = user_first_name or None
                elif rule.get("capture_assignee"):
                    result.assignee = _extract_assignee(text)

                return result

    # Fallback: check for team member names
    for member in team_members:
        if member in text_lower:
            return ClassificationResult(
                mention_type=MentionType.TEAM_TASK,
                confidence=0.5,
                extracted_task=_extract_task_description(text),
                assignee=member.title(),
                priority=_detect_priority(text),
            )

    return ClassificationResult(
        mention_type=MentionType.GENERAL,
        confidence=0.3,
        extracted_task=_extract_task_description(text),
        priority=_detect_priority(text),
    )


def classify_with_all_matches(text: str) -> List[ClassificationResult]:
    """
    Return all matching classifications for a mention.
    Useful when a message matches multiple categories.
    """
    matches = []
    text_lower = text.lower()
    user_first_name = _get_user_name()

    rules = list(CLASSIFICATION_RULES)
    for rule in rules:
        if rule["type"] == MentionType.OWNER_TASK:
            rule = dict(rule)
            rule["patterns"] = _get_owner_task_patterns()

    for rule in rules:
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
                elif rule["type"] == MentionType.OWNER_TASK:
                    result.assignee = user_first_name or None
                matches.append(result)
                break

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
                    if rule["type"] == MentionType.OWNER_TASK:
                        result.assignee = user_first_name or None
                    matches.append(result)
                    break

    matches.sort(key=lambda x: -x.confidence)

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
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    bot_name = _get_bot_name()
    user_name = _get_user_name()

    test_cases = [
        "@%s remind %s to review the OTP PRD before Friday" % (bot_name, user_name),
        "@%s PM-OS feature request: add Confluence sync" % bot_name,
        "@%s bug: context updater times out on large docs" % bot_name,
        "@%s can you add a new dashboard feature?" % bot_name,
        "@%s the brain sync is broken" % bot_name,
        "@%s hello there!" % bot_name,
    ]

    if len(sys.argv) > 1:
        test_cases = [" ".join(sys.argv[1:])]

    print("=== Slack Mention Classifier Test ===\n")

    for text in test_cases:
        result = classify_mention(text)
        print("Input: %s" % text)
        print("  Type: %s" % result.mention_type.value)
        print("  Confidence: %s" % result.confidence)
        print("  Task: %s" % result.extracted_task)
        print("  Assignee: %s" % result.assignee)
        print("  Priority: %s" % result.priority)
        print()
