#!/usr/bin/env python3
"""
Gemini CLI - Quint Code Bridge

Provides FPF (First Principles Framework) reasoning capabilities for Gemini CLI.
This bridge allows Gemini to invoke Quint Code reasoning commands and sync with Brain.

Usage:
    python gemini_quint_bridge.py init                    # Initialize FPF session
    python gemini_quint_bridge.py hypothesize "question"  # Generate hypotheses (Q1)
    python gemini_quint_bridge.py verify                  # Verify hypotheses (Q2)
    python gemini_quint_bridge.py validate                # Validate with evidence (Q3)
    python gemini_quint_bridge.py audit                   # Audit for bias (Q4)
    python gemini_quint_bridge.py decide                  # Create DRR (Q5)
    python gemini_quint_bridge.py status                  # Show current reasoning state
    python gemini_quint_bridge.py sync                    # Sync with Brain

Environment:
    QUINT_CODE_PATH: Path to quint-code binary (default: ~/.local/bin/quint-code)
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_PATH = config_loader.get_root_path()
USER_PATH = ROOT_PATH / "user"
BRAIN_DIR = str(USER_PATH / "brain")
REASONING_DIR = os.path.join(BRAIN_DIR, "Reasoning")
QUINT_DIR = str(ROOT_PATH / ".quint")
QUINT_CODE_PATH = os.environ.get(
    "QUINT_CODE_PATH", os.path.expanduser("~/.local/bin/quint-code")
)

# FPF State file for Gemini sessions
GEMINI_FPF_STATE = os.path.join(QUINT_DIR, "gemini_fpf_state.json")


def load_fpf_state() -> Dict[str, Any]:
    """Load current FPF state for Gemini session."""
    if os.path.exists(GEMINI_FPF_STATE):
        try:
            with open(GEMINI_FPF_STATE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "session_id": None,
        "phase": None,
        "hypotheses": [],
        "evidence": [],
        "created": None,
        "last_updated": None,
    }


def save_fpf_state(state: Dict[str, Any]):
    """Save FPF state."""
    state["last_updated"] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(GEMINI_FPF_STATE), exist_ok=True)
    with open(GEMINI_FPF_STATE, "w") as f:
        json.dump(state, f, indent=2)


def run_quint_command(args: List[str]) -> tuple[int, str, str]:
    """Run a quint-code command and return (returncode, stdout, stderr)."""
    if not os.path.exists(QUINT_CODE_PATH):
        return (
            1,
            "",
            f"Quint Code not found at {QUINT_CODE_PATH}. Install with: curl -sSL https://raw.githubusercontent.com/m0n0x41d/quint-code/main/install.sh | bash",
        )

    try:
        result = subprocess.run(
            [QUINT_CODE_PATH] + args, capture_output=True, text=True, cwd=REPO_ROOT
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def init_session(question: Optional[str] = None) -> Dict[str, Any]:
    """Initialize a new FPF reasoning session (Q0)."""
    state = load_fpf_state()

    session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    state = {
        "session_id": session_id,
        "phase": "Q0-INIT",
        "question": question,
        "hypotheses": [],
        "evidence": [],
        "created": datetime.now().isoformat(),
        "last_updated": None,
    }

    save_fpf_state(state)

    # Create session file in Brain/Reasoning/Active/
    active_dir = os.path.join(REASONING_DIR, "Active")
    os.makedirs(active_dir, exist_ok=True)

    session_file = os.path.join(active_dir, f"gemini-{session_id}.md")
    with open(session_file, "w") as f:
        f.write(f"""---
session_id: gemini-{session_id}
phase: Q0-INIT
created: {state['created']}
source: gemini-cli
---

# FPF Reasoning Session

**Question:** {question or 'Not specified'}

## Phase: Q0 - Initialization

Session initialized. Ready for hypothesis generation (Q1).

## Hypotheses

(None yet)

## Evidence

(None yet)

## Decision

