"""
PM-OS CCE ResearchInsightBridge (v5.0)

Converts research results to InsightData for context document generation.
Maps QuestionnaireResult and ResearchSwarmResult into InsightData fields
that feed the ContextDocGenerator.

Usage:
    from pm_os_cce.tools.research.research_insight_bridge import ResearchInsightBridge
"""

import logging
from typing import Any, Dict, List, Optional

try:
    from pm_os_cce.tools.research.deep_research_swarm import (
        ResearchSwarmResult,
        ResearchTaskResult,
    )
except ImportError:
    from research.deep_research_swarm import (
        ResearchSwarmResult,
        ResearchTaskResult,
    )

try:
    from pm_os_cce.tools.research.discovery_questionnaire import QuestionnaireResult
except ImportError:
    from research.discovery_questionnaire import QuestionnaireResult

try:
    from pm_os_cce.tools.research.research_plan_generator import ResearchSource
except ImportError:
    from research.research_plan_generator import ResearchSource

# InsightData lives in the documents subpackage (context_doc_generator)
# Import with fallback since it may not yet be ported
try:
    from pm_os_cce.tools.documents.context_doc_generator import InsightData
except ImportError:
    try:
        from documents.context_doc_generator import InsightData
    except ImportError:
        # Provide a minimal stub so the module can load without context_doc_generator
        from dataclasses import dataclass, field

        @dataclass
        class InsightData:  # type: ignore[no-redef]
            """Minimal stub for InsightData when context_doc_generator is unavailable."""
            problem: str = ""
            evidence: List[str] = field(default_factory=list)
            user_segments: List[str] = field(default_factory=list)
            impact: str = ""
            sources: List[str] = field(default_factory=list)
            related_features: List[str] = field(default_factory=list)
            competitor_analysis: str = ""
            market_validation: str = ""
            experiment_history: str = ""
            user_flow_analysis: str = ""
            code_dependencies: str = ""
            service_impact: str = ""
            past_discussions_summary: str = ""
            design_system_context: str = ""
            code_architecture: str = ""

logger = logging.getLogger(__name__)


