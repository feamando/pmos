"""
PM-OS CCE TaskDecomposer (v5.0)

Strategy pattern for decomposing tasks into subtasks. Provides three
built-in decomposition strategies and a registry for extensibility.

Strategies:
    - ByDocumentSection: Split by markdown headers
    - ByEntityType: Split by Brain entity types
    - ByQuestionType: Split research into who/what/why/how/when

Usage:
    from pm_os_cce.tools.reasoning.task_decomposer import ByEntityType
"""

import re
from abc import ABC, abstractmethod
from typing import Dict, List, Type

try:
    from pm_os_cce.tools.reasoning.rlm_engine import Subtask
except ImportError:
    from reasoning.rlm_engine import Subtask


class DecompositionStrategy(ABC):
    """Abstract base for task decomposition strategies."""

    @abstractmethod
    def decompose(self, task_description: str, **kwargs) -> List[Subtask]:
        """Decompose a task into subtasks.

        Args:
            task_description: The task to decompose.
            **kwargs: Strategy-specific parameters.

        Returns:
            List of Subtask objects.
        """


class ByDocumentSection(DecompositionStrategy):
    """Decompose by splitting a markdown document into sections.

    Each section becomes a subtask with its own context query.
    Useful for orthogonal challenge decomposition.
    """

    def decompose(self, task_description: str, **kwargs) -> List[Subtask]:
        """Decompose document into section-level subtasks.

        Keyword Args:
            document: Markdown content to split.
            section_level: Header level to split on (default: 2 for ``##``).
        """
        document = kwargs.get("document", task_description)
        section_level = kwargs.get("section_level", 2)

        sections = self._extract_sections(document, section_level)
        if not sections:
            return [
                Subtask(
                    id="section-0",
                    description=f"Process full document: {task_description[:80]}",
                    context_query=task_description,
                    priority=0,
                )
            ]

        subtasks: List[Subtask] = []
        for i, (title, content) in enumerate(sections):
            subtasks.append(
                Subtask(
                    id=f"section-{i}",
                    description=f"Analyze section: {title}",
                    context_query=f"{task_description} — focus on: {title}",
                    priority=i,
                    metadata={
                        "section_title": title,
                        "section_content": content,
                        "word_count": len(content.split()),
                    },
                )
            )

        return subtasks

    def _extract_sections(
        self, document: str, level: int
    ) -> List[tuple]:
        """Extract sections at given header level."""
        pattern = r"^(#{" + str(level) + r"})\s+(.+)$"
        sections: List[tuple] = []
        current_title = None
        current_lines: List[str] = []

        for line in document.split("\n"):
            match = re.match(pattern, line, re.MULTILINE)
            if match and len(match.group(1)) == level:
                if current_title:
                    sections.append(
                        (current_title, "\n".join(current_lines).strip())
                    )
                current_title = match.group(2).strip()
                current_lines = []
            elif current_title is not None:
                current_lines.append(line)

        if current_title:
            sections.append(
                (current_title, "\n".join(current_lines).strip())
            )

        return sections


class ByEntityType(DecompositionStrategy):
    """Decompose by Brain entity types.

    Creates one subtask per entity type to search for,
    enabling focused discovery per category.
    """

    DEFAULT_ENTITY_TYPES = [
        ("project", "Find related projects and features"),
        ("system", "Find technical systems and infrastructure"),
        ("person", "Find key stakeholders and domain experts"),
        ("brand", "Find related brands and products"),
        ("experiment", "Find related experiments and A/B tests"),
        ("framework", "Find applicable PM frameworks"),
    ]

    def decompose(self, task_description: str, **kwargs) -> List[Subtask]:
        """Decompose into entity-type-specific search subtasks.

        Keyword Args:
            entity_types: Optional list of ``(type, description)`` tuples.
            feature_title: Feature being researched.
        """
        entity_types = kwargs.get("entity_types", self.DEFAULT_ENTITY_TYPES)
        feature_title = kwargs.get("feature_title", task_description)

        subtasks: List[Subtask] = []
        for i, (etype, edesc) in enumerate(entity_types):
            subtasks.append(
                Subtask(
                    id=f"entity-{etype}",
                    description=f"{edesc} related to {feature_title}",
                    context_query=f"{feature_title} {etype}",
                    priority=i,
                    metadata={"entity_type": etype},
                )
            )

        return subtasks


class ByQuestionType(DecompositionStrategy):
    """Decompose a research question into who/what/why/how/when dimensions.

    Creates subtasks for each dimension of inquiry, producing
    comprehensive research coverage.
    """

    QUESTION_DIMENSIONS = [
        ("who", "Who is affected? Who are the stakeholders?"),
        ("what", "What is the problem? What exists today?"),
        ("why", "Why does this matter? Why now?"),
        ("how", "How should this be approached? How do others solve it?"),
        ("when", "When should this happen? What are the timelines?"),
    ]

    def decompose(self, task_description: str, **kwargs) -> List[Subtask]:
        """Decompose research into question-type subtasks.

        Keyword Args:
            dimensions: Optional list of ``(dimension, question_template)`` tuples.
        """
        dimensions = kwargs.get("dimensions", self.QUESTION_DIMENSIONS)

        subtasks: List[Subtask] = []
        for i, (dim, template) in enumerate(dimensions):
            subtasks.append(
                Subtask(
                    id=f"question-{dim}",
                    description=f"[{dim.upper()}] {template}",
                    context_query=f"{dim} {task_description}",
                    priority=i,
                    metadata={"dimension": dim, "question": template},
                )
            )

        return subtasks


# ---------------------------------------------------------------------------
# Strategy registry
# ---------------------------------------------------------------------------

_STRATEGY_REGISTRY: Dict[str, Type[DecompositionStrategy]] = {
    "ByDocumentSection": ByDocumentSection,
    "ByEntityType": ByEntityType,
    "ByQuestionType": ByQuestionType,
}

_DEFAULT_STRATEGIES: Dict[str, str] = {
    "discovery": "ByEntityType",
    "challenge": "ByDocumentSection",
    "research": "ByQuestionType",
}


def get_strategy(name: str) -> Type[DecompositionStrategy]:
    """Get a decomposition strategy class by name."""
    if name not in _STRATEGY_REGISTRY:
        raise ValueError(
            f"Unknown strategy: {name}. "
            f"Available: {list(_STRATEGY_REGISTRY.keys())}"
        )
    return _STRATEGY_REGISTRY[name]


def get_default_strategy(task_type: str) -> Type[DecompositionStrategy]:
    """Get the default decomposition strategy for a task type."""
    strategy_name = _DEFAULT_STRATEGIES.get(task_type, "ByEntityType")
    return _STRATEGY_REGISTRY[strategy_name]
