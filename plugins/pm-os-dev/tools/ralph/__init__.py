"""
PM-OS Dev Ralph (v5.0)

Multi-iteration feature development manager.

Usage:
    from pm_os_dev.tools.ralph.ralph_manager import RalphManager
"""

try:
    from pm_os_dev.tools.ralph.ralph_manager import RalphManager, get_ralph_manager
except ImportError:
    try:
        from ralph.ralph_manager import RalphManager, get_ralph_manager
    except ImportError:
        RalphManager = None
        get_ralph_manager = None
