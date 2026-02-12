#!/usr/bin/env python3
"""
File Chunker - Split large context/inbox files into processable chunks.

Handles files that exceed context window limits by splitting at logical
boundaries (sections, documents) while preserving structure.

Usage:
    python3 file_chunker.py --check FILE           # Check if file needs chunking
    python3 file_chunker.py --split FILE           # Split file into chunks
    python3 file_chunker.py --split FILE --output DIR  # Output to specific directory
    python3 file_chunker.py --scan DIR             # Scan directory for large files
    python3 file_chunker.py --status               # Show chunking status

Examples:
    python3 file_chunker.py --check user/brain/Inbox/INBOX_2025-12-05.md
    python3 file_chunker.py --split user/brain/Inbox/INBOX_2025-12-05.md
    python3 file_chunker.py --scan user/brain/Inbox --threshold 1500
"""

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add tools directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# ============================================================================
# CONFIGURATION
# ============================================================================

# Default thresholds
DEFAULT_MAX_LINES = 1500  # Safe limit for context window
DEFAULT_MAX_BYTES = 200 * 1024  # 200KB
OVERLAP_LINES = 50  # Lines to overlap between chunks for context continuity

# Section markers (in order of priority for split points)
SECTION_MARKERS = [
    r"^# ",  # H1 headers
    r"^## ",  # H2 headers
    r"^### ",  # H3 headers
    r"^---+$",  # Horizontal rules
    r"^={3,}$",  # Alternate HR
    r"^\*{3,}$",  # Asterisk HR
]

# Document boundary patterns (strongest split points)
DOCUMENT_BOUNDARIES = [
    r"^# (?:GOOGLE DOCS|GMAIL|JIRA|SLACK|GITHUB)",  # Source sections in inbox
    r"^## \d{4}-\d{2}-\d{2}",  # Date headers
    r"^# Daily Context:",  # Context file header
    r"^## Critical",  # Priority sections
    r"^## Key Decisions",
    r"^## Blockers",
]

# State tracking - use config_loader for proper path resolution
ROOT_PATH = config_loader.get_root_path()
STATE_DIR = ROOT_PATH / "user" / ".cache" / "chunker_state"

# ============================================================================
# DATA CLASSES
# ============================================================================


@dataclass
class FileInfo:
    """Information about a file's size and chunk requirements."""

    path: str
    lines: int
    bytes: int
    needs_chunking: bool
    suggested_chunks: int
    chunk_size: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Chunk:
    """A chunk of a file."""

    index: int
    start_line: int
    end_line: int
    lines: int
    bytes: int
    content: str
    header: str  # First line/section for identification

    def to_dict(self) -> dict:
        d = asdict(self)
        d["content"] = f"[{len(self.content)} chars]"  # Don't serialize full content
        return d


@dataclass
class ChunkingResult:
    """Result of chunking a file."""

    source_file: str
    total_lines: int
    total_bytes: int
    num_chunks: int
    chunks: List[Chunk]
    output_files: List[str]
    timestamp: str


# ============================================================================
# FILE ANALYSIS
# ============================================================================


