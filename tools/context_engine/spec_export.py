"""
Spec Export Module - Context Engine to Spec Machine Integration

Converts feature context/PRD to spec machine format, enabling seamless export
of context engine features to the spec machine workflow.

The spec machine expects:
    - planning/initialization.md: Initial spec idea/description
    - planning/requirements.md: Q&A format requirements document

This module extracts from context engine:
    - Problem statement from context doc
    - Technical specs from ADRs
    - Acceptance criteria from feature state
    - Business case summary
    - Engineering estimates and risks

Usage:
    from tools.context_engine.spec_export import SpecExporter

    exporter = SpecExporter()

    # Export from feature slug
    result = exporter.export_feature(
        slug="mk-feature-recovery",
        target_repo="/path/to/mobile-rn",
        spec_name="otp-recovery"
    )

    # Or export from feature path
    result = exporter.export_from_path(
        feature_path=Path("/path/to/feature"),
        target_repo="/path/to/mobile-rn"
    )

Author: PM-OS Team
Version: 1.0.0
PRD: Context Creation Engine Integration
"""

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .feature_state import FeatureState, TrackStatus
from .tracks.business_case import BusinessCaseTrack
from .tracks.engineering import ADRStatus, EngineeringTrack


@dataclass
class SpecExportResult:
    """Result of spec export operation."""

    success: bool
    spec_folder: Optional[Path] = None
    files_created: List[str] = field(default_factory=list)
    message: str = ""
    errors: List[str] = field(default_factory=list)
    source_feature: str = ""
    target_repo: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "spec_folder": str(self.spec_folder) if self.spec_folder else None,
            "files_created": self.files_created,
            "message": self.message,
            "errors": self.errors,
            "source_feature": self.source_feature,
            "target_repo": self.target_repo,
        }


@dataclass
class FeatureContent:
    """Extracted content from a context engine feature."""

    title: str
    slug: str
    product_id: str
    organization: str

    # From context document
    problem_statement: str = ""
    description: str = ""
    stakeholders: str = ""
    references: str = ""
    scope_in: List[str] = field(default_factory=list)
    scope_out: List[str] = field(default_factory=list)

    # From business case
    baseline_metrics: Dict[str, Any] = field(default_factory=dict)
    impact_assumptions: Dict[str, Any] = field(default_factory=dict)
    roi_analysis: Dict[str, Any] = field(default_factory=dict)
    bc_executive_summary: str = ""
    bc_approved: bool = False

    # From engineering track
    estimate: Optional[Dict[str, Any]] = None
    adrs: List[Dict[str, Any]] = field(default_factory=list)
    technical_decisions: List[Dict[str, Any]] = field(default_factory=list)
    risks: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[Dict[str, Any]] = field(default_factory=list)

    # Artifacts
    figma_links: List[str] = field(default_factory=list)
    jira_epic: Optional[str] = None
    wireframes: Optional[str] = None

    # Acceptance criteria from decisions
    acceptance_criteria: List[str] = field(default_factory=list)


