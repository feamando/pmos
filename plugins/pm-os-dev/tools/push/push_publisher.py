"""
PM-OS Dev PushPublisher (v5.0)

Clone-then-compare publisher with content sanitization, pre-push validation,
enhanced dry-run, and changelog accumulation.

Usage:
    from pm_os_dev.tools.push.push_publisher import PushPublisherV3

CLI:
    python3 push_publisher.py --target common --dry-run
    python3 push_publisher.py --target common
    python3 push_publisher.py --status
"""

import argparse
import fnmatch
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

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

try:
    import yaml
except ImportError:
    yaml = None


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FileChange:
    path: str
    change_type: str  # "added", "modified", "deleted"


@dataclass
class SanitizationViolation:
    file_path: str
    line_number: int
    pattern_name: str
    matched_text: str
    severity: str
    description: str


@dataclass
class SanitizationReport:
    violations: List[SanitizationViolation] = field(default_factory=list)
    passed: bool = True
    scanned_files: int = 0
    scan_duration_ms: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "warning")


@dataclass
class PrePushValidation:
    checks_run: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    passed: bool = True


@dataclass
class PushResult:
    target: str
    success: bool
    method: str
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
    sanitization: Optional[SanitizationReport] = None

    @property
    def files_changed(self) -> int:
        return self.files_added + self.files_modified + self.files_deleted