(Pending)
""")

    return {
        "status": "success",
        "session_id": session_id,
        "phase": "Q0-INIT",
        "message": f"FPF session initialized. Session file: {session_file}",
        "next_step": 'Run `hypothesize "your question"` to generate hypotheses (Q1)',
    }


def hypothesize(question: str) -> Dict[str, Any]:
    """Generate hypotheses for a question (Q1)."""
    state = load_fpf_state()

    if not state["session_id"]:
        # Auto-init if no session
        init_result = init_session(question)
        state = load_fpf_state()

    state["phase"] = "Q1-HYPOTHESIZE"
    state["question"] = question

    # Generate hypotheses template
    hypotheses = [
        {
            "id": "H1",
            "claim": "(To be filled by Gemini)",
            "level": "L0",
            "confidence": 0.0,
        },
        {
            "id": "H2",
            "claim": "(To be filled by Gemini)",
            "level": "L0",
            "confidence": 0.0,
        },
        {
            "id": "H3",
            "claim": "(To be filled by Gemini)",
            "level": "L0",
            "confidence": 0.0,
        },
    ]
    state["hypotheses"] = hypotheses

    save_fpf_state(state)

    return {
        "status": "success",
        "phase": "Q1-HYPOTHESIZE",
        "question": question,
        "hypotheses": hypotheses,
        "instructions": """
FPF Q1 - Hypothesis Generation

Generate 3-5 hypotheses for the question. Each hypothesis should:
1. Be a falsifiable claim (can be proven wrong)
2. Start at L0 (Conjecture) level
3. Have an initial confidence score (0.0-1.0)

Update the hypotheses in the state file or provide them as structured output.

Example:
H1: "The API latency is caused by database queries" (L0, 0.3)
H2: "The API latency is caused by network overhead" (L0, 0.4)
H3: "The API latency is caused by serialization" (L0, 0.3)

Next step: Run `verify` to check hypotheses for logical consistency (Q2)
""",
        "next_step": "Run `verify` to check hypotheses (Q2)",
    }


def verify() -> Dict[str, Any]:
    """Verify hypotheses for logical consistency (Q2)."""
    state = load_fpf_state()

    if not state["session_id"]:
        return {
            "status": "error",
            "message": "No active FPF session. Run `init` first.",
        }

    state["phase"] = "Q2-VERIFY"
    save_fpf_state(state)

    return {
        "status": "success",
        "phase": "Q2-VERIFY",
        "hypotheses": state["hypotheses"],
        "instructions": """
FPF Q2 - Verification (Deductive Check)

For each hypothesis, verify:
1. Internal consistency - Does it contradict itself?
2. Constraint alignment - Does it violate known constraints?
3. Logical derivation - Can we derive testable predictions?

Promote valid hypotheses to L1 (Substantiated).
Mark invalid hypotheses as 'Invalid' with reason.

Example output:
H1: "API latency from DB queries" → L1 (consistent, testable via query profiling)
H2: "API latency from network" → Invalid (local testing shows <1ms network)
H3: "API latency from serialization" → L1 (consistent, testable via profiling)

Next step: Run `validate` to gather evidence (Q3)
""",
        "next_step": "Run `validate` to gather evidence (Q3)",
    }


def validate() -> Dict[str, Any]:
    """Validate hypotheses with evidence (Q3)."""
    state = load_fpf_state()

    if not state["session_id"]:
        return {
            "status": "error",
            "message": "No active FPF session. Run `init` first.",
        }

    state["phase"] = "Q3-VALIDATE"
    save_fpf_state(state)

    return {
        "status": "success",
        "phase": "Q3-VALIDATE",
        "hypotheses": state["hypotheses"],
        "evidence": state["evidence"],
        "instructions": """
FPF Q3 - Validation (Evidence Gathering)

For each L1 hypothesis, gather supporting/refuting evidence:
1. Search codebase for relevant data
2. Run experiments/tests
3. Check Brain for prior decisions
4. Research external sources

Rate evidence by Congruence Level (CL):
- CL3: Exact match to our context
- CL2: Similar domain, needs adaptation
- CL1: General principle only

Apply WLNK (Weakest Link):
R_eff = min(evidence scores)

Evidence that corroborates across sources promotes hypothesis to L2.

