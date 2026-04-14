#!/usr/bin/env python3
"""
PM-OS Interview Scorecard Generator (v5.0)

Generates structured interview scorecards from transcripts.
Supports single and batch generation, listing, and search.

Scorecard format: candidate info, competency ratings, verdict,
evidence-based assessment summary.

Usage:
    from pm_os_career.tools.interview_scorecard import InterviewScorecardGenerator
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# v5 shared utils
try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from config_loader import get_config

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from path_resolver import get_paths


# --- Data Classes ---

@dataclass
class Verdict:
    """Interview verdict with symbol and label."""
    symbol: str
    label: str

    STRONG_YES = None  # Set after class definition
    SOFT_YES = None
    SOFT_NO = None
    STRONG_NO = None


# Verdict constants
Verdict.STRONG_YES = Verdict("++", "Strong Yes")
Verdict.SOFT_YES = Verdict("+", "Soft Yes")
Verdict.SOFT_NO = Verdict("-", "Soft No")
Verdict.STRONG_NO = Verdict("--", "Strong No")

VERDICT_MAP = {
    "++": Verdict.STRONG_YES,
    "strong yes": Verdict.STRONG_YES,
    "+": Verdict.SOFT_YES,
    "soft yes": Verdict.SOFT_YES,
    "yes": Verdict.SOFT_YES,
    "-": Verdict.SOFT_NO,
    "soft no": Verdict.SOFT_NO,
    "no": Verdict.SOFT_NO,
    "--": Verdict.STRONG_NO,
    "strong no": Verdict.STRONG_NO,
}

DEFAULT_ASSESSMENT_DIMENSIONS = [
    "Systems Thinking",
    "Cross-Functional Influence",
    "Data Fluency",
    "Execution under Ambiguity",
    "Communication",
    "Customer Centricity",
    "AI Fluency",
]


@dataclass
class ScorecardInfo:
    """Parsed scorecard file metadata."""
    path: Path
    date: str
    candidates: List[str]
    role: str
    verdict: str


@dataclass
class ScorecardResult:
    """Result of scorecard generation."""
    success: bool
    path: Optional[str] = None
    candidate_name: str = ""
    role: str = ""
    verdict: str = ""
    transcript_found: bool = False
    error: Optional[str] = None


class InterviewScorecardGenerator:
    """Generates and manages interview scorecards."""

    def __init__(
        self,
        config: Optional[Any] = None,
        paths: Optional[Any] = None,
    ):
        self.config = config or get_config()
        self.paths = paths or get_paths()

    @property
    def manager_name(self) -> str:
        """Get hiring manager name from config."""
        return self.config.get("user.name", "")

    @property
    def interviews_dir(self) -> Path:
        """Get the interviews directory."""
        custom_path = self.config.get("team.scorecard_path")
        if custom_path:
            return Path(self.paths.user) / custom_path
        return Path(self.paths.user) / "team" / "recruiting" / "interviews"

    @property
    def assessment_dimensions(self) -> List[str]:
        """Get assessment dimensions from config or defaults."""
        configured = self.config.get("career.assessment_dimensions")
        if configured and isinstance(configured, list):
            return configured
        return DEFAULT_ASSESSMENT_DIMENSIONS

    def _slugify(self, text: str) -> str:
        """Convert text to a URL-friendly slug."""
        slug = text.lower().strip()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")

    def parse_verdict(self, verdict_str: str) -> Verdict:
        """Parse a verdict string into a Verdict object."""
        key = verdict_str.strip().lower()
        return VERDICT_MAP.get(key, Verdict.SOFT_YES)

    def generate_scorecard_markdown(
        self,
        candidate_name: str,
        role: str,
        verdict: Verdict,
        interview_date: str = "",
        duration_minutes: int = 0,
        transcript: str = "",
    ) -> str:
        """Generate the scorecard markdown content."""
        gen_date = datetime.now().strftime("%Y-%m-%d")
        if not interview_date:
            interview_date = gen_date

        duration_str = "~%d min" % duration_minutes if duration_minutes else "N/A"

        # Build assessment table
        dimension_rows = "\n".join(
            "| **%s** | | |" % dim for dim in self.assessment_dimensions
        )

        content = """# {role} Interview Scorecard — {candidate}

**Role:** {role}
**Hiring Manager Interview:** {manager}
**Date:** {gen_date}

---

## {candidate} — ({symbol})

**Interview Date:** {interview_date} | **Duration:** {duration} | **Verdict: {verdict_label}**

### Key Take-Aways

