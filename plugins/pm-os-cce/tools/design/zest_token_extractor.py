"""
PM-OS CCE ZestTokenExtractor (v5.0)

Fetches, resolves, and generates CSS from real Zest design tokens.
Connects to a design token GitHub repo via ``gh api``, resolves
the token reference chains, and produces a CSS file with real design
tokens for static HTML prototypes.

Three classes work as a pipeline:
    ZestTokenFetcher  ->  ZestTokenResolver  ->  ZestCssGenerator

Usage:
    from pm_os_cce.tools.design.zest_token_extractor import generate_brand_css
"""

import base64
import json
import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from core.config_loader import get_config
    except ImportError:
        get_config = None  # type: ignore[assignment]

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        from core.path_resolver import get_paths
    except ImportError:
        get_paths = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _get_token_repo() -> str:
    """Get the design token GitHub repo from config."""
    if get_config is not None:
        try:
            config = get_config()
            repo = config.get("design.token_repo", "")
            if repo:
                return repo
        except Exception:
            pass
    return ""


def _get_assets_dir() -> str:
    """Get assets directory from config/paths."""
    if get_paths is not None:
        try:
            paths = get_paths()
            assets = paths.get("assets_dir", "")
            if assets:
                return assets
        except Exception:
            pass
    return ""


CACHE_TTL_SECONDS = 86400  # 24 hours

# Component token files to fetch (subset of available)
COMPONENT_FILES = [
    "button", "card", "badge", "checkbox", "dialog", "input-field",
    "switch", "radio-button", "spinner", "toast", "banner-message",
    "tab-group", "accordion", "dropdown", "divider", "progress-bar",
    "drawer", "tooltip", "feedback-bar", "tag", "number-stepper",
]

# Regex for {reference.path} patterns
REF_PATTERN = re.compile(r"\{([^}]+)\}")

MAX_RESOLUTION_PASSES = 25


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------


