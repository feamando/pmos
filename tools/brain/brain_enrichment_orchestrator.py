#!/usr/bin/env python3
"""
PM-OS Brain Enrichment Orchestrator

Coordinates all enrichment tools to improve Brain graph density.
Called after unified_brain_writer.py, before synapse_builder.py.

TKS-derived tool for the create-context pipeline (bd-dce9).

Modes:
- quick: Body text extraction only (fastest, most effective for orphan reduction)
- full: All enrichers including external sources and embedding edges
- external: GDocs + Jira + GitHub only (requires OAuth/tokens)
- skip: Skip enrichment entirely

Usage:
    python3 brain_enrichment_orchestrator.py --mode quick
    python3 brain_enrichment_orchestrator.py --mode full
    python3 brain_enrichment_orchestrator.py --mode external --dry-run
    python3 brain_enrichment_orchestrator.py --status
"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Handle imports for both module and script execution
try:
    from .body_relationship_extractor import BodyRelationshipExtractor
    from .embedding_edge_inferrer import EmbeddingEdgeInferrer
    from .enrichers.gdocs_enricher import GDocsEnricher
    from .enrichers.github_enricher import GitHubEnricher
    from .enrichers.jira_enricher import JiraEnricher
    from .graph_health import GraphHealthMonitor
except ImportError:
    from body_relationship_extractor import BodyRelationshipExtractor
    from embedding_edge_inferrer import EmbeddingEdgeInferrer
    from enrichers.gdocs_enricher import GDocsEnricher
    from enrichers.github_enricher import GitHubEnricher
    from enrichers.jira_enricher import JiraEnricher
    from graph_health import GraphHealthMonitor


@dataclass
class EnrichmentResult:
    """Results from enrichment run."""

    mode: str
    started_at: str
    completed_at: Optional[str] = None
    success: bool = False

    # Graph health before/after
    orphan_rate_before: float = 0.0
    orphan_rate_after: float = 0.0
    total_entities: int = 0

    # Orphan changes
    orphans_before: int = 0
    orphans_after: int = 0
    orphans_reduced: int = 0

    # Relationships created by source
    relationships_by_source: Dict[str, int] = field(default_factory=dict)
    total_relationships_created: int = 0

    # Errors/warnings
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class BrainEnrichmentOrchestrator:
    """
    Orchestrates Brain enrichment in the proven order:
    1. Body text extraction (most effective)
    2. External sources (GDocs, Jira, GitHub)
    3. Embedding soft edges (least effective but increases density)

    Based on bd-3771 results:
    - Body text: +1328 rels, -499 orphans (MOST EFFECTIVE)
    - GDocs: +2200 rels, -300 orphans
    - Embeddings: +840 rels, -8 orphans (LEAST EFFECTIVE for orphans)
    """

    STATE_FILE = "enrichment_state.json"

    def __init__(self, brain_path: Path):
        """Initialize with brain directory path."""
        self.brain_path = brain_path
        self.state_file = brain_path / self.STATE_FILE

    def run(
        self,
        mode: str = "quick",
        dry_run: bool = False,
        entity_types: Optional[List[str]] = None,
        limit: int = 1000,
    ) -> EnrichmentResult:
        """
        Run enrichment with specified mode.

        Args:
            mode: Enrichment mode ("quick", "full", "external")
            dry_run: If True, preview without changes
            entity_types: Filter to specific entity types
            limit: Maximum orphans to process per enricher

        Returns:
            EnrichmentResult with metrics
        """
        result = EnrichmentResult(
            mode=mode,
            started_at=datetime.now().isoformat(),
        )

        # Measure baseline
        baseline = self._measure_graph_health()
        result.total_entities = baseline["total_entities"]
        result.orphan_rate_before = baseline["orphan_rate"]
        result.orphans_before = baseline["orphan_entities"]

        # Check for minimum entities (fresh brain case)
        if baseline["total_entities"] < 5:
            result.warnings.append(
                "Fresh brain detected (<5 entities). "
                "Run extraction pipeline first to populate entities."
            )
            result.success = True
            result.completed_at = datetime.now().isoformat()
            return result

        # Run enrichers based on mode
        try:
            if mode in ("quick", "full"):
                # Body text extraction - always run first (most effective)
                body_result = self._run_body_extraction(dry_run, limit)
                result.relationships_by_source["body_extraction"] = body_result.get(
                    "relationships_created", 0
                )

            if mode in ("external", "full"):
                # External source enrichment
                external_result = self._run_external_enrichment(
                    dry_run, entity_types or [], limit
                )
                result.relationships_by_source.update(external_result)

            if mode == "full":
                # Embedding soft edges - run last (least effective for orphans)
                embedding_result = self._run_embedding_edges(dry_run, limit)
                result.relationships_by_source["embedding"] = embedding_result.get(
                    "relationships_created", 0
                )

            result.success = True

        except Exception as e:
            result.errors.append(f"Enrichment failed: {str(e)}")
            result.success = False

        # Measure final health
        final = self._measure_graph_health()
        result.orphan_rate_after = final["orphan_rate"]
        result.orphans_after = final["orphan_entities"]
        result.orphans_reduced = result.orphans_before - result.orphans_after
        result.total_relationships_created = sum(
            result.relationships_by_source.values()
        )
        result.completed_at = datetime.now().isoformat()

        # Save state
        if not dry_run:
            self._save_state(result)

        return result

    def _measure_graph_health(self) -> Dict[str, Any]:
        """Measure current graph health metrics."""
        try:
            monitor = GraphHealthMonitor(self.brain_path)
            report = monitor.analyze()
            orphan_rate = (
                report.orphan_entities / report.total_entities * 100
                if report.total_entities > 0
                else 0
            )
            return {
                "total_entities": report.total_entities,
                "orphan_entities": report.orphan_entities,
                "orphan_rate": round(orphan_rate, 1),
                "total_relationships": report.total_relationships,
                "density_score": report.density_score,
            }
        except Exception as e:
            return {
                "total_entities": 0,
                "orphan_entities": 0,
                "orphan_rate": 0,
                "total_relationships": 0,
                "density_score": 0,
                "error": str(e),
            }

    def _run_body_extraction(self, dry_run: bool, limit: int) -> Dict[str, int]:
        """
        Run body text relationship extraction.

        This is the most effective enrichment method based on bd-3771 results.
        Scans entity body text for mentions of other entities.
        """
        try:
            extractor = BodyRelationshipExtractor(self.brain_path)
            report = extractor.scan(orphans_only=True, limit=limit)

            if report.relationships and not dry_run:
                applied = extractor.apply(report.relationships, dry_run=False)
                return {"relationships_created": applied}
            elif report.relationships:
                return {"relationships_created": len(report.relationships)}
            return {"relationships_created": 0}

        except Exception as e:
            return {"relationships_created": 0, "error": str(e)}

    def _run_external_enrichment(
        self,
        dry_run: bool,
        entity_types: List[str],
        limit: int,
    ) -> Dict[str, int]:
        """
        Run external source enrichers (GDocs, Jira, GitHub).

        Handles OAuth token expiry gracefully - continues with other sources.
        """
        results = {}

        # GDocs enrichment
        try:
            gdocs = GDocsEnricher(self.brain_path)
            gdocs_result = gdocs.enrich_orphans(
                entity_types=entity_types or None,
                limit=limit,
                dry_run=dry_run,
            )
            results["gdocs"] = gdocs_result.get("relationships_created", 0)
        except Exception as e:
            error_msg = str(e)
            if "token" in error_msg.lower() or "oauth" in error_msg.lower():
                results["gdocs"] = 0
                results["gdocs_warning"] = "OAuth token expired - skipping GDocs"
            else:
                results["gdocs"] = 0
                results["gdocs_error"] = error_msg

        # Jira enrichment
        try:
            jira = JiraEnricher(self.brain_path)
            jira_result = jira.enrich_orphans(
                entity_types=entity_types or None,
                limit=limit,
                dry_run=dry_run,
            )
            results["jira"] = jira_result.get("relationships_created", 0)
        except Exception as e:
            results["jira"] = 0
            results["jira_error"] = str(e)

        # GitHub enrichment
        try:
            github = GitHubEnricher(self.brain_path)
            github_result = github.enrich_orphans(
                entity_types=entity_types or None,
                limit=limit,
                dry_run=dry_run,
            )
            results["github"] = github_result.get("relationships_created", 0)
        except Exception as e:
            results["github"] = 0
            results["github_error"] = str(e)

        return results

    def _run_embedding_edges(self, dry_run: bool, limit: int) -> Dict[str, int]:
        """
        Run embedding-based soft edge inference.

        Least effective for orphan reduction but improves overall density.
        """
        try:
            inferrer = EmbeddingEdgeInferrer(self.brain_path, threshold=0.65)
            report = inferrer.scan_for_edges(limit=limit)

            if report.edges and not dry_run:
                applied = inferrer.apply_edges(report.edges, dry_run=False)
                return {"relationships_created": applied}
            elif report.edges:
                return {"relationships_created": len(report.edges)}
            return {"relationships_created": 0}

        except ImportError:
            # sentence-transformers not installed
            return {"relationships_created": 0, "warning": "ML libraries not available"}
        except Exception as e:
            return {"relationships_created": 0, "error": str(e)}

    def _save_state(self, result: EnrichmentResult) -> None:
        """Save enrichment state for resumability."""
        try:
            state = {
                "last_run": result.completed_at,
                "mode": result.mode,
                "results": asdict(result),
            }
            self.state_file.write_text(json.dumps(state, indent=2))
        except Exception:
            pass  # Non-critical

    def get_status(self) -> Dict[str, Any]:
        """Get current enrichment status and last run results."""
        status = {
            "brain_path": str(self.brain_path),
            "state_file_exists": self.state_file.exists(),
            "last_run": None,
            "current_health": self._measure_graph_health(),
        }

        if self.state_file.exists():
            try:
                state = json.loads(self.state_file.read_text())
                status["last_run"] = state.get("last_run")
                status["last_mode"] = state.get("mode")
                status["last_results"] = state.get("results", {})
            except Exception:
                pass

        return status


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Orchestrate Brain enrichment to improve graph density"
    )
    parser.add_argument(
        "--mode",
        choices=["quick", "full", "external", "skip"],
        default="quick",
        help="Enrichment mode (default: quick)",
    )
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without making changes",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Maximum orphans to process per enricher (default: 1000)",
    )
    parser.add_argument(
        "--entity-types",
        type=str,
        help="Comma-separated entity types to process",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current status only",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    args = parser.parse_args()

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

    orchestrator = BrainEnrichmentOrchestrator(args.brain_path)

    # Status mode
    if args.status:
        status = orchestrator.get_status()
        if args.output == "json":
            print(json.dumps(status, indent=2))
        else:
            print("Brain Enrichment Status")
            print("=" * 50)
            print(f"Brain path: {status['brain_path']}")
            print(
                f"State file: {'exists' if status['state_file_exists'] else 'not found'}"
            )
            if status["last_run"]:
                print(f"Last run: {status['last_run']}")
                print(f"Last mode: {status.get('last_mode', 'unknown')}")
            print()
            print("Current Health:")
            health = status["current_health"]
            print(f"  Entities: {health['total_entities']}")
            print(f"  Orphans: {health['orphan_entities']} ({health['orphan_rate']}%)")
            print(f"  Relationships: {health['total_relationships']}")
            print(f"  Density: {health['density_score']}")
        return 0

    # Skip mode
    if args.mode == "skip":
        result = EnrichmentResult(
            mode="skip",
            started_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            success=True,
        )
        result.warnings.append("Enrichment skipped by request")
        if args.output == "json":
            print(json.dumps(asdict(result), indent=2))
        else:
            print("Enrichment skipped")
        return 0

    # Parse entity types
    entity_types = None
    if args.entity_types:
        entity_types = [t.strip() for t in args.entity_types.split(",")]

    # Run enrichment
    result = orchestrator.run(
        mode=args.mode,
        dry_run=args.dry_run,
        entity_types=entity_types,
        limit=args.limit,
    )

    # Output
    if args.output == "json":
        print(json.dumps(asdict(result), indent=2))
    else:
        print("Brain Enrichment Report")
        print("=" * 60)
        print(f"Mode: {result.mode}")
        print(f"Status: {'SUCCESS' if result.success else 'FAILED'}")
        print(f"Duration: {result.started_at} -> {result.completed_at}")
        print()

        print("Graph Health:")
        print(
            f"  Orphan rate: {result.orphan_rate_before}% -> {result.orphan_rate_after}%"
        )
        print(f"  Orphans reduced: {result.orphans_reduced}")
        print()

        print("Relationships Created:")
        for source, count in result.relationships_by_source.items():
            if not source.endswith("_error") and not source.endswith("_warning"):
                print(f"  {source}: {count}")
        print(f"  TOTAL: {result.total_relationships_created}")

        if result.warnings:
            print()
            print("Warnings:")
            for warning in result.warnings:
                print(f"  - {warning}")

        if result.errors:
            print()
            print("Errors:")
            for error in result.errors:
                print(f"  - {error}")

        # Target check
        print()
        if result.orphan_rate_after < 30:
            print(f"Target achieved: {result.orphan_rate_after}% < 30%")
        else:
            print(
                f"Target not met: {result.orphan_rate_after}% >= 30% (run with --mode full)"
            )

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
