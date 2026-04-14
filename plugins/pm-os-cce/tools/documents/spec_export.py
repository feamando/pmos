"""
PM-OS CCE SpecExporter (v5.0)

Converts feature context/PRD to spec machine format, enabling seamless export
of context engine features to the spec machine workflow.

The spec machine expects:
    - planning/initialization.md: Initial spec idea/description
    - planning/requirements.md: Q&A format requirements document

Usage:
    from pm_os_cce.tools.documents.spec_export import SpecExporter
"""

import logging
import re
from dataclasses import dataclass, field
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

    Reads feature state, context documents, business case,
    and engineering track data to generate spec machine input files.
    """

    def __init__(self, user_path: Optional[Path] = None):
        """
        Initialize the spec exporter.

        Args:
            user_path: Path to user/ directory. If None, resolved via config.
        """
        self._config = get_config()
        if user_path:
            self._user_path = user_path
        else:
            paths = get_paths()
            self._user_path = paths.user
        self._components_cache = None

    def _get_design_context(self, product_id: Optional[str] = None):
        """Get DesignContext for spec export enrichment."""
        if not product_id:
            return None
        try:
            from pm_os_cce.tools.design.design_context_provider import DesignContextProvider
        except ImportError:
            try:
                from design.design_context_provider import DesignContextProvider
            except ImportError:
                return None
        try:
            provider = DesignContextProvider(product_id, user_path=str(self._user_path))
            return provider.get_context()
        except Exception as exc:
            logger.warning("DesignContextProvider unavailable: %s", exc)
            return None

    def _get_components_for_spec(self, product_id: Optional[str] = None) -> str:
        """Get component table for spec machine export."""
        try:
            from pm_os_cce.tools.design.design_context_provider import DesignContextProvider
        except ImportError:
            try:
                from design.design_context_provider import DesignContextProvider
            except ImportError:
                return ""
        try:
            pid = product_id or "default"
            provider = DesignContextProvider(pid, user_path=str(self._user_path))
            ctx = provider.get_context()
            return ctx.component_mapping_table
        except Exception as exc:
            logger.warning("DesignContextProvider unavailable for spec: %s", exc)
            return ""

    def _get_figma_analysis(self, figma_links: List[str]):
        """Analyze Figma files and return screen/component data."""
        if not figma_links:
            return None
        try:
            from pm_os_cce.tools.design.figma_client import FigmaClient
        except ImportError:
            try:
                from design.figma_client import FigmaClient
            except ImportError:
                return None
        try:
            client = FigmaClient()
            if not client.is_authenticated():
                return None

            file_key = client.extract_file_key(figma_links[0])
            if not file_key:
                return None

            screens = client.get_screen_list(file_key)
            instances = client.get_component_instances(file_key)

            ds_matches = [i for i in instances if getattr(i, "ds_match", None) or getattr(i, "zest_match", None)]
            coverage_pct = (
                round(len(ds_matches) / len(instances) * 100)
                if instances else 0
            )
            return {
                "screens": [s.name for s in screens],
                "components": [i.name for i in instances],
                "ds_matches": [getattr(i, "ds_match", None) or getattr(i, "zest_match", None) for i in ds_matches],
                "non_ds": [i.name for i in instances if not (getattr(i, "ds_match", None) or getattr(i, "zest_match", None))],
                "coverage_pct": coverage_pct,
            }
        except Exception as exc:
            logger.warning("Figma analysis unavailable: %s", exc)
            return None

    def _find_feature(self, slug: str) -> Optional[Path]:
        """Find a feature by slug across all products."""
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
        self, feature_path: Path, state
    ) -> Dict[str, Any]:
        """Extract content from the context document."""
        content = {
            "problem_statement": "",
            "description": "",
            "stakeholders": "",
            "references": "",
            "scope_in": [],
            "scope_out": [],
        }

        context_doc = feature_path / state.context_file
        if not context_doc.exists():
            context_docs_dir = feature_path / "context-docs"
            if context_docs_dir.exists():
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

        desc_match = re.search(
            r"## (?:Description|Problem Statement)\n+(.*?)(?=\n## |\Z)",
            doc_text, re.DOTALL,
        )
        if desc_match:
            problem_text = desc_match.group(1).strip()
            content["problem_statement"] = problem_text
            content["description"] = problem_text

        stake_match = re.search(
            r"## Stakeholders\n+(.*?)(?=\n## |\Z)", doc_text, re.DOTALL
        )
        if stake_match:
            content["stakeholders"] = stake_match.group(1).strip()

        ref_match = re.search(
            r"## References\n+(.*?)(?=\n## |\Z)", doc_text, re.DOTALL
        )
        if ref_match:
            content["references"] = ref_match.group(1).strip()

        scope_match = re.search(
            r"## Scope\n+(.*?)(?=\n## |\Z)", doc_text, re.DOTALL
        )
        if scope_match:
            scope_text = scope_match.group(1)
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
        """Extract content from the business case track."""
        content = {
            "baseline_metrics": {},
            "impact_assumptions": {},
            "roi_analysis": {},
            "executive_summary": "",
            "approved": False,
        }

        try:
            from pm_os_cce.tools.tracks.business_case import BusinessCaseTrack
        except ImportError:
            try:
                from tracks.business_case import BusinessCaseTrack
            except ImportError:
                return content

        try:
            bc_track = BusinessCaseTrack(feature_path)
            content["baseline_metrics"] = bc_track.assumptions.baseline_metrics
            content["impact_assumptions"] = bc_track.assumptions.impact_assumptions
            content["roi_analysis"] = bc_track.assumptions.roi_analysis
            content["approved"] = bc_track.is_approved
        except Exception:
            pass

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
        """Extract content from the engineering track."""
        content = {
            "estimate": None,
            "adrs": [],
            "technical_decisions": [],
            "risks": [],
            "dependencies": [],
        }

        try:
            from pm_os_cce.tools.tracks.engineering import ADRStatus, EngineeringTrack
        except ImportError:
            try:
                from tracks.engineering import ADRStatus, EngineeringTrack
            except ImportError:
                return content

        try:
            eng_track = EngineeringTrack(feature_path)

            if eng_track.estimate:
                content["estimate"] = eng_track.estimate.to_dict()

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

            for decision in eng_track.decisions:
                content["technical_decisions"].append(decision.to_dict())

            for risk in eng_track.risks:
                content["risks"].append(risk.to_dict())

            for dep in eng_track.dependencies:
                content["dependencies"].append(dep.to_dict())
        except Exception:
            pass

        return content

    def _extract_figma_links(self, state) -> List[str]:
        """Extract Figma links from artifacts."""
        links = []
        if state.artifacts.get("figma"):
            links.append(state.artifacts["figma"])
        return links

    def _extract_acceptance_criteria(self, state) -> List[str]:
        """Extract acceptance criteria from feature decisions."""
        criteria = []
        for decision in state.decisions:
            decision_text = decision.decision.lower()
            if any(
                keyword in decision_text
                for keyword in ["accept", "criteria", "requirement", "must"]
            ):
                criteria.append(decision.decision)
        return criteria

    def extract_feature_content(self, feature_path: Path) -> Optional[FeatureContent]:
        """Extract all content from a context engine feature."""
        try:
            from pm_os_cce.tools.feature.feature_state import FeatureState
        except ImportError:
            try:
                from feature.feature_state import FeatureState
            except ImportError:
                return None

        state = FeatureState.load(feature_path)
        if not state:
            return None

        context_content = self._extract_context_content(feature_path, state)
        bc_content = self._extract_bc_content(feature_path)
        eng_content = self._extract_engineering_content(feature_path)

        return FeatureContent(
            title=state.title,
            slug=state.slug,
            product_id=state.product_id,
            organization=state.organization,
            problem_statement=context_content["problem_statement"],
            description=context_content["description"],
            stakeholders=context_content["stakeholders"],
            references=context_content["references"],
            scope_in=context_content["scope_in"],
            scope_out=context_content["scope_out"],
            baseline_metrics=bc_content["baseline_metrics"],
            impact_assumptions=bc_content["impact_assumptions"],
            roi_analysis=bc_content["roi_analysis"],
            bc_executive_summary=bc_content["executive_summary"],
            bc_approved=bc_content["approved"],
            estimate=eng_content["estimate"],
            adrs=eng_content["adrs"],
            technical_decisions=eng_content["technical_decisions"],
            risks=eng_content["risks"],
            dependencies=eng_content["dependencies"],
            figma_links=self._extract_figma_links(state),
            jira_epic=state.artifacts.get("jira_epic"),
            wireframes=state.artifacts.get("wireframes_url"),
            acceptance_criteria=self._extract_acceptance_criteria(state),
        )

    def _generate_initialization_md(
        self, content: FeatureContent, spec_name: str
    ) -> str:
        """Generate initialization.md content for spec machine."""
        now = datetime.now()

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
        """Generate requirements.md content for spec machine."""
        now = datetime.now()
        lines = [f"# Requirements: {content.title}", "", "---", ""]

        # User's Description
        lines.append("## User's Description")
        lines.append("")
        if content.bc_executive_summary:
            lines.append(content.bc_executive_summary)
        elif content.problem_statement:
            lines.append(content.problem_statement)
        else:
            lines.append(f"*Implement {content.title} for {content.product_id}*")
        lines.extend(["", "---", ""])

        # Q&A Section
        lines.extend(["## Questions & Answers", ""])

        lines.append("### Q1: What problem does this solve?")
        lines.append(
            f"A: {content.problem_statement or 'Problem not specified in context document.'}"
        )
        lines.append("")

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
        lines.extend([f"A: {impact_text}", ""])

        lines.append("### Q3: What's the technical approach?")
        if content.adrs:
            tech_lines = []
            for adr in content.adrs:
                tech_lines.append(f"- **ADR-{adr['number']:03d}: {adr['title']}**")
                tech_lines.append(f"  Decision: {adr['decision'][:200]}...")
            lines.append("A: " + "\n".join(tech_lines))
        elif content.technical_decisions:
            tech_lines = [f"- {td['decision']}" for td in content.technical_decisions[:5]]
            lines.append("A: " + "\n".join(tech_lines))
        else:
            lines.append("A: Technical approach not specified. See engineering track for details.")
        lines.append("")

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

        lines.append("### Q7: What are the acceptance criteria?")
        if content.acceptance_criteria:
            criteria_lines = [f"- {c}" for c in content.acceptance_criteria[:5]]
            lines.append("A: " + "\n".join(criteria_lines))
        else:
            lines.append("A: Acceptance criteria to be defined during spec creation.")
        lines.append("")

        lines.append("### Q8: What's explicitly out of scope?")
        if content.scope_out:
            scope_lines = [f"- {s}" for s in content.scope_out]
            lines.append("A: " + "\n".join(scope_lines))
        else:
            lines.append("A: Out of scope items not specified.")
        lines.extend(["", "---", ""])

        # Tech Stack Context
        lines.extend(["## Tech Stack Context", ""])
        tech_stack_path = target_repo / "spec-machine" / "tech-stack.md"
        if tech_stack_path.exists():
            lines.extend([f"*See tech-stack.md in target repository: {repo_name}*", ""])

        design_ctx = self._get_design_context(content.product_id)
        if design_ctx and design_ctx.repo_profiles:
            for rp in design_ctx.repo_profiles:
                rp_name = rp.get("name", "Unknown")
                lines.append(f"### {rp_name}")
                tech_stack = rp.get("tech_stack", {})
                if tech_stack:
                    lines.extend(["", "| Component | Technology |", "|-----------|-----------|"])
                    for k, v in tech_stack.items():
                        lines.append(f"| {k} | {v} |")
                    lines.append("")
                key_deps = rp.get("key_deps", [])
                if key_deps:
                    lines.extend([f"**Key Dependencies:** {', '.join(key_deps[:10])}", ""])
                lang = rp.get("primary_language", "")
                if lang:
                    lines.extend([f"**Primary Language:** {lang}", ""])
        elif not tech_stack_path.exists():
            lines.extend([
                f"*No tech-stack.md found in {repo_name}. Run /analyze-tech-stack in target repo.*",
                "",
            ])

        lines.extend(["---", ""])

        # Codebase Context from deep analysis
        if design_ctx and any(
            rp.get("has_deep_analysis") for rp in design_ctx.repo_profiles
        ):
            lines.extend(["## Codebase Context", ""])
            for rp in design_ctx.repo_profiles:
                if not rp.get("has_deep_analysis"):
                    continue
                rp_name = rp.get("name", "Unknown")
                lines.extend([f"### {rp_name}", ""])
                arch = rp.get("architecture", "")
                if arch:
                    lines.append(f"**Architecture:** {arch}")
                total_feat = rp.get("total_features", 0)
                if total_feat:
                    lines.append(f"**Feature Modules:** {total_feat}")
                routing = rp.get("routing_type", "")
                if routing:
                    lines.append(f"**Routing:** {routing}")
                lines.append("")
                routes = rp.get("routes", [])
                if routes:
                    lines.append("**Key Routes:**")
                    for r in routes[:10]:
                        lines.append(f"- `{r['path']}` ({r['type']})")
                    if len(routes) > 10:
                        lines.append(f"*(+ {len(routes) - 10} more)*")
                    lines.append("")
                services = rp.get("services", [])
                if services:
                    lines.append("**Shared Services:**")
                    for s in services[:10]:
                        lines.append(f"- `{s['path']}` ({s['name']})")
                    if len(services) > 10:
                        lines.append(f"*(+ {len(services) - 10} more)*")
                    lines.append("")
                ff = rp.get("feature_flag_provider", "")
                if ff:
                    lines.extend([f"**Feature Flags:** {ff}", ""])
            lines.extend(["---", ""])

        # Design System Components
        lines.extend(["## Design System Components", ""])
        component_summary = self._get_components_for_spec(content.product_id)
        if component_summary:
            lines.append(component_summary)
        else:
            lines.append("*No design system components found.*")
        lines.extend(["", "---", ""])

        # Visual Assets
        lines.extend(["## Visual Assets", ""])
        if content.figma_links:
            lines.append("**Figma Links:**")
            for link in content.figma_links:
                lines.append(f"- {link}")
        else:
            lines.append("*No Figma links attached to feature.*")
        if content.wireframes:
            lines.append(f"\n**Wireframes:** {content.wireframes}")
        lines.extend(["", "---", ""])

        # Figma Analysis
        figma_analysis = self._get_figma_analysis(content.figma_links)
        if figma_analysis:
            lines.extend(["## Figma Analysis", ""])
            screens = figma_analysis.get("screens", [])
            if screens:
                lines.append(f"**Screens ({len(screens)}):**")
                for s in screens:
                    lines.append(f"- {s}")
                lines.append("")
            ds_matches = figma_analysis.get("ds_matches", [])
            non_ds = figma_analysis.get("non_ds", [])
            coverage = figma_analysis.get("coverage_pct", 0)
            total_comps = len(ds_matches) + len(non_ds)
            if total_comps > 0:
                lines.append(f"**Component Usage ({total_comps} unique):**")
                lines.extend([
                    f"- Design system coverage: **{coverage}%** ({len(ds_matches)}/{total_comps})",
                    "",
                ])
                if ds_matches:
                    lines.append("**Design System Components Used:**")
                    for comp in sorted(set(ds_matches)):
                        lines.append(f"- {comp}")
                    lines.append("")
                if non_ds:
                    lines.append("**Non-Standard Components (custom):**")
                    for comp in non_ds[:15]:
                        lines.append(f"- {comp}")
                    if len(non_ds) > 15:
                        lines.append(f"- *(+ {len(non_ds) - 15} more)*")
                    lines.append("")
            lines.extend(["---", ""])

        # ADR Summary
        if content.adrs:
            lines.extend(["## Architecture Decision Records", ""])
            for adr in content.adrs:
                lines.extend([
                    f"### ADR-{adr['number']:03d}: {adr['title']}",
                    f"**Status:** {adr['status']}",
                    "",
                    "**Context:**",
                    adr["context"][:500] + ("..." if len(adr["context"]) > 500 else ""),
                    "",
                    "**Decision:**",
                    adr["decision"][:500] + ("..." if len(adr["decision"]) > 500 else ""),
                    "",
                    "**Consequences:**",
                    adr["consequences"][:300] + ("..." if len(adr["consequences"]) > 300 else ""),
                    "",
                ])
            lines.extend(["---", ""])

        # Out of Scope
        lines.extend(["## Out of Scope", ""])
        if content.scope_out:
            for item in content.scope_out:
                lines.append(f"- {item}")
        else:
            lines.append("*No explicit out-of-scope items specified in context document.*")
        lines.extend(["", "---", ""])

        # Import Metadata
        lines.extend(["## Import Metadata", ""])
        lines.extend([
            f"- **Source Feature:** {content.slug}",
            f"- **Product:** {content.product_id}",
            f"- **Organization:** {content.organization}",
            f"- **Imported:** {now.isoformat()}",
            f"- **Target Repo:** {repo_name}",
            f"- **BC Approved:** {'Yes' if content.bc_approved else 'No'}",
        ])
        if content.jira_epic:
            lines.append(f"- **Jira Epic:** {content.jira_epic}")
        lines.extend(["", "---", "", "*Generated by Context Engine spec_export*"])

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
        """Export a context engine feature to spec machine format."""
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
        """Export a context engine feature from path to spec machine format."""
        result = SpecExportResult(
            success=False, source_feature=str(feature_path.name), target_repo=target_repo
        )

        content = self.extract_feature_content(feature_path)
        if not content:
            result.message = f"Could not extract content from {feature_path}"
            return result

        normalized_spec_name = self._normalize_spec_name(spec_name or content.slug)

        target_repo_path = Path(target_repo).expanduser()
        if not target_repo_path.exists():
            result.message = f"Target repo not found: {target_repo}"
            result.errors.append(f"Directory does not exist: {target_repo}")
            return result

        date_prefix = datetime.now().strftime("%Y-%m-%d")
        folder_name = f"{date_prefix}-{normalized_spec_name}"

        if subdir:
            spec_folder = target_repo_path / "spec-machine" / "specs" / subdir / folder_name
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

        try:
            (spec_folder / "planning").mkdir(parents=True, exist_ok=True)
            (spec_folder / "planning" / "visuals").mkdir(exist_ok=True)
            (spec_folder / "implementation").mkdir(exist_ok=True)
            (spec_folder / "verification").mkdir(exist_ok=True)
        except (PermissionError, OSError) as e:
            result.message = f"Failed to create folder structure: {e}"
            result.errors.append(str(e))
            return result

        init_content = self._generate_initialization_md(content, normalized_spec_name)
        init_path = spec_folder / "planning" / "initialization.md"
        try:
            init_path.write_text(init_content)
            result.files_created.append(str(init_path))
        except (IOError, OSError) as e:
            result.errors.append(f"Failed to write initialization.md: {e}")

        repo_name = target_repo_path.name
        req_content = self._generate_requirements_md(content, target_repo_path, repo_name)
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
        """Get a preview of what would be exported for a feature."""
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
