"""
Beads Integration Module for PM-OS Common.

Extends the developer beads wrapper with full PM-OS integrations:
- Confucius event hooks
- FPF/Quint integration for epics
- Ralph loop synchronization

Usage:
    from beads import BeadsManager

    manager = BeadsManager()
    manager.create_epic("My Epic", auto_fpf=True)
"""

# Import from developer tools if available, otherwise provide stubs
try:
    import sys
    from pathlib import Path

    # Try to import from developer location
    dev_tools = Path(__file__).parent.parent.parent.parent / "developer" / "tools"
    if dev_tools.exists():
        sys.path.insert(0, str(dev_tools))

    from beads.beads_config import get_beads_config, init_beads_project, is_bd_installed
    from beads.beads_wrapper import BeadsWrapper
except ImportError:
    BeadsWrapper = None
    get_beads_config = None
    init_beads_project = None
    is_bd_installed = None

from .beads_confucius_hook import BeadsConfuciusHook
from .beads_fpf_hook import BeadsFPFHook
from .beads_ralph_integration import BeadsRalphBridge

__all__ = [
    "BeadsWrapper",
    "BeadsConfuciusHook",
    "BeadsFPFHook",
    "BeadsRalphBridge",
    "get_beads_config",
    "init_beads_project",
    "is_bd_installed",
]

__version__ = "1.0.0"
