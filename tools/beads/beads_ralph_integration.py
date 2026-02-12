#!/usr/bin/env python3
"""
Beads-Ralph Integration Bridge.

Synchronizes Beads issues with Ralph features:
- Epics can initialize Ralph features
- Ralph acceptance criteria map to Beads tasks
- Iteration completion closes corresponding tasks

Usage:
    from beads.beads_ralph_integration import BeadsRalphBridge

    bridge = BeadsRalphBridge()
    bridge.create_feature_from_epic("bd-a3f8")
    bridge.sync_ac_to_tasks("user-auth", "bd-a3f8")

Author: PM-OS Team
Version: 2.0.0
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Try to import dependencies
try:
    from ralph.ralph_manager import RalphManager

    RALPH_AVAILABLE = True
except ImportError:
    RALPH_AVAILABLE = False
    RalphManager = None

try:
    # Try developer tools location first
    dev_tools = Path(__file__).parent.parent.parent.parent / "developer" / "tools"
    if dev_tools.exists():
        sys.path.insert(0, str(dev_tools))
    from beads.beads_wrapper import BeadsWrapper

    BEADS_AVAILABLE = True
except ImportError:
    BEADS_AVAILABLE = False
    BeadsWrapper = None


class BeadsRalphBridge:
    """
    Bridge between Beads issues and Ralph features.

    Enables bidirectional synchronization:
    - Epic creation can auto-create Ralph features
    - Ralph AC completion can close Beads tasks
    - Progress is tracked across both systems
    """

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize the bridge.

        Args:
            project_root: Project root path. If None, auto-detected.
        """
        self.project_root = project_root or self._find_project_root()
        self.beads_dir = self.project_root / ".beads"
        self.links_dir = self.beads_dir / ".ralph_links"

        self._beads: Optional[BeadsWrapper] = None
        self._ralph: Optional[RalphManager] = None

    @property
    def beads(self) -> Optional[BeadsWrapper]:
        """Lazy-load BeadsWrapper."""
        if self._beads is None and BEADS_AVAILABLE and BeadsWrapper:
            self._beads = BeadsWrapper(self.project_root)
        return self._beads

    @property
    def ralph(self) -> Optional[RalphManager]:
        """Lazy-load RalphManager."""
        if self._ralph is None and RALPH_AVAILABLE and RalphManager:
            self._ralph = RalphManager()
        return self._ralph

    def _find_project_root(self) -> Path:
        """Find project root."""
        current = Path.cwd()
        while current != current.parent:
            if (current / ".beads").exists():
                return current
            if (current / ".git").exists():
                return current
            current = current.parent
        return Path.cwd()

    def create_feature_from_epic(
        self, epic_id: str, feature_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a Ralph feature from a Beads epic.

        Args:
            epic_id: Beads epic ID (e.g., "bd-a3f8")
            feature_name: Optional custom feature name

        Returns:
            Result dict with feature details
        """
        if not self.beads:
            return {"success": False, "error": "Beads not available"}

        if not self.ralph:
            return {"success": False, "error": "Ralph not available"}

        # Get epic details
        epic = self.beads.show(epic_id)
        if "error" in epic:
            return {"success": False, "error": f"Epic not found: {epic_id}"}

        title = epic.get("title", epic_id)
        description = epic.get("description", "")

        # Generate feature name if not provided
        if not feature_name:
            feature_name = self._sanitize_feature_name(title)

        # Initialize Ralph feature
        result = self.ralph.init_feature(feature=feature_name, title=title)

        if result.get("success"):
            # Create link between epic and feature
            self._create_link(epic_id, feature_name, result.get("path"))

            return {
                "success": True,
                "epic_id": epic_id,
                "feature_name": feature_name,
                "feature_path": result.get("path"),
                "message": f"Created Ralph feature '{feature_name}' from epic {epic_id}",
            }

        return {
            "success": False,
            "error": result.get("error", "Failed to create Ralph feature"),
        }

    def sync_ac_to_tasks(self, feature_name: str, epic_id: str) -> Dict[str, Any]:
        """
        Create Beads tasks from Ralph acceptance criteria.

        Reads PLAN.md for the feature and creates subtasks under the epic.

        Args:
            feature_name: Ralph feature name
            epic_id: Parent Beads epic ID

        Returns:
            Result dict with created tasks
        """
        if not self.beads:
            return {"success": False, "error": "Beads not available"}

        if not self.ralph:
            return {"success": False, "error": "Ralph not available"}

        # Get Ralph feature status to find PLAN.md
        status = self.ralph.get_status(feature_name)
        if not status.get("success"):
            return {"success": False, "error": f"Feature not found: {feature_name}"}

        plan_path = Path(status["path"]) / "PLAN.md"
        if not plan_path.exists():
            return {"success": False, "error": "PLAN.md not found"}

        # Extract acceptance criteria
        criteria = self._extract_acceptance_criteria(plan_path.read_text())

        if not criteria:
            return {
                "success": False,
                "error": "No acceptance criteria found in PLAN.md",
            }

        # Create Beads tasks for each criterion
        created_tasks = []
        for idx, criterion in enumerate(criteria, 1):
            # Truncate for title, keep full in description
            task_title = criterion[:100] if len(criterion) > 100 else criterion

            task = self.beads.create(
                title=task_title,
                issue_type="task",
                parent=epic_id,
                description=criterion if len(criterion) > 100 else "",
            )

            task_id = task.get("id") or task.get("issue", {}).get("id")
            if task_id:
                # Store AC index mapping
                self._store_ac_mapping(feature_name, idx, task_id)

                created_tasks.append(
                    {
                        "task_id": task_id,
                        "ac_index": idx,
                        "title": (
                            task_title[:50] + "..."
                            if len(task_title) > 50
                            else task_title
                        ),
                    }
                )

        return {
            "success": True,
            "feature_name": feature_name,
            "epic_id": epic_id,
            "tasks_created": len(created_tasks),
            "tasks": created_tasks,
        }

    def on_ralph_iteration_complete(
        self, feature_name: str, ac_index: int
    ) -> Dict[str, Any]:
        """
        Called when a Ralph iteration completes an acceptance criterion.

        Finds and closes the corresponding Beads task.

        Args:
            feature_name: Ralph feature name
            ac_index: Completed acceptance criterion index (1-based)

        Returns:
            Result dict
        """
        if not self.beads:
            return {"success": False, "error": "Beads not available"}

        # Find the task ID for this AC
        task_id = self._get_task_for_ac(feature_name, ac_index)

        if not task_id:
            return {
                "success": False,
                "error": f"No Beads task linked to AC #{ac_index} for {feature_name}",
            }

        # Close the task
        result = self.beads.close(
            task_id, rationale=f"Completed in Ralph iteration for {feature_name}"
        )

        if result.get("success"):
            return {
                "success": True,
                "task_id": task_id,
                "ac_index": ac_index,
                "feature_name": feature_name,
                "message": f"Closed task {task_id} for AC #{ac_index}",
            }

        return {"success": False, "error": result.get("error", "Failed to close task")}

    def on_feature_complete(self, feature_name: str) -> Dict[str, Any]:
        """
        Called when a Ralph feature is completed.

        Closes the linked epic and suggests FPF finalization.

        Args:
            feature_name: Completed feature name

        Returns:
            Result dict
        """
        if not self.beads:
            return {"success": False, "error": "Beads not available"}

        # Get linked epic
        epic_id = self._get_linked_epic(feature_name)

        if not epic_id:
            return {
                "success": False,
                "error": f"No epic linked to feature {feature_name}",
            }

        # Close the epic
        result = self.beads.close(
            epic_id,
            rationale=f"Ralph feature '{feature_name}' completed with all acceptance criteria met",
        )

        response = {
            "success": result.get("success", False),
            "epic_id": epic_id,
            "feature_name": feature_name,
        }

        if result.get("success"):
            response["message"] = f"Closed epic {epic_id}"
            response["suggestion"] = (
                "Consider running /q5-decide to create a DRR for this feature"
            )

        return response

    def get_sync_status(self, feature_name: str) -> Dict[str, Any]:
        """
        Get synchronization status between Ralph feature and Beads issues.

        Args:
            feature_name: Ralph feature name

        Returns:
            Status dict with counts and progress
        """
        status = {
            "feature_name": feature_name,
            "epic_id": None,
            "total_tasks": 0,
            "completed_tasks": 0,
            "ralph_progress": None,
        }

        # Get linked epic
        epic_id = self._get_linked_epic(feature_name)
        if epic_id:
            status["epic_id"] = epic_id

            # Count tasks
            if self.beads:
                tasks = self.beads.list_issues(parent=epic_id)
                status["total_tasks"] = len(tasks)
                status["completed_tasks"] = sum(
                    1 for t in tasks if t.get("status") == "closed"
                )

        # Get Ralph progress
        if self.ralph:
            ralph_status = self.ralph.get_status(feature_name)
            if ralph_status.get("success"):
                status["ralph_progress"] = {
                    "completed": ralph_status.get("completed", 0),
                    "total": ralph_status.get("total", 0),
                    "percentage": ralph_status.get("percentage", 0),
                }

        return status

    def generate_plan_from_beads(
        self,
        epic_id: str,
        feature_name: Optional[str] = None,
        output_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Generate a PLAN.md file from a Beads epic and its child tasks.

        This enables using /ralph-loop with Beads-defined work items.
        The epic's child tasks become acceptance criteria checkboxes.

        Args:
            epic_id: Beads epic ID (e.g., "bd-a3f8")
            feature_name: Optional custom feature name (defaults to sanitized title)
            output_path: Optional custom output path for PLAN.md

        Returns:
            Result dict with plan path and task mappings
        """
        if not self.beads:
            return {"success": False, "error": "Beads not available"}

        # Get epic details
        epic_result = self.beads.show(epic_id)
        if not epic_result.get("success"):
            return {"success": False, "error": f"Epic not found: {epic_id}"}

        epic = epic_result.get("issue", epic_result)
        title = epic.get("title", epic_id)
        description = epic.get("description", "")
        children = epic.get("children", [])

        # Generate feature name
        if not feature_name:
            feature_name = self._sanitize_feature_name(title)

        # Collect all tasks recursively
        tasks = self._collect_tasks_recursive(epic_id)

        if not tasks:
            return {
                "success": False,
                "error": f"No child tasks found for epic {epic_id}",
            }

        # Determine output path
        if output_path:
            plan_path = Path(output_path)
        elif self.ralph:
            # Use Ralph feature directory
            feature_path = self.ralph.ralph_dir / feature_name
            feature_path.mkdir(parents=True, exist_ok=True)
            (feature_path / "logs").mkdir(exist_ok=True)
            plan_path = feature_path / "PLAN.md"
        else:
            return {
                "success": False,
                "error": "Ralph not available and no output_path specified",
            }

        # Generate PLAN.md content
        now = datetime.now()
        checked = sum(1 for t in tasks if t["status"] == "closed")
        total = len(tasks)
        percentage = round((checked / total * 100) if total > 0 else 0, 1)

        # Build acceptance criteria from tasks
        criteria_lines = []
        ac_mappings = {}
        for idx, task in enumerate(tasks, 1):
            checkbox = "[x]" if task["status"] == "closed" else "[ ]"
            # Include task ID as comment for traceability
            criteria_lines.append(
                f"- {checkbox} {task['title']}  <!-- {task['id']} -->"
            )
            ac_mappings[str(idx)] = task["id"]

        criteria_md = "\n".join(criteria_lines)

        # Extract description summary (first paragraph)
        desc_summary = (
            description.split("\n\n")[0] if description else "No description."
        )

        plan_content = f"""# Plan: {title}

**Feature**: {feature_name}
**Epic**: {epic_id}
**Created**: {now.strftime('%Y-%m-%d %H:%M')}
**Status**: {'Completed' if checked == total else 'In Progress'}

## Description

{desc_summary}

## Acceptance Criteria

{criteria_md}

---
*Progress: {checked}/{total} ({percentage}%) | Iteration: 0 | Generated from Beads*
"""

        # Write PLAN.md
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(plan_content)

        # Create link and store mappings
        self._create_link(epic_id, feature_name, str(plan_path.parent))
        link_file = self.links_dir / f"{feature_name}.json"
        if link_file.exists():
            try:
                data = json.loads(link_file.read_text())
                data["ac_mappings"] = ac_mappings
                data["generated_from_beads"] = True
                link_file.write_text(json.dumps(data, indent=2))
            except Exception:
                pass

        return {
            "success": True,
            "epic_id": epic_id,
            "feature_name": feature_name,
            "plan_path": str(plan_path),
            "tasks_count": total,
            "completed_count": checked,
            "ac_mappings": ac_mappings,
            "message": f"Generated PLAN.md with {total} acceptance criteria from Beads epic {epic_id}",
        }

    def sync_completion_to_beads(
        self, feature_name: str, plan_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Sync PLAN.md checkbox completion state to Beads tasks.

        Reads PLAN.md, finds checked items, and closes corresponding Beads tasks.

        Args:
            feature_name: Ralph feature name
            plan_path: Optional path to PLAN.md (auto-detected from feature if not provided)

        Returns:
            Result dict with sync details
        """
        if not self.beads:
            return {"success": False, "error": "Beads not available"}

        # Get plan path
        if plan_path:
            plan_file = Path(plan_path)
        elif self.ralph:
            status = self.ralph.get_status(feature_name)
            if not status.get("success"):
                return {"success": False, "error": f"Feature not found: {feature_name}"}
            plan_file = Path(status["path"]) / "PLAN.md"
        else:
            return {
                "success": False,
                "error": "Ralph not available and no plan_path specified",
            }

        if not plan_file.exists():
            return {"success": False, "error": f"PLAN.md not found at {plan_file}"}

        plan_content = plan_file.read_text()

        # Get AC mappings
        link_file = self.links_dir / f"{feature_name}.json"
        if not link_file.exists():
            return {
                "success": False,
                "error": f"No link file found for feature {feature_name}",
            }

        try:
            link_data = json.loads(link_file.read_text())
            ac_mappings = link_data.get("ac_mappings", {})
        except Exception as e:
            return {"success": False, "error": f"Failed to read link file: {e}"}

        if not ac_mappings:
            return {
                "success": False,
                "error": "No AC mappings found - was PLAN.md generated from Beads?",
            }

        # Parse checkboxes with task ID comments
        # Format: - [x] Task title  <!-- bd-xxxx -->
        checked_pattern = re.compile(
            r"- \[x\] .+?<!--\s*(bd-[a-z0-9]+)\s*-->", re.IGNORECASE
        )
        checked_ids = set(
            match.group(1) for match in checked_pattern.finditer(plan_content)
        )

        # Also check by AC index position
        all_items = re.findall(
            r"- \[([ x])\] (.+?)(?:<!--\s*(bd-[a-z0-9]+)\s*-->)?$",
            plan_content,
            re.MULTILINE | re.IGNORECASE,
        )

        synced = []
        errors = []

        for idx, (checkbox, title, task_id_comment) in enumerate(all_items, 1):
            is_checked = checkbox.lower() == "x"
            if not is_checked:
                continue

            # Get task ID from comment or mapping
            task_id = task_id_comment if task_id_comment else ac_mappings.get(str(idx))

            if not task_id:
                continue

            # Check if already closed
            task_result = self.beads.show(task_id)
            if task_result.get("success"):
                task = task_result.get("issue", task_result)
                if task.get("status") == "closed":
                    continue  # Already closed

            # Close the task
            close_result = self.beads.close(
                task_id, rationale=f"Completed in Ralph iteration for {feature_name}"
            )

            if close_result.get("success"):
                synced.append({"task_id": task_id, "title": title[:50]})
            else:
                errors.append(
                    {"task_id": task_id, "error": close_result.get("error", "Unknown")}
                )

        return {
            "success": True,
            "feature_name": feature_name,
            "synced_count": len(synced),
            "synced_tasks": synced,
            "errors": errors if errors else None,
            "message": f"Synced {len(synced)} completed tasks to Beads",
        }

    def ensure_plan_exists(
        self, epic_id: str, feature_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ensure a PLAN.md exists for a Beads epic, creating it if needed.

        This is the main entry point for /ralph-loop with Beads issues.
        If PLAN.md exists and is linked, returns existing. Otherwise generates new.

        Args:
            epic_id: Beads epic ID
            feature_name: Optional custom feature name

        Returns:
            Result dict with plan details
        """
        if not self.beads:
            return {"success": False, "error": "Beads not available"}

        # Get epic details
        epic_result = self.beads.show(epic_id)
        if not epic_result.get("success"):
            return {"success": False, "error": f"Epic not found: {epic_id}"}

        epic = epic_result.get("issue", epic_result)
        title = epic.get("title", epic_id)

        if not feature_name:
            feature_name = self._sanitize_feature_name(title)

        # Check if Ralph feature already exists
        if self.ralph:
            status = self.ralph.get_status(feature_name)
            if status.get("success"):
                plan_path = Path(status["path"]) / "PLAN.md"
                if plan_path.exists():
                    # Verify it's linked to this epic
                    linked_epic = self._get_linked_epic(feature_name)
                    if linked_epic == epic_id:
                        return {
                            "success": True,
                            "exists": True,
                            "feature_name": feature_name,
                            "plan_path": str(plan_path),
                            "message": f"PLAN.md already exists for {epic_id}",
                        }

        # Generate new PLAN.md
        return self.generate_plan_from_beads(epic_id, feature_name)

    def _collect_tasks_recursive(
        self, parent_id: str, depth: int = 0, max_depth: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Recursively collect all tasks under a parent issue.

        Args:
            parent_id: Parent issue ID
            depth: Current recursion depth
            max_depth: Maximum recursion depth

        Returns:
            List of task dicts with id, title, status
        """
        if depth > max_depth or not self.beads:
            return []

        tasks = []

        # Get children
        parent_result = self.beads.show(parent_id)
        if not parent_result.get("success"):
            return tasks

        parent = parent_result.get("issue", parent_result)
        children = parent.get("children", [])

        for child_id in children:
            child_result = self.beads.show(child_id)
            if not child_result.get("success"):
                continue

            child = child_result.get("issue", child_result)
            issue_type = child.get("issue_type", "task")

            if issue_type in ("task", "subtask"):
                # Add as acceptance criterion
                tasks.append(
                    {
                        "id": child_id,
                        "title": child.get("title", child_id),
                        "status": child.get("status", "open"),
                        "priority": child.get("priority", 3),
                    }
                )
            else:
                # Recurse into nested structures (stories under epics)
                nested = self._collect_tasks_recursive(child_id, depth + 1, max_depth)
                tasks.extend(nested)

        # Sort by priority then by ID
        tasks.sort(key=lambda t: (t.get("priority", 3), t.get("id", "")))

        return tasks

    def _sanitize_feature_name(self, title: str) -> str:
        """Convert title to kebab-case feature name."""
        # Remove special characters, convert to lowercase
        name = re.sub(r"[^a-zA-Z0-9\s-]", "", title.lower())
        # Replace spaces with hyphens
        name = re.sub(r"\s+", "-", name)
        # Remove multiple hyphens
        name = re.sub(r"-+", "-", name)
        # Truncate and strip
        return name[:50].strip("-")

    def _extract_acceptance_criteria(self, plan_content: str) -> List[str]:
        """Extract acceptance criteria from PLAN.md content."""
        criteria = []
        # Match unchecked criteria: - [ ] text
        for match in re.finditer(r"- \[ \] (.+)", plan_content):
            criteria.append(match.group(1).strip())
        return criteria

    def _create_link(
        self, epic_id: str, feature_name: str, feature_path: Optional[str]
    ) -> None:
        """Create link between epic and Ralph feature."""
        self.links_dir.mkdir(parents=True, exist_ok=True)

        link_data = {
            "epic_id": epic_id,
            "feature_name": feature_name,
            "feature_path": feature_path,
            "created_at": datetime.now().isoformat(),
            "ac_mappings": {},
        }

        # Save by feature name for easy lookup
        link_file = self.links_dir / f"{feature_name}.json"
        link_file.write_text(json.dumps(link_data, indent=2))

        # Also save by epic ID
        epic_link_file = self.links_dir / f"epic-{epic_id}.json"
        epic_link_file.write_text(json.dumps({"feature_name": feature_name}, indent=2))

    def _get_linked_epic(self, feature_name: str) -> Optional[str]:
        """Get epic ID linked to a feature."""
        link_file = self.links_dir / f"{feature_name}.json"
        if link_file.exists():
            try:
                data = json.loads(link_file.read_text())
                return data.get("epic_id")
            except Exception:
                pass
        return None

    def _store_ac_mapping(self, feature_name: str, ac_index: int, task_id: str) -> None:
        """Store mapping between AC index and task ID."""
        link_file = self.links_dir / f"{feature_name}.json"
        if link_file.exists():
            try:
                data = json.loads(link_file.read_text())
                data.setdefault("ac_mappings", {})[str(ac_index)] = task_id
                link_file.write_text(json.dumps(data, indent=2))
            except Exception:
                pass

    def _get_task_for_ac(self, feature_name: str, ac_index: int) -> Optional[str]:
        """Get task ID for an acceptance criterion."""
        link_file = self.links_dir / f"{feature_name}.json"
        if link_file.exists():
            try:
                data = json.loads(link_file.read_text())
                return data.get("ac_mappings", {}).get(str(ac_index))
            except Exception:
                pass
        return None


# Singleton instance
_bridge_instance: Optional[BeadsRalphBridge] = None


def get_beads_ralph_bridge(project_root: Optional[Path] = None) -> BeadsRalphBridge:
    """Get the singleton bridge instance."""
    global _bridge_instance
    if _bridge_instance is None or project_root is not None:
        _bridge_instance = BeadsRalphBridge(project_root)
    return _bridge_instance


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Beads-Ralph Integration v2.0")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # status command
    status_parser = subparsers.add_parser("status", help="Get sync status for feature")
    status_parser.add_argument("feature", help="Feature name")

    # create-feature command
    create_parser = subparsers.add_parser(
        "create-feature", help="Create Ralph feature from epic"
    )
    create_parser.add_argument("epic_id", help="Beads epic ID (e.g., bd-a3f8)")
    create_parser.add_argument("--name", help="Custom feature name")

    # generate-plan command (NEW)
    gen_parser = subparsers.add_parser(
        "generate-plan", help="Generate PLAN.md from Beads epic"
    )
    gen_parser.add_argument("epic_id", help="Beads epic ID")
    gen_parser.add_argument("--name", help="Custom feature name")
    gen_parser.add_argument("--output", help="Custom output path for PLAN.md")

    # sync-completion command (NEW)
    sync_parser = subparsers.add_parser(
        "sync-completion", help="Sync PLAN.md completion to Beads"
    )
    sync_parser.add_argument("feature", help="Feature name")
    sync_parser.add_argument("--plan", help="Custom PLAN.md path")

    # ensure-plan command (NEW)
    ensure_parser = subparsers.add_parser(
        "ensure-plan", help="Ensure PLAN.md exists for epic"
    )
    ensure_parser.add_argument("epic_id", help="Beads epic ID")
    ensure_parser.add_argument("--name", help="Custom feature name")

    # Legacy sync-tasks command
    sync_tasks_parser = subparsers.add_parser(
        "sync-tasks", help="[Legacy] Sync Ralph AC to Beads tasks"
    )
    sync_tasks_parser.add_argument("feature", help="Feature name")
    sync_tasks_parser.add_argument("epic_id", help="Beads epic ID")

    args = parser.parse_args()
    bridge = BeadsRalphBridge()

    if args.command == "status":
        print(json.dumps(bridge.get_sync_status(args.feature), indent=2))

    elif args.command == "create-feature":
        print(
            json.dumps(
                bridge.create_feature_from_epic(args.epic_id, args.name), indent=2
            )
        )

    elif args.command == "generate-plan":
        output = Path(args.output) if args.output else None
        print(
            json.dumps(
                bridge.generate_plan_from_beads(args.epic_id, args.name, output),
                indent=2,
            )
        )

    elif args.command == "sync-completion":
        plan = Path(args.plan) if args.plan else None
        print(json.dumps(bridge.sync_completion_to_beads(args.feature, plan), indent=2))

    elif args.command == "ensure-plan":
        print(json.dumps(bridge.ensure_plan_exists(args.epic_id, args.name), indent=2))

    elif args.command == "sync-tasks":
        print(json.dumps(bridge.sync_ac_to_tasks(args.feature, args.epic_id), indent=2))

    else:
        parser.print_help()
