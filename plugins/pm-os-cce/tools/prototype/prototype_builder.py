"""
PM-OS CCE PrototypeBuilder (v5.0)

Generates browser-viewable HTML/CSS/JS files from a PrototypePlan.
Supports both Zest and shadcn component rendering with brand theming.
Output is pure HTML that opens directly in a browser (no build step).

Usage:
    from pm_os_cce.tools.prototype.prototype_builder import PrototypeBuilder
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from core.config_loader import get_config

logger = logging.getLogger(__name__)


@dataclass
class BuildResult:
    """Result of a prototype build."""
    success: bool
    output_dir: str
    index_path: str = ""
    screen_files: List[str] = field(default_factory=list)
    manifest_path: str = ""
    total_files: int = 0
    errors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Component HTML templates
# ---------------------------------------------------------------------------

_ZEST_TEMPLATES: Dict[str, str] = {
    "Button": '<button class="zest-btn zest-btn-primary">{label}</button>',
    "Card": '<div class="zest-card"><div class="zest-card-body">{content}</div></div>',
    "InputField": '<div class="zest-input-group"><label class="zest-label">{label}</label><input type="text" class="zest-input" placeholder="{placeholder}"></div>',
    "Dialog": '<div class="zest-dialog-backdrop" style="display:none"><div class="zest-dialog"><div class="zest-dialog-header"><h3>{title}</h3><button class="zest-btn-icon" onclick="this.closest(\'.zest-dialog-backdrop\').style.display=\'none\'">&times;</button></div><div class="zest-dialog-body">{content}</div></div></div>',
    "Select": '<div class="zest-input-group"><label class="zest-label">{label}</label><select class="zest-select"><option>Select...</option><option>Option 1</option><option>Option 2</option></select></div>',
    "Checkbox": '<label class="zest-checkbox"><input type="checkbox"><span class="zest-checkbox-mark"></span><span>{label}</span></label>',
    "RadioButton": '<label class="zest-radio"><input type="radio" name="{group}"><span class="zest-radio-mark"></span><span>{label}</span></label>',
    "Switch": '<label class="zest-switch"><input type="checkbox"><span class="zest-switch-slider"></span><span>{label}</span></label>',
    "Tabs": '<div class="zest-tabs"><div class="zest-tab-list"><button class="zest-tab active">Tab 1</button><button class="zest-tab">Tab 2</button></div><div class="zest-tab-panel">Tab content</div></div>',
    "Accordion": '<div class="zest-accordion"><div class="zest-accordion-item"><button class="zest-accordion-trigger" onclick="this.parentElement.classList.toggle(\'open\')">{title} <span class="zest-chevron">&#9660;</span></button><div class="zest-accordion-content">{content}</div></div></div>',
    "Toast": '<div class="zest-toast zest-toast-info"><span>{message}</span><button class="zest-btn-icon">&times;</button></div>',
    "Banner": '<div class="zest-banner"><span>{message}</span></div>',
    "Avatar": '<div class="zest-avatar">{initials}</div>',
    "Badge": '<span class="zest-badge">{text}</span>',
    "Chip": '<span class="zest-chip">{text}<button class="zest-chip-remove">&times;</button></span>',
    "Tooltip": '<span class="zest-tooltip-wrapper"><span>{text}</span><span class="zest-tooltip-content">{tooltip}</span></span>',
    "ProgressBar": '<div class="zest-progress"><div class="zest-progress-bar" style="width:{percent}%"></div></div>',
    "Spinner": '<div class="zest-spinner"></div>',
    "List": '<ul class="zest-list"><li class="zest-list-item">Item 1</li><li class="zest-list-item">Item 2</li><li class="zest-list-item">Item 3</li></ul>',
    "ListItem": '<li class="zest-list-item">{content}</li>',
    "Table": '<table class="zest-table"><thead><tr><th>Column 1</th><th>Column 2</th><th>Column 3</th></tr></thead><tbody><tr><td>Data 1</td><td>Data 2</td><td>Data 3</td></tr></tbody></table>',
    "NavigationBar": '<nav class="zest-navbar"><div class="zest-navbar-brand">{brand}</div><div class="zest-navbar-links">{links}</div></nav>',
    "Header": '<header class="zest-header"><h1>{title}</h1></header>',
    "Footer": '<footer class="zest-footer"><p>{content}</p></footer>',
    "SearchBar": '<div class="zest-searchbar"><input type="search" class="zest-input" placeholder="Search..."><button class="zest-btn zest-btn-icon">&#128269;</button></div>',
    "Stepper": '<div class="zest-stepper"><div class="zest-step active"><span class="zest-step-num">1</span><span>Step 1</span></div><div class="zest-step"><span class="zest-step-num">2</span><span>Step 2</span></div><div class="zest-step"><span class="zest-step-num">3</span><span>Step 3</span></div></div>',
    "Image": '<div class="zest-image"><div class="zest-image-placeholder">Image</div></div>',
    "Carousel": '<div class="zest-carousel"><button class="zest-carousel-prev">&#8249;</button><div class="zest-carousel-track"><div class="zest-carousel-slide active">Slide 1</div></div><button class="zest-carousel-next">&#8250;</button></div>',
    "Menu": '<div class="zest-menu"><button class="zest-menu-item">Item 1</button><button class="zest-menu-item">Item 2</button></div>',
    "Dropdown": '<div class="zest-dropdown"><button class="zest-btn" onclick="this.nextElementSibling.classList.toggle(\'open\')">Dropdown &#9660;</button><div class="zest-dropdown-menu"><a class="zest-dropdown-item">Option 1</a><a class="zest-dropdown-item">Option 2</a></div></div>',
    "Popover": '<div class="zest-popover-wrapper"><button class="zest-btn">{trigger}</button><div class="zest-popover">{content}</div></div>',
    "Pagination": '<nav class="zest-pagination"><button class="zest-page-btn">&laquo;</button><button class="zest-page-btn active">1</button><button class="zest-page-btn">2</button><button class="zest-page-btn">3</button><button class="zest-page-btn">&raquo;</button></nav>',
    "FormField": '<div class="zest-input-group"><label class="zest-label">{label}</label><input type="text" class="zest-input" placeholder="{placeholder}"><span class="zest-helper-text">{helper}</span></div>',
    "Snackbar": '<div class="zest-snackbar"><span>{message}</span><button class="zest-btn-text">DISMISS</button></div>',
    "NavigationDrawer": '<aside class="zest-drawer"><nav class="zest-drawer-nav"><a class="zest-drawer-item active">Home</a><a class="zest-drawer-item">Settings</a></nav></aside>',
    "Breadcrumb": '<nav class="zest-breadcrumb"><a>Home</a><span>/</span><a>Section</a><span>/</span><span>Current</span></nav>',
    "Slider": '<div class="zest-slider-group"><label class="zest-label">{label}</label><input type="range" class="zest-slider" min="0" max="100"></div>',
}

_SHADCN_TEMPLATES: Dict[str, str] = {
    "Button": '<button class="shadcn-btn shadcn-btn-primary">{label}</button>',
    "Card": '<div class="shadcn-card"><div class="shadcn-card-header"><h3 class="shadcn-card-title">{title}</h3></div><div class="shadcn-card-content">{content}</div></div>',
    "Input": '<div class="shadcn-field"><label class="shadcn-label">{label}</label><input type="text" class="shadcn-input" placeholder="{placeholder}"></div>',
    "Dialog": '<div class="shadcn-dialog-overlay" style="display:none"><div class="shadcn-dialog"><div class="shadcn-dialog-header"><h2>{title}</h2></div><div class="shadcn-dialog-body">{content}</div><div class="shadcn-dialog-footer"><button class="shadcn-btn">Close</button></div></div></div>',
    "Select": '<div class="shadcn-field"><label class="shadcn-label">{label}</label><select class="shadcn-select"><option>Select...</option><option>Option 1</option></select></div>',
    "Checkbox": '<label class="shadcn-checkbox"><input type="checkbox"><span>{label}</span></label>',
    "RadioGroup": '<div class="shadcn-radio-group"><label class="shadcn-radio"><input type="radio" name="{group}"><span>{label}</span></label></div>',
    "Switch": '<label class="shadcn-switch"><input type="checkbox"><span class="shadcn-switch-thumb"></span>{label}</label>',
    "Tabs": '<div class="shadcn-tabs"><div class="shadcn-tabs-list"><button class="shadcn-tab active">Tab 1</button><button class="shadcn-tab">Tab 2</button></div><div class="shadcn-tabs-content">Content</div></div>',
    "Accordion": '<div class="shadcn-accordion"><div class="shadcn-accordion-item"><button class="shadcn-accordion-trigger" onclick="this.parentElement.classList.toggle(\'open\')">{title}</button><div class="shadcn-accordion-content">{content}</div></div></div>',
    "Toast": '<div class="shadcn-toast"><p>{message}</p></div>',
    "Alert": '<div class="shadcn-alert"><p>{message}</p></div>',
    "Avatar": '<div class="shadcn-avatar">{initials}</div>',
    "Badge": '<span class="shadcn-badge">{text}</span>',
    "Tooltip": '<span class="shadcn-tooltip-trigger" title="{tooltip}">{text}</span>',
    "Progress": '<div class="shadcn-progress"><div class="shadcn-progress-bar" style="width:{percent}%"></div></div>',
    "Skeleton": '<div class="shadcn-skeleton"></div>',
    "Table": '<table class="shadcn-table"><thead><tr><th>Column 1</th><th>Column 2</th></tr></thead><tbody><tr><td>Data</td><td>Data</td></tr></tbody></table>',
    "NavigationMenu": '<nav class="shadcn-nav"><a class="shadcn-nav-link active">Home</a><a class="shadcn-nav-link">About</a></nav>',
    "Sheet": '<div class="shadcn-sheet"><div class="shadcn-sheet-content"><h3>Sheet</h3><p>Content</p></div></div>',
    "DropdownMenu": '<div class="shadcn-dropdown"><button class="shadcn-btn" onclick="this.nextElementSibling.classList.toggle(\'open\')">Menu &#9660;</button><div class="shadcn-dropdown-content"><a>Item 1</a><a>Item 2</a></div></div>',
    "Form": '<form class="shadcn-form" onsubmit="return false">{content}</form>',
    "Label": '<label class="shadcn-label">{text}</label>',
    "Separator": '<hr class="shadcn-separator">',
    "AspectRatio": '<div class="shadcn-aspect-ratio"><div class="shadcn-image-placeholder">Image</div></div>',
    "Popover": '<div class="shadcn-popover-trigger"><button class="shadcn-btn">{trigger}</button><div class="shadcn-popover">{content}</div></div>',
    "Breadcrumb": '<nav class="shadcn-breadcrumb"><a>Home</a><span>/</span><span>Current</span></nav>',
    "Pagination": '<nav class="shadcn-pagination"><button>&laquo;</button><button class="active">1</button><button>2</button><button>&raquo;</button></nav>',
    "Carousel": '<div class="shadcn-carousel"><div class="shadcn-carousel-content">Slide 1</div></div>',
    "Slider": '<input type="range" class="shadcn-slider" min="0" max="100">',
}


class PrototypeBuilder:
    """
    Generates browser-viewable HTML/CSS/JS from a PrototypePlan.

    Output structure:
        output_dir/
            index.html
            styles.css
            navigation.js
            manifest.json
    """

    def build(self, plan, output_dir: str) -> BuildResult:
        """
        Build a complete prototype from a PrototypePlan.

        Args:
            plan: PrototypePlan with screen mappings, theme, and spec.
            output_dir: Target directory for output files.

        Returns:
            BuildResult with file paths and status.
        """
        out = Path(output_dir)
        errors: List[str] = []
        screen_files: List[str] = []

        try:
            out.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return BuildResult(success=False, output_dir=output_dir, errors=[str(exc)])

        # 1. Generate CSS
        css = self._get_zest_token_css(plan.theme) or self._generate_css(plan.theme)
        css_path = out / "styles.css"
        css_path.write_text(css, encoding="utf-8")

        # 2. Generate navigation JS
        nav_js = self._generate_navigation_js(plan)
        js_path = out / "navigation.js"
        js_path.write_text(nav_js, encoding="utf-8")

        # 3. Generate index.html
        index_html = self._generate_index_html(plan)
        index_path = out / "index.html"
        index_path.write_text(index_html, encoding="utf-8")

        # 4. Generate manifest
        manifest = self._generate_manifest(plan)
        manifest_path = out / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        total_files = 4
        logger.info("Built prototype: %d files in %s", total_files, out)

        return BuildResult(
            success=True,
            output_dir=str(out),
            index_path=str(index_path),
            screen_files=screen_files,
            manifest_path=str(manifest_path),
            total_files=total_files,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # CSS generation
    # ------------------------------------------------------------------

    @staticmethod
    def _get_zest_token_css(theme) -> Optional[str]:
        """Look for pre-generated real Zest token CSS for this brand."""
        if theme is None:
            return None
        brand_id = getattr(theme, "brand_id", "")
        if not brand_id:
            return None
        normalised = brand_id.lower().replace("-", "").replace(" ", "")

        # Try config-driven assets path, then fallback to relative
        try:
            config = get_config()
            assets_base = config.get("paths.assets_dir", "")
            if assets_base:
                css_file = Path(assets_base) / "zest" / f"{normalised}.css"
                if css_file.exists():
                    logger.info("Using real Zest token CSS: %s", css_file)
                    return css_file.read_text(encoding="utf-8")
        except Exception:
            pass

        # Fallback to relative path
        assets_dir = Path(__file__).resolve().parent.parent.parent / "assets" / "zest"
        css_file = assets_dir / f"{normalised}.css"
        if css_file.exists():
            logger.info("Using real Zest token CSS: %s", css_file)
            return css_file.read_text(encoding="utf-8")
        logger.debug("No Zest token CSS for brand '%s' at %s", brand_id, css_file)
        return None

    def _generate_css(self, theme) -> str:
        """Generate brand-themed CSS with custom properties."""
        if theme is None:
            primary = "#3B82F6"
            secondary = "#1E293B"
            accent = "#F59E0B"
            bg = "#FFFFFF"
            surface = "#F9FAFB"
            text = "#1F2937"
            text_sec = "#6B7280"
            error = "#EF4444"
            success = "#10B981"
            warning = "#F59E0B"
            border = "#E5E7EB"
            font = "'Inter', sans-serif"
            font_heading = "'Inter', sans-serif"
            radius = "8px"
            shadow_sm = "0 1px 2px 0 rgba(0,0,0,0.05)"
            shadow_md = "0 4px 6px -1px rgba(0,0,0,0.1)"
        else:
            primary = theme.primary_color
            secondary = theme.secondary_color
            accent = theme.accent_color
            bg = theme.background_color
            surface = theme.surface_color
            text = theme.text_color
            text_sec = theme.text_secondary_color
            error = theme.error_color
            success = theme.success_color
            warning = theme.warning_color
            border = theme.border_color
            font = theme.font_family
            font_heading = theme.font_family_heading
            radius = theme.border_radius
            shadow_sm = theme.shadow_sm
            shadow_md = theme.shadow_md

        return f"""/* PM-OS Prototype Theme — Auto-generated */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=DM+Sans:wght@400;500;700&family=Nunito:wght@400;600;700&family=Playfair+Display:wght@400;700&display=swap');

