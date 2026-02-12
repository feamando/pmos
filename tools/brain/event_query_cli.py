#!/usr/bin/env python3
"""
PM-OS Brain Event Query CLI

Query and inspect events across Brain entities.

Commands:
    timeline <entity_path>            Show event timeline for an entity
    recent [--days N] [--actor X]     Show recent events
    stats [--since DATE]              Show event counts by type and actor

Usage:
    python3 event_query_cli.py timeline Entities/People/Jane_Smith.md
    python3 event_query_cli.py recent --days 7
    python3 event_query_cli.py recent --actor system/jira_enricher
    python3 event_query_cli.py stats --since 2026-02-01
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from event_store import EventStore


def resolve_brain_path() -> Path:
    """Resolve the brain directory path."""
    try:
        import config_loader

        return config_loader.get_root_path() / "user" / "brain"
    except ImportError:
        return Path(__file__).parent.parent.parent / "user" / "brain"


def cmd_timeline(store: EventStore, brain_path: Path, entity_ref: str) -> int:
    """Show event timeline for an entity."""
    entity_path = brain_path / entity_ref

    if not entity_path.exists():
        # Try with .md extension
        if not entity_ref.endswith(".md"):
            entity_path = brain_path / f"{entity_ref}.md"
        if not entity_path.exists():
            print(f"Entity not found: {entity_ref}", file=sys.stderr)
            return 1

    timeline = store.get_entity_timeline(entity_path)

    if not timeline:
        print(f"No events found for {entity_ref}")
        return 0

    print(f"Timeline for {entity_ref}")
    print(f"{'=' * 60}")

    for entry in timeline:
        ts = entry["timestamp"][:19]
        etype = entry["event_type"]
        actor = entry["actor"]
        message = entry.get("message", "")
        changes = entry.get("changes", [])

        print(f"\n  {ts}  [{etype}]")
        print(f"  Actor: {actor}")
        if message:
            print(f"  Message: {message}")
        if changes:
            for c in changes:
                field = c.get("field", "?")
                op = c.get("operation", "?")
                value = c.get("value", "")
                old = c.get("old_value")
                change_str = f"    {field}: {op}"
                if old is not None:
                    change_str += f" ({old} -> {value})"
                elif value:
                    change_str += f" = {value}"
                print(change_str)

    print(f"\n{'=' * 60}")
    print(f"Total: {len(timeline)} events")
    return 0


def cmd_recent(
    store: EventStore,
    brain_path: Path,
    days: int = 1,
    actor: Optional[str] = None,
    entity_type: Optional[str] = None,
    limit: int = 50,
) -> int:
    """Show recent events."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Scope to entity type directory if specified
    entity_pattern = None
    if entity_type:
        entity_pattern = f"Entities/**/{entity_type}/**/*.md"

    actors = [actor] if actor else None

    events = store.query_events(
        since=since,
        actors=actors,
        entity_pattern=entity_pattern,
        limit=limit,
    )

    if not events:
        print(f"No events in the last {days} day(s)")
        if actor:
            print(f"  (filtered by actor: {actor})")
        return 0

    print(f"Recent events (last {days} day(s))")
    if actor:
        print(f"  Actor filter: {actor}")
    print(f"{'=' * 60}")

    for event in events:
        ts = event.timestamp.strftime("%Y-%m-%d %H:%M")
        print(f"\n  {ts}  [{event.event_type}]  {event.entity_id}")
        print(f"  Actor: {event.actor}")
        if event.message:
            print(f"  Message: {event.message[:80]}")

    print(f"\n{'=' * 60}")
    print(f"Total: {len(events)} events")
    return 0


def cmd_stats(
    store: EventStore,
    since: Optional[datetime] = None,
) -> int:
    """Show event statistics."""
    by_type = store.count_events(since=since, group_by="type")
    by_actor = store.count_events(since=since, group_by="actor")

    total = sum(by_type.values())
    since_str = since.strftime("%Y-%m-%d") if since else "all time"

    print(f"Event Statistics (since {since_str})")
    print(f"{'=' * 60}")
    print(f"Total events: {total}")

    if by_type:
        print(f"\nBy type:")
        for etype, count in sorted(by_type.items(), key=lambda x: -x[1]):
            pct = count / total * 100 if total else 0
            print(f"  {etype:30s} {count:5d}  ({pct:.1f}%)")

    if by_actor:
        print(f"\nBy actor:")
        for actor, count in sorted(by_actor.items(), key=lambda x: -x[1]):
            pct = count / total * 100 if total else 0
            print(f"  {actor:30s} {count:5d}  ({pct:.1f}%)")

    print(f"{'=' * 60}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Query Brain entity events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # timeline command
    timeline_parser = subparsers.add_parser("timeline", help="Show entity event timeline")
    timeline_parser.add_argument("entity", help="Entity path relative to brain dir")

    # recent command
    recent_parser = subparsers.add_parser("recent", help="Show recent events")
    recent_parser.add_argument("--days", type=int, default=1, help="Number of days (default: 1)")
    recent_parser.add_argument("--actor", type=str, help="Filter by actor")
    recent_parser.add_argument("--type", type=str, dest="entity_type", help="Filter by entity type directory")
    recent_parser.add_argument("--limit", type=int, default=50, help="Max events (default: 50)")

    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show event statistics")
    stats_parser.add_argument("--since", type=str, help="Start date (YYYY-MM-DD)")

    # brain path (global)
    parser.add_argument("--brain-path", type=Path, help="Path to brain directory")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    brain_path = args.brain_path or resolve_brain_path()
    store = EventStore(brain_path)

    if args.command == "timeline":
        return cmd_timeline(store, brain_path, args.entity)

    elif args.command == "recent":
        return cmd_recent(
            store, brain_path,
            days=args.days,
            actor=args.actor,
            entity_type=args.entity_type,
            limit=args.limit,
        )

    elif args.command == "stats":
        since = None
        if args.since:
            since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
        return cmd_stats(store, since=since)

    return 0


if __name__ == "__main__":
    sys.exit(main())
