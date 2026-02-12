#!/usr/bin/env python3
"""
PRD to Spec-Machine Bridge

Transforms PM-OS PRD output (including Orthogonal Challenge output) into
spec-machine's expected input format, bypassing the interactive /gather-requirements session.

Workflow:
    PM-OS Discovery → PRD Creation → Orthogonal Challenge → [THIS BRIDGE] → Spec-Machine

Usage:
    # Using repo alias from config
    python3 prd_to_spec.py --prd path/to/prd.md --spec-name feature --repo mobile-rn

    # Using explicit target path
    python3 prd_to_spec.py --prd path/to/prd.md --spec-name feature --target /path/to/repo

    # Interactive repo selection
    python3 prd_to_spec.py --prd path/to/prd.md --spec-name feature

    # Dry run
    python3 prd_to_spec.py --prd path/to/prd.md --spec-name feature --dry-run

Author: PM-OS Team
Version: 1.0.0
Beads: bd-cd39 (Epic), bd-2002 (Story)
"""

import argparse
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import config_loader

    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False


@dataclass
class PRDSection:
    """Represents a parsed PRD section."""

    name: str
    content: str
    subsections: Dict[str, str] = field(default_factory=dict)
    tables: List[str] = field(default_factory=list)


@dataclass
class ParsedPRD:
    """Complete parsed PRD structure."""

    title: str
    raw_content: str
    sections: Dict[str, PRDSection]
    metadata: Dict[str, str] = field(default_factory=dict)
    figma_links: List[str] = field(default_factory=list)


