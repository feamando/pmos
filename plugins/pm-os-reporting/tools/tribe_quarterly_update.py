#!/usr/bin/env python3
"""
PM-OS Reporting Quarterly Update (v5.0)

Generates department-level quarterly update documents for planning offsites.
Auto-populates from Brain, Jira, context files, and yearly plans.
Supports orthogonal challenge for rigorous review.

Usage:
    from pm_os_reporting.tools.quarterly_update import QuarterlyUpdate
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# --- v5 imports ---
try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from core.config_loader import get_config

try:
    from pm_os_base.tools.core.connector_bridge import get_auth
except ImportError:
    from core.connector_bridge import get_auth

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# --- Optional: Brain for entity resolution ---
try:
    from pm_os_brain.tools.brain_core.brain_loader import BrainLoader

    HAS_BRAIN = True
except ImportError:
    try:
        from brain_core.brain_loader import BrainLoader

        HAS_BRAIN = True
    except ImportError:
        HAS_BRAIN = False

# --- Optional: CCE orthogonal challenge ---
try:
    from pm_os_cce.tools.reasoning.orthogonal_challenge import OrthogonalChallenge

    HAS_ORTHOGONAL = True
except ImportError:
    HAS_ORTHOGONAL = False


# ============================================================================
# Document Sections
# ============================================================================

SECTIONS = [
    "executive_summary",
    "systemic_blockers",
    "key_learnings",
    "goals_roadmap",
    "dependencies",
    "hot_debates",
]


# ============================================================================
# Template
# ============================================================================

QUARTERLY_UPDATE_TEMPLATE = """# {dept_name} - {quarter} Planning Update

## Quarterly Planning Update

---

## I. {dept_name}'s Executive Summary of {prev_quarter} Performance

**Division:** {division}

