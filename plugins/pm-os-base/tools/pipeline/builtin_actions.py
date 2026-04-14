#!/usr/bin/env python3
"""
Built-in Actions — Base plugin pipeline actions.

Each action accepts (args: dict, context: dict) and returns
{"success": bool, "message": str, "data": dict}.

Plugin-specific actions (brain.enrich, context.update, etc.) are NOT here.
They register from their own plugins via pipeline extensions.
Base only provides: session, preflight, background check, and noop.
"""

import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

try:
    from pipeline.action_registry import ActionRegistry
except ImportError:
    from action_registry import ActionRegistry

logger = logging.getLogger(__name__)


def _run_tool(cmd: list, timeout: int = 120) -> Dict[str, Any]:
    """Run a tool subprocess and return standardized result."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env={**os.environ},
        )
        success = result.returncode == 0
        output = result.stdout.strip()
        error = result.stderr.strip()
        message = output[:200] if output else (error[:200] if error else "completed")
        return {"success": success, "message": message, "data": {"stdout": output, "stderr": error}}
    except subprocess.TimeoutExpired:
        return {"success": False, "message": f"Timeout after {timeout}s", "data": {}}
    except FileNotFoundError as e:
        return {"success": False, "message": f"Tool not found: {e}", "data": {}}


def _tool_path(*parts: str) -> str:
    """Resolve tool path relative to Base plugin tools/."""
    base_tools = Path(__file__).parent.parent
    return str(base_tools / Path(*parts))


def _user_path(*parts: str) -> str:
    """Resolve path relative to PM_OS_USER."""
    user = os.environ.get("PM_OS_USER", "")
    return str(Path(user) / Path(*parts))


def _background_status_dir() -> Path:
    """Return (and create) the directory for background task status files."""
    status_dir = Path(_user_path(".cache", "background"))
    status_dir.mkdir(parents=True, exist_ok=True)
    return status_dir


def _run_tool_background(cmd: list, step_name: str) -> Dict[str, Any]:
    """Launch a tool subprocess in the background with status tracking."""
    status_dir = _background_status_dir()
    status_file = status_dir / f"{step_name}.json"

    # Double-launch protection
    if status_file.exists():
        try:
            with open(status_file) as f:
                existing = json.load(f)
            if existing.get("status") == "running":
                pid = existing.get("pid")
                if pid:
                    try:
                        os.kill(pid, 0)
                        return {
                            "success": True,
                            "message": f"Already running in background (PID {pid})",
                            "data": {"pid": pid, "status_file": str(status_file)},
                        }
                    except OSError:
                        pass
        except (json.JSONDecodeError, IOError):
            pass

    try:
        wrapper_script = str(Path(__file__).parent / "background_wrapper.py")
        wrapped_cmd = [
            sys.executable, wrapper_script,
            "--status-file", str(status_file),
            "--step-name", step_name,
            "--",
        ] + cmd

        proc = subprocess.Popen(
            wrapped_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True, env={**os.environ},
        )

        status = {
            "step_name": step_name, "status": "running", "pid": proc.pid,
            "started_at": datetime.now().isoformat(),
        }
        with open(status_file, "w") as f:
            json.dump(status, f, indent=2)

        return {
            "success": True,
            "message": f"Launched in background (PID {proc.pid})",
            "data": {"pid": proc.pid, "status_file": str(status_file)},
        }
    except Exception as e:
        return {"success": False, "message": f"Failed to launch background: {e}", "data": {}}


# ---------------------------------------------------------------------------
# Session actions (Base-owned)
# ---------------------------------------------------------------------------

def action_session_ensure(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure a Confucius session is active."""
    topic = args.get("topic", "Daily Work Session")
    cmd = [sys.executable, _tool_path("session", "confucius_agent.py"), "--ensure", topic]
    return _run_tool(cmd, timeout=30)


def action_session_end(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """End the Confucius session."""
    return _run_tool([sys.executable, _tool_path("session", "confucius_agent.py"), "--end"], timeout=30)


# ---------------------------------------------------------------------------
# Preflight (Base-owned)
# ---------------------------------------------------------------------------

def action_preflight_check(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Run pre-flight checks."""
    cmd = [sys.executable, _tool_path("preflight", "preflight_runner.py")]
    if args.get("quick"):
        cmd.append("--quick")
    return _run_tool(cmd, timeout=60)


# ---------------------------------------------------------------------------
# Background task management (Base-owned)
# ---------------------------------------------------------------------------

def action_check_background(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Check and report results of background pipeline steps."""
    status_dir = _background_status_dir()
    if not status_dir.exists():
        return {"success": True, "message": "No background tasks", "data": {"results": []}}

    results = []
    for status_file in sorted(status_dir.glob("*.json")):
        try:
            with open(status_file) as f:
                status = json.load(f)
        except (json.JSONDecodeError, IOError):
            status_file.unlink(missing_ok=True)
            continue

        state = status.get("status", "unknown")

        if state in ("completed", "failed"):
            results.append(status)
            status_file.unlink(missing_ok=True)
        elif state == "running":
            pid = status.get("pid")
            if pid:
                try:
                    os.kill(pid, 0)
                    started = status.get("started_at", "")
                    if started:
                        try:
                            age = (datetime.now() - datetime.fromisoformat(started)).total_seconds()
                            if age > 3600:
                                try:
                                    os.kill(pid, 9)
                                except OSError:
                                    pass
                                status["status"] = "killed_stale"
                                results.append(status)
                                status_file.unlink(missing_ok=True)
                                continue
                        except ValueError:
                            pass
                    status["status"] = "still_running"
                    results.append(status)
                except OSError:
                    status["status"] = "crashed"
                    results.append(status)
                    status_file.unlink(missing_ok=True)
            else:
                status_file.unlink(missing_ok=True)
        else:
            status_file.unlink(missing_ok=True)

    completed = [r for r in results if r.get("status") == "completed"]
    failed = [r for r in results if r.get("status") in ("failed", "crashed", "killed_stale")]
    running = [r for r in results if r.get("status") == "still_running"]

    parts = []
    if completed:
        parts.append(f"{len(completed)} completed")
    if failed:
        parts.append(f"{len(failed)} failed")
    if running:
        parts.append(f"{len(running)} still running")

    message = f"Background tasks: {', '.join(parts)}" if parts else "No pending background tasks"

    return {
        "success": True, "message": message,
        "data": {"completed": completed, "failed": failed, "running": running},
    }


# ---------------------------------------------------------------------------
# Noop
# ---------------------------------------------------------------------------

def action_noop(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """No-op action for placeholder steps."""
    return {"success": True, "message": args.get("message", "no-op"), "data": {}}


# ---------------------------------------------------------------------------
# Registry — Base plugin actions only
# ---------------------------------------------------------------------------

def register_all(registry: ActionRegistry) -> None:
    """Register Base plugin built-in actions.

    Plugin-specific actions (brain.*, context.*, slack.*, meeting.*, etc.)
    are registered by their own plugins via pipeline extensions.
    """
    registry.register("session.ensure", action_session_ensure)
    registry.register("session.end", action_session_end)
    registry.register("preflight.check", action_preflight_check)
    registry.register("pipeline.check_background", action_check_background)
    registry.register("noop", action_noop)
