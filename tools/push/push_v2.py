#!/usr/bin/env python3
"""
PM-OS Push Publisher v2

A complete rewrite of the push publisher that works correctly when pm-os
is not a git repository. Uses clone-then-compare for change detection.

Key differences from v1:
- Does NOT rely on git commands in pm-os root
- Clones target repo, copies files, uses git status to detect changes
- Generates semantic release notes from Ralph PLAN.md completions
- Single automated flow with no manual steps

Usage:
    python3 push_v2.py                     # Push all enabled targets
    python3 push_v2.py --target common     # Push only common
    python3 push_v2.py --target user       # Push only user
    python3 push_v2.py --dry-run           # Preview without pushing
    python3 push_v2.py --status            # Show last push status
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml


@dataclass
class FileChange:
    """Represents a file change."""

    path: str
    change_type: str  # "added", "modified", "deleted"


@dataclass
class DocAuditResult:
    """Result of a documentation audit."""

    commands_total: int = 0
    commands_documented: int = 0
    tools_total: int = 0
    tools_documented: int = 0
    missing_docs: List[str] = field(default_factory=list)
    generated_docs: List[str] = field(default_factory=list)


@dataclass
class ConfluenceSyncResult:
    """Result of Confluence sync."""

    pages_synced: int = 0
    pages_failed: int = 0
    space: str = ""
    errors: List[str] = field(default_factory=list)


@dataclass
class PushResult:
    """Result of a push operation."""

    target: str
    success: bool
    method: str  # "pr" or "direct"
    repo: str
    branch: str
    files_added: int = 0
    files_modified: int = 0
    files_deleted: int = 0
    pr_url: Optional[str] = None
    commit_hash: Optional[str] = None
    release_notes: Optional[str] = None
    error: Optional[str] = None
    changes: List[FileChange] = field(default_factory=list)
    doc_audit: Optional[DocAuditResult] = None
    confluence_sync: Optional[ConfluenceSyncResult] = None

    @property
    def files_changed(self) -> int:
        return self.files_added + self.files_modified + self.files_deleted


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


def find_pmos_root() -> Path:
    """
    Find PM-OS root by looking for .pm-os-root marker.

    Search order:
    1. Current directory and ancestors
    2. Common locations (~pm-os, /Users/*/pm-os)
    3. Environment variable PM_OS_ROOT
    """
    # Check environment variable first
    if os.environ.get("PM_OS_ROOT"):
        root = Path(os.environ["PM_OS_ROOT"])
        if (root / ".pm-os-root").exists():
            return root

    # Search current directory and ancestors
    current = Path.cwd()
    while current != current.parent:
        if (current / ".pm-os-root").exists():
            return current
        current = current.parent

    # Check common locations
    common_locations = [
        Path.home() / "pm-os",
        Path("/Users/jane.smith/pm-os"),
    ]
    for path in common_locations:
        if path.exists() and (path / ".pm-os-root").exists():
            return path

    # Last resort: try script directory
    script_dir = Path(__file__).parent
    potential_root = script_dir.parent.parent.parent
    if (potential_root / ".pm-os-root").exists():
        return potential_root

    raise RuntimeError(
        "PM-OS root not found. Ensure .pm-os-root marker exists or set PM_OS_ROOT env var."
    )


class PushPublisherV2:
    """
    PM-OS Push Publisher v2.

    Uses clone-then-compare strategy:
    1. Clone target repo to temp directory
    2. Copy files from pm-os to clone
    3. Use git status to detect actual changes
    4. Generate release notes
    5. Commit and push
    """

    DEFAULT_CONFIG_PATH = "user/.config/push_config.yaml"
    DEFAULT_STATE_PATH = "user/.config/push_state.json"

    # Files/patterns to always exclude
    ALWAYS_EXCLUDE = {
        "__pycache__",
        "*.pyc",
        "*.pyo",
        ".pytest_cache",
        "*.egg-info",
        ".DS_Store",
        ".git",
        "*.log",
        ".env",
        ".secrets",
    }

    def __init__(self, pmos_root: Optional[Path] = None):
        """Initialize the publisher."""
        self.pmos_root = pmos_root or find_pmos_root()
        self.config_path = self.pmos_root / self.DEFAULT_CONFIG_PATH
        self.config = self._load_config()
        self.state_path = self.pmos_root / self.config.get("settings", {}).get(
            "state_file", self.DEFAULT_STATE_PATH
        )
        self.state = self._load_state()

    def _load_config(self) -> Dict[str, Any]:
        """Load push configuration."""
        if not self.config_path.exists():
            print(f"Warning: Config not found at {self.config_path}", file=sys.stderr)
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
        """Load push state."""
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

    def _should_exclude(self, path: Path, exclude_paths: List[str]) -> bool:
        """Check if a path should be excluded."""
        path_str = str(path)

        # Check always-exclude patterns
        for pattern in self.ALWAYS_EXCLUDE:
            if "*" in pattern:
                # Glob pattern
                import fnmatch

                if fnmatch.fnmatch(path.name, pattern):
                    return True
            else:
                # Exact match
                if pattern in path_str or path.name == pattern:
                    return True

        # Check configured exclude paths
        for exclude in exclude_paths:
            if path_str.startswith(exclude) or exclude in path_str:
                return True

        return False

    def publish(
        self,
        targets: Optional[List[str]] = None,
        dry_run: bool = False,
        skip_docs: bool = False,
        docs_only: bool = False,
    ) -> PublishReport:
        """
        Publish to specified targets.

        Args:
            targets: List of targets to publish (None = all enabled)
            dry_run: Preview without actually pushing
            skip_docs: Skip documentation audit and Confluence sync
            docs_only: Only run documentation (no git push)

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

        if not publish_targets:
            print("No targets to publish (none enabled or specified)")
            report.completed_at = datetime.now().isoformat()
            return report

        report.targets_attempted = len(publish_targets)

        for target in publish_targets:
            target_config = self.config.get(target, {})

            print(f"\n{'='*60}")
            print(f"Publishing: {target.upper()}")
            print(f"{'='*60}")

            result = self._publish_target(
                target, target_config, dry_run, skip_docs=skip_docs, docs_only=docs_only
            )
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
                if not dry_run and result.commit_hash:
                    self.state["last_push"][target] = {
                        "timestamp": datetime.now().isoformat(),
                        "commit": result.commit_hash,
                        "repo": result.repo,
                        "files_changed": result.files_changed,
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
        skip_docs: bool = False,
        docs_only: bool = False,
    ) -> PushResult:
        """Publish a single target using clone-then-compare."""
        repo = config.get("repo", "")
        branch = config.get("branch", "main")
        method = config.get("push_method", "direct")
        source_path = config.get("source_path", target)
        exclude_paths = config.get("exclude_paths", [])

        result = PushResult(
            target=target,
            success=False,
            method=method,
            repo=repo,
            branch=branch,
        )

        # Phase 0: Documentation (for common target only)
        if target == "common" and not skip_docs:
            print("\n--- Documentation Phase ---")

            # Run doc audit
            print("Running documentation audit...")
            audit_result = self.run_doc_audit(generate_missing=False)
            result.doc_audit = audit_result
            print(
                f"  Commands: {audit_result.commands_documented}/{audit_result.commands_total}"
            )
            print(
                f"  Tools: {audit_result.tools_documented}/{audit_result.tools_total}"
            )
            if audit_result.missing_docs:
                print(f"  Missing docs: {len(audit_result.missing_docs)}")

            # Confluence sync (if configured)
            doc_config = config.get("documentation", {})
            if doc_config.get("enabled", True):
                confluence_space = doc_config.get("confluence_space", "PMOS")
                sync_result = self.sync_confluence(
                    space=confluence_space, dry_run=dry_run
                )
                result.confluence_sync = sync_result

                # Update status file
                if not dry_run:
                    self.update_doc_status(audit_result, sync_result)

            print("--- End Documentation Phase ---\n")

            # If docs_only, we're done
            if docs_only:
                result.success = True
                result.error = "Documentation phase completed (docs_only mode)"
                return result

        if not repo:
            result.error = "No repository configured"
            return result

        source_full = self.pmos_root / source_path
        if not source_full.exists():
            result.error = f"Source path not found: {source_full}"
            return result

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)
                clone_path = tmpdir_path / "repo"

                # Step 1: Clone target repository
                # For PR method, clone from base_branch (main) to avoid conflicts
                clone_branch = (
                    config.get("base_branch", "main") if method == "pr" else branch
                )
                print(f"Cloning {repo}...")
                clone_result = subprocess.run(
                    [
                        "gh",
                        "repo",
                        "clone",
                        repo,
                        str(clone_path),
                        "--",
                        "--depth",
                        "1",
                        "-b",
                        clone_branch,
                    ],
                    capture_output=True,
                    text=True,
                )

                if clone_result.returncode != 0:
                    # Try without branch (might be new repo)
                    clone_result = subprocess.run(
                        [
                            "gh",
                            "repo",
                            "clone",
                            repo,
                            str(clone_path),
                            "--",
                            "--depth",
                            "1",
                        ],
                        capture_output=True,
                        text=True,
                    )
                    if clone_result.returncode != 0:
                        result.error = f"Clone failed: {clone_result.stderr}"
                        return result

                # Step 2: Copy files from source to clone
                print(f"Copying files from {source_path}...")
                files_copied = self._copy_files(
                    source_full,
                    clone_path,
                    exclude_paths,
                    source_path,
                )
                print(f"  Copied {files_copied} files")

                # Step 3: Detect changes using git status
                print("Detecting changes...")
                changes = self._detect_changes(clone_path)
                result.changes = changes
                result.files_added = len(
                    [c for c in changes if c.change_type == "added"]
                )
                result.files_modified = len(
                    [c for c in changes if c.change_type == "modified"]
                )
                result.files_deleted = len(
                    [c for c in changes if c.change_type == "deleted"]
                )

                print(f"  Added: {result.files_added}")
                print(f"  Modified: {result.files_modified}")
                print(f"  Deleted: {result.files_deleted}")

                if result.files_changed == 0:
                    result.success = True
                    result.error = "No changes to publish"
                    print("  No changes detected")
                    return result

                # Step 4: Generate release notes
                print("Generating release notes...")
                result.release_notes = self._generate_release_notes(target, changes)

                if dry_run:
                    result.success = True
                    result.error = f"DRY RUN: Would push {result.files_changed} files"
                    print(f"\n{result.error}")
                    print("\nChanges that would be pushed:")
                    for change in changes[:20]:
                        print(f"  [{change.change_type}] {change.path}")
                    if len(changes) > 20:
                        print(f"  ... and {len(changes) - 20} more")
                    return result

                # Step 5: Commit and push
                if method == "pr":
                    push_result = self._create_pr(
                        clone_path, target, config, changes, result.release_notes
                    )
                    result.pr_url = push_result.get("url")
                else:
                    push_result = self._direct_push(
                        clone_path, target, config, changes, result.release_notes
                    )

                result.commit_hash = push_result.get("commit")
                result.success = push_result.get("success", False)
                if not result.success:
                    result.error = push_result.get("error")

        except Exception as e:
            result.error = f"Exception: {str(e)}"
            import traceback

            traceback.print_exc()

        return result

    def _copy_files(
        self,
        source: Path,
        dest: Path,
        exclude_paths: List[str],
        source_path_prefix: str,
    ) -> int:
        """Copy files from source to destination, respecting excludes."""
        files_copied = 0

        for item in source.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(source)

                # Check excludes
                full_rel = f"{source_path_prefix}/{rel_path}"
                if self._should_exclude(rel_path, exclude_paths):
                    continue
                if self._should_exclude(Path(full_rel), exclude_paths):
                    continue

                dest_file = dest / rel_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest_file)
                files_copied += 1

        return files_copied

    def _detect_changes(self, repo_path: Path) -> List[FileChange]:
        """Detect changes in the cloned repo using git status."""
        changes = []

        # Stage all changes
        subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_path,
            capture_output=True,
        )

        # Get status
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            status = line[:2].strip()
            filepath = line[3:].strip()

            # Handle renamed files
            if " -> " in filepath:
                filepath = filepath.split(" -> ")[1]

            if status in ("A", "??"):
                change_type = "added"
            elif status == "D":
                change_type = "deleted"
            else:
                change_type = "modified"

            changes.append(FileChange(path=filepath, change_type=change_type))

        return changes

    def _generate_release_notes(
        self,
        target: str,
        changes: List[FileChange],
    ) -> str:
        """Generate semantic release notes."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Categorize changes
        categories = {
            "features": [],
            "fixes": [],
            "docs": [],
            "tools": [],
            "commands": [],
            "tests": [],
            "config": [],
            "other": [],
        }

        for change in changes:
            path = change.path.lower()
            if "test" in path:
                categories["tests"].append(change)
            elif path.endswith(".md") or "/docs/" in path or "/documentation/" in path:
                categories["docs"].append(change)
            elif "/tools/" in path:
                categories["tools"].append(change)
            elif "/commands/" in path or "/.claude/" in path:
                categories["commands"].append(change)
            elif "config" in path or path.endswith((".yaml", ".json")):
                categories["config"].append(change)
            else:
                categories["other"].append(change)

        # Try to extract semantic info from Ralph PLAN.md files
        ralph_completions = self._get_ralph_completions(target)

        # Build release notes
        notes = f"""## Release Notes: {target.title()}

**Date:** {timestamp}
**Files Changed:** {len(changes)} ({sum(1 for c in changes if c.change_type == 'added')} added, {sum(1 for c in changes if c.change_type == 'modified')} modified, {sum(1 for c in changes if c.change_type == 'deleted')} deleted)

"""

        if ralph_completions:
            notes += "### Recent Completions\n\n"
            for completion in ralph_completions[:10]:
                notes += f"- {completion}\n"
            notes += "\n"

        notes += "### Changes by Category\n\n"

        for category, cat_changes in categories.items():
            if cat_changes:
                notes += f"**{category.title()}** ({len(cat_changes)} files)\n"
                for c in cat_changes[:5]:
                    symbol = (
                        "+"
                        if c.change_type == "added"
                        else ("~" if c.change_type == "modified" else "-")
                    )
                    notes += f"- {symbol} `{c.path}`\n"
                if len(cat_changes) > 5:
                    notes += f"- ... and {len(cat_changes) - 5} more\n"
                notes += "\n"

        return notes

    def _get_ralph_completions(self, target: str) -> List[str]:
        """Extract recently completed items from Ralph PLAN.md files."""
        completions = []

        ralph_dir = self.pmos_root / "common" / "tools" / "Sessions" / "Ralph"
        if not ralph_dir.exists():
            return completions

        for plan_file in ralph_dir.glob("*/PLAN.md"):
            try:
                content = plan_file.read_text()
                # Extract checked items
                for line in content.split("\n"):
                    if line.strip().startswith("- [x]"):
                        item = line.strip()[6:].strip()
                        # Remove beads IDs
                        if "(bd-" in item:
                            item = item.split("(bd-")[0].strip()
                        completions.append(item)
            except Exception:
                pass

        return completions[-20:]  # Last 20 completions

    def _direct_push(
        self,
        repo_path: Path,
        target: str,
        config: Dict[str, Any],
        changes: List[FileChange],
        release_notes: str,
    ) -> Dict[str, Any]:
        """Push directly to the target repository."""
        branch = config.get("branch", "main")
        prefix = self.config.get("settings", {}).get("commit_prefix", "chore(pmos):")

        try:
            # Files are already staged from _detect_changes

            # Commit
            commit_msg = f"{prefix} Update {target} - {len(changes)} files changed"
            print(f"Committing: {commit_msg}")

            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )

            if commit_result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Commit failed: {commit_result.stderr}",
                }

            # Get commit hash
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            commit_hash = hash_result.stdout.strip()[:8]

            # Push
            print(f"Pushing to {branch}...")
            push_result = subprocess.run(
                ["git", "push", "origin", branch],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )

            if push_result.returncode != 0:
                return {"success": False, "error": f"Push failed: {push_result.stderr}"}

            print(f"Success! Commit: {commit_hash}")
            return {"success": True, "commit": commit_hash}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _create_pr(
        self,
        repo_path: Path,
        target: str,
        config: Dict[str, Any],
        changes: List[FileChange],
        release_notes: str,
    ) -> Dict[str, Any]:
        """Create a PR for the changes."""
        repo = config["repo"]
        branch = config.get("branch", "main")
        base_branch = config.get("base_branch", "main")
        prefix = self.config.get("settings", {}).get("pr_prefix", "[PM-OS]")

        try:
            # Create feature branch (use configured branch as base name for Jira ticket reference)
            configured_branch = config.get("branch", "main")
            if configured_branch != "main":
                feature_branch = (
                    f"{configured_branch}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                )
            else:
                feature_branch = (
                    f"pmos-update-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                )
            subprocess.run(
                ["git", "checkout", "-b", feature_branch],
                cwd=repo_path,
                capture_output=True,
            )

            # Commit
            commit_msg = f"{prefix} Update {target} - {len(changes)} files changed"
            print(f"Committing: {commit_msg}")

            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=repo_path,
                capture_output=True,
            )

            # Get commit hash
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            commit_hash = hash_result.stdout.strip()[:8]

            # Push branch
            print(f"Pushing branch {feature_branch}...")
            subprocess.run(
                ["git", "push", "-u", "origin", feature_branch],
                cwd=repo_path,
                capture_output=True,
            )

            # Create PR (extract Jira ticket from branch for title)
            import re as _re

            ticket_match = _re.search(r"[A-Z][A-Z0-9]+-\d+", feature_branch)
            ticket_prefix = f"{ticket_match.group(0)}: " if ticket_match else ""
            pr_title = f"{ticket_prefix}{prefix} {target.title()} Update - {len(changes)} files"
            print(f"Creating PR: {pr_title}")

            pr_result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "create",
                    "--repo",
                    repo,
                    "--title",
                    pr_title,
                    "--body",
                    release_notes,
                    "--base",
                    base_branch,
                    "--head",
                    feature_branch,
                ],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )

            if pr_result.returncode == 0:
                pr_url = pr_result.stdout.strip()
                print(f"PR created: {pr_url}")
                return {"success": True, "url": pr_url, "commit": commit_hash}
            else:
                # Check if PR already exists
                if "already exists" in pr_result.stderr.lower():
                    existing = subprocess.run(
                        [
                            "gh",
                            "pr",
                            "view",
                            "--repo",
                            repo,
                            "--json",
                            "url",
                            "-q",
                            ".url",
                        ],
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                    )
                    return {
                        "success": True,
                        "url": existing.stdout.strip(),
                        "commit": commit_hash,
                    }
                return {"success": False, "error": pr_result.stderr}

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
            message += f"PR: {result.pr_url}\n"
        else:
            message = f"*PM-OS {target.title()} Published*\n\n"
            message += f"Repo: `{result.repo}`\n"
            if result.commit_hash:
                message += f"Commit: `{result.commit_hash}`\n"

        message += f"Files: +{result.files_added} ~{result.files_modified} -{result.files_deleted}\n"

        if dry_run:
            return f"DRY RUN: Would post to {channel}"

        # Try to post using slack_poster tool
        slack_poster = self.pmos_root / "common" / "tools" / "slack" / "slack_poster.py"
        if slack_poster.exists():
            try:
                subprocess.run(
                    [
                        "python3",
                        str(slack_poster),
                        "--channel",
                        channel,
                        "--message",
                        message,
                    ],
                    capture_output=True,
                )
                return f"Posted to {channel}"
            except Exception:
                pass

        return f"Slack notification queued for {channel}"

    def run_doc_audit(self, generate_missing: bool = True) -> DocAuditResult:
        """
        Audit documentation coverage for commands and tools.

        Args:
            generate_missing: If True, generate docs for missing items

        Returns:
            DocAuditResult with coverage stats
        """
        result = DocAuditResult()

        common_dir = self.pmos_root / "common"
        doc_dir = common_dir / "documentation"
        commands_dir = common_dir / ".claude" / "commands"
        tools_dir = common_dir / "tools"

        # Audit commands
        if commands_dir.exists():
            command_files = list(commands_dir.glob("*.md"))
            result.commands_total = len(command_files)

            # Check which have documentation
            doc_commands_dir = doc_dir / "commands"
            for cmd_file in command_files:
                cmd_name = cmd_file.stem
                # Look for corresponding doc
                doc_file = doc_commands_dir / f"{cmd_name}.md"
                if doc_file.exists():
                    result.commands_documented += 1
                else:
                    result.missing_docs.append(f"commands/{cmd_name}")

        # Audit tools (Python files with docstrings)
        if tools_dir.exists():
            tool_files = list(tools_dir.glob("**/*.py"))
            # Filter out __init__.py, test files, and __pycache__
            tool_files = [
                f
                for f in tool_files
                if not f.name.startswith("__")
                and not f.name.startswith("test_")
                and "__pycache__" not in str(f)
            ]
            result.tools_total = len(tool_files)

            doc_tools_dir = doc_dir / "tools"
            for tool_file in tool_files:
                # Get relative path from tools dir
                rel_path = tool_file.relative_to(tools_dir)
                tool_name = tool_file.stem

                # Check if documented (look in tools docs)
                doc_file = doc_tools_dir / f"{tool_name}.md"
                if doc_file.exists():
                    result.tools_documented += 1
                # Also check if it's in a category doc
                elif any(
                    tool_name in (doc_tools_dir / f).read_text()
                    for f in doc_tools_dir.glob("*.md")
                    if f.exists()
                ):
                    result.tools_documented += 1
                else:
                    # Only report as missing if it's a main tool (not helper)
                    if "_" not in tool_name or tool_name.endswith("_tool"):
                        result.missing_docs.append(f"tools/{rel_path}")

        if generate_missing and result.missing_docs:
            print(f"Found {len(result.missing_docs)} undocumented items")
            # Note: Full doc generation would require reading each file
            # and generating structured documentation. For now, just report.

        return result

    def sync_confluence(
        self, space: str = "PMOS", dry_run: bool = False
    ) -> ConfluenceSyncResult:
        """
        Sync documentation to Confluence.

        Args:
            space: Confluence space key
            dry_run: Preview without actually syncing

        Returns:
            ConfluenceSyncResult with sync stats
        """
        result = ConfluenceSyncResult(space=space)

        # Use the confluence_doc_sync.py script
        sync_script = (
            self.pmos_root
            / "common"
            / "tools"
            / "documentation"
            / "confluence_doc_sync.py"
        )

        if not sync_script.exists():
            result.errors.append(f"Confluence sync script not found: {sync_script}")
            return result

        cmd = ["python3", str(sync_script), "--all", "--space", space]
        if dry_run:
            cmd.append("--dry-run")

        print(f"Syncing documentation to Confluence space '{space}'...")
        if dry_run:
            print("  (dry run - no changes)")

        try:
            sync_result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.pmos_root,
            )

            # Parse output for stats
            output = sync_result.stdout + sync_result.stderr

            # Look for "Pages synced: N" in output
            import re

            match = re.search(r"Pages synced:\s*(\d+)", output)
            if match:
                result.pages_synced = int(match.group(1))

            # Check for errors
            if sync_result.returncode != 0:
                result.errors.append(f"Sync failed: {sync_result.stderr}")
            elif "Error" in output:
                for line in output.split("\n"):
                    if "Error" in line or "Failed" in line:
                        result.errors.append(line.strip())

            print(f"  Synced {result.pages_synced} pages")
            if result.errors:
                print(f"  Errors: {len(result.errors)}")

        except Exception as e:
            result.errors.append(f"Exception during sync: {str(e)}")

        return result

    def update_doc_status(
        self,
        audit_result: DocAuditResult,
        sync_result: Optional[ConfluenceSyncResult] = None,
    ):
        """
        Update the documentation status file.

        Args:
            audit_result: Results from doc audit
            sync_result: Results from Confluence sync (optional)
        """
        status_file = (
            self.pmos_root
            / "common"
            / "documentation"
            / "_meta"
            / "documentation-status.json"
        )

        # Load existing or create new
        if status_file.exists():
            try:
                with open(status_file) as f:
                    status = json.load(f)
            except Exception:
                status = {}
        else:
            status = {}
            status_file.parent.mkdir(parents=True, exist_ok=True)

        # Update audit info
        status["last_audit"] = datetime.now().isoformat()
        status["coverage"] = {
            "commands": {
                "documented": audit_result.commands_documented,
                "total": audit_result.commands_total,
                "percentage": round(
                    audit_result.commands_documented
                    / max(1, audit_result.commands_total)
                    * 100,
                    1,
                ),
            },
            "tools": {
                "documented": audit_result.tools_documented,
                "total": audit_result.tools_total,
                "percentage": round(
                    audit_result.tools_documented
                    / max(1, audit_result.tools_total)
                    * 100,
                    1,
                ),
            },
        }

        if audit_result.missing_docs:
            status["missing_docs"] = audit_result.missing_docs[:20]  # Top 20

        # Update sync info if provided
        if sync_result:
            status["confluence_sync"] = {
                "enabled": True,
                "space": sync_result.space,
                "last_sync": datetime.now().isoformat(),
                "pages_synced": sync_result.pages_synced,
            }
            if sync_result.errors:
                status["confluence_sync"]["errors"] = sync_result.errors[:5]

        # Write status
        try:
            with open(status_file, "w") as f:
                json.dump(status, f, indent=2)
            print(f"Updated documentation status: {status_file}")
        except Exception as e:
            print(f"Warning: Could not update status file: {e}", file=sys.stderr)

    def get_status(self) -> Dict[str, Any]:
        """Get status of all targets."""
        status = {
            "pmos_root": str(self.pmos_root),
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
                "last_files": last_push.get("files_changed", 0),
            }

        return status


