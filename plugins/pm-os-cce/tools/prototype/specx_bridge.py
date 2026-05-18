#!/usr/bin/env python3
"""
PM-OS CCE Spec-Machine Bridge (v5.0)

Bridges the CCE feature lifecycle prototype workflow to the specx-ux
(Spec Machine) plugin when available. Provides:
  - Availability detection (filesystem + config)
  - Context translation (CCE PrototypeSpec -> specx-ux subagent parameters)
  - Output adaptation (specx-ux metadata -> CCE PrototypeOutputLinker format)

Usage:
    # From Python
    from pm_os_cce.tools.prototype.specx_bridge import (
        SpecxAvailability, SpecxContextTranslator, SpecxOutputAdapter
    )

    # From CLI (feature.md command)
    python3 specx_bridge.py --check
    python3 specx_bridge.py --translate --feature <slug> [--fidelity medium]
    python3 specx_bridge.py --adapt --feature <slug> --path <prototype_path>
"""

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from core.config_loader import get_config
    except ImportError:
        def get_config():
            return None

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        from core.path_resolver import get_paths
    except ImportError:
        def get_paths():
            return None

# Reuse the preflight check module - resolve path relative to PM_OS_ROOT
import os as _os
_pm_os_root = _os.environ.get(
    "PM_OS_ROOT",
    str(Path(__file__).resolve().parents[5]),  # v5/plugins/pm-os-cce/tools/prototype -> root
)
_plugin_base_core = str(Path(__file__).resolve().parent.parent.parent.parent / "pm-os-base" / "tools" / "core")
if _plugin_base_core not in sys.path:
    sys.path.insert(0, _plugin_base_core)
_common_tools = str(Path(_pm_os_root) / "common" / "tools")
if _common_tools not in sys.path:
    sys.path.insert(0, _common_tools)
try:
    from integrations.spec_machine_check import check_spec_machine_installed
except ImportError:
    def check_spec_machine_installed(config=None):
        return {"installed": False, "message": "spec_machine_check module not found"}


# ---------------------------------------------------------------------------
# Brand mapping: CCE product_id / brand name -> specx-ux brand identifier
# ---------------------------------------------------------------------------

# specx-ux expects these exact identifiers
_CCE_TO_SPECX_BRAND = {
    # product_id mappings
    "good-chop": "goodchop",
    "the-pets-table": "thepetstable",
    "factor-form": "factorform",
    "market-innovation": "default",
    # brand name mappings (from BrandTheme)
    "Good Chop": "goodchop",
    "The Pets Table": "thepetstable",
    "Factor Form": "factorform",
    "HelloFresh": "hellofresh",  # brand identifier for specx-ux, not org reference
    "Factor": "factorUI2",
    "GreenChef": "greenchef",
    "EveryPlate": "everyplate",
    "Chef's Plate": "chefsplate",
    "Youfoodz": "youfoodzUI2",
}

# Fidelity (CCE) -> Threshold (specx-ux)
_FIDELITY_TO_THRESHOLD = {
    "low": "freeform",
    "medium": "balanced",
    "high": "strict",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class AvailabilityResult:
    """Result of specx-ux availability check."""
    available: bool
    mode: str  # "subagent", "filesystem_only", "unavailable"
    plugin_path: str = ""
    version: str = ""
    agents: List[str] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)
    message: str = ""


@dataclass
class SpecxRequest:
    """Translated parameters for the specx-ux prototype-creator subagent."""
    output_path: str
    name: str
    source: str
    source_type: str = "description"
    description: str = ""
    platform: str = "web"
    threshold: str = "balanced"
    brand: str = "default"
    locale: str = "us"
    scope: str = "flow"
    target: str = ""
    reference_screen: str = ""
    reference_screenshot: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_subagent_prompt(self) -> str:
        """Format as the structured prompt expected by the prototype-creator subagent."""
        lines = [
            f"Create a prototype at: {self.output_path}",
            f"Name: {self.name}",
            f"Platform: {self.platform}",
            f"Brand: {self.brand}",
            f"Threshold: {self.threshold}",
            f"Locale: {self.locale}",
            f"Source type: {self.source_type}",
            "",
            "## Source Description",
            "",
            self.source,
        ]
        if self.description:
            lines.extend(["", "## Additional Context", "", self.description])
        if self.target:
            lines.extend(["", f"Primary target screen: {self.target}"])
        if self.reference_screen:
            lines.extend([f"Reference screen: {self.reference_screen}"])
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# SpecxAvailability
# ---------------------------------------------------------------------------