**Mission:** {mission}

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
*Department Lead: {lead}*
*Engineering Lead: {eng_lead}*
"""


# ============================================================================
# Generator
# ============================================================================


class QuarterlyUpdate:
    """Generates department-level quarterly update documents."""

    def __init__(self):
        self.paths = get_paths()
        self.config = get_config()

    # --- Config accessors ---

    def _get_dept_config(self, department: str) -> Dict[str, Any]:
        """Get department configuration from config.yaml.

        Department config lives under reporting.departments.<dept_slug>
        with keys: division, mission, teams, jira_projects, lead, eng_lead.
        """
        dept_slug = department.lower().replace(" ", "_")
        dept_config = self.config.get(
            f"reporting.departments.{dept_slug}", {}
        )

        if not dept_config:
            # Fallback: build minimal config from team registry
            teams = self._load_team_registry(department)
            team_names = [s["name"] for s in teams]
            jira_projects = [
                s["jira_project"] for s in teams if s.get("jira_project")
            ]
            user_name = self.config.get("user.name", "[Department Lead]")

            dept_config = {
                "division": self.config.get(
                    "reporting.division", "Division"
                ),
                "mission": f"[{department} mission — configure in reporting.departments.{dept_slug}.mission]",
                "teams": team_names,
                "jira_projects": jira_projects,
                "lead": user_name,
                "eng_lead": "[Engineering Lead]",
            }

        return dept_config

    def _get_available_departments(self) -> List[str]:
        """Get list of available departments from config or registry."""
        depts_config = self.config.get("reporting.departments", {})
        if depts_config:
            return list(depts_config.keys())

        # Fallback: derive from team registry
        registry_path = self.paths.root / "team_registry.yaml"
        if registry_path.exists() and YAML_AVAILABLE:
            with open(registry_path, "r") as f:
                data = yaml.safe_load(f)
            departments = set()
            for team in data.get("teams", data.get("squads", [])):
                dept = team.get("department", team.get("tribe"))
                if dept:
                    departments.add(dept)
            return sorted(departments)

        return []

    def _get_output_dir(self) -> Path:
        """Get quarterly update output directory."""
        output_dir = self.paths.user / "planning" / "Quarterly_Updates"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    # --- Data gathering ---

    def _load_team_registry(self, department: str) -> List[Dict]:
        """Load teams from registry for a specific department."""
        registry_path = self.paths.root / "team_registry.yaml"
        if not registry_path.exists() or not YAML_AVAILABLE:
            return []

        with open(registry_path, "r") as f:
            data = yaml.safe_load(f)

        teams = data.get("teams", data.get("squads", []))
        return [t for t in teams if t.get("department", t.get("tribe")) == department]

    def _gather_context_files(self, days: int = 30) -> List[Dict[str, Any]]:
        """Gather recent context files for insights."""
        context_dir = self.paths.user / "personal" / "context"
        if not context_dir.exists():
            # Fallback to legacy path
            context_dir = self.paths.user / "context"
        if not context_dir.exists():
            return []

        context_files = []
        for md_file in sorted(context_dir.glob("*.md"), reverse=True)[:days]:
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

    def _gather_brain_projects(self, dept_config: Dict) -> List[Dict[str, Any]]:
        """Gather Brain project files for the department's teams."""
        projects = []
        squad_names = dept_config.get("teams", dept_config.get("squads", []))

        projects_dir = self.paths.user / "brain" / "Projects"
        if not projects_dir.exists():
            return projects

        # Build search patterns from team names (config-driven)
        search_patterns = []
        for squad in squad_names:
            slug = squad.lower().replace(" ", "_")
            search_patterns.extend([slug, slug.replace("_", "")])

        # Add patterns from config
        extra_patterns = self.config.get(
            "reporting.brain_search_patterns", []
        )
        search_patterns.extend(extra_patterns)

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
                            "content": content[:3000],
                        }
                    )
                except Exception:
                    continue

        return projects

    def _gather_team_entities(self, dept_config: Dict) -> List[Dict[str, Any]]:
        """Gather Brain team entity files."""
        entities = []
        squad_names = dept_config.get("teams", dept_config.get("squads", []))

        entities_dir = self.paths.user / "brain" / "Entities"
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

    def _gather_jira_data(self, dept_config: Dict) -> Dict[str, Any]:
        """Gather Jira data for the department's projects."""
        jira_data: Dict[str, Any] = {
            "blockers": [],
            "delivered": [],
            "planned": [],
        }

        jira_inbox = self.paths.user / "brain" / "Inbox"
        if jira_inbox.exists():
            for jira_file in jira_inbox.glob("JIRA_*.md"):
                try:
                    with open(jira_file, "r", encoding="utf-8") as f:
                        content = f.read()
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

    def _gather_yearly_plans(self) -> Dict[str, Any]:
        """Gather yearly plan documents."""
        plans: Dict[str, Any] = {}

        search_locations = [
            self.paths.user / "planning",
            self.paths.user / "products",
            self.paths.user / "brain" / "Inbox" / "GDocs",
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

            for md_file in location.rglob("*roadmap*.md"):
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

    # --- Extraction helpers ---

    @staticmethod
    def _extract_blockers_from_context(
        context_files: List[Dict],
    ) -> List[str]:
        """Extract blockers mentioned in context files."""
        blockers = []
        seen: set = set()

        for ctx in context_files[:10]:
            content = ctx.get("content", "")
            blocker_section = re.search(
                r"## Blockers.*?(?=\n## |\Z)",
                content,
                re.DOTALL | re.IGNORECASE,
            )

            if blocker_section:
                section_text = blocker_section.group(0)
                for line in section_text.split("\n"):
                    if line.strip().startswith(("- ", "* ", "| ")):
                        blocker_text = line.strip().lstrip("-*| ")
                        if blocker_text and blocker_text not in seen:
                            blockers.append(blocker_text)
                            seen.add(blocker_text)

        return blockers[:10]

    @staticmethod
    def _extract_key_initiatives(
        context_files: List[Dict], projects: List[Dict]
    ) -> List[Dict]:
        """Extract key initiatives from context and projects."""
        initiatives = []

        for proj in projects:
            content = proj.get("content", "")
            name = proj.get("name", "Unknown")
            status_match = re.search(r"status:\s*(\w+)", content, re.IGNORECASE)
            status = status_match.group(1) if status_match else "Unknown"

            initiatives.append(
                {"name": name, "status": status, "source": "Brain"}
            )

        return initiatives[:15]

    # --- Section generators ---

    @staticmethod
    def _generate_executive_metrics(context_files: List[Dict]) -> str:
        """Generate executive metrics section from context."""
        metrics = []
        seen_metrics: set = set()

        patterns = [
            (r"(?:Blended\s+)?CAC[+\w]*:\s*\$?([\d,]+(?:\.\d+)?)", "CAC"),
            (r"CVR[:\s]+(\d+(?:\.\d+)?%)", "CVR"),
            (r"([\d,]+)\s+conversions?", "Conversions"),
            (r"\$([\d,]+k?)\s+spend", "Spend"),
            (r"Activations?[:\s]+([+\-]?\d+%[^|\n]*)", "Activations"),
        ]

        for ctx in context_files[:5]:
            content = ctx.get("content", "")
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

        if len(metrics) < 3:
            standard_metrics = [
                ("CVR", "[To be populated with final conversion rate]"),
                ("Net Revenue", "[To be populated with final revenue]"),
                ("AOR", "[To be populated with final Active Order Rate]"),
            ]
            for metric_name, placeholder in standard_metrics:
                if not any(metric_name in m for m in metrics):
                    metrics.append(f"- **{metric_name}:** {placeholder}")
                    if len(metrics) >= 4:
                        break

        return "\n".join(metrics[:5])

    @staticmethod
    def _generate_systemic_blockers(
        blockers: List[str], jira_data: Dict
    ) -> str:
        """Generate systemic blockers section."""
        clean_blockers = []
        for blocker in blockers:
            if "|" in blocker:
                parts = [p.strip() for p in blocker.split("|") if p.strip()]
                if len(parts) >= 2 and not any(
                    h in parts[0]
                    for h in ["Blocker", "Impact", "Owner", "---"]
                ):
                    blocker_desc = parts[0]
                    impact = parts[1] if len(parts) > 1 else ""
                    owner = parts[2] if len(parts) > 2 else ""
                    if blocker_desc and len(blocker_desc) > 5:
                        formatted = blocker_desc
                        if impact:
                            formatted += f". Impact: {impact}"
                        if owner:
                            formatted += f" (Owner: {owner})"
                        clean_blockers.append(formatted)
                continue
            if len(blocker) < 10:
                continue
            cleaned = blocker.strip()
            if cleaned:
                clean_blockers.append(cleaned)

        all_blockers = (
            clean_blockers[:3]
            if clean_blockers
            else [
                "[Cross-functional dependency — describe impact and root cause]",
                "[External dependency — describe impact and root cause]",
                "[Technical/process blocker — describe impact and root cause]",
            ]
        )

        content = []
        for i, blocker in enumerate(all_blockers, 1):
            content.append(f"{i}. **Blocker {i}:** {blocker}")

        return "\n\n".join(content)

    @staticmethod
    def _generate_key_learnings() -> str:
        """Generate key learnings section (template for manual fill)."""
        return "\n\n".join(
            [
                "1. **[Learning 1]:** [Description of key insight about market/technology/process]",
                "2. **[Learning 2]:** [Description of pattern or friction identified]",
                "3. **[Learning 3]:** [Description of new knowledge acquired]",
            ]
        )

    @staticmethod
    def _generate_roadmap_table(initiatives: List[Dict]) -> str:
        """Generate roadmap table rows."""
        rows = []
        for proj in initiatives[:5] if initiatives else []:
            if isinstance(proj, dict) and "name" in proj:
                row = (
                    f"| [Strategy] | {proj.get('name', '[Project]')} "
                    f"| [Description] | [KPI] | [DoD] | [Dependencies] |"
                )
            else:
                row = "| [Strategy] | [Project] | [Description] | [KPI] | [DoD] | [Dependencies] |"
            rows.append(row)

        while len(rows) < 5:
            rows.append(
                "| [Strategy] | [Project] | [Description] | [KPI] | [DoD] | [Dependencies] |"
            )

        return "\n".join(rows)

    @staticmethod
    def _generate_dependencies() -> str:
        """Generate cross-functional dependencies section."""
        return """
| Dependency | Owner | Status | Impact if Delayed |
|------------|-------|--------|-------------------|
| [Dependency 1] | [Team/Person] | [Status] | [Impact] |
| [Dependency 2] | [Team/Person] | [Status] | [Impact] |
| [Dependency 3] | [Team/Person] | [Status] | [Impact] |

**Key Ask from Central Functions:**
- [Specific request to Finance, Legal, HR, etc.]
"""

    @staticmethod
    def _generate_hot_debates() -> str:
        """Generate hot debates section."""
        return """
1. **[Topic 1]:** [Description of debate/open question]
   - Option A: [Describe]
   - Option B: [Describe]
   - Seeking: [Decision needed from whom]

2. **[Topic 2]:** [Description of debate/open question]
   - Current stance: [Describe]
   - Challenge: [What needs resolution]
"""

    # --- Main generation ---

    def generate(
        self,
        department: str,
        quarter: Optional[str] = None,
        prev_quarter: Optional[str] = None,
    ) -> str:
        """Generate complete quarterly update document."""
        dept_config = self._get_dept_config(department)

        # Derive quarter defaults from current date
        now = datetime.now()
        current_q = f"Q{(now.month - 1) // 3 + 1}-{now.year}"
        prev_q_num = ((now.month - 1) // 3)
        if prev_q_num == 0:
            prev_q = f"Q4-{now.year - 1}"
        else:
            prev_q = f"Q{prev_q_num}-{now.year}"

        quarter = quarter or current_q
        prev_quarter = prev_quarter or prev_q

        # Gather data
        logger.info("Gathering context files...")
        context_files = self._gather_context_files(30)

        logger.info("Gathering Brain projects...")
        projects = self._gather_brain_projects(dept_config)

        logger.info("Gathering team entities...")
        _entities = self._gather_team_entities(dept_config)

        logger.info("Gathering Jira data...")
        jira_data = self._gather_jira_data(dept_config)

        logger.info("Extracting blockers...")
        blockers = self._extract_blockers_from_context(context_files)

        logger.info("Extracting initiatives...")
        initiatives = self._extract_key_initiatives(context_files, projects)

        # Generate sections
        executive_metrics = self._generate_executive_metrics(context_files)
        systemic_blockers = self._generate_systemic_blockers(blockers, jira_data)
        key_learnings = self._generate_key_learnings()
        roadmap_table = self._generate_roadmap_table(initiatives)
        dependencies = self._generate_dependencies()
        hot_debates = self._generate_hot_debates()

        # Strategic relevance from config or placeholder
        strategic_relevance = dept_config.get(
            "strategic_relevance",
            f"[{department} strategic relevance — configure in reporting.departments config]",
        )

        # Fill template
        document = QUARTERLY_UPDATE_TEMPLATE.format(
            dept_name=department,
            quarter=quarter,
            prev_quarter=prev_quarter,
            division=dept_config.get("division", "Division"),
            mission=dept_config.get("mission", "[Department mission]"),
            executive_metrics=executive_metrics,
            strategic_relevance=strategic_relevance,
            systemic_blockers=systemic_blockers,
            root_cause_analysis="[Analyze root causes — focus on process gaps, data misalignment, or policy ambiguity]",
            key_learnings=key_learnings,
            mitigation_plan=f"[Describe how internal processes will change in {quarter} to minimize impact]",
            goals_intro=f"The {department} department will focus on the following key initiatives in {quarter}:",
            roadmap_table=roadmap_table,
            dependencies=dependencies,
            hot_debates=hot_debates,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
            lead=dept_config.get(
                "lead", self.config.get("user.name", "[Department Lead]")
            ),
            eng_lead=dept_config.get("eng_lead", "[Engineering Lead]"),
        )

        return document

    # --- Orthogonal challenge ---

    def run_orthogonal_challenge(
        self, department: str, output_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Run orthogonal challenge process for the quarterly update."""
        if not HAS_ORTHOGONAL:
            return {"error": "Orthogonal challenge module not available (pm-os-cce not installed)"}

        topic = f"{department} Quarterly Update"
        challenge = OrthogonalChallenge()
        result = challenge.run(
            doc_type="quarterly-update",
            topic=topic,
            research_sources=["brain", "jira", "gdrive", "slack"],
        )
        return result

    # --- Output ---

    def save_document(
        self,
        content: str,
        department: str,
        quarter: str,
        output_path: Optional[Path] = None,
    ) -> Path:
        """Save the generated document."""
        output_dir = self._get_output_dir()

        if output_path is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            dept_slug = department.lower().replace(" ", "_")
            output_path = output_dir / f"{dept_slug}_{quarter}_{date_str}.md"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return output_path

    # --- CLI entry point ---

    def run(
        self,
        department: Optional[str] = None,
        quarter: Optional[str] = None,
        prev_quarter: Optional[str] = None,
        orthogonal: bool = False,
        output: Optional[str] = None,
        as_json: bool = False,
    ) -> str:
        """Run the quarterly update generator.

        Args:
            department: Department name. Falls back to config default.
            quarter: Target quarter (e.g., "Q2-2026").
            prev_quarter: Previous quarter for review.
            orthogonal: Run orthogonal challenge.
            output: Custom output path.
            as_json: Return JSON output.
        """
        if department is None:
            department = self.config.get("reporting.default_department", "")
            if not department:
                available = self._get_available_departments()
                if available:
                    department = available[0]
                else:
                    return "Error: No department configured. Set reporting.default_department in config."

        if orthogonal:
            output_path = Path(output) if output else None
            result = self.run_orthogonal_challenge(department, output_path)
            if as_json:
                return json.dumps(result, indent=2)
            if result.get("error"):
                return f"Error: {result['error']}"
            return f"Orthogonal challenge complete! Final document: {result.get('v3_path')}"

        content = self.generate(department, quarter, prev_quarter)

        now = datetime.now()
        quarter = quarter or f"Q{(now.month - 1) // 3 + 1}-{now.year}"
        output_path = Path(output) if output else None
        saved_path = self.save_document(content, department, quarter, output_path)

        if as_json:
            return json.dumps(
                {
                    "department": department,
                    "quarter": quarter,
                    "output_path": str(saved_path),
                    "timestamp": datetime.now().isoformat(),
                },
                indent=2,
            )

        return (
            f"Quarterly Update Generated!\n"
            f"Department: {department}\n"
            f"Quarter: {quarter}\n"
            f"Output: {saved_path}\n\n"
            f"Next steps:\n"
            f"  1. Review and fill in [bracketed] sections\n"
            f"  2. Add specific metrics from previous quarter\n"
            f"  3. Run with orthogonal=True for review"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Quarterly Update Generator v5.0"
    )
    parser.add_argument("--department", type=str, help="Department name")
    parser.add_argument("--quarter", type=str, help="Target quarter (e.g., Q2-2026)")
    parser.add_argument("--prev-quarter", type=str, help="Previous quarter for review")
    parser.add_argument(
        "--orthogonal", action="store_true", help="Run orthogonal challenge"
    )
    parser.add_argument("--output", type=str, help="Custom output path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--status", action="store_true", help="Show existing updates"
    )
    args = parser.parse_args()

    updater = QuarterlyUpdate()

    if args.status:
        output_dir = updater._get_output_dir()
        print("Quarterly Updates:")
        if output_dir.exists():
            for f in sorted(output_dir.glob("*.md"), reverse=True):
                print(f"  - {f.name}")
        else:
            print("  No updates found.")
    else:
        result = updater.run(
            department=args.department,
            quarter=args.quarter,
            prev_quarter=args.prev_quarter,
            orthogonal=args.orthogonal,
            output=args.output,
            as_json=args.json,
        )
        print(result)
