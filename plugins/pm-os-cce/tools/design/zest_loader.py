"""
PM-OS CCE ZestLoader (v5.0)

Loads Zest design system component definitions from Brain entity files
at user/brain/Entities/Components/*.md. Provides lookup, filtering, and
Figma-to-code mapping for Zest components across web and React Native
platforms.

Each component entity is a markdown file with YAML frontmatter following
the brain://entity/component/v1 schema.

Usage:
    from pm_os_cce.tools.design.zest_loader import ZestLoader
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ZestComponent:
    """
    A single Zest design system component loaded from a Brain entity.

    Attributes:
        name: Canonical component name (e.g., "Button").
        category: Component category — one of interactive, layout, form,
            data-display, feedback, or unknown.
        platforms: Per-platform metadata dict. Keys are platform identifiers
            ("web", "rn"); values are dicts with code_name, package, and
            figma_names.
        aliases: Variant / alternate names from the $aliases frontmatter field.
        is_composite: Whether the component is composed of other components.
        figma_names: Flattened set of all Figma layer names across every
            platform (useful for reverse lookups).
        brain_entity_path: Absolute path to the source .md entity file.
    """

    name: str
    category: str
    platforms: Dict[str, Dict[str, Any]]
    aliases: List[str] = field(default_factory=list)
    is_composite: bool = False
    figma_names: Set[str] = field(default_factory=set)
    brain_entity_path: str = ""


# ---------------------------------------------------------------------------
# YAML frontmatter parser (fallback when PyYAML is not installed)
# ---------------------------------------------------------------------------


def _parse_frontmatter_fallback(text: str) -> Optional[Dict[str, Any]]:
    """
    Minimal YAML-frontmatter parser using only the standard library.

    Handles the subset of YAML produced by the Brain entity writer:
    scalar values, simple lists, and up to three levels of nested mapping.

    Args:
        text: Full file content (with ``---`` delimiters).

    Returns:
        Parsed dict, or None if frontmatter cannot be extracted.
    """
    match = re.match(r"^---\n(.+?)\n---", text, re.DOTALL)
    if not match:
        return None

    lines = match.group(1).splitlines()
    result: Dict[str, Any] = {}
    stack: list = [(result, -1)]  # (current_dict, indent_level)
    current_list_key: Optional[str] = None
    current_list_indent: int = -1

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip())

        # Detect list item
        list_match = re.match(r"^(\s*)- (.*)$", raw_line)
        if list_match:
            item_value = list_match.group(2).strip()
            if current_list_key is not None and indent >= current_list_indent:
                parent_dict = stack[-1][0]
                if isinstance(parent_dict.get(current_list_key), list):
                    parent_dict[current_list_key].append(_coerce_value(item_value))
                    continue

        # Detect key: value
        kv_match = re.match(r"^(\s*)([\w$.\-]+):\s*(.*)$", raw_line)
        if kv_match:
            current_list_key = None
            key = kv_match.group(2)
            value_str = kv_match.group(3).strip()

            while len(stack) > 1 and stack[-1][1] >= indent:
                stack.pop()

            parent = stack[-1][0]

            if value_str == "" or value_str == ">":
                child: Dict[str, Any] = {}
                parent[key] = child
                stack.append((child, indent))
            else:
                parent[key] = _coerce_value(value_str)
            continue

        # Detect bare list start
        bare_list_match = re.match(r"^(\s*)([\w$.\-]+):\s*$", raw_line)
        if bare_list_match:
            key = bare_list_match.group(2)
            while len(stack) > 1 and stack[-1][1] >= indent:
                stack.pop()
            parent = stack[-1][0]
            parent[key] = []
            current_list_key = key
            current_list_indent = indent + 2
            continue

        # Standalone list item continuation
        if list_match and current_list_key:
            item_value = list_match.group(2).strip()
            parent_dict = stack[-1][0]
            if isinstance(parent_dict.get(current_list_key), list):
                parent_dict[current_list_key].append(_coerce_value(item_value))

    return result


def _coerce_value(raw: str) -> Any:
    """Coerce a YAML scalar string to a Python type."""
    if not raw:
        return ""

    if (raw.startswith("'") and raw.endswith("'")) or (
        raw.startswith('"') and raw.endswith('"')
    ):
        return raw[1:-1]

    lower = raw.lower()
    if lower == "null" or lower == "~":
        return None
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower == "[]":
        return []

    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass

    return raw


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class ZestLoader:
    """
    Loads and indexes Zest design system components from Brain entity files.

    Components are read from ``{brain_path}/Entities/Components/*.md``,
    parsed once, and cached for the lifetime of the loader instance.

    Typical usage::

        loader = ZestLoader("/absolute/path/to/user/brain")
        all_components = loader.load_components()
        web_only = loader.get_components_for_platform("web")
        btn = loader.find_component_by_figma_name("Button Brand")
    """

    def __init__(self, brain_path: str) -> None:
        """
        Initialize the Zest component loader.

        Args:
            brain_path: Absolute path to the ``user/brain`` directory that
                contains ``Entities/Components/*.md``.
        """
        self.brain_path = Path(brain_path)
        self.components_dir = self.brain_path / "Entities" / "Components"
        self._components_cache: Optional[Dict[str, ZestComponent]] = None
        self._figma_index: Optional[Dict[str, ZestComponent]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_components(self) -> Dict[str, ZestComponent]:
        """
        Read all component entity files and return them keyed by name.

        Returns:
            Dict mapping component name to ZestComponent.
        """
        if self._components_cache is not None:
            return self._components_cache

        components: Dict[str, ZestComponent] = {}

        if not self.components_dir.exists():
            logger.warning(
                "Components directory does not exist: %s", self.components_dir
            )
            self._components_cache = components
            return components

        for md_file in sorted(self.components_dir.glob("*.md")):
            try:
                component = self._parse_component_file(md_file)
                if component is not None:
                    components[component.name] = component
            except Exception as exc:
                logger.warning(
                    "Skipping malformed component file %s: %s",
                    md_file.name,
                    exc,
                )

        logger.info("Loaded %d Zest components from %s", len(components), self.components_dir)
        self._components_cache = components
        self._figma_index = None
        return components

    def get_components_for_platform(self, platform: str) -> Dict[str, ZestComponent]:
        """
        Return components that support a given platform.

        Args:
            platform: Platform identifier, typically ``"web"`` or ``"rn"``.

        Returns:
            Dict of matching components keyed by name.
        """
        all_components = self.load_components()
        return {
            name: comp
            for name, comp in all_components.items()
            if platform in comp.platforms
        }

    def get_component_by_category(self, category: str) -> Dict[str, ZestComponent]:
        """
        Return components belonging to a specific category.

        Args:
            category: Category string (e.g., ``"interactive"``, ``"layout"``).

        Returns:
            Dict of matching components keyed by name.
        """
        all_components = self.load_components()
        return {
            name: comp
            for name, comp in all_components.items()
            if comp.category == category
        }

    def get_component_mapping(self) -> List[Dict[str, Any]]:
        """
        Build a full Figma-to-code mapping table for every component.

        Returns:
            List of mapping dicts, sorted by component name then platform.
        """
        all_components = self.load_components()
        mapping: List[Dict[str, Any]] = []

        for name in sorted(all_components):
            comp = all_components[name]
            for platform in sorted(comp.platforms):
                plat_info = comp.platforms[platform]
                mapping.append(
                    {
                        "component_name": comp.name,
                        "platform": platform,
                        "code_name": plat_info.get("code_name", comp.name),
                        "package": plat_info.get("package", ""),
                        "figma_names": list(plat_info.get("figma_names", [])),
                        "category": comp.category,
                        "is_composite": comp.is_composite,
                    }
                )

        return mapping

    def find_component_by_figma_name(self, figma_name: str) -> Optional[ZestComponent]:
        """
        Reverse-lookup a component by its Figma layer name.

        Args:
            figma_name: Figma component / layer name (e.g., ``"Button Brand"``).

        Returns:
            The matching ZestComponent, or ``None`` if no match is found.
        """
        index = self._build_figma_index()
        return index.get(figma_name.lower())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_figma_index(self) -> Dict[str, ZestComponent]:
        """Build (or return cached) case-insensitive Figma-name index."""
        if self._figma_index is not None:
            return self._figma_index

        all_components = self.load_components()
        index: Dict[str, ZestComponent] = {}

        for comp in all_components.values():
            for fname in comp.figma_names:
                key = fname.lower()
                if key in index:
                    logger.debug(
                        "Duplicate Figma name '%s' — maps to both '%s' and '%s'; "
                        "keeping first.",
                        fname,
                        index[key].name,
                        comp.name,
                    )
                else:
                    index[key] = comp

        self._figma_index = index
        return index

    def _parse_component_file(self, file_path: Path) -> Optional[ZestComponent]:
        """
        Parse a single component entity markdown file.

        Args:
            file_path: Path to the ``.md`` file.

        Returns:
            A ZestComponent, or ``None`` if the file lacks required fields.
        """
        content = file_path.read_text(encoding="utf-8")
        frontmatter = self._parse_frontmatter(content)

        if frontmatter is None:
            logger.warning("No YAML frontmatter found in %s", file_path.name)
            return None

        name = frontmatter.get("name")
        if not name:
            logger.warning("Missing 'name' in %s", file_path.name)
            return None

        metadata = frontmatter.get("metadata") or {}
        platforms_raw = metadata.get("platforms") or {}
        category = metadata.get("category", "unknown")
        is_composite = bool(metadata.get("is_composite", False))

        platforms: Dict[str, Dict[str, Any]] = {}
        all_figma_names: Set[str] = set()

        for plat_key, plat_data in platforms_raw.items():
            if not isinstance(plat_data, dict):
                continue
            platforms[plat_key] = plat_data
            figma_list = plat_data.get("figma_names") or []
            if isinstance(figma_list, list):
                for fn in figma_list:
                    if fn:
                        all_figma_names.add(str(fn))

        aliases_raw = frontmatter.get("$aliases") or []
        aliases = [str(a) for a in aliases_raw] if isinstance(aliases_raw, list) else []

        return ZestComponent(
            name=name,
            category=category,
            platforms=platforms,
            aliases=aliases,
            is_composite=is_composite,
            figma_names=all_figma_names,
            brain_entity_path=str(file_path),
        )

    @staticmethod
    def _parse_frontmatter(content: str) -> Optional[Dict[str, Any]]:
        """
        Parse YAML frontmatter from a markdown file.

        Attempts PyYAML if available, falls back to regex-based parser.

        Args:
            content: Full file text including ``---`` delimiters.

        Returns:
            Parsed dict, or ``None`` if frontmatter is missing or invalid.
        """
        if yaml is not None:
            match = re.match(r"^---\n(.+?)\n---", content, re.DOTALL)
            if not match:
                return None
            try:
                return yaml.safe_load(match.group(1))
            except Exception:
                return None

        return _parse_frontmatter_fallback(content)
