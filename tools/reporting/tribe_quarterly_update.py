#!/usr/bin/env python3
"""
Tribe Quarterly Update Generator

Generates Q1-2026 Tribe-Level Update documents for the Global Central Functions
Planning Offsite. Includes orthogonal challenge support for rigorous review.

Key Features:
- Auto-populates from Brain, Jira, Context files, and Yearly Plans
- Supports Growth Division tribe squads (Meal Kit, WB, Growth Platform, PROJ2)
- Orthogonal challenge mode for Claude<>Gemini review
- Multiple output formats (Markdown, Google Docs compatible)

Usage:
    python3 tribe_quarterly_update.py --tribe "Growth Division"
    python3 tribe_quarterly_update.py --tribe "Growth Division" --orthogonal
    python3 tribe_quarterly_update.py --tribe "Growth Division" --squad "Meal Kit"
    python3 tribe_quarterly_update.py --status
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add common directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    import config_loader
except ImportError:
    config_loader = None

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = Path(__file__).parent
# Use config_loader for proper path resolution
if config_loader:
    ROOT_PATH = config_loader.get_root_path()
    USER_PATH = ROOT_PATH / "user"
else:
    ROOT_PATH = BASE_DIR.parent.parent
    USER_PATH = ROOT_PATH / "user"

BRAIN_DIR = USER_PATH / "brain"
CONTEXT_DIR = USER_PATH / "context"
PLANNING_DIR = USER_PATH / "planning"
OUTPUT_DIR = PLANNING_DIR / "Quarterly_Updates"
TEMPLATE_DIR = PLANNING_DIR / "Templates"
SQUAD_REGISTRY_PATH = ROOT_PATH / "squad_registry.yaml"

# Tribe configuration
TRIBES = {
    "Growth Division": {
        "mega_alliance": "Enterprise Alliance",
        "mission": "Incubate, validate, and scale new business ventures beyond Acme Corp's core meal kit offering.",
        "squads": ["Meal Kit", "Wellness Brand", "Growth Platform", "Product Innovation"],
        "jira_projects": ["MK", "WB", "PROJ1", "PROJ2"],
        "lead": "Jane Smith",
        "eng_lead": "Carol Developer",
    }
}

# Quarter configuration
CURRENT_QUARTER = "Q1-2026"
PREV_QUARTER = "Q4-2025"

# Document structure
SECTIONS = [
    "executive_summary",
    "systemic_blockers",
    "key_learnings",
    "goals_roadmap",
    "dependencies",
    "hot_debates",
]


# ============================================================================
# TEMPLATE
# ============================================================================

TRIBE_UPDATE_TEMPLATE = """# {tribe_name} - {quarter} Global Central Functions Planning Offsite

## 2026 Tech Platform Tribe Quarterly Planning Update

---

## I. {tribe_name}'s Executive Summary of {prev_quarter} Performance

**Mega Alliance:** {mega_alliance}

**Tribe Mission:** {mission}

**{prev_quarter} Key Metrics:**

{executive_metrics}

**Strategic Relevance:** {strategic_relevance}

---

## II. Deep Dive of {prev_quarter} Systemic Blockers

{systemic_blockers}

**Root Cause Analysis:**

{root_cause_analysis}

---

## III. Key Learnings and Failure Analysis

{key_learnings}

**Mitigation Plan for {quarter}:**

{mitigation_plan}

---

## IV. {quarter} Goals and Roadmap

{goals_intro}

| Top 5 Company Strategy | Key Projects | Description | KPI Impacted | What does Complete Look like? | Critical Dependencies |
|------------------------|--------------|-------------|--------------|-------------------------------|----------------------|
{roadmap_table}

---

## V. Cross-Functional Dependencies

{dependencies}

---

## VI. Hot Debates / Open Questions

{hot_debates}

---