class SpecxAvailability:
    """Detects specx-ux availability via filesystem and config checks.

    Note: Subagent availability is a Claude Code runtime concept and must
    be checked in the command markdown, not here. This class handles the
    filesystem and config-level detection.
    """

    @staticmethod
    def check(config: Any = None) -> AvailabilityResult:
        """Check if specx-ux is available.

        Args:
            config: PM-OS config object (optional, auto-loaded if None)

        Returns:
            AvailabilityResult with availability status and details.
        """
        # Config override: prototype.provider
        provider = "auto"
        if config is None:
            try:
                config = get_config()
            except Exception:
                config = None

        if config is not None:
            try:
                provider = config.get("prototype.provider", "auto")
            except (AttributeError, TypeError):
                pass

        if provider == "internal":
            return AvailabilityResult(
                available=False,
                mode="unavailable",
                message="prototype.provider set to 'internal'; specx-ux delegation disabled",
            )

        # Filesystem check via shared module
        result = check_spec_machine_installed(config)

        if result["installed"]:
            return AvailabilityResult(
                available=True,
                mode="filesystem_only",  # "subagent" mode confirmed by command markdown
                plugin_path=result["path"],
                version=result["version"],
                agents=result.get("agents", []),
                commands=result.get("commands", []),
                message=result["message"],
            )

        if provider == "specx-ux":
            return AvailabilityResult(
                available=False,
                mode="unavailable",
                message=f"prototype.provider set to 'specx-ux' but plugin not found. {result['message']}",
            )

        return AvailabilityResult(
            available=False,
            mode="unavailable",
            message=result["message"],
        )


# ---------------------------------------------------------------------------
# SpecxContextTranslator
# ---------------------------------------------------------------------------

class SpecxContextTranslator:
    """Translates CCE feature context into specx-ux subagent parameters."""

    @staticmethod
    def translate(
        feature_slug: str,
        feature_dir: str,
        product_id: str = "",
        platform: str = "web",
        fidelity: str = "medium",
        locale: str = "us",
        context_content: str = "",
    ) -> SpecxRequest:
        """Translate feature context to specx-ux request.

        Args:
            feature_slug: Feature identifier (kebab-case)
            feature_dir: Path to the feature directory
            product_id: PM-OS product identifier (e.g. "good-chop")
            platform: Target platform (web/mobile)
            fidelity: CCE fidelity level (low/medium/high)
            locale: Market locale (default: us)
            context_content: Raw context document content

        Returns:
            SpecxRequest ready for subagent delegation.
        """
        feature_path = Path(feature_dir)
        output_path = str(feature_path / "prototype")

        # Map brand
        brand = _CCE_TO_SPECX_BRAND.get(product_id, "default")

        # Map threshold
        threshold = _FIDELITY_TO_THRESHOLD.get(fidelity, "balanced")

        # Determine scope from context (single screen vs. flow)
        scope = "flow"
        if context_content:
            screen_count = context_content.lower().count("## screen")
            if screen_count <= 1:
                scope = "screen"

        # Extract primary target screen name from context
        target = ""
        if context_content:
            import re
            screen_match = re.search(
                r"##\s+(?:Screen|View|Page)\s*[:\-]?\s*(.+)",
                context_content,
                re.IGNORECASE,
            )
            if screen_match:
                target = screen_match.group(1).strip()

        # Synthesize source description from context sections
        source = SpecxContextTranslator._synthesize_source(
            feature_slug, context_content
        )

        return SpecxRequest(
            output_path=output_path,
            name=feature_slug,
            source=source,
            source_type="description",
            description=f"Prototype for feature: {feature_slug}",
            platform=platform,
            threshold=threshold,
            brand=brand,
            locale=locale,
            scope=scope,
            target=target,
        )

    @staticmethod
    def _synthesize_source(feature_slug: str, context_content: str) -> str:
        """Synthesize a prototype source description from feature context."""
        if not context_content:
            return f"Create a prototype for the '{feature_slug}' feature."

        # Extract key sections from the context document
        sections = []

        # User flow
        flow_match = _extract_section(context_content, "User Flow")
        if flow_match:
            sections.append(f"## User Flow\n{flow_match}")

        # Screens / UI
        screens_match = _extract_section(context_content, "Screens")
        if not screens_match:
            screens_match = _extract_section(context_content, "UI")
        if screens_match:
            sections.append(f"## Screens\n{screens_match}")

        # Requirements
        req_match = _extract_section(context_content, "Requirements")
        if not req_match:
            req_match = _extract_section(context_content, "Functional Requirements")
        if req_match:
            sections.append(f"## Requirements\n{req_match}")

        # Interactions
        int_match = _extract_section(context_content, "Interactions")
        if int_match:
            sections.append(f"## Interactions\n{int_match}")

        # Corner cases
        cc_match = _extract_section(context_content, "Corner Cases")
        if not cc_match:
            cc_match = _extract_section(context_content, "Edge Cases")
        if cc_match:
            sections.append(f"## Edge Cases\n{cc_match}")

        if sections:
            return "\n\n".join(sections)

        # Fallback: use first 3000 chars of context as-is
        return context_content[:3000]


