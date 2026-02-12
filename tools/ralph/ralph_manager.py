#!/usr/bin/env python3
"""
Ralph Manager - Long-running agent iteration management for PM-OS.

Implements the "Ralph Wiggum" technique for structured multi-context-window work.
Each feature has a PLAN.md with acceptance criteria, and iterations work through
one criterion at a time until complete.

Usage:
    python3 ralph_manager.py init <feature> [--title "..."]
    python3 ralph_manager.py status <feature>
    python3 ralph_manager.py list
    python3 ralph_manager.py iteration <feature> --summary "..." [--files "..."]
    python3 ralph_manager.py check-complete <feature>
    python3 ralph_manager.py post-slack <feature> --iteration N
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Configuration
RALPH_DIR = Path(__file__).parent.parent / "Sessions" / "Ralph"
TEMPLATES_DIR = Path(__file__).parent / "ralph" / "templates"
STATE_FILE = RALPH_DIR / ".ralph-state.json"

# Slack configuration (from environment)
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.environ.get("SLACK_POST_CHANNEL", "CXXXXXXXXXX")


def ensure_directories():
    """Ensure Ralph directories exist."""
    RALPH_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> Dict[str, Any]:
    """Load global Ralph state."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"features": {}, "last_updated": None}


def save_state(state: Dict[str, Any]):
    """Save global Ralph state."""
    state["last_updated"] = datetime.now().isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_feature_path(feature: str) -> Path:
    """Get path to feature directory."""
    return RALPH_DIR / feature


def sanitize_feature_name(name: str) -> str:
    """Convert feature name to valid directory name."""
    # Convert to lowercase, replace spaces with hyphens
    sanitized = re.sub(r"[^a-z0-9-]", "-", name.lower())
    # Remove multiple consecutive hyphens
    sanitized = re.sub(r"-+", "-", sanitized)
    # Remove leading/trailing hyphens
    return sanitized.strip("-")