def analyze_file(
    file_path: str,
    max_lines: int = DEFAULT_MAX_LINES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> FileInfo:
    """Analyze a file to determine if it needs chunking."""
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    lines = content.count("\n") + 1
    bytes_size = len(content.encode("utf-8"))

    needs_chunking = lines > max_lines or bytes_size > max_bytes

    if needs_chunking:
        # Calculate suggested chunks based on both limits
        chunks_by_lines = (lines + max_lines - 1) // max_lines
        chunks_by_bytes = (bytes_size + max_bytes - 1) // max_bytes
        suggested_chunks = max(chunks_by_lines, chunks_by_bytes)
        chunk_size = lines // suggested_chunks
    else:
        suggested_chunks = 1
        chunk_size = lines

    return FileInfo(
        path=str(path),
        lines=lines,
        bytes=bytes_size,
        needs_chunking=needs_chunking,
        suggested_chunks=suggested_chunks,
        chunk_size=chunk_size,
    )


def scan_directory(
    dir_path: str, max_lines: int = DEFAULT_MAX_LINES, pattern: str = "*.md"
) -> List[FileInfo]:
    """Scan a directory for files that need chunking."""
    results = []
    path = Path(dir_path)

    if not path.exists():
        raise FileNotFoundError(f"Directory not found: {dir_path}")

    for file_path in path.rglob(pattern):
        if file_path.is_file():
            try:
                info = analyze_file(str(file_path), max_lines)
                results.append(info)
            except Exception as e:
                print(f"  Warning: Could not analyze {file_path}: {e}", file=sys.stderr)

    # Sort by size (largest first)
    results.sort(key=lambda x: x.lines, reverse=True)
    return results


# ============================================================================
# CHUNKING LOGIC
# ============================================================================


def find_split_points(lines: List[str]) -> List[int]:
    """
    Find optimal split points in the document.
    Returns list of line indices that are good places to split.
    """
    split_points = []

    # First pass: find document boundaries (strongest)
    for i, line in enumerate(lines):
        for pattern in DOCUMENT_BOUNDARIES:
            if re.match(pattern, line, re.IGNORECASE):
                split_points.append((i, 1))  # Priority 1 (highest)
                break

    # Second pass: find section markers
    for i, line in enumerate(lines):
        for priority, pattern in enumerate(SECTION_MARKERS, start=2):
            if re.match(pattern, line):
                # Don't add if already a document boundary
                if not any(sp[0] == i for sp in split_points):
                    split_points.append((i, priority))
                break

    # Sort by line number
    split_points.sort(key=lambda x: x[0])

    return [sp[0] for sp in split_points]


def split_file(
    file_path: str, max_lines: int = DEFAULT_MAX_LINES, overlap: int = OVERLAP_LINES
) -> List[Chunk]:
    """
    Split a file into chunks at logical boundaries.

    Args:
        file_path: Path to the file
        max_lines: Maximum lines per chunk
        overlap: Lines to overlap between chunks

    Returns:
        List of Chunk objects
    """
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    lines = content.split("\n")
    total_lines = len(lines)

    # If file is small enough, return as single chunk
    if total_lines <= max_lines:
        return [
            Chunk(
                index=0,
                start_line=0,
                end_line=total_lines,
                lines=total_lines,
                bytes=len(content.encode("utf-8")),
                content=content,
                header=lines[0] if lines else "",
            )
        ]

    # Find split points
    split_points = find_split_points(lines)

    chunks = []
    current_start = 0
    chunk_index = 0

    while current_start < total_lines:
        # Target end for this chunk
        target_end = min(current_start + max_lines, total_lines)

        # If remaining content is small enough, take it all
        remaining = total_lines - current_start
        if remaining <= max_lines:
            best_split = total_lines
        else:
            # Find the best split point near the target
            best_split = target_end

            # Look for a split point within the last 30% of the chunk
            search_start = current_start + int(max_lines * 0.7)

            for sp in split_points:
                if search_start <= sp <= target_end:
                    best_split = sp
                    break

            # If the remaining content after split is very small, include it
            if total_lines - best_split < max_lines * 0.3:
                best_split = total_lines

        # Create chunk content
        chunk_lines = lines[current_start:best_split]
        chunk_content = "\n".join(chunk_lines)

        # Add chunk header for context
        header = ""
        for line in chunk_lines[:5]:
            if line.strip():
                header = line.strip()[:100]
                break

        chunks.append(
            Chunk(
                index=chunk_index,
                start_line=current_start,
                end_line=best_split,
                lines=len(chunk_lines),
                bytes=len(chunk_content.encode("utf-8")),
                content=chunk_content,
                header=header,
            )
        )

        # If we've reached the end, stop
        if best_split >= total_lines:
            break

        # Move to next chunk (with small overlap for context)
        current_start = best_split - overlap
        chunk_index += 1

    return chunks


def write_chunks(
    chunks: List[Chunk], source_path: str, output_dir: Optional[str] = None
) -> List[str]:
    """
    Write chunks to separate files.

    Returns list of output file paths.
    """
    source = Path(source_path)

    if output_dir:
        out_dir = Path(output_dir)
    else:
        out_dir = source.parent / "chunks"

    out_dir.mkdir(parents=True, exist_ok=True)

    base_name = source.stem
    output_files = []

    for chunk in chunks:
        # Generate chunk filename
        chunk_name = f"{base_name}_chunk{chunk.index:02d}.md"
        chunk_path = out_dir / chunk_name

        # Add chunk metadata header
        header = f"""---
source: {source.name}
chunk: {chunk.index + 1} of {len(chunks)}
lines: {chunk.start_line + 1}-{chunk.end_line}
generated: {datetime.now().isoformat()}
---

"""

        with open(chunk_path, "w", encoding="utf-8") as f:
            f.write(header + chunk.content)

        output_files.append(str(chunk_path))

    return output_files


# ============================================================================
# STATE MANAGEMENT
# ============================================================================


def save_chunking_state(result: ChunkingResult):
    """Save chunking result for tracking."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    source_name = Path(result.source_file).stem
    state_file = STATE_DIR / f"{source_name}_state.json"

    # Convert to serializable dict
    state = {
        "source_file": result.source_file,
        "total_lines": result.total_lines,
        "total_bytes": result.total_bytes,
        "num_chunks": result.num_chunks,
        "output_files": result.output_files,
        "timestamp": result.timestamp,
        "chunks": [c.to_dict() for c in result.chunks],
    }

    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def load_chunking_state(source_path: str) -> Optional[dict]:
    """Load previous chunking state for a file."""
    source_name = Path(source_path).stem
    state_file = STATE_DIR / f"{source_name}_state.json"

    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def get_status() -> dict:
    """Get overall chunking status."""
    status = {"state_dir": str(STATE_DIR), "tracked_files": [], "total_chunks": 0}

    if STATE_DIR.exists():
        for state_file in STATE_DIR.glob("*_state.json"):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                status["tracked_files"].append(
                    {
                        "source": state.get("source_file"),
                        "chunks": state.get("num_chunks"),
                        "timestamp": state.get("timestamp"),
                    }
                )
                status["total_chunks"] += state.get("num_chunks", 0)
            except Exception:
                pass

    return status


# ============================================================================
# CLI OUTPUT FORMATTING
# ============================================================================


def print_file_info(info: FileInfo):
    """Print file analysis results."""
    status = "NEEDS CHUNKING" if info.needs_chunking else "OK"
    color = "\033[91m" if info.needs_chunking else "\033[92m"
    reset = "\033[0m"

    print(f"{color}[{status}]{reset} {info.path}")
    print(f"  Lines: {info.lines:,} | Bytes: {info.bytes:,} ({info.bytes // 1024}KB)")

    if info.needs_chunking:
        print(
            f"  Suggested: {info.suggested_chunks} chunks of ~{info.chunk_size} lines each"
        )


def print_scan_results(results: List[FileInfo], threshold: int):
    """Print directory scan results."""
    needs_chunking = [r for r in results if r.needs_chunking]

    print("=" * 60)
    print("FILE CHUNKING SCAN RESULTS")
    print("=" * 60)
    print(f"Threshold: {threshold} lines")
    print(f"Total files scanned: {len(results)}")
    print(f"Files needing chunking: {len(needs_chunking)}")
    print()

    if needs_chunking:
        print("Files requiring chunking:")
        print("-" * 40)
        for info in needs_chunking:
            print(f"  {info.path}")
            print(f"    {info.lines:,} lines → {info.suggested_chunks} chunks")
        print()

    print("Top 10 largest files:")
    print("-" * 40)
    for info in results[:10]:
        status = "⚠️ " if info.needs_chunking else "✓ "
        print(f"  {status}{info.lines:>6,} lines | {info.path}")


def print_chunking_result(result: ChunkingResult):
    """Print chunking operation results."""
    print("=" * 60)
    print("CHUNKING COMPLETE")
    print("=" * 60)
    print(f"Source: {result.source_file}")
    print(f"Total: {result.total_lines:,} lines, {result.total_bytes:,} bytes")
    print(f"Chunks created: {result.num_chunks}")
    print()
    print("Chunk files:")
    for i, chunk in enumerate(result.chunks):
        print(
            f"  [{i+1}] Lines {chunk.start_line+1}-{chunk.end_line} ({chunk.lines} lines)"
        )
        print(f"      → {result.output_files[i]}")
        print(f"      Header: {chunk.header[:60]}...")
    print()


# ============================================================================
# MAIN
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Split large context/inbox files into processable chunks"
    )

    # Actions
    parser.add_argument(
        "--check", type=str, metavar="FILE", help="Check if a file needs chunking"
    )
    parser.add_argument(
        "--split", type=str, metavar="FILE", help="Split a file into chunks"
    )
    parser.add_argument(
        "--scan",
        type=str,
        metavar="DIR",
        help="Scan directory for files needing chunking",
    )
    parser.add_argument("--status", action="store_true", help="Show chunking status")

    # Options
    parser.add_argument("--output", "-o", type=str, help="Output directory for chunks")
    parser.add_argument(
        "--threshold",
        "-t",
        type=int,
        default=DEFAULT_MAX_LINES,
        help=f"Line threshold for chunking (default: {DEFAULT_MAX_LINES})",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=OVERLAP_LINES,
        help=f"Lines to overlap between chunks (default: {OVERLAP_LINES})",
    )
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without creating files",
    )

    args = parser.parse_args()

    # Status mode
    if args.status:
        status = get_status()
        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print("=" * 60)
            print("CHUNKER STATUS")
            print("=" * 60)
            print(f"State directory: {status['state_dir']}")
            print(f"Tracked files: {len(status['tracked_files'])}")
            print(f"Total chunks: {status['total_chunks']}")
            if status["tracked_files"]:
                print("\nTracked files:")
                for tf in status["tracked_files"]:
                    print(
                        f"  {tf['source']} → {tf['chunks']} chunks ({tf['timestamp'][:10]})"
                    )
        return

    # Check mode
    if args.check:
        try:
            info = analyze_file(args.check, args.threshold)
            if args.json:
                print(json.dumps(info.to_dict(), indent=2))
            else:
                print_file_info(info)
            sys.exit(0 if not info.needs_chunking else 1)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)

    # Scan mode
    if args.scan:
        try:
            results = scan_directory(args.scan, args.threshold)
            if args.json:
                print(json.dumps([r.to_dict() for r in results], indent=2))
            else:
                print_scan_results(results, args.threshold)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # Split mode
    if args.split:
        try:
            # First check if chunking is needed
            info = analyze_file(args.split, args.threshold)

            if not info.needs_chunking:
                print(f"File does not need chunking ({info.lines} lines)")
                return

            # Split the file
            chunks = split_file(args.split, args.threshold, args.overlap)

            if args.dry_run:
                print(f"[DRY RUN] Would create {len(chunks)} chunks:")
                for chunk in chunks:
                    print(
                        f"  Chunk {chunk.index}: lines {chunk.start_line+1}-{chunk.end_line} ({chunk.lines} lines)"
                    )
                return

            # Write chunks
            output_files = write_chunks(chunks, args.split, args.output)

            # Create result
            result = ChunkingResult(
                source_file=args.split,
                total_lines=info.lines,
                total_bytes=info.bytes,
                num_chunks=len(chunks),
                chunks=chunks,
                output_files=output_files,
                timestamp=datetime.now().isoformat(),
            )

            # Save state
            save_chunking_state(result)

            # Output
            if args.json:
                print(
                    json.dumps(
                        {
                            "source": result.source_file,
                            "chunks": len(chunks),
                            "output_files": output_files,
                        },
                        indent=2,
                    )
                )
            else:
                print_chunking_result(result)

        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # No action specified
    parser.print_help()


if __name__ == "__main__":
    main()
