"""
PM-OS CCE Util (v5.0)

Framework matching and codebase analysis utilities for the
Context Creation Engine.

Usage:
    from pm_os_cce.tools.util.framework_matcher import FrameworkMatcher
    from pm_os_cce.tools.util.codebase_analyzer import CodebaseAnalyzer
"""

try:
    from pm_os_cce.tools.util.framework_matcher import FrameworkMatcher
except ImportError:
    from util.framework_matcher import FrameworkMatcher

try:
    from pm_os_cce.tools.util.codebase_analyzer import (
        CodebaseAnalyzer,
        CodebaseProfile,
        ComponentPattern,
        FeatureFlagPattern,
        RoutingPattern,
        ServicePattern,
    )
except ImportError:
    from util.codebase_analyzer import (
        CodebaseAnalyzer,
        CodebaseProfile,
        ComponentPattern,
        FeatureFlagPattern,
        RoutingPattern,
        ServicePattern,
    )

__all__ = [
    "CodebaseAnalyzer",
    "CodebaseProfile",
    "ComponentPattern",
    "FeatureFlagPattern",
    "FrameworkMatcher",
    "RoutingPattern",
    "ServicePattern",
]
