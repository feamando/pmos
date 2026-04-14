"""
PM-OS CCE PrototypeContextParser (v5.0)

Parses PM-OS feature context documents (markdown with YAML frontmatter) to
extract structured prototype specifications. Identifies user flows, screens,
interactions, and corner cases from context doc sections.

Usage:
    from pm_os_cce.tools.prototype.prototype_context_parser import (
        PrototypeContextParser, PrototypeSpec, PrototypeScreen
    )
"""

import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from core.config_loader import get_config

logger = logging.getLogger(__name__)

# Action verbs used to detect interactions in context doc text
ACTION_VERBS = [
    "click", "clicks", "navigate", "navigates", "submit", "submits",
    "select", "selects", "input", "inputs", "scroll", "scrolls",
    "drag", "drags", "tap", "taps", "swipe", "swipes",
    "toggle", "toggles", "expand", "expands", "collapse", "collapses",
    "open", "opens", "close", "closes", "type", "types",
    "enter", "enters", "press", "presses", "hover", "hovers",
    "drop", "drops",
]

# Canonical action verb mapping (variant -> canonical form)
_ACTION_CANONICAL = {
    "clicks": "click", "navigates": "navigate", "submits": "submit",
    "selects": "select", "inputs": "input", "scrolls": "scroll",
    "drags": "drag", "taps": "tap", "swipes": "swipe",
    "toggles": "toggle", "expands": "expand", "collapses": "collapse",
    "opens": "open", "closes": "close", "types": "type",
    "enters": "enter", "presses": "press", "hovers": "hover",
    "drops": "drop",
}


def _load_product_brand_map() -> Dict[str, str]:
    """Load product-to-brand mapping from config."""
    try:
        config = get_config()
        mapping = config.get("design.product_brand_map", {})
        if isinstance(mapping, dict):
            return mapping
    except Exception:
        pass
    return {}


# Config-driven product-to-brand mapping (no hardcoded company defaults)
PRODUCT_BRAND_MAP: Dict[str, str] = _load_product_brand_map()

# Platform-related keywords for inference
_PLATFORM_KEYWORDS = {
    "mobile": ["mobile", "ios", "android", "app", "native", "touch", "swipe", "tap"],
    "web": ["web", "browser", "desktop", "page", "website", "url", "http"],
}


@dataclass
class PrototypeScreen:
    """
    A single screen or view within the prototype.

    Attributes:
        name: Human-readable screen name (e.g., "Checkout Page")
        description: Brief description of the screen's purpose
        interactions: Actions available on this screen, each a dict with
            keys: action (str), target (str), description (str)
        components_hint: Suggested UI components (e.g., ["button", "form", "modal"])
        is_entry_point: Whether this is the first screen the user sees
    """

    name: str
    description: str = ""
    interactions: List[Dict[str, str]] = field(default_factory=list)
    components_hint: List[str] = field(default_factory=list)
    is_entry_point: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "interactions": list(self.interactions),
            "components_hint": list(self.components_hint),
            "is_entry_point": self.is_entry_point,
        }


@dataclass
class PrototypeSpec:
    """
    Complete prototype specification extracted from a context document.

    Contains all structured information needed by the prototyping engine
    to generate an interactive prototype.
    """

    title: str = ""
    feature_slug: str = ""
    product_id: str = ""
    platform: str = "web"
    brand: str = ""
    user_flow: List[str] = field(default_factory=list)
    screens: List[PrototypeScreen] = field(default_factory=list)
    interactions: List[Dict[str, str]] = field(default_factory=list)
    corner_cases: List[str] = field(default_factory=list)
    raw_context: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "feature_slug": self.feature_slug,
            "product_id": self.product_id,
            "platform": self.platform,
            "brand": self.brand,
            "user_flow": list(self.user_flow),
            "screens": [s.to_dict() for s in self.screens],
            "interactions": list(self.interactions),
            "corner_cases": list(self.corner_cases),
            "raw_context": self.raw_context,
        }


