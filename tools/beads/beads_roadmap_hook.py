#!/usr/bin/env python3
"""
Beads Roadmap Hook - Sync Beads status changes to Roadmap Inbox.

Hooks into Beads events to synchronize status changes with the Roadmap Inbox:
- When Beads item closes -> Roadmap status becomes DONE
- When Beads work starts -> Roadmap status becomes INPROGRESS

Usage:
    from beads.beads_roadmap_hook import BeadsRoadmapHook

    hook = BeadsRoadmapHook()
    hook.on_beads_closed("bd-a1b2")
    hook.on_beads_started("bd-a1b2")

Author: PM-OS Team
Version: 1.0.0
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Singleton instance
_instance = None


class BeadsRoadmapHook:
    """Hook for syncing Beads events to Roadmap Inbox."""

    def __init__(self, enabled: bool = True):
        """
        Initialize hook.

        Args:
            enabled: Whether hook is active
        """
        self.enabled = enabled
        self._sync = None

    @property
    def sync(self):
        """Lazy-load RoadmapBeadsSync."""
        if self._sync is None and self.enabled:
            try:
                # Add developer tools to path
                developer_root = self._find_developer_root()
                if developer_root:
                    sys.path.insert(0, str(developer_root / "tools"))
                    from roadmap.roadmap_beads_sync import RoadmapBeadsSync

                    self._sync = RoadmapBeadsSync()
            except ImportError:
                self._sync = None
        return self._sync

    def _find_developer_root(self) -> Optional[Path]:
        """Find developer root directory."""
        # Check environment
        if "PM_OS_DEVELOPER_ROOT" in os.environ:
            return Path(os.environ["PM_OS_DEVELOPER_ROOT"])

        # Look relative to this file
        current = Path(__file__).parent
        while current != current.parent:
            if (current / ".pm-os-developer").exists():
                return current
            if current.name == "common":
                dev_path = current.parent / "developer"
                if dev_path.exists():
                    return dev_path
            current = current.parent

        return None

    def on_beads_closed(
        self,
        issue_id: str,
        resolution: Optional[str] = None,
        rationale: Optional[str] = None,
    ) -> bool:
        """
        Handle Beads issue closure.

        Args:
            issue_id: Beads issue ID (bd-XXXX)
            resolution: Closure resolution (completed, wontfix, duplicate)
            rationale: Closure rationale

        Returns:
            True if roadmap was updated
        """
        if not self.enabled or not self.sync:
            return False

        return self.sync.on_beads_closed(issue_id)

    def on_beads_started(self, issue_id: str) -> bool:
        """
        Handle Beads issue work started.

        Args:
            issue_id: Beads issue ID (bd-XXXX)

        Returns:
            True if roadmap was updated
        """
        if not self.enabled or not self.sync:
            return False

        return self.sync.on_beads_started(issue_id)

    def on_beads_updated(self, issue_id: str, changes: Dict[str, Any]) -> bool:
        """
        Handle Beads issue update.

        Args:
            issue_id: Beads issue ID
            changes: Dict of changed fields

        Returns:
            True if roadmap was updated
        """
        if not self.enabled or not self.sync:
            return False

        # Check for status change
        if "status" in changes:
            new_status = changes["status"]
            if new_status in ["in_progress", "inprogress"]:
                return self.sync.on_beads_started(issue_id)
            elif new_status in ["closed", "completed", "done"]:
                return self.sync.on_beads_closed(issue_id)

        return False

    def get_linked_roadmap_id(self, beads_id: str) -> Optional[str]:
        """Get roadmap ID linked to Beads item."""
        if not self.sync:
            return None
        return self.sync.get_linked_roadmap_id(beads_id)

    def is_linked(self, beads_id: str) -> bool:
        """Check if Beads item is linked to roadmap."""
        return self.get_linked_roadmap_id(beads_id) is not None


def get_roadmap_hook() -> BeadsRoadmapHook:
    """Get singleton hook instance."""
    global _instance
    if _instance is None:
        _instance = BeadsRoadmapHook()
    return _instance


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Beads Roadmap Hook")
    parser.add_argument(
        "--check", metavar="BD_ID", help="Check if Beads ID is linked to roadmap"
    )
    parser.add_argument(
        "--close", metavar="BD_ID", help="Simulate close event for Beads ID"
    )

    args = parser.parse_args()
    hook = get_roadmap_hook()

    if args.check:
        ri_id = hook.get_linked_roadmap_id(args.check)
        if ri_id:
            print(f"{args.check} -> {ri_id}")
        else:
            print(f"{args.check} not linked to roadmap")

    elif args.close:
        result = hook.on_beads_closed(args.close)
        print(f"Roadmap updated: {result}")

    else:
        parser.print_help()
