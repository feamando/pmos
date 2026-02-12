#!/usr/bin/env python3
"""
PM-OS Boot Orchestrator
Runs the complete boot sequence as a single command.
Ensures no steps are skipped.
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Ensure PM-OS environment
PM_OS_ROOT = os.environ.get(
    "PM_OS_ROOT", str(Path(__file__).parent.parent.parent.parent)
)
PM_OS_COMMON = os.environ.get("PM_OS_COMMON", str(Path(PM_OS_ROOT) / "common"))
PM_OS_USER = os.environ.get("PM_OS_USER", str(Path(PM_OS_ROOT) / "user"))
PM_OS_DEVELOPER_ROOT = os.environ.get(
    "PM_OS_DEVELOPER_ROOT", str(Path(PM_OS_ROOT) / "developer")
)

os.environ["PM_OS_ROOT"] = PM_OS_ROOT
os.environ["PM_OS_COMMON"] = PM_OS_COMMON
os.environ["PM_OS_USER"] = PM_OS_USER
os.environ["PM_OS_DEVELOPER_ROOT"] = PM_OS_DEVELOPER_ROOT

# Add tools to path
sys.path.insert(0, str(Path(PM_OS_COMMON) / "tools"))


def run_step(
    name: str,
    cmd: list,
    required: bool = True,
    skip_on_quick: bool = False,
    quick_mode: bool = False,
    capture_stdout: bool = False,
):
    """Run a boot step and report status.

    Args:
        name: Display name for the step
        cmd: Command to run
        required: If True, failure affects overall boot status
        skip_on_quick: If True, skip this step in quick mode
        quick_mode: Whether quick mode is enabled
        capture_stdout: If True, return stdout content instead of True on success
    """
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


def main():
    quick_mode = "--quick" in sys.argv
    quiet_mode = "--quiet" in sys.argv

    print("=" * 60)
    print("PM-OS Boot Orchestrator")
    print("=" * 60)
    print(f"Quick mode: {quick_mode}")
    print(f"Quiet mode: {quiet_mode}")
    print()

    # Load .env if exists
    env_file = Path(PM_OS_USER) / ".env"
    if env_file.exists():
        print("[ENV] Loading .env...")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key] = value.strip('"').strip("'")

    results = {}

    # Step 0.5: Sync Developer Commands
    if Path(PM_OS_DEVELOPER_ROOT).exists():
        results["sync_commands"] = run_step(
            "Sync Developer Commands",
            ["python3", f"{PM_OS_COMMON}/tools/util/command_sync.py", "--quiet"],
        )

    # Step 0.6: Pre-Flight Checks
    results["preflight"] = run_step(
        "Pre-Flight Checks",
        ["python3", f"{PM_OS_COMMON}/tools/preflight/preflight_runner.py", "--quick"],
        required=False,
        skip_on_quick=True,
        quick_mode=quick_mode,
    )

    # Step 1.5: Validate Google OAuth
    results["oauth"] = run_step(
        "Validate Google OAuth",
        [
            "python3",
            f"{PM_OS_COMMON}/tools/integrations/google_scope_validator.py",
            "--fix",
            "--quiet",
        ],
        required=False,
        skip_on_quick=True,
        quick_mode=quick_mode,
    )

    # Step 2: Update Daily Context (fetch raw data)
    if not quick_mode:
        print(f"  [RUN] Fetch Daily Context...")
        try:
            # Run daily_context_updater and capture raw output
            fetch_result = subprocess.run(
                [
                    "python3",
                    f"{PM_OS_COMMON}/tools/daily_context/daily_context_updater.py",
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
            raw_output = fetch_result.stdout

            if fetch_result.returncode == 0 and raw_output:
                print(f"  [OK] Fetch Daily Context")
                results["context_fetch"] = True

                # Step 2b: Synthesize context file from raw data
                print(f"  [RUN] Synthesize Context File...")
                try:
                    synth_result = subprocess.run(
                        [
                            "python3",
                            f"{PM_OS_COMMON}/tools/daily_context/context_synthesizer.py",
                        ],
                        input=raw_output,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    if synth_result.returncode == 0:
                        print(f"  [OK] Synthesize Context File")
                        results["context_synthesize"] = True
                    else:
                        print(
                            f"  [WARN] Synthesize Context File: {synth_result.stderr[:200] if synth_result.stderr else 'failed'}"
                        )
                        results["context_synthesize"] = False
                except Exception as e:
                    print(f"  [ERROR] Synthesize Context File: {e}")
                    results["context_synthesize"] = False
            else:
                print(
                    f"  [WARN] Fetch Daily Context: {fetch_result.stderr[:200] if fetch_result.stderr else 'no output'}"
                )
                results["context_fetch"] = False
                results["context_synthesize"] = False

        except subprocess.TimeoutExpired:
            print(f"  [TIMEOUT] Fetch Daily Context")
            results["context_fetch"] = False
            results["context_synthesize"] = False
        except Exception as e:
            print(f"  [ERROR] Fetch Daily Context: {e}")
            results["context_fetch"] = False
            results["context_synthesize"] = False
    else:
        print(f"  [SKIP] Update Daily Context (--quick mode)")
        results["context_fetch"] = True
        results["context_synthesize"] = True

    # Step 4: Load Hot Topics
    results["brain_load"] = run_step(
        "Load Brain Hot Topics",
        ["python3", f"{PM_OS_COMMON}/tools/brain/brain_loader.py"],
        required=False,
    )

    # Step 4.1: Generate BRAIN.md compressed index
    results["brain_index"] = run_step(
        "Generate BRAIN.md Index",
        ["python3", f"{PM_OS_COMMON}/tools/brain/brain_index_generator.py"],
        required=False,
    )

    # Step 4.5: Brain Enrichment (boot mode - fast, minimal)
    results["brain_enrich"] = run_step(
        "Brain Enrichment (boot mode)",
        ["python3", f"{PM_OS_COMMON}/tools/brain/brain_enrich.py", "--boot"],
        required=False,
        skip_on_quick=True,
        quick_mode=quick_mode,
    )

    # Step 4.6: Master Sheet Sync
    master_sheet_output = run_step(
        "Master Sheet Sync",
        ["python3", f"{PM_OS_COMMON}/tools/master_sheet/master_sheet_sync.py"],
        required=False,
        skip_on_quick=True,
        quick_mode=quick_mode,
        capture_stdout=True,
    )
    results["master_sheet"] = bool(master_sheet_output)

    # Step 4.7: Tech Platform Sprint Sync (tribe-wide context)
    results["tech-platform_sprint"] = run_step(
        "Tech Platform Sprint Sync",
        ["python3", f"{PM_OS_COMMON}/tools/integrations/tech-platform_sprint_sync.py"],
        required=False,
        skip_on_quick=True,
        quick_mode=quick_mode,
    )

    # Step 5: Session Services (with stale session handling)
    results["confucius"] = run_step(
        "Ensure Confucius Session",
        [
            "python3",
            f"{PM_OS_COMMON}/tools/session/confucius_agent.py",
            "--ensure",
            f'Daily Work Session - {datetime.now().strftime("%Y-%m-%d")}',
        ],
        required=False,
    )

    # Step 5.5: Capture Roadmap Items
    if Path(PM_OS_DEVELOPER_ROOT).exists():
        results["roadmap_capture"] = run_step(
            "Capture Roadmap Items",
            [
                "python3",
                f"{PM_OS_DEVELOPER_ROOT}/tools/roadmap/roadmap_inbox_manager.py",
                "--capture",
            ],
            required=False,
            skip_on_quick=True,
            quick_mode=quick_mode,
        )

    # Step 6.5: Generate Meeting Pre-Reads
    results["meeting_prep"] = run_step(
        "Generate Meeting Pre-Reads",
        ["python3", f"{PM_OS_COMMON}/tools/meeting/meeting_prep.py", "--upload"],
        required=False,
        skip_on_quick=True,
        quick_mode=quick_mode,
    )

    # Step 7: Post to Slack (ALWAYS attempt if not quiet)
    today = datetime.now().strftime("%Y-%m-%d")
    context_file = Path(PM_OS_USER) / "personal" / "context" / f"{today}-context.md"

    if not quiet_mode:
        if context_file.exists():
            results["slack_post"] = run_step(
                "Post to Slack",
                [
                    "python3",
                    f"{PM_OS_COMMON}/tools/slack/slack_context_poster.py",
                    str(context_file),
                    "--type",
                    "boot",
                ],
                required=False,
            )
        else:
            print(f"  [FAIL] Post to Slack - Context file missing: {context_file}")
            print(f"         Synthesis may have failed. Check logs above.")
            results["slack_post"] = False
    else:
        print("  [SKIP] Post to Slack (--quiet mode)")
        results["slack_post"] = True  # Not a failure in quiet mode

    # Final Validation: Check that expected outputs exist
    print()
    print("=" * 60)
    print("BOOT VALIDATION")
    print("=" * 60)

    validation_issues = []

    # Check 1: Today's context file exists
    if context_file.exists():
        # Get file size for info
        file_size = context_file.stat().st_size
        print(f"  [OK] Context file: {context_file.name} ({file_size} bytes)")
        results["context_file_exists"] = True
    else:
        validation_issues.append(f"FAIL: Context file missing: {context_file}")
        results["context_file_exists"] = False

    # Check 2: Raw data was saved
    raw_file = Path(PM_OS_USER) / "personal" / "context" / "raw" / f"{today}-raw.md"
    if raw_file.exists():
        print(f"  [OK] Raw data saved: {raw_file.name}")
    else:
        validation_issues.append(
            f"WARN: Raw data not saved (may not have been fetched)"
        )

    # Check 3: Slack posting status
    if not quiet_mode:
        if results.get("slack_post"):
            print(f"  [OK] Slack post completed")
        else:
            validation_issues.append("FAIL: Slack post did not complete")

    # Check 4: Brain state (hot topics loaded)
    brain_hot_topics = Path(PM_OS_USER) / "brain" / "hot_topics.json"
    if brain_hot_topics.exists():
        print(f"  [OK] Brain hot topics loaded")
    else:
        validation_issues.append("WARN: Brain hot topics file not found")

    # Check 5: Master Sheet sync status
    if results.get("master_sheet"):
        print(f"  [OK] Master Sheet synced")
        # Display overdue items from master sheet if available
        if master_sheet_output and "OVERDUE" in master_sheet_output:
            print()
            print("  [!] MASTER SHEET ALERTS:")
            for line in master_sheet_output.strip().split("\n"):
                if (
                    "OVERDUE" in line
                    or "DUE THIS WEEK" in line
                    or line.startswith("  - ")
                ):
                    print(f"      {line}")
    else:
        validation_issues.append("WARN: Master Sheet sync did not complete")

    # Report validation issues
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
    print(f"  Root: {PM_OS_ROOT}")
    print(f"  Common: {PM_OS_COMMON}")
    print(f"  User: {PM_OS_USER}")
    print(
        f"  Developer: {'enabled' if Path(PM_OS_DEVELOPER_ROOT).exists() else 'disabled'}"
    )
    print()
    print(f"Steps: {passed}/{total} completed successfully")
    print()

    for step, success in results.items():
        status = "OK" if success else "FAILED"
        print(f"  [{status}] {step}")

    # Final status
    print()
    print("Ready for commands. Type /help for available commands.")
    print("=" * 60)

    # Determine exit status
    # Critical failures: context file missing (unless quick mode), slack failed (unless quiet mode)
    critical_failed = False
    if not context_file.exists() and not quick_mode:
        critical_failed = True
    if not results.get("slack_post", True) and not quiet_mode:
        critical_failed = True

    return 1 if critical_failed else 0


if __name__ == "__main__":
    sys.exit(main())
