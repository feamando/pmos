#!/usr/bin/env python3
"""
Atomic file write utilities for brain entity files.

Provides crash-safe writes using the POSIX rename() guarantee:
temp file -> fsync -> rename is atomic on both macOS (APFS) and Linux (ext4).

If the process crashes between write and rename, only the temp file is affected;
the original entity file remains intact.

Usage:
    from pm_os_brain.tools.brain_core.safe_write import atomic_write, atomic_write_json
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


def atomic_write(
    path: Path,
    content: str,
    encoding: str = "utf-8",
) -> None:
    """Write content to path atomically using temp-file + fsync + rename.

    Args:
        path: Target file path
        content: String content to write
        encoding: File encoding (default utf-8)

    Raises:
        OSError: If write, fsync, or rename fails
    """
    path = Path(path)
    tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}")

    try:
        fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        try:
            os.write(fd, content.encode(encoding))
            os.fsync(fd)
        finally:
            os.close(fd)

        os.rename(str(tmp_path), str(path))
    except Exception:
        # Clean up temp file on any failure
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def atomic_write_json(
    path: Path,
    data: Any,
    encoding: str = "utf-8",
) -> None:
    """Write JSON data to path atomically.

    Convenience wrapper around atomic_write() that serializes data as
    pretty-printed JSON.

    Args:
        path: Target file path
        data: Data to serialize as JSON
        encoding: File encoding (default utf-8)

    Raises:
        OSError: If write fails
        TypeError: If data is not JSON-serializable
    """
    content = json.dumps(data, indent=2, ensure_ascii=False)
    atomic_write(path, content, encoding=encoding)