:root {{
  --color-primary: {primary};
  --color-secondary: {secondary};
  --color-accent: {accent};
  --color-bg: {bg};
  --color-surface: {surface};
  --color-text: {text};
  --color-text-secondary: {text_sec};
  --color-error: {error};
  --color-success: {success};
  --color-warning: {warning};
  --color-border: {border};
  --font-family: {font};
  --font-heading: {font_heading};
  --radius: {radius};
  --shadow-sm: {shadow_sm};
  --shadow-md: {shadow_md};
}}

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: var(--font-family); color: var(--color-text); background: var(--color-bg); line-height: 1.6; }}
h1,h2,h3,h4 {{ font-family: var(--font-heading); font-weight: 700; }}

/* Layout */
.proto-container {{ max-width: 1200px; margin: 0 auto; padding: 1rem; }}
.proto-screen {{ display: none; padding: 2rem 0; }}
.proto-screen.active {{ display: block; }}
.proto-grid {{ display: grid; gap: 1.5rem; }}
.proto-grid-2 {{ grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }}
.proto-section {{ margin-bottom: 2rem; }}

/* Navigation */
.proto-nav {{ background: var(--color-secondary); padding: 0.75rem 1.5rem; display: flex; align-items: center; gap: 1.5rem; position: sticky; top: 0; z-index: 100; }}
.proto-nav-brand {{ color: white; font-weight: 700; font-size: 1.1rem; font-family: var(--font-heading); }}
.proto-nav-links {{ display: flex; gap: 0.5rem; }}
.proto-nav-link {{ color: rgba(255,255,255,0.7); text-decoration: none; padding: 0.4rem 0.8rem; border-radius: var(--radius); cursor: pointer; font-size: 0.9rem; border: none; background: none; }}
.proto-nav-link:hover,.proto-nav-link.active {{ color: white; background: rgba(255,255,255,0.15); }}

