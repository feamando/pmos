"""
PM-OS CCE BrandTheme (v5.0)

Resolves brand colors, typography, and design tokens per product/brand
for use in prototype generation. Config-driven with generic defaults;
brand palettes loaded from config or built-in registry.

Usage:
    from pm_os_cce.tools.design.brand_theme import BrandThemeResolver, BrandTheme
"""

import logging
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from core.config_loader import get_config

logger = logging.getLogger(__name__)


@dataclass
class BrandTheme:
    """Complete brand theme specification for prototype rendering."""

    brand_name: str
    brand_id: str
    # Core colors
    primary_color: str
    secondary_color: str
    accent_color: str
    background_color: str = "#FFFFFF"
    surface_color: str = "#F9FAFB"
    text_color: str = "#1F2937"
    text_secondary_color: str = "#6B7280"
    error_color: str = "#EF4444"
    success_color: str = "#10B981"
    warning_color: str = "#F59E0B"
    # Typography
    font_family: str = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    font_family_heading: str = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    # Border & radius
    border_radius: str = "8px"
    border_color: str = "#E5E7EB"
    # Shadows
    shadow_sm: str = "0 1px 2px 0 rgba(0, 0, 0, 0.05)"
    shadow_md: str = "0 4px 6px -1px rgba(0, 0, 0, 0.1)"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Generic default theme (no company-specific branding)
# ---------------------------------------------------------------------------

_DEFAULT_THEME = BrandTheme(
    brand_name="Default",
    brand_id="default",
    primary_color="#3B82F6",
    secondary_color="#1E293B",
    accent_color="#F59E0B",
    background_color="#FFFFFF",
    surface_color="#F9FAFB",
    text_color="#1F2937",
    text_secondary_color="#6B7280",
    font_family="'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    font_family_heading="'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    border_radius="8px",
)

# Built-in brand palette registry (config can extend/override)
BRAND_THEMES: Dict[str, BrandTheme] = {}

# Product ID to brand key mapping (config can extend/override)
PRODUCT_BRAND_MAP: Dict[str, str] = {}

# Default brand key used when product has no mapping
DEFAULT_BRAND = "default"


def _load_brand_registry() -> None:
    """Populate BRAND_THEMES and PRODUCT_BRAND_MAP from config."""
    global DEFAULT_BRAND

    try:
        config = get_config()
    except Exception:
        return

    # Load brand themes from config: design.brands.<key>
    brands_cfg = config.get("design.brands", {})
    if isinstance(brands_cfg, dict):
        for key, vals in brands_cfg.items():
            if not isinstance(vals, dict):
                continue
            try:
                BRAND_THEMES[key] = BrandTheme(
                    brand_name=vals.get("brand_name", key.replace("-", " ").title()),
                    brand_id=key,
                    primary_color=vals.get("primary_color", _DEFAULT_THEME.primary_color),
                    secondary_color=vals.get("secondary_color", _DEFAULT_THEME.secondary_color),
                    accent_color=vals.get("accent_color", _DEFAULT_THEME.accent_color),
                    background_color=vals.get("background_color", _DEFAULT_THEME.background_color),
                    surface_color=vals.get("surface_color", _DEFAULT_THEME.surface_color),
                    text_color=vals.get("text_color", _DEFAULT_THEME.text_color),
                    text_secondary_color=vals.get("text_secondary_color", _DEFAULT_THEME.text_secondary_color),
                    error_color=vals.get("error_color", _DEFAULT_THEME.error_color),
                    success_color=vals.get("success_color", _DEFAULT_THEME.success_color),
                    warning_color=vals.get("warning_color", _DEFAULT_THEME.warning_color),
                    font_family=vals.get("font_family", _DEFAULT_THEME.font_family),
                    font_family_heading=vals.get("font_family_heading", _DEFAULT_THEME.font_family_heading),
                    border_radius=vals.get("border_radius", _DEFAULT_THEME.border_radius),
                    border_color=vals.get("border_color", _DEFAULT_THEME.border_color),
                    shadow_sm=vals.get("shadow_sm", _DEFAULT_THEME.shadow_sm),
                    shadow_md=vals.get("shadow_md", _DEFAULT_THEME.shadow_md),
                )
            except Exception as exc:
                logger.warning("Skipping brand config '%s': %s", key, exc)

    # Load product-to-brand mapping from config
    product_map_cfg = config.get("design.product_brand_map", {})
    if isinstance(product_map_cfg, dict):
        PRODUCT_BRAND_MAP.update(product_map_cfg)

    # Default brand from config
    default_cfg = config.get("design.default_brand", "")
    if default_cfg:
        DEFAULT_BRAND = default_cfg