**Conclusions:**
- [Analysis paragraphs with specific examples from the interview]

**Pros:**
- **[Label]:** [Evidence-backed positive signal with specific examples]

**Cons:**
- **[Label]:** [Evidence-backed concern with specific examples]

**Follow-ups:**
- [ ] **Recommendation:** [Advance/Do not advance — with clear reasoning]
- [ ] [Specific validation items for next round]

---

## Assessment Summary

| Dimension | Rating | Notes |
|-----------|--------|-------|
{dimensions}

**Overall: ({symbol}) {verdict_label}** — [2-3 sentence summary anchoring strongest signal and biggest risk]

---

*Generated: {gen_date} | Source: {source}*
""".format(
            role=role,
            candidate=candidate_name,
            manager=self.manager_name,
            gen_date=gen_date,
            symbol=verdict.symbol,
            interview_date=interview_date,
            duration=duration_str,
            verdict_label=verdict.label,
            dimensions=dimension_rows,
            source="Interview transcript (%s)" % interview_date if transcript else "Manual entry",
        )

        return content

    def generate(
        self,
        candidate_name: str,
        role: str,
        verdict_str: str,
        interview_date: str = "",
        duration_minutes: int = 0,
        transcript: str = "",
    ) -> ScorecardResult:
        """Generate and save an interview scorecard."""
        verdict = self.parse_verdict(verdict_str)

        content = self.generate_scorecard_markdown(
            candidate_name=candidate_name,
            role=role,
            verdict=verdict,
            interview_date=interview_date,
            duration_minutes=duration_minutes,
            transcript=transcript,
        )

        # Build filename
        date_str = datetime.now().strftime("%Y-%m-%d")
        role_slug = self._slugify(role)
        candidate_slug = self._slugify(candidate_name)
        filename = "%s-%s-interview-scorecard-%s.md" % (date_str, role_slug, candidate_slug)

        # Ensure directory exists
        self.interviews_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.interviews_dir / filename
        file_path.write_text(content, encoding="utf-8")

        return ScorecardResult(
            success=True,
            path=str(file_path),
            candidate_name=candidate_name,
            role=role,
            verdict=verdict.label,
            transcript_found=bool(transcript),
        )

    def list_scorecards(self) -> List[ScorecardInfo]:
        """List all scorecards in the interviews directory."""
        if not self.interviews_dir.exists():
            return []

        scorecards = []
        for f in sorted(self.interviews_dir.glob("*scorecard*.md"), reverse=True):
            info = self._parse_scorecard_file(f)
            if info:
                scorecards.append(info)
        return scorecards

    def search_scorecards(self, query: str) -> List[ScorecardInfo]:
        """Search scorecards by content."""
        query_lower = query.lower()
        results = []

        if not self.interviews_dir.exists():
            return results

        for f in sorted(self.interviews_dir.glob("*.md"), reverse=True):
            try:
                content = f.read_text(encoding="utf-8").lower()
                if query_lower in content:
                    info = self._parse_scorecard_file(f)
                    if info:
                        results.append(info)
            except Exception:
                continue
        return results

    def _parse_scorecard_file(self, path: Path) -> Optional[ScorecardInfo]:
        """Parse metadata from a scorecard filename and content."""
        name = path.stem
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", name)
        date = date_match.group(1) if date_match else ""

        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return None

        # Extract candidates from headers
        candidates = re.findall(r"^## (.+?) — \(", content, re.MULTILINE)
        if not candidates:
            candidates = [name.split("scorecard-")[-1].replace("-", " ").title()]

        # Extract role
        role_match = re.search(r"\*\*Role:\*\*\s*(.+)", content)
        role = role_match.group(1).strip() if role_match else ""

        # Extract verdict
        verdict_match = re.search(r"\*\*Overall:.*?\((.+?)\)", content)
        verdict = verdict_match.group(1) if verdict_match else ""

        return ScorecardInfo(
            path=path,
            date=date,
            candidates=candidates,
            role=role,
            verdict=verdict,
        )


# --- CLI for testing ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    gen = InterviewScorecardGenerator()
    print("=== Interview Scorecard Generator ===")
    print("Manager: %s" % gen.manager_name)
    print("Interviews dir: %s" % gen.interviews_dir)
    print("Dimensions: %s" % gen.assessment_dimensions)

    existing = gen.list_scorecards()
    print("Existing scorecards: %d" % len(existing))
    for sc in existing[:5]:
        print("  %s | %s | %s" % (sc.date, ", ".join(sc.candidates), sc.verdict))
