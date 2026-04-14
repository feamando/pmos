"""
PM-OS CCE RLMEngine (v5.0)

Recursive Language Model task decomposition and execution engine.
Decomposes complex tasks into subtasks, executes each with context
retrieval, and recomposes results into a unified output. Supports
budget constraints for token/time allocation across subtasks.

Usage:
    from pm_os_cce.tools.reasoning.rlm_engine import RLMEngine
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SubtaskStatus(Enum):
    """Execution status of a subtask."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BUDGET_EXCEEDED = "budget_exceeded"


@dataclass
class Subtask:
    """A decomposed unit of work within an RLM pipeline.

    Attributes:
        id: Unique subtask identifier.
        description: What this subtask does.
        dependencies: IDs of subtasks that must complete first.
        context_query: Query string for context retrieval.
        budget: Maximum budget units (tokens, milliseconds, or abstract units).
        result: Filled after execution.
        priority: Execution order priority (lower = earlier).
        metadata: Additional task-specific data.
    """

    id: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    context_query: str = ""
    budget: int = 0
    result: Optional[Any] = None
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SubtaskResult:
    """Result of executing a single subtask.

    Attributes:
        subtask_id: Which subtask produced this result.
        status: Execution status.
        output: The actual result data.
        context_used: What context was retrieved.
        budget_used: How much budget was consumed.
        duration_ms: Execution time in milliseconds.
        error: Error message if failed.
    """

    subtask_id: str
    status: SubtaskStatus
    output: Any = None
    context_used: Any = None
    budget_used: int = 0
    duration_ms: int = 0
    error: str = ""