class SpecExporter:
    """
    Exports context engine features to spec machine format.

    The exporter reads feature state, context documents, business case,
    and engineering track data to generate spec machine input files.
    """

    def __init__(self, user_path: Optional[Path] = None):
        """
        Initialize the spec exporter.

        Args:
            user_path: Path to user/ directory. If None, auto-detected.
        """
        import config_loader

        self._config = config_loader.get_config()
        self._user_path = user_path or Path(self._config.user_path)
        self._raw_config = self._config.config  # Use .config attribute

    def _find_feature(self, slug: str) -> Optional[Path]:
        """
        Find a feature by slug across all products.

        Args:
            slug: Feature slug

        Returns:
            Path to feature folder or None
        """
        products_path = self._user_path / "products"
        if not products_path.exists():
            return None

        for org_path in products_path.iterdir():
            if not org_path.is_dir():
                continue
            for product_path in org_path.iterdir():
                if not product_path.is_dir():
                    continue
                feature_path = product_path / slug
                if (
                    feature_path.exists()
                    and (feature_path / "feature-state.yaml").exists()
                ):
                    return feature_path

        return None

    def _extract_context_content(
        self, feature_path: Path, state: FeatureState
    ) -> Dict[str, Any]:
        """
        Extract content from the context document.

        Args:
            feature_path: Path to feature folder
            state: Feature state

        Returns:
            Dictionary with extracted content
        """
        content = {
            "problem_statement": "",
            "description": "",
            "stakeholders": "",
            "references": "",
            "scope_in": [],
            "scope_out": [],
        }

        # Try to find the context document
        context_doc = feature_path / state.context_file
        if not context_doc.exists():
            # Try context-docs folder
            context_docs_dir = feature_path / "context-docs"
            if context_docs_dir.exists():
                # Find the latest version
                versions = sorted(context_docs_dir.glob("v*-final.md"), reverse=True)
                if versions:
                    context_doc = versions[0]
                else:
                    versions = sorted(context_docs_dir.glob("v*.md"), reverse=True)
                    if versions:
                        context_doc = versions[0]

        if not context_doc.exists():
            return content

        doc_text = context_doc.read_text()

        # Extract Description/Problem Statement
        desc_match = re.search(
            r"## (?:Description|Problem Statement)\n+(.*?)(?=\n## |\Z)",
            doc_text,
            re.DOTALL,
        )
        if desc_match:
            problem_text = desc_match.group(1).strip()
            content["problem_statement"] = problem_text
            content["description"] = problem_text

        # Extract Stakeholders
        stake_match = re.search(
            r"## Stakeholders\n+(.*?)(?=\n## |\Z)", doc_text, re.DOTALL
        )
        if stake_match:
            content["stakeholders"] = stake_match.group(1).strip()

        # Extract References
        ref_match = re.search(r"## References\n+(.*?)(?=\n## |\Z)", doc_text, re.DOTALL)
        if ref_match:
            content["references"] = ref_match.group(1).strip()

        # Extract Scope
        scope_match = re.search(r"## Scope\n+(.*?)(?=\n## |\Z)", doc_text, re.DOTALL)
        if scope_match:
            scope_text = scope_match.group(1)

            # In Scope
            in_scope_match = re.search(
                r"### In Scope\n+(.*?)(?=\n### |\n## |\Z)", scope_text, re.DOTALL
            )
            if in_scope_match:
                in_scope_text = in_scope_match.group(1).strip()
                content["scope_in"] = [
                    line.lstrip("- ").strip()
                    for line in in_scope_text.split("\n")
                    if line.strip().startswith("-")
                ]

            # Out of Scope
            out_scope_match = re.search(
                r"### Out of Scope\n+(.*?)(?=\n### |\n## |\Z)", scope_text, re.DOTALL
            )
            if out_scope_match:
                out_scope_text = out_scope_match.group(1).strip()
                content["scope_out"] = [
                    line.lstrip("- ").strip()
                    for line in out_scope_text.split("\n")
                    if line.strip().startswith("-")
                ]

        return content

    def _extract_bc_content(self, feature_path: Path) -> Dict[str, Any]:
        """
        Extract content from the business case track.

        Args:
            feature_path: Path to feature folder

        Returns:
            Dictionary with BC content
        """
        content = {
            "baseline_metrics": {},
            "impact_assumptions": {},
            "roi_analysis": {},
            "executive_summary": "",
            "approved": False,
        }

        bc_track = BusinessCaseTrack(feature_path)

        content["baseline_metrics"] = bc_track.assumptions.baseline_metrics
        content["impact_assumptions"] = bc_track.assumptions.impact_assumptions
        content["roi_analysis"] = bc_track.assumptions.roi_analysis
        content["approved"] = bc_track.is_approved

        # Try to read executive summary from BC document
        bc_dir = feature_path / "business-case"
        if bc_dir.exists():
            bc_files = sorted(bc_dir.glob("bc-v*-approved.md"), reverse=True)
            if not bc_files:
                bc_files = sorted(bc_dir.glob("bc-v*.md"), reverse=True)

            if bc_files:
                bc_text = bc_files[0].read_text()
                exec_match = re.search(
                    r"## Executive Summary\n+(.*?)(?=\n## |\Z)", bc_text, re.DOTALL
                )
                if exec_match:
                    content["executive_summary"] = exec_match.group(1).strip()

        return content

    def _extract_engineering_content(self, feature_path: Path) -> Dict[str, Any]:
        """
        Extract content from the engineering track.

        Args:
            feature_path: Path to feature folder

        Returns:
            Dictionary with engineering content
        """
        content = {
            "estimate": None,
            "adrs": [],
            "technical_decisions": [],
            "risks": [],
            "dependencies": [],
        }

        eng_track = EngineeringTrack(feature_path)

        # Estimate
        if eng_track.estimate:
            content["estimate"] = eng_track.estimate.to_dict()

        # ADRs
        for adr in eng_track.adrs:
            if adr.status in (ADRStatus.PROPOSED, ADRStatus.ACCEPTED):
                content["adrs"].append(
                    {
                        "number": adr.number,
                        "title": adr.title,
                        "status": adr.status.value,
                        "context": adr.context,
                        "decision": adr.decision,
                        "consequences": adr.consequences,
                    }
                )

        # Technical decisions
        for decision in eng_track.decisions:
            content["technical_decisions"].append(decision.to_dict())

        # Risks
        for risk in eng_track.risks:
            content["risks"].append(risk.to_dict())

        # Dependencies
        for dep in eng_track.dependencies:
            content["dependencies"].append(dep.to_dict())

        return content

    def _extract_figma_links(self, state: FeatureState) -> List[str]:
        """Extract Figma links from artifacts."""
        links = []
        if state.artifacts.get("figma"):
            links.append(state.artifacts["figma"])
        return links

    def _extract_acceptance_criteria(self, state: FeatureState) -> List[str]:
        """
        Extract acceptance criteria from feature decisions.

        Args:
            state: Feature state

        Returns:
            List of acceptance criteria strings
        """
        criteria = []

        # Look for decisions that might contain acceptance criteria
        for decision in state.decisions:
            decision_text = decision.decision.lower()
            if any(
                keyword in decision_text
                for keyword in ["accept", "criteria", "requirement", "must"]
            ):
                criteria.append(decision.decision)

        return criteria

    def extract_feature_content(self, feature_path: Path) -> Optional[FeatureContent]:
        """
        Extract all content from a context engine feature.

        Args:
            feature_path: Path to feature folder

        Returns:
            FeatureContent or None if feature not found
        """
        state = FeatureState.load(feature_path)
        if not state:
            return None

        # Extract content from various sources
        context_content = self._extract_context_content(feature_path, state)
        bc_content = self._extract_bc_content(feature_path)
        eng_content = self._extract_engineering_content(feature_path)

        return FeatureContent(
            title=state.title,
            slug=state.slug,
            product_id=state.product_id,
            organization=state.organization,
            # Context document
            problem_statement=context_content["problem_statement"],
            description=context_content["description"],
            stakeholders=context_content["stakeholders"],
            references=context_content["references"],
            scope_in=context_content["scope_in"],
            scope_out=context_content["scope_out"],
            # Business case
            baseline_metrics=bc_content["baseline_metrics"],
            impact_assumptions=bc_content["impact_assumptions"],
            roi_analysis=bc_content["roi_analysis"],
            bc_executive_summary=bc_content["executive_summary"],
            bc_approved=bc_content["approved"],
            # Engineering
            estimate=eng_content["estimate"],
            adrs=eng_content["adrs"],
            technical_decisions=eng_content["technical_decisions"],
            risks=eng_content["risks"],
            dependencies=eng_content["dependencies"],
            # Artifacts
            figma_links=self._extract_figma_links(state),
            jira_epic=state.artifacts.get("jira_epic"),
            wireframes=state.artifacts.get("wireframes_url"),
            # Acceptance criteria
            acceptance_criteria=self._extract_acceptance_criteria(state),
        )

    def _generate_initialization_md(
        self, content: FeatureContent, spec_name: str
    ) -> str:
        """
        Generate initialization.md content for spec machine.

        Args:
            content: Extracted feature content
            spec_name: Name for the spec

        Returns:
            Markdown content
        """
        now = datetime.now()

        # Build description from problem statement or executive summary
        description = (
            content.problem_statement
            or content.bc_executive_summary
            or content.description
        )
        if not description:
            description = (
                f"*Implement {content.title} feature for {content.product_id}*"
            )

        return f"""---
spec_name: {spec_name}
created: {now.strftime("%Y-%m-%d")}
source: context-engine
feature_slug: {content.slug}
product: {content.product_id}
---

# Initial Spec Idea

## User's Initial Description

{description}

---

*Imported from Context Engine feature: {content.title}*
*Generated on {now.isoformat()}*
"""

    def _generate_requirements_md(
        self, content: FeatureContent, target_repo: Path, repo_name: str
    ) -> str:
        """
        Generate requirements.md content for spec machine.

        Args:
            content: Extracted feature content
            target_repo: Path to target repository
            repo_name: Repository name/alias

        Returns:
            Markdown content
        """
        now = datetime.now()
        lines = [
            f"# Requirements: {content.title}",
            "",
            "---",
            "",
        ]

        # User's Description
        lines.append("## User's Description")
        lines.append("")
        if content.bc_executive_summary:
            lines.append(content.bc_executive_summary)
        elif content.problem_statement:
            lines.append(content.problem_statement)
        else:
            lines.append(f"*Implement {content.title} for {content.product_id}*")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Q&A Section from extracted content
        lines.append("## Questions & Answers")
        lines.append("")

        # Q1: Problem
        lines.append("### Q1: What problem does this solve?")
        lines.append(
            f"A: {content.problem_statement or 'Problem not specified in context document.'}"
        )
        lines.append("")

        # Q2: Business Impact
        lines.append("### Q2: What's the expected business impact?")
        impact_text = ""
        if content.impact_assumptions:
            impact_lines = [
                f"- **{k}**: {v}" for k, v in content.impact_assumptions.items()
            ]
            impact_text = "\n".join(impact_lines)
        elif content.baseline_metrics:
            impact_text = "Baseline metrics: " + ", ".join(
                f"{k}: {v}" for k, v in content.baseline_metrics.items()
            )
        else:
            impact_text = "Business impact not specified in business case."
        lines.append(f"A: {impact_text}")
        lines.append("")

        # Q3: Technical Approach (from ADRs)
        lines.append("### Q3: What's the technical approach?")
        if content.adrs:
            tech_lines = []
            for adr in content.adrs:
                tech_lines.append(f"- **ADR-{adr['number']:03d}: {adr['title']}**")
                tech_lines.append(f"  Decision: {adr['decision'][:200]}...")
            lines.append("A: " + "\n".join(tech_lines))
        elif content.technical_decisions:
            tech_lines = []
            for td in content.technical_decisions[:5]:
                tech_lines.append(f"- {td['decision']}")
            lines.append("A: " + "\n".join(tech_lines))
        else:
            lines.append(
                "A: Technical approach not specified. See engineering track for details."
            )
        lines.append("")

        # Q4: Effort Estimate
        lines.append("### Q4: What's the effort estimate?")
        if content.estimate:
            est = content.estimate
            estimate_text = f"Overall: {est.get('overall', 'TBD')} (Confidence: {est.get('confidence', 'medium')})"
            if est.get("breakdown"):
                breakdown = ", ".join(f"{k}: {v}" for k, v in est["breakdown"].items())
                estimate_text += f"\nBreakdown: {breakdown}"
            if est.get("assumptions"):
                assumptions = ", ".join(est["assumptions"][:3])
                estimate_text += f"\nAssumptions: {assumptions}"
            lines.append(f"A: {estimate_text}")
        else:
            lines.append("A: Estimate not recorded in engineering track.")
        lines.append("")

        # Q5: Risks
        lines.append("### Q5: What are the technical risks?")
        if content.risks:
            risk_lines = []
            for risk in content.risks[:5]:
                mitigation = risk.get("mitigation", "TBD") or "TBD"
                risk_lines.append(
                    f"- **{risk['risk'][:50]}** "
                    f"(Impact: {risk.get('impact', 'medium')}, "
                    f"Likelihood: {risk.get('likelihood', 'medium')})\n"
                    f"  Mitigation: {mitigation[:100]}"
                )
            lines.append("A: " + "\n".join(risk_lines))
        else:
            lines.append("A: No technical risks documented.")
        lines.append("")

        # Q6: Dependencies
        lines.append("### Q6: What are the dependencies?")
        if content.dependencies:
            dep_lines = []
            for dep in content.dependencies[:5]:
                eta = f" (ETA: {dep.get('eta')})" if dep.get("eta") else ""
                dep_lines.append(
                    f"- **{dep['name']}** ({dep.get('type', 'internal')}){eta}: "
                    f"{dep.get('description', '')}"
                )
            lines.append("A: " + "\n".join(dep_lines))
        else:
            lines.append("A: No dependencies documented.")
        lines.append("")

        # Q7: Acceptance Criteria
        lines.append("### Q7: What are the acceptance criteria?")
        if content.acceptance_criteria:
            criteria_lines = [f"- {c}" for c in content.acceptance_criteria[:5]]
            lines.append("A: " + "\n".join(criteria_lines))
        else:
            lines.append("A: Acceptance criteria to be defined during spec creation.")
        lines.append("")

        # Q8: Out of Scope
        lines.append("### Q8: What's explicitly out of scope?")
        if content.scope_out:
            scope_lines = [f"- {s}" for s in content.scope_out]
            lines.append("A: " + "\n".join(scope_lines))
        else:
            lines.append("A: Out of scope items not specified.")
        lines.append("")

        lines.append("---")
        lines.append("")

        # Tech Stack Context (if available in target repo)
        lines.append("## Tech Stack Context")
        tech_stack_path = target_repo / "spec-machine" / "tech-stack.md"
        if tech_stack_path.exists():
            lines.append(f"*See tech-stack.md in target repository: {repo_name}*")
        else:
            lines.append(
                f"*No tech-stack.md found in {repo_name}. Run /analyze-tech-stack in target repo.*"
            )
        lines.append("")
        lines.append("---")
        lines.append("")

        # Visual Assets
        lines.append("## Visual Assets")
        lines.append("")
        if content.figma_links:
            lines.append("**Figma Links:**")
            for link in content.figma_links:
                lines.append(f"- {link}")
        else:
            lines.append("*No Figma links attached to feature.*")
        if content.wireframes:
            lines.append(f"\n**Wireframes:** {content.wireframes}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ADR Summary
        if content.adrs:
            lines.append("## Architecture Decision Records")
            lines.append("")
            for adr in content.adrs:
                lines.append(f"### ADR-{adr['number']:03d}: {adr['title']}")
                lines.append(f"**Status:** {adr['status']}")
                lines.append("")
                lines.append("**Context:**")
                lines.append(
                    adr["context"][:500] + ("..." if len(adr["context"]) > 500 else "")
                )
                lines.append("")
                lines.append("**Decision:**")
                lines.append(
                    adr["decision"][:500]
                    + ("..." if len(adr["decision"]) > 500 else "")
                )
                lines.append("")
                lines.append("**Consequences:**")
                lines.append(
                    adr["consequences"][:300]
                    + ("..." if len(adr["consequences"]) > 300 else "")
                )
                lines.append("")
            lines.append("---")
            lines.append("")

        # Out of Scope (detailed)
        lines.append("## Out of Scope")
        lines.append("")
        if content.scope_out:
            for item in content.scope_out:
                lines.append(f"- {item}")
        else:
            lines.append(
                "*No explicit out-of-scope items specified in context document.*"
            )
        lines.append("")
        lines.append("---")
        lines.append("")

        # Import Metadata
        lines.append("## Import Metadata")
        lines.append("")
        lines.append(f"- **Source Feature:** {content.slug}")
        lines.append(f"- **Product:** {content.product_id}")
        lines.append(f"- **Organization:** {content.organization}")
        lines.append(f"- **Imported:** {now.isoformat()}")
        lines.append(f"- **Target Repo:** {repo_name}")
        lines.append(f"- **BC Approved:** {'Yes' if content.bc_approved else 'No'}")
        if content.jira_epic:
            lines.append(f"- **Jira Epic:** {content.jira_epic}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*Generated by Context Engine spec_export.py*")

        return "\n".join(lines)

    def _normalize_spec_name(self, name: str) -> str:
        """Normalize spec name to kebab-case."""
        name = re.sub(r"[^\w\s-]", "", name.lower())
        name = re.sub(r"[\s_]+", "-", name)
        name = re.sub(r"-+", "-", name)
        return name.strip("-")

    def export_feature(
        self,
        slug: str,
        target_repo: str,
        spec_name: Optional[str] = None,
        subdir: Optional[str] = None,
        dry_run: bool = False,
    ) -> SpecExportResult:
        """
        Export a context engine feature to spec machine format.

        Args:
            slug: Feature slug
            target_repo: Path to target repository
            spec_name: Optional spec name (defaults to feature slug)
            subdir: Optional spec subdirectory (e.g., 'meal-kit')
            dry_run: If True, only report what would be created

        Returns:
            SpecExportResult with operation outcome
        """
        # Find the feature
        feature_path = self._find_feature(slug)
        if not feature_path:
            return SpecExportResult(
                success=False, message=f"Feature not found: {slug}", source_feature=slug
            )

        return self.export_from_path(
            feature_path=feature_path,
            target_repo=target_repo,
            spec_name=spec_name,
            subdir=subdir,
            dry_run=dry_run,
        )

    def export_from_path(
        self,
        feature_path: Path,
        target_repo: str,
        spec_name: Optional[str] = None,
        subdir: Optional[str] = None,
        dry_run: bool = False,
    ) -> SpecExportResult:
        """
        Export a context engine feature from path to spec machine format.

        Args:
            feature_path: Path to feature folder
            target_repo: Path to target repository
            spec_name: Optional spec name
            subdir: Optional spec subdirectory
            dry_run: If True, only report what would be created

        Returns:
            SpecExportResult with operation outcome
        """
        result = SpecExportResult(
            source_feature=str(feature_path.name), target_repo=target_repo
        )

        # Extract feature content
        content = self.extract_feature_content(feature_path)
        if not content:
            result.message = f"Could not extract content from {feature_path}"
            return result

        # Determine spec name
        normalized_spec_name = self._normalize_spec_name(spec_name or content.slug)

        # Build spec folder path
        target_repo_path = Path(target_repo).expanduser()
        if not target_repo_path.exists():
            result.message = f"Target repo not found: {target_repo}"
            result.errors.append(f"Directory does not exist: {target_repo}")
            return result

        date_prefix = datetime.now().strftime("%Y-%m-%d")
        folder_name = f"{date_prefix}-{normalized_spec_name}"

        if subdir:
            spec_folder = (
                target_repo_path / "spec-machine" / "specs" / subdir / folder_name
            )
        else:
            spec_folder = target_repo_path / "spec-machine" / "specs" / folder_name

        result.spec_folder = spec_folder

        if dry_run:
            result.success = True
            result.message = f"[DRY RUN] Would create spec at {spec_folder}"
            result.files_created = [
                str(spec_folder / "planning" / "initialization.md"),
                str(spec_folder / "planning" / "requirements.md"),
            ]
            return result

        # Create folder structure
        try:
            (spec_folder / "planning").mkdir(parents=True, exist_ok=True)
            (spec_folder / "planning" / "visuals").mkdir(exist_ok=True)
            (spec_folder / "implementation").mkdir(exist_ok=True)
            (spec_folder / "verification").mkdir(exist_ok=True)
        except (PermissionError, OSError) as e:
            result.message = f"Failed to create folder structure: {e}"
            result.errors.append(str(e))
            return result

        # Generate and write initialization.md
        init_content = self._generate_initialization_md(content, normalized_spec_name)
        init_path = spec_folder / "planning" / "initialization.md"
        try:
            init_path.write_text(init_content)
            result.files_created.append(str(init_path))
        except (IOError, OSError) as e:
            result.errors.append(f"Failed to write initialization.md: {e}")

        # Generate and write requirements.md
        repo_name = target_repo_path.name
        req_content = self._generate_requirements_md(
            content, target_repo_path, repo_name
        )
        req_path = spec_folder / "planning" / "requirements.md"
        try:
            req_path.write_text(req_content)
            result.files_created.append(str(req_path))
        except (IOError, OSError) as e:
            result.errors.append(f"Failed to write requirements.md: {e}")

        result.success = len(result.errors) == 0
        result.message = (
            f"Feature exported to {spec_folder}"
            if result.success
            else f"Export completed with errors: {result.errors}"
        )

        return result

    def get_export_preview(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Get a preview of what would be exported for a feature.

        Useful for showing the user what content will be included
        before actually exporting.

        Args:
            slug: Feature slug

        Returns:
            Dictionary with content preview or None if not found
        """
        feature_path = self._find_feature(slug)
        if not feature_path:
            return None

        content = self.extract_feature_content(feature_path)
        if not content:
            return None

        return {
            "feature_slug": content.slug,
            "title": content.title,
            "product": content.product_id,
            "has_problem_statement": bool(content.problem_statement),
            "has_executive_summary": bool(content.bc_executive_summary),
            "bc_approved": content.bc_approved,
            "adr_count": len(content.adrs),
            "has_estimate": content.estimate is not None,
            "estimate_size": (
                content.estimate.get("overall") if content.estimate else None
            ),
            "risk_count": len(content.risks),
            "dependency_count": len(content.dependencies),
            "has_figma": len(content.figma_links) > 0,
            "has_jira_epic": content.jira_epic is not None,
            "scope_in_items": len(content.scope_in),
            "scope_out_items": len(content.scope_out),
        }
