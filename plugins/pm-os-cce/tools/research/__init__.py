"""
PM-OS CCE Research Tools (v5.0)

Research and discovery pipeline for the Context Engine.

Usage:
    from pm_os_cce.tools.research.deep_research_swarm import DeepResearchSwarm
"""

try:
    from pm_os_cce.tools.research.discovery_questionnaire import (
        DiscoveryQuestionnaire,
        Question,
        QuestionnaireResult,
        QuestionType,
    )
except ImportError:
    from research.discovery_questionnaire import (
        DiscoveryQuestionnaire,
        Question,
        QuestionnaireResult,
        QuestionType,
    )

try:
    from pm_os_cce.tools.research.research_plan_generator import (
        ResearchPlan,
        ResearchPlanGenerator,
        ResearchSource,
        ResearchTask,
        SourceProbe,
        SourceStatus,
    )
except ImportError:
    from research.research_plan_generator import (
        ResearchPlan,
        ResearchPlanGenerator,
        ResearchSource,
        ResearchTask,
        SourceProbe,
        SourceStatus,
    )

try:
    from pm_os_cce.tools.research.deep_research_swarm import (
        DeepResearchSwarm,
        ResearchSwarmResult,
        ResearchTaskResult,
    )
except ImportError:
    from research.deep_research_swarm import (
        DeepResearchSwarm,
        ResearchSwarmResult,
        ResearchTaskResult,
    )

try:
    from pm_os_cce.tools.research.discovery_researcher import (
        BrainEntityScanner,
        Confidence,
        DiscoveryFinding,
        DiscoveryResearcher,
        DiscoveryResult,
        FindingCategory,
    )
except ImportError:
    from research.discovery_researcher import (
        BrainEntityScanner,
        Confidence,
        DiscoveryFinding,
        DiscoveryResearcher,
        DiscoveryResult,
        FindingCategory,
    )

try:
    from pm_os_cce.tools.research.research_insight_bridge import ResearchInsightBridge
except ImportError:
    from research.research_insight_bridge import ResearchInsightBridge

__all__ = [
    "DiscoveryQuestionnaire",
    "Question",
    "QuestionnaireResult",
    "QuestionType",
    "ResearchPlan",
    "ResearchPlanGenerator",
    "ResearchSource",
    "ResearchTask",
    "SourceProbe",
    "SourceStatus",
    "DeepResearchSwarm",
    "ResearchSwarmResult",
    "ResearchTaskResult",
    "BrainEntityScanner",
    "Confidence",
    "DiscoveryFinding",
    "DiscoveryResearcher",
    "DiscoveryResult",
    "FindingCategory",
    "ResearchInsightBridge",
]