@dataclass
class ComposedResult:
    """Final recomposed result from all subtask outputs.

    Attributes:
        output: Merged/synthesized result.
        subtask_results: Individual subtask results.
        total_budget_used: Sum of all subtask budgets consumed.
        total_duration_ms: Total execution time.
        coverage: Which subtasks completed successfully.
    """

    output: Any = None
    subtask_results: List[SubtaskResult] = field(default_factory=list)
    total_budget_used: int = 0
    total_duration_ms: int = 0
    coverage: Dict[str, bool] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Fraction of subtasks that completed successfully."""
        if not self.subtask_results:
            return 0.0
        completed = sum(
            1
            for r in self.subtask_results
            if r.status == SubtaskStatus.COMPLETED
        )
        return completed / len(self.subtask_results)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "output": self.output,
            "total_budget_used": self.total_budget_used,
            "total_duration_ms": self.total_duration_ms,
            "success_rate": self.success_rate,
            "coverage": self.coverage,
            "subtask_count": len(self.subtask_results),
            "subtask_statuses": {
                r.subtask_id: r.status.value for r in self.subtask_results
            },
        }


class RLMEngine:
    """Recursive Language Model engine for decompose-execute-compose workflows.

    Manages budget allocation, dependency ordering, and result composition.
    """

    def __init__(self, total_budget: int = 10000):
        """Initialize the RLM engine.

        Args:
            total_budget: Total budget units available across all subtasks.
                         Interpretation depends on usage (tokens, ms, abstract).
        """
        self.total_budget = total_budget
        self._budget_remaining = total_budget

    def decompose(
        self,
        task_description: str,
        strategy: str = "auto",
        **kwargs,
    ) -> List[Subtask]:
        """Decompose a task into subtasks using a decomposition strategy.

        Args:
            task_description: The task to decompose.
            strategy: Strategy name (``ByEntityType``, ``ByDocumentSection``,
                     ``ByQuestionType``, or ``auto``).
            **kwargs: Additional arguments for the strategy.

        Returns:
            List of Subtask objects with allocated budgets.
        """
        try:
            from pm_os_cce.tools.reasoning.task_decomposer import (
                get_default_strategy,
                get_strategy,
            )
        except ImportError:
            from reasoning.task_decomposer import get_default_strategy, get_strategy

        if strategy == "auto":
            task_type = kwargs.get("task_type", "discovery")
            strategy_cls = get_default_strategy(task_type)
        else:
            strategy_cls = get_strategy(strategy)

        decomposer = strategy_cls()
        subtasks = decomposer.decompose(task_description, **kwargs)

        # Allocate budgets proportionally
        self._allocate_budgets(subtasks)

        return subtasks

    def execute(
        self,
        subtasks: List[Subtask],
        context_fn: Optional[Callable] = None,
    ) -> List[SubtaskResult]:
        """Execute subtasks in dependency order with budget constraints.

        Args:
            subtasks: List of subtasks to execute.
            context_fn: ``Callable(context_query) -> context_data``.
                       Called per subtask to retrieve relevant context.

        Returns:
            List of SubtaskResult objects.
        """
        self._budget_remaining = self.total_budget
        results: Dict[str, SubtaskResult] = {}
        ordered = self._topological_sort(subtasks)

        for subtask in ordered:
            # Check dependencies
            deps_met = all(
                dep_id in results
                and results[dep_id].status == SubtaskStatus.COMPLETED
                for dep_id in subtask.dependencies
            )

            if not deps_met:
                result = SubtaskResult(
                    subtask_id=subtask.id,
                    status=SubtaskStatus.SKIPPED,
                    error="Dependencies not met",
                )
                results[subtask.id] = result
                continue

            # Check budget
            if self._budget_remaining <= 0:
                result = SubtaskResult(
                    subtask_id=subtask.id,
                    status=SubtaskStatus.BUDGET_EXCEEDED,
                    error="Total budget exhausted",
                )
                results[subtask.id] = result
                continue

            # Execute
            result = self._execute_subtask(subtask, context_fn, results)
            results[subtask.id] = result

            # Track budget
            self._budget_remaining -= result.budget_used

        return list(results.values())

    def compose(
        self,
        subtask_results: List[SubtaskResult],
        composer_fn: Optional[Callable] = None,
    ) -> ComposedResult:
        """Recompose subtask results into a unified output.

        Args:
            subtask_results: Results from ``execute()``.
            composer_fn: Optional custom composition function.
                        If ``None``, uses default merge strategy.

        Returns:
            ComposedResult with merged output.
        """
        total_budget = sum(r.budget_used for r in subtask_results)
        total_duration = sum(r.duration_ms for r in subtask_results)
        coverage = {
            r.subtask_id: r.status == SubtaskStatus.COMPLETED
            for r in subtask_results
        }

        if composer_fn:
            output = composer_fn(subtask_results)
        else:
            output = self._default_compose(subtask_results)

        return ComposedResult(
            output=output,
            subtask_results=subtask_results,
            total_budget_used=total_budget,
            total_duration_ms=total_duration,
            coverage=coverage,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _allocate_budgets(self, subtasks: List[Subtask]) -> None:
        """Distribute total budget proportionally across subtasks."""
        if not subtasks:
            return

        explicit_total = sum(s.budget for s in subtasks if s.budget > 0)
        remaining = max(0, self.total_budget - explicit_total)
        unallocated = [s for s in subtasks if s.budget <= 0]

        if unallocated:
            per_task = remaining // len(unallocated)
            for s in unallocated:
                s.budget = per_task

    def _execute_subtask(
        self,
        subtask: Subtask,
        context_fn: Optional[Callable],
        prior_results: Dict[str, SubtaskResult],
    ) -> SubtaskResult:
        """Execute a single subtask with context retrieval."""
        start_time = time.monotonic()

        try:
            # Retrieve context
            context = None
            if context_fn and subtask.context_query:
                context = context_fn(subtask.context_query)

            output = {
                "subtask_id": subtask.id,
                "description": subtask.description,
                "context": context,
                "dependency_outputs": {
                    dep_id: prior_results[dep_id].output
                    for dep_id in subtask.dependencies
                    if dep_id in prior_results
                    and prior_results[dep_id].output is not None
                },
            }

            duration_ms = int((time.monotonic() - start_time) * 1000)
            budget_used = min(subtask.budget, self._budget_remaining)

            return SubtaskResult(
                subtask_id=subtask.id,
                status=SubtaskStatus.COMPLETED,
                output=output,
                context_used=context,
                budget_used=budget_used,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.warning("Subtask %s failed: %s", subtask.id, exc)
            return SubtaskResult(
                subtask_id=subtask.id,
                status=SubtaskStatus.FAILED,
                error=str(exc),
                duration_ms=duration_ms,
            )

    def _default_compose(
        self, results: List[SubtaskResult]
    ) -> Dict[str, Any]:
        """Default composition: merge all successful outputs."""
        merged: Dict[str, Any] = {
            "findings": [],
            "contexts": [],
            "errors": [],
        }

        for r in results:
            if r.status == SubtaskStatus.COMPLETED and r.output:
                merged["findings"].append(r.output)
                if r.context_used:
                    merged["contexts"].append(r.context_used)
            elif r.status in (SubtaskStatus.FAILED, SubtaskStatus.BUDGET_EXCEEDED):
                merged["errors"].append(
                    {"subtask_id": r.subtask_id, "error": r.error}
                )

        return merged

    def _topological_sort(self, subtasks: List[Subtask]) -> List[Subtask]:
        """Sort subtasks by dependencies then priority."""
        by_id = {s.id: s for s in subtasks}
        visited: set = set()
        order: List[Subtask] = []

        def visit(task_id: str) -> None:
            if task_id in visited:
                return
            visited.add(task_id)
            task = by_id.get(task_id)
            if not task:
                return
            for dep in task.dependencies:
                visit(dep)
            order.append(task)

        for s in sorted(subtasks, key=lambda x: x.priority):
            visit(s.id)

        return order
