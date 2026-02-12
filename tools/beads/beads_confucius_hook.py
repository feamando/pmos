#!/usr/bin/env python3
"""
Beads-Confucius Integration Hooks.

Provides event handlers that automatically log Beads activities to Confucius.
This module is used by the BeadsWrapper for automatic logging.

Usage:
    from beads.beads_confucius_hook import BeadsConfuciusHook

    hook = BeadsConfuciusHook()
    hook.on_issue_created("bd-a1b2", "task", "Add login form")
    hook.on_issue_closed("bd-a1b2", "completed", "All tests passing")

Author: PM-OS Team
Version: 1.0.0
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from session.confucius_agent import ConfuciusAgent

    CONFUCIUS_AVAILABLE = True
except ImportError:
    CONFUCIUS_AVAILABLE = False
    ConfuciusAgent = None


class BeadsConfuciusHook:
    """
    Event hooks for logging Beads activities to Confucius.

    All methods are safe to call even if Confucius is not available -
    they will silently succeed without logging.
    """

    def __init__(self, enabled: bool = True):
        """
        Initialize the hook.

        Args:
            enabled: Whether logging is enabled
        """
        self.enabled = enabled and CONFUCIUS_AVAILABLE
        self._confucius: Optional[ConfuciusAgent] = None

    @property
    def confucius(self) -> Optional[ConfuciusAgent]:
        """Lazy-load Confucius agent."""
        if self.enabled and self._confucius is None and ConfuciusAgent:
            self._confucius = ConfuciusAgent()
        return self._confucius

    def on_issue_created(
        self,
        issue_id: str,
        issue_type: str,
        title: str,
        priority: int = 1,
        parent: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Called when a new issue is created.

        Logs an action to Confucius.

        Args:
            issue_id: The created issue ID (e.g., "bd-a1b2")
            issue_type: Type of issue ("epic", "task", "subtask")
            title: Issue title
            priority: Priority level 0-3
            parent: Parent issue ID if applicable

        Returns:
            Confucius action record or None
        """
        if not self.confucius:
            return None

        parent_info = f" (under {parent})" if parent else ""
        text = f"Created {issue_type}: {title} [{issue_id}]{parent_info}"

        return self.confucius.capture_action(text=text, owner="beads")

    def on_issue_closed(
        self,
        issue_id: str,
        resolution: str,
        rationale: str,
        title: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Called when an issue is closed.

        Logs a decision to Confucius.

        Args:
            issue_id: The closed issue ID
            resolution: Resolution type ("completed", "wontfix", "duplicate")
            rationale: Reason for closing
            title: Issue title (optional, for better logging)

        Returns:
            Confucius decision record or None
        """
        if not self.confucius:
            return None

        title_info = f": {title}" if title else ""
        decision_title = f"Closed issue {issue_id}{title_info}"

        return self.confucius.capture_decision(
            title=decision_title,
            choice=resolution,
            rationale=rationale or "Work completed",
        )

    def on_issue_updated(
        self, issue_id: str, changes: Dict[str, Any], title: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Called when an issue is updated.

        Logs an observation to Confucius.

        Args:
            issue_id: The updated issue ID
            changes: Dict of field -> new_value for changed fields
            title: Issue title (optional)

        Returns:
            Confucius observation record or None
        """
        if not self.confucius:
            return None

        if not changes:
            return None

        changes_str = ", ".join(f"{k}={v}" for k, v in changes.items())
        title_info = f" ({title})" if title else ""
        text = f"Updated {issue_id}{title_info}: {changes_str}"

        return self.confucius.capture_observation(text=text, category="beads")

    def on_dependency_added(
        self, child_id: str, parent_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Called when a dependency is added between issues.

        Logs an observation to Confucius.

        Args:
            child_id: The dependent issue
            parent_id: The blocking issue

        Returns:
            Confucius observation record or None
        """
        if not self.confucius:
            return None

        text = f"Added dependency: {child_id} blocked by {parent_id}"

        return self.confucius.capture_observation(text=text, category="beads")

    def on_blocker_identified(
        self, issue_id: str, blocker_description: str, impact: str = "medium"
    ) -> Optional[Dict[str, Any]]:
        """
        Called when a blocker is identified for an issue.

        Logs a blocker to Confucius.

        Args:
            issue_id: The blocked issue ID
            blocker_description: Description of what's blocking
            impact: Impact level ("low", "medium", "high")

        Returns:
            Confucius blocker record or None
        """
        if not self.confucius:
            return None

        text = f"[{issue_id}] {blocker_description}"

        return self.confucius.capture_blocker(text=text, owner="beads", impact=impact)

    def on_epic_created(
        self, issue_id: str, title: str, fpf_triggered: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Special handler for epic creation.

        Logs both an action and an assumption about FPF planning.

        Args:
            issue_id: Epic issue ID
            title: Epic title
            fpf_triggered: Whether FPF was auto-triggered

        Returns:
            Confucius action record or None
        """
        if not self.confucius:
            return None

        # Log the creation
        action = self.confucius.capture_action(
            text=f"Created epic: {title} [{issue_id}]", owner="beads"
        )

        # Log assumption about planning
        if fpf_triggered:
            self.confucius.capture_assumption(
                text=f"Epic {issue_id} requires FPF planning for approach validation",
                source="beads-fpf-integration",
            )

        return action

    def get_beads_session_summary(self) -> Dict[str, Any]:
        """
        Get summary of Beads-related Confucius notes in current session.

        Returns:
            Summary dict with counts and recent items
        """
        if not self.confucius or not self.confucius.state:
            return {"available": False}

        notes = self.confucius.state.get("notes", {})

        # Filter for beads-related items
        beads_actions = [
            a
            for a in notes.get("actions", [])
            if a.get("owner") == "beads" or "beads" in a.get("text", "").lower()
        ]

        beads_observations = [
            o for o in notes.get("observations", []) if o.get("category") == "beads"
        ]

        beads_decisions = [
            d
            for d in notes.get("decisions", [])
            if "issue" in d.get("title", "").lower() or "bd-" in d.get("title", "")
        ]

        return {
            "available": True,
            "session_id": self.confucius.state.get("session_id"),
            "beads_actions": len(beads_actions),
            "beads_observations": len(beads_observations),
            "beads_decisions": len(beads_decisions),
            "recent_actions": beads_actions[-3:] if beads_actions else [],
            "recent_decisions": beads_decisions[-3:] if beads_decisions else [],
        }


# Singleton instance
_hook_instance: Optional[BeadsConfuciusHook] = None


def get_beads_confucius_hook() -> BeadsConfuciusHook:
    """Get the singleton hook instance."""
    global _hook_instance
    if _hook_instance is None:
        _hook_instance = BeadsConfuciusHook()
    return _hook_instance


if __name__ == "__main__":
    import json

    hook = BeadsConfuciusHook()
    summary = hook.get_beads_session_summary()
    print(json.dumps(summary, indent=2))