class PRDParser:
    """
    Parse PM-OS PRD markdown into structured sections.

    Handles both standard PRD output and Orthogonal Challenge v3_final.md format.
    """

    # Section patterns to look for (case-insensitive)
    SECTION_PATTERNS = [
        r"##?\s*\d*\.?\s*Purpose",
        r"##?\s*\d*\.?\s*Current State\s*/?\s*Problem",
        r"##?\s*\d*\.?\s*Strategic Solution",
        r"##?\s*\d*\.?\s*Business Impact",
        r"##?\s*\d*\.?\s*Technical Strategy",
        r"##?\s*\d*\.?\s*Recommendations",
        r"##?\s*\d*\.?\s*References",
        r"##?\s*\d*\.?\s*Out of Scope",
        r"##?\s*\d*\.?\s*Scope",
        r"##?\s*\d*\.?\s*Success Criteria",
        r"##?\s*\d*\.?\s*Risks",
        r"##?\s*\d*\.?\s*Dependencies",
        # Orthogonal challenge specific
        r"##?\s*Challenge FAQ",
        r"##?\s*Key Changes",
        r"##?\s*Decision Rationale",
    ]

    # Figma URL pattern
    FIGMA_PATTERN = r'https?://(?:www\.)?figma\.com/[^\s\)>\]"]+'

    def __init__(self, prd_path: Path):
        """Initialize parser with PRD file path."""
        self.prd_path = Path(prd_path)
        if not self.prd_path.exists():
            raise FileNotFoundError(f"PRD file not found: {prd_path}")

        self.raw_content = self.prd_path.read_text(encoding="utf-8")

    def parse(self) -> ParsedPRD:
        """Parse the PRD into structured format."""
        title = self._extract_title()
        metadata = self._extract_metadata()
        sections = self._extract_sections()
        figma_links = self._extract_figma_links()

        return ParsedPRD(
            title=title,
            raw_content=self.raw_content,
            sections=sections,
            metadata=metadata,
            figma_links=figma_links,
        )

    def _extract_title(self) -> str:
        """Extract document title from first H1."""
        match = re.search(r"^#\s+(.+?)(?:\n|$)", self.raw_content, re.MULTILINE)
        if match:
            # Clean up title (remove markdown formatting)
            title = match.group(1).strip()
            title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", title)  # Remove links
            return title
        return "Untitled PRD"

    def _extract_metadata(self) -> Dict[str, str]:
        """Extract metadata from frontmatter or header section."""
        metadata = {}

        # Check for YAML frontmatter
        if self.raw_content.startswith("---"):
            end_match = re.search(r"^---\s*$", self.raw_content[3:], re.MULTILINE)
            if end_match:
                frontmatter = self.raw_content[3 : end_match.start() + 3]
                for line in frontmatter.strip().split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip().lower()] = value.strip()

        # Extract inline metadata (Date:, Author:, Status:)
        for pattern in [
            r"\*\*Date:\*\*\s*(.+)",
            r"\*\*Author:\*\*\s*(.+)",
            r"\*\*Status:\*\*\s*(.+)",
        ]:
            match = re.search(pattern, self.raw_content)
            if match:
                key = pattern.split(":")[0].replace(r"\*\*", "").lower()
                metadata[key] = match.group(1).strip()

        return metadata

    def _extract_sections(self) -> Dict[str, PRDSection]:
        """Extract all sections from the PRD."""
        sections = {}

        # Build combined pattern
        all_patterns = "|".join(f"({p})" for p in self.SECTION_PATTERNS)
        section_regex = re.compile(all_patterns, re.IGNORECASE | re.MULTILINE)

        # Find all section headers
        matches = list(section_regex.finditer(self.raw_content))

        for i, match in enumerate(matches):
            header = match.group(0)
            start = match.end()

            # End is either next section or end of document
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(self.raw_content)

            content = self.raw_content[start:end].strip()

            # Normalize section name
            section_name = self._normalize_section_name(header)

            # Extract tables from content
            tables = self._extract_tables(content)

            # Extract subsections (###)
            subsections = self._extract_subsections(content)

            sections[section_name] = PRDSection(
                name=section_name,
                content=content,
                subsections=subsections,
                tables=tables,
            )

        return sections

    def _normalize_section_name(self, header: str) -> str:
        """Normalize section header to standard name."""
        # Remove markdown formatting and numbers
        name = re.sub(r"^#+\s*\d*\.?\s*", "", header).strip()

        # Map to standard names
        name_lower = name.lower()

        mappings = {
            "purpose": "purpose",
            "current state": "current_state",
            "problem": "current_state",
            "current state / problem": "current_state",
            "strategic solution": "solution",
            "solution": "solution",
            "business impact": "impact",
            "impact": "impact",
            "technical strategy": "technical",
            "technical": "technical",
            "recommendations": "recommendations",
            "references": "references",
            "out of scope": "out_of_scope",
            "scope": "scope",
            "success criteria": "success_criteria",
            "risks": "risks",
            "dependencies": "dependencies",
            "challenge faq": "challenge_faq",
            "key changes": "key_changes",
            "decision rationale": "decision_rationale",
        }

        for key, value in mappings.items():
            if key in name_lower:
                return value

        return name_lower.replace(" ", "_").replace("/", "_")

    def _extract_tables(self, content: str) -> List[str]:
        """Extract markdown tables from content."""
        tables = []
        # Match markdown tables (lines starting with |)
        table_pattern = r"(\|.+\|(?:\n\|.+\|)+)"
        for match in re.finditer(table_pattern, content):
            tables.append(match.group(1))
        return tables

    def _extract_subsections(self, content: str) -> Dict[str, str]:
        """Extract ### subsections from content."""
        subsections = {}
        pattern = r"###\s+(.+?)\n((?:(?!###).)*)"
        for match in re.finditer(pattern, content, re.DOTALL):
            name = match.group(1).strip()
            body = match.group(2).strip()
            subsections[name] = body
        return subsections

    def _extract_figma_links(self) -> List[str]:
        """Extract Figma URLs from content."""
        return re.findall(self.FIGMA_PATTERN, self.raw_content)


