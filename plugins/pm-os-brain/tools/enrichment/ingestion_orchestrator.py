#!/usr/bin/env python3
"""
Brain Ingestion Orchestrator (v5.0)

Chains existing processor -> analyzer -> writer tools to automatically
ingest inbox data into Brain entities after sync.

Uses config_loader for paths, path_resolver for directory resolution.
No hardcoded paths -- all derived from configuration.

Usage:
    python3 ingestion_orchestrator.py --mode full
    python3 ingestion_orchestrator.py --mode quick
    python3 ingestion_orchestrator.py --sources gdocs,jira
    python3 ingestion_orchestrator.py --sources slack --dry-run
    python3 ingestion_orchestrator.py --reset
    python3 ingestion_orchestrator.py --status
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    get_paths = None

try:
    from pm_os_base.tools.core.config_loader import get_config, get_root_path
except ImportError:
    get_config = None
    get_root_path = None

logger = logging.getLogger(__name__)


def _resolve_paths() -> Dict[str, Path]:
    """Resolve all needed paths via path_resolver and config_loader."""
    paths_dict = {}

    if get_paths is not None:
        try:
            paths = get_paths()
            paths_dict["root"] = paths.root
            paths_dict["common"] = paths.common
            paths_dict["brain"] = paths.brain
            paths_dict["inbox"] = paths.brain / "Inbox"
            return paths_dict
        except Exception:
            pass

    if get_root_path is not None:
        try:
            root = get_root_path()
            paths_dict["root"] = root
            paths_dict["common"] = root / "common"
            paths_dict["brain"] = root / "user" / "brain"
            paths_dict["inbox"] = root / "user" / "brain" / "Inbox"
            return paths_dict
        except Exception:
            pass

    # Last resort fallback
    root = Path.cwd()
    paths_dict["root"] = root
    paths_dict["common"] = root / "common"
    paths_dict["brain"] = root / "user" / "brain"
    paths_dict["inbox"] = root / "user" / "brain" / "Inbox"
    return paths_dict


def _build_source_chains(resolved: Dict[str, Path]) -> Dict[str, Dict[str, Any]]:
    """Build source chain definitions using resolved paths."""
    common = resolved["common"]
    inbox = resolved["inbox"]

    return {
        "gdocs": {
            "processor": str(common / "tools" / "integrations" / "gdocs_processor.py"),
            "processor_args": [],
            "analyzer": str(common / "tools" / "integrations" / "gdocs_analyzer.py"),
            "analyzer_args": ["--all"],
            "writer": str(common / "tools" / "brain" / "unified_brain_writer.py"),
            "writer_args": ["--source", "gdocs"],
            "inbox_dir": inbox / "GDocs",
            "timeout": 180,
            "needs_llm": True,
        },
        "slack": {
            "processor": str(common / "tools" / "slack" / "slack_processor.py"),
            "processor_args": [],
            "analyzer": str(common / "tools" / "slack" / "slack_analyzer.py"),
            "analyzer_args": ["--all"],
            "writer": str(common / "tools" / "slack" / "slack_brain_writer.py"),
            "writer_args": [],
            "inbox_dir": inbox / "Slack",
            "timeout": 120,
            "needs_llm": True,
        },
        "jira": {
            "processor": None,  # Already structured
            "analyzer": None,   # No LLM needed
            "writer": str(common / "tools" / "brain" / "unified_brain_writer.py"),
            "writer_args": ["--source", "jira"],
            "inbox_dir": inbox,  # JIRA_*.md files live directly in Inbox root
            "timeout": 60,
            "needs_llm": False,
        },
        "confluence": {
            "processor": str(common / "tools" / "integrations" / "confluence_processor.py"),
            "processor_args": ["--all"],
            "analyzer": None,
            "writer": str(common / "tools" / "brain" / "unified_brain_writer.py"),
            "writer_args": ["--source", "confluence"],
            "inbox_dir": inbox / "Confluence",
            "timeout": 120,
            "needs_llm": False,
        },
        "github": {
            "processor": str(common / "tools" / "integrations" / "github_pr_processor.py"),
            "processor_args": ["--all"],
            "analyzer": None,
            "writer": str(common / "tools" / "brain" / "unified_brain_writer.py"),
            "writer_args": ["--source", "github"],
            "inbox_dir": inbox / "GitHub",
            "timeout": 60,
            "needs_llm": False,
        },
    }


# Mode -> which sources to run
MODE_SOURCES = {
    "full": ["gdocs", "jira", "slack", "confluence", "github"],
    "quick": ["gdocs", "jira"],
}


def load_state(brain_dir: Path) -> Dict[str, Any]:
    """Load ingestion state."""
    state_file = brain_dir / ".ingestion-state.json"
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_state(brain_dir: Path, state: Dict[str, Any]):
    """Save ingestion state."""
    state_file = brain_dir / ".ingestion-state.json"
    state["last_updated"] = datetime.now().isoformat()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _run_step(cmd: List[str], timeout: int, dry_run: bool) -> Dict[str, Any]:
    """Run a single pipeline step as subprocess."""
    if dry_run:
        return {"success": True, "stdout": "[dry-run] skipped", "stderr": ""}

    try:
        result = subprocess.run(
            [sys.executable] + cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ},
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[-500:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": f"Timeout after {timeout}s"}
    except FileNotFoundError as e:
        return {"success": False, "stdout": "", "stderr": f"Not found: {e}"}


def _has_unprocessed_data(inbox_dir: Path) -> bool:
    """Check if a source inbox has any data to process."""
    if not inbox_dir.exists():
        return False
    for pattern in ["*.md", "*.json", "Raw/*.md", "Raw/*.json"]:
        if list(inbox_dir.glob(pattern)):
            return True
    return False


def ingest_source(
    source: str,
    chain: Dict[str, Any],
    state: Dict[str, Any],
    dry_run: bool,
    verbose: bool,
) -> Dict[str, Any]:
    """Run the full ingestion chain for a single source."""
    result = {
        "source": source,
        "steps_run": [],
        "entities_created": 0,
        "entities_updated": 0,
        "errors": [],
        "skipped": False,
    }

    inbox_dir = chain["inbox_dir"]

    # Check for data
    if not _has_unprocessed_data(inbox_dir):
        result["skipped"] = True
        if verbose:
            logger.info("  [%s] No data in inbox, skipping", source)
        return result

    # Step 1: Processor (if exists)
    if chain.get("processor") and Path(chain["processor"]).exists():
        if verbose:
            logger.info("  [%s] Processing...", source)
        proc_args = chain.get("processor_args", ["--all"])
        step_result = _run_step(
            [chain["processor"]] + proc_args, chain["timeout"], dry_run
        )
        result["steps_run"].append(("processor", step_result["success"]))
        if not step_result["success"]:
            result["errors"].append(f"Processor: {step_result['stderr'][:200]}")
            if verbose:
                logger.warning("    Warning: processor failed, continuing")

    # Step 2: Analyzer (if exists -- LLM step)
    if chain.get("analyzer") and Path(chain["analyzer"]).exists():
        if verbose:
            logger.info("  [%s] Analyzing (LLM)...", source)
        analyzer_args = chain.get("analyzer_args", ["--all"])
        step_result = _run_step(
            [chain["analyzer"]] + analyzer_args, chain["timeout"], dry_run
        )
        result["steps_run"].append(("analyzer", step_result["success"]))
        if not step_result["success"]:
            result["errors"].append(f"Analyzer: {step_result['stderr'][:200]}")
            if verbose:
                logger.warning("    Warning: analyzer failed, continuing")

    # Step 3: Writer
    if chain.get("writer") and Path(chain["writer"]).exists():
        if verbose:
            logger.info("  [%s] Writing entities...", source)
        writer_cmd = [chain["writer"]] + chain.get("writer_args", [])
        step_result = _run_step(writer_cmd, chain["timeout"], dry_run)
        result["steps_run"].append(("writer", step_result["success"]))
        if not step_result["success"]:
            result["errors"].append(f"Writer: {step_result['stderr'][:200]}")
        else:
            # Parse writer output for stats
            output = step_result.get("stderr", "") + step_result.get("stdout", "")
            for line in output.split("\n"):
                if "Entities updated:" in line:
                    try:
                        result["entities_updated"] = int(line.split(":")[-1].strip())
                    except ValueError:
                        pass
                elif "Decisions logged:" in line:
                    try:
                        result["entities_created"] = int(line.split(":")[-1].strip())
                    except ValueError:
                        pass

    return result


def run_ingestion(
    sources: List[str],
    mode: str = "full",
    dry_run: bool = False,
    verbose: bool = True,
    reset: bool = False,
) -> Dict[str, Any]:
    """
    Run the full ingestion pipeline.

    Args:
        sources: List of source names to process
        mode: 'full' or 'quick'
        dry_run: Preview without changes
        verbose: Print progress
        reset: Reset state and reprocess everything

    Returns:
        Summary dict with per-source results
    """
    resolved = _resolve_paths()
    brain_dir = resolved["brain"]
    source_chains = _build_source_chains(resolved)

    start_time = time.time()
    state = load_state(brain_dir)

    if reset:
        state = {}
        if verbose:
            logger.info("State reset -- will reprocess all sources")

    if not state.get("started_at"):
        state["started_at"] = datetime.now().isoformat()

    if verbose:
        logger.info("=" * 60)
        logger.info("BRAIN INGESTION -- mode=%s, sources=%s", mode, ",".join(sources))
        logger.info("=" * 60)

    results = []
    total_created = 0
    total_updated = 0
    total_errors = 0
    total_skipped = 0

    for source in sources:
        chain = source_chains.get(source)
        if not chain:
            if verbose:
                logger.info("  [%s] Unknown source, skipping", source)
            continue

        source_result = ingest_source(source, chain, state, dry_run, verbose)
        results.append(source_result)

        total_created += source_result["entities_created"]
        total_updated += source_result["entities_updated"]
        total_errors += len(source_result["errors"])
        if source_result["skipped"]:
            total_skipped += 1

        # Update state per source
        if not dry_run:
            state.setdefault("sources", {})[source] = {
                "last_run": datetime.now().isoformat(),
                "success": len(source_result["errors"]) == 0,
                "entities_created": source_result["entities_created"],
                "entities_updated": source_result["entities_updated"],
            }
            save_state(brain_dir, state)

    duration = time.time() - start_time

    summary = {
        "mode": mode,
        "dry_run": dry_run,
        "duration_seconds": round(duration, 1),
        "sources_processed": len(results) - total_skipped,
        "sources_skipped": total_skipped,
        "entities_created": total_created,
        "entities_updated": total_updated,
        "errors": total_errors,
        "results": results,
    }

    if verbose:
        logger.info("=" * 60)
        logger.info("INGESTION COMPLETE")
        logger.info("  Duration: %.1fs", duration)
        logger.info("  Sources processed: %d/%d", len(results) - total_skipped, len(results))
        logger.info("  Entities created: %d", total_created)
        logger.info("  Entities updated: %d", total_updated)
        logger.info("  Errors: %d", total_errors)
        logger.info("=" * 60)

    # Print JSON summary to stdout for pipeline consumption
    print(json.dumps(summary, indent=2))

    return summary


def show_status():
    """Show ingestion state."""
    resolved = _resolve_paths()
    brain_dir = resolved["brain"]
    state = load_state(brain_dir)

    print("=" * 60)
    print("BRAIN INGESTION STATUS")
    print("=" * 60)
    print(f"Started: {state.get('started_at', 'Never')}")
    print(f"Last Updated: {state.get('last_updated', 'N/A')}")
    print()

    for source, info in state.get("sources", {}).items():
        status = "OK" if info.get("success") else "FAILED"
        print(f"  {source}: {status} (last: {info.get('last_run', 'N/A')})")
        print(f"    created={info.get('entities_created', 0)}, updated={info.get('entities_updated', 0)}")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Brain Ingestion Orchestrator")
    parser.add_argument(
        "--mode", choices=["full", "quick"], default="full",
        help="Ingestion mode: full (all sources) or quick (GDocs+Jira)",
    )
    parser.add_argument(
        "--sources", type=str, default="",
        help="Comma-separated sources to process (overrides mode)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    parser.add_argument("--reset", action="store_true", help="Reset state, reprocess all")
    parser.add_argument("--status", action="store_true", help="Show status and exit")
    parser.add_argument("--verbose", "-v", action="store_true", default=True)
    parser.add_argument("--quiet", "-q", action="store_true")

    args = parser.parse_args()

    if args.status:
        show_status()
        return

    # Determine sources
    if args.sources:
        sources = [s.strip() for s in args.sources.split(",")]
    else:
        sources = MODE_SOURCES.get(args.mode, MODE_SOURCES["full"])

    verbose = args.verbose and not args.quiet

    run_ingestion(
        sources=sources,
        mode=args.mode,
        dry_run=args.dry_run,
        verbose=verbose,
        reset=args.reset,
    )


if __name__ == "__main__":
    main()
