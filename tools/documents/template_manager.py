#!/usr/bin/env python3
"""
Template Manager - Load and render document templates.

Manages templates for PRD, ADR, RFC, 4CQ, BC, and PRFAQ documents.
Supports variable substitution and FPF/Orthogonal section injection.

Usage:
    python3 template_manager.py --type prd --list-sections
    python3 template_manager.py --type adr --get-template
    python3 template_manager.py --type prd --render --context context.json
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = Path(__file__).parent
# Use config_loader for proper path resolution - frameworks are in common/
COMMON_PATH = config_loader.get_common_path()
FRAMEWORKS_DIR = COMMON_PATH / "frameworks"

# Template file mapping
TEMPLATE_FILES = {
    "prd": "PRD_Template.md",
    "adr": "ADR_Template.md",
    "rfc": "RFC_Template.md",
    "4cq": "4CQ_Template.md",
    "bc": "BC_Template.md",
    "prfaq": "PRFAQ_Template.md",
}

# Document type descriptions
DOC_TYPES = {
    "prd": "Product Requirements Document",
    "adr": "Architecture Decision Record",
    "rfc": "Request for Comments",
    "4cq": "Four Critical Questions",
    "bc": "Business Case",
    "prfaq": "Press Release / FAQ",
}


# ============================================================================
# TEMPLATE LOADING
# ============================================================================


def get_template_path(doc_type: str) -> Optional[Path]:
    """Get the path to a template file."""
    if doc_type not in TEMPLATE_FILES:
        return None
    return FRAMEWORKS_DIR / TEMPLATE_FILES[doc_type]


def get_template(doc_type: str) -> Optional[str]:
    """
    Load a template by document type.

    Args:
        doc_type: One of 'prd', 'adr', 'rfc', '4cq', 'bc', 'prfaq'

    Returns:
        Template content as string, or None if not found
    """
    template_path = get_template_path(doc_type)
    if not template_path or not template_path.exists():
        return None

    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def list_templates() -> Dict[str, str]:
    """List all available templates."""
    available = {}
    for doc_type, filename in TEMPLATE_FILES.items():
        path = FRAMEWORKS_DIR / filename
        if path.exists():
            available[doc_type] = DOC_TYPES.get(doc_type, filename)
    return available


def get_template_sections(doc_type: str) -> List[Dict[str, Any]]:
    """
    Extract section structure from a template.

    Returns:
        List of dicts with 'level', 'title', 'line_number'
    """
    template = get_template(doc_type)
    if not template:
        return []

    sections = []
    for i, line in enumerate(template.split("\n"), 1):
        # Match markdown headers
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            level = len(match.group(1))
            title = match.group(2)
            sections.append({"level": level, "title": title, "line_number": i})

    return sections


# ============================================================================
# TEMPLATE RENDERING
# ============================================================================


def render_template(
    doc_type: str,
    context: Dict[str, Any],
    include_fpf: bool = False,
    include_orthogonal: bool = False,
) -> Optional[str]:
    """
    Render a template with context variables.

    Args:
        doc_type: Template type
        context: Dict with variables to substitute
        include_fpf: Include FPF reasoning sections
        include_orthogonal: Include orthogonal challenge FAQ

    Returns:
        Rendered template string
    """
    template = get_template(doc_type)
    if not template:
        return None

    # Default context values
    defaults = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
        "author": os.getenv("USER", "Unknown"),
        "status": "Draft",
    }

    # Merge context with defaults
    full_context = {**defaults, **context}

    # Simple variable substitution: [Variable Name] -> value
    def replace_var(match):
        var_name = match.group(1)
        # Try exact match first
        if var_name in full_context:
            return str(full_context[var_name])
        # Try lowercase
        var_lower = var_name.lower().replace(" ", "_")
        if var_lower in full_context:
            return str(full_context[var_lower])
        # Keep original if not found
        return match.group(0)

    rendered = re.sub(r"\[([^\]]+)\]", replace_var, template)

    # Handle FPF sections
    if not include_fpf:
        # Remove FPF-only sections (marked with "FPF Mode")
        rendered = re.sub(
            r"\n## \d+\. Decision Rationale \(FPF Mode\).*?(?=\n## \d+\.|\n---|\Z)",
            "",
            rendered,
            flags=re.DOTALL,
        )

    # Handle Orthogonal sections
    if not include_orthogonal:
        # Remove Orthogonal-only sections
        rendered = re.sub(
            r"\n## \d+\. Challenge FAQ \(Orthogonal Mode\).*?(?=\n## \d+\.|\n---|\Z)",
            "",
            rendered,
            flags=re.DOTALL,
        )

    return rendered


def inject_fpf_content(
    document: str, fpf_state: Dict[str, Any], drr_path: Optional[str] = None
) -> str:
    """
    Inject FPF reasoning content into a document.

    Args:
        document: The document content
        fpf_state: FPF state with hypotheses, evidence, etc.
        drr_path: Path to DRR file if created

    Returns:
        Document with FPF content injected
    """
    fpf_section = """
## Decision Rationale (FPF Mode)

### DRR Reference

- **Decision:** {decision}
- **DRR Link:** `{drr_path}`
- **Assurance Level:** {assurance_level}

### Options Evaluation (FPF)

| Option | Assurance | R_eff | Status |
|--------|-----------|-------|--------|
{options_table}

