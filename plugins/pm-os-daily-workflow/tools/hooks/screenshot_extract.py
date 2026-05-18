#!/usr/bin/env python3
"""PostToolUse hook on Read -- triggers data extraction reminder for screenshots.

Fires when an image file is read. Injects context telling Claude to extract all
numbers, labels, and data points to memory immediately.

Hook registration:
  event: PostToolUse
  matcher: tool_name == "Read"

Version: 5.0.0
"""

import json
import logging
import sys

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}

STATSIG_KEYWORDS = ["statsig", "scorecard", "experiment", "ab_test", "abtest"]

STATSIG_CONTEXT = """You just read a screenshot. EXTRACT ALL numbers, labels, and data points into structured memory NOW.
Compaction will lose these numbers -- save before doing anything else.

If this is a Statsig screenshot, extract ALL of these fields per metric:
- Metric name
- Delta % and direction
- CI bounds (lower, upper)
- p-value
- N per group (control, test)
- Weekly breakdowns if visible
- CURE flag (yes/no)
- Settled vs unsettled

If this is NOT a data screenshot (UI mockup, logo, diagram), skip extraction and state why."""

GENERIC_CONTEXT = """You just read a screenshot. EXTRACT ALL numbers, labels, and data points into structured memory NOW.
Compaction will lose these numbers -- save before doing anything else.

If this is NOT a data screenshot (UI mockup, logo, diagram), skip extraction and state why."""


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        logger.debug("No valid JSON on stdin, exiting.")
        return

    tool_input = data.get("tool_input", {})
    if not tool_input:
        tool_input = data.get("tool_use", {}).get("input", {})
    file_path = tool_input.get("file_path", "")

    # Check if file is an image
    lower_path = file_path.lower()
    is_image = any(lower_path.endswith(ext) for ext in IMAGE_EXTENSIONS)

    if not is_image:
        return

    # Check if likely an experiment platform screenshot from path
    is_statsig = any(kw in lower_path for kw in STATSIG_KEYWORDS)

    logger.info(
        "Screenshot extraction triggered (statsig=%s) for: %s",
        is_statsig,
        file_path,
    )

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": STATSIG_CONTEXT if is_statsig else GENERIC_CONTEXT,
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
