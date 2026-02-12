"""
Context Engine Validators

Quality gates and validation framework for the Context Creation Engine.

Validation Types:
- Input validation: Format, required fields
- Content validation: Completeness, quality
- Cross-reference validation: Brain entity links valid
- Challenge validation: Orthogonal challenge for context docs
- Stakeholder validation: Human approval
- Artifact validation: URL valid, accessible
- Output validation: All requirements met

Usage:
    from tools.context_engine.validators import (
        QualityGate,
        FeatureValidator,
        ValidationResult,
    )

    validator = FeatureValidator(feature_path)
    result = validator.validate_phase("context_doc_v2")

    if not result.passed:
        print(result.blockers)
"""

# Validators will be imported here as they are implemented
# from .quality_gate import QualityGate, GateCriteria
# from .feature_validator import FeatureValidator, ValidationResult

__all__ = [
    "QualityGate",
    "GateCriteria",
    "FeatureValidator",
    "ValidationResult",
]