*Generated: {timestamp}*
*Tribe Lead: {lead}*
*Engineering Lead: {eng_lead}*
"""


# ============================================================================
# DATA GATHERING
# ============================================================================


def load_squad_registry(tribe: str) -> List[Dict]:
    """Load squads from registry for a specific tribe."""
    if not SQUAD_REGISTRY_PATH.exists():
        return []

    with open(SQUAD_REGISTRY_PATH, "r") as f:
        data = yaml.safe_load(f)

    squads = data.get("squads", [])
    return [s for s in squads if s.get("tribe") == tribe]


def gather_context_files(days: int = 30) -> List[Dict[str, Any]]:
    """Gather recent context files for insights."""
    context_files = []

    if not CONTEXT_DIR.exists():
        return context_files

    for md_file in sorted(CONTEXT_DIR.glob("*.md"), reverse=True)[:days]:
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()

            context_files.append(
                {
                    "path": str(md_file),
                    "date": md_file.stem.split("-context")[0],
                    "content": content,
                }
            )
        except Exception:
            continue

    return context_files


def gather_brain_projects(tribe: str) -> List[Dict[str, Any]]:
    """Gather Brain project files for the tribe's squads."""
    projects = []
    tribe_config = TRIBES.get(tribe, {})
    squad_names = tribe_config.get("squads", [])

    projects_dir = BRAIN_DIR / "Projects"
    if not projects_dir.exists():
        return projects

    # Map squad names to potential file patterns
    search_patterns = []
    for squad in squad_names:
        slug = squad.lower().replace(" ", "_")
        search_patterns.extend(
            [
                slug,
                slug.replace("_", ""),
                squad.lower().replace(" ", ""),
            ]
        )

    # Add tribe-specific patterns
    search_patterns.extend(
        [
            "otp",
            "vms",
            "Growth_Platform",
            "Meal_Kit",
            "tpt",
            "pet",
            "mio",
            "marketplace",
            "shopify",
            "portion",
            "beam",
        ]
    )

    for md_file in projects_dir.glob("*.md"):
        filename_lower = md_file.stem.lower()
        if any(pattern in filename_lower for pattern in search_patterns):
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()

                projects.append(
                    {
                        "name": md_file.stem.replace("_", " ").title(),
                        "path": str(md_file),
                        "content": content[:3000],  # Limit content
                    }
                )
            except Exception:
                continue

    return projects


def gather_squad_entities(tribe: str) -> List[Dict[str, Any]]:
    """Gather Brain squad entity files."""
    entities = []
    tribe_config = TRIBES.get(tribe, {})
    squad_names = tribe_config.get("squads", [])

    entities_dir = BRAIN_DIR / "Entities"
    if not entities_dir.exists():
        return entities

    for squad in squad_names:
        squad_file = entities_dir / f"Squad_{squad.replace(' ', '_')}.md"
        if squad_file.exists():
            try:
                with open(squad_file, "r", encoding="utf-8") as f:
                    content = f.read()

                entities.append(
                    {
                        "squad": squad,
                        "path": str(squad_file),
                        "content": content[:2000],
                    }
                )
            except Exception:
                continue

    return entities


