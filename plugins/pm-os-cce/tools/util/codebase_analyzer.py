"""
PM-OS CCE CodebaseAnalyzer (v5.0)

Deep GitHub repository analysis via ``gh api``. Detects component directories,
routing patterns, shared services, and feature flag usage. Results are returned
as a ``CodebaseProfile`` dataclass that can be persisted to Brain.

Usage:
    from pm_os_cce.tools.util.codebase_analyzer import CodebaseAnalyzer
"""

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# --- v5 imports: base plugin ---
try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from core.config_loader import get_config

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

# --- v5 imports: Brain (optional) ---
try:
    from pm_os_brain.tools.brain_core.brain_updater import BrainUpdater
    HAS_BRAIN = True
except ImportError:
    HAS_BRAIN = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ComponentPattern:
    """A component directory or pattern found in the codebase."""
    name: str
    path: str
    design_system_match: Optional[str] = None


@dataclass
class RoutingPattern:
    """A routing pattern detected in the codebase."""
    path: str
    pattern_type: str = ""  # "pages", "app-router", "feature"
    description: str = ""


@dataclass
class ServicePattern:
    """A shared service or library detected in the codebase."""
    name: str
    path: str
    description: str = ""


@dataclass
class FeatureFlagPattern:
    """Feature flag usage detected in the codebase."""
    provider: str  # "statsig", "launchdarkly", "custom"
    toggle_dir: str = ""
    toggle_count: int = 0
    examples: List[str] = field(default_factory=list)


