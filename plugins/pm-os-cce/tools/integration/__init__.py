"""
PM-OS CCE Integration (v5.0)

Jira epic/story/task creation and orthogonal challenge integrations
for the Context Creation Engine.

Usage:
    from pm_os_cce.tools.integration.jira_integration import JiraEpicCreator
    from pm_os_cce.tools.integration.orthogonal_integration import OrthogonalIntegration
"""

try:
    from pm_os_cce.tools.integration.jira_integration import (
        EpicCreationResult,
        JiraApiError,
        JiraConfigError,
        JiraEpicCreator,
        JiraIntegrationError,
        LinkedArtifact,
        StoryData,
        create_jira_epic,
    )
except ImportError:
    from integration.jira_integration import (
        EpicCreationResult,
        JiraApiError,
        JiraConfigError,
        JiraEpicCreator,
        JiraIntegrationError,
        LinkedArtifact,
        StoryData,
        create_jira_epic,
    )

try:
    from pm_os_cce.tools.integration.orthogonal_integration import (
        ChallengeIssue,
        ChallengeResult,
        OrthogonalIntegration,
        ReadinessLevel,
        SCORE_THRESHOLDS,
        determine_readiness,
    )
except ImportError:
    from integration.orthogonal_integration import (
        ChallengeIssue,
        ChallengeResult,
        OrthogonalIntegration,
        ReadinessLevel,
        SCORE_THRESHOLDS,
        determine_readiness,
    )

__all__ = [
    # Jira
    "EpicCreationResult",
    "JiraApiError",
    "JiraConfigError",
    "JiraEpicCreator",
    "JiraIntegrationError",
    "LinkedArtifact",
    "StoryData",
    "create_jira_epic",
    # Orthogonal
    "ChallengeIssue",
    "ChallengeResult",
    "OrthogonalIntegration",
    "ReadinessLevel",
    "SCORE_THRESHOLDS",
    "determine_readiness",
]