### Evidence Chain

{evidence_chain}

### Conditions for Revisiting

- Evidence expires: {evidence_expiry}
- Revisit if: {revisit_conditions}
"""

    # Extract values from FPF state
    decision = fpf_state.get("decision", "[Pending]")
    assurance = fpf_state.get("assurance_level", "L1 Substantiated")
    drr = drr_path or "Brain/Reasoning/Decisions/drr-pending.md"

    # Build options table
    hypotheses = fpf_state.get("hypotheses", [])
    options_rows = []
    for h in hypotheses:
        status = "**Selected**" if h.get("selected") else "Alternative"
        if h.get("invalid"):
            status = f"Rejected: {h.get('invalid_reason', 'N/A')}"
        options_rows.append(
            f"| {h.get('claim', 'Unknown')} | {h.get('level', 'L0')} | "
            f"{h.get('r_eff', 'N/A')} | {status} |"
        )
    options_table = (
        "\n".join(options_rows)
        if options_rows
        else "| (No options evaluated) | - | - | - |"
    )

    # Build evidence chain
    evidence = fpf_state.get("evidence", [])
    evidence_items = []
    for i, e in enumerate(evidence, 1):
        evidence_items.append(
            f"{i}. {e.get('description', 'Unknown')} - CL: {e.get('cl', 'N/A')}, "
            f"Weight: {e.get('weight', 'N/A')}"
        )
    evidence_chain = (
        "\n".join(evidence_items) if evidence_items else "1. (No evidence recorded)"
    )

    # Format section
    fpf_content = fpf_section.format(
        decision=decision,
        drr_path=drr,
        assurance_level=assurance,
        options_table=options_table,
        evidence_chain=evidence_chain,
        evidence_expiry=fpf_state.get("evidence_expiry", "YYYY-MM-DD"),
        revisit_conditions=fpf_state.get("revisit_conditions", "[Define conditions]"),
    )

    # Find insertion point (before References or at end)
    if "## References" in document:
        return document.replace("## References", fpf_content + "\n## References")
    else:
        return document + "\n" + fpf_content


def inject_challenge_faq(document: str, challenges: List[Dict[str, Any]]) -> str:
    """
    Inject Challenge FAQ from orthogonal process.

    Args:
        document: The document content
        challenges: List of challenge/response pairs

    Returns:
        Document with Challenge FAQ injected
    """
    faq_section = """
## Challenge FAQ (Orthogonal Mode)

*Generated from the orthogonal challenge process.*

"""

    for challenge in challenges:
        q = challenge.get("challenge", "Unknown challenge")
        a = challenge.get("resolution", "No resolution provided")
        status = challenge.get("status", "resolved")

        faq_section += f"### Q: {q}\n"
        if status == "accepted":
            faq_section += f"**A:** {a} *(Change incorporated)*\n\n"
        elif status == "rejected":
            faq_section += f"**A:** {a} *(Challenge rejected: {challenge.get('rejection_reason', 'N/A')})*\n\n"
        else:
            faq_section += f"**A:** {a}\n\n"

    # Find insertion point
    if "## References" in document:
        return document.replace("## References", faq_section + "\n## References")
    elif "## Decision Rationale" in document:
        return document.replace(
            "## Decision Rationale", faq_section + "\n## Decision Rationale"
        )
    else:
        return document + "\n" + faq_section


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Template Manager for document generation"
    )
    parser.add_argument(
        "--type", choices=list(TEMPLATE_FILES.keys()), help="Document type"
    )
    parser.add_argument("--list", action="store_true", help="List available templates")
    parser.add_argument(
        "--list-sections", action="store_true", help="List sections in a template"
    )
    parser.add_argument(
        "--get-template", action="store_true", help="Output raw template"
    )
    parser.add_argument(
        "--render", action="store_true", help="Render template with context"
    )
    parser.add_argument("--context", type=str, help="Path to context JSON file")
    parser.add_argument(
        "--fpf", action="store_true", help="Include FPF reasoning sections"
    )
    parser.add_argument(
        "--orthogonal", action="store_true", help="Include orthogonal challenge FAQ"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.list:
        templates = list_templates()
        if args.json:
            print(json.dumps(templates, indent=2))
        else:
            print("Available Templates:")
            for doc_type, desc in templates.items():
                print(f"  {doc_type}: {desc}")
        return 0

    if not args.type:
        parser.print_help()
        return 1

    if args.list_sections:
        sections = get_template_sections(args.type)
        if args.json:
            print(json.dumps(sections, indent=2))
        else:
            print(f"Sections in {args.type} template:")
            for s in sections:
                indent = "  " * (s["level"] - 1)
                print(f"{indent}[L{s['level']}] {s['title']}")
        return 0

    if args.get_template:
        template = get_template(args.type)
        if template:
            print(template)
        else:
            print(f"Template not found: {args.type}", file=sys.stderr)
            return 1
        return 0

    if args.render:
        context = {}
        if args.context:
            with open(args.context, "r", encoding="utf-8") as f:
                context = json.load(f)

        rendered = render_template(
            args.type, context, include_fpf=args.fpf, include_orthogonal=args.orthogonal
        )

        if rendered:
            print(rendered)
        else:
            print(f"Failed to render template: {args.type}", file=sys.stderr)
            return 1
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