class PrototypeContextParser:
    """
    Parses PM-OS context documents into structured prototype specifications.

    Reads markdown files with YAML frontmatter and extracts user flows,
    screens, interactions, and corner cases to produce a PrototypeSpec
    suitable for the prototyping engine.
    """

    def __init__(self) -> None:
        """Initialize the parser."""
        verbs_pattern = "|".join(re.escape(v) for v in ACTION_VERBS)
        self._action_re = re.compile(
            rf"\b({verbs_pattern})\b\s+(.{{1,80}}?)(?:[,;.]|$)",
            re.IGNORECASE,
        )
        self._numbered_re = re.compile(r"^\s*(\d+)[.)]\s+(.+)$", re.MULTILINE)
        self._bullet_re = re.compile(r"^\s*[-*]\s+(.+)$", re.MULTILINE)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(
        self,
        context_doc_path: str,
        feature_state: Optional[dict] = None,
    ) -> PrototypeSpec:
        """
        Parse a context document into a PrototypeSpec.

        Args:
            context_doc_path: Path to the context document markdown file.
            feature_state: Optional feature-state dict. Used to extract
                platform and other questionnaire answers.

        Returns:
            PrototypeSpec populated with all extractable information.
        """
        doc_path = Path(context_doc_path)

        if not doc_path.exists():
            logger.warning("Context document not found: %s", doc_path)
            return PrototypeSpec(raw_context="")

        content = doc_path.read_text(encoding="utf-8")
        logger.info("Parsing context document: %s (%d chars)", doc_path.name, len(content))

        # 1. Extract frontmatter metadata
        frontmatter = self._extract_frontmatter(content)
        title = frontmatter.get("title", "")
        feature_slug = frontmatter.get("feature_slug", frontmatter.get("slug", ""))
        product_id = frontmatter.get("product", frontmatter.get("product_id", ""))

        # 2. Extract user flow
        user_flow = self._extract_user_flow(content)

        # 3. Extract screens
        screens = self._extract_screens(content, user_flow)

        # 4. Extract cross-screen interactions
        interactions = self._extract_interactions(screens, content)

        # 5. Extract corner cases
        corner_cases = self._extract_corner_cases(content)

        # 6. Determine platform
        platform = self._infer_platform(content, feature_state)

        # 7. Map product to brand (config-driven)
        brand = self._map_product_to_brand(product_id)

        spec = PrototypeSpec(
            title=title,
            feature_slug=feature_slug,
            product_id=product_id,
            platform=platform,
            brand=brand,
            user_flow=user_flow,
            screens=screens,
            interactions=interactions,
            corner_cases=corner_cases,
            raw_context=content,
        )

        logger.info(
            "Parsed spec: title=%r, screens=%d, flow_steps=%d, interactions=%d, corner_cases=%d",
            spec.title, len(spec.screens), len(spec.user_flow),
            len(spec.interactions), len(spec.corner_cases),
        )

        return spec

    # ------------------------------------------------------------------
    # Frontmatter extraction
    # ------------------------------------------------------------------

    def _extract_frontmatter(self, content: str) -> dict:
        """Parse YAML frontmatter from markdown content."""
        match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not match:
            logger.debug("No YAML frontmatter found in document")
            return {}

        yaml_text = match.group(1)
        try:
            parsed = yaml.safe_load(yaml_text)
            if isinstance(parsed, dict):
                return parsed
            logger.warning("Frontmatter YAML did not parse to a dict")
            return {}
        except yaml.YAMLError as exc:
            logger.warning("Failed to parse YAML frontmatter: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Section extraction
    # ------------------------------------------------------------------

    def _extract_section(self, content: str, heading: str) -> str:
        """Extract content under a markdown heading."""
        pattern = re.compile(
            rf"^(#+)\s+{re.escape(heading)}\s*$",
            re.MULTILINE | re.IGNORECASE,
        )
        match = pattern.search(content)
        if not match:
            return ""

        heading_level = len(match.group(1))
        start = match.end()

        next_heading = re.compile(
            rf"^#{{1,{heading_level}}}\s+",
            re.MULTILINE,
        )
        next_match = next_heading.search(content, start)
        end = next_match.start() if next_match else len(content)

        return content[start:end].strip()

    def _extract_section_multi(self, content: str, headings: List[str]) -> str:
        """Try multiple heading names and return the first non-empty section."""
        for heading in headings:
            section = self._extract_section(content, heading)
            if section:
                return section
        return ""

    # ------------------------------------------------------------------
    # User flow extraction
    # ------------------------------------------------------------------

    def _extract_user_flow(self, content: str) -> List[str]:
        """Extract an ordered list of user journey steps."""
        section_names = [
            "User Flow", "Workflow", "User Journey",
            "Proposed Solution", "Flow",
        ]
        section_text = self._extract_section_multi(content, section_names)

        if section_text:
            steps = self._parse_numbered_list(section_text)
            if steps:
                return steps

        proposed = self._extract_section(content, "Proposed Solution")
        if proposed:
            sub_flow = self._extract_section(proposed, "User Flow")
            if sub_flow:
                steps = self._parse_numbered_list(sub_flow)
                if steps:
                    return steps
            steps = self._parse_numbered_list(proposed)
            if steps:
                return steps

        steps = self._parse_numbered_list(content)
        return steps

    def _parse_numbered_list(self, text: str) -> List[str]:
        """Parse a numbered list from text."""
        matches = self._numbered_re.findall(text)
        if not matches:
            return []
        sorted_matches = sorted(matches, key=lambda m: int(m[0]))
        return [step.strip() for _num, step in sorted_matches]

    # ------------------------------------------------------------------
    # Screen extraction
    # ------------------------------------------------------------------

    def _extract_screens(
        self, content: str, user_flow: List[str],
    ) -> List[PrototypeScreen]:
        """Identify unique screens for the prototype."""
        screens: List[PrototypeScreen] = []

        section_text = self._extract_section_multi(
            content, ["Screens", "Pages", "Views", "Screen List"]
        )
        if section_text:
            screens = self._parse_screen_list(section_text)

        if not screens and user_flow:
            screens = self._infer_screens_from_flow(user_flow)

        if not screens:
            screens = self._infer_screens_from_content(content)

        if screens and not any(s.is_entry_point for s in screens):
            screens[0].is_entry_point = True

        self._enrich_screen_components(screens, content)

        return screens

    def _parse_screen_list(self, section_text: str) -> List[PrototypeScreen]:
        """Parse an explicit bullet list of screens."""
        screens: List[PrototypeScreen] = []
        items = self._bullet_re.findall(section_text)

        for item in items:
            item = item.strip()
            if not item:
                continue
            name = item
            description = ""
            for sep in [" — ", " - ", ": ", " – "]:
                if sep in item:
                    parts = item.split(sep, 1)
                    name = parts[0].strip()
                    description = parts[1].strip()
                    break
            screens.append(PrototypeScreen(name=name, description=description))

        return screens

    def _infer_screens_from_flow(
        self, user_flow: List[str]
    ) -> List[PrototypeScreen]:
        """Infer screens from user flow steps."""
        screen_pattern = re.compile(
            r"(?:(?:navigates?\s+to|goes?\s+to|lands?\s+on|views?|sees?|shown?)\s+(?:the\s+)?)"
            r"([A-Z][A-Za-z0-9\s]+(?:page|screen|view|dialog|modal|panel|form|section))",
            re.IGNORECASE,
        )
        simple_pattern = re.compile(
            r"\b([A-Z][A-Za-z0-9\s]{1,40}?"
            r"(?:page|screen|view|dialog|modal|panel|form|section))\b",
            re.IGNORECASE,
        )

        seen: Dict[str, PrototypeScreen] = {}
        for step in user_flow:
            for pattern in [screen_pattern, simple_pattern]:
                for match in pattern.finditer(step):
                    raw_name = match.group(1).strip()
                    key = raw_name.lower()
                    if key not in seen:
                        seen[key] = PrototypeScreen(
                            name=raw_name,
                            description=f"Inferred from flow step: {step}",
                        )

        return list(seen.values())

    def _infer_screens_from_content(self, content: str) -> List[PrototypeScreen]:
        """Last-resort screen inference from the full document."""
        body = re.sub(r"^---.*?---\s*", "", content, count=1, flags=re.DOTALL)

        pattern = re.compile(
            r"\b([A-Z][A-Za-z0-9\s]{1,40}?"
            r"(?:page|screen|view|dialog|modal))\b",
            re.IGNORECASE,
        )

        seen: Dict[str, PrototypeScreen] = {}
        for match in pattern.finditer(body):
            raw_name = match.group(1).strip()
            key = raw_name.lower()
            if key not in seen:
                seen[key] = PrototypeScreen(
                    name=raw_name,
                    description="Inferred from document content",
                )

        return list(seen.values())

    def _enrich_screen_components(
        self, screens: List[PrototypeScreen], content: str
    ) -> None:
        """Add component hints to screens based on context doc content."""
        component_keywords = [
            "button", "form", "input", "modal", "dialog", "dropdown",
            "select", "table", "list", "card", "carousel", "slider",
            "tabs", "accordion", "navbar", "sidebar", "footer", "header",
            "banner", "toast", "notification", "checkbox", "radio",
            "toggle", "search", "pagination", "breadcrumb", "stepper",
            "progress", "spinner", "avatar", "badge", "chip", "tooltip",
            "popover", "menu", "image", "video", "map", "chart", "graph",
        ]
        component_re = re.compile(
            r"\b(" + "|".join(re.escape(kw) for kw in component_keywords) + r")s?\b",
            re.IGNORECASE,
        )

        content_lower = content.lower()

        for screen in screens:
            screen_name_lower = screen.name.lower()
            hints: set = set()
            start = 0
            while True:
                idx = content_lower.find(screen_name_lower, start)
                if idx == -1:
                    break
                window_start = max(0, idx - 200)
                window_end = min(len(content), idx + len(screen_name_lower) + 300)
                window = content[window_start:window_end]
                for m in component_re.finditer(window):
                    hints.add(m.group(1).lower().rstrip("s"))
                start = idx + 1

            screen.components_hint = sorted(hints)

    # ------------------------------------------------------------------
    # Interaction extraction
    # ------------------------------------------------------------------

    def _extract_interactions(
        self, screens: List[PrototypeScreen], content: str,
    ) -> List[Dict[str, str]]:
        """Map actions between screens."""
        if not screens:
            return []

        cross_interactions: List[Dict[str, str]] = []
        screen_names_lower = {s.name.lower(): s for s in screens}

        body = re.sub(r"^---.*?---\s*", "", content, count=1, flags=re.DOTALL)

        for line in body.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue

            for match in self._action_re.finditer(line_stripped):
                verb = match.group(1).lower()
                target_text = match.group(2).strip()
                canonical_verb = _ACTION_CANONICAL.get(verb, verb)

                target_screen: Optional[PrototypeScreen] = None
                source_screen: Optional[PrototypeScreen] = None

                for sname_lower, screen_obj in screen_names_lower.items():
                    if sname_lower in target_text.lower():
                        target_screen = screen_obj
                    elif sname_lower in line_stripped.lower() and target_screen != screen_obj:
                        source_screen = screen_obj

                if target_screen and source_screen:
                    interaction = {
                        "source": source_screen.name,
                        "target": target_screen.name,
                        "action": canonical_verb,
                        "description": line_stripped,
                    }
                    if interaction not in cross_interactions:
                        cross_interactions.append(interaction)
                elif target_screen:
                    per_screen_interaction = {
                        "action": canonical_verb,
                        "target": target_screen.name,
                        "description": line_stripped,
                    }
                    if per_screen_interaction not in target_screen.interactions:
                        target_screen.interactions.append(per_screen_interaction)
                else:
                    for sname_lower, screen_obj in screen_names_lower.items():
                        if sname_lower in line_stripped.lower():
                            per_screen_interaction = {
                                "action": canonical_verb,
                                "target": target_text,
                                "description": line_stripped,
                            }
                            if per_screen_interaction not in screen_obj.interactions:
                                screen_obj.interactions.append(per_screen_interaction)
                            break

        return cross_interactions

    # ------------------------------------------------------------------
    # Corner case extraction
    # ------------------------------------------------------------------

    def _extract_corner_cases(self, content: str) -> List[str]:
        """Extract error, edge, and corner cases from the document."""
        section_text = self._extract_section_multi(
            content,
            [
                "Corner Cases", "Edge Cases", "Error States",
                "Error Handling", "Exceptions", "Error Scenarios",
                "Failure Cases", "Boundary Conditions",
            ],
        )

        if not section_text:
            requirements = self._extract_section(content, "Requirements")
            if requirements:
                section_text = self._extract_error_items_from_text(requirements)
                if section_text:
                    return section_text
            return []

        cases: List[str] = []
        bullet_items = self._bullet_re.findall(section_text)
        cases.extend(item.strip() for item in bullet_items if item.strip())

        numbered_items = self._numbered_re.findall(section_text)
        cases.extend(step.strip() for _num, step in numbered_items if step.strip())

        if not cases:
            for line in section_text.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    cases.append(line)

        return cases

    def _extract_error_items_from_text(self, text: str) -> List[str]:
        """Extract lines mentioning errors or edge cases from free text."""
        error_pattern = re.compile(
            r".*\b(?:error|fail|invalid|timeout|empty|missing|unavailable|"
            r"expired|denied|exceeded|overflow|duplicate|conflict|"
            r"unauthorized|forbidden|offline|edge\s+case)\b.*",
            re.IGNORECASE,
        )
        items: List[str] = []
        for line in text.splitlines():
            line = line.strip()
            if line and error_pattern.match(line):
                cleaned = re.sub(r"^[\-*]\s+", "", line)
                cleaned = re.sub(r"^\d+[.)]\s+", "", cleaned)
                items.append(cleaned.strip())
        return items

    # ------------------------------------------------------------------
    # Platform inference
    # ------------------------------------------------------------------

    def _infer_platform(
        self, content: str, feature_state: Optional[dict],
    ) -> str:
        """Determine the target platform (web, mobile, or both)."""
        # 1. Check feature_state questionnaire
        if feature_state:
            questionnaire = feature_state.get("questionnaire", {})
            if isinstance(questionnaire, dict):
                platform_answer = questionnaire.get("platform", "")
                if platform_answer:
                    return self._normalize_platform(platform_answer)

            platform_answer = feature_state.get("platform", "")
            if platform_answer:
                return self._normalize_platform(platform_answer)

            engine = feature_state.get("engine", {})
            if isinstance(engine, dict):
                qa = engine.get("questionnaire_answers", {})
                if isinstance(qa, dict):
                    platform_answer = qa.get("platform", "")
                    if platform_answer:
                        return self._normalize_platform(platform_answer)

        # 2. Check frontmatter
        frontmatter = self._extract_frontmatter(content)
        fm_platform = frontmatter.get("platform", "")
        if fm_platform:
            return self._normalize_platform(fm_platform)

        # 3. Content keyword analysis
        content_lower = content.lower()
        mobile_score = sum(
            1 for kw in _PLATFORM_KEYWORDS["mobile"] if kw in content_lower
        )
        web_score = sum(
            1 for kw in _PLATFORM_KEYWORDS["web"] if kw in content_lower
        )

        if mobile_score > 0 and web_score > 0:
            if mobile_score > web_score * 2:
                return "mobile"
            elif web_score > mobile_score * 2:
                return "web"
            return "both"
        elif mobile_score > 0:
            return "mobile"
        elif web_score > 0:
            return "web"

        return "web"

    @staticmethod
    def _normalize_platform(raw: str) -> str:
        """Normalize a platform string to one of web/mobile/both."""
        raw_lower = raw.lower().strip()
        if raw_lower in ("web", "browser", "desktop"):
            return "web"
        if raw_lower in ("mobile", "ios", "android", "native", "app"):
            return "mobile"
        if raw_lower in ("both", "all", "cross-platform", "responsive"):
            return "both"
        if "," in raw_lower or " and " in raw_lower:
            return "both"
        return "web"

    # ------------------------------------------------------------------
    # Product-to-brand mapping (config-driven)
    # ------------------------------------------------------------------

    @staticmethod
    def _map_product_to_brand(product_id: str) -> str:
        """
        Map a product identifier to its brand display name.

        Uses config-driven PRODUCT_BRAND_MAP. Falls back to a generic
        title-cased version of the product_id for unknown products.
        """
        if not product_id:
            try:
                config = get_config()
                return config.get("persona.brand_name", "Default")
            except Exception:
                return "Default"
        brand = PRODUCT_BRAND_MAP.get(product_id, "")
        if brand:
            return brand
        # Fallback: title-case the product_id slug
        return product_id.replace("-", " ").title()
