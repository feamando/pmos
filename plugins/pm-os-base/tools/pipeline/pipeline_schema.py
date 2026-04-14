#!/usr/bin/env python3
"""
Pipeline Schema — dataclass definitions for YAML pipeline composition.

A pipeline is a sequence of steps that execute actions from the action registry.
Steps can have conditions, error strategies, and timeouts.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ErrorStrategy(Enum):
    """Pipeline-level error handling strategy."""
    FAIL_FAST = "fail_fast"
    CONTINUE = "continue"
    RETRY = "retry"


class StepErrorAction(Enum):
    """Per-step error handling action."""
    SKIP = "skip"
    FAIL = "fail"
    RETRY = "retry"


@dataclass
class PipelineStep:
    """A single step in a pipeline."""
    name: str
    action: str
    args: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[str] = None
    on_error: StepErrorAction = StepErrorAction.FAIL
    timeout_seconds: int = 0
    description: str = ""
    background: bool = False


@dataclass
class PipelineDefinition:
    """A declarative pipeline definition loaded from YAML."""
    name: str
    description: str = ""
    steps: List[PipelineStep] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    error_strategy: ErrorStrategy = ErrorStrategy.FAIL_FAST
    version: str = "1.0"


@dataclass
class StepResult:
    """Result of executing a single pipeline step."""
    step_name: str
    action: str
    success: bool
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    skipped: bool = False
    backgrounded: bool = False
    duration_ms: int = 0
    error: Optional[str] = None


@dataclass
class PipelineResult:
    """Result of executing an entire pipeline."""
    pipeline_name: str
    success: bool
    step_results: List[StepResult] = field(default_factory=list)
    total_duration_ms: int = 0
    steps_executed: int = 0
    steps_skipped: int = 0
    steps_failed: int = 0

    @property
    def summary(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return (
            f"Pipeline '{self.pipeline_name}': {status} "
            f"({self.steps_executed} executed, {self.steps_skipped} skipped, "
            f"{self.steps_failed} failed) in {self.total_duration_ms}ms"
        )