# ---------------------------------------------------------------------------
# SpecxOutputAdapter
# ---------------------------------------------------------------------------

class SpecxOutputAdapter:
    """Adapts specx-ux prototype output to CCE PrototypeOutputLinker format."""

    @staticmethod
    def adapt(prototype_path: str, feature_path: str) -> Dict[str, Any]:
        """Read specx-ux metadata and translate to CCE manifest format.

        Args:
            prototype_path: Path to the specx-ux prototype output
            feature_path: Path to the feature directory

        Returns:
            Dict compatible with PrototypeOutputLinker.link(manifest=...)
        """
        proto_dir = Path(prototype_path)
        manifest: Dict[str, Any] = {
            "total_screens": 0,
            "total_components": 0,
            "brand": "",
            "library": "zest",
            "platform": "web",
            "provider": "specx-ux",
        }

        # Read specx-ux source metadata
        source_json = proto_dir / "prototype-metadata" / "source.json"
        if source_json.exists():
            try:
                data = json.loads(source_json.read_text(encoding="utf-8"))
                manifest["brand"] = data.get("brand", "")
                manifest["platform"] = data.get("platform", "web")
                manifest["threshold"] = data.get("threshold", "balanced")
                manifest["locale"] = data.get("locale", "us")
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to read specx-ux source.json: %s", exc)

        # Read component manifest if available
        comp_json = proto_dir / "prototype-metadata" / "component-manifest.json"
        if comp_json.exists():
            try:
                comp_data = json.loads(comp_json.read_text(encoding="utf-8"))
                manifest["total_components"] = len(comp_data.get("components", []))
                manifest["components_used"] = comp_data.get("components", [])
            except (json.JSONDecodeError, OSError):
                pass

        # Count screens from HTML (look for data-screen attributes or sections)
        index_html = proto_dir / "index.html"
        if index_html.exists():
            try:
                html = index_html.read_text(encoding="utf-8")
                import re
                screens = re.findall(r'data-screen="([^"]+)"', html)
                if screens:
                    manifest["total_screens"] = len(screens)
                    manifest["screens"] = screens
                elif not manifest["total_screens"]:
                    manifest["total_screens"] = 1
            except OSError:
                pass

        # Read README for description
        readme = proto_dir / "README.md"
        if readme.exists():
            try:
                manifest["readme"] = readme.read_text(encoding="utf-8")[:2000]
            except OSError:
                pass

        return manifest

    @staticmethod
    def link_to_feature(
        feature_path: str,
        prototype_path: str,
        manifest: Optional[Dict[str, Any]] = None,
        serve_url: str = "",
    ) -> Dict[str, Any]:
        """Link specx-ux prototype output into the CCE feature lifecycle.

        Calls PrototypeOutputLinker.link() with the adapted manifest.

        Args:
            feature_path: Path to the feature directory
            prototype_path: Path to the specx-ux prototype output
            manifest: Pre-adapted manifest (calls adapt() if None)
            serve_url: Optional URL where prototype is served

        Returns:
            LinkResult as dict.
        """
        if manifest is None:
            manifest = SpecxOutputAdapter.adapt(prototype_path, feature_path)

        try:
            from pm_os_cce.tools.prototype.prototype_output_linker import (
                PrototypeOutputLinker,
            )
        except ImportError:
            try:
                from prototype_output_linker import PrototypeOutputLinker
            except ImportError:
                return {
                    "success": False,
                    "message": "PrototypeOutputLinker not available",
                    "updated_files": [],
                    "errors": ["Import failed"],
                }

        linker = PrototypeOutputLinker()
        result = linker.link(
            feature_path=feature_path,
            prototype_path=prototype_path,
            serve_url=serve_url,
            manifest=manifest,
        )
        return result.to_dict()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_section(content: str, heading: str) -> Optional[str]:
    """Extract content under a markdown heading."""
    import re
    pattern = rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="PM-OS CCE Spec-Machine Bridge",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Check specx-ux availability",
    )
    parser.add_argument(
        "--translate", action="store_true",
        help="Translate feature context to specx-ux parameters",
    )
    parser.add_argument(
        "--adapt", action="store_true",
        help="Adapt specx-ux output to CCE format",
    )
    parser.add_argument(
        "--link", action="store_true",
        help="Link specx-ux output into feature lifecycle",
    )
    parser.add_argument("--feature", type=str, default="", help="Feature slug")
    parser.add_argument("--path", type=str, default="", help="Prototype path")
    parser.add_argument("--fidelity", type=str, default="medium", help="Fidelity level")
    parser.add_argument("--platform", type=str, default="web", help="Platform")
    parser.add_argument("--product-id", type=str, default="", help="Product ID")
    parser.add_argument("--locale", type=str, default="us", help="Market locale")
    parser.add_argument("--context-file", type=str, default="", help="Context doc path")

    args = parser.parse_args()

    if args.check:
        result = SpecxAvailability.check()
        print(json.dumps(asdict(result), indent=2))
        sys.exit(0 if result.available else 1)

    elif args.translate:
        if not args.feature:
            print("ERROR: --feature required for --translate", file=sys.stderr)
            sys.exit(1)

        # Load context content if file provided
        context_content = ""
        if args.context_file:
            ctx_path = Path(args.context_file)
            if ctx_path.exists():
                context_content = ctx_path.read_text(encoding="utf-8")

        # Resolve feature directory
        try:
            paths = get_paths()
            user_dir = Path(paths.user) if paths else Path.home() / "pm-os" / "user"
        except Exception:
            user_dir = Path.home() / "pm-os" / "user"

        # Search for the feature directory
        feature_dir = ""
        for candidate in user_dir.rglob(f"{args.feature}/feature-state.yaml"):
            feature_dir = str(candidate.parent)
            break

        if not feature_dir:
            feature_dir = str(user_dir / "features" / args.feature)

        request = SpecxContextTranslator.translate(
            feature_slug=args.feature,
            feature_dir=feature_dir,
            product_id=args.product_id,
            platform=args.platform,
            fidelity=args.fidelity,
            locale=args.locale,
            context_content=context_content,
        )
        print(json.dumps(request.to_dict(), indent=2))

    elif args.adapt:
        if not args.path:
            print("ERROR: --path required for --adapt", file=sys.stderr)
            sys.exit(1)
        manifest = SpecxOutputAdapter.adapt(args.path, args.feature or "")
        print(json.dumps(manifest, indent=2))

    elif args.link:
        if not args.path or not args.feature:
            print("ERROR: --path and --feature required for --link", file=sys.stderr)
            sys.exit(1)

        # Resolve feature directory
        try:
            paths = get_paths()
            user_dir = Path(paths.user) if paths else Path.home() / "pm-os" / "user"
        except Exception:
            user_dir = Path.home() / "pm-os" / "user"

        feature_dir = ""
        for candidate in user_dir.rglob(f"{args.feature}/feature-state.yaml"):
            feature_dir = str(candidate.parent)
            break

        if not feature_dir:
            feature_dir = str(user_dir / "features" / args.feature)

        result = SpecxOutputAdapter.link_to_feature(
            feature_path=feature_dir,
            prototype_path=args.path,
        )
        print(json.dumps(result, indent=2))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
