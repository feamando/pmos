#!/usr/bin/env python3
"""
Beads-FPF Integration Hooks.

Provides automatic FPF (First Principles Framework) triggering when epics
are created in Beads. Links DRRs (Design Rationale Records) to issues.

Usage:
    from beads.beads_fpf_hook import BeadsFPFHook

    hook = BeadsFPFHook()
    hook.trigger_fpf_for_epic("bd-a3f8", "User Authentication System")
    hook.link_drr_to_issue("bd-a3f8", "DRR-2026-01-19-auth-approach")

Author: PM-OS Team
Version: 1.0.0
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class BeadsFPFHook:
    """
    Integration between Beads epics and FPF reasoning cycles.

    When an epic is created, this hook can:
    1. Create a trigger file for /q0-init
    2. Suggest an FPF question based on the epic title
    3. Link completed DRRs back to the issue
    """

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize the FPF hook.

        Args:
            project_root: Project root path. If None, auto-detected.
        """
        self.project_root = project_root or self._find_project_root()
        self.beads_dir = self.project_root / ".beads"
        self.fpf_trigger_file = self.beads_dir / ".fpf_trigger.json"

    def _find_project_root(self) -> Path:
        """Find project root by looking for .beads or .git."""
        current = Path.cwd()
        while current != current.parent:
            if (current / ".beads").exists():
                return current
            if (current / ".git").exists():
                return current
            current = current.parent
        return Path.cwd()

    def trigger_fpf_for_epic(
        self, issue_id: str, title: str, suggested_question: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an FPF trigger for a newly created epic.

        This writes a trigger file that slash commands can detect
        to prompt the user to run /q0-init.

        Args:
            issue_id: Epic issue ID (e.g., "bd-a3f8")
            title: Epic title
            suggested_question: Optional specific question for FPF

        Returns:
            Trigger context dict
        """
        if suggested_question is None:
            suggested_question = self._generate_fpf_question(title)

        trigger_context = {
            "trigger": "beads_epic_created",
            "issue_id": issue_id,
            "title": title,
            "suggested_question": suggested_question,
            "timestamp": datetime.now().isoformat(),
            "status": "pending",
            "fpf_phase": "q0-init",
        }

        try:
            self.beads_dir.mkdir(parents=True, exist_ok=True)
            self.fpf_trigger_file.write_text(json.dumps(trigger_context, indent=2))
            trigger_context["file_created"] = True
        except Exception as e:
            trigger_context["file_created"] = False
            trigger_context["error"] = str(e)

        return trigger_context

    def _generate_fpf_question(self, title: str) -> str:
        """
        Generate a suitable FPF question from an epic title.

        Args:
            title: Epic title

        Returns:
            Suggested FPF question
        """
        # Common patterns for generating questions
        title_lower = title.lower()

        if (
            "implement" in title_lower
            or "add" in title_lower
            or "create" in title_lower
        ):
            return f"What is the best architectural approach for: {title}?"
        elif "fix" in title_lower or "resolve" in title_lower:
            return f"What is the root cause and optimal solution for: {title}?"
        elif "improve" in title_lower or "optimize" in title_lower:
            return f"What improvements would have the highest impact for: {title}?"
        elif "migrate" in title_lower or "refactor" in title_lower:
            return f"What migration strategy minimizes risk for: {title}?"
        else:
            return f"What approach should we take for: {title}?"

    def check_pending_trigger(self) -> Optional[Dict[str, Any]]:
        """
        Check if there's a pending FPF trigger.

        Returns:
            Trigger context if pending, None otherwise
        """
        if not self.fpf_trigger_file.exists():
            return None

        try:
            context = json.loads(self.fpf_trigger_file.read_text())
            if context.get("status") == "pending":
                return context
        except Exception:
            pass

        return None

    def mark_trigger_processed(self, fpf_cycle_id: Optional[str] = None) -> bool:
        """
        Mark the current trigger as processed.

        Args:
            fpf_cycle_id: Optional FPF cycle ID to link

        Returns:
            True if successful
        """
        if not self.fpf_trigger_file.exists():
            return False

        try:
            context = json.loads(self.fpf_trigger_file.read_text())
            context["status"] = "processed"
            context["processed_at"] = datetime.now().isoformat()
            if fpf_cycle_id:
                context["fpf_cycle_id"] = fpf_cycle_id
            self.fpf_trigger_file.write_text(json.dumps(context, indent=2))
            return True
        except Exception:
            return False

    def clear_trigger(self) -> bool:
        """
        Remove the FPF trigger file.

        Returns:
            True if file was removed
        """
        if self.fpf_trigger_file.exists():
            self.fpf_trigger_file.unlink()
            return True
        return False

    def link_drr_to_issue(
        self, issue_id: str, drr_id: str, drr_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Link a DRR (Design Rationale Record) to a Beads issue.

        Creates a link file that can be used to navigate between
        the issue and its associated decision rationale.

        Args:
            issue_id: Beads issue ID
            drr_id: DRR identifier
            drr_path: Optional path to DRR file

        Returns:
            Link metadata dict
        """
        links_dir = self.beads_dir / ".fpf_links"
        links_dir.mkdir(parents=True, exist_ok=True)

        link_data = {
            "issue_id": issue_id,
            "drr_id": drr_id,
            "drr_path": drr_path,
            "linked_at": datetime.now().isoformat(),
        }

        link_file = links_dir / f"{issue_id}.json"

        try:
            # Append to existing links if present
            if link_file.exists():
                existing = json.loads(link_file.read_text())
                if isinstance(existing, list):
                    existing.append(link_data)
                else:
                    existing = [existing, link_data]
                link_file.write_text(json.dumps(existing, indent=2))
            else:
                link_file.write_text(json.dumps([link_data], indent=2))

            return {"success": True, "link_file": str(link_file), **link_data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_drrs_for_issue(self, issue_id: str) -> List[Dict[str, Any]]:
        """
        Get all DRRs linked to a specific issue.

        Args:
            issue_id: Beads issue ID

        Returns:
            List of DRR link records
        """
        link_file = self.beads_dir / ".fpf_links" / f"{issue_id}.json"

        if not link_file.exists():
            return []

        try:
            data = json.loads(link_file.read_text())
            return data if isinstance(data, list) else [data]
        except Exception:
            return []

    def get_fpf_status(self) -> Dict[str, Any]:
        """
        Get overall FPF integration status for the project.

        Returns:
            Status dict with trigger info and link counts
        """
        status = {
            "beads_initialized": self.beads_dir.exists(),
            "pending_trigger": None,
            "linked_issues": 0,
            "total_drr_links": 0,
        }

        # Check for pending trigger
        pending = self.check_pending_trigger()
        if pending:
            status["pending_trigger"] = {
                "issue_id": pending.get("issue_id"),
                "title": pending.get("title"),
                "suggested_question": pending.get("suggested_question"),
            }

        # Count linked issues
        links_dir = self.beads_dir / ".fpf_links"
        if links_dir.exists():
            link_files = list(links_dir.glob("*.json"))
            status["linked_issues"] = len(link_files)

            # Count total DRR links
            for link_file in link_files:
                try:
                    data = json.loads(link_file.read_text())
                    if isinstance(data, list):
                        status["total_drr_links"] += len(data)
                    else:
                        status["total_drr_links"] += 1
                except Exception:
                    pass

        return status


# Singleton instance
_hook_instance: Optional[BeadsFPFHook] = None


def get_beads_fpf_hook(project_root: Optional[Path] = None) -> BeadsFPFHook:
    """Get the singleton FPF hook instance."""
    global _hook_instance
    if _hook_instance is None or project_root is not None:
        _hook_instance = BeadsFPFHook(project_root)
    return _hook_instance


def trigger_fpf_for_epic(issue_id: str, title: str) -> Dict[str, Any]:
    """Convenience function to trigger FPF for an epic."""
    return get_beads_fpf_hook().trigger_fpf_for_epic(issue_id, title)


def link_drr_to_issue(
    issue_id: str, drr_id: str, drr_path: Optional[str] = None
) -> Dict[str, Any]:
    """Convenience function to link a DRR to an issue."""
    return get_beads_fpf_hook().link_drr_to_issue(issue_id, drr_id, drr_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Beads-FPF Integration")
    parser.add_argument("--status", action="store_true", help="Show FPF status")
    parser.add_argument(
        "--check-trigger", action="store_true", help="Check pending trigger"
    )
    parser.add_argument(
        "--clear-trigger", action="store_true", help="Clear pending trigger"
    )

    args = parser.parse_args()

    hook = BeadsFPFHook()

    if args.status:
        print(json.dumps(hook.get_fpf_status(), indent=2))
    elif args.check_trigger:
        trigger = hook.check_pending_trigger()
        if trigger:
            print(json.dumps(trigger, indent=2))
        else:
            print("No pending FPF trigger")
    elif args.clear_trigger:
        if hook.clear_trigger():
            print("Trigger cleared")
        else:
            print("No trigger to clear")
    else:
        parser.print_help()
