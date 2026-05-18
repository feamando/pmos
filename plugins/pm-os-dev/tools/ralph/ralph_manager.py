"""
PM-OS Dev RalphManager (v5.0)

Multi-iteration feature development manager. Implements the "Ralph"
technique: one acceptance criterion at a time across multiple context windows.

Usage:
    from pm_os_dev.tools.ralph.ralph_manager import RalphManager

CLI:
    python3 ralph_manager.py init <feature> --title "Feature Title"
    python3 ralph_manager.py status <feature>
    python3 ralph_manager.py iteration <feature> --summary "What was done"
    python3 ralph_manager.py list
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        from core.path_resolver import get_paths
    except ImportError:
        get_paths = None

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from core.config_loader import get_config
    except ImportError:
        get_config = None


def _get_ralph_dir() -> Path:
    """Get ralph data directory from config or fallback."""
    if get_paths is not None:
        try:
            paths = get_paths()
            ralph_dir = paths.user / "data" / "ralph"
            ralph_dir.mkdir(parents=True, exist_ok=True)
            return ralph_dir
        except Exception:
            pass
    # Fallback: relative to script
    ralph_dir = Path(__file__).parent.parent.parent.parent.parent.parent / "user" / "data" / "ralph"
    ralph_dir.mkdir(parents=True, exist_ok=True)
    return ralph_dir


def sanitize_name(name: str) -> str:
    """Convert name to valid directory name."""
    sanitized = re.sub(r"[^a-z0-9-]", "-", name.lower())
    sanitized = re.sub(r"-+", "-", sanitized)
    return sanitized.strip("-")


class RalphManager:
    """Manages Ralph feature iterations."""

    def __init__(self, ralph_dir: Optional[Path] = None):
        self.ralph_dir = ralph_dir or _get_ralph_dir()
        self.state = self._load_state()

    def _state_file(self) -> Path:
        return self.ralph_dir / ".ralph-state.json"

    def _load_state(self) -> Dict[str, Any]:
        """Load global state."""
        state_file = self._state_file()
        if state_file.exists():
            try:
                return json.loads(state_file.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"features": {}, "last_updated": None}

    def _save_state(self):
        """Save global state."""
        self.state["last_updated"] = datetime.now().isoformat()
        self._state_file().write_text(json.dumps(self.state, indent=2))

    def init_feature(
        self,
        feature: str,
        title: Optional[str] = None,
        acceptance_criteria: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Initialize a new feature."""
        feature = sanitize_name(feature)
        feature_path = self.ralph_dir / feature

        if feature_path.exists():
            return {"success": False, "error": f"Feature '{feature}' already exists"}

        # Create directories
        feature_path.mkdir(parents=True)
        (feature_path / "logs").mkdir()

        title = title or feature.replace("-", " ").title()
        now = datetime.now()
        criteria = acceptance_criteria or ["Define acceptance criteria"]

        # Create PLAN.md
        criteria_md = "\n".join([f"- [ ] {c}" for c in criteria])
        plan_content = f"""# Plan: {title}

**Feature**: {feature}
**Created**: {now.strftime('%Y-%m-%d %H:%M')}
**Status**: In Progress

## Description

{title}

## Acceptance Criteria

{criteria_md}

---
*Progress: 0/{len(criteria)} (0%) | Iteration: 0*
"""
        (feature_path / "PLAN.md").write_text(plan_content)

        # Create PROMPT.md
        prompt_content = f"""# Ralph Iteration Prompt: {feature}

## Your Task
Working on: **{title}**

## Instructions

1. **Orient**
   - Read `PLAN.md` to see progress
   - Find the FIRST unchecked `- [ ]` item

2. **Work on ONE item**
   - Complete that single criterion
   - Do not skip ahead

3. **After completing**
   - Mark item as `- [x]` in PLAN.md
   - Commit changes
   - Update progress line

4. **If ALL complete**
   - Add `## COMPLETED` at end

## Constraints
- ONE item per iteration
- Verify before marking complete
- Leave clean state
"""
        (feature_path / "PROMPT.md").write_text(prompt_content)

        # Update state
        self.state["features"][feature] = {
            "title": title,
            "created": now.isoformat(),
            "status": "in_progress",
            "iteration": 0,
            "progress": 0,
            "total_criteria": len(criteria),
        }
        self._save_state()

        return {
            "success": True,
            "feature": feature,
            "path": str(feature_path),
            "title": title,
        }

    def get_status(self, feature: str) -> Dict[str, Any]:
        """Get feature status."""
        feature = sanitize_name(feature)
        feature_path = self.ralph_dir / feature

        if not feature_path.exists():
            return {"success": False, "error": f"Feature '{feature}' not found"}

        plan_path = feature_path / "PLAN.md"
        if not plan_path.exists():
            return {"success": False, "error": "PLAN.md not found"}

        plan = plan_path.read_text()

        # Parse progress
        completed = len(re.findall(r"- \[x\]", plan))
        total = len(re.findall(r"- \[[ x]\]", plan))
        is_complete = "## COMPLETED" in plan

        # Get state info
        state_info = self.state["features"].get(feature, {})

        return {
            "success": True,
            "feature": feature,
            "title": state_info.get("title", feature),
            "status": "complete" if is_complete else "in_progress",
            "progress": completed,
            "total": total,
            "percent": int(completed / total * 100) if total > 0 else 0,
            "iteration": state_info.get("iteration", 0),
            "path": str(feature_path),
        }

    def record_iteration(
        self,
        feature: str,
        summary: str,
        files_changed: Optional[List[str]] = None,
        blockers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Record an iteration."""
        feature = sanitize_name(feature)
        feature_path = self.ralph_dir / feature

        if not feature_path.exists():
            return {"success": False, "error": f"Feature '{feature}' not found"}

        # Increment iteration
        state_info = self.state["features"].get(feature, {})
        iteration = state_info.get("iteration", 0) + 1

        # Create log
        now = datetime.now()
        files_list = "\n".join(
            ["- " + f for f in (files_changed or ["None recorded"])]
        )
        blockers_text = (
            "\n".join(["- " + b for b in blockers]) if blockers else "None"
        )
        log_content = f"""# Iteration {iteration}

**Date**: {now.strftime('%Y-%m-%d %H:%M')}
**Feature**: {feature}

## Summary

{summary}

## Files Changed

{files_list}

## Blockers

{blockers_text}
"""

        log_path = feature_path / "logs" / f"iteration-{iteration:03d}.md"
        log_path.write_text(log_content)

        # Update state
        if feature not in self.state["features"]:
            self.state["features"][feature] = {}
        self.state["features"][feature]["iteration"] = iteration
        self._save_state()

        # Update PLAN.md progress line
        plan_path = feature_path / "PLAN.md"
        plan = plan_path.read_text()
        completed = len(re.findall(r"- \[x\]", plan))
        total = len(re.findall(r"- \[[ x]\]", plan))
        pct = int(completed / total * 100) if total else 0
        progress_line = f"*Progress: {completed}/{total} ({pct}%) | Iteration: {iteration}*"
        plan = re.sub(r"\*Progress:.*\*", progress_line, plan)
        plan_path.write_text(plan)

        return {
            "success": True,
            "iteration": iteration,
            "log_path": str(log_path),
        }

    def list_features(self) -> List[Dict[str, Any]]:
        """List all features."""
        features = []
        for feature in self.state.get("features", {}):
            status = self.get_status(feature)
            if status["success"]:
                features.append(
                    {
                        "feature": feature,
                        "title": status["title"],
                        "status": status["status"],
                        "progress": f"{status['progress']}/{status['total']}",
                        "iteration": status["iteration"],
                    }
                )
        return features


# Singleton
_manager: Optional[RalphManager] = None


def get_ralph_manager() -> RalphManager:
    """Get ralph manager singleton."""
    global _manager
    if _manager is None:
        _manager = RalphManager()
    return _manager


def main():
    parser = argparse.ArgumentParser(description="Ralph Feature Manager")
    subparsers = parser.add_subparsers(dest="command")

    # init
    init_p = subparsers.add_parser("init", help="Initialize feature")
    init_p.add_argument("feature", help="Feature name")
    init_p.add_argument("--title", help="Feature title")
    init_p.add_argument("--criteria", nargs="+", help="Acceptance criteria")

    # status
    status_p = subparsers.add_parser("status", help="Get feature status")
    status_p.add_argument("feature", help="Feature name")

    # iteration
    iter_p = subparsers.add_parser("iteration", help="Record iteration")
    iter_p.add_argument("feature", help="Feature name")
    iter_p.add_argument("--summary", required=True, help="Iteration summary")
    iter_p.add_argument("--files", nargs="+", help="Files changed")
    iter_p.add_argument("--blockers", nargs="+", help="Blockers")

    # list
    subparsers.add_parser("list", help="List features")

    args = parser.parse_args()
    manager = get_ralph_manager()

    if args.command == "init":
        result = manager.init_feature(args.feature, args.title, args.criteria)
        if result["success"]:
            print(f"Initialized: {result['feature']}")
            print(f"Path: {result['path']}")
        else:
            print(f"Error: {result['error']}")

    elif args.command == "status":
        result = manager.get_status(args.feature)
        if result["success"]:
            print(f"Feature: {result['title']}")
            print(f"Status: {result['status']}")
            print(f"Progress: {result['progress']}/{result['total']} ({result['percent']}%)")
            print(f"Iteration: {result['iteration']}")
        else:
            print(f"Error: {result['error']}")

    elif args.command == "iteration":
        result = manager.record_iteration(
            args.feature, args.summary, args.files, args.blockers
        )
        if result["success"]:
            print(f"Recorded iteration {result['iteration']}")
            print(f"Log: {result['log_path']}")
        else:
            print(f"Error: {result['error']}")

    elif args.command == "list":
        features = manager.list_features()
        if features:
            print("Features:\n")
            for f in features:
                icon = "+" if f["status"] == "complete" else "o"
                print(f"  {icon} {f['feature']}: {f['title']}")
                print(f"    Progress: {f['progress']} | Iteration: {f['iteration']}\n")
        else:
            print("No features found.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
