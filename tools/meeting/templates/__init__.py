"""
Meeting Prep Templates Registry

Type-specific templates for meeting preparation documents.
Each template defines output structure, word limits, and prompt instructions.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base_template import MeetingTemplate

# Lazy imports to avoid circular dependencies
_templates = {}


def _load_templates():
    """Lazy load all templates."""
    global _templates
    if _templates:
        return _templates

    from .external import ExternalTemplate
    from .interview import InterviewTemplate
    from .large_meeting import LargeMeetingTemplate
    from .one_on_one import OneOnOneTemplate
    from .other import OtherTemplate
    from .planning import PlanningTemplate
    from .review import ReviewTemplate
    from .standup import StandupTemplate

    _templates = {
        "1on1": OneOnOneTemplate(),
        "standup": StandupTemplate(),
        "large_meeting": LargeMeetingTemplate(),
        "external": ExternalTemplate(),
        "interview": InterviewTemplate(),
        "review": ReviewTemplate(),
        "planning": PlanningTemplate(),
        "other": OtherTemplate(),
    }
    return _templates


def get_template(meeting_type: str) -> "MeetingTemplate":
    """
    Get the appropriate template for a meeting type.

    Args:
        meeting_type: One of '1on1', 'standup', 'large_meeting', 'external',
                     'interview', 'review', 'planning', 'other'

    Returns:
        MeetingTemplate instance for the given type
    """
    templates = _load_templates()
    return templates.get(meeting_type, templates["other"])


def list_templates() -> list:
    """List all available template types."""
    return list(_load_templates().keys())


__all__ = ["get_template", "list_templates"]
