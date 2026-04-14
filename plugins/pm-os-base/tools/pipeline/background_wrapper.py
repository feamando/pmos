#!/usr/bin/env python3
"""
Background Wrapper — runs a command and writes completion status to a JSON file.

Used by the pipeline executor to track background step results.

Usage:
    python3 background_wrapper.py --status-file /path/to/status.json --step-name meeting-prep -- python3 tool.py --arg1
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description="Run a command in the background with status tracking")
    parser.add_argument("--status-file", required=True, help="Path to status JSON file")
    parser.add_argument("--step-name", required=True, help="Pipeline step name for reporting")

    args, remainder = parser.parse_known_args()
    if remainder and remainder[0] == "--":
        remainder = remainder[1:]

    cmd = remainder
    if not cmd:
        sys.exit(1)

    status = {}
    try:
        with open(args.status_file) as f:
            status = json.load(f)
    except Exception:
        status = {"step_name": args.step_name, "started_at": datetime.now().isoformat()}

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ})
        status.update({
            "status": "completed" if result.returncode == 0 else "failed",
            "completed_at": datetime.now().isoformat(),
            "success": result.returncode == 0,
            "message": (result.stderr.strip()[:500] or result.stdout.strip()[:500] or "completed"),
            "returncode": result.returncode,
        })
    except Exception as e:
        status.update({
            "status": "failed",
            "completed_at": datetime.now().isoformat(),
            "success": False,
            "message": f"Exception: {e}",
        })

    try:
        with open(args.status_file, "w") as f:
            json.dump(status, f, indent=2)
    except IOError:
        pass


if __name__ == "__main__":
    main()
