"""
PM-OS CCE ContextDocGenerator (v5.0)

Generates context document v1 drafts from feature information and optional
enriched insight/signal data. Documents follow a standardized template
for consistency across features.

Output Location:
    {feature-folder}/context-docs/v1-draft.md

Usage:
    from pm_os_cce.tools.documents.context_doc_generator import ContextDocGenerator
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
class ContextDocResult:
    """Result of context document generation."""

    success: bool
    file_path: Optional[Path] = None
    version: int = 1
    message: str = ""
    sections_populated: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "file_path": str(self.file_path) if self.file_path else None,
            "version": self.version,
            "message": self.message,
            "sections_populated": self.sections_populated,
        }


@dataclass
class InsightData:
    """Enriched insight/signal data for context doc generation."""

    problem: str = ""
    evidence: List[str] = field(default_factory=list)
    user_segments: List[str] = field(default_factory=list)
    impact: str = ""
    sources: List[str] = field(default_factory=list)
    related_features: List[str] = field(default_factory=list)

    # Discovery enrichment fields
    discovery_findings: List[Dict[str, Any]] = field(default_factory=list)
    confidence_scores: Dict[str, str] = field(default_factory=dict)
    known_risks: List[str] = field(default_factory=list)
    known_technical_context: List[str] = field(default_factory=list)
    prior_decisions: List[str] = field(default_factory=list)

    # Framework enrichment
    recommended_frameworks: List[Dict[str, Any]] = field(default_factory=list)

    # Research enrichment fields
    competitor_analysis: str = ""
    market_validation: str = ""
    experiment_history: str = ""
    user_flow_analysis: str = ""
    code_dependencies: str = ""
    service_impact: str = ""
    past_discussions_summary: str = ""
    research_document_path: str = ""

    # Design system & codebase enrichment
    design_system_context: str = ""
    code_architecture: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InsightData":
        """Create InsightData from dictionary."""
        return cls(
            problem=data.get("problem", ""),
            evidence=data.get("evidence", []),
            user_segments=data.get("user_segments", []),
            impact=data.get("impact", ""),
            sources=data.get("sources", []),
            related_features=data.get("related_features", []),
            discovery_findings=data.get("discovery_findings", []),
            confidence_scores=data.get("confidence_scores", {}),
            known_risks=data.get("known_risks", []),
            known_technical_context=data.get("known_technical_context", []),
            prior_decisions=data.get("prior_decisions", []),
            recommended_frameworks=data.get("recommended_frameworks", []),
            competitor_analysis=data.get("competitor_analysis", ""),
            market_validation=data.get("market_validation", ""),
            experiment_history=data.get("experiment_history", ""),
            user_flow_analysis=data.get("user_flow_analysis", ""),
            code_dependencies=data.get("code_dependencies", ""),
            service_impact=data.get("service_impact", ""),
            past_discussions_summary=data.get("past_discussions_summary", ""),
            research_document_path=data.get("research_document_path", ""),
            design_system_context=data.get("design_system_context", ""),
            code_architecture=data.get("code_architecture", ""),
        )

    @classmethod
    def from_discovery_result(cls, discovery_result) -> "InsightData":
        """Create InsightData from a DiscoveryResult."""
        findings_dicts = [f.to_dict() for f in discovery_result.findings]
        confidence_map = {
            f.source_ref: f.confidence.value for f in discovery_result.findings
        }

        known_risks = []
        known_technical = []
        prior_decisions = []
        evidence = []
        related = list(discovery_result.related_features)

        for finding in discovery_result.findings:
            if finding.category.value == "risk":
                known_risks.append(finding.content)
            elif finding.category.value == "technical":
                known_technical.append(finding.content)
            elif finding.category.value == "decision":
                prior_decisions.append(finding.content)
            if finding.confidence.value in ("high", "medium"):
                evidence.append(f"[{finding.source_type}] {finding.title}")

        sources = list(discovery_result.sources_searched)

        return cls(
            evidence=evidence,
            sources=sources,
            related_features=related,
            discovery_findings=findings_dicts,
            confidence_scores=confidence_map,
            known_risks=known_risks,
            known_technical_context=known_technical,
            prior_decisions=prior_decisions,
        )


# Default success metrics templates by product type
DEFAULT_METRICS_BY_TYPE = {
    "brand": [
        "Conversion rate improvement",
        "User satisfaction score (NPS/CSAT)",
        "Feature adoption rate",
        "Support ticket reduction",
    ],
    "product": [
        "Monthly active users (MAU)",
        "Feature engagement rate",
        "Task completion rate",
        "Time to value",
    ],
    "feature": [
        "Feature adoption rate",
        "Task success rate",
        "Error rate reduction",
        "User satisfaction",
    ],
    "project": [
        "Project completion on time",
        "Stakeholder satisfaction",
        "Deliverable quality score",
        "Budget adherence",
    ],
}


class ContextDocGenerator:
    """
    Generates context document v1 drafts from feature information and insights.

    Creates standardized context documents that serve as the foundation
    for feature development.
    """

    def __init__(self, user_path: Optional[Path] = None):
        """
        Initialize the context document generator.

        Args:
            user_path: Path to user/ directory. If None, resolved via config.
        """
        self._config = get_config()
        if user_path:
            self._user_path = user_path
        else:
            paths = get_paths()
            self._user_path = paths.user

    def _get_user_info(self) -> Dict[str, str]:
        """Get user information from config."""
        return {
            "name": self._config.get("user.name", "PM"),
            "email": self._config.get("user.email", ""),
            "position": self._config.get("user.position", "Product Manager"),
        }

    def _get_product_info(self, product_id: str) -> Dict[str, Any]:
        """Get product information from config."""
        items = self._config.get("products.items", [])
        for product in items:
            if isinstance(product, dict) and product.get("id") == product_id:
                return product
        return {}

    def _get_stakeholders(self, product_id: str) -> List[Dict[str, str]]:
        """Get stakeholders for a product from config."""
        stakeholders = []
        user_info = self._get_user_info()
        product_info = self._get_product_info(product_id)

        stakeholders.append(
            {
                "role": "Owner",
                "name": user_info["name"],
                "responsibility": "Overall accountability",
            }
        )

        squad_name = product_info.get("squad", "")
        reports = self._config.get("team.reports", [])
        for report in reports:
            if isinstance(report, dict) and report.get("squad") == squad_name:
                stakeholders.append(
                    {
                        "role": "Product Lead",
                        "name": report.get("name", ""),
                        "responsibility": f"Product decisions for {squad_name}",
                    }
                )
                break

        eng_stakeholders = self._config.get("team.stakeholders", [])
        for stakeholder in eng_stakeholders:
            if isinstance(stakeholder, dict):
                if stakeholder.get("relationship") == "leadership_partner":
                    if "Engineering" in stakeholder.get("role", ""):
                        stakeholders.append(
                            {
                                "role": "Engineering Lead",
                                "name": stakeholder.get("name", ""),
                                "responsibility": "Technical feasibility and implementation",
                            }
                        )
                        break

        return stakeholders

    def _get_suggested_metrics(
        self, product_type: str = "brand", insight: Optional[InsightData] = None
    ) -> List[str]:
        """Get suggested success metrics based on product type and insight."""
        base_metrics = DEFAULT_METRICS_BY_TYPE.get(
            product_type, DEFAULT_METRICS_BY_TYPE["brand"]
        )
        if insight and insight.impact:
            return [f"Impact metric: {insight.impact}"] + base_metrics[:3]
        return base_metrics

    def _generate_user_stories(
        self, insight: Optional[InsightData] = None, feature_title: str = ""
    ) -> str:
        """Generate user stories section from insight data."""
        if not insight or not insight.user_segments:
            return """*User stories will be generated during context refinement.*