class QAGenerator:
    """
    Generate spec-machine Q&A format from parsed PRD sections.
    """

    # Q&A mapping: (question, source_sections, fallback)
    QA_TEMPLATE = [
        (
            "What problem does this solve?",
            ["current_state", "problem"],
            "Problem not specified in PRD.",
        ),
        ("What's the main user goal?", ["purpose"], "User goal not specified in PRD."),
        (
            "What's the proposed solution?",
            ["solution", "strategic_solution"],
            "Solution not specified in PRD.",
        ),
        (
            "What's the expected business impact?",
            ["impact", "business_impact"],
            "Business impact not specified in PRD.",
        ),
        (
            "What's the technical approach?",
            ["technical", "technical_strategy"],
            "Technical approach not specified in PRD.",
        ),
        (
            "What are the implementation priorities?",
            ["recommendations"],
            "Priorities not specified in PRD.",
        ),
        (
            "Are there existing patterns to reuse?",
            ["references", "dependencies"],
            "No references specified in PRD.",
        ),
        (
            "What's explicitly out of scope?",
            ["out_of_scope", "scope"],
            "Out of scope items not specified.",
        ),
    ]

    def __init__(self, parsed_prd: ParsedPRD):
        """Initialize with parsed PRD."""
        self.prd = parsed_prd

    def generate(self) -> str:
        """Generate Q&A markdown content."""
        lines = []

        for i, (question, sources, fallback) in enumerate(self.QA_TEMPLATE, 1):
            answer = self._get_answer(sources, fallback)
            lines.append(f"### Q{i}: {question}")
            lines.append(f"A: {answer}")
            lines.append("")

        return "\n".join(lines)

    def _get_answer(self, source_sections: List[str], fallback: str) -> str:
        """Get answer from first available source section."""
        for section_name in source_sections:
            if section_name in self.prd.sections:
                section = self.prd.sections[section_name]
                content = section.content

                # Include tables if present
                if section.tables:
                    content += "\n\n" + "\n\n".join(section.tables)

                # Clean up content
                content = self._clean_content(content)

                if content.strip():
                    return content

        return fallback

    def _clean_content(self, content: str) -> str:
        """Clean up content for Q&A format."""
        # Remove excessive blank lines
        content = re.sub(r"\n{3,}", "\n\n", content)

        # Limit length (spec-machine has context limits)
        max_length = 2000
        if len(content) > max_length:
            content = content[:max_length] + "\n\n[Content truncated for brevity...]"

        return content.strip()


class TechStackInjector:
    """
    Read and format tech-stack.md from target repository.
    """

    def __init__(self, target_repo: Path):
        """Initialize with target repository path."""
        self.target_repo = Path(target_repo)
        self.tech_stack_path = self.target_repo / "spec-machine" / "tech-stack.md"

    def get_tech_stack(self) -> Optional[str]:
        """Read and format tech stack content."""
        if not self.tech_stack_path.exists():
            return None

        content = self.tech_stack_path.read_text(encoding="utf-8")

        # Extract key sections
        sections = []
        for pattern in [
            r"##\s*Platform\s*\n(.*?)(?=##|$)",
            r"##\s*Language\s*\n(.*?)(?=##|$)",
            r"##\s*State\s*(?:Management)?\s*\n(.*?)(?=##|$)",
            r"##\s*UI\s*\n(.*?)(?=##|$)",
            r"##\s*Testing\s*\n(.*?)(?=##|$)",
        ]:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                section_content = match.group(1).strip()
                if section_content:
                    sections.append(section_content)

        if sections:
            return "\n".join(sections)

        # Fallback: return full content (trimmed)
        return content[:1500] if len(content) > 1500 else content

    def format_for_requirements(self, repo_name: str) -> str:
        """Format tech stack section for requirements.md."""
        tech_stack = self.get_tech_stack()

        if not tech_stack:
            return f"## Tech Stack Context\n*No tech-stack.md found in {repo_name}. Run /analyze-tech-stack in target repo.*\n"

        return f"""## Tech Stack Context
*Injected from target repository: {repo_name}*

{tech_stack}
"""


