#!/usr/bin/env python3
"""
PM-OS Brain Enrichment Orchestrator

Runs all TKS-derived brain quality tools in sequence to improve
graph density, identify gaps, and maintain relationship health.

Usage:
    python3 brain_enrich.py                    # Full enrichment
    python3 brain_enrich.py --quick            # Quick mode (soft edges only)
    python3 brain_enrich.py --report           # Report only (no changes)
    python3 brain_enrich.py --boot             # Boot-time mode (minimal, fast)
    python3 brain_enrich.py --orphan           # Orphan cleanup mode (bd-dcc2)

Runs:
    1. Graph health baseline
    2. Soft edge inference (by entity type)
    3. Relationship decay scan
    4. Extraction hints summary
    5. Graph health comparison

Orphan Mode (bd-3771) runs:
    Phase 1 (body): Body text relationship extraction
    Phase 2 (external): Jira + GitHub enrichment
    Phase 3 (inference): Soft edge inference for remaining orphans
    Phase 4 (cleanup): Mark remaining orphans with appropriate reason
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import sibling modules
try:
    from body_relationship_extractor import BodyRelationshipExtractor
    from embedding_edge_inferrer import EdgeInferenceReport, EmbeddingEdgeInferrer
    from extraction_hints import ExtractionHintsGenerator, ExtractionHintsReport
    from graph_health import GraphHealthMonitor, GraphHealthReport
    from orphan_analyzer import OrphanAnalyzer
    from relationship_decay import RelationshipDecayMonitor, RelationshipDecayReport
except ImportError:
    # Add parent to path for standalone execution
    sys.path.insert(0, str(Path(__file__).parent))
    from body_relationship_extractor import BodyRelationshipExtractor
    from embedding_edge_inferrer import EdgeInferenceReport, EmbeddingEdgeInferrer
    from extraction_hints import ExtractionHintsGenerator, ExtractionHintsReport
    from graph_health import GraphHealthMonitor, GraphHealthReport
    from orphan_analyzer import OrphanAnalyzer
    from relationship_decay import RelationshipDecayMonitor, RelationshipDecayReport


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

    # Orphan mode results (bd-dcc2)
    body_relationships_created: int = 0
    jira_enriched: int = 0
    github_enriched: int = 0
    orphans_marked_no_data: int = 0
    orphans_marked_standalone: int = 0


class BrainEnrichmentOrchestrator:
    """
    Orchestrates all brain enrichment tools.

    Modes:
    - full: Run all tools, apply changes
    - quick: Soft edges only
    - report: Analysis only, no changes
    - boot: Minimal checks for boot-time
    - orphan: Focused orphan cleanup (bd-3771)
    """

    # Soft edge thresholds by entity type
    SOFT_EDGE_CONFIG = {
        "brand": {"threshold": 0.85, "limit": 50},
        "system": {"threshold": 0.85, "limit": 100},
        "squad": {"threshold": 0.80, "limit": 50},
        "team": {"threshold": 0.80, "limit": 50},
        "experiment": {"threshold": 0.85, "limit": 50},
        "person": {"threshold": 0.80, "limit": 100},
        "project": {
            "threshold": 0.92,
            "limit": 100,
        },  # Higher threshold for projects (many artifacts)
    }

    # Boot mode: only these entity types (fast)
    BOOT_ENTITY_TYPES = ["brand", "squad", "team"]

    def __init__(self, brain_path: Path, verbose: bool = False):
        """Initialize the orchestrator."""
        self.brain_path = brain_path
        self.verbose = verbose

        # Initialize tools
        self.graph_health = GraphHealthMonitor(brain_path)
        self.decay_monitor = RelationshipDecayMonitor(brain_path)
        self.hints_generator = ExtractionHintsGenerator(brain_path)

    def run(
        self,
        mode: str = "full",
        dry_run: bool = False,
    ) -> EnrichmentResult:
        """
        Run brain enrichment.

        Args:
            mode: full, quick, report, or boot
            dry_run: Preview changes without applying

        Returns:
            EnrichmentResult with all metrics
        """
        result = EnrichmentResult(
            timestamp=datetime.now().isoformat(),
            mode=mode,
        )

        # Step 1: Baseline
        if self.verbose:
            print("Step 1: Analyzing baseline graph health...")

        baseline = self.graph_health.analyze()
        result.baseline_entities = baseline.total_entities
        result.baseline_relationships = baseline.total_relationships
        result.baseline_orphans = baseline.orphan_entities
        result.baseline_density = baseline.density_score

        # Orphan mode: run specialized cleanup
        if mode == "orphan":
            return self._run_orphan_cleanup(result, dry_run)

        if mode == "report":
            # Report mode: just analyze
            self._run_analysis(result)
            result.final_entities = result.baseline_entities
            result.final_relationships = result.baseline_relationships
            result.final_orphans = result.baseline_orphans
            result.final_density = result.baseline_density
            return result

        # Step 2: Soft edge inference
        if self.verbose:
            print("Step 2: Running soft edge inference...")

        entity_types = (
            self.BOOT_ENTITY_TYPES
            if mode == "boot"
            else list(self.SOFT_EDGE_CONFIG.keys())
        )

        for entity_type in entity_types:
            config = self.SOFT_EDGE_CONFIG.get(
                entity_type, {"threshold": 0.85, "limit": 50}
            )

            if self.verbose:
                print(f"  - {entity_type} (threshold={config['threshold']})...")

            try:
                inferrer = EmbeddingEdgeInferrer(
                    self.brain_path,
                    threshold=config["threshold"],
                )
                report = inferrer.scan_for_edges(
                    entity_type=entity_type,
                    limit=config["limit"],
                )

                if report.edges and not dry_run:
                    applied = inferrer.apply_edges(report.edges)
                    result.soft_edges_added += applied
                    result.soft_edges_by_type[entity_type] = applied
                elif report.edges:
                    result.soft_edges_by_type[entity_type] = len(report.edges)

            except Exception as e:
                if self.verbose:
                    print(f"    Warning: {e}")

        # Step 3: Analysis (skip in boot mode)
        if mode != "boot":
            self._run_analysis(result)

        # Step 4: Final metrics
        if self.verbose:
            print("Step 4: Measuring final graph health...")

        final = self.graph_health.analyze()
        result.final_entities = final.total_entities
        result.final_relationships = final.total_relationships
        result.final_orphans = final.orphan_entities
        result.final_density = final.density_score

        # Calculate improvements
        result.density_improvement = result.final_density - result.baseline_density
        result.orphans_reduced = result.baseline_orphans - result.final_orphans

        return result

    def _run_analysis(self, result: EnrichmentResult) -> None:
        """Run decay and hints analysis."""
        # Relationship decay
        if self.verbose:
            print("Step 3a: Scanning relationship staleness...")

        decay_report = self.decay_monitor.scan_relationships()
        result.stale_relationships = decay_report.stale_relationships

        # Extraction hints
        if self.verbose:
            print("Step 3b: Generating extraction hints...")

        hints_report = self.hints_generator.generate_hints(priority_filter="high")
        result.high_priority_hints = hints_report.high_priority_hints
        result.top_missing_fields = list(hints_report.hints_by_field.keys())[:5]

    def _run_orphan_cleanup(
        self,
        result: EnrichmentResult,
        dry_run: bool,
    ) -> EnrichmentResult:
        """
        Run orphan cleanup mode (bd-3771, bd-dcc2).

        Phases:
        1. Body text relationship extraction
        2. External enrichment (Jira + GitHub)
        3. Soft edge inference for remaining orphans
        4. Mark remaining orphans with appropriate reason
        """
        # Phase 1: Body text extraction
        if self.verbose:
            print("Phase 1: Body text relationship extraction...")

        try:
            body_extractor = BodyRelationshipExtractor(self.brain_path)
            body_report = body_extractor.scan(orphans_only=True, limit=1000)

            if body_report.relationships and not dry_run:
                applied = body_extractor.apply(body_report.relationships)
                result.body_relationships_created = applied
            elif body_report.relationships:
                result.body_relationships_created = len(body_report.relationships)

            if self.verbose:
                print(
                    f"  Found {len(body_report.relationships)} potential relationships"
                )
                print(f"  Applied: {result.body_relationships_created}")
        except Exception as e:
            if self.verbose:
                print(f"  Warning: Body extraction failed: {e}")

        # Phase 2: External enrichment
        if self.verbose:
            print("Phase 2: External enrichment (Jira + GitHub)...")

        # Jira enrichment
        try:
            sys.path.insert(0, str(Path(__file__).parent / "enrichers"))
            from enrichers.jira_enricher import JiraEnricher

            jira_enricher = JiraEnricher(self.brain_path)
            jira_results = jira_enricher.enrich_orphans_live(
                entity_types=["project", "person"],
                limit=100,
                dry_run=dry_run,
            )
            result.jira_enriched = jira_results.get("enriched", 0)

            if self.verbose:
                print(f"  Jira: enriched {result.jira_enriched} entities")
        except Exception as e:
            if self.verbose:
                print(f"  Jira enrichment skipped: {e}")

        # GitHub enrichment
        try:
            from enrichers.github_enricher import GitHubEnricher

            github_enricher = GitHubEnricher(self.brain_path)
            github_results = github_enricher.enrich_orphans(
                entity_types=["system", "project"],
                limit=50,
                dry_run=dry_run,
            )
            result.github_enriched = github_results.get("enriched", 0)

            if self.verbose:
                print(f"  GitHub: enriched {result.github_enriched} entities")
        except Exception as e:
            if self.verbose:
                print(f"  GitHub enrichment skipped: {e}")

        # GDocs enrichment (primary source - bd-3771)
        try:
            from enrichers.gdocs_enricher import GDocsEnricher

            gdocs_enricher = GDocsEnricher(self.brain_path)
            gdocs_results = gdocs_enricher.enrich_orphans(
                entity_types=["project", "person", "system", "experiment"],
                limit=200,
                dry_run=dry_run,
            )
            gdocs_enriched = gdocs_results.get("enriched", 0)
            result.relationships_created = (
                result.body_relationships_created
                + gdocs_results.get("relationships_created", 0)
            )

            if self.verbose:
                print(
                    f"  GDocs: enriched {gdocs_enriched} entities, {gdocs_results.get('relationships_created', 0)} relationships"
                )
        except Exception as e:
            if self.verbose:
                print(f"  GDocs enrichment skipped: {e}")

        # Phase 3: Soft edge inference for remaining orphans
        if self.verbose:
            print("Phase 3: Soft edge inference for remaining orphans...")

        for entity_type in ["project", "system", "person"]:
            try:
                inferrer = EmbeddingEdgeInferrer(
                    self.brain_path,
                    threshold=0.85,
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
                    print(f"    {entity_type}: {e}")

        if self.verbose:
            print(f"  Soft edges added: {result.soft_edges_added}")

        # Phase 4: Mark remaining orphans
        if self.verbose:
            print("Phase 4: Marking remaining orphans...")

        try:
            orphan_analyzer = OrphanAnalyzer(self.brain_path)

            # Mark standalone types
            standalone_count = orphan_analyzer.mark_standalone(dry_run=dry_run)
            result.orphans_marked_standalone = standalone_count

            # Clear reason for now-connected entities
            orphan_analyzer.clear_reason_for_connected(dry_run=dry_run)

            if self.verbose:
                print(f"  Marked {standalone_count} as standalone")
        except Exception as e:
            if self.verbose:
                print(f"  Orphan analysis failed: {e}")

        # Final metrics
        if self.verbose:
            print("Measuring final graph health...")

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
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Shortcut for --mode quick",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Shortcut for --mode report",
    )
    parser.add_argument(
        "--boot",
        action="store_true",
        help="Shortcut for --mode boot (minimal, fast)",
    )
    parser.add_argument(
        "--orphan",
        action="store_true",
        help="Shortcut for --mode orphan (orphan cleanup, bd-3771)",
    )
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )

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

    # Resolve brain path
    if not args.brain_path:
        script_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(script_dir))
        try:
            from path_resolver import get_paths

            paths = get_paths()
            args.brain_path = paths.user / "brain"
        except ImportError:
            args.brain_path = Path.cwd() / "user" / "brain"

    # Run enrichment
    orchestrator = BrainEnrichmentOrchestrator(
        args.brain_path,
        verbose=args.verbose or args.output == "text",
    )

    result = orchestrator.run(mode=mode, dry_run=args.dry_run)

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
        }
        # Add orphan mode details
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

        # Orphan mode details
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
