#!/usr/bin/env python3
"""
Action Registry — maps dotted action names to Python callables.

Actions are registered by name (e.g. "brain.enrich") and resolved at runtime.
Each action callable must accept (args: dict, context: dict) and return a dict
with keys: success (bool), message (str), data (dict).
"""

from typing import Any, Callable, Dict, List, Optional


ActionCallable = Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]


class ActionRegistry:
    """Registry mapping action names to callables."""

    def __init__(self):
        self._actions: Dict[str, ActionCallable] = {}

    def register(self, name: str, fn: ActionCallable) -> None:
        """Register an action callable by name."""
        self._actions[name] = fn

    def resolve(self, name: str) -> Optional[ActionCallable]:
        """Resolve an action name to its callable."""
        return self._actions.get(name)

    def list_actions(self) -> List[str]:
        """Return sorted list of registered action names."""
        return sorted(self._actions.keys())

    def has(self, name: str) -> bool:
        """Check if an action is registered."""
        return name in self._actions

    def __len__(self) -> int:
        return len(self._actions)