Example format:
- As a [user type], I want to [action] so that [benefit]
"""
        stories = []
        for segment in insight.user_segments[:5]:
            stories.append(
                f"- As a **{segment}**, I want to [action TBD] "
                f"so that [benefit TBD]"
            )
        return (
            "\n".join(stories)
            + "\n\n*Refine these user stories during context iteration.*"
        )

    def _generate_problem_statement(
        self, insight: Optional[InsightData] = None, feature_title: str = ""
    ) -> str:
        """Generate problem statement from insight or placeholder."""
        if insight and insight.problem:
            statement = insight.problem
            if insight.evidence:
                statement += "\n\n**Supporting Evidence:**\n"
                for evidence in insight.evidence[:5]:
                    statement += f"- {evidence}\n"
            if insight.sources:
                statement += "\n**Sources:** " + ", ".join(insight.sources)
            return statement

        return f"""*Define the problem that "{feature_title}" will solve.*

Consider:
- Who is affected by this problem?
- What is the current state vs. desired state?
- What evidence supports this problem exists?
- What is the cost of not solving it?
"""

    def _get_design_context(self, product_id: Optional[str] = None):
        """Get unified design context via DesignContextProvider."""
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
            provider = DesignContextProvider(
                product_id, user_path=str(self._user_path)
            )
            return provider.get_context()
        except Exception as exc:
            logger.warning("DesignContextProvider failed: %s", exc)
            return None

    def _get_components_summary(self, product_id: Optional[str] = None) -> str:
        """Get summary of available design system components."""
        ctx = self._get_design_context(product_id)
        if not ctx or not ctx.components:
            return ""

        by_category: Dict[str, List[str]] = {}
        for comp in ctx.components:
            platforms = list(comp.platforms.keys())
            platform_str = "/".join(
                {"web": "Web", "rn": "RN"}.get(p, p) for p in sorted(platforms)
            )
            by_category.setdefault(comp.category, []).append(
                f"{comp.name} ({platform_str})"
            )

        if not by_category:
            return ""

        lines = [
            "\n### Available Design System Components\n",
            f"*{sum(len(v) for v in by_category.values())} components synced.*\n",
        ]
        for category in sorted(by_category.keys()):
            comps = sorted(by_category[category])
            lines.append(
                f"- **{category}**: {', '.join(comps[:8])}"
                + (f" (+{len(comps)-8} more)" if len(comps) > 8 else "")
            )
        lines.append(
            "\n*See `brain/Entities/Components/` for mapping details.*"
        )
        return "\n".join(lines)

    def _build_technical_section(
        self,
        insight: Optional[InsightData],
        product_id: Optional[str] = None,
    ) -> str:
        """Build Technical Considerations from discovery data, repo profiles, or placeholder."""
        parts = []

        if insight and insight.known_technical_context:
            lines = []
            for ctx in insight.known_technical_context:
                first_line = ctx.split("\n")[0].strip()
                if first_line:
                    lines.append(f"- {first_line}")
            if lines:
                parts.append(
                    "\n".join(lines)
                    + "\n\n*Discovered from Brain entities. "
                    "Verify and expand during engineering review.*"
                )

        design_ctx = self._get_design_context(product_id)
        if design_ctx and design_ctx.repo_profiles:
            repo_lines = ["\n### Repository Tech Stack\n"]
            for rp in design_ctx.repo_profiles:
                repo_name = rp.get("name", "Unknown")
                repo_lines.append(f"**{repo_name}**")
                tech = rp.get("tech_stack", {})
                if tech:
                    for key, val in tech.items():
                        repo_lines.append(f"- {key}: {val}")
                lang = rp.get("primary_language", "")
                if lang and "Language" not in tech:
                    repo_lines.append(f"- Language: {lang}")
                deps = rp.get("key_deps", [])
                if deps:
                    repo_lines.append(f"- Key deps: {', '.join(deps[:5])}")
                repo_lines.append("")
            parts.append("\n".join(repo_lines))

        if design_ctx and design_ctx.repo_profiles:
            deep_profiles = [
                rp for rp in design_ctx.repo_profiles if rp.get("has_deep_analysis")
            ]
            if deep_profiles:
                codebase_lines = ["\n### Relevant Existing Components in Codebase\n"]
                for rp in deep_profiles:
                    repo_name = rp.get("name", "Unknown")
                    arch = rp.get("architecture", "")
                    if arch:
                        codebase_lines.append(f"**{repo_name}** -- {arch}")
                    total_feat = rp.get("total_features", 0)
                    if total_feat:
                        codebase_lines.append(f"- {total_feat} feature modules")
                    routing = rp.get("routing_type", "")
                    if routing:
                        codebase_lines.append(f"- Routing: {routing}")
                    services = rp.get("services", [])
                    if services:
                        svc_names = [s["name"] for s in services[:8]]
                        codebase_lines.append(
                            f"- Key services: {', '.join(svc_names)}"
                        )
                        if len(services) > 8:
                            codebase_lines.append(
                                f"  *(+ {len(services) - 8} more)*"
                            )
                    ff_provider = rp.get("feature_flag_provider", "")
                    if ff_provider:
                        codebase_lines.append(f"- Feature flags: {ff_provider}")
                    codebase_lines.append("")
                parts.append("\n".join(codebase_lines))

        if insight and insight.code_architecture:
            parts.append(f"\n### Codebase Architecture\n\n{insight.code_architecture}")

        if not parts:
            parts.append(
                "- TBD\n"
                "- *Technical considerations will be identified during "
                "engineering review.*"
            )

        components_summary = self._get_components_summary(product_id)
        if components_summary:
            parts.append(components_summary)

        return "\n".join(parts)

    def _build_design_system_section(
        self,
        insight: Optional[InsightData],
        product_id: Optional[str] = None,
        figma_url: Optional[str] = None,
    ) -> str:
        """Build Design System section with component mapping, brand tokens, Figma URL."""
        design_ctx = self._get_design_context(product_id)
        if not design_ctx:
            return ""

        parts = []

        if design_ctx.token_summary:
            ts = design_ctx.token_summary
            parts.append("### Brand Tokens\n")
            token_lines = []
            if ts.get("brand_name"):
                token_lines.append(f"- **Brand:** {ts['brand_name']}")
            if ts.get("primary_color"):
                token_lines.append(f"- **Primary:** {ts['primary_color']}")
            if ts.get("secondary_color"):
                token_lines.append(f"- **Secondary:** {ts['secondary_color']}")
            if ts.get("font_family"):
                token_lines.append(f"- **Font:** {ts['font_family']}")
            if ts.get("font_family_heading") and ts.get("font_family_heading") != ts.get("font_family"):
                token_lines.append(f"- **Heading Font:** {ts['font_family_heading']}")
            if ts.get("border_radius"):
                token_lines.append(f"- **Border Radius:** {ts['border_radius']}")
            if token_lines:
                parts.append("\n".join(token_lines))
                parts.append("")

        if design_ctx.component_mapping_table:
            parts.append("### Component Mapping\n")
            parts.append(design_ctx.component_mapping_table)
            parts.append("")

        if figma_url:
            parts.append(f"### Figma\n\n[Design File]({figma_url})\n")

        if insight and insight.design_system_context:
            parts.append(f"### Design System Alignment\n\n{insight.design_system_context}\n")

        if not parts:
            return ""
        return "\n".join(parts)

    def _build_risks_section(self, insight: Optional[InsightData]) -> str:
        """Build Risks and Mitigations table from discovery data or placeholder."""
        if insight and insight.known_risks:
            table = (
                "| Risk | Likelihood | Impact | Mitigation |\n"
                "|------|------------|--------|------------|\n"
            )
            for risk in insight.known_risks:
                first_line = risk.split("\n")[0].strip()
                if first_line:
                    table += f"| {first_line} | TBD | TBD | TBD |\n"
            return table + (
                "\n*Risks discovered from Brain entities. "
                "Assess likelihood/impact during context iteration.*"
            )
        return (
            "| Risk | Likelihood | Impact | Mitigation |\n"
            "|------|------------|--------|------------|\n"
            "| *Identify during context refinement* | - | - | - |"
        )

    def _build_open_questions_section(
        self, insight: Optional[InsightData]
    ) -> str:
        """Build Open Questions from discovery gaps or placeholder."""
        questions = []

        if insight and insight.prior_decisions:
            questions.append("**Prior Decisions (from Brain):**")
            for decision in insight.prior_decisions[:5]:
                first_line = decision.split("\n")[0].strip()
                if first_line:
                    questions.append(f"- {first_line}")
            questions.append("")

        if not questions:
            return "1. *Questions from orthogonal challenge will go here*"

        questions.append(
            "*Additional questions from orthogonal challenge will be added.*"
        )
        return "\n".join(questions)

    def _build_frameworks_section(
        self,
        feature_title: str,
        insight: Optional[InsightData],
    ) -> str:
        """Build Recommended Frameworks section from matcher or insight data."""
        frameworks = []

        if insight and insight.recommended_frameworks:
            frameworks = insight.recommended_frameworks
        else:
            try:
                from pm_os_cce.tools.reasoning.framework_matcher import FrameworkMatcher
            except ImportError:
                try:
                    from reasoning.framework_matcher import FrameworkMatcher
                except ImportError:
                    FrameworkMatcher = None

            if FrameworkMatcher is not None:
                try:
                    matcher = FrameworkMatcher(
                        brain_path=self._user_path / "brain"
                    )
                    if matcher.available:
                        frameworks = matcher.match(feature_title, top_k=3)
                except Exception as e:
                    logger.debug("Framework matching unavailable: %s", e)

        if not frameworks:
            return ""

        lines = ["\n## Recommended Frameworks\n"]
        lines.append("*Matched from PM framework library.*\n")
        for fw in frameworks[:3]:
            name = fw.get("framework_name", fw.get("name", ""))
            author = fw.get("author", "")
            use_case = fw.get("use_case", "")
            score = fw.get("relevance_score", 0)
            steps = fw.get("key_steps_summary", "")

            lines.append(f"### {name}")
            if author:
                lines.append(f"**Author:** {author} | **Relevance:** {score:.0%}")
            if use_case:
                lines.append(f"\n{use_case[:200]}")
            if steps:
                lines.append(f"\n**Key steps:** {steps[:200]}")
            lines.append("")

        lines.append("*Use `/framework-search` to explore more frameworks.*\n")
        return "\n".join(lines)

    def _build_related_features_section(
        self, insight: Optional[InsightData]
    ) -> str:
        """Build Related Features section from discovery data."""
        if not insight or not insight.related_features:
            return ""

        lines = ["\n## Related Features\n"]
        for feature in insight.related_features[:10]:
            lines.append(f"- {feature}")
        lines.append(
            "\n*Related features found. Consider dependencies and shared scope.*\n"
        )
        return "\n".join(lines)

    def generate_v1(
        self, feature_path: Path, insight: Optional[Dict[str, Any]] = None
    ) -> ContextDocResult:
        """
        Generate a v1 context document for an existing feature.

        Reads feature-state.yaml to get feature info and generates
        the context document at {feature-path}/context-docs/v1-draft.md.
        """
        try:
            from pm_os_cce.tools.feature.feature_state import FeatureState, TrackStatus
        except ImportError:
            from feature.feature_state import FeatureState, TrackStatus

        state = FeatureState.load(feature_path)
        if not state:
            return ContextDocResult(
                success=False,
                message=f"Feature state not found at {feature_path}/feature-state.yaml",
            )

        product_info = self._get_product_info(state.product_id)
        product_name = product_info.get("name", state.product_id)
        product_type = product_info.get("type", "brand")

        insight_data = InsightData.from_dict(insight) if insight else None

        result = self.generate_v1_from_info(
            feature_title=state.title,
            product_id=state.product_id,
            product_name=product_name,
            product_type=product_type,
            feature_path=feature_path,
            insight=insight_data,
        )

        if result.success:
            state.update_track(
                "context",
                status=TrackStatus.IN_PROGRESS,
                current_version=1,
                current_step="v1_draft",
                file="context-docs/v1-draft.md",
            )
            state.save(feature_path)

        return result

    def generate_v1_from_info(
        self,
        feature_title: str,
        product_id: str,
        product_name: str,
        feature_path: Path,
        product_type: str = "brand",
        insight: Optional[InsightData] = None,
    ) -> ContextDocResult:
        """Generate a v1 context document from explicit feature information."""
        context_docs_dir = feature_path / "context-docs"
        context_docs_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")

        stakeholders = self._get_stakeholders(product_id)
        metrics = self._get_suggested_metrics(product_type, insight)

        problem_statement = self._generate_problem_statement(insight, feature_title)
        user_stories = self._generate_user_stories(insight, feature_title)

        has_discovery = insight is not None and bool(insight.discovery_findings)

        sections_populated = {
            "problem_statement": insight is not None and bool(insight.problem),
            "success_metrics": False,
            "scope": False,
            "stakeholders": len(stakeholders) > 1,
            "user_stories": insight is not None and bool(insight.user_segments),
            "technical_considerations": has_discovery and bool(
                insight.known_technical_context if insight else []
            ),
            "risks": has_discovery and bool(
                insight.known_risks if insight else []
            ),
            "open_questions": False,
        }

        # Merge discovered stakeholders
        if has_discovery:
            seen_names = {s["name"].lower() for s in stakeholders}
            for finding in insight.discovery_findings:
                if finding.get("category") == "stakeholder":
                    name = finding.get("title", "")
                    if name.lower() not in seen_names:
                        stakeholders.append({
                            "role": "Discovered",
                            "name": name,
                            "responsibility": "Related (from Brain)",
                        })
                        seen_names.add(name.lower())
            if len(stakeholders) > 1:
                sections_populated["stakeholders"] = True

        # Build stakeholders table
        stakeholders_table = (
            "| Role | Name | Responsibility |\n|------|------|----------------|\n"
        )
        for s in stakeholders:
            stakeholders_table += (
                f"| {s['role']} | {s['name']} | {s['responsibility']} |\n"
            )

        # Build metrics checklist
        metrics_checklist = ""
        for metric in metrics:
            metrics_checklist += f"- [ ] {metric}\n"

        feature_slug = feature_path.name

        # Generate enriched sections
        technical_section = self._build_technical_section(insight, product_id)
        risks_section = self._build_risks_section(insight)
        open_questions_section = self._build_open_questions_section(insight)
        related_features_section = self._build_related_features_section(insight)
        frameworks_section = self._build_frameworks_section(feature_title, insight)
        sections_populated["recommended_frameworks"] = bool(frameworks_section)

        # Build design system section
        figma_url = None
        if insight and insight.research_document_path:
            try:
                from pm_os_cce.tools.feature.feature_state import FeatureState
            except ImportError:
                try:
                    from feature.feature_state import FeatureState
                except ImportError:
                    FeatureState = None
            if FeatureState is not None:
                try:
                    fs = FeatureState.load(feature_path)
                    if fs and hasattr(fs, "artifacts"):
                        figma_url = fs.artifacts.get("figma")
                except Exception:
                    pass

        design_system_section = self._build_design_system_section(
            insight, product_id, figma_url
        )
        sections_populated["design_system"] = bool(design_system_section)

        # Build research sections conditionally
        research_sections = ""
        research_tracking = {
            "competitor_analysis": False,
            "market_validation": False,
            "experiment_history": False,
            "user_flow_analysis": False,
            "service_dependencies": False,
        }

        if insight:
            if insight.competitor_analysis:
                research_sections += f"\n## Competitor Analysis\n\n{insight.competitor_analysis}\n"
                research_tracking["competitor_analysis"] = True
            if insight.market_validation:
                research_sections += f"\n## Market Validation\n\n{insight.market_validation}\n"
                research_tracking["market_validation"] = True
            if insight.experiment_history:
                research_sections += f"\n## Experiment History\n\n{insight.experiment_history}\n"
                research_tracking["experiment_history"] = True
            if insight.user_flow_analysis:
                research_sections += f"\n## User Flow Analysis\n\n{insight.user_flow_analysis}\n"
                research_tracking["user_flow_analysis"] = True
            if insight.code_dependencies or insight.service_impact:
                deps_content = ""
                if insight.code_dependencies:
                    deps_content += f"### Code Dependencies\n\n{insight.code_dependencies}\n\n"
                if insight.service_impact:
                    deps_content += f"### Service Impact\n\n{insight.service_impact}\n"
                research_sections += f"\n## Service Dependencies\n\n{deps_content}"
                research_tracking["service_dependencies"] = True
            if insight.past_discussions_summary:
                research_sections += f"\n## Past Discussions Summary\n\n{insight.past_discussions_summary}\n"
            if insight.research_document_path:
                research_sections += f"\n*Full research report: `{insight.research_document_path}`*\n"

        sections_populated.update(research_tracking)

        # Generate the document content
        content = f"""# Context Document: {feature_title}

