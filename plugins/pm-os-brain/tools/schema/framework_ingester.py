#!/usr/bin/env python3
"""
Framework Ingester (v5.0) -- Converts vendored Lenny Skills markdown to Brain entities.

Reads curated PM frameworks from frameworks_bundle/, parses their structure,
and writes Brain entities to user/brain/Frameworks/{Framework_Name}.md.

Usage:
    python3 framework_ingester.py [--bundle PATH] [--output PATH] [--dry-run]

Source: Lenny Skills (MIT, RefoundAI) -- 86 PM frameworks from Lenny's Podcast.
"""

import argparse
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# Map framework slugs to categories
CATEGORY_MAP = {
    # Strategy & Planning
    "defining-product-vision": "strategy",
    "prioritizing-roadmap": "strategy",
    "setting-okrs-goals": "strategy",
    "planning-under-uncertainty": "strategy",
    "writing-prds": "strategy",
    "writing-north-star-metrics": "strategy",
    "working-backwards": "strategy",
    "problem-definition": "strategy",
    "platform-strategy": "strategy",
    # Research & Discovery
    "conducting-user-interviews": "research",
    "analyzing-user-feedback": "research",
    "designing-surveys": "research",
    "usability-testing": "research",
    "measuring-product-market-fit": "research",
    "competitive-analysis": "research",
    # Execution
    "shipping-products": "execution",
    "scoping-cutting": "execution",
    "managing-timelines": "execution",
    "managing-tech-debt": "execution",
    "post-mortems-retrospectives": "execution",
    "evaluating-trade-offs": "execution",
    # Leadership & Alignment
    "stakeholder-alignment": "leadership",
    "cross-functional-collaboration": "leadership",
    "running-effective-meetings": "leadership",
    "running-decision-processes": "leadership",
    "giving-presentations": "leadership",
    # Growth & Business
    "designing-growth-loops": "growth",
    "retention-engagement": "growth",
    "pricing-strategy": "growth",
    "user-onboarding": "growth",
    "positioning-messaging": "growth",
    # Team & Process
    "running-effective-1-1s": "leadership",
    "coaching-pms": "leadership",
    "running-design-reviews": "execution",
    "team-rituals": "execution",
}


def parse_skill_md(content: str) -> Dict[str, Any]:
    """Parse a SKILL.md file into structured data."""
    # Extract YAML frontmatter
    fm_match = re.match(r"^---\n(.+?)\n---\n", content, re.DOTALL)
    frontmatter = {}
    body = content
    if fm_match:
        try:
            frontmatter = yaml.safe_load(fm_match.group(1)) or {}
        except yaml.YAMLError:
            pass
        body = content[fm_match.end():]

    # Extract title
    title_match = re.match(r"^#\s+(.+)$", body.strip(), re.MULTILINE)
    title = title_match.group(1).strip() if title_match else frontmatter.get("name", "")

    # Extract sections
    sections = _extract_sections(body)

    # Extract authors from Core Principles
    authors = _extract_authors(sections.get("Core Principles", ""))

    # Extract how-to steps
    how_to = sections.get("How to Help", "")
    key_steps = _extract_steps(how_to)

    # Extract questions
    questions = _extract_list_items(sections.get("Questions to Help Users", ""))

    # Extract common mistakes
    mistakes = _extract_list_items(sections.get("Common Mistakes to Flag", ""))

    # Build core principles summary
    principles = _extract_principles(sections.get("Core Principles", ""))

    return {
        "name": frontmatter.get("name", ""),
        "description": frontmatter.get("description", ""),
        "title": title,
        "authors": authors,
        "key_steps": key_steps,
        "principles": principles,
        "questions": questions,
        "mistakes": mistakes,
    }


def _extract_sections(body: str) -> Dict[str, str]:
    """Extract H2 sections from markdown body."""
    sections: Dict[str, str] = {}
    current_header = None
    current_lines: List[str] = []

    for line in body.split("\n"):
        h2_match = re.match(r"^##\s+(.+)$", line)
        if h2_match:
            if current_header:
                sections[current_header] = "\n".join(current_lines).strip()
            current_header = h2_match.group(1).strip()
            current_lines = []
        elif current_header is not None:
            current_lines.append(line)

    if current_header:
        sections[current_header] = "\n".join(current_lines).strip()

    return sections


def _extract_authors(core_principles: str) -> List[str]:
    """Extract unique author names from Core Principles section."""
    authors = []
    seen = set()
    for match in re.finditer(r"^###\s+.+?\n(.+?):", core_principles, re.MULTILINE):
        name = match.group(1).strip()
        if name and name not in seen and not name.startswith("*"):
            seen.add(name)
            authors.append(name)
    return authors[:5]


def _extract_steps(how_to: str) -> List[str]:
    """Extract numbered steps from How to Help section."""
    steps = []
    for match in re.finditer(
        r"^\d+\.\s+\*\*(.+?)\*\*\s*[-\u2013\u2014]?\s*(.*)", how_to, re.MULTILINE
    ):
        step_title = match.group(1).strip()
        step_desc = match.group(2).strip()
        if step_desc:
            steps.append(f"{step_title}: {step_desc}")
        else:
            steps.append(step_title)
    return steps


def _extract_principles(core_text: str) -> List[str]:
    """Extract principle titles from Core Principles H3 headers."""
    principles = []
    for match in re.finditer(r"^###\s+(.+)$", core_text, re.MULTILINE):
        title = match.group(1).strip()
        principles.append(title)
    return principles


