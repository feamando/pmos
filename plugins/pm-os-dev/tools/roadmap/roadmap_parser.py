"""
PM-OS Dev RoadmapParser (v5.0)

LLM-based parsing of raw roadmap inbox items (Slack mentions) into structured
items with title, description, acceptance criteria, and priority.

Usage:
    from pm_os_dev.tools.roadmap.roadmap_parser import RoadmapParser

CLI:
    python3 roadmap_parser.py --parse --model gemini
    python3 roadmap_parser.py --parse --dry-run
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        from core.path_resolver import get_paths
    except ImportError:
        get_paths = None

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from core.config_loader import get_config
    except ImportError:
        get_config = None

# Model bridge for LLM invocation (optional dependency)
try:
    from pm_os_base.tools.util.model_bridge import invoke_gemini, invoke_claude
except ImportError:
    try:
        from util.model_bridge import invoke_gemini, invoke_claude
    except ImportError:
        invoke_gemini = None
        invoke_claude = None


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PARSE_PROMPT_TEMPLATE = """You are a technical product manager assistant. Parse the following feature request or bug report into a structured format.

## Raw Input
{raw_text}

## Source Context
- Requester: {requester}
- Classification: {classification}
- Channel: {channel}

## Output Format
Respond with ONLY a JSON object (no markdown, no explanation):
{{
    "title": "Clear, concise title (max 80 chars)",
    "description": "Full description of the feature/bug",
    "acceptance_criteria": ["AC 1", "AC 2", "AC 3"],
    "priority": "P0|P1|P2|P3",
    "category": "feature|bug"
}}

