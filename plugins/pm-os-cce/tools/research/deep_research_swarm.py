"""
PM-OS CCE DeepResearchSwarm (v5.0)

Executes approved research plans across multiple internal and external sources.
Given a ResearchPlan, runs two-pass task execution (broad discovery then
targeted follow-up), synthesizes findings into a structured research document,
and optionally persists high-confidence findings to Brain.

Usage:
    from pm_os_cce.tools.research.deep_research_swarm import (
        DeepResearchSwarm, ResearchSwarmResult
    )
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

try:
    from pm_os_cce.tools.research.research_plan_generator import (
        ResearchPlan,
        ResearchSource,
        ResearchTask,
    )
except ImportError:
    from research.research_plan_generator import (
        ResearchPlan,
        ResearchSource,
        ResearchTask,
    )

# Brain plugin is OPTIONAL
HAS_BRAIN = False
try:
    from pm_os_brain.tools.brain.brain_entity_creator import BrainEntityCreator
    HAS_BRAIN = True
except ImportError:
    try:
        from brain.brain_entity_creator import BrainEntityCreator
        HAS_BRAIN = True
    except ImportError:
        pass

logger = logging.getLogger(__name__)


# ============================================================================
# DATA STRUCTURES
# ============================================================================


@dataclass
class ResearchTaskResult:
    """Result of executing a single research task."""

    task_id: str
    source: ResearchSource
    success: bool
    findings: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    raw_data: Optional[Any] = None
    execution_seconds: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "task_id": self.task_id,
            "source": self.source.value,
            "success": self.success,
            "findings": self.findings,
            "summary": self.summary,
            "execution_seconds": self.execution_seconds,
        }
        if self.error:
            result["error"] = self.error
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchTaskResult":
        return cls(
            task_id=data["task_id"],
            source=ResearchSource(data["source"]),
            success=data.get("success", False),
            findings=data.get("findings", []),
            summary=data.get("summary", ""),
            execution_seconds=data.get("execution_seconds", 0.0),
            error=data.get("error"),
        )


@dataclass
class ResearchSwarmResult:
    """Complete result of a research swarm execution."""

    plan: ResearchPlan
    task_results: List[ResearchTaskResult] = field(default_factory=list)
    internal_synthesis: str = ""
    external_synthesis: str = ""
    combined_document: str = ""
    quality_score: float = 0.0
    challenge_feedback: Optional[str] = None
    total_execution_seconds: float = 0.0
    total_findings: int = 0
    completed_at: datetime = field(default_factory=datetime.now)

    @property
    def successful_tasks(self) -> List[ResearchTaskResult]:
        return [r for r in self.task_results if r.success]

    @property
    def failed_tasks(self) -> List[ResearchTaskResult]:
        return [r for r in self.task_results if not r.success]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan": self.plan.to_dict(),
            "task_results": [r.to_dict() for r in self.task_results],
            "internal_synthesis": self.internal_synthesis,
            "external_synthesis": self.external_synthesis,
            "combined_document": self.combined_document,
            "quality_score": self.quality_score,
            "challenge_feedback": self.challenge_feedback,
            "total_execution_seconds": self.total_execution_seconds,
            "total_findings": self.total_findings,
            "completed_at": self.completed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchSwarmResult":
        return cls(
            plan=ResearchPlan.from_dict(data.get("plan", {})),
            task_results=[
                ResearchTaskResult.from_dict(r)
                for r in data.get("task_results", [])
            ],
            internal_synthesis=data.get("internal_synthesis", ""),
            external_synthesis=data.get("external_synthesis", ""),
            combined_document=data.get("combined_document", ""),
            quality_score=data.get("quality_score", 0.0),
            challenge_feedback=data.get("challenge_feedback"),
            total_execution_seconds=data.get("total_execution_seconds", 0.0),
            total_findings=data.get("total_findings", 0),
            completed_at=datetime.fromisoformat(
                data.get("completed_at", datetime.now().isoformat())
            ),
        )


# ============================================================================
# SOURCE HANDLERS
# ============================================================================


def _handle_brain(task: ResearchTask) -> ResearchTaskResult:
    """Execute a Brain search task."""
    start = time.time()
    try:
        from documents.research_aggregator import search_brain

        findings = search_brain(task.query, limit=10)
        elapsed = time.time() - start
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=True,
            findings=findings,
            summary=f"Found {len(findings)} Brain entities related to query",
            execution_seconds=elapsed,
        )
    except Exception as e:
        elapsed = time.time() - start
        logger.warning(f"Brain task {task.id} failed: {e}")
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=False,
            error=str(e),
            execution_seconds=elapsed,
        )


def _handle_jira(task: ResearchTask) -> ResearchTaskResult:
    """Execute a Jira search task."""
    start = time.time()
    try:
        from documents.research_aggregator import search_jira

        findings = search_jira(task.query, limit=10)
        elapsed = time.time() - start
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=True,
            findings=findings,
            summary=f"Found {len(findings)} Jira tickets",
            execution_seconds=elapsed,
        )
    except Exception as e:
        elapsed = time.time() - start
        logger.warning(f"Jira task {task.id} failed: {e}")
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=False,
            error=str(e),
            execution_seconds=elapsed,
        )


def _handle_github(task: ResearchTask) -> ResearchTaskResult:
    """Execute a GitHub search task."""
    start = time.time()
    try:
        from documents.research_aggregator import search_github

        findings = search_github(task.query, limit=10)
        elapsed = time.time() - start
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=True,
            findings=findings,
            summary=f"Found {len(findings)} GitHub results (PRs, issues, code)",
            execution_seconds=elapsed,
        )
    except Exception as e:
        elapsed = time.time() - start
        logger.warning(f"GitHub task {task.id} failed: {e}")
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=False,
            error=str(e),
            execution_seconds=elapsed,
        )


def _handle_slack(task: ResearchTask) -> ResearchTaskResult:
    """Execute a Slack search task."""
    start = time.time()
    try:
        from documents.research_aggregator import search_slack

        findings = search_slack(task.query, limit=10)
        elapsed = time.time() - start
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=True,
            findings=findings,
            summary=f"Found {len(findings)} Slack messages",
            execution_seconds=elapsed,
        )
    except Exception as e:
        elapsed = time.time() - start
        logger.warning(f"Slack task {task.id} failed: {e}")
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=False,
            error=str(e),
            execution_seconds=elapsed,
        )


def _handle_confluence(task: ResearchTask) -> ResearchTaskResult:
    """Execute a Confluence search task."""
    start = time.time()
    try:
        from documents.research_aggregator import search_confluence

        findings = search_confluence(task.query, limit=10)
        elapsed = time.time() - start
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=True,
            findings=findings,
            summary=f"Found {len(findings)} Confluence pages",
            execution_seconds=elapsed,
        )
    except Exception as e:
        elapsed = time.time() - start
        logger.warning(f"Confluence task {task.id} failed: {e}")
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=False,
            error=str(e),
            execution_seconds=elapsed,
        )


def _handle_gdocs(task: ResearchTask) -> ResearchTaskResult:
    """Execute a GDocs search task."""
    start = time.time()
    try:
        from documents.research_aggregator import search_gdrive

        findings = search_gdrive(task.query, limit=10)
        elapsed = time.time() - start
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=True,
            findings=findings,
            summary=f"Found {len(findings)} Google Docs/Sheets",
            execution_seconds=elapsed,
        )
    except Exception as e:
        elapsed = time.time() - start
        logger.warning(f"GDocs task {task.id} failed: {e}")
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=False,
            error=str(e),
            execution_seconds=elapsed,
        )


def _handle_statsig(task: ResearchTask) -> ResearchTaskResult:
    """Execute a Statsig/experiment search task via Brain experiments directory."""
    start = time.time()
    try:
        from documents.research_aggregator import search_brain

        findings = search_brain(task.query, limit=10)
        experiment_findings = [
            f for f in findings
            if "experiment" in f.get("type", "").lower()
            or "experiment" in f.get("path", "").lower()
        ]
        elapsed = time.time() - start
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=True,
            findings=experiment_findings,
            summary=f"Found {len(experiment_findings)} experiment entities",
            execution_seconds=elapsed,
        )
    except Exception as e:
        elapsed = time.time() - start
        logger.warning(f"Statsig task {task.id} failed: {e}")
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=False,
            error=str(e),
            execution_seconds=elapsed,
        )


def _fallback_to_claude(
    task: ResearchTask,
    prompt: str,
    start_time: float,
    task_type: str = "deep_research",
) -> ResearchTaskResult:
    """Fall back to Claude when Gemini fails."""
    try:
        try:
            from pm_os_base.tools.util.model_bridge import invoke_claude
        except ImportError:
            from util.model_bridge import invoke_claude

        claude_response = invoke_claude(
            prompt=prompt,
            max_tokens=8192,
            temperature=0.3,
        )
        elapsed = time.time() - start_time

        if claude_response.get("error"):
            logger.warning(
                f"Task {task.id}: Claude fallback also failed: "
                f"{claude_response['error']}"
            )
            return ResearchTaskResult(
                task_id=task.id,
                source=task.source,
                success=False,
                error=f"Gemini failed, Claude fallback also failed: {claude_response['error']}",
                execution_seconds=elapsed,
            )

        content = claude_response.get("response", "")
        findings = [{"type": task_type, "content": content}] if content else []
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=True,
            findings=findings,
            summary=f"{task_type} completed (Claude fallback)",
            raw_data=claude_response,
            execution_seconds=elapsed,
        )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.warning(f"Task {task.id}: Claude fallback exception: {e}")
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=False,
            error=f"Gemini failed, Claude fallback exception: {e}",
            execution_seconds=elapsed,
        )


def _handle_web(task: ResearchTask) -> ResearchTaskResult:
    """Execute a web search task using model_bridge with Google Search grounding."""
    start = time.time()
    prompt = (
        f"Research the following topic and provide detailed findings:\n\n"
        f"{task.query}\n\nProvide structured analysis with key findings."
    )
    try:
        try:
            from pm_os_base.tools.util.model_bridge import invoke_gemini
        except ImportError:
            from util.model_bridge import invoke_gemini

        response = invoke_gemini(prompt=prompt, use_grounding=True)
        elapsed = time.time() - start

        if response.get("error"):
            logger.info(
                f"Web task {task.id}: Gemini grounded search failed "
                f"({response['error']}), falling back to Claude"
            )
            return _fallback_to_claude(task, prompt, start, task_type="web_research")

        content = response.get("response", "")
        findings = [{"type": "web_research", "content": content}] if content else []
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=True,
            findings=findings,
            summary="Web research completed",
            raw_data=response,
            execution_seconds=elapsed,
        )
    except Exception as e:
        logger.warning(
            f"Web task {task.id}: Gemini exception ({e}), "
            f"falling back to Claude"
        )
        return _fallback_to_claude(task, prompt, start, task_type="web_research")


def _handle_gemini_deep_research(task: ResearchTask) -> ResearchTaskResult:
    """Execute a Gemini Deep Research task."""
    start = time.time()
    try:
        try:
            from pm_os_base.tools.util.model_bridge import invoke_gemini
        except ImportError:
            from util.model_bridge import invoke_gemini

        response = invoke_gemini(
            prompt=task.query,
            use_deep_research=True,
        )
        elapsed = time.time() - start

        if response.get("error"):
            logger.info(
                f"Deep research task {task.id}: Gemini failed "
                f"({response['error']}), falling back to Claude"
            )
            return _fallback_to_claude(task, task.query, start, task_type="deep_research")

        content = response.get("response", "")
        findings = [{"type": "deep_research", "content": content}] if content else []
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=True,
            findings=findings,
            summary="Gemini Deep Research completed",
            raw_data=response,
            execution_seconds=elapsed,
        )
    except Exception as e:
        logger.warning(
            f"Deep research task {task.id}: Gemini exception ({e}), "
            f"falling back to Claude"
        )
        return _fallback_to_claude(task, task.query, start, task_type="deep_research")


def _handle_codebase(task: ResearchTask) -> ResearchTaskResult:
    """Execute a codebase architecture analysis task."""
    start = time.time()
    try:
        # Resolve brain path via config
        try:
            paths = get_paths()
            brain_path = Path(paths.get("brain", ""))
        except Exception:
            brain_path = Path("")

        repos_dir = brain_path / "Technical" / "repositories"

        findings = []
        target = task.query

        if repos_dir.exists():
            for md_file in sorted(repos_dir.glob("*.md")):
                content = md_file.read_text(encoding="utf-8")
                if target:
                    safe = target.replace("/", "_")
                    if md_file.stem != safe and target.lower() not in content.lower():
                        continue

                findings.append({
                    "type": "repo_profile",
                    "title": md_file.stem.replace("_", "/"),
                    "content": content[:3000],
                    "source_file": str(md_file),
                })

        elapsed = time.time() - start
        return ResearchTaskResult(
            task_id=task.id,
            source=task.source,
            success=True,
            findings=findings,
            summary=f"Found {len(findings)} repository profiles",
            execution_seconds=elapsed,
        )
    except Exception as e:
        elapsed = time.time() - start
        logger.warning(f"Codebase task {task.id} failed: {e}")
        return ResearchTaskResult(
            task_id=task.id, source=task.source, success=False,
            error=str(e), execution_seconds=elapsed,
        )


def _handle_figma(task: ResearchTask) -> ResearchTaskResult:
    """Execute a Figma design file analysis task."""
    start = time.time()
    try:
        try:
            from pm_os_cce.tools.design.figma_client import FigmaClient
        except ImportError:
            from design.figma_client import FigmaClient

        client = FigmaClient()
        if not client.is_authenticated():
            return ResearchTaskResult(
                task_id=task.id, source=task.source, success=True,
                findings=[], summary="Figma not authenticated -- skipped",
                execution_seconds=time.time() - start,
            )

        file_key = client.extract_file_key(task.query)
        if not file_key:
            return ResearchTaskResult(
                task_id=task.id, source=task.source, success=True,
                findings=[], summary="No valid Figma file key found",
                execution_seconds=time.time() - start,
            )

        findings = []

        summary = client.get_file_summary(file_key)
        if summary:
            findings.append({
                "type": "figma_summary",
                "title": summary.name,
                "content": (
                    f"Figma file: {summary.name}\n"
                    f"Pages: {len(summary.pages)}\n"
                    f"Last modified: {summary.last_modified}"
                ),
            })

        screens = client.get_screen_list(file_key)
        if screens:
            screen_names = [s.name for s in screens]
            findings.append({
                "type": "figma_screens",
                "title": "Screens",
                "screens": screen_names,
                "content": f"{len(screen_names)} screens: {', '.join(screen_names[:10])}",
            })

        # Component instances (design system coverage)
        try:
            instances = client.get_component_instances(file_key)
            if instances:
                findings.append({
                    "type": "figma_components",
                    "title": "Component Analysis",
                    "content": f"Total components: {len(instances)}",
                })
        except Exception:
            pass

        elapsed = time.time() - start
        return ResearchTaskResult(
            task_id=task.id, source=task.source, success=True,
            findings=findings,
            summary=f"Figma analysis: {len(findings)} sections",
            execution_seconds=elapsed,
        )
    except Exception as e:
        elapsed = time.time() - start
        logger.warning(f"Figma task {task.id} failed: {e}")
        return ResearchTaskResult(
            task_id=task.id, source=task.source, success=False,
            error=str(e), execution_seconds=elapsed,
        )


# Source handler dispatch table
_HANDLERS = {
    ResearchSource.BRAIN: _handle_brain,
    ResearchSource.MASTER_SHEET: _handle_brain,  # Master Sheet searches via Brain
    ResearchSource.JIRA: _handle_jira,
    ResearchSource.GITHUB: _handle_github,
    ResearchSource.SLACK: _handle_slack,
    ResearchSource.CONFLUENCE: _handle_confluence,
    ResearchSource.GDOCS: _handle_gdocs,
    ResearchSource.STATSIG: _handle_statsig,
    ResearchSource.WEB: _handle_web,
    ResearchSource.GEMINI_DEEP_RESEARCH: _handle_gemini_deep_research,
    ResearchSource.CODEBASE: _handle_codebase,
    ResearchSource.FIGMA: _handle_figma,
}


# ============================================================================
# SWARM EXECUTOR
# ============================================================================


class DeepResearchSwarm:
    """
    Executes approved research plans across internal and external sources.

    Runs tasks in two passes:
    - Pass 1: Broad discovery across all available sources
    - Pass 2: Targeted follow-up based on pass 1 findings and gaps

    Then synthesizes all findings into a structured research document.
    """

    def __init__(self):
        self._results: List[ResearchTaskResult] = []

    def execute_plan(
        self,
        plan: ResearchPlan,
        feature_path: Optional[Path] = None,
    ) -> ResearchSwarmResult:
        """
        Execute a full research plan.

        Args:
            plan: The approved research plan to execute
            feature_path: Optional path to feature folder for saving output

        Returns:
            ResearchSwarmResult with all findings and synthesis
        """
        overall_start = time.time()
        self._results = []

        # Pass 1: Internal
        pass_1_internal = [t for t in plan.internal_tasks if t.pass_number == 1]
        internal_p1_results = self._execute_internal_pass(pass_1_internal, 1, [])

        # Pass 1: External
        pass_1_external = [t for t in plan.external_tasks if t.pass_number == 1]
        external_p1_results = self._execute_external_pass(pass_1_external, 1, [])

        # Pass 2: Generate refined queries from pass 1 findings
        all_p1_results = internal_p1_results + external_p1_results

        # Pass 2: Internal
        pass_2_internal = [t for t in plan.internal_tasks if t.pass_number == 2]
        pass_2_internal = self._refine_pass_2_tasks(pass_2_internal, all_p1_results)
        internal_p2_results = self._execute_internal_pass(pass_2_internal, 2, all_p1_results)

        # Pass 2: External
        pass_2_external = [t for t in plan.external_tasks if t.pass_number == 2]
        pass_2_external = self._refine_pass_2_tasks(pass_2_external, all_p1_results)
        external_p2_results = self._execute_external_pass(pass_2_external, 2, all_p1_results)

        # Gather all results
        all_internal = internal_p1_results + internal_p2_results
        all_external = external_p1_results + external_p2_results
        all_results = all_internal + all_external

        # Synthesize
        internal_synthesis = self._synthesize_internal(all_internal)
        external_synthesis = self._synthesize_external(all_external)
        combined = self._combine_research(
            internal_synthesis, external_synthesis, plan.feature_title
        )

        # Challenge
        quality_score, challenge_feedback = self._challenge_research(combined)

        # Count findings
        total_findings = sum(len(r.findings) for r in all_results if r.success)

        elapsed = time.time() - overall_start

        result = ResearchSwarmResult(
            plan=plan,
            task_results=all_results,
            internal_synthesis=internal_synthesis,
            external_synthesis=external_synthesis,
            combined_document=combined,
            quality_score=quality_score,
            challenge_feedback=challenge_feedback,
            total_execution_seconds=elapsed,
            total_findings=total_findings,
        )

        # Save outputs
        if feature_path:
            self._save_outputs(result, feature_path)

        # Persist high-confidence findings to Brain (if Brain plugin available)
        if HAS_BRAIN:
            self._persist_findings_to_brain(result)

        return result

    def _execute_task(self, task: ResearchTask) -> ResearchTaskResult:
        """Execute a single research task by dispatching to the appropriate handler."""
        handler = _HANDLERS.get(task.source)
        if not handler:
            return ResearchTaskResult(
                task_id=task.id,
                source=task.source,
                success=False,
                error=f"No handler for source: {task.source.value}",
            )

        try:
            result = handler(task)
            self._results.append(result)
            return result
        except Exception as e:
            logger.error(f"Unexpected error executing task {task.id}: {e}")
            result = ResearchTaskResult(
                task_id=task.id,
                source=task.source,
                success=False,
                error=f"Unexpected error: {e}",
            )
            self._results.append(result)
            return result

    def _execute_internal_pass(
        self,
        tasks: List[ResearchTask],
        pass_num: int,
        prior_findings: List[ResearchTaskResult],
    ) -> List[ResearchTaskResult]:
        """Execute all internal tasks for a given pass."""
        results = []
        ordered = self._order_by_deps(tasks)
        completed_ids = {r.task_id for r in prior_findings}

        for task in ordered:
            if task.depends_on:
                deps_met = all(d in completed_ids for d in task.depends_on)
                if not deps_met:
                    logger.info(f"Skipping {task.id}: dependencies not met")
                    continue

            result = self._execute_task(task)
            results.append(result)
            if result.success:
                completed_ids.add(task.id)

        return results

    def _execute_external_pass(
        self,
        tasks: List[ResearchTask],
        pass_num: int,
        prior_findings: List[ResearchTaskResult],
    ) -> List[ResearchTaskResult]:
        """Execute all external tasks for a given pass."""
        results = []
        ordered = self._order_by_deps(tasks)
        completed_ids = {r.task_id for r in prior_findings}

        for task in ordered:
            if task.depends_on:
                deps_met = all(d in completed_ids for d in task.depends_on)
                if not deps_met:
                    logger.info(f"Skipping {task.id}: dependencies not met")
                    continue

            result = self._execute_task(task)
            results.append(result)
            if result.success:
                completed_ids.add(task.id)

        return results

    @staticmethod
    def _order_by_deps(tasks: List[ResearchTask]) -> List[ResearchTask]:
        """Order tasks so that dependencies come first."""
        no_deps = [t for t in tasks if not t.depends_on]
        with_deps = [t for t in tasks if t.depends_on]
        return no_deps + with_deps

    @staticmethod
    def _refine_pass_2_tasks(
        tasks: List[ResearchTask],
        pass_1_results: List[ResearchTaskResult],
    ) -> List[ResearchTask]:
        """Refine pass-2 placeholder tasks based on pass-1 findings."""
        if not pass_1_results:
            return tasks

        finding_keywords = []
        for result in pass_1_results:
            if result.success:
                for finding in result.findings:
                    if isinstance(finding, dict):
                        title = finding.get("title", "")
                        if title:
                            finding_keywords.append(title)

        empty_sources = {
            r.source.value for r in pass_1_results
            if r.success and len(r.findings) == 0
        }

        refined = []
        for task in tasks:
            if "[Generated from pass 1 gaps]" in task.query:
                if finding_keywords:
                    refined_query = " ".join(finding_keywords[:5])
                    if empty_sources:
                        refined_query += f" (gaps in: {', '.join(empty_sources)})"
                else:
                    refined_query = task.query
                refined.append(
                    ResearchTask(
                        id=task.id,
                        source=task.source,
                        query=refined_query,
                        purpose=task.purpose,
                        pass_number=task.pass_number,
                        category=task.category,
                        estimated_seconds=task.estimated_seconds,
                        depends_on=task.depends_on,
                    )
                )
            else:
                refined.append(task)

        return refined

    def _synthesize_internal(
        self, results: List[ResearchTaskResult]
    ) -> str:
        """Synthesize internal research findings into structured Markdown."""
        sections = []
        sections.append("## Internal Research Findings\n")

        brain_findings = []
        jira_findings = []
        github_findings = []
        slack_findings = []
        confluence_findings = []
        gdocs_findings = []
        statsig_findings = []
        codebase_findings = []
        figma_findings = []

        for result in results:
            if not result.success:
                continue
            if result.source == ResearchSource.BRAIN:
                brain_findings.extend(result.findings)
            elif result.source == ResearchSource.JIRA:
                jira_findings.extend(result.findings)
            elif result.source == ResearchSource.GITHUB:
                github_findings.extend(result.findings)
            elif result.source == ResearchSource.SLACK:
                slack_findings.extend(result.findings)
            elif result.source == ResearchSource.CONFLUENCE:
                confluence_findings.extend(result.findings)
            elif result.source == ResearchSource.GDOCS:
                gdocs_findings.extend(result.findings)
            elif result.source == ResearchSource.STATSIG:
                statsig_findings.extend(result.findings)
            elif result.source == ResearchSource.CODEBASE:
                codebase_findings.extend(result.findings)
            elif result.source == ResearchSource.FIGMA:
                figma_findings.extend(result.findings)

        if brain_findings:
            sections.append("### Related Brain Entities")
            for f in brain_findings[:10]:
                title = f.get("title", f.get("name", "Unknown"))
                sections.append(f"- {title}")
            sections.append("")

        if jira_findings:
            sections.append("### Related Jira Tickets")
            for f in jira_findings[:10]:
                key = f.get("key", "")
                summary = f.get("summary", f.get("title", ""))
                status = f.get("status", "")
                sections.append(f"- **{key}**: {summary} ({status})")
            sections.append("")

        if github_findings:
            sections.append("### Related Code & PRs")
            for f in github_findings[:10]:
                title = f.get("title", f.get("name", ""))
                url = f.get("url", f.get("html_url", ""))
                sections.append(f"- [{title}]({url})" if url else f"- {title}")
            sections.append("")

        if slack_findings:
            sections.append("### Team Discussions (Slack)")
            for f in slack_findings[:5]:
                text = f.get("text", f.get("content", ""))[:200]
                channel = f.get("channel", "")
                sections.append(f"- #{channel}: {text}")
            sections.append("")

        if confluence_findings:
            sections.append("### Related Documentation (Confluence)")
            for f in confluence_findings[:5]:
                title = f.get("title", "")
                url = f.get("url", "")
                sections.append(f"- [{title}]({url})" if url else f"- {title}")
            sections.append("")

        if gdocs_findings:
            sections.append("### Related Google Docs")
            for f in gdocs_findings[:5]:
                title = f.get("title", f.get("name", ""))
                url = f.get("url", f.get("webViewLink", ""))
                sections.append(f"- [{title}]({url})" if url else f"- {title}")
            sections.append("")

        if statsig_findings:
            sections.append("### Past Experiments")
            for f in statsig_findings[:5]:
                name = f.get("name", f.get("title", ""))
                status = f.get("status", "")
                sections.append(f"- **{name}**: {status}")
            sections.append("")

        if codebase_findings:
            repo_profiles = [f for f in codebase_findings if f.get("type") == "repo_profile"]
            design_info = [f for f in codebase_findings if f.get("type") == "design_system"]

            if repo_profiles:
                sections.append("### Codebase Architecture")
                for f in repo_profiles[:5]:
                    title = f.get("title", "Unknown")
                    highlighted = " **(target)**" if f.get("highlighted") else ""
                    sections.append(f"- **{title}**{highlighted}")
                    content = f.get("content", "")
                    if "Framework" in content or "Language" in content:
                        for line in content.split("\n"):
                            if "|" in line and "---" not in line:
                                sections.append(f"  {line.strip()}")
                sections.append("")

            if design_info:
                sections.append("### Design System Alignment")
                for f in design_info:
                    sections.append(f"- {f.get('content', '')}")
                sections.append("")

        if figma_findings:
            sections.append("### Design File Analysis")
            for f in figma_findings:
                ftype = f.get("type", "")
                if ftype == "figma_summary":
                    sections.append(f"**{f.get('title', 'Figma File')}**")
                    sections.append(f.get("content", ""))
                    sections.append("")
                elif ftype == "figma_screens":
                    screen_list = f.get("screens", [])
                    sections.append(f"**Screens ({len(screen_list)}):** {', '.join(screen_list[:15])}")
                    if len(screen_list) > 15:
                        sections.append(f"  *(+ {len(screen_list) - 15} more)*")
                    sections.append("")
                elif ftype == "figma_components":
                    sections.append("**Component Coverage:**")
                    sections.append(f.get("content", ""))
                    sections.append("")
                else:
                    sections.append(f"- {f.get('content', '')}")
            sections.append("")

        if len(sections) == 1:
            sections.append("No internal findings from available sources.\n")

        return "\n".join(sections)

    def _synthesize_external(
        self, results: List[ResearchTaskResult]
    ) -> str:
        """Synthesize external research findings into structured Markdown."""
        sections = []
        sections.append("## External Research Findings\n")

        web_findings = []
        deep_research_findings = []

        for result in results:
            if not result.success:
                continue
            if result.source == ResearchSource.WEB:
                web_findings.extend(result.findings)
            elif result.source == ResearchSource.GEMINI_DEEP_RESEARCH:
                deep_research_findings.extend(result.findings)

        if web_findings:
            sections.append("### Web Research")
            for f in web_findings:
                content = f.get("content", "")
                if isinstance(content, str) and content:
                    preview = content[:500] + "..." if len(content) > 500 else content
                    sections.append(preview)
                    sections.append("")

        if deep_research_findings:
            sections.append("### Deep Research Analysis")
            for f in deep_research_findings:
                content = f.get("content", "")
                if isinstance(content, str) and content:
                    sections.append(content)
                    sections.append("")

        if len(sections) == 1:
            sections.append("No external findings from available sources.\n")

        return "\n".join(sections)

    def _combine_research(
        self,
        internal: str,
        external: str,
        feature_title: str,
    ) -> str:
        """Combine internal and external synthesis into a unified research document."""
        lines = [
            f"# Deep Research Report: {feature_title}\n",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n",
            "---\n",
            internal,
            "\n---\n",
            external,
            "\n---\n",
            "## Research Metadata\n",
            f"- **Internal sources searched:** {self._count_sources(internal)}",
            f"- **External sources searched:** {self._count_sources(external)}",
            f"- **Total task results:** {len(self._results)}",
            f"- **Successful tasks:** {sum(1 for r in self._results if r.success)}",
            f"- **Failed tasks:** {sum(1 for r in self._results if not r.success)}",
            "",
        ]
        return "\n".join(lines)

    @staticmethod
    def _count_sources(synthesis: str) -> int:
        """Count the number of ### sections in a synthesis."""
        return synthesis.count("### ")

    def _challenge_research(self, combined: str) -> tuple:
        """Orthogonally challenge the research document."""
        try:
            try:
                from pm_os_base.tools.util.model_bridge import (
                    detect_active_model,
                    get_challenger_model,
                )
            except ImportError:
                from util.model_bridge import detect_active_model, get_challenger_model

            active = detect_active_model()
            challenger = get_challenger_model(active)
            logger.info(f"Challenging research with {challenger}")

            score = self._calculate_quality_score(combined)
            feedback = (
                f"Research document reviewed by orthogonal challenger ({challenger}). "
                f"Quality score: {score:.1f}/10."
            )
            return score, feedback

        except (ImportError, Exception) as e:
            logger.warning(f"Challenge skipped: {e}")
            score = self._calculate_quality_score(combined)
            return score, f"Challenge skipped -- {e}"

    @staticmethod
    def _calculate_quality_score(combined: str) -> float:
        """Calculate a quality score based on document content."""
        score = 0.0
        if "### Related Brain Entities" in combined:
            score += 1.5
        if "### Related Jira Tickets" in combined:
            score += 1.5
        if "### Related Code & PRs" in combined:
            score += 1.5
        if "### Team Discussions" in combined:
            score += 1.0
        if "### Related Documentation" in combined:
            score += 1.0
        if "### Past Experiments" in combined:
            score += 1.0
        if "### Web Research" in combined:
            score += 1.0
        if "### Deep Research Analysis" in combined:
            score += 1.5
        if "### Codebase Architecture" in combined:
            score += 1.0
        if "### Design System Alignment" in combined:
            score += 0.5
        if "### Design File Analysis" in combined:
            score += 1.0
        if len(combined) > 2000:
            score = min(score + 0.5, 10.0)
        if len(combined) > 5000:
            score = min(score + 0.5, 10.0)
        return min(score, 10.0)

    def _save_outputs(
        self,
        result: ResearchSwarmResult,
        feature_path: Path,
    ) -> None:
        """Save research outputs to the feature folder."""
        research_dir = feature_path / "research"
        research_dir.mkdir(parents=True, exist_ok=True)

        report_path = research_dir / "deep-research-report.md"
        report_path.write_text(result.combined_document)
        logger.info(f"Research report saved to {report_path}")

        tasks_dir = research_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        for task_result in result.task_results:
            task_path = tasks_dir / f"{task_result.task_id}.json"
            task_path.write_text(
                json.dumps(task_result.to_dict(), indent=2, default=str)
            )

        logger.info(
            f"Saved {len(result.task_results)} task results to {tasks_dir}"
        )

    def _persist_findings_to_brain(
        self,
        result: ResearchSwarmResult,
    ) -> None:
        """Persist high-confidence research findings to Brain for accumulative learning."""
        if not HAS_BRAIN:
            logger.debug("Brain plugin not available; skipping brain persistence")
            return

        try:
            paths = get_paths()
            brain_path = Path(paths.get("brain", ""))
        except Exception:
            logger.warning("Cannot resolve brain path; skipping brain persistence")
            return

        persisted = 0
        skipped = 0

        for task_result in result.task_results:
            if not task_result.success:
                continue

            for finding in task_result.findings:
                entity_type = self._classify_finding_for_brain(finding, task_result.source)
                if not entity_type:
                    continue

                title = finding.get("title", finding.get("name", ""))
                if not title:
                    continue

                content = finding.get("content", finding.get("summary", ""))
                if not content:
                    content = finding.get("text", str(finding))

                if entity_type == "decision":
                    target_dir = brain_path / "Reasoning" / "Decisions"
                elif entity_type == "system":
                    target_dir = brain_path / "Entities" / "Systems"
                elif entity_type == "risk":
                    target_dir = brain_path / "Reasoning" / "Risks"
                else:
                    continue

                target_dir.mkdir(parents=True, exist_ok=True)

                slug = title.lower().replace(" ", "-").replace("/", "-")
                slug = "".join(c for c in slug if c.isalnum() or c == "-")[:60]
                entity_file = target_dir / f"{slug}.md"

                if entity_file.exists():
                    skipped += 1
                    continue

                source_label = task_result.source.value
                entity_content = (
                    f"---\n"
                    f"$id: entity/{entity_type}/{slug}\n"
                    f'name: "{title}"\n'
                    f"type: {entity_type}\n"
                    f"status: active\n"
                    f"confidence: high\n"
                    f"source: deep-research:{source_label}\n"
                    f'created: "{datetime.now().strftime("%Y-%m-%d")}"\n'
                    f"---\n\n"
                    f"# {title}\n\n"
                    f"{content[:2000]}\n\n"
                    f"---\n"
                    f"*Auto-created from deep research ({source_label} source).*\n"
                )
                try:
                    entity_file.write_text(entity_content)
                    persisted += 1
                except Exception as exc:
                    logger.warning(f"Failed to write brain entity {slug}: {exc}")

        if persisted > 0:
            logger.info(
                f"Persisted {persisted} findings to Brain "
                f"({skipped} skipped as duplicates)"
            )

    @staticmethod
    def _classify_finding_for_brain(
        finding: Dict[str, Any],
        source: ResearchSource,
    ) -> Optional[str]:
        """Classify a research finding into a Brain entity type."""
        title = finding.get("title", finding.get("name", "")).lower()
        content = finding.get("content", finding.get("summary", "")).lower()
        ftype = finding.get("type", "")

        if not title or len(title) < 5:
            return None

        if source in (ResearchSource.CONFLUENCE, ResearchSource.GDOCS, ResearchSource.BRAIN):
            decision_keywords = ["decision", "decided", "agreed", "approved", "chose", "selected"]
            if any(kw in title or kw in content for kw in decision_keywords):
                return "decision"

        if source in (ResearchSource.BRAIN, ResearchSource.GITHUB, ResearchSource.CODEBASE, ResearchSource.FIGMA):
            if ftype in ("system", "repo_profile", "design_system", "figma_summary"):
                return "system"
            system_keywords = ["service", "system", "platform", "component", "architecture"]
            if any(kw in title for kw in system_keywords):
                return "system"

        risk_keywords = ["risk", "blocker", "concern", "vulnerability", "issue", "problem"]
        if any(kw in title or kw in content[:200] for kw in risk_keywords):
            return "risk"

        return None