class ResearchInsightBridge:
    """
    Converts QuestionnaireResult and ResearchSwarmResult into InsightData.

    The bridge extracts structured information from raw research findings
    and maps it into InsightData fields that the ContextDocGenerator
    understands.
    """

    def convert_to_insight(
        self,
        questionnaire: QuestionnaireResult,
        swarm_result: Optional[ResearchSwarmResult] = None,
    ) -> InsightData:
        """
        Convert questionnaire answers and research findings to InsightData.

        Args:
            questionnaire: Structured answers from the discovery questionnaire
            swarm_result: Optional results from the research swarm execution

        Returns:
            InsightData populated with questionnaire and research data
        """
        insight = InsightData(
            problem=questionnaire.user_problem or "",
            evidence=self._build_evidence(questionnaire),
            user_segments=[questionnaire.users] if questionnaire.users else [],
            impact=questionnaire.business_problem or "",
            sources=["questionnaire"],
        )

        if not swarm_result:
            return insight

        # Populate research enrichment fields
        insight.competitor_analysis = self._extract_competitors(swarm_result)
        insight.market_validation = self._extract_market_validation(swarm_result)
        insight.experiment_history = self._extract_experiments(swarm_result)
        insight.user_flow_analysis = self._extract_user_flows(swarm_result)
        insight.code_dependencies = self._extract_dependencies(swarm_result)
        insight.service_impact = self._extract_service_impact(swarm_result)
        insight.past_discussions_summary = self._extract_discussions(swarm_result)

        # Design system & codebase enrichment
        insight.design_system_context = self._extract_design_system(swarm_result)
        insight.code_architecture = self._extract_code_architecture(swarm_result)

        # Add research sources
        for task_result in swarm_result.task_results:
            if task_result.success:
                source_name = f"research:{task_result.source.value}"
                if source_name not in insight.sources:
                    insight.sources.append(source_name)

        # Add related features from Brain findings
        brain_results = [
            r for r in swarm_result.task_results
            if r.source == ResearchSource.BRAIN and r.success
        ]
        for result in brain_results:
            for finding in result.findings:
                title = finding.get("title", finding.get("name", ""))
                if title and title not in insight.related_features:
                    insight.related_features.append(title)

        return insight

    @staticmethod
    def _build_evidence(questionnaire: QuestionnaireResult) -> List[str]:
        """Build evidence list from questionnaire answers."""
        evidence = []
        if questionnaire.business_problem:
            evidence.append(f"Business problem: {questionnaire.business_problem}")
        if questionnaire.user_problem:
            evidence.append(f"User problem: {questionnaire.user_problem}")
        if questionnaire.competitors:
            evidence.append(
                f"Competitors: {', '.join(questionnaire.competitors)}"
            )
        return evidence

    @staticmethod
    def _extract_competitors(swarm_result: ResearchSwarmResult) -> str:
        """Extract competitor analysis from web/external research tasks."""
        sections = []
        for result in swarm_result.task_results:
            if not result.success:
                continue
            if result.source in (ResearchSource.WEB, ResearchSource.GEMINI_DEEP_RESEARCH):
                for finding in result.findings:
                    content = finding.get("content", "")
                    if isinstance(content, str) and content:
                        lower = content.lower()
                        if any(
                            term in lower
                            for term in ["competitor", "vs", "comparison", "alternative"]
                        ):
                            sections.append(content[:1000])
        return "\n\n".join(sections) if sections else ""

    @staticmethod
    def _extract_market_validation(swarm_result: ResearchSwarmResult) -> str:
        """Extract market validation from external research tasks."""
        sections = []
        for result in swarm_result.task_results:
            if not result.success:
                continue
            if result.source in (ResearchSource.WEB, ResearchSource.GEMINI_DEEP_RESEARCH):
                for finding in result.findings:
                    content = finding.get("content", "")
                    if isinstance(content, str) and content:
                        lower = content.lower()
                        if any(
                            term in lower
                            for term in ["market", "validation", "demand", "trend", "industry"]
                        ):
                            sections.append(content[:1000])
        return "\n\n".join(sections) if sections else ""

    @staticmethod
    def _extract_experiments(swarm_result: ResearchSwarmResult) -> str:
        """Extract experiment history from Statsig and internal findings."""
        experiments = []
        for result in swarm_result.task_results:
            if not result.success:
                continue
            if result.source == ResearchSource.STATSIG:
                for finding in result.findings:
                    name = finding.get("name", finding.get("title", ""))
                    status = finding.get("status", "")
                    if name:
                        experiments.append(f"- **{name}**: {status}")
        return "\n".join(experiments) if experiments else ""

    @staticmethod
    def _extract_user_flows(swarm_result: ResearchSwarmResult) -> str:
        """Extract user flow analysis from GitHub code search results."""
        flows = []
        for result in swarm_result.task_results:
            if not result.success:
                continue
            if result.source == ResearchSource.GITHUB:
                for finding in result.findings:
                    title = finding.get("title", "")
                    url = finding.get("url", finding.get("html_url", ""))
                    if title:
                        if url:
                            flows.append(f"- [{title}]({url})")
                        else:
                            flows.append(f"- {title}")
        return "\n".join(flows) if flows else ""

    @staticmethod
    def _extract_dependencies(swarm_result: ResearchSwarmResult) -> str:
        """Extract code dependencies from GitHub results."""
        deps = []
        for result in swarm_result.task_results:
            if not result.success:
                continue
            if result.source == ResearchSource.GITHUB:
                for finding in result.findings:
                    title = finding.get("title", "")
                    ftype = finding.get("type", "")
                    if title and ftype in ("code", "file", "service"):
                        deps.append(f"- {title}")
        return "\n".join(deps) if deps else ""

    @staticmethod
    def _extract_service_impact(swarm_result: ResearchSwarmResult) -> str:
        """Extract service impact from Jira and GitHub results."""
        impacts = []
        for result in swarm_result.task_results:
            if not result.success:
                continue
            if result.source == ResearchSource.JIRA:
                for finding in result.findings:
                    key = finding.get("key", "")
                    summary = finding.get("summary", finding.get("title", ""))
                    if key and summary:
                        impacts.append(f"- **{key}**: {summary}")
        return "\n".join(impacts) if impacts else ""

    @staticmethod
    def _extract_discussions(swarm_result: ResearchSwarmResult) -> str:
        """Extract past discussions from Slack and Confluence."""
        discussions = []
        for result in swarm_result.task_results:
            if not result.success:
                continue
            if result.source == ResearchSource.SLACK:
                for finding in result.findings:
                    text = finding.get("text", finding.get("content", ""))
                    channel = finding.get("channel", "")
                    if text:
                        preview = text[:200]
                        discussions.append(
                            f"- **#{channel}**: {preview}" if channel else f"- {preview}"
                        )
            elif result.source == ResearchSource.CONFLUENCE:
                for finding in result.findings:
                    title = finding.get("title", "")
                    url = finding.get("url", "")
                    if title:
                        if url:
                            discussions.append(f"- [{title}]({url})")
                        else:
                            discussions.append(f"- {title}")
        return "\n".join(discussions) if discussions else ""

    @staticmethod
    def _extract_design_system(swarm_result: ResearchSwarmResult) -> str:
        """Extract design system context from codebase research findings."""
        lines = []
        for result in swarm_result.task_results:
            if not result.success:
                continue
            if result.source == ResearchSource.CODEBASE:
                for finding in result.findings:
                    if finding.get("type") == "design_system":
                        lines.append(f"- {finding.get('content', '')}")
        return "\n".join(lines) if lines else ""

    @staticmethod
    def _extract_code_architecture(swarm_result: ResearchSwarmResult) -> str:
        """Extract codebase architecture from repo profile findings."""
        lines = []
        for result in swarm_result.task_results:
            if not result.success:
                continue
            if result.source == ResearchSource.CODEBASE:
                for finding in result.findings:
                    if finding.get("type") == "repo_profile":
                        title = finding.get("title", "Unknown")
                        highlighted = " **(target repo)**" if finding.get("highlighted") else ""
                        content = finding.get("content", "")[:300]
                        lines.append(f"**{title}**{highlighted}\n{content}")
        return "\n\n".join(lines) if lines else ""
