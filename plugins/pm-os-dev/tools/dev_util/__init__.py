"""
PM-OS Dev Utilities (v5.0)

Development utilities: command sync, cross-CLI validation, data scrubbing.

Usage:
    from pm_os_dev.tools.dev_util.command_sync import sync_commands
    from pm_os_dev.tools.dev_util.pmos_scrubber import ScrubEngine
"""

try:
    from pm_os_dev.tools.dev_util.command_sync import sync_commands
except ImportError:
    try:
        from dev_util.command_sync import sync_commands
    except ImportError:
        sync_commands = None
