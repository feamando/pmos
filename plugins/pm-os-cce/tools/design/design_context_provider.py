"""
PM-OS CCE DesignContextProvider (v5.0)

Unified design system + codebase knowledge provider. Composes ZestLoader
(components), BrandThemeResolver (brand tokens), and Brain repo profiles
into a single DesignContext that any consumer can use: context doc generator,
deep research swarm, spec exporter, prototype engine.

Usage:
    from pm_os_cce.tools.design.design_context_provider import DesignContextProvider
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    from pm_os_cce.tools.design.brand_theme import (
        PRODUCT_BRAND_MAP,
        BrandTheme,
        BrandThemeResolver,
    )
except ImportError:
    from design.brand_theme import PRODUCT_BRAND_MAP, BrandTheme, BrandThemeResolver

try:
    from pm_os_cce.tools.design.zest_loader import ZestComponent, ZestLoader
except ImportError:
    from design.zest_loader import ZestComponent, ZestLoader

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class DesignContext:
    """
    Unified design system + codebase snapshot for a product.

    Attributes:
        product_id: Product identifier (e.g., "my-product").
        brand: Resolved brand theme with colors and typography.
        components: Zest components filtered by platform.
        token_summary: Key brand tokens (colors, font, spacing, radius).
        component_mapping_table: Pre-formatted markdown Figma-to-Code table.
        repo_profiles: Tech stack summaries from Brain Technical entities.
        figma_file_key: Figma file key from feature artifacts (if provided).
        figma_components_used: Zest component names used in Figma.
        figma_screens: Frame/screen names from Figma file.
    """

    product_id: str
    brand: Optional[BrandTheme] = None
    components: List[ZestComponent] = field(default_factory=list)
    token_summary: Dict[str, str] = field(default_factory=dict)
    component_mapping_table: str = ""
    repo_profiles: List[Dict[str, Any]] = field(default_factory=list)
    figma_file_key: Optional[str] = None
    figma_components_used: List[str] = field(default_factory=list)
    figma_screens: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class DesignContextProvider:
    """
    Single entry point for design system + codebase knowledge.

    Composes:
    - ZestLoader: Zest component library from Brain entities
    - BrandThemeResolver: Brand colors, typography, spacing
    - Brain repo profiles: Tech stack from tech_context_sync.py

    Typical usage::

        provider = DesignContextProvider("my-product")
        ctx = provider.get_context()
        print(ctx.component_mapping_table)

    Or with platform override::

        ctx = provider.get_context(platform="rn")
    """

    def __init__(
        self,
        product_id: str,
        user_path: Optional[str] = None,
    ) -> None:
        """
        Initialize the design context provider.

        Args:
            product_id: Product identifier (e.g., "my-product").
            user_path: Path to user/ directory. Auto-detected via get_paths()
                if not provided.
        """
        self.product_id = product_id

        if user_path:
            self._user_path = Path(user_path)
        else:
            try:
                paths = get_paths()
                self._user_path = Path(paths.get("user_dir", "user"))
            except Exception:
                self._user_path = Path("user")

        self._brain_path = self._user_path / "brain"
        self._zest_loader = ZestLoader(str(self._brain_path))
        self._theme_resolver = BrandThemeResolver()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_context(
        self,
        platform: Optional[str] = None,
        figma_file_key: Optional[str] = None,
    ) -> DesignContext:
        """
        Build a unified design context for the product.

        Args:
            platform: Filter components by platform ("web" or "rn").
                Defaults to "web".
            figma_file_key: Optional Figma file key for design analysis.

        Returns:
            DesignContext with components, tokens, repo profiles, and mappings.
        """
        platform = platform or "web"

        # -- Brand theme --
        brand = self._theme_resolver.resolve_theme(self.product_id)

        # -- Components --
        components_dict = self._zest_loader.get_components_for_platform(platform)
        components = list(components_dict.values())

        # -- Token summary --
        token_summary = self._build_token_summary(brand)

        # -- Component mapping table --
        mapping_table = self._build_component_mapping_table(platform)

        # -- Repo profiles --
        repo_profiles = self._load_repo_profiles()

        # -- Figma analysis (optional — FigmaClient may not be configured) --
        figma_components_used: List[str] = []
        figma_screens: List[str] = []

        if figma_file_key:
            try:
                from pm_os_cce.tools.design.figma_client import FigmaClient
            except ImportError:
                try:
                    from design.figma_client import FigmaClient
                except ImportError:
                    FigmaClient = None  # type: ignore[assignment,misc]

            if FigmaClient is not None:
                try:
                    figma = FigmaClient()
                    if figma.is_authenticated():
                        screens = figma.get_screen_list(figma_file_key)
                        figma_screens = [s.name for s in screens]

                        instances = figma.get_component_instances(
                            figma_file_key, zest_loader=self._zest_loader
                        )
                        figma_components_used = [
                            inst.zest_match or inst.name for inst in instances
                        ]

                        logger.info(
                            "Figma analysis: %d screens, %d components (%d Zest matches)",
                            len(figma_screens),
                            len(instances),
                            sum(1 for i in instances if i.zest_match),
                        )
                    else:
                        logger.debug("FigmaClient not authenticated — skipping Figma analysis")
                except Exception as exc:
                    logger.warning("Figma analysis failed: %s", exc)

        ctx = DesignContext(
            product_id=self.product_id,
            brand=brand,
            components=components,
            token_summary=token_summary,
            component_mapping_table=mapping_table,
            repo_profiles=repo_profiles,
            figma_file_key=figma_file_key,
            figma_components_used=figma_components_used,
            figma_screens=figma_screens,
        )

        logger.info(
            "DesignContext for %s: %d components, %d repo profiles, brand=%s, "
            "%d figma screens, %d figma components",
            self.product_id,
            len(components),
            len(repo_profiles),
            brand.brand_name if brand else "unknown",
            len(figma_screens),
            len(figma_components_used),
        )

        return ctx

    # ------------------------------------------------------------------
    # Token summary
    # ------------------------------------------------------------------

    def _build_token_summary(self, brand: BrandTheme) -> Dict[str, str]:
        """
        Extract key design tokens from the brand theme.

        Returns a flat dict of the most important tokens for documentation
        and context injection.
        """
        return {
            "brand_name": brand.brand_name,
            "primary_color": brand.primary_color,
            "secondary_color": brand.secondary_color,
            "accent_color": brand.accent_color,
            "background_color": brand.background_color,
            "surface_color": brand.surface_color,
            "text_color": brand.text_color,
            "font_family": brand.font_family,
            "font_family_heading": brand.font_family_heading,
            "border_radius": brand.border_radius,
        }

    # ------------------------------------------------------------------
    # Component mapping table (markdown)
    # ------------------------------------------------------------------

    def _build_component_mapping_table(self, platform: str) -> str:
        """
        Build a markdown Figma-to-Code mapping table.

        Columns: Component | Category | Web Code | RN Code | Figma Name(s)
        """
        all_components = self._zest_loader.load_components()

        if not all_components:
            return ""

        lines = [
            f"*{len(all_components)} Zest components available "
            f"(synced from spec-machine).*\n",
            "| Component | Category | Web Code | RN Code | Figma Name(s) |",
            "|-----------|----------|----------|---------|---------------|",
        ]

        for name in sorted(all_components):
            comp = all_components[name]
            web_info = comp.platforms.get("web", {})
            rn_info = comp.platforms.get("rn", {})

            web_code = web_info.get("code_name", "-") if web_info else "-"
            rn_code = rn_info.get("code_name", "-") if rn_info else "-"

            figma_names: Set[str] = set()
            for plat_data in comp.platforms.values():
                for fn in plat_data.get("figma_names", []):
                    if fn:
                        figma_names.add(fn)
            figma_str = ", ".join(sorted(figma_names)[:3]) if figma_names else "-"

            lines.append(
                f"| {comp.name} | {comp.category} | {web_code} | {rn_code} | {figma_str} |"
            )

        lines.append(
            "\n*Full mapping details in `brain/Entities/Components/`.*"
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Repo profiles
    # ------------------------------------------------------------------

    def _load_repo_profiles(self) -> List[Dict[str, Any]]:
        """
        Load repository tech stack profiles from Brain Technical entities.

        Reads markdown files from user/brain/Technical/repositories/*.md
        and extracts tech stack tables and key directories.
        """
        repos_dir = self._brain_path / "Technical" / "repositories"
        if not repos_dir.exists():
            logger.debug("No repo profiles directory: %s", repos_dir)
            return []

        profiles = []
        for md_file in sorted(repos_dir.glob("*.md")):
            try:
                profile = self._parse_repo_profile(md_file)
                if profile:
                    profiles.append(profile)
            except Exception as exc:
                logger.warning("Skipping repo profile %s: %s", md_file.name, exc)

        return profiles

    def _parse_repo_profile(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Parse a repository profile markdown file.

        Extracts:
        - name: Repo name from H1 heading
        - description: From Overview section
        - tech_stack: Dict from Tech Stack table
        - key_deps: List from Key Dependencies
        - key_dirs: List from Key Directories
        """
        content = file_path.read_text(encoding="utf-8")

        profile: Dict[str, Any] = {
            "file": str(file_path),
            "name": file_path.stem.replace("_", "/"),
        }

        # Extract name from H1
        h1_match = re.search(r"^# (.+)$", content, re.MULTILINE)
        if h1_match:
            profile["name"] = h1_match.group(1).strip()

        # Extract description
        desc_match = re.search(
            r"\*\*Description:\*\*\s*(.+?)$", content, re.MULTILINE
        )
        if desc_match:
            profile["description"] = desc_match.group(1).strip()

        # Extract tech stack table
        tech_stack: Dict[str, str] = {}
        tech_section = re.search(
            r"## Tech Stack\s*\n(.*?)(?=\n## |\n---|\Z)", content, re.DOTALL
        )
        if tech_section:
            rows = re.findall(
                r"\|\s*(\w[\w\s]*?)\s*\|\s*(.+?)\s*\|",
                tech_section.group(1),
            )
            for key, val in rows:
                key_clean = key.strip()
                val_clean = val.strip()
                if key_clean not in ("Component", "---", "--------"):
                    tech_stack[key_clean] = val_clean
        profile["tech_stack"] = tech_stack

        # Extract key dependencies
        deps_section = re.search(
            r"### Key Dependencies\s*\n(.*?)(?=\n## |\n###|\n---|\Z)",
            content,
            re.DOTALL,
        )
        if deps_section:
            deps = re.findall(r"^- (.+)$", deps_section.group(1), re.MULTILINE)
            profile["key_deps"] = [d.strip() for d in deps]
        else:
            profile["key_deps"] = []

        # Extract primary language
        lang_match = re.search(
            r"\*\*Primary Language:\*\*\s*(.+?)$", content, re.MULTILINE
        )
        if lang_match:
            profile["primary_language"] = lang_match.group(1).strip()

        # Extract Deep Analysis data (from CodebaseAnalyzer)
        deep_section = re.search(
            r"## Deep Analysis\s*\n(.*?)(?=\n## |\n---|\Z)", content, re.DOTALL
        )
        if deep_section:
            deep = deep_section.group(1)

            # Architecture
            arch_match = re.search(r"\*\*Architecture:\*\*\s*(.+?)$", deep, re.MULTILINE)
            if arch_match:
                profile["architecture"] = arch_match.group(1).strip()

            # Total features
            feat_match = re.search(r"\*\*Total Features:\*\*\s*(\d+)", deep)
            if feat_match:
                profile["total_features"] = int(feat_match.group(1))

            # Routing type
            routing_match = re.search(r"### Routing:\s*(.+?)$", deep, re.MULTILINE)
            if routing_match:
                profile["routing_type"] = routing_match.group(1).strip()

            # Routes
            route_items = re.findall(r"^- `([^`]+)`\s*\((\w+)\)", deep, re.MULTILINE)
            if route_items:
                profile["routes"] = [
                    {"path": path, "type": rtype}
                    for path, rtype in route_items[:20]
                ]

            # Services
            svc_section = re.search(
                r"### Shared Services.*?\n(.*?)(?=\n### |\Z)", deep, re.DOTALL
            )
            if svc_section:
                svc_items = re.findall(
                    r"^- `([^`]+)`\s*\(([^)]+)\)", svc_section.group(1), re.MULTILINE
                )
                profile["services"] = [
                    {"path": path, "name": name}
                    for path, name in svc_items[:30]
                ]

            # Feature flags
            ff_match = re.search(r"### Feature Flags \((\w+)\)", deep)
            if ff_match:
                profile["feature_flag_provider"] = ff_match.group(1)

            # Feature directories count
            fd_match = re.search(r"### Feature Directories \((\d+)\)", deep)
            if fd_match:
                profile["feature_dir_count"] = int(fd_match.group(1))

            profile["has_deep_analysis"] = True

        return profile