class SpecFolderCreator:
    """
    Create spec-machine folder structure with generated content.
    """

    def __init__(self, target_repo: Path, spec_name: str, subdir: Optional[str] = None):
        """
        Initialize folder creator.

        Args:
            target_repo: Path to target repository
            spec_name: Name for the spec (kebab-case)
            subdir: Optional subdirectory (e.g., 'meal-kit')
        """
        self.target_repo = Path(target_repo)
        self.spec_name = self._normalize_spec_name(spec_name)
        self.subdir = subdir

        # Build spec folder path
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        folder_name = f"{date_prefix}-{self.spec_name}"

        if subdir:
            self.spec_folder = (
                self.target_repo / "spec-machine" / "specs" / subdir / folder_name
            )
        else:
            self.spec_folder = self.target_repo / "spec-machine" / "specs" / folder_name

    def _normalize_spec_name(self, name: str) -> str:
        """Normalize spec name to kebab-case."""
        # Remove special characters, convert to lowercase
        name = re.sub(r"[^\w\s-]", "", name.lower())
        # Replace spaces with hyphens
        name = re.sub(r"[\s_]+", "-", name)
        # Remove multiple hyphens
        name = re.sub(r"-+", "-", name)
        return name.strip("-")

    def create_structure(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Create the folder structure.

        Args:
            dry_run: If True, only report what would be created

        Returns:
            Dict with created paths and status
        """
        result = {"spec_folder": str(self.spec_folder), "files": [], "dry_run": dry_run}

        # Define structure
        folders = [
            self.spec_folder / "planning",
            self.spec_folder / "planning" / "visuals",
            self.spec_folder / "implementation",
            self.spec_folder / "verification",
        ]

        if dry_run:
            result["folders"] = [str(f) for f in folders]
            return result

        # Create folders
        for folder in folders:
            folder.mkdir(parents=True, exist_ok=True)
            result["files"].append({"type": "folder", "path": str(folder)})

        return result

    def write_initialization(self, prd_title: str, prd_purpose: str) -> Path:
        """
        Write initialization.md file.

        Args:
            prd_title: Title from PRD
            prd_purpose: Purpose/description from PRD
        """
        content = f"""---
spec_name: {self.spec_name}
created: {datetime.now().strftime("%Y-%m-%d")}
source: pm-os-prd
---

# Initial Spec Idea

## User's Initial Description

{prd_purpose}

---

*Imported from PM-OS PRD: {prd_title}*
*Generated by prd_to_spec.py on {datetime.now().isoformat()}*
"""

        path = self.spec_folder / "planning" / "initialization.md"
        path.write_text(content, encoding="utf-8")
        return path

    def write_requirements(self, content: str) -> Path:
        """Write requirements.md file."""
        path = self.spec_folder / "planning" / "requirements.md"
        path.write_text(content, encoding="utf-8")
        return path


class PRDToSpecBridge:
    """
    Main bridge class that orchestrates the PRD to spec-machine transformation.
    """

    def __init__(
        self,
        prd_path: str,
        spec_name: str,
        target_repo: Optional[str] = None,
        repo_alias: Optional[str] = None,
        subdir: Optional[str] = None,
    ):
        """
        Initialize the bridge.

        Args:
            prd_path: Path to PRD file
            spec_name: Name for the generated spec
            target_repo: Explicit target repository path
            repo_alias: Repo alias from config (e.g., 'mobile-rn')
            subdir: Spec subdirectory (e.g., 'meal-kit')
        """
        self.prd_path = Path(prd_path)
        self.spec_name = spec_name
        self.subdir = subdir

        # Resolve target repo
        self.target_repo = self._resolve_target_repo(target_repo, repo_alias)
        self.repo_name = repo_alias or self.target_repo.name

        # Initialize components
        self.parser = PRDParser(self.prd_path)
        self.parsed_prd: Optional[ParsedPRD] = None

    def _resolve_target_repo(
        self, target_repo: Optional[str], repo_alias: Optional[str]
    ) -> Path:
        """Resolve target repository path from explicit path or config alias."""
        if target_repo:
            path = Path(target_repo).expanduser()
            if not path.exists():
                raise FileNotFoundError(f"Target repo not found: {target_repo}")
            return path

        if repo_alias and CONFIG_AVAILABLE:
            config = config_loader.get_config()
            repos = config.get("spec_machine.repos", {})
            if repo_alias in repos:
                path = Path(repos[repo_alias]).expanduser()
                if not path.exists():
                    raise FileNotFoundError(
                        f"Configured repo not found: {repos[repo_alias]}"
                    )
                return path
            raise ValueError(
                f"Unknown repo alias: {repo_alias}. Available: {list(repos.keys())}"
            )

        raise ValueError("Must specify --target or --repo")

    def transform(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Execute the full transformation.

        Args:
            dry_run: If True, only report what would be created

        Returns:
            Dict with transformation results
        """
        result = {
            "success": False,
            "prd_path": str(self.prd_path),
            "target_repo": str(self.target_repo),
            "spec_name": self.spec_name,
            "dry_run": dry_run,
            "files_created": [],
            "errors": [],
        }

        try:
            # Step 1: Parse PRD
            self.parsed_prd = self.parser.parse()
            result["prd_title"] = self.parsed_prd.title
            result["sections_found"] = list(self.parsed_prd.sections.keys())
            result["figma_links"] = self.parsed_prd.figma_links

            # Step 2: Create folder structure
            folder_creator = SpecFolderCreator(
                self.target_repo, self.spec_name, self.subdir
            )
            folder_result = folder_creator.create_structure(dry_run)
            result["spec_folder"] = folder_result["spec_folder"]

            if dry_run:
                result["would_create"] = folder_result.get("folders", [])
                result["success"] = True
                return result

            # Step 3: Generate and write initialization.md
            purpose_content = ""
            if "purpose" in self.parsed_prd.sections:
                purpose_content = self.parsed_prd.sections["purpose"].content

            init_path = folder_creator.write_initialization(
                self.parsed_prd.title, purpose_content
            )
            result["files_created"].append(str(init_path))

            # Step 4: Generate requirements.md
            requirements_content = self._generate_requirements()
            req_path = folder_creator.write_requirements(requirements_content)
            result["files_created"].append(str(req_path))

            result["success"] = True

        except Exception as e:
            result["errors"].append(str(e))

        return result

    def _generate_requirements(self) -> str:
        """Generate full requirements.md content."""
        if not self.parsed_prd:
            raise RuntimeError("PRD not parsed yet")

        lines = [
            f"# Requirements: {self.parsed_prd.title}",
            "",
            "---",
            "",
        ]

        # User's Description
        lines.append("## User's Description")
        lines.append("")
        if "purpose" in self.parsed_prd.sections:
            lines.append(self.parsed_prd.sections["purpose"].content)
        else:
            lines.append(self.parsed_prd.title)
        lines.append("")
        lines.append("---")
        lines.append("")

        # Q&A Section
        lines.append("## Questions & Answers")
        lines.append("")
        qa_generator = QAGenerator(self.parsed_prd)
        lines.append(qa_generator.generate())
        lines.append("---")
        lines.append("")

        # Tech Stack Context
        tech_injector = TechStackInjector(self.target_repo)
        lines.append(tech_injector.format_for_requirements(self.repo_name))
        lines.append("---")
        lines.append("")

        # Code Reuse Opportunities
        lines.append("## Code Reuse Opportunities")
        lines.append("")
        if "references" in self.parsed_prd.sections:
            lines.append(self.parsed_prd.sections["references"].content)
        else:
            lines.append(
                "*No specific references found in PRD. Spec-writer should analyze codebase.*"
            )
        lines.append("")
        lines.append("---")
        lines.append("")

        # Visual Assets
        lines.append("## Visual Assets")
        lines.append("")
        if self.parsed_prd.figma_links:
            lines.append("**Figma Links:**")
            for link in self.parsed_prd.figma_links:
                lines.append(f"- {link}")
        else:
            lines.append("*No Figma links found in PRD.*")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Out of Scope
        lines.append("## Out of Scope")
        lines.append("")
        if "out_of_scope" in self.parsed_prd.sections:
            lines.append(self.parsed_prd.sections["out_of_scope"].content)
        elif "scope" in self.parsed_prd.sections:
            # Try to extract "out of scope" from scope section
            scope_content = self.parsed_prd.sections["scope"].content
            if "out of scope" in scope_content.lower():
                lines.append(scope_content)
            else:
                lines.append("*No explicit out-of-scope items specified in PRD.*")
        else:
            lines.append("*No explicit out-of-scope items specified in PRD.*")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Metadata footer
        lines.append("## Import Metadata")
        lines.append("")
        lines.append(f"- **Source PRD:** {self.prd_path.name}")
        lines.append(f"- **Imported:** {datetime.now().isoformat()}")
        lines.append(f"- **Target Repo:** {self.repo_name}")
        if self.parsed_prd.metadata:
            for key, value in self.parsed_prd.metadata.items():
                lines.append(f"- **PRD {key.title()}:** {value}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*Generated by PM-OS prd_to_spec.py bridge*")

        return "\n".join(lines)


def get_available_repos() -> Dict[str, str]:
    """Get available repos from config."""
    if not CONFIG_AVAILABLE:
        return {}

    try:
        config = config_loader.get_config()
        return config.get("spec_machine.repos", {})
    except Exception:
        return {}


def interactive_repo_select() -> Tuple[str, str]:
    """
    Interactive repo selection.

    Returns:
        Tuple of (repo_alias, repo_path)
    """
    repos = get_available_repos()

    if not repos:
        print("No repositories configured in spec_machine.repos")
        print("Please specify --target explicitly or add repos to config.yaml")
        sys.exit(1)

    print("\nSelect target repository:")
    repo_list = list(repos.items())
    for i, (alias, path) in enumerate(repo_list, 1):
        print(f"  [{i}] {alias} ({path})")

    while True:
        try:
            choice = input(f"\nEnter choice [1-{len(repo_list)}]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(repo_list):
                return repo_list[idx]
            print(f"Invalid choice. Enter 1-{len(repo_list)}")
        except ValueError:
            print("Invalid input. Enter a number.")
        except KeyboardInterrupt:
            print("\nCancelled.")
            sys.exit(0)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Transform PM-OS PRD to spec-machine input format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using repo alias from config
  %(prog)s --prd path/to/prd.md --spec-name user-auth --repo mobile-rn

  # Using explicit target path
  %(prog)s --prd path/to/prd.md --spec-name user-auth --target ~/code/mobile-rn

  # Interactive repo selection
  %(prog)s --prd path/to/prd.md --spec-name user-auth

  # Dry run (preview only)
  %(prog)s --prd path/to/prd.md --spec-name user-auth --repo mobile-rn --dry-run
        """,
    )

    parser.add_argument("--prd", "-p", required=True, help="Path to PRD markdown file")
    parser.add_argument(
        "--spec-name",
        "-n",
        required=True,
        help="Name for the spec folder (will be kebab-cased)",
    )
    parser.add_argument(
        "--repo", "-r", help="Repository alias from config (e.g., 'mobile-rn')"
    )
    parser.add_argument("--target", "-t", help="Explicit target repository path")
    parser.add_argument("--subdir", "-s", help="Spec subdirectory (e.g., 'meal-kit')")
    parser.add_argument(
        "--dry-run",
        "-d",
        action="store_true",
        help="Preview changes without creating files",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    # Handle interactive repo selection
    repo_alias = args.repo
    target_repo = args.target

    if not repo_alias and not target_repo:
        repo_alias, target_repo = interactive_repo_select()

    try:
        bridge = PRDToSpecBridge(
            prd_path=args.prd,
            spec_name=args.spec_name,
            target_repo=target_repo,
            repo_alias=repo_alias,
            subdir=args.subdir,
        )

        result = bridge.transform(dry_run=args.dry_run)

        if args.json:
            import json

            print(json.dumps(result, indent=2))
        else:
            # Human-readable output
            if result["success"]:
                print(
                    f"\n✅ {'[DRY RUN] ' if args.dry_run else ''}PRD transformed successfully!"
                )
                print(f"\nPRD: {result['prd_title']}")
                print(f"Sections found: {', '.join(result['sections_found'])}")
                print(f"\nSpec folder: {result['spec_folder']}")

                if args.dry_run:
                    print("\nWould create:")
                    for folder in result.get("would_create", []):
                        print(f"  📁 {folder}")
                else:
                    print("\nFiles created:")
                    for f in result["files_created"]:
                        print(f"  📄 {f}")

                if result.get("figma_links"):
                    print(f"\nFigma links found: {len(result['figma_links'])}")

                print("\n📋 Next steps:")
                print(f"  1. cd {result['target_repo']}")
                print("  2. Review the generated requirements.md")
                print("  3. Run /create-spec to generate specification")
            else:
                print(f"\n❌ Transformation failed:")
                for error in result["errors"]:
                    print(f"  - {error}")
                sys.exit(1)

    except Exception as e:
        if args.json:
            import json

            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
