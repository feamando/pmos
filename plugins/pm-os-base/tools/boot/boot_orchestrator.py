#!/usr/bin/env python3
"""
PM-OS v5.0 Boot Orchestrator

Runs the complete boot sequence as a single command.
Plugin-extensible: base provides preflight + session, plugins contribute
additional steps via pipeline extensions.

Usage:
    python3 boot_orchestrator.py                # Full boot
    python3 boot_orchestrator.py --quick        # Quick boot (skip enrichment)
    python3 boot_orchestrator.py --quiet        # Skip Slack posting

Version: 5.0.0
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Bootstrap environment
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
_TOOLS_DIR = _PLUGIN_ROOT / "tools"

if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))


def _resolve_env():
    """Resolve PM-OS environment variables."""
    # Try PM_OS_ROOT first
    root = os.environ.get("PM_OS_ROOT", "")
    if not root:
        # Walk up from plugin location
        current = _PLUGIN_ROOT.resolve()
        for _ in range(10):
            if (current / "user").exists():
                root = str(current)
                break
            current = current.parent
        if not root:
            root = str(Path.home() / "pm-os")

    user_dir = os.environ.get("PM_OS_USER", str(Path(root) / "user"))

    os.environ.setdefault("PM_OS_ROOT", root)
    os.environ.setdefault("PM_OS_USER", user_dir)

    return root, user_dir


def _load_env(user_dir: str):
    """Load .env file if it exists."""
    env_file = Path(user_dir) / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def run_step(
    name: str,
    cmd: list,
    required: bool = True,
    skip_on_quick: bool = False,
    quick_mode: bool = False,
    capture_stdout: bool = False,
):
    """Run a boot step and report status."""
    if skip_on_quick and quick_mode:
        print(f"  [SKIP] {name} (--quick mode)")
        return True if not capture_stdout else ""

    print(f"  [RUN] {name}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            print(f"  [OK] {name}")
            if capture_stdout:
                return result.stdout
            return True
        else:
            print(
                f"  [WARN] {name}: {result.stderr[:200] if result.stderr else 'non-zero exit'}"
            )
            if capture_stdout:
                return result.stdout if result.stdout else ""
            return not required
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {name}")
        return "" if capture_stdout else not required
    except Exception as e:
        print(f"  [ERROR] {name}: {e}")
        return "" if capture_stdout else not required


def _check_background_tasks(user_dir: str):
    """Check and report on previous background tasks."""
    bg_dir = Path(user_dir) / ".cache" / "background"
    if not bg_dir.exists():
        return

    for sf in sorted(bg_dir.glob("*.json")):
        try:
            with open(sf) as f:
                bg = json.load(f)
            name = bg.get("step_name", sf.stem)
            state = bg.get("status", "unknown")
            if state == "completed":
                print(f"  [BG-DONE] {name}: completed at {bg.get('completed_at', '?')}")
                sf.unlink()
            elif state == "failed":
                print(f"  [BG-FAIL] {name}: {str(bg.get('message', 'unknown'))[:100]}")
                sf.unlink()
            elif state == "running":
                pid = bg.get("pid")
                if pid:
                    try:
                        os.kill(pid, 0)
                        started = bg.get("started_at", "")
                        if started:
                            age = (datetime.now() - datetime.fromisoformat(started)).total_seconds()
                            if age > 3600:
                                try:
                                    os.kill(pid, 9)
                                except OSError:
                                    pass
                                print(f"  [BG-STALE] {name}: killed (ran >{int(age)}s)")
                                sf.unlink()
                                continue
                        print(f"  [BG-RUN] {name}: still running (PID {pid})")
                    except OSError:
                        print(f"  [BG-CRASH] {name}: process died (PID {pid})")
                        sf.unlink()
                else:
                    sf.unlink()
        except Exception:
            sf.unlink(missing_ok=True)


def main():
    quick_mode = "--quick" in sys.argv
    quiet_mode = "--quiet" in sys.argv

    root, user_dir = _resolve_env()
    _load_env(user_dir)

    print("=" * 60)
    print("PM-OS Boot Orchestrator (v5.0)")
    print("=" * 60)
    print(f"Quick mode: {quick_mode}")
    print(f"Quiet mode: {quiet_mode}")
    print()

    results = {}

    # Step 0: Check previous background tasks
    _check_background_tasks(user_dir)

    # Step 1: Pre-Flight Checks
    preflight_script = _TOOLS_DIR / "preflight" / "preflight_runner.py"
    results["preflight"] = run_step(
        "Pre-Flight Checks",
        ["python3", str(preflight_script), "--quick"],
        required=False,
        skip_on_quick=True,
        quick_mode=quick_mode,
    )

    # Step 2: Ensure Session
    session_script = _TOOLS_DIR / "session" / "session_manager.py"
    results["session_ensure"] = run_step(
        "Ensure Session",
        [
            "python3", str(session_script),
            "--create", f'Daily Work Session - {datetime.now().strftime("%Y-%m-%d")}',
            "--tags", "boot,daily",
        ],
        required=False,
    )

    # Step 3: Ensure Confucius Session
    confucius_script = _TOOLS_DIR / "session" / "confucius_agent.py"
    results["confucius"] = run_step(
        "Ensure Confucius Session",
        [
            "python3", str(confucius_script),
            "--ensure",
            f'Daily Work Session - {datetime.now().strftime("%Y-%m-%d")}',
        ],
        required=False,
    )

    # Plugin-contributed steps run via pipeline executor
    # (boot.yaml pipeline extensions handle brain.load, context.update, etc.)

    # Final Validation
    print()
    print("=" * 60)
    print("BOOT VALIDATION")
    print("=" * 60)

    validation_issues = []

    # Check: Today's context file exists
    today = datetime.now().strftime("%Y-%m-%d")
    context_file = Path(user_dir) / "personal" / "context" / f"{today}-context.md"
    if context_file.exists():
        file_size = context_file.stat().st_size
        print(f"  [OK] Context file: {context_file.name} ({file_size} bytes)")
    else:
        if not quick_mode:
            validation_issues.append(f"Context file missing: {context_file.name}")
        else:
            print(f"  [SKIP] Context file check (--quick mode)")

    # Check: Brain index exists
    brain_index = Path(user_dir) / "brain" / "BRAIN.md"
    if brain_index.exists():
        print(f"  [OK] Brain index loaded")
    else:
        validation_issues.append("Brain index (BRAIN.md) not found")

    if validation_issues:
        print()
        print("ISSUES DETECTED:")
        for issue in validation_issues:
            print(f"  [!] {issue}")

    # Summary
    print()
    print("=" * 60)
    print("BOOT SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"Environment:")
    print(f"  Root: {root}")
    print(f"  User: {user_dir}")
    print(f"  Plugin: {_PLUGIN_ROOT}")
    print()
    print(f"Steps: {passed}/{total} completed successfully")
    print()

    for step, success in results.items():
        status = "OK" if success else "FAILED"
        print(f"  [{status}] {step}")

    print()
    print("Ready for commands. Type /help for available commands.")
    print("=" * 60)

    critical_failed = False
    if not results.get("session_ensure", True):
        critical_failed = True

    return 1 if critical_failed else 0


if __name__ == "__main__":
    sys.exit(main())