@dataclass
class CodebaseProfile:
    """
    Deep analysis profile for a GitHub repository.

    Extends the basic tech stack info with structural patterns,
    component mappings, and architectural details.
    """
    repo: str  # "owner/repo" format
    analyzed_at: str = ""
    default_branch: str = "main"

    # Architecture overview
    is_monorepo: bool = False
    workspace_dirs: List[str] = field(default_factory=list)
    total_features: int = 0

    # Component patterns
    component_dirs: List[ComponentPattern] = field(default_factory=list)
    design_system_components_found: List[str] = field(default_factory=list)
    non_design_system_components: List[str] = field(default_factory=list)

    # Routing
    routing_type: str = ""
    routes: List[RoutingPattern] = field(default_factory=list)

    # Services and libraries
    services: List[ServicePattern] = field(default_factory=list)

    # Feature flags
    feature_flags: Optional[FeatureFlagPattern] = None

    # Feature directories
    feature_dirs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a serializable dictionary."""
        return {
            "repo": self.repo,
            "analyzed_at": self.analyzed_at,
            "default_branch": self.default_branch,
            "is_monorepo": self.is_monorepo,
            "workspace_dirs": self.workspace_dirs,
            "total_features": self.total_features,
            "component_dirs": [
                {"name": c.name, "path": c.path, "design_system_match": c.design_system_match}
                for c in self.component_dirs
            ],
            "design_system_components_found": self.design_system_components_found,
            "non_design_system_components": self.non_design_system_components,
            "routing_type": self.routing_type,
            "routes": [
                {"path": r.path, "type": r.pattern_type, "desc": r.description}
                for r in self.routes
            ],
            "services": [
                {"name": s.name, "path": s.path, "desc": s.description}
                for s in self.services
            ],
            "feature_flags": {
                "provider": self.feature_flags.provider,
                "toggle_dir": self.feature_flags.toggle_dir,
                "toggle_count": self.feature_flags.toggle_count,
                "examples": self.feature_flags.examples,
            } if self.feature_flags else None,
            "feature_dirs": self.feature_dirs,
        }

    def to_markdown_section(self) -> str:
        """Render as a markdown section for Brain entity enrichment."""
        lines: List[str] = []

        if self.is_monorepo:
            lines.append(f"**Architecture:** Monorepo ({', '.join(self.workspace_dirs)})")
        lines.append(f"**Total Features:** {self.total_features}")
        lines.append("")

        if self.component_dirs:
            lines.append("### Component Patterns")
            for comp in self.component_dirs[:20]:
                ds = f" -> DS: **{comp.design_system_match}**" if comp.design_system_match else ""
                lines.append(f"- `{comp.path}` ({comp.name}){ds}")
            lines.append("")

        if self.design_system_components_found:
            lines.append(
                f"**Design System Components in Codebase:** "
                f"{', '.join(self.design_system_components_found[:15])}"
            )
            if len(self.design_system_components_found) > 15:
                lines.append(f"*(+ {len(self.design_system_components_found) - 15} more)*")
            lines.append("")

        if self.routing_type:
            lines.append(f"### Routing: {self.routing_type}")
            for route in self.routes[:15]:
                lines.append(f"- `{route.path}` ({route.pattern_type})")
            if len(self.routes) > 15:
                lines.append(f"*(+ {len(self.routes) - 15} more routes)*")
            lines.append("")

        if self.services:
            lines.append("### Shared Services / Libraries")
            for svc in self.services[:15]:
                desc = f" -- {svc.description}" if svc.description else ""
                lines.append(f"- `{svc.path}` ({svc.name}){desc}")
            if len(self.services) > 15:
                lines.append(f"*(+ {len(self.services) - 15} more)*")
            lines.append("")

        if self.feature_flags:
            ff = self.feature_flags
            lines.append(f"### Feature Flags ({ff.provider})")
            lines.append(f"- Toggle directory: `{ff.toggle_dir}`")
            lines.append(f"- Toggles found: {ff.toggle_count}")
            if ff.examples:
                lines.append(f"- Examples: {', '.join(ff.examples[:5])}")
            lines.append("")

        if self.feature_dirs:
            lines.append(f"### Feature Directories ({len(self.feature_dirs)})")
            for fd in self.feature_dirs[:10]:
                lines.append(f"- `{fd}`")
            if len(self.feature_dirs) > 10:
                lines.append(f"*(+ {len(self.feature_dirs) - 10} more)*")
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class CodebaseAnalyzer:
    """
    Deep GitHub repository analyzer using ``gh api``.

    Detects:
    - Component directories and design system usage
    - Routing patterns (Next.js pages/app router, React Router)
    - Shared services and libraries
    - Feature flag usage (Statsig, LaunchDarkly, custom toggles)
    - Feature directories and module structure
    """

    def __init__(self, brain_path: Optional[str] = None) -> None:
        if brain_path:
            self._brain_path = Path(brain_path)
        else:
            try:
                paths = get_paths()
                self._brain_path = Path(paths.get("brain_path", "")) / "brain"
            except Exception:
                self._brain_path = Path(".")

        # Load configurable component keywords and feature flag providers
        try:
            config = get_config()
            self._component_keywords = set(
                config.get("codebase_analyzer.component_keywords", [
                    "components", "ui", "design-system",
                ])
            )
            self._ff_providers = config.get("codebase_analyzer.feature_flag_providers", {})
        except Exception:
            self._component_keywords = {"components", "ui", "design-system"}
            self._ff_providers = {}

        # Design system loader name from config (optional)
        try:
            self._ds_loader_module = config.get(
                "codebase_analyzer.design_system_loader", ""
            )
        except Exception:
            self._ds_loader_module = ""

    def analyze(self, repo: str) -> CodebaseProfile:
        """
        Perform deep analysis of a GitHub repository.

        Args:
            repo: Repository in "owner/repo" format.

        Returns:
            CodebaseProfile with structural analysis.
        """
        profile = CodebaseProfile(
            repo=repo,
            analyzed_at=datetime.now().isoformat(),
        )

        # Step 1: Get repo metadata
        meta = self._gh_api(f"repos/{repo}")
        if not meta:
            logger.warning("Cannot access repo %s", repo)
            return profile

        profile.default_branch = meta.get("default_branch", "main")

        # Step 2: Get top-level tree
        tree = self._get_tree(repo, profile.default_branch)
        if not tree:
            return profile

        top_dirs = {e["path"] for e in tree if e.get("type") == "tree"}

        # Step 3: Detect monorepo
        profile.is_monorepo = bool(
            top_dirs & {"packages", "apps", "libs", "modules"}
            or "yarn.lock" in {e["path"] for e in tree if e.get("type") == "blob"}
            and len(top_dirs & {"app", "packages"}) >= 2
        )
        profile.workspace_dirs = sorted(
            top_dirs & {"app", "apps", "packages", "libs", "modules", "services"}
        )

        # Step 4: Analyze subdirectories for each workspace
        for ws_dir in profile.workspace_dirs:
            ws_sha = self._find_sha(tree, ws_dir)
            if ws_sha:
                self._analyze_workspace(repo, ws_dir, ws_sha, profile)

        # Step 5: Detect routing
        self._detect_routing(repo, tree, top_dirs, profile)

        # Step 6: Detect feature flags
        self._detect_feature_flags(repo, tree, top_dirs, profile)

        # Step 7: Cross-reference with design system (optional)
        self._cross_ref_design_system(profile)

        logger.info(
            "CodebaseAnalyzer: %s -- %d component dirs, %d routes, "
            "%d services, %d features, %d design system matches",
            repo,
            len(profile.component_dirs),
            len(profile.routes),
            len(profile.services),
            profile.total_features,
            len(profile.design_system_components_found),
        )

        return profile

    def persist_to_brain(self, profile: CodebaseProfile) -> Optional[Path]:
        """
        Persist a CodebaseProfile to brain/Technical/repositories/.

        Appends a "## Deep Analysis" section to the existing repo profile,
        or creates a new one if it doesn't exist.
        """
        repos_dir = self._brain_path / "Technical" / "repositories"
        repos_dir.mkdir(parents=True, exist_ok=True)

        safe_name = profile.repo.replace("/", "_")
        file_path = repos_dir / f"{safe_name}.md"

        deep_section = profile.to_markdown_section()
        deep_header = (
            f"\n## Deep Analysis\n\n"
            f"*Analyzed: {profile.analyzed_at}*\n\n"
        )

        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            if "## Deep Analysis" in content:
                parts = content.split("## Deep Analysis")
                base = parts[0].rstrip()
                remaining = ""
                if len(parts) > 1:
                    rest = parts[1]
                    next_h2 = rest.find("\n## ")
                    if next_h2 != -1:
                        remaining = rest[next_h2:]
                content = base + "\n" + deep_header + deep_section + remaining
            else:
                content += "\n" + deep_header + deep_section
        else:
            content = (
                f"# {profile.repo}\n\n"
                f"## Overview\n\n"
                f"- **Analyzed:** {profile.analyzed_at}\n"
                f"- **Default Branch:** {profile.default_branch}\n\n"
                + deep_header + deep_section
                + "\n---\n\n"
                f"*Run `/analyze-codebase {profile.repo}` to refresh*\n"
            )

        file_path.write_text(content, encoding="utf-8")
        logger.info("Persisted CodebaseProfile to %s", file_path)
        return file_path

    # ------------------------------------------------------------------
    # Internal: GitHub API
    # ------------------------------------------------------------------

    @staticmethod
    def _gh_api(endpoint: str, jq_filter: str = "") -> Any:
        """Call gh api and return parsed JSON."""
        cmd = ["gh", "api", endpoint]
        if jq_filter:
            cmd.extend(["--jq", jq_filter])
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                logger.warning("gh api %s failed: %s", endpoint, result.stderr[:200])
                return None
            return json.loads(result.stdout) if result.stdout.strip() else None
        except subprocess.TimeoutExpired:
            logger.warning("gh api timeout: %s", endpoint)
            return None
        except json.JSONDecodeError:
            return result.stdout.strip() if result.stdout else None
        except Exception as e:
            logger.warning("gh api error: %s", e)
            return None

    def _get_tree(self, repo: str, ref: str) -> Optional[List[Dict[str, Any]]]:
        """Get the top-level tree for a repo."""
        data = self._gh_api(f"repos/{repo}/git/trees/{ref}")
        if data and "tree" in data:
            return data["tree"]
        return None

    def _get_subtree(self, repo: str, sha: str) -> Optional[List[Dict[str, Any]]]:
        """Get a subtree by SHA."""
        data = self._gh_api(f"repos/{repo}/git/trees/{sha}")
        if data and "tree" in data:
            return data["tree"]
        return None

    @staticmethod
    def _find_sha(tree: List[Dict[str, Any]], path: str) -> Optional[str]:
        """Find the SHA for a path in a tree listing."""
        for entry in tree:
            if entry.get("path") == path and entry.get("type") == "tree":
                return entry["sha"]
        return None

    # ------------------------------------------------------------------
    # Internal: workspace analysis
    # ------------------------------------------------------------------

    def _analyze_workspace(
        self,
        repo: str,
        ws_dir: str,
        ws_sha: str,
        profile: CodebaseProfile,
    ) -> None:
        """Analyze a workspace directory for components, features, and services."""
        subtree = self._get_subtree(repo, ws_sha)
        if not subtree:
            return

        subdirs = {e["path"]: e["sha"] for e in subtree if e.get("type") == "tree"}

        # Detect feature directories
        if "features" in subdirs:
            features_tree = self._get_subtree(repo, subdirs["features"])
            if features_tree:
                feature_names = [
                    e["path"] for e in features_tree if e.get("type") == "tree"
                ]
                profile.feature_dirs.extend(
                    f"{ws_dir}/features/{name}" for name in feature_names
                )
                profile.total_features += len(feature_names)

        # Detect component directories (config-driven keywords)
        for dirname in sorted(subdirs.keys()):
            if dirname.lower() in self._component_keywords:
                comp_tree = self._get_subtree(repo, subdirs[dirname])
                if comp_tree:
                    for entry in comp_tree:
                        if entry.get("type") == "tree":
                            profile.component_dirs.append(
                                ComponentPattern(
                                    name=entry["path"],
                                    path=f"{ws_dir}/{dirname}/{entry['path']}",
                                )
                            )

        # Detect service/library patterns
        service_keywords = {
            "libs", "services", "api", "data-access",
            "operations", "state", "data-schema",
        }
        for dirname in sorted(subdirs.keys()):
            if dirname.lower() in service_keywords:
                svc_tree = self._get_subtree(repo, subdirs[dirname])
                if svc_tree:
                    for entry in svc_tree:
                        if entry.get("type") == "tree":
                            profile.services.append(
                                ServicePattern(
                                    name=entry["path"],
                                    path=f"{ws_dir}/{dirname}/{entry['path']}",
                                )
                            )

        # Detect spaces (unified-spaces pattern)
        if "spaces" in subdirs or "unified-spaces" in subdirs:
            spaces_key = "unified-spaces" if "unified-spaces" in subdirs else "spaces"
            spaces_tree = self._get_subtree(repo, subdirs[spaces_key])
            if spaces_tree:
                for entry in spaces_tree:
                    if entry.get("type") == "tree":
                        profile.routes.append(
                            RoutingPattern(
                                path=f"{ws_dir}/{spaces_key}/{entry['path']}",
                                pattern_type="space",
                                description=f"Unified space: {entry['path']}",
                            )
                        )

    # ------------------------------------------------------------------
    # Internal: routing detection
    # ------------------------------------------------------------------

    def _detect_routing(
        self,
        repo: str,
        tree: List[Dict[str, Any]],
        top_dirs: Set[str],
        profile: CodebaseProfile,
    ) -> None:
        """Detect routing patterns in the repository."""
        for ws in profile.workspace_dirs + [""]:
            if ws:
                ws_sha = self._find_sha(tree, ws)
                if not ws_sha:
                    continue
                ws_tree = self._get_subtree(repo, ws_sha)
                if not ws_tree:
                    continue
            else:
                ws_tree = tree

            ws_dirs = {e["path"]: e["sha"] for e in ws_tree if e.get("type") == "tree"}

            # Next.js pages router
            if "pages" in ws_dirs:
                profile.routing_type = profile.routing_type or "pages-router"
                pages_tree = self._get_subtree(repo, ws_dirs["pages"])
                if pages_tree:
                    for entry in pages_tree:
                        if entry.get("type") == "tree":
                            prefix = f"{ws}/" if ws else ""
                            profile.routes.append(
                                RoutingPattern(
                                    path=f"{prefix}pages/{entry['path']}",
                                    pattern_type="page",
                                )
                            )

            # Next.js app router
            if "app" in ws_dirs and not ws:
                app_tree = self._get_subtree(repo, ws_dirs["app"])
                if app_tree:
                    has_layout = any(
                        e["path"] in ("layout.tsx", "layout.js")
                        for e in app_tree
                        if e.get("type") == "blob"
                    )
                    if has_layout:
                        profile.routing_type = "app-router"

    # ------------------------------------------------------------------
    # Internal: feature flag detection
    # ------------------------------------------------------------------

    def _detect_feature_flags(
        self,
        repo: str,
        tree: List[Dict[str, Any]],
        top_dirs: Set[str],
        profile: CodebaseProfile,
    ) -> None:
        """Detect feature flag usage patterns."""
        # Config-driven feature flag detection
        ff_config = self._ff_providers
        if isinstance(ff_config, dict) and ff_config:
            for provider_name, provider_cfg in ff_config.items():
                toggle_dir = provider_cfg.get("toggle_dir", "")
                if toggle_dir and toggle_dir.rstrip("/") in top_dirs:
                    dir_name = toggle_dir.rstrip("/")
                    sha = self._find_sha(tree, dir_name)
                    if sha:
                        toggle_tree = self._get_subtree(repo, sha)
                        if toggle_tree:
                            toggle_names = [e["path"] for e in toggle_tree]
                            profile.feature_flags = FeatureFlagPattern(
                                provider=provider_name,
                                toggle_dir=f"{dir_name}/",
                                toggle_count=len(toggle_names),
                                examples=toggle_names[:5],
                            )
                            return

        # Generic detection: check common toggle directories
        for flag_dir, provider in [
            ("toggles", "statsig"),
            ("feature-flags", "custom"),
            (".launchdarkly", "launchdarkly"),
            ("flags", "custom"),
        ]:
            if flag_dir in top_dirs:
                fd_sha = self._find_sha(tree, flag_dir)
                if fd_sha:
                    fd_tree = self._get_subtree(repo, fd_sha)
                    if fd_tree:
                        profile.feature_flags = FeatureFlagPattern(
                            provider=provider,
                            toggle_dir=f"{flag_dir}/",
                            toggle_count=len(fd_tree),
                            examples=[e["path"] for e in fd_tree[:5]],
                        )
                        return

    # ------------------------------------------------------------------
    # Internal: design system cross-reference (optional)
    # ------------------------------------------------------------------

    def _cross_ref_design_system(self, profile: CodebaseProfile) -> None:
        """Cross-reference component directories with design system components."""
        if not self._ds_loader_module:
            return

        try:
            import importlib
            mod = importlib.import_module(self._ds_loader_module)
            loader_cls = getattr(mod, "DesignSystemLoader", None)
            if not loader_cls:
                return

            loader = loader_cls(str(self._brain_path))
            all_components = loader.load_components()
            if not all_components:
                return

            ds_names_lower = {
                name.lower(): name for name in all_components
            }

            matched: Set[str] = set()
            unmatched: Set[str] = set()

            for comp in profile.component_dirs:
                comp_lower = comp.name.lower().replace("-", "").replace("_", "")
                if comp_lower in ds_names_lower:
                    comp.design_system_match = ds_names_lower[comp_lower]
                    matched.add(comp.design_system_match)
                else:
                    for ds_lower, ds_name in ds_names_lower.items():
                        if (
                            comp_lower == ds_lower.replace("-", "").replace("_", "")
                            or comp_lower in ds_lower
                            or ds_lower in comp_lower
                        ):
                            comp.design_system_match = ds_name
                            matched.add(ds_name)
                            break
                    else:
                        unmatched.add(comp.name)

            profile.design_system_components_found = sorted(matched)
            profile.non_design_system_components = sorted(unmatched)

        except Exception as exc:
            logger.warning("Design system cross-reference failed: %s", exc)