def _extract_list_items(section_text: str) -> List[str]:
    """Extract list items (- or *) from a section."""
    items = []
    for match in re.finditer(r"^[-*]\s+(.+)$", section_text, re.MULTILINE):
        text = match.group(1).strip()
        # Clean bold markers
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        items.append(text)
    return items


def slug_to_entity_name(slug: str) -> str:
    """Convert kebab-case slug to Entity_Name format."""
    return "_".join(word.capitalize() for word in slug.split("-"))


def slug_to_display_name(slug: str) -> str:
    """Convert kebab-case slug to human-readable title."""
    return " ".join(word.capitalize() for word in slug.split("-"))


def build_entity_md(slug: str, parsed: Dict[str, Any]) -> str:
    """Build a Brain entity markdown file from parsed framework data."""
    now = datetime.now(timezone.utc).isoformat()
    entity_id = f"entity/framework/{slug}"
    display_name = parsed["title"] or slug_to_display_name(slug)
    category = CATEGORY_MAP.get(slug, "strategy")
    use_case = parsed["description"]
    authors = parsed["authors"]
    author_str = authors[0] if authors else "Lenny's Podcast guests"

    # Build frontmatter
    fm = {
        "$schema": "brain://entity/framework/v1",
        "$id": entity_id,
        "$type": "framework",
        "$version": 1,
        "$created": now,
        "$updated": now,
        "$confidence": 0.9,
        "$source": "lenny_skills",
        "$status": "active",
        "$relationships": [],
        "$tags": [category, "pm_framework", "lenny_skills"],
        "$aliases": [display_name, slug],
        "name": display_name,
        "author": author_str,
        "category": category,
        "use_case": use_case,
        "key_steps": parsed["key_steps"],
    }

    # Build body
    body_lines = [f"# {display_name}"]
    body_lines.append("")
    body_lines.append(use_case)
    body_lines.append("")

    if parsed["principles"]:
        body_lines.append("## Core Principles")
        body_lines.append("")
        for p in parsed["principles"]:
            body_lines.append(f"- {p}")
        body_lines.append("")

    if parsed["questions"]:
        body_lines.append("## Key Questions")
        body_lines.append("")
        for q in parsed["questions"][:5]:
            body_lines.append(f"- {q}")
        body_lines.append("")

    if parsed["mistakes"]:
        body_lines.append("## Common Mistakes")
        body_lines.append("")
        for m in parsed["mistakes"][:5]:
            body_lines.append(f"- {m}")
        body_lines.append("")

    body_lines.append(f"*Source: Lenny Skills (MIT) -- {author_str} and others*")

    # Combine
    frontmatter_str = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
    body_str = "\n".join(body_lines)

    return f"---\n{frontmatter_str}---\n{body_str}\n"


def ingest_frameworks(
    bundle_path: Path,
    output_path: Path,
    dry_run: bool = False,
) -> List[Dict[str, str]]:
    """
    Ingest all framework files from bundle into Brain entities.

    Args:
        bundle_path: Path to frameworks_bundle/ directory
        output_path: Path to user/brain/Frameworks/ directory
        dry_run: If True, don't write files

    Returns:
        List of dicts with 'slug', 'name', 'path' for each ingested framework
    """
    if not bundle_path.exists():
        logger.error("Bundle path does not exist: %s", bundle_path)
        return []

    results = []
    md_files = sorted(bundle_path.glob("*.md"))

    if not md_files:
        logger.warning("No .md files found in %s", bundle_path)
        return []

    if not dry_run:
        output_path.mkdir(parents=True, exist_ok=True)

    for md_file in md_files:
        slug = md_file.stem
        content = md_file.read_text(encoding="utf-8")
        parsed = parse_skill_md(content)

        entity_name = slug_to_entity_name(slug)
        entity_md = build_entity_md(slug, parsed)
        out_file = output_path / f"{entity_name}.md"

        if not dry_run:
            out_file.write_text(entity_md, encoding="utf-8")

        results.append({
            "slug": slug,
            "name": parsed["title"] or slug_to_display_name(slug),
            "category": CATEGORY_MAP.get(slug, "strategy"),
            "path": str(out_file),
        })

        logger.info("%sIngested: %s -> %s", "[DRY] " if dry_run else "", slug, out_file.name)

    return results


def _resolve_default_paths() -> tuple:
    """Resolve default bundle and output paths via config."""
    try:
        from pm_os_base.tools.core.path_resolver import get_paths
        paths = get_paths()
        root = paths.root
    except ImportError:
        try:
            from core.path_resolver import get_paths
            paths = get_paths()
            root = paths.root
        except ImportError:
            root = Path(__file__).resolve().parent.parent.parent.parent.parent

    bundle_default = Path(__file__).parent / "frameworks_bundle"
    output_default = root / "user" / "brain" / "Frameworks"
    return bundle_default, output_default


def main():
    bundle_default, output_default = _resolve_default_paths()

    parser = argparse.ArgumentParser(description="Ingest Lenny Skills as Brain entities")
    parser.add_argument(
        "--bundle",
        type=Path,
        default=bundle_default,
        help="Path to vendored frameworks bundle",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=output_default,
        help="Output path for Brain entities",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    results = ingest_frameworks(args.bundle, args.output, args.dry_run)
    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Ingested {len(results)} frameworks")

    # Summary by category
    categories: Dict[str, int] = {}
    for r in results:
        cat = r["category"]
        categories[cat] = categories.get(cat, 0) + 1

    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