/* Responsive */
@media (max-width: 768px) {{
  .proto-nav {{ flex-direction: column; gap: 0.5rem; }}
  .proto-grid-2 {{ grid-template-columns: 1fr; }}
}}

/* Utility */
.mb-1 {{ margin-bottom: 0.5rem; }}
.mb-2 {{ margin-bottom: 1rem; }}
.mb-3 {{ margin-bottom: 1.5rem; }}
.mt-2 {{ margin-top: 1rem; }}
.gap-1 {{ gap: 0.5rem; }}
.flex {{ display: flex; }}
.flex-col {{ flex-direction: column; }}
.items-center {{ align-items: center; }}
.justify-between {{ justify-content: space-between; }}
.w-full {{ width: 100%; }}
.text-center {{ text-align: center; }}
.text-sm {{ font-size: 0.875rem; }}
.text-muted {{ color: var(--color-text-secondary); }}
.font-bold {{ font-weight: 700; }}
"""

    # ------------------------------------------------------------------
    # HTML generation
    # ------------------------------------------------------------------

    def _generate_index_html(self, plan) -> str:
        """Generate single-page index.html with all screens."""
        brand = plan.brand if plan.brand else "Prototype"
        title = plan.title if plan.title else plan.feature_slug

        nav_links = []
        for i, mapping in enumerate(plan.screen_mappings):
            slug = self._slugify(mapping.screen_name)
            active = " active" if i == 0 else ""
            nav_links.append(
                f'<button class="proto-nav-link{active}" '
                f'onclick="showScreen(\'{slug}\')">{mapping.screen_name}</button>'
            )

        screens_html = []
        for i, mapping in enumerate(plan.screen_mappings):
            slug = self._slugify(mapping.screen_name)
            active = " active" if i == 0 else ""
            screen_content = self._generate_screen_content(mapping, plan)
            screens_html.append(
                f'<div id="screen-{slug}" class="proto-screen{active}">\n'
                f'  <div class="proto-container">\n'
                f'    <h2 class="mb-2">{mapping.screen_name}</h2>\n'
                f'    {screen_content}\n'
                f'  </div>\n'
                f'</div>'
            )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — {brand} Prototype</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <nav class="proto-nav">
    <span class="proto-nav-brand">{brand}</span>
    <div class="proto-nav-links">
      {''.join(nav_links)}
    </div>
  </nav>

  {''.join(screens_html)}

  <script src="navigation.js"></script>
</body>
</html>
"""

    def _generate_screen_content(self, mapping, plan) -> str:
        """Generate HTML content for a single screen."""
        parts: List[str] = []
        rendered: set = set()
        for detail in mapping.components:
            lib = detail.get("library", "")
            comp_name = detail.get("component", "")
            if not comp_name or comp_name in rendered:
                continue
            rendered.add(comp_name)
            html = self._render_component(comp_name, lib, mapping.screen_name)
            if html:
                parts.append(f'<div class="proto-section">{html}</div>')

        if not parts:
            if mapping.zest_components:
                for comp in mapping.zest_components:
                    html = self._render_component(comp, "zest", mapping.screen_name)
                    if html:
                        parts.append(f'<div class="proto-section">{html}</div>')
            elif mapping.shadcn_components:
                for comp in mapping.shadcn_components:
                    html = self._render_component(comp, "shadcn", mapping.screen_name)
                    if html:
                        parts.append(f'<div class="proto-section">{html}</div>')

        if not parts:
            parts.append(
                '<div class="proto-section">'
                '<div class="zest-card"><div class="zest-card-body">'
                f'<p class="text-muted">Screen: {mapping.screen_name}</p>'
                '</div></div></div>'
            )

        return "\n    ".join(parts)

    def _render_component(self, name: str, library: str, screen: str) -> str:
        """Render a single component to HTML."""
        defaults = {
            "label": name, "content": f"Content for {screen}",
            "title": screen, "placeholder": f"Enter {name.lower()}...",
            "text": name, "message": f"Sample {name.lower()} message",
            "tooltip": f"{name} tooltip", "trigger": name,
            "helper": "", "brand": "Brand",
            "links": '<a>Home</a><a>About</a>', "initials": "AB",
            "percent": "65", "group": f"group-{screen}",
        }

        if library == "zest":
            template = _ZEST_TEMPLATES.get(name, "")
        elif library == "shadcn":
            template = _SHADCN_TEMPLATES.get(name, "")
        else:
            return f'<div class="proto-section"><p class="text-muted">[{name}]</p></div>'

        if not template:
            return ""

        try:
            return template.format(**defaults)
        except (KeyError, IndexError):
            return template

    # ------------------------------------------------------------------
    # Navigation JS
    # ------------------------------------------------------------------

    def _generate_navigation_js(self, plan) -> str:
        """Generate screen switching JavaScript."""
        return """// PM-OS Prototype Navigation
function showScreen(slug) {
  document.querySelectorAll('.proto-screen').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.proto-nav-link').forEach(l => l.classList.remove('active'));
  const target = document.getElementById('screen-' + slug);
  if (target) target.classList.add('active');
  event.target.classList.add('active');
  window.scrollTo(0, 0);
}

// Close dropdowns on outside click
document.addEventListener('click', function(e) {
  if (!e.target.closest('.zest-dropdown, .shadcn-dropdown')) {
    document.querySelectorAll('.zest-dropdown-menu, .shadcn-dropdown-content').forEach(m => m.classList.remove('open'));
  }
});
"""

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------

    def _generate_manifest(self, plan) -> dict:
        """Generate build manifest JSON."""
        screens = []
        components_used = set()

        for mapping in plan.screen_mappings:
            components = len(mapping.zest_components) + len(mapping.shadcn_components)
            screens.append({
                "name": mapping.screen_name,
                "components": components,
                "complexity": mapping.complexity,
            })
            for c in mapping.zest_components:
                components_used.add(f"zest:{c}")
            for c in mapping.shadcn_components:
                components_used.add(f"shadcn:{c}")

        return {
            "feature_slug": plan.feature_slug,
            "title": plan.title,
            "brand": plan.brand,
            "platform": plan.platform,
            "library": "zest" if plan.use_zest else "shadcn",
            "total_screens": plan.total_screens,
            "total_components": plan.total_components,
            "screens": screens,
            "components_used": sorted(components_used),
            "generated_by": "PM-OS Prototype Builder v5.0",
        }

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to URL-safe slug."""
        slug = text.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        return slug.strip("-")