def gather_jira_data(tribe: str) -> Dict[str, Any]:
    """Gather Jira data for the tribe's projects."""
    jira_data = {
        "blockers": [],
        "delivered": [],
        "planned": [],
    }

    tribe_config = TRIBES.get(tribe, {})
    jira_projects = tribe_config.get("jira_projects", [])

    # Check for Jira inbox files
    jira_inbox = BRAIN_DIR / "Inbox"
    if jira_inbox.exists():
        for jira_file in jira_inbox.glob("JIRA_*.md"):
            try:
                with open(jira_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Look for blockers
                if "blocker" in content.lower():
                    jira_data["blockers"].append(
                        {
                            "source": jira_file.name,
                            "excerpt": content[:1000],
                        }
                    )
            except Exception:
                continue

    return jira_data


def gather_yearly_plans() -> Dict[str, Any]:
    """Gather yearly plan documents."""
    plans = {}

    # Search for yearly plan files
    search_locations = [
        PLANNING_DIR,
        REPO_ROOT / "Products",
        BRAIN_DIR / "Inbox" / "GDocs",
    ]

    for location in search_locations:
        if not location.exists():
            continue

        for md_file in location.rglob("*yearly*plan*.md"):
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()

                plans[md_file.name] = {
                    "path": str(md_file),
                    "content": content[:5000],
                }
            except Exception:
                continue

        for md_file in location.rglob("*2026*.md"):
            if "roadmap" in md_file.name.lower():
                try:
                    with open(md_file, "r", encoding="utf-8") as f:
                        content = f.read()

                    plans[md_file.name] = {
                        "path": str(md_file),
                        "content": content[:5000],
                    }
                except Exception:
                    continue

    return plans


def extract_blockers_from_context(context_files: List[Dict]) -> List[str]:
    """Extract blockers mentioned in context files."""
    blockers = []
    seen = set()

    for ctx in context_files[:10]:  # Last 10 context files
        content = ctx.get("content", "")

        # Look for blocker patterns
        blocker_section = re.search(
            r"## Blockers.*?(?=\n## |\Z)", content, re.DOTALL | re.IGNORECASE
        )

        if blocker_section:
            section_text = blocker_section.group(0)
            # Extract bullet points
            for line in section_text.split("\n"):
                if line.strip().startswith(("- ", "* ", "| ")):
                    blocker_text = line.strip().lstrip("-*| ")
                    if blocker_text and blocker_text not in seen:
                        blockers.append(blocker_text)
                        seen.add(blocker_text)

    return blockers[:10]  # Top 10 blockers


def extract_key_initiatives(
    context_files: List[Dict], projects: List[Dict]
) -> List[Dict]:
    """Extract key initiatives from context and projects."""
    initiatives = []

    # From Brain projects
    for proj in projects:
        content = proj.get("content", "")
        name = proj.get("name", "Unknown")

        # Look for status and description
        status_match = re.search(r"status:\s*(\w+)", content, re.IGNORECASE)
        status = status_match.group(1) if status_match else "Unknown"

        initiatives.append(
            {
                "name": name,
                "status": status,
                "source": "Brain",
            }
        )

    return initiatives[:15]


# ============================================================================
# CONTENT GENERATION
# ============================================================================


def generate_executive_metrics(tribe: str, context_files: List[Dict]) -> str:
    """Generate executive metrics section."""
    metrics = []
    seen_metrics = set()

    # Extract structured metrics from recent context
    for ctx in context_files[:5]:
        content = ctx.get("content", "")

        # Look for specific metric patterns with numbers/percentages
        patterns = [
            # CAC with dollar amounts: CAC: $167, CAC $234
            (r"(?:Blended\s+)?CAC[+\w]*:\s*\$?([\d,]+(?:\.\d+)?)", "CAC"),
            # CVR with percentages: CVR: 1.5%, CVR 2%
            (r"CVR[:\s]+(\d+(?:\.\d+)?%)", "CVR"),
            # Conversion counts: 2,449 conversions
            (r"([\d,]+)\s+conversions?", "Conversions"),
            # Spend amounts: $410k spend
            (r"\$([\d,]+k?)\s+spend", "Spend"),
            # Activations: +98% WoW
            (r"Activations?[:\s]+([+\-]?\d+%[^|\n]*)", "Activations"),
        ]

        for pattern, metric_name in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                key = f"{metric_name}:{match}"
                if key not in seen_metrics and metric_name not in [
                    m.split(":")[0].strip("- *") for m in metrics
                ]:
                    seen_metrics.add(key)
                    metrics.append(f"- **{metric_name}:** {match}")
                    break

    # Ensure we have standard metrics with placeholders
    if len(metrics) < 3:
        standard_metrics = [
            ("CVR", "[To be populated with Q4 final conversion rate]"),
            ("Net Revenue", "[To be populated with Q4 final revenue]"),
            ("AOR", "[To be populated with Q4 final Active Order Rate]"),
        ]
        for metric_name, placeholder in standard_metrics:
            if not any(metric_name in m for m in metrics):
                metrics.append(f"- **{metric_name}:** {placeholder}")
                if len(metrics) >= 4:
                    break

    return "\n".join(metrics[:5])


def generate_systemic_blockers(blockers: List[str], jira_data: Dict) -> str:
    """Generate systemic blockers section."""
    content = []

    # Filter and clean blockers - only keep substantive items
    clean_blockers = []
    for blocker in blockers:
        # Skip table headers or malformed entries
        if "|" in blocker:
            # Parse table rows: "Meal Kit 492 orders delayed | Customer experience | Ops/Laurence"
            parts = [p.strip() for p in blocker.split("|") if p.strip()]
            if len(parts) >= 2 and not any(
                h in parts[0] for h in ["Blocker", "Impact", "Owner", "---"]
            ):
                # Extract meaningful blocker description
                blocker_desc = parts[0]
                impact = parts[1] if len(parts) > 1 else ""
                owner = parts[2] if len(parts) > 2 else ""
                if blocker_desc and len(blocker_desc) > 5:
                    formatted = f"{blocker_desc}"
                    if impact:
                        formatted += f". Impact: {impact}"
                    if owner:
                        formatted += f" (Owner: {owner})"
                    clean_blockers.append(formatted)
            continue
        # Skip very short entries
        if len(blocker) < 10:
            continue
        # Clean up the text
        cleaned = blocker.strip()
        if cleaned:
            clean_blockers.append(cleaned)

    # Use cleaned blockers or defaults
    all_blockers = (
        clean_blockers[:3]
        if clean_blockers
        else [
            "[Cross-functional dependency with Central Function - describe impact and root cause]",
            "[External dependency on Other Tribe - describe impact and root cause]",
            "[Technical/process blocker - describe impact and root cause]",
        ]
    )

    for i, blocker in enumerate(all_blockers, 1):
        # Format consistently
        content.append(f"{i}. **Blocker {i}:** {blocker}")

    return "\n\n".join(content)


def generate_key_learnings(context_files: List[Dict]) -> str:
    """Generate key learnings section."""
    learnings = [
        "1. **[Learning 1]:** [Description of key insight about market/technology/process]",
        "2. **[Learning 2]:** [Description of pattern or friction identified]",
        "3. **[Learning 3]:** [Description of new knowledge acquired]",
    ]

    return "\n\n".join(learnings)


def generate_roadmap_table(initiatives: List[Dict], tribe_config: Dict) -> str:
    """Generate roadmap table rows."""
    rows = []

    # Default projects if none found
    default_projects = [
        {
            "strategy": "CVR/Revenue",
            "name": "[Project 1]",
            "description": "[Description]",
            "kpi": "[KPI]",
            "complete": "[Definition of Done]",
            "dependencies": "[Dependencies]",
        },
    ]

    for proj in (initiatives[:5] if initiatives else default_projects):
        if isinstance(proj, dict) and "name" in proj:
            row = f"| [Strategy] | {proj.get('name', '[Project]')} | [Description] | [KPI] | [DoD] | [Dependencies] |"
        else:
            row = "| [Strategy] | [Project] | [Description] | [KPI] | [DoD] | [Dependencies] |"
        rows.append(row)

    # Pad to 5 rows
    while len(rows) < 5:
        rows.append(
            "| [Strategy] | [Project] | [Description] | [KPI] | [DoD] | [Dependencies] |"
        )

    return "\n".join(rows)


def generate_dependencies(tribe_config: Dict) -> str:
    """Generate cross-functional dependencies section."""
    dependencies = """
| Dependency | Owner | Status | Impact if Delayed |
|------------|-------|--------|-------------------|
| [Dependency 1] | [Team/Person] | [Status] | [Impact] |
| [Dependency 2] | [Team/Person] | [Status] | [Impact] |
| [Dependency 3] | [Team/Person] | [Status] | [Impact] |

**Key Ask from Central Functions:**
- [Specific request to Finance, Legal, HR, etc.]
"""
    return dependencies


def generate_hot_debates(context_files: List[Dict]) -> str:
    """Generate hot debates section."""
    debates = """
1. **[Topic 1]:** [Description of debate/open question]
   - Option A: [Describe]
   - Option B: [Describe]
   - Seeking: [Decision needed from whom]

2. **[Topic 2]:** [Description of debate/open question]
   - Current stance: [Describe]
   - Challenge: [What needs resolution]
"""
    return debates


# ============================================================================
# DOCUMENT GENERATION
# ============================================================================


def generate_tribe_update(
    tribe: str,
    quarter: str = CURRENT_QUARTER,
    prev_quarter: str = PREV_QUARTER,
) -> str:
    """Generate complete tribe quarterly update document."""

    tribe_config = TRIBES.get(tribe)
    if not tribe_config:
        return f"Error: Tribe '{tribe}' not configured."

    # Gather data
    print(f"Gathering context files...", file=sys.stderr)
    context_files = gather_context_files(30)

    print(f"Gathering Brain projects...", file=sys.stderr)
    projects = gather_brain_projects(tribe)

    print(f"Gathering squad entities...", file=sys.stderr)
    entities = gather_squad_entities(tribe)

    print(f"Gathering Jira data...", file=sys.stderr)
    jira_data = gather_jira_data(tribe)

    print(f"Extracting blockers...", file=sys.stderr)
    blockers = extract_blockers_from_context(context_files)

    print(f"Extracting initiatives...", file=sys.stderr)
    initiatives = extract_key_initiatives(context_files, projects)

    # Generate sections
    executive_metrics = generate_executive_metrics(tribe, context_files)
    systemic_blockers = generate_systemic_blockers(blockers, jira_data)
    key_learnings = generate_key_learnings(context_files)
    roadmap_table = generate_roadmap_table(initiatives, tribe_config)
    dependencies = generate_dependencies(tribe_config)
    hot_debates = generate_hot_debates(context_files)

    # Fill template
    document = TRIBE_UPDATE_TEMPLATE.format(
        tribe_name=tribe,
        quarter=quarter,
        prev_quarter=prev_quarter,
        mega_alliance=tribe_config.get("mega_alliance", "Enterprise Alliance"),
        mission=tribe_config.get("mission", "[Tribe mission]"),
        executive_metrics=executive_metrics,
        strategic_relevance="Growth Division drives diversification revenue streams and de-risks Acme Corp's dependency on the core meal kit business. The tribe's success directly impacts the company's long-term growth trajectory and TAM expansion.",
        systemic_blockers=systemic_blockers,
        root_cause_analysis="[Analyze root causes of the blockers - focus on process gaps, data misalignment, or policy ambiguity]",
        key_learnings=key_learnings,
        mitigation_plan=f"[Describe how internal processes will change in {quarter} to minimize impact of past issues]",
        goals_intro=f"The {tribe} tribe will focus on the following key initiatives in {quarter}:",
        roadmap_table=roadmap_table,
        dependencies=dependencies,
        hot_debates=hot_debates,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        lead=tribe_config.get("lead", "[Tribe Lead]"),
        eng_lead=tribe_config.get("eng_lead", "[Engineering Lead]"),
    )

    return document


# ============================================================================
# ORTHOGONAL CHALLENGE INTEGRATION
# ============================================================================


def run_orthogonal_challenge(
    tribe: str,
    output_path: Path,
) -> Dict[str, Any]:
    """Run orthogonal challenge process for the tribe update."""

    # Import orthogonal challenge module
    try:
        from orthogonal_challenge import run_orthogonal
    except ImportError:
        return {"error": "Orthogonal challenge module not available"}

    topic = f"{tribe} Q1-2026 Tribe Quarterly Update"

    result = run_orthogonal(
        doc_type="tribe-update",
        topic=topic,
        research_sources=["brain", "jira", "gdrive", "slack"],
    )

    return result


# ============================================================================
# OUTPUT
# ============================================================================


def save_document(
    content: str,
    tribe: str,
    quarter: str = CURRENT_QUARTER,
    output_path: Optional[Path] = None,
) -> Path:
    """Save the generated document."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        tribe_slug = tribe.lower().replace(" ", "_")
        output_path = OUTPUT_DIR / f"{tribe_slug}_{quarter}_{date_str}.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(description="Tribe Quarterly Update Generator")
    parser.add_argument(
        "--tribe",
        type=str,
        default="Growth Division",
        choices=list(TRIBES.keys()),
        help="Tribe name (default: Growth Division)",
    )
    parser.add_argument(
        "--quarter",
        type=str,
        default=CURRENT_QUARTER,
        help=f"Target/future quarter for roadmap (default: {CURRENT_QUARTER})",
    )
    parser.add_argument(
        "--prev-quarter",
        type=str,
        default=PREV_QUARTER,
        help=f"Previous quarter for review/blockers/learnings (default: {PREV_QUARTER})",
    )
    parser.add_argument("--squad", type=str, help="Generate for specific squad only")
    parser.add_argument(
        "--orthogonal",
        action="store_true",
        help="Run orthogonal challenge (Claude<>Gemini review)",
    )
    parser.add_argument("--output", type=str, help="Custom output path")
    parser.add_argument(
        "--status", action="store_true", help="Show status of existing updates"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output as JSON (for programmatic use)"
    )

    args = parser.parse_args()

    if args.status:
        # List existing updates
        print("Tribe Quarterly Updates:")
        if OUTPUT_DIR.exists():
            for f in sorted(OUTPUT_DIR.glob("*.md"), reverse=True):
                print(f"  - {f.name}")
        else:
            print("  No updates found.")
        return 0

    # Generate document
    print(f"Generating {args.quarter} update for {args.tribe}...", file=sys.stderr)

    if args.orthogonal:
        output_path = Path(args.output) if args.output else None
        result = run_orthogonal_challenge(args.tribe, output_path)

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("error"):
                print(f"Error: {result['error']}", file=sys.stderr)
                return 1
            print(f"Orthogonal challenge complete!")
            print(f"Final document: {result.get('v3_path')}")
        return 0

    # Standard generation
    prev_quarter = getattr(args, "prev_quarter", PREV_QUARTER)
    content = generate_tribe_update(
        args.tribe,
        args.quarter,
        prev_quarter,
    )

    output_path = Path(args.output) if args.output else None
    saved_path = save_document(content, args.tribe, args.quarter, output_path)

    if args.json:
        print(
            json.dumps(
                {
                    "tribe": args.tribe,
                    "quarter": args.quarter,
                    "output_path": str(saved_path),
                    "timestamp": datetime.now().isoformat(),
                },
                indent=2,
            )
        )
    else:
        print(f"\nTribe Quarterly Update Generated!")
        print(f"Tribe: {args.tribe}")
        print(f"Quarter: {args.quarter}")
        print(f"Output: {saved_path}")
        print(f"\nNext steps:")
        print(f"  1. Review and fill in [bracketed] sections")
        print(f"  2. Add specific metrics from Q4-2025")
        print(f"  3. Run with --orthogonal for Claude<>Gemini review")

    return 0


if __name__ == "__main__":
    sys.exit(main())