**Slug:** `{feature_slug}`
**Version:** 1 (Draft)
**Status:** Pending Review
**Created:** {date_str}
**Product:** {product_name}

## Problem Statement

{problem_statement}

## Success Metrics

{metrics_checklist}
*Metrics to be refined during context iteration.*

## Scope

### In Scope

- TBD

### Out of Scope

- TBD

## Stakeholders

{stakeholders_table}

## User Stories

{user_stories}

## Technical Considerations

{technical_section}
{f'''
## Design System

{design_system_section}
''' if design_system_section else ""}
## Risks and Mitigations

{risks_section}

## Open Questions

{open_questions_section}
{frameworks_section}{related_features_section}{research_sections}
---
*Generated by Context Creation Engine | Ready for orthogonal challenge*
"""

        output_path = context_docs_dir / "v1-draft.md"
        try:
            output_path.write_text(content)
        except (IOError, OSError) as e:
            return ContextDocResult(
                success=False, message=f"Failed to write context document: {e}"
            )

        return ContextDocResult(
            success=True,
            file_path=output_path,
            version=1,
            message=f"Context document v1 generated at {output_path}",
            sections_populated=sections_populated,
        )

    def get_document_path(self, feature_path: Path, version: int = 1) -> Path:
        """Get the path to a context document version."""
        version_map = {
            1: "v1-draft.md",
            2: "v2-revised.md",
            3: "v3-final.md",
        }
        filename = version_map.get(version, f"v{version}-draft.md")
        return feature_path / "context-docs" / filename

    def document_exists(self, feature_path: Path, version: int = 1) -> bool:
        """Check if a context document version exists."""
        return self.get_document_path(feature_path, version).exists()