Next step: Run `audit` to check for cognitive biases (Q4)
""",
        "next_step": "Run `audit` to check for biases (Q4)",
    }


def audit() -> Dict[str, Any]:
    """Audit reasoning for cognitive biases (Q4)."""
    state = load_fpf_state()

    if not state["session_id"]:
        return {
            "status": "error",
            "message": "No active FPF session. Run `init` first.",
        }

    state["phase"] = "Q4-AUDIT"
    save_fpf_state(state)

    return {
        "status": "success",
        "phase": "Q4-AUDIT",
        "instructions": """
FPF Q4 - Bias Audit

Check for common cognitive biases:

1. Confirmation Bias - Did we only seek confirming evidence?
2. Anchoring - Are we over-weighting initial hypothesis?
3. Availability - Are we biased by recent/memorable examples?
4. Sunk Cost - Are we favoring options we invested in?
5. Authority Bias - Are we accepting claims without verification?

For each bias:
- Rate risk (Low/Medium/High)
- Note mitigation taken
- Flag if unmitigated

Example:
| Bias | Risk | Mitigation |
|------|------|------------|
| Confirmation | Medium | Actively searched for counter-evidence |
| Anchoring | Low | Re-evaluated after new data |

Next step: Run `decide` to create DRR (Q5)
""",
        "next_step": "Run `decide` to create DRR (Q5)",
    }


def decide() -> Dict[str, Any]:
    """Create Design Rationale Record (Q5)."""
    state = load_fpf_state()

    if not state["session_id"]:
        return {
            "status": "error",
            "message": "No active FPF session. Run `init` first.",
        }

    state["phase"] = "Q5-DECIDE"

    # Create DRR template
    drr_date = datetime.now().strftime("%Y-%m-%d")
    drr_id = f"drr-{drr_date}-{state['session_id']}"

    drr_dir = os.path.join(REASONING_DIR, "Decisions")
    os.makedirs(drr_dir, exist_ok=True)

    drr_file = os.path.join(drr_dir, f"{drr_id}.md")

    drr_template = f"""---
id: {drr_id}
session: gemini-{state['session_id']}
created: {datetime.now().isoformat()}
status: draft
source: gemini-cli
---

# Design Rationale Record: {state.get('question', 'Decision Topic')}

## Context

(Describe the situation requiring a decision)

## Question

{state.get('question', 'What should we decide?')}

## Options Evaluated

| Option | Assurance | R_eff | Status |
|--------|-----------|-------|--------|
| (Option A) | L2 | 0.XX | Selected |
| (Option B) | L1 | 0.XX | Alternative |
| (Option C) | Invalid | - | Rejected: (reason) |

## Selected Option

**Decision:** (State the decision)

**Rationale:** (Why this option won based on evidence)

## Evidence Chain

1. (Evidence 1) - CL: X, Weight: 0.XX
2. (Evidence 2) - CL: X, Weight: 0.XX

## WLNK Analysis

R_eff = min(evidence scores) = X.XX

## Bias Audit Summary

- Confirmation: (status)
- Anchoring: (status)

## Conditions for Revisiting

- Evidence expires: YYYY-MM-DD
- Revisit if: (conditions)

---
*Generated by Gemini via FPF Bridge | {datetime.now().strftime('%Y-%m-%d')}*
"""

    with open(drr_file, "w") as f:
        f.write(drr_template)

    state["drr_file"] = drr_file
    save_fpf_state(state)

    # Clean up active session file
    active_file = os.path.join(
        REASONING_DIR, "Active", f"gemini-{state['session_id']}.md"
    )
    if os.path.exists(active_file):
        os.remove(active_file)

    return {
        "status": "success",
        "phase": "Q5-DECIDE",
        "drr_file": drr_file,
        "message": f"DRR template created at: {drr_file}",
        "instructions": """
FPF Q5 - Decision

A DRR template has been created. Fill in:
1. Selected option and rationale
2. Evidence chain with confidence scores
3. WLNK calculation (R_eff = min of scores)
4. Expiry date for evidence
5. Conditions that would trigger re-evaluation

