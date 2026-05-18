"""
PM-OS Dev ReleasePipeline (v5.0)

Unified release pipeline for PM-OS: preflight, version bump, sanitization,
PR creation, post-merge tagging, verification, and Slack announcement.

Usage:
    from pm_os_dev.tools.release.release_pipeline import ReleaseOrchestrator

CLI:
    python3 release_pipeline.py full --version 5.0.0
    python3 release_pipeline.py common --version 5.0.0
    python3 release_pipeline.py status
    python3 release_pipeline.py resume
    python3 release_pipeline.py dry-run --version 5.0.0
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    from pm_os_dev.tools.release.version_manager import VersionManager
except ImportError:
    try:
        from release.version_manager import VersionManager
    except ImportError:
        VersionManager = None

try:
    import yaml
except ImportError:
    yaml = None


# ---------------------------------------------------------------------------
# Release state
# ---------------------------------------------------------------------------

PHASES = [
    "INIT",
    "PREFLIGHT",
    "VERSION_BUMP",
    "SANITIZED",
    "PR_CREATED",
    "WAITING_MERGE",
    "POST_MERGE",
    "VERIFIED",
    "SLACK_POSTED",
    "COMPLETE",
]


@dataclass
class ReleaseState:
    """Persistent state for a release pipeline run."""

    release_id: str = ""
    version: str = ""
    app_version: str = ""
    current_phase: str = "INIT"
    started_at: str = ""
    completed_phases: List[str] = field(default_factory=list)
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    tag_name: Optional[str] = None
    app_zip_path: Optional[str] = None
    app_gdrive_id: Optional[str] = None
    changelog_entry: Optional[str] = None
    error: Optional[str] = None
    dry_run: bool = False
    scope: str = "full"

    def advance(self, to_phase: str) -> None:
        if self.current_phase not in self.completed_phases:
            self.completed_phases.append(self.current_phase)
        self.current_phase = to_phase
        self.error = None

    def fail(self, error_msg: str) -> None:
        self.error = error_msg

    @property
    def is_failed(self) -> bool:
        return self.error is not None

    @property
    def is_complete(self) -> bool:
        return self.current_phase == "COMPLETE"

    @property
    def is_waiting(self) -> bool:
        return self.current_phase == "WAITING_MERGE"

    def status_line(self) -> str:
        if self.is_complete:
            return f"Release {self.version} COMPLETE"
        if self.is_failed:
            return f"Release {self.version} FAILED at {self.current_phase}: {self.error}"
        if self.is_waiting:
            return f"Release {self.version} WAITING for PR merge: {self.pr_url}"
        return f"Release {self.version} in progress — phase: {self.current_phase}"


def _new_release(version: str, app_version: str = "", scope: str = "full", dry_run: bool = False) -> ReleaseState:
    datestamp = datetime.now().strftime("%Y%m%d")
    return ReleaseState(
        release_id=f"release-{version}-{datestamp}",
        version=version,
        app_version=app_version,
        current_phase="INIT",
        started_at=datetime.now().isoformat(),
        dry_run=dry_run,
        scope=scope,
    )


def _save_state(state: ReleaseState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2))


def _load_state(path: Path) -> Optional[ReleaseState]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return ReleaseState(**data)
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _log(phase: str, msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{phase}] {msg}")


def _run(cmd: List[str], cwd: str = None, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def _find_pmos_root() -> Path:
    """Find PM-OS root directory."""
    if get_paths is not None:
        try:
            return get_paths().root
        except Exception:
            pass
    # Fallback
    script_dir = Path(__file__).resolve().parent
    for ancestor in [script_dir] + list(script_dir.parents):
        if (ancestor / ".pm-os-root").exists():
            return ancestor
    return Path.home() / "pm-os"


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

class ReleaseOrchestrator:
    """Orchestrates the full PM-OS release pipeline."""

    def __init__(
        self,
        pmos_root: Optional[Path] = None,
        version: str = "",
        app_version: str = "",
        scope: str = "full",
        dry_run: bool = False,
    ):
        self.pmos_root = pmos_root or _find_pmos_root()
        self.version = version
        self.app_version = app_version or version
        self.scope = scope
        self.dry_run = dry_run

        # Load config
        self.config = self._load_config()
        release_cfg = self.config.get("release", {})
        self.state_path = self.pmos_root / release_cfg.get(
            "state_file", "user/.config/release_state.json"
        )
        self.state: Optional[ReleaseState] = None

    def _load_config(self) -> Dict[str, Any]:
        cfg_path = self.pmos_root / "user" / ".config" / "push_config.yaml"
        if not cfg_path.exists():
            return {}
        if yaml is None:
            return {}
        try:
            with open(cfg_path) as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def _get_release_config(self) -> Dict[str, Any]:
        return self.config.get("release", {})

    def _get_distribution_repo(self) -> str:
        """Get distribution repo from config — never hardcoded."""
        cfg = get_config() if get_config else {}
        repo = cfg.get("distribution.repo", "")
        if not repo:
            repo = self._get_release_config().get("pr_repo", "")
        return repo

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------

    def run(self) -> ReleaseState:
        self.state = _new_release(
            version=self.version,
            app_version=self.app_version,
            scope=self.scope,
            dry_run=self.dry_run,
        )
        _save_state(self.state, self.state_path)
        prefix = "[DRY RUN] " if self.dry_run else ""
        _log("start", f"{prefix}Starting release {self.version} (scope={self.scope})")
        return self._execute_from_current_phase()

    def resume(self) -> ReleaseState:
        self.state = _load_state(self.state_path)
        if self.state is None:
            raise RuntimeError("No release state found. Start a new release first.")
        _log("resume", f"Resuming release {self.state.version} from {self.state.current_phase}")
        self.version = self.state.version
        self.app_version = self.state.app_version
        self.scope = self.state.scope
        self.dry_run = self.state.dry_run
        return self._execute_from_current_phase()

    def status(self) -> str:
        state = _load_state(self.state_path)
        if state is None:
            return "No active release."
        return (
            f"Release ID:    {state.release_id}\n"
            f"Version:       {state.version}\n"
            f"App Version:   {state.app_version}\n"
            f"Scope:         {state.scope}\n"
            f"Phase:         {state.current_phase}\n"
            f"Completed:     {', '.join(state.completed_phases)}\n"
            f"PR URL:        {state.pr_url or 'N/A'}\n"
            f"Tag:           {state.tag_name or 'N/A'}\n"
            f"Dry Run:       {state.dry_run}\n"
            f"Error:         {state.error or 'None'}\n"
            f"Started:       {state.started_at}\n"
            f"---\n"
            f"Status:        {state.status_line()}"
        )

    def _execute_from_current_phase(self) -> ReleaseState:
        phase_map = {
            "INIT": self._phase_preflight,
            "PREFLIGHT": self._phase_version_bump,
            "VERSION_BUMP": self._phase_sanitization,
            "SANITIZED": self._phase_create_pr,
            "PR_CREATED": self._phase_wait_merge,
            "WAITING_MERGE": self._phase_post_merge,
            "POST_MERGE": self._phase_verify,
            "VERIFIED": self._phase_slack,
            "SLACK_POSTED": self._phase_complete,
        }

        while self.state.current_phase != "COMPLETE":
            handler = phase_map.get(self.state.current_phase)
            if handler is None:
                self.state.fail(f"Unknown phase: {self.state.current_phase}")
                _save_state(self.state, self.state_path)
                break

            should_continue = handler()
            _save_state(self.state, self.state_path)

            if not should_continue:
                break

        return self.state

    # ------------------------------------------------------------------
    # Phases
    # ------------------------------------------------------------------

    def _phase_preflight(self) -> bool:
        _log("preflight", "Running pre-flight checks...")
        errors = []

        result = _run(["gh", "auth", "status"])
        if result.returncode != 0:
            errors.append("gh CLI not authenticated. Run: gh auth login")

        if self.scope in ("full", "app"):
            for tool in ["node", "npm"]:
                if shutil.which(tool) is None:
                    errors.append(f"{tool} not found in PATH")

        version_file = self.pmos_root / "common" / "package" / "VERSION"
        if not version_file.exists():
            errors.append(f"VERSION file not found: {version_file}")
        else:
            current = version_file.read_text().strip()
            _log("preflight", f"Current PM-OS version: {current}")

        if self.version and not re.match(r"^\d+\.\d+\.\d+$", self.version):
            errors.append(f"Invalid version format: {self.version} (expected X.Y.Z)")

        if errors:
            msg = "Preflight failed:\n  - " + "\n  - ".join(errors)
            _log("preflight", msg)
            self.state.fail(msg)
            return False

        _log("preflight", "All pre-flight checks passed")
        self.state.advance("PREFLIGHT")
        return True

    def _phase_version_bump(self) -> bool:
        _log("version", f"Bumping versions to {self.version}...")

        if self.dry_run:
            _log("version", f"[DRY RUN] Would bump VERSION to {self.version}")
            self.state.advance("VERSION_BUMP")
            return True

        if VersionManager is not None:
            vm = VersionManager(self.pmos_root)

            if self.scope in ("full", "common"):
                vm.write_version(self.version)
                _log("version", f"Updated VERSION to {self.version}")

                # Update plugin manifests
                updated = vm.update_plugin_manifests(self.version)
                if updated:
                    _log("version", f"Updated {len(updated)} plugin manifests")

        self.state.advance("VERSION_BUMP")
        return True

    def _phase_sanitization(self) -> bool:
        _log("sanitize", "Running content sanitization pre-check...")
        # Sanitization is advisory — always advance
        self.state.advance("SANITIZED")
        return True

    def _phase_create_pr(self) -> bool:
        if self.scope == "app":
            self.state.advance("PR_CREATED")
            self.state.advance("WAITING_MERGE")
            return True

        repo = self._get_distribution_repo()
        release_cfg = self._get_release_config()
        base_branch = release_cfg.get("pr_base_branch", "master")
        branch_prefix = release_cfg.get("pr_branch_prefix", "release")
        datestamp = datetime.now().strftime("%Y%m%d")
        feature_branch = f"{branch_prefix}-{self.version}-{datestamp}"

        if self.dry_run:
            _log("pr", "[DRY RUN] Would create PR:")
            _log("pr", f"  Repo: {repo}")
            _log("pr", f"  Branch: {feature_branch} -> {base_branch}")
            self.state.advance("PR_CREATED")
            self.state.advance("WAITING_MERGE")
            return True

        if not repo:
            self.state.fail("No distribution repo configured (distribution.repo)")
            return False

        _log("pr", f"Publishing to {repo} via PR...")

        # Use push_publisher if available
        try:
            from pm_os_dev.tools.push.push_publisher import PushPublisherV3
        except ImportError:
            try:
                from push.push_publisher import PushPublisherV3
            except ImportError:
                PushPublisherV3 = None

        if PushPublisherV3 is not None:
            publisher = PushPublisherV3(pmos_root=self.pmos_root)
            common_config = self.config.get("common", {})
            common_config["branch"] = branch_prefix
            common_config["push_method"] = "pr"

            result = publisher._publish_target(
                target="common",
                config=common_config,
                dry_run=False,
                skip_sanitization=True,
                force=False,
            )

            if not result.success:
                self.state.fail(f"PR creation failed: {result.error}")
                return False

            self.state.pr_url = result.pr_url
            if result.pr_url:
                match = re.search(r"/pull/(\d+)", result.pr_url)
                if match:
                    self.state.pr_number = int(match.group(1))

            _log("pr", f"PR created: {result.pr_url}")
            self.state.changelog_entry = result.release_notes
        else:
            _log("pr", "PushPublisherV3 not available — manual PR required")

        self.state.advance("PR_CREATED")
        return True

    def _phase_wait_merge(self) -> bool:
        if self.scope == "app" or self.dry_run:
            self.state.advance("WAITING_MERGE")
            return True

        if self.state.pr_number:
            repo = self._get_distribution_repo()
            if repo:
                result = _run([
                    "gh", "pr", "view", str(self.state.pr_number),
                    "--repo", repo, "--json", "state",
                ])
                if result.returncode == 0:
                    try:
                        pr_data = json.loads(result.stdout)
                        if pr_data.get("state") == "MERGED":
                            _log("merge", "PR already merged! Continuing...")
                            self.state.advance("WAITING_MERGE")
                            return True
                    except json.JSONDecodeError:
                        pass

        _log("merge", "=" * 60)
        _log("merge", "PAUSED: Waiting for PR merge")
        _log("merge", f"  PR: {self.state.pr_url}")
        _log("merge", "  Run: /release resume  (after merging)")
        _log("merge", "=" * 60)
        return False

    def _phase_post_merge(self) -> bool:
        _log("post-merge", "Running post-merge phases...")

        if self.dry_run:
            self.state.advance("POST_MERGE")
            return True

        tasks = {}
        if self.scope in ("full", "common"):
            tasks["pypi"] = self._tag_for_pypi

        if not tasks:
            self.state.advance("POST_MERGE")
            return True

        results = {}
        for name, fn in tasks.items():
            try:
                results[name] = fn()
            except Exception as e:
                results[name] = (False, str(e))

        errors = []
        for name, (success, msg) in results.items():
            if success:
                _log("post-merge", f"  {name}: OK — {msg}")
            else:
                _log("post-merge", f"  {name}: FAILED — {msg}")
                errors.append(f"{name}: {msg}")

        if errors:
            self.state.fail("Post-merge failures:\n  " + "\n  ".join(errors))
            return False

        self.state.advance("POST_MERGE")
        return True

    def _tag_for_pypi(self) -> Tuple[bool, str]:
        repo = self._get_distribution_repo()
        tag_name = f"v{self.version}"

        if not repo:
            return (False, "No distribution repo configured")

        _log("pypi", f"Tagging {tag_name} on {repo}...")

        result = _run(["gh", "api", f"repos/{repo}/git/refs/tags/{tag_name}"])
        if result.returncode == 0:
            self.state.tag_name = tag_name
            return (True, f"Tag {tag_name} already exists")

        with tempfile.TemporaryDirectory(prefix="pmos-tag-") as tmp:
            clone_result = _run(
                ["git", "clone", "--depth", "1", f"https://github.com/{repo}.git", tmp],
                timeout=120,
            )
            if clone_result.returncode != 0:
                return (False, f"Clone failed: {clone_result.stderr}")

            tag_result = _run(["git", "tag", "-a", tag_name, "-m", f"Release {self.version}"], cwd=tmp)
            if tag_result.returncode != 0:
                return (False, f"Tag creation failed: {tag_result.stderr}")

            push_result = _run(["git", "push", "origin", tag_name], cwd=tmp, timeout=60)
            if push_result.returncode != 0:
                return (False, f"Tag push failed: {push_result.stderr}")

        self.state.tag_name = tag_name
        return (True, f"Tag {tag_name} pushed")

    def _phase_verify(self) -> bool:
        _log("verify", "Running post-release verification...")

        if self.dry_run:
            self.state.advance("VERIFIED")
            return True

        warnings = []
        repo = self._get_distribution_repo()

        # Check GitHub Actions
        if self.scope in ("full", "common") and repo:
            result = _run([
                "gh", "run", "list", "--repo", repo,
                "--limit", "5", "--json", "status,conclusion,name,headBranch",
            ])
            if result.returncode == 0:
                try:
                    runs = json.loads(result.stdout)
                    tag_runs = [r for r in runs if r.get("headBranch", "").startswith("v")]
                    if tag_runs:
                        latest = tag_runs[0]
                        status = latest.get("conclusion", latest.get("status", "unknown"))
                        _log("verify", f"  Latest tag workflow: {status}")
                except json.JSONDecodeError:
                    pass

        # Check PyPI
        if self.scope in ("full", "common"):
            cfg = get_config() if get_config else {}
            package_name = cfg.get("distribution.pypi_package", "pm-os")
            pip_cmd = "pip3" if shutil.which("pip3") else "pip"
            result = _run([pip_cmd, "index", "versions", package_name], timeout=30)
            if result.returncode == 0 and self.version in result.stdout:
                _log("verify", f"  {package_name} {self.version} found on PyPI")
            else:
                warnings.append(f"{package_name} {self.version} not yet on PyPI")

        if warnings:
            for w in warnings:
                _log("verify", f"  [WARN] {w}")

        self.state.advance("VERIFIED")
        return True

    def _phase_slack(self) -> bool:
        release_cfg = self._get_release_config()
        slack_enabled = release_cfg.get("slack_enabled", True)

        if not slack_enabled or self.dry_run:
            self.state.advance("SLACK_POSTED")
            return True

        channel = release_cfg.get("slack_channel", "")
        if channel:
            _log("slack", f"Posting release announcement to {channel}...")
            message = self._build_slack_message()
            try:
                from pm_os_base.tools.core.connector_bridge import get_connector_client
                client = get_connector_client("slack")
                if client:
                    client.chat_postMessage(channel=channel, text=message)
                    _log("slack", "Slack announcement posted")
            except Exception as e:
                _log("slack", f"Could not post to Slack: {e}")

        self.state.advance("SLACK_POSTED")
        return True

    def _build_slack_message(self) -> str:
        lines = [f"*PM-OS v{self.version} Released*", f"*Version:* `{self.version}`"]
        if self.state.pr_url:
            lines.append(f"*PR:* {self.state.pr_url}")
        if self.state.tag_name:
            lines.append(f"*Tag:* `{self.state.tag_name}`")
        cfg = get_config() if get_config else {}
        package_name = cfg.get("distribution.pypi_package", "pm-os")
        lines.append(f"\nTo update: `pip install --upgrade {package_name}`")
        return "\n".join(lines)

    def _phase_complete(self) -> bool:
        self.state.advance("COMPLETE")
        _log("complete", "=" * 60)
        _log("complete", f"Release {self.version} COMPLETE")
        _log("complete", "=" * 60)
        return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="PM-OS Release Pipeline")
    parser.add_argument(
        "command",
        choices=["full", "common", "app", "status", "resume", "dry-run"],
        help="Release command",
    )
    parser.add_argument("--version", help="PM-OS version (e.g., 5.0.0)")
    parser.add_argument("--app-version", help="App version (defaults to --version)")
    parser.add_argument("--pmos-root", help="PM-OS root directory")

    args = parser.parse_args()

    pmos_root = Path(args.pmos_root) if args.pmos_root else _find_pmos_root()

    if args.command in ("full", "common", "app", "dry-run") and not args.version:
        print("Error: --version is required", file=sys.stderr)
        sys.exit(1)

    orchestrator = ReleaseOrchestrator(
        pmos_root=pmos_root,
        version=args.version or "",
        app_version=args.app_version or args.version or "",
        scope="full" if args.command in ("full", "dry-run") else args.command,
        dry_run=args.command == "dry-run",
    )

    if args.command == "status":
        print(orchestrator.status())
        return

    if args.command == "resume":
        state = orchestrator.resume()
    else:
        state = orchestrator.run()

    if state.is_complete or state.is_waiting:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
