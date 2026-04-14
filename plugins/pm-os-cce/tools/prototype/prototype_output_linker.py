"""
PM-OS CCE PrototypeOutputLinker (v5.0)

Updates PM-OS artifacts with prototype build references after a prototype
is built. Links to feature-state.yaml, context document, brain entity,
and generates a summary report.

Usage:
    from pm_os_cce.tools.prototype.prototype_output_linker import PrototypeOutputLinker
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class LinkResult:
    """Result of the output linking operation."""

    success: bool
    message: str
    updated_files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    summary_path: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "updated_files": self.updated_files,
            "errors": self.errors,
            "summary_path": self.summary_path,
        }


class PrototypeOutputLinker:
    """
    Updates PM-OS artifacts with prototype build references.

    Links the prototype output to:
    1. feature-state.yaml (artifacts.prototype)
    2. Context document (References section)
    3. Brain entity (prototype relationship) — optional, guarded
    4. Feature reports/ directory (summary report)
    """

    def link(
        self,
        feature_path: str,
        prototype_path: str,
        serve_url: Optional[str] = None,
        manifest: Optional[dict] = None,
    ) -> LinkResult:
        """
        Link prototype output to all PM-OS artifacts.

        Args:
            feature_path: Path to the feature directory.
            prototype_path: Path to the prototype output directory.
            serve_url: Optional URL where the prototype is served.
            manifest: Optional pre-loaded manifest dict.

        Returns:
            LinkResult with updated file list and any errors.
        """
        feature_dir = Path(feature_path)
        proto_dir = Path(prototype_path)
        updated: List[str] = []
        errors: List[str] = []

        if manifest is None:
            manifest_file = proto_dir / "manifest.json"
            if manifest_file.exists():
                try:
                    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                except Exception as exc:
                    logger.warning("Failed to read manifest: %s", exc)
                    manifest = {}
            else:
                manifest = {}

        # 1. Update feature-state.yaml
        state_result = self._update_feature_state(
            feature_dir, proto_dir, serve_url, manifest
        )
        if state_result:
            updated.append(state_result)
        else:
            errors.append("Failed to update feature-state.yaml")

        # 2. Update context document
        context_result = self._update_context_doc(feature_dir, proto_dir, serve_url)
        if context_result:
            updated.append(context_result)

        # 3. Update brain entity (optional — Brain plugin may not be present)
        brain_result = self._update_brain_entity(feature_dir, proto_dir, serve_url)
        if brain_result:
            updated.append(brain_result)

        # 4. Generate summary report
        summary_path = self._generate_summary(
            feature_dir, proto_dir, serve_url, manifest
        )
        if summary_path:
            updated.append(summary_path)

        success = len(errors) == 0
        return LinkResult(
            success=success,
            message=f"Linked prototype to {len(updated)} artifacts"
                    if success
                    else f"Partial linking: {len(errors)} errors",
            updated_files=updated,
            errors=errors,
            summary_path=summary_path,
        )

    # ------------------------------------------------------------------
    # Feature state update
    # ------------------------------------------------------------------

    def _update_feature_state(
        self, feature_dir: Path, proto_dir: Path,
        serve_url: Optional[str], manifest: dict,
    ) -> Optional[str]:
        """Add prototype artifact to feature-state.yaml."""
        state_file = feature_dir / "feature-state.yaml"
        if not state_file.exists():
            logger.warning("feature-state.yaml not found in %s", feature_dir)
            return None

        try:
            state = yaml.safe_load(state_file.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                logger.warning("feature-state.yaml is not a dict")
                return None

            if "artifacts" not in state:
                state["artifacts"] = {}

            state["artifacts"]["prototype"] = {
                "path": str(proto_dir),
                "url": serve_url or "",
                "built_at": datetime.now().isoformat(),
                "screens": manifest.get("total_screens", 0),
                "components": manifest.get("total_components", 0),
                "brand": manifest.get("brand", ""),
                "library": manifest.get("library", ""),
            }

            state_file.write_text(
                yaml.dump(state, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
            logger.info("Updated feature-state.yaml with prototype artifact")
            return str(state_file)

        except Exception as exc:
            logger.error("Failed to update feature-state.yaml: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Context document update
    # ------------------------------------------------------------------

    def _update_context_doc(
        self, feature_dir: Path, proto_dir: Path, serve_url: Optional[str],
    ) -> Optional[str]:
        """Append a prototype reference to the context document."""
        context_docs = list(feature_dir.glob("*-context.md"))
        if not context_docs:
            context_docs_dir = feature_dir / "context-docs"
            if context_docs_dir.exists():
                context_docs = list(context_docs_dir.glob("*-context.md"))
        if not context_docs:
            logger.info("No context document found in %s", feature_dir)
            return None

        context_file = context_docs[0]
        try:
            content = context_file.read_text(encoding="utf-8")

            if "## Prototype" in content or "### Prototype" in content:
                logger.info("Prototype reference already exists in %s", context_file.name)
                return str(context_file)

            proto_block = self._build_prototype_reference(proto_dir, serve_url)

            if "## References" in content:
                content = content.replace(
                    "## References",
                    f"## References\n\n{proto_block}",
                )
            else:
                content = content.rstrip() + f"\n\n## Prototype\n\n{proto_block}\n"

            context_file.write_text(content, encoding="utf-8")
            logger.info("Updated context document with prototype reference")
            return str(context_file)

        except Exception as exc:
            logger.error("Failed to update context document: %s", exc)
            return None

    @staticmethod
    def _build_prototype_reference(
        proto_dir: Path, serve_url: Optional[str],
    ) -> str:
        """Build the markdown block for the prototype reference."""
        lines = [
            "### Prototype", "",
            f"- **Output directory:** `{proto_dir}`",
        ]
        if serve_url:
            lines.append(f"- **Local URL:** [{serve_url}]({serve_url})")
        lines.append(f"- **Built:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Brain entity update (optional — Brain plugin guarded)
    # ------------------------------------------------------------------

    def _update_brain_entity(
        self, feature_dir: Path, proto_dir: Path, serve_url: Optional[str],
    ) -> Optional[str]:
        """Add prototype relationship to the brain entity."""
        state_file = feature_dir / "feature-state.yaml"
        if not state_file.exists():
            return None

        try:
            state = yaml.safe_load(state_file.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                return None

            brain_ref = state.get("brain_entity", "")
            if not brain_ref:
                logger.info("No brain_entity in feature-state.yaml")
                return None

            entity_rel = brain_ref.strip("[]' ")
            if not entity_rel:
                return None

            brain_path = self._find_brain_entity(feature_dir, entity_rel)
            if brain_path is None or not brain_path.exists():
                logger.info("Brain entity not found: %s", entity_rel)
                return None

            content = brain_path.read_text(encoding="utf-8")

            if "prototype" in content.lower() and str(proto_dir) in content:
                logger.info("Prototype already referenced in brain entity")
                return str(brain_path)

            proto_line = (
                f"\n## Prototype\n\n"
                f"- Output: `{proto_dir}`\n"
            )
            if serve_url:
                proto_line += f"- URL: {serve_url}\n"
            proto_line += f"- Built: {datetime.now().strftime('%Y-%m-%d')}\n"

            content = content.rstrip() + "\n" + proto_line
            brain_path.write_text(content, encoding="utf-8")
            logger.info("Updated brain entity with prototype reference")
            return str(brain_path)

        except Exception as exc:
            logger.error("Failed to update brain entity: %s", exc)
            return None

    @staticmethod
    def _find_brain_entity(feature_dir: Path, entity_rel: str) -> Optional[Path]:
        """Resolve a brain entity relative path to an absolute path."""
        current = feature_dir
        for _ in range(10):
            candidate = current / "user" / "brain" / (entity_rel + ".md")
            if candidate.exists():
                return candidate
            candidate2 = current / "user" / "brain" / entity_rel
            if candidate2.exists():
                return candidate2
            if candidate2.with_suffix(".md").exists():
                return candidate2.with_suffix(".md")
            current = current.parent
            if current == current.parent:
                break
        return None

    # ------------------------------------------------------------------
    # Summary report
    # ------------------------------------------------------------------

    def _generate_summary(
        self, feature_dir: Path, proto_dir: Path,
        serve_url: Optional[str], manifest: dict,
    ) -> Optional[str]:
        """Generate a prototype build summary in the feature's reports/ directory."""
        reports_dir = feature_dir / "reports"
        try:
            reports_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.error("Cannot create reports dir: %s", exc)
            return None

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        summary_file = reports_dir / f"prototype-summary-{timestamp}.md"

        lines = [
            f"# Prototype Build Summary", "",
            f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Output:** `{proto_dir}`",
        ]
        if serve_url:
            lines.append(f"**URL:** [{serve_url}]({serve_url})")

        lines.extend([
            "", "## Build Details", "",
            f"- **Brand:** {manifest.get('brand', 'Unknown')}",
            f"- **Library:** {manifest.get('library', 'Unknown')}",
            f"- **Platform:** {manifest.get('platform', 'web')}",
            f"- **Screens:** {manifest.get('total_screens', 'Unknown')}",
            f"- **Components:** {manifest.get('total_components', 'Unknown')}",
            "",
        ])

        screens = manifest.get("screens", [])
        if screens:
            lines.append("## Screens")
            lines.append("")
            for screen in screens:
                if isinstance(screen, dict):
                    lines.append(f"- **{screen.get('name', 'Unknown')}** — "
                                 f"{screen.get('components', 0)} components")
                elif isinstance(screen, str):
                    lines.append(f"- {screen}")
            lines.append("")

        components_used = manifest.get("components_used", [])
        if components_used:
            lines.append("## Components Used")
            lines.append("")
            for comp in components_used:
                if isinstance(comp, dict):
                    lines.append(
                        f"- `{comp.get('name', '')}` ({comp.get('library', '')})"
                    )
                elif isinstance(comp, str):
                    lines.append(f"- `{comp}`")
            lines.append("")

        try:
            summary_file.write_text("\n".join(lines), encoding="utf-8")
            logger.info("Generated prototype summary at %s", summary_file)
            return str(summary_file)
        except Exception as exc:
            logger.error("Failed to write summary: %s", exc)
            return None