# Attempt to load on import (silently degrades if config unavailable)
try:
    _load_brand_registry()
except Exception:
    pass

# Ensure default theme is always present
if "default" not in BRAND_THEMES:
    BRAND_THEMES["default"] = _DEFAULT_THEME


class BrandThemeResolver:
    """Resolves brand themes from product IDs or brand names.

    Uses config-driven brand palettes with generic defaults.
    Supports CSS custom property and Tailwind config generation.
    """

    def __init__(self, config_path: Optional[str] = None):
        """Initialize resolver.

        Args:
            config_path: Optional path to user/config.yaml for product lookup.
        """
        self._config_path = config_path

    def resolve_theme(self, product_id: str) -> BrandTheme:
        """Resolve brand theme for a product.

        Args:
            product_id: Product identifier (e.g., 'my-product', 'brand-x').

        Returns:
            BrandTheme with full color/typography specification.
        """
        brand_key = PRODUCT_BRAND_MAP.get(product_id, DEFAULT_BRAND)
        theme = BRAND_THEMES.get(brand_key)

        if theme is None:
            logger.warning(
                "Unknown brand '%s' for product '%s', using default",
                brand_key, product_id,
            )
            theme = BRAND_THEMES.get(DEFAULT_BRAND, _DEFAULT_THEME)

        return theme

    def resolve_by_brand_name(self, brand_name: str) -> BrandTheme:
        """Resolve theme directly by brand name.

        Args:
            brand_name: Brand name or ID (e.g., 'My Brand', 'my-brand').

        Returns:
            BrandTheme for the brand.
        """
        # Try direct key lookup
        key = brand_name.lower().replace(" ", "-")
        if key in BRAND_THEMES:
            return BRAND_THEMES[key]

        # Try matching by brand_name field
        for theme in BRAND_THEMES.values():
            if theme.brand_name.lower() == brand_name.lower():
                return theme

        logger.warning("Unknown brand '%s', using default", brand_name)
        return BRAND_THEMES.get(DEFAULT_BRAND, _DEFAULT_THEME)

    def list_available_brands(self) -> List[dict]:
        """List all available brand themes.

        Returns:
            List of dicts with brand_id and brand_name.
        """
        return [
            {"brand_id": t.brand_id, "brand_name": t.brand_name}
            for t in BRAND_THEMES.values()
        ]

    def generate_css_variables(self, theme: BrandTheme) -> str:
        """Generate CSS custom properties from a theme.

        Args:
            theme: BrandTheme to convert.

        Returns:
            CSS string with :root custom properties.
        """
        return f""":root {{
  /* {theme.brand_name} Theme */
  --color-primary: {theme.primary_color};
  --color-secondary: {theme.secondary_color};
  --color-accent: {theme.accent_color};
  --color-background: {theme.background_color};
  --color-surface: {theme.surface_color};
  --color-text: {theme.text_color};
  --color-text-secondary: {theme.text_secondary_color};
  --color-error: {theme.error_color};
  --color-success: {theme.success_color};
  --color-warning: {theme.warning_color};
  --color-border: {theme.border_color};
  --font-family: {theme.font_family};
  --font-family-heading: {theme.font_family_heading};
  --border-radius: {theme.border_radius};
  --shadow-sm: {theme.shadow_sm};
  --shadow-md: {theme.shadow_md};
}}"""

    def generate_tailwind_config(self, theme: BrandTheme) -> dict:
        """Generate Tailwind CSS config extend block from a theme.

        Args:
            theme: BrandTheme to convert.

        Returns:
            Dict suitable for tailwind.config.js theme.extend.
        """
        return {
            "colors": {
                "primary": theme.primary_color,
                "secondary": theme.secondary_color,
                "accent": theme.accent_color,
                "background": theme.background_color,
                "surface": theme.surface_color,
                "foreground": theme.text_color,
                "muted": theme.text_secondary_color,
                "destructive": theme.error_color,
                "success": theme.success_color,
                "warning": theme.warning_color,
                "border": theme.border_color,
            },
            "fontFamily": {
                "sans": [theme.font_family],
                "heading": [theme.font_family_heading],
            },
            "borderRadius": {
                "DEFAULT": theme.border_radius,
            },
        }
