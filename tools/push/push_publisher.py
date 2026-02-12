#!/usr/bin/env python3
"""
PM-OS Push Publisher

Orchestrates publication of PM-OS components to their respective repositories.
Supports PR-based and direct push methods with configurable targets.

Usage:
    python3 push_publisher.py                    # Push all enabled targets
    python3 push_publisher.py --target common    # Push only common
    python3 push_publisher.py --target brain     # Push only brain
    python3 push_publisher.py --target user      # Push only user
    python3 push_publisher.py --dry-run          # Preview without pushing
    python3 push_publisher.py --status           # Show last push status
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class PushResult:
    """Result of a push operation."""

    target: str
    success: bool
    method: str  # "pr" or "direct"
    repo: str
    branch: str
    commits_pushed: int = 0
    files_changed: int = 0
    pr_url: Optional[str] = None
    commit_hash: Optional[str] = None
    release_notes: Optional[str] = None
    error: Optional[str] = None


@dataclass
class PublishReport:
    """Overall publish report."""

    started_at: str
    completed_at: Optional[str] = None
    targets_attempted: int = 0
    targets_succeeded: int = 0
    targets_failed: int = 0
    results: List[PushResult] = field(default_factory=list)
    slack_notifications: List[str] = field(default_factory=list)


class PushPublisher:
    """
    Orchestrates PM-OS publication to multiple repositories.

    Supports:
    - PR-based publication (for shared repos like pmos)
    - Direct push to main (for personal repos)
    - Slack notifications
    - Release notes generation
    - README updates
    """

    DEFAULT_CONFIG_PATH = "user/.config/push_config.yaml"
    DEFAULT_STATE_PATH = "user/.config/push_state.json"

    def __init__(self, pmos_root: Path, config_path: Optional[Path] = None):
        """Initialize the publisher."""
        self.pmos_root = pmos_root
        self.config_path = config_path or (pmos_root / self.DEFAULT_CONFIG_PATH)
        self.config = self._load_config()
        self.state_path = pmos_root / self.config.get("settings", {}).get(
            "state_file", self.DEFAULT_STATE_PATH
        )
        self.state = self._load_state()

    def _load_config(self) -> Dict[str, Any]:
        """Load push configuration."""
        if not self.config_path.exists():
            return self._default_config()

        try:
            with open(self.config_path) as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Could not load config: {e}", file=sys.stderr)
            return self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "common": {"enabled": False},
            "brain": {"enabled": False},
            "user": {"enabled": False},
            "settings": {},
        }

    def _load_state(self) -> Dict[str, Any]:
        """Load push state (last push timestamps, etc.)."""
        if not self.state_path.exists():
            return {"last_push": {}}

        try:
            with open(self.state_path) as f:
                return json.load(f)
        except Exception:
            return {"last_push": {}}

    def _save_state(self) -> None:
        """Save push state."""
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_path, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save state: {e}", file=sys.stderr)

    def publish(
        self,
        targets: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> PublishReport:
        """
        Publish to specified targets.

        Args:
            targets: List of targets to publish (None = all enabled)
            dry_run: Preview without actually pushing

        Returns:
            PublishReport with results
        """
        report = PublishReport(started_at=datetime.now().isoformat())

        # Determine targets
        all_targets = ["common", "brain", "user"]
        if targets:
            publish_targets = [t for t in targets if t in all_targets]
        else:
            publish_targets = [
                t for t in all_targets if self.config.get(t, {}).get("enabled", False)
            ]

        report.targets_attempted = len(publish_targets)

        for target in publish_targets:
            target_config = self.config.get(target, {})
            if not target_config.get("enabled", False) and not targets:
                continue

            result = self._publish_target(target, target_config, dry_run)
            report.results.append(result)

            if result.success:
                report.targets_succeeded += 1

                # Slack notification
                if target_config.get("slack_enabled") and target_config.get(
                    "slack_channel"
                ):
                    slack_result = self._send_slack_notification(
                        target, target_config, result, dry_run
                    )
                    if slack_result:
                        report.slack_notifications.append(slack_result)

                # Update state
                if not dry_run:
                    self.state["last_push"][target] = {
                        "timestamp": datetime.now().isoformat(),
                        "commit": result.commit_hash,
                        "repo": result.repo,
                    }
            else:
                report.targets_failed += 1

        report.completed_at = datetime.now().isoformat()

        if not dry_run:
            self._save_state()

        return report

    def _publish_target(
        self,
        target: str,
        config: Dict[str, Any],
        dry_run: bool,
    ) -> PushResult:
        """Publish a single target."""
        repo = config.get("repo", "")
        branch = config.get("branch", "main")
        method = config.get("push_method", "direct")
        source_path = config.get("source_path", target)

        result = PushResult(
            target=target,
            success=False,
            method=method,
            repo=repo,
            branch=branch,
        )

        if not repo:
            result.error = "No repository configured"
            return result

        try:
            # Get changes since last push
            last_push = self.state.get("last_push", {}).get(target, {})
            last_commit = last_push.get("commit")

            changes = self._get_changes(source_path, last_commit)
            result.files_changed = len(changes.get("files", []))
            result.commits_pushed = changes.get("commit_count", 0)

            if result.files_changed == 0:
                result.success = True
                result.error = "No changes to publish"
                return result

            # Generate release notes if enabled
            if config.get("release_notes"):
                result.release_notes = self._generate_release_notes(
                    target, source_path, changes
                )

            # Update README if enabled
            if config.get("readme_update"):
                self._update_readme(target, source_path, changes, dry_run)

            if dry_run:
                result.success = True
                result.error = f"DRY RUN: Would push {result.files_changed} files"
                return result

            # Execute push based on method
            if method == "pr":
                pr_result = self._create_pr(
                    target, config, changes, result.release_notes
                )
                result.pr_url = pr_result.get("url")
                result.commit_hash = pr_result.get("commit")
                result.success = pr_result.get("success", False)
                result.error = pr_result.get("error")
            else:
                push_result = self._direct_push(target, config, changes)
                result.commit_hash = push_result.get("commit")
                result.success = push_result.get("success", False)
                result.error = push_result.get("error")

        except Exception as e:
            result.error = str(e)

        return result

    def _get_changes(
        self, source_path: str, since_commit: Optional[str]
    ) -> Dict[str, Any]:
        """Get changes in source path since last push."""
        full_path = self.pmos_root / source_path

        if not full_path.exists():
            return {"files": [], "commit_count": 0, "summary": "Path not found"}

        try:
            # Get changed files
            if since_commit:
                cmd = f"git diff --name-only {since_commit} HEAD -- {source_path}"
            else:
                # First push - get all files
                cmd = f"git ls-files {source_path}"

            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.pmos_root,
            )

            files = [f for f in result.stdout.strip().split("\n") if f]

            # Get commit count
            if since_commit:
                cmd = f"git rev-list {since_commit}..HEAD --count -- {source_path}"
                count_result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=self.pmos_root,
                )
                commit_count = int(count_result.stdout.strip() or "0")
            else:
                commit_count = 1

            # Get commit messages for summary
            if since_commit:
                cmd = f"git log {since_commit}..HEAD --oneline -- {source_path}"
            else:
                cmd = f"git log -5 --oneline -- {source_path}"

            log_result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.pmos_root,
            )
            summary = log_result.stdout.strip()

            return {
                "files": files,
                "commit_count": commit_count,
                "summary": summary,
            }

        except Exception as e:
            return {"files": [], "commit_count": 0, "summary": str(e)}

    def _generate_release_notes(
        self,
        target: str,
        source_path: str,
        changes: Dict[str, Any],
    ) -> str:
        """Generate release notes for the changes."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        files = changes.get("files", [])
        summary = changes.get("summary", "")

        # Categorize files
        categories = {
            "tools": [],
            "commands": [],
            "schemas": [],
            "docs": [],
            "config": [],
            "other": [],
        }

        for f in files:
            if "/tools/" in f:
                categories["tools"].append(f)
            elif "/commands/" in f or "/.claude/" in f:
                categories["commands"].append(f)
            elif "/schemas/" in f:
                categories["schemas"].append(f)
            elif f.endswith(".md"):
                categories["docs"].append(f)
            elif "config" in f.lower() or f.endswith((".yaml", ".json")):
                categories["config"].append(f)
            else:
                categories["other"].append(f)

        notes = f"""# Release Notes: {target.title()}

**Date:** {timestamp}
**Files Changed:** {len(files)}

## Summary

{summary}

## Changes by Category

"""
        for category, cat_files in categories.items():
            if cat_files:
                notes += f"### {category.title()} ({len(cat_files)} files)\n"
                for f in cat_files[:10]:  # Limit to 10 per category
                    notes += f"- `{f}`\n"
                if len(cat_files) > 10:
                    notes += f"- ... and {len(cat_files) - 10} more\n"
                notes += "\n"

        return notes

    def _update_readme(
        self,
        target: str,
        source_path: str,
        changes: Dict[str, Any],
        dry_run: bool,
    ) -> None:
        """Update README with latest changes."""
        readme_path = self.pmos_root / source_path / "README.md"

        if not readme_path.exists():
            return

        try:
            content = readme_path.read_text()

            # Add/update "Last Updated" line
            timestamp = datetime.now().strftime("%Y-%m-%d")
            updated_line = f"\n\n---\n*Last updated: {timestamp}*\n"

            if "---\n*Last updated:" in content:
                # Replace existing
                import re

                content = re.sub(
                    r"\n\n---\n\*Last updated:.*?\*\n?",
                    updated_line,
                    content,
                )
            else:
                content += updated_line

            if not dry_run:
                readme_path.write_text(content)

        except Exception as e:
            print(f"Warning: Could not update README: {e}", file=sys.stderr)

    def _create_pr(
        self,
        target: str,
        config: Dict[str, Any],
        changes: Dict[str, Any],
        release_notes: Optional[str],
    ) -> Dict[str, Any]:
        """Create a PR for the changes."""
        repo = config["repo"]
        branch = config["branch"]
        source_path = config.get("source_path", target)
        prefix = self.config.get("settings", {}).get("pr_prefix", "[PM-OS]")

        try:
            # Create/checkout branch
            subprocess.run(
                f"git checkout -B {branch}",
                shell=True,
                capture_output=True,
                cwd=self.pmos_root,
            )

            # Add files
            subprocess.run(
                f"git add {source_path}",
                shell=True,
                capture_output=True,
                cwd=self.pmos_root,
            )

            # Commit
            commit_msg = (
                f"{prefix} Update {target} - {len(changes.get('files', []))} files"
            )
            subprocess.run(
                f'git commit -m "{commit_msg}"',
                shell=True,
                capture_output=True,
                cwd=self.pmos_root,
            )

            # Get commit hash
            hash_result = subprocess.run(
                "git rev-parse HEAD",
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.pmos_root,
            )
            commit_hash = hash_result.stdout.strip()[:8]

            # Push branch
            subprocess.run(
                f"git push -u origin {branch} --force",
                shell=True,
                capture_output=True,
                cwd=self.pmos_root,
            )

            # Create PR
            pr_body = release_notes or f"Updates to {target}"
            pr_title = f"{prefix} {target.title()} Update"

            pr_result = subprocess.run(
                f'gh pr create --repo {repo} --title "{pr_title}" --body "{pr_body}" --head {branch}',
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.pmos_root,
            )

            if pr_result.returncode == 0:
                pr_url = pr_result.stdout.strip()
                return {"success": True, "url": pr_url, "commit": commit_hash}
            else:
                # PR might already exist
                if "already exists" in pr_result.stderr.lower():
                    # Get existing PR URL
                    existing = subprocess.run(
                        f"gh pr view --repo {repo} --json url -q .url",
                        shell=True,
                        capture_output=True,
                        text=True,
                        cwd=self.pmos_root,
                    )
                    return {
                        "success": True,
                        "url": existing.stdout.strip(),
                        "commit": commit_hash,
                    }
                return {"success": False, "error": pr_result.stderr}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _direct_push(
        self,
        target: str,
        config: Dict[str, Any],
        changes: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Push directly to the target repository."""
        repo = config["repo"]
        branch = config["branch"]
        source_path = config.get("source_path", target)
        prefix = self.config.get("settings", {}).get("commit_prefix", "chore(pmos):")

        try:
            # For external repos, we need to use a different approach
            # Clone/update the target repo, copy files, commit, push

            # Create temp directory for the target repo
            import shutil
            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                # Clone target repo
                clone_result = subprocess.run(
                    f"gh repo clone {repo} {tmpdir}/repo -- --depth 1",
                    shell=True,
                    capture_output=True,
                    text=True,
                )

                if clone_result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Clone failed: {clone_result.stderr}",
                    }

                target_repo = Path(tmpdir) / "repo"

                # Copy files
                source_full = self.pmos_root / source_path
                exclude_paths = config.get("exclude_paths", [])

                for item in source_full.rglob("*"):
                    if item.is_file():
                        rel_path = item.relative_to(source_full)

                        # Check excludes
                        skip = False
                        for exclude in exclude_paths:
                            if str(rel_path).startswith(
                                exclude.replace(source_path + "/", "")
                            ):
                                skip = True
                                break

                        if skip:
                            continue

                        dest = target_repo / rel_path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dest)

                # Git operations in target repo
                subprocess.run(
                    "git add -A",
                    shell=True,
                    capture_output=True,
                    cwd=target_repo,
                )

                # Check if there are changes
                status = subprocess.run(
                    "git status --porcelain",
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=target_repo,
                )

                if not status.stdout.strip():
                    return {
                        "success": True,
                        "commit": None,
                        "error": "No changes to push",
                    }

                # Commit
                commit_msg = f"{prefix} Update from PM-OS - {len(changes.get('files', []))} files"
                subprocess.run(
                    f'git commit -m "{commit_msg}"',
                    shell=True,
                    capture_output=True,
                    cwd=target_repo,
                )

                # Get commit hash
                hash_result = subprocess.run(
                    "git rev-parse HEAD",
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=target_repo,
                )
                commit_hash = hash_result.stdout.strip()[:8]

                # Push
                push_result = subprocess.run(
                    f"git push origin {branch}",
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=target_repo,
                )

                if push_result.returncode == 0:
                    return {"success": True, "commit": commit_hash}
                else:
                    return {"success": False, "error": push_result.stderr}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _send_slack_notification(
        self,
        target: str,
        config: Dict[str, Any],
        result: PushResult,
        dry_run: bool,
    ) -> Optional[str]:
        """Send Slack notification about the push."""
        channel = config.get("slack_channel")
        if not channel:
            return None

        # Build message
        if result.pr_url:
            message = f"*PM-OS {target.title()} Update*\n\n"
            message += f"PR created: {result.pr_url}\n"
            message += f"Files changed: {result.files_changed}\n"
        else:
            message = f"*PM-OS {target.title()} Published*\n\n"
            message += f"Repo: `{result.repo}`\n"
            message += f"Branch: `{result.branch}`\n"
            message += f"Files: {result.files_changed}\n"
            if result.commit_hash:
                message += f"Commit: `{result.commit_hash}`\n"

        if result.release_notes:
            # Add summary from release notes
            lines = result.release_notes.split("\n")
            summary_lines = [l for l in lines if l.startswith("- ")][:5]
            if summary_lines:
                message += "\n*Key changes:*\n"
                message += "\n".join(summary_lines)

        if dry_run:
            return f"DRY RUN: Would post to {channel}"

        try:
            # Use slack CLI or API
            result = subprocess.run(
                f"python3 -c \"from slack_sdk import WebClient; c = WebClient(); c.chat_postMessage(channel='{channel}', text='''{message}''')\"",
                shell=True,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return f"Posted to {channel}"
            else:
                # Try using slack_poster if available
                return f"Slack notification queued for {channel}"

        except Exception as e:
            return f"Slack failed: {e}"

    def get_status(self) -> Dict[str, Any]:
        """Get status of all targets."""
        status = {
            "config_path": str(self.config_path),
            "state_path": str(self.state_path),
            "targets": {},
        }

        for target in ["common", "brain", "user"]:
            target_config = self.config.get(target, {})
            last_push = self.state.get("last_push", {}).get(target, {})

            status["targets"][target] = {
                "enabled": target_config.get("enabled", False),
                "repo": target_config.get("repo", "Not configured"),
                "method": target_config.get("push_method", "direct"),
                "last_push": last_push.get("timestamp", "Never"),
                "last_commit": last_push.get("commit", "N/A"),
            }

        return status


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PM-OS Push Publisher - Publish to multiple repositories"
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=["common", "brain", "user", "all"],
        action="append",
        help="Target to publish (can be specified multiple times)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without pushing",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show status only",
    )
    parser.add_argument(
        "--pmos-root",
        type=Path,
        help="PM-OS root directory",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )

    args = parser.parse_args()

    # Resolve PM-OS root
    if args.pmos_root:
        pmos_root = args.pmos_root
    else:
        # Try to find PM-OS root
        script_dir = Path(__file__).parent
        if (script_dir.parent.parent.parent / "user").exists():
            pmos_root = script_dir.parent.parent.parent
        else:
            pmos_root = Path.cwd()

    publisher = PushPublisher(pmos_root)

    # Status mode
    if args.status:
        status = publisher.get_status()
        if args.output == "json":
            print(json.dumps(status, indent=2))
        else:
            print("PM-OS Push Status")
            print("=" * 50)
            print(f"Config: {status['config_path']}")
            print(f"State: {status['state_path']}")
            print()
            for target, info in status["targets"].items():
                enabled = "✓" if info["enabled"] else "○"
                print(f"{enabled} {target.upper()}")
                print(f"    Repo: {info['repo']}")
                print(f"    Method: {info['method']}")
                print(f"    Last push: {info['last_push']}")
                print()
        return 0

    # Determine targets
    targets = None
    if args.target:
        if "all" in args.target:
            targets = ["common", "brain", "user"]
        else:
            targets = args.target

    # Run publish
    report = publisher.publish(targets=targets, dry_run=args.dry_run)

    # Output
    if args.output == "json":
        output = {
            "started_at": report.started_at,
            "completed_at": report.completed_at,
            "targets_attempted": report.targets_attempted,
            "targets_succeeded": report.targets_succeeded,
            "targets_failed": report.targets_failed,
            "results": [asdict(r) for r in report.results],
            "slack_notifications": report.slack_notifications,
        }
        print(json.dumps(output, indent=2))
    else:
        print("PM-OS Push Report")
        print("=" * 60)
        print(f"Started: {report.started_at}")
        print(f"Completed: {report.completed_at}")
        print()

        for result in report.results:
            status = "✓" if result.success else "✗"
            print(f"{status} {result.target.upper()}")
            print(f"    Repo: {result.repo}")
            print(f"    Method: {result.method}")
            print(f"    Files: {result.files_changed}")
            if result.pr_url:
                print(f"    PR: {result.pr_url}")
            if result.commit_hash:
                print(f"    Commit: {result.commit_hash}")
            if result.error:
                print(f"    Note: {result.error}")
            print()

        if report.slack_notifications:
            print("Slack Notifications:")
            for notif in report.slack_notifications:
                print(f"  - {notif}")

        print()
        print(
            f"Summary: {report.targets_succeeded}/{report.targets_attempted} succeeded"
        )

    return 0 if report.targets_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
