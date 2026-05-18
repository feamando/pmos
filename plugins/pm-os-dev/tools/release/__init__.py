"""
PM-OS Dev Release (v5.0)

Release pipeline orchestration and version management.

Usage:
    from pm_os_dev.tools.release.release_pipeline import ReleaseOrchestrator
    from pm_os_dev.tools.release.version_manager import VersionManager
"""

try:
    from pm_os_dev.tools.release.release_pipeline import ReleaseOrchestrator
except ImportError:
    try:
        from release.release_pipeline import ReleaseOrchestrator
    except ImportError:
        ReleaseOrchestrator = None

try:
    from pm_os_dev.tools.release.version_manager import VersionManager
except ImportError:
    try:
        from release.version_manager import VersionManager
    except ImportError:
        VersionManager = None
