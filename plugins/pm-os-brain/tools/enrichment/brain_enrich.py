#!/usr/bin/env python3
"""
PM-OS Brain Enrichment Orchestrator (v5.0)

Runs all brain quality tools in sequence to improve
graph density, identify gaps, and maintain relationship health.

Uses config_loader for configuration, path_resolver for paths,
connector_bridge for external service auth.

Usage:
    python3 brain_enrich.py                    # Full enrichment
    python3 brain_enrich.py --quick            # Quick mode (soft edges only)
    python3 brain_enrich.py --report           # Report only (no changes)
    python3 brain_enrich.py --boot             # Boot-time mode (minimal, fast)
    python3 brain_enrich.py --orphan           # Orphan cleanup mode

Runs:
    1. Graph health baseline
    2. Soft edge inference (by entity type)
    3. Relationship decay scan
    4. Extraction hints summary
    5. Graph health comparison
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    get_paths = None

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    get_config = None

# Sibling imports with try/except pattern
try:
    from ..relationships.body_relationship_extractor import BodyRelationshipExtractor
    from ..relationships.embedding_edge_inferrer import EdgeInferenceReport, EmbeddingEdgeInferrer
    from ..core.entity_cache import EntityCache
    from ..quality.extraction_hints import ExtractionHintsGenerator, ExtractionHintsReport
    from ..quality.graph_health import GraphHealthMonitor, GraphHealthReport
    from ..quality.orphan_analyzer import OrphanAnalyzer
    from ..quality.relationship_decay import RelationshipDecayMonitor, RelationshipDecayReport
except ImportError:
    try:
        from body_relationship_extractor import BodyRelationshipExtractor
        from embedding_edge_inferrer import EdgeInferenceReport, EmbeddingEdgeInferrer
        from brain_core.entity_cache import EntityCache
        from extraction_hints import ExtractionHintsGenerator, ExtractionHintsReport
        from graph_health import GraphHealthMonitor, GraphHealthReport
        from orphan_analyzer import OrphanAnalyzer
        from relationship_decay import RelationshipDecayMonitor, RelationshipDecayReport
    except ImportError:
        BodyRelationshipExtractor = None
        EmbeddingEdgeInferrer = None
        EdgeInferenceReport = None
        EntityCache = None
        ExtractionHintsGenerator = None
        ExtractionHintsReport = None
        GraphHealthMonitor = None
        GraphHealthReport = None
        OrphanAnalyzer = None
        RelationshipDecayMonitor = None
        RelationshipDecayReport = None

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    """Results from a full enrichment run."""

    timestamp: str
    mode: str

    # Baseline
    baseline_entities: int = 0
    baseline_relationships: int = 0
    baseline_orphans: int = 0
    baseline_density: float = 0.0

    # Actions taken
    soft_edges_added: int = 0
    soft_edges_by_type: Dict[str, int] = field(default_factory=dict)

    # Post-enrichment
    final_entities: int = 0
    final_relationships: int = 0
    final_orphans: int = 0
    final_density: float = 0.0

    # Insights
    stale_relationships: int = 0
    high_priority_hints: int = 0
    top_missing_fields: List[str] = field(default_factory=list)

    # Improvements
    density_improvement: float = 0.0
    orphans_reduced: int = 0

    # Orphan mode results
    body_relationships_created: int = 0
    jira_enriched: int = 0
    github_enriched: int = 0
    orphans_marked_no_data: int = 0
    orphans_marked_standalone: int = 0

    # Cache metrics
    cache_entities_loaded: int = 0
    cache_load_time_ms: float = 0.0

    # Parallel metrics
    parallel_enabled: bool = False
    parallel_types_processed: int = 0
    parallel_wall_clock_ms: float = 0.0

    # Incremental metrics
    incremental_enabled: bool = False
    entities_changed: int = 0
    entities_skipped: int = 0
    types_scanned: int = 0
    types_skipped: int = 0

    # ANN metrics
    ann_enabled: bool = False
    ann_queries: int = 0
    ann_fallback_to_bruteforce: int = 0

    # External enrichment metrics
    external_enrichment_ran: bool = False
    relationships_created: int = 0


class BrainEnrichmentOrchestrator:
    """
    Orchestrates all brain enrichment tools.

    Modes:
    - full: Run all tools, apply changes
    - quick: Soft edges only
    - report: Analysis only, no changes
    - boot: Minimal checks for boot-time
    - orphan: Focused orphan cleanup

    Config-driven soft edge thresholds from config.yaml:
      brain.enrichment.soft_edge_config
    """

    # Default soft edge thresholds by entity type (overridable via config)
    DEFAULT_SOFT_EDGE_CONFIG = {
        "brand": {"threshold": 0.85, "limit": 50},
        "system": {"threshold": 0.85, "limit": 100},
        "squad": {"threshold": 0.80, "limit": 50},
        "team": {"threshold": 0.80, "limit": 50},
        "experiment": {"threshold": 0.85, "limit": 50},
        "person": {"threshold": 0.80, "limit": 100},
        "project": {"threshold": 0.92, "limit": 100},
        "component": {"threshold": 0.90, "limit": 200},
    }

    # Boot mode: only these entity types (fast)
    BOOT_ENTITY_TYPES = ["brand", "squad", "team"]

    # State files that should never be committed
    _STATE_FILES = [
        ".enrichment-state.json",
        ".enrichment-snapshot",
        ".enrichment-pid",
        ".enrichment-progress.json",
        ".enrichment-log",
    ]

    def __init__(self, brain_path: Path, verbose: bool = False):
        """Initialize the orchestrator."""
        self.brain_path = brain_path
        self.verbose = verbose

        # Load config-driven soft edge settings
        self._soft_edge_config = self._load_soft_edge_config()

        # Shared entity cache -- single scan for all modules
        if EntityCache is not None:
            self._cache = EntityCache(brain_path)
        else:
            self._cache = None

        # Initialize tools with shared cache
        if GraphHealthMonitor is not None:
            self.graph_health = GraphHealthMonitor(
                brain_path, cache=self._cache
            )
        else:
            self.graph_health = None

        if RelationshipDecayMonitor is not None:
            self.decay_monitor = RelationshipDecayMonitor(brain_path)
        else:
            self.decay_monitor = None

        if ExtractionHintsGenerator is not None:
            self.hints_generator = ExtractionHintsGenerator(brain_path)
        else:
            self.hints_generator = None

    def _load_soft_edge_config(self) -> Dict[str, Any]:
        """Load soft edge config from config.yaml, with defaults."""
        config_values = {}
        if get_config is not None:
            try:
                config = get_config()
                config_values = config.get("brain.enrichment.soft_edge_config", {}) or {}
            except Exception:
                pass

        # Merge config over defaults
        result = dict(self.DEFAULT_SOFT_EDGE_CONFIG)
        if config_values:
            for entity_type, settings in config_values.items():
                if entity_type in result:
                    result[entity_type].update(settings)
                else:
                    result[entity_type] = settings

        return result

    def run(
        self,
        mode: str = "full",
        dry_run: bool = False,
    ) -> EnrichmentResult:
        """
        Run brain enrichment.

        Args:
            mode: full, quick, report, boot, or orphan
            dry_run: Preview changes without applying

        Returns:
            EnrichmentResult with all metrics
        """
        result = EnrichmentResult(
            timestamp=datetime.now().isoformat(),
            mode=mode,
        )

        # Ensure enrichment state files are in .gitignore
        self._ensure_gitignore()

        # Load entity cache once for all modules
        if self._cache is not None:
            if self.verbose:
                logger.info("Loading entity cache...")
            self._cache.load()
            result.cache_entities_loaded = self._cache.entity_count
            result.cache_load_time_ms = self._cache.scan_ms
            if self.verbose:
                logger.info(
                    "  Loaded %d entities in %.0fms",
                    result.cache_entities_loaded, result.cache_load_time_ms,
                )

        # Step 1: Baseline
        if self.verbose:
            logger.info("Step 1: Analyzing baseline graph health...")

        if self.graph_health is not None:
            baseline = self.graph_health.analyze()
            result.baseline_entities = baseline.total_entities
            result.baseline_relationships = baseline.total_relationships
            result.baseline_orphans = baseline.orphan_entities
            result.baseline_density = baseline.density_score

        # Orphan mode: run specialized cleanup
        if mode == "orphan":
            return self._run_orphan_cleanup(result, dry_run)

        if mode == "report":
            self._run_analysis(result)
            result.final_entities = result.baseline_entities
            result.final_relationships = result.baseline_relationships
            result.final_orphans = result.baseline_orphans
            result.final_density = result.baseline_density
            return result

        # Snapshot: create pre-enrichment snapshot before any writes
        if not dry_run and mode not in ("report",):
            self._create_snapshot()

        # Step 2: Soft edge inference
        import time as _time
        parallel = os.environ.get("PMOS_ENRICH_PARALLEL", "1") != "0"
        incremental = os.environ.get("PMOS_ENRICH_INCREMENTAL", "1") != "0"
        result.parallel_enabled = parallel
        result.incremental_enabled = incremental
        if self.verbose:
            logger.info(
                "Step 2: Running soft edge inference (parallel=%s, incremental=%s)...",
                parallel, incremental,
            )

        entity_types = (
            self.BOOT_ENTITY_TYPES
            if mode == "boot"
            else list(self._soft_edge_config.keys())
        )

        # Incremental mode: skip types where no entities changed
        skipped_types: List[str] = []
        if incremental and self._cache is not None:
            entity_types, skipped_types = self._filter_changed_types(entity_types)
            if self.verbose and skipped_types:
                logger.info("  Skipping unchanged types: %s", ", ".join(skipped_types))

        result.types_scanned = len(entity_types)
        result.types_skipped = len(skipped_types)

        # Count changed vs skipped entities
        if self._cache is not None:
            for et in entity_types:
                result.entities_changed += len(self._cache.get_by_type(et))
            for et in skipped_types:
                result.entities_skipped += len(self._cache.get_by_type(et))

        _t_scan_start = _time.perf_counter()
        if parallel and len(entity_types) > 1:
            scan_results = self._parallel_scan(entity_types)
        else:
            scan_results = self._sequential_scan(entity_types)
        _t_scan_end = _time.perf_counter()
        result.parallel_wall_clock_ms = (_t_scan_end - _t_scan_start) * 1000
        result.parallel_types_processed = len(entity_types)

        # Track ANN usage from scan results
        for _, report in scan_results:
            if hasattr(report, 'used_ann') and report.used_ann:
                result.ann_enabled = True
                result.ann_queries += 1
            elif hasattr(report, 'entities_processed') and report.entities_processed >= 20:
                result.ann_fallback_to_bruteforce += 1

        # Sequential apply phase: writes to files (not thread-safe)
        if EmbeddingEdgeInferrer is not None:
            for entity_type, report in scan_results:
                if report.edges and not dry_run:
                    inferrer = EmbeddingEdgeInferrer(
                        self.brain_path,
                        threshold=self._soft_edge_config.get(
                            entity_type, {"threshold": 0.85}
                        )["threshold"],
                        cache=self._cache,
                    )
                    applied = inferrer.apply_edges(report.edges)
                    result.soft_edges_added += applied
                    result.soft_edges_by_type[entity_type] = applied
                elif report.edges:
                    result.soft_edges_by_type[entity_type] = len(report.edges)

        # Step 3: External enrichment (full mode only)
        if mode == "full":
            if self.verbose:
                logger.info("Step 3: Running external enrichment...")
            self._run_external_enrichment(
                result, dry_run,
                jira_limit=30, github_limit=20, gdocs_limit=50,
            )

        # Step 4: Analysis (skip in boot mode)
        if mode != "boot":
            self._run_analysis(result)

        # Step 5: Final metrics
        if self.verbose:
            logger.info("Step 5: Measuring final graph health...")

        if self._cache is not None:
            self._cache.reload()

        if self.graph_health is not None:
            final = self.graph_health.analyze()
            result.final_entities = final.total_entities
            result.final_relationships = final.total_relationships
            result.final_orphans = final.orphan_entities
            result.final_density = final.density_score

        # Calculate improvements
        result.density_improvement = result.final_density - result.baseline_density
        result.orphans_reduced = result.baseline_orphans - result.final_orphans

        # Save incremental state for next run
        if not dry_run:
            self._save_enrichment_state()

        return result

    def _load_enrichment_state(self) -> Dict[str, Any]:
        """Load incremental enrichment state."""
        state_path = self.brain_path / ".enrichment-state.json"
        if not state_path.exists():
            return {}
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_enrichment_state(self) -> None:
        """Save content hashes per type for incremental enrichment."""
        if self._cache is None:
            return

        try:
            from ..core.safe_write import atomic_write_json
        except ImportError:
            try:
                from brain_core.safe_write import atomic_write_json
            except ImportError:
                def atomic_write_json(p, d, **kw):
                    Path(p).write_text(
                        json.dumps(d, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )

        state: Dict[str, Any] = {}
        for entity_type in self._cache.get_types():
            entities = self._cache.get_by_type(entity_type)
            type_hashes = {}
            for eid, fm in entities.items():
                h = fm.get("_content_hash", "")
                if h:
                    type_hashes[eid] = h
            state[entity_type] = {
                "entity_count": len(entities),
                "hashes": type_hashes,
            }

        state_path = self.brain_path / ".enrichment-state.json"
        state_json = json.dumps(state, indent=2, ensure_ascii=False)
        if len(state_json) > 500_000:
            for et in state:
                state[et]["hashes"] = {}
            state_json = json.dumps(state, indent=2, ensure_ascii=False)

        atomic_write_json(state_path, state)

    def _filter_changed_types(
        self,
        entity_types: List[str],
    ) -> Tuple[List[str], List[str]]:
        """Filter entity types to only those with changed entities."""
        if self._cache is None:
            return entity_types, []

        prev_state = self._load_enrichment_state()
        if not prev_state:
            return entity_types, []

        changed = []
        skipped = []

        for et in entity_types:
            prev_type = prev_state.get(et, {})
            prev_hashes = prev_type.get("hashes", {})
            prev_count = prev_type.get("entity_count", 0)

            current_entities = self._cache.get_by_type(et)
            current_count = len(current_entities)

            if current_count != prev_count:
                changed.append(et)
                continue

            changed_entities = False
            for eid, fm in current_entities.items():
                current_hash = fm.get("_content_hash", "")
                prev_hash = prev_hashes.get(eid, "")
                if current_hash != prev_hash:
                    changed_entities = True
                    break

            if not changed_entities:
                for eid in prev_hashes:
                    if eid not in current_entities:
                        changed_entities = True
                        break

            if changed_entities:
                changed.append(et)
            else:
                skipped.append(et)

        return changed, skipped

    def _scan_one_type(self, entity_type: str) -> Tuple[str, Any]:
        """Scan a single entity type for edges (thread-safe, read-only)."""
        if EmbeddingEdgeInferrer is None:
            return entity_type, type('MockReport', (), {'edges': [], 'edges_inferred': 0})()

        config = self._soft_edge_config.get(
            entity_type, {"threshold": 0.85, "limit": 50}
        )
        inferrer = EmbeddingEdgeInferrer(
            self.brain_path,
            threshold=config["threshold"],
            cache=self._cache,
        )
        report = inferrer.scan_for_edges(
            entity_type=entity_type,
            limit=config["limit"],
        )
        return entity_type, report

    def _parallel_scan(self, entity_types: List[str]) -> List[Tuple[str, Any]]:
        """Scan multiple entity types in parallel."""
        results = []
        max_workers = min(4, len(entity_types))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._scan_one_type, et): et
                for et in entity_types
            }
            for future in as_completed(futures):
                et = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    if self.verbose:
                        _, report = result
                        logger.info("  - %s: %d edges found", et, getattr(report, 'edges_inferred', 0))
                except Exception as e:
                    if self.verbose:
                        logger.warning("  - %s: Warning: %s", et, e)

        type_order = {et: i for i, et in enumerate(entity_types)}
        results.sort(key=lambda r: type_order.get(r[0], 999))
        return results

    def _sequential_scan(self, entity_types: List[str]) -> List[Tuple[str, Any]]:
        """Scan entity types sequentially (fallback)."""
        results = []
        for entity_type in entity_types:
            try:
                et, report = self._scan_one_type(entity_type)
                results.append((et, report))
                if self.verbose:
                    logger.info("  - %s: %d edges found", entity_type, getattr(report, 'edges_inferred', 0))
            except Exception as e:
                if self.verbose:
                    logger.warning("  - %s: Warning: %s", entity_type, e)
        return results

    def _ensure_gitignore(self) -> None:
        """Ensure enrichment state files are in brain .gitignore."""
        gitignore_path = self.brain_path / ".gitignore"

        existing = ""
        if gitignore_path.exists():
            existing = gitignore_path.read_text(encoding="utf-8")

        existing_lines = set(existing.splitlines())
        missing = [f for f in self._STATE_FILES if f not in existing_lines]

        if not missing:
            return

        addition = "\n".join(missing) + "\n"
        if existing and not existing.endswith("\n"):
            addition = "\n" + addition

        if not existing:
            addition = "# Enrichment state files (auto-generated)\n" + addition

        with open(gitignore_path, "a", encoding="utf-8") as f:
            f.write(addition)

    def _create_snapshot(self) -> None:
        """Create pre-enrichment snapshot via git stash create."""
        try:
            check = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=str(self.brain_path),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if check.returncode != 0:
                if self.verbose:
                    logger.info("  Note: brain directory is not git-initialized, skipping snapshot")
                return

            stash = subprocess.run(
                ["git", "stash", "create"],
                cwd=str(self.brain_path),
                capture_output=True,
                text=True,
                timeout=10,
            )
            ref = stash.stdout.strip()
            snapshot_file = self.brain_path / ".enrichment-snapshot"
            snapshot_file.write_text(ref, encoding="utf-8")
            if self.verbose:
                if ref:
                    logger.info("  Snapshot created: %s", ref[:12])
                else:
                    logger.info("  Snapshot created (clean working tree)")

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            if self.verbose:
                logger.warning("  Warning: snapshot creation failed: %s", e)

    def rollback(self) -> bool:
        """Rollback brain to pre-enrichment state using snapshot.

        Returns:
            True if rollback succeeded, False otherwise.
        """
        snapshot_file = self.brain_path / ".enrichment-snapshot"

        if not snapshot_file.exists():
            raise FileNotFoundError(
                "no enrichment snapshot found -- nothing to rollback"
            )

        ref = snapshot_file.read_text(encoding="utf-8").strip()

        checkout = subprocess.run(
            ["git", "checkout", "--", "."],
            cwd=str(self.brain_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if checkout.returncode != 0:
            logger.warning("git checkout failed: %s", checkout.stderr)

        if ref:
            apply = subprocess.run(
                ["git", "stash", "apply", ref],
                cwd=str(self.brain_path),
                capture_output=True,
                text=True,
                timeout=30,
            )

            if apply.returncode != 0:
                logger.error(
                    "Rollback conflict -- manually inspect with: git stash show -p %s",
                    ref,
                )
                return False

        snapshot_file.unlink()

        if self.verbose:
            if ref:
                logger.info("  Rollback applied from snapshot: %s", ref[:12])
            else:
                logger.info("  Rollback applied (restored to HEAD)")

        return True

    def _run_external_enrichment(
        self,
        result: EnrichmentResult,
        dry_run: bool,
        jira_limit: int = 100,
        github_limit: int = 50,
        gdocs_limit: int = 200,
    ) -> None:
        """Run external enrichment (Jira + GitHub + GDocs)."""
        if self.verbose:
            logger.info("  External enrichment (Jira + GitHub + GDocs)...")

        result.external_enrichment_ran = True

        # Jira enrichment
        try:
            from .jira_enricher import JiraEnricher

            jira_enricher = JiraEnricher(self.brain_path)
            jira_results = jira_enricher.enrich_orphans_live(
                entity_types=["project", "person"],
                limit=jira_limit,
                dry_run=dry_run,
            )
            result.jira_enriched = jira_results.get("enriched", 0)

            if self.verbose:
                logger.info("    Jira: enriched %d entities", result.jira_enriched)
        except Exception as e:
            if self.verbose:
                logger.info("    Jira enrichment skipped: %s", e)

        # GitHub enrichment
        try:
            from .github_enricher import GitHubEnricher

            github_enricher = GitHubEnricher(self.brain_path)
            github_results = github_enricher.enrich_orphans(
                entity_types=["system", "project"],
                limit=github_limit,
                dry_run=dry_run,
            )
            result.github_enriched = github_results.get("enriched", 0)

            if self.verbose:
                logger.info("    GitHub: enriched %d entities", result.github_enriched)
        except Exception as e:
            if self.verbose:
                logger.info("    GitHub enrichment skipped: %s", e)

        # GDocs enrichment
        try:
            from .gdocs_enricher import GDocsEnricher

            gdocs_enricher = GDocsEnricher(self.brain_path)
            gdocs_results = gdocs_enricher.enrich_orphans(
                entity_types=["project", "person", "system", "experiment"],
                limit=gdocs_limit,
                dry_run=dry_run,
            )
            gdocs_enriched = gdocs_results.get("enriched", 0)
            result.relationships_created += gdocs_results.get("relationships_created", 0)

            if self.verbose:
                logger.info(
                    "    GDocs: enriched %d entities, %d relationships",
                    gdocs_enriched,
                    gdocs_results.get("relationships_created", 0),
                )
        except Exception as e:
            if self.verbose:
                logger.info("    GDocs enrichment skipped: %s", e)

    def _run_analysis(self, result: EnrichmentResult) -> None:
        """Run decay and hints analysis."""
        if self.decay_monitor is not None:
            if self.verbose:
                logger.info("Step 3a: Scanning relationship staleness...")
            decay_report = self.decay_monitor.scan_relationships()
            result.stale_relationships = decay_report.stale_relationships

        if self.hints_generator is not None:
            if self.verbose:
                logger.info("Step 3b: Generating extraction hints...")
            hints_report = self.hints_generator.generate_hints(priority_filter="high")
            result.high_priority_hints = hints_report.high_priority_hints
            result.top_missing_fields = list(hints_report.hints_by_field.keys())[:5]

    def _run_orphan_cleanup(
        self,
        result: EnrichmentResult,
        dry_run: bool,
    ) -> EnrichmentResult:
        """
        Run orphan cleanup mode.

        Phases:
        1. Body text relationship extraction
        2. External enrichment (Jira + GitHub + GDocs)
        3. Soft edge inference for remaining orphans
        4. Mark remaining orphans with appropriate reason
        """
        # Phase 1: Body text extraction
        if self.verbose:
            logger.info("Phase 1: Body text relationship extraction...")

        if BodyRelationshipExtractor is not None:
            try:
                body_extractor = BodyRelationshipExtractor(self.brain_path)
                body_report = body_extractor.scan(orphans_only=True, limit=1000)

                if body_report.relationships and not dry_run:
                    applied = body_extractor.apply(body_report.relationships)
                    result.body_relationships_created = applied
                elif body_report.relationships:
                    result.body_relationships_created = len(body_report.relationships)

                if self.verbose:
                    logger.info(
                        "  Found %d potential relationships",
                        len(body_report.relationships),
                    )
                    logger.info("  Applied: %d", result.body_relationships_created)
            except Exception as e:
                if self.verbose:
                    logger.warning("  Warning: Body extraction failed: %s", e)

        # Phase 2: External enrichment
        if self.verbose:
            logger.info("Phase 2: External enrichment (Jira + GitHub + GDocs)...")
        self._run_external_enrichment(result, dry_run)
        result.relationships_created += result.body_relationships_created

        # Phase 3: Soft edge inference for remaining orphans
        if self.verbose:
            logger.info("Phase 3: Soft edge inference for remaining orphans...")

        if EmbeddingEdgeInferrer is not None:
            for entity_type in ["project", "system", "person"]:
                try:
                    inferrer = EmbeddingEdgeInferrer(
                        self.brain_path,
                        threshold=0.85,
                        cache=self._cache,
                    )
                    report = inferrer.scan_for_edges(
                        entity_type=entity_type,
                        limit=50,
                    )

                    if report.edges and not dry_run:
                        applied = inferrer.apply_edges(report.edges)
                        result.soft_edges_added += applied
                    elif report.edges:
                        result.soft_edges_added += len(report.edges)

                except Exception as e:
                    if self.verbose:
                        logger.warning("    %s: %s", entity_type, e)

        if self.verbose:
            logger.info("  Soft edges added: %d", result.soft_edges_added)

        # Phase 4: Mark remaining orphans
        if self.verbose:
            logger.info("Phase 4: Marking remaining orphans...")

        if OrphanAnalyzer is not None:
            try:
                orphan_analyzer = OrphanAnalyzer(self.brain_path)
                standalone_count = orphan_analyzer.mark_standalone(dry_run=dry_run)
                result.orphans_marked_standalone = standalone_count
                orphan_analyzer.clear_reason_for_connected(dry_run=dry_run)

                if self.verbose:
                    logger.info("  Marked %d as standalone", standalone_count)
            except Exception as e:
                if self.verbose:
                    logger.warning("  Orphan analysis failed: %s", e)

        # Final metrics
        if self.verbose:
            logger.info("Measuring final graph health...")

        if self.graph_health is not None:
            final = self.graph_health.analyze()
            result.final_entities = final.total_entities
            result.final_relationships = final.total_relationships
            result.final_orphans = final.orphan_entities
            result.final_density = final.density_score

        result.density_improvement = result.final_density - result.baseline_density
        result.orphans_reduced = result.baseline_orphans - result.final_orphans

        return result


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run brain enrichment to improve graph quality"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "quick", "report", "boot", "orphan"],
        default="full",
        help="Enrichment mode",
    )
    parser.add_argument("--quick", action="store_true", help="Shortcut for --mode quick")
    parser.add_argument("--report", action="store_true", help="Shortcut for --mode report")
    parser.add_argument("--boot", action="store_true", help="Shortcut for --mode boot")
    parser.add_argument("--orphan", action="store_true", help="Shortcut for --mode orphan")
    parser.add_argument("--brain-path", type=Path, help="Path to brain directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--embed", action="store_true", help="Rebuild vector index after enrichment")
    parser.add_argument("--timeout", type=int, default=0, help="Self-imposed timeout in seconds")
    parser.add_argument("--rollback", action="store_true", help="Rollback to pre-enrichment state")
    parser.add_argument("--output", choices=["text", "json"], default="text", help="Output format")

    args = parser.parse_args()

    # Resolve mode shortcuts
    mode = args.mode
    if args.quick:
        mode = "quick"
    elif args.report:
        mode = "report"
    elif args.boot:
        mode = "boot"
    elif args.orphan:
        mode = "orphan"

    # Resolve brain path via path_resolver
    if not args.brain_path:
        if get_paths is not None:
            try:
                paths = get_paths()
                args.brain_path = paths.brain
            except Exception:
                args.brain_path = Path.cwd() / "user" / "brain"
        else:
            args.brain_path = Path.cwd() / "user" / "brain"

    # Handle rollback
    if args.rollback:
        orchestrator = BrainEnrichmentOrchestrator(
            args.brain_path,
            verbose=args.verbose or args.output == "text",
        )
        try:
            success = orchestrator.rollback()
            if success:
                print("Rollback successful -- brain restored to pre-enrichment state.")
                return 0
            else:
                return 1
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Self-imposed timeout via SIGALRM (Unix only)
    if args.timeout > 0 and hasattr(signal, "SIGALRM"):
        def _timeout_handler(signum, frame):
            print(
                f"Enrichment timed out after {args.timeout}s",
                file=sys.stderr,
            )
            sys.exit(124)
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(args.timeout)

    # Run enrichment
    orchestrator = BrainEnrichmentOrchestrator(
        args.brain_path,
        verbose=args.verbose or args.output == "text",
    )

    result = orchestrator.run(mode=mode, dry_run=args.dry_run)

    # Cancel timeout if still active
    if args.timeout > 0 and hasattr(signal, "SIGALRM"):
        signal.alarm(0)

    # Rebuild vector index if requested
    if args.embed and mode != "boot" and not args.dry_run:
        try:
            from ..index.vector_index import BrainVectorIndex, VECTOR_AVAILABLE
            if VECTOR_AVAILABLE:
                if args.verbose or args.output == "text":
                    print("Step 5: Rebuilding vector index...")
                vi = BrainVectorIndex(args.brain_path)
                vi_stats = vi.build_index()
                if args.verbose or args.output == "text":
                    print(f"  Indexed {vi_stats['entities_indexed']} entities")
            else:
                if args.verbose or args.output == "text":
                    print("Step 5: Skipped vector index (dependencies not installed)")
        except Exception as e:
            if args.verbose or args.output == "text":
                print(f"Step 5: Vector index rebuild failed: {e}")

    # Output
    if args.output == "json":
        output = {
            "timestamp": result.timestamp,
            "mode": result.mode,
            "baseline": {
                "entities": result.baseline_entities,
                "relationships": result.baseline_relationships,
                "orphans": result.baseline_orphans,
                "density": result.baseline_density,
            },
            "actions": {
                "soft_edges_added": result.soft_edges_added,
                "by_type": result.soft_edges_by_type,
            },
            "final": {
                "entities": result.final_entities,
                "relationships": result.final_relationships,
                "orphans": result.final_orphans,
                "density": result.final_density,
            },
            "insights": {
                "stale_relationships": result.stale_relationships,
                "high_priority_hints": result.high_priority_hints,
                "top_missing_fields": result.top_missing_fields,
            },
            "improvements": {
                "density_change": round(result.density_improvement, 4),
                "orphans_reduced": result.orphans_reduced,
            },
            "performance": {
                "cache_entities_loaded": result.cache_entities_loaded,
                "cache_load_time_ms": round(result.cache_load_time_ms, 1),
                "parallel_enabled": result.parallel_enabled,
                "parallel_types_processed": result.parallel_types_processed,
                "parallel_wall_clock_ms": round(result.parallel_wall_clock_ms, 1),
                "incremental_enabled": result.incremental_enabled,
                "types_scanned": result.types_scanned,
                "types_skipped": result.types_skipped,
                "entities_changed": result.entities_changed,
                "entities_skipped": result.entities_skipped,
                "ann_enabled": result.ann_enabled,
                "ann_queries": result.ann_queries,
                "ann_fallback_to_bruteforce": result.ann_fallback_to_bruteforce,
            },
        }
        if result.external_enrichment_ran:
            output["external_enrichment"] = {
                "jira_enriched": result.jira_enriched,
                "github_enriched": result.github_enriched,
                "relationships_created": result.relationships_created,
            }
        if result.mode == "orphan":
            output["orphan_cleanup"] = {
                "body_relationships": result.body_relationships_created,
                "jira_enriched": result.jira_enriched,
                "github_enriched": result.github_enriched,
                "marked_standalone": result.orphans_marked_standalone,
            }
        print(json.dumps(output, indent=2))
    else:
        print()
        print("=" * 60)
        print("Brain Enrichment Complete")
        print("=" * 60)
        print(f"Mode: {result.mode}")
        print(f"Timestamp: {result.timestamp}")
        print()

        print("Baseline:")
        print(f"  Entities: {result.baseline_entities}")
        print(f"  Relationships: {result.baseline_relationships}")
        print(f"  Orphans: {result.baseline_orphans}")
        print(f"  Density: {result.baseline_density:.3f}")
        print()

        if result.soft_edges_added > 0 or result.soft_edges_by_type:
            print("Soft Edges Added:")
            print(f"  Total: {result.soft_edges_added}")
            for etype, count in result.soft_edges_by_type.items():
                print(f"  - {etype}: {count}")
            print()

        if result.mode == "orphan":
            print("Orphan Cleanup:")
            print(f"  Body relationships created: {result.body_relationships_created}")
            print(f"  Jira enriched: {result.jira_enriched}")
            print(f"  GitHub enriched: {result.github_enriched}")
            print(f"  Marked standalone: {result.orphans_marked_standalone}")
            print()

        print("Final:")
        print(f"  Entities: {result.final_entities}")
        print(f"  Relationships: {result.final_relationships}")
        print(f"  Orphans: {result.final_orphans}")
        print(f"  Density: {result.final_density:.3f}")
        print()

        if result.stale_relationships > 0 or result.high_priority_hints > 0:
            print("Insights:")
            print(f"  Stale relationships: {result.stale_relationships}")
            print(f"  High-priority hints: {result.high_priority_hints}")
            if result.top_missing_fields:
                print(f"  Top missing: {', '.join(result.top_missing_fields)}")
            print()

        print("Improvements:")
        density_pct = (
            result.density_improvement / max(result.baseline_density, 0.001)
        ) * 100
        print(
            f"  Density: {result.baseline_density:.3f} -> {result.final_density:.3f} ({density_pct:+.1f}%)"
        )
        print(f"  Orphans reduced: {result.orphans_reduced}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
