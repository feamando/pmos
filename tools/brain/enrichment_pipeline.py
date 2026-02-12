#!/usr/bin/env python3
"""
PM-OS Brain Enrichment Pipeline

Orchestrates re-processing of all data sources to increase entity data density.

Features:
- Parallel enricher execution (4 concurrent)
- Batch LLM calls (10 items per batch)
- Rate limiting (60 requests/minute)
- Checkpoint progress for resumability
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add common to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@dataclass
class EnrichmentResult:
    """Result of enriching an entity."""

    entity_id: str
    source: str
    success: bool
    fields_updated: int = 0
    error: Optional[str] = None


@dataclass
class PipelineProgress:
    """Tracks pipeline progress for resumability."""

    started_at: str
    last_checkpoint: str
    total_entities: int = 0
    processed_entities: int = 0
    successful: int = 0
    failed: int = 0
    sources_completed: List[str] = field(default_factory=list)
    current_source: Optional[str] = None
    last_entity_id: Optional[str] = None


class EnrichmentPipeline:
    """
    Orchestrates entity enrichment from multiple data sources.

    Supports parallel execution, rate limiting, and checkpointing.
    """

    SOURCES = ["gdocs", "slack", "jira", "github", "context", "session"]

    def __init__(
        self,
        brain_path: Path,
        max_workers: int = 4,
        batch_size: int = 10,
        rate_limit: int = 60,  # requests per minute
        checkpoint_file: Optional[Path] = None,
    ):
        self.brain_path = brain_path
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.rate_limit = rate_limit
        self.checkpoint_file = (
            checkpoint_file or brain_path / ".enrichment_checkpoint.json"
        )

        self.progress: Optional[PipelineProgress] = None
        self.results: List[EnrichmentResult] = []

        # Rate limiting
        self._request_times: List[float] = []

    def run(
        self,
        sources: Optional[List[str]] = None,
        resume: bool = True,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Run the enrichment pipeline.

        Args:
            sources: List of sources to process (default: all)
            resume: Resume from checkpoint if available
            dry_run: Preview without making changes

        Returns:
            Summary of enrichment results
        """
        sources = sources or self.SOURCES

        # Load or create progress
        if resume and self.checkpoint_file.exists():
            self.progress = self._load_checkpoint()
            print(
                f"Resuming from checkpoint: {self.progress.processed_entities}/{self.progress.total_entities}"
            )
        else:
            self.progress = PipelineProgress(
                started_at=datetime.utcnow().isoformat(),
                last_checkpoint=datetime.utcnow().isoformat(),
            )

        # Count total entities
        entity_files = list(self.brain_path.rglob("*.md"))
        entity_files = [
            f for f in entity_files if f.name.lower() not in ("readme.md", "index.md")
        ]
        self.progress.total_entities = len(entity_files)

        print(f"Enrichment Pipeline Starting")
        print(f"  Total entities: {self.progress.total_entities}")
        print(f"  Sources: {', '.join(sources)}")
        print(f"  Workers: {self.max_workers}")
        print(f"  Dry run: {dry_run}")
        print()

        # Process each source
        for source in sources:
            if source in self.progress.sources_completed:
                print(f"Skipping {source} (already completed)")
                continue

            self.progress.current_source = source
            print(f"Processing source: {source}")

            enricher = self._get_enricher(source)
            if not enricher:
                print(f"  No enricher available for {source}")
                continue

            # Get data for this source
            source_data = self._load_source_data(source)
            if not source_data:
                print(f"  No data found for {source}")
                self.progress.sources_completed.append(source)
                continue

            # Process in batches
            results = self._process_source(source, source_data, enricher, dry_run)
            self.results.extend(results)

            self.progress.sources_completed.append(source)
            self._save_checkpoint()

            print(f"  Completed {source}: {len(results)} entities processed")

        # Final summary
        return self._get_summary()

    def _get_enricher(self, source: str):
        """Get the enricher for a source."""
        try:
            if source == "gdocs":
                from enrichers.gdocs_enricher import GDocsEnricher

                return GDocsEnricher(self.brain_path)
            elif source == "slack":
                from enrichers.slack_enricher import SlackEnricher

                return SlackEnricher(self.brain_path)
            elif source == "jira":
                from enrichers.jira_enricher import JiraEnricher

                return JiraEnricher(self.brain_path)
            elif source == "github":
                from enrichers.github_enricher import GitHubEnricher

                return GitHubEnricher(self.brain_path)
            elif source == "context":
                from enrichers.context_enricher import ContextEnricher

                return ContextEnricher(self.brain_path)
            elif source == "session":
                from enrichers.session_enricher import SessionEnricher

                return SessionEnricher(self.brain_path)
        except ImportError:
            return None
        return None

    def _load_source_data(self, source: str) -> List[Dict[str, Any]]:
        """Load raw data for a source."""
        # Special handling for context files
        if source == "context":
            return self._load_context_data()

        # Special handling for session research
        if source == "session":
            return self._load_session_data()

        data_dir = self.brain_path / "Inbox" / source.capitalize()
        if not data_dir.exists():
            # Try alternative paths
            alt_paths = {
                "gdocs": self.brain_path.parent / "brain" / "Inbox" / "GDocs" / "Batch",
                "slack": self.brain_path.parent
                / "brain"
                / "Inbox"
                / "Slack"
                / "Messages",
                "jira": self.brain_path.parent / "brain" / "Inbox" / "Jira",
                "github": self.brain_path.parent / "brain" / "Inbox" / "GitHub",
            }
            data_dir = alt_paths.get(source)
            if not data_dir or not data_dir.exists():
                return []

        data = []
        for file in data_dir.glob("*.json"):
            try:
                with open(file, "r") as f:
                    content = json.load(f)
                    if isinstance(content, list):
                        data.extend(content)
                    else:
                        data.append(content)
            except Exception:
                continue

        return data

    def _load_context_data(self) -> List[Dict[str, Any]]:
        """Load daily context files for enrichment."""
        import re

        # Context files are in user/personal/context/ (WCR structure)
        context_dir = self.brain_path.parent / "personal" / "context"
        if not context_dir.exists():
            return []

        data = []
        for file in context_dir.glob("*-context.md"):
            try:
                content = file.read_text(encoding="utf-8")
                # Extract date from filename (e.g., 2026-01-22-context.md)
                date_match = re.match(r"(\d{4}-\d{2}-\d{2})", file.name)
                date = date_match.group(1) if date_match else ""

                data.append(
                    {
                        "content": content,
                        "date": date,
                        "filename": file.name,
                    }
                )
            except Exception:
                continue

        return data

    def _load_session_data(self) -> List[Dict[str, Any]]:
        """Load Claude session research findings for enrichment."""
        session_dir = self.brain_path / "Inbox" / "ClaudeSession" / "Raw"
        if not session_dir.exists():
            return []

        data = []
        for file in session_dir.glob("session_*.json"):
            try:
                with open(file, "r") as f:
                    content = json.load(f)
                    if isinstance(content, list):
                        data.extend(content)
                    else:
                        data.append(content)
            except Exception:
                continue

        return data

    def _process_source(
        self,
        source: str,
        data: List[Dict[str, Any]],
        enricher,
        dry_run: bool,
    ) -> List[EnrichmentResult]:
        """Process all data from a source."""
        results = []

        # Process in batches
        for i in range(0, len(data), self.batch_size):
            batch = data[i : i + self.batch_size]

            # Rate limiting
            self._wait_for_rate_limit()

            if self.max_workers > 1:
                # Parallel processing
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = {
                        executor.submit(
                            self._enrich_item, enricher, item, dry_run
                        ): item
                        for item in batch
                    }

                    for future in as_completed(futures):
                        try:
                            result = future.result()
                            results.append(result)
                            self.progress.processed_entities += 1
                            if result.success:
                                self.progress.successful += 1
                            else:
                                self.progress.failed += 1
                        except Exception as e:
                            self.progress.failed += 1

            else:
                # Sequential processing
                for item in batch:
                    result = self._enrich_item(enricher, item, dry_run)
                    results.append(result)
                    self.progress.processed_entities += 1

            # Checkpoint after each batch
            self._save_checkpoint()

        return results

    def _enrich_item(
        self,
        enricher,
        item: Dict[str, Any],
        dry_run: bool,
    ) -> EnrichmentResult:
        """Enrich a single item."""
        try:
            entity_id = item.get("entity_id") or item.get("id") or "unknown"
            fields_updated = enricher.enrich(item, dry_run=dry_run)

            return EnrichmentResult(
                entity_id=entity_id,
                source=enricher.source_name,
                success=True,
                fields_updated=fields_updated,
            )
        except Exception as e:
            return EnrichmentResult(
                entity_id=item.get("entity_id", "unknown"),
                source=enricher.source_name if enricher else "unknown",
                success=False,
                error=str(e),
            )

    def _wait_for_rate_limit(self):
        """Wait if necessary to respect rate limit."""
        now = time.time()

        # Remove old timestamps
        self._request_times = [t for t in self._request_times if now - t < 60]

        if len(self._request_times) >= self.rate_limit:
            # Wait until oldest request is more than 60 seconds old
            wait_time = 60 - (now - self._request_times[0])
            if wait_time > 0:
                time.sleep(wait_time)

        self._request_times.append(time.time())

    def _load_checkpoint(self) -> PipelineProgress:
        """Load progress from checkpoint file."""
        try:
            with open(self.checkpoint_file, "r") as f:
                data = json.load(f)
                return PipelineProgress(**data)
        except Exception:
            return PipelineProgress(
                started_at=datetime.utcnow().isoformat(),
                last_checkpoint=datetime.utcnow().isoformat(),
            )

    def _save_checkpoint(self):
        """Save progress to checkpoint file."""
        if self.progress:
            self.progress.last_checkpoint = datetime.utcnow().isoformat()
            with open(self.checkpoint_file, "w") as f:
                json.dump(self.progress.__dict__, f, indent=2)

    def _get_summary(self) -> Dict[str, Any]:
        """Get pipeline execution summary."""
        return {
            "total_entities": self.progress.total_entities if self.progress else 0,
            "processed": self.progress.processed_entities if self.progress else 0,
            "successful": self.progress.successful if self.progress else 0,
            "failed": self.progress.failed if self.progress else 0,
            "sources_completed": (
                self.progress.sources_completed if self.progress else []
            ),
            "results": [r.__dict__ for r in self.results[:100]],  # First 100 results
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run Brain enrichment pipeline")
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["gdocs", "slack", "jira", "github", "context", "session"],
        help="Sources to process",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Batch size for processing",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Start fresh, don't resume from checkpoint",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without making changes",
    )

    args = parser.parse_args()

    # Default brain path
    if not args.brain_path:
        from path_resolver import get_paths

        paths = get_paths()
        args.brain_path = paths.user / "brain"

    pipeline = EnrichmentPipeline(
        brain_path=args.brain_path,
        max_workers=args.workers,
        batch_size=args.batch_size,
    )

    summary = pipeline.run(
        sources=args.sources,
        resume=not args.no_resume,
        dry_run=args.dry_run,
    )

    print("\nEnrichment Pipeline Complete")
    print(f"  Total: {summary['total_entities']}")
    print(f"  Processed: {summary['processed']}")
    print(f"  Successful: {summary['successful']}")
    print(f"  Failed: {summary['failed']}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