class ZestTokenFetcher:
    """Downloads token JSON files from a design token repo via ``gh api``."""

    def __init__(self, cache_dir: Optional[str] = None, repo: Optional[str] = None) -> None:
        self._repo = repo or _get_token_repo()
        if cache_dir:
            self._cache = Path(cache_dir)
        else:
            assets = _get_assets_dir()
            if assets:
                self._cache = Path(assets) / "zest" / ".tokens_cache"
            else:
                self._cache = Path(".tokens_cache")
        self._cache.mkdir(parents=True, exist_ok=True)

    def fetch_brand_tokens(self, brand: str) -> Dict[str, Any]:
        """
        Fetch all token files needed for a brand.

        Returns::

            {
                "global": { ... },
                "shared_alias": { ... },
                "brand": { ... },
                "components": { "button": {...}, "card": {...}, ... }
            }
        """
        if not self._repo:
            logger.warning("No design token repo configured (design.token_repo)")
            return {}

        result: Dict[str, Any] = {}

        result["global"] = self._fetch_file("tokens/global.json")
        result["shared_alias"] = self._fetch_file("tokens/shared-alias.json")
        result["brand"] = self._fetch_file(f"tokens/brand/{brand}.json")

        components: Dict[str, dict] = {}
        for comp in COMPONENT_FILES:
            try:
                components[comp] = self._fetch_file(f"tokens/components/{comp}.json")
            except Exception as exc:
                logger.debug("Skipping component %s: %s", comp, exc)
        result["components"] = components

        logger.info(
            "Fetched tokens for brand=%s: global, shared-alias, brand, %d components",
            brand,
            len(components),
        )
        return result

    # -- internal --

    def _fetch_file(self, repo_path: str) -> dict:
        cache_path = self._get_cache_path(repo_path)
        if self._is_cache_fresh(cache_path):
            logger.debug("Cache hit: %s", cache_path)
            return json.loads(cache_path.read_text(encoding="utf-8"))
        data = self._fetch_from_github(repo_path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data

    def _fetch_from_github(self, repo_path: str) -> dict:
        cmd = [
            "gh", "api",
            f"repos/{self._repo}/contents/{repo_path}",
            "--jq", ".content",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            raise RuntimeError(
                f"gh api failed for {repo_path}: {proc.stderr.strip()}"
            )
        raw = base64.b64decode(proc.stdout.strip())
        return json.loads(raw)

    def _get_cache_path(self, repo_path: str) -> Path:
        safe = repo_path.replace("/", "__")
        return self._cache / safe

    def _is_cache_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        age = time.time() - path.stat().st_mtime
        return age < CACHE_TTL_SECONDS

    def clear_cache(self) -> None:
        """Remove all cached token files."""
        for f in self._cache.glob("*"):
            if f.is_file():
                f.unlink()
        logger.info("Token cache cleared")


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


class ZestTokenResolver:
    """
    Resolves ``{reference}`` chains across token dictionaries.

    Merges global -> shared-alias -> brand -> components, then iteratively
    replaces ``{path}`` references with their resolved values.
    """

    def __init__(self) -> None:
        self._registry: Dict[str, str] = {}
        self._types: Dict[str, str] = {}

    def resolve(self, token_sets: Dict[str, Any]) -> Dict[str, str]:
        """Resolve all references and return flat dict of path -> CSS value."""
        self._registry.update(self._flatten(token_sets.get("global", {})))
        self._registry.update(self._flatten(token_sets.get("shared_alias", {})))
        self._registry.update(self._flatten(token_sets.get("brand", {})))
        for comp_name, comp_data in token_sets.get("components", {}).items():
            self._registry.update(self._flatten(comp_data))

        for pass_num in range(MAX_RESOLUTION_PASSES):
            changes = 0
            for key in list(self._registry):
                val = self._registry[key]
                if not isinstance(val, str) or "{" not in val:
                    continue
                resolved = self._resolve_value(val)
                if resolved != val:
                    self._registry[key] = resolved
                    changes += 1
            if changes == 0:
                break
            logger.debug("Resolution pass %d: %d changes", pass_num + 1, changes)

        # Post-process: convert rgba(#hex, alpha) to proper CSS
        for key in list(self._registry):
            val = self._registry[key]
            if isinstance(val, str) and "rgba(#" in val:
                self._registry[key] = self._hex_rgba_to_css(val)

        unresolved = [k for k, v in self._registry.items() if isinstance(v, str) and "{" in v]
        if unresolved:
            logger.debug("%d unresolved tokens remain", len(unresolved))

        return dict(self._registry)

    # -- flattening --

    def _flatten(self, data: dict, prefix: str = "") -> Dict[str, str]:
        result: Dict[str, str] = {}
        for key, val in data.items():
            if key.startswith("$"):
                continue
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(val, dict):
                if "value" in val:
                    raw = val["value"]
                    token_type = val.get("type", "")
                    self._types[path] = token_type
                    if isinstance(raw, dict) and raw.get("type") == "dropShadow":
                        result[path] = self._shadow_to_css(raw)
                    elif isinstance(raw, list):
                        parts = []
                        for item in raw:
                            if isinstance(item, dict) and item.get("type") == "dropShadow":
                                parts.append(self._shadow_to_css(item))
                        result[path] = ", ".join(parts) if parts else str(raw)
                    else:
                        result[path] = str(raw)
                else:
                    result.update(self._flatten(val, path))
        return result

    # -- reference resolution --

    def _resolve_value(self, value: str) -> str:
        def _replace(match):
            ref = match.group(1)
            if ref in self._registry:
                return str(self._registry[ref])
            return match.group(0)
        return REF_PATTERN.sub(_replace, value)

    # -- shadow handling --

    @staticmethod
    def _shadow_to_css(s: dict) -> str:
        x = s.get("x", "0")
        y = s.get("y", "0")
        blur = s.get("blur", "0")
        spread = s.get("spread", "0")
        color = s.get("color", "rgba(0,0,0,0.1)")
        return f"{x}px {y}px {blur}px {spread}px {color}"

    # -- rgba post-processing --

    @staticmethod
    def _hex_rgba_to_css(val: str) -> str:
        """Convert ``rgba(#aabbcc, 0.4)`` to ``rgba(r, g, b, 0.4)``."""
        pattern = re.compile(r"rgba\(\s*#([0-9a-fA-F]{6})\s*,\s*([0-9.]+)\s*\)")
        def _convert(m):
            hex_str = m.group(1)
            alpha = m.group(2)
            r = int(hex_str[0:2], 16)
            g = int(hex_str[2:4], 16)
            b = int(hex_str[4:6], 16)
            return f"rgba({r}, {g}, {b}, {alpha})"
        return pattern.sub(_convert, val)

    def get_unresolved(self) -> List[str]:
        return [k for k, v in self._registry.items() if isinstance(v, str) and "{" in v]


# ---------------------------------------------------------------------------
# CSS Generator
# ---------------------------------------------------------------------------


class ZestCssGenerator:
    """Converts resolved Zest tokens to a CSS file."""

    def __init__(self, brand_name: str = "default") -> None:
        self.brand = brand_name

    def generate(
        self,
        tokens: Dict[str, str],
        output_path: Optional[str] = None,
    ) -> str:
        sections = [
            self._header(),
            self._font_import(),
            self._custom_properties(tokens),
            self._base_reset(),
            self._layout_scaffold(),
            self._button_css(tokens),
            self._card_css(tokens),
            self._input_css(tokens),
            self._badge_css(tokens),
            self._checkbox_radio_css(tokens),
            self._switch_css(tokens),
            self._dialog_css(tokens),
            self._spinner_css(tokens),
            self._progress_css(tokens),
            self._toast_banner_css(tokens),
            self._tab_css(tokens),
            self._misc_css(tokens),
            self._utilities(),
            self._responsive(),
        ]
        css = "\n\n".join(s for s in sections if s)

        if output_path:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(css, encoding="utf-8")
            logger.info("Wrote Zest CSS to %s (%d bytes)", p, len(css))

        return css

    # -- helpers --

    def _t(self, tokens: dict, path: str, fallback: str = "") -> str:
        """Get resolved token; skip unresolved refs."""
        val = tokens.get(path, fallback)
        if isinstance(val, str) and "{" in val:
            return fallback
        return val

    def _var(self, path: str, fallback: str = "") -> str:
        """Emit a CSS var() reference with fallback."""
        name = "--zest-" + path.replace(".", "-")
        if fallback:
            return f"var({name}, {fallback})"
        return f"var({name})"

    # -- sections --

    def _header(self) -> str:
        return f"/* Zest Design Tokens — {self.brand} — Generated by PM-OS */\n/* Source: design token repo */"

    def _font_import(self) -> str:
        return "@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700&display=swap');"

    def _custom_properties(self, tokens: dict) -> str:
        lines = [":root {"]

        for path in sorted(tokens):
            val = tokens[path]
            if isinstance(val, str) and "{" not in val and val:
                css_name = "--zest-" + path.replace(".", "-")
                lines.append(f"  {css_name}: {val};")

        # Legacy compatibility layer
        lines.append("")
        lines.append("  /* Legacy compatibility — maps to prototype_builder vars */")
        lines.append(f"  --color-primary: {self._t(tokens, 'color.brand.foreground.default', '#3B82F6')};")
        lines.append(f"  --color-secondary: {self._t(tokens, 'color.gray.800', '#242424')};")
        lines.append(f"  --color-accent: {self._t(tokens, 'color.accent.400', '#F59E0B')};")
        lines.append(f"  --color-bg: {self._t(tokens, 'color.white', '#ffffff')};")
        lines.append(f"  --color-surface: {self._t(tokens, 'color.gray.100', '#F9FAFB')};")
        lines.append(f"  --color-text: {self._t(tokens, 'color.gray.800', '#242424')};")
        lines.append(f"  --color-text-secondary: {self._t(tokens, 'color.gray.600', '#656565')};")
        lines.append("  --color-error: #EF4444;")
        lines.append("  --color-success: #10B981;")
        lines.append("  --color-warning: #F59E0B;")
        lines.append(f"  --color-border: {self._t(tokens, 'color.gray.300', '#e0e0e0')};")
        lines.append("  --font-family: 'Source Sans 3', 'Inter', sans-serif;")
        lines.append("  --font-heading: 'Source Sans 3', 'Inter', sans-serif;")
        lines.append(f"  --radius: {self._t(tokens, 'corner-radius.sm', '4')}px;")
        lines.append(f"  --shadow-sm: {self._t(tokens, 'shadow.sm', '0 1px 4px 0 rgba(0,0,0,0.1)')};")
        lines.append(f"  --shadow-md: {self._t(tokens, 'shadow.md', '0 2px 4px 0 rgba(0,0,0,0.15)')};")

        lines.append("}")
        return "\n".join(lines)

    def _base_reset(self) -> str:
        return """*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--font-family); color: var(--color-text); background: var(--color-bg); line-height: 1.6; }
h1,h2,h3,h4 { font-family: var(--font-heading); font-weight: 700; }"""

    def _layout_scaffold(self) -> str:
        return """.proto-container { max-width: 1200px; margin: 0 auto; padding: 1rem; }
.proto-screen { display: none; padding: 2rem 0; }
.proto-screen.active { display: block; }
.proto-grid { display: grid; gap: 1.5rem; }
.proto-grid-2 { grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
.proto-section { margin-bottom: 2rem; }

.proto-nav { background: var(--color-secondary); padding: 0.75rem 1.5rem; display: flex; align-items: center; gap: 1.5rem; position: sticky; top: 0; z-index: 100; }
.proto-nav-brand { color: white; font-weight: 700; font-size: 1.1rem; }
.proto-nav-links { display: flex; gap: 0.5rem; }
.proto-nav-link { color: rgba(255,255,255,0.7); text-decoration: none; padding: 0.4rem 0.8rem; border-radius: var(--radius); cursor: pointer; font-size: 0.9rem; border: none; background: none; }
.proto-nav-link:hover,.proto-nav-link.active { color: white; background: rgba(255,255,255,0.15); }"""

    def _button_css(self, t: dict) -> str:
        bg_primary = self._t(t, "color.action.background.primary.default",
                             self._t(t, "color.brand.background.default", "#3B82F6"))
        fg_primary = self._t(t, "color.action.foreground.primary.default",
                             self._t(t, "color.white", "#ffffff"))
        bg_hover = self._t(t, "color.action.background.primary.hover",
                           self._t(t, "color.brand.foreground.hover", "#2563EB"))
        bg_press = self._t(t, "color.action.background.primary.press",
                           self._t(t, "color.brand.foreground.darkest", "#1D4ED8"))
        bg_disabled = self._t(t, "color.action.background.primary.disabled", "rgba(59,130,246,0.4)")
        fg_secondary = self._t(t, "color.action.foreground.secondary.default",
                               self._t(t, "color.brand.foreground.default", "#3B82F6"))
        border_secondary = self._t(t, "color.action.border.secondary.default",
                                   self._t(t, "color.brand.border.default", "#3B82F6"))
        radius = self._t(t, "corner-radius.sm", "4")
        pad_y = self._t(t, "spacing.sm-1", "12")
        pad_x = self._t(t, "spacing.md-1", "24")
        pad_y_sm = self._t(t, "spacing.xs", "8")
        pad_x_sm = self._t(t, "spacing.sm-2", "16")
        gap = self._t(t, "spacing.xs", "8")

        return f"""/* Button */
.zest-btn {{ display: inline-flex; align-items: center; justify-content: center; gap: {gap}px; font-weight: 600; font-size: 0.9rem; cursor: pointer; border: none; transition: background-color 0.15s, color 0.15s, border-color 0.15s, opacity 0.15s; font-family: var(--font-family); }}
.zest-btn-primary {{ background: {bg_primary}; color: {fg_primary}; padding: {pad_y}px {pad_x}px; border-radius: {radius}px; }}
.zest-btn-primary:hover {{ background: {bg_hover}; }}
.zest-btn-primary:active {{ background: {bg_press}; }}
.zest-btn-primary:disabled {{ background: {bg_disabled}; cursor: not-allowed; }}
.zest-btn-secondary {{ background: transparent; color: {fg_secondary}; padding: {pad_y}px {pad_x}px; border-radius: {radius}px; border: 1px solid {border_secondary}; }}
.zest-btn-secondary:hover {{ background: var(--color-surface); }}
.zest-btn-tertiary {{ background: none; border: none; color: {fg_secondary}; padding: {pad_y}px {pad_x}px; text-decoration: underline; }}
.zest-btn-sm {{ padding: {pad_y_sm}px {pad_x_sm}px; font-size: 0.85rem; }}
.zest-btn-icon {{ background: none; border: none; cursor: pointer; font-size: 1.2rem; color: var(--color-text-secondary); }}"""

    def _card_css(self, t: dict) -> str:
        shadow = self._t(t, "shadow.sm", "0px 1px 4px 0px rgba(0,0,0,0.1)")
        shadow_hover = self._t(t, "shadow.md", "0px 2px 4px 0px rgba(0,0,0,0.15)")
        radius = self._t(t, "corner-radius.sm", "4")
        border_w = self._t(t, "border-width.default", "1")
        border_c = self._t(t, "color.gray.300", "#e0e0e0")

        return f"""/* Card */
.zest-card {{ background: var(--color-bg); border: {border_w}px solid {border_c}; border-radius: {radius}px; overflow: hidden; box-shadow: {shadow}; }}
.zest-card:hover {{ box-shadow: {shadow_hover}; }}
.zest-card-body {{ padding: 1.25rem; }}"""

    def _input_css(self, t: dict) -> str:
        border_default = self._t(t, "color.gray.300", "#e0e0e0")
        border_focus = self._t(t, "color.brand.border.default", "#3B82F6")
        text_color = self._t(t, "color.gray.800", "#242424")
        label_color = self._t(t, "color.gray.600", "#656565")
        error_color = "#EF4444"
        radius = self._t(t, "corner-radius.sm", "4")

        return f"""/* Input / Form */
.zest-input-group {{ display: flex; flex-direction: column; gap: 0.35rem; }}
.zest-label {{ font-size: 0.85rem; font-weight: 500; color: {label_color}; }}
.zest-input {{ padding: 0.6rem 0.8rem; border: 1px solid {border_default}; border-radius: {radius}px; font-size: 0.9rem; font-family: var(--font-family); color: {text_color}; background: var(--color-bg); }}
.zest-input:focus {{ outline: none; border-color: {border_focus}; box-shadow: 0 0 0 2px rgba(59,130,246,0.15); }}
.zest-input[aria-invalid="true"],.zest-input.error {{ border-color: {error_color}; }}
.zest-select {{ padding: 0.6rem 0.8rem; border: 1px solid {border_default}; border-radius: {radius}px; font-size: 0.9rem; background: white; }}
.zest-helper-text {{ font-size: 0.8rem; color: var(--color-text-secondary); }}"""

    def _badge_css(self, t: dict) -> str:
        brand_bg = self._t(t, "color.brand.background.default", "#3B82F6")
        accent_bg = self._t(t, "color.accent.400", "#F59E0B")
        radius = self._t(t, "corner-radius.pill", "999")

        return f"""/* Badge */
.zest-badge {{ display: inline-flex; padding: 0.15rem 0.5rem; font-size: 0.75rem; font-weight: 600; border-radius: {radius}px; background: {brand_bg}; color: white; }}
.zest-badge-accent {{ background: {accent_bg}; color: var(--color-text); }}
.zest-badge-neutral {{ background: var(--color-text-secondary); color: white; }}
.zest-badge-positive {{ background: var(--color-success); color: white; }}
.zest-badge-negative {{ background: var(--color-error); color: white; }}"""

    def _checkbox_radio_css(self, t: dict) -> str:
        brand = self._t(t, "color.brand.foreground.default", "#3B82F6")
        return f"""/* Checkbox & Radio */
.zest-checkbox,.zest-radio {{ display: flex; align-items: center; gap: 0.5rem; cursor: pointer; font-size: 0.9rem; }}
.zest-checkbox input[type="checkbox"],.zest-radio input[type="radio"] {{ width: 18px; height: 18px; accent-color: {brand}; }}
.zest-checkbox-mark,.zest-radio-mark {{ display: none; }}"""

    def _switch_css(self, t: dict) -> str:
        brand = self._t(t, "color.brand.background.default", "#3B82F6")
        border = self._t(t, "color.gray.300", "#e0e0e0")
        return f"""/* Switch */
.zest-switch {{ display: flex; align-items: center; gap: 0.5rem; cursor: pointer; }}
.zest-switch input {{ display: none; }}
.zest-switch-slider {{ width: 40px; height: 22px; background: {border}; border-radius: 11px; position: relative; transition: 0.2s; }}
.zest-switch-slider::after {{ content: ''; width: 18px; height: 18px; background: white; border-radius: 50%; position: absolute; top: 2px; left: 2px; transition: 0.2s; }}
.zest-switch input:checked + .zest-switch-slider {{ background: {brand}; }}
.zest-switch input:checked + .zest-switch-slider::after {{ left: 20px; }}"""

    def _dialog_css(self, t: dict) -> str:
        shadow = self._t(t, "shadow.xl", "0px 4px 16px 0px rgba(0,0,0,0.2)")
        radius = self._t(t, "corner-radius.md", "8")
        border = self._t(t, "color.gray.300", "#e0e0e0")
        return f"""/* Dialog */
.zest-dialog-backdrop {{ position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }}
.zest-dialog {{ background: white; border-radius: {radius}px; box-shadow: {shadow}; min-width: 400px; max-width: 90vw; }}
.zest-dialog-header {{ display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.25rem; border-bottom: 1px solid {border}; }}
.zest-dialog-body {{ padding: 1.25rem; }}"""

    def _spinner_css(self, t: dict) -> str:
        brand = self._t(t, "color.brand.foreground.default", "#3B82F6")
        border = self._t(t, "color.gray.300", "#e0e0e0")
        return f"""/* Spinner */
.zest-spinner {{ width: 24px; height: 24px; border: 3px solid {border}; border-top-color: {brand}; border-radius: 50%; animation: zest-spin 0.6s linear infinite; }}
@keyframes zest-spin {{ to {{ transform: rotate(360deg); }} }}"""

    def _progress_css(self, t: dict) -> str:
        brand = self._t(t, "color.brand.background.default", "#3B82F6")
        track = self._t(t, "color.gray.200", "#f7f7f7")
        return f"""/* Progress */
.zest-progress,.shadcn-progress {{ height: 8px; background: {track}; border-radius: 4px; overflow: hidden; }}
.zest-progress-bar,.shadcn-progress-bar {{ height: 100%; background: {brand}; border-radius: 4px; transition: width 0.3s; }}"""

    def _toast_banner_css(self, t: dict) -> str:
        border = self._t(t, "color.gray.300", "#e0e0e0")
        shadow = self._t(t, "shadow.md", "0px 2px 4px 0px rgba(0,0,0,0.15)")
        return f"""/* Toast & Banner */
.zest-toast {{ display: flex; align-items: center; justify-content: space-between; padding: 0.75rem 1rem; border-radius: var(--radius); box-shadow: {shadow}; }}
.zest-toast-info {{ background: var(--color-surface); border-left: 4px solid var(--color-primary); }}
.zest-banner {{ background: var(--color-surface); padding: 0.75rem 1rem; border-radius: var(--radius); border: 1px solid {border}; text-align: center; }}
.shadcn-alert {{ padding: 1rem; border: 1px solid {border}; border-radius: var(--radius); background: var(--color-surface); }}
.zest-snackbar {{ position: fixed; bottom: 1rem; left: 50%; transform: translateX(-50%); display: flex; align-items: center; gap: 1rem; padding: 0.75rem 1rem; background: var(--color-secondary); color: white; border-radius: var(--radius); box-shadow: {shadow}; }}
.zest-btn-text {{ background: none; border: none; color: var(--color-primary); font-weight: 600; cursor: pointer; }}"""

    def _tab_css(self, t: dict) -> str:
        brand = self._t(t, "color.brand.foreground.default", "#3B82F6")
        border = self._t(t, "color.gray.300", "#e0e0e0")
        return f"""/* Tabs */
.zest-tabs {{ border: 1px solid {border}; border-radius: var(--radius); overflow: hidden; }}
.zest-tab-list {{ display: flex; background: var(--color-surface); border-bottom: 1px solid {border}; }}
.zest-tab {{ padding: 0.6rem 1rem; border: none; background: none; cursor: pointer; font-size: 0.9rem; }}
.zest-tab.active {{ border-bottom: 2px solid {brand}; font-weight: 600; }}
.zest-tab-panel {{ padding: 1rem; }}"""

    def _misc_css(self, t: dict) -> str:
        brand = self._t(t, "color.brand.foreground.default", "#3B82F6")
        border = self._t(t, "color.gray.300", "#e0e0e0")
        shadow = self._t(t, "shadow.md", "0px 2px 4px 0px rgba(0,0,0,0.15)")

        return f"""/* Accordion */
.zest-accordion-item {{ border: 1px solid {border}; border-radius: var(--radius); margin-bottom: 0.5rem; }}
.zest-accordion-trigger {{ width: 100%; text-align: left; padding: 0.75rem 1rem; border: none; background: none; cursor: pointer; font-weight: 500; display: flex; justify-content: space-between; }}
.zest-accordion-content {{ max-height: 0; overflow: hidden; padding: 0 1rem; transition: 0.2s; }}
.zest-accordion-item.open .zest-accordion-content {{ max-height: 200px; padding: 0.75rem 1rem; }}

/* Avatar */
.zest-avatar {{ width: 40px; height: 40px; border-radius: 50%; background: var(--color-primary); color: white; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 0.9rem; }}

/* Chip */
.zest-chip {{ display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.25rem 0.6rem; font-size: 0.85rem; border-radius: 9999px; background: var(--color-surface); border: 1px solid {border}; }}
.zest-chip-remove {{ background: none; border: none; cursor: pointer; font-size: 0.9rem; }}

/* List */
.zest-list {{ list-style: none; border: 1px solid {border}; border-radius: var(--radius); overflow: hidden; }}
.zest-list-item {{ padding: 0.75rem 1rem; border-bottom: 1px solid {border}; }}
.zest-list-item:last-child {{ border-bottom: none; }}

/* Table */
.zest-table {{ width: 100%; border-collapse: collapse; }}
.zest-table th,.zest-table td {{ padding: 0.6rem 1rem; text-align: left; border-bottom: 1px solid {border}; }}
.zest-table th {{ font-weight: 600; background: var(--color-surface); font-size: 0.85rem; }}

/* Navbar */
.zest-navbar {{ display: flex; align-items: center; justify-content: space-between; padding: 0.75rem 1.5rem; background: var(--color-secondary); color: white; }}
.zest-navbar-brand {{ font-weight: 700; font-size: 1.1rem; }}
.zest-navbar-links {{ display: flex; gap: 1rem; }}
.zest-navbar-links a {{ color: rgba(255,255,255,0.8); text-decoration: none; }}
.zest-header {{ padding: 1.5rem; border-bottom: 1px solid {border}; }}
.zest-footer {{ padding: 1.5rem; border-top: 1px solid {border}; color: var(--color-text-secondary); font-size: 0.85rem; text-align: center; }}

/* Search */
.zest-searchbar {{ display: flex; gap: 0.5rem; }}
.zest-searchbar .zest-input {{ flex: 1; }}

/* Stepper */
.zest-stepper {{ display: flex; gap: 1rem; align-items: center; }}
.zest-step {{ display: flex; align-items: center; gap: 0.4rem; color: var(--color-text-secondary); }}
.zest-step.active {{ color: var(--color-primary); font-weight: 600; }}
.zest-step-num {{ width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: var(--color-surface); border: 2px solid {border}; font-size: 0.8rem; }}
.zest-step.active .zest-step-num {{ background: var(--color-primary); color: white; border-color: var(--color-primary); }}

/* Image */
.zest-image {{ border-radius: var(--radius); overflow: hidden; }}
.zest-image-placeholder {{ width: 100%; height: 200px; background: var(--color-surface); display: flex; align-items: center; justify-content: center; color: var(--color-text-secondary); }}

/* Dropdown */
.zest-dropdown {{ position: relative; display: inline-block; }}
.zest-dropdown-menu {{ position: absolute; top: 100%; left: 0; background: white; border: 1px solid {border}; border-radius: var(--radius); box-shadow: {shadow}; display: none; min-width: 160px; z-index: 10; }}
.zest-dropdown-menu.open {{ display: block; }}
.zest-dropdown-item {{ display: block; padding: 0.5rem 1rem; text-decoration: none; color: var(--color-text); }}
.zest-dropdown-item:hover {{ background: var(--color-surface); }}

/* Pagination */
.zest-pagination {{ display: flex; gap: 0.25rem; }}
.zest-page-btn {{ padding: 0.4rem 0.7rem; border: 1px solid {border}; background: white; border-radius: var(--radius); cursor: pointer; }}
.zest-page-btn.active {{ background: var(--color-primary); color: white; border-color: var(--color-primary); }}

/* Tooltip */
.zest-tooltip-wrapper {{ position: relative; display: inline-block; }}
.zest-tooltip-content {{ display: none; position: absolute; bottom: calc(100% + 8px); left: 50%; transform: translateX(-50%); background: var(--color-secondary); color: white; padding: 0.4rem 0.8rem; border-radius: var(--radius); font-size: 0.8rem; white-space: nowrap; }}

/* Breadcrumb */
.zest-breadcrumb {{ display: flex; gap: 0.4rem; font-size: 0.85rem; color: var(--color-text-secondary); }}
.zest-breadcrumb a {{ color: var(--color-primary); text-decoration: none; }}

/* Drawer */
.zest-drawer {{ width: 240px; background: var(--color-surface); border-right: 1px solid {border}; min-height: 100vh; }}
.zest-drawer-nav {{ padding: 1rem 0; }}
.zest-drawer-item {{ display: block; padding: 0.6rem 1.25rem; color: var(--color-text); text-decoration: none; }}
.zest-drawer-item.active {{ background: rgba(0,0,0,0.05); font-weight: 600; border-left: 3px solid var(--color-primary); }}

/* Carousel */
.zest-carousel {{ position: relative; overflow: hidden; border-radius: var(--radius); }}
.zest-carousel-track {{ display: flex; }}
.zest-carousel-slide {{ min-width: 100%; padding: 2rem; text-align: center; background: var(--color-surface); }}

/* Menu */
.zest-menu {{ display: flex; flex-direction: column; border: 1px solid {border}; border-radius: var(--radius); overflow: hidden; }}
.zest-menu-item {{ padding: 0.6rem 1rem; border: none; background: none; text-align: left; cursor: pointer; border-bottom: 1px solid {border}; }}
.zest-menu-item:last-child {{ border-bottom: none; }}
.zest-menu-item:hover {{ background: var(--color-surface); }}

/* Popover */
.zest-popover-wrapper {{ position: relative; display: inline-block; }}
.zest-popover {{ display: none; position: absolute; top: calc(100% + 8px); left: 0; background: white; border: 1px solid {border}; border-radius: var(--radius); box-shadow: {shadow}; padding: 1rem; min-width: 200px; z-index: 10; }}

/* Slider */
.zest-slider-group {{ display: flex; flex-direction: column; gap: 0.35rem; }}
.zest-slider {{ width: 100%; accent-color: var(--color-primary); }}

/* Separator */
.shadcn-separator {{ border: none; border-top: 1px solid {border}; margin: 1rem 0; }}

/* Skeleton */
.shadcn-skeleton {{ height: 20px; background: linear-gradient(90deg, var(--color-surface) 25%, {border} 50%, var(--color-surface) 75%); background-size: 200% 100%; animation: zest-shimmer 1.5s infinite; border-radius: var(--radius); }}
@keyframes zest-shimmer {{ 0% {{ background-position: 200% 0; }} 100% {{ background-position: -200% 0; }} }}"""

    def _utilities(self) -> str:
        return """.mb-1 { margin-bottom: 0.5rem; }
.mb-2 { margin-bottom: 1rem; }
.mb-3 { margin-bottom: 1.5rem; }
.mt-2 { margin-top: 1rem; }
.gap-1 { gap: 0.5rem; }
.flex { display: flex; }
.flex-col { flex-direction: column; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.w-full { width: 100%; }
.text-center { text-align: center; }
.text-sm { font-size: 0.875rem; }
.text-muted { color: var(--color-text-secondary); }
.font-bold { font-weight: 700; }"""

    def _responsive(self) -> str:
        return """@media (max-width: 768px) {
  .proto-nav { flex-direction: column; gap: 0.5rem; }
  .proto-grid-2 { grid-template-columns: 1fr; }
  .zest-dialog { min-width: auto; margin: 1rem; }
}"""


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def generate_brand_css(brand: str, output_dir: Optional[str] = None) -> str:
    """
    One-call pipeline: fetch -> resolve -> generate CSS for a brand.

    Args:
        brand: Brand identifier matching the token repo filename.
        output_dir: Where to write the CSS file.
            Defaults to assets/zest/ from config paths.

    Returns:
        The generated CSS string.
    """
    fetcher = ZestTokenFetcher()
    resolver = ZestTokenResolver()
    generator = ZestCssGenerator(brand_name=brand)

    token_sets = fetcher.fetch_brand_tokens(brand)
    if not token_sets:
        logger.warning("No tokens fetched for brand '%s'", brand)
        return ""

    resolved = resolver.resolve(token_sets)

    if output_dir is None:
        assets = _get_assets_dir()
        if assets:
            output_dir = str(Path(assets) / "zest")
        else:
            output_dir = "."

    output_path = str(Path(output_dir) / f"{brand}.css")
    css = generator.generate(resolved, output_path=output_path)

    unresolved = resolver.get_unresolved()
    if unresolved:
        logger.warning(
            "%d tokens could not be fully resolved (sample: %s)",
            len(unresolved),
            unresolved[:5],
        )

    return css
