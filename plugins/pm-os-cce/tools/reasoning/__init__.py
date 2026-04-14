"""
PM-OS CCE Reasoning (v5.0)

First-Principles Framework (FPF), orthogonal challenge, RLM engine,
task decomposition, and evidence decay monitoring tools.

Usage:
    from pm_os_cce.tools.reasoning.fpf_engine import FPFEngine
    from pm_os_cce.tools.reasoning.orthogonal_challenge import OrthogonalChallenge
    from pm_os_cce.tools.reasoning.rlm_engine import RLMEngine
    from pm_os_cce.tools.reasoning.task_decomposer import (
        ByDocumentSection, ByEntityType, ByQuestionType,
    )
    from pm_os_cce.tools.reasoning.evidence_decay_monitor import EvidenceDecayMonitor
"""

__all__ = [
    "FPFEngine",
    "OrthogonalChallenge",
    "RLMEngine",
    "EvidenceDecayMonitor",
    "ByDocumentSection",
    "ByEntityType",
    "ByQuestionType",
]
