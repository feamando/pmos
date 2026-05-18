"""
PM-OS Dev Roadmap (v5.0)

Roadmap inbox parsing and management.

Usage:
    from pm_os_dev.tools.roadmap.roadmap_parser import RoadmapParser
"""

try:
    from pm_os_dev.tools.roadmap.roadmap_parser import RoadmapParser
except ImportError:
    try:
        from roadmap.roadmap_parser import RoadmapParser
    except ImportError:
        RoadmapParser = None