## Priority Guidelines
- P0: Critical/blocking issues, security vulnerabilities
- P1: High-priority features, important bugs
- P2: Normal priority work items
- P3: Nice-to-have, low priority
"""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ParsedItem:
    """A parsed roadmap inbox item."""

    item_id: str = ""
    title: str = ""
    description: str = ""
    acceptance_criteria: List[str] = field(default_factory=list)
    priority: str = "P2"
    category: str = "feature"
    source_channel: str = ""
    source_user: str = ""
    parsed_at: str = ""
    model_used: str = ""


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class RoadmapParser:
    """LLM-based parser for roadmap inbox items."""

    def __init__(self, model: str = "gemini"):
        self.model = model
        self.config = get_config() if get_config else {}

    def parse_item(
        self,
        raw_text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Parse a single raw item through LLM.

        Args:
            raw_text: Raw text from Slack mention
            context: Optional context (requester, classification, channel)

        Returns:
            Dict with parsed fields
        """
        context = context or {}

        prompt = PARSE_PROMPT_TEMPLATE.format(
            raw_text=raw_text,
            requester=context.get("requester", "Unknown"),
            classification=context.get("classification", "feature"),
            channel=context.get("channel", "Unknown"),
        )

        response = self._invoke_llm(prompt)

        if "error" in response:
            return self._fallback_parse(raw_text, context)

        try:
            response_text = response.get("response", "")
            json_match = re.search(r"\{[^{}]+\}", response_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
            else:
                parsed = json.loads(response_text)

            return {
                "title": parsed.get("title", self._extract_title(raw_text)),
                "description": parsed.get("description", raw_text),
                "acceptance_criteria": parsed.get("acceptance_criteria", []),
                "priority": self._validate_priority(parsed.get("priority", "P2")),
                "category": parsed.get("category", "feature"),
                "model_used": self.model,
                "parsed_at": datetime.now().isoformat(),
            }
        except (json.JSONDecodeError, KeyError):
            return self._fallback_parse(raw_text, context)

    def parse_batch(
        self,
        items: List[Dict[str, Any]],
        check_duplicates: bool = True,
    ) -> List[ParsedItem]:
        """Parse multiple raw items.

        Args:
            items: List of dicts with 'raw_text' and optional context fields
            check_duplicates: Whether to check for duplicates

        Returns:
            List of ParsedItem
        """
        parsed_items = []
        existing_titles: List[str] = []

        for item in items:
            raw_text = item.get("raw_text", "")
            if not raw_text:
                continue

            context = {
                "requester": item.get("source_user", "Unknown"),
                "classification": item.get("classification", "feature"),
                "channel": item.get("source_channel", "Unknown"),
            }

            parsed_data = self.parse_item(raw_text, context)

            # Duplicate check
            if check_duplicates:
                new_title = parsed_data.get("title", "").lower()
                is_duplicate = any(
                    self._string_similarity(new_title, t) > 0.8
                    for t in existing_titles
                )
                if is_duplicate:
                    continue

            parsed_item = ParsedItem(
                item_id=item.get("item_id", ""),
                title=parsed_data.get("title", ""),
                description=parsed_data.get("description", ""),
                acceptance_criteria=parsed_data.get("acceptance_criteria", []),
                priority=parsed_data.get("priority", "P2"),
                category=parsed_data.get("category", "feature"),
                source_channel=item.get("source_channel", ""),
                source_user=item.get("source_user", ""),
                parsed_at=parsed_data.get("parsed_at", ""),
                model_used=parsed_data.get("model_used", ""),
            )
            parsed_items.append(parsed_item)
            existing_titles.append(parsed_item.title.lower())

        return parsed_items

    def detect_duplicates(self, items: List[ParsedItem]) -> List[Tuple[str, str]]:
        """Detect duplicate item pairs."""
        duplicates = []
        for i, item1 in enumerate(items):
            for item2 in items[i + 1 :]:
                if self._are_similar(item1, item2):
                    duplicates.append((item1.item_id, item2.item_id))
        return duplicates

    # ------------------------------------------------------------------
    # LLM invocation
    # ------------------------------------------------------------------

    def _invoke_llm(self, prompt: str) -> Dict[str, Any]:
        try:
            if self.model == "gemini" and invoke_gemini is not None:
                return invoke_gemini(prompt, max_tokens=2000, temperature=0.2)
            elif invoke_claude is not None:
                return invoke_claude(prompt, max_tokens=2000, temperature=0.2)
            else:
                return {"error": "No LLM bridge available"}
        except Exception as e:
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fallback_parse(self, raw_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        classification = context.get("classification", "feature")
        return {
            "title": self._extract_title(raw_text),
            "description": raw_text,
            "acceptance_criteria": [],
            "priority": "P2",
            "category": "bug" if "bug" in classification.lower() else "feature",
            "model_used": "fallback",
            "parsed_at": datetime.now().isoformat(),
        }

    def _extract_title(self, raw_text: str) -> str:
        lines = raw_text.strip().split("\n")
        first_line = lines[0].strip()

        # Remove common prefixes (config-driven if available)
        prefixes = self.config.get("roadmap.title_prefixes", [
            "feature request:", "bug:", "feature:", "request:",
        ]) if self.config else ["feature request:", "bug:", "feature:"]

        for prefix in prefixes:
            if first_line.lower().startswith(prefix.lower()):
                first_line = first_line[len(prefix) :].strip()

        if len(first_line) > 80:
            first_line = first_line[:77] + "..."
        return first_line or "Untitled item"

    def _validate_priority(self, priority: str) -> str:
        priority = priority.upper().strip()
        if priority in ["P0", "P1", "P2", "P3"]:
            return priority
        match = re.search(r"P([0-3])", priority)
        if match:
            return f"P{match.group(1)}"
        return "P2"

    def _are_similar(self, item1: ParsedItem, item2: ParsedItem) -> bool:
        title_sim = self._string_similarity(item1.title.lower(), item2.title.lower())
        if title_sim > 0.7:
            return True
        if len(item1.description) > 50 and len(item2.description) > 50:
            desc_sim = self._string_similarity(
                item1.description.lower()[:200], item2.description.lower()[:200]
            )
            if desc_sim > 0.6:
                return True
        return False

    def _string_similarity(self, s1: str, s2: str) -> float:
        if not s1 or not s2:
            return 0.0
        words1 = set(s1.split())
        words2 = set(s2.split())
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Roadmap Parser")
    parser.add_argument("--parse", action="store_true")
    parser.add_argument("--model", default="gemini", choices=["gemini", "claude"])
    parser.add_argument("--no-duplicates", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.parse:
        rp = RoadmapParser(model=args.model)
        print(f"Roadmap parser ready (model: {args.model})")
        if args.dry_run:
            print("(DRY RUN — no items will be saved)")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
