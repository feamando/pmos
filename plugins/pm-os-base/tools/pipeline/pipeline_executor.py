#!/usr/bin/env python3
"""
Pipeline Executor — loads YAML pipeline definitions and executes them.

Supports plugin-contributed pipeline extensions: plugins can add steps
to boot.yaml and logout.yaml via extension files.

Usage:
    python3 pipeline_executor.py --run boot.yaml --var quick=true
    python3 pipeline_executor.py --list boot.yaml
    python3 pipeline_executor.py --validate boot.yaml
"""

import argparse
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

try:
    from pipeline.pipeline_schema import (
        ErrorStrategy,
        PipelineDefinition,
        PipelineResult,
        PipelineStep,
        StepErrorAction,
        StepResult,
    )
    from pipeline.action_registry import ActionRegistry
except ImportError:
    from pipeline_schema import (
        ErrorStrategy,
        PipelineDefinition,
        PipelineResult,
        PipelineStep,
        StepErrorAction,
        StepResult,
    )
    from action_registry import ActionRegistry

logger = logging.getLogger(__name__)


class PipelineExecutor:
    """Loads and executes YAML pipeline definitions with plugin extension support."""

    def __init__(self, registry: ActionRegistry):
        self.registry = registry

    def load(self, yaml_path: Path) -> PipelineDefinition:
        """Load a pipeline definition from a YAML file."""
        if not yaml_path.exists():
            raise FileNotFoundError(f"Pipeline file not found: {yaml_path}")

        with open(yaml_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict):
            raise ValueError(f"Pipeline YAML must be a mapping, got {type(raw).__name__}")

        pipeline = self._parse_pipeline(raw)

        # Load plugin extensions
        extensions = self._discover_extensions(yaml_path, pipeline.name)
        if extensions:
            pipeline = self._apply_extensions(pipeline, extensions)

        return pipeline

    def _parse_pipeline(self, raw: Dict[str, Any]) -> PipelineDefinition:
        """Parse raw YAML dict into PipelineDefinition."""
        if "name" not in raw:
            raise ValueError("Pipeline YAML must have a 'name' field")

        steps = []
        for i, step_raw in enumerate(raw.get("steps", [])):
            if not isinstance(step_raw, dict):
                raise ValueError(f"Step {i} must be a mapping")
            if "action" not in step_raw:
                raise ValueError(f"Step {i} must have an 'action' field")

            on_error_str = step_raw.get("on_error", "fail")
            try:
                on_error = StepErrorAction(on_error_str)
            except ValueError:
                raise ValueError(
                    f"Step {i} on_error must be one of: skip, fail, retry. Got: {on_error_str}"
                )

            steps.append(PipelineStep(
                name=step_raw.get("name", f"step-{i}"),
                action=step_raw["action"],
                args=step_raw.get("args", {}),
                condition=step_raw.get("condition"),
                on_error=on_error,
                timeout_seconds=step_raw.get("timeout_seconds", 0),
                description=step_raw.get("description", ""),
                background=step_raw.get("background", False),
            ))

        error_strategy_str = raw.get("error_strategy", "fail_fast")
        try:
            error_strategy = ErrorStrategy(error_strategy_str)
        except ValueError:
            raise ValueError(
                f"error_strategy must be one of: fail_fast, continue, retry. Got: {error_strategy_str}"
            )

        return PipelineDefinition(
            name=raw["name"],
            description=raw.get("description", ""),
            steps=steps,
            variables=raw.get("variables", {}),
            error_strategy=error_strategy,
            version=raw.get("version", "1.0"),
        )

    def _discover_extensions(self, base_path: Path, pipeline_name: str) -> List[Dict[str, Any]]:
        """Discover plugin pipeline extensions for this pipeline."""
        extensions = []
        plugins_dir = self._find_plugins_dir(base_path)
        if not plugins_dir:
            return extensions

        extension_filename = f"{pipeline_name}-extension.yaml"
        for plugin_dir in sorted(plugins_dir.iterdir()):
            if not plugin_dir.is_dir() or not plugin_dir.name.startswith("pm-os-"):
                continue
            ext_file = plugin_dir / "pipelines" / extension_filename
            if ext_file.exists():
                try:
                    with open(ext_file, "r", encoding="utf-8") as f:
                        ext_raw = yaml.safe_load(f)
                    if isinstance(ext_raw, dict) and ext_raw.get("extends") == pipeline_name:
                        ext_raw["_source_plugin"] = plugin_dir.name
                        extensions.append(ext_raw)
                        logger.debug("Found extension from %s", plugin_dir.name)
                except Exception as e:
                    logger.warning("Failed to load extension %s: %s", ext_file, e)

        return extensions

    def _find_plugins_dir(self, base_path: Path) -> Optional[Path]:
        """Find the plugins directory by walking up from base_path."""
        current = base_path.resolve().parent
        for _ in range(10):
            # Check if we're inside a plugin's pipelines dir
            if current.name == "plugins" or (current / "pm-os-base").is_dir():
                return current
            # Check parent for plugins/
            plugins_candidate = current / "plugins"
            if plugins_candidate.is_dir() and (plugins_candidate / "pm-os-base").is_dir():
                return plugins_candidate
            current = current.parent
        return None

    def _apply_extensions(
        self, pipeline: PipelineDefinition, extensions: List[Dict[str, Any]]
    ) -> PipelineDefinition:
        """Apply plugin extension steps to a pipeline."""
        for ext in extensions:
            for step_raw in ext.get("steps", []):
                after = step_raw.get("after")
                on_error_str = step_raw.get("on_error", "skip")
                try:
                    on_error = StepErrorAction(on_error_str)
                except ValueError:
                    on_error = StepErrorAction.SKIP

                new_step = PipelineStep(
                    name=step_raw.get("name", "ext-step"),
                    action=step_raw["action"],
                    args=step_raw.get("args", {}),
                    condition=step_raw.get("condition"),
                    on_error=on_error,
                    timeout_seconds=step_raw.get("timeout_seconds", 0),
                    description=step_raw.get("description", ""),
                    background=step_raw.get("background", False),
                )

                # Insert after the named step
                if after:
                    insert_idx = None
                    for i, existing in enumerate(pipeline.steps):
                        if existing.name == after:
                            insert_idx = i + 1
                            break
                    if insert_idx is not None:
                        pipeline.steps.insert(insert_idx, new_step)
                    else:
                        pipeline.steps.append(new_step)
                else:
                    pipeline.steps.append(new_step)

        return pipeline

    def validate(self, pipeline: PipelineDefinition) -> List[str]:
        """Validate a pipeline definition against the registry."""
        issues = []
        for step in pipeline.steps:
            if not self.registry.has(step.action):
                issues.append(f"Step '{step.name}': unknown action '{step.action}'")
        return issues

    def execute(
        self,
        pipeline: PipelineDefinition,
        var_overrides: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
    ) -> PipelineResult:
        """Execute a pipeline definition."""
        context: Dict[str, Any] = dict(pipeline.variables)
        if var_overrides:
            context.update(var_overrides)

        context.setdefault("pm_os_root", os.environ.get("PM_OS_ROOT", ""))
        context.setdefault("pm_os_common", os.environ.get("PM_OS_COMMON", ""))
        context.setdefault("pm_os_user", os.environ.get("PM_OS_USER", ""))

        result = PipelineResult(pipeline_name=pipeline.name, success=True)
        start_time = time.time()

        print(f"=== Pipeline: {pipeline.name} ===")
        if pipeline.description:
            print(f"    {pipeline.description}")
        print()

        for step in pipeline.steps:
            step_result = self._execute_step(step, context, dry_run)
            result.step_results.append(step_result)

            if step_result.skipped:
                result.steps_skipped += 1
            elif step_result.backgrounded:
                result.steps_executed += 1
            elif step_result.success:
                result.steps_executed += 1
                if step_result.data:
                    context[f"_result_{step.name.replace('-', '_').replace(' ', '_')}"] = step_result.data
            else:
                result.steps_failed += 1
                result.steps_executed += 1

                if pipeline.error_strategy == ErrorStrategy.FAIL_FAST:
                    result.success = False
                    print(f"\n  [ABORT] Fail-fast: stopping pipeline after '{step.name}'")
                    break
                elif pipeline.error_strategy == ErrorStrategy.CONTINUE:
                    print(f"  [CONTINUE] Ignoring failure in '{step.name}'")

        if result.steps_failed > 0:
            result.success = False

        result.total_duration_ms = int((time.time() - start_time) * 1000)
        print(f"\n{result.summary}")
        return result

    def _execute_step(
        self, step: PipelineStep, context: Dict[str, Any], dry_run: bool,
    ) -> StepResult:
        """Execute a single pipeline step."""
        if step.condition and not self._evaluate_condition(step.condition, context):
            print(f"  [SKIP] {step.name} (condition: {step.condition})")
            return StepResult(
                step_name=step.name, action=step.action, success=True,
                skipped=True, message=f"Skipped: condition '{step.condition}' not met",
            )

        action_fn = self.registry.resolve(step.action)
        if action_fn is None:
            msg = f"Unknown action: {step.action}"
            print(f"  [ERROR] {step.name}: {msg}")
            return StepResult(step_name=step.name, action=step.action, success=False, error=msg)

        resolved_args = self._resolve_args(step.args, context)

        if dry_run:
            print(f"  [DRY-RUN] {step.name}: {step.action}({resolved_args})")
            return StepResult(
                step_name=step.name, action=step.action, success=True,
                skipped=True, message="Dry run",
            )

        if step.background:
            resolved_args["background"] = True

        tag = "BACKGROUND" if step.background else "RUN"
        print(f"  [{tag}] {step.name}: {step.action} ...", end="", flush=True)
        start = time.time()

        try:
            action_result = action_fn(resolved_args, context)
            duration_ms = int((time.time() - start) * 1000)

            success = action_result.get("success", True)
            message = action_result.get("message", "")
            data = action_result.get("data", {})

            status = "OK" if success else "FAIL"
            print(f" [{status}] {message} ({duration_ms}ms)")

            return StepResult(
                step_name=step.name, action=step.action, success=success,
                message=message, data=data, backgrounded=step.background,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            error_msg = f"{type(e).__name__}: {e}"
            print(f" [ERROR] {error_msg} ({duration_ms}ms)")

            if step.on_error == StepErrorAction.SKIP:
                return StepResult(
                    step_name=step.name, action=step.action, success=True,
                    skipped=True, message=f"Error skipped: {error_msg}",
                    duration_ms=duration_ms,
                )

            return StepResult(
                step_name=step.name, action=step.action, success=False,
                error=error_msg, duration_ms=duration_ms,
            )

    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate a simple condition expression against context."""
        condition = condition.strip()

        if condition.startswith("not "):
            var = condition[4:].strip()
            return not self._is_truthy(context.get(var))

        eq_match = re.match(r"^(\w+)\s*==\s*(.+)$", condition)
        if eq_match:
            var = eq_match.group(1)
            expected = eq_match.group(2).strip().strip("'\"")
            return str(context.get(var, "")).lower() == expected.lower()

        neq_match = re.match(r"^(\w+)\s*!=\s*(.+)$", condition)
        if neq_match:
            var = neq_match.group(1)
            expected = neq_match.group(2).strip().strip("'\"")
            return str(context.get(var, "")).lower() != expected.lower()

        return self._is_truthy(context.get(condition))

    @staticmethod
    def _is_truthy(val: Any) -> bool:
        """Check if a value is truthy, handling string booleans."""
        if val is None:
            return False
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() not in ("", "false", "0", "no", "none")
        return bool(val)

    def _resolve_args(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve ${variable} references in step args from context."""
        resolved = {}
        for key, value in args.items():
            if isinstance(value, str) and "${" in value:
                resolved[key] = self._interpolate(value, context)
            else:
                resolved[key] = value
        return resolved

    @staticmethod
    def _interpolate(template: str, context: Dict[str, Any]) -> str:
        """Replace ${var} references in a string."""
        def replacer(match):
            var_name = match.group(1)
            return str(context.get(var_name, match.group(0)))
        return re.sub(r"\$\{(\w+)}", replacer, template)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="PM-OS Pipeline Executor")
    parser.add_argument("--run", type=str, help="Path to pipeline YAML to execute")
    parser.add_argument("--validate", type=str, help="Validate a pipeline YAML")
    parser.add_argument("--list", type=str, help="List steps in a pipeline YAML")
    parser.add_argument("--var", action="append", default=[], help="Variable override: key=value")
    parser.add_argument("--dry-run", action="store_true", help="Show steps without executing")
    parser.add_argument("--fallback", type=str, help="Fallback command if pipeline fails")
    parser.add_argument("--list-actions", action="store_true", help="List registered actions")

    args = parser.parse_args()

    from builtin_actions import register_all
    registry = ActionRegistry()
    register_all(registry)

    if args.list_actions:
        print("Registered actions:")
        for name in registry.list_actions():
            print(f"  {name}")
        return 0

    executor = PipelineExecutor(registry)

    var_overrides = {}
    for var_str in args.var:
        if "=" in var_str:
            key, val = var_str.split("=", 1)
            if val.lower() in ("true", "yes"):
                var_overrides[key] = True
            elif val.lower() in ("false", "no"):
                var_overrides[key] = False
            else:
                var_overrides[key] = val

    yaml_path = args.run or args.validate or args.list
    if not yaml_path:
        parser.print_help()
        return 1

    pipeline_file = Path(yaml_path)
    if not pipeline_file.is_absolute():
        common = os.environ.get("PM_OS_COMMON", "")
        candidate = Path(common) / "pipelines" / yaml_path
        if candidate.exists():
            pipeline_file = candidate

    try:
        pipeline = executor.load(pipeline_file)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading pipeline: {e}", file=sys.stderr)
        return 1

    if args.validate:
        issues = executor.validate(pipeline)
        if issues:
            print("Validation issues:")
            for issue in issues:
                print(f"  - {issue}")
            return 1
        print(f"Pipeline '{pipeline.name}' is valid ({len(pipeline.steps)} steps)")
        return 0

    if args.list:
        print(f"Pipeline: {pipeline.name}")
        print(f"Steps ({len(pipeline.steps)}):")
        for i, step in enumerate(pipeline.steps, 1):
            cond = f" [if {step.condition}]" if step.condition else ""
            print(f"  {i}. {step.name}: {step.action}{cond}")
        return 0

    result = executor.execute(pipeline, var_overrides=var_overrides, dry_run=args.dry_run)

    if not result.success and args.fallback:
        print(f"\n[FALLBACK] Pipeline failed, running: {args.fallback}")
        os.system(args.fallback)

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
