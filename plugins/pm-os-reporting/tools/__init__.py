"""
PM-OS Reporting Tools (v5.0)

Sprint reports, performance updates, and organizational reporting.

Usage:
    from pm_os_reporting.tools.sprint_report_generator import SprintReportGenerator
    from pm_os_reporting.tools.tribe_quarterly_update import QuarterlyUpdate
    from pm_os_reporting.tools.performance_updater import PerformanceUpdater
"""

try:
    from pm_os_reporting.tools.sprint_report_generator import (
        CSV_HEADERS,
        PriorityCluster,
        SprintReportGenerator,
        TicketDetail,
    )
except ImportError:
    from sprint_report_generator import (
        CSV_HEADERS,
        PriorityCluster,
        SprintReportGenerator,
        TicketDetail,
    )

try:
    from pm_os_reporting.tools.tribe_quarterly_update import (
        SECTIONS,
        QuarterlyUpdate,
    )
except ImportError:
    from tribe_quarterly_update import (
        SECTIONS,
        QuarterlyUpdate,
    )

try:
    from pm_os_reporting.tools.performance_updater import (
        ChannelBreakdown,
        MetricComparison,
        MetricPoint,
        PerformanceReport,
        PerformanceUpdater,
    )
except ImportError:
    from performance_updater import (
        ChannelBreakdown,
        MetricComparison,
        MetricPoint,
        PerformanceReport,
        PerformanceUpdater,
    )

__all__ = [
    # Sprint report
    "SprintReportGenerator",
    "TicketDetail",
    "PriorityCluster",
    "CSV_HEADERS",
    # Tribe update
    "QuarterlyUpdate",
    "SECTIONS",
    # Performance updater
    "PerformanceUpdater",
    "MetricPoint",
    "MetricComparison",
    "ChannelBreakdown",
    "PerformanceReport",
]