@dataclass
class PublishReport:
    started_at: str
    completed_at: Optional[str] = None
    targets_attempted: int = 0
    targets_succeeded: int = 0
    targets_failed: int = 0
    results: List[PushResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _find_pmos_root() -> Path:
    """Find PM-OS root directory."""
    if get_paths is not None:
        try:
            return get_paths().root
        except Exception:
            pass
    # Fallback search
    for path in [Path.cwd()] + list(Path.cwd().parents):
        if (path / ".pm-os-root").exists():
            return path
    return Path.home() / "pm-os"


# ---------------------------------------------------------------------------
# Main publisher class
# ---------------------------------------------------------------------------

class PushPublisherV3:
    """PM-OS Push Publisher v3 — config-driven, zero hardcoded values."""

    DEFAULT_CONFIG_PATH = "user/.config/push_config.yaml"
    DEFAULT_STATE_PATH = "user/.config/push_state.json"

    ALWAYS_EXCLUDE: Set[str] = {
        "__pycache__", "*.pyc", "*.pyo", ".pytest_cache", "*.egg-info",
        ".DS_Store", ".git", "*.log", ".env", ".secrets",
    }

    def __init__(self, pmos_root: Optional[Path] = None):
        self.pmos_root = pmos_root or _find_pmos_root()
        self.config_path = self.pmos_root / self.DEFAULT_CONFIG_PATH
        self.config = self._load_config()
        self.state_path = self.pmos_root / self.config.get("settings", {}).get(
            "state_file", self.DEFAULT_STATE_PATH
        )
        self.state = self._load_state()

    def _load_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return self._default_config()
        if yaml is None:
            return self._default_config()
        try:
            with open(self.config_path) as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        return {"common": {"enabled": False}, "settings": {}}

    def _load_state(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            return {"last_push": {}}
        try:
            return json.loads(self.state_path.read_text())
        except Exception:
            return {"last_push": {}}

    def _save_state(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(self.state, indent=2))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Exclude matching
    # ------------------------------------------------------------------

    def _should_exclude(self, rel_path: Path, exclude_paths: List[str]) -> bool:
        path_str = str(rel_path)
        parts = rel_path.parts

        for pattern in self.ALWAYS_EXCLUDE:
            if "*" in pattern or "?" in pattern:
                if fnmatch.fnmatch(rel_path.name, pattern):
                    return True
            else:
                if pattern in parts or rel_path.name == pattern:
                    return True

        for exclude in exclude_paths:
            if "*" in exclude or "?" in exclude:
                if fnmatch.fnmatch(path_str, exclude):
                    return True
            else:
                exclude_norm = exclude.rstrip("/")
                if path_str == exclude_norm or path_str.startswith(exclude_norm + "/"):
                    return True

        return False

    # ------------------------------------------------------------------
    # Clone management
    # ------------------------------------------------------------------

    def _clear_clone_working_tree(self, clone_path: Path) -> None:
        for item in clone_path.iterdir():
            if item.name == ".git":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    # ------------------------------------------------------------------
    # Content sanitization
    # ------------------------------------------------------------------

    def _sanitize_content(self, source_path: Path, exclude_paths: List[str]) -> SanitizationReport:
        report = SanitizationReport()
        start = time.monotonic()

        san_config = self.config.get("sanitization", {})
        if not san_config.get("enabled", False):
            return report

        patterns = san_config.get("patterns", {})
        skip_files = san_config.get("skip_files", [])
        scan_extensions = set(san_config.get("scan_extensions", []))

        compiled: Dict[str, Dict[str, Any]] = {}
        for name, pat_config in patterns.items():
            raw = pat_config.get("regex", "")
            if not raw:
                continue
            try:
                compiled[name] = {
                    "regex": re.compile(raw),
                    "severity": pat_config.get("severity", "error"),
                    "description": pat_config.get("description", name),
                }
            except re.error:
                continue

        if not compiled:
            return report

        for item in source_path.rglob("*"):
            if not item.is_file():
                continue
            rel_path = item.relative_to(source_path)
            if self._should_exclude(rel_path, exclude_paths):
                continue
            if any(fnmatch.fnmatch(item.name, skip) for skip in skip_files):
                continue
            if scan_extensions and item.suffix not in scan_extensions:
                continue

            try:
                content = item.read_text(errors="ignore")
            except (UnicodeDecodeError, PermissionError, OSError):
                continue

            report.scanned_files += 1

            for line_num, line in enumerate(content.splitlines(), 1):
                for name, pat in compiled.items():
                    for match in pat["regex"].finditer(line):
                        matched = match.group(0)
                        redacted = matched[:5] + "..." + matched[-4:] if len(matched) > 12 else matched
                        report.violations.append(SanitizationViolation(
                            file_path=str(rel_path),
                            line_number=line_num,
                            pattern_name=name,
                            matched_text=redacted,
                            severity=pat["severity"],
                            description=pat["description"],
                        ))

        report.scan_duration_ms = int((time.monotonic() - start) * 1000)
        report.passed = report.error_count == 0
        return report

    # ------------------------------------------------------------------
    # Pre-push validation
    # ------------------------------------------------------------------

    def _run_pre_push_validation(self, target: str, config: Dict[str, Any]) -> PrePushValidation:
        validation = PrePushValidation()
        val_config = self.config.get("validation", {})

        if val_config.get("todo_scan", True):
            validation.checks_run.append("todo_scan")
            source_path = self.pmos_root / config.get("source_path", target)
            todo_count = 0
            todo_re = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
            if source_path.exists():
                for item in source_path.rglob("*.py"):
                    try:
                        content = item.read_text(errors="ignore")
                        todo_count += len(todo_re.findall(content))
                    except (OSError, UnicodeDecodeError):
                        pass
            if todo_count > 0:
                validation.warnings.append(
                    f"Found {todo_count} TODO/FIXME/HACK/XXX markers in {target} source"
                )

        validation.passed = len(validation.errors) == 0
        return validation

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _copy_files(self, source: Path, dest: Path, exclude_paths: List[str], source_path_prefix: str) -> int:
        files_copied = 0
        for item in source.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(source)
                if self._should_exclude(rel_path, exclude_paths):
                    continue
                full_rel = Path(f"{source_path_prefix}/{rel_path}")
                if self._should_exclude(full_rel, exclude_paths):
                    continue
                dest_file = dest / rel_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest_file)
                files_copied += 1
        return files_copied

    def _detect_changes(self, repo_path: Path) -> List[FileChange]:
        changes = []
        subprocess.run(["git", "add", "-A"], cwd=repo_path, capture_output=True)
        result = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo_path, capture_output=True, text=True,
        )
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            status = line[:2].strip()
            filepath = line[3:].strip()
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

    # ------------------------------------------------------------------
    # Release notes
    # ------------------------------------------------------------------

    def _generate_release_notes(self, target: str, changes: List[FileChange]) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        added = sum(1 for c in changes if c.change_type == "added")
        modified = sum(1 for c in changes if c.change_type == "modified")
        deleted = sum(1 for c in changes if c.change_type == "deleted")

        notes = (
            f"## Release Notes: {target.title()}\n\n"
            f"**Date:** {timestamp}\n"
            f"**Files Changed:** {len(changes)} "
            f"({added} added, {modified} modified, {deleted} deleted)\n\n"
        )

        categories: Dict[str, List[FileChange]] = {
            "tools": [], "commands": [], "docs": [], "tests": [], "config": [], "other": [],
        }
        for change in changes:
            path = change.path.lower()
            if "test" in path:
                categories["tests"].append(change)
            elif path.endswith(".md") or "/docs/" in path:
                categories["docs"].append(change)
            elif "/tools/" in path:
                categories["tools"].append(change)
            elif "/commands/" in path:
                categories["commands"].append(change)
            elif "config" in path or path.endswith((".yaml", ".json")):
                categories["config"].append(change)
            else:
                categories["other"].append(change)

        notes += "### Changes by Category\n\n"
        for category, cat_changes in categories.items():
            if cat_changes:
                notes += f"**{category.title()}** ({len(cat_changes)} files)\n"
                for c in cat_changes[:5]:
                    symbol = {"added": "+", "modified": "~", "deleted": "-"}.get(c.change_type, "?")
                    notes += f"- {symbol} `{c.path}`\n"
                if len(cat_changes) > 5:
                    notes += f"- ... and {len(cat_changes) - 5} more\n"
                notes += "\n"

        return notes

    # ------------------------------------------------------------------
    # Push methods
    # ------------------------------------------------------------------

    def _direct_push(self, repo_path: Path, target: str, config: Dict[str, Any], changes: List[FileChange], release_notes: str) -> Dict[str, Any]:
        branch = config.get("branch", "main")
        prefix = self.config.get("settings", {}).get("commit_prefix", "chore(pmos):")

        try:
            commit_msg = f"{prefix} Update {target} - {len(changes)} files changed"
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_msg], cwd=repo_path, capture_output=True, text=True,
            )
            if commit_result.returncode != 0:
                return {"success": False, "error": f"Commit failed: {commit_result.stderr}"}

            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True, text=True,
            )
            commit_hash = hash_result.stdout.strip()[:8]

            push_result = subprocess.run(
                ["git", "push", "origin", branch], cwd=repo_path, capture_output=True, text=True,
            )
            if push_result.returncode != 0:
                return {"success": False, "error": f"Push failed: {push_result.stderr}"}

            return {"success": True, "commit": commit_hash}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _create_pr(self, repo_path: Path, target: str, config: Dict[str, Any], changes: List[FileChange], release_notes: str) -> Dict[str, Any]:
        repo = config.get("repo", "")
        base_branch = config.get("base_branch", "main")
        prefix = self.config.get("settings", {}).get("pr_prefix", "[PM-OS]")

        try:
            configured_branch = config.get("branch", "main")
            if configured_branch != "main":
                feature_branch = f"{configured_branch}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            else:
                feature_branch = f"pmos-update-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

            subprocess.run(["git", "checkout", "-b", feature_branch], cwd=repo_path, capture_output=True)
            commit_msg = f"{prefix} Update {target} - {len(changes)} files changed"
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_path, capture_output=True)

            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True, text=True,
            )
            commit_hash = hash_result.stdout.strip()[:8]

            subprocess.run(
                ["git", "push", "-u", "origin", feature_branch], cwd=repo_path, capture_output=True,
            )

            pr_title = f"{prefix} {target.title()} Update - {len(changes)} files"
            pr_result = subprocess.run(
                [
                    "gh", "pr", "create", "--repo", repo,
                    "--title", pr_title, "--body", release_notes,
                    "--base", base_branch, "--head", feature_branch,
                ],
                cwd=repo_path, capture_output=True, text=True,
            )

            if pr_result.returncode == 0:
                return {"success": True, "url": pr_result.stdout.strip(), "commit": commit_hash}
            else:
                return {"success": False, "error": pr_result.stderr}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Main publish orchestration
    # ------------------------------------------------------------------

    def publish(
        self,
        targets: Optional[List[str]] = None,
        dry_run: bool = False,
        skip_sanitization: bool = False,
        force: bool = False,
    ) -> PublishReport:
        report = PublishReport(started_at=datetime.now().isoformat())
        git_targets = ["common", "brain", "user"]

        if targets:
            publish_targets = [t for t in targets if t in git_targets]
        else:
            publish_targets = [
                t for t in git_targets
                if self.config.get(t, {}).get("enabled", False)
            ]

        report.targets_attempted = len(publish_targets)

        for target in publish_targets:
            target_config = self.config.get(target, {})
            result = self._publish_target(target, target_config, dry_run, skip_sanitization=skip_sanitization, force=force)
            report.results.append(result)
            if result.success:
                report.targets_succeeded += 1
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
        skip_sanitization: bool = False,
        force: bool = False,
        **kwargs,
    ) -> PushResult:
        repo = config.get("repo", "")
        branch = config.get("branch", "main")
        method = config.get("push_method", "direct")
        source_path = config.get("source_path", target)
        exclude_paths = config.get("exclude_paths", [])

        result = PushResult(target=target, success=False, method=method, repo=repo, branch=branch)

        if not repo:
            result.error = "No repository configured"
            return result

        source_full = self.pmos_root / source_path
        if not source_full.exists():
            result.error = f"Source path not found: {source_full}"
            return result

        # Pre-push validation
        validation = self._run_pre_push_validation(target, config)
        if not validation.passed:
            result.error = "Pre-push validation failed: " + "; ".join(validation.errors)
            return result

        # Content sanitization
        if not skip_sanitization:
            san_report = self._sanitize_content(source_full, exclude_paths)
            result.sanitization = san_report
            if not san_report.passed and not force:
                result.error = f"Sanitization blocked: {san_report.error_count} errors found."
                return result

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                clone_path = Path(tmpdir) / "repo"
                clone_branch = config.get("base_branch", "main") if method == "pr" else branch

                clone_result = subprocess.run(
                    ["gh", "repo", "clone", repo, str(clone_path), "--", "--depth", "1", "-b", clone_branch],
                    capture_output=True, text=True,
                )
                if clone_result.returncode != 0:
                    clone_result = subprocess.run(
                        ["gh", "repo", "clone", repo, str(clone_path), "--", "--depth", "1"],
                        capture_output=True, text=True,
                    )
                    if clone_result.returncode != 0:
                        result.error = f"Clone failed: {clone_result.stderr}"
                        return result

                self._clear_clone_working_tree(clone_path)

                files_copied = self._copy_files(source_full, clone_path, exclude_paths, source_path)
                changes = self._detect_changes(clone_path)
                result.changes = changes
                result.files_added = len([c for c in changes if c.change_type == "added"])
                result.files_modified = len([c for c in changes if c.change_type == "modified"])
                result.files_deleted = len([c for c in changes if c.change_type == "deleted"])

                if result.files_changed == 0:
                    result.success = True
                    result.error = "No changes to publish"
                    return result

                result.release_notes = self._generate_release_notes(target, changes)

                if dry_run:
                    result.success = True
                    result.error = f"DRY RUN: Would push {result.files_changed} files"
                    return result

                if method == "pr":
                    push_result = self._create_pr(clone_path, target, config, changes, result.release_notes)
                    result.pr_url = push_result.get("url")
                else:
                    push_result = self._direct_push(clone_path, target, config, changes, result.release_notes)

                result.commit_hash = push_result.get("commit")
                result.success = push_result.get("success", False)
                if not result.success:
                    result.error = push_result.get("error")

        except Exception as e:
            result.error = f"Exception: {str(e)}"

        return result

    def get_status(self) -> Dict[str, Any]:
        status = {
            "pmos_root": str(self.pmos_root),
            "config_path": str(self.config_path),
            "version": "3",
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="PM-OS Push Publisher v3")
    parser.add_argument("--target", "-t", choices=["common", "brain", "user", "all"], action="append")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--pmos-root", type=Path)
    parser.add_argument("--skip-sanitization", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--output", choices=["text", "json"], default="text")

    args = parser.parse_args()

    try:
        publisher = PushPublisherV3(pmos_root=args.pmos_root)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.status:
        status = publisher.get_status()
        if args.output == "json":
            print(json.dumps(status, indent=2))
        else:
            print("PM-OS Push Status (v3)")
            print("=" * 50)
            for target, info in status["targets"].items():
                enabled = "+" if info["enabled"] else "o"
                print(f"{enabled} {target.upper()}")
                print(f"    Repo: {info['repo']}")
                print(f"    Last push: {info['last_push']}")
                print()
        return 0

    targets = None
    if args.target:
        if "all" in args.target:
            targets = ["common", "brain", "user"]
        else:
            targets = list(set(args.target))

    report = publisher.publish(
        targets=targets,
        dry_run=args.dry_run,
        skip_sanitization=args.skip_sanitization,
        force=args.force,
    )

    print(f"\nSummary: {report.targets_succeeded}/{report.targets_attempted} succeeded")
    for result in report.results:
        icon = "+" if result.success else "X"
        print(f"  {icon} {result.target}: {result.error or 'OK'}")

    return 0 if report.targets_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
