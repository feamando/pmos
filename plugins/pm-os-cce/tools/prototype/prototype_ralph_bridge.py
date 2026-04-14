"""
PM-OS CCE PrototypeRalphBridge (v5.0)

Generates Ralph PLAN.md, PROMPT.md, and .ralph-state.json files from a
PrototypePlan so that prototype builds can be executed via Ralph loops.

Usage:
    from pm_os_cce.tools.prototype.prototype_ralph_bridge import (
        PrototypeRalphBridge, RalphPlanResult,
    )
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pm_os_cce.tools.prototype.prototype_engine import ComponentMapping, PrototypePlan
except ImportError:
    from prototype.prototype_engine import ComponentMapping, PrototypePlan

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class RalphPlanResult:
    """Result returned after Ralph plan generation."""

    success: bool
    plan_path: str = ""
    prompt_path: str = ""
    state_path: str = ""
    total_criteria: int = 0
    estimated_loops: int = 0
    message: str = ""
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "plan_path": self.plan_path,
            "prompt_path": self.prompt_path,
            "state_path": self.state_path,
            "total_criteria": self.total_criteria,
            "estimated_loops": self.estimated_loops,
            "message": self.message,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------


class PrototypeRalphBridge:
    """Translates a PrototypePlan into Ralph-compatible artefacts."""

    # ------------------------------------------------------------------
    # Public API — Plan Generation
    # ------------------------------------------------------------------

    def generate_plan(
        self,
        prototype_plan: PrototypePlan,
        feature_slug: str,
        output_dir: str,
    ) -> RalphPlanResult:
        """Generate a complete set of Ralph files for a prototype build."""
        errors: List[str] = []
        out = Path(output_dir)

        try:
            out.mkdir(parents=True, exist_ok=True)
            logger.info("Output directory ready: %s", out)
        except OSError as exc:
            msg = f"Cannot create output directory '{output_dir}': {exc}"
            logger.error(msg)
            return RalphPlanResult(success=False, message=msg, errors=[msg])

        try:
            plan_md = self._build_plan_md(prototype_plan)
        except Exception as exc:
            msg = f"Failed to build PLAN.md content: {exc}"
            logger.error(msg, exc_info=True)
            errors.append(msg)
            plan_md = ""

        try:
            prompt_md = self._build_prompt_md(prototype_plan, output_dir)
        except Exception as exc:
            msg = f"Failed to build PROMPT.md content: {exc}"
            logger.error(msg, exc_info=True)
            errors.append(msg)
            prompt_md = ""

        total_criteria = self._count_criteria(plan_md)

        try:
            ralph_state = self._build_ralph_state(
                prototype_plan, feature_slug, total_criteria
            )
        except Exception as exc:
            msg = f"Failed to build Ralph state: {exc}"
            logger.error(msg, exc_info=True)
            errors.append(msg)
            ralph_state = {}

        plan_path = out / "PLAN.md"
        prompt_path = out / "PROMPT.md"
        state_path = out / ".ralph-state.json"

        try:
            plan_path.write_text(plan_md, encoding="utf-8")
        except OSError as exc:
            errors.append(f"Failed to write PLAN.md: {exc}")

        try:
            prompt_path.write_text(prompt_md, encoding="utf-8")
        except OSError as exc:
            errors.append(f"Failed to write PROMPT.md: {exc}")

        try:
            state_path.write_text(
                json.dumps(ralph_state, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            errors.append(f"Failed to write .ralph-state.json: {exc}")

        success = len(errors) == 0
        summary = (
            f"Generated Ralph plan for '{prototype_plan.title}': "
            f"{total_criteria} criteria across "
            f"{len(prototype_plan.deliverables)} deliverables, "
            f"~{prototype_plan.estimated_ralph_loops} estimated loops"
        )

        return RalphPlanResult(
            success=success,
            plan_path=str(plan_path),
            prompt_path=str(prompt_path),
            state_path=str(state_path),
            total_criteria=total_criteria,
            estimated_loops=prototype_plan.estimated_ralph_loops,
            message=summary,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Public API — Progress Tracking
    # ------------------------------------------------------------------

    def check_progress(self, output_dir: str) -> dict:
        """Read Ralph state and PLAN.md to report build progress."""
        out = Path(output_dir)
        result: Dict[str, Any] = {
            "status": "unknown", "iteration": 0,
            "total_criteria": 0, "completed_criteria": 0,
            "percent_complete": 0, "next_criterion": None, "errors": [],
        }

        state_path = out / ".ralph-state.json"
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                result["status"] = state.get("status", "unknown")
                result["iteration"] = state.get("iteration", 0)
            except (json.JSONDecodeError, OSError) as exc:
                result["errors"].append(f"Cannot read .ralph-state.json: {exc}")
        else:
            result["errors"].append(f".ralph-state.json not found in {output_dir}")

        plan_path = out / "PLAN.md"
        if plan_path.exists():
            try:
                plan_md = plan_path.read_text(encoding="utf-8")
                total = self._count_criteria(plan_md)
                completed = self._count_completed_criteria(plan_md)
                result["total_criteria"] = total
                result["completed_criteria"] = completed
                if total > 0:
                    result["percent_complete"] = round((completed / total) * 100)
                result["next_criterion"] = self._find_next_criterion(plan_md)
            except OSError as exc:
                result["errors"].append(f"Cannot read PLAN.md: {exc}")
        else:
            result["errors"].append(f"PLAN.md not found in {output_dir}")

        if result["total_criteria"] > 0 and result["completed_criteria"] == result["total_criteria"]:
            result["status"] = "complete"
        elif result["completed_criteria"] > 0:
            result["status"] = "in_progress"

        return result

    def resume_plan(self, output_dir: str) -> dict:
        """Prepare Ralph state for resuming an interrupted build."""
        out = Path(output_dir)
        progress = self.check_progress(output_dir)

        if progress["errors"]:
            return {
                "success": False,
                "message": "Cannot resume — errors reading state",
                "progress": progress,
            }

        if progress["status"] == "complete":
            return {
                "success": True,
                "message": "Plan already complete — nothing to resume",
                "progress": progress,
            }

        state_path = out / ".ralph-state.json"
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["status"] = "resumed"
            state["resumed_at"] = datetime.now(timezone.utc).isoformat()
            state["iteration"] = progress["completed_criteria"]
            state_path.write_text(
                json.dumps(state, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except (json.JSONDecodeError, OSError) as exc:
            return {
                "success": False,
                "message": f"Failed to update .ralph-state.json: {exc}",
                "progress": progress,
            }

        return {
            "success": True,
            "message": (
                f"Resumed at criterion {progress['completed_criteria']}"
                f"/{progress['total_criteria']} "
                f"({progress['percent_complete']}% complete)"
            ),
            "progress": progress,
        }

    # ------------------------------------------------------------------
    # Internal — PLAN.md generation
    # ------------------------------------------------------------------

    def _build_plan_md(self, plan: PrototypePlan) -> str:
        """Build the full PLAN.md content."""
        lines: List[str] = [f"# Ralph Plan: {plan.title}", ""]

        lines.append("## Context")
        library = "Zest" if plan.use_zest else "shadcn/ui"
        lines.append(
            f"Build an interactive web prototype for the **{plan.title}** "
            f"feature ({plan.feature_slug}). Brand: {plan.brand}. "
            f"Component library: {library}. "
            f"Target: {plan.total_screens} screens, "
            f"{plan.total_components} components."
        )
        lines.extend(["", "## Phases", ""])

        phase_num = 0
        total_criteria = 0

        for deliverable in plan.deliverables:
            phase_num += 1
            d_name = deliverable.get("name", f"Phase {phase_num}")
            screen_name = deliverable.get("screen_name", "")

            lines.append(f"### Phase {phase_num}: {d_name}")
            lines.append("")

            criteria = self._generate_criteria_for_deliverable(
                deliverable, plan, screen_name
            )
            for criterion in criteria:
                lines.append(f"- [ ] {criterion}")
                total_criteria += 1
            lines.append("")

        lines.append("## Progress")
        lines.append(f"*Progress: 0/{total_criteria} (0%) | Iteration: 0*")
        lines.append("")

        return "\n".join(lines)

    def _generate_criteria_for_deliverable(
        self, deliverable: Dict[str, Any], plan: PrototypePlan, screen_name: str,
    ) -> List[str]:
        """Generate acceptance criteria for a deliverable."""
        d_type = deliverable.get("type", "unknown")
        library = "Zest" if plan.use_zest else "shadcn/ui"

        if d_type == "scaffold":
            return self._criteria_scaffold(plan, library)
        elif d_type == "screen":
            return self._criteria_screen(plan, screen_name, library)
        elif d_type == "navigation":
            return self._criteria_navigation(plan)
        elif d_type == "corner_cases":
            return self._criteria_corner_cases(plan)
        else:
            return [
                f"Implement {deliverable.get('name', 'deliverable')}",
                f"Verify {deliverable.get('name', 'deliverable')} works as described",
            ]

    def _criteria_scaffold(self, plan: PrototypePlan, library: str) -> List[str]:
        criteria = [
            "Create output directory structure with assets/ and screens/ subdirectories",
            (
                f"Generate {plan.brand} brand theme CSS with correct colors "
                f"(primary: {plan.theme.primary_color}, "
                f"secondary: {plan.theme.secondary_color})"
                if plan.theme
                else f"Generate {plan.brand} brand theme CSS with brand colors"
            ),
            "Generate index.html shell with responsive viewport meta, theme CSS link, and navigation header",
        ]
        if plan.total_screens > 1:
            screen_names = [m.screen_name for m in plan.screen_mappings]
            criteria.append(f"Add navigation links for all screens: {', '.join(screen_names)}")
        if plan.use_zest:
            criteria.append("Include Zest component library CSS/JS references in the HTML head")
        return criteria

    def _criteria_screen(self, plan: PrototypePlan, screen_name: str, library: str) -> List[str]:
        mapping: Optional[ComponentMapping] = None
        for m in plan.screen_mappings:
            if m.screen_name == screen_name:
                mapping = m
                break

        criteria = [
            f"Create {screen_name} HTML file with semantic layout and {plan.brand} theme styling",
        ]

        if mapping:
            all_components: List[str] = list(mapping.zest_components) + list(mapping.shadcn_components)
            if all_components:
                criteria.append(f"Render {library} components: {', '.join(all_components)}")
            if mapping.gap_components:
                criteria.append(f"Implement custom HTML/CSS for gap components: {', '.join(mapping.gap_components)}")
            if plan.spec:
                for spec_screen in plan.spec.screens:
                    if spec_screen.name == screen_name and spec_screen.interactions:
                        criteria.append(
                            f"Wire {len(spec_screen.interactions)} interactive behaviour(s) "
                            f"(e.g. button clicks, form validation, state changes)"
                        )
                        break
        else:
            criteria.append(f"Render UI components for {screen_name} using {library}")

        criteria.append(f"Verify {screen_name} renders correctly in desktop and mobile viewports")
        return criteria

    def _criteria_navigation(self, plan: PrototypePlan) -> List[str]:
        screen_names = [m.screen_name for m in plan.screen_mappings]
        criteria = [
            "Wire click handlers on all navigation links and call-to-action buttons",
            f"Test navigation flow across all {len(screen_names)} screens: {' -> '.join(screen_names)}",
            "Ensure browser back/forward navigation works correctly between screens",
        ]
        if plan.spec and plan.spec.interactions:
            criteria.append(
                f"Verify {len(plan.spec.interactions)} cross-screen interaction(s) "
                f"trigger the correct screen transitions"
            )
        return criteria

    def _criteria_corner_cases(self, plan: PrototypePlan) -> List[str]:
        criteria = [
            "Add error state displays (e.g. form validation errors, API failure messages)",
            "Add empty state displays for screens with dynamic content",
            "Add loading/skeleton states for async operations",
        ]
        if plan.spec and plan.spec.corner_cases:
            for case_text in plan.spec.corner_cases[:2]:
                if len(case_text) > 120:
                    case_text = case_text[:117] + "..."
                criteria.append(f"Handle corner case: {case_text}")
        return criteria

    # ------------------------------------------------------------------
    # Internal — PROMPT.md generation
    # ------------------------------------------------------------------

    def _build_prompt_md(self, plan: PrototypePlan, output_dir: str) -> str:
        """Build the full PROMPT.md content."""
        library = "Zest" if plan.use_zest else "shadcn/ui"
        lines: List[str] = [f"# Ralph Prompt: {plan.title}", ""]

        lines.append("## Role")
        lines.append(
            f"You are building a web prototype for the **{plan.title}** "
            f"feature. The prototype should be a realistic, interactive "
            f"HTML/CSS/JS implementation that demonstrates the user flow "
            f"using {plan.brand} brand styling and {library} components."
        )
        lines.extend(["", "## Context"])
        lines.append(f"- **Feature:** `{plan.feature_slug}`")
        lines.append(f"- **Brand:** {plan.brand}")
        lines.append(f"- **Platform:** {plan.platform}")
        lines.append(f"- **Component library:** {library}")
        lines.append(f"- **Output directory:** `{output_dir}`")
        lines.append(f"- **Total screens:** {plan.total_screens}")
        lines.append(f"- **Total components:** {plan.total_components}")
        lines.extend(["", "## Files"])
        lines.append("- **Plan:** `PLAN.md` (acceptance criteria with checkboxes)")
        lines.append("- **State:** `.ralph-state.json` (iteration tracking)")

        if plan.spec and plan.spec.raw_context:
            lines.append(f"- **Feature context:** The context document for `{plan.feature_slug}` (parsed into this plan)")
        lines.append("")

        if plan.theme:
            lines.append("## Brand Theme")
            lines.append(f"- **Brand:** {plan.theme.brand_name}")
            lines.append(f"- **Primary color:** `{plan.theme.primary_color}`")
            lines.append(f"- **Secondary color:** `{plan.theme.secondary_color}`")
            lines.append(f"- **Accent color:** `{plan.theme.accent_color}`")
            lines.append(f"- **Background:** `{plan.theme.background_color}`")
            lines.append(f"- **Text color:** `{plan.theme.text_color}`")
            lines.append(f"- **Font family:** `{plan.theme.font_family}`")
            lines.append(f"- **Heading font:** `{plan.theme.font_family_heading}`")
            lines.append(f"- **Border radius:** `{plan.theme.border_radius}`")
            lines.append("")

        lines.append("## Per-Iteration Instructions")
        lines.append("")
        lines.append("On each iteration, follow these steps exactly:")
        lines.append("")
        lines.append("1. Read `PLAN.md` to find the **next unchecked** criterion (`- [ ]`)")
        lines.append("2. Implement that single criterion completely")
        lines.append("3. Mark it as checked in `PLAN.md` (`- [x]`)")
        lines.append("4. Update the `Progress` line at the bottom of `PLAN.md`")
        lines.append("5. Update `.ralph-state.json`: increment `iteration`, set `status` to `\"in_progress\"`")
        lines.append("6. Commit the changes with a message describing what was implemented")
        lines.append("")
        lines.append("When all criteria are checked, set `.ralph-state.json` `status` to `\"complete\"`.")
        lines.append("")

        lines.append("## Component Library Reference")
        lines.append("")
        if plan.use_zest:
            lines.append(
                f"This prototype uses the **Zest** design system ({plan.brand} variant). "
                "Where Zest components are not available, fall back to semantic HTML with brand CSS variables."
            )
        else:
            lines.append(
                f"This prototype uses **shadcn/ui** components styled with {plan.brand} brand CSS custom properties."
            )
        lines.append("")

        if plan.screen_mappings:
            lines.append("### Components by Screen")
            lines.append("")
            for mapping in plan.screen_mappings:
                lines.append(f"**{mapping.screen_name}** ({mapping.complexity} complexity)")
                if mapping.zest_components:
                    lines.append(f"  - Zest: {', '.join(mapping.zest_components)}")
                if mapping.shadcn_components:
                    lines.append(f"  - shadcn: {', '.join(mapping.shadcn_components)}")
                if mapping.gap_components:
                    lines.append(f"  - Custom/gap: {', '.join(mapping.gap_components)}")
                lines.append("")

        if plan.total_screens > 1:
            lines.append("## Screen Flow")
            lines.append("")
            flow_parts = [m.screen_name for m in plan.screen_mappings]
            lines.append(f"Navigation order: {' -> '.join(flow_parts)}")
            lines.append("")

            if plan.spec and plan.spec.user_flow:
                lines.append("### User Flow Steps")
                lines.append("")
                for i, step in enumerate(plan.spec.user_flow, 1):
                    lines.append(f"{i}. {step}")
                lines.append("")

        lines.append("## Deliverables Summary")
        lines.append("")
        for i, d in enumerate(plan.deliverables, 1):
            loops = d.get("ralph_loops", 1)
            lines.append(f"{i}. **{d['name']}** — {d['description']} (~{loops} loop{'s' if loops != 1 else ''})")
        lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal — Ralph state generation
    # ------------------------------------------------------------------

    def _build_ralph_state(
        self, plan: PrototypePlan, feature_slug: str, total_criteria: int,
    ) -> dict:
        return {
            "feature_id": f"proto-{feature_slug}",
            "plan_path": "PLAN.md",
            "prompt_path": "PROMPT.md",
            "iteration": 0,
            "status": "initialized",
            "created": datetime.now(timezone.utc).isoformat(),
            "total_criteria": total_criteria,
            "estimated_loops": plan.estimated_ralph_loops,
            "prototype_meta": {
                "title": plan.title,
                "brand": plan.brand,
                "platform": plan.platform,
                "use_zest": plan.use_zest,
                "total_screens": plan.total_screens,
                "total_components": plan.total_components,
            },
        }

    # ------------------------------------------------------------------
    # Internal — Criteria counting / scanning
    # ------------------------------------------------------------------

    def _count_criteria(self, plan_md: str) -> int:
        return len(re.findall(r"^- \[[ xX]\] ", plan_md, re.MULTILINE))

    def _count_completed_criteria(self, plan_md: str) -> int:
        return len(re.findall(r"^- \[[xX]\] ", plan_md, re.MULTILINE))

    def _find_next_criterion(self, plan_md: str) -> Optional[str]:
        match = re.search(r"^- \[ \] (.+)$", plan_md, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return None
