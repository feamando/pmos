"""
PM-OS CCE TemplateManager (v5.0)

Loads and renders document templates for PRD, ADR, RFC, 4CQ, BC, and PRFAQ.
Supports variable substitution and FPF/Orthogonal section injection.

Usage:
    from pm_os_cce.tools.documents.template_manager import TemplateManager
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from core.config_loader import get_config

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

logger = logging.getLogger(__name__)

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


def _get_frameworks_dir() -> Path:
    """Resolve the frameworks directory via path resolver."""
    try:
        paths = get_paths()
        return paths.common / "frameworks"
    except Exception:
        # Fallback: assume common/ sibling to this plugin
        return Path(__file__).parent.parent.parent.parent.parent / "common" / "frameworks"


class TemplateManager:
    """
    Manages document templates for PM-OS document generation.

    Loads templates from frameworks/ directory, renders with context
    variables, and supports FPF/Orthogonal section injection.
    """

    def __init__(self, frameworks_dir: Optional[Path] = None):
        """
        Initialize the template manager.

        Args:
            frameworks_dir: Path to frameworks directory. If None, resolved via config.
        """
        self._frameworks_dir = frameworks_dir or _get_frameworks_dir()

    def get_template_path(self, doc_type: str) -> Optional[Path]:
        """Get the path to a template file."""
        if doc_type not in TEMPLATE_FILES:
            return None
        return self._frameworks_dir / TEMPLATE_FILES[doc_type]

    def get_template(self, doc_type: str) -> Optional[str]:
        """
        Load a template by document type.

        Args:
            doc_type: One of 'prd', 'adr', 'rfc', '4cq', 'bc', 'prfaq'

        Returns:
            Template content as string, or None if not found
        """
        template_path = self.get_template_path(doc_type)
        if not template_path or not template_path.exists():
            return None
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()

    def list_templates(self) -> Dict[str, str]:
        """List all available templates."""
        available = {}
        for doc_type, filename in TEMPLATE_FILES.items():
            path = self._frameworks_dir / filename
            if path.exists():
                available[doc_type] = DOC_TYPES.get(doc_type, filename)
        return available

    def get_template_sections(self, doc_type: str) -> List[Dict[str, Any]]:
        """
        Extract section structure from a template.

        Returns:
            List of dicts with 'level', 'title', 'line_number'
        """
        template = self.get_template(doc_type)
        if not template:
            return []

        sections = []
        for i, line in enumerate(template.split("\n"), 1):
            match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if match:
                level = len(match.group(1))
                title = match.group(2)
                sections.append({"level": level, "title": title, "line_number": i})
        return sections

    def render_template(
        self,
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
        template = self.get_template(doc_type)
        if not template:
            return None

        defaults = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
            "author": os.getenv("USER", "Unknown"),
            "status": "Draft",
        }

        full_context = {**defaults, **context}

        def replace_var(match):
            var_name = match.group(1)
            if var_name in full_context:
                return str(full_context[var_name])
            var_lower = var_name.lower().replace(" ", "_")
            if var_lower in full_context:
                return str(full_context[var_lower])
            return match.group(0)

        rendered = re.sub(r"\[([^\]]+)\]", replace_var, template)

        if not include_fpf:
            rendered = re.sub(
                r"\n## \d+\. Decision Rationale \(FPF Mode\).*?(?=\n## \d+\.|\n---|\Z)",
                "", rendered, flags=re.DOTALL,
            )

        if not include_orthogonal:
            rendered = re.sub(
                r"\n## \d+\. Challenge FAQ \(Orthogonal Mode\).*?(?=\n## \d+\.|\n---|\Z)",
                "", rendered, flags=re.DOTALL,
            )

        return rendered

    def inject_fpf_content(
        self,
        document: str,
        fpf_state: Dict[str, Any],
        drr_path: Optional[str] = None,
    ) -> str:
        """Inject FPF reasoning content into a document."""
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

        decision = fpf_state.get("decision", "[Pending]")
        assurance = fpf_state.get("assurance_level", "L1 Substantiated")
        drr = drr_path or "Brain/Reasoning/Decisions/drr-pending.md"

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

        fpf_content = fpf_section.format(
            decision=decision,
            drr_path=drr,
            assurance_level=assurance,
            options_table=options_table,
            evidence_chain=evidence_chain,
            evidence_expiry=fpf_state.get("evidence_expiry", "YYYY-MM-DD"),
            revisit_conditions=fpf_state.get("revisit_conditions", "[Define conditions]"),
        )

        if "## References" in document:
            return document.replace("## References", fpf_content + "\n## References")
        return document + "\n" + fpf_content

    def inject_challenge_faq(
        self, document: str, challenges: List[Dict[str, Any]]
    ) -> str:
        """Inject Challenge FAQ from orthogonal process."""
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

        if "## References" in document:
            return document.replace("## References", faq_section + "\n## References")
        elif "## Decision Rationale" in document:
            return document.replace(
                "## Decision Rationale", faq_section + "\n## Decision Rationale"
            )
        return document + "\n" + faq_section

    def inject_frameworks(
        self,
        document: str,
        frameworks: List[Dict[str, Any]],
        doc_type: str = "prd",
    ) -> str:
        """Inject framework references into a rendered document."""
        if not frameworks:
            return document

        section_titles = {
            "prd": "Recommended Frameworks",
            "adr": "Decision Framework",
            "rfc": "Recommended Approach Frameworks",
        }
        section_title = section_titles.get(doc_type, "Recommended Frameworks")

        lines = [f"\n## {section_title}\n"]
        lines.append("*Matched from PM framework library.*\n")

        for fw in frameworks[:3]:
            name = fw.get("framework_name", fw.get("name", ""))
            author = fw.get("author", "")
            use_case = fw.get("use_case", "")
            steps = fw.get("key_steps_summary", "")

            lines.append(f"- **{name}**" + (f" ({author})" if author else ""))
            if use_case:
                lines.append(f"  {use_case[:150]}")
            if steps:
                lines.append(f"  *Steps:* {steps[:150]}")
            lines.append("")

        section_content = "\n".join(lines)

        insertion_markers = {
            "prd": ["## References", "## Appendix", "## Open Questions"],
            "adr": ["## References", "## Consequences", "## Notes"],
            "rfc": ["## References", "## Drawbacks", "## Alternatives"],
        }

        markers = insertion_markers.get(doc_type, ["## References"])
        for marker in markers:
            if marker in document:
                return document.replace(marker, section_content + "\n" + marker)

        return document + "\n" + section_content


# Module-level convenience functions (backward-compatible API)

_default_manager = None


def _get_default_manager() -> TemplateManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = TemplateManager()
    return _default_manager


def get_template_path(doc_type: str) -> Optional[Path]:
    """Get the path to a template file."""
    return _get_default_manager().get_template_path(doc_type)


def get_template(doc_type: str) -> Optional[str]:
    """Load a template by document type."""
    return _get_default_manager().get_template(doc_type)


def list_templates() -> Dict[str, str]:
    """List all available templates."""
    return _get_default_manager().list_templates()


def get_template_sections(doc_type: str) -> List[Dict[str, Any]]:
    """Extract section structure from a template."""
    return _get_default_manager().get_template_sections(doc_type)


def render_template(
    doc_type: str,
    context: Dict[str, Any],
    include_fpf: bool = False,
    include_orthogonal: bool = False,
) -> Optional[str]:
    """Render a template with context variables."""
    return _get_default_manager().render_template(
        doc_type, context, include_fpf, include_orthogonal
    )


def inject_fpf_content(
    document: str, fpf_state: Dict[str, Any], drr_path: Optional[str] = None
) -> str:
    """Inject FPF reasoning content into a document."""
    return _get_default_manager().inject_fpf_content(document, fpf_state, drr_path)


def inject_challenge_faq(
    document: str, challenges: List[Dict[str, Any]]
) -> str:
    """Inject Challenge FAQ from orthogonal process."""
    return _get_default_manager().inject_challenge_faq(document, challenges)


def inject_frameworks(
    document: str,
    frameworks: List[Dict[str, Any]],
    doc_type: str = "prd",
) -> str:
    """Inject framework references into a rendered document."""
    return _get_default_manager().inject_frameworks(document, frameworks, doc_type)
