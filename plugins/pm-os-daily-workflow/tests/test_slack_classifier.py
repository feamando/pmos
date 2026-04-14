"""Tests for slack_mention_classifier.py — mention classification."""

from unittest.mock import patch

import pytest


class TestMentionType:
    """Validate MentionType enum values."""

    def test_enum_values_are_generic(self):
        from slack.slack_mention_classifier import MentionType

        # Must NOT contain user-specific names
        for member in MentionType:
            assert "nikita" not in member.value.lower()
            assert "nikita" not in member.name.lower()

    def test_owner_task_exists(self):
        from slack.slack_mention_classifier import MentionType

        assert hasattr(MentionType, "OWNER_TASK")
        assert MentionType.OWNER_TASK.value == "owner_task"

    def test_all_types_present(self):
        from slack.slack_mention_classifier import MentionType

        names = {m.name for m in MentionType}
        assert "PM_OS_FEATURE" in names
        assert "PM_OS_BUG" in names
        assert "OWNER_TASK" in names
        assert "TEAM_TASK" in names
        assert "GENERAL" in names


class TestClassifyMention:
    """Test classify_mention with mock config."""

    def test_feature_request(self, mock_config):
        from slack.slack_mention_classifier import classify_mention, MentionType

        result = classify_mention("@bot PM-OS feature request: add Confluence sync")
        assert result.mention_type == MentionType.PM_OS_FEATURE
        assert result.confidence >= 0.6

    def test_bug_report(self, mock_config):
        from slack.slack_mention_classifier import classify_mention, MentionType

        result = classify_mention("@bot bug: context updater times out")
        assert result.mention_type == MentionType.PM_OS_BUG

    def test_team_task_with_known_member(self, mock_config):
        from slack.slack_mention_classifier import classify_mention, MentionType

        result = classify_mention("@bot remind Alice to update the PRD")
        assert result.mention_type == MentionType.TEAM_TASK
        assert result.assignee is not None

    def test_general_fallback(self, mock_config):
        from slack.slack_mention_classifier import classify_mention, MentionType

        result = classify_mention("@bot hello there!")
        assert result.mention_type == MentionType.GENERAL

    def test_priority_detection_high(self, mock_config):
        from slack.slack_mention_classifier import classify_mention

        # Use text that won't match bug/feature patterns, only general + urgent keyword
        result = classify_mention("@bot urgent please review the deployment plan ASAP")
        assert result.priority == "high"

    def test_priority_detection_low(self, mock_config):
        from slack.slack_mention_classifier import classify_mention

        # Use text that won't match bug/feature patterns
        result = classify_mention("@bot no rush but when you can please check the summary")
        assert result.priority == "low"


class TestClassifyWithAllMatches:
    """Test classify_with_all_matches returns multiple."""

    def test_returns_list(self, mock_config):
        from slack.slack_mention_classifier import classify_with_all_matches

        results = classify_with_all_matches("@bot PM-OS feature request: add Confluence sync")
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_sorted_by_confidence(self, mock_config):
        from slack.slack_mention_classifier import classify_with_all_matches

        results = classify_with_all_matches("@bot bug: feature request issue")
        confidences = [r.confidence for r in results]
        assert confidences == sorted(confidences, reverse=True)


class TestHelperFunctions:
    """Test internal helpers with mock config."""

    def test_get_team_member_names(self, mock_config):
        from slack.slack_mention_classifier import _get_team_member_names

        names = _get_team_member_names()
        assert "alice" in names
        assert "bob" in names

    def test_get_user_name(self, mock_config):
        from slack.slack_mention_classifier import _get_user_name

        name = _get_user_name()
        assert name == "Test"

    def test_get_bot_name(self, mock_config):
        from slack.slack_mention_classifier import _get_bot_name

        assert _get_bot_name() == "test-bot"

    def test_owner_task_patterns_use_config_name(self, mock_config):
        from slack.slack_mention_classifier import _get_owner_task_patterns

        patterns = _get_owner_task_patterns()
        assert len(patterns) > 0
        # All patterns should reference "test" (user first name), not hardcoded names
        for p in patterns:
            assert "test" in p.lower() or "Test" in p

    def test_detect_priority(self):
        from slack.slack_mention_classifier import _detect_priority

        assert _detect_priority("this is urgent") == "high"
        assert _detect_priority("no rush on this") == "low"
        assert _detect_priority("please review") == "medium"

    def test_extract_task_description_removes_bot_mention(self, mock_config):
        from slack.slack_mention_classifier import _extract_task_description

        text = "@test-bot please review the PRD"
        result = _extract_task_description(text)
        assert "test-bot" not in result.lower()
        assert "review" in result.lower()