def print_report(report: PublishReport) -> None:
    """Print a formatted report."""
    print("\n" + "=" * 60)
    print("PM-OS Push Report (v2)")
    print("=" * 60)
    print(f"Started: {report.started_at}")
    print(f"Completed: {report.completed_at}")
    print()

    for result in report.results:
        status = "✓" if result.success else "✗"
        print(f"{status} {result.target.upper()}")
        print(f"    Repo: {result.repo}")
        print(f"    Method: {result.method}")
        print(
            f"    Files: +{result.files_added} ~{result.files_modified} -{result.files_deleted}"
        )
        if result.pr_url:
            print(f"    PR: {result.pr_url}")
        if result.commit_hash:
            print(f"    Commit: {result.commit_hash}")
        if result.error:
            print(f"    Note: {result.error}")

        # Documentation results (for common target)
        if result.doc_audit:
            print(f"    Documentation:")
            audit = result.doc_audit
            print(f"      Commands: {audit.commands_documented}/{audit.commands_total}")
            print(f"      Tools: {audit.tools_documented}/{audit.tools_total}")
            if audit.missing_docs:
                print(f"      Missing: {len(audit.missing_docs)} items")

        if result.confluence_sync:
            sync = result.confluence_sync
            print(f"    Confluence Sync:")
            print(f"      Space: {sync.space}")
            print(f"      Pages synced: {sync.pages_synced}")
            if sync.errors:
                print(f"      Errors: {len(sync.errors)}")

        print()

    if report.slack_notifications:
        print("Slack Notifications:")
        for notif in report.slack_notifications:
            print(f"  - {notif}")
        print()

    print(f"Summary: {report.targets_succeeded}/{report.targets_attempted} succeeded")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PM-OS Push Publisher v2 - Clone-then-compare publication"
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=["common", "brain", "user", "all"],
        action="append",
        help="Target to publish (can specify multiple)",
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
        help="PM-OS root directory (auto-detected if not specified)",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--skip-docs",
        action="store_true",
        help="Skip documentation audit and Confluence sync (common target)",
    )
    parser.add_argument(
        "--docs-only",
        action="store_true",
        help="Only run documentation phase, no git push (common target)",
    )

    args = parser.parse_args()

    try:
        publisher = PushPublisherV2(pmos_root=args.pmos_root)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Status mode
    if args.status:
        status = publisher.get_status()
        if args.output == "json":
            print(json.dumps(status, indent=2))
        else:
            print("PM-OS Push Status (v2)")
            print("=" * 50)
            print(f"PM-OS Root: {status['pmos_root']}")
            print(f"Config: {status['config_path']}")
            print(f"State: {status['state_path']}")
            print()
            for target, info in status["targets"].items():
                enabled = "✓" if info["enabled"] else "○"
                print(f"{enabled} {target.upper()}")
                print(f"    Repo: {info['repo']}")
                print(f"    Method: {info['method']}")
                print(f"    Last push: {info['last_push']}")
                if info["last_commit"] != "N/A":
                    print(f"    Last commit: {info['last_commit']}")
                    print(f"    Files changed: {info['last_files']}")
                print()
        return 0

    # Determine targets
    targets = None
    if args.target:
        if "all" in args.target:
            targets = ["common", "brain", "user"]
        else:
            targets = list(set(args.target))

    # Run publish
    report = publisher.publish(
        targets=targets,
        dry_run=args.dry_run,
        skip_docs=args.skip_docs,
        docs_only=args.docs_only,
    )

    # Output
    if args.output == "json":
        results_list = []
        for r in report.results:
            r_dict = asdict(r)
            # Convert dataclass results to dicts
            if r.doc_audit:
                r_dict["doc_audit"] = asdict(r.doc_audit)
            if r.confluence_sync:
                r_dict["confluence_sync"] = asdict(r.confluence_sync)
            results_list.append(r_dict)

        output = {
            "started_at": report.started_at,
            "completed_at": report.completed_at,
            "targets_attempted": report.targets_attempted,
            "targets_succeeded": report.targets_succeeded,
            "targets_failed": report.targets_failed,
            "results": results_list,
            "slack_notifications": report.slack_notifications,
        }
        print(json.dumps(output, indent=2, default=str))
    else:
        print_report(report)

    return 0 if report.targets_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