After completing the DRR, run `sync` to update Brain.
""",
        "next_step": "Fill in DRR template, then run `sync`",
    }


def show_status() -> Dict[str, Any]:
    """Show current FPF reasoning state."""
    state = load_fpf_state()

    # Also check Brain/Reasoning for files
    active_cycles = []
    drrs = []

    active_dir = os.path.join(REASONING_DIR, "Active")
    if os.path.exists(active_dir):
        active_cycles = [f for f in os.listdir(active_dir) if f.endswith(".md")]

    drr_dir = os.path.join(REASONING_DIR, "Decisions")
    if os.path.exists(drr_dir):
        drrs = [f for f in os.listdir(drr_dir) if f.startswith("drr-")]

    return {
        "status": "success",
        "current_session": state.get("session_id"),
        "phase": state.get("phase"),
        "question": state.get("question"),
        "hypotheses_count": len(state.get("hypotheses", [])),
        "evidence_count": len(state.get("evidence", [])),
        "active_cycles": active_cycles,
        "total_drrs": len(drrs),
        "last_updated": state.get("last_updated"),
        "quint_available": os.path.exists(QUINT_DIR),
    }


def sync_to_brain() -> Dict[str, Any]:
    """Sync reasoning state to Brain."""
    # Import and run the sync tool
    sync_script = os.path.join(BASE_DIR, "quint_brain_sync.py")

    if not os.path.exists(sync_script):
        return {"status": "error", "message": f"Sync script not found: {sync_script}"}

    try:
        result = subprocess.run(
            ["python3", sync_script, "--bidirectional"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )

        return {
            "status": "success" if result.returncode == 0 else "error",
            "message": (
                "Brain sync completed" if result.returncode == 0 else "Sync failed"
            ),
            "output": result.stdout,
            "errors": result.stderr if result.returncode != 0 else None,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Gemini CLI - Quint Code Bridge for FPF Reasoning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  init [question]    Initialize FPF session (Q0)
  hypothesize Q      Generate hypotheses for question Q (Q1)
  verify             Verify hypotheses for consistency (Q2)
  validate           Validate with evidence (Q3)
  audit              Audit for cognitive biases (Q4)
  decide             Create Design Rationale Record (Q5)
  status             Show current reasoning state
  sync               Sync reasoning to Brain

Example workflow:
  python gemini_quint_bridge.py init "Should we use REST or GraphQL?"
  python gemini_quint_bridge.py hypothesize "What are the trade-offs?"
  python gemini_quint_bridge.py verify
  python gemini_quint_bridge.py validate
  python gemini_quint_bridge.py audit
  python gemini_quint_bridge.py decide
  python gemini_quint_bridge.py sync
""",
    )

    parser.add_argument(
        "command",
        choices=[
            "init",
            "hypothesize",
            "verify",
            "validate",
            "audit",
            "decide",
            "status",
            "sync",
        ],
        help="FPF command to execute",
    )
    parser.add_argument(
        "question",
        nargs="?",
        default=None,
        help="Question for init/hypothesize commands",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Execute command
    if args.command == "init":
        result = init_session(args.question)
    elif args.command == "hypothesize":
        if not args.question:
            result = {
                "status": "error",
                "message": "Question required for hypothesize command",
            }
        else:
            result = hypothesize(args.question)
    elif args.command == "verify":
        result = verify()
    elif args.command == "validate":
        result = validate()
    elif args.command == "audit":
        result = audit()
    elif args.command == "decide":
        result = decide()
    elif args.command == "status":
        result = show_status()
    elif args.command == "sync":
        result = sync_to_brain()
    else:
        result = {"status": "error", "message": f"Unknown command: {args.command}"}

    # Output
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        # Human-readable output
        print(f"\n{'='*60}")
        print(f"FPF {args.command.upper()}")
        print(f"{'='*60}")

        if result["status"] == "success":
            for key, value in result.items():
                if key not in ["status", "instructions"]:
                    if isinstance(value, list):
                        print(f"\n{key}:")
                        for item in value:
                            print(f"  - {item}")
                    elif value is not None:
                        print(f"{key}: {value}")

            if "instructions" in result:
                print(f"\n{'-'*40}")
                print(result["instructions"])
        else:
            print(f"Error: {result.get('message', 'Unknown error')}")

        print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