class RalphManager:
    """Manages Ralph feature iterations."""

    def __init__(self):
        ensure_directories()
        self.state = load_state()

    def init_feature(
        self, feature: str, title: str = None, brain_context: str = None
    ) -> Dict[str, Any]:
        """Initialize a new Ralph feature."""
        feature = sanitize_feature_name(feature)
        feature_path = get_feature_path(feature)

        if feature_path.exists():
            return {
                "success": False,
                "error": f"Feature '{feature}' already exists at {feature_path}",
            }

        # Create directory structure
        feature_path.mkdir(parents=True)
        (feature_path / "specs").mkdir()
        (feature_path / "logs").mkdir()

        title = title or feature.replace("-", " ").title()
        now = datetime.now()

        # Create PROMPT.md
        brain_path = brain_context or "user/brain/"
        prompt_content = f"""# Ralph Iteration Prompt: {feature}

## Context Training
Read these files to understand the codebase:
- {brain_path}
- AI_Guidance/Rules/NGO.md
- AI_Guidance/Core_Context/ (latest context file)

## Your Task
You are working on: **{title}**

Feature directory: `AI_Guidance/Sessions/Ralph/{feature}/`

## Instructions

1. **Orient yourself**
   - Run `pwd` to confirm working directory
   - Read `PLAN.md` in the feature directory to see progress
   - Find the FIRST unchecked `- [ ]` item

2. **Work on ONE item only**
   - Focus entirely on completing that single acceptance criterion
   - Do not skip ahead or work on multiple items
   - Take the time needed to do it properly

3. **After completing work**
   - Test/verify the work is actually complete
   - Commit to git with descriptive message
   - Mark the item as `- [x]` in PLAN.md
   - Update the progress line at the bottom of PLAN.md

4. **If ALL items complete**
   - Add `## COMPLETED` marker at the end of PLAN.md
   - Write final summary in the last iteration log

5. **Leave clean state**
   - No half-implemented features
   - No broken tests
   - Clear git history

## Constraints

- Do NOT remove or modify existing acceptance criteria text
- Do NOT mark items complete without actual verification
- Do NOT work on multiple items in one iteration
- Do NOT declare completion prematurely

## Iteration Logging

After each iteration, the loop will automatically log your work to:
`logs/iteration-NNN.md`

Include in your final message:
- Summary of what was completed
- Files created/modified
- Any blockers encountered
"""
        (feature_path / "PROMPT.md").write_text(prompt_content)

        # Create PLAN.md (placeholder - specs command will fill it)
        plan_content = f"""# Plan: {title}

**Feature**: {feature}
**Created**: {now.strftime('%Y-%m-%d %H:%M')}
**Status**: Initializing

## Description

*Run `/ralph-specs {feature}` to generate acceptance criteria*

## Acceptance Criteria

<!-- Criteria will be generated by /ralph-specs -->

---
*Progress: 0/0 (0%) | Iteration: 0*
"""
        (feature_path / "PLAN.md").write_text(plan_content)

        # Update state
        self.state["features"][feature] = {
            "title": title,
            "created": now.isoformat(),
            "status": "initializing",
            "iteration": 0,
            "progress": 0,
            "total_criteria": 0,
        }
        save_state(self.state)

        return {
            "success": True,
            "feature": feature,
            "path": str(feature_path),
            "title": title,
            "next_step": f"Run /ralph-specs {feature} to create acceptance criteria",
        }

    def get_status(self, feature: str) -> Dict[str, Any]:
        """Get status of a Ralph feature."""
        feature = sanitize_feature_name(feature)
        feature_path = get_feature_path(feature)

        if not feature_path.exists():
            return {"success": False, "error": f"Feature '{feature}' not found"}

        plan_path = feature_path / "PLAN.md"
        if not plan_path.exists():
            return {"success": False, "error": "PLAN.md not found"}

        plan_content = plan_path.read_text()

        # Parse checkboxes
        checked = len(re.findall(r"- \[x\]", plan_content, re.IGNORECASE))
        unchecked = len(re.findall(r"- \[ \]", plan_content))
        total = checked + unchecked

        # Check for completion marker
        is_complete = "## COMPLETED" in plan_content

        # Get current item being worked on
        current_item = None
        unchecked_match = re.search(r"- \[ \] (.+)", plan_content)
        if unchecked_match:
            current_item = unchecked_match.group(1).strip()

        # Count iterations
        log_files = list((feature_path / "logs").glob("iteration-*.md"))
        iteration_count = len(log_files)

        # Get feature metadata from state
        feature_state = self.state.get("features", {}).get(feature, {})

        progress_pct = round((checked / total * 100) if total > 0 else 0, 1)

        return {
            "success": True,
            "feature": feature,
            "title": feature_state.get("title", feature),
            "status": "completed" if is_complete else "in_progress",
            "progress": {
                "checked": checked,
                "total": total,
                "percentage": progress_pct,
            },
            "current_item": current_item,
            "iteration": iteration_count,
            "is_complete": is_complete,
            "path": str(feature_path),
        }

    def list_features(self) -> List[Dict[str, Any]]:
        """List all Ralph features."""
        features = []

        if not RALPH_DIR.exists():
            return features

        for feature_dir in RALPH_DIR.iterdir():
            if feature_dir.is_dir() and not feature_dir.name.startswith("."):
                status = self.get_status(feature_dir.name)
                if status.get("success"):
                    features.append(
                        {
                            "feature": feature_dir.name,
                            "title": status.get("title", ""),
                            "status": status.get("status", "unknown"),
                            "progress": status.get("progress", {}),
                            "iteration": status.get("iteration", 0),
                        }
                    )

        return sorted(features, key=lambda x: x.get("feature", ""))

    def record_iteration(
        self,
        feature: str,
        summary: str,
        files_changed: List[str] = None,
        commit_hash: str = None,
        commit_message: str = None,
        blockers: str = None,
    ) -> Dict[str, Any]:
        """Record an iteration completion."""
        feature = sanitize_feature_name(feature)
        feature_path = get_feature_path(feature)

        if not feature_path.exists():
            return {"success": False, "error": f"Feature '{feature}' not found"}

        logs_dir = feature_path / "logs"
        logs_dir.mkdir(exist_ok=True)

        # Find next iteration number
        existing = list(logs_dir.glob("iteration-*.md"))
        next_num = len(existing) + 1

        # Get current status for next item
        status = self.get_status(feature)
        next_item = status.get("current_item", "N/A")

        now = datetime.now()

        # Create iteration log
        log_content = f"""# Iteration {next_num} - {now.strftime('%Y-%m-%d %H:%M')}

## Work Completed
{summary}

## Files Changed
{chr(10).join(['- ' + f for f in (files_changed or ['None recorded'])]) }

## Git Commit
{f'{commit_hash}: {commit_message}' if commit_hash else 'No commit recorded'}

## Progress
- Checked: {status['progress']['checked']}/{status['progress']['total']}
- Percentage: {status['progress']['percentage']}%

## Next Item
{next_item or 'All items complete!'}

## Blockers
{blockers or 'None'}

---
*Recorded: {now.isoformat()}*
"""

        log_path = logs_dir / f"iteration-{next_num:03d}.md"
        log_path.write_text(log_content)

        # Update state
        if feature in self.state.get("features", {}):
            self.state["features"][feature]["iteration"] = next_num
            self.state["features"][feature]["progress"] = status["progress"][
                "percentage"
            ]
            self.state["features"][feature]["total_criteria"] = status["progress"][
                "total"
            ]
            save_state(self.state)

        return {
            "success": True,
            "iteration": next_num,
            "log_path": str(log_path),
            "progress": status["progress"],
        }

    def check_complete(self, feature: str) -> Dict[str, Any]:
        """Check if a feature is complete."""
        status = self.get_status(feature)
        if not status.get("success"):
            return status

        return {
            "success": True,
            "is_complete": status.get("is_complete", False),
            "progress": status.get("progress", {}),
            "current_item": status.get("current_item"),
        }

    def post_to_slack(
        self, feature: str, iteration: int = None, custom_message: str = None
    ) -> Dict[str, Any]:
        """Post iteration status to Slack."""
        if not SLACK_BOT_TOKEN:
            return {"success": False, "error": "SLACK_BOT_TOKEN not configured"}

        try:
            from slack_sdk import WebClient

            client = WebClient(token=SLACK_BOT_TOKEN)
        except ImportError:
            return {"success": False, "error": "slack_sdk not installed"}

        status = self.get_status(feature)
        if not status.get("success"):
            return status

        progress = status.get("progress", {})

        if custom_message:
            message = custom_message
        else:
            status_emoji = (
                ":white_check_mark:" if status["is_complete"] else ":hourglass:"
            )
            message = f"""{status_emoji} *[Ralph] {status['title']}*
Feature: `{feature}` | Iteration: {status['iteration']} | Progress: {progress['checked']}/{progress['total']} ({progress['percentage']}%)
{f"Working on: {status['current_item'][:60]}..." if status.get('current_item') else "All criteria complete!"}"""

        try:
            response = client.chat_postMessage(
                channel=SLACK_CHANNEL, text=message, unfurl_links=False
            )
            return {"success": True, "channel": SLACK_CHANNEL, "ts": response["ts"]}
        except Exception as e:
            return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Ralph Manager for PM-OS")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize a new feature")
    init_parser.add_argument("feature", help="Feature name (will be sanitized)")
    init_parser.add_argument("--title", "-t", help="Human-readable title")
    init_parser.add_argument("--brain-context", "-b", help="Brain context path")

    # status command
    status_parser = subparsers.add_parser("status", help="Get feature status")
    status_parser.add_argument("feature", help="Feature name")

    # list command
    subparsers.add_parser("list", help="List all features")

    # iteration command
    iter_parser = subparsers.add_parser("iteration", help="Record iteration")
    iter_parser.add_argument("feature", help="Feature name")
    iter_parser.add_argument("--summary", "-s", required=True, help="Work summary")
    iter_parser.add_argument("--files", "-f", help="Files changed (comma-separated)")
    iter_parser.add_argument("--commit", "-c", help="Commit hash")
    iter_parser.add_argument("--message", "-m", help="Commit message")
    iter_parser.add_argument("--blockers", help="Any blockers encountered")

    # check-complete command
    check_parser = subparsers.add_parser("check-complete", help="Check if complete")
    check_parser.add_argument("feature", help="Feature name")

    # post-slack command
    slack_parser = subparsers.add_parser("post-slack", help="Post to Slack")
    slack_parser.add_argument("feature", help="Feature name")
    slack_parser.add_argument("--iteration", "-i", type=int, help="Iteration number")
    slack_parser.add_argument("--message", "-m", help="Custom message")

    args = parser.parse_args()

    manager = RalphManager()

    if args.command == "init":
        result = manager.init_feature(
            args.feature, title=args.title, brain_context=args.brain_context
        )
        if result["success"]:
            print(f"Initialized feature: {result['feature']}")
            print(f"Path: {result['path']}")
            print(f"Title: {result['title']}")
            print(f"\nNext step: {result['next_step']}")
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "status":
        result = manager.get_status(args.feature)
        if result["success"]:
            print(f"Feature: {result['feature']}")
            print(f"Title: {result['title']}")
            print(f"Status: {result['status']}")
            print(
                f"Progress: {result['progress']['checked']}/{result['progress']['total']} ({result['progress']['percentage']}%)"
            )
            print(f"Iteration: {result['iteration']}")
            if result.get("current_item"):
                print(f"Current: {result['current_item']}")
            print(f"Path: {result['path']}")
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "list":
        features = manager.list_features()
        if features:
            print("Ralph Features:\n")
            for f in features:
                status_icon = "✓" if f["status"] == "completed" else "○"
                progress = f.get("progress", {})
                print(f"  {status_icon} [{f['feature']}] {f['title']}")
                print(
                    f"    Progress: {progress.get('checked', 0)}/{progress.get('total', 0)} | Iteration: {f['iteration']}"
                )
                print()
        else:
            print("No Ralph features found.")

    elif args.command == "iteration":
        files = args.files.split(",") if args.files else None
        result = manager.record_iteration(
            args.feature,
            summary=args.summary,
            files_changed=files,
            commit_hash=args.commit,
            commit_message=args.message,
            blockers=args.blockers,
        )
        if result["success"]:
            print(f"Recorded iteration {result['iteration']}")
            print(f"Log: {result['log_path']}")
            print(
                f"Progress: {result['progress']['checked']}/{result['progress']['total']}"
            )
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "check-complete":
        result = manager.check_complete(args.feature)
        if result["success"]:
            if result["is_complete"]:
                print("COMPLETE")
                sys.exit(0)
            else:
                progress = result.get("progress", {})
                print(
                    f"IN_PROGRESS ({progress.get('checked', 0)}/{progress.get('total', 0)})"
                )
                if result.get("current_item"):
                    print(f"Next: {result['current_item']}")
                sys.exit(1)  # Non-zero to indicate not complete
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(2)

    elif args.command == "post-slack":
        result = manager.post_to_slack(
            args.feature, iteration=args.iteration, custom_message=args.message
        )
        if result["success"]:
            print(f"Posted to {result['channel']}")
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
