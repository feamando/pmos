"""
PM-OS: AI-powered Product Management Operating System

A comprehensive workflow system for Product Managers.
"""

try:
    from importlib.metadata import version
    __version__ = version("pm-os")
except Exception:
    __version__ = "0.0.0"  # Fallback for development

__all__ = ["__version__"]
