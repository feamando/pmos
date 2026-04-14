"""
PM-OS CCE PrototypeEngine (v5.0)

Central orchestrator for the PM-OS prototyping pipeline. Coordinates
feature validation, component library selection, context document parsing,
component-to-screen mapping, plan generation, and execution orchestration.

Usage:
    from pm_os_cce.tools.prototype.prototype_engine import PrototypeEngine
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from core.config_loader import get_config

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

try:
    from pm_os_cce.tools.design.brand_theme import (
        BRAND_THEMES, PRODUCT_BRAND_MAP, BrandTheme, BrandThemeResolver,
    )
except ImportError:
    from design.brand_theme import (
        BRAND_THEMES, PRODUCT_BRAND_MAP, BrandTheme, BrandThemeResolver,
    )

try:
    from pm_os_cce.tools.prototype.prototype_context_parser import (
        PrototypeContextParser, PrototypeScreen, PrototypeSpec,
    )
except ImportError:
    from prototype.prototype_context_parser import (
        PrototypeContextParser, PrototypeScreen, PrototypeSpec,
    )

try:
    from pm_os_cce.tools.design.zest_loader import ZestComponent, ZestLoader
except ImportError:
    from design.zest_loader import ZestComponent, ZestLoader

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ComponentMapping:
    """Maps a screen to its resolved UI components."""

    screen_name: str
    components: List[Dict[str, Any]] = field(default_factory=list)
    zest_components: List[str] = field(default_factory=list)
    shadcn_components: List[str] = field(default_factory=list)
    gap_components: List[str] = field(default_factory=list)
    complexity: str = "medium"

    def to_dict(self) -> dict:
        return {
            "screen_name": self.screen_name,
            "components": self.components,
            "zest_components": self.zest_components,
            "shadcn_components": self.shadcn_components,
            "gap_components": self.gap_components,
            "complexity": self.complexity,
        }


@dataclass
class PrototypePlan:
    """Complete prototype build plan ready for execution."""

    feature_slug: str
    title: str
    product_id: str
    brand: str
    platform: str
    use_zest: bool
    theme: Optional[BrandTheme] = None
    spec: Optional[PrototypeSpec] = None
    screen_mappings: List[ComponentMapping] = field(default_factory=list)
    estimated_ralph_loops: int = 0
    deliverables: List[Dict[str, Any]] = field(default_factory=list)
    total_components: int = 0
    total_screens: int = 0
    validation_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "feature_slug": self.feature_slug,
            "title": self.title,
            "product_id": self.product_id,
            "brand": self.brand,
            "platform": self.platform,
            "use_zest": self.use_zest,
            "theme": self.theme.to_dict() if self.theme else None,
            "screen_mappings": [m.to_dict() for m in self.screen_mappings],
            "estimated_ralph_loops": self.estimated_ralph_loops,
            "deliverables": self.deliverables,
            "total_components": self.total_components,
            "total_screens": self.total_screens,
            "validation_notes": self.validation_notes,
        }


@dataclass
class PrototypeResult:
    """Result of a prototype engine run."""

    success: bool
    message: str
    plan: Optional[PrototypePlan] = None
    output_dir: Optional[str] = None
    serve_url: Optional[str] = None
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "plan": self.plan.to_dict() if self.plan else None,
            "output_dir": self.output_dir,
            "serve_url": self.serve_url,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Component hint -> Zest/shadcn mapping tables
# ---------------------------------------------------------------------------

_HINT_TO_ZEST: Dict[str, List[str]] = {
    "button": ["Button"], "form": ["InputField", "Button", "FormField"],
    "input": ["InputField"], "modal": ["Dialog"], "dialog": ["Dialog"],
    "dropdown": ["Select", "Dropdown"], "select": ["Select"],
    "table": ["Table"], "list": ["List", "ListItem"], "card": ["Card"],
    "carousel": ["Carousel"], "slider": ["Slider"], "tabs": ["Tabs"],
    "accordion": ["Accordion"], "navbar": ["NavigationBar"],
    "sidebar": ["NavigationDrawer"], "header": ["Header", "NavigationBar"],
    "banner": ["Banner"], "toast": ["Toast", "Snackbar"],
    "notification": ["Toast", "Snackbar"], "checkbox": ["Checkbox"],
    "radio": ["RadioButton"], "toggle": ["Switch"],
    "search": ["SearchBar", "InputField"], "pagination": ["Pagination"],
    "stepper": ["Stepper"], "progress": ["ProgressBar"],
    "spinner": ["Spinner"], "avatar": ["Avatar"], "badge": ["Badge"],
    "chip": ["Chip"], "tooltip": ["Tooltip"], "menu": ["Menu", "Dropdown"],
    "image": ["Image"], "footer": ["Footer"], "breadcrumb": ["Breadcrumb"],
    "popover": ["Popover"],
}

_HINT_TO_SHADCN: Dict[str, List[str]] = {
    "button": ["Button"], "form": ["Input", "Button", "Form", "Label"],
    "input": ["Input"], "modal": ["Dialog"], "dialog": ["Dialog"],
    "dropdown": ["Select", "DropdownMenu"], "select": ["Select"],
    "table": ["Table"], "list": ["Card"], "card": ["Card"],
    "carousel": ["Carousel"], "slider": ["Slider"], "tabs": ["Tabs"],
    "accordion": ["Accordion"], "navbar": ["NavigationMenu"],
    "sidebar": ["Sheet"], "header": ["NavigationMenu"],
    "banner": ["Alert"], "toast": ["Toast"], "notification": ["Toast"],
    "checkbox": ["Checkbox"], "radio": ["RadioGroup"], "toggle": ["Switch"],
    "search": ["Input"], "pagination": ["Pagination"],
    "stepper": ["Progress"], "progress": ["Progress"],
    "spinner": ["Skeleton"], "avatar": ["Avatar"], "badge": ["Badge"],
    "chip": ["Badge"], "tooltip": ["Tooltip"], "menu": ["DropdownMenu"],
    "image": ["AspectRatio"], "footer": ["Separator"],
    "breadcrumb": ["Breadcrumb"], "popover": ["Popover"],
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class PrototypeEngine:
    """
    Core orchestrator for the PM-OS prototyping pipeline.

    Coordinates feature validation, context parsing, component mapping,
    plan generation, and execution.
    """

    def __init__(
        self,
        brain_path: Optional[str] = None,
        products_root: Optional[str] = None,
    ) -> None:
        """
        Initialize the prototype engine.

        Args:
            brain_path: Path to user/brain directory. Auto-detected if not provided.
            products_root: Path to user/products directory. Auto-detected if not provided.
        """
        if brain_path is None:
            brain_path = self._find_path("user/brain")
        if products_root is None:
            products_root = self._find_path("user/products")

        self.brain_path = brain_path
        self.products_root = products_root

        self._zest_loader = ZestLoader(brain_path) if brain_path else None
        self._theme_resolver = BrandThemeResolver()
        self._context_parser = PrototypeContextParser()

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def run(
        self,
        slug: str,
        use_zest: bool = False,
        context_path: Optional[str] = None,
        brand_id: Optional[str] = None,
        serve: bool = False,
        auto_execute: bool = False,
        figma_file_key: Optional[str] = None,
    ) -> PrototypeResult:
        """Run the full prototype pipeline for a feature."""
        errors: List[str] = []

        logger.info("Starting prototype pipeline for '%s'", slug)
        spec, validation_errors = self._validate_and_parse(slug, context_path)

        if validation_errors:
            errors.extend(validation_errors)

        if spec is None:
            return PrototypeResult(
                success=False,
                message=f"Feature validation failed for '{slug}'",
                errors=errors,
            )

        # Resolve brand/theme (config-driven, no hardcoded defaults)
        if brand_id:
            theme = self._theme_resolver.resolve_by_brand_name(brand_id)
        elif spec.product_id:
            theme = self._theme_resolver.resolve_theme(spec.product_id)
        else:
            theme = self._theme_resolver.resolve_theme("default")

        # Load components
        zest_components = {}
        if use_zest and self._zest_loader:
            zest_components = self._zest_loader.get_components_for_platform(
                "web" if spec.platform != "mobile" else "rn"
            )
            if not zest_components:
                logger.warning("No Zest components found for platform '%s'", spec.platform)
                errors.append(f"No Zest components available for {spec.platform}; falling back to shadcn")
                use_zest = False

        # Enrich from Figma if available
        if figma_file_key:
            spec = self._enrich_spec_from_figma(spec, figma_file_key)

        # Create plan
        plan = self._create_plan(spec, theme, use_zest, zest_components)

        # Validate plan
        validation_notes = self._validate_plan(plan)
        plan.validation_notes = validation_notes

        return PrototypeResult(
            success=True,
            message=f"Prototype plan ready: {plan.total_screens} screens, "
                    f"~{plan.estimated_ralph_loops} Ralph loops",
            plan=plan,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step-by-step API
    # ------------------------------------------------------------------

    def validate_and_parse(
        self, slug: str, context_path: Optional[str] = None,
    ) -> PrototypeSpec:
        """Validate feature and parse its context document."""
        spec, errors = self._validate_and_parse(slug, context_path)
        if spec is None:
            raise FileNotFoundError(
                f"Cannot find feature or context document for '{slug}'. "
                f"Errors: {'; '.join(errors)}"
            )
        return spec

    def create_plan(
        self,
        spec: PrototypeSpec,
        use_zest: bool = False,
        brand_id: Optional[str] = None,
        figma_file_key: Optional[str] = None,
    ) -> PrototypePlan:
        """Create a prototype build plan from a parsed spec."""
        if figma_file_key:
            spec = self._enrich_spec_from_figma(spec, figma_file_key)

        if brand_id:
            theme = self._theme_resolver.resolve_by_brand_name(brand_id)
        elif spec.product_id:
            theme = self._theme_resolver.resolve_theme(spec.product_id)
        else:
            theme = self._theme_resolver.resolve_theme("default")

        zest_components = {}
        if use_zest and self._zest_loader:
            platform = "web" if spec.platform != "mobile" else "rn"
            zest_components = self._zest_loader.get_components_for_platform(platform)

        return self._create_plan(spec, theme, use_zest, zest_components)

    def present_plan(self, plan: PrototypePlan) -> str:
        """Format a plan for user review."""
        lines = [
            f"## Prototype Plan: {plan.title}", "",
            f"**Feature:** `{plan.feature_slug}`",
            f"**Brand:** {plan.brand} | **Platform:** {plan.platform}",
            f"**Library:** {'Zest' if plan.use_zest else 'shadcn/ui'}",
            f"**Screens:** {plan.total_screens} | **Components:** {plan.total_components}",
            f"**Estimated Ralph loops:** {plan.estimated_ralph_loops}", "",
            "### Screen Breakdown", "",
        ]

        for mapping in plan.screen_mappings:
            lines.append(f"#### {mapping.screen_name} ({mapping.complexity})")
            if mapping.zest_components:
                lines.append(f"  Zest: {', '.join(mapping.zest_components)}")
            if mapping.shadcn_components:
                lines.append(f"  shadcn: {', '.join(mapping.shadcn_components)}")
            if mapping.gap_components:
                lines.append(f"  Custom/gaps: {', '.join(mapping.gap_components)}")
            lines.append("")

        if plan.deliverables:
            lines.append("### Deliverables")
            lines.append("")
            for i, d in enumerate(plan.deliverables, 1):
                lines.append(f"{i}. {d['name']} — {d['description']}")
            lines.append("")

        if plan.validation_notes:
            lines.append("### Validation Notes")
            lines.append("")
            for note in plan.validation_notes:
                lines.append(f"- {note}")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal: Validation and parsing
    # ------------------------------------------------------------------

    def _validate_and_parse(
        self, slug: str, context_path: Optional[str],
    ) -> Tuple[Optional[PrototypeSpec], List[str]]:
        """Validate feature exists and parse its context document."""
        errors: List[str] = []

        if context_path:
            doc_path = Path(context_path)
            if not doc_path.exists():
                errors.append(f"Context document not found: {context_path}")
                return None, errors

            feature_state = self._load_feature_state_near(doc_path)
            spec = self._context_parser.parse(
                context_doc_path=str(doc_path),
                feature_state=feature_state,
            )
            if not spec.feature_slug:
                spec.feature_slug = slug
            return spec, errors

        feature_path, state_path, context_doc_path = self._find_feature(slug)

        if feature_path is None:
            errors.append(
                f"Feature '{slug}' not found in PM-OS products. "
                f"Use --context-path to provide an explicit path, "
                f"or run /feature start first."
            )
            return None, errors

        if context_doc_path is None:
            errors.append(
                f"No context document found for feature '{slug}' at {feature_path}. "
                f"Expected a *-context.md file in the feature directory."
            )
            return None, errors

        feature_state = None
        if state_path and state_path.exists():
            try:
                import yaml
                feature_state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Failed to load feature state: %s", exc)

        spec = self._context_parser.parse(
            context_doc_path=str(context_doc_path),
            feature_state=feature_state,
        )
        if not spec.feature_slug:
            spec.feature_slug = slug

        return spec, errors

    def _find_feature(
        self, slug: str,
    ) -> Tuple[Optional[Path], Optional[Path], Optional[Path]]:
        """Find a feature's folder, state file, and context document."""
        if not self.products_root:
            return None, None, None

        products_dir = Path(self.products_root)
        if not products_dir.exists():
            return None, None, None

        for state_file in products_dir.rglob("feature-state.yaml"):
            feature_dir = state_file.parent
            if feature_dir.name == slug:
                context_doc = self._find_context_doc(feature_dir)
                return feature_dir, state_file, context_doc
            try:
                import yaml
                state = yaml.safe_load(state_file.read_text(encoding="utf-8"))
                if isinstance(state, dict) and state.get("slug") == slug:
                    context_doc = self._find_context_doc(feature_dir)
                    return feature_dir, state_file, context_doc
            except Exception:
                continue

        for candidate in products_dir.rglob(slug):
            if candidate.is_dir():
                state_file = candidate / "feature-state.yaml"
                state_path = state_file if state_file.exists() else None
                context_doc = self._find_context_doc(candidate)
                return candidate, state_path, context_doc

        return None, None, None

    @staticmethod
    def _find_context_doc(feature_dir: Path) -> Optional[Path]:
        """Find a context document in a feature directory."""
        context_docs = list(feature_dir.glob("*-context.md"))
        if context_docs:
            return context_docs[0]

        context_docs_dir = feature_dir / "context-docs"
        if context_docs_dir.exists():
            docs = list(context_docs_dir.glob("*-context.md"))
            if docs:
                return docs[0]

        for md in feature_dir.glob("*.md"):
            if "context" in md.name.lower():
                return md

        return None

    @staticmethod
    def _load_feature_state_near(doc_path: Path) -> Optional[dict]:
        """Try to load feature-state.yaml near a context document."""
        candidates = [
            doc_path.parent / "feature-state.yaml",
            doc_path.parent.parent / "feature-state.yaml",
        ]
        for candidate in candidates:
            if candidate.exists():
                try:
                    import yaml
                    return yaml.safe_load(candidate.read_text(encoding="utf-8"))
                except Exception:
                    pass
        return None

    # ------------------------------------------------------------------
    # Internal: Figma enrichment
    # ------------------------------------------------------------------

    def _enrich_spec_from_figma(
        self, spec: PrototypeSpec, figma_file_key: str,
    ) -> PrototypeSpec:
        """Enrich prototype spec with Figma design file data."""
        try:
            try:
                from pm_os_cce.tools.design.figma_client import FigmaClient
            except ImportError:
                from design.figma_client import FigmaClient

            client = FigmaClient()
            if not client.is_authenticated():
                logger.debug("FigmaClient not authenticated — skipping Figma enrichment")
                return spec

            file_key = client.extract_file_key(figma_file_key) or figma_file_key
            figma_screens = client.get_screen_list(file_key)
            instances = client.get_component_instances(
                file_key, zest_loader=self._zest_loader
            )
            figma_hints = set()
            for inst in instances:
                name_lower = (inst.zest_match or inst.name).lower()
                for hint_key in _HINT_TO_ZEST:
                    if hint_key in name_lower:
                        figma_hints.add(hint_key)

            if not spec.screens and figma_screens:
                logger.info(
                    "Populating %d screens from Figma file (context parser found none)",
                    len(figma_screens),
                )
                for i, fs in enumerate(figma_screens):
                    frame_hints = list(figma_hints)
                    screen = PrototypeScreen(
                        name=fs.name,
                        description=f"Screen from Figma ({fs.page})",
                        components_hint=frame_hints[:8],
                        is_entry_point=(i == 0),
                    )
                    spec.screens.append(screen)
            elif spec.screens and figma_hints:
                for screen in spec.screens:
                    existing = set(screen.components_hint)
                    new_hints = figma_hints - existing
                    if new_hints:
                        screen.components_hint.extend(sorted(new_hints)[:5])

            logger.info(
                "Figma enrichment: %d screens, %d component hints from %d instances",
                len(figma_screens), len(figma_hints), len(instances),
            )
        except Exception as exc:
            logger.warning("Figma enrichment failed (falling back): %s", exc)

        return spec

    # ------------------------------------------------------------------
    # Internal: Plan creation
    # ------------------------------------------------------------------

    def _create_plan(
        self, spec: PrototypeSpec, theme: BrandTheme,
        use_zest: bool, zest_components: Dict[str, ZestComponent],
    ) -> PrototypePlan:
        """Create a PrototypePlan from a parsed spec and component inventory."""
        plan = PrototypePlan(
            feature_slug=spec.feature_slug,
            title=spec.title or spec.feature_slug,
            product_id=spec.product_id,
            brand=theme.brand_name,
            platform=spec.platform,
            use_zest=use_zest,
            theme=theme,
            spec=spec,
        )

        for screen in spec.screens:
            mapping = self._map_screen_to_components(
                screen, use_zest, zest_components, theme
            )
            plan.screen_mappings.append(mapping)

        if not plan.screen_mappings:
            default_mapping = ComponentMapping(
                screen_name="Main Screen",
                components=[],
                shadcn_components=["Card", "Button", "Input"],
                complexity="medium",
            )
            plan.screen_mappings.append(default_mapping)

        plan.total_screens = len(plan.screen_mappings)
        plan.total_components = sum(
            len(m.zest_components) + len(m.shadcn_components) + len(m.gap_components)
            for m in plan.screen_mappings
        )
        plan.deliverables = self._generate_deliverables(plan)
        plan.estimated_ralph_loops = self._estimate_ralph_loops(plan)

        return plan

    def _map_screen_to_components(
        self, screen: PrototypeScreen, use_zest: bool,
        zest_components: Dict[str, ZestComponent], theme: BrandTheme,
    ) -> ComponentMapping:
        """Map a single screen to its resolved UI components."""
        mapping = ComponentMapping(screen_name=screen.name)
        zest_used: List[str] = []
        shadcn_used: List[str] = []
        gaps: List[str] = []
        component_details: List[Dict[str, Any]] = []

        hints = screen.components_hint if screen.components_hint else ["button", "card"]

        for hint in hints:
            hint_lower = hint.lower()

            if use_zest:
                zest_names = _HINT_TO_ZEST.get(hint_lower, [])
                matched_zest = [z for z in zest_names if z in zest_components]

                if matched_zest:
                    zest_used.extend(matched_zest)
                    for z in matched_zest:
                        comp = zest_components[z]
                        web_info = comp.platforms.get("web", {})
                        component_details.append({
                            "hint": hint, "library": "zest",
                            "component": z,
                            "package": web_info.get("package", ""),
                            "code_name": web_info.get("code_name", z),
                        })
                else:
                    shadcn_names = _HINT_TO_SHADCN.get(hint_lower, [])
                    if shadcn_names:
                        shadcn_used.extend(shadcn_names)
                        for s in shadcn_names:
                            component_details.append({
                                "hint": hint, "library": "shadcn",
                                "component": s,
                                "note": "Zest gap — using shadcn fallback",
                            })
                    else:
                        gaps.append(hint)
                        component_details.append({
                            "hint": hint, "library": "custom",
                            "note": "No Zest or shadcn match — needs custom HTML",
                        })
            else:
                shadcn_names = _HINT_TO_SHADCN.get(hint_lower, [])
                if shadcn_names:
                    shadcn_used.extend(shadcn_names)
                    for s in shadcn_names:
                        component_details.append({
                            "hint": hint, "library": "shadcn",
                            "component": s,
                        })
                else:
                    gaps.append(hint)
                    component_details.append({
                        "hint": hint, "library": "custom",
                        "note": "No shadcn match — needs custom HTML",
                    })

        mapping.zest_components = sorted(set(zest_used))
        mapping.shadcn_components = sorted(set(shadcn_used))
        mapping.gap_components = sorted(set(gaps))
        mapping.components = component_details

        total = len(mapping.zest_components) + len(mapping.shadcn_components) + len(mapping.gap_components)
        interactions = len(screen.interactions)
        if total > 8 or interactions > 5:
            mapping.complexity = "high"
        elif total > 4 or interactions > 2:
            mapping.complexity = "medium"
        else:
            mapping.complexity = "low"

        return mapping

    def _generate_deliverables(self, plan: PrototypePlan) -> List[Dict[str, Any]]:
        """Generate the deliverable list for a prototype plan."""
        deliverables: List[Dict[str, Any]] = []

        deliverables.append({
            "name": "Project Scaffold",
            "description": f"Create base HTML structure, {plan.brand} theme CSS, and navigation shell",
            "type": "scaffold", "ralph_loops": 1,
        })

        for mapping in plan.screen_mappings:
            loops = 2 if mapping.complexity == "high" else 1
            deliverables.append({
                "name": f"Screen: {mapping.screen_name}",
                "description": (
                    f"Build {mapping.screen_name} with "
                    f"{len(mapping.zest_components)} Zest + "
                    f"{len(mapping.shadcn_components)} shadcn components"
                ),
                "type": "screen", "screen_name": mapping.screen_name,
                "ralph_loops": loops,
            })

        if plan.total_screens > 1:
            deliverables.append({
                "name": "Navigation & Interactivity",
                "description": "Wire screen-to-screen navigation and interactive states",
                "type": "navigation", "ralph_loops": 1,
            })

        if plan.spec and plan.spec.corner_cases:
            deliverables.append({
                "name": "Error States & Corner Cases",
                "description": f"Implement {len(plan.spec.corner_cases)} error/edge case states",
                "type": "corner_cases", "ralph_loops": 1,
            })

        return deliverables

    def _estimate_ralph_loops(self, plan: PrototypePlan) -> int:
        """Estimate total Ralph loops from deliverables."""
        return sum(d.get("ralph_loops", 1) for d in plan.deliverables)

    # ------------------------------------------------------------------
    # Internal: Plan validation
    # ------------------------------------------------------------------

    def _validate_plan(self, plan: PrototypePlan) -> List[str]:
        """Orthogonal validation of a prototype plan."""
        notes: List[str] = []

        if plan.total_screens == 0:
            notes.append("WARNING: No screens in plan — prototype will be empty")
        if plan.total_components == 0:
            notes.append("WARNING: No components mapped — screens will be placeholder-only")

        if plan.use_zest:
            total_zest = sum(len(m.zest_components) for m in plan.screen_mappings)
            total_shadcn = sum(len(m.shadcn_components) for m in plan.screen_mappings)
            if total_zest == 0:
                notes.append(
                    "WARNING: Zest mode enabled but no Zest components resolved — "
                    "all screens use shadcn fallback"
                )
            elif total_shadcn > 0:
                notes.append(f"INFO: {total_shadcn} components falling back to shadcn (Zest gaps)")

        total_gaps = sum(len(m.gap_components) for m in plan.screen_mappings)
        if total_gaps > 0:
            notes.append(f"INFO: {total_gaps} component hints have no library match — will use custom HTML")

        high_screens = [m for m in plan.screen_mappings if m.complexity == "high"]
        if high_screens:
            names = ", ".join(m.screen_name for m in high_screens)
            notes.append(f"INFO: High-complexity screens: {names}")

        if plan.spec and plan.spec.corner_cases:
            notes.append(
                f"INFO: {len(plan.spec.corner_cases)} corner cases will be "
                f"implemented as error states"
            )

        if plan.estimated_ralph_loops > 15:
            notes.append(
                f"WARNING: Estimated {plan.estimated_ralph_loops} Ralph loops — "
                f"consider simplifying scope"
            )

        return notes

    # ------------------------------------------------------------------
    # Internal: Path utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _find_path(relative: str) -> Optional[str]:
        """Auto-detect an absolute path from the cwd or known PM-OS roots."""
        # Try get_paths first
        try:
            paths = get_paths()
            if hasattr(paths, 'user_dir'):
                candidate = Path(paths.user_dir) / relative.replace("user/", "")
                if candidate.exists():
                    return str(candidate)
        except Exception:
            pass

        # Try from cwd upwards
        cwd = Path.cwd()
        for parent in [cwd] + list(cwd.parents):
            candidate = parent / relative
            if candidate.exists():
                return str(candidate)

        # Try common PM-OS install locations
        home = Path.home()
        for root_name in ["pm-os", "pmos"]:
            candidate = home / root_name / relative
            if candidate.exists():
                return str(candidate)

        return None
